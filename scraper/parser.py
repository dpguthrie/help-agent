from __future__ import annotations
import re


def parse_article_page(html: str, url: str) -> dict:
    title = ""
    content = ""
    related_urls = []

    title_patterns = [
        r'<h1[^>]*class="[^"]*article-title[^"]*"[^>]*>(.*?)</h1>',
        r'<h1[^>]*>(.*?)</h1>',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            break

    content_patterns = [
        r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*slds-rich-text-editor__output[^"]*"[^>]*>(.*?)</div>',
        r'<article[^>]*>(.*?)</article>',
    ]
    for pattern in content_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            raw = match.group(1)
            content = re.sub(r'<[^>]+>', ' ', raw)
            content = re.sub(r'\s+', ' ', content).strip()
            break

    if not content:
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
        if body_match:
            content = re.sub(r'<[^>]+>', ' ', body_match.group(1))
            content = re.sub(r'\s+', ' ', content).strip()

    see_also_match = re.search(r'(?:see.also|SEE\s+ALSO)(.*?)(?:</section>|</div>|$)', html, re.DOTALL | re.IGNORECASE)
    if see_also_match:
        links = re.findall(r'href="([^"]*(?:articleView|help\.salesforce\.com)[^"]*)"', see_also_match.group(1))
        related_urls = links

    return {
        "url": url,
        "title": title,
        "content": content,
        "related_urls": related_urls,
    }
