from tools.base import Tool, ToolResult


class EndSessionTool(Tool):
    name = "end_session"
    description = (
        "Ends the conversation with a user completely. Only call this when the user "
        "is completely satisfied and has no other questions. Do not end session without "
        "asking the user first."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Farewell message to the user."},
        },
        "required": ["message"],
    }

    async def execute(self, params, session):
        return ToolResult(status="ok", output={
            "session_ended": True,
            "message": params.get("message", "Thank you for contacting Salesforce support. Goodbye!"),
        })
