"""Only validated data is interpolated using repr; user text is never Python source."""
import json
from urllib.parse import urlsplit

from .store import require


KINDS = {"home_reachable": (), "title_contains": ("text",),
         "keyword_present": ("keyword",), "path_status": ("path", "expect"),
         "element_present": ("selector", "min"), "search_no_redirect": ("query",),
         "player_ready": (), "player_play": (), "player_pause": (), "player_seek": ("seconds",),
         "player_volume": ("level",), "player_fullscreen": (), "player_quality": ("label",),
         "player_rate": ("rate",), "media_range": (), "viewport_overflow": ("width", "height")}


def validate(spec):
    require(isinstance(spec, dict), "用例必须是对象", 400)
    require(isinstance(spec.get("name"), str) and 0 < len(spec["name"]) <= 240, "用例名称必填且不超过240字", 400)
    require(spec.get("priority", "P1") in ("P0", "P1", "P2", "P3"), "优先级无效", 400)
    require(isinstance(spec.get("tags", []), list) and
            all(isinstance(x, str) for x in spec.get("tags", [])), "tags 必须为字符串数组", 400)
    if spec.get("automation") is False:
        return {**spec, "desc": str(spec.get("desc", "")), "priority": spec.get("priority", "P1"),
                "area": str(spec.get("area", "未分类")), "tags": spec.get("tags", []),
                "check": {"kind": "manual", "params": {}}}
    check = spec.get("check", {})
    require(isinstance(check, dict), "check 必须是对象", 400)
    kind, params = check.get("kind"), check.get("params", {})
    require(kind in KINDS and isinstance(params, dict), "不支持的检查类型", 400)
    require(all(k in params for k in KINDS[kind]), "检查参数不完整", 400)
    for key in KINDS[kind]:
        value = params[key]
        if key in ("expect", "min", "width", "height"):
            limit = {"expect": (100, 599), "min": (1, 10000), "width": (320, 3840), "height": (480, 2400)}[key]
            require(type(value) is int and limit[0] <= value <= limit[1], "数值检查参数无效", 400)
        elif key in ("seconds", "level", "rate"):
            require(isinstance(value, (int, float)) and not isinstance(value, bool), "播放器数值参数无效", 400)
            limits = {"seconds": (0, 36000), "level": (0, 1), "rate": (0.25, 4)}[key]
            require(limits[0] <= float(value) <= limits[1], "播放器数值超出允许范围", 400)
        else:
            require(isinstance(value, str) and 0 < len(value) <= 2000, "文本检查参数无效", 400)
    if kind == "path_status":
        path = params["path"]
        require(path.startswith("/") and not path.startswith("//") and
                not urlsplit(path).netloc and "\\" not in path, "仅允许站内绝对路径", 400)
    result = {**spec, "name": spec["name"], "desc": str(spec.get("desc", "")),
            "priority": spec.get("priority", "P1"), "area": str(spec.get("area", "未分类")),
            "tags": spec.get("tags", []), "check": {"kind": kind, "params": params}}
    for key in ("goal", "preconditions", "steps", "expected_results", "test_type", "target", "test_data", "cleanup"):
        result[key] = spec.get(key, [] if key in ("steps", "expected_results") else "")
    return result


def fingerprint(spec):
    return json.dumps(spec["check"], sort_keys=True, ensure_ascii=False)


def render(spec):
    # Name and description remain database data. The sole literal is safely quoted JSON.
    payload = repr(json.dumps(spec["check"], ensure_ascii=True))
    return '''# QA fixed template v1; metadata is stored in SQLite.
import json
import os
import re
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CHECK = json.loads(''' + payload + ''')

def test_generated():
    base = os.environ["ZG_BASE_URL"].rstrip("/")
    kind, p = CHECK["kind"], CHECK["params"]
    if kind.startswith(("player_", "media_range", "viewport_overflow")):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel=os.getenv("ZG_CHANNEL", "chrome"), headless=os.getenv("ZG_HEADLESS", "1") != "0")
            page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="zh-CN")
            _run(page, base, kind, p)
            browser.close()
        return
    _run(None, base, kind, p)


def _run(page, base, kind, p):
    path = p["path"] if kind == "path_status" else (
        "/search.html/" + quote(p["query"], safe="") if kind == "search_no_redirect" else "/")
    response = requests.get(base + path, timeout=20, allow_redirects=False)
    if kind == "home_reachable":
        assert response.status_code == 200
    elif kind == "title_contains":
        title = re.search(r"<title>(.*?)</title>", response.text, re.S)
        assert title and p["text"] in title.group(1)
    elif kind == "keyword_present":
        assert p["keyword"] in response.text
    elif kind == "path_status":
        assert response.status_code == p["expect"]
    elif kind == "element_present":
        assert len(BeautifulSoup(response.text, "html.parser").select(p["selector"])) >= p["min"]
    elif kind == "search_no_redirect":
        assert response.status_code == 200
    elif kind == "player_ready":
        _player(page, base)
    elif kind == "player_play":
        _player(page, base).evaluate("async v => { v.muted = true; await v.play(); }")
    elif kind == "player_pause":
        _player(page, base).evaluate("v => v.pause()")
    elif kind == "player_seek":
        _player(page, base).evaluate("(v, s) => { v.currentTime = s }", p["seconds"])
    elif kind == "player_volume":
        _player(page, base).evaluate("(v, n) => { v.muted = true; v.volume = n }", p["level"])
    elif kind == "player_fullscreen":
        assert page.locator(".prism-fullscreen-btn").count() >= 1
    elif kind == "player_quality":
        assert p["label"] in page.locator(".prism-player").inner_text()
    elif kind == "player_rate":
        _player(page, base).evaluate("(v, n) => { v.playbackRate = n }", p["rate"])
    elif kind == "media_range":
        media = _player(page, base).get_attribute("src")
        assert media
        assert requests.head("https:" + media if media.startswith("//") else media, timeout=20).status_code == 200
    elif kind == "viewport_overflow":
        page.set_viewport_size({"width": p["width"], "height": p["height"]})
        _player(page, base)
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    else:
        raise AssertionError("Unsupported check")


def _player(page, base):
    page.goto(base + "/list/26.html", wait_until="domcontentloaded", timeout=30000)
    href = page.locator("a[href^='/video/']").first.get_attribute("href")
    page.goto(base + href, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function("() => { const v=document.querySelector('video'); return v && v.readyState >= 2 }", timeout=30000)
    return page.locator("video").first
'''
