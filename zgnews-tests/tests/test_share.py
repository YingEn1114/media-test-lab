import allure


@allure.feature("页面与内容")
@allure.story("文章分享组件")
def test_article_share_component(page, article_url):
    page.goto(article_url, wait_until="domcontentloaded", timeout=30000)
    assert page.locator(".social-share").count() >= 1
    icons = page.locator(".social-share-icon").count()
    assert icons >= 3
    classes = page.locator(".social-share-icon").evaluate_all("els => els.map(e => e.className)")
    joined = " ".join(classes)
    assert "wechat" in joined
    assert "weibo" in joined
    assert "分享至" in page.locator("body").inner_text()
