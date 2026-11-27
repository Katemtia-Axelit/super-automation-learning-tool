"""AR02-G01 同进程双 Factory legacy 全局路径串读刻画 (synthetic-only).

背景: `server/app/legacy_compat.py::register_legacy_compat` 在装配每个
Factory app 时改写模块级 `backend_api.DB_PATH/NOTES_DIR`,而 legacy handler
在请求时才读全局路径。同进程先装配 cfgB 后,appA 的 legacy 路由会读到 B 库.
native 蓝图按 `current_app.config["_db_path"]` 取连接,不受影响.

本文件只允许做一件事:用 `tempfile` + source-only sandbox + 独立子进程复现
上述行为,供 AR04 G03 修复。生产源码、工具链、既有测试、真实用户数据一律不碰.

AR03-P2 / Stage 2：``expectedFailure`` 标记 **已移除**
------------------------------------------------------
移除条件（本文件头部写死的条件）现已 **全部满足**：

* ``/api/discard-pile`` 已在 Stage 2 迁到 **真 Blueprint**
  （``server/blueprints/discard_bp.py``），不再由 legacy 兼容桥转发；
* 同进程双 Factory 下，native 与原 legacy 路径 **全部** 读到各自 DB
  （本文件全绿，出现 XPASS）。

因此 ``test_2`` 的 ``@unittest.expectedFailure`` 标记按原约定移除，
该用例现在是 **真实的隔离断言**（不再容许失败）。
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed

_RUNNER = """
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
from server.app import create_app
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
db_a = root / "data" / "synth_a.sqlite3"
db_b = root / "data" / "synth_b.sqlite3"
app_a = create_app(make_cfg(db_a))
app_b = create_app(make_cfg(db_b))
app_a.config["TESTING"] = True
app_b.config["TESTING"] = True
ca, cb = app_a.test_client(), app_b.test_client()
def snap(resp):
    try:
        payload = resp.get_json(force=True)
    except Exception:
        payload = None
    names = []
    if isinstance(payload, list):
        for row in payload:
            names.append(row.get("name") if isinstance(row, dict) else str(row))
    return {"status": resp.status_code, "names": names}
out = {
    "native_a": snap(ca.get("/api/tasks?unlocked_only=false")),
    "native_b": snap(cb.get("/api/tasks?unlocked_only=false")),
    "legacy_a": snap(ca.get("/api/discard-pile")),
    "legacy_b": snap(cb.get("/api/discard-pile")),
}
print("PROBE_JSON=" + json.dumps(out))
"""


def _run_dual_factory_probe() -> tuple[dict, bool]:
    """物化 sandbox,准备 A/B 哨兵库,在子进程内跑双 Factory,返回 (probe, 清理是否OK)."""
    with TemporaryDirectory(prefix="lt_ar02_factory_iso_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        tmp = Path(temp)
        db_a = root / "data" / "synth_a.sqlite3"
        db_b = root / "data" / "synth_b.sqlite3"
        shutil.copyfile(root / "data" / "synthetic.sqlite3", db_a)
        shutil.copyfile(root / "data" / "synthetic.sqlite3", db_b)
        for db, tag in ((db_a, "SYNTH_A"), (db_b, "SYNTH_B")):
            conn = sqlite3.connect(db)
            try:
                conn.execute("UPDATE tasks SET name=?, in_discard_pile=1 WHERE id=1", (tag,))
                conn.commit()
            finally:
                conn.close()
        runner = root / "_dual_factory_probe.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if (
            "API_KEY" not in k.upper() and "TOKEN" not in k.upper()
            and "SECRET" not in k.upper()
            and k.upper() not in ("PYTHONPATH", "PYTHONHOME"))}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-I", str(runner)],
            cwd=root, env=env, capture_output=True, text=True,
            encoding="utf-8", timeout=40,
        )
        if proc.returncode != 0:
            raise AssertionError(f"probe 子进程退出码非0: {proc.stderr[-2000:]}")
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON=")]
        if len(lines) != 1:
            raise AssertionError(f"未捕获到 PROBE_JSON: {proc.stdout[-2000:]}")
        probe = json.loads(lines[0][len("PROBE_JSON="):])
        return probe, True
    # with 退出即清理 TemporaryDirectory,能执行到这里说明无 Windows 占用残留.


class FactoryInstanceIsolationTests(unittest.TestCase):
    PROBE: dict = {}
    CLEANUP_OK = False

    @classmethod
    def setUpClass(cls):
        cls.PROBE, cls.CLEANUP_OK = _run_dual_factory_probe()

    def test_1_native_tasks_isolated_control(self):
        """控制组(真实 PASS):native /api/tasks 各读各自哨兵,互不串读."""
        self.assertTrue(self.CLEANUP_OK, "sandbox 临时目录未能干净清理,证据不可信")
        native_a, native_b = self.PROBE["native_a"], self.PROBE["native_b"]
        self.assertEqual(native_a["status"], 200, native_a)
        self.assertEqual(native_b["status"], 200, native_b)
        self.assertIn("SYNTH_A", native_a["names"], native_a)
        self.assertNotIn("SYNTH_B", native_a["names"], native_a)
        self.assertIn("SYNTH_B", native_b["names"], native_b)
        self.assertNotIn("SYNTH_A", native_b["names"], native_b)

    def test_2_discard_pile_is_isolated_between_instances(self):
        """弃牌堆在同进程双 Factory 下各读各自 DB（Stage 2 已修）。

        Stage 2 之前，这条路由由 legacy 兼容桥转发，先装配的 appA 会读到
        后装配的 appB 的库（已知历史红项）。现在它是 native Blueprint，
        按 ``current_app.config["_db_path"]`` 取连接，因此隔离成立。
        """
        legacy_a = self.PROBE["legacy_a"]
        self.assertEqual(legacy_a["status"], 200, legacy_a)
        self.assertIn("SYNTH_A", legacy_a["names"], legacy_a)
        self.assertNotIn("SYNTH_B", legacy_a["names"], legacy_a)

    def test_3_legacy_b_reads_own_db(self):
        """可选证据:后装配的 B legacy 读到 B 自身(当前行为,不证明隔离正常)."""
        legacy_b = self.PROBE["legacy_b"]
        self.assertEqual(legacy_b["status"], 200, legacy_b)
        self.assertIn("SYNTH_B", legacy_b["names"], legacy_b)


if __name__ == "__main__":
    unittest.main()
