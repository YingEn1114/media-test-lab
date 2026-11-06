import requests


def test_security_headers(base_url):
    resp = requests.get(base_url + "/", timeout=15)
    assert resp.status_code == 200
    if base_url.startswith("https://"):
        assert resp.url.startswith("https://")
    headers = resp.headers
    assert headers.get("x-content-type-options", "").lower() == "nosniff"
    assert "x-frame-options" in headers
    assert "x-xss-protection" in headers
    for cookie in resp.cookies:
        print(f"cookie {cookie.name}: secure={cookie.secure}")
