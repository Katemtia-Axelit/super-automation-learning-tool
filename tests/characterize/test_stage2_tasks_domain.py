"""AR03-P2 / Stage 2 — 任务 / 标签 / 弃牌 域的 **分层契约** 测试。

Stage 2 把任务域从"蓝图里塞着业务逻辑 + SQL"重构成三层：

* ``server/blueprints/*_bp.py`` —— **只** 是 HTTP 边界；
* ``server/services/{tasks,tags,discard}.py`` —— 业务编排；
* ``server/repositories/{task_repo,tags_repo,discard_repo}.py`` —— SQL。

本文件机械校验这个分层契约：

1. **方向单向** —— service 不 import blueprint；repository 不 import
   service / blueprint / legacy 单体；
2. **蓝图瘦身** —— 蓝图里 **不再有** 裸 SQL（``execute(`` / ``SELECT`` /
   ``INSERT`` / ``UPDATE`` / ``DELETE``）；
3. **service 不写 SQL** —— service 里没有裸 SQL 语句；
4. **连接统一** —— 蓝图只通过 ``server.repositories.db`` 开连接；
5. **卡类型词表单一权威** —— service 层是唯一定义处，其它模块从那里 import；
6. **行为不回归** —— 关键业务规则（解锁、循环依赖、周期恢复、弃牌幂等）
   在合成库上逐条断言。

全程 **不** 触碰生产数据库：全部在 ``tests/characterize/sandbox_env.py``
的合成根内。
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BLUEPRINT_DIR = PROJECT_ROOT / "server" / "blueprints"
SERVICE_DIR = PROJECT_ROOT / "server" / "services"
REPO_DIR = PROJECT_ROOT / "server" / "repositories"

#: Stage 2 迁完的三个域的蓝图。
STAGE2_BLUEPRINTS = ("tasks_bp.py", "tags_bp.py", "discard_bp.py")

#: Stage 2 新建/重写的 service 与 repository 文件（分层契约只约束这些）。
STAGE2_SERVICES = ("tasks.py", "tags.py", "discard.py")
STAGE2_REPOSITORIES = ("task_repo.py", "tags_repo.py", "discard_repo.py", "db.py")

#: 裸 SQL 特征（用于静态扫描）。
_SQL_MARKERS = (
    "SELECT ",
    "INSERT INTO",
    "INSERT OR",
    "UPDATE ",
    "DELETE FROM",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments_and_docstrings(source: str) -> str:
    """去掉注释与字符串字面量，只留 **可执行代码**。

    这样扫描裸 SQL 时不会误报文档字符串里出现的 ``SELECT`` 字样。
    """
    import io
    import tokenize

    out = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(token.string)
    except (tokenize.TokenError, IndentationError):
        return source
    return " ".join(out)


class LayeringDirectionTests(unittest.TestCase):
    """1. 依赖方向单向。"""

    def test_services_do_not_import_blueprints(self):
        """Stage 2 新写的 service 不得 import 蓝图。"""
        offenders = []
        for name in STAGE2_SERVICES:
            text = _read(SERVICE_DIR / name)
            if "server.blueprints" in text:
                offenders.append(name)
        self.assertFalse(
            offenders, "service 层 import 了蓝图: " + ", ".join(offenders)
        )

    def test_repositories_do_not_import_services_or_blueprints(self):
        """Stage 2 新写的 repository 不得依赖 service / blueprint / Flask。

        只看 **可执行代码**（排除注释与文档字符串里的说明文字）。
        """
        offenders = []
        for name in STAGE2_REPOSITORIES:
            code = _strip_comments_and_docstrings(_read(REPO_DIR / name))
            for forbidden in (
                "server.services",
                "server.blueprints",
                "from flask",
                "import flask",
            ):
                if forbidden in code:
                    offenders.append(name + " -> " + forbidden)
        self.assertFalse(
            offenders, "repository 层依赖越界: " + ", ".join(offenders)
        )

    def test_repositories_do_not_import_legacy_monolith(self):
        """Stage 2 新写的 repository 不得 import legacy 单体。"""
        offenders = []
        for name in STAGE2_REPOSITORIES:
            code = _strip_comments_and_docstrings(_read(REPO_DIR / name))
            if "server.backend_api" in code:
                offenders.append(name)
        self.assertFalse(
            offenders, "repository 层仍 import legacy 单体: " + ", ".join(offenders)
        )

    def test_stage2_blueprints_do_not_open_connections(self):
        """蓝图 **不再** 开连接 —— 事务边界下沉到 Service。

        AR03-P2 / P2 收尾修正了 Stage 2 的这条契约。

        Stage 2 当时要求"蓝图只通过 ``server.repositories.db`` 开连接"
        （蓝图持有事务边界）。P2 收尾把事务边界 **下沉到 Service**
        （``server.repositories.db.service_transaction``），因此蓝图
        **彻底不碰数据库连接**：

        * 蓝图里 **不得** 出现 ``read_connection()`` /
          ``write_connection()`` / ``sqlite3.connect(``；
        * 蓝图里 **不得** import ``server.repositories.db``（它不需要它了）。

        只读蓝图（``config_bp``）**同样**适用 —— 规则统一，没有例外。
        """
        for name in STAGE2_BLUEPRINTS:
            text = _read(BLUEPRINT_DIR / name)
            code = _strip_comments_and_docstrings(text)
            self.assertNotIn(
                "read_connection", code, name + " 仍在开只读连接"
            )
            self.assertNotIn(
                "write_connection", code, name + " 仍在开读写连接"
            )
            self.assertNotIn("sqlite3.connect(", code, name + " 自己开了连接")
            self.assertNotIn(
                "server.repositories.db",
                code,
                name + " 不应再直接依赖 repo 连接助手（事务边界已下沉到 Service）",
            )


class BlueprintSlimmingTests(unittest.TestCase):
    """2. 蓝图里不再有裸 SQL。"""

    def test_stage2_blueprints_have_no_raw_sql(self):
        for name in STAGE2_BLUEPRINTS:
            code = _strip_comments_and_docstrings(_read(BLUEPRINT_DIR / name))
            for marker in _SQL_MARKERS:
                self.assertNotIn(
                    marker,
                    code,
                    name + " 仍含裸 SQL 特征: " + marker,
                )
            self.assertNotIn(".execute(", code, name + " 直接执行 SQL")

    def test_tasks_blueprint_delegates_to_service(self):
        text = _read(BLUEPRINT_DIR / "tasks_bp.py")
        self.assertIn("from server.services import tasks as tasks_service", text)

    def test_tags_blueprint_delegates_to_service(self):
        text = _read(BLUEPRINT_DIR / "tags_bp.py")
        self.assertIn("from server.services import tags as tags_service", text)

    def test_discard_blueprint_delegates_to_service(self):
        text = _read(BLUEPRINT_DIR / "discard_bp.py")
        self.assertIn("from server.services import discard as discard_service", text)


class ServiceHasNoRawSqlTests(unittest.TestCase):
    """3. service 层不写 SQL。"""

    def test_stage2_services_have_no_raw_sql(self):
        for name in STAGE2_SERVICES:
            code = _strip_comments_and_docstrings(_read(SERVICE_DIR / name))
            for marker in _SQL_MARKERS:
                self.assertNotIn(
                    marker,
                    code,
                    "service/" + name + " 含裸 SQL: " + marker,
                )
            self.assertNotIn(".execute(", code, "service/" + name + " 直接执行 SQL")


class CardTypeSingleAuthorityTests(unittest.TestCase):
    """5. 卡类型词表单一权威。"""

    def test_card_type_vocabulary_defined_only_in_service(self):
        service_text = _read(SERVICE_DIR / "tasks.py")
        self.assertIn("CARD_TYPES = (", service_text)
        self.assertIn("def normalize_card_type", service_text)
        self.assertIn("def validate_task_type", service_text)

    def test_gacha_blueprint_imports_card_type_from_service(self):
        text = _read(BLUEPRINT_DIR / "gacha_bp.py")
        self.assertIn("from server.services.tasks import", text)
        self.assertNotIn("from server.blueprints.tasks_bp import", text)

    def test_tasks_blueprint_reexports_card_type_from_service(self):
        """蓝图可以 re-export（向后兼容），但不得 **重新定义** 词表。"""
        text = _read(BLUEPRINT_DIR / "tasks_bp.py")
        self.assertNotIn("CARD_TYPES = (", text)
        self.assertIn("tasks_service.CARD_TYPES", text)


_RUNNER = r'''
import json, sqlite3, sys
from datetime import datetime, timedelta
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app
from server.repositories.db import write_connection
from server.services import discard as discard_service
from server.services import tasks as tasks_service

db = root / "data" / "stage2.sqlite3"
if db.exists():
    db.unlink()

def make_cfg():
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

app = create_app(make_cfg())
client = app.test_client()
out = {}

# ---- 1. 解锁：完成前置任务后，依赖者被解锁 ------------------------------
r = client.post("/api/tasks", json={"name": "PREREQ", "category": "study"})
out["prereq_status"] = r.status_code
prereq_id = r.get_json(force=True)["id"]
r = client.post(
    "/api/tasks",
    json={"name": "DEPENDENT", "category": "study", "prerequisite_ids": [prereq_id]},
)
out["dependent_status"] = r.status_code
dependent_id = r.get_json(force=True)["id"]

listing = client.get("/api/tasks?unlocked_only=true").get_json(force=True)
out["dependent_locked_initially"] = dependent_id not in [
    t["id"] for t in listing
]

r = client.post(f"/api/tasks/{prereq_id}/complete")
body = r.get_json(force=True)
out["complete_status"] = r.status_code
out["unlocked_tasks"] = body.get("unlocked_tasks")
out["dependent_now_unlocked"] = dependent_id in [
    t["id"] for t in client.get("/api/tasks?unlocked_only=true").get_json(force=True)
]

# ---- 2. 循环依赖被拒绝，且零副作用 --------------------------------------
before = len(client.get("/api/tasks?unlocked_only=false").get_json(force=True))
r = client.put(
    f"/api/tasks/{dependent_id}",
    json={"prerequisite_ids": [dependent_id]},
)
out["cycle_status"] = r.status_code
out["cycle_error"] = r.get_json(force=True).get("error")
after = len(client.get("/api/tasks?unlocked_only=false").get_json(force=True))
out["cycle_no_side_effect"] = (before == after)

# ---- 3. 卡类型：非法值 400 且零写入 --------------------------------------
before = len(client.get("/api/tasks?unlocked_only=false").get_json(force=True))
r = client.post("/api/tasks", json={"name": "BAD_TYPE", "task_type": "FREE"})
out["bad_card_type_status"] = r.status_code
after = len(client.get("/api/tasks?unlocked_only=false").get_json(force=True))
out["bad_card_type_no_write"] = (before == after)

r = client.post("/api/tasks", json={"name": "GOOD_TYPE", "task_type": "goal"})
out["good_card_type_status"] = r.status_code

# ---- 4. 依赖图 ------------------------------------------------------------
graph = client.get("/api/dependencies").get_json(force=True)
out["graph_has_nodes"] = len(graph.get("nodes", [])) > 0
out["graph_has_edges"] = any(
    e.get("from") == prereq_id and e.get("to") == dependent_id
    for e in graph.get("edges", [])
)

# ---- 5. 标签：重名返回 200 ------------------------------------------------
r = client.post("/api/tags", json={"name": "dup"})
out["tag_first_status"] = r.status_code
r = client.post("/api/tags", json={"name": "dup"})
out["tag_dup_status"] = r.status_code
r = client.post("/api/tags", json={"name": "  "})
out["tag_empty_status"] = r.status_code

# ---- 6. 弃牌：手动弃牌 + 恢复 --------------------------------------------
r = client.post(f"/api/tasks/{dependent_id}/move-to-discard")
out["move_to_discard_status"] = r.status_code
pile = client.get("/api/discard-pile").get_json(force=True)
out["in_pile"] = dependent_id in [t["id"] for t in pile]
r = client.post(f"/api/discard-pile/{dependent_id}/restore")
out["restore_status"] = r.status_code
pile = client.get("/api/discard-pile").get_json(force=True)
out["restored_out_of_pile"] = dependent_id not in [t["id"] for t in pile]

# ---- 7. 弃牌幂等：已完成任务重复移入不重复计数 ----------------------------
with write_connection() as conn:
    conn.execute(
        "UPDATE tasks SET completed=1, completed_count=0, repeat_type='daily' "
        "WHERE id=?", (prereq_id,)
    )
with write_connection() as conn:
    discard_service.move_to_discard(conn, prereq_id)
with write_connection() as conn:
    row = conn.execute(
        "SELECT completed_count FROM tasks WHERE id=?", (prereq_id,)
    ).fetchone()
    out["completed_count_first"] = row["completed_count"]
with write_connection() as conn:
    discard_service.move_to_discard(conn, prereq_id)
with write_connection() as conn:
    row = conn.execute(
        "SELECT completed_count FROM tasks WHERE id=?", (prereq_id,)
    ).fetchone()
    out["completed_count_second"] = row["completed_count"]

# ---- 8. 周期回收：daily 已到期 → 自动恢复 --------------------------------
# 用 **固定的过去时间** 构造到期状态，避免依赖真实当前时间。
with write_connection() as conn:
    conn.execute(
        "UPDATE tasks SET completed=1, in_discard_pile=1, repeat_type='daily', "
        "last_completed_at='2026-01-01T10:00:00', "
        "next_available_at='2026-01-02T00:00:00' WHERE id=?", (prereq_id,)
    )
with write_connection() as conn:
    result = discard_service.recover_discard_cycle(
        conn, datetime(2026, 1, 2, 12, 0, 0)
    )
    out["recover_result"] = result

with write_connection() as conn:
    row = conn.execute(
        "SELECT completed, in_discard_pile, next_available_at, completed_count "
        "FROM tasks WHERE id=?", (prereq_id,)
    ).fetchone()
    out["recovered_completed"] = row["completed"]
    out["recovered_in_pile"] = row["in_discard_pile"]
    out["recovered_next_available"] = row["next_available_at"]
    out["recovered_completed_count_unchanged"] = row["completed_count"]

# ---- 9. 周期未到期不恢复 --------------------------------------------------
with write_connection() as conn:
    conn.execute(
        "UPDATE tasks SET completed=1, in_discard_pile=1, repeat_type='daily', "
        "last_completed_at='2026-01-01T10:00:00', "
        "next_available_at='2026-01-05T00:00:00' WHERE id=?", (dependent_id,)
    )
with write_connection() as conn:
    result = discard_service.recover_discard_cycle(
        conn, datetime(2026, 1, 2, 12, 0, 0)
    )
    out["recover_not_due_result"] = result
with write_connection() as conn:
    row = conn.execute(
        "SELECT in_discard_pile FROM tasks WHERE id=?", (dependent_id,)
    ).fetchone()
    out["not_due_stays_in_pile"] = bool(row["in_discard_pile"])

# ---- 10. 一次性（非周期）已完成任务不自动恢复 ----------------------------
with write_connection() as conn:
    conn.execute(
        "UPDATE tasks SET completed=1, in_discard_pile=1, repeat_type='none', "
        "last_completed_at='2026-01-01T10:00:00', next_available_at=NULL "
        "WHERE id=?", (prereq_id,)
    )
with write_connection() as conn:
    result = discard_service.recover_discard_cycle(
        conn, datetime(2026, 1, 2, 12, 0, 0)
    )
    out["recover_nonrecurring_result"] = result
with write_connection() as conn:
    row = conn.execute(
        "SELECT in_discard_pile, completed FROM tasks WHERE id=?", (prereq_id,)
    ).fetchone()
    out["nonrecurring_stays_in_pile"] = bool(row["in_discard_pile"])
    out["nonrecurring_stays_completed"] = bool(row["completed"])

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    import json

    with TemporaryDirectory(prefix="lt_stage2_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_stage2_probe.py"
        runner.write_text(_RUNNER, encoding="utf-8")
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
            [sys.executable, "-I", str(runner)],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        if proc.returncode != 0:
            raise AssertionError(f"probe 退出码非0: {proc.stderr[-3000:]}")
        lines = [
            ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON=")
        ]
        if len(lines) != 1:
            raise AssertionError(f"未捕获 PROBE_JSON: {proc.stdout[-3000:]}")
        return json.loads(lines[0][len("PROBE_JSON=") :])


class TaskDomainBehaviorTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_dependent_is_locked_until_prereq_completed(self):
        p = self.PROBE
        self.assertTrue(p["dependent_locked_initially"], p)
        self.assertTrue(p["dependent_now_unlocked"], p)
        self.assertIn("DEPENDENT", p["unlocked_tasks"], p)

    def test_cycle_is_rejected_without_side_effects(self):
        p = self.PROBE
        self.assertEqual(p["cycle_status"], 400, p)
        self.assertTrue(p["cycle_no_side_effect"], p)

    def test_invalid_card_type_rejected_without_write(self):
        p = self.PROBE
        self.assertEqual(p["bad_card_type_status"], 400, p)
        self.assertTrue(p["bad_card_type_no_write"], p)
        self.assertEqual(p["good_card_type_status"], 201, p)

    def test_dependency_graph_contains_edge(self):
        p = self.PROBE
        self.assertTrue(p["graph_has_nodes"], p)
        self.assertTrue(p["graph_has_edges"], p)

    def test_tag_duplicate_returns_200_not_201(self):
        p = self.PROBE
        self.assertEqual(p["tag_first_status"], 201, p)
        self.assertEqual(p["tag_dup_status"], 200, p)
        self.assertEqual(p["tag_empty_status"], 400, p)

    def test_discard_roundtrip(self):
        p = self.PROBE
        self.assertEqual(p["move_to_discard_status"], 200, p)
        self.assertTrue(p["in_pile"], p)
        self.assertEqual(p["restore_status"], 200, p)
        self.assertTrue(p["restored_out_of_pile"], p)

    def test_discard_count_is_idempotent(self):
        p = self.PROBE
        self.assertEqual(p["completed_count_first"], 1, p)
        self.assertEqual(p["completed_count_second"], 1, p)

    def test_daily_cycle_recovers_when_due(self):
        p = self.PROBE
        self.assertEqual(p["recover_result"]["completed_restored"], 1, p)
        self.assertEqual(p["recovered_completed"], 0, p)
        self.assertEqual(p["recovered_in_pile"], 0, p)
        self.assertIsNone(p["recovered_next_available"], p)
        # 恢复 **绝不** 改写 completed_count / last_completed_at
        self.assertEqual(p["recovered_completed_count_unchanged"], 1, p)

    def test_cycle_not_due_is_not_recovered(self):
        p = self.PROBE
        self.assertEqual(p["recover_not_due_result"]["completed_restored"], 0, p)
        self.assertTrue(p["not_due_stays_in_pile"], p)

    def test_non_recurring_completed_task_is_not_auto_recovered(self):
        """一次性任务不自动恢复（fail-closed），保持完成状态。"""
        p = self.PROBE
        self.assertEqual(
            p["recover_nonrecurring_result"]["completed_restored"], 0, p
        )
        self.assertTrue(p["nonrecurring_stays_in_pile"], p)
        self.assertTrue(p["nonrecurring_stays_completed"], p)


if __name__ == "__main__":
    unittest.main()
