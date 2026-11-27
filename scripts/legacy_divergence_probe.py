"""scripts/legacy_divergence_probe.py — 实测 **实时 Factory** 与 **冻结 legacy 基线** 的行为差异。

背景（AR03-P2 / Stage 1 → Stage 7）
-----------------------------------
``server/backend_api.py`` 与 Blueprint 长期并存，**同一 URL 在两侧的实现在
部分路由上并不一致**。生产默认运行时是 Factory，但 21 条兼容桥路由在
迁移前 **只由 legacy 提供** —— 因此只以 Factory 黄金快照为 oracle 会留下
功能保全的真空区。

Stage 1 时本脚本在 **同一个合成根** 里分别启动 legacy 与 Factory 两个
服务，对每条 legacy 路由执行 **相同的请求**，逐条比对：

* HTTP 状态码
* 响应体（结构化，忽略时间戳等易变字段）
* 副作用（受影响表的行数 + 内容摘要）

Stage 7 的变化
--------------
legacy 单体被收口成 **薄别名**（委托 ``create_app()``），**不再持有任何
Flask 路由** —— "现场跑 legacy" 的取数方式随之失效。而且 legacy 已被
判定为"历史残留"（见台账权威判定规则 R1），继续跑它既无意义也会让
探针失去鉴别力。

因此本脚本改为：

* **legacy 侧** → 读取 **冻结基线** ``tests/fixtures/legacy_baseline.json``
  （Stage 1 一次性采集的 legacy 实测观测值，见
  :mod:`scripts.legacy_baseline`）；
* **Factory 侧** → 在合成根里 **实时** 跑 ``create_app()``；
* 逐条比对，产出与 Stage 1 **同口径** 的差异清单。

这样探针在 legacy 收口后仍然具备鉴别力：任何迁移回归都会让实时
Factory 与冻结基线产生新的差异。

用法
----
::

    python scripts/legacy_divergence_probe.py            # 打印 JSON
    python scripts/legacy_divergence_probe.py --write    # 写冻结差异清单
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
OUTPUT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "legacy_divergence.json"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

#: 采集器源码（跑在合成根内）。
_COLLECTOR = r'''
"""Observe the live Factory (Blueprint/Service/Repository) route by route."""
import json
import sqlite3
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app

VOLATILE = {
    "created_at", "updated_at", "timestamp", "last_completed_at",
    "last_drawn_at", "next_available_at", "started_at", "ended_at",
    "date", "exported_at", "port",
}

#: (name, method, path, body, query, tables)
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


def main():
    import random
    # 抽卡是 **随机** 的 —— 固定种子，保证每次采集抽到同一张卡，
    # 否则比对结果会被随机性污染。
    random.seed(20260121)

    db = root / "data" / "factory.sqlite3"
    if db.exists():
        db.unlink()

    app = create_app(make_cfg(db))
    client = app.test_client()
    results = []
    for name, method, path, body, query, tables in CASES:
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

    out_file = root / "_probe_factory.json"
    out_file.write_text(
        json.dumps({"results": results}, ensure_ascii=False), encoding="utf-8"
    )
    print("PROBE_FILE=" + str(out_file))


main()
'''


def _run(root: Path) -> List[Dict[str, Any]]:
    """在合成根里实时采集 Factory 的观测值。"""
    sys.path.insert(0, str(CHARACTERIZE_DIR))
    from sandbox_env import available_port, materialize, seed

    with tempfile.TemporaryDirectory(prefix="lt_divergence_") as temp:
        sandbox = materialize(Path(temp) / "sandbox", available_port())
        seed(sandbox)
        collector = sandbox / "_divergence_probe.py"
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
            raise RuntimeError("差异探针失败 (factory): " + stderr[-4000:])
        stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
        lines = [
            ln for ln in stdout.splitlines() if ln.startswith("PROBE_FILE=")
        ]
        if len(lines) != 1:
            raise RuntimeError("未捕获 PROBE_FILE: " + stdout[-4000:])
        path = Path(lines[0][len("PROBE_FILE=") :].strip())
        return json.loads(path.read_text(encoding="utf-8"))["results"]


def _index(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {item["name"]: item for item in results}


def build_divergence() -> Dict[str, Any]:
    """实时 Factory 与冻结 legacy 基线逐条比对。"""
    from legacy_baseline import baseline_index

    legacy_index = baseline_index()
    factory_index = _index(_run(PROJECT_ROOT))

    entries: List[Dict[str, Any]] = []
    for name, legacy_item in legacy_index.items():
        factory_item = factory_index.get(name)
        if factory_item is None:
            entries.append(
                {
                    "name": name,
                    "method": legacy_item["method"],
                    "path": legacy_item["path"],
                    "verdict": "factory_missing",
                    "status_legacy": legacy_item.get("status"),
                    "status_factory": None,
                    "body_differs": None,
                    "side_effects_differ": None,
                }
            )
            continue
        body_differs = legacy_item.get("json") != factory_item.get("json")
        effects_differ = legacy_item.get("side_effects") != factory_item.get(
            "side_effects"
        )
        status_differs = legacy_item.get("status") != factory_item.get("status")
        entries.append(
            {
                "name": name,
                "method": legacy_item["method"],
                "path": legacy_item["path"],
                "verdict": (
                    "identical"
                    if not (status_differs or body_differs or effects_differ)
                    else "divergent"
                ),
                "status_legacy": legacy_item.get("status"),
                "status_factory": factory_item.get("status"),
                "body_differs": body_differs,
                "side_effects_differ": effects_differ,
                "legacy_json": legacy_item.get("json"),
                "factory_json": factory_item.get("json"),
            }
        )

    divergent = [e for e in entries if e["verdict"] != "identical"]
    return {
        "schema_version": 2,
        "generated_by": "scripts/legacy_divergence_probe.py",
        "legacy_baseline": "tests/fixtures/legacy_baseline.json",
        "total_cases": len(entries),
        "identical_count": len(entries) - len(divergent),
        "divergent_count": len(divergent),
        "entries": entries,
    }


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="实时 Factory vs 冻结 legacy 基线 的行为差异探针"
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv[1:])

    divergence = build_divergence()

    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
            json.dumps(divergence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("WROTE " + str(OUTPUT_PATH))
        print(
            "total={} identical={} divergent={}".format(
                divergence["total_cases"],
                divergence["identical_count"],
                divergence["divergent_count"],
            )
        )
        return 0

    print(json.dumps(divergence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
