from __future__ import annotations
import asyncio
import json
import logging
import click
from playwright.async_api import async_playwright

from scraper.crawler import discover_doc_sections, discover_toc_articles, extract_article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Salesforce Help article scraper."""
    pass


@cli.command()
@click.option("--category", required=True, help="Product category to scrape (e.g., 'platform', 'sales')")
@click.option("--output", default="scraped_articles.jsonl", help="Output JSONL file path")
@click.option("--limit", default=0, type=int, help="Max articles to scrape (0 = unlimited)")
@click.option("--section-limit", default=0, type=int, help="Max doc sections to crawl (0 = all)")
def scrape(category: str, output: str, limit: int, section_limit: int):
    """Scrape articles from a Salesforce Help product category."""
    asyncio.run(_scrape(category, output, limit, section_limit))


async def _scrape(category: str, output: str, limit: int, section_limit: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Step 1: Discover top-level doc sections for the category
        sections = await discover_doc_sections(page, category)
        logger.info(f"Found {len(sections)} doc sections for '{category}'")
        for s in sections[:10]:
            logger.info(f"  - {s['text']}")

        if section_limit:
            sections = sections[:section_limit]

        # Step 2: For each section, discover all articles in its TOC tree
        all_article_urls = {}  # url -> section_name for dedup
        for section in sections:
            toc_articles = await discover_toc_articles(page, section["href"])
            logger.info(f"  {section['text']}: {len(toc_articles)} articles in TOC")
            for art in toc_articles:
                if art["href"] not in all_article_urls:
                    all_article_urls[art["href"]] = section["text"]

        logger.info(f"Total unique article URLs discovered: {len(all_article_urls)}")

        if limit:
            urls_to_scrape = list(all_article_urls.items())[:limit]
        else:
            urls_to_scrape = list(all_article_urls.items())

        # Step 3: Extract content from each article
        articles = []
        for i, (url, section_name) in enumerate(urls_to_scrape):
            logger.info(f"  [{i+1}/{len(urls_to_scrape)}] Fetching: {url[:80]}...")
            try:
                article = await extract_article(page, url)
                article["product_category"] = category
                article["product_sub_category"] = section_name
                if article["content"]:  # Skip empty articles
                    articles.append(article)
                else:
                    logger.warning(f"  Skipped (empty content): {url}")
            except Exception as e:
                logger.error(f"  Error fetching {url}: {e}")

        await browser.close()

    with open(output, "w") as f:
        for article in articles:
            f.write(json.dumps(article) + "\n")
    logger.info(f"Wrote {len(articles)} articles to {output}")


@cli.command()
@click.option("--input", "input_file", required=True, help="JSONL file from scrape command")
@click.option("--db-url", envvar="DATABASE_URL", required=True, help="Postgres connection string")
@click.option("--api-key", envvar="BRAINTRUST_API_KEY", required=True, help="Braintrust API key")
@click.option("--gateway-url", default="https://gateway.braintrust.dev", help="Gateway base URL")
@click.option("--generate-questions/--no-questions", default=True, help="Generate questions per article")
@click.option("--force", is_flag=True, help="Re-process articles already in the database")
def load(input_file: str, db_url: str, api_key: str, gateway_url: str, generate_questions: bool, force: bool):
    """Load scraped articles into Postgres with embeddings."""
    from scraper.embedder import Embedder
    from scraper.question_gen import QuestionGenerator
    from scraper.loader import load_articles

    embedder = Embedder(gateway_base_url=gateway_url, api_key=api_key)
    qgen = QuestionGenerator(gateway_base_url=gateway_url, api_key=api_key) if generate_questions else None
    asyncio.run(load_articles(db_url, input_file, embedder, qgen, force=force))
    logger.info("Load complete.")


if __name__ == "__main__":
    cli()
