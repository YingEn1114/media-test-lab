import os
import hashlib
import json
from pathlib import Path

import pytest
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("ZG_BASE_URL", "https://www.zhengguannews.cn")
CHANNEL = os.getenv("ZG_CHANNEL", "chrome")
HEADLESS = os.getenv("ZG_HEADLESS", "1").lower() not in ("0", "false", "no")
SLOWMO = int(os.getenv("ZG_SLOWMO", "0"))


def _generated_allowed(path):
    try:
        manifest = json.loads(os.getenv("ZG_QA_GENERATED_MANIFEST", "{}"))
        return manifest.get(str(path.resolve())) == hashlib.sha256(path.read_bytes()).hexdigest()
    except (ValueError, OSError):
        return False


def pytest_ignore_collect(collection_path, config):
    generated = Path(__file__).resolve().parent / "tests" / "generated"
    if collection_path == generated:
        return not bool(os.getenv("ZG_QA_GENERATED_MANIFEST"))
    if generated in collection_path.parents and collection_path.is_file() and collection_path.suffix == ".py":
        return not _generated_allowed(collection_path)


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(module_path, parent):
    generated = Path(__file__).resolve().parent / "tests" / "generated"
    if generated in module_path.parents and not _generated_allowed(module_path):
        raise pytest.UsageError("generated资产未绑定已发布评审及代码hash，禁止收集")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def home_soup(base_url):
    """首页 DOM，供用例发现文章/频道/专题入口，避免硬编码可能失效的 ID。"""
    resp = requests.get(base_url + "/", timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


@pytest.fixture(scope="session")
def article_url(base_url, home_soup):
    link = home_soup.select_one('a[href^="/news/"]')
    assert link is not None, "首页未找到新闻链接"
    return base_url + link["href"]


@pytest.fixture(scope="session")
def zhengzhou_url(base_url, home_soup):
    for link in home_soup.select(".top-menu a[href]"):
        if "郑州" in link.get_text():
            return base_url + link["href"]
    return base_url + "/list/16.html"


@pytest.fixture(scope="session")
def special_url(base_url, home_soup):
    for link in home_soup.select('a[href^="/special/"]'):
        if "早参" in link.get_text():
            return base_url + link["href"]
    return base_url + "/special/2708.html"


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance):
    browser = playwright_instance.chromium.launch(
        channel=CHANNEL, headless=HEADLESS, slow_mo=SLOWMO, args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"]
    )
    yield browser
    browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(
        viewport={"width": 1440, "height": 900}, locale="zh-CN"
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def mobile_page(browser):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        locale="zh-CN",
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        page = item.funcargs.get("page") or item.funcargs.get("mobile_page")
        if page:
            path = os.path.join("screenshots", f"fail-{item.name}.png")
            try:
                page.screenshot(path=path, full_page=False)
            except Exception:
                pass
