from __future__ import annotations
import json
import re
from openai import AsyncOpenAI
from agent.config import Settings
from agent.models import ClassifierResult, Message
from topics.registry import TopicRegistry


def _extract_json(text: str) -> dict:
    """Extract JSON from text that may be wrapped in markdown code fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = cleaned.rstrip("`").strip()
    return json.loads(cleaned)


class TopicClassifier:
    def __init__(self, settings: Settings, topic_registry: TopicRegistry):
        self._settings = settings
        self._topic_registry = topic_registry
        self._client = AsyncOpenAI(
            base_url=settings.gateway_base_url,
            api_key=settings.braintrust_api_key,
        )

    async def classify(
        self,
        user_message: str,
        history: list[Message],
        extra_headers: dict | None = None,
    ) -> ClassifierResult:
        system_prompt = self._topic_registry.classification_prompt()

        history_text = ""
        if history:
            recent = history[-6:]
            lines = [f"{m.role}: {m.content}" for m in recent if m.role in ("user", "assistant")]
            history_text = "\n\nRecent conversation:\n" + "\n".join(lines) + "\n"

        user_content = f"{history_text}\nCurrent user message: {user_message}"

        response = await self._client.chat.completions.create(
            model=self._settings.classifier_model,
            temperature=self._settings.classifier_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            **({"extra_headers": extra_headers} if extra_headers else {}),
        )

        content = response.choices[0].message.content or ""
        try:
            data = _extract_json(content)
            result = ClassifierResult(
                topic_id=data.get("topic_id", "off_topic"),
                confidence=float(data.get("confidence", 0.0)),
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            result = ClassifierResult(topic_id="off_topic", confidence=0.0)

        if result.confidence < self._settings.confidence_threshold:
            result = ClassifierResult(topic_id="off_topic", confidence=result.confidence)

        return result
