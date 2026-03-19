# Salesforce Help Agent Reconstruction - Design Spec

> Functional reconstruction of the Salesforce Agentforce Help Agent based on trace analysis of 100 real customer support sessions.

## Goals

- **Primary:** Build a working help agent that replicates the core behaviors observed in production traces (knowledge answers, case creation, agent transfer, case management).
- **Secondary:** Establish infrastructure (scraper pipeline, question corpus, tracing) that supports future evals and conversation simulation.
- **Constraint:** Functional demo first, but every component must be designed to extend toward full reconstruction (all product categories, all topics, all tools, guardrails).

## Stack

| Component | Choice | Rationale |
|---|---|---|
| Language | Python | Matches original agent's SDK (OpenTelemetry Python), Braintrust SDK, data ecosystem |
| LLM Gateway | Braintrust AI Gateway | Model-agnostic (swap via config), built-in tracing, caching, OpenAI-compatible API |
| Database | PostgreSQL + pgvector | Production-grade, vector search for RAG, deployable |
| Chat Frontend | Chainlit | Python-native, agent-friendly (tool call display, streaming), Docker-ready |
| Containerization | Docker Compose | Local dev and Railway deployment |
| Deployment | Railway | Postgres provisioning, env var management, public URL |

## Architecture

### Two-Phase Orchestration

Each user message goes through two LLM phases, mirroring the Atlas Reasoning Engine's topic-based architecture:

```
User message
    |
    v
Phase 1: CLASSIFY (fast/cheap model)
    |  Input: topic descriptions + user message + recent history
    |  Output: topic_id, confidence
    |
    v
Phase 2: EXECUTE (strong model, scoped to classified topic)
    |  Input: full conversation history + topic instructions + scoped tools
    |  Output: assistant response (may include 0-N tool calls via ReAct loop)
    |
    v
Update session state, return response
```

**Why two phases:** The real Agentforce agent classifies intent into a Topic, which scopes available actions and instructions. This prevents the LLM from having to consider all tools at once (scales poorly) and gives us clean observability into routing decisions. The classifier can use a cheaper/faster model while execution uses a stronger one.

**Topic reclassification:** The classifier runs every turn. If it returns a different topic than the current one, the orchestrator switches context. This produces the natural escalation patterns observed in traces (knowledge -> case creation, knowledge -> transfer).

### System Diagram

```
+-----------------------------------------------------+
|                    Chainlit UI                        |
|              (Chat frontend, streaming)               |
+-------------------------+----------------------------+
                          | HTTP/WebSocket
+-------------------------v----------------------------+
|                   Agent Server                        |
|                                                       |
|  +--------------+    +----------------------------+   |
|  |   Session    |    |      Orchestrator          |   |
|  |   Manager    +--->|                            |   |
|  |              |    |  1. Topic Classifier       |   |
|  | (conv history|    |     (fast model via GW)    |   |
|  |  auth state, |    |            |               |   |
|  |  tenant ctx) |    |  2. Topic Executor         |   |
|  +--------------+    |     (strong model via GW)  |   |
|                      |     (scoped tools + instr) |   |
|                      +-------------+--------------+   |
|                                    |                  |
|  +---------------------------------v---------------+  |
|  |              Tool Registry                      |  |
|  | Knowledge | UserCtx | CreateCase | Transfer |.. |  |
|  +-----+----------+----------+----------+---------+  |
+--------|-----------|---------|-----------|-----------+
         |           |         |           |
   +-----v---+ +----v----+ +--v------+    |
   |Postgres  | |Postgres | |Postgres |    |
   |pgvector  | | users   | | cases   |    |
   |(articles)| |(tenant) | |         |    |
   +----------+ +---------+ +---------+    |
                                      (simulated)
```

All LLM calls route through the Braintrust gateway with `x-bt-parent` headers for automatic trace logging.

## Topics

Each topic is a structured definition containing a classification trigger, behavioral instructions, and scoped tools.

### Topic Definition Structure

```python
@dataclass
class Topic:
    id: str                          # e.g., "knowledge_faq"
    name: str                        # e.g., "Knowledge & FAQ"
    classification_description: str  # when the classifier should select this topic
    instructions: str                # natural language behavioral instructions for the executor
    tools: list[str]                 # tool names available in this topic
```

### Classifier Output

The classifier returns structured JSON:

```python
@dataclass
class ClassifierResult:
    topic_id: str          # one of the registered topic IDs
    confidence: float      # 0.0 to 1.0
```

The classifier uses JSON mode / structured output. If confidence is below `0.3`, the orchestrator defaults to `off_topic`. This threshold is a tuning parameter.

### Demo Topics

| Topic ID | Tools | Purpose |
|---|---|---|
| `knowledge_faq` | `search_knowledge` | Answer questions using KB articles. Cite sources with URLs. |
| `case_creation` | `get_user_context`, `create_case`, `emit_event` | Structured case intake: confirm tenant, collect timezone, description, severity (1-4), phone for sev 1-2, confirm, create. |
| `agent_transfer` | `get_user_context`, `validate_and_transfer`, `emit_event` | Check auth, prompt login if needed, validate eligibility, initiate transfer. |
| `case_management` | `get_user_context`, `get_recent_cases`, `get_case`, `perform_case_action` | Look up existing cases, check status, perform actions (reopen, update). |
| `off_topic` | *(none)* | Redirect user to approved topics. Refuse to engage with out-of-scope requests. |

### Topic Consolidation from Traces

The trace analysis identifies 9 distinct topic suffixes. For the demo, we consolidate these into 5 topics:

| Trace Suffix(es) | Trace Topic | Demo Topic | Rationale |
|---|---|---|---|
| `_179Ek000000DZb8` | Knowledge | `knowledge_faq` | Direct 1:1 mapping. |
| `_179Ek000000DZb3` | Case Management/Support | `case_creation` + `agent_transfer` | The trace topic is broad (includes CreateCase, Transfer, Event, UserContext). We split it into two demo topics for cleaner separation of concerns. The trade-off is that our classifier must distinguish "create case" from "transfer to agent" where the real agent may handle both under one topic. |
| `_179Ek000000DZb5` | Agent Transfer | `agent_transfer` | Merged with the transfer portion of DZb3. In traces, DZb5 has only UserContext + ValidateAndTransfer (no Event). We add `emit_event` to our transfer topic because auth prompts (LOGIN_REQUESTED) are needed before transfer. |
| `_179Ek000000GAvd` | User Context/Auth | *(absorbed)* | Not a standalone topic in our design. User context checks happen as tool calls within other topics (case_creation, agent_transfer). |
| `_179Ea0000058Pnx` | Existing Case Mgmt | `case_management` | Direct mapping. |
| `_179Em00000080Kg` | Case Lookup | `case_management` | Merged with existing case management - both deal with querying cases. |
| `_179Ek000000DZb9` | UI Events | *(absorbed)* | Event emission happens as a tool within other topics, not a standalone topic. |
| `_179Ek000000DZbA` | Personalization | *(path-to-B)* | Only 3 occurrences in traces. Deferred. |
| `_179Ea000005A3gD` | Supervisor Escalation | *(path-to-B)* | Only 1 occurrence. Deferred. |

### Path-to-B Topics

- `personalization` - CSM lookup, personalized solutions
- `supervisor_escalation` - Raise flag for supervisor review
- `harmful_content` - Prompt injection detection, toxicity rejection

## Tools

### Tool Interface

```python
class Tool(ABC):
    name: str
    description: str           # for the LLM's tool-calling schema
    parameters: dict           # JSON schema for input

    async def execute(self, params: dict, session: SessionState) -> ToolResult

@dataclass
class ToolResult:
    status: str                # "ok" or "error"
    output: dict | str         # tool response data
    latency_ms: float
```

### Tool Implementations

| Canonical Name | Backend | Notes |
|---|---|---|
| `get_datetime` | Python stdlib | Returns UTC timestamp. Called as bootstrap on session start. |
| `search_knowledge` | Postgres pgvector | Embeds query via gateway `/embeddings`, cosine similarity against `article_chunks`. Returns top-K results with URLs, scores, snippets. |
| `get_user_context` | Postgres `users` table | Looks up tenant by session auth state. Returns tenant name, product, org ID, success plan, timezone, eligibility flags. Returns `NOT_AUTHENTICATED` if no auth. |
| `create_case` | Postgres `cases` table | Inserts case record from collected intake slots. Returns case number and confirmation message. |
| `validate_and_transfer` | Simulated | Checks eligibility flags from user context, returns success/failure. Actual transfer is simulated. |
| `emit_event` | Chainlit callback | Sends UI events. `LOGIN_REQUESTED` triggers simulated login flow. `showOrgPickerModalForASA` triggers simulated org picker. |
| `get_recent_cases` | Postgres `cases` table | Queries recent cases for authenticated user. |
| `get_case` | Postgres `cases` table | Looks up specific case by number. |
| `perform_case_action` | Postgres `cases` table | Updates case status (reopen, update, etc.). |
| `raise_flag_for_supervisor` | Simulated | Logs escalation, returns confirmation. Placeholder. |
| `get_personalization` | Simulated | Returns mock CSM info. Placeholder for path-to-B. |

## Database Schema

### PostgreSQL + pgvector

```sql
-- Knowledge base (populated by scraper)
CREATE TABLE articles (
    id              SERIAL PRIMARY KEY,
    url             TEXT UNIQUE,
    title           TEXT,
    content         TEXT,
    product_category    TEXT,
    product_sub_category TEXT,
    related_urls    JSONB,           -- "See Also" links, stored as metadata
    scraped_at      TIMESTAMP
);

CREATE TABLE article_chunks (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER REFERENCES articles(id),
    chunk_index     INTEGER,
    chunk_text      TEXT,
    embedding       vector(1536),
    UNIQUE(article_id, chunk_index)
);

-- Generated questions for evals/simulation
CREATE TABLE questions (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER REFERENCES articles(id),
    question_text   TEXT,
    generated_at    TIMESTAMP
);

-- Simulated tenant data
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    tenant_name     TEXT,
    org_id          TEXT,
    product         TEXT,
    success_plan    TEXT,            -- "Premier", "Standard", etc.
    timezone        TEXT,
    phone_number    TEXT,
    can_create_case         BOOLEAN DEFAULT true,
    is_chat_transfer_allowed BOOLEAN DEFAULT true,
    is_authenticated        BOOLEAN DEFAULT false  -- seed data only: controls initial auth state for test users. Runtime auth is tracked per-session via SessionState.auth_state (None = not authenticated).
);

-- Case management (linked to users by org_id, matching trace behavior where cases are tenant-scoped)
CREATE TABLE cases (
    id              SERIAL PRIMARY KEY,
    case_number     TEXT UNIQUE,
    user_id         INTEGER REFERENCES users(id),
    tenant_name     TEXT,
    org_id          TEXT,
    subject         TEXT,
    description     TEXT,
    severity        INTEGER CHECK (severity BETWEEN 1 AND 4),
    status          TEXT DEFAULT 'open',
    created_at      TIMESTAMP DEFAULT now()
);

-- Session persistence
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,
    state_json      JSONB,
    updated_at      TIMESTAMP DEFAULT now()
);

-- pgvector index for similarity search (HNSW - works on empty tables, good at all scales)
CREATE INDEX ON article_chunks USING hnsw (embedding vector_cosine_ops);
```

> **Note:** The `vector(1536)` dimension must match the chosen embedding model's output dimension. `text-embedding-3-small` defaults to 1536. If swapping to a different embedding model, update the column dimension accordingly.

## Session State

```python
@dataclass
class AuthState:
    tenant_name: str
    org_id: str
    product: str
    success_plan: str              # "Premier", "Standard", etc.
    timezone: str | None
    phone_number: str | None
    can_create_case: bool
    is_chat_transfer_allowed: bool

@dataclass
class CaseIntakeState:
    tenant_confirmed: bool = False
    timezone: str | None = None
    description: str | None = None
    severity: int | None = None    # 1-4
    phone_number: str | None = None  # Required for severity 1-2
    summary_confirmed: bool = False

`CaseIntakeState` is populated by the orchestrator when the `create_case` tool is called. The LLM gathers required information conversationally (guided by topic instructions), then passes the complete set of fields as parameters to `create_case`. The intake state tracks what has been collected so far, allowing the orchestrator to inform the LLM which fields are still missing if the tool call is incomplete.

@dataclass
class SessionState:
    session_id: str
    conversation_history: list[Message]
    current_topic: str | None
    auth_state: AuthState | None        # tenant info or None (NOT_AUTHENTICATED)
    case_intake: CaseIntakeState | None # slots being collected during case creation
    turn_count: int
    session_timestamp: datetime         # set by bootstrap GetDateTime call
    created_at: datetime
```

Stored in-memory per Chainlit session, persisted to `sessions` table for durability.

### Conversation History Management

The full `conversation_history` is passed to the executor LLM. To manage token budgets:
- Include all messages up to a configurable token limit (default: 8000 tokens of history).
- When history exceeds the limit, truncate from the oldest turns, always preserving the most recent 4 turns.
- Messages include role, content, and any tool call/result pairs.

### Bootstrap Turn

On session start, the orchestrator calls `get_datetime` **directly, bypassing classification** (this is a global utility, not topic-scoped). This matches the pattern in every production trace where turn 0 is always "What's the current date and time?". The result is stored as `session_timestamp` on `SessionState`.

### Automated Messages

The platform injects synthetic user messages for lifecycle events. We simulate these in Chainlit:
- `"Automated message: log in successful"` - after simulated login flow
- `"Automated message: Tenant Id Changed."` - after org picker selection
- `"Automated message: org selection cancelled"` - after org picker dismissal

## Error Handling

Tool errors are returned to the executor LLM as observation text so it can reason about recovery. The agent does not crash on tool failures - the LLM decides what to do.

| Scenario | Behavior |
|---|---|
| `search_knowledge` returns no results | LLM receives empty results, responds that it couldn't find relevant articles, suggests alternatives (create case, transfer). |
| `get_user_context` returns `NOT_AUTHENTICATED` | LLM receives the NOT_AUTHENTICATED status. For case creation/transfer, it should trigger `emit_event` with LOGIN_REQUESTED. For knowledge queries, it proceeds without auth. |
| `validate_and_transfer` fails eligibility | LLM receives the failure reason, communicates it to the user, suggests alternatives. |
| LLM returns tool call not in current topic scope | Orchestrator rejects the call, returns an error observation to the LLM: "Tool {name} is not available in the current topic ({topic_id})." LLM must choose from scoped tools. |
| Database connection error | Tool returns status "error" with a generic message. LLM apologizes and suggests trying again. |
| LLM call fails (gateway error) | Orchestrator retries once. On second failure, returns a static error message to the user. |

## Knowledge Base Scraper Pipeline

A standalone CLI tool that crawls Salesforce Help articles and loads them into Postgres.

### Crawl Hierarchy

```
help.salesforce.com/s/products
  └── Product Category (e.g., "Sales")
        └── Product Sub-Category (e.g., "Sales Cloud Einstein")
              └── Doc pages (individual articles)
                    └── "See Also" links (stored as metadata, not followed)
```

### Pipeline Steps

```
scraper CLI (e.g., `python -m scraper --category platform`)
    |
    v
1. Playwright (headless browser)
    |  Navigate product category page
    |  Discover sub-category links
    |  For each sub-category, discover doc page links
    |  For each doc page: extract title, content, breadcrumb, "See Also" links
    |
    v
2. Upsert into articles table
    |  Deduplicate by URL, track scraped_at for incremental runs
    |
    v
3. Chunking
    |  Split articles into ~500-token chunks, preserve metadata per chunk
    |
    v
4. Embedding (via Braintrust gateway /embeddings endpoint)
    |  Batch embed chunks, store in article_chunks with vector
    |
    v
5. Question Generation (via Braintrust gateway)
    |  For each article: generate 3-5 realistic customer questions
    |  Store in questions table linked to article
```

### Design Decisions

- **"See Also" links stored but not followed** - prevents unbounded graph traversal during scraping. Cross-links resolve naturally when the target category is scraped separately.
- **Incremental** - deduplicates by URL (skips articles already in the database). Does not detect content changes in existing articles; re-scraping a URL requires deleting the existing row first or passing a `--force` flag.
- **Rate-limited** - respectful crawl delays.
- **Category-scoped** - run per category/sub-category. Start narrow (topics from traces), expand by running more categories.
- **Question generation** - produces eval/simulation corpus alongside the knowledge base.

### Demo Seed Coverage

Based on query topics observed in traces: core platform, reports, lead management, authentication, DKIM/DMARC, data loader, Tableau basics, Slack basics.

## Tracing & Observability

### Span Hierarchy (mirrors original OpenTelemetry traces)

```
Session span (root)
  └── Turn span (one per user message)
        ├── classify span (topic classifier LLM call)
        ├── execute span (executor LLM call)
        └── tool_call span(s) (one per tool invocation)
              ├── input params
              ├── output data
              └── latency_ms
```

### Implementation

```python
from braintrust import init_logger

logger = init_logger(project="sfdc-help-agent")

# Per session
session_span = logger.start_span(name="session", session_id=session_id)

# Per turn
turn_span = session_span.start_span(name=f"turn.{turn_count}")

# Classifier call
classify_span = turn_span.start_span(name="classify")
# LLM call with extra_headers={"x-bt-parent": classify_span.export()}
classify_span.log(output={"topic": topic_id, "confidence": score})
classify_span.end()

# Executor call (with nested tool calls)
execute_span = turn_span.start_span(name="execute")
# LLM call with extra_headers={"x-bt-parent": execute_span.export()}

# Tool calls nested under execute
tool_span = execute_span.start_span(name=f"tool_call.{tool_name}")
tool_span.log(input=params, output=result, metrics={"latency_ms": ms})
tool_span.end()
```

### Logged Data

| Span | Data |
|---|---|
| Session | session_id, user_id, total turns, total duration |
| Turn | user message, assistant response, topic classified, topic_changed (bool) |
| Classify | message + history summary, topic + confidence, model, tokens |
| Execute | full prompt, response + tool calls, model, tokens |
| Tool call | tool name, input params, output, latency, status |

## Project Structure

```
sfdc/
├── resources/                    # Existing - trace data, analysis, reference docs
│   ├── traces.jsonl
│   ├── trace-analysis.md
│   ├── resources.md
│   └── how_agentforce_works.md
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # Main loop: classify -> execute -> respond
│   │   ├── classifier.py         # Topic classification (LLM call)
│   │   ├── executor.py           # Topic-scoped execution (LLM call + tool loop)
│   │   ├── session.py            # Session state management
│   │   └── config.py             # Models, temperature, gateway URL, etc.
│   ├── topics/
│   │   ├── __init__.py
│   │   ├── base.py               # Topic dataclass definition
│   │   ├── knowledge.py          # Knowledge/FAQ topic config
│   │   ├── case_creation.py      # Case creation topic config
│   │   ├── agent_transfer.py     # Transfer topic config
│   │   ├── case_management.py    # Existing case management topic config
│   │   └── off_topic.py          # Off-topic guardrail config
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py               # Tool ABC + ToolResult
│   │   ├── registry.py           # Tool registry (name -> implementation)
│   │   ├── datetime_tool.py
│   │   ├── knowledge.py          # pgvector search
│   │   ├── user_context.py       # Tenant lookup
│   │   ├── create_case.py
│   │   ├── validate_transfer.py
│   │   ├── emit_event.py
│   │   ├── get_case.py
│   │   ├── get_recent_cases.py
│   │   ├── perform_case_action.py
│   │   └── raise_flag.py
│   ├── tracing/
│   │   ├── __init__.py
│   │   └── braintrust.py         # Span hierarchy, logging helpers
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py         # Async Postgres connection pool
│   │   ├── models.py             # Table definitions
│   │   └── seed.py               # Seed simulated users/tenants
│   └── app.py                    # Chainlit app entry point
├── scraper/
│   ├── __init__.py
│   ├── cli.py                    # CLI entry point
│   ├── crawler.py                # Playwright page navigation
│   ├── parser.py                 # Extract content, title, breadcrumb, see-also
│   ├── chunker.py                # Split articles into chunks
│   ├── embedder.py               # Batch embed via gateway
│   ├── question_gen.py           # Generate questions per article
│   └── loader.py                 # Upsert into Postgres
├── db/
│   └── migrations/
│       └── 001_initial.sql       # All tables
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

## Deployment

### Docker Compose

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/migrations:/docker-entrypoint-initdb.d
    environment:
      POSTGRES_DB: sfdc
      POSTGRES_USER: sfdc
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"

  agent:
    build: .
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://sfdc:${DB_PASSWORD}@db:5432/sfdc
      - BRAINTRUST_API_KEY=${BRAINTRUST_API_KEY}
      - CLASSIFIER_MODEL=claude-haiku-4-5
      - EXECUTOR_MODEL=claude-sonnet-4-5
      - EMBEDDING_MODEL=text-embedding-3-small
    ports:
      - "8000:8000"

volumes:
  pgdata:
```

### Configuration (all via environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection string | - |
| `BRAINTRUST_API_KEY` | Gateway auth + tracing | - |
| `CLASSIFIER_MODEL` | Model for topic classification | `claude-haiku-4-5` |
| `EXECUTOR_MODEL` | Model for topic execution | `claude-sonnet-4-5` |
| `EMBEDDING_MODEL` | Model for article/query embeddings | `text-embedding-3-small` |
| `CLASSIFIER_TEMPERATURE` | Temperature for classifier | `0.0` |
| `EXECUTOR_TEMPERATURE` | Temperature for executor | `0.2` |
| `EXECUTOR_MAX_TOKENS` | Max tokens for executor response | `4096` |

The executor temperature of `0.2` matches the production agent's configuration observed in traces.

### Railway

Railway deployment requires configuring services individually (not auto-detected from docker-compose). Setup:
1. Create a Railway project with two services: the Python app and a Postgres database (Railway provisions Postgres natively).
2. Set `DATABASE_URL` on the app service to the Railway-provided Postgres connection string.
3. Set `BRAINTRUST_API_KEY` and model config env vars on the app service.
4. Configure the app service to build from the Dockerfile, expose port 8000.
5. Run migrations against the Railway Postgres instance.

Detailed deployment steps to be documented in a separate Railway deployment guide.

## Reference

- Trace analysis: `resources/trace-analysis.md`
- Original traces: `resources/traces.jsonl`
- Agentforce architecture: `resources/resources.md`
- Agentforce demo transcript: `resources/how_agentforce_works.md`
