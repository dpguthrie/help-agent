#!/bin/bash
# Load all scraped JSONL files into the database, then backup
# Usage: ./scripts/load_all_scraped.sh

set -e
set -a; source .env; set +a

echo "=== Merging all scraped files ==="
cat scraped_*.jsonl > /tmp/all_scraped_merged.jsonl 2>/dev/null
TOTAL=$(wc -l < /tmp/all_scraped_merged.jsonl)
echo "Total articles to load: $TOTAL"

echo ""
echo "=== Seeding users ==="
PYTHONPATH=src:. .venv/bin/python -c "
import asyncio, asyncpg
from pgvector.asyncpg import register_vector
from db.seed import seed_users
async def main():
    pool = await asyncpg.create_pool('$DATABASE_URL', init=lambda c: register_vector(c))
    await seed_users(pool)
    await pool.close()
asyncio.run(main())
"

echo ""
echo "=== Loading into database ==="
PYTHONPATH=src:. .venv/bin/python -m scraper.cli load \
  --input /tmp/all_scraped_merged.jsonl \
  --db-url "$DATABASE_URL" \
  --api-key "$BRAINTRUST_API_KEY" \
  --no-questions \
  --force

echo ""
echo "=== Database stats ==="
docker compose exec db psql -U sfdc -c "
SELECT product_category, count(*) as articles
FROM articles GROUP BY product_category ORDER BY articles DESC;
SELECT count(*) as total_articles, (SELECT count(*) FROM article_chunks) as total_chunks FROM articles;
"

echo ""
echo "=== Backing up database ==="
./scripts/db_backup.sh
