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
                "responseMessage": "Chat transfer is not available for this tenant's support plan.",
                "recommendCaseOnEscalation": True,
            })
        return ToolResult(status="ok", output={
            "isValidationPassed": True,
            "responseMessage": f"Validation Success Session ID: {session.session_id}",
            "recommendCaseOnEscalation": False,
            "tenantName": session.auth_state.tenant_name,
            "product": session.auth_state.product,
        })
