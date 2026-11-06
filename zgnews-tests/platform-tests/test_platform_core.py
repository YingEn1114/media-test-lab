import asyncio
import base64
import json
import sqlite3
import time
from types import SimpleNamespace

from fastapi import Response

import app


def test_init_db_idempotent():
    app.init_db()
    app.init_db()
    conn = sqlite3.connect(app.DB_PATH)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "runs" in tables


def test_select_case_ids():
    cases = [
        {"id": "a", "tags": ["smoke", "ui"]},
        {"id": "b", "tags": ["ui"]},
        {"id": "c", "tags": []},
    ]
    assert app.select_case_ids(cases, tags=["smoke"]) == ["a"]
    assert app.select_case_ids(cases, tags=["ui"]) == ["a", "b"]
    assert app.select_case_ids(cases, tags=["nope"]) == []
    assert app.select_case_ids(cases, ids=["b", "missing"]) == ["b"]
    assert app.select_case_ids(cases) == ["a", "b", "c"]


def test_counts():
    log = "33 passed, 5 xfailed in 154.1s"
    assert app._counts(log) == {"passed": 33, "failed": 0, "skipped": 0, "xfailed": 5}
    assert app._counts("") == {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0}
    assert app._counts("1 failed, 2 passed, 1 skipped")["failed"] == 1


def test_reconcile_stale_running():
    conn = sqlite3.connect(app.DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO runs (id,started,status,nodeids,log) VALUES (?,?,?,?,?)",
        ("unit-stale", time.time(), "running", "[]", ""),
    )
    conn.commit()
    conn.close()

    n = app.reconcile_runs()
    assert n >= 1

    conn = sqlite3.connect(app.DB_PATH)
    row = conn.execute(
        "SELECT status, finished FROM runs WHERE id='unit-stale'"
    ).fetchone()
    conn.close()
    assert row[0] == "aborted"
    assert row[1] is not None


def test_save_run_and_history():
    app._save_run(
        "unit-passed",
        time.time() - 2,
        "passed",
        ["tests/test_home.py::test_homepage"],
        "/reports/unit.html",
        "1 passed in 1.0s",
        {"passed": 1},
        None,
        0,
    )
    rows = app.api_history(limit=20)
    row = next(r for r in rows if r["id"] == "unit-passed")
    assert row["count"] == 1
    assert row["passed"] == 1
    assert row["rate"] == 100
    assert row["returncode"] == 0


def test_health_ok():
    resp = app.api_health()
    body = json.loads(resp.body)
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["checks"]["db"] is True
    assert body["checks"]["reports"] is True


def test_security_headers():
    async def call_next(request):
        return Response("ok", status_code=200)

    resp = asyncio.run(app.security_headers(None, call_next))
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "same-origin"
    assert "permissions-policy" in resp.headers


def test_basic_auth():
    old = app.AUTH
    app.AUTH = "qa:secret"

    async def call_next(request):
        return Response("ok", status_code=200)

    try:
        missing = asyncio.run(app.basic_auth(SimpleNamespace(headers={}), call_next))
        assert missing.status_code == 401
        assert "Basic" in missing.headers["www-authenticate"]

        token = base64.b64encode(b"qa:secret").decode()
        ok = asyncio.run(
            app.basic_auth(SimpleNamespace(headers={"authorization": f"Basic {token}"}), call_next)
        )
        assert ok.status_code == 200
    finally:
        app.AUTH = old
