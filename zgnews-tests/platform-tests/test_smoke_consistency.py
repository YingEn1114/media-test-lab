import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_smoke_tags_match_markers():
    """cases.json 的 smoke 标签必须与 pytest -m smoke 收集到的用例完全一致。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-m", "smoke", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    collected = {
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    }
    meta = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    tagged = {nodeid for nodeid, info in meta.items() if "smoke" in info.get("tags", [])}
    assert collected, "pytest -m smoke 没有收集到用例"
    assert collected == tagged, f"仅 marker: {collected - tagged}；仅 tag: {tagged - collected}"
