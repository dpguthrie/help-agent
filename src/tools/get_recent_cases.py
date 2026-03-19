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
