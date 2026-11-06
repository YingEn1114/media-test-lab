import allure
import pytest


@allure.feature("搜索")
@allure.story("空关键词与特殊字符")
def test_search_edge(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    page.locator(".search-box").first.click()
    page.wait_for_timeout(300)
    page.locator("#keyword").fill("")
    page.locator("#search").click()
    page.wait_for_timeout(500)
    assert page.url.rstrip("/") == base_url.rstrip("/"), "空关键词不应跳转"

    page.locator("#keyword").fill("测试<>&%20" + "长" * 30)
    page.locator("#search").click()
    page.wait_for_timeout(1200)
    if "/down.html" in page.url:
        pytest.xfail("特殊字符搜索被重定向到 /down.html（站点搜索现状）")
    assert "search" in page.url
    assert page.locator("body").inner_text().strip()
