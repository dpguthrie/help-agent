from __future__ import annotations
from openai import OpenAI


class Embedder:
    def __init__(self, gateway_base_url: str, api_key: str, model: str = "text-embedding-3-small"):
        self._client = OpenAI(base_url=gateway_base_url, api_key=api_key)
        self._model = model

    def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self._client.embeddings.create(model=self._model, input=batch)
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings
