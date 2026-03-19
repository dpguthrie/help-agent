from tools.base import Tool, ToolResult


class RetrieveAccountContractsTool(Tool):
    name = "retrieve_account_contracts"
    description = "Retrieves active contracts for the authenticated user's account."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        # Simulated contracts based on user's product/plan
        contracts = [
            {
                "id": f"CTR-{session.auth_state.org_id[-4:]}01",
                "product": session.auth_state.product,
                "start_date": "2025-01-01",
                "end_date": "2026-12-31",
                "status": "active",
                "success_plan": session.auth_state.success_plan,
                "renewal_manager": "Sarah Johnson",
            },
        ]
        return ToolResult(status="ok", output={"contracts": contracts})


class RetrieveContractDetailsTool(Tool):
    name = "retrieve_contract_details"
    description = "Retrieves detailed information about a specific contract."
    parameters = {
        "type": "object",
        "properties": {
            "contract_id": {"type": "string", "description": "The contract ID."},
        },
        "required": ["contract_id"],
    }

    async def execute(self, params, session):
        return ToolResult(status="ok", output={
            "contract_id": params["contract_id"],
            "product": "Salesforce Platform",
            "terms": "24 months",
            "start_date": "2025-01-01",
            "renewal_date": "2026-12-31",
            "renewal_manager_name": "Sarah Johnson",
            "renewal_manager_email": "sarah.johnson@salesforce.com",
            "pricing_tier": "Enterprise",
            "status": "active",
        })
