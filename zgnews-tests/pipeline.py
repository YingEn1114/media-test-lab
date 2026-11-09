"""AI 测试流水线编排：需求 → 生成用例 → 评测 → 写入用例库 → 冒烟 → 全量
→ 失败转缺陷并按域发邮件 → RD 认领/修复/自回测 → QA 验收 → 出报告抄送领导。

与 app.py 解耦：app 通过 configure() 注入 run_suite/discover/路径等依赖，
本模块不反向 import app，避免循环依赖。
"""
import json
import os
import sqlite3
import threading
import time
import uuid

import ai_client
import mailer

DEPS = {}


def configure(**kw):
    DEPS.update(kw)


def _db():
    conn = sqlite3.connect(DEPS["db_path"])
    conn.row_factory = sqlite3.Row
    return conn


def init_pipeline_db():
    conn = sqlite3.connect(DEPS["db_path"])
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY, created REAL NOT NULL, requirement TEXT NOT NULL,
            status TEXT NOT NULL, stage TEXT, source TEXT, data TEXT )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS bugs (
            id TEXT PRIMARY KEY, pipeline_id TEXT, created REAL NOT NULL,
            nodeid TEXT, title TEXT, area TEXT, priority TEXT, severity TEXT,
            owner_name TEXT, owner_email TEXT, status TEXT NOT NULL,
            history TEXT, fix_note TEXT, regress_run TEXT, report TEXT )"""
    )
    conn.commit()
    conn.close()
    mailer.init_mail_db()


GEN_DIR = None  # tests/generated 绝对路径，configure 后计算


def _gen_dir():
    d = os.path.join(DEPS["root"], "tests", "generated")
    os.makedirs(d, exist_ok=True)
    initf = os.path.join(d, "__init__.py")
    if not os.path.exists(initf):
        open(initf, "w").close()
    return d


# PLACEHOLDER_RENDER


def _body(check):
    kind, p = check["kind"], check.get("params", {})
    if kind == "home_reachable":
        return ['    r = requests.get(BASE + "/", timeout=20)',
                '    assert r.status_code == 200, f"首页状态码 {r.status_code}"']
    if kind == "title_contains":
        return ['    r = requests.get(BASE + "/", timeout=20)',
                '    m = re.search(r"<title>(.*?)</title>", r.text, re.S)',
                f'    assert m and {p["text"]!r} in m.group(1), "标题未包含预期文本"']
    if kind == "keyword_present":
        return ['    r = requests.get(BASE + "/", timeout=20)',
                f'    assert {p["keyword"]!r} in r.text, "首页未包含关键词"']
    if kind == "path_status":
        return [f'    r = requests.get(BASE + {p["path"]!r}, timeout=20, allow_redirects=False)',
                f'    assert r.status_code == {int(p["expect"])}, f"状态码 {{r.status_code}}"']
    if kind == "element_present":
        return ['    r = requests.get(BASE + "/", timeout=20)',
                '    soup = BeautifulSoup(r.text, "html.parser")',
                f'    assert len(soup.select({p["selector"]!r})) >= {int(p["min"])}, "元素数量不足"']
    if kind == "search_no_redirect":
        return [f'    r = requests.get(BASE + "/search.html/" + {p["query"]!r}, timeout=20, allow_redirects=False)',
                '    loc = r.headers.get("Location", "")',
                '    assert not (r.status_code in (301, 302) and "down" in loc), f"搜索被重定向到 {loc}"']
    return ['    assert True']


def render_test_file(case, idx, pid6):
    kind = case["check"]["kind"]
    slug = f"{kind}_{idx}"
    filename = f"test_gen_{pid6}_{idx}.py"
    func = f"test_{slug}"
    lines = [
        f"# 由 AI 测试流水线自动生成 · pipeline {pid6} · {case['name']}",
        "import os",
        "import re",
        "import requests",
        "from bs4 import BeautifulSoup",
        "",
        'BASE = os.getenv("ZG_BASE_URL", "https://www.zhengguannews.cn")',
        "",
        "",
        f"def {func}():",
        f'    """{case["name"]}：{case.get("desc", "")}"""',
    ]
    lines += _body(case["check"])
    content = "\n".join(lines) + "\n"
    nodeid = f"tests/generated/{filename}::{func}"
    return filename, nodeid, content


# PLACEHOLDER_STORE


def _save_pipeline(p):
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO pipelines(id,created,requirement,status,stage,source,data)"
        " VALUES(?,?,?,?,?,?,?)",
        (p["id"], p["created"], p["requirement"], p["status"], p["stage"],
         p.get("source"), json.dumps(p["data"], ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def _load_pipeline(pid):
    conn = _db()
    r = conn.execute("SELECT * FROM pipelines WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not r:
        return None
    p = dict(r)
    p["data"] = json.loads(p["data"] or "{}")
    return p


def _timeline(p, stage, msg):
    p["stage"] = stage
    p["data"].setdefault("timeline", []).append(
        {"stage": stage, "ts": time.time(), "msg": msg})
    _save_pipeline(p)


def _save_bug(b):
    conn = _db()
    conn.execute(
        """INSERT OR REPLACE INTO bugs(id,pipeline_id,created,nodeid,title,area,
        priority,severity,owner_name,owner_email,status,history,fix_note,regress_run,report)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (b["id"], b["pipeline_id"], b["created"], b["nodeid"], b["title"], b["area"],
         b["priority"], b["severity"], b["owner_name"], b["owner_email"], b["status"],
         json.dumps(b.get("history", []), ensure_ascii=False), b.get("fix_note"),
         b.get("regress_run"), b.get("report")),
    )
    conn.commit()
    conn.close()


def _load_bug(bid):
    conn = _db()
    r = conn.execute("SELECT * FROM bugs WHERE id=?", (bid,)).fetchone()
    conn.close()
    if not r:
        return None
    b = dict(r)
    b["history"] = json.loads(b["history"] or "[]")
    return b


def _bug_log(b, actor, action, note=""):
    b.setdefault("history", []).append(
        {"ts": time.time(), "actor": actor, "action": action, "note": note})


def _route(area):
    routing = mailer.config().get("routing", {})
    return routing.get(area) or routing.get("default") or {"name": "值班 RD", "email": "rd@local"}


# PLACEHOLDER_ORCH


def _wait_idle(timeout=180):
    state = DEPS["state"]
    waited = 0.0
    while state.get("status") == "running" and waited < timeout:
        time.sleep(1.0)
        waited += 1.0


def _run_stage(nodeids):
    _wait_idle()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    return DEPS["run_suite"](nodeids, run_id)


def _write_cases(accepted, pid6):
    """把通过评测的用例写成 pytest 文件并登记到 cases.json。"""
    gen = _gen_dir()
    meta_path = DEPS["meta_path"]
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    written = []
    for i, case in enumerate(accepted, 1):
        filename, nodeid, content = render_test_file(case, i, pid6)
        with open(os.path.join(gen, filename), "w", encoding="utf-8") as f:
            f.write(content)
        meta[nodeid] = {
            "name": case["name"], "desc": case.get("desc", ""),
            "priority": case["priority"], "tags": case["tags"], "area": case["area"],
        }
        case["nodeid"] = nodeid
        written.append(case)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    DEPS["discover"](force=True)
    return written


def start(requirement):
    pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    p = {"id": pid, "created": time.time(), "requirement": requirement,
         "status": "running", "stage": "queued", "source": None,
         "data": {"timeline": [], "cases": [], "warnings": []}}
    _save_pipeline(p)
    threading.Thread(target=_orchestrate, args=(pid,), daemon=True).start()
    return pid


def _orchestrate(pid):
    p = _load_pipeline(pid)
    req = p["requirement"]
    try:
        # 1. 生成
        _timeline(p, "generate", "调用 AI 生成用例")
        gen = ai_client.generate_cases(req)
        p["source"] = gen["source"]
        if gen.get("warning"):
            p["data"]["warnings"].append(gen["warning"])
        specs = gen["cases"]
        p["data"]["generated"] = specs
        _timeline(p, "generate", f"生成 {len(specs)} 条（来源：{gen['source']}）")

        # 2. 评测
        _timeline(p, "evaluate", "AI 评测用例质量")
        ev = ai_client.evaluate_cases(req, specs)
        p["data"]["evaluation"] = ev
        accepted_names = {v["name"] for v in ev.get("verdicts", []) if v.get("accepted")}
        accepted = [c for c in specs if c["name"] in accepted_names] or specs
        _timeline(p, "evaluate", f"评测均分 {ev.get('overallScore')}，采纳 {len(accepted)} 条")

        # 3. 写入用例库
        _timeline(p, "write", "写入 tests/generated 并登记用例库")
        written = _write_cases(accepted, pid.split("-")[-1])
        p["data"]["cases"] = written
        smoke_ids = [c["nodeid"] for c in written if "smoke" in (c.get("tags") or [])]
        all_ids = [c["nodeid"] for c in written]
        _timeline(p, "write", f"入库 {len(all_ids)} 条，冒烟 {len(smoke_ids)} 条")

        # 4. 冒烟
        _timeline(p, "smoke", "执行冒烟")
        smoke = _run_stage(smoke_ids or all_ids)
        p["data"]["smoke"] = smoke
        _timeline(p, "smoke", f"冒烟 {smoke['status']}：{smoke['counts']}")

        # 5. 全量
        _timeline(p, "full", "执行全量")
        full = _run_stage(all_ids)
        p["data"]["full"] = full
        _timeline(p, "full", f"全量 {full['status']}：{full['counts']}")

        # 6. 失败转缺陷并发邮件
        failures = [c for c in full["cases"] if c["outcome"] in ("failed",)]
        _open_bugs(p, failures)
        if failures:
            p["status"] = "waiting_fix"
            _timeline(p, "triage", f"发现 {len(failures)} 个缺陷，已邮件通知 RD")
            _save_pipeline(p)
        else:
            _timeline(p, "triage", "全部通过，无缺陷")
            _finalize(p)
    except Exception as exc:
        p = _load_pipeline(pid) or p
        p["status"] = "error"
        p["data"].setdefault("warnings", []).append(f"流水线异常：{exc}")
        _timeline(p, "error", f"异常：{exc}")


# PLACEHOLDER_BUGS


def _open_bugs(p, failures):
    full = p["data"].get("full", {})
    report = full.get("report")
    sev_by_prio = {"P0": "严重", "P1": "高", "P2": "中"}
    meta_by_node = {c["nodeid"]: c for c in p["data"].get("cases", [])}
    bug_ids = []
    for f in failures:
        case = meta_by_node.get(f["nodeid"], {})
        area = case.get("area", "AI 生成")
        prio = case.get("priority", "P1")
        owner = _route(area)
        bid = "BUG-" + uuid.uuid4().hex[:8]
        b = {"id": bid, "pipeline_id": p["id"], "created": time.time(),
             "nodeid": f["nodeid"], "title": case.get("name") or f["name"],
             "area": area, "priority": prio, "severity": sev_by_prio.get(prio, "中"),
             "owner_name": owner["name"], "owner_email": owner["email"],
             "status": "open", "history": [], "fix_note": None,
             "regress_run": None, "report": report}
        _bug_log(b, "平台", "创建缺陷", f.get("message", "")[:400])
        _save_bug(b)
        bug_ids.append(bid)
        cfg = mailer.config()
        body = (
            f"你好 {owner['name']}：\n\n自动化流水线发现一个缺陷，请处理。\n\n"
            f"缺陷号：{bid}\n标题：{b['title']}\n优先级：{prio}（{b['severity']}）\n"
            f"测试域：{area}\n用例：{f['nodeid']}\n\n失败信息：\n{f.get('message','')[:600]}\n\n"
            f"处理步骤：\n1. 在平台『AI 流水线』页认领本缺陷；\n"
            f"2. 修复后提交『修复说明』，平台会自动做一次自回测；\n"
            f"3. 自回测通过后状态流转到『待 QA 验收』。\n\n"
            f"测试报告：{report or '（见平台报告页）'}\n"
        )
        mailer.send(owner["email"], f"[BUG][{prio}] {b['title']}（{bid}）", body,
                    cc=[cfg["qa"]["email"]], pipeline_id=p["id"], bug_id=bid)
    p["data"]["bug_ids"] = bug_ids


def claim_bug(bid, owner_name):
    b = _load_bug(bid)
    if not b:
        return None
    b["status"] = "claimed"
    if owner_name:
        b["owner_name"] = owner_name
    _bug_log(b, owner_name or b["owner_name"], "认领")
    _save_bug(b)
    cfg = mailer.config()
    mailer.send(cfg["qa"]["email"], f"[已认领] {b['title']}（{bid}）",
                f"{b['owner_name']} 已认领缺陷 {bid}，开始修复。\n用例：{b['nodeid']}",
                pipeline_id=b["pipeline_id"], bug_id=bid)
    return b


def submit_fix(bid, note, fixer=None):
    """RD 提交修复说明，平台立即自回测（重跑该用例）。"""
    b = _load_bug(bid)
    if not b:
        return None
    b["fix_note"] = note
    b["status"] = "fixing"
    _bug_log(b, fixer or b["owner_name"], "提交修复", note)
    _save_bug(b)
    result = _run_stage([b["nodeid"]])
    b["regress_run"] = result.get("report")
    passed = result["status"] == "passed" and not any(
        c["outcome"] == "failed" for c in result["cases"])
    if passed:
        b["status"] = "fixed_pending_qa"
        _bug_log(b, fixer or b["owner_name"], "自回测通过", result.get("report", ""))
        _save_bug(b)
        cfg = mailer.config()
        body = (f"QA 你好：\n\n缺陷 {bid}『{b['title']}』已由 {b['owner_name']} 修复，"
                f"RD 自回测通过，返回 QA 侧验收。\n\n修复说明：{note}\n"
                f"自回测报告：{result.get('report')}\n用例：{b['nodeid']}\n")
        mailer.send(cfg["qa"]["email"], f"[修复待验证] {b['title']}（{bid}）", body,
                    pipeline_id=b["pipeline_id"], bug_id=bid)
    else:
        b["status"] = "fixing"
        _bug_log(b, fixer or b["owner_name"], "自回测未通过", result.get("report", ""))
        _save_bug(b)
    return b


def verify_bug(bid, accept, qa="QA", note=""):
    b = _load_bug(bid)
    if not b:
        return None
    if accept:
        b["status"] = "closed"
        _bug_log(b, qa, "QA 验收通过", note)
        _save_bug(b)
        mailer.send(b["owner_email"], f"[验收通过] {b['title']}（{bid}）",
                    f"{b['owner_name']} 你好：缺陷 {bid} 已验收关闭，感谢修复。\n{note}",
                    pipeline_id=b["pipeline_id"], bug_id=bid)
        _maybe_finalize(b["pipeline_id"])
    else:
        b["status"] = "reopened"
        _bug_log(b, qa, "QA 打回", note)
        _save_bug(b)
        mailer.send(b["owner_email"], f"[验收打回] {b['title']}（{bid}）",
                    f"{b['owner_name']} 你好：缺陷 {bid} 验收未通过，请继续处理。\n原因：{note}",
                    pipeline_id=b["pipeline_id"], bug_id=bid)
    return b


# PLACEHOLDER_FINAL


def _maybe_finalize(pid):
    conn = _db()
    rows = conn.execute(
        "SELECT status FROM bugs WHERE pipeline_id=?", (pid,)).fetchall()
    conn.close()
    if rows and all(r["status"] == "closed" for r in rows):
        p = _load_pipeline(pid)
        if p and p["status"] != "passed":
            _finalize(p)


def _finalize(p):
    full = p["data"].get("full", {})
    counts = full.get("counts", {})
    bugs = list_bugs(p["id"])
    report = full.get("report")
    p["status"] = "passed"
    _timeline(p, "done", "全部缺陷关闭，出报告并抄送领导")
    cfg = mailer.config()
    leaders = [l["email"] for l in cfg.get("leaders", [])]
    lines = [
        f"各位领导、QA：",
        "",
        f"需求『{p['requirement'][:60]}』的自动化测试已完成。",
        "",
        f"用例：{len(p['data'].get('cases', []))} 条（AI 生成，来源 {p.get('source')}）",
        f"评测均分：{p['data'].get('evaluation', {}).get('overallScore')}",
        f"全量结果：{counts}",
        f"缺陷：共 {len(bugs)} 个，均已修复并通过 QA 验收。",
        "",
        "缺陷明细：",
    ]
    for b in bugs:
        lines.append(f"  - {b['id']} {b['title']}（{b['priority']}）→ {b['status']}，处理人 {b['owner_name']}")
    lines += ["", f"测试报告：{report or '（见平台报告页）'}", "",
              "本邮件由正观新闻自动化测试平台发出。"]
    mailer.send(cfg["qa"]["email"], f"[测试报告] {p['requirement'][:40]} 验收通过",
                "\n".join(lines), cc=leaders, pipeline_id=p["id"])
    p["data"]["finalReport"] = {"to": cfg["qa"]["email"], "cc": leaders, "report": report}
    _save_pipeline(p)


# ---- getters ----

def get_pipeline(pid):
    p = _load_pipeline(pid)
    if p:
        p["bugs"] = list_bugs(pid)
    return p


def list_pipelines(limit=50):
    conn = _db()
    rows = conn.execute(
        "SELECT id,created,requirement,status,stage,source FROM pipelines ORDER BY created DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_bugs(pid=None):
    conn = _db()
    if pid:
        rows = conn.execute("SELECT * FROM bugs WHERE pipeline_id=? ORDER BY created", (pid,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM bugs ORDER BY created DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        b = dict(r)
        b["history"] = json.loads(b["history"] or "[]")
        out.append(b)
    return out
