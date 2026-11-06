def test_home_seo(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    desc = page.locator('meta[name="description"]').first.get_attribute("content")
    assert desc and len(desc) > 10
    assert page.locator('link[rel="canonical"]').count() >= 1


def test_article_seo(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    href = page.locator('a[href^="/news/"]').first.get_attribute("href")
    page.goto(base_url + href, wait_until="domcontentloaded", timeout=30000)
    assert "正观新闻" in page.title()
    desc = page.locator('meta[name="description"]').first.get_attribute("content")
    assert desc and len(desc) > 10
