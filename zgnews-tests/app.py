import base64
import glob
import json
import os
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(ROOT, "reports")
DB_PATH = os.getenv("ZG_DB", os.path.join(ROOT, "platform.db"))
META_PATH = os.path.join(ROOT, "cases.json")
DEFECTS_PATH = os.path.join(ROOT, "defects.json")
# 缺陷卡片与证据包共用一份截图目录（demo/evidence），存在时才挂载
EVIDENCE_DIR = os.path.join(os.path.dirname(ROOT), "demo", "evidence")
# 可选访问控制：ZG_AUTH=user:password 时启用 HTTP Basic Auth；默认关闭
AUTH = os.getenv("ZG_AUTH", "")
os.makedirs(REPORT_DIR, exist_ok=True)

app = FastAPI(title="正观新闻 Python 测试平台")
app.mount("/reports", StaticFiles(directory=REPORT_DIR), name="reports")
app.mount("/assets", StaticFiles(directory=os.path.join(ROOT, "web", "assets")), name="assets")
app.mount("/vendor", StaticFiles(directory=os.path.join(ROOT, "web", "vendor")), name="vendor")
if os.path.isdir(EVIDENCE_DIR):
    app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")
templates = Jinja2Templates(directory=os.path.join(ROOT, "web", "templates"))


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not AUTH:
        return await call_next(request)
    header = request.headers.get("authorization", "")
    ok = False
    if header.startswith("Basic "):
        try:
            raw = base64.b64decode(header[6:]).decode("utf-8")
            user, _, pwd = raw.partition(":")
            exp_user, _, exp_pwd = AUTH.partition(":")
            ok = secrets.compare_digest(user, exp_user) and secrets.compare_digest(pwd, exp_pwd)
        except Exception:
            ok = False
    if not ok:
        return Response(
            status_code=401,
            content="需要登录：请使用管理员提供的账号密码",
            headers={"WWW-Authenticate": 'Basic realm="ZG QA"'},
        )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

TOOLS = os.path.join(ROOT, ".tools")
ALLURE_BIN = next(iter(glob.glob(os.path.join(TOOLS, "allure-*", "bin", "allure"))), None)
JRE_HOME = next(iter(glob.glob(os.path.join(TOOLS, "jdk-*", "Contents", "Home"))), None)

_CACHE = {"ts": 0.0, "cases": []}
LOCK = threading.Lock()
PROC = None
CANCEL = {"flag": False}
STATE = {
    "status": "idle", "log": "", "report": None, "runId": None,
    "started": None, "finished": None, "returncode": None, "nodeids": [],
    "allure": None,
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            started REAL NOT NULL,
            finished REAL,
            status TEXT NOT NULL,
            nodeids TEXT NOT NULL,
            report TEXT,
            log TEXT
        )"""
    )
    for col in ("passed", "failed", "skipped", "xfailed"):
        try:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    for col, ctype in (("allure", "TEXT"), ("returncode", "INTEGER")):
        try:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {ctype}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


init_db()


def reconcile_runs():
    """服务重启后，把上一次残留的 running 记录标记为 aborted，避免历史永久悬挂。"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "UPDATE runs SET status='aborted', finished=? WHERE status='running'",
        (time.time(),),
    )
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n


RECONCILED = reconcile_runs()
if RECONCILED:
    print(f"[startup] reconciled {RECONCILED} stale running run(s)", flush=True)


def discover_cases(force=False):
    now = time.time()
    if not force and _CACHE["cases"] and now - _CACHE["ts"] < 30:
        return _CACHE["cases"]

    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            meta = json.load(f)

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        # 收集超时时退回上一次缓存，避免整个用例页 500
        return _CACHE["cases"]
    cases = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("tests/") or "::" not in line:
            continue
        file, rest = line.split("::", 1)
        info = meta.get(line, {})
        cases.append({
            "id": line,
            "file": file,
            "func": rest,
            "name": info.get("name") or rest,
            "desc": info.get("desc", ""),
            "priority": info.get("priority", "P2"),
            "tags": info.get("tags", []),
            "area": info.get("area") or file.split("/")[-1].replace("test_", "").replace(".py", ""),
        })
    cases.sort(key=lambda c: (c["file"], c["id"]))
    _CACHE.update(ts=now, cases=cases)
    return cases


def _counts(log):
    out = {}
    for key in ("passed", "failed", "skipped", "xfailed"):
        m = re.search(rf"(\d+) {key}", log or "")
        out[key] = int(m.group(1)) if m else 0
    return out


def _save_run(run_id, started, status, nodeids, report=None, log="", counts=None, allure=None, returncode=None):
    counts = counts or {}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO runs
        (id,started,finished,status,nodeids,report,log,passed,failed,skipped,xfailed,allure,returncode)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, started, time.time() if status != "running" else None,
         status, json.dumps(nodeids, ensure_ascii=False), report, log[-300000:],
         counts.get("passed", 0), counts.get("failed", 0),
         counts.get("skipped", 0), counts.get("xfailed", 0), allure, returncode),
    )
    conn.commit()
    conn.close()


def _runner(nodeids, run_id, headed=False, slowmo=0):
    report_name = f"report-{run_id}.html"
    report_path = os.path.join(REPORT_DIR, report_name)
    allure_results = os.path.join(ROOT, "allure-results", run_id)
    cmd = [sys.executable, "-m", "pytest", *nodeids, "-q",
           "--html", report_path, "--self-contained-html",
           "--alluredir", allure_results]
    started = time.time()
    with LOCK:
        STATE.update(status="running", log=f"$ {' '.join(cmd)}\n", report=None,
                     runId=run_id, started=started, finished=None, returncode=None,
                     nodeids=nodeids)
    _save_run(run_id, started, "running", nodeids, counts={})
    global PROC
    CANCEL["flag"] = False
    env = os.environ.copy()
    env["ZG_HEADLESS"] = "0" if headed else "1"
    env["ZG_SLOWMO"] = str(slowmo)
    try:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1,
                                env=env, start_new_session=True)
        PROC = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            with LOCK:
                STATE["log"] = (STATE["log"] + line)[-500_000:]
        code = proc.wait()
        status = "cancelled" if CANCEL["flag"] else ("passed" if code == 0 else "failed")
    except Exception as exc:
        code = -1
        status = "failed"
        with LOCK:
            STATE["log"] = (STATE["log"] + f"\n[runner error] {exc}\n")[-500_000:]
    finally:
        PROC = None

    allure_url = None
    if ALLURE_BIN and JRE_HOME:
        out_dir = os.path.join(REPORT_DIR, f"allure-{run_id}")
        env2 = env.copy()
        env2["JAVA_HOME"] = JRE_HOME
        env2["PATH"] = os.path.join(JRE_HOME, "bin") + ":" + env2.get("PATH", "")
        try:
            gen = subprocess.run(
                [ALLURE_BIN, "generate", allure_results, "-o", out_dir, "--clean"],
                cwd=ROOT, env=env2, capture_output=True, text=True, timeout=180,
            )
            if gen.returncode == 0 and os.path.exists(os.path.join(out_dir, "index.html")):
                allure_url = f"/reports/allure-{run_id}/index.html"
                extra = "Allure 报告已生成\n"
            else:
                extra = "Allure 报告生成失败: " + (gen.stderr or gen.stdout)[-500:] + "\n"
        except Exception as exc:
            extra = f"Allure 报告生成失败: {exc}\n"
    else:
        extra = "Allure CLI/JRE 未安装，跳过 Allure 报告\n"

    with LOCK:
        STATE.update(status=status, returncode=code, finished=time.time(),
                     report=f"/reports/{report_name}", allure=allure_url)
        STATE["log"] += extra
        log = STATE["log"]
    _save_run(run_id, started, status, nodeids, f"/reports/{report_name}", log,
              _counts(log), allure_url, returncode=code)


@app.get("/api/cases")
def api_cases(refresh: bool = False):
    cases = discover_cases(force=refresh)
    return {"cases": cases, "collectedAt": _CACHE["ts"]}


@app.post("/api/refresh")
def api_refresh():
    cases = discover_cases(force=True)
    return {"cases": len(cases)}


def select_case_ids(cases, ids=None, tags=None):
    """按显式 id 或标签选择用例；tags 优先，便于“冒烟”一键运行。"""
    if tags:
        wanted = set(tags)
        return [c["id"] for c in cases if wanted.intersection(c.get("tags") or [])]
    valid = {c["id"] for c in cases}
    selected = ids or [c["id"] for c in cases]
    return [i for i in selected if i in valid]


@app.post("/api/run")
async def api_run(request: Request):
    data = await request.json()
    all_cases = discover_cases()
    tags = data.get("tags") or []
    ids = select_case_ids(all_cases, data.get("ids"), tags)
    if not ids:
        message = "没有匹配标签的用例" if tags else "没有可用用例"
        return JSONResponse({"error": message}, status_code=400)
    with LOCK:
        if STATE["status"] == "running":
            return JSONResponse({"error": "已有任务在运行"}, status_code=409)
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    headed = bool(data.get("headed"))
    slowmo = int(data.get("slowmo") or (300 if headed else 0))
    threading.Thread(target=_runner, args=(ids, run_id, headed, slowmo), daemon=True).start()
    return {"runId": run_id, "count": len(ids), "headed": headed, "slowmo": slowmo, "tags": tags}


@app.post("/api/cancel")
def api_cancel():
    global PROC
    with LOCK:
        if STATE["status"] != "running" or PROC is None:
            return JSONResponse({"error": "没有正在运行的任务"}, status_code=400)
        CANCEL["flag"] = True
        try:
            os.killpg(os.getpgid(PROC.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    return {"cancelled": True}


@app.get("/api/status")
def api_status():
    with LOCK:
        payload = dict(STATE)
    if payload["started"] and payload["finished"]:
        payload["duration"] = round(payload["finished"] - payload["started"], 1)
    else:
        payload["duration"] = None
    return payload


@app.get("/api/history")
def api_history(limit: int = 30):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,started,finished,status,nodeids,report,passed,failed,skipped,xfailed,allure,returncode FROM runs ORDER BY started DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        ids = json.loads(r["nodeids"] or "[]")
        # 有效用例 = passed + failed；xfail 是已确认的站点现状，不计入通过率分母
        effective = (r["passed"] or 0) + (r["failed"] or 0)
        out.append({
            "id": r["id"], "started": r["started"], "finished": r["finished"],
            "status": r["status"], "count": len(ids),
            "passed": r["passed"], "failed": r["failed"],
            "skipped": r["skipped"], "xfailed": r["xfailed"],
            "effective": effective,
            "rate": round(r["passed"] * 100 / effective) if effective else None,
            "report": r["report"], "allure": r["allure"],
            "returncode": r["returncode"],
            "duration": round(r["finished"] - r["started"], 1) if r["finished"] else None,
        })
    return out


@app.get("/api/meta")
def api_meta():
    return {
        "baseUrl": os.getenv("ZG_BASE_URL", "https://www.zhengguannews.cn"),
        "version": "0.8",
        "allure": bool(ALLURE_BIN and JRE_HOME),
        "allureVersion": "2.46.1" if ALLURE_BIN else None,
        "passRateBasis": "有效用例 = passed + failed；xfail 单列，不计入通过率分母",
        "auth": bool(AUTH),
    }


@app.get("/api/health")
def api_health():
    checks = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        checks["db"] = True
    except Exception:
        checks["db"] = False
    checks["reports"] = os.path.isdir(REPORT_DIR)
    checks["evidence"] = os.path.isdir(EVIDENCE_DIR)  # 可选：缺失不影响平台可用
    ok = checks["db"] and checks["reports"]
    payload = {
        "status": "ok" if ok else "degraded",
        "checks": checks,
        "running": STATE["status"] == "running",
        "version": "0.8",
    }
    return JSONResponse(payload, status_code=200 if ok else 503)


@app.get("/api/reports")
def api_reports():
    items = []
    for name in os.listdir(REPORT_DIR):
        path = os.path.join(REPORT_DIR, name)
        if os.path.isdir(path) and name.startswith("allure-") and os.path.exists(os.path.join(path, "index.html")):
            items.append({"type": "allure", "name": name, "url": f"/reports/{name}/index.html", "mtime": os.path.getmtime(path)})
        elif os.path.isfile(path) and name.startswith("report-") and name.endswith(".html"):
            items.append({"type": "pytest", "name": name, "url": f"/reports/{name}", "mtime": os.path.getmtime(path)})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


@app.get("/api/defects")
def api_defects():
    data = {"generatedAt": None, "items": []}
    if os.path.exists(DEFECTS_PATH):
        with open(DEFECTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    items = data.get("items", [])
    counts = {
        "total": len(items),
        "p1": sum(1 for i in items if i.get("priority") == "P1"),
        "p2": sum(1 for i in items if i.get("priority") == "P2"),
        "todo": sum(1 for i in items if i.get("status") == "待修复"),
        "high": sum(1 for i in items if i.get("severity") == "高"),
    }
    return {
        "generatedAt": data.get("generatedAt"),
        "source": data.get("source"),
        "note": data.get("note"),
        "items": items,
        "counts": counts,
        "evidence": os.path.isdir(EVIDENCE_DIR),
    }


def _ctx(request, page):
    return {
        "request": request,
        "page": page,
        "base_url": os.getenv("ZG_BASE_URL", "https://www.zhengguannews.cn"),
        "version": "0.8",
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context=_ctx(request, "dashboard"))


@app.get("/cases", response_class=HTMLResponse)
def cases_page(request: Request):
    return templates.TemplateResponse(request=request, name="cases.html", context=_ctx(request, "cases"))


@app.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request):
    return templates.TemplateResponse(request=request, name="runs.html", context=_ctx(request, "runs"))


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    return templates.TemplateResponse(request=request, name="reports.html", context=_ctx(request, "reports"))


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html", context=_ctx(request, "settings"))


@app.get("/defects", response_class=HTMLResponse)
def defects_page(request: Request):
    return templates.TemplateResponse(request=request, name="defects.html", context=_ctx(request, "defects"))
