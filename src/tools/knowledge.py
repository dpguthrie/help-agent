from __future__ import annotations
import asyncpg
import numpy as np
from openai import AsyncOpenAI
from tools.base import Tool, ToolResult


class SearchKnowledgeTool(Tool):
    name = "search_knowledge"
    description = (
        "Searches the Salesforce knowledge base for articles relevant to the user's question. "
        "Returns results with relevance scores (0.0-1.0). Scores below 0.3 indicate low relevance. "
        "When the user is authenticated, include their product context in the query for better results "
        "(e.g., 'marketing cloud email setup' instead of just 'email setup')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query. Include the user's product name when relevant for better results."},
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

        # If user is authenticated, boost results from their product category
        product_category = None
        if session and session.auth_state:
            product_category = session.auth_state.product

        async with self._pool.acquire() as conn:
            if product_category:
                # Boost matching product category results by blending scores
                rows = await conn.fetch(
                    """
                    SELECT ac.chunk_text, a.url, a.title, a.product_category,
                           1 - (ac.embedding <=> $1) AS vector_score,
                           CASE WHEN a.product_category = $2 THEN 0.05 ELSE 0.0 END AS product_boost
                    FROM article_chunks ac
                    JOIN articles a ON a.id = ac.article_id
                    ORDER BY (ac.embedding <=> $1) - (CASE WHEN a.product_category = $2 THEN 0.05 ELSE 0.0 END)
                    LIMIT 3
                    """,
                    embedding, product_category,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT ac.chunk_text, a.url, a.title, a.product_category,
                           1 - (ac.embedding <=> $1) AS vector_score,
                           0.0 AS product_boost
                    FROM article_chunks ac
                    JOIN articles a ON a.id = ac.article_id
                    ORDER BY ac.embedding <=> $1
                    LIMIT 3
                    """,
                    embedding,
                )

        results = [
            {
                "chunk_text": r["chunk_text"],
                "url": r["url"],
                "title": r["title"],
                "product_category": r["product_category"],
                "score": round(float(r["vector_score"]) + float(r["product_boost"]), 4),
            }
            for r in rows
        ]
        return ToolResult(status="ok", output={"results": results, "query": query})
