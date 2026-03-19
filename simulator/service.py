"""
Simulator Service - Runs as a background service on Railway.

Generates simulated conversations at a configurable cadence to mimic
real traffic patterns. Produces Braintrust traces for error analysis.

Usage:
  # Run as a service (continuous, with cadence)
  python -m simulator.service

  # Or via CLI
  python -m simulator.cli service --cadence 300 --batch-size 5

Environment variables:
  SIMULATOR_CADENCE       Seconds between batches (default: 300 = 5 min)
  SIMULATOR_BATCH_SIZE    Conversations per batch (default: 5)
  SIMULATOR_CONCURRENCY   Max concurrent conversations (default: 3)
  SIMULATOR_MODEL         Model for user sim (default: gpt-5-nano)
  SIMULATOR_AGENT_MODEL   Override agent executor model (optional)
  SIMULATOR_ENABLED       Set to "false" to disable (default: true)
"""
from __future__ import annotations
import asyncio
import logging
import os
import random
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("simulator.service")


class SimulatorService:
    def __init__(self):
        self.cadence = int(os.getenv("SIMULATOR_CADENCE", "300"))
        self.batch_size = int(os.getenv("SIMULATOR_BATCH_SIZE", "5"))
        self.concurrency = int(os.getenv("SIMULATOR_CONCURRENCY", "3"))
        self.sim_model = os.getenv("SIMULATOR_MODEL", "gpt-5-nano")
        self.agent_model = os.getenv("SIMULATOR_AGENT_MODEL", None)
        self.enabled = os.getenv("SIMULATOR_ENABLED", "true").lower() != "false"
        self._running = True
        self._orchestrator = None
        self._sim_client = None
        self._db_pool = None

    async def setup(self):
        """Initialize DB pool, orchestrator, and sim client."""
        import asyncpg
        from pgvector.asyncpg import register_vector
        from openai import AsyncOpenAI
        from agent.config import Settings
        from agent.orchestrator import Orchestrator

        settings = Settings()
        if self.agent_model:
            settings.executor_model = self.agent_model
            logger.info(f"Agent executor model: {self.agent_model}")

        self._db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=self.concurrency + 2,
            init=lambda c: register_vector(c),
        )
        self._orchestrator = Orchestrator(settings=settings, db_pool=self._db_pool)
        self._sim_client = AsyncOpenAI(
            base_url=settings.gateway_base_url,
            api_key=settings.braintrust_api_key,
        )
        logger.info(f"Simulator service initialized")
        logger.info(f"  Cadence: {self.cadence}s")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Concurrency: {self.concurrency}")
        logger.info(f"  Sim model: {self.sim_model}")

    async def run_batch(self):
        """Run a single batch of simulated conversations."""
        from simulator.runner import run_simulation

        logger.info(f"Starting batch of {self.batch_size} conversations...")
        results = await run_simulation(
            num_conversations=self.batch_size,
            concurrency=self.concurrency,
            orchestrator=self._orchestrator,
            sim_client=self._sim_client,
            sim_model=self.sim_model,
            db_pool=self._db_pool,
            max_turns=random.randint(5, 10),
        )

        # Summarize
        total = len(results)
        achieved = sum(1 for r in results if r.get("end_reason") == "goal_achieved")
        frustrated = sum(1 for r in results if r.get("end_reason") == "frustrated")
        errors = sum(1 for r in results if "error" in r)
        avg_turns = sum(r.get("turns", 0) for r in results) / max(total, 1)
        avg_frust = sum(r.get("final_frustration", 0) for r in results) / max(total, 1)

        logger.info(
            f"Batch complete: {total} conversations | "
            f"achieved={achieved} frustrated={frustrated} errors={errors} | "
            f"avg_turns={avg_turns:.1f} avg_frustration={avg_frust:.2f}"
        )
        return results

    async def run_forever(self):
        """Main service loop - run batches at the configured cadence."""
        await self.setup()

        if not self.enabled:
            logger.info("Simulator service is DISABLED (SIMULATOR_ENABLED=false). Exiting.")
            return

        logger.info(f"Simulator service starting. Running every {self.cadence}s.")

        while self._running:
            try:
                await self.run_batch()
            except Exception as e:
                logger.error(f"Batch failed: {e}", exc_info=True)

            # Add jitter to cadence (±20%) to avoid regular patterns
            jitter = self.cadence * random.uniform(-0.2, 0.2)
            sleep_time = max(30, self.cadence + jitter)
            logger.info(f"Next batch in {sleep_time:.0f}s")

            # Sleep in small increments so we can respond to shutdown signals
            slept = 0
            while slept < sleep_time and self._running:
                await asyncio.sleep(min(5, sleep_time - slept))
                slept += 5

        logger.info("Simulator service shutting down.")
        if self._db_pool:
            await self._db_pool.close()

    def stop(self):
        self._running = False


def main():
    service = SimulatorService()

    # Handle graceful shutdown
    loop = asyncio.new_event_loop()

    def shutdown_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        service.stop()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        loop.run_until_complete(service.run_forever())
    finally:
        loop.close()


if __name__ == "__main__":
    # Allow running as: python -m simulator.service
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    main()
