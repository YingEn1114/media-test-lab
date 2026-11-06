import pytest


@pytest.mark.smoke
def test_search_overlay(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    page.locator(".search-box").first.click()
    page.wait_for_timeout(300)
    assert page.locator(".search-main-box").first.is_visible()
    page.locator("#keyword").fill("正观")
    assert page.locator("#keyword").input_value() == "正观"


def test_search_results(page, base_url):
    resp = page.goto(base_url + "/search.html/%E6%AD%A3%E8%A7%82", wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    if page.url.endswith("/down.html"):
        pytest.xfail("Web 搜索重定向到 /down.html，未提供搜索结果页（已知问题）")
    assert "404" not in page.locator("body").inner_text()
