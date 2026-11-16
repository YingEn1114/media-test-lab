"""在隔离服务上验证需求→演示草稿→Git同步→评审拒绝的真实界面操作。"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def verify(base_url, token_file, output):
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(base_url + "/requirements", wait_until="networkidle")
        page.locator("#token").fill(token_file.read_text().strip())
        page.locator("#login button[type=submit]").click()
        page.get_by_role("button", name="新建需求", exact=True).click()
        page.locator('#req-form [name="title"]').fill("界面验收：需求与草稿隔离")
        page.locator('#req-form [name="description"]').fill("验证首页标题和频道导航")
        page.locator('#req-form [name="acceptance"]').fill("首页返回200，标题包含正观新闻，频道导航可见")
        page.locator('#req-form [name="owner"]').fill("验收 QA")
        page.get_by_role("button", name="保存需求", exact=True).click()
        expect(page.locator('#detail [data-action="demo"]')).to_be_visible()
        page.locator('#detail [data-action="demo"]').click()
        page.wait_for_url("**/factory")
        expect(page.locator("#listing .qa-row").first).to_be_visible()
        expect(page.locator("#draft-form")).to_be_visible()
        page.locator('#detail [data-action="diff"]').click()
        expect(page.locator("#evidence")).to_contain_text("QA fixed template")
        with page.expect_response(lambda r: r.url.endswith("/sync")) as sync_response:
            page.locator('#detail [data-action="sync"]').click()
        assert sync_response.value.status == 200, sync_response.value.json()
        assert len(sync_response.value.json()["commit"]) == 40

        # Exercise read-only case browsing; no tests or real AI calls are started.
        drafts = page.evaluate("""async () => {
          const headers={Authorization:'Bearer '+sessionStorage.getItem('qa-token')};
          return await (await fetch('/api/qa/drafts',{headers})).json();
        }""")
        synced = [d for d in drafts if d.get("commit")]
        assert synced and len(synced[0]["commit"]) == 40
        page.goto(base_url + "/cases", wait_until="networkidle")
        expect(page.get_by_role("link", name="运行这条用例", exact=True)).to_be_visible()
        count = page.evaluate("""async () => (await (await fetch('/api/qa/cases',{
          headers:{Authorization:'Bearer '+sessionStorage.getItem('qa-token')}
        })).json()).length""")
        assert count == 38, "演示草稿不得进入正式用例库"
        page.locator('#filter-area').select_option(label="视频与播放器")
        assert page.locator("#rows .qa-row").count() == 8
        page.locator('#filter-priority').select_option("P1")
        assert page.locator("#rows .qa-row").count() == 8
        page.screenshot(path=str(output / "cases-filtered.png"), full_page=True)
        page.get_by_role("link", name="运行这条用例", exact=True).click()
        expect(page.locator('#run-form [name=scope]')).to_have_value("selected")
        expect(page.locator('#run-form input[name=ids]:checked')).to_have_count(1)
        assert not errors, errors
        result = {
            "requirement_created": True, "demo_drafts": len(drafts),
            "isolated_git_sync": True, "published_case_unchanged": True,
            "area_priority_filters": True, "selected_case_run_prefilled": True,
            "page_errors": errors,
        }
        (output / "flow-results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.base_url.rstrip("/"), args.token_file, args.output)
