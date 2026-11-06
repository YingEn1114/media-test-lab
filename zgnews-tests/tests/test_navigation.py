from urllib.parse import urlparse
import pytest


@pytest.mark.smoke
def test_navigate_to_zhengzhou(page, base_url, zhengzhou_url):
    path = urlparse(zhengzhou_url).path
    page.goto(base_url + "/", wait_until="domcontentloaded", timeout=30000)
    page.locator(f'.top-menu a[href="{path}"]').first.click()
    page.wait_for_load_state("domcontentloaded")
    assert path in page.url
    assert "郑州" in page.title()
