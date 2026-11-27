"""AR03-P2 / Stage 1 — **静态** 路由清单 oracle 契约测试。

背景
----
P1 的 ``test_route_inventory.py`` / ``test_legacy_route_full_parity.py``
依赖 **现场运行** legacy ``backend_api.py`` 的 ``__main__`` 取路由清单。
Stage 7 收口后 legacy 不再有 Flask 路由，该取数方式必然失效。

本文件把路由清单改成 **静态 oracle**：

* ``scripts/route_inventory.py`` 用 **AST** 解析源码得到 legacy 的活跃 /
  被注释路由声明，以及兼容桥白名单；
* 冻结产物：``tests/fixtures/route_inventory.json``；
* 运行时比对：Factory 的 ``url_map`` 必须覆盖 legacy 全部活跃路由。

全程 **不** 启动 legacy 进程、不触碰生产数据库。
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
# 与既有 characterize 用例保持一致：sandbox_env 与本文件同目录。
_CHARACTERIZE_DIR = Path(__file__).resolve().parent
if str(_CHARACTERIZE_DIR) not in sys.path:
    sys.path.insert(0, str(_CHARACTERIZE_DIR))

import route_inventory  # type: ignore  # noqa: E402

INVENTORY_PATH = PROJECT_ROOT / "tests" / "fixtures" / "route_inventory.json"


class StaticRouteInventoryTests(unittest.TestCase):
    """静态 oracle 自身。"""

    @classmethod
    def setUpClass(cls):
        cls.inventory = route_inventory.build_inventory()

    def test_inventory_file_exists_and_matches_live_source(self):
        self.assertTrue(INVENTORY_PATH.is_file(), "冻结清单缺失")
        frozen = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["counts"],
            self.inventory["counts"],
            "冻结清单与源码漂移；请重新运行 "
            "`python scripts/route_inventory.py --write` 并复核差异",
        )

    def test_legacy_active_routes_found(self):
        """legacy 必须有活跃路由被静态识别到（防止 AST 扫描失效）。"""
        active = {tuple(r) for r in self.inventory["legacy_active_routes"]}
        self.assertGreater(len(active), 30)
        # 抽查若干必须存在的关键路由
        for expected in (
            ("/api/tasks", "GET"),
            ("/api/tasks", "POST"),
            ("/api/gacha/draw", "POST"),
            ("/api/gacha/statistics", "GET"),
            ("/api/tags", "GET"),
            ("/api/config", "GET"),
            ("/api/export", "GET"),
            ("/api/dependencies", "GET"),
            ("/", "GET"),
            ("/api/prompts", "GET"),
            ("/api/agent/process", "POST"),
        ):
            self.assertIn(expected, active, "静态扫描漏掉 " + repr(expected))

    def test_commented_routes_are_not_active(self):
        """被注释掉的历史路由不得出现在活跃集合。"""
        active = {tuple(r) for r in self.inventory["legacy_active_routes"]}
        for dead in (
            ("/api/knowledge/categories", "GET"),
            ("/api/schedule/slots", "GET"),
            ("/api/timer/start", "POST"),
        ):
            self.assertNotIn(dead, active)

    def test_bridge_and_shadowed_partition_legacy(self):
        """bridged + shadowed 必须恰好划分 legacy 活跃路由全集。"""
        active = {tuple(r) for r in self.inventory["legacy_active_routes"]}
        bridged = {tuple(r) for r in self.inventory["compat_bridge"]["bridged_routes"]}
        shadowed = {tuple(r) for r in self.inventory["compat_bridge"]["shadowed_routes"]}
        self.assertEqual(active, bridged | shadowed)
        self.assertEqual(bridged & shadowed, set())

    def test_bridge_matches_legacy_compat_module(self):
        """兼容桥必须 **不存在** 或 **不挂载任何路由**。

        Stage 5 之后：``EXACT_ROUTES`` 已 **清空**（``/``、``/api/config``、
        ``/api/config/save``、``/api/export`` 全部迁到真 Blueprint）。

        Stage 6 之后：``PREFIX_ROUTES`` 也 **清空**（``/api/agent/*`` 9 条与
        ``/api/prompts/*`` 5 条迁到真 Blueprint ``agent_bp`` /
        ``prompts_bp``）—— 兼容桥至此 **不再挂载任何路由**。

        Stage 7 之后：兼容桥 **模块本身被退役**。Cursor 的破坏性操作守卫
        拒绝在会话内物理删除文件，因此物理删除由 Controller / 用户在会话外
        执行；在那之前，模块保持 **零路由** 的等价语义（见下）。
        """
        compat = route_inventory.scan_legacy_compat()
        self.assertEqual(
            compat["exact_routes"],
            [],
            "兼容桥的 EXACT_ROUTES 必须为空集",
        )
        self.assertEqual(
            compat["prefix_routes"],
            [],
            "兼容桥的 PREFIX_ROUTES 必须为空元组",
        )
        if compat["module_present"]:
            # 模块尚在（等待会话外物理删除）→ 必须证明它 **不注册任何路由**。
            self.assertFalse(
                compat["bridged_routes"],
                "兼容桥模块仍在但不得挂载任何路由",
            )

    def test_compat_bridge_module_is_not_imported_by_server(self):
        """``server/**`` 不得再 **import** 已退役的兼容桥。

        用 AST 检测（而不是文本 grep）——文档字符串里对历史兼容桥的
        **说明性提及** 是允许的（那是迁移记录，不是依赖）。
        """
        import ast

        offenders = []
        for path in (PROJECT_ROOT / "server").rglob("*.py"):
            if path.name == "legacy_compat.py":
                # 兼容桥模块自身不算"引用它"。
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.endswith("legacy_compat"):
                            offenders.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.endswith("legacy_compat"):
                        offenders.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}"
                        )
                    for alias in node.names:
                        if alias.name == "register_legacy_compat":
                            offenders.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}"
                            )
        self.assertFalse(
            offenders, "server/** 仍 import 兼容桥: " + ", ".join(offenders)
        )


class FactoryCoversStaticInventoryTests(unittest.TestCase):
    """Factory 运行时 url_map 必须覆盖静态清单里的 legacy 活跃路由。"""

    def test_factory_covers_all_legacy_active_routes(self):
        from sandbox_env import available_port, materialize, seed
        from tempfile import TemporaryDirectory

        scanner = (
            "import json, runpy, sys\n"
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parent\n"
            "sys.path.insert(0, str(root))\n"
            "from server.app import create_app\n"
            "app = create_app()\n"
            "routes = sorted({(r.rule, m) for r in app.url_map.iter_rules()\n"
            "                  for m in r.methods if m not in {'HEAD', 'OPTIONS'}})\n"
            "print('ROUTES_JSON=' + json.dumps(routes))\n"
        )

        with TemporaryDirectory(prefix="lt_static_inventory_") as temp:
            root = materialize(Path(temp) / "sandbox", available_port())
            seed(root)
            runner = root / "_route_scanner.py"
            runner.write_text(scanner, encoding="utf-8")
            import os

            env = {
                k: v
                for k, v in os.environ.items()
                if "API_KEY" not in k.upper()
                and "TOKEN" not in k.upper()
                and k.upper() not in ("PYTHONPATH", "PYTHONHOME")
            }
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                [sys.executable, "-I", str(runner)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            lines = [
                line
                for line in proc.stdout.splitlines()
                if line.startswith("ROUTES_JSON=")
            ]
            self.assertEqual(len(lines), 1, proc.stdout[-2000:])
            factory_routes = {tuple(r) for r in json.loads(lines[0][12:])}

        inventory = route_inventory.build_inventory()
        legacy_active = {tuple(r) for r in inventory["legacy_active_routes"]}
        missing = legacy_active - factory_routes
        self.assertFalse(
            missing, "Factory 未覆盖的 legacy 路由: " + repr(sorted(missing))
        )


if __name__ == "__main__":
    unittest.main()
