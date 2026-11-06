import pytest
@pytest.mark.smoke
def test_list_page(page, zhengzhou_url):
    resp = page.goto(zhengzhou_url, wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    assert "郑州" in page.title()
    assert page.locator('a[href^="/news/"]').count() >= 5
    page.screenshot(path="screenshots/list.png", full_page=False)
