import re

import allure


@allure.feature("页面与内容")
@allure.story("正观早参专题页")
def test_special_calendar(page, special_url):
    resp = page.goto(special_url, wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    assert "正观早参" in page.title()
    assert page.locator(".calendar").count() >= 1
    title = page.locator(".calendar-title").first.inner_text()
    assert re.search(r"20\d{2}", title), f"日历标题未包含年份: {title}"
    assert "星期" in page.locator("body").inner_text()
