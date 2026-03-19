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


if __name__ == "__main__":
    cli()
