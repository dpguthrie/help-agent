from __future__ import annotations
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from agent.config import Settings
from agent.models import SessionState, Message
from tools.registry import ToolRegistry
from topics.base import Topic


MAX_TOOL_ROUNDS = 5


@dataclass
class ExecutorResult:
    response: str
    tool_messages: list[Message] = field(default_factory=list)


class TopicExecutor:
    def __init__(self, settings: Settings, tool_registry: ToolRegistry):
        self._settings = settings
        self._tool_registry = tool_registry
        self._client = AsyncOpenAI(
            base_url=settings.gateway_base_url,
            api_key=settings.braintrust_api_key,
        )

    def _build_messages(
        self, topic: Topic, user_message: str, session: SessionState
    ) -> list[dict]:
        system = (
            f"You are a Salesforce help agent operating in the '{topic.name}' topic.\n\n"
            f"{topic.instructions}\n\n"
            "Respond in the same language the user writes in. Be concise and helpful."
        )

        messages: list[dict] = [{"role": "system", "content": system}]

        for msg in session.conversation_history:
            m = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            messages.append(m)

        messages.append({"role": "user", "content": user_message})
        return messages

    async def execute(
        self,
        topic: Topic,
        user_message: str,
        session: SessionState,
        extra_headers: dict | None = None,
        trace_span: object | None = None,
    ) -> ExecutorResult:
        """Non-streaming execution. Returns complete result."""
        full_response = ""
        tool_messages: list[Message] = []

        async for chunk in self.execute_stream(
            topic=topic,
            user_message=user_message,
            session=session,
            extra_headers=extra_headers,
            trace_span=trace_span,
        ):
            if chunk.type == "token":
                full_response += chunk.token
            elif chunk.type == "tool_messages":
                tool_messages = chunk.tool_messages
            elif chunk.type == "done":
                full_response = chunk.response
                tool_messages = chunk.tool_messages

        return ExecutorResult(response=full_response, tool_messages=tool_messages)

    async def execute_stream(
        self,
        topic: Topic,
        user_message: str,
        session: SessionState,
        extra_headers: dict | None = None,
        trace_span: object | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streaming execution. Yields tokens as they arrive, handles tool calls internally."""
        messages = self._build_messages(topic, user_message, session)
        tools = self._tool_registry.get_openai_tool_schemas(topic.tools) or None
        tool_messages: list[Message] = []
        full_response = ""

        for _ in range(MAX_TOOL_ROUNDS):
            stream = await self._client.chat.completions.create(
                model=self._settings.executor_model,
                temperature=self._settings.executor_temperature,
                max_tokens=self._settings.executor_max_tokens,
                messages=messages,
                tools=tools if tools else None,
                stream=True,
                **({"extra_headers": extra_headers} if extra_headers else {}),
            )

            # Accumulate the streamed response
            content_parts: list[str] = []
            tool_call_deltas: dict[int, dict] = {}  # index -> {id, name, arguments}
            finish_reason = None

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                finish_reason = chunk.choices[0].finish_reason or finish_reason

                # Content tokens
                if delta.content:
                    content_parts.append(delta.content)
                    yield StreamChunk(type="token", token=delta.content)

                # Tool call deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_deltas:
                            tool_call_deltas[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_call_deltas[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_call_deltas[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_call_deltas[idx]["arguments"] += tc_delta.function.arguments

            content = "".join(content_parts)

            # No tool calls - we're done
            if not tool_call_deltas:
                full_response = content
                yield StreamChunk(type="done", response=full_response, tool_messages=tool_messages)
                return

            # Process tool calls (non-streaming phase)
            assembled_tool_calls = [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in sorted(tool_call_deltas.values(), key=lambda t: t["id"])
            ]

            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": assembled_tool_calls,
            }
            messages.append(assistant_msg)
            tool_messages.append(Message(
                role="assistant",
                content=content or "",
                tool_calls=assembled_tool_calls,
            ))

            for tc in assembled_tool_calls:
                tool_name = tc["function"]["name"]

                if tool_name not in topic.tools:
                    error_content = json.dumps({
                        "error": f"Tool '{tool_name}' is not available in the current topic ({topic.id}). Available tools: {topic.tools}"
                    })
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": error_content})
                    tool_messages.append(Message(role="tool", content=error_content, tool_call_id=tc["id"], name=tool_name))
                    continue

                try:
                    params = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    params = {}

                yield StreamChunk(type="tool_start", tool_name=tool_name, tool_input=params)

                tool_span = None
                if trace_span:
                    tool_span = trace_span.start_span(name=f"tool_call.{tool_name}", span_attributes={"type": "tool"})

                result = await self._tool_registry.execute(tool_name, params, session)

                if tool_span:
                    tool_span.log(input=params, output=result.output, metrics={"latency_ms": result.latency_ms})
                    tool_span.end()

                result_content = json.dumps(result.output) if isinstance(result.output, dict) else str(result.output)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_content})
                tool_messages.append(Message(role="tool", content=result_content, tool_call_id=tc["id"], name=tool_name))

                yield StreamChunk(type="tool_end", tool_name=tool_name, tool_output=result_content[:200])

            # Loop back for the next LLM call (post-tool-execution), which will stream the final response

        full_response = "I'm having trouble completing this request. Please try again."
        yield StreamChunk(type="done", response=full_response, tool_messages=tool_messages)


@dataclass
class StreamChunk:
    type: str  # "token", "done", "classify_start", "classify_end", "tool_start", "tool_end"
    token: str = ""
    response: str = ""
    tool_messages: list[Message] = field(default_factory=list)
    # For classify events
    topic_id: str = ""
    confidence: float = 0.0
    # For tool events
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_output: str = ""
