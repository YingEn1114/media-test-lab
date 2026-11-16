"""Backend implementation of AI_REVIEW_POLICY.md, independent of model decisions."""
from decimal import Decimal, ROUND_HALF_UP

from .store import require

WEIGHTS = {"requirement_coverage": 20, "step_completeness": 15,
           "expected_result_clarity": 15, "automation_feasibility": 15,
           "stability": 10, "maintainability": 10, "risk_coverage": 10,
           "duplication_control": 5}
CORE = list(WEIGHTS)[:4]
ARRAYS = ("blocking_issues", "suggestions", "missing_scenarios", "duplicate_candidates",
          "security_concerns", "automation_concerns", "evidence_gaps")


def evaluate(response, requirement, candidate, duplicate):
    require(response.get("requirement_id") == requirement["id"], "评审需求ID不匹配", 422)
    items = response.get("reviewed_cases")
    require(isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict),
            "逐条评审必须有且仅有当前候选的结论", 422)
    verdict = items[0]
    require(verdict.get("candidate_id") == candidate["id"] and
            verdict.get("candidate_version") == candidate["version"] and
            verdict.get("code_hash") == candidate["code_hash"], "评审候选ID、版本或代码hash不匹配", 422)
    dimensions = verdict.get("dimensions")
    require(isinstance(dimensions, dict) and set(dimensions) == set(WEIGHTS) and
            all(type(v) in (int, float) and 0 <= v <= 100 for v in dimensions.values()),
            "必须完整返回八维0—100分评分", 422)
    require(all(isinstance(verdict.get(k), list) for k in ARRAYS), "逐条问题、建议及证据缺口数组不完整", 422)
    for key in ("blocking_issues", "security_concerns", "automation_concerns", "evidence_gaps", "suggestions"):
        require(all(isinstance(v, dict) and all(isinstance(v.get(k), str) and v[k].strip()
                    for k in ("code", "location", "reason", "suggestion")) for v in verdict[key]),
                "问题建议必须含code/location/reason/suggestion", 422)
    require(isinstance(verdict.get("summary"), str) and verdict["summary"].strip(), "评审摘要必填", 422)
    require(verdict.get("decision") in ("pass", "pass_with_changes", "needs_revision", "reject"),
            "评审decision无效", 422)
    weighted = sum(Decimal(str(dimensions[k])) * weight for k, weight in WEIGHTS.items()) / 100
    score = int(weighted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    accepted = (score >= 80 and all(dimensions[k] >= 70 for k in CORE) and
                not duplicate and not any(verdict[k] for k in (
                    "blocking_issues", "security_concerns", "duplicate_candidates",
                    "automation_concerns", "evidence_gaps")) and
                verdict["decision"] in ("pass", "pass_with_changes"))
    return {**verdict, "overall_score": score, "accepted": accepted,
            "duplicate_detected": duplicate, "model_overall_score": verdict.get("overall_score")}
