# -*- coding: utf-8 -*-
"""AR03-G15.4：弃牌 / 恢复 owner（Discard-Restore Owner）characterization 测试。

覆盖：

1. ``static/modules/tasks/lifecycle.js`` 的**行为契约** —— 把源码复制到
   ``tempfile`` 临时目录的 ``lifecycle.mjs``，用 Node 内建能力动态 import，
   依赖全部是**合成 stub**（不触碰真实 DB / notes / 配置 / 服务）。
2. ``static/app.js`` 三个同名全局 facade 的 **null-safe 委托契约** —— 从
   app.js 源码抽取 facade 函数片段，在 Node ``vm`` 沙箱里执行（owner 存在 /
   不存在两种情形）。
3. ``static/app.js`` / ``static/app.entry.js`` / ``static/modules/tasks/
   presentation.js`` 的**结构约束**（源码级断言）。

只使用 Python 标准库 + Node 内建能力；不安装任何第三方依赖。
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_JS = REPO_ROOT / "static" / "modules" / "tasks" / "lifecycle.js"
APP_JS = REPO_ROOT / "static" / "app.js"
APP_ENTRY_JS = REPO_ROOT / "static" / "app.entry.js"
PRESENTATION_JS = REPO_ROOT / "static" / "modules" / "tasks" / "presentation.js"
#: AR03-P3-A：自由卡流程的 **真实 owner**（ESM owner）。
FREE_CARD_JS = REPO_ROOT / "static" / "modules" / "free-card" / "index.js"

FACADE_NAMES = ("moveToDiscard", "loadDiscardPileList", "restoreFromDiscard")

# ---------------------------------------------------------------------------
# Node 沙箱 harness（合成依赖 + 行为探针 + facade vm 抽取）
# ---------------------------------------------------------------------------
_HARNESS_JS = r"""
import fs from 'node:fs';
import vm from 'node:vm';
import { createTaskLifecycleOwner } from './lifecycle.mjs';

const appJsPath = process.argv[2];
const out = { scenarios: {}, facade: {}, syntax: {}, error: null };

function safe(v) {
  if (typeof v === 'function') return '[fn]';
  if (v === undefined) return null;
  if (v instanceof Error) return '[error:' + v.message + ']';
  try { return JSON.parse(JSON.stringify(v)); } catch (e) { return '[unserializable]'; }
}

function makeOwner(cfg) {
  cfg = cfg || {};
  const calls = [];
  const rec = function (name, args) {
    calls.push({ name: name, args: (args || []).map(safe) });
  };
  const deps = {
    api: function (url, opts) {
      rec('api', [{
        url: url,
        method: opts ? opts.method : null,
        body: opts && opts.body ? opts.body : null
      }]);
      if (cfg.apiHandler) return cfg.apiHandler(url, opts);
      if (Object.prototype.hasOwnProperty.call(cfg, 'apiError')) {
        return Promise.reject(new Error(cfg.apiError));
      }
      if (url === '/api/discard-pile') {
        return Promise.resolve(cfg.listResult || []);
      }
      return Promise.resolve(cfg.apiResult || {});
    },
    toast: function (m, t) { rec('toast', [m, t]); },
    loadTasks: function () { rec('loadTasks', []); },
    refreshGachaStats: function () { rec('refreshGachaStats', []); },
    updateDiscardPileVisual: function () { rec('updateDiscardPileVisual', []); },
    getDiscardPileMessage: function () {
      rec('getDiscardPileMessage', []);
      return '先放一边，等状态好的时候再试试';
    }
  };
  if (!cfg.omitPlayCardAnim) {
    deps.playCardAnim = function (id, cls) {
      rec('playCardAnim', [id, cls]);
      return Promise.resolve();
    };
  }
  if (!cfg.omitConfirm) {
    deps.confirmDiscardRestore = function (id, name) {
      rec('confirmDiscardRestore', [id, name]);
      if (cfg.confirmHandler) return cfg.confirmHandler(id, name);
      return true;
    };
  }
  if (!cfg.omitRenderAdapters) {
    deps.renderDiscardPileLoading = function () {
      rec('renderDiscardPileLoading', []);
      return cfg.loadingResult === false ? false : true;
    };
    deps.renderDiscardPileEmpty = function () { rec('renderDiscardPileEmpty', []); };
    deps.renderDiscardPileItems = function (items) {
      rec('renderDiscardPileItems', [items]);
    };
    deps.renderDiscardPileError = function () { rec('renderDiscardPileError', []); };
  }
  const owner = createTaskLifecycleOwner(deps);
  return { owner: owner, calls: calls };
}

function names(calls) { return calls.map(function (c) { return c.name; }); }
function pick(calls, name) {
  return calls.filter(function (c) { return c.name === name; })
    .map(function (c) { return c.args; });
}
function count(calls, name) {
  return calls.filter(function (c) { return c.name === name; }).length;
}
function summarize(calls) {
  return {
    steps: names(calls),
    api: pick(calls, 'api'),
    toasts: pick(calls, 'toast'),
    playCardAnim: pick(calls, 'playCardAnim'),
    renderDiscardPileLoading: pick(calls, 'renderDiscardPileLoading'),
    renderDiscardPileEmpty: pick(calls, 'renderDiscardPileEmpty'),
    renderDiscardPileItems: pick(calls, 'renderDiscardPileItems'),
    renderDiscardPileError: pick(calls, 'renderDiscardPileError'),
    confirmDiscardRestore: pick(calls, 'confirmDiscardRestore'),
    apiCount: count(calls, 'api'),
    animCount: count(calls, 'playCardAnim'),
    loadCount: count(calls, 'loadTasks'),
    statsCount: count(calls, 'refreshGachaStats'),
    visualCount: count(calls, 'updateDiscardPileVisual'),
    confirmCount: count(calls, 'confirmDiscardRestore'),
    loadingCount: count(calls, 'renderDiscardPileLoading'),
    emptyCount: count(calls, 'renderDiscardPileEmpty'),
    itemsCount: count(calls, 'renderDiscardPileItems'),
    errorCount: count(calls, 'renderDiscardPileError')
  };
}

async function tick(n) {
  for (let i = 0; i < (n || 10); i += 1) {
    await Promise.resolve();
  }
}

async function main() {
  // --- 1. 手动弃牌：正常调用顺序 ----------------------------------------
  {
    const h = makeOwner({});
    await h.owner.moveToDiscard(7);
    out.scenarios.move_to_discard = summarize(h.calls);
  }

  // --- 1b. 手动弃牌：API 失败 --------------------------------------------
  {
    const h = makeOwner({ apiError: 'boom' });
    await h.owner.moveToDiscard(8);
    out.scenarios.move_to_discard_api_failed = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: '' });
    await h.owner.moveToDiscard(9);
    out.scenarios.move_to_discard_api_failed_empty = summarize(h.calls);
  }

  // --- 1c. 手动弃牌：动画适配器缺失 → fail closed，绝不 POST -------------
  {
    const h = makeOwner({ omitPlayCardAnim: true });
    await h.owner.moveToDiscard(10);
    out.scenarios.move_to_discard_no_anim = summarize(h.calls);
  }

  // --- 2. 弃牌列表：非空 / 空 / 失败 / 容器缺失 -------------------------
  {
    const h = makeOwner({ listResult: [{ id: 3, name: 'x' }, { id: 4, name: 'y' }] });
    await h.owner.loadDiscardPileList();
    out.scenarios.list_items = summarize(h.calls);
  }
  {
    const h = makeOwner({ listResult: [] });
    await h.owner.loadDiscardPileList();
    out.scenarios.list_empty = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: 'boom' });
    await h.owner.loadDiscardPileList();
    out.scenarios.list_failed = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: '' });
    await h.owner.loadDiscardPileList();
    out.scenarios.list_failed_empty = summarize(h.calls);
  }
  {
    const h = makeOwner({ loadingResult: false });
    await h.owner.loadDiscardPileList();
    out.scenarios.list_no_container = summarize(h.calls);
  }
  {
    const h = makeOwner({ omitRenderAdapters: true });
    await h.owner.loadDiscardPileList();
    out.scenarios.list_no_render_adapters = summarize(h.calls);
  }

  // --- 3. 手动恢复 -------------------------------------------------------
  {
    const h = makeOwner({});
    await h.owner.restoreFromDiscard(21, '任务名');
    await tick(20);
    out.scenarios.restore_ok = summarize(h.calls);
  }
  {
    const h = makeOwner({ confirmHandler: function () { return false; } });
    await h.owner.restoreFromDiscard(22, '任务名');
    await tick(20);
    out.scenarios.restore_cancelled = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiHandler: function (url) {
      if (url.indexOf('/restore') >= 0) return Promise.reject(new Error('boom'));
      return Promise.resolve([]);
    } });
    await h.owner.restoreFromDiscard(23, '任务名');
    await tick(20);
    out.scenarios.restore_api_failed = summarize(h.calls);
  }
  {
    const h = makeOwner({ omitConfirm: true });
    await h.owner.restoreFromDiscard(24, '任务名');
    await tick(20);
    out.scenarios.restore_no_confirm = summarize(h.calls);
  }

  // --- 4. app.js facade：null-safe + 委托 ------------------------------
  const appSrc = fs.readFileSync(appJsPath, 'utf8');
  try {
    new vm.Script(appSrc, { filename: 'app.js' });
    out.syntax.app_js = true;
  } catch (e) {
    out.syntax.app_js = false;
    out.syntax.app_js_error = String(e && e.message);
  }

  function extractFunction(src, name) {
    const marker = 'function ' + name + '(';
    const idx = src.indexOf(marker);
    if (idx < 0) return null;
    const braceIdx = src.indexOf('{', idx);
    if (braceIdx < 0) return null;
    let depth = 0;
    let inStr = null;
    let inLine = false;
    let inBlock = false;
    for (let i = braceIdx; i < src.length; i += 1) {
      const ch = src[i];
      const nx = src[i + 1];
      if (inLine) { if (ch === '\n') inLine = false; continue; }
      if (inBlock) { if (ch === '*' && nx === '/') { inBlock = false; i += 1; } continue; }
      if (inStr) {
        if (ch === '\\') { i += 1; continue; }
        if (ch === inStr) inStr = null;
        continue;
      }
      if (ch === '/' && nx === '/') { inLine = true; i += 1; continue; }
      if (ch === '/' && nx === '*') { inBlock = true; i += 1; continue; }
      if (ch === '"' || ch === "'" || ch === '`') { inStr = ch; continue; }
      if (ch === '{') depth += 1;
      else if (ch === '}') {
        depth -= 1;
        if (depth === 0) return src.slice(idx, i + 1);
      }
    }
    return null;
  }

  function runFacade(code, windowObj) {
    const toasts = [];
    const ctx = {
      window: windowObj,
      toast: function (m, t) { toasts.push([m, t]); },
      console: console
    };
    vm.createContext(ctx);
    vm.runInContext(code, ctx);
    return { ctx: ctx, toasts: toasts };
  }

  for (const name of ['moveToDiscard', 'loadDiscardPileList', 'restoreFromDiscard']) {
    const code = extractFunction(appSrc, name);
    if (code === null) {
      out.facade[name] = { found: false };
      continue;
    }
    const missing = runFacade(code, {});
    let missingThrew = null;
    try { await missing.ctx[name](123, '名字'); } catch (e) { missingThrew = String(e && e.message); }

    const delegated = [];
    const ownerObj = {};
    ownerObj[name] = function () {
      delegated.push(Array.prototype.slice.call(arguments));
      return 'delegated-' + name;
    };
    const present = runFacade(code, { __taskLifecycleOwner: ownerObj });
    let presentThrew = null;
    let presentRet = null;
    try { presentRet = await present.ctx[name](123, '名字'); }
    catch (e) { presentThrew = String(e && e.message); }

    out.facade[name] = {
      found: true,
      missing_threw: missingThrew,
      missing_toasts: missing.toasts,
      present_threw: presentThrew,
      present_return: safe(presentRet),
      delegated: delegated
    };
  }
}

try {
  await main();
} catch (e) {
  out.error = String(e && e.stack ? e.stack : e);
}

process.stdout.write(JSON.stringify(out));
"""


class DiscardRestoreOwnerTest(unittest.TestCase):
    """G15.4 弃牌 / 恢复 owner 的行为与边界契约。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="lt_g15_4_discardrestore_")
        try:
            shutil.copyfile(str(LIFECYCLE_JS), os.path.join(cls._tmp, "lifecycle.mjs"))
            harness = os.path.join(cls._tmp, "harness.mjs")
            with open(harness, "w", encoding="utf-8") as fh:
                fh.write(_HARNESS_JS)
            proc = subprocess.run(
                ["node", harness, str(APP_JS)],
                cwd=cls._tmp,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
            )
            cls.node_stdout = proc.stdout or ""
            cls.node_stderr = proc.stderr or ""
            cls.node_returncode = proc.returncode
            try:
                cls.result = json.loads(cls.node_stdout)
            except Exception as exc:  # pragma: no cover - 诊断用
                raise AssertionError(
                    "Node harness 输出无法解析（rc=%s）：%s / stderr=%s"
                    % (proc.returncode, cls.node_stdout[:2000], cls.node_stderr[:2000])
                ) from exc
        finally:
            pass

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    # -- helpers ----------------------------------------------------------
    def scenarios(self):
        self.assertIsNone(
            self.result.get("error"),
            "Node harness 运行失败：%s" % self.result.get("error"),
        )
        return self.result["scenarios"]

    # -- 0. harness --------------------------------------------------------
    def test_harness_ran(self):
        """harness 必须真实执行（node 可用、无运行时错误）。"""
        self.assertEqual(0, self.node_returncode,
                         "Node harness 返回码非 0：%s" % self.node_stderr[:2000])
        self.assertIsNone(self.result.get("error"))

    # -- 1. 手动弃牌 -------------------------------------------------------
    def test_move_to_discard_full_order(self):
        s = self.scenarios()["move_to_discard"]
        steps = s["steps"]
        self.assertEqual(1, s["apiCount"], "手动弃牌必须只发一个业务 API")
        self.assertEqual(1, s["animCount"], "手动弃牌必须执行卡片动画")
        self.assertEqual(1, s["loadCount"], "手动弃牌必须刷新任务列表")
        self.assertEqual(1, s["visualCount"], "手动弃牌必须刷新弃牌堆视觉")
        self.assertLess(steps.index("api"), steps.index("playCardAnim"))
        self.assertLess(steps.index("playCardAnim"), steps.index("toast"))
        self.assertLess(steps.index("toast"), steps.index("loadTasks"))
        self.assertLess(steps.index("loadTasks"), steps.index("updateDiscardPileVisual"))

    def test_move_to_discard_endpoint_anim_and_toast(self):
        s = self.scenarios()["move_to_discard"]
        call = s["api"][0][0]
        self.assertEqual("/api/tasks/7/move-to-discard", call["url"],
                         "手动弃牌端点必须保持不变")
        self.assertEqual("POST", call["method"], "手动弃牌必须保持 POST")
        self.assertEqual([[7, "is-discarding"]], s["playCardAnim"],
                         "动画类必须保持 is-discarding")
        self.assertEqual([["先放一边，等状态好的时候再试试", "inf"]], s["toasts"],
                         "成功提示文案与类型必须保持不变")

    def test_move_to_discard_api_failure_stops_success_steps(self):
        s = self.scenarios()["move_to_discard_api_failed"]
        self.assertEqual(1, s["apiCount"], "失败场景仍只发一个 API")
        self.assertEqual([["boom", "err"]], s["toasts"],
                         "必须显示实际错误 message")
        self.assertEqual(0, s["animCount"], "失败后不得执行动画")
        self.assertEqual(0, s["loadCount"], "失败后不得刷新任务列表")
        self.assertEqual(0, s["visualCount"], "失败后不得刷新弃牌堆视觉")

    def test_move_to_discard_api_failure_empty_message_uses_fallback(self):
        s = self.scenarios()["move_to_discard_api_failed_empty"]
        self.assertEqual([["操作失败", "err"]], s["toasts"],
                         "空 message 必须回退到「操作失败」")

    def test_move_to_discard_missing_anim_never_posts(self):
        s = self.scenarios()["move_to_discard_no_anim"]
        self.assertEqual(0, s["apiCount"],
                         "动画适配器缺失时手动弃牌绝不能 POST")
        self.assertEqual(0, s["animCount"])
        self.assertEqual(0, s["loadCount"])
        self.assertEqual(0, s["visualCount"])
        self.assertEqual(1, len(s["toasts"]),
                         "动画适配器缺失时必须给出错误提示")
        self.assertEqual("err", s["toasts"][0][1],
                         "动画适配器缺失提示必须是错误类型")

    # -- 2. 弃牌列表 -------------------------------------------------------
    def test_list_items_flow(self):
        s = self.scenarios()["list_items"]
        steps = s["steps"]
        self.assertEqual(1, s["loadingCount"], "必须先渲染加载态")
        self.assertEqual(1, s["apiCount"], "只发一个 GET")
        self.assertEqual(1, s["itemsCount"], "非空列表必须交给列表渲染适配器")
        self.assertEqual(0, s["emptyCount"], "非空列表不得渲染空态")
        self.assertEqual(0, s["errorCount"], "非空列表不得渲染错误态")
        self.assertLess(steps.index("renderDiscardPileLoading"), steps.index("api"))
        self.assertLess(steps.index("api"), steps.index("renderDiscardPileItems"))
        call = s["api"][0][0]
        self.assertEqual("/api/discard-pile", call["url"], "弃牌列表端点必须保持不变")
        self.assertIsNone(call["method"], "弃牌列表必须保持 GET")
        self.assertEqual([[[{"id": 3, "name": "x"}, {"id": 4, "name": "y"}]]],
                         s["renderDiscardPileItems"],
                         "服务端顺序必须原样交给渲染适配器")

    def test_list_empty_flow(self):
        s = self.scenarios()["list_empty"]
        self.assertEqual(1, s["loadingCount"], "必须先渲染加载态")
        self.assertEqual(1, s["apiCount"], "空列表也必须请求一次")
        self.assertEqual(1, s["emptyCount"], "空数组必须渲染空态")
        self.assertEqual(0, s["itemsCount"], "空数组不得渲染列表")
        self.assertEqual([], s["toasts"], "空列表不得弹提示")

    def test_list_failure_flow(self):
        s = self.scenarios()["list_failed"]
        self.assertEqual(1, s["loadingCount"])
        self.assertEqual(1, s["errorCount"], "失败必须渲染错误态")
        self.assertEqual(0, s["itemsCount"], "失败后不得渲染列表")
        self.assertEqual([["boom", "err"]], s["toasts"],
                         "失败必须显示实际错误 message")
        e = self.scenarios()["list_failed_empty"]
        self.assertEqual([["弃牌堆加载失败", "err"]], e["toasts"],
                         "空 message 必须回退到「弃牌堆加载失败」")

    def test_list_no_container_never_requests(self):
        s = self.scenarios()["list_no_container"]
        self.assertEqual(0, s["apiCount"],
                         "容器不存在时不得发起任何请求")
        self.assertEqual(0, s["itemsCount"])

    def test_list_missing_render_adapters_never_requests(self):
        s = self.scenarios()["list_no_render_adapters"]
        self.assertEqual(0, s["apiCount"],
                         "渲染适配器缺失时不得发起任何请求（fail closed）")

    # -- 3. 手动恢复 -------------------------------------------------------
    def test_restore_ok_order_and_body(self):
        s = self.scenarios()["restore_ok"]
        steps = s["steps"]
        self.assertEqual(1, s["confirmCount"], "恢复必须先走确认适配器")
        self.assertEqual([[21, "任务名"]], s["confirmDiscardRestore"],
                         "确认适配器必须收到任务 id 与名称")
        restore_calls = [c for c in s["api"] if "/restore" in c[0]["url"]]
        self.assertEqual(1, len(restore_calls), "恢复必须只发一个恢复 API")
        self.assertEqual("/api/discard-pile/21/restore", restore_calls[0][0]["url"],
                         "恢复端点必须保持不变")
        self.assertEqual("POST", restore_calls[0][0]["method"])
        self.assertEqual("{}", restore_calls[0][0]["body"],
                         "恢复请求 body 必须保持 {}")
        self.assertEqual(1, s["statsCount"], "恢复必须刷新抽卡统计")
        self.assertEqual(1, s["visualCount"], "恢复必须刷新弃牌堆视觉")
        self.assertEqual(1, s["loadCount"], "恢复必须刷新任务列表")
        self.assertEqual(1, s["loadingCount"], "恢复必须刷新弃牌列表")
        self.assertLess(steps.index("confirmDiscardRestore"), steps.index("api"))
        self.assertLess(steps.index("api"), steps.index("toast"))
        self.assertLess(steps.index("toast"), steps.index("loadTasks"))
        self.assertLess(steps.index("loadTasks"), steps.index("refreshGachaStats"))
        self.assertLess(steps.index("refreshGachaStats"),
                        steps.index("updateDiscardPileVisual"))
        self.assertIn(["已恢复任务", "suc"], s["toasts"],
                      "成功提示文案与类型必须保持不变")

    def test_restore_cancelled_never_posts(self):
        s = self.scenarios()["restore_cancelled"]
        self.assertEqual(1, s["confirmCount"], "必须调用确认适配器")
        self.assertEqual(0, s["apiCount"], "用户取消时零 POST")
        self.assertEqual(0, s["loadCount"], "用户取消时不得刷新任务列表")
        self.assertEqual(0, s["statsCount"], "用户取消时不得刷新抽卡统计")
        self.assertEqual(0, s["visualCount"], "用户取消时不得刷新弃牌堆视觉")
        self.assertEqual(0, s["loadingCount"], "用户取消时不得刷新弃牌列表")
        self.assertEqual([], s["toasts"], "用户取消时不得弹提示")

    def test_restore_api_failure_skips_success_refresh(self):
        s = self.scenarios()["restore_api_failed"]
        self.assertEqual(1, s["confirmCount"])
        self.assertEqual([["boom", "err"]], s["toasts"],
                         "恢复失败必须显示实际错误 message")
        self.assertEqual(0, s["loadCount"], "恢复失败后不得刷新任务列表")
        self.assertEqual(0, s["statsCount"], "恢复失败后不得刷新抽卡统计")
        self.assertEqual(0, s["visualCount"], "恢复失败后不得刷新弃牌堆视觉")
        self.assertEqual(0, s["loadingCount"], "恢复失败后不得刷新弃牌列表")

    def test_restore_missing_confirm_never_posts(self):
        s = self.scenarios()["restore_no_confirm"]
        self.assertEqual(0, s["apiCount"],
                         "确认适配器缺失时绝不能 POST")
        self.assertEqual(0, s["loadCount"])
        self.assertEqual(0, s["statsCount"])
        self.assertEqual(0, s["visualCount"])
        self.assertEqual(1, len(s["toasts"]),
                         "确认适配器缺失时必须给出错误提示")
        self.assertEqual("err", s["toasts"][0][1],
                         "确认适配器缺失提示必须是错误类型")

    # -- 4. app.js facade --------------------------------------------------
    def test_app_js_facades_are_null_safe_and_delegate(self):
        for name in FACADE_NAMES:
            f = self.result["facade"][name]
            self.assertTrue(f.get("found"), "app.js 必须保留入口名 %s" % name)
            self.assertIsNone(f["missing_threw"],
                              "owner 缺失时 %s 不得抛异常" % name)
            self.assertEqual(1, len(f["missing_toasts"]),
                             "owner 缺失时 %s 必须提示模块未就绪" % name)
            self.assertEqual("err", f["missing_toasts"][0][1])
            self.assertIsNone(f["present_threw"],
                              "owner 存在时 %s 不得抛异常" % name)
            expected = {
                "moveToDiscard": [[123]],
                "loadDiscardPileList": [[]],
                "restoreFromDiscard": [[123, "名字"]],
            }[name]
            self.assertEqual(expected, f["delegated"],
                             "owner 存在时 %s 必须委托给 owner" % name)

    # -- 5. 架构边界 -------------------------------------------------------
    def test_lifecycle_js_has_no_dom_or_global_access(self):
        src = LIFECYCLE_JS.read_text(encoding="utf-8")
        for token in ("window", "document", "globalThis"):
            self.assertNotIn(
                token, src,
                "lifecycle.js 不得出现 %s（DOM / 全局访问必须经注入适配器）" % token,
            )

    def test_app_entry_injects_discard_restore_dependencies(self):
        src = APP_ENTRY_JS.read_text(encoding="utf-8")
        for token in (
            "renderDiscardPileLoading",
            "renderDiscardPileEmpty",
            "renderDiscardPileItems",
            "renderDiscardPileError",
            "confirmDiscardRestore",
            "getDiscardPileMessage",
        ):
            self.assertIn(token, src, "app.entry.js 必须注入 %s" % token)
        self.assertIn(
            "get: function () { return taskLifecycleOwner; }",
            src,
            "window.__taskLifecycleOwner 必须保持只读 getter",
        )
        self.assertEqual(
            1,
            len(re.findall(r"createTaskLifecycleOwner\s*\(", src)),
            "不得建立第二个 Task Lifecycle Owner",
        )

    def test_app_js_keeps_dom_adapters_and_pure_dom_entries(self):
        src = APP_JS.read_text(encoding="utf-8")
        for name in (
            "openDiscardPileModal",
            "closeDiscardPileModal",
            "formatDiscardTime",
            "discardTaskStatus",
            "renderDiscardPileLoading",
            "renderDiscardPileEmpty",
            "renderDiscardPileItems",
            "renderDiscardPileError",
            "confirmDiscardRestore",
        ):
            self.assertRegex(
                src,
                r"function\s+" + re.escape(name) + r"\s*\(",
                "app.js 必须保留 DOM 适配器 / 纯 DOM 入口 %s" % name,
            )
        self.assertIn("var REPEAT_LABELS = {", src, "app.js 必须保留 REPEAT_LABELS")
        self.assertIn("确定将「", src, "恢复确认框文案必须逐字保留在 classic 层")

    def test_app_js_no_longer_holds_discard_restore_business_orchestration(self):
        src = APP_JS.read_text(encoding="utf-8")
        for token in (
            "/api/discard-pile",
            "is-discarding",
            "已恢复任务",
        ):
            self.assertNotIn(
                token, src,
                "app.js 不得再持有弃牌 / 恢复的业务编排（含 %s）" % token,
            )
        # 自由卡顺利结束路径的 /complete + /move-to-discard 属于另一条业务路径。
        # AR03-P3-A：自由卡流程的实现已归位到 owner 模块
        # （static/modules/free-card/index.js）—— 该路径的 move-to-discard
        # 调用随之迁入 owner，classic app.js 只保留薄 facade。
        free_card_src = FREE_CARD_JS.read_text(encoding="utf-8")
        self.assertIn(
            "/api/tasks/' + numericId + '/move-to-discard'",
            free_card_src,
            "自由卡顺利结束路径的 move-to-discard 调用必须保持不变",
        )

    def test_presentation_inline_handler_unchanged(self):
        src = PRESENTATION_JS.read_text(encoding="utf-8")
        self.assertIn('onclick="moveToDiscard(\'', src,
                      "任务列表弃牌按钮的 inline handler 名必须保持")

    def test_app_js_syntax_is_valid(self):
        self.assertTrue(self.result["syntax"].get("app_js"),
                        "app.js 语法必须有效：%s"
                        % self.result["syntax"].get("app_js_error"))


if __name__ == "__main__":
    unittest.main()
