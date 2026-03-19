from __future__ import annotations
from topics.base import Topic
from topics.knowledge import KNOWLEDGE_FAQ
from topics.case_creation import CASE_CREATION
from topics.agent_transfer import AGENT_TRANSFER
from topics.case_management import CASE_MANAGEMENT
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
        lines = ["Classify the user's intent into one of these topics:\n"]
        for topic in self._topics.values():
            lines.append(f"- **{topic.id}**: {topic.classification_description}")
        lines.append(
            "\nRespond with JSON: {\"topic_id\": \"<id>\", \"confidence\": <0.0-1.0>}"
        )
        return "\n".join(lines)


def get_default_registry() -> TopicRegistry:
    registry = TopicRegistry()
    for topic in [KNOWLEDGE_FAQ, CASE_CREATION, AGENT_TRANSFER, CASE_MANAGEMENT, OFF_TOPIC]:
        registry.register(topic)
    return registry
