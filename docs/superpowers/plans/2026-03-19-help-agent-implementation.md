# Help Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a functional Salesforce Help Agent reconstruction with two-phase orchestration (classify then execute), 11 tools, 5 topics, Braintrust tracing, Postgres/pgvector backend, and Chainlit frontend.

**Architecture:** Two-phase per turn: a fast LLM classifies intent into a topic (scoping available tools), then a stronger LLM executes within that topic's context via a ReAct tool-calling loop. All LLM calls go through the Braintrust gateway for model-agnosticism and tracing.

**Tech Stack:** Python 3.12+, OpenAI SDK (via Braintrust gateway), PostgreSQL + pgvector, Chainlit, Docker Compose, Braintrust SDK, asyncpg, Playwright (scraper)

**Spec:** `docs/superpowers/specs/2026-03-19-help-agent-reconstruction-design.md`

---

## Phase 1: Project Scaffold & Infrastructure

### Task 1: Project setup (pyproject.toml, Docker, .env, git init)

**Files:**
- Create: `pyproject.toml`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `db/migrations/001_initial.sql`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/dpg/repos/sfdc
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.env
.venv/
*.egg-info/
dist/
build/
.chainlit/
```

- [ ] **Step 3: Create pyproject.toml**

```toml
[project]
name = "sfdc-help-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.40.0",
    "braintrust>=0.0.160",
    "chainlit>=1.1.0",
    "asyncpg>=0.29.0",
    "pgvector>=0.3.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "tiktoken>=0.7.0",
    "numpy>=1.26.0",
]

[project.optional-dependencies]
scraper = [
    "playwright>=1.45.0",
    "click>=8.1.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.14.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 4: Create .env.example**

```env
DATABASE_URL=postgresql://sfdc:sfdc@localhost:5432/sfdc
BRAINTRUST_API_KEY=sk-your-key-here
CLASSIFIER_MODEL=claude-haiku-4-5
EXECUTOR_MODEL=claude-sonnet-4-5
EMBEDDING_MODEL=text-embedding-3-small
CLASSIFIER_TEMPERATURE=0.0
EXECUTOR_TEMPERATURE=0.2
EXECUTOR_MAX_TOKENS=4096
```

- [ ] **Step 5: Create db/migrations/001_initial.sql**

Full SQL schema from the spec (articles, article_chunks, questions, users, cases, sessions tables + HNSW index + pgvector extension).

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE articles (
    id                   SERIAL PRIMARY KEY,
    url                  TEXT UNIQUE,
    title                TEXT,
    content              TEXT,
    product_category     TEXT,
    product_sub_category TEXT,
    related_urls         JSONB,
    scraped_at           TIMESTAMP
);

CREATE TABLE article_chunks (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index     INTEGER,
    chunk_text      TEXT,
    embedding       vector(1536),
    UNIQUE(article_id, chunk_index)
);

CREATE TABLE questions (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    question_text   TEXT,
    generated_at    TIMESTAMP DEFAULT now()
);

CREATE TABLE users (
    id                       SERIAL PRIMARY KEY,
    tenant_name              TEXT,
    org_id                   TEXT UNIQUE,
    product                  TEXT,
    success_plan             TEXT,
    timezone                 TEXT,
    phone_number             TEXT,
    can_create_case          BOOLEAN DEFAULT true,
    is_chat_transfer_allowed BOOLEAN DEFAULT true,
    is_authenticated         BOOLEAN DEFAULT false
);

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

CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,
    state_json      JSONB,
    updated_at      TIMESTAMP DEFAULT now()
);

CREATE INDEX ON article_chunks USING hnsw (embedding vector_cosine_ops);
```

- [ ] **Step 6: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

COPY src/ src/
COPY .chainlit/ .chainlit/ 2>/dev/null || true

EXPOSE 8000
CMD ["chainlit", "run", "src/app.py", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Create docker-compose.yml**

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
      POSTGRES_PASSWORD: ${DB_PASSWORD:-sfdc}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sfdc"]
      interval: 5s
      timeout: 5s
      retries: 5

  agent:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://sfdc:${DB_PASSWORD:-sfdc}@db:5432/sfdc
      - BRAINTRUST_API_KEY=${BRAINTRUST_API_KEY}
      - CLASSIFIER_MODEL=${CLASSIFIER_MODEL:-claude-haiku-4-5}
      - EXECUTOR_MODEL=${EXECUTOR_MODEL:-claude-sonnet-4-5}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL:-text-embedding-3-small}
      - CLASSIFIER_TEMPERATURE=${CLASSIFIER_TEMPERATURE:-0.0}
      - EXECUTOR_TEMPERATURE=${EXECUTOR_TEMPERATURE:-0.2}
      - EXECUTOR_MAX_TOKENS=${EXECUTOR_MAX_TOKENS:-4096}
    ports:
      - "8000:8000"

volumes:
  pgdata:
```

- [ ] **Step 8: Create directory structure**

```bash
mkdir -p src/agent src/topics src/tools src/tracing src/db tests/agent tests/tools tests/topics
touch src/__init__.py src/agent/__init__.py src/topics/__init__.py src/tools/__init__.py src/tracing/__init__.py src/db/__init__.py
```

- [ ] **Step 9: Verify Docker Compose starts**

```bash
docker compose up db -d
# Wait for healthy
docker compose exec db psql -U sfdc -c "SELECT 1 FROM pg_extension WHERE extname = 'vector';"
# Expected: 1 row
docker compose down
```

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml Dockerfile docker-compose.yml .env.example .gitignore db/ src/
git commit -m "feat: project scaffold with Docker, Postgres+pgvector, and Python project config"
```

---

### Task 2: Config module and DB connection

**Files:**
- Create: `src/agent/config.py`
- Create: `src/db/connection.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write test for config loading**

```python
# tests/test_config.py
import os
from agent.config import Settings

def test_settings_defaults():
    settings = Settings()
    assert settings.classifier_model == "claude-haiku-4-5"
    assert settings.executor_model == "claude-sonnet-4-5"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.classifier_temperature == 0.0
    assert settings.executor_temperature == 0.2
    assert settings.executor_max_tokens == 4096
    assert settings.confidence_threshold == 0.3

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("EXECUTOR_MODEL", "gpt-4o")
    monkeypatch.setenv("EXECUTOR_TEMPERATURE", "0.5")
    settings = Settings()
    assert settings.executor_model == "gpt-4o"
    assert settings.executor_temperature == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dpg/repos/sfdc && uv pip install -e ".[dev]" && PYTHONPATH=src pytest tests/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement config.py**

```python
# src/agent/config.py
from __future__ import annotations
import os

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://sfdc:sfdc@localhost:5432/sfdc"
    braintrust_api_key: str = ""
    gateway_base_url: str = "https://gateway.braintrust.dev"

    classifier_model: str = "claude-haiku-4-5"
    executor_model: str = "claude-sonnet-4-5"
    embedding_model: str = "text-embedding-3-small"

    classifier_temperature: float = 0.0
    executor_temperature: float = 0.2
    executor_max_tokens: int = 4096

    confidence_threshold: float = 0.3
    history_token_limit: int = 8000
    history_min_turns: int = 4

    model_config = {"env_prefix": "", "case_sensitive": False}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Implement db/connection.py**

```python
# src/db/connection.py
from __future__ import annotations
import asyncpg
from agent.config import Settings


_pool: asyncpg.Pool | None = None


async def get_pool(settings: Settings | None = None) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        s = settings or Settings()
        _pool = await asyncpg.create_pool(
            s.database_url, min_size=2, max_size=10,
            init=_init_connection,
        )
    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register pgvector codec on each new connection."""
    from pgvector.asyncpg import register_vector
    await register_vector(conn)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
```

- [ ] **Step 6: Commit**

```bash
git add src/agent/config.py src/db/connection.py tests/test_config.py pyproject.toml
git commit -m "feat: config module with env-based settings and async DB connection pool"
```

---

## Phase 2: Data Models & Tool Foundation

### Task 3: Data models (SessionState, AuthState, CaseIntakeState, Message)

**Files:**
- Create: `src/agent/models.py`
- Create: `tests/agent/test_models.py`

- [ ] **Step 1: Write tests for data models**

```python
# tests/agent/test_models.py
from agent.models import SessionState, AuthState, CaseIntakeState, Message


def test_session_state_defaults():
    state = SessionState(session_id="test-123")
    assert state.current_topic is None
    assert state.auth_state is None
    assert state.case_intake is None
    assert state.turn_count == 0
    assert state.conversation_history == []


def test_auth_state():
    auth = AuthState(
        tenant_name="ACME Corp",
        org_id="00D123456789",
        product="core",
        success_plan="Premier",
    )
    assert auth.can_create_case is True
    assert auth.is_chat_transfer_allowed is True
    assert auth.timezone is None


def test_case_intake_state_missing_fields():
    intake = CaseIntakeState()
    missing = intake.missing_fields()
    assert "description" in missing
    assert "severity" in missing
    assert "timezone" in missing


def test_case_intake_state_phone_required_for_sev1():
    intake = CaseIntakeState(
        tenant_confirmed=True, timezone="UTC",
        description="broken", severity=1,
    )
    missing = intake.missing_fields()
    assert "phone_number" in missing


def test_case_intake_state_phone_not_required_for_sev3():
    intake = CaseIntakeState(
        tenant_confirmed=True, timezone="UTC",
        description="broken", severity=3,
    )
    missing = intake.missing_fields()
    assert "phone_number" not in missing


def test_message_serialization():
    msg = Message(role="user", content="hello")
    d = msg.model_dump()
    assert d["role"] == "user"
    assert d["content"] == "hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/agent/test_models.py -v`
Expected: FAIL

- [ ] **Step 3: Implement models.py**

```python
# src/agent/models.py
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str  # "user", "assistant", "tool"
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class AuthState(BaseModel):
    tenant_name: str
    org_id: str
    product: str
    success_plan: str = "Standard"
    timezone: str | None = None
    phone_number: str | None = None
    can_create_case: bool = True
    is_chat_transfer_allowed: bool = True


class CaseIntakeState(BaseModel):
    tenant_confirmed: bool = False
    timezone: str | None = None
    description: str | None = None
    severity: int | None = None
    phone_number: str | None = None
    summary_confirmed: bool = False

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.tenant_confirmed:
            missing.append("tenant_confirmed")
        if self.timezone is None:
            missing.append("timezone")
        if self.description is None:
            missing.append("description")
        if self.severity is None:
            missing.append("severity")
        if self.severity is not None and self.severity <= 2 and self.phone_number is None:
            missing.append("phone_number")
        if not self.summary_confirmed:
            missing.append("summary_confirmed")
        return missing


class ClassifierResult(BaseModel):
    topic_id: str
    confidence: float


class SessionState(BaseModel):
    session_id: str
    conversation_history: list[Message] = Field(default_factory=list)
    current_topic: str | None = None
    auth_state: AuthState | None = None
    case_intake: CaseIntakeState | None = None
    turn_count: int = 0
    session_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/agent/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent/models.py tests/agent/test_models.py
git commit -m "feat: data models for session state, auth, case intake, and messages"
```

---

### Task 4: Tool base class and registry

**Files:**
- Create: `src/tools/base.py`
- Create: `src/tools/registry.py`
- Create: `tests/tools/test_registry.py`

- [ ] **Step 1: Write tests for tool registry**

```python
# tests/tools/test_registry.py
import pytest
from tools.base import Tool, ToolResult
from tools.registry import ToolRegistry


class FakeTool(Tool):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters = {"type": "object", "properties": {"x": {"type": "string"}}}

    async def execute(self, params, session):
        return ToolResult(status="ok", output={"echo": params["x"]})


def test_register_and_get():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)
    assert registry.get("fake_tool") is tool


def test_get_unknown_returns_none():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_get_tools_for_names():
    registry = ToolRegistry()
    registry.register(FakeTool())
    tools = registry.get_tools_for_names(["fake_tool", "nonexistent"])
    assert len(tools) == 1
    assert tools[0].name == "fake_tool"


def test_get_openai_tool_schemas():
    registry = ToolRegistry()
    registry.register(FakeTool())
    schemas = registry.get_openai_tool_schemas(["fake_tool"])
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "fake_tool"


@pytest.mark.asyncio
async def test_execute_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    result = await registry.execute("fake_tool", {"x": "hello"}, session=None)
    assert result.status == "ok"
    assert result.output["echo"] == "hello"


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {}, session=None)
    assert result.status == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/tools/test_registry.py -v`
Expected: FAIL

- [ ] **Step 3: Implement base.py and registry.py**

```python
# src/tools/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Any

from agent.models import SessionState


@dataclass
class ToolResult:
    status: str  # "ok" or "error"
    output: Any
    latency_ms: float = 0.0


class Tool(ABC):
    name: str
    description: str
    parameters: dict

    @abstractmethod
    async def execute(self, params: dict, session: SessionState | None) -> ToolResult:
        ...
```

```python
# src/tools/registry.py
from __future__ import annotations
import time
from typing import Any

from agent.models import SessionState
from tools.base import Tool, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_tools_for_names(self, names: list[str]) -> list[Tool]:
        return [self._tools[n] for n in names if n in self._tools]

    def get_openai_tool_schemas(self, names: list[str]) -> list[dict]:
        schemas = []
        for tool in self.get_tools_for_names(names):
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas

    async def execute(
        self, name: str, params: dict, session: SessionState | None
    ) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(status="error", output=f"Unknown tool: {name}")
        start = time.monotonic()
        try:
            result = await tool.execute(params, session)
            result.latency_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as e:
            return ToolResult(
                status="error",
                output=str(e),
                latency_ms=(time.monotonic() - start) * 1000,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/tools/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/base.py src/tools/registry.py tests/tools/test_registry.py
git commit -m "feat: tool base class and registry with OpenAI schema generation"
```

---

### Task 5: Topic base class and all 5 topic definitions

**Files:**
- Create: `src/topics/base.py`
- Create: `src/topics/knowledge.py`
- Create: `src/topics/case_creation.py`
- Create: `src/topics/agent_transfer.py`
- Create: `src/topics/case_management.py`
- Create: `src/topics/off_topic.py`
- Create: `src/topics/registry.py`
- Create: `tests/topics/test_topics.py`

- [ ] **Step 1: Write tests for topic registry**

```python
# tests/topics/test_topics.py
from topics.registry import TopicRegistry, get_default_registry


def test_default_registry_has_5_topics():
    registry = get_default_registry()
    assert len(registry.all()) == 5


def test_default_registry_topic_ids():
    registry = get_default_registry()
    ids = {t.id for t in registry.all()}
    assert ids == {"knowledge_faq", "case_creation", "agent_transfer", "case_management", "off_topic"}


def test_get_topic_by_id():
    registry = get_default_registry()
    topic = registry.get("knowledge_faq")
    assert topic is not None
    assert topic.name == "Knowledge & FAQ"
    assert "search_knowledge" in topic.tools


def test_knowledge_topic_has_instructions():
    registry = get_default_registry()
    topic = registry.get("knowledge_faq")
    assert len(topic.instructions) > 50


def test_case_creation_tools():
    registry = get_default_registry()
    topic = registry.get("case_creation")
    assert "get_user_context" in topic.tools
    assert "create_case" in topic.tools
    assert "emit_event" in topic.tools


def test_off_topic_has_no_tools():
    registry = get_default_registry()
    topic = registry.get("off_topic")
    assert topic.tools == []


def test_classification_prompt():
    registry = get_default_registry()
    prompt = registry.classification_prompt()
    assert "knowledge_faq" in prompt
    assert "case_creation" in prompt
    assert "off_topic" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/topics/test_topics.py -v`
Expected: FAIL

- [ ] **Step 3: Implement topic base and definitions**

```python
# src/topics/base.py
from __future__ import annotations
from pydantic import BaseModel


class Topic(BaseModel):
    id: str
    name: str
    classification_description: str
    instructions: str
    tools: list[str]
```

```python
# src/topics/knowledge.py
from topics.base import Topic

KNOWLEDGE_FAQ = Topic(
    id="knowledge_faq",
    name="Knowledge & FAQ",
    classification_description=(
        "The user is asking a how-to question, troubleshooting an error, asking about "
        "Salesforce features or configuration, or requesting documentation. They want "
        "information, not to create a case or talk to a human."
    ),
    instructions=(
        "You are a Salesforce help agent answering questions using the knowledge base.\n\n"
        "1. Search the knowledge base using the search_knowledge tool with the user's question.\n"
        "2. You may call search_knowledge up to 3 times per turn to gather comprehensive results.\n"
        "3. Synthesize the results into a clear, helpful answer.\n"
        "4. Always cite your sources with article URLs.\n"
        "5. If the knowledge base has no relevant results, say so honestly and suggest "
        "the user create a support case or transfer to a human agent.\n"
        "6. Respond in the same language the user writes in."
    ),
    tools=["search_knowledge"],
)
```

```python
# src/topics/case_creation.py
from topics.base import Topic

CASE_CREATION = Topic(
    id="case_creation",
    name="Case Creation",
    classification_description=(
        "The user wants to create a support case, log a case, open a ticket, or report "
        "an issue that needs formal tracking. They may say 'create case', 'open a case', "
        "'log a case', or express that they need to escalate beyond self-service."
    ),
    instructions=(
        "You are helping the user create a Salesforce support case. Follow this process:\n\n"
        "1. Call get_user_context to check authentication and get tenant details.\n"
        "   - If NOT_AUTHENTICATED: call emit_event with LOGIN_REQUESTED and ask the user to log in.\n"
        "   - If authenticated: show the tenant details and ask the user to confirm.\n"
        "2. Ask for the user's timezone.\n"
        "3. Ask for a brief description of the issue.\n"
        "4. Ask for severity level (1-4):\n"
        "   - Severity 1: Critical production issue - business completely stopped or revenue impacted\n"
        "   - Severity 2: Major functionality impacted and time-sensitive\n"
        "   - Severity 3: Minor functionality impacted and time-sensitive\n"
        "   - Severity 4: General inquiry, how-to or routine technical issue\n"
        "5. For severity 1 or 2: ask for a phone number with country code (format: +[code] [number]).\n"
        "6. Summarize all details and ask for final confirmation.\n"
        "7. Call create_case with all collected information.\n"
        "8. Return the case number and tracking link.\n\n"
        "Collect one piece of information per turn. Do not skip steps."
    ),
    tools=["get_user_context", "create_case", "emit_event"],
)
```

```python
# src/topics/agent_transfer.py
from topics.base import Topic

AGENT_TRANSFER = Topic(
    id="agent_transfer",
    name="Agent Transfer",
    classification_description=(
        "The user wants to speak with a human agent, transfer to support, talk to someone, "
        "or be connected to a support engineer. They may say 'transfer to agent', 'talk to "
        "someone', 'speak to a human', or 'connect me to support'."
    ),
    instructions=(
        "You are helping transfer the user to a human support engineer.\n\n"
        "1. Call get_user_context to check authentication.\n"
        "   - If NOT_AUTHENTICATED: call emit_event with LOGIN_REQUESTED and ask them to log in.\n"
        "   - Wait for the 'Automated message: log in successful' before proceeding.\n"
        "2. Once authenticated, show tenant details and ask the user to confirm.\n"
        "3. Call validate_and_transfer to check eligibility and initiate the transfer.\n"
        "   - If eligible: inform the user they are being transferred.\n"
        "   - If not eligible: explain why and suggest alternatives (create a case, try KB).\n"
        "4. Respond in the same language the user writes in."
    ),
    tools=["get_user_context", "validate_and_transfer", "emit_event"],
)
```

```python
# src/topics/case_management.py
from topics.base import Topic

CASE_MANAGEMENT = Topic(
    id="case_management",
    name="Case Management",
    classification_description=(
        "The user is asking about an existing case, wants to check case status, look up "
        "a case number, see recent cases, or perform an action on an existing case "
        "(reopen, update). They are NOT trying to create a new case."
    ),
    instructions=(
        "You are helping the user manage their existing support cases.\n\n"
        "1. Call get_user_context to check authentication.\n"
        "   - If NOT_AUTHENTICATED: ask the user to log in first.\n"
        "2. Based on the user's request:\n"
        "   - To list recent cases: call get_recent_cases.\n"
        "   - To look up a specific case: call get_case with the case number.\n"
        "   - To perform an action (reopen, update): call perform_case_action.\n"
        "3. Present the results clearly.\n"
        "4. Respond in the same language the user writes in."
    ),
    tools=["get_user_context", "get_recent_cases", "get_case", "perform_case_action"],
)
```

```python
# src/topics/off_topic.py
from topics.base import Topic

OFF_TOPIC = Topic(
    id="off_topic",
    name="Off Topic",
    classification_description=(
        "The user's request is outside the scope of Salesforce product support. This includes "
        "requests unrelated to Salesforce, general chitchat, or anything the agent is not "
        "designed to handle."
    ),
    instructions=(
        "The user's request is outside your scope. You are a Salesforce help agent that can:\n"
        "- Answer questions about Salesforce products and features\n"
        "- Create support cases\n"
        "- Transfer to a human support agent\n"
        "- Look up existing cases\n\n"
        "Politely redirect the user to one of these approved topics. Do not attempt to "
        "answer questions outside your scope."
    ),
    tools=[],
)
```

```python
# src/topics/registry.py
from __future__ import annotations
from topics.base import Topic
from topics.knowledge import KNOWLEDGE_FAQ
from topics.case_creation import CASE_CREATION
from topics.agent_transfer import AGENT_TRANSFER
from topics.case_management import CASE_MANAGEMENT
from topics.off_topic import OFF_TOPIC


class TopicRegistry:
    def __init__(self) -> None:
        self._topics: dict[str, Topic] = {}

    def register(self, topic: Topic) -> None:
        self._topics[topic.id] = topic

    def get(self, topic_id: str) -> Topic | None:
        return self._topics.get(topic_id)

    def all(self) -> list[Topic]:
        return list(self._topics.values())

    def classification_prompt(self) -> str:
        lines = ["Classify the user's intent into one of these topics:\n"]
        for topic in self._topics.values():
            lines.append(f"- **{topic.id}**: {topic.classification_description}")
        lines.append(
            "\nRespond with JSON: {\"topic_id\": \"<id>\", \"confidence\": <0.0-1.0>}"
        )
        return "\n".join(lines)


def get_default_registry() -> TopicRegistry:
    registry = TopicRegistry()
    for topic in [KNOWLEDGE_FAQ, CASE_CREATION, AGENT_TRANSFER, CASE_MANAGEMENT, OFF_TOPIC]:
        registry.register(topic)
    return registry
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/topics/test_topics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/topics/ tests/topics/
git commit -m "feat: topic definitions for all 5 demo topics with registry and classification prompt"
```

---

## Phase 3: Tool Implementations

### Task 6: Simple tools (get_datetime, emit_event, raise_flag, validate_transfer, get_personalization)

**Files:**
- Create: `src/tools/datetime_tool.py`
- Create: `src/tools/emit_event.py`
- Create: `src/tools/raise_flag.py`
- Create: `src/tools/validate_transfer.py`
- Create: `src/tools/get_personalization.py`
- Create: `tests/tools/test_simple_tools.py`

- [ ] **Step 1: Write tests**

```python
# tests/tools/test_simple_tools.py
import pytest
from agent.models import SessionState, AuthState
from tools.datetime_tool import GetDateTimeTool
from tools.emit_event import EmitEventTool
from tools.raise_flag import RaiseFlagTool
from tools.validate_transfer import ValidateAndTransferTool
from tools.get_personalization import GetPersonalizationTool


@pytest.mark.asyncio
async def test_get_datetime():
    tool = GetDateTimeTool()
    result = await tool.execute({}, session=None)
    assert result.status == "ok"
    assert "T" in result.output  # ISO format


@pytest.mark.asyncio
async def test_emit_event_login():
    tool = EmitEventTool()
    result = await tool.execute({"event_name": "LOGIN_REQUESTED"}, session=None)
    assert result.status == "ok"
    assert result.output["name"] == "LOGIN_REQUESTED"


@pytest.mark.asyncio
async def test_validate_transfer_authenticated():
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="ACME", org_id="001", product="core",
            is_chat_transfer_allowed=True,
        ),
    )
    tool = ValidateAndTransferTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output["eligible"] is True


@pytest.mark.asyncio
async def test_validate_transfer_not_allowed():
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="ACME", org_id="001", product="core",
            is_chat_transfer_allowed=False,
        ),
    )
    tool = ValidateAndTransferTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output["eligible"] is False


@pytest.mark.asyncio
async def test_validate_transfer_not_authenticated():
    session = SessionState(session_id="test")
    tool = ValidateAndTransferTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert "NOT_AUTHENTICATED" in str(result.output)


@pytest.mark.asyncio
async def test_raise_flag():
    tool = RaiseFlagTool()
    result = await tool.execute({"reason": "customer upset"}, session=None)
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_get_personalization():
    tool = GetPersonalizationTool()
    result = await tool.execute({}, session=None)
    assert result.status == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/tools/test_simple_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Implement all 5 simple tools**

```python
# src/tools/datetime_tool.py
from datetime import datetime, timezone
from tools.base import Tool, ToolResult


class GetDateTimeTool(Tool):
    name = "get_datetime"
    description = "Returns the current date and time in UTC ISO format."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        now = datetime.now(timezone.utc).isoformat()
        return ToolResult(status="ok", output=now)
```

```python
# src/tools/emit_event.py
from tools.base import Tool, ToolResult


class EmitEventTool(Tool):
    name = "emit_event"
    description = "Triggers a UI event. Supported events: LOGIN_REQUESTED, showOrgPickerModalForASA."
    parameters = {
        "type": "object",
        "properties": {
            "event_name": {
                "type": "string",
                "enum": ["LOGIN_REQUESTED", "showOrgPickerModalForASA"],
                "description": "The UI event to trigger.",
            }
        },
        "required": ["event_name"],
    }

    async def execute(self, params, session):
        event_name = params.get("event_name", "")
        return ToolResult(status="ok", output={"name": event_name, "data": None})
```

```python
# src/tools/validate_transfer.py
from tools.base import Tool, ToolResult


class ValidateAndTransferTool(Tool):
    name = "validate_and_transfer"
    description = "Validates whether the user is eligible for transfer to a human support engineer and initiates the transfer."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output={"eligible": False, "reason": "NOT_AUTHENTICATED"})
        if not session.auth_state.is_chat_transfer_allowed:
            return ToolResult(status="ok", output={"eligible": False, "reason": "Chat transfer is not available for this tenant."})
        return ToolResult(
            status="ok",
            output={
                "eligible": True,
                "session_id": session.session_id,
                "message": "Transferring to a support engineer now.",
            },
        )
```

```python
# src/tools/raise_flag.py
from tools.base import Tool, ToolResult


class RaiseFlagTool(Tool):
    name = "raise_flag_for_supervisor"
    description = "Raises a flag for supervisor review and escalation."
    parameters = {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Reason for escalation."}
        },
        "required": ["reason"],
    }

    async def execute(self, params, session):
        return ToolResult(
            status="ok",
            output={"flagged": True, "reason": params.get("reason", "")},
        )
```

```python
# src/tools/get_personalization.py
from tools.base import Tool, ToolResult


class GetPersonalizationTool(Tool):
    name = "get_personalization"
    description = "Returns personalized solutions and Customer Success Manager information."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        return ToolResult(
            status="ok",
            output={
                "csm_name": "Jane Doe",
                "csm_email": "jane.doe@salesforce.com",
                "solutions": ["Schedule a review with your CSM for personalized guidance."],
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/tools/test_simple_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/datetime_tool.py src/tools/emit_event.py src/tools/validate_transfer.py src/tools/raise_flag.py src/tools/get_personalization.py tests/tools/test_simple_tools.py
git commit -m "feat: simple tool implementations (datetime, emit_event, validate_transfer, raise_flag, personalization)"
```

---

### Task 7: Database-backed tools (user_context, create_case, get_case, get_recent_cases, perform_case_action)

**Files:**
- Create: `src/tools/user_context.py`
- Create: `src/tools/create_case.py`
- Create: `src/tools/get_case.py`
- Create: `src/tools/get_recent_cases.py`
- Create: `src/tools/perform_case_action.py`
- Create: `src/db/seed.py`
- Create: `tests/tools/test_db_tools.py`
- Create: `tests/conftest.py`

These tools require a live Postgres instance. Tests use a real database (Docker Compose `db` service must be running).

- [ ] **Step 1: Create test fixtures (conftest.py)**

```python
# tests/conftest.py
import asyncio
import os
import pytest
import asyncpg

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://sfdc:sfdc@localhost:5432/sfdc")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture(autouse=True)
async def clean_tables(db_pool):
    """Clean test data before each test."""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM cases")
        await conn.execute("DELETE FROM sessions")
        # Don't delete users - we need seed data
    yield


@pytest.fixture
async def seeded_db(db_pool):
    """Ensure seed data exists."""
    from db.seed import seed_users
    await seed_users(db_pool)
    return db_pool
```

- [ ] **Step 2: Create seed.py**

```python
# src/db/seed.py
from __future__ import annotations
import asyncpg


SEED_USERS = [
    {
        "tenant_name": "COMPANY_demo_001",
        "org_id": "SFID_demo_001",
        "product": "core",
        "success_plan": "Premier",
        "timezone": "America/Chicago",
        "phone_number": "+1 555-0100",
        "can_create_case": True,
        "is_chat_transfer_allowed": True,
        "is_authenticated": True,
    },
    {
        "tenant_name": "COMPANY_demo_002",
        "org_id": "SFID_demo_002",
        "product": "core",
        "success_plan": "Standard",
        "timezone": None,
        "phone_number": None,
        "can_create_case": True,
        "is_chat_transfer_allowed": False,
        "is_authenticated": True,
    },
    {
        "tenant_name": "COMPANY_demo_003",
        "org_id": "SFID_demo_003",
        "product": "marketing_cloud",
        "success_plan": "Premier",
        "timezone": "Asia/Tokyo",
        "phone_number": "+81 3-1234-5678",
        "can_create_case": True,
        "is_chat_transfer_allowed": True,
        "is_authenticated": False,
    },
]


async def seed_users(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        for user in SEED_USERS:
            await conn.execute(
                """
                INSERT INTO users (tenant_name, org_id, product, success_plan, timezone,
                                   phone_number, can_create_case, is_chat_transfer_allowed, is_authenticated)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (org_id) DO NOTHING
                """,
                user["tenant_name"], user["org_id"], user["product"],
                user["success_plan"], user["timezone"], user["phone_number"],
                user["can_create_case"], user["is_chat_transfer_allowed"],
                user["is_authenticated"],
            )
```

- [ ] **Step 3: Write tests for DB tools**

```python
# tests/tools/test_db_tools.py
import pytest
from agent.models import SessionState, AuthState
from tools.user_context import GetUserContextTool
from tools.create_case import CreateCaseTool
from tools.get_case import GetCaseTool
from tools.get_recent_cases import GetRecentCasesTool
from tools.perform_case_action import PerformCaseActionTool


@pytest.mark.asyncio
async def test_get_user_context_authenticated(seeded_db):
    tool = GetUserContextTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output["tenant_name"] == "COMPANY_demo_001"
    assert result.output["success_plan"] == "Premier"


@pytest.mark.asyncio
async def test_get_user_context_not_authenticated(seeded_db):
    tool = GetUserContextTool(seeded_db)
    session = SessionState(session_id="test")
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_create_case(seeded_db):
    tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    result = await tool.execute({
        "subject": "Test Issue",
        "description": "Something is broken",
        "severity": 3,
        "timezone": "America/Chicago",
    }, session)
    assert result.status == "ok"
    assert "case_number" in result.output


@pytest.mark.asyncio
async def test_get_case(seeded_db):
    # Create a case first
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    create_result = await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)
    case_number = create_result.output["case_number"]

    tool = GetCaseTool(seeded_db)
    result = await tool.execute({"case_number": case_number}, session)
    assert result.status == "ok"
    assert result.output["case_number"] == case_number


@pytest.mark.asyncio
async def test_get_recent_cases(seeded_db):
    # Create a case
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)

    tool = GetRecentCasesTool(seeded_db)
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert len(result.output["cases"]) >= 1


@pytest.mark.asyncio
async def test_perform_case_action_reopen(seeded_db):
    # Create and then reopen
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    create_result = await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)
    case_number = create_result.output["case_number"]

    tool = PerformCaseActionTool(seeded_db)
    result = await tool.execute({
        "case_number": case_number, "action": "reopen",
    }, session)
    assert result.status == "ok"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `docker compose up db -d && PYTHONPATH=src pytest tests/tools/test_db_tools.py -v`
Expected: FAIL (tools not implemented)

- [ ] **Step 5: Implement all 5 DB-backed tools**

```python
# src/tools/user_context.py
from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class GetUserContextTool(Tool):
    name = "get_user_context"
    description = "Retrieves the authenticated user's tenant context including org details, product, and eligibility flags."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE org_id = $1", session.auth_state.org_id
            )
        if row is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        return ToolResult(status="ok", output={
            "tenant_name": row["tenant_name"],
            "org_id": row["org_id"],
            "product": row["product"],
            "success_plan": row["success_plan"],
            "timezone": row["timezone"],
            "phone_number": row["phone_number"],
            "can_create_case": row["can_create_case"],
            "is_chat_transfer_allowed": row["is_chat_transfer_allowed"],
        })
```

```python
# src/tools/create_case.py
from __future__ import annotations
import uuid
import asyncpg
from tools.base import Tool, ToolResult


class CreateCaseTool(Tool):
    name = "create_case"
    description = "Creates a new support case with the provided details."
    parameters = {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Brief case subject."},
            "description": {"type": "string", "description": "Detailed description of the issue."},
            "severity": {"type": "integer", "enum": [1, 2, 3, 4], "description": "Severity level 1-4."},
            "timezone": {"type": "string", "description": "User's timezone."},
            "phone_number": {"type": "string", "description": "Phone with country code (required for sev 1-2)."},
        },
        "required": ["subject", "description", "severity", "timezone"],
    }

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="error", output="NOT_AUTHENTICATED")
        case_number = str(uuid.uuid4().int)[:9]
        async with self._pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE org_id = $1", session.auth_state.org_id
            )
            user_id = user_row["id"] if user_row else None
            await conn.execute(
                """
                INSERT INTO cases (case_number, user_id, tenant_name, org_id, subject, description, severity)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                case_number, user_id, session.auth_state.tenant_name,
                session.auth_state.org_id, params["subject"],
                params["description"], params["severity"],
            )
        return ToolResult(status="ok", output={
            "case_number": case_number,
            "tenant_name": session.auth_state.tenant_name,
            "org_id": session.auth_state.org_id,
            "subject": params["subject"],
            "description": params["description"],
            "severity": params["severity"],
            "success_plan": session.auth_state.success_plan,
            "message": f"Case {case_number} created successfully.",
        })
```

```python
# src/tools/get_case.py
from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class GetCaseTool(Tool):
    name = "get_case"
    description = "Looks up a specific support case by case number."
    parameters = {
        "type": "object",
        "properties": {
            "case_number": {"type": "string", "description": "The case number to look up."},
        },
        "required": ["case_number"],
    }

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM cases WHERE case_number = $1", params["case_number"]
            )
        if row is None:
            return ToolResult(status="ok", output={"error": f"Case {params['case_number']} not found."})
        return ToolResult(status="ok", output={
            "case_number": row["case_number"],
            "subject": row["subject"],
            "description": row["description"],
            "severity": row["severity"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })
```

```python
# src/tools/get_recent_cases.py
from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class GetRecentCasesTool(Tool):
    name = "get_recent_cases"
    description = "Retrieves the most recent support cases for the authenticated user."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT case_number, subject, severity, status, created_at FROM cases WHERE org_id = $1 ORDER BY created_at DESC LIMIT 10",
                session.auth_state.org_id,
            )
        cases = [
            {
                "case_number": r["case_number"],
                "subject": r["subject"],
                "severity": r["severity"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return ToolResult(status="ok", output={"cases": cases})
```

```python
# src/tools/perform_case_action.py
from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class PerformCaseActionTool(Tool):
    name = "perform_case_action"
    description = "Performs an action on an existing case (reopen, close, update)."
    parameters = {
        "type": "object",
        "properties": {
            "case_number": {"type": "string", "description": "The case number."},
            "action": {"type": "string", "enum": ["reopen", "close", "update"], "description": "Action to perform."},
            "comment": {"type": "string", "description": "Optional comment for the action."},
        },
        "required": ["case_number", "action"],
    }

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        action = params["action"]
        new_status = {"reopen": "reopened", "close": "closed", "update": "open"}.get(action, "open")
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE cases SET status = $1 WHERE case_number = $2",
                new_status, params["case_number"],
            )
        if result == "UPDATE 0":
            return ToolResult(status="error", output=f"Case {params['case_number']} not found.")
        return ToolResult(status="ok", output={
            "case_number": params["case_number"],
            "action": action,
            "new_status": new_status,
            "message": f"Case {params['case_number']} has been {new_status}.",
        })
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose up db -d && PYTHONPATH=src pytest tests/tools/test_db_tools.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/tools/user_context.py src/tools/create_case.py src/tools/get_case.py src/tools/get_recent_cases.py src/tools/perform_case_action.py src/db/seed.py tests/tools/test_db_tools.py tests/conftest.py
git commit -m "feat: database-backed tools (user_context, create_case, get_case, get_recent_cases, perform_case_action) with seed data"
```

---

### Task 8: Knowledge search tool (pgvector)

**Files:**
- Create: `src/tools/knowledge.py`
- Create: `tests/tools/test_knowledge.py`

This tool requires the Braintrust gateway for embeddings. Tests use a real DB with test article data.

- [ ] **Step 1: Write tests**

```python
# tests/tools/test_knowledge.py
import pytest
from unittest.mock import AsyncMock, patch
import numpy as np
from tools.knowledge import SearchKnowledgeTool


@pytest.fixture
async def knowledge_tool(db_pool):
    """Insert test articles + chunks with embeddings."""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM article_chunks")
        await conn.execute("DELETE FROM articles")
        art_id = await conn.fetchval(
            "INSERT INTO articles (url, title, content, product_category) VALUES ($1, $2, $3, $4) RETURNING id",
            "https://help.salesforce.com/test-article", "How to reset password",
            "To reset your Salesforce password, go to Settings > Password Reset.", "platform",
        )
        # Insert a chunk with a known embedding
        embedding = [0.1] * 1536
        await conn.execute(
            "INSERT INTO article_chunks (article_id, chunk_index, chunk_text, embedding) VALUES ($1, $2, $3, $4)",
            art_id, 0, "To reset your Salesforce password, go to Settings > Password Reset.", str(embedding),
        )
    return SearchKnowledgeTool(pool=db_pool, gateway_base_url="https://gateway.braintrust.dev", api_key="test")


@pytest.mark.asyncio
async def test_search_knowledge_returns_results(knowledge_tool):
    # Mock the embedding call to return a similar vector
    mock_embedding = np.array([0.1] * 1536, dtype=np.float32)
    with patch.object(knowledge_tool, "_embed_query", new_callable=AsyncMock, return_value=mock_embedding):
        result = await knowledge_tool.execute({"query": "how to reset password"}, session=None)
    assert result.status == "ok"
    assert len(result.output["results"]) >= 1
    assert "password" in result.output["results"][0]["chunk_text"].lower()


@pytest.mark.asyncio
async def test_search_knowledge_no_results(knowledge_tool):
    # Mock embedding that won't match anything (orthogonal vector)
    mock_embedding = np.array([0.0] * 1535 + [1.0], dtype=np.float32)
    with patch.object(knowledge_tool, "_embed_query", new_callable=AsyncMock, return_value=mock_embedding):
        result = await knowledge_tool.execute({"query": "quantum physics"}, session=None)
    assert result.status == "ok"
    # May return results but with low scores, or empty
    assert "results" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose up db -d && PYTHONPATH=src pytest tests/tools/test_knowledge.py -v`
Expected: FAIL

- [ ] **Step 3: Implement knowledge.py**

```python
# src/tools/knowledge.py
from __future__ import annotations
import asyncpg
import numpy as np
from openai import AsyncOpenAI
from tools.base import Tool, ToolResult


class SearchKnowledgeTool(Tool):
    name = "search_knowledge"
    description = "Searches the Salesforce knowledge base for articles relevant to the user's question."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["query"],
    }

    def __init__(self, pool: asyncpg.Pool, gateway_base_url: str, api_key: str, model: str = "text-embedding-3-small"):
        self._pool = pool
        self._client = AsyncOpenAI(base_url=gateway_base_url, api_key=api_key)
        self._model = model

    async def _embed_query(self, query: str) -> np.ndarray:
        response = await self._client.embeddings.create(model=self._model, input=query)
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def execute(self, params, session):
        query = params.get("query", "")
        embedding = await self._embed_query(query)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ac.chunk_text, a.url, a.title, a.product_category,
                       1 - (ac.embedding <=> $1) AS score
                FROM article_chunks ac
                JOIN articles a ON a.id = ac.article_id
                ORDER BY ac.embedding <=> $1
                LIMIT 5
                """,
                embedding,
            )
        results = [
            {
                "chunk_text": r["chunk_text"],
                "url": r["url"],
                "title": r["title"],
                "product_category": r["product_category"],
                "score": float(r["score"]),
            }
            for r in rows
        ]
        return ToolResult(status="ok", output={"results": results, "query": query})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose up db -d && PYTHONPATH=src pytest tests/tools/test_knowledge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/knowledge.py tests/tools/test_knowledge.py
git commit -m "feat: knowledge search tool with pgvector similarity search and embedding via gateway"
```

---

## Phase 4: Orchestration

### Task 9: Topic classifier

**Files:**
- Create: `src/agent/classifier.py`
- Create: `tests/agent/test_classifier.py`

- [ ] **Step 1: Write tests**

```python
# tests/agent/test_classifier.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.classifier import TopicClassifier
from agent.config import Settings
from agent.models import ClassifierResult, Message
from topics.registry import get_default_registry


@pytest.fixture
def classifier():
    settings = Settings(braintrust_api_key="test-key")
    return TopicClassifier(settings=settings, topic_registry=get_default_registry())


@pytest.mark.asyncio
async def test_classify_knowledge_query(classifier):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "knowledge_faq", "confidence": 0.95})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("How do I reset my Salesforce password?", [])
    assert result.topic_id == "knowledge_faq"
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_classify_case_creation(classifier):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "case_creation", "confidence": 0.92})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("I want to create a case", [])
    assert result.topic_id == "case_creation"


@pytest.mark.asyncio
async def test_classify_low_confidence_defaults_to_off_topic(classifier):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "knowledge_faq", "confidence": 0.1})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await classifier.classify("asdfghjkl", [])
    assert result.topic_id == "off_topic"


@pytest.mark.asyncio
async def test_classify_includes_history(classifier):
    history = [Message(role="user", content="I have an issue"), Message(role="assistant", content="How can I help?")]
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"topic_id": "case_creation", "confidence": 0.8})

    with patch.object(classifier._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response) as mock_create:
        await classifier.classify("create a case", history)
    # Verify history was included in the prompt
    call_args = mock_create.call_args
    messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
    user_msg = [m for m in messages if m["role"] == "user"][0]
    assert "I have an issue" in user_msg["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/agent/test_classifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement classifier.py**

```python
# src/agent/classifier.py
from __future__ import annotations
import json
from openai import AsyncOpenAI
from agent.config import Settings
from agent.models import ClassifierResult, Message
from topics.registry import TopicRegistry


class TopicClassifier:
    def __init__(self, settings: Settings, topic_registry: TopicRegistry):
        self._settings = settings
        self._topic_registry = topic_registry
        self._client = AsyncOpenAI(
            base_url=settings.gateway_base_url,
            api_key=settings.braintrust_api_key,
        )

    async def classify(
        self,
        user_message: str,
        history: list[Message],
        extra_headers: dict | None = None,
    ) -> ClassifierResult:
        system_prompt = self._topic_registry.classification_prompt()

        # Include recent history for context
        history_text = ""
        if history:
            recent = history[-6:]  # last 3 turns (user+assistant pairs)
            lines = [f"{m.role}: {m.content}" for m in recent if m.role in ("user", "assistant")]
            history_text = "\n\nRecent conversation:\n" + "\n".join(lines) + "\n"

        user_content = f"{history_text}\nCurrent user message: {user_message}"

        response = await self._client.chat.completions.create(
            model=self._settings.classifier_model,
            temperature=self._settings.classifier_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            **({"extra_headers": extra_headers} if extra_headers else {}),
        )

        content = response.choices[0].message.content
        try:
            data = json.loads(content)
            result = ClassifierResult(
                topic_id=data.get("topic_id", "off_topic"),
                confidence=float(data.get("confidence", 0.0)),
            )
        except (json.JSONDecodeError, ValueError):
            result = ClassifierResult(topic_id="off_topic", confidence=0.0)

        # Apply confidence threshold
        if result.confidence < self._settings.confidence_threshold:
            result = ClassifierResult(topic_id="off_topic", confidence=result.confidence)

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/agent/test_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent/classifier.py tests/agent/test_classifier.py
git commit -m "feat: topic classifier with LLM-driven classification via Braintrust gateway"
```

---

### Task 10: Topic executor

**Files:**
- Create: `src/agent/executor.py`
- Create: `tests/agent/test_executor.py`

- [ ] **Step 1: Write tests**

```python
# tests/agent/test_executor.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agent.executor import TopicExecutor, ExecutorResult
from agent.config import Settings
from agent.models import SessionState, Message
from topics.knowledge import KNOWLEDGE_FAQ
from topics.off_topic import OFF_TOPIC
from tools.base import ToolResult
from tools.registry import ToolRegistry


@pytest.fixture
def executor():
    settings = Settings(braintrust_api_key="test-key")
    registry = ToolRegistry()
    return TopicExecutor(settings=settings, tool_registry=registry)


@pytest.mark.asyncio
async def test_execute_no_tool_calls(executor):
    """Executor returns text response when LLM doesn't call tools."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I can help you with Salesforce questions."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"

    session = SessionState(session_id="test")

    with patch.object(executor._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await executor.execute(
            topic=OFF_TOPIC,
            user_message="What's the weather?",
            session=session,
        )
    assert isinstance(result, ExecutorResult)
    assert "Salesforce" in result.response


@pytest.mark.asyncio
async def test_execute_with_tool_call(executor):
    """Executor handles tool calls in a ReAct loop."""
    # First response: LLM calls a tool
    tool_call_response = MagicMock()
    tool_call_response.choices = [MagicMock()]
    tool_call_response.choices[0].message.content = None
    tool_call_response.choices[0].message.tool_calls = [MagicMock()]
    tool_call_response.choices[0].message.tool_calls[0].id = "call_123"
    tool_call_response.choices[0].message.tool_calls[0].function.name = "search_knowledge"
    tool_call_response.choices[0].message.tool_calls[0].function.arguments = json.dumps({"query": "password reset"})
    tool_call_response.choices[0].finish_reason = "tool_calls"

    # Second response: LLM produces final answer
    final_response = MagicMock()
    final_response.choices = [MagicMock()]
    final_response.choices[0].message.content = "To reset your password, go to Settings."
    final_response.choices[0].message.tool_calls = None
    final_response.choices[0].finish_reason = "stop"

    # Mock tool execution
    executor._tool_registry.execute = AsyncMock(
        return_value=ToolResult(status="ok", output={"results": [{"chunk_text": "password reset steps"}]})
    )

    session = SessionState(session_id="test")

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_call_response, final_response],
    ):
        result = await executor.execute(
            topic=KNOWLEDGE_FAQ,
            user_message="How do I reset my password?",
            session=session,
        )
    assert isinstance(result, ExecutorResult)
    assert "password" in result.response.lower() or "Settings" in result.response
    assert len(result.tool_messages) > 0  # tool calls were recorded


@pytest.mark.asyncio
async def test_execute_rejects_out_of_scope_tool(executor):
    """If LLM calls a tool not in the topic's scope, it gets an error."""
    tool_call_response = MagicMock()
    tool_call_response.choices = [MagicMock()]
    tool_call_response.choices[0].message.content = None
    tool_call_response.choices[0].message.tool_calls = [MagicMock()]
    tool_call_response.choices[0].message.tool_calls[0].id = "call_456"
    tool_call_response.choices[0].message.tool_calls[0].function.name = "create_case"
    tool_call_response.choices[0].message.tool_calls[0].function.arguments = "{}"
    tool_call_response.choices[0].finish_reason = "tool_calls"

    final_response = MagicMock()
    final_response.choices = [MagicMock()]
    final_response.choices[0].message.content = "I can only search knowledge in this context."
    final_response.choices[0].message.tool_calls = None
    final_response.choices[0].finish_reason = "stop"

    session = SessionState(session_id="test")

    with patch.object(
        executor._client.chat.completions, "create",
        new_callable=AsyncMock,
        side_effect=[tool_call_response, final_response],
    ):
        result = await executor.execute(
            topic=KNOWLEDGE_FAQ,  # only has search_knowledge
            user_message="create a case",
            session=session,
        )
    assert isinstance(result, ExecutorResult)
    assert result.response is not None  # Should recover gracefully
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/agent/test_executor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement executor.py**

```python
# src/agent/executor.py
from __future__ import annotations
import json
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from agent.config import Settings
from agent.models import SessionState, Message
from tools.registry import ToolRegistry
from topics.base import Topic


MAX_TOOL_ROUNDS = 5


@dataclass
class ExecutorResult:
    response: str
    tool_messages: list[Message] = field(default_factory=list)


class TopicExecutor:
    def __init__(self, settings: Settings, tool_registry: ToolRegistry):
        self._settings = settings
        self._tool_registry = tool_registry
        self._client = AsyncOpenAI(
            base_url=settings.gateway_base_url,
            api_key=settings.braintrust_api_key,
        )

    def _build_messages(
        self, topic: Topic, user_message: str, session: SessionState
    ) -> list[dict]:
        system = (
            f"You are a Salesforce help agent operating in the '{topic.name}' topic.\n\n"
            f"{topic.instructions}\n\n"
            "Respond in the same language the user writes in. Be concise and helpful."
        )

        messages: list[dict] = [{"role": "system", "content": system}]

        # Add conversation history (already truncated by orchestrator)
        for msg in session.conversation_history:
            m = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            messages.append(m)

        messages.append({"role": "user", "content": user_message})
        return messages

    async def execute(
        self,
        topic: Topic,
        user_message: str,
        session: SessionState,
        extra_headers: dict | None = None,
        trace_span: object | None = None,
    ) -> ExecutorResult:
        messages = self._build_messages(topic, user_message, session)
        tools = self._tool_registry.get_openai_tool_schemas(topic.tools) or None
        tool_messages: list[Message] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self._client.chat.completions.create(
                model=self._settings.executor_model,
                temperature=self._settings.executor_temperature,
                max_tokens=self._settings.executor_max_tokens,
                messages=messages,
                tools=tools if tools else None,
                **({"extra_headers": extra_headers} if extra_headers else {}),
            )

            choice = response.choices[0]

            if choice.finish_reason == "stop" or not choice.message.tool_calls:
                return ExecutorResult(response=choice.message.content or "", tool_messages=tool_messages)

            # Process tool calls
            assistant_tc_msg = {
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.message.tool_calls
                ],
            }
            messages.append(assistant_tc_msg)
            tool_messages.append(Message(
                role="assistant",
                content=choice.message.content or "",
                tool_calls=assistant_tc_msg["tool_calls"],
            ))

            for tc in choice.message.tool_calls:
                tool_name = tc.function.name

                # Reject out-of-scope tools
                if tool_name not in topic.tools:
                    error_content = json.dumps({
                        "error": f"Tool '{tool_name}' is not available in the current topic ({topic.id}). Available tools: {topic.tools}"
                    })
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": error_content})
                    tool_messages.append(Message(role="tool", content=error_content, tool_call_id=tc.id, name=tool_name))
                    continue

                try:
                    params = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    params = {}

                # Trace tool call
                tool_span = None
                if trace_span:
                    tool_span = trace_span.start_span(name=f"tool_call.{tool_name}")

                result = await self._tool_registry.execute(tool_name, params, session)

                if tool_span:
                    tool_span.log(input=params, output=result.output, metrics={"latency_ms": result.latency_ms})
                    tool_span.end()

                result_content = json.dumps(result.output) if isinstance(result.output, dict) else str(result.output)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_content})
                tool_messages.append(Message(role="tool", content=result_content, tool_call_id=tc.id, name=tool_name))

        return ExecutorResult(
            response="I'm having trouble completing this request. Please try again.",
            tool_messages=tool_messages,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/agent/test_executor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent/executor.py tests/agent/test_executor.py
git commit -m "feat: topic executor with ReAct tool-calling loop and out-of-scope tool rejection"
```

---

### Task 11: Orchestrator (ties classifier + executor + session together)

**Files:**
- Create: `src/agent/history.py`
- Create: `src/agent/orchestrator.py`
- Create: `tests/agent/test_history.py`
- Create: `tests/agent/test_orchestrator.py`

- [ ] **Step 0a: Write test for history truncation**

```python
# tests/agent/test_history.py
from agent.models import Message
from agent.history import truncate_history


def test_short_history_unchanged():
    msgs = [Message(role="user", content="hi"), Message(role="assistant", content="hello")]
    result = truncate_history(msgs, max_tokens=8000, min_turns=4)
    assert len(result) == 2


def test_long_history_truncated():
    msgs = []
    for i in range(50):
        msgs.append(Message(role="user", content=f"Message number {i} " * 100))
        msgs.append(Message(role="assistant", content=f"Response number {i} " * 100))
    result = truncate_history(msgs, max_tokens=2000, min_turns=4)
    assert len(result) < len(msgs)
    # Most recent 4 turns (8 messages) should always be preserved
    assert len(result) >= 8


def test_preserves_most_recent_turns():
    msgs = []
    for i in range(20):
        msgs.append(Message(role="user", content=f"msg-{i}"))
        msgs.append(Message(role="assistant", content=f"resp-{i}"))
    result = truncate_history(msgs, max_tokens=500, min_turns=4)
    # Last message should always be the most recent
    assert result[-1].content == "resp-19"
    assert result[-2].content == "msg-19"
```

- [ ] **Step 0b: Implement history.py**

```python
# src/agent/history.py
from __future__ import annotations
import tiktoken
from agent.models import Message


def truncate_history(
    messages: list[Message],
    max_tokens: int = 8000,
    min_turns: int = 4,
) -> list[Message]:
    """Truncate conversation history to fit within token budget.

    Always preserves the most recent `min_turns` turns (2 messages each).
    Removes oldest messages first.
    """
    if not messages:
        return messages

    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    # Minimum messages to keep (min_turns * 2 for user+assistant pairs)
    min_messages = min_turns * 2

    def count_tokens(msgs: list[Message]) -> int:
        return sum(len(enc.encode(m.content)) for m in msgs)

    # If already within budget, return as-is
    if count_tokens(messages) <= max_tokens:
        return list(messages)

    # Always keep the most recent min_messages
    if len(messages) <= min_messages:
        return list(messages)

    protected = messages[-min_messages:]
    candidates = messages[:-min_messages]

    # Remove from the front until within budget
    remaining_budget = max_tokens - count_tokens(protected)
    kept = []
    for msg in reversed(candidates):
        msg_tokens = len(enc.encode(msg.content))
        if remaining_budget >= msg_tokens:
            kept.append(msg)
            remaining_budget -= msg_tokens
        else:
            break

    return list(reversed(kept)) + protected
```

- [ ] **Step 0c: Run history tests**

Run: `PYTHONPATH=src pytest tests/agent/test_history.py -v`
Expected: PASS

- [ ] **Step 1: Write tests**

```python
# tests/agent/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
    """First turn should call get_datetime and set session_timestamp."""
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
    """Orchestrator should update current_topic when classifier returns different topic."""
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

    assert len(session.conversation_history) == 2  # user + assistant
    assert session.conversation_history[0].role == "user"
    assert session.conversation_history[1].role == "assistant"


@pytest.mark.asyncio
async def test_tool_messages_persisted_in_history(orchestrator):
    """Tool call messages from executor should be in conversation history."""
    session = SessionState(session_id="test")
    orchestrator._classifier.classify = AsyncMock(
        return_value=ClassifierResult(topic_id="knowledge_faq", confidence=0.9)
    )
    tool_msg = Message(role="tool", content='{"results": []}', tool_call_id="call_1", name="search_knowledge")
    orchestrator._executor.execute = AsyncMock(
        return_value=ExecutorResult(response="No results found.", tool_messages=[tool_msg])
    )

    await orchestrator.handle_message("search for something", session)

    # History should be: user, tool_msg, assistant
    assert len(session.conversation_history) == 3
    assert session.conversation_history[1].role == "tool"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/agent/test_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement orchestrator.py**

```python
# src/agent/orchestrator.py
from __future__ import annotations
from datetime import datetime, timezone

import asyncpg

from agent.classifier import TopicClassifier
from agent.config import Settings
from agent.executor import TopicExecutor, ExecutorResult
from agent.history import truncate_history
from agent.models import Message, SessionState
from tools.datetime_tool import GetDateTimeTool
from tools.emit_event import EmitEventTool
from tools.knowledge import SearchKnowledgeTool
from tools.user_context import GetUserContextTool
from tools.create_case import CreateCaseTool
from tools.get_case import GetCaseTool
from tools.get_recent_cases import GetRecentCasesTool
from tools.perform_case_action import PerformCaseActionTool
from tools.validate_transfer import ValidateAndTransferTool
from tools.raise_flag import RaiseFlagTool
from tools.get_personalization import GetPersonalizationTool
from tools.registry import ToolRegistry
from topics.registry import get_default_registry
from tracing.braintrust import TracingManager


class Orchestrator:
    def __init__(self, settings: Settings, db_pool: asyncpg.Pool | None):
        self._settings = settings
        self._topic_registry = get_default_registry()
        self._tool_registry = self._build_tool_registry(settings, db_pool)
        self._classifier = TopicClassifier(settings=settings, topic_registry=self._topic_registry)
        self._executor = TopicExecutor(settings=settings, tool_registry=self._tool_registry)
        self._tracing = TracingManager(
            project="sfdc-help-agent", api_key=settings.braintrust_api_key
        )
        self._session_spans: dict[str, object] = {}

    def _build_tool_registry(self, settings: Settings, pool: asyncpg.Pool | None) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(GetDateTimeTool())
        registry.register(EmitEventTool())
        registry.register(ValidateAndTransferTool())
        registry.register(RaiseFlagTool())
        registry.register(GetPersonalizationTool())
        if pool is not None:
            registry.register(GetUserContextTool(pool))
            registry.register(CreateCaseTool(pool))
            registry.register(GetCaseTool(pool))
            registry.register(GetRecentCasesTool(pool))
            registry.register(PerformCaseActionTool(pool))
            registry.register(SearchKnowledgeTool(
                pool=pool,
                gateway_base_url=settings.gateway_base_url,
                api_key=settings.braintrust_api_key,
                model=settings.embedding_model,
            ))
        return registry

    def _get_session_span(self, session: SessionState):
        if session.session_id not in self._session_spans:
            self._session_spans[session.session_id] = self._tracing.start_session(
                session.session_id
            )
        return self._session_spans[session.session_id]

    async def handle_message(self, user_message: str, session: SessionState) -> str:
        session_span = self._get_session_span(session)
        turn_span = session_span.start_span(name=f"turn.{session.turn_count}")

        # Bootstrap: set timestamp on first turn
        if session.turn_count == 0:
            dt_tool = self._tool_registry.get("get_datetime")
            if dt_tool:
                result = await dt_tool.execute({}, session)
                session.session_timestamp = datetime.fromisoformat(result.output)

        # Truncate history before passing to LLM
        truncated_history = truncate_history(
            session.conversation_history,
            max_tokens=self._settings.history_token_limit,
            min_turns=self._settings.history_min_turns,
        )

        # Phase 1: Classify
        classify_span = turn_span.start_span(name="classify")
        classify_headers = {"x-bt-parent": classify_span.export()} if classify_span.export() else None
        classify_result = await self._classifier.classify(
            user_message, truncated_history, extra_headers=classify_headers,
        )
        classify_span.log(output={"topic_id": classify_result.topic_id, "confidence": classify_result.confidence})
        classify_span.end()

        topic_id = classify_result.topic_id
        topic = self._topic_registry.get(topic_id)
        if topic is None:
            topic = self._topic_registry.get("off_topic")
            topic_id = "off_topic"

        topic_changed = session.current_topic != topic_id
        session.current_topic = topic_id

        # Phase 2: Execute
        execute_span = turn_span.start_span(name="execute")
        execute_headers = {"x-bt-parent": execute_span.export()} if execute_span.export() else None
        exec_result = await self._executor.execute(
            topic=topic,
            user_message=user_message,
            session=session,
            extra_headers=execute_headers,
            trace_span=execute_span,
        )
        execute_span.log(output={"response": exec_result.response[:200], "tool_calls_count": len(exec_result.tool_messages)})
        execute_span.end()

        # Update session with user message, tool call messages, and assistant response
        session.conversation_history.append(Message(role="user", content=user_message))
        for msg in exec_result.tool_messages:
            session.conversation_history.append(msg)
        session.conversation_history.append(Message(role="assistant", content=exec_result.response))
        session.turn_count += 1

        turn_span.log(
            input=user_message,
            output=exec_result.response,
            metadata={"topic": topic_id, "topic_changed": topic_changed},
        )
        turn_span.end()

        return exec_result.response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/agent/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat: orchestrator with two-phase classify-then-execute loop and bootstrap turn"
```

---

## Phase 5: Tracing & Frontend

### Task 12: Braintrust tracing integration

**Files:**
- Create: `src/tracing/braintrust.py`
- Create: `tests/tracing/test_braintrust.py`

- [ ] **Step 1: Write tests**

```python
# tests/tracing/test_braintrust.py
import pytest
from unittest.mock import MagicMock, patch
from tracing.braintrust import TracingManager


def test_tracing_manager_creates_session_span():
    with patch("tracing.braintrust.init_logger") as mock_init:
        mock_logger = MagicMock()
        mock_init.return_value = mock_logger
        mock_span = MagicMock()
        mock_logger.start_span.return_value = mock_span

        manager = TracingManager(project="test-project", api_key="test")
        session_span = manager.start_session("session-123")

        mock_logger.start_span.assert_called_once()
        assert session_span is not None


def test_tracing_manager_noop_without_api_key():
    manager = TracingManager(project="test", api_key="")
    session_span = manager.start_session("session-123")
    # Should return a no-op span that doesn't crash
    turn_span = session_span.start_span(name="turn.0")
    turn_span.log(output={"test": True})
    turn_span.end()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/tracing/test_braintrust.py -v`
Expected: FAIL

- [ ] **Step 3: Implement tracing/braintrust.py**

```python
# src/tracing/braintrust.py
from __future__ import annotations
from typing import Any


class NoopSpan:
    """No-op span for when tracing is disabled."""
    def start_span(self, **kwargs) -> NoopSpan:
        return NoopSpan()

    def log(self, **kwargs) -> None:
        pass

    def end(self) -> None:
        pass

    def export(self) -> str:
        return ""


class TracingManager:
    def __init__(self, project: str, api_key: str):
        self._project = project
        self._api_key = api_key
        self._logger = None

        if api_key:
            try:
                from braintrust import init_logger
                self._logger = init_logger(project=project, api_key=api_key)
            except Exception:
                pass

    def start_session(self, session_id: str) -> Any:
        if self._logger is None:
            return NoopSpan()
        return self._logger.start_span(name="session", session_id=session_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/tracing/test_braintrust.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tracing/braintrust.py tests/tracing/test_braintrust.py
git commit -m "feat: Braintrust tracing manager with no-op fallback when API key not configured"
```

---

### Task 13: Chainlit app

**Files:**
- Create: `src/app.py`
- Create: `src/agent/session.py`

This is the entry point that wires everything together. Not easily unit-testable (relies on Chainlit runtime), so we validate manually.

- [ ] **Step 1: Implement session.py (session persistence)**

```python
# src/agent/session.py
from __future__ import annotations
import json
import asyncpg
from agent.models import SessionState


async def save_session(pool: asyncpg.Pool, session: SessionState) -> None:
    state_json = session.model_dump_json()
    await pool.execute(
        """
        INSERT INTO sessions (id, state_json, updated_at)
        VALUES ($1, $2::jsonb, now())
        ON CONFLICT (id) DO UPDATE SET state_json = $2::jsonb, updated_at = now()
        """,
        session.session_id, state_json,
    )


async def load_session(pool: asyncpg.Pool, session_id: str) -> SessionState | None:
    row = await pool.fetchrow("SELECT state_json FROM sessions WHERE id = $1", session_id)
    if row is None:
        return None
    return SessionState.model_validate(row["state_json"])
```

- [ ] **Step 2: Implement app.py (Chainlit entry point)**

```python
# src/app.py
from __future__ import annotations
import os
import chainlit as cl
from dotenv import load_dotenv

load_dotenv()

from agent.config import Settings
from agent.models import SessionState, AuthState
from agent.orchestrator import Orchestrator
from db.connection import get_pool, close_pool

settings = Settings()
_orchestrator: Orchestrator | None = None


async def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        pool = await get_pool(settings)
        _orchestrator = Orchestrator(settings=settings, db_pool=pool)
    return _orchestrator


@cl.on_chat_start
async def on_start():
    session_id = cl.user_session.get("id")
    session = SessionState(session_id=session_id)
    cl.user_session.set("session_state", session)

    # Simulate authenticated user for demo
    session.auth_state = AuthState(
        tenant_name="COMPANY_demo_001",
        org_id="SFID_demo_001",
        product="core",
        success_plan="Premier",
    )

    await cl.Message(content="Welcome to Salesforce Help. How can I assist you today?").send()


@cl.on_message
async def on_message(message: cl.Message):
    session = cl.user_session.get("session_state")
    orchestrator = await get_orchestrator()

    response = await orchestrator.handle_message(message.content, session)
    await cl.Message(content=response).send()


@cl.on_chat_end
async def on_end():
    pass


@cl.on_stop
async def on_stop():
    await close_pool()
```

- [ ] **Step 3: Start services and test manually**

```bash
# Terminal 1: start database
docker compose up db -d

# Terminal 2: seed database
PYTHONPATH=src python -c "
import asyncio, asyncpg
from db.seed import seed_users
async def main():
    pool = await asyncpg.create_pool('postgresql://sfdc:sfdc@localhost:5432/sfdc')
    await seed_users(pool)
    await pool.close()
    print('Seeded.')
asyncio.run(main())
"

# Terminal 3: start Chainlit
PYTHONPATH=src chainlit run src/app.py --port 8000
```

Open http://localhost:8000 and test:
1. Ask "How do I reset my Salesforce password?" - should classify as knowledge_faq
2. Say "create a case" - should classify as case_creation and start intake flow
3. Say "transfer to agent" - should classify as agent_transfer
4. Say "What's the weather?" - should classify as off_topic

- [ ] **Step 4: Commit**

```bash
git add src/app.py src/agent/session.py
git commit -m "feat: Chainlit app entry point with orchestrator wiring and session management"
```

---

## Phase 6: Scraper Pipeline

### Task 14: Scraper - crawler and parser

**Files:**
- Create: `scraper/__init__.py`
- Create: `scraper/cli.py`
- Create: `scraper/crawler.py`
- Create: `scraper/parser.py`
- Create: `tests/scraper/test_parser.py`

- [ ] **Step 1: Write tests for parser**

```python
# tests/scraper/test_parser.py
from scraper.parser import parse_article_page


def test_parse_article_extracts_title():
    html = """
    <h1 class="article-title">Set Up Einstein Activity Capture</h1>
    <div class="article-content"><p>Steps to set up EAC.</p></div>
    <div class="see-also"><a href="/s/articleView?id=001">Related Article</a></div>
    """
    result = parse_article_page(html, "https://help.salesforce.com/s/articleView?id=123")
    assert result["title"] == "Set Up Einstein Activity Capture"
    assert "Steps to set up EAC" in result["content"]


def test_parse_article_extracts_see_also():
    html = """
    <h1>Test Article</h1>
    <div class="article-content"><p>Content here.</p></div>
    <section class="see-also">
        <a href="https://help.salesforce.com/s/articleView?id=001">Link 1</a>
        <a href="https://help.salesforce.com/s/articleView?id=002">Link 2</a>
    </section>
    """
    result = parse_article_page(html, "https://help.salesforce.com/test")
    assert len(result["related_urls"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src:. pytest tests/scraper/test_parser.py -v`
Expected: FAIL

- [ ] **Step 3: Implement parser.py**

```python
# scraper/parser.py
from __future__ import annotations
import re
from html.parser import HTMLParser


def parse_article_page(html: str, url: str) -> dict:
    """Extract title, content, and see-also links from a Salesforce help article page.

    This is a best-effort parser. The actual Salesforce help pages are JS-rendered,
    so Playwright must render the page first and pass the resulting HTML here.
    Selectors may need adjustment based on actual page structure.
    """
    title = ""
    content = ""
    related_urls = []

    # Title extraction - try multiple patterns
    title_patterns = [
        r'<h1[^>]*class="[^"]*article-title[^"]*"[^>]*>(.*?)</h1>',
        r'<h1[^>]*>(.*?)</h1>',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            break

    # Content extraction
    content_patterns = [
        r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*slds-rich-text-editor__output[^"]*"[^>]*>(.*?)</div>',
        r'<article[^>]*>(.*?)</article>',
    ]
    for pattern in content_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            raw = match.group(1)
            content = re.sub(r'<[^>]+>', ' ', raw)
            content = re.sub(r'\s+', ' ', content).strip()
            break

    if not content:
        # Fallback: strip all tags from body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
        if body_match:
            content = re.sub(r'<[^>]+>', ' ', body_match.group(1))
            content = re.sub(r'\s+', ' ', content).strip()

    # See Also links
    see_also_match = re.search(r'(?:see.also|SEE\s+ALSO)(.*?)(?:</section>|</div>|$)', html, re.DOTALL | re.IGNORECASE)
    if see_also_match:
        links = re.findall(r'href="([^"]*(?:articleView|help\.salesforce\.com)[^"]*)"', see_also_match.group(1))
        related_urls = links

    return {
        "url": url,
        "title": title,
        "content": content,
        "related_urls": related_urls,
    }
```

- [ ] **Step 4: Implement crawler.py**

```python
# scraper/crawler.py
from __future__ import annotations
import asyncio
import logging
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

BASE_URL = "https://help.salesforce.com"
CRAWL_DELAY = 2.0  # seconds between page loads


async def discover_sub_categories(page: Page, category: str) -> list[dict]:
    """Navigate to a product category page and discover sub-category links."""
    url = f"{BASE_URL}/s/products/{category}"
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(CRAWL_DELAY)

    # Extract sub-category links - selectors may need adjustment
    links = await page.eval_on_selector_all(
        "a[href*='/s/products/']",
        "els => els.map(el => ({name: el.textContent.trim(), href: el.href}))"
    )
    return [l for l in links if l["href"] != url and l["name"]]


async def discover_doc_pages(page: Page, sub_category_url: str) -> list[str]:
    """Navigate to a sub-category page and discover doc page links."""
    await page.goto(sub_category_url, wait_until="networkidle")
    await asyncio.sleep(CRAWL_DELAY)

    links = await page.eval_on_selector_all(
        "a[href*='articleView']",
        "els => els.map(el => el.href)"
    )
    return list(set(links))


async def fetch_article_html(page: Page, url: str) -> str:
    """Navigate to an article page and return the rendered HTML."""
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(CRAWL_DELAY)
    return await page.content()
```

- [ ] **Step 5: Implement cli.py**

```python
# scraper/cli.py
from __future__ import annotations
import asyncio
import json
import logging
import click
from playwright.async_api import async_playwright

from scraper.crawler import discover_sub_categories, discover_doc_pages, fetch_article_html
from scraper.parser import parse_article_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Salesforce Help article scraper."""
    pass


@cli.command()
@click.option("--category", required=True, help="Product category to scrape (e.g., 'platform', 'sales')")
@click.option("--output", default="scraped_articles.jsonl", help="Output JSONL file path")
@click.option("--limit", default=0, type=int, help="Max articles to scrape (0 = unlimited)")
def scrape(category: str, output: str, limit: int):
    """Scrape articles from a Salesforce Help product category."""
    asyncio.run(_scrape(category, output, limit))


async def _scrape(category: str, output: str, limit: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        logger.info(f"Discovering sub-categories for: {category}")
        sub_cats = await discover_sub_categories(page, category)
        logger.info(f"Found {len(sub_cats)} sub-categories")

        articles = []
        for sc in sub_cats:
            logger.info(f"Discovering docs for: {sc['name']}")
            doc_urls = await discover_doc_pages(page, sc["href"])
            logger.info(f"  Found {len(doc_urls)} articles")

            for url in doc_urls:
                if limit and len(articles) >= limit:
                    break
                logger.info(f"  Fetching: {url}")
                html = await fetch_article_html(page, url)
                article = parse_article_page(html, url)
                article["product_category"] = category
                article["product_sub_category"] = sc["name"]
                articles.append(article)

        await browser.close()

    with open(output, "w") as f:
        for article in articles:
            f.write(json.dumps(article) + "\n")
    logger.info(f"Wrote {len(articles)} articles to {output}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 6: Run parser tests to verify they pass**

Run: `PYTHONPATH=src:. pytest tests/scraper/test_parser.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/ tests/scraper/
git commit -m "feat: scraper pipeline with Playwright crawler, HTML parser, and CLI"
```

---

### Task 15: Scraper - chunker, embedder, question generator, and DB loader

**Files:**
- Create: `scraper/chunker.py`
- Create: `scraper/embedder.py`
- Create: `scraper/question_gen.py`
- Create: `scraper/loader.py`
- Create: `tests/scraper/test_chunker.py`

- [ ] **Step 1: Write tests for chunker**

```python
# tests/scraper/test_chunker.py
from scraper.chunker import chunk_text


def test_short_text_single_chunk():
    chunks = chunk_text("Hello world", max_tokens=500)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_long_text_multiple_chunks():
    text = " ".join(["word"] * 2000)
    chunks = chunk_text(text, max_tokens=500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 600  # rough token estimate


def test_chunk_preserves_sentence_boundaries():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    chunks = chunk_text(text, max_tokens=10)
    # Each chunk should end at a sentence boundary when possible
    for chunk in chunks:
        assert chunk.strip().endswith(".")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src:. pytest tests/scraper/test_chunker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement chunker.py**

```python
# scraper/chunker.py
from __future__ import annotations
import re


def chunk_text(text: str, max_tokens: int = 500) -> list[str]:
    """Split text into chunks of approximately max_tokens tokens.

    Uses sentence boundaries when possible. Rough estimate: 1 token ~= 0.75 words.
    """
    if not text.strip():
        return []

    max_words = int(max_tokens * 0.75)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    chunks = []
    current_chunk: list[str] = []
    current_words = 0

    for sentence in sentences:
        word_count = len(sentence.split())
        if current_words + word_count > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_words = 0
        current_chunk.append(sentence)
        current_words += word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
```

- [ ] **Step 4: Run chunker tests to verify they pass**

Run: `PYTHONPATH=src:. pytest tests/scraper/test_chunker.py -v`
Expected: PASS

- [ ] **Step 5: Implement embedder.py**

```python
# scraper/embedder.py
from __future__ import annotations
from openai import OpenAI


class Embedder:
    def __init__(self, gateway_base_url: str, api_key: str, model: str = "text-embedding-3-small"):
        self._client = OpenAI(base_url=gateway_base_url, api_key=api_key)
        self._model = model

    def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """Embed a list of texts in batches."""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self._client.embeddings.create(model=self._model, input=batch)
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings
```

- [ ] **Step 6: Implement question_gen.py**

```python
# scraper/question_gen.py
from __future__ import annotations
from openai import OpenAI


class QuestionGenerator:
    def __init__(self, gateway_base_url: str, api_key: str, model: str = "claude-haiku-4-5"):
        self._client = OpenAI(base_url=gateway_base_url, api_key=api_key)
        self._model = model

    def generate(self, title: str, content: str, n: int = 5) -> list[str]:
        """Generate realistic customer questions for an article."""
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate realistic customer support questions. "
                        "Given a Salesforce help article, produce questions a customer "
                        "might ask that this article would answer. "
                        "Return one question per line, no numbering or bullets."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Title: {title}\n\nContent: {content[:2000]}\n\nGenerate {n} questions:",
                },
            ],
        )
        text = response.choices[0].message.content or ""
        questions = [q.strip() for q in text.strip().split("\n") if q.strip()]
        return questions[:n]
```

- [ ] **Step 7: Implement loader.py**

```python
# scraper/loader.py
from __future__ import annotations
import json
import asyncio
import asyncpg
from scraper.chunker import chunk_text
from scraper.embedder import Embedder
from scraper.question_gen import QuestionGenerator


async def load_articles(
    db_url: str,
    articles_file: str,
    embedder: Embedder,
    question_gen: QuestionGenerator | None = None,
    force: bool = False,
) -> None:
    """Load scraped articles into Postgres with embeddings and optional question generation."""
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)

    with open(articles_file) as f:
        articles = [json.loads(line) for line in f]

    for article in articles:
        async with pool.acquire() as conn:
            # Check if already exists
            existing = await conn.fetchval("SELECT id FROM articles WHERE url = $1", article["url"])
            if existing and not force:
                continue

            # Upsert article
            art_id = await conn.fetchval(
                """
                INSERT INTO articles (url, title, content, product_category, product_sub_category, related_urls, scraped_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
                ON CONFLICT (url) DO UPDATE SET content = $3, scraped_at = now()
                RETURNING id
                """,
                article["url"], article["title"], article["content"],
                article.get("product_category"), article.get("product_sub_category"),
                json.dumps(article.get("related_urls", [])),
            )

            # Delete old chunks
            await conn.execute("DELETE FROM article_chunks WHERE article_id = $1", art_id)

        # Chunk and embed
        chunks = chunk_text(article["content"])
        if chunks:
            embeddings = embedder.embed_batch(chunks)
            async with pool.acquire() as conn:
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    await conn.execute(
                        "INSERT INTO article_chunks (article_id, chunk_index, chunk_text, embedding) VALUES ($1, $2, $3, $4)",
                        art_id, i, chunk, str(embedding),
                    )

        # Generate questions
        if question_gen and article.get("content"):
            questions = question_gen.generate(article.get("title", ""), article["content"])
            async with pool.acquire() as conn:
                for q in questions:
                    await conn.execute(
                        "INSERT INTO questions (article_id, question_text) VALUES ($1, $2)",
                        art_id, q,
                    )

    await pool.close()
```

- [ ] **Step 8: Add `load` command to cli.py**

Add this to `scraper/cli.py`:

```python
@cli.command()
@click.option("--input", "input_file", required=True, help="JSONL file from scrape command")
@click.option("--db-url", envvar="DATABASE_URL", required=True, help="Postgres connection string")
@click.option("--api-key", envvar="BRAINTRUST_API_KEY", required=True, help="Braintrust API key")
@click.option("--gateway-url", default="https://gateway.braintrust.dev", help="Gateway base URL")
@click.option("--generate-questions/--no-questions", default=True, help="Generate questions per article")
@click.option("--force", is_flag=True, help="Re-process articles already in the database")
def load(input_file: str, db_url: str, api_key: str, gateway_url: str, generate_questions: bool, force: bool):
    """Load scraped articles into Postgres with embeddings."""
    from scraper.embedder import Embedder
    from scraper.question_gen import QuestionGenerator
    from scraper.loader import load_articles

    embedder = Embedder(gateway_base_url=gateway_url, api_key=api_key)
    qgen = QuestionGenerator(gateway_base_url=gateway_url, api_key=api_key) if generate_questions else None
    asyncio.run(load_articles(db_url, input_file, embedder, qgen, force=force))
    logger.info("Load complete.")
```

- [ ] **Step 9: Commit**

```bash
git add scraper/chunker.py scraper/embedder.py scraper/question_gen.py scraper/loader.py scraper/cli.py tests/scraper/test_chunker.py
git commit -m "feat: scraper pipeline - chunker, embedder, question generator, and DB loader with CLI"
```

---

## Phase 7: Integration & Smoke Test

### Task 16: Full integration test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""
Integration test: requires Docker Compose `db` running and BRAINTRUST_API_KEY set.
Run with: PYTHONPATH=src pytest tests/test_integration.py -v --timeout=60
"""
import os
import pytest
import asyncpg
from agent.config import Settings
from agent.models import SessionState, AuthState
from agent.orchestrator import Orchestrator
from db.seed import seed_users

pytestmark = pytest.mark.skipif(
    not os.getenv("BRAINTRUST_API_KEY"),
    reason="BRAINTRUST_API_KEY not set - skipping integration tests",
)


@pytest.fixture(scope="module")
async def orchestrator():
    settings = Settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    await seed_users(pool)
    orch = Orchestrator(settings=settings, db_pool=pool)
    yield orch
    await pool.close()


@pytest.mark.asyncio
async def test_knowledge_flow(orchestrator):
    session = SessionState(
        session_id="integration-knowledge",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    response = await orchestrator.handle_message("How do I reset my Salesforce password?", session)
    assert len(response) > 0
    assert session.turn_count == 1
    assert session.current_topic is not None


@pytest.mark.asyncio
async def test_case_creation_flow(orchestrator):
    session = SessionState(
        session_id="integration-case",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    response = await orchestrator.handle_message("I want to create a case", session)
    assert len(response) > 0
    assert session.current_topic == "case_creation"


@pytest.mark.asyncio
async def test_off_topic_flow(orchestrator):
    session = SessionState(session_id="integration-offtopic")
    response = await orchestrator.handle_message("What's the weather in San Francisco?", session)
    assert len(response) > 0
    # Should redirect to approved topics
    assert session.current_topic == "off_topic"
```

- [ ] **Step 2: Run integration tests**

```bash
docker compose up db -d
PYTHONPATH=src BRAINTRUST_API_KEY=$BRAINTRUST_API_KEY pytest tests/test_integration.py -v --timeout=60
```

Expected: PASS (requires valid Braintrust API key and running Postgres)

- [ ] **Step 3: Run all tests**

```bash
PYTHONPATH=src pytest tests/ -v --timeout=60 -k "not integration"
```

Expected: All unit tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: integration tests for knowledge, case creation, and off-topic flows"
```

---

### Task 17: Docker build and end-to-end verification

- [ ] **Step 1: Build and start all services**

```bash
docker compose build
docker compose up -d
```

- [ ] **Step 2: Seed the database**

```bash
docker compose exec agent python -c "
import asyncio, asyncpg
from db.seed import seed_users
async def main():
    pool = await asyncpg.create_pool('postgresql://sfdc:sfdc@db:5432/sfdc')
    await seed_users(pool)
    await pool.close()
asyncio.run(main())
"
```

- [ ] **Step 3: Verify Chainlit is accessible**

Open http://localhost:8000 in a browser. Verify:
- Welcome message appears
- Can send a message and receive a response
- Knowledge queries return answers
- "create a case" triggers the intake flow
- "transfer to agent" triggers the transfer flow
- Off-topic queries are redirected

- [ ] **Step 4: Verify traces in Braintrust**

Check the Braintrust dashboard for the `sfdc-help-agent` project. Verify:
- Session spans appear
- Turn spans nested under sessions
- Classify and execute spans nested under turns
- Tool call spans with inputs/outputs

- [ ] **Step 5: Commit final state**

```bash
git add -A
git commit -m "feat: complete functional demo - Docker build verified, end-to-end flow working"
```

---

## Summary

| Phase | Tasks | What it delivers |
|---|---|---|
| 1: Scaffold | 1-2 | Docker, DB, config, project structure |
| 2: Models & Foundation | 3-5 | Data models, tool base, 5 topic definitions |
| 3: Tools | 6-8 | All 11 tool implementations |
| 4: Orchestration | 9-11 | Classifier, executor, orchestrator |
| 5: Tracing & Frontend | 12-13 | Braintrust tracing, Chainlit app |
| 6: Scraper | 14-15 | Full scraper pipeline (crawl, chunk, embed, question gen) |
| 7: Integration | 16-17 | Integration tests, Docker build, E2E verification |
