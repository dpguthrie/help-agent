import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.executor import TopicExecutor, ExecutorResult, StreamChunk
from agent.config import Settings
from agent.models import SessionState, Message
from topics.knowledge import KNOWLEDGE_FAQ
from topics.off_topic import OFF_TOPIC
from tools.base import ToolResult
from tools.registry import ToolRegistry


def _make_stream_chunks(content: str = "", tool_calls: list | None = None, finish_reason: str = "stop"):
    """Helper to create a mock async iterator that mimics OpenAI streaming."""
    chunks = []

    # Content tokens
    if content:
        for char in content:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = char
            chunk.choices[0].delta.tool_calls = None
            chunk.choices[0].finish_reason = None
            chunks.append(chunk)

    # Tool call deltas
    if tool_calls:
        for i, tc in enumerate(tool_calls):
            # First chunk: id + name
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = None
            tc_delta = MagicMock()
            tc_delta.index = i
            tc_delta.id = tc["id"]
            tc_delta.function = MagicMock()
            tc_delta.function.name = tc["name"]
            tc_delta.function.arguments = ""
            chunk.choices[0].delta.tool_calls = [tc_delta]
            chunk.choices[0].finish_reason = None
            chunks.append(chunk)

            # Second chunk: arguments
            chunk2 = MagicMock()
            chunk2.choices = [MagicMock()]
            chunk2.choices[0].delta = MagicMock()
            chunk2.choices[0].delta.content = None
            tc_delta2 = MagicMock()
            tc_delta2.index = i
            tc_delta2.id = None
            tc_delta2.function = MagicMock()
            tc_delta2.function.name = None
            tc_delta2.function.arguments = tc["arguments"]
            chunk2.choices[0].delta.tool_calls = [tc_delta2]
            chunk2.choices[0].finish_reason = None
            chunks.append(chunk2)

    # Final chunk with finish_reason
    final = MagicMock()
    final.choices = [MagicMock()]
    final.choices[0].delta = MagicMock()
    final.choices[0].delta.content = None
    final.choices[0].delta.tool_calls = None
    final.choices[0].finish_reason = finish_reason
    chunks.append(final)

    async def async_iter():
        for c in chunks:
            yield c

    return async_iter()


@pytest.fixture
def executor():
    settings = Settings(braintrust_api_key="test-key")
    registry = ToolRegistry()
    return TopicExecutor(settings=settings, tool_registry=registry)


@pytest.mark.asyncio
async def test_execute_no_tool_calls(executor):
    """Non-streaming execute() still works via streaming under the hood."""
    stream = _make_stream_chunks(content="I can help you with Salesforce questions.")

    with patch.object(executor._client.chat.completions, "create", new_callable=AsyncMock, return_value=stream):
        result = await executor.execute(
            topic=OFF_TOPIC,
            user_message="What's the weather?",
            session=SessionState(session_id="test"),
        )
    assert isinstance(result, ExecutorResult)
    assert "Salesforce" in result.response


@pytest.mark.asyncio
async def test_execute_with_tool_call(executor):
    """Tool call flow: stream tool call deltas, execute tool, stream final response."""
    tool_stream = _make_stream_chunks(
        tool_calls=[{"id": "call_123", "name": "search_knowledge", "arguments": json.dumps({"query": "password reset"})}],
        finish_reason="tool_calls",
    )
    final_stream = _make_stream_chunks(content="To reset your password, go to Settings.")

    executor._tool_registry.execute = AsyncMock(
        return_value=ToolResult(status="ok", output={"results": [{"chunk_text": "password reset steps"}]})
    )

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_stream, final_stream],
    ):
        result = await executor.execute(
            topic=KNOWLEDGE_FAQ,
            user_message="How do I reset my password?",
            session=SessionState(session_id="test"),
        )
    assert isinstance(result, ExecutorResult)
    assert "password" in result.response.lower() or "Settings" in result.response
    assert len(result.tool_messages) > 0


@pytest.mark.asyncio
async def test_execute_rejects_out_of_scope_tool(executor):
    """Out-of-scope tool call gets error, then LLM recovers in next stream."""
    tool_stream = _make_stream_chunks(
        tool_calls=[{"id": "call_456", "name": "create_case", "arguments": "{}"}],
        finish_reason="tool_calls",
    )
    final_stream = _make_stream_chunks(content="I can only search knowledge in this context.")

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_stream, final_stream],
    ):
        result = await executor.execute(
            topic=KNOWLEDGE_FAQ,
            user_message="create a case",
            session=SessionState(session_id="test"),
        )
    assert isinstance(result, ExecutorResult)
    assert result.response is not None
    assert len(result.response) > 0


@pytest.mark.asyncio
async def test_stream_yields_tokens(executor):
    """Streaming yields individual token chunks."""
    stream = _make_stream_chunks(content="Hello world")

    with patch.object(executor._client.chat.completions, "create", new_callable=AsyncMock, return_value=stream):
        tokens = []
        async for chunk in executor.execute_stream(
            topic=OFF_TOPIC,
            user_message="hi",
            session=SessionState(session_id="test"),
        ):
            if chunk.type == "token":
                tokens.append(chunk.token)
            elif chunk.type == "done":
                assert chunk.response == "Hello world"

        assert "".join(tokens) == "Hello world"


@pytest.mark.asyncio
async def test_stream_tool_call_then_tokens(executor):
    """Streaming: tool call phase (no tokens), then final response streams tokens."""
    tool_stream = _make_stream_chunks(
        tool_calls=[{"id": "call_1", "name": "search_knowledge", "arguments": json.dumps({"query": "test"})}],
        finish_reason="tool_calls",
    )
    final_stream = _make_stream_chunks(content="Here is the answer.")

    executor._tool_registry.execute = AsyncMock(
        return_value=ToolResult(status="ok", output={"results": []})
    )

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_stream, final_stream],
    ):
        tokens = []
        done_chunk = None
        async for chunk in executor.execute_stream(
            topic=KNOWLEDGE_FAQ,
            user_message="search something",
            session=SessionState(session_id="test"),
        ):
            if chunk.type == "token":
                tokens.append(chunk.token)
            elif chunk.type == "done":
                done_chunk = chunk

        assert "".join(tokens) == "Here is the answer."
        assert done_chunk is not None
        assert done_chunk.response == "Here is the answer."
        assert len(done_chunk.tool_messages) > 0
