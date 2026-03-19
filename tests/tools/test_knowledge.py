import pytest
from unittest.mock import AsyncMock, patch
import numpy as np
from tools.knowledge import SearchKnowledgeTool


@pytest.fixture
async def knowledge_tool(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM article_chunks")
        await conn.execute("DELETE FROM articles")
        art_id = await conn.fetchval(
            "INSERT INTO articles (url, title, content, product_category) VALUES ($1, $2, $3, $4) RETURNING id",
            "https://help.salesforce.com/test-article", "How to reset password",
            "To reset your Salesforce password, go to Settings > Password Reset.", "platform",
        )
        embedding = np.array([0.1] * 1536, dtype=np.float32)
        await conn.execute(
            "INSERT INTO article_chunks (article_id, chunk_index, chunk_text, embedding) VALUES ($1, $2, $3, $4)",
            art_id, 0, "To reset your Salesforce password, go to Settings > Password Reset.", embedding,
        )
    return SearchKnowledgeTool(pool=db_pool, gateway_base_url="https://gateway.braintrust.dev", api_key="test")


@pytest.mark.asyncio
async def test_search_knowledge_returns_results(knowledge_tool):
    mock_embedding = np.array([0.1] * 1536, dtype=np.float32)
    with patch.object(knowledge_tool, "_embed_query", new_callable=AsyncMock, return_value=mock_embedding):
        result = await knowledge_tool.execute({"query": "how to reset password"}, session=None)
    assert result.status == "ok"
    assert len(result.output["results"]) >= 1
    assert "password" in result.output["results"][0]["chunk_text"].lower()


@pytest.mark.asyncio
async def test_search_knowledge_returns_metadata(knowledge_tool):
    mock_embedding = np.array([0.1] * 1536, dtype=np.float32)
    with patch.object(knowledge_tool, "_embed_query", new_callable=AsyncMock, return_value=mock_embedding):
        result = await knowledge_tool.execute({"query": "password"}, session=None)
    assert result.status == "ok"
    r = result.output["results"][0]
    assert "url" in r
    assert "title" in r
    assert "score" in r
