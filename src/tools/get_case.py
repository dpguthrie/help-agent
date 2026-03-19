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
