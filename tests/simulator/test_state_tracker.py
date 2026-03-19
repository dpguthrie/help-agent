import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from simulator.state_tracker import update_state
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
async def test_update_state_advancing(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({
            "goal_progress": "advancing",
            "frustration": 0.1,
            "should_end": False,
            "end_reason": None,
            "next_behavior": "provide_info",
        })))]
    )
    persona = PERSONA_TEMPLATES[0]
    current = ConversationState(goal_progress="not_started", frustration=0.0, turns_taken=0)
    result = await update_state(
        mock_client, "gpt-5-nano", persona, "test scenario", current, "Here's how to do that..."
    )
    assert result.goal_progress == "advancing"
    assert result.turns_taken == 1
    assert not result.should_end


@pytest.mark.asyncio
async def test_update_state_achieved(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({
            "goal_progress": "achieved",
            "frustration": 0.0,
            "should_end": True,
            "end_reason": "goal_achieved",
            "next_behavior": "say_thanks",
        })))]
    )
    persona = PERSONA_TEMPLATES[0]
    current = ConversationState(goal_progress="advancing", frustration=0.1, turns_taken=3)
    result = await update_state(
        mock_client, "gpt-5-nano", persona, "test scenario", current, "Your case has been created."
    )
    assert result.goal_progress == "achieved"
    assert result.should_end
    assert result.end_reason == "goal_achieved"


@pytest.mark.asyncio
async def test_update_state_max_turns(mock_client):
    persona = PERSONA_TEMPLATES[0]
    current = ConversationState(goal_progress="stalled", frustration=0.8, turns_taken=9)
    result = await update_state(
        mock_client, "gpt-5-nano", persona, "test scenario", current, "response", max_turns=10
    )
    assert result.should_end
    assert result.end_reason == "max_turns"
    # LLM should NOT have been called (max turns short-circuits)
    mock_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_update_state_bad_json_fallback(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="not json"))]
    )
    persona = PERSONA_TEMPLATES[0]
    current = ConversationState(goal_progress="advancing", frustration=0.3, turns_taken=2)
    result = await update_state(
        mock_client, "gpt-5-nano", persona, "test scenario", current, "some response"
    )
    # Should fallback gracefully: increment frustration, keep going
    assert result.turns_taken == 3
    assert result.frustration == pytest.approx(0.4, abs=0.01)
    assert not result.should_end
