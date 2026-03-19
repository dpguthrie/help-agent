from __future__ import annotations
from topics.base import Topic
from topics.prompt_injection import PROMPT_INJECTION
from topics.inappropriate_content import INAPPROPRIATE_CONTENT
from topics.reverse_engineering import REVERSE_ENGINEERING
from topics.ambiguous_question import AMBIGUOUS_QUESTION
from topics.knowledge import KNOWLEDGE_FAQ
from topics.case_creation import CASE_CREATION
from topics.agent_transfer import AGENT_TRANSFER
from topics.case_management import CASE_MANAGEMENT
from topics.appointment_scheduling import APPOINTMENT_SCHEDULING
from topics.contract_renewals import CONTRACT_RENEWALS
from topics.off_topic import OFF_TOPIC


class TopicRegistry:
    def __init__(self) -> None:
        self._topics: dict[str, Topic] = {}

    def register(self, topic: Topic) -> None:
        self._topics[topic.id] = topic

    def get(self, topic_id: str) -> Topic | None:
        return self._topics.get(topic_id)

    def all(self) -> list[Topic]:
        return list(self._topics.values())

    def classification_prompt(self) -> str:
        lines = ["Classify the user's intent into exactly one of these topics:\n"]
        for topic in self._topics.values():
            lines.append(f"- **{topic.id}**: {topic.classification_description}")
        lines.append(
            '\nYou MUST respond with ONLY a JSON object in this exact format, no other text:'
            '\n{"topic_id": "<id>", "confidence": <0.0-1.0>}'
        )
        return "\n".join(lines)


# Order matters: safety topics first, then functional, then fallback
_TOPIC_ORDER = [
    PROMPT_INJECTION,
    INAPPROPRIATE_CONTENT,
    REVERSE_ENGINEERING,
    AMBIGUOUS_QUESTION,
    KNOWLEDGE_FAQ,
    CASE_CREATION,
    AGENT_TRANSFER,
    CASE_MANAGEMENT,
    APPOINTMENT_SCHEDULING,
    CONTRACT_RENEWALS,
    OFF_TOPIC,
]


def get_default_registry() -> TopicRegistry:
    registry = TopicRegistry()
    for topic in _TOPIC_ORDER:
        registry.register(topic)
    return registry
