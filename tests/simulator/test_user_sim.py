import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from simulator.user_sim import generate_scenario, generate_user_message
from simulator.personas import PERSONA_TEMPLATES
from simulator.state import ConversationState


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_generate_scenario(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({
            "scenario_description": "Admin can't get report subscriptions working",
            "opening_message": "My report subscriptions aren't sending emails",
            "expected_resolution": "knowledge_answer",
        })))]
    )
    persona = PERSONA_TEMPLATES[0]
    result = await generate_scenario(mock_client, "gpt-5-nano", persona)
    assert "scenario_description" in result
    assert "opening_message" in result
    assert "expected_resolution" in result


@pytest.mark.asyncio
async def test_generate_scenario_handles_bad_json(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="not json at all"))]
    )
    persona = PERSONA_TEMPLATES[0]
    result = await generate_scenario(mock_client, "gpt-5-nano", persona)
    assert "opening_message" in result  # should fallback


@pytest.mark.asyncio
async def test_generate_user_message(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Yes, I've already tried that"))]
    )
    persona = PERSONA_TEMPLATES[0]
    state = ConversationState(goal_progress="advancing", frustration=0.2, next_behavior="answer_question")
    history = [{"role": "user", "content": "help"}, {"role": "assistant", "content": "How can I help?"}]
    msg = await generate_user_message(mock_client, "gpt-5-nano", persona, "test scenario", state, history)
    assert isinstance(msg, str)
    assert len(msg) > 0
