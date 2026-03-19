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
