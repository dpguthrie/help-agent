from __future__ import annotations
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
