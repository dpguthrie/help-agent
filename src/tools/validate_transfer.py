from tools.base import Tool, ToolResult


class ValidateAndTransferTool(Tool):
    name = "validate_and_transfer"
    description = "Validates whether the user is eligible for transfer to a human support engineer and initiates the transfer."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output={"eligible": False, "reason": "NOT_AUTHENTICATED"})
        if not session.auth_state.is_chat_transfer_allowed:
            return ToolResult(status="ok", output={"eligible": False, "reason": "Chat transfer is not available for this tenant."})
        return ToolResult(
            status="ok",
            output={
                "eligible": True,
                "session_id": session.session_id,
                "message": "Transferring to a support engineer now.",
            },
        )
