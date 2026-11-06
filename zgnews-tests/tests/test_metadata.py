import json

import allure


def _find_type(obj, type_name):
    if isinstance(obj, dict):
        if obj.get("@type") == type_name:
            return obj
        for value in obj.values():
            found = _find_type(value, type_name)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_type(item, type_name)
            if found:
                return found
    return None


@allure.feature("页面与内容")
@allure.story("新闻结构化数据")
def test_news_jsonld(page, article_url):
    page.goto(article_url, wait_until="domcontentloaded", timeout=30000)
    blocks = page.locator('script[type="application/ld+json"]').all_inner_texts()
    assert blocks
    article = None
    for block in blocks:
        try:
            article = _find_type(json.loads(block), "NewsArticle")
        except json.JSONDecodeError:
            continue
        if article:
            break
    assert article, "未找到 NewsArticle JSON-LD"
    assert article.get("headline")
    assert article.get("datePublished")
    assert article.get("image", "").startswith("http")
    assert article.get("author")
    assert article.get("publisher")


@allure.feature("页面与内容")
@allure.story("Open Graph / canonical")
def test_open_graph_and_canonical(page, article_url):
    page.goto(article_url, wait_until="domcontentloaded", timeout=30000)
    metas = page.eval_on_selector_all(
        'meta[property^="og:"]',
        "els => Object.fromEntries(els.map(e => [e.getAttribute('property'), e.getAttribute('content')]))",
    )
    assert metas.get("og:type") == "article"
    assert metas.get("og:title")
    assert metas.get("og:url") == page.url
    assert metas.get("og:image", "").startswith("http")
    canonical = page.locator('link[rel="canonical"]').get_attribute("href")
    assert canonical == page.url
