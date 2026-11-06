import pytest
@pytest.mark.smoke
def test_article_detail(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    href = page.locator('a[href^="/news/"]').first.get_attribute("href")
    assert href and href.startswith("/news/")
    resp = page.goto(base_url + href, wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    assert "正观新闻" in page.title()
    content = page.locator(".post-content").first
    assert content.count() >= 1
    text = content.inner_text()
    assert len(text) > 30
    assert page.locator("h1, h2").count() >= 1
    page.screenshot(path="screenshots/article.png", full_page=False)
