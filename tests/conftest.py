import asyncio
import os
import pytest
import asyncpg
from pgvector.asyncpg import register_vector

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://sfdc:sfdc@localhost:5433/sfdc")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=5, init=_init_conn)
    yield pool
    await pool.close()


async def _init_conn(conn):
    await register_vector(conn)


@pytest.fixture(autouse=True)
async def clean_tables(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM cases")
        await conn.execute("DELETE FROM sessions")
    yield


@pytest.fixture
async def seeded_db(db_pool):
    from db.seed import seed_users
    await seed_users(db_pool)
    return db_pool
