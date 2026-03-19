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
    from pgvector.asyncpg import register_vector
    await register_vector(conn)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
