import allure


@allure.feature("首页与导航")
@allure.story("登录弹层")
def test_login_modal(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    page.locator("#login").first.click()
    page.wait_for_timeout(500)
    assert page.get_by_text("短信验证登录").first.is_visible()
    assert page.get_by_text("账户密码登录").first.is_visible()
    assert page.locator("input").count() >= 2
    assert page.get_by_text("获取验证码").first.is_visible()
