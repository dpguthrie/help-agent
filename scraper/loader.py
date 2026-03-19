from __future__ import annotations
import json
import asyncio
import asyncpg
from pgvector.asyncpg import register_vector
from scraper.chunker import chunk_text
from scraper.embedder import Embedder
from scraper.question_gen import QuestionGenerator


async def load_articles(
    db_url: str,
    articles_file: str,
    embedder: Embedder,
    question_gen: QuestionGenerator | None = None,
    force: bool = False,
) -> None:
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5, init=lambda c: register_vector(c))

    with open(articles_file) as f:
        articles = [json.loads(line) for line in f]

    for article in articles:
        async with pool.acquire() as conn:
            existing = await conn.fetchval("SELECT id FROM articles WHERE url = $1", article["url"])
            if existing and not force:
                continue

            art_id = await conn.fetchval(
                """
                INSERT INTO articles (url, title, content, product_category, product_sub_category, related_urls, scraped_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
                ON CONFLICT (url) DO UPDATE SET content = $3, scraped_at = now()
                RETURNING id
                """,
                article["url"], article["title"], article["content"],
                article.get("product_category"), article.get("product_sub_category"),
                json.dumps(article.get("related_urls", [])),
            )

            await conn.execute("DELETE FROM article_chunks WHERE article_id = $1", art_id)

        chunks = chunk_text(article["content"])
        if chunks:
            embeddings = embedder.embed_batch(chunks)
            async with pool.acquire() as conn:
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    import numpy as np
                    emb_arr = np.array(embedding, dtype=np.float32)
                    await conn.execute(
                        "INSERT INTO article_chunks (article_id, chunk_index, chunk_text, embedding) VALUES ($1, $2, $3, $4)",
                        art_id, i, chunk, emb_arr,
                    )

        if question_gen and article.get("content"):
            questions = question_gen.generate(article.get("title", ""), article["content"])
            async with pool.acquire() as conn:
                for q in questions:
                    await conn.execute(
                        "INSERT INTO questions (article_id, question_text) VALUES ($1, $2)",
                        art_id, q,
                    )

    await pool.close()
