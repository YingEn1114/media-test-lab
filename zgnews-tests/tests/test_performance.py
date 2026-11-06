def test_home_performance(page, base_url):
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    timing = page.evaluate("""() => {
        const nav = performance.getEntriesByType('navigation')[0];
        const res = performance.getEntriesByType('resource');
        return {
            dcl: nav ? nav.domContentLoadedEventEnd : 0,
            load: nav ? nav.loadEventEnd : 0,
            resources: res.length
        };
    }""")
    print("performance", timing)
    assert timing["dcl"] < 15000
    assert timing["resources"] > 10
