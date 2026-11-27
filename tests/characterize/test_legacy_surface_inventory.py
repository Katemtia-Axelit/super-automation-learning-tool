"""AR03-P5 —— Legacy 表面收敛的机械门禁。

被测对象
--------
* ``server/backend_api.py`` —— **薄别名**（必须零业务逻辑）
* ``server/app/legacy_compat.py`` —— **墓碑**（零路由 / 零副作用）
* ``server/utils/``、``server/config.py`` —— **待归档**的零 importer 死代码
* 生产启动链 ``scripts/launch_server.py`` / ``run_app.py``

关键设计：``legacy_compat.py`` 的断言是 **双形态** 的
----------------------------------------------------
本门禁断言的是 **不变量**（零路由、零副作用、零运行时引用），
而 **不是** 「文件必须在原地」：

* 文件 **存在** → 校验墓碑不变量；
* 文件 **不存在**（已归档）→ 校验「无运行时引用」+ 归档登记。

因此归档本身 **不会** 让本门禁变红 —— 这正是 P5 能安全推进归档的前提。

安全边界
--------
全部静态分析 + **临时合成** SQLite；
**绝不** 读写生产 ``data/task_publisher.db*``、``src/notes/**``、
``config/config.json``。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


LEGACY_COMPAT = _PROJECT_ROOT / "server" / "app" / "legacy_compat.py"
BACKEND_API = _PROJECT_ROOT / "server" / "backend_api.py"
SERVER_DIR = _PROJECT_ROOT / "server"
ARCHIVE_DIR = _PROJECT_ROOT / "_archive"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _parse(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_names(tree) -> set:
    """收集源码里 import 的 **模块名**（含 from-import 的符号）。"""
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                modules.add(base)
            for alias in node.names:
                modules.add(f"{base}.{alias.name}" if base else alias.name)
    return modules


def _route_rules(tree) -> set:
    """收集源码里注册的 Flask 路由规则。"""
    rules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in {"route", "add_url_rule"}:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        rules.add(arg.value)
    return rules


def _dml_statements(tree) -> list:
    """收集源码里 **执行** 的 INSERT / UPDATE / DELETE 语句。"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            upper = node.value.upper().lstrip()
            for keyword in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
                if upper.startswith(keyword):
                    found.append(node.value.strip()[:80])
    return found


# ---------------------------------------------------------------------------
# backend_api.py —— 薄别名
# ---------------------------------------------------------------------------

def test_backend_api_has_no_flask_routes():
    """``server/backend_api.py`` **零 Flask 路由**（路由归 Blueprint 所有）。"""
    rules = _route_rules(_parse(BACKEND_API))
    assert not rules, f"backend_api.py 不得注册路由：{sorted(rules)}"


def test_backend_api_has_no_ddl():
    """``server/backend_api.py`` **零 DDL**（Schema 权威在 ``server/schema/``）。"""
    tree = _parse(BACKEND_API)
    ddl = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            upper = node.value.upper()
            for keyword in ("CREATE TABLE", "ALTER TABLE", "DROP TABLE", "CREATE INDEX"):
                if keyword in upper:
                    ddl.append(node.value.strip()[:80])
    assert not ddl, f"backend_api.py 不得持有 DDL：{ddl}"


def test_backend_api_has_no_dml():
    """``server/backend_api.py`` **零 DML**（业务写入归 Service / Repository）。"""
    dml = _dml_statements(_parse(BACKEND_API))
    assert not dml, f"backend_api.py 不得持有 DML：{dml}"


def test_backend_api_delegates_to_factory():
    """``backend_api.py`` 必须 **委托** ``create_app()``（薄别名的定义）。"""
    source = BACKEND_API.read_text(encoding="utf-8")
    assert "create_app" in source, "backend_api.py 必须委托 create_app()"


# ---------------------------------------------------------------------------
# legacy_compat.py —— 墓碑（双形态）
# ---------------------------------------------------------------------------

def test_legacy_compat_tombstone_invariants_when_present():
    """文件 **保留** 时：墓碑不变量必须成立。

    * ``EXACT_ROUTES`` 空；
    * ``PREFIX_ROUTES`` 空；
    * ``RETIRED`` True；
    * ``register_legacy_compat`` 返回 0、不注册路由、不 import ``backend_api``。
    """
    if not LEGACY_COMPAT.is_file():
        pytest.skip("legacy_compat.py 已归档 —— 由归档分支的测试覆盖")

    source = LEGACY_COMPAT.read_text(encoding="utf-8")

    assert "EXACT_ROUTES: set[str] = set()" in source, "EXACT_ROUTES 必须为空集"
    assert "PREFIX_ROUTES: tuple[str, ...] = ()" in source, "PREFIX_ROUTES 必须为空元组"
    assert "RETIRED = True" in source, "RETIRED 必须为 True"

    imported = _imported_names(_parse(LEGACY_COMPAT))
    offenders = [
        name
        for name in imported
        if "backend_api" in name or "register_legacy_compat" in name
    ]
    assert not offenders, f"墓碑模块不得 import：{offenders}"

    assert not _route_rules(_parse(LEGACY_COMPAT)), "墓碑模块不得注册路由"

    from flask import Flask

    import server.app.legacy_compat as compat_module

    probe = Flask(__name__)
    before = {
        (r.rule, m)
        for r in probe.url_map.iter_rules()
        for m in r.methods - {"HEAD", "OPTIONS"}
    }
    returned = compat_module.register_legacy_compat(
        probe, {"_project_root": str(_PROJECT_ROOT), "_db_path": "synthetic.db"}
    )
    after = {
        (r.rule, m)
        for r in probe.url_map.iter_rules()
        for m in r.methods - {"HEAD", "OPTIONS"}
    }

    assert returned == 0, "register_legacy_compat 必须返回 0"
    assert after == before, "register_legacy_compat 不得注册任何路由"
    assert probe.config.get("_compat_route_count") == 0


def test_legacy_compat_no_runtime_references_when_archived():
    """文件 **归档** 后：``server/**`` 不得有任何运行时引用。

    归档分支必须成立，否则「删掉文件」会让生产启动链炸掉。
    """
    if LEGACY_COMPAT.is_file():
        pytest.skip("legacy_compat.py 仍在原位 —— 由墓碑分支的测试覆盖")

    offenders = []
    for path in SERVER_DIR.rglob("*.py"):
        if path.name == "legacy_compat.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for name in _imported_names(tree):
            if "legacy_compat" in name:
                offenders.append(f"{path.relative_to(_PROJECT_ROOT)}: {name}")

    assert not offenders, f"归档后仍存在运行时引用：{offenders}"


def test_legacy_compat_archived_file_is_recorded():
    """归档后：归档位置必须存在（可审计性）。"""
    if LEGACY_COMPAT.is_file():
        pytest.skip("legacy_compat.py 仍在原位")

    candidates = list(ARCHIVE_DIR.rglob("legacy_compat.py"))
    assert candidates, "归档后必须在 _archive/ 下找到 legacy_compat.py"


# ---------------------------------------------------------------------------
# 待归档模块 —— server/utils/ 与 server/config.py
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "module_rel",
    ["server/utils", "server/config.py"],
    ids=["server-utils", "server-config"],
)
def test_archived_modules_have_zero_importers(module_rel):
    """``server/utils/`` 与 ``server/config.py`` **零 importer**。

    这是归档的 **前置条件** —— 不是「有 importer 也能归档」。
    """
    leaf = module_rel.split("/")[-1]
    offenders = []
    for path in SERVER_DIR.rglob("*.py"):
        rel = path.relative_to(_PROJECT_ROOT).as_posix()
        if rel.startswith(module_rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for name in _imported_names(tree):
            if name.startswith(module_rel) or name.endswith(f".{leaf}"):
                offenders.append(f"{rel}: {name}")

    assert not offenders, f"{module_rel} 仍有 importer，不可归档：{offenders}"


def test_server_utils_is_dead_code():
    """``server/utils/`` 是 **转发壳**，不含独立实现。

    判定方式（只针对 **公开** 门面，即 ``__all__`` 里列出的名字）：
    每个公开函数体 **只做一件事** —— 立即委托给真正的 owner
    （``from server.services... import X as _impl; return _impl(...)``），
    自身 **不** 含计算逻辑（无循环 / 无条件分支）。

    私有的形状适配helper（如 ``_as_mapping``）**不**参与本判定 ——
    它们只是把入参形状统一，不是业务实现。
    """
    utils_dir = SERVER_DIR / "utils"
    if not utils_dir.is_dir():
        pytest.skip("server/utils/ 已归档")
    for path in sorted(utils_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))

        # 公开名字 = __all__ 里列出的（没有 __all__ 时 = 顶层非下划线函数）
        public_names = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == "__all__":
                    for element in getattr(node.value, "elts", []):
                        if isinstance(element, ast.Constant) and isinstance(
                            element.value, str
                        ):
                            public_names.add(element.value)
        if not public_names:
            public_names = {
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            }

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in public_names:
                continue
            body = node.body
            # 允许一个 docstring
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            # 必须存在「导入真正的 owner」这一步
            imports_owner = any(
                isinstance(stmt, (ast.Import, ast.ImportFrom))
                for stmt in body
            )
            assert imports_owner, (
                f"{path.name}::{node.name} 不是转发壳 —— 没有委托给真正的 owner"
            )
            # 不得含分支 / 循环 → 说明它自己实现了逻辑
            branching = [
                stmt
                for stmt in body
                if isinstance(
                    stmt, (ast.For, ast.While, ast.If, ast.Try, ast.With)
                )
            ]
            assert not branching, (
                f"{path.name}::{node.name} 含控制流 —— 不是纯转发壳"
            )


# ---------------------------------------------------------------------------
# 生产启动链
# ---------------------------------------------------------------------------

def test_launch_server_default_entrypoint_is_run_app():
    """``scripts/launch_server.py`` 的 **默认** 入口是 ``run_app.py``。

    ``legacy`` 模式确实在 ``select_entrypoint()`` 里出现过
    ``server/backend_api.py`` 字样，但那条分支被 :func:`main` **fail closed**
    拒绝（在创建 ``.run/`` / 日志 / 进程 **之前** 就 ``SystemExit``），
    因此 **不是** 生产启动链的一部分。
    """
    script = _PROJECT_ROOT / "scripts" / "launch_server.py"
    if not script.is_file():
        pytest.skip("launch_server.py 不存在")
    source = script.read_text(encoding="utf-8")

    assert 'os.environ.get("LEARNING_TOOL_BACKEND", "factory")' in source, (
        "默认后端模式必须是 factory"
    )
    assert 'os.path.join(root, "run_app.py")' in source, (
        "默认入口必须是 run_app.py"
    )


def test_launch_server_fails_closed_on_legacy_mode():
    """legacy 模式必须 **fail closed**（在创建任何进程/文件之前）。"""
    script = _PROJECT_ROOT / "scripts" / "launch_server.py"
    if not script.is_file():
        pytest.skip("launch_server.py 不存在")
    source = script.read_text(encoding="utf-8")

    assert 'if mode != "factory":' in source, "legacy 模式必须被拒绝"
    assert "REFUSED" in source, "拒绝时必须给出明确提示"
    # 拒绝必须发生在 os.makedirs / Popen / 写 PID 之前
    refuse_at = source.index('if mode != "factory":')
    for later in ("os.makedirs(RUN_DIR", "subprocess.Popen", 'open(PID_FILE, "w"'):
        position = source.find(later)
        assert position > refuse_at, (
            f"fail-closed 检查必须早于 {later}"
        )


def test_run_app_does_not_import_backend_api():
    """``run_app.py`` **不再 import** ``server.backend_api``。

    弃牌周期恢复的真实 owner 是
    :func:`server.services.discard.recover_discard_cycle` —— 直接调用它，
    即可断开生产启动链对 legacy 薄别名的运行时依赖。
    """
    source = (_PROJECT_ROOT / "run_app.py").read_text(encoding="utf-8")
    assert "from server.backend_api" not in source, (
        "run_app.py 不得 import server.backend_api"
    )
    assert "server.services" in source or "discard_service" in source, (
        "run_app.py 必须直接调用弃牌恢复的真实 owner"
    )


def test_discard_recovery_owner_is_the_service():
    """真正的 owner 是 ``server/services/discard.py``。"""
    source = (SERVER_DIR / "services" / "discard.py").read_text(encoding="utf-8")
    assert "def recover_discard_cycle(" in source, (
        "server/services/discard.py 必须持有 recover_discard_cycle"
    )
