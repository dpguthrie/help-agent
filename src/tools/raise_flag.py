from tools.base import Tool, ToolResult


class RaiseFlagTool(Tool):
    name = "raise_flag_for_supervisor"
    description = "Raises a flag for supervisor review and escalation."
    parameters = {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Reason for escalation."}
        },
        "required": ["reason"],
    }

    async def execute(self, params, session):
        return ToolResult(
            status="ok",
            output={"flagged": True, "reason": params.get("reason", "")},
        )
