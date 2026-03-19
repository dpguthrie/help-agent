# simulator/state_tracker.py
from __future__ import annotations
import json
import re
from openai import AsyncOpenAI
from simulator.personas import PersonaTemplate
from simulator.state import ConversationState


async def update_state(
    client: AsyncOpenAI,
    model: str,
    persona: PersonaTemplate,
    scenario_description: str,
    current_state: ConversationState,
    agent_response: str,
    max_turns: int = 10,
) -> ConversationState:
    new_turns = current_state.turns_taken + 1

    # Force end at max turns
    if new_turns >= max_turns:
        return ConversationState(
            goal_progress=current_state.goal_progress,
            frustration=current_state.frustration,
            turns_taken=new_turns,
            should_end=True,
            end_reason="max_turns",
            next_behavior="say_goodbye",
        )

    response = await client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You track the state of a customer support conversation. "
                    "Respond with ONLY a JSON object, no other text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User's goal: {scenario_description}\n"
                    f"User patience: {persona.patience} (0=impatient, 1=patient)\n"
                    f"Current state: {json.dumps({'goal_progress': current_state.goal_progress, 'frustration': current_state.frustration, 'turns_taken': current_state.turns_taken})}\n\n"
                    f"Agent just responded: \"{agent_response[:500]}\"\n\n"
                    f"Update the state. Respond with JSON:\n"
                    f'{{"goal_progress": "advancing|stalled|achieved|abandoned",'
                    f' "frustration": <0.0-1.0>,'
                    f' "should_end": true|false,'
                    f' "end_reason": null|"goal_achieved"|"frustrated"|"gave_up",'
                    f' "next_behavior": "answer_question|express_frustration|ask_to_transfer|say_thanks|change_topic|provide_info|clarify|say_goodbye"}}'
                ),
            },
        ],
    )

    content = response.choices[0].message.content or "{}"
    cleaned = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()

    try:
        data = json.loads(cleaned)
        return ConversationState(
            goal_progress=data.get("goal_progress", current_state.goal_progress),
            frustration=min(1.0, max(0.0, float(data.get("frustration", current_state.frustration)))),
            turns_taken=new_turns,
            should_end=bool(data.get("should_end", False)),
            end_reason=data.get("end_reason"),
            next_behavior=data.get("next_behavior", "answer_question"),
        )
    except (json.JSONDecodeError, ValueError):
        # Fallback: increment frustration slightly, keep going
        return ConversationState(
            goal_progress=current_state.goal_progress,
            frustration=min(1.0, current_state.frustration + 0.1),
            turns_taken=new_turns,
            should_end=False,
            end_reason=None,
            next_behavior="answer_question",
        )
