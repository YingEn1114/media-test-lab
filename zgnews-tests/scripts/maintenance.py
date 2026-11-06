#!/usr/bin/env python3
"""维护脚本：清理空运行记录与过期报告。默认 dry-run，只打印不动手。

用法：
    .venv/bin/python scripts/maintenance.py                 # 预览
    .venv/bin/python scripts/maintenance.py --apply         # 执行（先备份 DB）
    .venv/bin/python scripts/maintenance.py --keep-reports 30 --keep-allure 8
"""

import argparse
import os
import shutil
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("ZG_DB", os.path.join(ROOT, "platform.db"))
REPORT_DIR = os.path.join(ROOT, "reports")
ALLURE_RESULTS = os.path.join(ROOT, "allure-results")


def empty_runs():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, started FROM runs WHERE nodeids IS NULL OR nodeids IN ('', '[]') ORDER BY started"
    ).fetchall()
    conn.close()
    return rows


def files_newest(paths, keep):
    paths = sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)
    return paths[:keep], paths[keep:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际删除（默认只预览）")
    parser.add_argument("--keep-reports", type=int, default=20)
    parser.add_argument("--keep-allure", type=int, default=5)
    args = parser.parse_args()

    runs = empty_runs()
    report_files = [
        os.path.join(REPORT_DIR, n)
        for n in os.listdir(REPORT_DIR)
        if n.startswith("report-") and n.endswith(".html")
    ]
    allure_dirs = [
        os.path.join(REPORT_DIR, n)
        for n in os.listdir(REPORT_DIR)
        if n.startswith("allure-") and os.path.isdir(os.path.join(REPORT_DIR, n))
    ]
    keep_reports, drop_reports = files_newest(report_files, args.keep_reports)
    keep_allure, drop_allure = files_newest(allure_dirs, args.keep_allure)
    result_dirs = [
        os.path.join(ALLURE_RESULTS, n)
        for n in os.listdir(ALLURE_RESULTS)
        if os.path.isdir(os.path.join(ALLURE_RESULTS, n))
    ] if os.path.isdir(ALLURE_RESULTS) else []
    keep_results, drop_results = files_newest(result_dirs, args.keep_allure)

    print(f"DB: {DB_PATH}")
    print(f"空运行记录: {len(runs)} 条")
    for rid, started in runs:
        print(f"  - {rid}  {time.strftime('%Y-%m-%d %H:%M', time.localtime(started))}")
    print(f"报告: 保留 {len(keep_reports)} / 删除 {len(drop_reports)}")
    for p in drop_reports:
        print(f"  - {os.path.basename(p)}")
    print(f"Allure 报告: 保留 {len(keep_allure)} / 删除 {len(drop_allure)}")
    print(f"Allure 原始结果: 保留 {len(keep_results)} / 删除 {len(drop_results)}")

    if not args.apply:
        print("\nDRY-RUN：未修改任何文件。加 --apply 执行。")
        return

    backup = DB_PATH + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(DB_PATH, backup)
    print(f"\n已备份 DB: {backup}")

    conn = sqlite3.connect(DB_PATH)
    conn.executemany("DELETE FROM runs WHERE id = ?", [(rid,) for rid, _ in runs])
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    for p in drop_reports:
        os.remove(p)
    for p in drop_allure + drop_results:
        shutil.rmtree(p, ignore_errors=True)
    print(f"已删除 {len(runs)} 条空运行、{len(drop_reports)} 份报告、{len(drop_allure) + len(drop_results)} 个 Allure 目录。")


if __name__ == "__main__":
    main()
