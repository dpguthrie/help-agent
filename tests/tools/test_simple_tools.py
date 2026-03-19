import pytest
from agent.models import SessionState, AuthState
from tools.datetime_tool import GetDateTimeTool
from tools.emit_event import EmitEventTool
from tools.raise_flag import RaiseFlagTool
from tools.validate_transfer import ValidateAndTransferTool
from tools.get_personalization import GetPersonalizationTool


@pytest.mark.asyncio
async def test_get_datetime():
    tool = GetDateTimeTool()
    result = await tool.execute({}, session=None)
    assert result.status == "ok"
    assert "T" in result.output


@pytest.mark.asyncio
async def test_emit_event_login():
    tool = EmitEventTool()
    result = await tool.execute({"event_name": "LOGIN_REQUESTED"}, session=None)
    assert result.status == "ok"
    assert result.output["name"] == "LOGIN_REQUESTED"


@pytest.mark.asyncio
async def test_validate_transfer_authenticated():
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="ACME", org_id="001", product="core",
            is_chat_transfer_allowed=True,
        ),
    )
    tool = ValidateAndTransferTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output["isValidationPassed"] is True


@pytest.mark.asyncio
async def test_validate_transfer_not_allowed():
    session = SessionState(
        session_id="test",
        auth_state=AuthState(
            tenant_name="ACME", org_id="001", product="core",
            is_chat_transfer_allowed=False,
        ),
    )
    tool = ValidateAndTransferTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert result.output["isValidationPassed"] is False


@pytest.mark.asyncio
async def test_validate_transfer_not_authenticated():
    session = SessionState(session_id="test")
    tool = ValidateAndTransferTool()
    result = await tool.execute({}, session)
    assert result.status == "ok"
    assert "NOT_AUTHENTICATED" in str(result.output)


@pytest.mark.asyncio
async def test_raise_flag():
    tool = RaiseFlagTool()
    result = await tool.execute({"reason": "customer upset"}, session=None)
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_get_personalization():
    tool = GetPersonalizationTool()
    result = await tool.execute({}, session=None)
    assert result.status == "ok"
