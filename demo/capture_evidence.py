# -*- coding: utf-8 -*-
"""重新采集证据包：HTTP 问题 + 页面截图 + 平台/Allure 截图。

运行（使用 zgnews-tests 的虚拟环境，内含 playwright/requests）：
    cd demo
    ../zgnews-tests/.venv/bin/python capture_evidence.py
"""

import datetime
import json
import os
import pathlib
import uuid

import requests
from playwright.sync_api import sync_playwright

BASE = os.getenv("ZG_BASE_URL", "https://www.zhengguannews.cn")
PLATFORM = os.getenv("ZG_PLATFORM", "http://127.0.0.1:8090")
RUN_ID = os.getenv("ZG_RUN_ID", "20261106-151242-c818a1")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "evidence")
SHOTS = os.path.join(OUT, "shots")
os.makedirs(SHOTS, exist_ok=True)

session = requests.Session()
session.headers["User-Agent"] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

result = {
    "capturedAt": datetime.datetime.now().isoformat(timespec="seconds"),
    "base": BASE,
    "platform": PLATFORM,
    "runId": RUN_ID,
    "issues": {},
}

# ---------- HTTP 层证据 ----------
r = session.get(f"{BASE}/search.html/%E6%AD%A3%E8%A7%82", timeout=20, allow_redirects=True)
result["issues"]["search_redirect"] = {
    "requested": f"{BASE}/search.html/正观",
    "status": r.status_code,
    "finalUrl": r.url,
    "redirects": [h.status_code for h in r.history],
    "isDownPage": "/down.html" in r.url,
    "note": "搜索 URL 302 跳转到 /down.html（客户端下载页），无搜索结果页",
}

unknown = f"/this-path-not-exist-{uuid.uuid4().hex}.html"
r2 = session.get(BASE + unknown, timeout=20, allow_redirects=True)
result["issues"]["soft_404_unknown"] = {
    "path": unknown,
    "status": r2.status_code,
    "finalUrl": r2.url,
    "bodyHas404": "404" in r2.text,
    "bodyLength": len(r2.text),
    "note": "随机不存在路径返回 HTTP 200，正文仅 22 字节 404 文案",
}

r3 = session.get(BASE + "/sitemap.xml", timeout=20)
result["issues"]["soft_404_sitemap"] = {
    "status": r3.status_code,
    "contentType": r3.headers.get("content-type", ""),
    "bodyHas404": "404" in r3.text,
    "snippet": r3.text.strip().replace("\n", " ")[:140],
    "note": "sitemap.xml 返回 HTTP 200 + text/html，正文为 404 页",
}

# ---------- 浏览器层证据 ----------
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])

    page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page.goto(f"{BASE}/search.html/%E6%AD%A3%E8%A7%82", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1200)
    result["issues"]["search_redirect"]["landedTitle"] = page.title()
    page.screenshot(path=os.path.join(SHOTS, "01-search-redirect.png"))

    page.goto(BASE + unknown, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(800)
    result["issues"]["soft_404_unknown"]["title"] = page.title()
    page.screenshot(path=os.path.join(SHOTS, "02-soft-404-unknown.png"))

    page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
    page.locator(".search-box").first.click()
    page.wait_for_timeout(400)
    keyword = "测试<>&%20" + "长" * 30
    page.locator("#keyword").fill(keyword)
    page.locator("#search").click()
    page.wait_for_timeout(1500)
    result["issues"]["search_special_chars"] = {
        "keyword": keyword,
        "landedUrl": page.url,
        "isDownPage": "/down.html" in page.url,
        "title": page.title(),
        "note": "特殊字符搜索同样 302 跳转 /down.html",
    }
    page.screenshot(path=os.path.join(SHOTS, "04-search-special-chars.png"))

    # 移动端播放器：390 视口 + 页面内标注 + 裁剪顶部 1000px
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="zh-CN"
    )
    mobile = ctx.new_page()
    mobile.goto(BASE + "/list/26.html", wait_until="domcontentloaded", timeout=30000)
    hrefs = mobile.locator('a[href^="/video/"]').evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    first = next((h for h in hrefs if h), None)
    result["issues"]["mobile_video"] = {"listUrl": BASE + "/list/26.html", "videoPath": first}
    if first:
        mobile.goto(BASE + first, wait_until="domcontentloaded", timeout=30000)
        mobile.wait_for_function(
            "() => { const v = document.querySelector('video'); return v && v.readyState >= 2; }",
            timeout=30000,
        )
        mobile.wait_for_timeout(1500)
        box = mobile.locator("video").first.bounding_box()
        metrics = mobile.evaluate(
            """() => ({
                clientWidth: document.documentElement.clientWidth,
                scrollWidth: document.documentElement.scrollWidth,
                visual: window.visualViewport ? window.visualViewport.width : null
            })"""
        )
        scroll_width = metrics["scrollWidth"]
        mobile.evaluate(
            """([vw, sw]) => {
                const shade = document.createElement('div');
                shade.style.cssText = `position:fixed;left:${vw}px;top:0;width:${sw - vw}px;height:1000px;`
                    + 'background:rgba(217,95,67,.14);border-left:3px solid #d95f43;'
                    + 'z-index:2147483647;pointer-events:none;';
                document.documentElement.appendChild(shade);
                const label = document.createElement('div');
                label.textContent = '视口边界 390px';
                label.style.cssText = 'position:fixed;left:8px;top:8px;background:#1b222a;color:#fffdf8;'
                    + 'font:600 20px -apple-system,PingFang SC;padding:8px 14px;border-radius:4px;'
                    + 'z-index:2147483647;';
                document.documentElement.appendChild(label);
            }""",
            [390, scroll_width],
        )
        raw = os.path.join(SHOTS, "_mobile-raw.png")
        mobile.screenshot(path=raw, full_page=True)
        final = os.path.join(SHOTS, "05-mobile-video-overflow.png")
        wrap = os.path.join(SHOTS, "_annotate.html")
        with open(wrap, "w", encoding="utf-8") as f:
            f.write(
                "<html><body style='margin:0;position:relative'>"
                f"<img src='{os.path.basename(raw)}' style='display:block;width:{scroll_width}px;height:auto'>"
                f"<div style='position:absolute;left:390px;top:0;width:{scroll_width - 390}px;height:1000px;"
                "background:rgba(217,95,67,.16);border-left:3px solid #d95f43;box-sizing:border-box'></div>"
                "<div style='position:absolute;left:8px;top:8px;background:#1b222a;color:#fffdf8;"
                "font:600 20px -apple-system,PingFang SC;padding:8px 14px;border-radius:4px'>视口边界 390px</div>"
                "</body></html>"
            )
        shot = browser.new_page(viewport={"width": scroll_width, "height": 1000})
        shot.goto(pathlib.Path(wrap).as_uri())
        shot.wait_for_timeout(600)
        shot.screenshot(path=final)
        shot.close()
        os.remove(raw)
        os.remove(wrap)
        result["issues"]["mobile_video"].update(
            {
                "viewportWidth": 390,
                "clientWidth": metrics["clientWidth"],
                "visualViewportWidth": metrics["visual"],
                "videoWidth": round(box["width"]) if box else None,
                "videoHeight": round(box["height"]) if box else None,
                "scrollWidth": scroll_width,
                "overflow": bool(box and box["width"] > 390),
                "note": "390×844 移动端上下文：video 固定 1240px，页面横向滚动宽度 1412px",
            }
        )
    ctx.close()

    # ---------- 平台与报告 ----------
    view = browser.new_page(viewport={"width": 1600, "height": 1000}, locale="zh-CN")
    view.goto(PLATFORM + "/", wait_until="networkidle")
    view.wait_for_function(
        "() => document.getElementById('kpiRate').textContent.includes('%')", timeout=15000
    )
    view.screenshot(path=os.path.join(SHOTS, "10-platform-dashboard.png"), full_page=True)

    view.goto(PLATFORM + "/reports", wait_until="networkidle")
    view.wait_for_timeout(800)
    view.screenshot(path=os.path.join(SHOTS, "11-platform-reports.png"), full_page=True)

    view.goto(f"{PLATFORM}/reports/allure-{RUN_ID}/index.html", wait_until="networkidle")
    view.wait_for_timeout(2500)
    view.screenshot(path=os.path.join(SHOTS, "12-allure-overview.png"))

    view.close()
    browser.close()

with open(os.path.join(OUT, "measurements.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(json.dumps(result["issues"], ensure_ascii=False, indent=1))
print("saved to", OUT)
