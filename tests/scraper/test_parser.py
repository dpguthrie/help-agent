from scraper.parser import parse_article_page


def test_parse_article_extracts_title():
    html = """
    <h1 class="article-title">Set Up Einstein Activity Capture</h1>
    <div class="article-content"><p>Steps to set up EAC.</p></div>
    <div class="see-also"><a href="/s/articleView?id=001">Related Article</a></div>
    """
    result = parse_article_page(html, "https://help.salesforce.com/s/articleView?id=123")
    assert result["title"] == "Set Up Einstein Activity Capture"
    assert "Steps to set up EAC" in result["content"]


def test_parse_article_extracts_see_also():
    html = """
    <h1>Test Article</h1>
    <div class="article-content"><p>Content here.</p></div>
    <section class="see-also">
        <a href="https://help.salesforce.com/s/articleView?id=001">Link 1</a>
        <a href="https://help.salesforce.com/s/articleView?id=002">Link 2</a>
    </section>
    """
    result = parse_article_page(html, "https://help.salesforce.com/test")
    assert len(result["related_urls"]) == 2
