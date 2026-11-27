"""AR03-P3-E：前端模块边界的 **机械契约测试**。

设计意图
--------
``scripts/check_module_imports.js`` 是独立可执行门禁（退出码 0/1）。
本文件把同一批规则再以 pytest 形式锁住，原因是二者覆盖的 **失败方式**
不同：

* 脚本失败 → CI / 命令行门禁立刻红；
* pytest 失败 → 回归套件红，且失败信息直接指向 **哪条架构约束** 被破坏。

规则本身见 ``scripts/check_module_imports.js`` 顶部注释。这里只做
**等价断言**，不引入第二套规则来源。

规则的质量标准
--------------
每条检查必须验证 **真实的架构约束**（可从代码 / 依赖图 / 状态所有权
直接观察），**不得** 为了"通过测试"而不断增加形式主义规则。若某条规则
无法用具体违规案例说明其价值，则不加入。

保护边界
--------
本文件 **只读** 仓库；不写任何文件；不触碰生产 DB / config / notes。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = PROJECT_ROOT / "static"
MODULES_DIR = STATIC_ROOT / "modules"
APP_JS = STATIC_ROOT / "app.js"
APP_ENTRY_JS = STATIC_ROOT / "app.entry.js"
CHECK_SCRIPT = PROJECT_ROOT / "scripts" / "check_module_imports.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _feature_module_dirs() -> list[Path]:
    if not MODULES_DIR.exists():
        return []
    return sorted(
        (p for p in MODULES_DIR.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )


def _js_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.js") if p.is_file())


def _extract_specifiers(source: str) -> list[str]:
    """提取 import/export 的模块 specifier（静态 + 动态）。"""
    specs: list[str] = []
    static_re = re.compile(
        r"(?:^|[\s;}])(?:import|export)\b[^'\";]*?from\s*['\"]([^'\"]+)['\"]"
    )
    for match in static_re.finditer(source):
        specs.append(match.group(1))
    dynamic_re = re.compile(r"\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
    for match in dynamic_re.finditer(source):
        specs.append(match.group(1))
    return specs


def _function_body(source: str, name: str) -> str:
    """按花括号配平抽取 ``function <name>(...) { ... }`` 的源码体。"""
    match = re.search(
        r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
        source,
    )
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return source[start:]


# ---------------------------------------------------------------------------
# A. 门禁脚本自身必须可执行、且当前仓库无违规
# ---------------------------------------------------------------------------
class BoundaryScriptGateTests(unittest.TestCase):
    """``scripts/check_module_imports.js`` 是独立可执行门禁。"""

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        cls.available = cls.node is not None and CHECK_SCRIPT.exists()

    def test_boundary_script_exists(self):
        self.assertTrue(
            CHECK_SCRIPT.exists(),
            "边界检查脚本必须存在（AR03-P3-E 的独立可执行门禁）",
        )

    def test_boundary_script_passes_with_exit_code_zero(self):
        """当前仓库必须无边界违规（退出码 0）。"""
        if not self.available:
            self.skipTest("node is not available on PATH")
        proc = subprocess.run(
            [self.node, str(CHECK_SCRIPT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            timeout=120,
        )
        self.assertEqual(
            proc.returncode,
            0,
            "模块边界检查必须通过（退出码 0）：\n%s\n%s"
            % (proc.stdout, proc.stderr),
        )

    def test_boundary_script_json_output_is_machine_readable(self):
        """``--json`` 必须产出可机读结果（可作为 CI 门禁输入）。"""
        if not self.available:
            self.skipTest("node is not available on PATH")
        proc = subprocess.run(
            [self.node, str(CHECK_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            timeout=120,
        )
        payload = json.loads(proc.stdout)
        self.assertIn("violations", payload)
        self.assertIn("ok", payload)
        self.assertIsInstance(payload["violations"], list)
        self.assertTrue(payload["ok"], "当前仓库的边界检查必须通过")
        self.assertIn("appScopedModules", payload)


# ---------------------------------------------------------------------------
# B. 规则 ⑥：循环依赖检测
# ---------------------------------------------------------------------------
class NoCircularModuleImportTests(unittest.TestCase):
    """Feature 模块之间的 import 图必须是 DAG。

    违规案例：``modules/tasks/index.js`` import ``modules/gacha/index.js``
    且 ``modules/gacha/index.js`` import ``modules/tasks/index.js`` ——
    两者互相依赖，ESM 的初始化顺序会让其中一方的顶层状态在对方执行时
    尚未就绪。这种 bug 只在运行时暴露，且极难定位。
    """

    def _build_graph(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {}
        for directory in _feature_module_dirs():
            owner = directory.name
            edges: set[str] = set()
            for file in _js_files(directory):
                source = _read(file)
                for spec in _extract_specifiers(source):
                    if not spec.startswith("."):
                        continue
                    resolved = (file.parent / spec).resolve()
                    try:
                        parts = resolved.relative_to(MODULES_DIR.resolve()).parts
                    except ValueError:
                        continue
                    if not parts:
                        continue
                    target = parts[0]
                    if target == owner:
                        continue
                    edges.add(target)
            graph[owner] = edges
        return graph

    def test_module_import_graph_is_acyclic(self):
        graph = self._build_graph()
        color: dict[str, int] = {}
        stack: list[str] = []

        def visit(node: str) -> list[str] | None:
            color[node] = 1
            stack.append(node)
            for child in sorted(graph.get(node, set())):
                if child not in graph:
                    continue
                state = color.get(child, 0)
                if state == 1:
                    index = stack.index(child)
                    return stack[index:] + [child]
                if state == 0:
                    cycle = visit(child)
                    if cycle:
                        return cycle
            stack.pop()
            color[node] = 2
            return None

        for node in sorted(graph):
            if color.get(node, 0) == 0:
                cycle = visit(node)
                self.assertIsNone(
                    cycle,
                    "模块之间存在循环依赖：%s" % (" → ".join(cycle or [])),
                )

    def test_cross_module_imports_target_only_public_entry(self):
        """跨模块 import 只能指向对方的 ``index.js`` 公共入口。"""
        for directory in _feature_module_dirs():
            owner = directory.name
            for file in _js_files(directory):
                source = _read(file)
                for spec in _extract_specifiers(source):
                    if not spec.startswith("."):
                        continue
                    resolved = (file.parent / spec).resolve()
                    try:
                        parts = resolved.relative_to(MODULES_DIR.resolve()).parts
                    except ValueError:
                        continue
                    if len(parts) < 2 or parts[0] == owner:
                        continue
                    self.assertEqual(
                        parts,
                        (parts[0], "index.js"),
                        "%s 越界 import %s（跨模块只能 import 公共入口）"
                        % (file.relative_to(PROJECT_ROOT), spec),
                    )


# ---------------------------------------------------------------------------
# C. 规则 ⑦：唯一状态所有权
# ---------------------------------------------------------------------------
class UniqueStateOwnershipTests(unittest.TestCase):
    """``modules/*`` 内的 owner 状态必须 **闭包私有**。

    违规案例：owner 把自己的 session 挂到 ``window`` 上
    （``window.__mySession = …``），于是同一份状态存在两个所有者
    （闭包 + 全局），谁最后写谁赢，状态随时漂移。
    """

    def test_modules_never_write_writable_global_state(self):
        violations: list[str] = []
        for file in _js_files(MODULES_DIR):
            source = _read(file)
            for match in re.finditer(
                r"(?:^|[^\w.$])window\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)",
                source,
            ):
                name = match.group(1)
                if name == "SAL":
                    continue  # 内核命名空间的幂等声明
                violations.append(
                    "%s → window.%s" % (file.relative_to(PROJECT_ROOT), name)
                )
        self.assertEqual(
            violations,
            [],
            "modules/* 内不得写全局状态（owner 状态必须闭包私有）：%s"
            % ", ".join(violations),
        )

    def test_core_and_shared_never_depend_on_modules(self):
        """内核不反向依赖业务（依赖方向永远是 入口 → 内核 ← 业务）。"""
        for base in (STATIC_ROOT / "core", STATIC_ROOT / "shared"):
            for file in _js_files(base):
                for spec in _extract_specifiers(_read(file)):
                    normalized = spec.replace("\\", "/")
                    self.assertNotIn(
                        "modules/",
                        normalized,
                        "%s 不得 import 业务模块：%s"
                        % (file.relative_to(PROJECT_ROOT), spec),
                    )


# ---------------------------------------------------------------------------
# D. 规则 ⑧：app.js 可写全局白名单
# ---------------------------------------------------------------------------
class AppJsGlobalWhitelistTests(unittest.TestCase):
    """``static/app.js`` 的可写全局必须登记在白名单里。

    违规案例：迁移完自由卡后又在 app.js 里写 ``window.__gachaCache = …``
    —— 一个未登记的全局业务状态，既逃过了 owner 化，又让"谁是权威"再次模糊。
    """

    @classmethod
    def setUpClass(cls):
        cls.source = _read(APP_JS)
        cls.script = _read(CHECK_SCRIPT)

    def _whitelist_names(self) -> set[str]:
        block = re.search(
            r"const\s+APP_JS_GLOBAL_WHITELIST\s*=\s*\{([\s\S]*?)\n\};",
            self.script,
        )
        self.assertIsNotNone(block, "白名单必须登记在 check_module_imports.js 里")
        return set(re.findall(r"^\s*'([^']+)'\s*:", block.group(1), re.MULTILINE))

    def test_every_writable_global_in_app_js_is_whitelisted(self):
        whitelist = self._whitelist_names()
        seen: set[str] = set()
        for match in re.finditer(
            r"(?:^|[^\w.$])window\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)",
            self.source,
        ):
            seen.add(match.group(1))
        unlisted = sorted(seen - whitelist)
        self.assertEqual(
            unlisted,
            [],
            "app.js 出现未登记的可写全局：%s（新业务实现必须落到 owner 模块）"
            % ", ".join(unlisted),
        )

    def test_whitelist_entries_all_still_exist(self):
        """白名单条目不得全部消失（否则 whitelist 已腐化）。"""
        whitelist = self._whitelist_names()
        seen: set[str] = set()
        for match in re.finditer(
            r"(?:^|[^\w.$])window\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)",
            self.source,
        ):
            seen.add(match.group(1))
        stale = sorted(whitelist - seen)
        self.assertEqual(
            stale,
            [],
            "白名单条目已不存在（请同步清理）：%s" % ", ".join(stale),
        )

    def test_whitelist_entries_carry_a_rationale(self):
        """白名单每一条都必须写明 **为什么** 它必须留在全局。

        没有理由的白名单条目 = 形式主义登记 = 单体重新膨胀的入口。
        """
        block = re.search(
            r"const\s+APP_JS_GLOBAL_WHITELIST\s*=\s*\{([\s\S]*?)\n\};",
            self.script,
        )
        self.assertIsNotNone(block)
        entries = re.findall(
            r"^\s*'([^']+)'\s*:\s*'([^']*)'", block.group(1), re.MULTILINE
        )
        self.assertTrue(entries, "白名单不得为空")
        for name, reason in entries:
            self.assertTrue(
                reason.strip(),
                "白名单条目 %s 必须写明留在全局的理由" % name,
            )


# ---------------------------------------------------------------------------
# E. 规则 ④/⑤：helper 唯一权威
# ---------------------------------------------------------------------------
class HelperSingleAuthorityTests(unittest.TestCase):
    """公共 helper（escapeHtml / toast / showModal / closeModal）单一权威。"""

    @classmethod
    def setUpClass(cls):
        cls.app_js = _read(APP_JS)

    def test_app_js_helpers_delegate_to_core(self):
        for name in ("api", "toast", "showModal", "closeModal", "escapeHtml"):
            body = _function_body(self.app_js, name)
            self.assertTrue(body, "app.js 必须保留全局 helper：%s" % name)
            self.assertRegex(
                body,
                r"SAL\s*\.\s*core",
                "%s 必须委托给 SAL.core.*（唯一权威）" % name,
            )

    def test_app_js_does_not_reimplement_core_helpers(self):
        """classic 层不得保留第二份实现（必须是纯委托 facade）。"""
        for name in ("escapeHtml", "toast", "showModal", "closeModal"):
            body = _function_body(self.app_js, name)
            self.assertTrue(body)
            self.assertRegex(body, r"SAL\s*\.\s*core")


# ---------------------------------------------------------------------------
# F. Feature 契约完整性
# ---------------------------------------------------------------------------
class FeatureModuleContractTests(unittest.TestCase):
    """Feature 模块必须满足 ``meta`` / ``mount`` / ``unmount`` 契约。

    AR03-P3-F 之后：**应用级** 模块（timer / gacha）**不**实现该契约；
    它们的唯一权威是 ``app.entry.js`` 的 ``APP_SCOPED_MODULES`` 名单。
    """

    @classmethod
    def setUpClass(cls):
        cls.entry = _read(APP_ENTRY_JS)

    def _registry_names(self) -> list[str]:
        block = re.search(
            r"const\s+MODULE_CONTRACTS\s*=\s*\[([\s\S]*?)\];", self.entry
        )
        self.assertIsNotNone(block, "app.entry.js 必须声明 MODULE_CONTRACTS")
        return re.findall(r"name\s*:\s*'([^']+)'", block.group(1))

    def _app_scoped_names(self) -> list[str]:
        block = re.search(
            r"const\s+APP_SCOPED_MODULES\s*=\s*\[([\s\S]*?)\]", self.entry
        )
        self.assertIsNotNone(block, "app.entry.js 必须声明 APP_SCOPED_MODULES")
        return re.findall(r"'([^']+)'", block.group(1))

    def test_registry_modules_satisfy_the_contract(self):
        for name in self._registry_names():
            index = MODULES_DIR / name / "index.js"
            self.assertTrue(index.exists(), "注册模块必须有 index.js：%s" % name)
            source = _read(index)
            for required in ("meta", "mount", "unmount"):
                self.assertRegex(
                    source,
                    r"\b%s\b" % required,
                    "%s 缺少契约成员 %s" % (name, required),
                )

    def test_owner_factory_modules_export_create_owner(self):
        """未注册进 registry 的模块必须是 owner 工厂（createXxxOwner）。"""
        registry = set(self._registry_names())
        for directory in _feature_module_dirs():
            if directory.name in registry:
                continue
            index = directory / "index.js"
            self.assertTrue(index.exists())
            source = _read(index)
            self.assertRegex(
                source,
                r"\bexport\s+function\s+create\w*Owner\s*\(",
                "%s 未注册进 registry，必须是 owner 工厂" % directory.name,
            )

    def test_registry_and_app_scoped_lists_are_disjoint(self):
        """应用级模块绝不能同时注册进页面级 registry。"""
        registry = set(self._registry_names())
        app_scoped = set(self._app_scoped_names())
        overlap = sorted(registry & app_scoped)
        self.assertEqual(
            overlap,
            [],
            "这些模块既是应用级又注册进了页面级挂载流程：%s"
            % ", ".join(overlap),
        )


if __name__ == "__main__":
    unittest.main()
