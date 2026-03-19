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
            "tenantName": row["tenant_name"],
            "orgId": row["org_id"],
            "product": row["product"],
            "successPlan": row["success_plan"],
            "timezone": row["timezone"],
            "phoneNumberForSev1": row["phone_number"],
            "canCreateCase": row["can_create_case"],
            "isChatTransferAllowed": row["is_chat_transfer_allowed"],
            "isTenantSelected": True,
            "isSeverityQuestionRequired": True,
            "isOrgIdRequired": True,
            "isOrgPickerDisabled": False,
            "showDisclaimer": False,
            "validationErrorMessage": None,
            "tenantConfirmationText": "I can help with the following org.",
            "orgIdHelpText": "Find your OrgID (https://help.salesforce.com/s/articleView?id=000385215&type=1)",
        })
