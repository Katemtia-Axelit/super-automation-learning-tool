"""P1 切片 2 — Factory 收口：空库可启动 / 配置可替换 / 实例隔离。

本文件只使用 ``tests/characterize/sandbox_env.py`` 的 **合成根**
（source-only 拷贝 + 合成 SQLite + 合成 config），绝不读写
``data/task_publisher.db*`` / ``src/notes/**`` / ``config/config.json``。

覆盖：
1. Factory 在 **空合成库**（无任何表）上能创建 app 并响应 ``/api/health``；
2. ``create_app(config=...)`` 可注入替换配置（DB 路径真的被使用）；
3. 两个 app 实例互不串扰（DB 路径不同，各自写入互不可见）；
4. 装配顺序显式化（extensions 在 schema 之前 ⇒ ``get_db_path()`` 可用）；
5. ``server.config`` 与 ``server.app.config`` 是同一权威（薄 re-export）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# 让 ``sandbox_env`` 可被导入（pytest 的 rootdir 推断不保证本目录在 sys.path）。
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed

SOURCE_ROOT = Path(__file__).resolve().parents[2]

_RUNNER = r'''
import json, os, sqlite3, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app
from server.extensions import get_db_path


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


out = {}

# ---------------------------------------------------------------- 1. 空库启动
empty_db = root / "data" / "empty.sqlite3"
if empty_db.exists():
    empty_db.unlink()
app = create_app(make_cfg(empty_db))
client = app.test_client()
resp = client.get("/api/health")
out["empty_health_status"] = resp.status_code
out["empty_health_body"] = resp.get_json(force=True)
conn = sqlite3.connect(empty_db)
try:
    tables = sorted(
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    )
finally:
    conn.close()
out["empty_tables"] = tables
out["empty_db_path"] = str(empty_db)

# 2. extensions 在 schema 之前生效：get_db_path() 可用且等于配置路径
out["get_db_path"] = get_db_path()

# 3. 写入隔离：实例 A 写一条任务，实例 B 不应看到
db_a = root / "data" / "iso_a.sqlite3"
db_b = root / "data" / "iso_b.sqlite3"
for p in (db_a, db_b):
    if p.exists():
        p.unlink()
app_a = create_app(make_cfg(db_a))
app_b = create_app(make_cfg(db_b))
ca = app_a.test_client()
cb = app_b.test_client()
created = ca.post("/api/tasks", json={"name": "ISO_SENTINEL_A"})
out["iso_create_status"] = created.status_code
list_a = ca.get("/api/tasks?unlocked_only=false").get_json(force=True)
list_b = cb.get("/api/tasks?unlocked_only=false").get_json(force=True)
names_a = [r.get("name") for r in list_a] if isinstance(list_a, list) else []
names_b = [r.get("name") for r in list_b] if isinstance(list_b, list) else []
out["iso_a_has_sentinel"] = "ISO_SENTINEL_A" in names_a
out["iso_b_has_sentinel"] = "ISO_SENTINEL_A" in names_b
out["iso_a_count"] = len(names_a)
out["iso_b_count"] = len(names_b)

# 4. 配置权威唯一性：server.config 是 server.app.config 的薄 re-export
# AR03-P5：**双形态** —— server/config.py 若已归档，则改为断言
# 「归档后无运行时引用」+「配置权威唯一性仍由 server.app.config 保持」。
import ast as _ast
from pathlib import Path as _Path

_config_path = _Path(root) / "server" / "config.py"
out["legacy_config_present"] = _config_path.is_file()

if out["legacy_config_present"]:
    import server.config as legacy_cfg
    import server.app.config as app_cfg

    out["config_same_object"] = legacy_cfg.load_config is app_cfg.load_config
else:
    import server.app.config as app_cfg

    # 归档后：server/** 不得再 import server.config
    _offenders = []
    for _p in (_Path(root) / "server").rglob("*.py"):
        if _p.name == "config.py" and _p.parent.name == "server":
            continue
        try:
            _tree = _ast.parse(_p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for _node in _ast.walk(_tree):
            if isinstance(_node, _ast.Import):
                for _alias in _node.names:
                    if _alias.name == "server.config":
                        _offenders.append(f"{_p.relative_to(root)}:{_node.lineno}")
            elif isinstance(_node, _ast.ImportFrom):
                if (_node.module or "") == "server.config":
                    _offenders.append(f"{_p.relative_to(root)}:{_node.lineno}")
    out["legacy_config_runtime_references"] = sorted(_offenders)
    out["config_same_object"] = None

out["config_default_keys"] = sorted(
    k for k in app_cfg.DEFAULT_CONFIG.keys()
)

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    with TemporaryDirectory(prefix="lt_factory_bootstrap_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_factory_probe.py"
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
            timeout=90,
        )
        if proc.returncode != 0:
            raise AssertionError(f"probe 退出码非0: {proc.stderr[-3000:]}")
        lines = [
            ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON=")
        ]
        if len(lines) != 1:
            raise AssertionError(f"未捕获 PROBE_JSON: {proc.stdout[-3000:]}")
        import json

        return json.loads(lines[0][len("PROBE_JSON=") :])


class FactoryBootstrapTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_1_factory_boots_on_empty_synthetic_db(self):
        """空库（无任何表）上 Factory 能建 app 并响应 /api/health。"""
        self.assertEqual(self.PROBE["empty_health_status"], 200, self.PROBE)
        body = self.PROBE["empty_health_body"]
        self.assertIsInstance(body, dict, body)
        self.assertEqual(body.get("status"), "ok", body)

    def test_2_empty_db_gets_the_full_schema(self):
        """空库启动后 schema 权威层必须把真实表建出来（不是空壳）。"""
        tables = set(self.PROBE["empty_tables"])
        for required in (
            "tasks",
            "tags",
            "task_tags",
            "gacha_records",
            "task_rejection_log",
            "timer_sessions",
            "daily_user_state",
            "state_assessments",
            "task_feedback_events",
        ):
            self.assertIn(required, tables, f"missing {required}: {sorted(tables)}")

    def test_3_extensions_are_initialised_before_use(self):
        """init_extensions 真正生效：get_db_path() 不再抛 RuntimeError。"""
        self.assertTrue(
            str(self.PROBE["get_db_path"]).endswith("empty.sqlite3"),
            self.PROBE.get("get_db_path"),
        )

    def test_4_two_instances_do_not_cross_contaminate(self):
        """两个 app 实例 DB 路径不同，写入互不可见。"""
        self.assertTrue(self.PROBE["iso_a_has_sentinel"], self.PROBE)
        self.assertFalse(self.PROBE["iso_b_has_sentinel"], self.PROBE)

    def test_5_config_authority_is_single(self):
        """配置权威唯一。

        **双形态**（AR03-P5）：
        * ``server/config.py`` 仍在原位 → 它必须是 ``server/app/config.py``
          的薄 re-export（同一函数对象）；
        * 已归档 → ``server/**`` 不得再有运行时引用，配置权威仍唯一地
          落在 ``server/app/config.py``。
        """
        if self.PROBE.get("legacy_config_present", True):
            self.assertTrue(self.PROBE["config_same_object"], self.PROBE)
        else:
            self.assertEqual(
                self.PROBE.get("legacy_config_runtime_references", []),
                [],
                "server/config.py 归档后仍存在运行时引用",
            )


class FactoryBootstrapStaticTests(unittest.TestCase):
    """静态契约：装配顺序与注册清单必须显式。"""

    def test_app_factory_documents_the_assembly_order(self):
        text = (SOURCE_ROOT / "server" / "app" / "app_factory.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("init_extensions(app, cfg[\"_db_path\"])", text)
        self.assertIn("ensure_all_schema(conn)", text)
        # schema 初始化必须晚于 extensions 初始化
        self.assertLess(
            text.index("init_extensions(app, cfg[\"_db_path\"])"),
            text.index("ensure_all_schema(conn)"),
        )

    def test_blueprints_all_matches_registered_blueprints(self):
        root = str(SOURCE_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from server.app.app_factory import REGISTERED_BLUEPRINTS

        import server.blueprints as bp_pkg

        registered = {bp.name.replace("_bp", "_bp") for bp in REGISTERED_BLUEPRINTS}
        exported = set(bp_pkg.__all__)
        # Blueprint 实例名是 'tasks'/'gacha'…，模块名是 'tasks_bp'/'gacha_bp'。
        registered_modules = {f"{bp.name}_bp" for bp in REGISTERED_BLUEPRINTS}
        self.assertTrue(
            registered_modules.issubset(exported),
            f"registered but not exported: {sorted(registered_modules - exported)}",
        )
        # __all__ 里多出来的只允许是惰性 stub 模块
        extra = exported - registered_modules
        self.assertTrue(
            extra.issubset(bp_pkg._STUB_BP_MODULES),
            f"unexpected exports: {sorted(extra)}",
        )

    def test_server_config_is_a_thin_reexport(self):
        """``server/config.py`` 必须是 ``server/app/config.py`` 的薄 re-export。

        **双形态**（AR03-P5）：该文件若已被归档，则改为断言
        「归档后 ``server/**`` 无运行时引用」+「归档件可追溯」。
        """
        import ast as _ast

        config_path = SOURCE_ROOT / "server" / "config.py"
        if not config_path.is_file():
            archived = list((SOURCE_ROOT / "_archive").rglob("config.py"))
            self.assertTrue(
                archived, "server/config.py 归档后必须在 _archive/ 下可追溯"
            )
            offenders = []
            for path in (SOURCE_ROOT / "server").rglob("*.py"):
                if path.name == "config.py" and path.parent.name == "server":
                    continue
                try:
                    tree = _ast.parse(path.read_text(encoding="utf-8"))
                except (SyntaxError, UnicodeDecodeError):
                    continue
                for node in _ast.walk(tree):
                    if isinstance(node, _ast.Import):
                        for alias in node.names:
                            if alias.name == "server.config":
                                offenders.append(
                                    str(path.relative_to(SOURCE_ROOT))
                                )
                    elif isinstance(node, _ast.ImportFrom):
                        if (node.module or "") == "server.config":
                            offenders.append(
                                str(path.relative_to(SOURCE_ROOT))
                            )
            self.assertFalse(
                offenders,
                "server/config.py 归档后仍存在运行时引用: " + ", ".join(offenders),
            )
            return

        text = config_path.read_text(encoding="utf-8")
        self.assertIn("server.app.config", text)
        self.assertNotIn("def load_config", text)


if __name__ == "__main__":
    unittest.main()
