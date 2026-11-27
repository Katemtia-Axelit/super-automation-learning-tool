"""AR03-P2 / Stage 7 — legacy 收口后的 **路由面** 覆盖契约。

背景
----
P1 的 ``test_route_inventory.py`` / ``test_legacy_route_full_parity.py``
依赖 **现场运行** legacy ``backend_api.py`` 的 ``__main__`` 取路由清单。
Stage 7 收口后 legacy 是 **薄别名**（委托 ``create_app()``），**不再**
持有任何 Flask 路由 —— 那套取数方式必然失效。

本文件把该保证改成 **不依赖 legacy 运行时** 的形态：

* legacy 覆盖面 → **冻结** 的迁移前路由面
  （``tests/fixtures/legacy_route_surface.json``，43 条）；
* Factory 覆盖面 → 在 **合成根** 里 **实时** 采集 ``url_map``；
* 断言：冻结清单里的每一条 legacy 路由在 Factory 中 **零缺失**。

同时断言 legacy 入口 ``python server/backend_api.py`` 与 ``run_app.py``
**等价**（Stage 7 的公开承诺：legacy 入口 = ``create_app()``）。

全程使用 ``sandbox_env`` 合成根；生产 DB / Vault / config 零读写。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# 让 ``sandbox_env`` 可被导入（pytest 的 rootdir 推断不保证本目录在 sys.path）。
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed  # noqa: E402

_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import route_inventory  # type: ignore  # noqa: E402

#: 采集 Factory 运行时路由 + legacy 入口等价性的扫描器。
_SCANNER = r'''
import json, runpy, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
mode = sys.argv[1]

if mode == "legacy_entry":
    # legacy 入口（薄别名）—— 必须与 run_app.py 等价。
    from flask import Flask
    Flask.run = lambda self, *args, **kwargs: None
    app = runpy.run_path(str(root / "run_app.py"), run_name="legacy_entry")["app"]
elif mode == "legacy_module":
    # legacy 模块入口（薄别名委托 create_app）。
    from flask import Flask
    Flask.run = lambda self, *args, **kwargs: None
    app = runpy.run_path(str(root / "server" / "backend_api.py"),
                         run_name="legacy_module")["app"]
else:
    from server.app import create_app
    app = create_app()

routes = sorted({(r.rule, m) for r in app.url_map.iter_rules()
                 for m in r.methods if m not in {"HEAD", "OPTIONS"}})
print("ROUTES_JSON=" + json.dumps(routes))
'''


class LegacyRouteSurfaceCoverageTests(unittest.TestCase):
    """冻结的 legacy 路由面必须在 Factory 中零缺失。"""

    @classmethod
    def setUpClass(cls):
        cls.routes: dict[str, set[tuple[str, str]]] = {}
        with TemporaryDirectory(prefix="lt_legacy_route_full_") as temp:
            root = materialize(Path(temp) / "sandbox", available_port())
            seed(root)
            # ``sandbox_env`` 只复制 ``server/**``；legacy 入口等价性需要
            # 顶层 ``run_app.py``，因此显式复制（合成根内，仍是源码拷贝）。
            shutil.copyfile(
                _PROJECT_ROOT / "run_app.py", root / "run_app.py"
            )
            runner = root / "_route_scanner.py"
            runner.write_text(_SCANNER, encoding="utf-8")
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
            for mode in ("factory", "legacy_entry", "legacy_module"):
                proc = subprocess.run(
                    [sys.executable, "-I", str(runner), mode],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=60,
                )
                assert proc.returncode == 0, (mode, proc.stderr[-2000:])
                lines = [
                    ln
                    for ln in proc.stdout.splitlines()
                    if ln.startswith("ROUTES_JSON=")
                ]
                assert len(lines) == 1, (mode, proc.stdout[-2000:])
                cls.routes[mode] = {
                    tuple(r) for r in json.loads(lines[0][len("ROUTES_JSON=") :])
                }

    def test_factory_covers_every_frozen_legacy_route(self):
        """冻结清单里的每一条 legacy 路由在 Factory 中零缺失。"""
        inventory = route_inventory.build_inventory()
        legacy_routes = {tuple(r) for r in inventory["legacy_active_routes"]}
        self.assertGreater(len(legacy_routes), 30)
        missing = legacy_routes - self.routes["factory"]
        self.assertFalse(
            missing, f"Legacy 路由在 Factory 中缺失: {sorted(missing)}"
        )

    def test_legacy_entry_equals_factory(self):
        """``run_app.py`` 入口的路由集与 Factory **完全一致**。"""
        self.assertEqual(
            self.routes["legacy_entry"],
            self.routes["factory"],
            "legacy 入口（run_app.py）与 Factory 的路由集不一致",
        )

    def test_legacy_module_entry_equals_factory(self):
        """``server/backend_api.py`` 入口的路由集与 Factory **完全一致**。

        Stage 7 的公开承诺：``python server/backend_api.py`` 等价于
        ``run_app.py``（委托 ``create_app()``）。
        """
        self.assertEqual(
            self.routes["legacy_module"],
            self.routes["factory"],
            "legacy 模块入口与 Factory 的路由集不一致",
        )

    def test_legacy_module_entry_has_no_own_routes(self):
        """legacy 薄别名 **不得** 额外持有任何路由（避免第二业务事实源）。"""
        self.assertEqual(
            self.routes["legacy_module"],
            self.routes["factory"],
            "legacy 薄别名出现了 Factory 之外的路由",
        )

    def test_representative_blueprint_routes_are_present(self):
        """各域 Blueprint 的代表路由必须在 Factory 中。"""
        representatives = [
            ("/api/state/sleep", "GET"),
            ("/api/schedule/daily", "GET"),
            ("/api/timer/active", "GET"),
            ("/api/task-feedback", "POST"),
            ("/api/knowledge/notes", "GET"),
            ("/api/config", "GET"),
            ("/api/export", "GET"),
            ("/api/dependencies", "GET"),
            ("/api/agent/agents", "GET"),
            ("/api/prompts", "GET"),
        ]
        factory = self.routes["factory"]
        for rule, method in representatives:
            self.assertIn(
                (rule, method),
                factory,
                f"missing representative route {method} {rule}",
            )


if __name__ == "__main__":
    unittest.main()
