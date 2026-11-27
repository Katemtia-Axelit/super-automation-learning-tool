"""一次性脚本：从 **迁移前** 的 legacy 单体采集冻结行为基线。

Stage 7 把 ``server/backend_api.py`` 收口成薄别名之后，"现场跑 legacy"
不再可行。但 P2 的功能保全证据要求台账里的每条判定都有 **实测观测值**
支撑（含 **副作用** 摘要），所以这里做一次 **一次性** 采集：

1. 从 Git HEAD（Stage 7 之前）取出迁移前的 ``server/backend_api.py``；
2. 在合成根里把它当作独立单体跑起来（自带 Flask 路由 + 自带 ensure）；
3. 逐条执行与 ``scripts/legacy_divergence_probe.py`` **完全相同** 的用例；
4. 把观测值（含副作用摘要）冻结成 ``tests/fixtures/legacy_baseline.json``。

采集出来的基线 **只读**；Stage 8 之后的每次探针运行都是拿 **实时
Factory** 与这份冻结基线比对。

用法::

    python scripts/_freeze_legacy_baseline.py --write
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHARACTERIZE_DIR = PROJECT_ROOT / "tests" / "characterize"
OUTPUT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "legacy_baseline.json"

#: 迁移前 legacy 单体从 Git HEAD 取出。
LEGACY_HEAD_REV = "HEAD"

#: 采集器：把 legacy 单体放进合成根单独跑。
_COLLECTOR = r'''
"""Observe the pre-migration legacy monolith (from git HEAD) route by route."""
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlencode

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

VOLATILE = {
    "created_at", "updated_at", "timestamp", "last_completed_at",
    "last_drawn_at", "next_available_at", "started_at", "ended_at",
    "date", "exported_at", "port",
}

CASES = [
    ("health", "GET", "/api/health", None, None, ()),
    ("list_tasks", "GET", "/api/tasks", None, {"unlocked_only": "false"}, ("tasks",)),
    ("get_task_missing", "GET", "/api/tasks/999999", None, None, ()),
    ("get_dependents_missing", "GET", "/api/tasks/999999/dependents", None, None, ()),
    ("create_task", "POST", "/api/tasks",
     {"name": "PROBE_TASK", "category": "study", "estimated_time": 25}, None, ("tasks",)),
    ("create_task_no_name", "POST", "/api/tasks", {"category": "study"}, None, ()),
    ("complete_task", "POST", "/api/tasks/1/complete", None, None,
     ("tasks", "gacha_records")),
    ("skip_task", "POST", "/api/tasks/2/skip", None, None, ("tasks",)),
    ("update_task_missing", "PUT", "/api/tasks/999999", {"name": "X"}, None, ()),
    ("delete_task_missing", "DELETE", "/api/tasks/999999", None, None, ()),
    ("complete_missing", "POST", "/api/tasks/999999/complete", None, None, ()),
    ("skip_missing", "POST", "/api/tasks/999999/skip", None, None, ()),
    ("refuse_missing", "POST", "/api/tasks/999999/refuse", None, None, ()),
    ("list_tags", "GET", "/api/tags", None, None, ("tags",)),
    ("create_tag", "POST", "/api/tags", {"name": "probetag"}, None, ("tags",)),
    ("create_tag_dup", "POST", "/api/tags", {"name": "probetag"}, None, ()),
    ("delete_tag_missing", "DELETE", "/api/tags/999999", None, None, ()),
    ("tags_batch", "POST", "/api/tags/batch", {"names": ["b1", "b2"]}, None, ("tags",)),
    ("gacha_pools", "GET", "/api/gacha/pools", None, None, ()),
    ("gacha_pools_detail", "GET", "/api/gacha/pools/detail", None, None, ()),
    ("gacha_statistics", "GET", "/api/gacha/statistics", None, None, ()),
    ("gacha_draw", "POST", "/api/gacha/draw", {}, None, ("gacha_records",)),
    ("gacha_care_draw", "POST", "/api/gacha/care-draw", {}, None, ("gacha_records",)),
    ("gacha_replace_missing", "POST", "/api/gacha/replace", {"task_id": 999999}, None, ()),
    ("gacha_replace_no_reason", "POST", "/api/gacha/replace", {"task_id": 1}, None, ()),
    ("gacha_replace_with_reason", "POST", "/api/gacha/replace",
     {"task_id": 1, "reason": "other"}, None,
     ("gacha_records", "task_rejection_log")),
    ("discard_pile", "GET", "/api/discard-pile", None, None, ("tasks",)),
    ("discard_restore_missing", "POST", "/api/discard-pile/999999/restore", None, None, ()),
    ("move_to_discard_missing", "POST", "/api/tasks/999999/move-to-discard", None, None, ()),
    ("dependencies", "GET", "/api/dependencies", None, None, ()),
    ("config_get", "GET", "/api/config", None, None, ()),
    ("export", "GET", "/api/export", None, None, ()),
    ("index", "GET", "/", None, None, ()),
    ("agent_agents", "GET", "/api/agent/agents", None, None, ()),
    ("agent_files_raw", "GET", "/api/agent/files/raw", None, None, ()),
    ("agent_files_vault", "GET", "/api/agent/files/vault", None, None, ()),
    ("agent_save_note", "POST", "/api/agent/save-note",
     {"note_path": "x.md", "content": "y"}, None, ()),
    ("prompts_list", "GET", "/api/prompts", None, None, ()),
    ("prompt_get_missing", "GET", "/api/prompts/does-not-exist.md", None, None, ()),
    ("agent_policy_status", "GET", "/api/agent-policy/status", None, None, ()),
]


def strip_volatile(value):
    if isinstance(value, dict):
        return {
            k: strip_volatile(v)
            for k, v in sorted(value.items())
            if k not in VOLATILE
        }
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
    return value


def table_digest(conn, table):
    try:
        rows = conn.execute("SELECT * FROM " + table).fetchall()
    except sqlite3.Error:
        return None
    out = []
    for row in rows:
        item = {}
        for key in row.keys():
            if key in VOLATILE:
                continue
            item[key] = repr(row[key]) if isinstance(row[key], bytes) else row[key]
        out.append(item)
    out.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    return out


def main():
    import random
    random.seed(20260121)

    db = root / "data" / "legacy.sqlite3"
    if db.exists():
        db.unlink()

    # legacy 单体是 **独立** 的：它自带 Flask app、自带 ensure、自带路由。
    # 关键：它 **不能** import 当前工作区的 server.app（那是 Factory）。
    import importlib.util

    spec = importlib.util.find_spec("server.backend_api")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_PATH = str(db)
    module.NOTES_DIR = str(root / "vault")

    from flask import Flask
    Flask.run = lambda self, *a, **k: None

    legacy_app = module.app

    conn = sqlite3.connect(str(db))
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        # P1 的 Schema 权威层（server/schema）是 legacy 的 **DDL 来源**：
        # legacy 单体在 HEAD 时期已把建表交给它，只保留 ensure_* 的增量列。
        from server.schema import ensure_all
        ensure_all(conn)
        # legacy 单体自带 ensure_* 链（其增量列 DDL 权威当时就在 backend_api 里）。
        module.ensure_task_dependency_schema(conn)
        module.ensure_schedule_schema(conn)
        module.ensure_timer_schema(conn)
        module.ensure_assessment_schema(conn)
        module.ensure_daily_state_schema(conn)
        module.ensure_task_feedback_events_schema(conn)
        module.ensure_indexes(conn)
        conn.commit()
    finally:
        conn.close()

    client = legacy_app.test_client()
    results = []
    for name, method, path, body, query, tables in CASES:
        url = path
        if query:
            url = path + "?" + urlencode(query)
        kwargs = {}
        if body is not None:
            kwargs["json"] = body
        resp = getattr(client, method.lower())(url, **kwargs)
        try:
            payload = resp.get_json(force=True)
        except Exception:
            payload = {"__non_json__": resp.data[:200].decode("utf-8", "replace")}
        entry = {
            "name": name, "method": method, "path": path,
            "status": resp.status_code,
            "json": strip_volatile(payload),
        }
        if tables:
            conn = sqlite3.connect(str(db))
            try:
                conn.row_factory = sqlite3.Row
                entry["side_effects"] = {
                    t: table_digest(conn, t) for t in tables
                }
            finally:
                conn.close()
        results.append(entry)

    out_file = root / "_probe_legacy.json"
    out_file.write_text(
        json.dumps({"results": results}, ensure_ascii=False), encoding="utf-8"
    )
    print("PROBE_FILE=" + str(out_file))


main()
'''


def _git_show(path: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{LEGACY_HEAD_REV}:{path}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "git show 失败: " + path + " :: " + proc.stderr.decode("utf-8", "replace")
        )
    return proc.stdout


def collect() -> List[Dict[str, Any]]:
    """在合成根里跑迁移前 legacy 单体，采集观测值。"""
    sys.path.insert(0, str(CHARACTERIZE_DIR))
    from sandbox_env import available_port, materialize, seed

    with tempfile.TemporaryDirectory(prefix="lt_freeze_baseline_") as temp:
        sandbox = materialize(Path(temp) / "sandbox", available_port())
        seed(sandbox)

        # 迁移前的 legacy 单体 + 迁移前的兼容桥（legacy 侧依赖它）。
        legacy_src = _git_show("server/backend_api.py")
        (sandbox / "server" / "backend_api.py").write_bytes(legacy_src)
        compat_src = _git_show("server/app/legacy_compat.py")
        compat_path = sandbox / "server" / "app" / "legacy_compat.py"
        compat_path.parent.mkdir(parents=True, exist_ok=True)
        compat_path.write_bytes(compat_src)

        collector = sandbox / "_freeze_baseline.py"
        collector.write_text(_COLLECTOR, encoding="utf-8")

        env = {
            k: v
            for k, v in os.environ.items()
            if (
                "API_KEY" not in k.upper()
                and "TOKEN" not in k.upper()
                and "SECRET" not in k.upper()
                and k.upper() not in ("PYTHONPATH", "PYTHONHOME")
            )
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-I", str(collector)],
            cwd=sandbox,
            env=env,
            capture_output=True,
            timeout=180,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
            raise RuntimeError("legacy 基线采集失败: " + stderr[-4000:])
        stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
        lines = [
            ln for ln in stdout.splitlines() if ln.startswith("PROBE_FILE=")
        ]
        if len(lines) != 1:
            raise RuntimeError("未捕获 PROBE_FILE: " + stdout[-4000:])
        path = Path(lines[0][len("PROBE_FILE=") :].strip())
        return json.loads(path.read_text(encoding="utf-8"))["results"]


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="冻结 legacy 行为基线")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv[1:])

    results = collect()
    payload = {
        "schema_version": 2,
        "generated_by": "scripts/_freeze_legacy_baseline.py",
        "legacy_source_rev": LEGACY_HEAD_REV,
        "note": (
            "迁移前 legacy 单体（git HEAD 版本）在合成根内的实测观测值；"
            "Stage 7 legacy 收口后作为只读基线，与实时 Factory 对比。"
        ),
        "total_cases": len(results),
        "entries": results,
    }
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("WROTE " + str(OUTPUT_PATH))
        print("cases=" + str(len(results)))
        return 0

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
