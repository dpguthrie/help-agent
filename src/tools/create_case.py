from __future__ import annotations
import uuid
import asyncpg
from tools.base import Tool, ToolResult


class CreateCaseTool(Tool):
    name = "create_case"
    description = "Creates a new support case with the provided details."
    parameters = {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Brief case subject."},
            "description": {"type": "string", "description": "Detailed description of the issue."},
            "severity": {"type": "integer", "enum": [1, 2, 3, 4], "description": "Severity level 1-4."},
            "timezone": {"type": "string", "description": "User's timezone."},
            "phone_number": {"type": "string", "description": "Phone with country code (required for sev 1-2)."},
        },
        "required": ["subject", "description", "severity", "timezone"],
    }

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="error", output="NOT_AUTHENTICATED")
        case_number = str(uuid.uuid4().int)[:9]
        async with self._pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE org_id = $1", session.auth_state.org_id
            )
            user_id = user_row["id"] if user_row else None
            await conn.execute(
                """
                INSERT INTO cases (case_number, user_id, tenant_name, org_id, subject, description, severity)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                case_number, user_id, session.auth_state.tenant_name,
                session.auth_state.org_id, params["subject"],
                params["description"], params["severity"],
            )
        return ToolResult(status="ok", output={
            "case_number": case_number,
            "tenant_name": session.auth_state.tenant_name,
            "org_id": session.auth_state.org_id,
            "subject": params["subject"],
            "description": params["description"],
            "severity": params["severity"],
            "success_plan": session.auth_state.success_plan,
            "message": f"Case {case_number} created successfully.",
        })
