# -*- coding: utf-8 -*-
"""AR03-G15：任务生命周期 owner（startTask / confirmComplete / completeWithFeedback）
characterization 测试。

覆盖三件事：

1. ``static/modules/tasks/lifecycle.js`` 的**行为契约** —— 把源码复制到
   ``tempfile`` 临时目录的 ``lifecycle.mjs``，用 Node 内建能力动态 import，
   依赖全部是**合成 stub**（不触碰真实 DB / Vault / notes / 服务）。
2. ``static/app.js`` 三个同名全局 facade 的 **null-safe 委托契约** —— 从
   app.js 源码抽取 facade 函数片段，在 Node ``vm`` 沙箱里执行（owner 存在 /
   不存在两种情形）。
3. ``static/app.js`` 与 ``static/app.entry.js`` 的**结构约束**（源码级断言）。

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

FACADE_NAMES = ("startTask", "confirmComplete", "completeWithFeedback")

# ---------------------------------------------------------------------------
# Node 沙箱 harness（合成依赖 + 行为探针 + facade vm 抽取）
# ---------------------------------------------------------------------------
_HARNESS_JS = r"""
import fs from 'node:fs';
import vm from 'node:vm';
import { createTaskLifecycleOwner } from './lifecycle.mjs';

const appJsPath = process.argv[2];
const appEntryPath = process.argv[3];
const out = { scenarios: {}, facade: {}, syntax: {}, error: null };

const GETTER_NAMES = ['getTasks', 'getDrawnTask', 'getMultiDrawResults',
  'getTimerOwner', 'getCurrentTimerOwner', 'prereqHint'];

function safe(v) {
  if (typeof v === 'function') return '[fn]';
  if (v === undefined) return null;
  if (v instanceof Error) return '[error:' + v.message + ']';
  try { return JSON.parse(JSON.stringify(v)); } catch (e) { return '[unserializable]'; }
}

function baseCfg() {
  return {
    allTasks: [],
    drawn: null,
    multi: [],
    timerSession: null,
    actualMinutes: 1,
    timerOwnerError: null,
    startSessionError: null,
    completeSessionError: null,
    renderStatus: 'RENDERED',
    apiHandler: null,
    prereqHintText: '',
    currentTimerOwner: undefined,
    normalizeCardType: function (v) {
      if (typeof v !== 'string') return 'standard';
      var allowed = ['standard', 'free', 'micro', 'goal'];
      for (var i = 0; i < allowed.length; i += 1) { if (allowed[i] === v) return v; }
      return 'standard';
    }
  };
}

function createHarness(overrides) {
  const cfg = Object.assign(baseCfg(), overrides || {});
  const calls = [];
  const push = function (name, args) {
    calls.push({ name: name, args: (args || []).map(safe) });
  };
  const timerOwner = {
    getSnapshot: function () {
      push('getSnapshot', [cfg.timerSession]);
      return { session: cfg.timerSession, paused: false, pausedElapsedMs: 0 };
    },
    getActualMinutes: function () { push('getActualMinutes', []); return cfg.actualMinutes; },
    startSession: async function (p) {
      push('startSession', [p]);
      if (cfg.startSessionError) throw cfg.startSessionError;
      return { ok: true };
    },
    completeSession: async function (p) {
      push('completeSession', [p]);
      if (cfg.completeSessionError) throw cfg.completeSessionError;
      return { ok: true };
    },
    stopInlineTimer: function () { push('stopInlineTimer', []); },
    clear: function () { push('clear', []); }
  };
  const api = async function (url, opts) {
    push('api', [url, opts]);
    if (cfg.apiHandler) return cfg.apiHandler(url, opts);
    return {};
  };
  const owner = createTaskLifecycleOwner({
    getTasks: function () { push('getTasks', []); return cfg.allTasks; },
    getDrawnTask: function () { push('getDrawnTask', []); return cfg.drawn; },
    getMultiDrawResults: function () { push('getMultiDrawResults', []); return cfg.multi; },
    getTimerOwner: async function () {
      push('getTimerOwner', []);
      if (cfg.timerOwnerError) throw cfg.timerOwnerError;
      return timerOwner;
    },
    getCurrentTimerOwner: function () {
      push('getCurrentTimerOwner', []);
      return cfg.currentTimerOwner === undefined ? timerOwner : cfg.currentTimerOwner;
    },
    startInlineTimer: function (id) { push('startInlineTimer', [id]); },
    refreshTimerViews: function () { push('refreshTimerViews', []); },
    resetReplaceChain: function () { push('resetReplaceChain', []); },
    openFreeCardAcceptForm: function (id) { push('openFreeCardAcceptForm', [id]); },
    renderTaskRightPanel: function (id, html) {
      push('renderTaskRightPanel', [id, html]);
      return cfg.renderStatus;
    },
    flyDrawnCardToDiscard: async function (id) { push('flyDrawnCardToDiscard', [id]); },
    loadTasks: function () { push('loadTasks', []); },
    refreshGachaStats: function () { push('refreshGachaStats', []); },
    updateDiscardPileVisual: function () { push('updateDiscardPileVisual', []); },
    openFeedbackModalForTask: function (id, cat, fe) { push('openFeedbackModalForTask', [id, cat, fe]); },
    api: api,
    toast: function (m, t) { push('toast', [m, t]); },
    normalizeCardType: cfg.normalizeCardType,
    prereqHint: function (task) { push('prereqHint', [task ? task.id : null]); return cfg.prereqHintText; }
  });
  return { owner: owner, calls: calls, cfg: cfg };
}

function summarize(calls) {
  const pick = function (n) {
    return calls.filter(function (x) { return x.name === n; }).map(function (x) { return x.args; });
  };
  return {
    steps: calls.map(function (x) { return x.name; })
      .filter(function (n) { return GETTER_NAMES.indexOf(n) < 0; }),
    toasts: pick('toast'),
    startSession: pick('startSession').map(function (a) { return a[0]; }),
    completeSession: pick('completeSession').map(function (a) { return a[0]; }),
    api: pick('api'),
    rendered: pick('renderTaskRightPanel'),
    feedback: pick('openFeedbackModalForTask'),
    freeCard: pick('openFreeCardAcceptForm'),
    snapshots: pick('getSnapshot').map(function (a) { return a[0]; })
  };
}

function stdTask(id, extra) {
  return Object.assign({ id: id, name: 'task-' + id, is_unlocked: true, task_type: 'standard', estimated_time: 20 }, extra || {});
}

async function main() {
  // --- 1. 非法 ID 一律提示「任务不存在」，且不启动计时 -------------------
  {
    const h = createHarness({ allTasks: [stdTask(1)] });
    const bads = ['abc', 0, -3, null, undefined, 1.5, NaN];
    for (const bad of bads) { await h.owner.startTask(bad); }
    out.scenarios.invalid_ids = summarize(h.calls);
    out.scenarios.invalid_ids.count = bads.length;
  }

  // --- 2. 查找优先级：drawn > multiDrawResults > allTasks ----------------
  {
    const h = createHarness({
      allTasks: [stdTask(1, { name: 'catalog' })],
      multi: [stdTask(2, { name: 'multi' })],
      drawn: stdTask(2, { name: 'drawn', estimated_time: 60 })
    });
    await h.owner.startTask(2);
    out.scenarios.drawn_priority = summarize(h.calls);
  }
  {
    const h = createHarness({
      allTasks: [stdTask(1, { name: 'catalog' })],
      multi: [stdTask(3, { name: 'multi' })],
      drawn: null
    });
    await h.owner.startTask(3);
    out.scenarios.multi_priority = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [stdTask(1, { name: 'catalog' })], multi: [], drawn: null });
    await h.owner.startTask(1);
    out.scenarios.catalog_priority = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [], multi: [], drawn: null });
    await h.owner.startTask(999);
    out.scenarios.not_found = summarize(h.calls);
  }

  // --- 3. 未解锁：提示前置依赖，且不 resetReplaceChain / 不启动计时 ------
  {
    const h = createHarness({
      allTasks: [stdTask(9, { is_unlocked: false })],
      prereqHintText: '等待前置：X'
    });
    await h.owner.startTask(9);
    out.scenarios.locked = summarize(h.calls);
  }

  // --- 4. 自由卡：只委派 openFreeCardAcceptForm，且释放 pending lock -----
  {
    const h = createHarness({ allTasks: [stdTask(10, { task_type: 'free' })] });
    await h.owner.startTask(10);
    out.scenarios.free_card = summarize(h.calls);
    h.cfg.allTasks = [stdTask(11)];
    await h.owner.startTask(11);
    out.scenarios.free_card_then_other = summarize(h.calls);
  }

  // --- 5. 计划分钟：仅接受 1..480 的有限整数，否则 30 -------------------
  {
    const cases = [45, 0, 481, '30', 'abc', null, 30.5, 1, 480];
    out.scenarios.planned = [];
    let id = 100;
    for (const est of cases) {
      const h = createHarness({ allTasks: [stdTask(id, { estimated_time: est })] });
      await h.owner.startTask(id);
      const s = summarize(h.calls);
      out.scenarios.planned.push({
        est: safe(est),
        planned: s.startSession.length ? s.startSession[0].plannedMinutes : null
      });
      id += 1;
    }
  }

  // --- 6. pending lock：同 ID 并发只启动一次，finally 释放 ---------------
  {
    const h = createHarness({ allTasks: [stdTask(20)] });
    const first = h.owner.startTask(20);
    await h.owner.startTask(20);
    await first;
    out.scenarios.lock_while_pending = summarize(h.calls);
    await h.owner.startTask(20);
    out.scenarios.lock_after_release = summarize(h.calls);
  }

  // --- 7. renderTaskRightPanel 三种状态 --------------------------------
  {
    const h = createHarness({ allTasks: [stdTask(30)], renderStatus: 'CARD_MISSING' });
    await h.owner.startTask(30);
    out.scenarios.card_missing = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [stdTask(31)], renderStatus: 'PANEL_MISSING' });
    await h.owner.startTask(31);
    out.scenarios.panel_missing = summarize(h.calls);
  }

  // --- 8. 计时启动失败：只 toast + 恢复「开始任务」按钮 ------------------
  {
    const h = createHarness({ allTasks: [stdTask(32)], startSessionError: new Error('boom') });
    await h.owner.startTask(32);
    out.scenarios.timer_start_failed = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [stdTask(33)], timerOwnerError: new Error('load fail') });
    await h.owner.startTask(33);
    out.scenarios.timer_owner_failed = summarize(h.calls);
  }

  // --- 9. confirmComplete ----------------------------------------------
  {
    const h = createHarness({ allTasks: [stdTask(40)], timerOwnerError: new Error('x') });
    await h.owner.confirmComplete(40);
    out.scenarios.confirm_owner_failed = summarize(h.calls);
  }
  {
    const h = createHarness({
      allTasks: [stdTask(41)],
      timerSession: { id: 's1', task_id: 41 },
      completeSessionError: new Error('stop failed')
    });
    await h.owner.confirmComplete(41);
    out.scenarios.confirm_complete_failed = summarize(h.calls);
  }
  {
    const h = createHarness({
      allTasks: [stdTask(42)],
      timerSession: { id: 's2', task_id: 42 },
      actualMinutes: 7
    });
    await h.owner.confirmComplete(42);
    out.scenarios.confirm_ok = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [stdTask(43)], timerSession: null });
    await h.owner.confirmComplete(43);
    out.scenarios.confirm_no_session = summarize(h.calls);
  }

  // --- 10. completeWithFeedback 成功顺序 --------------------------------
  {
    const h = createHarness({
      allTasks: [stdTask(50, { category: 'study' })],
      apiHandler: function (url) {
        if (url.indexOf('/complete') >= 0) return { unlocked_tasks: ['51'] };
        return {};
      }
    });
    await h.owner.completeWithFeedback(50);
    out.scenarios.complete_ok = summarize(h.calls);
  }
  {
    const h = createHarness({
      allTasks: [stdTask(52)],
      apiHandler: function () { throw new Error('complete failed'); }
    });
    await h.owner.completeWithFeedback(52);
    out.scenarios.complete_failed = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [stdTask(53)] });
    await h.owner.completeWithFeedback(53, { finishEarly: true });
    out.scenarios.complete_finish_early = summarize(h.calls);
  }
  {
    const h = createHarness({ allTasks: [stdTask(54)], currentTimerOwner: null });
    await h.owner.completeWithFeedback(54);
    out.scenarios.complete_no_timer_owner = summarize(h.calls);
  }

  // --- 11. Gacha 状态只读：owner 不修改注入的数组/对象 -------------------
  {
    const tasks = [stdTask(60)];
    const multi = [stdTask(61)];
    const drawn = stdTask(62);
    const before = JSON.stringify([tasks, multi, drawn]);
    const h = createHarness({ allTasks: tasks, multi: multi, drawn: drawn });
    await h.owner.startTask(62);
    await h.owner.completeWithFeedback(60);
    out.scenarios.readonly = {
      unchanged: JSON.stringify([tasks, multi, drawn]) === before
    };
  }

  // --- 12. app.js facade：null-safe + 委托 ------------------------------
  const appSrc = fs.readFileSync(appJsPath, 'utf8');
  // 语法体检：app.js 是 classic script，app.entry.js 是 ESM module。
  try {
    new vm.Script(appSrc, { filename: 'app.js' });
    out.syntax.app_js = true;
  } catch (e) {
    out.syntax.app_js = false;
    out.syntax.app_js_error = String(e && e.message);
  }
  try {
    if (typeof vm.SourceTextModule === 'function') {
      new vm.SourceTextModule(fs.readFileSync(appEntryPath, 'utf8'), { identifier: 'app.entry.js' });
      out.syntax.app_entry_js = true;
    } else {
      out.syntax.app_entry_js = 'skipped-no-source-text-module';
    }
  } catch (e) {
    out.syntax.app_entry_js = false;
    out.syntax.app_entry_js_error = String(e && e.message);
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

  const FACADES = ['startTask', 'confirmComplete', 'completeWithFeedback'];
  for (const name of FACADES) {
    const code = extractFunction(appSrc, name);
    if (code === null) {
      out.facade[name] = { found: false };
      continue;
    }
    const missing = runFacade(code, {});
    let missingThrew = null;
    try { missing.ctx[name](123); } catch (e) { missingThrew = String(e && e.message); }

    const delegated = [];
    const ownerObj = {
      startTask: function (id) { delegated.push(['startTask', id]); return 'delegated-start'; },
      confirmComplete: function (id) { delegated.push(['confirmComplete', id]); return 'delegated-confirm'; },
      completeWithFeedback: function (id, opts) { delegated.push(['completeWithFeedback', id, opts]); return 'delegated-complete'; }
    };
    const present = runFacade(code, { __taskLifecycleOwner: ownerObj });
    let presentThrew = null;
    let presentRet = null;
    try { presentRet = present.ctx[name](123, { finishEarly: true }); }
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


def _extract_js_function(src, name):
    """从 JS 源码里抽取 ``function name(...) {...}`` 的完整函数体文本。"""
    marker = "function %s(" % name
    idx = src.find(marker)
    if idx < 0:
        return None
    brace = src.find("{", idx)
    if brace < 0:
        return None
    depth = 0
    i = brace
    in_str = None
    while i < len(src):
        ch = src[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'`":
            in_str = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[idx:i + 1]
        i += 1
    return None


class TaskLifecycleOwnerTest(unittest.TestCase):
    """AR03-G15 任务生命周期 owner characterization（唯一主测试）。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="sal-g15-lifecycle-")
        cls.tmp_root = Path(cls._tmp.name)
        cls.node = shutil.which("node")
        if cls.node is None:
            raise unittest.SkipTest("node 不在 PATH 上，跳过 AR03-G15 生命周期 owner 测试")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _run_harness(self):
        """把 lifecycle.js 复制成临时 .mjs，跑 Node harness，返回结果 dict。"""
        self.assertTrue(
            LIFECYCLE_JS.exists(),
            "AR03-G15：static/modules/tasks/lifecycle.js 尚不存在（唯一预期 baseline 失败点）",
        )
        harness_path = self.tmp_root / "harness.mjs"
        harness_path.write_text(_HARNESS_JS, encoding="utf-8")
        lifecycle_copy = self.tmp_root / "lifecycle.mjs"
        lifecycle_copy.write_text(
            LIFECYCLE_JS.read_text(encoding="utf-8"), encoding="utf-8"
        )
        proc = subprocess.run(
            [self.node, str(harness_path), str(APP_JS), str(APP_ENTRY_JS)],
            cwd=str(self.tmp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(
            0,
            proc.returncode,
            "Node harness 退出码非 0：\nstdout=%s\nstderr=%s" % (proc.stdout, proc.stderr),
        )
        try:
            return json.loads(proc.stdout)
        except ValueError as exc:  # pragma: no cover - 诊断路径
            self.fail("Node harness 输出不是合法 JSON（%s）：\n%s\n%s" % (exc, proc.stdout, proc.stderr))

    # -- 断言小工具 --------------------------------------------------------
    def _steps(self, scenario):
        return scenario["steps"]

    def _index(self, scenario, name):
        steps = self._steps(scenario)
        self.assertIn(name, steps, "步骤序列中缺少 %s：%s" % (name, steps))
        return steps.index(name)

    def test_task_lifecycle_owner(self):
        app_js = APP_JS.read_text(encoding="utf-8")
        app_entry_js = APP_ENTRY_JS.read_text(encoding="utf-8")

        # === 0. 唯一业务实现确实落在新模块里 ==============================
        self.assertTrue(LIFECYCLE_JS.exists(), "static/modules/tasks/lifecycle.js 不存在")
        lifecycle_src = LIFECYCLE_JS.read_text(encoding="utf-8")
        self.assertIn(
            "export function createTaskLifecycleOwner",
            lifecycle_src,
            "lifecycle.js 必须导出 createTaskLifecycleOwner(deps)",
        )
        self.assertNotRegex(
            lifecycle_src, r"\bwindow\b", "lifecycle.js 不得访问宿主全局对象"
        )
        self.assertNotRegex(
            lifecycle_src, r"\bdocument\b", "lifecycle.js 不得访问 DOM"
        )
        self.assertNotRegex(
            lifecycle_src, r"^\s*import\s", "lifecycle.js 不得 import 任何模块"
        )
        self.assertIn(
            "计时已开始，加油！", lifecycle_src, "计时成功提示文案必须逐字保留在 owner 内"
        )

        # === 1. app.js：旧业务实现已移除，facade + 两个 adapter 就位 ======
        self.assertNotIn(
            "_pendingStartTaskId", app_js, "app.js 不得再持有 pending lock"
        )
        self.assertNotIn(
            "计时已开始，加油！", app_js, "app.js 不得保留 startTask 业务实现"
        )
        self.assertNotIn(
            "停止计时失败，任务未完成", app_js, "app.js 不得保留 confirmComplete 业务实现"
        )
        for token in ("CARD_MISSING", "PANEL_MISSING", "RENDERED"):
            self.assertIn(token, app_js, "renderTaskRightPanel 必须返回 %s" % token)

        # facade 函数体必须是「只委托、不含业务」的薄壳
        for name in FACADE_NAMES:
            body = _extract_js_function(app_js, name)
            self.assertIsNotNone(body, "app.js 缺少 facade：%s" % name)
            self.assertIn(
                "__taskLifecycleOwner", body, "facade %s 必须委托 window.__taskLifecycleOwner" % name
            )
            self.assertNotIn(
                "/api/tasks/", body, "facade %s 不得残留任何业务 API 调用" % name
            )
        self.assertIn(
            "async function flyCardToDiscard(cardEl)",
            app_js,
            "既有 flyCardToDiscard(cardEl) 签名不得改动",
        )
        for name in FACADE_NAMES:
            self.assertRegex(
                app_js,
                r"function\s+%s\s*\(" % name,
                "app.js 必须保留同名全局 facade：%s" % name,
            )
        self.assertIn(
            "function renderTaskRightPanel(", app_js, "app.js 缺少 renderTaskRightPanel adapter"
        )
        self.assertIn(
            "async function flyDrawnCardToDiscard(", app_js, "app.js 缺少 flyDrawnCardToDiscard adapter"
        )

        # === 2. app.entry.js：唯一 owner + getter-only 暴露 =================
        self.assertRegex(
            app_entry_js,
            r"import\s*\{\s*createTaskLifecycleOwner\s*\}\s*from\s*['\"]\./modules/tasks/lifecycle\.js['\"]",
            "app.entry.js 必须静态 import G15 lifecycle owner",
        )
        self.assertIn(
            "Object.defineProperty", app_entry_js, "app.entry.js 必须用 defineProperty 暴露 owner"
        )
        self.assertIn(
            "__taskLifecycleOwner", app_entry_js, "app.entry.js 必须暴露 window.__taskLifecycleOwner"
        )
        for name in FACADE_NAMES:
            self.assertNotRegex(
                app_entry_js,
                r"window\.%s\s*=" % name,
                "app.entry.js 不得覆盖 app.js 的 facade：%s" % name,
            )
        self.assertRegex(
            app_entry_js,
            r"import\s*\{[^}]*\bcreateGachaOwner\b[^}]*\}\s*from\s*['\"]\./modules/gacha/index\.js['\"]",
            "main app.entry.js 必须保留唯一的 G14 Gacha owner import",
        )
        # AR03-P3-F：gacha 升为 **应用级（app-scoped）** 模块，装配根额外
        # 引入幂等的应用级启动钩子（同一个 import 语句）。
        self.assertRegex(
            app_entry_js,
            r"import\s*\{[^}]*\binitAppScoped\b[^}]*\}\s*from\s*['\"]\./modules/gacha/index\.js['\"]",
            "app.entry.js 必须引入抽卡的应用级启动钩子 initAppScoped",
        )
        self.assertEqual(
            1,
            len(re.findall(r"import\s*(?:\{[^}]*\}\s*from\s*)?['\"][^'\"]*gacha[^'\"]*['\"]", app_entry_js)),
            "main app.entry.js 必须只导入一个 Gacha owner",
        )
        self.assertLess(
            app_entry_js.index("gachaOwner.init();"),
            app_entry_js.index("const taskLifecycleOwner = createLifecycleOwnerFromClassic();"),
            "G15 Lifecycle owner 必须在 G14 Gacha facade 初始化后创建",
        )
        self.assertRegex(
            app_entry_js,
            r"import\s*\{[^}]*createTaskEditorOwner[^}]*\}\s*from\s*['\"]\./modules/tasks/editor\.js['\"]",
            "app.entry.js 必须保留 G13 任务编辑器 import",
        )
        for name in ("openTaskEdit", "buildDepList", "addTagChip", "saveTask", "deleteCurrentTask"):
            self.assertRegex(
                app_entry_js,
                r"window\.%s\s*=" % name,
                "app.entry.js 必须保留 G13 全局入口 window.%s" % name,
            )

        # === 3. Node 沙箱：owner 行为契约 =================================
        result = self._run_harness()
        self.assertIsNone(result.get("error"), "Node harness 执行异常：%s" % result.get("error"))
        scenarios = result["scenarios"]

        # 3.1 非法 ID
        invalid = scenarios["invalid_ids"]
        self.assertEqual(invalid["count"], len(invalid["toasts"]), "每个非法 ID 都必须提示一次")
        for t in invalid["toasts"]:
            self.assertEqual(["任务不存在", "err"], t, "非法 ID 必须提示「任务不存在」")
        self.assertEqual([], invalid["startSession"], "非法 ID 不得启动计时")

        # 3.2 查找优先级
        drawn = scenarios["drawn_priority"]
        self.assertEqual(1, len(drawn["startSession"]))
        self.assertEqual("drawn", drawn["startSession"][0]["taskName"], "drawn card 优先级最高")
        multi = scenarios["multi_priority"]
        self.assertEqual("multi", multi["startSession"][0]["taskName"], "其次是 multiDrawResults")
        catalog = scenarios["catalog_priority"]
        self.assertEqual("catalog", catalog["startSession"][0]["taskName"], "最后回落到 allTasks")
        not_found = scenarios["not_found"]
        self.assertEqual([["任务不存在", "err"]], not_found["toasts"])
        self.assertEqual([], not_found["startSession"])

        # 3.3 未解锁
        locked = scenarios["locked"]
        self.assertEqual([["等待前置：X", "err"]], locked["toasts"])
        self.assertNotIn("resetReplaceChain", locked["steps"], "未解锁时不得 resetReplaceChain")
        self.assertEqual([], locked["startSession"])

        # 3.4 自由卡
        free = scenarios["free_card"]
        self.assertEqual([[10]], free["freeCard"], "自由卡必须委派 openFreeCardAcceptForm")
        self.assertEqual([], free["startSession"], "自由卡不得直接启动计时")
        self.assertEqual([], free["rendered"], "自由卡不得写计时面板")
        after = scenarios["free_card_then_other"]
        self.assertEqual(1, len(after["startSession"]), "自由卡分支后 pending lock 必须释放")
        self.assertEqual(11, after["startSession"][0]["taskId"])

        # 3.5 计划分钟
        expected_planned = {45: 45, 0: 30, 481: 30, "30": 30, "abc": 30, None: 30, 30.5: 30, 1: 1, 480: 480}
        seen = {}
        for item in scenarios["planned"]:
            key = item["est"]
            self.assertIn(key, expected_planned, "未预期的 estimated_time 用例：%r" % (key,))
            seen[key] = item["planned"]
        for key, want in expected_planned.items():
            self.assertEqual(want, seen.get(key), "estimated_time=%r 的计划分钟错误" % (key,))

        # 3.6 pending lock
        pending = scenarios["lock_while_pending"]
        self.assertEqual(1, len(pending["startSession"]), "同 ID 并发只能启动一次计时")
        released = scenarios["lock_after_release"]
        self.assertEqual(2, len(released["startSession"]), "finally 之后 pending lock 必须释放")

        # 3.7 renderTaskRightPanel 三态
        card_missing = scenarios["card_missing"]
        self.assertEqual([["请先抽一张卡牌", "err"]], card_missing["toasts"])
        self.assertEqual([], card_missing["startSession"], "CARD_MISSING 时不得启动计时")
        panel_missing = scenarios["panel_missing"]
        self.assertEqual([], panel_missing["toasts"], "PANEL_MISSING 是安全 no-op")
        self.assertEqual([], panel_missing["startSession"], "PANEL_MISSING 时不得启动计时")

        # 3.8 计时启动失败
        failed = scenarios["timer_start_failed"]
        self.assertEqual([["boom", "err"]], failed["toasts"], "计时启动失败只 toast 错误")
        self.assertEqual(2, len(failed["rendered"]), "失败后必须通过 adapter 恢复按钮")
        self.assertIn("startTask(32)", failed["rendered"][1][1], "恢复按钮必须回到「开始任务」")
        self.assertIn("开始任务", failed["rendered"][1][1])
        self.assertNotIn("refreshTimerViews", failed["steps"], "计时启动失败不得刷新计时视图")
        self.assertNotIn("startInlineTimer", failed["steps"], "计时启动失败不得启动内嵌计时")
        owner_failed = scenarios["timer_owner_failed"]
        self.assertEqual([["load fail", "err"]], owner_failed["toasts"])
        self.assertEqual([], owner_failed["startSession"])

        # 3.9 confirmComplete
        confirm_owner_failed = scenarios["confirm_owner_failed"]
        self.assertEqual(
            [["计时模块加载失败，任务未完成", "err"]], confirm_owner_failed["toasts"]
        )
        self.assertEqual([], confirm_owner_failed["api"], "计时 owner 失败时不得完成任务")
        self.assertNotIn("stopInlineTimer", confirm_owner_failed["steps"], "不得停止仍有效的 session")

        confirm_complete_failed = scenarios["confirm_complete_failed"]
        self.assertEqual([["stop failed", "err"]], confirm_complete_failed["toasts"])
        self.assertEqual([], confirm_complete_failed["api"], "计时完成失败不得完成任务")
        self.assertNotIn(
            "stopInlineTimer", confirm_complete_failed["steps"], "计时完成失败不得停止内嵌计时"
        )

        confirm_ok = scenarios["confirm_ok"]
        self.assertEqual(
            1, len(confirm_ok["completeSession"]), "confirmComplete 必须调用 completeSession"
        )
        self.assertEqual(
            {"sessionId": "s2", "actualMinutes": 7, "result": "completed"},
            confirm_ok["completeSession"][0],
            "completeSession 参数不得改变",
        )
        self._index(confirm_ok, "completeSession")
        self.assertLess(
            self._index(confirm_ok, "completeSession"),
            self._index(confirm_ok, "stopInlineTimer"),
            "顺序：completeSession → stopInlineTimer",
        )
        self.assertLess(
            self._index(confirm_ok, "stopInlineTimer"),
            self._index(confirm_ok, "refreshTimerViews"),
            "顺序：stopInlineTimer → refreshTimerViews",
        )
        self.assertLess(
            self._index(confirm_ok, "refreshTimerViews"),
            self._index(confirm_ok, "api"),
            "顺序：refreshTimerViews → completeWithFeedback",
        )

        confirm_no_session = scenarios["confirm_no_session"]
        self.assertEqual([], confirm_no_session["completeSession"], "无活动 session 不得调 completeSession")
        self.assertIn("stopInlineTimer", confirm_no_session["steps"])
        self.assertIn("api", confirm_no_session["steps"])

        # 3.10 completeWithFeedback 成功顺序
        complete_ok = scenarios["complete_ok"]
        self.assertEqual(
            [["/api/tasks/50/complete", {"method": "POST"}],
             ["/api/tasks/50/move-to-discard", {"method": "POST"}]],
            complete_ok["api"],
            "completeWithFeedback 的 endpoint / method / 顺序不得改变",
        )
        expected_order = [
            ("api", 0),
            ("toast", 0),
            ("flyDrawnCardToDiscard", 0),
            ("api", 1),
            ("loadTasks", 0),
            ("refreshGachaStats", 0),
            ("updateDiscardPileVisual", 0),
            ("clear", 0),
            ("refreshTimerViews", 0),
            ("openFeedbackModalForTask", 0),
        ]
        steps = complete_ok["steps"]
        last = -1
        for name, occurrence in expected_order:
            idxs = [i for i, s in enumerate(steps) if s == name]
            self.assertTrue(idxs, "步骤序列缺少 %s：%s" % (name, steps))
            pos = idxs[occurrence]
            self.assertGreater(pos, last, "顺序错误：%s 应在更靠后位置（%s）" % (name, steps))
            last = pos
        self.assertIn(
            ["恭喜解锁了新任务: 51", "suc"],
            complete_ok["toasts"],
            "解锁提示文案必须逐字保留",
        )
        self.assertEqual([[50, "study", False]], complete_ok["feedback"], "反馈 modal 参数不得改变")

        complete_failed = scenarios["complete_failed"]
        self.assertEqual([["complete failed", "err"]], complete_failed["toasts"], "/complete 失败只 toast")
        self.assertEqual(1, len(complete_failed["api"]), "/complete 失败不得再请求 move-to-discard")
        self.assertNotIn("flyDrawnCardToDiscard", complete_failed["steps"])
        self.assertNotIn("loadTasks", complete_failed["steps"])
        self.assertNotIn("refreshGachaStats", complete_failed["steps"])
        self.assertNotIn("updateDiscardPileVisual", complete_failed["steps"])
        self.assertNotIn("clear", complete_failed["steps"])
        self.assertNotIn("openFeedbackModalForTask", complete_failed["steps"])

        finish_early = scenarios["complete_finish_early"]
        self.assertEqual([[53, None, True]], finish_early["feedback"], "opts.finishEarly 必须保留")

        no_timer_owner = scenarios["complete_no_timer_owner"]
        self.assertNotIn("clear", no_timer_owner["steps"], "无当前 Timer owner 时不得 clear")

        # 3.11 Gacha 状态只读
        self.assertTrue(
            scenarios["readonly"]["unchanged"], "owner 不得修改 Gacha 只读 getter 返回值"
        )

        # === 4. 语法体检（app.js classic script / app.entry.js ESM module）===
        syntax = result.get("syntax") or {}
        self.assertTrue(
            syntax.get("app_js"),
            "static/app.js 语法错误：%s" % syntax.get("app_js_error"),
        )
        self.assertNotEqual(
            False,
            syntax.get("app_entry_js"),
            "static/app.entry.js 语法错误：%s" % syntax.get("app_entry_js_error"),
        )

        # === 5. app.js facade：null-safe + 委托 ============================
        facade = result["facade"]
        for name in FACADE_NAMES:
            info = facade.get(name) or {}
            self.assertTrue(info.get("found"), "app.js 缺少 facade：%s" % name)
            self.assertIsNone(
                info.get("missing_threw"),
                "owner 未初始化时 facade %s 不得抛 TypeError：%s" % (name, info.get("missing_threw")),
            )
            self.assertTrue(
                info.get("missing_toasts"),
                "owner 未初始化时 facade %s 必须安全 toast" % name,
            )
            self.assertIsNone(
                info.get("present_threw"),
                "owner 存在时 facade %s 不得抛异常" % name,
            )
            self.assertEqual(
                1, len(info.get("delegated") or []), "facade %s 必须委托给 owner" % name
            )
            self.assertEqual(name, info["delegated"][0][0], "facade %s 委托目标错误" % name)


if __name__ == "__main__":
    unittest.main()
