"""P1 切片 4/5：Frontend Micro Kernel 契约测试（纯静态 + 合成运行期）。

本文件验证 P1 的 **内核真的在运行期存在**，而不是"文件存在但从未加载"：

  A. 加载合同
     - ``src/index.html`` 必须加载全部 ``static/core/*`` 与 ``static/shared/*``
       脚本，且 **全部在 app.js 之前**（classic script 顺序依赖）；
     - ``core/*`` 与 ``shared/*`` 下 **任何** .js 文件都不得游离在 index.html 之外。

  B. 运行期合同（Node 合成页面）
     - 加载 index.html 声明的 core/shared 脚本后，``window.SAL.core.*`` 与
       ``window.SAL.shared.*`` 的 **全部** 能力必须真实存在；
     - ``SAL.core.registry`` 的 register / mount / unmount 契约可用；
     - ``SAL.core.router`` 的 hash 解析可用；
     - ``SAL.core.state`` 的 subscribe / get / set 可用；
     - ``SAL.core.ui`` 的 escapeHtml / toast / showModal / closeModal 可用。

  C. 模块契约
     - 每个 Feature 模块必须导出 ``meta`` / ``mount`` / ``unmount``；
     - ``core/*`` 与 ``shared/*`` **不得** import ``modules/*``（内核不反向依赖业务）。

  D. 边界机械检查
     - 调用 ``scripts/check_module_imports.js``，断言退出码 0。

本文件是 **纯合成** 测试：只在 ``tempfile`` 临时目录里写 Node 脚本；
绝不触碰真实 ``data/task_publisher.db``(±wal/shm)、``config/config.json``、
``src/notes/**``；不启动真实 Web 服务。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parents[1]
STATIC_ROOT = PROJECT_ROOT / "static"
INDEX_HTML = PROJECT_ROOT / "src" / "index.html"

#: 必须在运行期真实存在的 core 能力（app.entry.js 的 reportBoot 也检查同一份）。
REQUIRED_CORE = (
    "eventBus",
    "api",
    "ui",
    "theme",
    "router",
    "state",
    "constants",
    "registry",
)

#: ``SAL.core.ui.*`` 的子能力。
REQUIRED_CORE_UI = ("modal", "toast", "theme", "sandbox", "xss")

#: ``SAL.shared.*`` 的子能力。
REQUIRED_SHARED = ("timer", "xss", "formatters")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _index_script_paths() -> list:
    """index.html 中所有 ``<script src="...">`` 的静态路径（去掉 /static/ 与 ?v=）。"""
    html = _read(INDEX_HTML)
    out = []
    for match in re.finditer(r"<script[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", html):
        src = match.group(1)
        if not src.startswith("/static/"):
            continue
        rel = src[len("/static/"):].split("?")[0]
        out.append(rel)
    return out


def _core_and_shared_files() -> list:
    """core/ 与 shared/ 下的全部 .js（相对 static/ 的路径）。"""
    out = []
    for folder in ("core", "shared"):
        base = STATIC_ROOT / folder
        for path in sorted(base.rglob("*.js")):
            out.append(path.relative_to(STATIC_ROOT).as_posix())
    return out


# ===========================================================================
# A. 加载合同
# ===========================================================================


class IndexHtmlLoadingContractTests(unittest.TestCase):
    """src/index.html 必须真的加载内核脚本。"""

    def setUp(self):
        self.paths = _index_script_paths()
        self.html = _read(INDEX_HTML)

    def test_every_core_and_shared_script_is_loaded(self):
        loaded = set(self.paths)
        missing = [rel for rel in _core_and_shared_files() if rel not in loaded]
        self.assertEqual(
            missing, [],
            "这些内核脚本从未被 index.html 加载（运行期不存在）：" + ", ".join(missing),
        )

    def test_kernel_scripts_are_loaded_before_app_js(self):
        if "app.js" not in self.paths:
            self.skipTest("index.html 未加载 app.js")
        app_index = self.paths.index("app.js")
        kernel = [
            rel for rel in self.paths
            if (rel.startswith("core/") or rel.startswith("shared/"))
            and rel != "core/theme-init.js"
        ]
        late = [rel for rel in kernel if self.paths.index(rel) > app_index]
        self.assertEqual(
            late, [],
            "内核脚本必须在 app.js **之前** 加载（app.js 委托 SAL.core.*）",
        )

    def test_app_entry_module_is_loaded(self):
        self.assertIn("app.entry.js", self.paths)


# ===========================================================================
# B. 运行期合同（Node 合成页面）
# ===========================================================================

_NODE_HARNESS = r"""
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const STATIC_ROOT = process.env.SAL_STATIC_ROOT;
const INDEX_HTML = process.env.SAL_INDEX_HTML;

// index.html 声明的 core/shared 脚本（按声明顺序）。
const html = fs.readFileSync(INDEX_HTML, 'utf8');
const scripts = [];
const re = /<script[^>]*\bsrc\s*=\s*["']([^"']+)["'][^>]*>/g;
let m;
while ((m = re.exec(html)) !== null) {
  const src = m[1];
  if (!src.startsWith('/static/')) continue;
  const rel = src.slice('/static/'.length).split('?')[0];
  if (rel.startsWith('core/') || rel.startsWith('shared/')) scripts.push(rel);
}

// 极简 DOM stub：内核脚本只需要 window / document 的一点点。
const noopEl = {
  classList: { add() {}, remove() {}, contains() { return false; } },
  style: { setProperty() {} },
  appendChild() {},
  remove() {},
  setAttribute() {},
  getAttribute() { return null; },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {}
};
const documentStub = {
  documentElement: noopEl,
  body: noopEl,
  head: noopEl,
  getElementById() { return null; },
  createElement() { return Object.assign({}, noopEl); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  removeEventListener() {},
  readyState: 'complete'
};

const sandbox = {
  document: documentStub,
  console: console,
  location: { hash: '' },
  addEventListener() {},
  removeEventListener() {},
  setTimeout: function () { return 0; },
  clearTimeout() {},
  setInterval: function () { return 0; },
  clearInterval() {},
  Promise: Promise,
  JSON: JSON,
  Math: Math,
  Date: Date,
  isFinite: isFinite,
  Object: Object,
  Array: Array,
  String: String,
  Number: Number,
  Boolean: Boolean,
  Error: Error,
  Proxy: Proxy,
  Reflect: Reflect,
  Map: Map,
  Set: Set,
  Symbol: Symbol
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

const ctx = vm.createContext(sandbox);
scripts.forEach(function (rel) {
  vm.runInContext(
    fs.readFileSync(path.join(STATIC_ROOT, rel), 'utf8'),
    ctx,
    { filename: rel }
  );
});

const out = { loaded: scripts, results: {} };
const R = out.results;

const SAL = sandbox.SAL || {};
const core = SAL.core || {};
const shared = SAL.shared || {};

R.coreKeys = Object.keys(core);
R.sharedKeys = Object.keys(shared);
R.uiKeys = core.ui ? Object.keys(core.ui) : [];
R.missingCore = [];
R.missingCoreUi = [];
R.missingShared = [];
process.env.SAL_REQUIRED_CORE.split(',').forEach(function (k) {
  if (!core[k]) R.missingCore.push(k);
});
process.env.SAL_REQUIRED_CORE_UI.split(',').forEach(function (k) {
  if (!core.ui || !core.ui[k]) R.missingCoreUi.push(k);
});
process.env.SAL_REQUIRED_SHARED.split(',').forEach(function (k) {
  if (!shared[k]) R.missingShared.push(k);
});

// ---- registry 契约 ----
if (core.registry) {
  const calls = [];
  core.registry.register('demo', { name: 'demo', version: '1.0.0', deps: [] },
    function (rootEl, c) { calls.push('mount:' + c.page); },
    function () { calls.push('unmount'); });
  R.registryRegistered = core.registry.has('demo');
  R.registryList = core.registry.list();
  R.registryMounted = core.registry.mount('demo', { page: 'demo' });
  R.registryIsMounted = core.registry.isMounted('demo');
  R.registryUnmounted = core.registry.unmount('demo');
  R.registryCalls = calls;
  // 重复注册必须 fail closed（抛错）
  try {
    core.registry.register('demo', { name: 'demo' }, function () {}, function () {});
    R.registryDuplicateRejected = false;
  } catch (e) {
    R.registryDuplicateRejected = true;
  }
  // 缺 mount 的模块必须 fail closed
  try {
    core.registry.register('broken', { name: 'broken' }, null, function () {});
    R.registryIncompleteRejected = false;
  } catch (e) {
    R.registryIncompleteRejected = true;
  }
}

// ---- router 契约 ----
if (core.router) {
  R.routerParseGacha = core.router.parseHash('#gacha');
  R.routerParseUnknown = core.router.parseHash('#not-a-page');
  R.routerCurrent = core.router.getCurrentPage();
  R.routerKnown = core.router.isKnownPage('gacha');
  R.routerUnknownKnown = core.router.isKnownPage('not-a-page');
}

// ---- state 契约 ----
if (core.state && typeof core.state.createStore === 'function') {
  const store = core.state.createStore({ count: 0 });
  const seen = [];
  store.subscribe('count', function (v, meta) { seen.push([v, meta.key]); });
  store.count = 7;
  R.stateSeen = seen;
  R.stateGet = store.get('count');
  R.stateSnapshot = store.snapshot();
  R.stateSubscriberCount = store.subscriberCount();
}

// ---- ui 契约 ----
if (core.ui) {
  R.uiEscape = core.ui.escapeHtml('<b>&"x"</b>');
  R.uiHasToast = typeof core.ui.toast === 'function';
  R.uiHasShowModal = typeof core.ui.showModal === 'function';
  R.uiHasCloseModal = typeof core.ui.closeModal === 'function';
}

// ---- shared 契约 ----
if (shared.timer) {
  // shared/timer 是只读视图：set 必须 fail closed。
  try {
    shared.timer.set({ session: { id: 1 } });
    R.sharedTimerWriteRejected = false;
  } catch (e) {
    R.sharedTimerWriteRejected = true;
  }
  R.sharedTimerSnapshot = shared.timer.get();
}

process.stdout.write(JSON.stringify(out));
"""


class KernelRuntimeContractTests(unittest.TestCase):
    """合成页面里内核能力必须真实存在。"""

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node 不可用，跳过内核运行期测试")
        cls.node = node
        cls._tmp = tempfile.TemporaryDirectory(
            prefix="lt_p1_kernel_", ignore_cleanup_errors=True
        )
        tmp_root = Path(cls._tmp.name)
        harness = tmp_root / "harness.js"
        harness.write_text(_NODE_HARNESS, encoding="utf-8")
        env = dict(os.environ)
        env["SAL_STATIC_ROOT"] = str(STATIC_ROOT)
        env["SAL_INDEX_HTML"] = str(INDEX_HTML)
        env["SAL_REQUIRED_CORE"] = ",".join(REQUIRED_CORE)
        env["SAL_REQUIRED_CORE_UI"] = ",".join(REQUIRED_CORE_UI)
        env["SAL_REQUIRED_SHARED"] = ",".join(REQUIRED_SHARED)
        result = subprocess.run(
            [node, str(harness)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(tmp_root),
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(
                "Node harness 失败 (exit=%s):\n%s" % (result.returncode, result.stderr)
            )
        cls.out = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls):
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_all_required_core_capabilities_exist(self):
        self.assertEqual(
            self.out["results"]["missingCore"], [],
            "这些 SAL.core.* 能力在运行期不存在",
        )

    def test_all_required_core_ui_capabilities_exist(self):
        self.assertEqual(
            self.out["results"]["missingCoreUi"], [],
            "这些 SAL.core.ui.* 能力在运行期不存在",
        )

    def test_all_required_shared_capabilities_exist(self):
        self.assertEqual(
            self.out["results"]["missingShared"], [],
            "这些 SAL.shared.* 能力在运行期不存在",
        )

    def test_registry_registers_mounts_and_unmounts(self):
        r = self.out["results"]
        self.assertTrue(r["registryRegistered"])
        self.assertIn("demo", r["registryList"])
        self.assertTrue(r["registryMounted"])
        self.assertTrue(r["registryIsMounted"])
        self.assertTrue(r["registryUnmounted"])
        self.assertEqual(r["registryCalls"], ["mount:demo", "unmount"])

    def test_registry_fails_closed_on_bad_registration(self):
        r = self.out["results"]
        self.assertTrue(r["registryDuplicateRejected"], "重复注册必须 fail closed")
        self.assertTrue(
            r["registryIncompleteRejected"], "缺 mount 的注册必须 fail closed"
        )

    def test_router_parses_hash_routes(self):
        r = self.out["results"]
        self.assertEqual(r["routerParseGacha"], "gacha")
        self.assertIsNone(r["routerParseUnknown"])
        self.assertEqual(r["routerCurrent"], "gacha")
        self.assertTrue(r["routerKnown"])
        self.assertFalse(r["routerUnknownKnown"])

    def test_state_store_is_observable(self):
        r = self.out["results"]
        self.assertEqual(r["stateSeen"], [[7, "count"]])
        self.assertEqual(r["stateGet"], 7)
        self.assertEqual(r["stateSnapshot"]["count"], 7)
        self.assertGreaterEqual(r["stateSubscriberCount"], 1)

    def test_ui_helpers_escape_and_expose_facade(self):
        r = self.out["results"]
        self.assertNotIn("<b>", r["uiEscape"])
        self.assertIn("&lt;b&gt;", r["uiEscape"])
        self.assertTrue(r["uiHasToast"])
        self.assertTrue(r["uiHasShowModal"])
        self.assertTrue(r["uiHasCloseModal"])

    def test_shared_timer_is_read_only(self):
        r = self.out["results"]
        self.assertTrue(
            r["sharedTimerWriteRejected"],
            "shared/timer.set 必须 fail closed（唯一写者是 modules/timer）",
        )
        self.assertIn("session", r["sharedTimerSnapshot"])


# ===========================================================================
# C. 模块契约
# ===========================================================================


class FeatureModuleContractTests(unittest.TestCase):
    """Feature 模块必须满足契约，且注册清单与实现一致。"""

    def _registry_module_names(self):
        source = _read(STATIC_ROOT / "app.entry.js")
        block = re.search(
            r"const\s+MODULE_CONTRACTS\s*=\s*\[([\s\S]*?)\];", source
        )
        self.assertIsNotNone(block, "app.entry.js 必须有 MODULE_CONTRACTS 注册清单")
        return re.findall(r"name\s*:\s*['\"]([^'\"]+)['\"]", block.group(1))

    def test_registry_modules_satisfy_the_meta_mount_unmount_contract(self):
        registry = set(self._registry_module_names())
        self.assertTrue(registry, "注册清单为空")
        for name in sorted(registry):
            with self.subTest(module=name):
                index = STATIC_ROOT / "modules" / name / "index.js"
                self.assertTrue(index.exists(), name + " 缺少 index.js")
                source = _read(index)
                for required in ("meta", "mount", "unmount"):
                    self.assertIn(
                        required,
                        source,
                        "{}/index.js 必须导出 {}".format(name, required),
                    )

    def test_owner_factory_modules_are_not_registry_modules(self):
        """未注册的模块必须是 owner 工厂（导出 createXxxOwner）。"""
        registry = set(self._registry_module_names())
        modules_dir = STATIC_ROOT / "modules"
        for entry in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
            if entry.name in registry:
                continue
            with self.subTest(module=entry.name):
                source = _read(entry / "index.js")
                self.assertRegex(
                    source,
                    r"export\s+function\s+create\w*Owner\s*\(",
                    "{}/index.js 必须是 owner 工厂（导出 createXxxOwner(deps)）".format(
                        entry.name
                    ),
                )

    def test_core_and_shared_do_not_import_modules(self):
        """内核不反向依赖业务模块。"""
        offenders = []
        for rel in _core_and_shared_files():
            source = _read(STATIC_ROOT / rel)
            for match in re.finditer(
                r"(?:^|\n)\s*(?:import|export)\b[^\n;]*?from\s*['\"]([^'\"]+)['\"]",
                source,
            ):
                spec = match.group(1)
                if "modules/" in spec or spec.startswith("../modules"):
                    offenders.append(rel + " → " + spec)
            if re.search(r"import\s*\(\s*['\"][^'\"]*modules/", source):
                offenders.append(rel + " → 动态 import modules/")
        self.assertEqual(
            offenders, [],
            "core/* 与 shared/* 不得 import modules/*（内核不反向依赖业务）",
        )


# ===========================================================================
# D. 边界机械检查
# ===========================================================================


class ModuleBoundaryScriptTests(unittest.TestCase):
    """scripts/check_module_imports.js 必须退出码 0。"""

    def test_boundary_script_passes(self):
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node 不可用，跳过边界脚本测试")
        script = PROJECT_ROOT / "scripts" / "check_module_imports.js"
        self.assertTrue(script.exists(), "缺少 scripts/check_module_imports.js")
        result = subprocess.run(
            [node, str(script)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(
            result.returncode, 0,
            "模块边界检查失败：\n%s\n%s" % (result.stdout, result.stderr),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
