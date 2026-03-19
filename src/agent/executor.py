from __future__ import annotations
import json
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
        messages = self._build_messages(topic, user_message, session)
        tools = self._tool_registry.get_openai_tool_schemas(topic.tools) or None
        tool_messages: list[Message] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self._client.chat.completions.create(
                model=self._settings.executor_model,
                temperature=self._settings.executor_temperature,
                max_tokens=self._settings.executor_max_tokens,
                messages=messages,
                tools=tools if tools else None,
                **({"extra_headers": extra_headers} if extra_headers else {}),
            )

            choice = response.choices[0]

            if choice.finish_reason == "stop" or not choice.message.tool_calls:
                return ExecutorResult(response=choice.message.content or "", tool_messages=tool_messages)

            assistant_tc_msg = {
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.message.tool_calls
                ],
            }
            messages.append(assistant_tc_msg)
            tool_messages.append(Message(
                role="assistant",
                content=choice.message.content or "",
                tool_calls=assistant_tc_msg["tool_calls"],
            ))

            for tc in choice.message.tool_calls:
                tool_name = tc.function.name

                if tool_name not in topic.tools:
                    error_content = json.dumps({
                        "error": f"Tool '{tool_name}' is not available in the current topic ({topic.id}). Available tools: {topic.tools}"
                    })
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": error_content})
                    tool_messages.append(Message(role="tool", content=error_content, tool_call_id=tc.id, name=tool_name))
                    continue

                try:
                    params = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    params = {}

                tool_span = None
                if trace_span:
                    tool_span = trace_span.start_span(name=f"tool_call.{tool_name}")

                result = await self._tool_registry.execute(tool_name, params, session)

                if tool_span:
                    tool_span.log(input=params, output=result.output, metrics={"latency_ms": result.latency_ms})
                    tool_span.end()

                result_content = json.dumps(result.output) if isinstance(result.output, dict) else str(result.output)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_content})
                tool_messages.append(Message(role="tool", content=result_content, tool_call_id=tc.id, name=tool_name))

        return ExecutorResult(
            response="I'm having trouble completing this request. Please try again.",
            tool_messages=tool_messages,
        )
