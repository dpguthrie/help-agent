from __future__ import annotations
import asyncpg
import numpy as np
from openai import AsyncOpenAI
from tools.base import Tool, ToolResult


class SearchKnowledgeTool(Tool):
    name = "search_knowledge"
    description = "Searches the Salesforce knowledge base for articles relevant to the user's question. Returns results with relevance scores (0.0-1.0). Scores below 0.3 indicate low relevance."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["query"],
    }

    def __init__(self, pool: asyncpg.Pool, gateway_base_url: str, api_key: str, model: str = "text-embedding-3-small"):
        self._pool = pool
        self._client = AsyncOpenAI(base_url=gateway_base_url, api_key=api_key)
        self._model = model

    async def _embed_query(self, query: str) -> np.ndarray:
        response = await self._client.embeddings.create(model=self._model, input=query)
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def execute(self, params, session):
        query = params.get("query", "")
        embedding = await self._embed_query(query)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ac.chunk_text, a.url, a.title, a.product_category,
                       1 - (ac.embedding <=> $1) AS score
                FROM article_chunks ac
                JOIN articles a ON a.id = ac.article_id
                ORDER BY ac.embedding <=> $1
                LIMIT 5
                """,
                embedding,
            )
        results = [
            {
                "chunk_text": r["chunk_text"],
                "url": r["url"],
                "title": r["title"],
                "product_category": r["product_category"],
                "score": float(r["score"]),
            }
            for r in rows
        ]
        return ToolResult(status="ok", output={"results": results, "query": query})
