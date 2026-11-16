"""All state, code, asset commits and HTTP targets are isolated under tmp_path."""
import json
import os
import socket
import sqlite3
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests
import uvicorn
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

import app
from qa_center.codegen import render, validate
from qa_center.evidence import inspect
from qa_center.review import ARRAYS, WEIGHTS
from qa_center.service import Center
from qa_center.store import Problem, Store, uid
from qa_center.web import install

ROOT = Path(__file__).resolve().parent.parent


def junit(nodes, outcome="passed"):
    suite = ET.Element("testsuite", tests=str(len(nodes)), errors="0")
    for node in nodes:
        parts = node.split("::")
        tc = ET.SubElement(suite, "testcase", classname=parts[0][:-3].replace("/", "."),
                           name=parts[-1], time="0.01")
        if outcome == "failed":
            ET.SubElement(tc, "failure", message="expected failure")
        elif outcome in ("xfailed", "skipped"):
            ET.SubElement(tc, "skipped", type="pytest.xfail" if outcome == "xfailed" else "pytest.skip")
    return ET.tostring(suite, encoding="unicode")


class AI:
    def __init__(self):
        self.score = 90
        self.blocking = False
        self.invalid = False
        self.spec = {"name": "本地首页", "desc": "可达性", "goal": "访问首页",
                     "preconditions": "本地HTTP可用", "steps": ["请求首页"], "expected": ["200"],
                     "test_type": "http", "smoke": True, "automation": True,
                     "implementation": "固定模板", "risk": "只验证可达性",
                     "priority": "P1", "area": "本地域", "tags": ["smoke"],
                     "check": {"kind": "home_reachable", "params": {}}}

    def __call__(self, messages):
        payload = json.loads(messages[-1]["content"])
        if "candidate" not in payload:
            return {"cases": [self.spec]}
        c = payload["candidate"]
        verdict = {"candidate_id": c["id"] if not self.invalid else "unknown",
                   "candidate_version": c["version"], "code_hash": c["code_hash"],
                   "decision": "pass", "overall_score": 100,
                   "dimensions": {k: self.score for k in WEIGHTS}, "summary": "依据验收标准和HTTP检查规格",
                   **{k: [] for k in ARRAYS}}
        if self.blocking:
            verdict["blocking_issues"] = [{"code": "GAP", "location": "check", "reason": "覆盖缺口",
                                          "suggestion": "补充验收断言"}]
        return {"requirement_id": payload["requirement"]["id"], "reviewed_cases": [verdict]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ZG_ADMIN_TOKEN", "isolated-admin-token")
    monkeypatch.delenv("ZG_ASSET_REPO", raising=False)
    for key in ("ZG_AI_KEY", "ZG_AI_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / "code"
    root.mkdir()
    manual = {"tests/test_manual.py::test_manual": {"name": "人工", "priority": "P1",
              "area": "人工域", "tags": ["smoke"]}}
    (root / "cases.json").write_text(json.dumps(manual))
    ai, outcomes = AI(), ["passed"]

    def runner(nodes, run_id, manifest=None):
        outcome = outcomes[0]
        return {"status": "failed" if outcome == "failed" else "passed",
                "returncode": 1 if outcome == "failed" else 0, "junit": junit(nodes, outcome)}

    center = Center(tmp_path / "data.db", root, runner, background=False, ai=ai)
    admin = center.store.actor("isolated-admin-token")
    return center, admin, ai, outcomes


def call(env, kind, action="create", data=None, oid=None, actor=None):
    center, admin, _, _ = env
    return center.dispatch(actor or admin, kind, oid, action, data or {})


def requirement(env):
    return call(env, "requirements", data={"title": "本地需求", "description": "测试首页",
                                         "acceptance": "首页HTTP为200", "owner": "QA"})


def draft(env):
    req = requirement(env)
    call(env, "drafts", "generate", {"requirement_id": req["id"]})
    return env[0].snapshot(env[1], "drafts")[0]


def publish(env):
    d = draft(env)
    sync = call(env, "drafts", "sync", {"confirm": True}, d["id"])
    assert sync["commit"] and sync["status"] == "synced"
    review = call(env, "drafts", "review", oid=d["id"])
    assert review["accepted"] and review["verdict"]["overall_score"] == 90
    return d, call(env, "drafts", "publish", {"confirm": True}, d["id"])


def user(env, name, role):
    u = call(env, "users", data={"name": name, "role": role, "email": f"{name}@local"})
    return env[0].store.actor(u["token"]), u["token"]


def test_requirement_crud_and_metadata(env):
    req = requirement(env)
    assert req["version"] == 1
    req = call(env, "requirements", "update", {"title": "更名", "version": 1}, req["id"])
    assert req["version"] == 2
    with pytest.raises(Problem):
        call(env, "requirements", "update", {"version": 1}, req["id"])
    assert call(env, "requirements", "delete", oid=req["id"])["status"] == "deleted"
    d = draft(env)
    for key in ("goal", "preconditions", "steps", "expected", "test_type", "smoke",
                "automation", "implementation", "risk"):
        assert d["spec"][key] == env[2].spec[key]


@pytest.mark.parametrize("score,blocking,accepted", [(79, False, False), (80, False, True), (95, True, False)])
def test_review_rejection_and_weighted_score(env, score, blocking, accepted):
    d = draft(env)
    env[2].score, env[2].blocking = score, blocking
    r = call(env, "drafts", "review", oid=d["id"])
    assert r["accepted"] is accepted
    assert r["verdict"]["overall_score"] == score  # ignore model's invented 100
    if not accepted:
        with pytest.raises(Problem):
            call(env, "drafts", "publish", {"confirm": True}, d["id"])
        assert len(env[0].snapshot(env[1], "cases")) == 1


@pytest.mark.parametrize("field,empty", [
    ("goal", ""), ("preconditions", ""), ("test_type", ""),
    ("implementation", ""), ("steps", []), ("expected", []),
])
def test_publication_requires_complete_design_even_if_model_passes(env, field, empty):
    d = draft(env)
    modified = {**d["spec"], field: empty}
    if field == "expected":
        modified["expected_results"] = []
    d = call(env, "drafts", "update", {"version": d["version"], "spec": modified}, d["id"])
    call(env, "drafts", "sync", {"confirm": True}, d["id"])
    assert call(env, "drafts", "review", oid=d["id"])["accepted"]
    with pytest.raises(Problem) as exc:
        call(env, "drafts", "publish", {"confirm": True}, d["id"])
    assert exc.value.status == 400
    assert not any(c.get("draft_id") == d["id"] for c in env[0].snapshot(env[1], "cases"))


def test_asset_configuration_cannot_target_user_working_repository(tmp_path, monkeypatch):
    root = tmp_path / "working"
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    before = (root / ".git" / "HEAD").read_text()
    monkeypatch.setenv("ZG_ASSET_REPO", str(root / ".git"))
    with pytest.raises(Problem, match="bare"):
        Center(tmp_path / "blocked.db", root, lambda *a, **kw: {})
    assert (root / ".git" / "HEAD").read_text() == before


def test_ai_timeout_is_configurable_without_network(monkeypatch):
    import ai_client
    import requests
    seen = {}

    def post(url, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"choices": [{"message": {"content": '{"ok":true}'}}]})

    monkeypatch.setenv("ZG_AI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("ZG_AI_TIMEOUT", "12.5")
    monkeypatch.setattr(requests, "post", post)
    assert ai_client._chat([]) == {"ok": True}
    assert seen["timeout"] == 12.5
    monkeypatch.setenv("ZG_AI_TIMEOUT", "301")
    with pytest.raises(ValueError, match="ZG_AI_TIMEOUT"):
        ai_client._chat([])


def test_prompt_rollback_preserves_history_and_monotonic_versions(env):
    original = next(p for p in env[0].snapshot(env[1], "prompts") if p["category"] == "review")
    second = call(env, "prompts", data={"category": "review", "text": "review v2"})
    assert second["version"] == 2
    call(env, "prompts", "activate", oid=original["id"])
    third = call(env, "prompts", data={"category": "review", "text": "review v3"})
    versions = [p for p in env[0].snapshot(env[1], "prompts") if p["category"] == "review"]
    assert sorted(p["version"] for p in versions) == [1, 2, 3]
    assert [p["id"] for p in versions if p["active"]] == [third["id"]]


@pytest.mark.parametrize("role", ["test_lead", "tech_lead", "project_lead"])
def test_lead_roles_are_read_only(env, role):
    actor, _ = user(env, role, role)
    assert isinstance(env[0].snapshot(actor, "cases"), list)
    with pytest.raises(Problem) as exc:
        call(env, "requirements", data={"title": "越权", "acceptance": "不应创建"}, actor=actor)
    assert exc.value.status == 403
    with pytest.raises(Problem):
        env[0].snapshot(actor, "settings")


def test_review_response_identity_core_dimension_and_duplicate(env):
    d = draft(env)
    env[2].invalid = True
    with pytest.raises(Problem, match="不匹配"):
        call(env, "drafts", "review", oid=d["id"])
    env[2].invalid = False
    base = env[0].ai
    def low_core(messages):
        out = base(messages)
        out["reviewed_cases"][0]["dimensions"]["step_completeness"] = 69
        return out
    env[0].ai = low_core
    assert not call(env, "drafts", "review", oid=d["id"])["accepted"]
    env[0].ai = base
    call(env, "drafts", "generate", {"requirement_id": d["requirement_id"]})
    assert not call(env, "drafts", "review", oid=d["id"])["accepted"]


def test_publish_idempotency_staleness_and_code_tampering(env):
    d, c = publish(env)
    same = call(env, "drafts", "publish", {"confirm": True}, d["id"])
    assert same["id"] == c["id"]
    assert len(env[0].snapshot(env[1], "cases")) == 2
    updated = call(env, "drafts", "update", {"version": 1, "spec": {**d["spec"], "name": "改名"}}, d["id"])
    with pytest.raises(Problem):
        call(env, "drafts", "publish", {"confirm": True}, d["id"])
    with pytest.raises(Problem, match="变化"):
        call(env, "runs", data={"scope": "full"})
    assert updated["version"] == 2
    path = env[0].root / updated["code_path"]
    path.write_text(path.read_text() + "\n# local modification\n")
    with pytest.raises(Problem, match="hash"):
        call(env, "drafts", "review", oid=d["id"])


def test_sync_isolated_repo_preserves_user_index_and_cases(env):
    center = env[0]
    root = center.root
    original = (root / "cases.json").read_bytes()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    (root / "user.txt").write_text("user staged content")
    subprocess.run(["git", "add", "user.txt"], cwd=root, check=True)
    before = (root / ".git/index").read_bytes()
    d = draft(env)
    record = call(env, "drafts", "sync", {"confirm": True}, d["id"])
    again = call(env, "drafts", "sync", {"confirm": True}, d["id"])
    assert record["commit"] == again["commit"]
    assert (root / ".git/index").read_bytes() == before
    assert (root / "cases.json").read_bytes() == original
    tree = center.git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert tree == [d["code_path"]]


@pytest.mark.parametrize("outcome,strict,passed", [
    ("passed", True, True), ("xfailed", False, True), ("xfailed", True, False),
    ("skipped", False, False), ("failed", False, False)])
def test_junit_semantics(outcome, strict, passed):
    nodes = ["tests/test_a.py::test_one"]
    result = inspect({"junit": junit(nodes, outcome), "returncode": 1 if outcome == "failed" else 0},
                     nodes, strict=strict)
    assert (result["status"] == "passed") is passed
    assert result["counts"][outcome] == 1


@pytest.mark.parametrize("change", ["missing", "malformed", "duplicate", "extra", "cancelled", "collection"])
def test_junit_incomplete_never_passes(change):
    nodes = ["tests/test_a.py::test_one"]
    result = {"junit": junit(nodes), "returncode": 0}
    if change == "missing": result["junit"] = ""
    elif change == "malformed": result["junit"] = "<!"
    elif change == "duplicate": result["junit"] = junit(nodes * 2)
    elif change == "extra": result["junit"] = junit(nodes + ["tests/test_a.py::test_two"])
    elif change == "cancelled": result["status"] = "cancelled"
    else: result["returncode"] = 2
    assert inspect(result, nodes)["status"] != "passed"


def test_full_selection_and_evidence_failure_report(env):
    publish(env)
    run = call(env, "runs", data={"scope": "full"})
    assert len(run["selection"]) == 2 and run["evidence"]["complete"]
    env[0].runner = lambda *a, **k: {"returncode": 1}
    broken = call(env, "runs", data={"scope": "full"})
    assert broken["status"] == "failed" and not broken["evidence"]["complete"]
    report = call(env, "reports", data={"run_id": broken["id"]})
    assert report["verdict"] == "risk"
    selected = call(env, "runs", data={"scope": "selected", "ids": [run["selection"][0]["id"]]})
    with pytest.raises(Problem):
        call(env, "reports", data={"run_id": selected["id"]})


def defect_setup(env):
    rd, _ = user(env, "rd", "rd")
    qa, _ = user(env, "qa", "qa")
    call(env, "settings", "update", {"routing": {"default": rd["id"]},
                                   "qa": ["qa@local"], "leaders": ["lead@local"]})
    env[3][0] = "failed"
    call(env, "runs", data={"scope": "full"})
    defect = env[0].snapshot(env[1], "defects")[0]
    return rd, qa, defect


def test_role_transitions_rd_and_qa_true_regressions(env):
    rd, qa, d = defect_setup(env)
    with pytest.raises(Problem):
        call(env, "defects", "verify", oid=d["id"], actor=qa)
    call(env, "defects", "claim", oid=d["id"], actor=rd)
    with pytest.raises(Problem):
        call(env, "defects", "fix", {"note": "no proof"}, d["id"], rd)
    env[3][0] = "xfailed"
    failed = call(env, "defects", "fix", {"note": "fix", "commit": "abcdef123"}, d["id"], rd)
    assert failed["status"] == "fix_failed"
    env[3][0] = "passed"
    fixed = call(env, "defects", "fix", {"note": "fix", "commit": "abcdef123"}, d["id"], rd)
    assert fixed["status"] == "pending_qa"
    with pytest.raises(Problem):
        call(env, "defects", "close", oid=d["id"], actor=qa)
    env[3][0] = "failed"
    assert call(env, "defects", "verify", oid=d["id"], actor=qa)["status"] == "reopened"
    call(env, "defects", "claim", oid=d["id"], actor=rd)
    env[3][0] = "passed"
    call(env, "defects", "fix", {"note": "fix again", "pr": "https://local/pr/1"}, d["id"], rd)
    assert call(env, "defects", "verify", oid=d["id"], actor=qa)["status"] == "fixed"
    assert call(env, "defects", "close", oid=d["id"], actor=qa)["status"] == "closed"


def test_rd_visibility_and_cancel_ownership(env):
    rd, qa, d = defect_setup(env)
    stranger, _ = user(env, "stranger", "rd")
    assert env[0].snapshot(stranger, "defects") == []
    assert len(env[0].snapshot(rd, "cases")) == 1
    requirement(env)
    assert env[0].snapshot(rd, "requirements") == []
    for collection in ("drafts", "reviews", "sync", "prompts", "settings", "history"):
        with pytest.raises(Problem) as e:
            env[0].snapshot(rd, collection)
        assert e.value.status == 403
    with pytest.raises(Problem):
        call(env, "defects", "claim", oid=d["id"], actor=stranger)
    with env[0].store.tx() as conn:
        run, _ = env[0].reserve(conn, qa, {"scope": "full"})
    with pytest.raises(Problem) as e:
        call(env, "runs", "cancel", oid=run["id"], actor=rd)
    assert e.value.status == 403
    with pytest.raises(Problem):
        call(env, "runs", data={"scope": "full"}, actor=rd)


def test_atomic_slot_concurrency_and_crash_recovery(env):
    center, admin, _, _ = env
    def reserve():
        try:
            with center.store.tx() as conn:
                return center.reserve(conn, admin, {"scope": "full"})[0]["id"]
        except Problem:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: reserve(), range(2)))
    assert sum(x is not None for x in attempts) == 1
    with pytest.raises(Problem, match="存活"):
        call(env, "runs", "recover", {"reason": "test"})
    with center.store.tx() as conn:
        conn.execute("UPDATE qa_runner_slot SET pid=99999999")
    center.recover_dead()
    recovered = center.snapshot(admin, "runs")[0]
    assert recovered["status"] == "aborted"
    assert any(a["action"] == "runs.recovered" for a in center.snapshot(admin, "audit"))
    assert call(env, "runs", data={"scope": "full"})["status"] == "passed"


def test_report_recipients_notifications_edit_preview_and_stale_run(env):
    rd, qa, d = defect_setup(env)
    mails = env[0].snapshot(env[1], "outbox")
    assert mails and mails[0]["to"] == ["rd@local"]
    assert mails[0]["transport"] == "outbox"
    run = env[0].snapshot(env[1], "runs")[0]
    report = call(env, "reports", data={"run_id": run["id"]})
    assert report["verdict"] == "risk" and report["risks"]
    mail = call(env, "outbox", data={"report_id": report["id"]})
    assert mail["to"] == ["qa@local"] and mail["cc"] == ["lead@local"]
    mail = call(env, "outbox", "update", {"body": "自定义说明", "to": ["other@local"], "cc": []}, mail["id"])
    raw = env[0].eml(env[1], mail["id"])
    assert b"other@local" in raw
    from email import policy
    from email.parser import BytesParser
    content = BytesParser(policy=policy.default).parsebytes(raw).get_content()
    assert "自定义说明" in content and d["id"] in content and "risk" in content
    with pytest.raises(Problem):
        call(env, "outbox", "update", {"to": ["bad\r\nBcc:hacker"]}, mail["id"])
    assert call(env, "outbox", "send", oid=mail["id"])["status"] == "queued-local"
    old = call(env, "outbox", data={"report_id": report["id"]})
    env[3][0] = "passed"
    call(env, "runs", data={"scope": "full"})
    with pytest.raises(Problem, match="更新"):
        call(env, "outbox", "send", oid=old["id"])


def test_migration_backup_idempotency_and_original_38_metadata(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE runs(id TEXT PRIMARY KEY, started REAL,status TEXT)")
        conn.execute("INSERT INTO runs VALUES('old',1,'failed')")
    Store(path)
    Store(path)
    assert Path(str(path) + ".pre-qa-v1.bak").exists()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT status FROM runs").fetchone()[0] == "failed"
        assert len(conn.execute("SELECT * FROM qa_schema_migrations").fetchall()) >= 3
    assert len(app.CENTER.snapshot(app.CENTER.store.actor(
        os.getenv("ZG_ADMIN_TOKEN") or Path(app.DB_PATH + ".admin-token").read_text()), "cases")) >= 38


def test_no_ai_configuration_and_demo_not_auto_approved(env):
    center = env[0]
    center.ai = __import__("ai_client")._chat
    req = requirement(env)
    with pytest.raises(Problem, match="未配置"):
        call(env, "drafts", "generate", {"requirement_id": req["id"]})
    generated = call(env, "drafts", "generate", {"requirement_id": req["id"], "demo": True})
    assert generated["source"] == "demo-local-rules"
    d = center.snapshot(env[1], "drafts")[0]
    with pytest.raises(Problem, match="未配置"):
        call(env, "drafts", "review", oid=d["id"])


def test_fixed_template_injection_and_actual_local_http(env):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"local fixture")
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        spec = validate({**env[2].spec, "name": '"""\nraise RuntimeError("injected")\n#',
                         "desc": "';__import__('os').system('false')"})
        code = render(spec)
        assert "injected" not in code
        file = env[0].root / "test_fixed.py"; file.write_text(code)
        result = subprocess.run([sys.executable, "-m", "pytest", str(file), "-q", "--confcutdir",
                                 str(env[0].root)], cwd=env[0].root, capture_output=True, text=True,
                                env={**os.environ, "ZG_BASE_URL": f"http://127.0.0.1:{server.server_port}"},
                                timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=3)


def test_local_api_auth_basic_separation_and_templates(env):
    # Start only an ephemeral localhost API; no use of user's running services.
    mini = FastAPI()
    mini.middleware("http")(app.basic_auth)
    templates = Jinja2Templates(directory=str(ROOT / "web/templates"))
    install(mini, env[0], templates, app._ctx)
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(mini, log_level="error", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    old = app.AUTH; app.AUTH = "legacy:password"
    thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(0.01)
        base = f"http://127.0.0.1:{port}"
        assert requests.get(base + "/api/qa/me", timeout=5).status_code == 401
        headers = {"Authorization": "Bearer isolated-admin-token"}
        assert requests.get(base + "/api/qa/me", headers=headers, timeout=5).status_code == 200
        assert requests.post(base + "/api/pipeline/start", json={}, timeout=5).status_code == 410
        forged = requests.post(base + "/api/qa/requirements", json={"role": "admin"}, timeout=5)
        assert forged.status_code == 401
        for route in ("/requirements", "/factory", "/prompts", "/outbox", "/history"):
            response = requests.get(base+route, auth=("legacy","password"), timeout=5)
            assert response.status_code == 200 and 'id="qa-center"' in response.text
    finally:
        app.AUTH = old; server.should_exit = True; thread.join(timeout=5); sock.close()


def test_frontend_javascript_syntax():
    import playwright
    node = shutil.which("node") or str(Path(playwright.__file__).parent / "driver" / "node")
    result = subprocess.run([node, "--check", str(ROOT / "web/assets/center.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_browser_navigation_and_requirement_form_at_390_and_desktop(env):
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import sync_playwright, expect

    mini = FastAPI()
    templates = Jinja2Templates(directory=str(ROOT / "web/templates"))
    install(mini, env[0], templates, app._ctx)
    mini.mount("/assets", StaticFiles(directory=str(ROOT / "web/assets")))
    mini.mount("/vendor", StaticFiles(directory=str(ROOT / "web/vendor")))
    sections = {"/": "overview", "/cases": "cases", "/runs": "runs",
                "/reports": "reports", "/defects": "defects", "/settings": "settings",
                "/pipeline": "factory"}
    def page(request: app.Request):
        return templates.TemplateResponse(request=request, name="center.html",
            context={**app._ctx(request, sections[request.url.path]),
                     "section": sections[request.url.path]})
    for path in sections:
        mini.add_api_route(path, page, methods=["GET"])
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(mini, log_level="error", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.01)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context()
            context.add_init_script("sessionStorage.setItem('qa-token','isolated-admin-token')")
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            base = f"http://127.0.0.1:{port}"
            routes = ["/", "/requirements", "/factory", "/prompts", "/cases", "/runs",
                      "/defects", "/reports", "/outbox", "/settings", "/history", "/pipeline"]
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 844})
                for route in routes:
                    response = page.goto(base+route)
                    assert response.status == 200
                    expect(page.locator("#identity")).to_contain_text("本机管理员")
                    expect(page.locator("#listing")).not_to_have_attribute("aria-busy", "true")
                    assert not page.locator(".qa-error").count(), page.locator("#notice").inner_text()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), route
            page.goto(base+"/requirements")
            page.get_by_role("button", name="新建需求", exact=True).click()
            page.locator('[name="title"]').fill("浏览器验收需求")
            page.locator('[name="acceptance"]').fill("本地假HTTP返回200")
            page.get_by_role("button", name="保存需求", exact=True).click()
            expect(page.locator("#listing")).to_contain_text("浏览器验收需求")
            page.get_by_role("button", name="浏览器验收需求", exact=False).click()
            page.get_by_role("button", name="演示生成", exact=True).click()
            expect(page).to_have_url(base+"/factory")
            expect(page.locator("#listing")).to_contain_text("首页")
            page.locator("#rows button").first.click()
            expect(page.locator("#draft-form")).to_be_visible()
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
