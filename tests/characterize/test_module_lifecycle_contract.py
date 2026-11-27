"""AR03-P3-F：**应用级（app-scoped）vs 页面级（page-scoped）** 生命周期契约。

核心约束
--------
**页面切换不得让跨页面的全局能力停止运行。**

用户在 **任务页** 启动计时 → 切到 **其他页** → Dock 仍在显示、计时仍在走
→ 用户在另一页完成/取消计时。若 ``timer`` 随任务页 ``unmount`` 而停 tick /
清 session，会导致：Dock 时间停住、刷新后恢复不到、另一页无法结束计时
—— **这是功能回归，不是架构洁癖**。

同样地，抽卡 session / 换卡链是跨页面的连续概念：换卡链必须沿用同一个
session，离开抽卡页才结束 —— 因此 ``gacha`` 也是应用级。

分级语义
--------
| 级别                | 模块                    | 生命周期语义 |
|---------------------|-------------------------|--------------|
| 应用级 app-scoped   | ``timer`` / ``gacha``   | 应用启动即创建；**页面切换永不 unmount**。 |
| 页面级 page-scoped  | ``tasks`` / 其余页面模块 | ``page:change`` → ``mount`` / ``unmount``；``unmount`` 只释放**本模块自己的** interval / 监听，**不得**清掉其他模块的状态。 |

「是否重绘任务面板」是 **渲染层** 判断；「计时是否继续运行」是 **服务层**
判断 —— 两者不得互相牵连。

保护边界
--------
本文件 **只读** 仓库；不写任何文件；不触碰生产 DB / config / notes。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = PROJECT_ROOT / "static"
MODULES_DIR = STATIC_ROOT / "modules"
APP_JS = STATIC_ROOT / "app.js"
APP_ENTRY_JS = STATIC_ROOT / "app.entry.js"
TIMER_JS = MODULES_DIR / "timer" / "index.js"
GACHA_JS = MODULES_DIR / "gacha" / "index.js"
TASKS_JS = MODULES_DIR / "tasks" / "index.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def _feature_module_dirs() -> list[Path]:
    if not MODULES_DIR.exists():
        return []
    return sorted((p for p in MODULES_DIR.iterdir() if p.is_dir()), key=lambda p: p.name)


# ---------------------------------------------------------------------------
# A. 应用级名单的唯一权威在装配根
# ---------------------------------------------------------------------------
class AppScopedModuleListTests(unittest.TestCase):
    """``APP_SCOPED_MODULES`` 的唯一权威 = ``static/app.entry.js``。"""

    @classmethod
    def setUpClass(cls):
        cls.entry = _read(APP_ENTRY_JS)

    def _app_scoped_names(self) -> list[str]:
        block = re.search(
            r"const\s+APP_SCOPED_MODULES\s*=\s*\[([\s\S]*?)\]", self.entry
        )
        self.assertIsNotNone(
            block, "app.entry.js 必须显式声明 APP_SCOPED_MODULES（生命周期分级）"
        )
        return re.findall(r"'([^']+)'", block.group(1))

    def test_timer_is_app_scoped(self):
        """计时必须是应用级：页面切换永不 unmount。"""
        self.assertIn(
            "timer",
            self._app_scoped_names(),
            "timer 必须在 APP_SCOPED_MODULES 里（页面切换不得停掉计时）",
        )

    def test_gacha_is_app_scoped(self):
        """抽卡 session / 换卡链是跨页面连续概念 → 应用级。"""
        self.assertIn(
            "gacha",
            self._app_scoped_names(),
            "gacha 必须在 APP_SCOPED_MODULES 里（换卡链必须沿用同一 session）",
        )

    def test_app_scoped_list_is_not_empty_and_has_no_duplicates(self):
        names = self._app_scoped_names()
        self.assertTrue(names, "APP_SCOPED_MODULES 不得为空")
        self.assertEqual(
            len(names), len(set(names)), "APP_SCOPED_MODULES 不得有重复项"
        )

    def test_timer_is_not_in_the_page_level_registry(self):
        """应用级模块绝不能进 registry 的页面挂载/卸载流程。"""
        block = re.search(
            r"const\s+MODULE_CONTRACTS\s*=\s*\[([\s\S]*?)\];", self.entry
        )
        self.assertIsNotNone(block)
        registered = re.findall(r"name\s*:\s*'([^']+)'", block.group(1))
        self.assertNotIn(
            "timer",
            registered,
            "timer 是应用级模块，不得注册进页面级 MODULE_CONTRACTS",
        )

    def test_gacha_is_not_in_the_page_level_registry(self):
        block = re.search(
            r"const\s+MODULE_CONTRACTS\s*=\s*\[([\s\S]*?)\];", self.entry
        )
        self.assertIsNotNone(block)
        registered = re.findall(r"name\s*:\s*'([^']+)'", block.group(1))
        self.assertNotIn(
            "gacha",
            registered,
            "gacha 是应用级模块，不得注册进页面级 MODULE_CONTRACTS",
        )


# ---------------------------------------------------------------------------
# B. 应用级模块不得实现页面级契约
# ---------------------------------------------------------------------------
class AppScopedModulesHaveNoPageContractTests(unittest.TestCase):
    """``modules/timer/index.js`` / ``modules/gacha/index.js`` 不得导出
    页面级 ``meta`` / ``mount`` / ``unmount``。"""

    def test_timer_does_not_export_page_level_contract(self):
        source = _read(TIMER_JS)
        self.assertNotRegex(
            source,
            r"\bexport\s*\{[^}]*\bmeta\b[^}]*\}",
            "timer 是应用级模块，不得导出页面级 meta/mount/unmount 契约",
        )
        self.assertNotRegex(
            source,
            r"\bexport\s+default\s*\{[^}]*\bmount\b",
            "timer 是应用级模块，不得导出页面级 default 契约",
        )

    def test_gacha_does_not_export_page_level_contract(self):
        source = _read(GACHA_JS)
        self.assertNotRegex(
            source,
            r"\bexport\s*\{[^}]*\bmeta\b[^}]*\}",
            "gacha 是应用级模块，不得导出页面级 meta/mount/unmount 契约",
        )
        self.assertNotRegex(
            source,
            r"\bexport\s+default\s*\{[^}]*\bmount\b",
            "gacha 是应用级模块，不得导出页面级 default 契约",
        )

    def test_timer_module_has_no_page_mount_unmount_functions(self):
        """应用级模块内不得存在页面级 mount / unmount 实现。"""
        source = _read(TIMER_JS)
        for name in ("mount", "unmount"):
            self.assertEqual(
                _function_body(source, name),
                "",
                "modules/timer/index.js 不得定义页面级 %s()" % name,
            )

    def test_gacha_module_has_no_page_mount_unmount_functions(self):
        source = _read(GACHA_JS)
        for name in ("mount", "unmount"):
            self.assertEqual(
                _function_body(source, name),
                "",
                "modules/gacha/index.js 不得定义页面级 %s()" % name,
            )


# ---------------------------------------------------------------------------
# C. tick 启动不得与页面切换挂钩
# ---------------------------------------------------------------------------
class TickLifecycleTests(unittest.TestCase):
    """计时 tick 由 **装配阶段** 启动，**不随 page:change 停止**。

    机械判据：
      - ``page:change`` 处理器体内不得出现 tick 启动 / 停止调用；
      - ``startTick`` 的调用点不在任何页面切换路径上；
      - app.js 的 ``showPage``（页面切换入口）不得停止 tick。
    """

    @classmethod
    def setUpClass(cls):
        cls.timer = _read(TIMER_JS)
        cls.entry = _read(APP_ENTRY_JS)
        cls.app_js = _read(APP_JS)

    def test_page_change_handlers_do_not_touch_the_tick(self):
        """``page:change`` 订阅体内不得出现 tick 启停。"""
        found = False
        for match in re.finditer(r"page:change", self.entry):
            found = True
            window = self.entry[match.start(): match.start() + 1200]
            for token in ("startTick", "stopTick", "tickHandle"):
                self.assertNotIn(
                    token,
                    window,
                    "page:change 处理器不得触碰计时节拍（%s）" % token,
                )
        self.assertTrue(found, "app.entry.js 必须监听 page:change")

    def test_timer_tick_is_started_from_the_app_startup_path(self):
        """tick 由启动路径启动（initTimerDock 在 app.js 的启动块里）。"""
        startup_index = self.app_js.find("initTimerDock();")
        self.assertNotEqual(
            startup_index,
            -1,
            "initTimerDock() 必须在启动块里被调用（应用级启动）",
        )
        # 启动块位于文件末尾的「启动加载」分隔线之后。
        marker = self.app_js.find("// ============ 启动加载 ============")
        self.assertNotEqual(marker, -1)
        self.assertGreater(
            startup_index,
            marker,
            "initTimerDock() 必须属于启动加载段，而不是页面切换路径",
        )

    def test_show_page_does_not_stop_the_timer_tick(self):
        """页面切换（showPage）不得停止 **主节拍** 或清空活动 session。

        注意区分两个概念（AR03-P3-C）：
          - ``tickHandle``：**主节拍**，同时驱动 Dock 与任务面板。
            页面切换 **绝不** 停止它（否则 Dock 时间停住）。
          - ``inlineTickHandle``：**卡内局部显示**的节拍，只负责
            "已抽出的卡片上那个小计时器"的渲染。它读同一个 session，
            但句柄独立；离开抽卡页停止它属于既有语义（AR03-G08），
            不属于本条约束。
        """
        body = _function_body(self.app_js, "showPage")
        self.assertTrue(body, "showPage 必须存在")
        for token in ("stopTick", "clearInterval"):
            self.assertNotIn(
                token,
                body,
                "showPage 不得停止主计时节拍（%s）" % token,
            )
        # 不得清空 owner 的活动 session（clear() 会清 session + 句柄）。
        self.assertNotRegex(
            body,
            r"_timerOwner\s*\.\s*clear\s*\(\s*\)",
            "showPage 不得清空计时 owner 的活动 session",
        )
        # 不得直接操作主节拍句柄。
        self.assertNotIn(
            "tickHandle",
            body,
            "showPage 不得直接操作主节拍句柄 tickHandle",
        )

    def test_timer_owner_exposes_a_single_main_tick_handle(self):
        """唯一 **主节拍** 句柄（AR03-P3-C）：只有一个 tickHandle。

        ``inlineTickHandle`` 是卡内局部渲染的独立句柄（读同一个 session），
        不属于"主节拍"，因此不在本约束范围内。
        """
        handles = re.findall(r"\bvar\s+(\w*[Tt]ickHandle)\s*=", self.timer)
        main_handles = [h for h in handles if h == "tickHandle"]
        self.assertEqual(
            main_handles,
            ["tickHandle"],
            "计时 owner 必须只有一个主节拍句柄 tickHandle，实际：%s"
            % ", ".join(handles),
        )
        # 主节拍不得有第二份副本（例如 tickHandle2 / panelTickHandle）。
        suspicious = [
            h for h in handles
            if h not in ("tickHandle", "inlineTickHandle")
        ]
        self.assertEqual(
            suspicious,
            [],
            "不得出现第二个主节拍句柄：%s" % ", ".join(suspicious),
        )


# ---------------------------------------------------------------------------
# D. 页面级 unmount 不得清理应用级状态
# ---------------------------------------------------------------------------
class PageScopedUnmountIsolationTests(unittest.TestCase):
    """任何页面级模块的 ``unmount`` 都 **不得** 触碰 timer owner 的
    session / tick（否则页面切换会清掉进行中的计时）。"""

    FORBIDDEN = (
        "stopInlineTimer",
        "clearSession",
        "tickHandle",
        "stopTick",
        "endUnifiedGachaSession",
    )

    @classmethod
    def setUpClass(cls):
        cls.entry = _read(APP_ENTRY_JS)
        block = re.search(
            r"const\s+APP_SCOPED_MODULES\s*=\s*\[([\s\S]*?)\]", cls.entry
        )
        cls.app_scoped = set(re.findall(r"'([^']+)'", block.group(1))) if block else set()

    def test_page_scoped_unmount_never_touches_app_scoped_state(self):
        for directory in _feature_module_dirs():
            name = directory.name
            if name in self.app_scoped:
                continue
            index = directory / "index.js"
            if not index.exists():
                continue
            body = _function_body(_read(index), "unmount")
            if not body:
                continue
            for token in self.FORBIDDEN:
                self.assertNotIn(
                    token,
                    body,
                    "页面级模块 %s 的 unmount 不得触碰应用级状态（%s）"
                    % (name, token),
                )

    def test_page_scoped_unmount_never_calls_owner_clear(self):
        """``owner.clear()`` 会清空 session —— 页面级 unmount 绝不能调。"""
        for directory in _feature_module_dirs():
            name = directory.name
            if name in self.app_scoped:
                continue
            index = directory / "index.js"
            if not index.exists():
                continue
            body = _function_body(_read(index), "unmount")
            if not body:
                continue
            self.assertNotRegex(
                body,
                r"\.\s*clear\s*\(\s*\)",
                "页面级模块 %s 的 unmount 不得调用 owner.clear()" % name,
            )


# ---------------------------------------------------------------------------
# E. 装配根是唯一的 owner 创建点
# ---------------------------------------------------------------------------
class AssemblyRootTests(unittest.TestCase):
    """``static/app.entry.js`` 是 **唯一装配根**：owner 在装配阶段一次性创建。"""

    @classmethod
    def setUpClass(cls):
        cls.entry = _read(APP_ENTRY_JS)
        cls.app_js = _read(APP_JS)

    def test_entry_statically_imports_the_app_scoped_owners(self):
        """应用级 owner 必须 **静态 import**（装配期同步就绪）。"""
        self.assertRegex(
            self.entry,
            r"import\s+\*\s+as\s+timerModule\s+from\s+'\./modules/timer/index\.js'",
            "app.entry.js 必须静态 import 计时 owner 模块",
        )
        self.assertRegex(
            self.entry,
            r"from\s+'\./modules/gacha/index\.js'",
            "app.entry.js 必须静态 import 抽卡 owner 模块",
        )

    def test_entry_injects_the_timer_owner_at_assembly_time(self):
        """装配根必须把计时 owner 注入 classic 层（同步就绪）。"""
        self.assertIn(
            "window.__setTimerOwner",
            self.entry,
            "装配根必须注入唯一计时 owner",
        )
        self.assertIn(
            "window.__createTimerOwner",
            self.entry,
            "装配根必须经唯一工厂创建计时 owner",
        )

    def test_classic_layer_exposes_only_narrow_timer_assembly_interfaces(self):
        """classic 层只暴露 **装配接口**（窄 setter + 工厂），不暴露业务实现。"""
        self.assertRegex(
            self.app_js,
            r"window\.__setTimerOwner\s*=",
            "app.js 必须暴露 __setTimerOwner 装配接口",
        )
        self.assertRegex(
            self.app_js,
            r"window\.__createTimerOwner\s*=",
            "app.js 必须暴露 __createTimerOwner 装配工厂",
        )

    def test_app_entry_does_not_stop_app_scoped_owners_on_page_change(self):
        """装配根的页面切换调度不得卸载应用级模块。"""
        match = re.search(
            r"function\s+dispatchPage\s*\([^)]*\)\s*\{", self.entry
        )
        self.assertIsNotNone(match, "app.entry.js 必须有页面调度函数")
        body = _function_body(self.entry, "dispatchPage")
        self.assertNotIn(
            "timer",
            body,
            "页面调度不得触碰应用级 timer 模块",
        )
        self.assertNotIn(
            "gacha",
            body,
            "页面调度不得触碰应用级 gacha 模块",
        )


# ---------------------------------------------------------------------------
# F. 防空洞闸门：owner 必须真的被装配
# ---------------------------------------------------------------------------
class OwnerWiringProofTests(unittest.TestCase):
    """证明装配链 **真的存在**（防止上面的断言空洞地通过）。"""

    @classmethod
    def setUpClass(cls):
        cls.entry = _read(APP_ENTRY_JS)
        cls.app_js = _read(APP_JS)

    def test_timer_owner_factory_delegates_to_the_owner_module(self):
        """classic 层的工厂必须真的调用 owner 模块的 createTimerOwner。"""
        body = _function_body(self.app_js, "_createTimerOwnerFromModule")
        self.assertTrue(body, "app.js 必须保留 _createTimerOwnerFromModule 工厂")
        self.assertIn(
            "mod.createTimerOwner",
            body,
            "工厂必须调用 owner 模块的 createTimerOwner",
        )

    def test_gacha_app_scoped_hook_is_invoked_by_the_assembly_root(self):
        """抽卡的应用级启动钩子必须被装配根调用（否则是死代码）。"""
        self.assertIn(
            "initGachaAppScoped",
            self.entry,
            "装配根必须调用抽卡的应用级启动钩子",
        )

    def test_app_scoped_hook_is_idempotent(self):
        """应用级启动钩子必须幂等（绝不重复接线）。"""
        source = _read(GACHA_JS)
        body = _function_body(source, "initAppScoped")
        self.assertTrue(body, "gacha 必须提供 initAppScoped() 应用级钩子")
        self.assertIn(
            "_appScopedInitialized",
            body,
            "应用级启动钩子必须幂等（只做一次性全局接线）",
        )


# ---------------------------------------------------------------------------
# G. 唯一实例不变式（AR03-P3-F 修正）
# ---------------------------------------------------------------------------
class SingleOwnerInstanceTests(unittest.TestCase):
    """每个 owner 在整个应用生命周期内 **只允许存在一个实例**。

    背景（真实功能回归）
    --------------------
    ``static/app.js`` 是 classic script，在 **同步** 执行体末尾调用
    ``loadTimerPanel()`` / ``initTimerDock()``，两者都走
    ``_getTimerOwner()`` → **动态 import**（异步）。而
    ``static/app.entry.js`` 是 ``type=module``（deferred），在 app.js 的
    同步体 **之后** 才执行。

    于是两条路径可能 **各创建一个计时 owner**：

    - 实例 A：动态 import 兜底路径创建（tick 句柄在 A 上）；
    - 实例 B：装配根创建（用户点「开始」把 session 写进 B）。

    A 的 tick 每秒执行 ``updatePanel()``，而 A **没有** session →
    任务页计时面板被覆盖回「未在计时」。用户看到的症状是
    **「计时器不走动」** —— 这是功能回归，不是架构洁癖。

    同样的竞态对 ``tasks`` / ``free-card`` owner 同样成立（第二状态源）。

    因此本组断言锁定：
      1. classic 层的注入 setter 在 **已有 owner 时绝不替换**；
      2. classic 层的动态 import 兜底在创建前 **先检查** 已有 owner；
      3. 装配根在创建前 **先问** classic 层「是否已有 owner」。
    """

    @classmethod
    def setUpClass(cls):
        cls.app_js = _read(APP_JS)
        cls.entry = _read(APP_ENTRY_JS)

    # --- classic 层：注入 setter 绝不替换 ---------------------------------

    def test_set_timer_owner_never_replaces_an_existing_owner(self):
        body = _function_body(self.app_js, "_setTimerOwner")
        self.assertTrue(body, "app.js 必须保留 _setTimerOwner")
        self.assertIn(
            "if (_timerOwner)",
            body,
            "注入 setter 必须先判断是否已有 owner（已有则绝不替换）",
        )
        self.assertIn(
            "拒绝注入第二个实例",
            body,
            "注入第二个 owner 必须显式告警（不得静默）",
        )

    def test_set_tasks_owner_never_replaces_an_existing_owner(self):
        body = _function_body(self.app_js, "_setTasksOwner")
        self.assertTrue(body, "app.js 必须保留 _setTasksOwner")
        self.assertIn(
            "if (_tasksOwner)",
            body,
            "注入 setter 必须先判断是否已有 owner（已有则绝不替换）",
        )

    def test_set_free_card_owner_never_replaces_an_existing_owner(self):
        body = _function_body(self.app_js, "_setFreeCardOwner")
        self.assertTrue(body, "app.js 必须保留 _setFreeCardOwner")
        self.assertIn(
            "if (_freeCardOwner)",
            body,
            "注入 setter 必须先判断是否已有 owner（已有则绝不替换）",
        )

    # --- classic 层：动态 import 兜底先检查 -------------------------------

    def test_timer_dynamic_import_fallback_reuses_an_existing_owner(self):
        body = _function_body(self.app_js, "_getTimerOwner")
        self.assertTrue(body, "app.js 必须保留 _getTimerOwner")
        self.assertIn(
            "if (_timerOwner) return _timerOwner;",
            body,
            "动态 import 兜底创建前必须复用已有 owner（绝不创建第二个）",
        )

    def test_tasks_dynamic_import_fallback_reuses_an_existing_owner(self):
        body = _function_body(self.app_js, "_getTasksOwner")
        self.assertTrue(body, "app.js 必须保留 _getTasksOwner")
        self.assertIn(
            "if (_tasksOwner) return _tasksOwner;",
            body,
            "动态 import 兜底创建前必须复用已有 owner（绝不创建第二个）",
        )

    def test_free_card_dynamic_import_fallback_reuses_an_existing_owner(self):
        body = _function_body(self.app_js, "_getFreeCardOwner")
        self.assertTrue(body, "app.js 必须保留 _getFreeCardOwner")
        self.assertIn(
            "if (_freeCardOwner) return _freeCardOwner;",
            body,
            "动态 import 兜底创建前必须复用已有 owner（绝不创建第二个）",
        )

    # --- classic 层：暴露同步读取接口 ------------------------------------

    def test_classic_layer_exposes_sync_owner_probes(self):
        """装配根必须能 **同步** 问「是否已有 owner」。"""
        for name in (
            "__getTimerOwnerSync",
            "__getTasksOwnerSync",
            "__getFreeCardOwnerSync",
        ):
            self.assertIn(
                "window." + name,
                self.app_js,
                "app.js 必须暴露 " + name + " 同步探针",
            )

    # --- 装配根：创建前先问 ----------------------------------------------

    def test_entry_reuses_an_existing_timer_owner_before_creating_one(self):
        self.assertIn(
            "__getTimerOwnerSync",
            self.entry,
            "装配根必须先问 classic 层是否已有计时 owner",
        )
        self.assertIn(
            "existing",
            self.entry,
            "装配根必须保存「已有 owner」的查询结果",
        )

    def test_entry_reuses_an_existing_tasks_owner_before_creating_one(self):
        self.assertIn(
            "__getTasksOwnerSync",
            self.entry,
            "装配根必须先问 classic 层是否已有任务 owner",
        )

    def test_entry_reuses_an_existing_free_card_owner_before_creating_one(self):
        self.assertIn(
            "__getFreeCardOwnerSync",
            self.entry,
            "装配根必须先问 classic 层是否已有自由卡 owner",
        )

    # --- 语义保护：owner 数量必须真的被约束 ------------------------------

    def test_only_one_timer_owner_can_be_reachable_through_the_classic_layer(self):
        """classic 层的计时 owner 引用点必须 **只有一个变量**。

        若将来有人再加一个 ``_timerOwner2`` 之类的第二引用点，本断言
        会立刻失败 —— 因为那意味着「两份 session 源」。
        """
        matches = re.findall(r"var\s+_timerOwner(?![A-Za-z])\s*=", self.app_js)
        self.assertEqual(
            1,
            len(matches),
            "classic 层只能有一个计时 owner 引用点（发现多个：%r）" % (matches,),
        )


if __name__ == "__main__":
    unittest.main()
