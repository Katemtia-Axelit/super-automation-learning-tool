"""AR03-P2 / P2 收尾 — Blueprint 事务边界的 **机械契约** 测试。

背景
----
Stage 2 把蓝图"瘦身"为纯 HTTP 层时，**事务边界仍留在 Blueprint**：
``with read_connection()/write_connection() as conn:`` 写在蓝图里，
Service 只在给定连接上工作。

P2 收尾把事务边界 **下沉到 Service**：

* :func:`server.repositories.db.service_transaction` 是新的唯一入口
  （自行开连接 → Service 在 **同一连接** 上完成全部 repo 调用 →
  Service 决定提交 / 回滚）；
* **全部 14 个蓝图**都不再直接开连接（包括只读的 ``config_bp``）——
  规则统一，**没有"只读可以例外"的特例**；
* Blueprint 退化为「解析请求 → 调 Service → 组装响应」。

本文件机械校验这条契约，并断言 **行为不回归**（事务原子性、提交时机、
只读不写、异常回滚）。

全程 **不** 触碰生产数据库：全部在 ``tests/characterize/sandbox_env.py``
的合成根内。
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tokenize
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BP_DIR = PROJECT_ROOT / "server" / "blueprints"
SERVICE_DIR = PROJECT_ROOT / "server" / "services"
REPO_DIR = PROJECT_ROOT / "server" / "repositories"

#: 全部真蓝图（app_factory 注册的 14 个 + 不在 app_factory 里的也在此列）。
#:
#: 断言覆盖 **全部** 蓝图文件，而不是只挑几个 —— 规则统一，不留特例。
ALL_BLUEPRINTS = sorted(p.name for p in BP_DIR.glob("*_bp.py"))

#: 需要数据库连接语义的蓝图（纯文件系统的 ``knowledge_bp`` 除外）。
DB_BLUEPRINTS = tuple(
    name for name in ALL_BLUEPRINTS if name != "knowledge_bp.py"
)


def _code_only(path: Path) -> str:
    """去掉注释与字符串字面量，只留可执行代码（避免 docstring 误报）。"""
    out = []
    try:
        tokens = tokenize.generate_tokens(
            io.StringIO(path.read_text(encoding="utf-8")).readline
        )
        for token in tokens:
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(token.string)
    except (tokenize.TokenError, IndentationError):
        return path.read_text(encoding="utf-8")
    return " ".join(out)


class BlueprintNoConnectionTests(unittest.TestCase):
    """1. 蓝图 **不** 直接开连接（事务边界下沉到 Service）。"""

    def test_at_least_fourteen_blueprints_exist(self):
        """守卫：蓝图数量不得意外缩水（契约覆盖面随之缩小）。"""
        self.assertGreaterEqual(
            len(ALL_BLUEPRINTS),
            14,
            "蓝图数量少于 14 个：" + ", ".join(ALL_BLUEPRINTS),
        )

    def test_no_blueprint_opens_read_connection(self):
        """没有任何蓝图直接 ``with read_connection()``。

        **包括只读蓝图**（``config_bp``）—— 只读没有事务边界争议，
        但规则统一更重要，不允许并存两种风格。
        """
        offenders = []
        for name in ALL_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            if "read_connection" in code:
                offenders.append(name)
        self.assertFalse(
            offenders,
            "蓝图仍在开只读连接（事务边界必须下沉到 Service）: "
            + ", ".join(offenders),
        )

    def test_no_blueprint_opens_write_connection(self):
        """没有任何蓝图直接 ``with write_connection()``。"""
        offenders = []
        for name in ALL_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            if "write_connection" in code:
                offenders.append(name)
        self.assertFalse(
            offenders,
            "蓝图仍在开读写连接（事务边界必须下沉到 Service）: "
            + ", ".join(offenders),
        )

    def test_no_blueprint_calls_sqlite3_connect(self):
        """蓝图从不自己 ``sqlite3.connect(...)``。"""
        offenders = []
        for name in ALL_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            if "sqlite3.connect(" in code:
                offenders.append(name)
        self.assertFalse(
            offenders, "蓝图自己开了连接: " + ", ".join(offenders)
        )

    def test_blueprints_do_not_import_repository_db(self):
        """蓝图 **不再** import ``server.repositories.db``。

        它不需要连接助手了 —— 连接由 Service 自己开。
        """
        offenders = []
        for name in ALL_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            if "server.repositories.db" in code:
                offenders.append(name)
        self.assertFalse(
            offenders,
            "蓝图仍直接依赖 repo 连接助手: " + ", ".join(offenders),
        )


class BlueprintPurityTests(unittest.TestCase):
    """2. 蓝图仍是纯 HTTP 层（无裸 SQL）。"""

    def test_no_blueprint_contains_raw_sql(self):
        offenders = []
        for name in ALL_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            for marker in ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM"):
                if marker in code:
                    offenders.append(name + " (" + marker.strip() + ")")
                    break
        self.assertFalse(
            offenders, "蓝图含裸 SQL: " + ", ".join(offenders)
        )

    def test_no_blueprint_executes_sql_directly(self):
        offenders = []
        for name in ALL_BLUEPRINTS:
            if ".execute(" in _code_only(BP_DIR / name):
                offenders.append(name)
        self.assertFalse(
            offenders, "蓝图直接执行 SQL: " + ", ".join(offenders)
        )


class ServiceOwnsTransactionTests(unittest.TestCase):
    """3. Service 层持有事务边界。"""

    def test_repository_db_exposes_service_transaction(self):
        """``server.repositories.db`` 提供 ``service_transaction``。"""
        text = (REPO_DIR / "db.py").read_text(encoding="utf-8")
        self.assertIn("def service_transaction(", text)
        self.assertIn('"service_transaction"', text)

    def test_service_transaction_supports_read_only_mode(self):
        """``service_transaction(commit=False)`` = 只读语义。

        只读 Service 用它；正常退出 **不**提交，异常时回滚。
        """
        text = (REPO_DIR / "db.py").read_text(encoding="utf-8")
        self.assertIn("commit: bool = True", text)
        self.assertIn("commit=False", text)

    def test_services_use_service_transaction(self):
        """确实有 Service 用 ``service_transaction`` 开连接。"""
        users = []
        for path in sorted(SERVICE_DIR.glob("*.py")):
            code = _code_only(path)
            if "service_transaction" in code:
                users.append(path.name)
        self.assertTrue(
            users,
            "没有任何 service 使用 service_transaction —— 事务边界没有下沉",
        )
        for expected in ("tasks.py", "tags.py", "discard.py", "schedule.py"):
            self.assertIn(
                expected,
                users,
                expected + " 应当用 service_transaction 自持事务",
            )

    def test_repositories_still_receive_explicit_conn(self):
        """Repository 仍 **只** 接收显式 ``conn``（不自开连接）。

        这是分层契约的核心：只有 ``server/repositories/db.py`` 能开连接。
        """
        offenders = []
        for path in sorted((REPO_DIR).glob("*.py")):
            if path.name == "db.py":
                continue  # db.py 是唯一允许开连接的模块
            code = _code_only(path)
            if "sqlite3.connect(" in code or "connect(" in code.replace(
                "make_request_conn(", ""
            ).replace("resolve_db_path(", ""):
                if "connect(" in code and "make_request_conn(" not in code:
                    if "sqlite3.connect(" in code:
                        offenders.append(path.name)
        self.assertFalse(
            offenders, "repository 自己开了连接: " + ", ".join(offenders)
        )


_PROBE = r'''
import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app

db = root / "data" / "probe.sqlite3"
if db.exists():
    db.unlink()

def make_cfg():
    return {
        "server": {"host": "127.0.0.1", "port": 0, "debug": False},
        "obsidian": {"vault_path": "vault", "notes_directory": "vault"},
        "api": {"openai_api_key": "", "claude_api_key": ""},
        "database": {"task_db_path": str(db)},
        "_project_root": str(root),
        "_static_dir": str(root / "static"),
        "_db_path": str(db),
        "_notes_dir": str(root / "vault"),
        "_config_path": str(root / "config" / "config.json"),
    }

app = create_app(make_cfg())
client = app.test_client()
out = {}

# ---- 事务原子性：完成一个任务会同时解锁依赖者 --------------------------
r = client.post("/api/tasks", json={
    "name": "PARENT", "category": "study", "estimated_time": 25})
parent = r.get_json(force=True)
out["parent_create_status"] = r.status_code
out["parent_id"] = parent.get("id")

r = client.post("/api/tasks", json={
    "name": "CHILD", "category": "study", "estimated_time": 25,
    "prerequisite_ids": [parent["id"]]})
child = r.get_json(force=True)
out["child_create_status"] = r.status_code
out["child_id"] = child.get("id")

# 依赖者初始应被锁定
r = client.get("/api/tasks/%d" % child["id"])
out["child_initially_locked"] = r.get_json(force=True).get("is_unlocked")

r = client.post("/api/tasks/%d/complete" % parent["id"])
out["parent_complete_status"] = r.status_code
body = r.get_json(force=True)
out["unlocked_tasks_count"] = len(body.get("unlocked_tasks") or [])

r = client.get("/api/tasks/%d" % child["id"])
out["child_after_unlock"] = r.get_json(force=True).get("is_unlocked")

# ---- 提交时机：写入立即对后续读可见 -------------------------------------
r = client.post("/api/tags", json={"name": "TRANSACTION_TAG"})
out["tag_create_status"] = r.status_code
out["tag_id"] = r.get_json(force=True).get("id")
r = client.get("/api/tags")
names = [t.get("name") for t in r.get_json(force=True)]
out["tag_visible_after_commit"] = "TRANSACTION_TAG" in names

# ---- 重名标签返回 200（逐字契约） ---------------------------------------
r = client.post("/api/tags", json={"name": "TRANSACTION_TAG"})
out["dup_tag_status"] = r.status_code

# ---- 只读蓝图同样工作（config_bp 的 /api/export） ------------------------
r = client.get("/api/export")
out["export_status"] = r.status_code
out["export_has_tasks_key"] = "tasks" in (r.get_json(force=True) or {})

# ---- 任务读取路由 -------------------------------------------------------
r = client.get("/api/tasks?include_completed=true&unlocked_only=false")
out["list_tasks_status"] = r.status_code
out["list_tasks_count"] = len(r.get_json(force=True) or [])

r = client.get("/api/tasks/%d/dependents" % parent["id"])
out["dependents_status"] = r.status_code
out["dependents_count"] = r.get_json(force=True).get("count")

r = client.get("/api/dependencies")
out["deps_status"] = r.status_code
out["deps_nodes"] = len((r.get_json(force=True) or {}).get("nodes") or [])

# ---- 删除后立即不可见（提交生效） ----------------------------------------
r = client.delete("/api/tasks/%d" % child["id"])
out["delete_status"] = r.status_code
r = client.get("/api/tasks/%d" % child["id"])
out["get_after_delete_status"] = r.status_code

# ---- 错误语义保持：400 / 404 --------------------------------------------
r = client.post("/api/tasks/%d/complete" % 999999)
out["complete_missing_status"] = r.status_code
r = client.put("/api/tasks/%d" % parent["id"], json={"priority": 1})
out["update_status"] = r.status_code
r = client.post("/api/tasks", json={"prerequisite_ids": "notalist"})
out["bad_prereq_status"] = r.status_code

# ---- 日程域（schedule_bp 的 try/except 错误语义） ------------------------
r = client.get("/api/schedule/weekly")
out["weekly_status"] = r.status_code
r = client.post("/api/schedule/weekly", json={"slot_id": "am1"})
out["weekly_missing_day_status"] = r.status_code
r = client.post("/api/schedule/activities", json={"name": "阅读"})
out["activity_status"] = r.status_code
out["activity_added"] = r.get_json(force=True).get("added")

# ---- 弃牌域 --------------------------------------------------------------
# 用一个 **未完成** 的任务来验证弃牌/恢复（已完成任务不可手动恢复 → 409）。
r = client.post("/api/tasks", json={
    "name": "DISCARD_TARGET", "category": "study", "estimated_time": 25})
discard_target = r.get_json(force=True)["id"]
r = client.post("/api/tasks/%d/move-to-discard" % discard_target)
out["move_to_discard_status"] = r.status_code
r = client.get("/api/discard-pile")
out["discard_pile_status"] = r.status_code
out["discard_pile_count"] = len(r.get_json(force=True) or [])
r = client.post("/api/discard-pile/%d/restore" % discard_target)
out["restore_status"] = r.status_code
# 父任务从未进入弃牌堆 → 恢复返回 400（"not in discard pile"，既有语义）
r = client.post("/api/discard-pile/%d/restore" % parent["id"])
out["restore_not_in_pile_status"] = r.status_code

# ---- 标签域：批量分配 ----------------------------------------------------
r = client.post("/api/tags/batch", json={"task_ids": [], "tags": ["x"]})
out["batch_empty_status"] = r.status_code

# ---- agent 域：import 走 Service（错误路径） ------------------------------
r = client.post("/api/agent/import-tasks", json={"output": "not json at all"})
out["agent_import_bad_status"] = r.status_code

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    with TemporaryDirectory(prefix="lt_txn_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_txn_probe.py"
        runner.write_text(_PROBE, encoding="utf-8")
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
            timeout=120,
        )
        stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
        stderr = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
        if proc.returncode != 0:
            raise AssertionError(f"probe 退出码非0: {stderr[-3000:]}")
        lines = [
            ln for ln in stdout.splitlines() if ln.startswith("PROBE_JSON=")
        ]
        if len(lines) != 1:
            raise AssertionError(f"未捕获 PROBE_JSON: {stdout[-3000:]}")
        return json.loads(lines[0][len("PROBE_JSON=") :])


class TransactionBehaviorTests(unittest.TestCase):
    """4. 行为不回归（事务原子性 / 提交时机 / 错误语义）。"""

    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_task_crud_status_codes_unchanged(self):
        p = self.PROBE
        self.assertEqual(p["parent_create_status"], 201, p)
        self.assertEqual(p["child_create_status"], 201, p)
        self.assertEqual(p["list_tasks_status"], 200, p)
        self.assertEqual(p["delete_status"], 200, p)

    def test_unlock_side_effect_is_atomic(self):
        """完成任务 → 依赖者解锁，**同一事务**内完成。"""
        p = self.PROBE
        self.assertEqual(p["parent_complete_status"], 200, p)
        self.assertEqual(p["unlocked_tasks_count"], 1, p)
        self.assertFalse(p["child_initially_locked"], p)
        self.assertTrue(p["child_after_unlock"], p)

    def test_commit_timing_is_equivalent(self):
        """写入提交后立即对后续读可见（旧写法退出 with 时提交）。"""
        p = self.PROBE
        self.assertEqual(p["tag_create_status"], 201, p)
        self.assertTrue(p["tag_visible_after_commit"], p)

    def test_duplicate_tag_returns_200(self):
        """重名标签返回 **200**（与迁移前逐字一致）。"""
        p = self.PROBE
        self.assertEqual(p["dup_tag_status"], 200, p)

    def test_read_only_blueprint_export_works(self):
        """只读蓝图（``config_bp``）下沉后行为不变。"""
        p = self.PROBE
        self.assertEqual(p["export_status"], 200, p)
        self.assertTrue(p["export_has_tasks_key"], p)

    def test_dependents_and_dependency_graph(self):
        p = self.PROBE
        self.assertEqual(p["dependents_status"], 200, p)
        self.assertEqual(p["dependents_count"], 1, p)
        self.assertEqual(p["deps_status"], 200, p)
        self.assertGreaterEqual(p["deps_nodes"], 1, p)

    def test_error_semantics_unchanged(self):
        p = self.PROBE
        self.assertEqual(p["complete_missing_status"], 404, p)
        self.assertEqual(p["update_status"], 200, p)
        self.assertEqual(p["bad_prereq_status"], 400, p)
        self.assertEqual(p["get_after_delete_status"], 404, p)

    def test_schedule_domain_unchanged(self):
        p = self.PROBE
        self.assertEqual(p["weekly_status"], 200, p)
        self.assertEqual(p["weekly_missing_day_status"], 400, p)
        self.assertEqual(p["activity_status"], 200, p)
        self.assertTrue(p["activity_added"], p)

    def test_discard_domain_unchanged(self):
        p = self.PROBE
        self.assertEqual(p["move_to_discard_status"], 200, p)
        self.assertEqual(p["discard_pile_status"], 200, p)
        self.assertEqual(p["discard_pile_count"], 1, p)
        # 未完成的手动弃牌 → 恢复成功（200）
        self.assertEqual(p["restore_status"], 200, p)
        # 不在弃牌堆 → 400（既有语义）
        self.assertEqual(p["restore_not_in_pile_status"], 400, p)

    def test_tags_batch_and_agent_import_unchanged(self):
        p = self.PROBE
        self.assertEqual(p["batch_empty_status"], 400, p)
        self.assertEqual(p["agent_import_bad_status"], 400, p)


if __name__ == "__main__":
    unittest.main()
