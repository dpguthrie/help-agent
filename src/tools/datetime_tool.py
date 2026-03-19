from datetime import datetime, timezone
from tools.base import Tool, ToolResult


class GetDateTimeTool(Tool):
    name = "get_datetime"
    description = "Returns the current date and time in UTC ISO format."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        now = datetime.now(timezone.utc).isoformat()
        return ToolResult(status="ok", output=now)
