import allure
import requests


@allure.feature("首页与导航")
@allure.story("页脚与合规链接")
def test_footer_links(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    footer_text = page.locator("body").inner_text()
    for text in ["关于我们", "用户协议", "隐私政策", "版权所有", "豫ICP"]:
        assert text in footer_text
    for path in ["/about/us.html", "/about/xy.html", "/about/ys.html", "/about/copyright.html"]:
        assert page.locator(f'a[href="{path}"]').count() >= 1
        resp = requests.get(base_url + path, timeout=15)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"
