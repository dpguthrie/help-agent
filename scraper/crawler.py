from __future__ import annotations
import asyncio
import logging
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

BASE_URL = "https://help.salesforce.com"
CRAWL_DELAY = 2.0


async def discover_sub_categories(page: Page, category: str) -> list[dict]:
    url = f"{BASE_URL}/s/products/{category}"
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(CRAWL_DELAY)

    links = await page.eval_on_selector_all(
        "a[href*='/s/products/']",
        "els => els.map(el => ({name: el.textContent.trim(), href: el.href}))"
    )
    return [l for l in links if l["href"] != url and l["name"]]


async def discover_doc_pages(page: Page, sub_category_url: str) -> list[str]:
    await page.goto(sub_category_url, wait_until="networkidle")
    await asyncio.sleep(CRAWL_DELAY)

    links = await page.eval_on_selector_all(
        "a[href*='articleView']",
        "els => els.map(el => el.href)"
    )
    return list(set(links))


async def fetch_article_html(page: Page, url: str) -> str:
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(CRAWL_DELAY)
    return await page.content()
