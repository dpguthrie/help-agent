from tools.base import Tool, ToolResult


class EmitEventTool(Tool):
    name = "emit_event"
    description = "Triggers a UI event. Supported events: LOGIN_REQUESTED, showOrgPickerModalForASA."
    parameters = {
        "type": "object",
        "properties": {
            "event_name": {
                "type": "string",
                "enum": ["LOGIN_REQUESTED", "showOrgPickerModalForASA"],
                "description": "The UI event to trigger.",
            }
        },
        "required": ["event_name"],
    }

    async def execute(self, params, session):
        event_name = params.get("event_name", "")
        return ToolResult(status="ok", output={"name": event_name, "data": None})
