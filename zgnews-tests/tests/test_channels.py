import allure
import requests
from bs4 import BeautifulSoup


@allure.feature("首页与导航")
@allure.story("全部频道可用性")
def test_all_channels(base_url):
    home = requests.get(base_url + "/", timeout=15)
    assert home.status_code == 200
    soup = BeautifulSoup(home.text, "html.parser")
    links = {}
    for a in soup.select(".top-menu a[href]"):
        href = a.get("href")
        if href and href.startswith("/"):
            links[a.get_text(strip=True)] = href
    assert len(links) >= 10
    failures = []
    for name, href in links.items():
        r = requests.get(base_url + href, timeout=15)
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            failures.append((name, href, r.status_code))
    assert not failures, failures
