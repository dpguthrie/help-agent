from agent.models import SessionState, AuthState, CaseIntakeState, Message


def test_session_state_defaults():
    state = SessionState(session_id="test-123")
    assert state.current_topic is None
    assert state.auth_state is None
    assert state.case_intake is None
    assert state.turn_count == 0
    assert state.conversation_history == []


def test_auth_state():
    auth = AuthState(
        tenant_name="ACME Corp",
        org_id="00D123456789",
        product="core",
        success_plan="Premier",
    )
    assert auth.can_create_case is True
    assert auth.is_chat_transfer_allowed is True
    assert auth.timezone is None


def test_case_intake_state_missing_fields():
    intake = CaseIntakeState()
    missing = intake.missing_fields()
    assert "description" in missing
    assert "severity" in missing
    assert "timezone" in missing


def test_case_intake_state_phone_required_for_sev1():
    intake = CaseIntakeState(
        tenant_confirmed=True, timezone="UTC",
        description="broken", severity=1,
    )
    missing = intake.missing_fields()
    assert "phone_number" in missing


def test_case_intake_state_phone_not_required_for_sev3():
    intake = CaseIntakeState(
        tenant_confirmed=True, timezone="UTC",
        description="broken", severity=3,
    )
    missing = intake.missing_fields()
    assert "phone_number" not in missing


def test_message_serialization():
    msg = Message(role="user", content="hello")
    d = msg.model_dump()
    assert d["role"] == "user"
    assert d["content"] == "hello"
