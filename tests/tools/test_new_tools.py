import pytest
from agent.models import SessionState, AuthState
from tools.end_session import EndSessionTool
from tools.change_case_severity import ChangeCaseSeverityTool
from tools.schedule_appointment import ScheduleAppointmentTool
from tools.retrieve_contracts import RetrieveAccountContractsTool, RetrieveContractDetailsTool


@pytest.mark.asyncio
async def test_end_session():
    tool = EndSessionTool()
    result = await tool.execute({"message": "Goodbye!"}, session=None)
    assert result.status == "ok"
    assert result.output["session_ended"] is True
    assert "Goodbye" in result.output["message"]


@pytest.mark.asyncio
async def test_change_case_severity(seeded_db):
    from tools.create_case import CreateCaseTool
    import re
    # Create a case first
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core"),
    )
    create_result = await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)
    # Extract case number from the markdown output
    case_match = re.search(r"\*\*Here is your Case Number: \*\*(\d+)", str(create_result.output))
    assert case_match, "Case number not found in create_case output"
    case_number = case_match.group(1)

    tool = ChangeCaseSeverityTool(seeded_db)
    result = await tool.execute({"case_number": case_number, "new_severity": 2}, session)
    assert result.status == "ok"
    assert result.output["new_severity"] == 2


@pytest.mark.asyncio
async def test_schedule_appointment():
    session = SessionState(
        session_id="test",
        auth_state=AuthState(tenant_name="ACME", org_id="001", product="core"),
    )
    tool = ScheduleAppointmentTool()
    result = await tool.execute({
        "appointment_type": "technical review",
        "preferred_date": "2026-04-01",
        "preferred_time": "10:00 AM",
    }, session)
    assert result.status == "ok"
    assert "appointment_id" in result.output


@pytest.mark.asyncio
async def test_retrieve_account_contracts():
    session = SessionState(
        session_id="test",
        auth_state=AuthState(tenant_name="ACME", org_id="001", product="core", success_plan="Premier"),
    )
    tool = RetrieveAccountContractsTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert "contracts" in result.output
    assert len(result.output["contracts"]) >= 1


@pytest.mark.asyncio
async def test_retrieve_account_contracts_not_authenticated():
    session = SessionState(session_id="test")
    tool = RetrieveAccountContractsTool()
    result = await tool.execute({}, session)
    assert result.output == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_retrieve_contract_details():
    tool = RetrieveContractDetailsTool()
    result = await tool.execute({"contract_id": "CTR-001"}, session=None)
    assert result.status == "ok"
    assert "renewal_date" in result.output
    assert "renewal_manager_name" in result.output
