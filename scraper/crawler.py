from __future__ import annotations
import asyncio
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

BASE_URL = "https://help.salesforce.com"
CRAWL_DELAY = 2.0


async def discover_doc_sections(page: Page, category: str) -> list[dict]:
    """Navigate to a product category page and find top-level doc section links."""
    url = f"{BASE_URL}/s/products/{category}"
    logger.info(f"Discovering doc sections at: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(CRAWL_DELAY)

    links = await page.eval_on_selector_all(
        "a[href*='articleView']",
        """els => els.map(el => ({
            text: el.textContent.trim(),
            href: el.href
        })).filter(l => l.text.length > 2
            && l.href.includes('language=en_US')
            && !l.href.includes('nocache')
            && !l.text.includes('Refresh'))"""
    )
    # Deduplicate by href
    seen = set()
    unique = []
    for l in links:
        if l["href"] not in seen:
            seen.add(l["href"])
            unique.append(l)
    return unique


async def discover_toc_articles(page: Page, section_url: str) -> list[dict]:
    """Navigate to a doc section and extract all article links from the TOC sidebar."""
    logger.info(f"Discovering TOC articles at: {section_url}")
    await page.goto(section_url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(CRAWL_DELAY)

    links = await page.eval_on_selector_all(
        "a[href*='articleView']",
        """els => els.map(el => ({
            text: el.textContent.trim(),
            href: el.href
        })).filter(l => l.text.length > 2
            && l.href.includes('language=en_US')
            && !l.href.includes('nocache')
            && !l.text.includes('Refresh')
            && !l.text.includes('Back'))"""
    )
    seen = set()
    unique = []
    for l in links:
        if l["href"] not in seen:
            seen.add(l["href"])
            unique.append(l)
    return unique


async def extract_article(page: Page, url: str) -> dict:
    """Navigate to an article page and extract title, content, and related links using innerText."""
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(CRAWL_DELAY)

    result = await page.evaluate("""() => {
        // Title: grab from the page title (more reliable than h1 which may be hidden)
        let title = document.title || '';
        // Also try h1
        const h1 = document.querySelector('h1');
        if (h1 && h1.innerText.trim()) {
            title = h1.innerText.trim();
        }

        const bodyText = document.body.innerText;

        // Extract content after the "You are here:" breadcrumb
        let content = '';
        const youAreHere = bodyText.lastIndexOf('You are here:');
        if (youAreHere >= 0) {
            let afterBreadcrumb = bodyText.substring(youAreHere + 'You are here:'.length).trim();
            // Skip the breadcrumb path lines (SALESFORCE HELP / DOCS / SECTION)
            // Find where the title appears after the breadcrumb
            const titleIdx = afterBreadcrumb.indexOf(title);
            if (titleIdx >= 0) {
                content = afterBreadcrumb.substring(titleIdx + title.length).trim();
            } else {
                content = afterBreadcrumb;
            }
        } else if (title) {
            // Fallback: find content after the last occurrence of the title
            const lastTitle = bodyText.lastIndexOf(title);
            if (lastTitle >= 0) {
                content = bodyText.substring(lastTitle + title.length).trim();
            }
        }

        // Clean up: remove common footer/nav noise at the end
        const footerMarkers = [
            'DID THIS ARTICLE SOLVE YOUR ISSUE?',
            'Was this helpful?',
            'Still need help?',
        ];
        for (const marker of footerMarkers) {
            const idx = content.indexOf(marker);
            if (idx > 100) {  // Only trim if there's real content before the marker
                content = content.substring(0, idx).trim();
            }
        }

        // Extract see-also links
        const relatedUrls = [];
        const seeAlsoIdx = content.indexOf('SEE ALSO');
        if (seeAlsoIdx >= 0) {
            const afterSeeAlso = content.substring(seeAlsoIdx);
            const seeAlsoLinks = document.querySelectorAll('a[href*="articleView"]');
            // We'll capture these from the DOM instead
        }

        const allArticleLinks = Array.from(document.querySelectorAll('a[href*="articleView"]'))
            .map(a => a.href)
            .filter(href => href.includes('language=en_US'));

        return {
            title: title,
            content: content,
            related_urls: [...new Set(allArticleLinks)].slice(0, 20),
        };
    }""")

    return {
        "url": url,
        "title": result.get("title", ""),
        "content": result.get("content", ""),
        "related_urls": result.get("related_urls", []),
    }
