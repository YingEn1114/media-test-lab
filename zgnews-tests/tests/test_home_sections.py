import allure


@allure.feature("首页与导航")
@allure.story("首页视频与专题栏目")
def test_home_sections(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    assert page.locator(".video-center").count() >= 1
    assert page.locator(".video-swiper .swiper-slide").count() >= 3
    assert page.locator('a[href^="/video/"]').count() >= 3
    assert page.locator('a[href^="/special/"]').count() >= 3
