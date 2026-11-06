def test_mobile_home(mobile_page, base_url):
    resp = mobile_page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    assert "正观新闻" in mobile_page.title()
    assert mobile_page.locator('meta[name="viewport"]').count() >= 1
    assert mobile_page.locator(".top-menu").count() >= 1
    mobile_page.screenshot(path="screenshots/mobile-home.png", full_page=False)
