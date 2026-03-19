from __future__ import annotations
from openai import OpenAI


class QuestionGenerator:
    def __init__(self, gateway_base_url: str, api_key: str, model: str = "claude-haiku-4-5"):
        self._client = OpenAI(base_url=gateway_base_url, api_key=api_key)
        self._model = model

    def generate(self, title: str, content: str, n: int = 5) -> list[str]:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate realistic customer support questions. "
                        "Given a Salesforce help article, produce questions a customer "
                        "might ask that this article would answer. "
                        "Return one question per line, no numbering or bullets."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Title: {title}\n\nContent: {content[:2000]}\n\nGenerate {n} questions:",
                },
            ],
        )
        text = response.choices[0].message.content or ""
        questions = [q.strip() for q in text.strip().split("\n") if q.strip()]
        return questions[:n]
