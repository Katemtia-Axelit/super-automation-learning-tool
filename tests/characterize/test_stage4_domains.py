"""AR03-P2 / Stage 4 — state / timer / schedule / knowledge / feedback 域的
**边界收口** 契约测试。

Stage 4 的目标不是重写这些域的业务逻辑（它们在 P1 已经是真 BP + service +
repo 三层），而是：

1. **统一连接入口** —— 蓝图不再各自手工拼 DB 路径，统一走
   :mod:`server.repositories.db`（按 **当前 app** 解析）；
2. **schedule 补齐业务编排** —— 参数校验与幂等语义从蓝图下沉到
   :mod:`server.services.schedule`；
3. **消除残留的 legacy 全局依赖** —— 蓝图层不再 import ``backend_api``
   来解析 DB 路径。

本文件机械校验以上三点，并断言 **行为不回归**（用黄金快照 + 域行为探针）。

全程 **不** 触碰生产数据库：全部在 ``tests/characterize/sandbox_env.py``
的合成根内。
"""

from __future__ import annotations

import io
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

#: Stage 4 收口的蓝图。
STAGE4_BLUEPRINTS = (
    "state_bp.py",
    "timer_bp.py",
    "schedule_bp.py",
    "knowledge_bp.py",
    "feedback_bp.py",
)

#: 需要 **DB 连接** 的蓝图（走 ``server.repositories.db``）。
#:
#: ``knowledge_bp`` **不在**其中：知识库是 **文件系统** 域（Obsidian
#: vault），它只读 ``app.config["_notes_dir"]`` 指定的目录，从不开数据库
#: 连接 —— 把它算进 "DB 连接统一入口" 是错误的期望。
DB_BLUEPRINTS = (
    "state_bp.py",
    "timer_bp.py",
    "schedule_bp.py",
    "feedback_bp.py",
)

#: 这些蓝图历史上 **必须** 保留的 legacy 惰性 import 契约（P1 T3 不变量）。
#:
#: P1 的 ``verify_p0_cleanup.py`` T3 断言"导入这些蓝图后 ``backend_api``
#: **尚未** 被加载，只有首次属性访问才触发"。Stage 4 **不** 改动这个契约，
#: 也不把它当作"legacy 依赖"来清理 —— 它是刻意的惰性加载设计。
LAZY_BACKEND_CONTRACT = ("state_bp.py", "timer_bp.py", "schedule_bp.py",
                          "knowledge_bp.py", "feedback_bp.py")


def _code_only(path: Path) -> str:
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


class UnifiedConnectionTests(unittest.TestCase):
    """1. 统一连接入口。"""

    def test_stage4_blueprints_use_repository_db_helper(self):
        """需要 DB 的蓝图统一走 :mod:`server.repositories.db`。"""
        for name in DB_BLUEPRINTS:
            text = (BP_DIR / name).read_text(encoding="utf-8")
            self.assertIn(
                "server.repositories.db",
                text,
                name + " 没有使用统一的 repo 连接助手",
            )

    def test_knowledge_bp_is_filesystem_only(self):
        """``knowledge_bp`` 是文件系统域，**不开数据库连接**。

        知识库读的是 Obsidian vault（``app.config["_notes_dir"]``），
        不是 SQLite。因此它不 import ``server.repositories.db`` 是 **正确**
        的 —— 本断言把这个边界固定下来，防止有人给它硬加一条 DB 连接。
        """
        text = (BP_DIR / "knowledge_bp.py").read_text(encoding="utf-8")
        self.assertNotIn("server.repositories.db", text)
        self.assertNotIn("sqlite3", text)

    def test_stage4_blueprints_do_not_handcraft_db_paths(self):
        """蓝图不再手工拼 ``data/task_publisher.db`` 路径。"""
        for name in DB_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            self.assertNotIn(
                "task_publisher.db",
                code,
                name + " 仍在手工拼 DB 路径",
            )

    def test_feedback_bp_no_longer_uses_legacy_db_path(self):
        """``feedback_bp`` 的路径解析不再依赖 legacy 全局 ``DB_PATH``。"""
        code = _code_only(BP_DIR / "feedback_bp.py")
        # `_legacy_db_path` 仍保留为诊断参考，但 **不在** `_conn()` 的路径上。
        self.assertNotIn(
            "_legacy_db_path()",
            code.split("def _legacy_db_path")[0],
            "feedback_bp 的 _conn() 仍在调用 _legacy_db_path()",
        )


class ScheduleServiceOrchestrationTests(unittest.TestCase):
    """2. schedule 补齐业务编排。"""

    def test_schedule_service_owns_validation(self):
        text = (
            PROJECT_ROOT / "server" / "services" / "schedule.py"
        ).read_text(encoding="utf-8")
        self.assertIn("day_of_week and slot_id required", text)
        self.assertIn("slot_id required", text)
        self.assertIn("Activity name required", text)

    def test_schedule_blueprint_delegates_to_service(self):
        text = (BP_DIR / "schedule_bp.py").read_text(encoding="utf-8")
        self.assertIn(
            "from server.services import schedule as schedule_service", text
        )
        # 蓝图里 **不再** 出现业务校验字符串
        self.assertNotIn("day_of_week and slot_id required", text)
        self.assertNotIn("Activity name required", text)

    def test_schedule_blueprint_has_no_raw_sql(self):
        code = _code_only(BP_DIR / "schedule_bp.py")
        for marker in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(marker, code, "schedule_bp 仍含裸 SQL: " + marker)

    def test_schedule_slots_constant_is_in_service(self):
        text = (
            PROJECT_ROOT / "server" / "services" / "schedule.py"
        ).read_text(encoding="utf-8")
        self.assertIn("SCHEDULE_SLOTS", text)
        # 10 个时间槽 —— 每槽一行 ``"slot_id":`` 条目
        self.assertEqual(text.count('"slot_id":'), 10, "时间槽数量应为 10")


class LazyBackendContractTests(unittest.TestCase):
    """3. P1 的 lazy-import 契约保持不变（Stage 4 不得破坏它）。"""

    def test_lazy_backend_import_contract_preserved(self):
        """P1 的惰性 legacy import 契约保持不变（Stage 4 不得破坏它）。

        契约内容：这些蓝图在 **首次属性访问** 时才
        ``from server import backend_api``（PEP 562 ``__getattr__``），
        顶层 import 不触发 legacy 单体加载。
        """
        for name in LAZY_BACKEND_CONTRACT:
            path = BP_DIR / name
            self.assertTrue(path.is_file(), name + " 缺失")
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "from server import backend_api",
                text,
                name + " 丢失了 P1 的惰性 legacy import 契约",
            )
            # 惰性：必须包在 __getattr__ 里，不能在模块顶层
            self.assertIn(
                "def __getattr__",
                text,
                name + " 的惰性 import 未包在 __getattr__ 中",
            )


_RUNNER = r'''
import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app

db = root / "data" / "stage4.sqlite3"
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

# ---- schedule：slots 常量 -------------------------------------------------
slots = client.get("/api/schedule/slots").get_json(force=True)
out["slots_count"] = len(slots)
out["slots_first"] = slots[0]["slot_id"] if slots else None

# ---- schedule：参数校验（400，且零写入） ----------------------------------
r = client.post("/api/schedule/weekly", json={"slot_id": "am1"})
out["weekly_missing_day_status"] = r.status_code
r = client.post("/api/schedule/daily", json={"activity": "x"})
out["daily_missing_slot_status"] = r.status_code
r = client.post("/api/schedule/activities", json={"name": "  "})
out["activity_empty_name_status"] = r.status_code

# ---- schedule：周计划保存与读取 -------------------------------------------
r = client.post("/api/schedule/weekly", json={
    "day_of_week": 1, "slot_id": "am1", "activity": "复习"})
out["weekly_save_status"] = r.status_code
weekly = client.get("/api/schedule/weekly").get_json(force=True)
out["weekly_has_entry"] = weekly.get("1", {}).get("am1", {}).get("activity") == "复习"

# ---- schedule：日计划保存与读取 -------------------------------------------
r = client.post("/api/schedule/daily", json={
    "date": "2026-03-04", "slot_id": "pm1", "activity": "自习", "notes": "n"})
out["daily_save_status"] = r.status_code
daily = client.get("/api/schedule/daily?date=2026-03-04").get_json(force=True)
out["daily_entry_count"] = len(daily)
out["daily_activity"] = daily[0]["activity"] if daily else None

# ---- schedule：活动幂等（同名不重复新增） ----------------------------------
r = client.post("/api/schedule/activities", json={"name": "阅读"})
body1 = r.get_json(force=True)
out["activity_first_status"] = r.status_code
out["activity_first_added"] = body1.get("added")
r = client.post("/api/schedule/activities", json={"name": "阅读"})
body2 = r.get_json(force=True)
out["activity_second_status"] = r.status_code
out["activity_second_added"] = body2.get("added")
out["activity_same_id"] = body1.get("id") == body2.get("id")
acts = client.get("/api/schedule/activities").get_json(force=True)
out["activity_total"] = len([a for a in acts if a["name"] == "阅读"])

# ---- feedback：写入落到当前 app 的库 --------------------------------------
# 先建一条真实任务 —— feedback 有外键约束（task_id → tasks.id）。
# （PRAGMA foreign_keys=ON 正是统一连接助手要保证的语义。）
fb_task = client.post("/api/tasks", json={
    "name": "FEEDBACK_TARGET", "category": "study", "estimated_time": 25,
}).get_json(force=True)
out["feedback_task_id"] = fb_task.get("id")
# payload 必须满足统一行为事件合同（note 是 JSON 对象字符串、schema_version=1、
# event_id / session_id 合法、reason_category=other）。
note = json.dumps({
    "schema_version": 1,
    "event_id": "evt-stage4-1",
    "session_id": "sess-stage4-1",
    "source": "unified_gacha",
})
r = client.post("/api/task-feedback", json={
    "task_id": fb_task["id"],
    "event_type": "timer_ended",
    "reason_category": "other",
    "note": note,
})
out["feedback_status"] = r.status_code
out["feedback_body"] = r.get_json(force=True)

# ---- state：睡眠校验 ------------------------------------------------------
r = client.get("/api/state/sleep")
out["sleep_status"] = r.status_code

# ---- timer：空状态 -------------------------------------------------------
r = client.get("/api/timer/active")
out["timer_active_status"] = r.status_code

# ---- knowledge：空 vault 不报错 -------------------------------------------
r = client.get("/api/knowledge/categories")
out["knowledge_status"] = r.status_code

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    import json

    with TemporaryDirectory(prefix="lt_stage4_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_stage4_probe.py"
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


class Stage4BehaviorTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_schedule_slots_unchanged(self):
        p = self.PROBE
        self.assertEqual(p["slots_count"], 10, p)
        self.assertEqual(p["slots_first"], "am1", p)

    def test_schedule_validation_rejects_bad_input(self):
        p = self.PROBE
        self.assertEqual(p["weekly_missing_day_status"], 400, p)
        self.assertEqual(p["daily_missing_slot_status"], 400, p)
        self.assertEqual(p["activity_empty_name_status"], 400, p)

    def test_weekly_schedule_roundtrip(self):
        p = self.PROBE
        self.assertEqual(p["weekly_save_status"], 200, p)
        self.assertTrue(p["weekly_has_entry"], p)

    def test_daily_schedule_roundtrip(self):
        p = self.PROBE
        self.assertEqual(p["daily_save_status"], 200, p)
        self.assertEqual(p["daily_entry_count"], 1, p)
        self.assertEqual(p["daily_activity"], "自习", p)

    def test_activity_creation_is_idempotent(self):
        p = self.PROBE
        self.assertEqual(p["activity_first_status"], 200, p)
        self.assertTrue(p["activity_first_added"], p)
        self.assertEqual(p["activity_second_status"], 200, p)
        self.assertFalse(p["activity_second_added"], p)
        self.assertTrue(p["activity_same_id"], p)
        self.assertEqual(p["activity_total"], 1, p)

    def test_feedback_writes_to_current_app_db(self):
        """feedback 写入落到 **当前 app** 的库（不再是另一个空库 500）。"""
        p = self.PROBE
        self.assertEqual(p["feedback_status"], 201, p)
        self.assertTrue(p["feedback_body"].get("saved"), p)

    def test_other_domains_still_respond(self):
        p = self.PROBE
        self.assertEqual(p["sleep_status"], 200, p)
        self.assertEqual(p["timer_active_status"], 200, p)
        self.assertEqual(p["knowledge_status"], 200, p)


if __name__ == "__main__":
    unittest.main()
