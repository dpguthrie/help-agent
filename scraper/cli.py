from __future__ import annotations
import asyncio
import json
import logging
import click
from playwright.async_api import async_playwright

from scraper.crawler import discover_sub_categories, discover_doc_pages, fetch_article_html
from scraper.parser import parse_article_page

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
def scrape(category: str, output: str, limit: int):
    """Scrape articles from a Salesforce Help product category."""
    asyncio.run(_scrape(category, output, limit))


async def _scrape(category: str, output: str, limit: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        logger.info(f"Discovering sub-categories for: {category}")
        sub_cats = await discover_sub_categories(page, category)
        logger.info(f"Found {len(sub_cats)} sub-categories")

        articles = []
        for sc in sub_cats:
            logger.info(f"Discovering docs for: {sc['name']}")
            doc_urls = await discover_doc_pages(page, sc["href"])
            logger.info(f"  Found {len(doc_urls)} articles")

            for url in doc_urls:
                if limit and len(articles) >= limit:
                    break
                logger.info(f"  Fetching: {url}")
                html = await fetch_article_html(page, url)
                article = parse_article_page(html, url)
                article["product_category"] = category
                article["product_sub_category"] = sc["name"]
                articles.append(article)

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
