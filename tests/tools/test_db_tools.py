import pytest
from agent.models import SessionState, AuthState
from tools.user_context import GetUserContextTool
from tools.create_case import CreateCaseTool
from tools.get_case import GetCaseTool
from tools.get_recent_cases import GetRecentCasesTool
from tools.perform_case_action import PerformCaseActionTool


@pytest.mark.asyncio
async def test_get_user_context_authenticated(seeded_db):
    tool = GetUserContextTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output["tenantName"] == "COMPANY_demo_001"
    assert result.output["successPlan"] == "Premier"


@pytest.mark.asyncio
async def test_get_user_context_not_authenticated(seeded_db):
    tool = GetUserContextTool(seeded_db)
    session = SessionState(session_id="test")
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_create_case(seeded_db):
    tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    result = await tool.execute({
        "subject": "Test Issue",
        "description": "Something is broken",
        "severity": 3,
        "timezone": "America/Chicago",
    }, session)
    assert result.status == "ok"
    assert "output" in result.output
    assert "Case Number" in result.output["output"]


def _extract_case_number(create_result):
    """Extract case number from the formatted markdown output string."""
    import re
    match = re.search(r"\*\*Here is your Case Number: \*\*(\d+)", create_result.output["output"])
    assert match, "Case number not found in create_case output"
    return match.group(1)


@pytest.mark.asyncio
async def test_get_case(seeded_db):
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    create_result = await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)
    case_number = _extract_case_number(create_result)

    tool = GetCaseTool(seeded_db)
    result = await tool.execute({"case_number": case_number}, session)
    assert result.status == "ok"
    assert result.output["case_number"] == case_number


@pytest.mark.asyncio
async def test_get_recent_cases(seeded_db):
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)

    tool = GetRecentCasesTool(seeded_db)
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert len(result.output["cases"]) >= 1


@pytest.mark.asyncio
async def test_perform_case_action_reopen(seeded_db):
    create_tool = CreateCaseTool(seeded_db)
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="COMPANY_demo_001", org_id="SFID_demo_001", product="core",
        ),
    )
    create_result = await create_tool.execute({
        "subject": "Test", "description": "Test", "severity": 4, "timezone": "UTC",
    }, session)
    case_number = _extract_case_number(create_result)

    tool = PerformCaseActionTool(seeded_db)
    result = await tool.execute({
        "case_number": case_number, "action": "reopen",
    }, session)
    assert result.status == "ok"
