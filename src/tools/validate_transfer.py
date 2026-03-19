from tools.base import Tool, ToolResult


class ValidateAndTransferTool(Tool):
    name = "validate_and_transfer"
    description = "Validates whether the user is eligible for transfer to a human support engineer and initiates the transfer."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output={
                "isValidationPassed": False,
                "responseMessage": "NOT_AUTHENTICATED",
                "recommendCaseOnEscalation": True,
            })
        if not session.auth_state.is_chat_transfer_allowed:
            return ToolResult(status="ok", output={
                "isValidationPassed": False,
                "responseMessage": (
                    "It looks like your current tenant isn't eligible to start a chat with a "
                    "Support Engineer or you may not have an active tenant yet. If you have access "
                    "to another supported tenant, please select it and restart your conversation. "
                    "If you need to create a case, I can help you with that instead."
                ),
                "recommendCaseOnEscalation": True,
                "isSupportRestrictedForDC": False,
            })
        return ToolResult(status="ok", output={
            "isValidationPassed": True,
            "responseMessage": f"Validation Success Session ID: {session.session_id}",
            "recommendCaseOnEscalation": False,
            "tenantName": session.auth_state.tenant_name,
            "product": session.auth_state.product,
        })
