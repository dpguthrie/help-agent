from __future__ import annotations
import asyncpg
from tools.base import Tool, ToolResult


class GetUserContextTool(Tool):
    name = "get_user_context"
    description = "Retrieves the authenticated user's tenant context including org details, product, and eligibility flags."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE org_id = $1", session.auth_state.org_id
            )
        if row is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        return ToolResult(status="ok", output={
            "tenant_name": row["tenant_name"],
            "org_id": row["org_id"],
            "product": row["product"],
            "success_plan": row["success_plan"],
            "timezone": row["timezone"],
            "phone_number": row["phone_number"],
            "can_create_case": row["can_create_case"],
            "is_chat_transfer_allowed": row["is_chat_transfer_allowed"],
        })
