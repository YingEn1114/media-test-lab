import allure


@allure.feature("页面与内容")
@allure.story("客户端下载页")
def test_download_page(page, base_url):
    resp = page.goto(base_url + "/down.html", wait_until="networkidle", timeout=30000)
    assert resp and resp.status == 200
    assert "客户端下载" in page.title()
    assert page.locator('a[href*="sj.qq.com"]').count() >= 1
