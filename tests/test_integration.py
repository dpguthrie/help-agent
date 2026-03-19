"""
Integration test: requires Docker Compose `db` running and BRAINTRUST_API_KEY set.
Run with: PYTHONPATH=src pytest tests/test_integration.py -v --timeout=60
"""
import os
import pytest
import asyncpg
from pgvector.asyncpg import register_vector
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
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5, init=lambda c: register_vector(c))
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
    assert session.current_topic == "off_topic"
