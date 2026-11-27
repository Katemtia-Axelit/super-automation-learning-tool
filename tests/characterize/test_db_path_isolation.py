"""AR03-P2 / Stage 1 — **双 Factory 实例隔离** 契约测试。

背景
----
P1 的 ``server/extensions.py`` 用 **模块级可变全局** ``_DB_PATH`` 保存 DB
路径。同进程内创建两个不同 DB 路径的 Factory 实例时，后一个会覆盖前一个
—— 违反"Factory 实例不互相污染"的验收项，且任何在 **请求期** 读取
``get_db_path()`` 的代码都可能拿到 **另一个 app** 的路径。

Stage 1 的修法：权威存储搬到 app 对象
（``app.extensions["sal"]["db_path"]``），``get_db_path()`` 在 **请求期**
优先读当前 app 上下文。

本文件用 **合成根**（``tests/characterize/sandbox_env.py``）验证：

1. 同一进程内两个 Factory 实例，各自的请求只读写 **自己** 的 DB；
2. 请求期 ``get_db_path()`` 返回当前 app 的路径（不是另一个 app 的）；
3. ``server.extensions`` 里 **不再** 存在 ``_DB_PATH`` 形式的进程级可变
   状态源（静态契约）；
4. ``server.repositories.db`` 的连接/事务助手按 app 作用域解析路径。

全程 **不** 触碰 ``data/task_publisher.db*`` / ``src/notes/**`` /
``config/config.json``。
"""

from __future__ import annotations

import os
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

_RUNNER = r'''
import json, sqlite3, sys
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

db_a = root / "data" / "iso_a.sqlite3"
db_b = root / "data" / "iso_b.sqlite3"
for p in (db_a, db_b):
    if p.exists():
        p.unlink()

app_a = create_app(make_cfg(db_a))
app_b = create_app(make_cfg(db_b))

out["cfg_a_path"] = str(db_a)
out["cfg_b_path"] = str(db_b)

# --- 1. 请求期 get_db_path() 必须按 app 上下文解析 -----------------------
with app_a.test_request_context("/api/health"):
    out["req_path_a"] = get_db_path()
with app_b.test_request_context("/api/health"):
    out["req_path_b"] = get_db_path()

# --- 2. app 对象上的权威存储 ---------------------------------------------
out["ext_path_a"] = app_a.extensions["sal"]["db_path"]
out["ext_path_b"] = app_b.extensions["sal"]["db_path"]
out["cfg_key_a"] = app_a.config["_db_path"]
out["cfg_key_b"] = app_b.config["_db_path"]

# --- 3. 写入隔离 ---------------------------------------------------------
ca = app_a.test_client()
cb = app_b.test_client()
out["create_a"] = ca.post(
    "/api/tasks", json={"name": "SENTINEL_ALPHA"}
).status_code
out["create_b"] = cb.post(
    "/api/tasks", json={"name": "SENTINEL_BETA"}
).status_code

def names(client):
    data = client.get("/api/tasks?unlocked_only=false").get_json(force=True)
    if isinstance(data, list):
        return sorted(r.get("name") for r in data if isinstance(r, dict))
    if isinstance(data, dict):
        for key in ("tasks", "items", "data"):
            if isinstance(data.get(key), list):
                return sorted(
                    r.get("name") for r in data[key] if isinstance(r, dict)
                )
    return []

out["names_a"] = names(ca)
out["names_b"] = names(cb)

# --- 4. repo 连接助手按 app 作用域解析 -----------------------------------
from server.repositories import db as repo_db

with app_a.test_request_context("/api/health"):
    out["repo_db_path_a"] = repo_db.resolve_db_path()
    with repo_db.read_connection() as conn:
        out["repo_db_file_a"] = conn.execute("PRAGMA database_list").fetchone()[2]
with app_b.test_request_context("/api/health"):
    out["repo_db_path_b"] = repo_db.resolve_db_path()
    with repo_db.read_connection() as conn:
        out["repo_db_file_b"] = conn.execute("PRAGMA database_list").fetchone()[2]

# --- 5. 事务助手：异常回滚 -----------------------------------------------
with app_a.test_request_context("/api/health"):
    try:
        with repo_db.write_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (name, category, priority, estimated_time)"
                " VALUES ('ROLLBACK_ME','daily',5,25)"
            )
            raise ValueError("intentional failure")
    except ValueError:
        out["rollback_caught"] = True
    with repo_db.read_connection() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE name='ROLLBACK_ME'"
        ).fetchone()[0]
    out["rollback_rows"] = cnt

# --- 6. 事务助手：正常提交 -----------------------------------------------
with app_a.test_request_context("/api/health"):
    with repo_db.write_connection() as conn:
        conn.execute(
            "INSERT INTO tasks (name, category, priority, estimated_time)"
            " VALUES ('COMMIT_ME','daily',5,25)"
        )
    with repo_db.read_connection() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE name='COMMIT_ME'"
        ).fetchone()[0]
    out["commit_rows"] = cnt

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    import json

    with TemporaryDirectory(prefix="lt_db_isolation_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_isolation_probe.py"
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


class DualFactoryIsolationTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_request_scoped_db_path_is_per_app(self):
        """请求期 ``get_db_path()`` 按 app 上下文解析，两个实例互不串扰。"""
        p = self.PROBE
        self.assertTrue(
            str(p["req_path_a"]).endswith("iso_a.sqlite3"), p
        )
        self.assertTrue(
            str(p["req_path_b"]).endswith("iso_b.sqlite3"), p
        )
        self.assertNotEqual(p["req_path_a"], p["req_path_b"], p)

    def test_app_object_is_the_authoritative_store(self):
        """app.extensions 与 app.config 上的 DB 路径一致且各归各 app。"""
        p = self.PROBE
        self.assertEqual(p["ext_path_a"], p["cfg_key_a"], p)
        self.assertEqual(p["ext_path_b"], p["cfg_key_b"], p)
        self.assertNotEqual(p["ext_path_a"], p["ext_path_b"], p)

    def test_writes_do_not_cross_contaminate(self):
        """实例 A 写入的任务在实例 B 不可见。"""
        p = self.PROBE
        self.assertIn("SENTINEL_ALPHA", p["names_a"], p)
        self.assertNotIn("SENTINEL_ALPHA", p["names_b"], p)
        self.assertIn("SENTINEL_BETA", p["names_b"], p)
        self.assertNotIn("SENTINEL_BETA", p["names_a"], p)

    def test_repo_helper_resolves_per_app(self):
        """repository 连接助手按 app 作用域解析，且真正连到该 app 的 DB 文件。"""
        p = self.PROBE
        self.assertTrue(str(p["repo_db_path_a"]).endswith("iso_a.sqlite3"), p)
        self.assertTrue(str(p["repo_db_path_b"]).endswith("iso_b.sqlite3"), p)
        self.assertTrue(
            str(p["repo_db_file_a"]).endswith("iso_a.sqlite3"), p
        )
        self.assertTrue(
            str(p["repo_db_file_b"]).endswith("iso_b.sqlite3"), p
        )

    def test_transaction_helper_rolls_back_on_error(self):
        """``write_connection`` 在异常时回滚。"""
        p = self.PROBE
        self.assertTrue(p.get("rollback_caught"), p)
        self.assertEqual(p.get("rollback_rows"), 0, p)

    def test_transaction_helper_commits_on_success(self):
        """``write_connection`` 在正常退出时提交。"""
        p = self.PROBE
        self.assertEqual(p.get("commit_rows"), 1, p)


class NoProcessLevelMutableGlobalTests(unittest.TestCase):
    """静态契约：不得再有 ``_DB_PATH`` 形式的进程级可变状态源。"""

    def test_extensions_has_no_mutable_db_path_global(self):
        """``server.extensions`` 不得再有 ``_DB_PATH`` 形式的进程级可变全局。

        Stage 1 之后：权威存储是 app 对象
        （``app.extensions["sal"]["db_path"]``）；模块级只保留
        ``_LAST_DB_PATH`` 作为 **请求期之外** 的兼容兜底。
        """
        text = (PROJECT_ROOT / "server" / "extensions.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("global _DB_PATH", text)
        self.assertNotIn("_DB_PATH:", text.replace("_LAST_DB_PATH:", ""))
        self.assertIn("_LAST_DB_PATH", text)
        # 权威来源必须是 app 对象
        self.assertIn('app.extensions["sal"]["db_path"] = db_path', text)

    def test_repositories_do_not_import_backend_api(self):
        """repository 层不得 import legacy 单体（方向单向）。

        例外：``task_repo`` / ``gacha_repo`` 目前仍是 P1 遗留的 **转发壳**，
        它们在 Stage 2 / Stage 3 被真 SQL 实现替换。本断言锁定
        "除这两个已知待迁移壳之外，不得有新的 legacy 依赖"。
        """
        repo_dir = PROJECT_ROOT / "server" / "repositories"
        known_shells = {"task_repo.py", "gacha_repo.py"}
        offenders = []
        for path in sorted(repo_dir.glob("*.py")):
            if path.name in known_shells:
                continue
            text = path.read_text(encoding="utf-8")
            if "from server.backend_api" in text or (
                "import server.backend_api" in text
            ):
                offenders.append(path.name)
        self.assertFalse(
            offenders,
            "repository 层仍 import legacy 单体: " + ", ".join(offenders),
        )

    def test_repo_db_helper_has_no_flask_app_context_dependency(self):
        """``server.repositories.db`` 不得硬编码任何项目相对 DB 路径。"""
        text = (PROJECT_ROOT / "server" / "repositories" / "db.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"data/task_publisher.db"', text)
        self.assertNotIn("'data/task_publisher.db'", text)


if __name__ == "__main__":
    unittest.main()
