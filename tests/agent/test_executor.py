import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.executor import TopicExecutor, ExecutorResult
from agent.config import Settings
from agent.models import SessionState, Message
from topics.knowledge import KNOWLEDGE_FAQ
from topics.off_topic import OFF_TOPIC
from tools.base import ToolResult
from tools.registry import ToolRegistry


@pytest.fixture
def executor():
    settings = Settings(braintrust_api_key="test-key")
    registry = ToolRegistry()
    return TopicExecutor(settings=settings, tool_registry=registry)


@pytest.mark.asyncio
async def test_execute_no_tool_calls(executor):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I can help you with Salesforce questions."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"

    session = SessionState(session_id="test")

    with patch.object(executor._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await executor.execute(
            topic=OFF_TOPIC,
            user_message="What's the weather?",
            session=session,
        )
    assert isinstance(result, ExecutorResult)
    assert "Salesforce" in result.response


@pytest.mark.asyncio
async def test_execute_with_tool_call(executor):
    tool_call_response = MagicMock()
    tool_call_response.choices = [MagicMock()]
    tool_call_response.choices[0].message.content = None
    tool_call_response.choices[0].message.tool_calls = [MagicMock()]
    tool_call_response.choices[0].message.tool_calls[0].id = "call_123"
    tool_call_response.choices[0].message.tool_calls[0].function.name = "search_knowledge"
    tool_call_response.choices[0].message.tool_calls[0].function.arguments = json.dumps({"query": "password reset"})
    tool_call_response.choices[0].finish_reason = "tool_calls"

    final_response = MagicMock()
    final_response.choices = [MagicMock()]
    final_response.choices[0].message.content = "To reset your password, go to Settings."
    final_response.choices[0].message.tool_calls = None
    final_response.choices[0].finish_reason = "stop"

    executor._tool_registry.execute = AsyncMock(
        return_value=ToolResult(status="ok", output={"results": [{"chunk_text": "password reset steps"}]})
    )

    session = SessionState(session_id="test")

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_call_response, final_response],
    ):
        result = await executor.execute(
            topic=KNOWLEDGE_FAQ,
            user_message="How do I reset my password?",
            session=session,
        )
    assert isinstance(result, ExecutorResult)
    assert "password" in result.response.lower() or "Settings" in result.response
    assert len(result.tool_messages) > 0


@pytest.mark.asyncio
async def test_execute_rejects_out_of_scope_tool(executor):
    tool_call_response = MagicMock()
    tool_call_response.choices = [MagicMock()]
    tool_call_response.choices[0].message.content = None
    tool_call_response.choices[0].message.tool_calls = [MagicMock()]
    tool_call_response.choices[0].message.tool_calls[0].id = "call_456"
    tool_call_response.choices[0].message.tool_calls[0].function.name = "create_case"
    tool_call_response.choices[0].message.tool_calls[0].function.arguments = "{}"
    tool_call_response.choices[0].finish_reason = "tool_calls"

    final_response = MagicMock()
    final_response.choices = [MagicMock()]
    final_response.choices[0].message.content = "I can only search knowledge in this context."
    final_response.choices[0].message.tool_calls = None
    final_response.choices[0].finish_reason = "stop"

    session = SessionState(session_id="test")

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_call_response, final_response],
    ):
        result = await executor.execute(
            topic=KNOWLEDGE_FAQ,
            user_message="create a case",
            session=session,
        )
    assert isinstance(result, ExecutorResult)
    assert result.response is not None
