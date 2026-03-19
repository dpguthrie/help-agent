# simulator/personas.py
from __future__ import annotations
import fnmatch
import random
from dataclasses import dataclass, field


@dataclass
class PersonaTemplate:
    id: str
    role: str
    technical_level: str  # low, intermediate, high
    language: str  # en, ja, fr, de, pt, es, etc.
    patience: float  # 0.0 to 1.0
    verbosity: str  # terse, concise, verbose
    goal_type: str  # knowledge, case_creation, transfer, case_management, mixed
    topic_areas: list[str] = field(default_factory=list)
    may_escalate: bool = False
    may_change_topic: bool = False
    authenticated: bool | None = None  # True, False, or None (random)


PERSONA_TEMPLATES = [
    # Knowledge seekers
    PersonaTemplate(
        id="admin_how_to", role="Salesforce administrator",
        technical_level="intermediate", language="en", patience=0.7,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["platform", "reports", "flows", "permissions", "lightning"],
        may_escalate=True, authenticated=None,
    ),
    PersonaTemplate(
        id="developer_troubleshoot", role="Salesforce developer",
        technical_level="high", language="en", patience=0.8,
        verbosity="verbose", goal_type="knowledge",
        topic_areas=["apex", "lwc", "flows", "api", "integrations"],
        may_escalate=True, authenticated=True,
    ),
    PersonaTemplate(
        id="end_user_confused", role="business user with limited Salesforce experience",
        technical_level="low", language="en", patience=0.4,
        verbosity="terse", goal_type="knowledge",
        topic_areas=["reports", "dashboards", "password", "login", "basics"],
        may_escalate=True, may_change_topic=True, authenticated=None,
    ),
    PersonaTemplate(
        id="japanese_admin", role="Japanese Salesforce administrator",
        technical_level="intermediate", language="ja", patience=0.8,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["platform", "email", "authentication", "partner_portal"],
        may_escalate=True, authenticated=True,
    ),
    PersonaTemplate(
        id="french_user", role="French-speaking Salesforce user",
        technical_level="intermediate", language="fr", patience=0.6,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["reports", "authentication", "configuration"],
        authenticated=None,
    ),
    # Case creators
    PersonaTemplate(
        id="urgent_case_creator", role="IT manager dealing with a production outage",
        technical_level="high", language="en", patience=0.3,
        verbosity="verbose", goal_type="case_creation",
        topic_areas=["production_issues", "outages", "email", "integrations"],
        authenticated=True,
    ),
    PersonaTemplate(
        id="routine_case_creator", role="Salesforce administrator logging a non-urgent issue",
        technical_level="intermediate", language="en", patience=0.8,
        verbosity="concise", goal_type="case_creation",
        topic_areas=["configuration", "features", "bugs"],
        authenticated=True,
    ),
    # Transfer
    PersonaTemplate(
        id="wants_human", role="frustrated user who wants to talk to a real person",
        technical_level="low", language="en", patience=0.2,
        verbosity="terse", goal_type="transfer",
        topic_areas=["any"], authenticated=None,
    ),
    # Case management
    PersonaTemplate(
        id="case_follower", role="user checking on an existing support case",
        technical_level="intermediate", language="en", patience=0.6,
        verbosity="concise", goal_type="case_management",
        topic_areas=["existing_cases"], may_escalate=True, authenticated=True,
    ),
    # Mixed
    PersonaTemplate(
        id="knowledge_then_case",
        role="user who starts with a question but needs to escalate to a case",
        technical_level="intermediate", language="en", patience=0.5,
        verbosity="concise", goal_type="mixed",
        topic_areas=["platform", "email", "reports"],
        may_escalate=True, authenticated=True,
    ),
    # Edge cases
    PersonaTemplate(
        id="edge_empty_messages", role="user who sends incomplete or empty messages",
        technical_level="low", language="en", patience=0.3,
        verbosity="terse", goal_type="knowledge",
        topic_areas=["any"], may_change_topic=True, authenticated=None,
    ),
    PersonaTemplate(
        id="edge_topic_switcher", role="user who keeps changing what they want",
        technical_level="intermediate", language="en", patience=0.5,
        verbosity="concise", goal_type="mixed",
        topic_areas=["platform", "marketing", "sales", "service"],
        may_escalate=True, may_change_topic=True, authenticated=True,
    ),
    PersonaTemplate(
        id="edge_adversarial", role="user testing the boundaries of the agent",
        technical_level="high", language="en", patience=0.9,
        verbosity="verbose", goal_type="knowledge",
        topic_areas=["off_topic", "prompt_injection", "unrelated"],
        may_change_topic=True, authenticated=False,
    ),
    PersonaTemplate(
        id="edge_mixed_language",
        role="bilingual user who switches between English and another language",
        technical_level="intermediate", language="en,ja", patience=0.6,
        verbosity="concise", goal_type="knowledge",
        topic_areas=["platform", "authentication"], authenticated=None,
    ),
]


def get_random_persona(pattern: str | None = None) -> PersonaTemplate:
    pool = PERSONA_TEMPLATES
    if pattern:
        pool = [p for p in pool if fnmatch.fnmatch(p.id, pattern)]
    if not pool:
        pool = PERSONA_TEMPLATES
    return random.choice(pool)
