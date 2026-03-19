from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class PerformCaseActionTool(Tool):
    name = "perform_case_action"
    description = "Performs an action on an existing case (reopen, close, update)."
    parameters = {
        "type": "object",
        "properties": {
            "case_number": {"type": "string", "description": "The case number."},
            "action": {"type": "string", "enum": ["reopen", "close", "update"], "description": "Action to perform."},
            "comment": {"type": "string", "description": "Optional comment for the action."},
        },
        "required": ["case_number", "action"],
    }

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        action = params["action"]
        new_status = {"reopen": "reopened", "close": "closed", "update": "open"}.get(action, "open")
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE cases SET status = $1 WHERE case_number = $2",
                new_status, params["case_number"],
            )
        if result == "UPDATE 0":
            return ToolResult(status="error", output=f"Case {params['case_number']} not found.")
        return ToolResult(status="ok", output={
            "case_number": params["case_number"],
            "action": action,
            "new_status": new_status,
            "message": f"Case {params['case_number']} has been {new_status}.",
        })
