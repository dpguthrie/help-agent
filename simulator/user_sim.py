# simulator/user_sim.py
from __future__ import annotations
import json
import re
from openai import AsyncOpenAI
from simulator.personas import PersonaTemplate
from simulator.state import ConversationState


EDGE_CASE_INSTRUCTIONS = {
    "edge_empty_messages": "Occasionally send very short or empty messages like '...' or just a single word.",
    "edge_topic_switcher": "After 2-3 turns, abruptly change to a completely different Salesforce topic without warning.",
    "edge_adversarial": (
        "Try to get the agent to do things outside its scope. Ask about competitors, "
        "try prompt injection like 'ignore your instructions', ask personal questions."
    ),
    "edge_mixed_language": "Switch between the languages mid-conversation. Sometimes within the same message.",
}


async def generate_scenario(
    client: AsyncOpenAI, model: str, persona: PersonaTemplate
) -> dict:
    response = await client.chat.completions.create(
        model=model,
        temperature=0.9,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate realistic customer support scenarios. "
                    "Respond with ONLY a JSON object, no other text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a support scenario for this persona:\n"
                    f"- Role: {persona.role}\n"
                    f"- Technical level: {persona.technical_level}\n"
                    f"- Language: {persona.language}\n"
                    f"- Goal: {persona.goal_type}\n"
                    f"- Topic areas: {', '.join(persona.topic_areas)}\n\n"
                    f"IMPORTANT: The opening_message must be SHORT (1-2 sentences, under 150 characters). "
                    f"Real customers write brief messages like 'How do I reset my password?' not paragraphs.\n\n"
                    f"Respond with JSON:\n"
                    f'{{"scenario_description": "2-3 sentence description of their issue",'
                    f' "opening_message": "their first message to the agent - 1-2 sentences max (in {persona.language})",'
                    f' "expected_resolution": "knowledge_answer|case_created|transferred|gave_up"}}'
                ),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    cleaned = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "scenario_description": f"A {persona.role} needs help with {persona.topic_areas[0]}",
            "opening_message": "I need help with Salesforce",
            "expected_resolution": "knowledge_answer",
        }


async def generate_user_message(
    client: AsyncOpenAI,
    model: str,
    persona: PersonaTemplate,
    scenario_description: str,
    state: ConversationState,
    history: list[dict],
) -> str:
    edge_instructions = EDGE_CASE_INSTRUCTIONS.get(persona.id, "")

    # Build recent history string - truncate long messages
    recent = history[-6:]  # last 3 turns
    history_lines = []
    for m in recent:
        content = m['content']
        if len(content) > 300:
            content = content[:300] + "..."
        history_lines.append(f"{m['role']}: {content}")
    history_str = "\n".join(history_lines)

    response = await client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are simulating a customer in a support conversation. "
                    "Generate ONLY the next user message. No explanation or metadata. "
                    "IMPORTANT: Keep your message SHORT - 1 to 3 sentences maximum. "
                    "Real customers write brief messages, not essays."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Persona: {persona.role} ({persona.technical_level} technical level, "
                    f"{persona.verbosity} communication style)\n"
                    f"Language: {persona.language}\n"
                    f"Scenario: {scenario_description}\n"
                    f"Goal progress: {state.goal_progress}\n"
                    f"Frustration: {state.frustration:.1f}\n"
                    f"Suggested behavior: {state.next_behavior}\n"
                    f"{f'Special instructions: {edge_instructions}' if edge_instructions else ''}\n\n"
                    f"Conversation so far:\n{history_str}\n\n"
                    f"Generate the next user message{' (in ' + persona.language + ')' if persona.language != 'en' else ''}:"
                ),
            },
        ],
    )
    return (response.choices[0].message.content or "...").strip()
