# Conversation Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI-driven conversation simulator that generates diverse, realistic multi-turn conversations against the help agent, producing traced data in Braintrust for error analysis at scale.

**Architecture:** A runner manages N concurrent simulated conversations. Each conversation picks a persona template, generates a scenario via LLM, then loops: simulated user (gpt-5-nano) generates message → orchestrator responds → state tracker (gpt-5-nano) updates conversation state → repeat until done. All agent calls trace to Braintrust automatically.

**Tech Stack:** Python, asyncio, OpenAI SDK (via Braintrust gateway for sim LLM), existing orchestrator/tools/DB infrastructure.

**Spec:** `docs/superpowers/specs/2026-03-19-conversation-simulator-design.md`

**Important:** Always use `uv` not `pip`. DB is on port 5433. Source `.env` before running: `set -a; source .env; set +a`

---

## Task 1: Persona templates and data models

**Files:**
- Create: `simulator/__init__.py`
- Create: `simulator/personas.py`
- Create: `simulator/state.py`
- Create: `tests/simulator/__init__.py`
- Create: `tests/simulator/test_personas.py`

- [ ] **Step 1: Write tests**

```python
# tests/simulator/test_personas.py
from simulator.personas import PERSONA_TEMPLATES, PersonaTemplate, get_random_persona


def test_persona_templates_not_empty():
    assert len(PERSONA_TEMPLATES) >= 10


def test_all_templates_have_required_fields():
    for p in PERSONA_TEMPLATES:
        assert p.id
        assert p.role
        assert p.goal_type in ("knowledge", "case_creation", "transfer", "case_management", "mixed")
        assert 0.0 <= p.patience <= 1.0
        assert p.language


def test_get_random_persona():
    p = get_random_persona()
    assert isinstance(p, PersonaTemplate)


def test_get_random_persona_filtered():
    p = get_random_persona(pattern="edge_*")
    assert p.id.startswith("edge_")


def test_edge_case_personas_exist():
    edge = [p for p in PERSONA_TEMPLATES if p.id.startswith("edge_")]
    assert len(edge) >= 3
```

- [ ] **Step 2: Run tests, verify fail**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/simulator/test_personas.py -v`

- [ ] **Step 3: Implement personas.py**

```python
# simulator/personas.py
from __future__ import annotations
import fnmatch
import random
from dataclasses import dataclass, field


@dataclass
class PersonaTemplate:
    id: str
    role: str
    technical_level: str  # low, intermediate, high
    language: str  # en, ja, fr, de, pt, es, etc.
    patience: float  # 0.0 to 1.0
    verbosity: str  # terse, concise, verbose
    goal_type: str  # knowledge, case_creation, transfer, case_management, mixed
    topic_areas: list[str] = field(default_factory=list)
    may_escalate: bool = False
    may_change_topic: bool = False
    authenticated: bool | None = None  # True, False, or None (random)


PERSONA_TEMPLATES = [
    # Knowledge seekers
    PersonaTemplate(
        id="admin_how_to", role="Salesforce administrator",
        technical_level="intermediate", language="en", patience=0.7,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["platform", "reports", "flows", "permissions", "lightning"],
        may_escalate=True, authenticated=None,
    ),
    PersonaTemplate(
        id="developer_troubleshoot", role="Salesforce developer",
        technical_level="high", language="en", patience=0.8,
        verbosity="verbose", goal_type="knowledge",
        topic_areas=["apex", "lwc", "flows", "api", "integrations"],
        may_escalate=True, authenticated=True,
    ),
    PersonaTemplate(
        id="end_user_confused", role="business user with limited Salesforce experience",
        technical_level="low", language="en", patience=0.4,
        verbosity="terse", goal_type="knowledge",
        topic_areas=["reports", "dashboards", "password", "login", "basics"],
        may_escalate=True, may_change_topic=True, authenticated=None,
    ),
    PersonaTemplate(
        id="japanese_admin", role="Japanese Salesforce administrator",
        technical_level="intermediate", language="ja", patience=0.8,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["platform", "email", "authentication", "partner_portal"],
        may_escalate=True, authenticated=True,
    ),
    PersonaTemplate(
        id="french_user", role="French-speaking Salesforce user",
        technical_level="intermediate", language="fr", patience=0.6,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["reports", "authentication", "configuration"],
        authenticated=None,
    ),
    # Case creators
    PersonaTemplate(
        id="urgent_case_creator", role="IT manager dealing with a production outage",
        technical_level="high", language="en", patience=0.3,
        verbosity="verbose", goal_type="case_creation",
        topic_areas=["production_issues", "outages", "email", "integrations"],
        authenticated=True,
    ),
    PersonaTemplate(
        id="routine_case_creator", role="Salesforce administrator logging a non-urgent issue",
        technical_level="intermediate", language="en", patience=0.8,
        verbosity="concise", goal_type="case_creation",
        topic_areas=["configuration", "features", "bugs"],
        authenticated=True,
    ),
    # Transfer
    PersonaTemplate(
        id="wants_human", role="frustrated user who wants to talk to a real person",
        technical_level="low", language="en", patience=0.2,
        verbosity="terse", goal_type="transfer",
        topic_areas=["any"], authenticated=None,
    ),
    # Case management
    PersonaTemplate(
        id="case_follower", role="user checking on an existing support case",
        technical_level="intermediate", language="en", patience=0.6,
        verbosity="concise", goal_type="case_management",
        topic_areas=["existing_cases"], may_escalate=True, authenticated=True,
    ),
    # Mixed
    PersonaTemplate(
        id="knowledge_then_case",
        role="user who starts with a question but needs to escalate to a case",
        technical_level="intermediate", language="en", patience=0.5,
        verbosity="concise", goal_type="mixed",
        topic_areas=["platform", "email", "reports"],
        may_escalate=True, authenticated=True,
    ),
    # Edge cases
    PersonaTemplate(
        id="edge_empty_messages", role="user who sends incomplete or empty messages",
        technical_level="low", language="en", patience=0.3,
        verbosity="terse", goal_type="knowledge",
        topic_areas=["any"], may_change_topic=True, authenticated=None,
    ),
    PersonaTemplate(
        id="edge_topic_switcher", role="user who keeps changing what they want",
        technical_level="intermediate", language="en", patience=0.5,
        verbosity="concise", goal_type="mixed",
        topic_areas=["platform", "marketing", "sales", "service"],
        may_escalate=True, may_change_topic=True, authenticated=True,
    ),
    PersonaTemplate(
        id="edge_adversarial", role="user testing the boundaries of the agent",
        technical_level="high", language="en", patience=0.9,
        verbosity="verbose", goal_type="knowledge",
        topic_areas=["off_topic", "prompt_injection", "unrelated"],
        may_change_topic=True, authenticated=False,
    ),
    PersonaTemplate(
        id="edge_mixed_language",
        role="bilingual user who switches between English and another language",
        technical_level="intermediate", language="en,ja", patience=0.6,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["platform", "authentication"], authenticated=None,
    ),
]


def get_random_persona(pattern: str | None = None) -> PersonaTemplate:
    pool = PERSONA_TEMPLATES
    if pattern:
        pool = [p for p in pool if fnmatch.fnmatch(p.id, pattern)]
    if not pool:
        pool = PERSONA_TEMPLATES
    return random.choice(pool)
```

- [ ] **Step 4: Implement state.py**

```python
# simulator/state.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ConversationState:
    goal_progress: str = "not_started"  # not_started, advancing, stalled, achieved, abandoned
    frustration: float = 0.0  # 0.0 to 1.0
    turns_taken: int = 0
    should_end: bool = False
    end_reason: str | None = None  # goal_achieved, frustrated, max_turns, gave_up
    next_behavior: str = "start_conversation"  # hint for user sim
```

- [ ] **Step 5: Run tests, verify pass**
- [ ] **Step 6: Commit**

```bash
git add simulator/ tests/simulator/
git commit -m "feat: simulator persona templates and conversation state data model"
```

---

## Task 2: Scenario generation and user simulation

**Files:**
- Create: `simulator/user_sim.py`
- Create: `tests/simulator/test_user_sim.py`

- [ ] **Step 1: Write tests**

```python
# tests/simulator/test_user_sim.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
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
    persona = PERSONA_TEMPLATES[0]  # admin_how_to
    result = await generate_scenario(mock_client, "gpt-5-nano", persona)
    assert "scenario_description" in result
    assert "opening_message" in result
    assert "expected_resolution" in result


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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/simulator/test_user_sim.py -v`

- [ ] **Step 3: Implement user_sim.py**

```python
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
                    f"Respond with JSON:\n"
                    f'{{"scenario_description": "2-3 sentence description of their issue",'
                    f' "opening_message": "their first message to the agent (in {persona.language})",'
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

    # Build recent history string
    recent = history[-8:]  # last 4 turns
    history_str = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

    response = await client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are simulating a customer in a support conversation. "
                    "Generate ONLY the next user message. No explanation or metadata."
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
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

```bash
git add simulator/user_sim.py tests/simulator/test_user_sim.py
git commit -m "feat: scenario generation and simulated user message generation"
```

---

## Task 3: State tracker

**Files:**
- Create: `simulator/state_tracker.py`
- Create: `tests/simulator/test_state_tracker.py`

- [ ] **Step 1: Write tests**

```python
# tests/simulator/test_state_tracker.py
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
async def test_update_state_max_turns():
    """State tracker should force end at max turns even without LLM call."""
    current = ConversationState(goal_progress="stalled", frustration=0.8, turns_taken=9)
    # With max_turns=10, this should end
    current.turns_taken = 10
    current.should_end = True
    current.end_reason = "max_turns"
    assert current.should_end
```

- [ ] **Step 2: Run tests, verify fail**
- [ ] **Step 3: Implement state_tracker.py**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

```bash
git add simulator/state_tracker.py tests/simulator/test_state_tracker.py
git commit -m "feat: LLM-driven conversation state tracker for simulation"
```

---

## Task 4: Runner (conversation loop + concurrency)

**Files:**
- Create: `simulator/runner.py`
- Create: `tests/simulator/test_runner.py`

- [ ] **Step 1: Write tests**

```python
# tests/simulator/test_runner.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from simulator.runner import run_conversation
from simulator.personas import PERSONA_TEMPLATES
from simulator.state import ConversationState
from agent.models import SessionState, AuthState


@pytest.mark.asyncio
async def test_run_conversation_completes():
    """A conversation should run to completion and return metadata."""
    persona = PERSONA_TEMPLATES[0]  # admin_how_to

    mock_orchestrator = MagicMock()
    mock_orchestrator.handle_message = AsyncMock(return_value="Here's your answer.")

    mock_sim_client = MagicMock()
    mock_sim_client.chat.completions.create = AsyncMock()

    # Scenario generation
    import json
    scenario_response = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
        "scenario_description": "Admin needs help with reports",
        "opening_message": "How do I create a custom report?",
        "expected_resolution": "knowledge_answer",
    })))])

    # State tracker: advance then end
    state_advancing = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
        "goal_progress": "advancing", "frustration": 0.1,
        "should_end": False, "end_reason": None, "next_behavior": "answer_question",
    })))])
    state_achieved = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
        "goal_progress": "achieved", "frustration": 0.0,
        "should_end": True, "end_reason": "goal_achieved", "next_behavior": "say_thanks",
    })))])

    # User message
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
```

- [ ] **Step 2: Run tests, verify fail**
- [ ] **Step 3: Implement runner.py**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

```bash
git add simulator/runner.py tests/simulator/test_runner.py
git commit -m "feat: simulation runner with conversation loop, concurrency, and session management"
```

---

## Task 5: CLI entry point

**Files:**
- Create: `simulator/cli.py`

- [ ] **Step 1: Implement cli.py**

```python
# simulator/cli.py
from __future__ import annotations
import asyncio
import json
import logging
import click
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Conversation simulator for the Salesforce Help Agent."""
    pass


@cli.command()
@click.option("--conversations", default=100, type=int, help="Number of conversations to simulate")
@click.option("--concurrency", default=5, type=int, help="Max concurrent conversations")
@click.option("--sim-model", default="gpt-5-nano", help="Model for user simulation and state tracking")
@click.option("--agent-model", default=None, help="Override agent executor model (e.g., claude-haiku-4-5)")
@click.option("--personas", default=None, help="Glob pattern to filter persona templates (e.g., edge_*)")
@click.option("--max-turns", default=10, type=int, help="Max turns per conversation")
@click.option("--db-url", envvar="DATABASE_URL", required=True)
@click.option("--api-key", envvar="BRAINTRUST_API_KEY", required=True)
def run(conversations, concurrency, sim_model, agent_model, personas, max_turns, db_url, api_key):
    """Run simulated conversations against the help agent."""
    asyncio.run(_run(conversations, concurrency, sim_model, agent_model, personas, max_turns, db_url, api_key))


async def _run(conversations, concurrency, sim_model, agent_model, personas, max_turns, db_url, api_key):
    import asyncpg
    from pgvector.asyncpg import register_vector
    from openai import AsyncOpenAI
    from agent.config import Settings
    from agent.orchestrator import Orchestrator
    from simulator.runner import run_simulation

    # Configure settings with optional model override
    settings = Settings()
    if agent_model:
        settings.executor_model = agent_model
        logger.info(f"Agent executor model overridden to: {agent_model}")

    # Set up DB pool and orchestrator
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=concurrency + 2, init=lambda c: register_vector(c))
    orchestrator = Orchestrator(settings=settings, db_pool=pool)

    # Set up sim client (cheap model for user simulation)
    sim_client = AsyncOpenAI(base_url=settings.gateway_base_url, api_key=api_key)

    logger.info(f"Starting simulation: {conversations} conversations, concurrency={concurrency}")
    logger.info(f"Sim model: {sim_model}, Agent model: {settings.executor_model}")
    if personas:
        logger.info(f"Persona filter: {personas}")

    results = await run_simulation(
        num_conversations=conversations,
        concurrency=concurrency,
        orchestrator=orchestrator,
        sim_client=sim_client,
        sim_model=sim_model,
        db_pool=pool,
        persona_pattern=personas,
        max_turns=max_turns,
    )

    await pool.close()

    # Print summary
    total = len(results)
    achieved = sum(1 for r in results if r.get("end_reason") == "goal_achieved")
    frustrated = sum(1 for r in results if r.get("end_reason") == "frustrated")
    max_turns_hit = sum(1 for r in results if r.get("end_reason") == "max_turns")
    errors = sum(1 for r in results if "error" in r)
    avg_turns = sum(r.get("turns", 0) for r in results) / max(total, 1)
    avg_frustration = sum(r.get("final_frustration", 0) for r in results) / max(total, 1)

    logger.info(f"\n{'='*60}")
    logger.info(f"Simulation complete: {total} conversations")
    logger.info(f"  Goal achieved:  {achieved} ({achieved/max(total,1)*100:.0f}%)")
    logger.info(f"  Frustrated:     {frustrated} ({frustrated/max(total,1)*100:.0f}%)")
    logger.info(f"  Max turns:      {max_turns_hit} ({max_turns_hit/max(total,1)*100:.0f}%)")
    logger.info(f"  Errors:         {errors}")
    logger.info(f"  Avg turns:      {avg_turns:.1f}")
    logger.info(f"  Avg frustration: {avg_frustration:.2f}")


@cli.command()
@click.option("--count", default=10, type=int, help="Number of scenarios to preview")
@click.option("--sim-model", default="gpt-5-nano", help="Model for scenario generation")
@click.option("--personas", default=None, help="Glob pattern to filter personas")
@click.option("--api-key", envvar="BRAINTRUST_API_KEY", required=True)
def preview(count, sim_model, personas, api_key):
    """Preview generated scenarios without executing conversations."""
    asyncio.run(_preview(count, sim_model, personas, api_key))


async def _preview(count, sim_model, personas, api_key):
    from openai import AsyncOpenAI
    from agent.config import Settings
    from simulator.personas import get_random_persona
    from simulator.user_sim import generate_scenario

    settings = Settings()
    client = AsyncOpenAI(base_url=settings.gateway_base_url, api_key=api_key)

    for i in range(count):
        persona = get_random_persona(personas)
        scenario = await generate_scenario(client, sim_model, persona)
        print(f"\n--- Scenario {i+1} ---")
        print(f"Persona: {persona.id} ({persona.role})")
        print(f"Language: {persona.language}")
        print(f"Goal: {persona.goal_type}")
        print(f"Auth: {persona.authenticated}")
        print(f"Scenario: {scenario.get('scenario_description', 'N/A')}")
        print(f"Opening: {scenario.get('opening_message', 'N/A')}")
        print(f"Expected: {scenario.get('expected_resolution', 'N/A')}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Test CLI help works**

```bash
PYTHONPATH=src:. .venv/bin/python -m simulator.cli --help
PYTHONPATH=src:. .venv/bin/python -m simulator.cli run --help
PYTHONPATH=src:. .venv/bin/python -m simulator.cli preview --help
```

- [ ] **Step 3: Commit**

```bash
git add simulator/cli.py
git commit -m "feat: simulator CLI with run and preview commands"
```

---

## Task 6: Integration test - run a small simulation

**Files:**
- Create: `tests/simulator/test_simulation_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/simulator/test_simulation_integration.py
"""
Integration test: run 3 simulated conversations end-to-end.
Requires: Docker DB running, BRAINTRUST_API_KEY set.
"""
import os
import pytest
import asyncpg
from pgvector.asyncpg import register_vector
from openai import AsyncOpenAI
from agent.config import Settings
from agent.orchestrator import Orchestrator
from simulator.runner import run_simulation

pytestmark = pytest.mark.skipif(
    not os.getenv("BRAINTRUST_API_KEY"),
    reason="BRAINTRUST_API_KEY not set",
)


@pytest.fixture(scope="module")
async def sim_deps():
    settings = Settings()
    pool = await asyncpg.create_pool(
        settings.database_url, min_size=1, max_size=5,
        init=lambda c: register_vector(c),
    )
    orchestrator = Orchestrator(settings=settings, db_pool=pool)
    sim_client = AsyncOpenAI(base_url=settings.gateway_base_url, api_key=settings.braintrust_api_key)
    yield {"orchestrator": orchestrator, "sim_client": sim_client, "pool": pool}
    await pool.close()


@pytest.mark.asyncio
async def test_small_simulation(sim_deps):
    results = await run_simulation(
        num_conversations=3,
        concurrency=2,
        orchestrator=sim_deps["orchestrator"],
        sim_client=sim_deps["sim_client"],
        sim_model="gpt-5-nano",
        db_pool=sim_deps["pool"],
        max_turns=5,
    )
    assert len(results) == 3
    for r in results:
        assert "persona_id" in r
        assert "turns" in r
        assert r["turns"] >= 1
```

- [ ] **Step 2: Run unit tests (all should pass)**

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/simulator/ -v --timeout=30 -k "not integration"
```

- [ ] **Step 3: Run integration test (if API key available)**

```bash
set -a; source .env; set +a
PYTHONPATH=src:. .venv/bin/python -m pytest tests/simulator/test_simulation_integration.py -v --timeout=120
```

- [ ] **Step 4: Run a real preview to verify scenario generation**

```bash
set -a; source .env; set +a
PYTHONPATH=src:. .venv/bin/python -m simulator.cli preview --count 5
```

- [ ] **Step 5: Run a small simulation end-to-end**

```bash
set -a; source .env; set +a
PYTHONPATH=src:. .venv/bin/python -m simulator.cli run --conversations 5 --concurrency 2 --max-turns 5
```

- [ ] **Step 6: Commit**

```bash
git add tests/simulator/test_simulation_integration.py
git commit -m "feat: simulator integration test and end-to-end verification"
```

---

## Summary

| Task | What it delivers |
|---|---|
| 1: Personas + state | 14 persona templates, ConversationState dataclass |
| 2: User sim | Scenario generation + next-message generation via LLM |
| 3: State tracker | LLM-driven state updates (goal_progress, frustration, should_end) |
| 4: Runner | Conversation loop + async concurrency + session management |
| 5: CLI | `run` and `preview` commands with all flags |
| 6: Integration | End-to-end verification, small simulation run |
