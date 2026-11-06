import pytest
@pytest.mark.smoke
def test_homepage(page, base_url):
    resp = page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    assert "正观新闻" in page.title()
    assert page.locator(".top-menu .nav-link").count() >= 10
    assert page.locator('a[href^="/news/"]').count() >= 10
    assert page.locator("#keyword").count() == 1
    page.screenshot(path="screenshots/home.png", full_page=False)
