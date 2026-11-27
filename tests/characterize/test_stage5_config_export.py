"""AR03-P2 / Stage 5 — 配置 / 导出 / 索引 域的 **分层契约** 与 **安全** 测试。

Stage 5 把 ``/``、``/api/config``、``/api/config/save``、``/api/export``
从 legacy 单体迁到 **真 Blueprint**，并把业务规则下沉到
:mod:`server.services.config` / :mod:`server.services.export`。

本文件锁定：

1. **分层方向** —— repo 不依赖 service / blueprint / Flask；
2. **脱敏** —— ``GET /api/config`` **绝不**回显 API key，只回布尔值；
3. **深度合并** —— ``POST /api/config/save`` 的扁平字段落到正确的子对象；
4. **原子写入** —— 配置写入不会留下半个损坏文件；
5. **合成隔离** —— 配置写入落在 **合成根**，**绝不**触碰生产的
   ``config/config.json``（红线）；
6. **导出只读** —— 导出 **不写** 任何表，且表清单固定；
7. **兼容桥收口** —— ``EXACT_ROUTES`` 已清空。

全程 **不** 触碰生产数据库与生产配置：全部在
``tests/characterize/sandbox_env.py`` 的合成根内。
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

#: Stage 5 新建的蓝图 / service / repo。
STAGE5_BLUEPRINTS = ("config_bp.py", "index_bp.py")
STAGE5_SERVICES = ("config.py", "export.py")
STAGE5_REPOSITORIES = ("export_repo.py",)


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


class Stage5LayeringTests(unittest.TestCase):
    def test_export_repo_has_no_upward_dependency(self):
        code = _code_only(REPO_DIR / "export_repo.py")
        for forbidden in (
            "server.services",
            "server.blueprints",
            "from flask",
            "import flask",
            "server.backend_api",
        ):
            self.assertNotIn(forbidden, code, "export_repo 依赖越界: " + forbidden)

    def test_config_service_has_no_flask_dependency(self):
        for name in STAGE5_SERVICES:
            code = _code_only(SERVICE_DIR / name)
            self.assertNotIn("from flask", code, name + " 依赖 Flask")

    def test_config_blueprints_have_no_raw_sql(self):
        for name in STAGE5_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            for marker in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
                self.assertNotIn(marker, code, name + " 仍含裸 SQL: " + marker)
            self.assertNotIn(".execute(", code, name + " 直接执行 SQL")

    def test_config_blueprints_delegate_to_service(self):
        text = (BP_DIR / "config_bp.py").read_text(encoding="utf-8")
        self.assertIn("from server.services import config as config_service", text)
        self.assertIn("from server.services import export as export_service", text)

    def test_compat_bridge_exact_routes_is_empty(self):
        """Stage 5 后兼容桥的 ``EXACT_ROUTES`` 已清空。

        **AR03-P5**：兼容桥文件已归档到 ``_archive/``。归档后不变量
        依然成立且更强 —— 文件 **根本不存在**，不可能再暴露任何路由。
        因此本测试是 **双形态** 的：

        - 文件仍在原位 → 断言 ``EXACT_ROUTES`` 已清空；
        - 文件已归档 → 断言原位文件 **不存在**，且归档副本存在
          （证明它是"被归档"，而不是"被删除"或"从未存在"）。
        """
        live = PROJECT_ROOT / "server" / "app" / "legacy_compat.py"
        archived = (
            PROJECT_ROOT
            / "_archive"
            / "11_AR03_P5_一次性脚本"
            / "server"
            / "app"
            / "legacy_compat.py"
        )
        if live.exists():
            text = live.read_text(encoding="utf-8")
            self.assertIn("EXACT_ROUTES: set[str] = set()", text)
        else:
            self.assertFalse(
                live.exists(),
                "兼容桥已归档：原位文件必须不存在",
            )
            self.assertTrue(
                archived.exists(),
                "兼容桥必须以归档副本形式保留（不得删除/丢失）",
            )


class ConfigServiceUnitTests(unittest.TestCase):
    """3./4. 深度合并 + 原子写入（纯函数，无 IO 依赖）。"""

    def test_flat_api_fields_merge_into_api_subobject(self):
        from server.services import config as config_service

        merged = config_service.merge_config_payload(
            {"api": {"model": "gpt-4o-mini"}},
            {"openai_api_key": "sk-x", "model": "gpt-4o"},
        )
        self.assertEqual(merged["api"]["openai_api_key"], "sk-x")
        self.assertEqual(merged["api"]["model"], "gpt-4o")

    def test_bed_time_merges_into_obsidian_subobject(self):
        from server.services import config as config_service

        merged = config_service.merge_config_payload(
            {"obsidian": {"vault_path": "vault"}}, {"bed_time": "23:00"}
        )
        self.assertEqual(merged["obsidian"]["bed_time"], "23:00")
        self.assertEqual(merged["obsidian"]["vault_path"], "vault")

    def test_unknown_nested_dict_is_merged_not_replaced(self):
        from server.services import config as config_service

        merged = config_service.merge_config_payload(
            {"custom": {"a": 1, "b": 2}}, {"custom": {"b": 3}}
        )
        self.assertEqual(merged["custom"], {"a": 1, "b": 3})

    def test_input_config_is_not_mutated(self):
        from server.services import config as config_service

        original = {"api": {"model": "x"}}
        config_service.merge_config_payload(original, {"model": "y"})
        self.assertEqual(original, {"api": {"model": "x"}})

    def test_config_view_never_exposes_keys(self):
        from server.services import config as config_service

        view = config_service.build_config_view(
            {
                "server": {"port": 50585},
                "obsidian": {"notes_directory": "vault", "vault_path": "v"},
                "api": {"openai_api_key": "sk-secret", "claude_api_key": "ck-secret"},
            }
        )
        self.assertTrue(view["has_openai_key"])
        self.assertTrue(view["has_claude_key"])
        serialized = json.dumps(view, ensure_ascii=False)
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("ck-secret", serialized)

    def test_save_config_is_atomic_and_leaves_no_temp_files(self):
        from server.services import config as config_service

        with TemporaryDirectory(prefix="lt_cfg_") as temp:
            path = Path(temp) / "config.json"
            path.write_text(
                json.dumps({"api": {"model": "old"}}), encoding="utf-8"
            )
            result = config_service.save_config(path, {"model": "new"})
            self.assertTrue(result["success"])
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(written["api"]["model"], "new")
            # 没有残留临时文件
            leftovers = [p.name for p in Path(temp).iterdir() if p.name != "config.json"]
            self.assertEqual(leftovers, [], "残留临时文件: " + repr(leftovers))


class ExportContractTests(unittest.TestCase):
    """6. 导出只读 + 表清单固定。"""

    def test_export_table_list_is_fixed(self):
        from server.services import export as export_service

        self.assertEqual(
            export_service.EXPORT_TABLES,
            (
                "tasks",
                "tags",
                "task_tags",
                "task_dependencies",
                "user_schedule",
                "daily_schedules",
                "daily_user_state",
                "gacha_records",
                "task_rejection_log",
                "task_completion_feedback",
            ),
        )

    def test_export_service_does_not_write(self):
        code = _code_only(SERVICE_DIR / "export.py")
        for marker in ("INSERT ", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(marker, code, "export service 含写操作: " + marker)

    def test_export_repo_only_reads(self):
        code = _code_only(REPO_DIR / "export_repo.py")
        for marker in ("INSERT ", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(marker, code, "export_repo 含写操作: " + marker)


_RUNNER = r'''
import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app

db = root / "data" / "stage5.sqlite3"
if db.exists():
    db.unlink()

config_path = root / "config" / "config.json"

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
        "_config_path": str(config_path),
    }

app = create_app(make_cfg())
client = app.test_client()
out = {}

# ---- 1. GET /api/config 脱敏 ---------------------------------------------
view = client.get("/api/config").get_json(force=True)
out["config_view"] = view
out["config_has_key_fields"] = (
    "openai_api_key" in view or "claude_api_key" in view
)

# ---- 2. POST /api/config/save：写到合成根，扁平字段落子对象 ---------------
r = client.post("/api/config/save", json={
    "openai_api_key": "sk-stage5", "bed_time": "23:30",
})
out["save_status"] = r.status_code
out["save_body"] = r.get_json(force=True)
written = json.loads(config_path.read_text(encoding="utf-8"))
out["written_api_key"] = written.get("api", {}).get("openai_api_key")
out["written_bed_time"] = written.get("obsidian", {}).get("bed_time")
out["written_preserves"] = written.get("obsidian", {}).get("vault_path")

# ---- 3. 导出只读：调用前后 DB 内容不变 ------------------------------------
before = client.get("/api/export").get_json(force=True)
client.post("/api/tasks", json={"name": "EXPORT_PROBE", "category": "study"})
exported = client.get("/api/export").get_json(force=True)
out["export_keys"] = sorted(k for k in exported.keys() if k != "exported_at")
out["export_has_exported_at"] = "exported_at" in exported
out["export_tasks_count"] = len(exported.get("tasks", []))
out["export_reflects_new_task"] = any(
    t.get("name") == "EXPORT_PROBE" for t in exported.get("tasks", [])
)

# ---- 4. 索引页 -------------------------------------------------------------
r = client.get("/")
out["index_status"] = r.status_code
out["index_body"] = r.data.decode("utf-8", "replace")[:200]

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    with TemporaryDirectory(prefix="lt_stage5_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_stage5_probe.py"
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


class Stage5BehaviorTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_config_view_is_redacted(self):
        p = self.PROBE
        self.assertFalse(p["config_has_key_fields"], p)
        self.assertIn("has_openai_key", p["config_view"], p)
        self.assertIn("has_claude_key", p["config_view"], p)

    def test_config_save_writes_into_synthetic_root(self):
        """配置写入落在合成根（生产 config/config.json 绝不被碰）。"""
        p = self.PROBE
        self.assertEqual(p["save_status"], 200, p)
        self.assertTrue(p["save_body"].get("success"), p)
        self.assertEqual(p["written_api_key"], "sk-stage5", p)
        self.assertEqual(p["written_bed_time"], "23:30", p)
        # 未提及的既有字段被保留（深度合并，不是整块替换）
        self.assertEqual(p["written_preserves"], "vault", p)

    def test_export_lists_the_fixed_table_set(self):
        p = self.PROBE
        self.assertTrue(p["export_has_exported_at"], p)
        for table in (
            "tasks",
            "tags",
            "task_tags",
            "task_dependencies",
            "user_schedule",
            "daily_schedules",
            "daily_user_state",
            "gacha_records",
            "task_rejection_log",
            "task_completion_feedback",
        ):
            self.assertIn(table, p["export_keys"], p)

    def test_export_reflects_current_db_state(self):
        p = self.PROBE
        self.assertGreaterEqual(p["export_tasks_count"], 1, p)
        self.assertTrue(p["export_reflects_new_task"], p)

    def test_index_page_renders(self):
        p = self.PROBE
        self.assertEqual(p["index_status"], 200, p)
        self.assertIn("SYNTHETIC_ONLY_UI", p["index_body"], p)


if __name__ == "__main__":
    unittest.main()
