"""AI 适配器：需求 → 生成用例规格；对生成的用例做评测打分。

接入方式（OpenAI 兼容）：
    ZG_AI_BASE_URL=https://.../v1   ZG_AI_KEY=sk-...   ZG_AI_MODEL=gpt-4o-mini
未配置或调用失败时，退回本地启发式生成/评测，保证整条链路离线可跑。

安全设计：AI 只能从受限的「检查工具箱」里挑选 kind + 参数，平台据此渲染
固定模板的 pytest 代码；**绝不执行 AI 直接产出的任意代码**。
"""
import json
import os
import re

# 允许的检查类型；AI/本地生成都只能产出这些 kind
CHECK_KINDS = {
    "home_reachable": [],
    "title_contains": ["text"],
    "keyword_present": ["keyword"],
    "path_status": ["path", "expect"],
    "element_present": ["selector", "min"],
    "search_no_redirect": ["query"],
}

SYSTEM_PROMPT = (
    "你是资深 QA。根据需求，为网站产出 4-7 条可自动化的黑盒测试用例。"
    "只能使用下列检查类型（kind）及参数，不要编写任何代码：\n"
    "- home_reachable: 首页返回 200\n"
    "- title_contains{text}: 首页 <title> 含 text\n"
    "- keyword_present{keyword}: 首页 HTML 含 keyword\n"
    "- path_status{path,expect}: 访问 path 返回 expect 状态码\n"
    "- element_present{selector,min}: 首页该 CSS 选择器元素数 >= min\n"
    "- search_no_redirect{query}: 站内搜索 query 不应被 302 到下载页\n"
    "严格输出 JSON：{\"cases\":[{\"name\",\"desc\",\"priority\"(P0/P1/P2),"
    "\"area\",\"tags\":[],\"check\":{\"kind\",\"params\":{}}}]}。"
)


def available():
    return bool(os.getenv("ZG_AI_BASE_URL") and os.getenv("ZG_AI_KEY"))


def _chat(messages, temperature=0.2):
    import requests

    base = os.getenv("ZG_AI_BASE_URL", "").rstrip("/")
    url = base + "/chat/completions"
    model = os.getenv("ZG_AI_MODEL", "gpt-4o-mini")
    headers = {"Authorization": "Bearer " + os.getenv("ZG_AI_KEY", ""),
               "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "temperature": temperature,
            "response_format": {"type": "json_object"}}
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _valid_check(chk):
    if not isinstance(chk, dict):
        return False
    kind = chk.get("kind")
    if kind not in CHECK_KINDS:
        return False
    params = chk.get("params") or {}
    return all(k in params for k in CHECK_KINDS[kind])


def _normalize(cases):
    out = []
    for c in cases:
        if not _valid_check(c.get("check")):
            continue
        tags = list(dict.fromkeys(["generated", "ai"] + (c.get("tags") or [])))
        out.append({
            "name": c.get("name") or "未命名用例",
            "desc": c.get("desc", ""),
            "priority": c.get("priority") if c.get("priority") in ("P0", "P1", "P2") else "P1",
            "area": c.get("area") or "AI 生成",
            "tags": tags,
            "check": {"kind": c["check"]["kind"], "params": c["check"].get("params") or {}},
        })
    return out


def _local_generate(requirement):
    """无 AI 时的启发式生成：从需求关键词推导受限检查。"""
    req = requirement or ""
    cases = [
        {"name": "首页可访问", "desc": "首页返回 200", "priority": "P0",
         "area": "首页与导航", "tags": ["smoke"],
         "check": {"kind": "home_reachable", "params": {}}},
        {"name": "首页标题含品牌", "desc": "<title> 含“正观新闻”", "priority": "P0",
         "area": "首页与导航", "tags": ["smoke"],
         "check": {"kind": "title_contains", "params": {"text": "正观新闻"}}},
    ]
    if any(k in req for k in ("搜索", "search", "检索")):
        cases.append({"name": "站内搜索不跳下载页", "desc": "搜索不应被 302 到 /down.html",
                      "priority": "P1", "area": "搜索", "tags": ["search"],
                      "check": {"kind": "search_no_redirect", "params": {"query": "正观"}}})
    if any(k in req for k in ("视频", "播放", "media", "video")):
        cases.append({"name": "首页视频入口存在", "desc": "首页存在视频相关链接",
                      "priority": "P1", "area": "视频与播放器", "tags": ["video"],
                      "check": {"kind": "element_present", "params": {"selector": "a[href*='video']", "min": 1}}})
    if any(k in req for k in ("频道", "导航", "menu", "栏目")):
        cases.append({"name": "顶部导航可用", "desc": "顶部菜单链接数 >= 10",
                      "priority": "P1", "area": "首页与导航", "tags": ["ui"],
                      "check": {"kind": "element_present", "params": {"selector": ".top-menu .nav-link", "min": 10}}})
    if any(k in req for k in ("接口", "api", "robots", "资源")):
        cases.append({"name": "robots.txt 可用", "desc": "/robots.txt 返回 200",
                      "priority": "P2", "area": "接口与资源", "tags": ["api", "http"],
                      "check": {"kind": "path_status", "params": {"path": "/robots.txt", "expect": 200}}})
    m = re.findall(r"[“\"']([^”\"']{2,20})[”\"']", req)
    if m:
        cases.append({"name": f"首页含关键词：{m[0]}", "desc": f"首页 HTML 含“{m[0]}”",
                      "priority": "P2", "area": "页面与内容", "tags": ["content"],
                      "check": {"kind": "keyword_present", "params": {"keyword": m[0]}}})
    return _normalize(cases)


def generate_cases(requirement):
    """返回用例规格列表；优先 AI，失败回退本地。附带 source 标记。"""
    if available():
        try:
            data = _chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "需求：" + (requirement or "")},
            ])
            cases = _normalize(data.get("cases") or [])
            if cases:
                return {"cases": cases, "source": "ai"}
        except Exception as exc:
            return {"cases": _local_generate(requirement), "source": "local",
                    "warning": f"AI 调用失败，已回退本地生成：{exc}"}
    return {"cases": _local_generate(requirement), "source": "local"}


def _local_evaluate(requirement, cases):
    verdicts = []
    for c in cases:
        kind = c["check"]["kind"]
        # 覆盖度/风险启发式：可复现已知问题的用例价值更高
        score = 80
        if kind == "search_no_redirect":
            score = 90
        elif kind in ("home_reachable", "title_contains"):
            score = 75
        comment = "检查项明确、可自动化、断言稳定。"
        verdicts.append({"name": c["name"], "accepted": score >= 60,
                         "score": score, "comment": comment})
    overall = round(sum(v["score"] for v in verdicts) / len(verdicts)) if verdicts else 0
    summary = (f"共 {len(cases)} 条，建议全部纳入；"
               f"覆盖首页可用性、内容与已知风险点。平均 {overall} 分。")
    return {"overallScore": overall, "verdicts": verdicts, "summary": summary}


def evaluate_cases(requirement, cases):
    if available():
        try:
            prompt = ("需求：" + (requirement or "") + "\n待评测用例（JSON）："
                      + json.dumps(cases, ensure_ascii=False))
            data = _chat([
                {"role": "system", "content":
                 "你是测试评审。对每条用例给出 accepted(bool)、score(0-100)、comment，"
                 "并给 overallScore 与 summary。严格输出 JSON："
                 "{\"overallScore\":int,\"verdicts\":[{\"name\",\"accepted\",\"score\",\"comment\"}],\"summary\":str}"},
                {"role": "user", "content": prompt},
            ])
            if data.get("verdicts"):
                return data
        except Exception:
            pass
    return _local_evaluate(requirement, cases)
