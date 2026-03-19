from __future__ import annotations
from datetime import datetime, timezone as tz

import asyncpg

from agent.classifier import TopicClassifier
from agent.config import Settings
from collections.abc import AsyncGenerator
from agent.executor import TopicExecutor, ExecutorResult, StreamChunk
from agent.history import truncate_history
from agent.models import Message, SessionState
from tools.datetime_tool import GetDateTimeTool
from tools.emit_event import EmitEventTool
from tools.knowledge import SearchKnowledgeTool
from tools.user_context import GetUserContextTool
from tools.create_case import CreateCaseTool
from tools.get_case import GetCaseTool
from tools.get_recent_cases import GetRecentCasesTool
from tools.perform_case_action import PerformCaseActionTool
from tools.validate_transfer import ValidateAndTransferTool
from tools.raise_flag import RaiseFlagTool
from tools.get_personalization import GetPersonalizationTool
from tools.registry import ToolRegistry
from topics.registry import get_default_registry


class _NoopSpan:
    def start_span(self, **kw):  # accepts name=, span_attributes=, etc.
        return _NoopSpan()

    def log(self, **kw):
        pass

    def end(self):
        pass

    def export(self):
        return ""


class Orchestrator:
    def __init__(self, settings: Settings, db_pool: asyncpg.Pool | None):
        self._settings = settings
        self._topic_registry = get_default_registry()
        self._tool_registry = self._build_tool_registry(settings, db_pool)
        self._classifier = TopicClassifier(settings=settings, topic_registry=self._topic_registry)
        self._executor = TopicExecutor(settings=settings, tool_registry=self._tool_registry)
        self._session_spans: dict[str, object] = {}

        # Try to init tracing, fall back to noop
        try:
            from tracing.braintrust import TracingManager
            self._tracing = TracingManager(
                project="sfdc-help-agent", api_key=settings.braintrust_api_key
            )
        except ImportError:
            self._tracing = None

    def _build_tool_registry(self, settings: Settings, pool: asyncpg.Pool | None) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(GetDateTimeTool())
        registry.register(EmitEventTool())
        registry.register(ValidateAndTransferTool())
        registry.register(RaiseFlagTool())
        registry.register(GetPersonalizationTool())
        if pool is not None:
            registry.register(GetUserContextTool(pool))
            registry.register(CreateCaseTool(pool))
            registry.register(GetCaseTool(pool))
            registry.register(GetRecentCasesTool(pool))
            registry.register(PerformCaseActionTool(pool))
            registry.register(SearchKnowledgeTool(
                pool=pool,
                gateway_base_url=settings.gateway_base_url,
                api_key=settings.braintrust_api_key,
                model=settings.embedding_model,
            ))
        return registry

    def _get_session_span(self, session: SessionState):
        if self._tracing is None:
            return _NoopSpan()
        if session.session_id not in self._session_spans:
            self._session_spans[session.session_id] = self._tracing.start_session(
                session.session_id
            )
        return self._session_spans[session.session_id]

    async def handle_message(self, user_message: str, session: SessionState) -> str:
        session_span = self._get_session_span(session)
        turn_span = session_span.start_span(name=f"turn.{session.turn_count}", span_attributes={"type": "task"})

        # Bootstrap: set timestamp on first turn
        if session.turn_count == 0:
            dt_tool = self._tool_registry.get("get_datetime")
            if dt_tool:
                result = await dt_tool.execute({}, session)
                session.session_timestamp = datetime.fromisoformat(result.output)

        # Truncate history before passing to LLM
        truncated_history = truncate_history(
            session.conversation_history,
            max_tokens=self._settings.history_token_limit,
            min_turns=self._settings.history_min_turns,
        )

        # Phase 1: Classify
        classify_span = turn_span.start_span(name="classify", span_attributes={"type": "task"})
        bt_header = classify_span.export()
        classify_headers = {"x-bt-parent": bt_header} if bt_header else None
        classify_result = await self._classifier.classify(
            user_message, truncated_history, extra_headers=classify_headers,
        )
        classify_span.log(
            input=user_message,
            output={"topic_id": classify_result.topic_id, "confidence": classify_result.confidence},
        )
        classify_span.end()

        topic_id = classify_result.topic_id
        topic = self._topic_registry.get(topic_id)
        if topic is None:
            topic = self._topic_registry.get("off_topic")
            topic_id = "off_topic"

        topic_changed = session.current_topic != topic_id
        session.current_topic = topic_id

        # Phase 2: Execute
        execute_span = turn_span.start_span(name="execute", span_attributes={"type": "task"})
        bt_header = execute_span.export()
        execute_headers = {"x-bt-parent": bt_header} if bt_header else None
        exec_result = await self._executor.execute(
            topic=topic,
            user_message=user_message,
            session=session,
            extra_headers=execute_headers,
            trace_span=execute_span,
        )
        execute_span.log(
            input=user_message,
            output=exec_result.response,
            metadata={"tool_calls_count": len(exec_result.tool_messages), "topic": topic_id},
        )
        execute_span.end()

        # Update session
        session.conversation_history.append(Message(role="user", content=user_message))
        for msg in exec_result.tool_messages:
            session.conversation_history.append(msg)
        session.conversation_history.append(Message(role="assistant", content=exec_result.response))
        session.turn_count += 1

        turn_span.log(
            input=user_message,
            output=exec_result.response,
            metadata={"topic": topic_id, "topic_changed": topic_changed},
        )
        turn_span.end()

        return exec_result.response

    async def handle_message_stream(
        self, user_message: str, session: SessionState
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streaming version of handle_message. Yields StreamChunks with tokens."""
        session_span = self._get_session_span(session)
        turn_span = session_span.start_span(name=f"turn.{session.turn_count}", span_attributes={"type": "task"})

        # Bootstrap: set timestamp on first turn
        if session.turn_count == 0:
            dt_tool = self._tool_registry.get("get_datetime")
            if dt_tool:
                result = await dt_tool.execute({}, session)
                session.session_timestamp = datetime.fromisoformat(result.output)

        # Truncate history
        truncated_history = truncate_history(
            session.conversation_history,
            max_tokens=self._settings.history_token_limit,
            min_turns=self._settings.history_min_turns,
        )

        # Phase 1: Classify (non-streaming, fast)
        yield StreamChunk(type="classify_start")

        classify_span = turn_span.start_span(name="classify", span_attributes={"type": "task"})
        bt_header = classify_span.export()
        classify_headers = {"x-bt-parent": bt_header} if bt_header else None
        classify_result = await self._classifier.classify(
            user_message, truncated_history, extra_headers=classify_headers,
        )
        classify_span.log(
            input=user_message,
            output={"topic_id": classify_result.topic_id, "confidence": classify_result.confidence},
        )
        classify_span.end()

        topic_id = classify_result.topic_id
        topic = self._topic_registry.get(topic_id)
        if topic is None:
            topic = self._topic_registry.get("off_topic")
            topic_id = "off_topic"

        topic_changed = session.current_topic != topic_id
        session.current_topic = topic_id

        yield StreamChunk(
            type="classify_end",
            topic_id=topic_id,
            confidence=classify_result.confidence,
        )

        # Phase 2: Execute (streaming)
        execute_span = turn_span.start_span(name="execute", span_attributes={"type": "task"})
        bt_header = execute_span.export()
        execute_headers = {"x-bt-parent": bt_header} if bt_header else None

        full_response = ""
        tool_messages: list[Message] = []

        async for chunk in self._executor.execute_stream(
            topic=topic,
            user_message=user_message,
            session=session,
            extra_headers=execute_headers,
            trace_span=execute_span,
        ):
            if chunk.type in ("token", "tool_start", "tool_end"):
                yield chunk
            elif chunk.type == "done":
                full_response = chunk.response
                tool_messages = chunk.tool_messages

        execute_span.log(
            input=user_message,
            output=full_response,
            metadata={"tool_calls_count": len(tool_messages), "topic": topic_id},
        )
        execute_span.end()

        # Update session
        session.conversation_history.append(Message(role="user", content=user_message))
        for msg in tool_messages:
            session.conversation_history.append(msg)
        session.conversation_history.append(Message(role="assistant", content=full_response))
        session.turn_count += 1

        turn_span.log(
            input=user_message,
            output=full_response,
            metadata={"topic": topic_id, "topic_changed": topic_changed},
        )
        turn_span.end()
