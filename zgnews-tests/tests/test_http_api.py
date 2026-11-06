import uuid

import pytest
import requests
from bs4 import BeautifulSoup


def _home_html(base_url):
    resp = requests.get(base_url + "/", timeout=15)
    assert resp.status_code == 200
    return resp


@pytest.mark.smoke
def test_home_http_contract(base_url):
    resp = _home_html(base_url)
    assert "text/html" in resp.headers.get("content-type", "")
    assert resp.headers.get("x-content-type-options", "").lower() == "nosniff"
    assert resp.headers.get("content-encoding", "") in ("gzip", "br", "")
    assert len(resp.text) > 5000


def test_head_home(base_url):
    resp = requests.head(base_url + "/", timeout=15, allow_redirects=True)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_robots_txt(base_url):
    resp = requests.get(base_url + "/robots.txt", timeout=15)
    assert resp.status_code == 200
    assert "User-agent" in resp.text
    assert "Disallow: /admin/" in resp.text


def test_static_assets(base_url):
    soup = BeautifulSoup(_home_html(base_url).text, "html.parser")
    urls = []
    for tag, attr in (("link", "href"), ("script", "src")):
        for el in soup.select(f"{tag}[{attr}]"):
            url = el.get(attr, "")
            if url.startswith("https://static.zhengguannews.cn/") and url.endswith((".css", ".js")):
                urls.append(url)
    urls = list(dict.fromkeys(urls))[:4]
    assert urls, "未找到 static CDN 资源"
    for url in urls:
        r = requests.get(url, timeout=15)
        assert r.status_code == 200, url
        ctype = r.headers.get("content-type", "")
        assert ("text/css" in ctype) or ("javascript" in ctype), f"{url} -> {ctype}"
        assert len(r.content) > 100


def test_image_cdn(base_url):
    soup = BeautifulSoup(_home_html(base_url).text, "html.parser")
    urls = []
    for img in soup.select("img"):
        url = img.get("src") or img.get("data-src") or ""
        if url.startswith("https://media.zhengguannews.cn/"):
            urls.append(url)
    urls = list(dict.fromkeys(urls))[:3]
    assert urls, "未找到 media CDN 图片"
    for url in urls:
        r = requests.get(url, timeout=15)
        assert r.status_code == 200, url
        assert r.headers.get("content-type", "").startswith("image/"), url
        assert len(r.content) > 1000, url


def test_unknown_path_soft_404(base_url):
    url = f"{base_url}/this-path-not-exist-{uuid.uuid4().hex}.html"
    resp = requests.get(url, timeout=15, allow_redirects=True)
    if resp.status_code == 200 and "404" in resp.text:
        pytest.xfail("软 404：未知路径返回 HTTP 200，但内容为 404 页面")
    assert resp.status_code == 404


def test_sitemap_soft_404(base_url):
    resp = requests.get(base_url + "/sitemap.xml", timeout=15)
    if resp.status_code == 200 and "404" in resp.text:
        pytest.xfail("软 404：sitemap.xml 返回 HTTP 200，但内容是 404 页面")
    assert resp.status_code == 200
    assert "xml" in resp.headers.get("content-type", "")
