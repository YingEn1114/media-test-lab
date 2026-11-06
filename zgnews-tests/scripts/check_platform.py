#!/usr/bin/env python3
"""平台巡检：健康检查、关键接口、页面与安全头。

用法：
    .venv/bin/python scripts/check_platform.py
    ZG_PLATFORM=http://172.26.73.50:8090 .venv/bin/python scripts/check_platform.py
"""

import os
import sys

import requests

BASE = os.getenv("ZG_PLATFORM", "http://127.0.0.1:8090").rstrip("/")
TIMEOUT = 10


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
    return ok


def main():
    results = []

    try:
        health = requests.get(f"{BASE}/api/health", timeout=TIMEOUT)
        body = health.json()
        results.append(check("health", health.status_code == 200 and body.get("status") == "ok", str(body)))
    except Exception as exc:
        results.append(check("health", False, str(exc)))

    try:
        meta = requests.get(f"{BASE}/api/meta", timeout=TIMEOUT).json()
        results.append(check("meta", bool(meta.get("version")), f"v{meta.get('version')}"))
    except Exception as exc:
        results.append(check("meta", False, str(exc)))

    try:
        cases = requests.get(f"{BASE}/api/cases", timeout=TIMEOUT).json().get("cases", [])
        results.append(check("cases", len(cases) > 0, f"{len(cases)} 条"))
    except Exception as exc:
        results.append(check("cases", False, str(exc)))

    try:
        defects = requests.get(f"{BASE}/api/defects", timeout=TIMEOUT).json()
        results.append(check("defects", defects.get("counts", {}).get("total", 0) > 0, str(defects.get("counts"))))
    except Exception as exc:
        results.append(check("defects", False, str(exc)))

    for path in ("/", "/cases", "/runs", "/reports", "/defects", "/settings"):
        try:
            resp = requests.get(BASE + path, timeout=TIMEOUT)
            results.append(check(f"page {path}", resp.status_code == 200, str(resp.status_code)))
        except Exception as exc:
            results.append(check(f"page {path}", False, str(exc)))

    try:
        resp = requests.get(BASE + "/", timeout=TIMEOUT)
        results.append(check("header nosniff", resp.headers.get("x-content-type-options") == "nosniff",
                             resp.headers.get("x-content-type-options", "")))
        results.append(check("header frame", resp.headers.get("x-frame-options") == "DENY",
                             resp.headers.get("x-frame-options", "")))
    except Exception as exc:
        results.append(check("security headers", False, str(exc)))

    ok = all(results)
    print(f"\n{'OK' if ok else 'FAILED'}  {BASE}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
