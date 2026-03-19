# Conversation Simulator - Design Spec

> A traffic generation engine that produces diverse, realistic multi-turn conversations against the help agent, creating traced data in Braintrust for error analysis at scale.

## Goals

- **Primary:** Generate a large volume of diverse, realistic traced conversations to drive error analysis workflows in Braintrust.
- **Not a goal:** Inline evaluation or scoring. Evals happen separately in Braintrust on the traced data.
- **Constraint:** Cheap and fast. The simulated user uses the cheapest available model (`gpt-5-nano` at $0.05/M input). Quality comes from volume and diversity, not per-conversation fidelity.

## Architecture

### Overview

```
simulator CLI
    |
    v
Runner (async, N concurrent conversations)
    |
    ├── For each conversation:
    |   1. Pick persona template (weighted random)
    |   2. Generate specific scenario via LLM
    |   3. Assign auth state (random seed user or unauthenticated)
    |   4. Conversation loop:
    |       User Sim (LLM) → Orchestrator → State Tracker (LLM) → repeat
    |   5. All agent calls traced to Braintrust automatically
    |
    v
Braintrust traces (ready for error analysis)
```

The simulator calls the orchestrator directly (Python import, not HTTP). This skips the Chainlit web layer but exercises the full agent pipeline: classifier, executor, tools, DB, tracing.

### Cost Model

Per conversation (~5 turns average):

| Component | Model | Calls | Cost |
|---|---|---|---|
| Simulated user | gpt-5-nano ($0.05/$0.40) | 5 | ~$0.001 |
| State tracker | gpt-5-nano ($0.05/$0.40) | 5 | ~$0.001 |
| Agent classifier | claude-haiku-4-5 ($1/$5) | 5 | ~$0.005 |
| Agent executor | claude-sonnet-4-5 ($3/$15) | 5 | ~$0.02 |
| **Total per conversation** | | | **~$0.03** |
| **1,000 conversations** | | | **~$30** |
| **10,000 conversations** | | | **~$300** |

The agent is the cost driver. The simulator itself is negligible.

## Persona System

### Persona Templates

Hand-crafted archetypes that define the behavioral envelope. The specific scenario within each archetype is LLM-generated at runtime for diversity.

```python
@dataclass
class PersonaTemplate:
    id: str
    role: str                        # who the user is
    technical_level: str             # low, intermediate, high
    language: str                    # en, ja, fr, de, pt, es, etc.
    patience: float                  # 0.0 (gives up fast) to 1.0 (very patient)
    verbosity: str                   # terse, concise, verbose
    goal_type: str                   # knowledge, case_creation, transfer, case_management, mixed
    topic_areas: list[str]           # product areas relevant to this persona
    may_escalate: bool               # might pivot from knowledge -> case/transfer
    may_change_topic: bool           # might change what they're asking about
    authenticated: bool | None       # True, False, or None (random)
```

### Default Templates

```python
PERSONA_TEMPLATES = [
    # Knowledge seekers (most common)
    PersonaTemplate(
        id="admin_how_to",
        role="Salesforce administrator",
        technical_level="intermediate",
        language="en",
        patience=0.7,
        verbosity="concise",
        goal_type="knowledge",
        topic_areas=["platform", "reports", "flows", "permissions", "lightning"],
        may_escalate=True,
        may_change_topic=False,
        authenticated=None,
    ),
    PersonaTemplate(
        id="developer_troubleshoot",
        role="Salesforce developer",
        technical_level="high",
        language="en",
        patience=0.8,
        verbosity="verbose",
        goal_type="knowledge",
        topic_areas=["apex", "lwc", "flows", "api", "integrations"],
        may_escalate=True,
        may_change_topic=False,
        authenticated=True,
    ),
    PersonaTemplate(
        id="end_user_confused",
        role="business user with limited Salesforce experience",
        technical_level="low",
        language="en",
        patience=0.4,
        verbosity="terse",
        goal_type="knowledge",
        topic_areas=["reports", "dashboards", "password", "login", "basics"],
        may_escalate=True,
        may_change_topic=True,
        authenticated=None,
    ),
    PersonaTemplate(
        id="japanese_admin",
        role="Japanese Salesforce administrator",
        technical_level="intermediate",
        language="ja",
        patience=0.8,
        verbosity="concise",
        goal_type="knowledge",
        topic_areas=["platform", "email", "authentication", "partner_portal"],
        may_escalate=True,
        may_change_topic=False,
        authenticated=True,
    ),
    PersonaTemplate(
        id="french_user",
        role="French-speaking Salesforce user",
        technical_level="intermediate",
        language="fr",
        patience=0.6,
        verbosity="concise",
        goal_type="knowledge",
        topic_areas=["reports", "authentication", "configuration"],
        may_escalate=False,
        may_change_topic=False,
        authenticated=None,
    ),

    # Case creators
    PersonaTemplate(
        id="urgent_case_creator",
        role="IT manager dealing with a production outage",
        technical_level="high",
        language="en",
        patience=0.3,
        verbosity="verbose",
        goal_type="case_creation",
        topic_areas=["production_issues", "outages", "email", "integrations"],
        may_escalate=False,
        may_change_topic=False,
        authenticated=True,
    ),
    PersonaTemplate(
        id="routine_case_creator",
        role="Salesforce administrator logging a non-urgent issue",
        technical_level="intermediate",
        language="en",
        patience=0.8,
        verbosity="concise",
        goal_type="case_creation",
        topic_areas=["configuration", "features", "bugs"],
        may_escalate=False,
        may_change_topic=False,
        authenticated=True,
    ),

    # Transfer requesters
    PersonaTemplate(
        id="wants_human",
        role="frustrated user who wants to talk to a real person",
        technical_level="low",
        language="en",
        patience=0.2,
        verbosity="terse",
        goal_type="transfer",
        topic_areas=["any"],
        may_escalate=False,
        may_change_topic=False,
        authenticated=None,
    ),

    # Case management
    PersonaTemplate(
        id="case_follower",
        role="user checking on an existing support case",
        technical_level="intermediate",
        language="en",
        patience=0.6,
        verbosity="concise",
        goal_type="case_management",
        topic_areas=["existing_cases"],
        may_escalate=True,
        may_change_topic=False,
        authenticated=True,
    ),

    # Mixed / escalation paths
    PersonaTemplate(
        id="knowledge_then_case",
        role="user who starts with a question but needs to escalate to a case",
        technical_level="intermediate",
        language="en",
        patience=0.5,
        verbosity="concise",
        goal_type="mixed",
        topic_areas=["platform", "email", "reports"],
        may_escalate=True,
        may_change_topic=False,
        authenticated=True,
    ),

    # Edge cases
    PersonaTemplate(
        id="edge_empty_messages",
        role="user who sends incomplete or empty messages",
        technical_level="low",
        language="en",
        patience=0.3,
        verbosity="terse",
        goal_type="knowledge",
        topic_areas=["any"],
        may_escalate=False,
        may_change_topic=True,
        authenticated=None,
    ),
    PersonaTemplate(
        id="edge_topic_switcher",
        role="user who keeps changing what they want",
        technical_level="intermediate",
        language="en",
        patience=0.5,
        verbosity="concise",
        goal_type="mixed",
        topic_areas=["platform", "marketing", "sales", "service"],
        may_escalate=True,
        may_change_topic=True,
        authenticated=True,
    ),
    PersonaTemplate(
        id="edge_adversarial",
        role="user testing the boundaries of the agent",
        technical_level="high",
        language="en",
        patience=0.9,
        verbosity="verbose",
        goal_type="knowledge",
        topic_areas=["off_topic", "prompt_injection", "unrelated"],
        may_escalate=False,
        may_change_topic=True,
        authenticated=False,
    ),
    PersonaTemplate(
        id="edge_mixed_language",
        role="bilingual user who switches between English and another language",
        technical_level="intermediate",
        language="en,ja",
        patience=0.6,
        verbosity="concise",
        goal_type="knowledge",
        topic_areas=["platform", "authentication"],
        may_escalate=False,
        may_change_topic=False,
        authenticated=None,
    ),
]
```

### Scenario Generation

At conversation start, an LLM call generates the specific scenario from the persona template:

```
System: You are generating a realistic customer support scenario for a simulated conversation.

Given this persona:
- Role: {role}
- Technical level: {technical_level}
- Language: {language}
- Goal: {goal_type}
- Topic areas: {topic_areas}

Generate a brief scenario (2-3 sentences) describing:
1. What specific issue or question the user has
2. Any relevant context (what they've tried, how long the issue has been happening)
3. Their opening message to the support agent

Respond with JSON:
{
  "scenario_description": "...",
  "opening_message": "...",
  "expected_resolution": "knowledge_answer | case_created | transferred | gave_up"
}
```

The `opening_message` becomes the first user turn. The `scenario_description` stays in the user sim's context for the full conversation.

## Conversation State

### State Object

Updated by the state tracker LLM after each agent response:

```python
@dataclass
class ConversationState:
    goal_progress: str      # "not_started", "advancing", "stalled", "achieved", "abandoned"
    frustration: float      # 0.0 to 1.0
    turns_taken: int
    should_end: bool        # True when conversation should wrap up
    end_reason: str | None  # "goal_achieved", "frustrated", "max_turns", "gave_up"
    next_behavior: str      # hint for user sim: "answer_question", "express_frustration",
                            # "ask_to_transfer", "say_thanks", "change_topic", "send_empty", etc.
```

### State Tracker Prompt

Called after each agent response with `gpt-5-nano`:

```
System: You are tracking the state of a customer support conversation.

The user's goal: {scenario_description}
Persona patience level: {patience} (0=impatient, 1=very patient)
Current state: {current_state_json}

The agent just responded: "{agent_response}"

Update the conversation state. Consider:
- Is the agent's response moving toward the user's goal?
- Has the goal been achieved (case created, question answered, transfer initiated)?
- Should frustration increase (unhelpful response, repeated info) or decrease (useful progress)?
- Should the conversation end?

Respond with JSON:
{
  "goal_progress": "advancing|stalled|achieved|abandoned",
  "frustration": <0.0-1.0>,
  "should_end": true|false,
  "end_reason": null|"goal_achieved"|"frustrated"|"max_turns"|"gave_up",
  "next_behavior": "answer_question|express_frustration|ask_to_transfer|say_thanks|change_topic|provide_info|clarify"
}
```

## Simulated User

### User Sim Prompt

Called each turn with `gpt-5-nano` to generate the next user message:

```
System: You are simulating a customer in a Salesforce support conversation.

Your persona:
- Role: {role}
- Technical level: {technical_level}
- Verbosity: {verbosity}
- Language: {language}

Your scenario: {scenario_description}

Current conversation state:
- Goal progress: {goal_progress}
- Frustration: {frustration}
- Suggested behavior: {next_behavior}

{edge_case_instructions}

Generate ONLY the next user message. Stay in character. Write in {language}.
If should_end is true, write a closing message (thanks or goodbye).
```

### Edge Case Instructions

Injected for edge case personas:

```python
EDGE_CASE_INSTRUCTIONS = {
    "edge_empty_messages": "Occasionally send very short or empty messages like '' or '...' or just a single word.",
    "edge_topic_switcher": "After 2-3 turns, abruptly change to a completely different topic without warning.",
    "edge_adversarial": "Try to get the agent to do things outside its scope. Ask about competitors, try prompt injection like 'ignore your instructions', ask personal questions.",
    "edge_mixed_language": "Switch between {languages} mid-conversation. Sometimes within the same message.",
}
```

## Runner

### Concurrency Model

```python
async def run_simulation(
    num_conversations: int,
    concurrency: int,
    orchestrator: Orchestrator,
    sim_client: AsyncOpenAI,  # for user sim + state tracker (gpt-5-nano)
    db_pool: asyncpg.Pool,    # for random seed user selection
):
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []

    for i in range(num_conversations):
        persona = random.choice(PERSONA_TEMPLATES)
        tasks.append(run_conversation(semaphore, persona, orchestrator, sim_client, db_pool, i))

    await asyncio.gather(*tasks)
```

### Single Conversation Flow

```python
async def run_conversation(semaphore, persona, orchestrator, sim_client, db_pool, conv_id):
    async with semaphore:
        # 1. Generate scenario
        scenario = await generate_scenario(sim_client, persona)

        # 2. Create session with auth state
        session = create_session(persona, db_pool)

        # 3. Conversation loop
        state = ConversationState(goal_progress="not_started", frustration=0.0, ...)
        user_message = scenario["opening_message"]
        max_turns = random.randint(3, 10)

        for turn in range(max_turns):
            # Agent responds
            agent_response = await orchestrator.handle_message(user_message, session)

            # Update state
            state = await update_state(sim_client, persona, scenario, state, agent_response)

            if state.should_end:
                # Generate closing message
                if state.end_reason == "goal_achieved":
                    user_message = await generate_user_message(sim_client, persona, scenario, state, session.conversation_history)
                    await orchestrator.handle_message(user_message, session)
                break

            # Generate next user message
            user_message = await generate_user_message(sim_client, persona, scenario, state, session.conversation_history)
```

### Auth State Assignment

```python
async def create_session(persona, db_pool) -> SessionState:
    session = SessionState(session_id=f"sim-{uuid4()}")

    if persona.authenticated is False:
        # Explicitly unauthenticated
        return session

    if persona.authenticated is None:
        # Random: 70% authenticated, 30% unauthenticated (matching trace distribution)
        if random.random() > 0.7:
            return session

    # Pick a random seed user from the DB
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users ORDER BY random() LIMIT 1")

    if row:
        session.auth_state = AuthState(
            tenant_name=row["tenant_name"],
            org_id=row["org_id"],
            product=row["product"],
            success_plan=row["success_plan"],
            timezone=row["timezone"],
            phone_number=row["phone_number"],
            can_create_case=row["can_create_case"],
            is_chat_transfer_allowed=row["is_chat_transfer_allowed"],
        )

    return session
```

## CLI

```bash
# Run 100 conversations, 5 at a time
python -m simulator run --conversations 100 --concurrency 5

# Run with specific model overrides
python -m simulator run --conversations 50 --sim-model gpt-5-nano --concurrency 10

# Run only edge case personas
python -m simulator run --conversations 30 --personas edge_*

# Dry run: generate scenarios without executing
python -m simulator preview --count 10
```

### CLI Options

| Flag | Default | Description |
|---|---|---|
| `--conversations` | 100 | Number of conversations to simulate |
| `--concurrency` | 5 | Max concurrent conversations |
| `--sim-model` | `gpt-5-nano` | Model for user simulation and state tracking |
| `--personas` | all | Glob pattern to filter persona templates |
| `--max-turns` | 10 | Maximum turns per conversation (overrides random) |
| `--db-url` | env `DATABASE_URL` | Postgres connection string |
| `--api-key` | env `BRAINTRUST_API_KEY` | Braintrust API key for gateway + tracing |

## Project Structure

```
simulator/
    __init__.py
    cli.py              # Click CLI entry point
    runner.py           # Async runner with concurrency control
    personas.py         # PersonaTemplate dataclass + PERSONA_TEMPLATES list
    user_sim.py         # generate_scenario(), generate_user_message()
    state.py            # ConversationState dataclass + update_state()
```

## Tracing

All conversations are traced through the existing Braintrust tracing in the orchestrator. Each simulated conversation produces a trace identical to a real user conversation. The simulator adds metadata to the session span:

```python
session_span.log(metadata={
    "simulation": True,
    "persona_id": persona.id,
    "scenario": scenario["scenario_description"],
    "expected_resolution": scenario["expected_resolution"],
    "end_reason": state.end_reason,
    "final_frustration": state.frustration,
    "turns": state.turns_taken,
})
```

This metadata enables filtering in Braintrust:
- `metadata.simulation = true` to find all simulated conversations
- `metadata.persona_id = "edge_adversarial"` to find edge case runs
- `metadata.end_reason = "frustrated"` to find conversations that went badly
- `metadata.final_frustration > 0.7` to find high-frustration conversations

## What This Does NOT Do

- **No inline scoring or evaluation.** The simulator generates traffic; evals happen in Braintrust.
- **No Chainlit/HTTP testing.** Calls the orchestrator directly for speed.
- **No deterministic replay.** Each run generates different scenarios. For reproducibility, log the generated scenarios.
- **No rate limiting against external APIs.** The Braintrust gateway and LLM providers handle their own rate limits. If we hit 429s, the OpenAI SDK retries automatically.

## Reference

- Agent orchestrator: `src/agent/orchestrator.py`
- Braintrust tracing: `src/tracing/braintrust.py`
- Existing personas from traces: `resources/trace-analysis.md` (Section: Conversation Flow Patterns)
