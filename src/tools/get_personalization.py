from tools.base import Tool, ToolResult


class GetPersonalizationTool(Tool):
    name = "get_personalization"
    description = "Returns personalized solutions and Customer Success Manager information."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        return ToolResult(
            status="ok",
            output={
                "csm_name": "Jane Doe",
                "csm_email": "jane.doe@salesforce.com",
                "solutions": ["Schedule a review with your CSM for personalized guidance."],
            },
        )
