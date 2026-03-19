import pytest
from unittest.mock import AsyncMock
from agent.orchestrator import Orchestrator
from agent.executor import ExecutorResult
from agent.config import Settings
from agent.models import SessionState, ClassifierResult, Message


@pytest.fixture
def orchestrator():
    settings = Settings(braintrust_api_key="test-key")
    orch = Orchestrator(settings=settings, db_pool=None)
    return orch


@pytest.mark.asyncio
async def test_first_turn_runs_bootstrap(orchestrator):
    orchestrator._classifier.classify = AsyncMock(
        return_value=ClassifierResult(topic_id="knowledge_faq", confidence=0.9)
    )
    orchestrator._executor.execute = AsyncMock(
        return_value=ExecutorResult(response="Here's the answer.")
    )

    session = SessionState(session_id="test")
    response = await orchestrator.handle_message("How do I reset my password?", session)

    assert session.turn_count == 1
    assert response == "Here's the answer."


@pytest.mark.asyncio
async def test_topic_reclassification(orchestrator):
    session = SessionState(session_id="test", current_topic="knowledge_faq", turn_count=1)

    orchestrator._classifier.classify = AsyncMock(
        return_value=ClassifierResult(topic_id="case_creation", confidence=0.9)
    )
    orchestrator._executor.execute = AsyncMock(
        return_value=ExecutorResult(response="Let's create a case.")
    )

    await orchestrator.handle_message("I want to create a case", session)
    assert session.current_topic == "case_creation"


@pytest.mark.asyncio
async def test_conversation_history_updated(orchestrator):
    session = SessionState(session_id="test")
    orchestrator._classifier.classify = AsyncMock(
        return_value=ClassifierResult(topic_id="knowledge_faq", confidence=0.9)
    )
    orchestrator._executor.execute = AsyncMock(
        return_value=ExecutorResult(response="The answer is 42.")
    )

    await orchestrator.handle_message("What is the answer?", session)

    assert len(session.conversation_history) == 2
    assert session.conversation_history[0].role == "user"
    assert session.conversation_history[1].role == "assistant"


@pytest.mark.asyncio
async def test_tool_messages_persisted_in_history(orchestrator):
    session = SessionState(session_id="test")
    orchestrator._classifier.classify = AsyncMock(
        return_value=ClassifierResult(topic_id="knowledge_faq", confidence=0.9)
    )
    tool_msg = Message(role="tool", content='{"results": []}', tool_call_id="call_1", name="search_knowledge")
    orchestrator._executor.execute = AsyncMock(
        return_value=ExecutorResult(response="No results found.", tool_messages=[tool_msg])
    )

    await orchestrator.handle_message("search for something", session)

    assert len(session.conversation_history) == 3
    assert session.conversation_history[1].role == "tool"
