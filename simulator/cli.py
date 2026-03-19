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
