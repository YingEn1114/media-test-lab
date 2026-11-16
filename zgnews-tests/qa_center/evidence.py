import xml.etree.ElementTree as ET
from collections import Counter


def inspect(result, expected, strict=False):
    """Require exact identities, one result each, valid exit code and no cancellation."""
    cases, errors = [], []
    try:
        root = ET.fromstring(result.get("junit") or "")
        if root.tag not in ("testsuites", "testsuite"):
            raise ValueError("invalid JUnit root")
        for tc in root.iter("testcase"):
            name, classname = tc.get("name", ""), tc.get("classname", "")
            matches = []
            for node in expected:
                parts = node.split("::")
                klass = parts[0][:-3].replace("/", ".") + (
                    "." + ".".join(parts[1:-1]) if len(parts) > 2 else "")
                if name == parts[-1] and classname == klass:
                    matches.append(node)
            if len(matches) != 1:
                errors.append(f"JUnit identity ambiguous/unknown: {classname}.{name}")
                continue
            outcome = "passed"
            message = ""
            for child in tc:
                if child.tag in ("error", "failure", "skipped"):
                    outcome = ("failed" if child.tag in ("error", "failure") else
                               ("xfailed" if "xfail" in child.get("type", "").lower() else "skipped"))
                    message = (child.get("message") or child.text or "")[:4000]
                    break
            cases.append({"nodeid": matches[0], "outcome": outcome, "message": message})
        if any(int(s.get("errors", 0)) for s in root.iter("testsuite")):
            errors.append("collection/setup errors")
    except (ET.ParseError, ValueError, TypeError):
        errors.append("JUnit missing or malformed")
    if Counter(c["nodeid"] for c in cases) != Counter(expected):
        errors.append("JUnit evidence does not cover exact run selection")
    cancelled = result.get("status") == "cancelled"
    complete = not errors and not cancelled and result.get("returncode") in (0, 1)
    acceptable = ("passed",) if strict else ("passed", "xfailed")
    passed = complete and result.get("returncode") == 0 and all(c["outcome"] in acceptable for c in cases)
    return {"status": "cancelled" if cancelled else ("passed" if passed else "failed"),
            "complete": complete, "cases": cases, "errors": errors,
            "returncode": result.get("returncode"), "report": result.get("report"),
            "junit": result.get("junit", ""),
            "counts": {key: sum(c["outcome"] == key for c in cases)
                       for key in ("passed", "failed", "skipped", "xfailed")}}
