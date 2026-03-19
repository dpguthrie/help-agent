import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from simulator.runner import run_conversation
from simulator.personas import PERSONA_TEMPLATES
from simulator.state import ConversationState
from agent.models import SessionState, AuthState


@pytest.mark.asyncio
async def test_run_conversation_completes():
    persona = PERSONA_TEMPLATES[0]  # admin_how_to

    mock_orchestrator = MagicMock()
    mock_orchestrator.handle_message = AsyncMock(return_value="Here's your answer.")

    mock_sim_client = MagicMock()
    mock_sim_client.chat = MagicMock()
    mock_sim_client.chat.completions = MagicMock()
    mock_sim_client.chat.completions.create = AsyncMock()

    scenario_response = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
        "scenario_description": "Admin needs help with reports",
        "opening_message": "How do I create a custom report?",
        "expected_resolution": "knowledge_answer",
    })))])

    state_advancing = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
        "goal_progress": "advancing", "frustration": 0.1,
        "should_end": False, "end_reason": None, "next_behavior": "answer_question",
    })))])
    state_achieved = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
        "goal_progress": "achieved", "frustration": 0.0,
        "should_end": True, "end_reason": "goal_achieved", "next_behavior": "say_thanks",
    })))])

    user_msg = MagicMock(choices=[MagicMock(message=MagicMock(content="Thanks, that helps!"))])

    mock_sim_client.chat.completions.create.side_effect = [
        scenario_response,   # generate_scenario
        state_advancing,     # update_state turn 1
        user_msg,            # generate_user_message turn 1
        state_achieved,      # update_state turn 2
        user_msg,            # closing message
    ]

    session = SessionState(
        session_id="test-sim",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )

    result = await run_conversation(
        persona=persona,
        orchestrator=mock_orchestrator,
        sim_client=mock_sim_client,
        sim_model="gpt-5-nano",
        session=session,
        max_turns=5,
    )
    assert result["end_reason"] == "goal_achieved"
    assert result["turns"] >= 1
    assert result["persona_id"] == "admin_how_to"
