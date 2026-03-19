from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class AuthState(BaseModel):
    tenant_name: str
    org_id: str
    product: str
    success_plan: str = "Standard"
    timezone: str | None = None
    phone_number: str | None = None
    can_create_case: bool = True
    is_chat_transfer_allowed: bool = True


class CaseIntakeState(BaseModel):
    tenant_confirmed: bool = False
    timezone: str | None = None
    description: str | None = None
    severity: int | None = None
    phone_number: str | None = None
    summary_confirmed: bool = False

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.tenant_confirmed:
            missing.append("tenant_confirmed")
        if self.timezone is None:
            missing.append("timezone")
        if self.description is None:
            missing.append("description")
        if self.severity is None:
            missing.append("severity")
        if self.severity is not None and self.severity <= 2 and self.phone_number is None:
            missing.append("phone_number")
        if not self.summary_confirmed:
            missing.append("summary_confirmed")
        return missing


class ClassifierResult(BaseModel):
    topic_id: str
    confidence: float


class SessionState(BaseModel):
    session_id: str
    conversation_history: list[Message] = Field(default_factory=list)
    current_topic: str | None = None
    auth_state: AuthState | None = None
    case_intake: CaseIntakeState | None = None
    turn_count: int = 0
    session_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_ended: bool = False
