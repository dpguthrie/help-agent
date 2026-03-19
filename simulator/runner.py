# simulator/runner.py
from __future__ import annotations
import asyncio
import logging
import random
from uuid import uuid4

import asyncpg
from openai import AsyncOpenAI

from agent.config import Settings
from agent.models import SessionState, AuthState
from agent.orchestrator import Orchestrator
from simulator.personas import PersonaTemplate, get_random_persona
from simulator.state import ConversationState
from simulator.state_tracker import update_state
from simulator.user_sim import generate_scenario, generate_user_message

logger = logging.getLogger(__name__)


async def run_simulation(
    num_conversations: int,
    concurrency: int,
    orchestrator: Orchestrator,
    sim_client: AsyncOpenAI,
    sim_model: str,
    db_pool: asyncpg.Pool,
    persona_pattern: str | None = None,
    max_turns: int = 10,
) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def run_one(conv_id: int):
        async with semaphore:
            persona = get_random_persona(persona_pattern)
            session = await create_session(persona, db_pool)
            logger.info(f"[{conv_id}] Starting: persona={persona.id}, auth={'yes' if session.auth_state else 'no'}")

            try:
                result = await run_conversation(
                    persona=persona,
                    orchestrator=orchestrator,
                    sim_client=sim_client,
                    sim_model=sim_model,
                    session=session,
                    max_turns=max_turns,
                )
                logger.info(
                    f"[{conv_id}] Done: {result['end_reason']} after {result['turns']} turns "
                    f"(frustration={result['final_frustration']:.1f})"
                )
                results.append(result)
            except Exception as e:
                logger.error(f"[{conv_id}] Error: {e}")
                results.append({"persona_id": persona.id, "error": str(e), "turns": 0})

    tasks = [run_one(i) for i in range(num_conversations)]
    await asyncio.gather(*tasks)
    return results


async def run_conversation(
    persona: PersonaTemplate,
    orchestrator: Orchestrator,
    sim_client: AsyncOpenAI,
    sim_model: str,
    session: SessionState,
    max_turns: int = 10,
) -> dict:
    # Generate scenario
    scenario = await generate_scenario(sim_client, sim_model, persona)
    user_message = scenario.get("opening_message", "I need help with Salesforce")

    state = ConversationState()
    history: list[dict] = []

    actual_max = random.randint(max(3, max_turns - 4), max_turns)

    for turn in range(actual_max):
        # Agent responds
        agent_response = await orchestrator.handle_message(user_message, session)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": agent_response})

        # Update state
        state = await update_state(
            sim_client, sim_model, persona,
            scenario.get("scenario_description", ""),
            state, agent_response, max_turns=actual_max,
        )

        if state.should_end:
            # Generate closing message if goal achieved
            if state.end_reason == "goal_achieved":
                closing = await generate_user_message(
                    sim_client, sim_model, persona,
                    scenario.get("scenario_description", ""),
                    state, history,
                )
                await orchestrator.handle_message(closing, session)
                history.append({"role": "user", "content": closing})
            break

        # Generate next user message
        user_message = await generate_user_message(
            sim_client, sim_model, persona,
            scenario.get("scenario_description", ""),
            state, history,
        )

    return {
        "persona_id": persona.id,
        "session_id": session.session_id,
        "scenario": scenario.get("scenario_description", ""),
        "expected_resolution": scenario.get("expected_resolution", ""),
        "end_reason": state.end_reason or "max_turns",
        "final_frustration": state.frustration,
        "turns": state.turns_taken,
        "goal_progress": state.goal_progress,
    }


async def create_session(persona: PersonaTemplate, db_pool: asyncpg.Pool) -> SessionState:
    session = SessionState(session_id=f"sim-{uuid4()}")

    if persona.authenticated is False:
        return session

    if persona.authenticated is None:
        if random.random() > 0.7:
            return session

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users ORDER BY random() LIMIT 1")

    if row:
        session.auth_state = AuthState(
            tenant_name=row["tenant_name"],
            org_id=row["org_id"],
            product=row["product"],
            success_plan=row["success_plan"] or "Standard",
            timezone=row["timezone"],
            phone_number=row["phone_number"],
            can_create_case=row["can_create_case"],
            is_chat_transfer_allowed=row["is_chat_transfer_allowed"],
        )

    return session
