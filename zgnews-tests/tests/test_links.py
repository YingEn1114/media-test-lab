import requests
from bs4 import BeautifulSoup


def test_nav_and_article_links(base_url):
    resp = requests.get(base_url + "/", timeout=15)
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.select(".top-menu a[href]"):
        links.append(a["href"])
    for a in soup.select('a[href^="/news/"]')[:5]:
        links.append(a["href"])
    links = list(dict.fromkeys(links))[:8]
    assert links
    for href in links:
        url = base_url + href if href.startswith("/") else href
        r = requests.get(url, timeout=15, allow_redirects=True)
        assert r.status_code < 400, f"{url} -> {r.status_code}"
