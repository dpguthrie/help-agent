from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class ChangeCaseSeverityTool(Tool):
    name = "change_case_severity"
    description = "Changes the severity level of an existing support case."
    parameters = {
        "type": "object",
        "properties": {
            "case_number": {"type": "string", "description": "The case number."},
            "new_severity": {"type": "integer", "enum": [1, 2, 3, 4], "description": "New severity level."},
        },
        "required": ["case_number", "new_severity"],
    }

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT severity FROM cases WHERE case_number = $1", params["case_number"]
            )
            if row is None:
                return ToolResult(status="error", output=f"Case {params['case_number']} not found.")
            old_severity = row["severity"]
            await conn.execute(
                "UPDATE cases SET severity = $1 WHERE case_number = $2",
                params["new_severity"], params["case_number"],
            )
        return ToolResult(status="ok", output={
            "case_number": params["case_number"],
            "old_severity": old_severity,
            "new_severity": params["new_severity"],
            "message": f"Case {params['case_number']} severity changed from {old_severity} to {params['new_severity']}.",
        })
