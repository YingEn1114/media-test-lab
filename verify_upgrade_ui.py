"""只读浏览器检查：遍历平台导航，在桌面和移动视口检查页面错误与水平溢出。

使用 zgnews-tests/.venv/bin/python 执行。不会启动测试、改缺陷或发送邮件。
需要登录时由操作者先提供 storage_state 文件（不应提交 Git）。
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


def verify(base_url, output, storage_state=None, token_file=None):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        for width, height in ((1440, 1000), (390, 844)):
            options = {"viewport": {"width": width, "height": height}}
            if storage_state:
                options["storage_state"] = storage_state
            context = browser.new_context(**options)
            page = context.new_page()
            page.goto(base_url, wait_until="networkidle")
            if token_file:
                page.locator("#token").fill(token_file.read_text().strip())
                page.locator("#login button").first.click()
                page.wait_for_timeout(700)
            links = page.locator("nav a[href]").evaluate_all(
                "els => els.map(el => ({label: el.textContent.trim(), href: el.getAttribute('href')}))"
            )
            if not links:
                raise AssertionError("没有发现导航入口，可能需要先登录")
            origin = urlparse(base_url).netloc
            seen = set()
            for link in links:
                target = urljoin(base_url, link["href"])
                if urlparse(target).netloc != origin or target in seen:
                    continue
                seen.add(target)
                errors = []
                def capture_error(exc):
                    errors.append(str(exc))
                page.on("pageerror", capture_error)
                response = page.goto(target, wait_until="networkidle")
                page.wait_for_timeout(250)
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth > window.innerWidth + 1"
                )
                headings = page.locator("h1").all_text_contents()
                identity = (
                    page.locator("#identity").inner_text()
                    if page.locator("#identity").count() else None
                )
                load_failed = (
                    "加载失败" in page.locator("#workspace").inner_text()
                    if page.locator("#workspace").count() else False
                )
                name = urlparse(target).path.strip("/").replace("/", "-") or "dashboard"
                page.screenshot(
                    path=str(output / f"{width}-{name}.png"), full_page=True
                )
                record = {
                    "viewport": width,
                    "label": link["label"],
                    "url": page.url,
                    "status": response.status if response else None,
                    "headings": headings,
                    "horizontal_overflow": overflow,
                    "page_errors": list(errors),
                    "identity": identity,
                    "load_failed": load_failed,
                }
                records.append(record)
                page.remove_listener("pageerror", capture_error)
            context.close()
        browser.close()
    (output / "results.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failures = [
        r for r in records
        if r["status"] != 200 or not r["headings"]
        or r["horizontal_overflow"] or r["page_errors"] or r["load_failed"]
        or (token_file and not r["identity"])
    ]
    print(json.dumps({
        "checked": len(records), "failures": failures, "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8090/")
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).parent / "zgnews-tests/reports/upgrade-ui",
    )
    parser.add_argument("--storage-state")
    parser.add_argument("--token-file", type=Path)
    args = parser.parse_args()
    raise SystemExit(verify(
        args.base_url, args.output, args.storage_state, args.token_file
    ))
