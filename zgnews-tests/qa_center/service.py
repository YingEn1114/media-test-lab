import json
import os
import re
import secrets
import subprocess
import threading
import time
import tempfile
import socket
from pathlib import Path
from email.message import EmailMessage

import ai_client

from .codegen import fingerprint, render, validate
from .evidence import inspect
from .review import evaluate
from .store import Problem, Store, digest, require, uid


COLLECTIONS = {"requirements", "drafts", "reviews", "cases", "runs", "defects",
               "reports", "outbox", "prompts", "sync"}


class Center:
    def __init__(self, db_path, root, runner, cancel=None, background=True, ai=None):
        self.store = Store(db_path)
        self.root = Path(root).resolve()
        repo_path = os.getenv("ZG_ASSET_REPO") or os.getenv("ZG_GIT_REPO") or str(db_path) + ".assets.git"
        require("://" not in repo_path, "当前 Git 同步配置应为专用本地资产仓库路径，不能填远程 URL", 400)
        self.asset_repo = Path(repo_path).resolve()
        if self.asset_repo.exists():
            bare = subprocess.run(["git", f"--git-dir={self.asset_repo}", "rev-parse", "--is-bare-repository"],
                                  capture_output=True, text=True, timeout=15)
            require(bare.returncode == 0 and bare.stdout.strip() == "true",
                    "生成资产必须使用专用 bare 仓库，禁止指向用户工作仓库的 .git", 400)
        self.runner, self.cancel_runner = runner, cancel
        self.background = background
        self.process_owner = uid()
        self.host = socket.gethostname()
        self.ai = ai or ai_client._chat
        self.store.bootstrap()
        defaults = json.loads(Path(__file__).with_name("prompts.json").read_text())
        with self.store.tx() as conn:
            if not self.store.list(conn, "prompts"):
                for category, text in defaults.items():
                    self.store.put(conn, "prompts", {
                        "category": category, "version": 1, "text": text, "active": True})
            if not self.store.list(conn, "settings"):
                self.store.put(conn, "settings", {"routing": {}, "qa": [], "leaders": []})
            # Preserve all human metadata and map old nodeids to stable UUIDs.
            meta = self.root / "cases.json"
            existing = {c["nodeid"] for c in self.store.list(conn, "cases")}
            if meta.exists():
                for nodeid, data in json.loads(meta.read_text()).items():
                    if nodeid not in existing and not nodeid.startswith("tests/generated/"):
                        self.store.put(conn, "cases", {**data, "nodeid": nodeid,
                            "origin": "manual", "status": "published", "requirement_id": None})
            # Workers from a dead process cannot provide valid completion evidence.
            # Only bootstrap recovery is explicit; do not steal another live process's slot.
        self.recover_dead()

    def role(self, actor, *roles):
        require(actor["role"] in roles or actor["role"] == "admin", "当前角色无权执行此操作", 403)

    def prompt(self, conn, category):
        items = [p for p in self.store.list(conn, "prompts") if p["category"] == category and p["active"]]
        require(len(items) == 1, "Prompt 配置错误")
        return items[0]

    def chat(self, conn, category, payload):
        require(ai_client.available() or self.ai is not ai_client._chat, "AI 未配置；演示生成须显式选择 demo，演示不自动通过评审", 422)
        prompt = self.prompt(conn, category)
        try:
            result = self.ai([{"role": "system", "content": prompt["text"]},
                              {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
        except Exception as exc:
            # Never expose API credentials or request headers through exceptions.
            raise Problem("AI 调用失败，请检查服务端配置；没有自动回退或自动通过", 502) from exc
        require(isinstance(result, dict), "AI 响应不是结构化对象", 422)
        return result, prompt["id"]

    def write_code(self, draft):
        folder = self.root / "tests" / "generated" / draft["requirement_id"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"case_{draft['id'].replace('-', '')}_v{draft['version']}.py"
        code = render(draft["spec"])
        # Immutable version assets; no mutable filename reused after review.
        if path.exists():
            require(path.read_text() == code, "生成资产已被本地修改，请先检查 diff")
        else:
            with path.open("x") as stream:
                stream.write(code)
        draft["code_path"] = path.relative_to(self.root).as_posix()
        draft["code_hash"] = digest(code)
        draft["nodeid"] = draft["code_path"] + "::test_generated"

    def code_hash(self, obj):
        path = (self.root / obj["code_path"]).resolve()
        require(path.is_relative_to(self.root / "tests" / "generated"), "资产路径无效")
        require(path.is_file(), "生成代码缺失")
        return digest(path.read_text())

    def snapshot(self, actor, collection):
        require(collection in COLLECTIONS or collection in ("settings", "users", "audit", "overview", "history"),
                "未知资源", 404)
        with self.store.tx() as conn:
            if actor["role"] == "rd":
                require(collection in ("defects", "cases", "requirements", "runs", "overview"),
                        "RD无权读取工厂、评审、同步或管理资源", 403)
            if collection == "users":
                self.role(actor, "admin")
                return [dict(r) for r in conn.execute("SELECT id,name,role,active,email FROM qa_users")]
            if collection == "history":
                self.role(actor, "qa")
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                data = {table: [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY created DESC LIMIT 100")]
                        for table in ("pipelines", "bugs", "mails") if table in tables}
                if "runs" in tables:
                    data["runs"] = [dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY started DESC LIMIT 100")]
                path = self.root / "defects.json"
                data["known_defects"] = json.loads(path.read_text()) if path.exists() else {}
                return data
            if collection == "audit":
                self.role(actor, "admin")
                return [dict(r) for r in conn.execute("SELECT * FROM qa_audit ORDER BY created DESC LIMIT 300")]
            if collection == "settings":
                self.role(actor, "admin")
                return {"config": self.store.list(conn, "settings")[0],
                        "ai": {"configured": ai_client.available(),
                               "base_url": os.getenv("ZG_AI_BASE_URL", ""),
                               "model": os.getenv("ZG_AI_MODEL", ""),
                               "key": "********" if os.getenv("ZG_AI_KEY") else ""},
                        "transport": "outbox-only"}
            if collection == "overview":
                if actor["role"] == "rd":
                    return {"defects": sum(self.visible_defect(actor, d) for d in self.store.list(conn, "defects"))}
                return {kind: len(self.store.list(conn, kind)) for kind in COLLECTIONS}
            items = self.store.list(conn, collection)
            if actor["role"] == "rd":
                defects = [d for d in self.store.list(conn, "defects") if self.visible_defect(actor, d)]
                visible = {d["id"] for d in defects}
                case_ids = {d["case_id"] for d in defects}
                case_items = [c for c in self.store.list(conn, "cases") if c["id"] in case_ids]
                requirements = {c.get("requirement_id") for c in case_items}
                if collection == "defects":
                    items = [d for d in items if d["id"] in visible]
                elif collection == "runs":
                    items = [r for r in items if r.get("defect_id") in visible]
                elif collection == "cases":
                    items = case_items
                elif collection == "requirements":
                    items = [r for r in items if r["id"] in requirements]
                elif collection in ("reports", "outbox"):
                    raise Problem("报告和邮件仅QA/负责人可见", 403)
            return items

    def visible_defect(self, actor, defect):
        return actor["role"] != "rd" or actor["id"] in (defect.get("owner_id"), defect.get("routed_owner_id"))

    def dispatch(self, actor, collection, object_id, action, data):
        self.role(actor, "qa", "rd")  # viewer is strictly read-only
        pending = None
        with self.store.tx() as conn:
            result = self._mutate(conn, actor, collection, object_id, action, data)
            if isinstance(result, tuple):
                result, pending = result
            self.store.audit(conn, actor, f"{collection}.{action}", result.get("id"),
                             {"input_keys": sorted(data)})  # no secrets in audit
        if pending:
            if self.background:
                threading.Thread(target=self.execute, args=(pending,), daemon=True).start()
            else:
                self.execute(pending)
                with self.store.tx() as conn:
                    result = self.store.get(conn, result["id"])
        return result

    def import_requirement_document(self, actor, filename, content, options):
        """Extract a text requirement and reuse the normal draft generation flow."""
        self.role(actor, "qa")
        name = Path(filename or "requirement.txt").name
        suffix = Path(name).suffix.lower()
        require(suffix in {".txt", ".md", ".markdown", ".csv"}, "当前支持 TXT、Markdown 和 CSV 文档", 415)
        require(len(content or b"") <= 2 * 1024 * 1024, "需求文档不能超过 2MB", 413)
        text = content.decode("utf-8-sig", errors="replace").replace("\x00", "").strip()
        require(text, "文档没有可分析的文本内容", 422)
        title = next((line.strip("# *-").strip() for line in text.splitlines() if line.strip()), Path(name).stem)
        lines = [line.strip(" -*#") for line in text.splitlines() if line.strip()]
        points = [line for line in lines if any(word in line for word in ("验收", "验证", "必须", "返回", "播放", "搜索", "导航", "视口"))][:8]
        payload = {
            "title": title[:120], "description": text[:20000], "acceptance": "\n".join(points or lines[:6]),
            "owner": (options.get("owner") or "文档导入").strip(), "area": (options.get("area") or "需求文档").strip(),
            "priority": options.get("priority") if options.get("priority") in ("P0", "P1", "P2", "P3") else "P1",
            "scope": f"来源文档：{name}", "tags": ["document"], "test_points": points or lines[:6],
        }
        requirement = self.dispatch(actor, "requirements", None, "create", payload)
        generated = self.dispatch(actor, "drafts", None, "generate",
                                  {"requirement_id": requirement["id"], "demo": bool(options.get("demo"))})
        return {"requirement": requirement, "drafts": generated}

    def _mutate(self, conn, actor, kind, oid, action, data):
        s = self.store
        if kind == "requirements":
            self.role(actor, "qa")
            obj = s.get(conn, oid, kind) if oid else {"version": 0, "status": "active"}
            if action == "delete":
                obj["status"] = "deleted"  # tombstone preserves foreign references
            else:
                require(action in ("create", "update"), "未知操作", 404)
                if oid:
                    require(data.get("version") == obj["version"], "需求版本冲突")
                for key in ("title", "description", "acceptance", "owner", "area", "priority", "tags", "scope",
                            "goal", "risk", "implementation", "environment", "test_points"):
                    if key in data:
                        obj[key] = data[key]
                require(isinstance(obj.get("title"), str) and obj["title"].strip(), "需求标题必填", 400)
                require(isinstance(obj.get("acceptance"), str) and obj["acceptance"].strip(), "验收标准必填", 400)
                obj["version"] += 1
            return s.put(conn, kind, obj)

        if kind == "drafts":
            self.role(actor, "qa")
            if action == "generate":
                req = s.get(conn, data.get("requirement_id"), "requirements")
                require(req["status"] == "active", "需求已删除")
                if data.get("demo") is True:
                    specs, prompt_id, source = ai_client._local_generate(req.get("description", "")), None, "demo-local-rules"
                else:
                    output, prompt_id = self.chat(conn, "generation", req)
                    specs, source = output.get("cases", []), "ai"
                require(isinstance(specs, list) and 0 < len(specs) <= 50, "AI 未返回1至50条用例", 422)
                validated = [validate(spec) for spec in specs]
                batch = uid()
                for spec in validated:
                    obj = {"id": uid(), "requirement_id": req["id"], "requirement_version": req["version"],
                           "spec": spec, "source": source, "prompt_id": prompt_id,
                           "version": 1, "status": "draft", "batch_id": batch}
                    self.write_code(obj)
                    s.put(conn, kind, obj)
                return {"id": batch, "count": len(validated), "source": source}
            obj = s.get(conn, oid, kind)
            require(obj["status"] != "deleted", "草稿已删除")
            if action == "delete":
                require(not any(c.get("draft_id") == oid for c in s.list(conn, "cases")), "已发布草稿不可删除，请保留追溯")
                obj["status"] = "deleted"
                return s.put(conn, kind, obj)
            if action == "update":
                require(data.get("version") == obj["version"], "草稿版本冲突")
                obj["spec"] = validate(data["spec"])
                req = s.get(conn, obj["requirement_id"], "requirements")
                obj.update(version=obj["version"] + 1, requirement_version=req["version"], status="draft")
                obj.pop("review_id", None)
                obj.pop("commit", None)
                self.write_code(obj)
                return s.put(conn, kind, obj)
            if action == "review":
                req = s.get(conn, obj["requirement_id"], "requirements")
                require(req["status"] == "active" and req["version"] == obj["requirement_version"], "需求已变化，请更新草稿后重审")
                require(self.code_hash(obj) == obj["code_hash"], "代码 hash 变化，需重新生成并评审")
                duplicate = any(fingerprint(d["spec"]) == fingerprint(obj["spec"]) and
                                d["id"] != oid and d["status"] != "deleted"
                                for d in s.list(conn, "drafts"))
                duplicate |= any(c.get("draft_id") != oid and c.get("spec") and
                                 fingerprint(c["spec"]) == fingerprint(obj["spec"])
                                 for c in s.list(conn, "cases"))
                prompt = self.prompt(conn, "review")
                inputs = {"requirement": req, "candidate": obj,
                          "code": (self.root / obj["code_path"]).read_text(),
                          "sync": [r for r in s.list(conn, "sync") if r["draft_id"] == oid],
                          "published_cases": s.list(conn, "cases"),
                          "batch_candidates": [d for d in s.list(conn, "drafts") if d.get("batch_id") == obj.get("batch_id")],
                          "environment": s.list(conn, "settings")[0].get("capabilities", {}),
                          "prompt": prompt, "model": os.getenv("ZG_AI_MODEL", "unconfigured")}
                response, prompt_id = self.chat(conn, "review", inputs)
                verdict = evaluate(response, req, obj, duplicate)
                accepted = verdict["accepted"]
                review = s.put(conn, "reviews", {"draft_id": oid, "draft_version": obj["version"],
                    "requirement_version": obj["requirement_version"], "code_hash": obj["code_hash"],
                    "prompt_id": prompt_id, "verdict": verdict, "accepted": accepted,
                    "input_snapshot": inputs, "duplicate_detected": duplicate, "source": "ai", "actor_id": actor["id"]})
                obj.update(review_id=review["id"], status="reviewed" if accepted else "rejected")
                s.put(conn, kind, obj)
                return review
            if action == "publish":
                require(data.get("confirm") is True, "必须人工确认入库", 400)
                require(obj["spec"].get("automation") is not False, "手工设计不得作为自动化用例入库执行")
                spec = obj["spec"]
                require(all(isinstance(spec.get(k), str) and spec[k].strip()
                            for k in ("goal", "preconditions", "test_type", "implementation")),
                        "入库前请补全用例目标、前置条件、测试类型与实现说明", 400)
                expected = spec.get("expected") or spec.get("expected_results")
                require(all(isinstance(values, list) and values and
                            all(isinstance(v, str) and v.strip() for v in values)
                            for values in (spec.get("steps"), expected)),
                        "入库前必须提供非空的逐步操作与明确预期结果", 400)
                review = s.get(conn, obj.get("review_id"), "reviews")
                req = s.get(conn, obj["requirement_id"], "requirements")
                require(review["accepted"] and review["draft_version"] == obj["version"] and
                        review["requirement_version"] == req["version"] and req["status"] == "active" and
                        review["code_hash"] == self.code_hash(obj) == obj["code_hash"], "评审拒绝或已过期，必须重新评审")
                commit = self.asset_commit(obj)
                prior = [c for c in s.list(conn, "cases") if c.get("draft_id") == oid]
                if prior and prior[0].get("draft_version") == obj["version"]:
                    return prior[0]
                case = {**obj, "id": prior[0]["id"] if prior else uid(), "draft_id": oid,
                        "draft_version": obj["version"], "review_id": review["id"], "commit": commit,
                        "published_by": actor["id"], "status": "published", "origin": "generated",
                        **{k: obj["spec"][k] for k in ("name", "desc", "area", "priority", "tags")}}
                obj["status"] = "published"
                s.put(conn, kind, obj)
                return s.put(conn, "cases", case)
            if action in ("sync", "commit"):
                require(data.get("confirm") is True, "同步将定向提交当前generated资产，请明确确认", 400)
                self.sync_asset(obj)
                record = self.git_info(obj)
                obj["commit"] = record.get("commit")
                s.put(conn, kind, obj)
                return s.put(conn, "sync", {"draft_id": oid, "code_hash": obj["code_hash"], **record})
            if action == "diff":
                return {"id": oid, **self.git_info(obj)}
            raise Problem("未知草稿操作", 404)

        if kind == "prompts":
            self.role(actor, "admin")
            if action == "activate":
                obj = s.get(conn, oid, kind)
                for prompt in s.list(conn, kind):
                    if prompt["category"] == obj["category"]:
                        prompt["active"] = prompt["id"] == oid
                        s.put(conn, kind, prompt)
                obj["active"] = True
                return s.put(conn, kind, obj)
            require(action == "create" and isinstance(data.get("text"), str) and data["text"].strip(), "Prompt 内容必填", 400)
            category = data.get("category")
            old = self.prompt(conn, category)
            old["active"] = False
            s.put(conn, kind, old)
            version = max(p["version"] for p in s.list(conn, kind) if p["category"] == category) + 1
            return s.put(conn, kind, {"category": category, "text": data["text"],
                                     "version": version, "active": True, "actor_id": actor["id"]})

        if kind == "runs":
            self.role(actor, "qa", "rd")
            if action == "recover":
                self.role(actor, "admin")
                require(bool(data.get("reason", "").strip()), "恢复必须填写原因", 400)
                return self.recover_slot(conn, actor, explicit=True, reason=data["reason"])
            if action == "cancel":
                run = s.get(conn, oid, kind)
                if actor["role"] == "rd":
                    require(run.get("actor_id") == actor["id"] and run.get("defect_id") and
                            self.visible_defect(actor, s.get(conn, run["defect_id"], "defects")),
                            "不能取消其他人的任务", 403)
                require(run["status"] in ("queued", "running"), "运行已完成")
                run["cancel_requested"] = True
                s.put(conn, kind, run)
                if self.cancel_runner:
                    self.cancel_runner()
                return run
            require(action == "create", "未知运行操作", 404)
            self.role(actor, "qa")  # RD runs only linked regressions via defect fix
            return self.reserve(conn, actor, {k: data[k] for k in ("scope", "ids", "value") if k in data})

        if kind == "defects":
            defect = s.get(conn, oid, kind)
            require(self.visible_defect(actor, defect), "无权访问此缺陷", 403)
            if action == "claim":
                self.role(actor, "rd")
                require(defect["status"] in ("open", "reopened"), "仅未解决缺陷可认领")
                defect.update(owner_id=actor["id"], status="claimed")
                return s.put(conn, kind, defect)
            if action == "fix":
                self.role(actor, "rd")
                require(defect["status"] in ("claimed", "fix_failed") and defect.get("owner_id") == actor["id"],
                        "仅认领者可提交修复")
                require(isinstance(data.get("note"), str) and data["note"].strip() and
                        (re.fullmatch(r"[a-fA-F0-9]{7,40}", data.get("commit", "")) or
                         re.fullmatch(r"https?://[^\s]+", data.get("pr", ""))), "修复需说明及有效commit或PR", 400)
                defect["fix"] = {"id": uid(), "commit": data.get("commit"), "pr": data.get("pr"),
                                 "note": data["note"], "actor_id": actor["id"], "created": time.time()}
                run, pending = self.reserve(conn, actor, {"scope": "selected", "ids": [defect["case_id"]],
                                    "purpose": "rd", "defect_id": oid, "fix_id": defect["fix"]["id"]})
                defect.update(status="rd_running", rd_run_id=run["id"])
                return s.put(conn, kind, defect), pending
            if action == "verify":
                self.role(actor, "qa")
                require(defect["status"] == "pending_qa", "仅RD真实自测通过后可QA回测")
                require(defect.get("owner_id") != actor["id"], "QA必须由独立人员执行", 403)
                run, pending = self.reserve(conn, actor, {"scope": "selected", "ids": [defect["case_id"]],
                                    "purpose": "qa", "defect_id": oid, "fix_id": defect["fix"]["id"]})
                defect.update(status="qa_running", qa_run_id=run["id"], qa_id=actor["id"])
                return s.put(conn, kind, defect), pending
            if action == "close":
                self.role(actor, "qa")
                require(defect["status"] == "fixed" and defect.get("qa_id") == actor["id"],
                        "仅真实QA回测通过的验收者可关闭")
                defect["status"] = "closed"
                return s.put(conn, kind, defect)
            if action == "assign":
                self.role(actor, "qa")
                owner = conn.execute("SELECT id FROM qa_users WHERE id=? AND role='rd' AND active=1",
                                     (data.get("owner_id"),)).fetchone()
                require(owner is not None, "负责人必须为有效RD", 400)
                require(defect["status"] in ("open", "reopened"), "仅未认领缺陷可改派")
                defect["routed_owner_id"] = owner[0]
                self.notify(conn, defect, "缺陷已分派")
                return s.put(conn, kind, defect)
            raise Problem("禁止的状态转换", 409)

        if kind == "reports":
            self.role(actor, "qa")
            require(action == "create", "报告快照不可修改", 409)
            run = s.get(conn, data.get("run_id"), "runs")
            require(run["scope"] == "full" and run["status"] in ("passed", "failed") and run.get("finished"),
                    "报告只能来自已完成全量run")
            defects = s.list(conn, "defects")
            risks = [d for d in defects if d["priority"] in ("P0", "P1") and d["status"] not in ("fixed", "closed")]
            verdict = "passed" if run["status"] == "passed" and run["evidence"]["complete"] and not risks else "risk"
            prompts = {k: self.prompt(conn, k)["id"] for k in ("summary", "report", "email")}
            return s.put(conn, kind, {"run_id": run["id"], "run_snapshot": run, "defect_snapshot": defects,
                       "risks": risks, "verdict": verdict, "prompt_ids": prompts,
                       "source": "evidence-template", "title": data.get("title") or "全量测试报告",
                       "actor_id": actor["id"]})

        if kind == "outbox":
            self.role(actor, "qa")
            if action == "create":
                report = s.get(conn, data.get("report_id"), "reports")
                settings = s.list(conn, "settings")[0]
                obj = {"report_id": report["id"], "status": "draft", "transport": "outbox",
                       "subject": f"[{'风险' if report['verdict'] == 'risk' else '通过'}] {report['title']}",
                       "body": "", "evidence_summary": self.report_text(report),
                       "to": settings["qa"], "cc": settings["leaders"]}
            else:
                obj = s.get(conn, oid, kind)
                require(obj["status"] == "draft" or action == "archive", "已发送草稿不可编辑")
            if action in ("create", "update"):
                for key in ("to", "cc", "subject", "body"):
                    if key in data:
                        obj[key] = data[key]
                obj.setdefault("to", [])
                obj.setdefault("cc", [])
                self.recipients(obj)
                # Body stays derived from immutable evidence to prevent risk omission.
            elif action == "send":
                self.recipients(obj)
                require(bool(obj["to"]), "至少填写一个收件人", 400)
                report = s.get(conn, obj["report_id"], "reports")
                newer = [r for r in s.list(conn, "runs") if r["scope"] == "full" and r["created"] > report["run_snapshot"]["created"]]
                require(not newer, "存在更新的全量run，请生成新报告，旧报告仅可归档")
                risks = [d for d in s.list(conn, "defects") if d["priority"] in ("P0", "P1") and d["status"] not in ("fixed", "closed")]
                require(not risks or report["verdict"] == "risk", "新增未解决P0/P1，需重新生成风险报告")
                obj["status"], obj["sent_at"] = "queued-local", time.time()
                obj["subject"] = f"[{'风险' if report['verdict'] == 'risk' else '通过'}] " + obj["subject"]
                obj["evidence_summary"] = self.report_text(report)
            elif action == "archive":
                obj["status"] = "archived"
            else:
                raise Problem("未知发件箱操作", 404)
            return s.put(conn, kind, obj)

        if kind == "settings":
            self.role(actor, "admin")
            obj = s.list(conn, kind)[0]
            routing = data.get("routing", obj["routing"])
            require(isinstance(routing, dict), "路由必须是对象", 400)
            users = {r[0] for r in conn.execute("SELECT id FROM qa_users WHERE active=1 AND role='rd'")}
            require(all(v in users for v in routing.values()), "路由仅允许指向有效RD用户UUID", 400)
            obj.update(routing=routing)
            if "capabilities" in data:
                require(isinstance(data["capabilities"], dict), "环境能力必须是对象", 400)
                obj["capabilities"] = data["capabilities"]
            for key in ("qa", "leaders"):
                if key in data:
                    self.recipients({"to": data[key], "cc": []})
                    obj[key] = data[key]
            return s.put(conn, kind, obj)

        if kind == "users":
            self.role(actor, "admin")
            require(action in ("create", "update"), "未知用户操作", 404)
            if action == "update":
                email = data.get("email", "")
                self.recipients({"to": [email] if email else [], "cc": []})
                require(conn.execute("SELECT 1 FROM qa_users WHERE id=?", (oid,)).fetchone(), "用户不存在", 404)
                conn.execute("UPDATE qa_users SET email=? WHERE id=?", (email, oid))
                return {"id": oid, "email": email}
            require(data.get("role") in ("qa", "rd", "viewer", "test_lead", "tech_lead", "project_lead", "admin") and
                    isinstance(data.get("name"), str) and data["name"].strip(), "用户名称和角色必填", 400)
            token = secrets.token_urlsafe(32)
            user = {"id": uid(), "name": data["name"].strip(), "role": data["role"]}
            user["email"] = data.get("email", "")
            self.recipients({"to": [user["email"]] if user["email"] else [], "cc": []})
            require(not conn.execute("SELECT 1 FROM qa_users WHERE name=?", (user["name"],)).fetchone(), "用户已存在")
            conn.execute("INSERT INTO qa_users(id,name,role,token_hash,active,email) VALUES(?,?,?,?,1,?)",
                         (user["id"], user["name"], user["role"], digest(token), user["email"]))
            return {**user, "token": token}  # shown exactly once, never persisted in plaintext
        raise Problem("未知资源或操作", 404)

    def recipients(self, obj):
        for key in ("to", "cc"):
            addresses = obj.get(key, [])
            require(isinstance(addresses, list) and len(addresses) <= 100 and
                    all(isinstance(a, str) and re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+", a) for a in addresses),
                    "收件人/抄送须为有效邮箱数组", 400)
        require(isinstance(obj.get("subject", ""), str) and
                not any(c in obj.get("subject", "") for c in "\r\n"), "邮件标题无效", 400)

    def report_text(self, report):
        return (f"报告：{report['title']}\n结论：{report['verdict']}\n"
                f"全量run：{report['run_id']}\n"
                f"证据完整：{report['run_snapshot']['evidence']['complete']}\n"
                "未解决P0/P1：\n" + "\n".join(
                    f"{d['id']} {d['title']} {d['priority']} {d['status']}" for d in report["risks"]) +
                "\n运行结果：\n" + json.dumps(report["run_snapshot"]["evidence"]["cases"], ensure_ascii=False))

    def notify(self, conn, defect, subject):
        owner = defect.get("owner_id") or defect.get("routed_owner_id")
        user = conn.execute("SELECT email FROM qa_users WHERE id=?", (owner,)).fetchone()
        settings = self.store.list(conn, "settings")[0]
        return self.store.put(conn, "outbox", {
            "defect_id": defect["id"], "status": "queued-local" if user and user[0] else "needs-recipient",
            "to": [user[0]] if user and user[0] else [], "cc": settings["qa"],
            "subject": f"[{defect['priority']}] {subject}：{defect['title']}",
            "body": f"缺陷：{defect['id']}\n状态：{defect['status']}\n请在缺陷协同中认领并提交修复证明。",
            "evidence_summary": json.dumps(defect.get("evidence", {}), ensure_ascii=False),
            "transport": "outbox"})

    def eml(self, actor, mail_id):
        mails = self.snapshot(actor, "outbox")
        mail = next((m for m in mails if m["id"] == mail_id), None)
        require(mail is not None, "邮件不存在", 404)
        message = EmailMessage()
        message["From"] = "qa-platform@localhost"
        message["To"], message["Cc"] = ", ".join(mail["to"]), ", ".join(mail["cc"])
        message["Subject"] = mail["subject"]
        message.set_content(mail.get("body", "") + "\n\n--- 不可移除的执行证据与风险摘要 ---\n" +
                            mail.get("evidence_summary", ""))
        return message.as_bytes()

    def reserve(self, conn, actor, data):
        s = self.store
        require(not conn.execute("SELECT 1 FROM qa_runner_slot").fetchone(), "已有执行占用运行槽", 409)
        cases = [c for c in s.list(conn, "cases") if c["status"] == "published"]
        scope = data.get("scope", "full")
        require(scope in ("scope", "full", "smoke", "selected", "requirement", "area", "priority", "tag"), "执行范围无效", 400)
        if scope in ("scope", "selected"):
            wanted = data.get("ids", [])
            require(isinstance(wanted, list) and wanted and set(wanted).issubset({c["id"] for c in cases}),
                    "所选用例必须全部已发布且存在", 400)
            cases = [c for c in cases if c["id"] in wanted]
        elif scope == "smoke":
            cases = [c for c in cases if "smoke" in c.get("tags", [])]
        elif scope == "tag":
            cases = [c for c in cases if data.get("value") in c.get("tags", [])]
        elif scope in ("requirement", "area", "priority"):
            key = "requirement_id" if scope == "requirement" else scope
            require(bool(data.get("value")), "范围过滤值必填", 400)
            cases = [c for c in cases if c.get(key) == data["value"]]
        require(cases, "范围内没有已发布用例", 400)
        for case in cases:
            if case["origin"] == "generated":
                require(self.code_hash(case) == case["code_hash"], "已发布代码发生变化，禁止执行")
                draft = s.get(conn, case["draft_id"], "drafts")
                req = s.get(conn, case["requirement_id"], "requirements")
                require(draft["version"] == case["draft_version"] and req["version"] == case["requirement_version"]
                        and req["status"] == "active", "草稿或需求已变化，必须重新评审入库")
        run = s.put(conn, "runs", {"scope": scope, "selection": cases,
                    "status": "queued", "actor_id": actor["id"], "cancel_requested": False,
                    "purpose": data.get("purpose") if data.get("defect_id") else None,
                    "defect_id": data.get("defect_id"), "fix_id": data.get("fix_id")})
        conn.execute("INSERT INTO qa_runner_slot(slot,run_id,pid,owner,host) VALUES(1,?,?,?,?)",
                     (run["id"], os.getpid(), self.process_owner, self.host))
        return run, run["id"]

    def execute(self, run_id):
        s = self.store
        with s.tx() as conn:
            run = s.get(conn, run_id, "runs")
            run.update(status="running", started=time.time())
            s.put(conn, "runs", run)
        expected = [c["nodeid"] for c in run["selection"]]
        try:
            allowed = {str(self.root / c["code_path"]): c["code_hash"]
                       for c in run["selection"] if c["origin"] == "generated"}
            result = ({"status": "cancelled", "returncode": -1} if run["cancel_requested"] else
                      self.runner(expected, run_id, manifest=allowed))
            evidence = inspect(result, expected, strict=bool(run.get("defect_id")))
        except Exception:
            evidence = inspect({"returncode": -1}, expected)
        with s.tx() as conn:
            current = s.get(conn, run_id, "runs")
            if current["cancel_requested"]:
                evidence.update(status="cancelled", complete=False)
            current.update(status=evidence["status"], evidence=evidence, finished=time.time())
            s.put(conn, "runs", current)
            conn.execute("DELETE FROM qa_runner_slot WHERE run_id=?", (run_id,))
            defect_id = current.get("defect_id")
            if defect_id:
                defect = s.get(conn, defect_id, "defects")
                # Completion must match the exact fix and current pending transition.
                expected_state = "rd_running" if current["purpose"] == "rd" else "qa_running"
                require(defect["status"] == expected_state and defect["fix"]["id"] == current["fix_id"],
                        "回测结果对应的修复版本已失效")
                if current["purpose"] == "rd":
                    defect["status"] = "pending_qa" if evidence["status"] == "passed" else "fix_failed"
                else:
                    defect["status"] = "fixed" if evidence["status"] == "passed" else "reopened"
                s.put(conn, "defects", defect)
                self.notify(conn, defect, "缺陷回测结果")
                s.audit(conn, {"id": current["actor_id"]}, "defects.regression", defect_id,
                        {"run_id": run_id, "status": defect["status"]})
            else:
                for failure in evidence["cases"]:
                    if failure["outcome"] != "failed":
                        continue
                    case = next(c for c in run["selection"] if c["nodeid"] == failure["nodeid"])
                    existing = [d for d in s.list(conn, "defects") if d["case_id"] == case["id"] and d["status"] != "closed"]
                    if existing:
                        defect = existing[0]
                        defect["status"] = "reopened"
                        defect["run_id"], defect["evidence"] = run_id, failure
                    else:
                        routing = s.list(conn, "settings")[0]["routing"]
                        defect = {"case_id": case["id"], "requirement_id": case.get("requirement_id"),
                                  "run_id": run_id, "title": case.get("name", case["nodeid"]),
                                  "area": case.get("area", ""), "priority": case.get("priority", "P1"),
                                  "status": "open", "evidence": failure,
                                  "routed_owner_id": routing.get(case.get("area")) or routing.get("default")}
                    s.put(conn, "defects", defect)
                    self.notify(conn, defect, "自动化执行发现缺陷")
            s.audit(conn, {"id": current["actor_id"]}, "runs.complete", run_id,
                    {"status": current["status"], "complete": evidence["complete"]})

    def git(self, *args, env=None, input=None):
        result = subprocess.run(["git", f"--git-dir={self.asset_repo}", f"--work-tree={self.root}", *args],
                                cwd=self.root, env=env, input=input, capture_output=True, text=True, timeout=15)
        require(result.returncode == 0, "本地Git查询失败；请确认资产已定向提交", 409)
        return result.stdout

    def asset_commit(self, obj):
        """No staging/commit/push here: inspect committed blob of exactly this asset."""
        rel = obj["code_path"]
        try:
            commit = self.git("log", "-1", "--format=%H", "--", obj["code_path"]).strip()
            require(bool(commit), "代码尚未同步；请点击同步代码定向提交generated资产")
            blob = self.git("show", f"{commit}:{rel}")
            require(digest(blob) == obj["code_hash"] == self.code_hash(obj), "提交内容与评审代码不一致")
            return commit
        except Problem:
            raise

    def git_info(self, obj):
        require(self.code_hash(obj) == obj["code_hash"], "代码hash已变化")
        try:
            diff = self.git("diff", "HEAD", "--", obj["code_path"])
        except Problem:
            diff = ""
        if not diff:
            # Untracked assets have no HEAD diff; show an explicit addition preview.
            try:
                self.asset_commit(obj)
            except Problem:
                diff = "--- /dev/null\n+++ " + obj["code_path"] + "\n" + "\n".join(
                    "+" + line for line in (self.root / obj["code_path"]).read_text().splitlines())
        try:
            commit = self.asset_commit(obj)
        except Problem:
            commit = None
        branch = self.git("symbolic-ref", "--short", "HEAD").strip() if self.asset_repo.exists() else os.getenv("ZG_GIT_BRANCH", "main")
        return {"commit": commit, "repository": str(self.asset_repo), "branch": branch,
                "diff": diff, "content": (self.root / obj["code_path"]).read_text(),
                "status": "synced" if commit else "pending-sync", "path": obj["code_path"],
                "note": "同步仅提交选定generated资产，使用隔离index；从不远程push"}

    def sync_asset(self, obj):
        """Create a commit from a private index, then CAS HEAD; never touch user's index."""
        require(self.code_hash(obj) == obj["code_hash"], "代码hash变化，禁止同步")
        try:
            return self.asset_commit(obj)  # idempotent if this exact asset is already committed
        except Problem:
            pass
        if not self.asset_repo.exists():
            self.asset_repo.parent.mkdir(parents=True, exist_ok=True)
            branch = os.getenv("ZG_GIT_BRANCH", "main")
            valid_branch = subprocess.run(["git", "check-ref-format", "--branch", branch],
                                           capture_output=True, text=True, timeout=15)
            require(valid_branch.returncode == 0, "ZG_GIT_BRANCH 不是有效分支名", 400)
            initialized = subprocess.run(["git", "init", "--bare", "--initial-branch", branch, str(self.asset_repo)],
                                         capture_output=True, text=True, timeout=15)
            require(initialized.returncode == 0, "无法初始化独立资产仓库")
        try:
            head = self.git("rev-parse", "--verify", "HEAD").strip()
        except Problem:
            head = None
        path = obj["code_path"]
        require(obj["code_path"].startswith("tests/generated/"), "只能同步generated资产")
        with tempfile.TemporaryDirectory(prefix="qa-git-index-") as temp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(temp) / "index"),
                   "GIT_AUTHOR_NAME": os.getenv("ZG_GIT_AUTHOR_NAME", "QA Asset Bot"),
                   "GIT_AUTHOR_EMAIL": os.getenv("ZG_GIT_AUTHOR_EMAIL", "qa-assets@localhost"),
                   "GIT_COMMITTER_NAME": os.getenv("ZG_GIT_AUTHOR_NAME", "QA Asset Bot"),
                   "GIT_COMMITTER_EMAIL": os.getenv("ZG_GIT_AUTHOR_EMAIL", "qa-assets@localhost")}
            self.git("read-tree", *([head] if head else ["--empty"]), env=env)
            self.git("add", "-f", "--", obj["code_path"], env=env)
            tree = self.git("write-tree", env=env).strip()
            baseline = head or self.git("mktree", input="", env=env).strip()
            changed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", baseline, tree, env=env).splitlines()
            require(changed == [path], "隔离提交包含非选定资产，已拒绝")
            commit = self.git("commit-tree", tree, *(["-p", head] if head else []), "-m",
                              f"qa generated asset {obj['id']} v{obj['version']}", env=env).strip()
            # Fail if another process advanced HEAD; leaves only an unreachable object, no lost commits.
            self.git("update-ref", "HEAD", commit, head or "0" * 40, env=env)
        require(self.asset_commit(obj) == commit, "同步后代码校验失败")
        return commit

    def recover_dead(self):
        with self.store.tx() as conn:
            slot = conn.execute("SELECT * FROM qa_runner_slot").fetchone()
            if slot and slot["pid"] and slot["host"] == self.host and not self.pid_alive(slot["pid"]):
                self.recover_slot(conn, {"id": "system"}, reason="启动检测到原进程已退出")

    @staticmethod
    def pid_alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def recover_slot(self, conn, actor, explicit=False, reason=""):
        slot = conn.execute("SELECT * FROM qa_runner_slot").fetchone()
        require(slot is not None, "没有待恢复运行槽")
        # Never seize a known live process. Legacy slots without PID need explicit admin action.
        require(not (slot["pid"] and slot["host"] == self.host and self.pid_alive(slot["pid"])),
                "运行槽所属进程仍存活，禁止抢占")
        require((slot["host"] == self.host and slot["pid"]) or explicit,
                "未知/异机运行槽需要管理员明确恢复")
        run = self.store.get(conn, slot["run_id"], "runs")
        run.update(status="aborted", finished=time.time(), recovery_reason=reason)
        self.store.put(conn, "runs", run)
        if run.get("defect_id"):
            defect = self.store.get(conn, run["defect_id"], "defects")
            if defect["status"] in ("rd_running", "qa_running"):
                defect["status"] = "fix_failed" if run["purpose"] == "rd" else "pending_qa"
                self.store.put(conn, "defects", defect)
        conn.execute("DELETE FROM qa_runner_slot WHERE run_id=?", (run["id"],))
        self.store.audit(conn, actor, "runs.recovered", run["id"], {"reason": reason, "previous_owner": slot["owner"]})
        return run
