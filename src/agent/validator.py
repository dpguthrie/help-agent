from __future__ import annotations
import json
import re
from dataclasses import dataclass
from openai import AsyncOpenAI
from agent.config import Settings


@dataclass
class ValidationResult:
    is_grounded: bool
    reason: str
    sources: list[str]


class GroundingValidator:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.gateway_base_url,
            api_key=settings.braintrust_api_key,
        )

    async def validate(
        self,
        response: str,
        tool_results: list[dict],
        conversation_context: list[dict],
        extra_headers: dict | None = None,
    ) -> ValidationResult:
        tool_history = json.dumps(tool_results[:5], default=str)[:2000] if tool_results else "[]"
        conv_history = json.dumps(conversation_context[-6:], default=str)[:2000] if conversation_context else "[]"

        llm_response = await self._client.chat.completions.create(
            model=self._settings.validation_model,
            temperature=self._settings.validation_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You validate whether an AI agent's response is grounded in the available context. "
                        "A response is GROUNDED if its claims are supported by the tool results (function_history) "
                        "or conversation history. A response is NOT_GROUNDED if it makes claims not supported "
                        "by any available evidence. Respond with ONLY a JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"function_history: {tool_history}\n\n"
                        f"conversation_history: {conv_history}\n\n"
                        f"response to validate: \"{response[:1000]}\"\n\n"
                        'Respond with JSON: {"result": "GROUNDED|NOT_GROUNDED", '
                        '"reason": "explanation", "sources": ["list of evidence"]}'
                    ),
                },
            ],
            **({"extra_headers": extra_headers} if extra_headers else {}),
        )

        content = llm_response.choices[0].message.content or ""
        cleaned = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()

        try:
            data = json.loads(cleaned)
            return ValidationResult(
                is_grounded=data.get("result", "GROUNDED") == "GROUNDED",
                reason=data.get("reason", ""),
                sources=data.get("sources", []),
            )
        except (json.JSONDecodeError, ValueError):
            # Fail-open: if we can't parse, assume grounded
            return ValidationResult(is_grounded=True, reason="Validation parse error - defaulting to grounded", sources=[])
