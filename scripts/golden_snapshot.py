"""scripts/golden_snapshot.py — 迁移前 Factory 的 **黄金 HTTP 快照**（AR03-P2 / Stage 1）。

为什么需要
----------
Stage 1–8 的每一域迁移都要回答同一个问题：**"迁移后的行为与迁移前一致吗？"**

生产默认运行时是 **Factory**，因此 parity oracle = **迁移前** Factory 在
**合成环境** 下的 HTTP 行为。本模块负责：

1. 在合成根（``tests/characterize/sandbox_env.py``）里建一个 Factory app；
2. 对每条路由执行 **成功路径 + 错误路径** 的请求；
3. 记录 **状态码 / 响应结构 / 响应体 / 副作用后的 DB 状态**；
4. 产出机读快照（JSON），供各阶段比对。

设计要点
--------
* **合成根**：绝不触碰生产 DB / WAL / SHM / Vault / config；
* **可复现**：每个用例都是"无副作用"或"自带清理"；
* **结构化比对**：比对器忽略 ``created_at`` / ``updated_at`` / ``timestamp``
  等时间戳字段（只比 **结构** 与 **语义**），避免时间抖动造成假阴性；
* **副作用快照**：每个写操作之后，把受影响表的 **行数 + 内容摘要** 记下来。

用法
----
::

    # 采集（覆盖写回冻结快照）
    python scripts/golden_snapshot.py --write

    # 比对（当前实现 vs 冻结快照）
    python scripts/golden_snapshot.py --check
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "golden_http_snapshot.json"
CHARACTERIZE_DIR = PROJECT_ROOT / "tests" / "characterize"

#: 快照比对时 **忽略** 的字段（时间戳 / 自增 id 之类）。
VOLATILE_KEYS = frozenset(
    {
        "created_at",
        "updated_at",
        "timestamp",
        "last_completed_at",
        "last_drawn_at",
        "next_available_at",
        "started_at",
        "ended_at",
        "date",
    }
)

#: 采集器（跑在合成根内）的源码。
_COLLECTOR = r'''
"""Golden HTTP snapshot collector — runs inside the synthetic root."""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app

VOLATILE = {
    "created_at", "updated_at", "timestamp", "last_completed_at",
    "last_drawn_at", "next_available_at", "started_at", "ended_at", "date",
    "exported_at",
    "port",
}


def make_cfg(db):
    return {
        "server": {"host": "127.0.0.1", "port": 0, "debug": False},
        "obsidian": {"vault_path": "vault", "notes_directory": "vault"},
        "api": {"openai_api_key": "", "claude_api_key": ""},
        "database": {"task_db_path": str(Path(db).relative_to(root))},
        "_project_root": str(root),
        "_static_dir": str(root / "static"),
        "_db_path": str(db),
        "_notes_dir": str(root / "vault"),
        "_config_path": str(root / "config" / "config.json"),
    }


def strip_volatile(value):
    """Recursively drop volatile keys so snapshots compare structurally."""
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
    """Return a deterministic digest of a table's rows (excluding volatile cols)."""
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
            value = row[key]
            if isinstance(value, bytes):
                value = repr(value)
            item[key] = value
        out.append(item)
    out.sort(key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
    return out


def snapshot_tables(conn, tables):
    return {t: table_digest(conn, t) for t in tables}


def main():
    # 抽卡是 **随机** 的 —— 固定随机种子，保证快照可复现。
    import random
    random.seed(20260121)

    db = root / "data" / "golden.sqlite3"
    if db.exists():
        db.unlink()
    app = create_app(make_cfg(db))
    client = app.test_client()

    cases = []
    out_file = root / "_golden_snapshot.json"

    def record(name, method, path, body=None, query=None, tables=()):
        """Execute one request and capture status + body + DB side effects."""
        url = path
        if query:
            from urllib.parse import urlencode
            url = path + "?" + urlencode(query)
        kwargs = {}
        if body is not None:
            kwargs["json"] = body
        resp = getattr(client, method.lower())(url, **kwargs)
        try:
            payload = resp.get_json(force=True)
        except Exception:
            payload = None
        entry = {
            "name": name,
            "method": method.upper(),
            "path": path,
            "query": query or {},
            "status": resp.status_code,
            "json": strip_volatile(payload),
        }
        if tables:
            conn = sqlite3.connect(str(db))
            try:
                conn.row_factory = sqlite3.Row
                entry["side_effects"] = snapshot_tables(conn, tables)
            finally:
                conn.close()
        cases.append(entry)
        return entry

    # ---------------- 前置：造一些可用的合成数据 ----------------------
    record("create_task_a", "POST", "/api/tasks",
           {"name": "GOLDEN_TASK_A", "category": "study",
            "estimated_time": 25, "priority": 5},
           tables=["tasks"])
    record("create_task_b", "POST", "/api/tasks",
           {"name": "GOLDEN_TASK_B", "category": "study",
            "estimated_time": 30, "priority": 6},
           tables=["tasks"])
    record("create_tag", "POST", "/api/tags", {"name": "goldentag"},
           tables=["tags", "task_tags"])

    # ---------------- health -------------------------------------------
    record("health", "GET", "/api/health")

    # ---------------- tasks --------------------------------------------
    record("list_tasks", "GET", "/api/tasks", query={"unlocked_only": "false"},
           tables=["tasks"])
    record("list_tasks_completed", "GET", "/api/tasks",
           query={"unlocked_only": "false", "include_completed": "true"})
    record("get_task_missing", "GET", "/api/tasks/999999")
    record("get_task_missing_dependents", "GET", "/api/tasks/999999/dependents")
    record("create_task_no_name", "POST", "/api/tasks", {"category": "study"})
    record("create_task_cycle", "POST", "/api/tasks",
           {"name": "CYCLE", "prerequisite_ids": [999999]})
    record("update_task_missing", "PUT", "/api/tasks/999999", {"name": "X"})
    record("delete_task_missing", "DELETE", "/api/tasks/999999")
    record("complete_task_missing", "POST", "/api/tasks/999999/complete")
    record("skip_task_missing", "POST", "/api/tasks/999999/skip")
    record("refuse_task_missing", "POST", "/api/tasks/999999/refuse")

    # ---------------- tags ---------------------------------------------
    record("list_tags", "GET", "/api/tags", tables=["tags", "task_tags"])
    record("create_tag_dup", "POST", "/api/tags", {"name": "goldentag"})
    record("create_tag_missing_name", "POST", "/api/tags", {})
    record("delete_tag_missing", "DELETE", "/api/tags/999999")
    record("tags_batch", "POST", "/api/tags/batch", {"names": ["batch1", "batch2"]},
           tables=["tags"])

    # ---------------- gacha --------------------------------------------
    record("gacha_pools", "GET", "/api/gacha/pools")
    record("gacha_pools_detail", "GET", "/api/gacha/pools/detail")
    record("gacha_statistics", "GET", "/api/gacha/statistics")
    record("gacha_draw_empty", "POST", "/api/gacha/draw", {})
    record("gacha_care_draw", "POST", "/api/gacha/care-draw", {})
    record("gacha_replace_missing", "POST", "/api/gacha/replace",
           {"task_id": 999999})

    # ---------------- discard / dependencies --------------------------
    record("discard_pile", "GET", "/api/discard-pile", tables=["tasks"])
    record("discard_restore_missing", "POST",
           "/api/discard-pile/999999/restore")
    record("move_to_discard_missing", "POST",
           "/api/tasks/999999/move-to-discard")
    record("dependencies", "GET", "/api/dependencies")

    # ---------------- config / export ---------------------------------
    record("config_get", "GET", "/api/config")
    record("export", "GET", "/api/export")

    # ---------------- agent / prompts ----------------------------------
    record("agent_agents", "GET", "/api/agent/agents")
    record("agent_files_raw", "GET", "/api/agent/files/raw")
    record("agent_files_vault", "GET", "/api/agent/files/vault")
    record("agent_save_note_blocked", "POST", "/api/agent/save-note",
           {"note_path": "x.md", "content": "y"})
    record("prompts_list", "GET", "/api/prompts")
    record("prompt_get_missing", "GET", "/api/prompts/does-not-exist.md")

    # ---------------- state / timer / schedule / knowledge / feedback ---
    record("state_daily_tone", "GET", "/api/state/daily-tone")
    record("state_sleep", "GET", "/api/state/sleep")
    record("state_weekly_energy", "GET", "/api/state/weekly-energy")
    record("timer_active", "GET", "/api/timer/active")
    record("schedule_slots", "GET", "/api/schedule/slots")
    record("schedule_weekly", "GET", "/api/schedule/weekly")
    record("schedule_daily", "GET", "/api/schedule/daily")
    record("schedule_activities", "GET", "/api/schedule/activities")
    record("knowledge_categories", "GET", "/api/knowledge/categories")
    record("knowledge_notes", "GET", "/api/knowledge/notes")
    record("knowledge_points", "GET", "/api/knowledge/points")
    record("knowledge_recent", "GET", "/api/knowledge/recent")
    record("feedback_list", "GET", "/api/task-feedback")

    # ---------------- 写出结果到文件（避免 stdout 编码问题） --------------
    out_file.write_text(
        json.dumps({"cases": cases}, ensure_ascii=False),
        encoding="utf-8",
    )
    print("SNAPSHOT_FILE=" + str(out_file))
    print("SNAPSHOT_DONE")


main()
'''


def _run_collector() -> Dict[str, Any]:
    """在合成根内运行采集器，返回 ``{"cases": [...]}``。"""
    sys.path.insert(0, str(CHARACTERIZE_DIR))
    from sandbox_env import available_port, materialize, seed

    with tempfile.TemporaryDirectory(prefix="lt_golden_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        collector = root / "_golden_collector.py"
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
            cwd=root,
            env=env,
            capture_output=True,
            timeout=180,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
            raise RuntimeError("黄金快照采集器失败: " + stderr[-4000:])
        stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
        lines = [ln for ln in stdout.splitlines() if ln.startswith("SNAPSHOT_FILE=")]
        if len(lines) != 1:
            raise RuntimeError("未捕获 SNAPSHOT_FILE: " + stdout[-4000:])
        out_path = Path(lines[0][len("SNAPSHOT_FILE=") :].strip())
        if not out_path.is_file():
            raise RuntimeError("采集结果文件缺失: " + str(out_path))
        return json.loads(out_path.read_text(encoding="utf-8"))


def _index(cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {case["name"]: case for case in cases}


def compare(frozen: Dict[str, Any], live: Dict[str, Any]) -> List[str]:
    """比对冻结快照与当前实现的差异，返回差异描述列表（空 = 完全一致）。"""
    problems: List[str] = []
    frozen_index = _index(frozen.get("cases", []))
    live_index = _index(live.get("cases", []))

    missing = sorted(set(frozen_index) - set(live_index))
    extra = sorted(set(live_index) - set(frozen_index))
    for name in missing:
        problems.append("用例缺失: " + name)
    for name in extra:
        problems.append("用例新增（需同步冻结快照并复核）: " + name)

    for name in sorted(set(frozen_index) & set(live_index)):
        expected = frozen_index[name]
        actual = live_index[name]
        if expected["status"] != actual["status"]:
            problems.append(
                "{}: 状态码 {} → {}".format(
                    name, expected["status"], actual["status"]
                )
            )
        if expected["json"] != actual["json"]:
            problems.append(
                "{}: 响应体变化\n  frozen={}\n  live  ={}".format(
                    name,
                    json.dumps(expected["json"], ensure_ascii=False)[:600],
                    json.dumps(actual["json"], ensure_ascii=False)[:600],
                )
            )
        if expected.get("side_effects") != actual.get("side_effects"):
            problems.append(
                "{}: 副作用（DB 状态）变化\n  frozen={}\n  live  ={}".format(
                    name,
                    json.dumps(expected.get("side_effects"), ensure_ascii=False)[:600],
                    json.dumps(actual.get("side_effects"), ensure_ascii=False)[:600],
                )
            )
    return problems


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="黄金 HTTP 快照 oracle")
    parser.add_argument("--write", action="store_true", help="写入冻结快照")
    parser.add_argument("--check", action="store_true", help="与冻结快照比对")
    args = parser.parse_args(argv[1:])

    live = _run_collector()

    if args.write:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(
            json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("WROTE " + str(SNAPSHOT_PATH))
        print("cases=" + str(len(live.get("cases", []))))
        return 0

    if args.check:
        if not SNAPSHOT_PATH.is_file():
            print("MISSING " + str(SNAPSHOT_PATH), file=sys.stderr)
            return 1
        frozen = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        problems = compare(frozen, live)
        if problems:
            print("DRIFT " + str(SNAPSHOT_PATH), file=sys.stderr)
            for problem in problems:
                print("  - " + problem, file=sys.stderr)
            return 1
        print("OK " + str(SNAPSHOT_PATH))
        print("cases=" + str(len(live.get("cases", []))))
        return 0

    print(json.dumps(live, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
