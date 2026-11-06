def test_basic_accessibility(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    counts = {tag: page.locator(tag).count() for tag in ["h1", "h2", "h3"]}
    print(f"headings {counts}")
    assert sum(counts.values()) >= 1
    if counts["h1"] == 0:
        print("FINDING: 首页无 h1，SEO/可访问性建议补充")

    total = page.locator("img").count()
    missing = page.locator("img:not([alt])").count()
    print(f"images total={total} missing_alt={missing}")
    assert total > 0
    assert missing <= total * 0.8
    assert page.locator("#keyword").get_attribute("placeholder")
