# -*- coding: utf-8 -*-
"""AR03-G15.3：跳过 / 拒绝 owner（Skip-Refuse Owner）characterization 测试。

覆盖：

1. ``static/modules/tasks/lifecycle.js`` 的**行为契约** —— 把源码复制到
   ``tempfile`` 临时目录的 ``lifecycle.mjs``，用 Node 内建能力动态 import，
   依赖全部是**合成 stub**（不触碰真实 DB / notes / 配置 / 服务）。
2. ``static/app.js`` 四个同名全局 facade 的 **null-safe 委托契约** —— 从
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

FACADE_NAMES = ("handleSkip", "handleRefuse", "taskSkip", "taskRefuse")

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
      rec('api', [{ url: url, method: opts ? opts.method : null }]);
      // 区分「apiError 未提供」与「apiError 已提供但值为空字符串」：
      // 空 message 必须走 fallback 文案分支。
      if (Object.prototype.hasOwnProperty.call(cfg, 'apiError')) {
        return Promise.reject(new Error(cfg.apiError));
      }
      if (cfg.apiHandler) return cfg.apiHandler(url, opts);
      return Promise.resolve(cfg.apiResult || {});
    },
    toast: function (m, t) { rec('toast', [m, t]); },
    resetReplaceChain: function () { rec('resetReplaceChain', []); },
    loadTasks: function () { rec('loadTasks', []); },
    refreshGachaStats: function () { rec('refreshGachaStats', []); }
  };
  if (!cfg.omitPlayCardAnim) {
    deps.playCardAnim = function (id, cls) {
      rec('playCardAnim', [id, cls]);
      return Promise.resolve();
    };
  }
  if (!cfg.omitRenderDrawnCardResult) {
    deps.renderDrawnCardResult = function (kind) { rec('renderDrawnCardResult', [kind]); };
  }
  if (!cfg.omitFeedbackContext) {
    deps.getTaskFeedbackContext = function (id) {
      rec('getTaskFeedbackContext', [id]);
      return {
        taskId: id,
        plannedMinutes: 25,
        actualMinutes: null,
        completionStatus: null
      };
    };
  }
  if (!cfg.omitPromptFeedback) {
    deps.promptTaskFeedback = function (presetKey, ctx) {
      rec('promptTaskFeedback', [presetKey, ctx]);
      if (cfg.promptHandler) return cfg.promptHandler(presetKey, ctx);
      return Promise.resolve({ saved: true });
    };
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
    renderDrawnCardResult: pick(calls, 'renderDrawnCardResult'),
    promptTaskFeedback: pick(calls, 'promptTaskFeedback'),
    getTaskFeedbackContext: pick(calls, 'getTaskFeedbackContext'),
    apiCount: count(calls, 'api'),
    resetCount: count(calls, 'resetReplaceChain'),
    loadCount: count(calls, 'loadTasks'),
    statsCount: count(calls, 'refreshGachaStats'),
    animCount: count(calls, 'playCardAnim'),
    resultCount: count(calls, 'renderDrawnCardResult'),
    promptCount: count(calls, 'promptTaskFeedback')
  };
}

async function tick(n) {
  for (let i = 0; i < (n || 5); i += 1) {
    await Promise.resolve();
  }
}

async function main() {
  // --- 1. 抽卡结果卡：跳过 ---------------------------------------------
  {
    const h = makeOwner({ apiResult: { unlocked_tasks: ['9'] } });
    await h.owner.handleSkip(7);
    out.scenarios.drawn_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiResult: {} });
    await h.owner.handleSkip(8);
    out.scenarios.drawn_skip_no_unlock = summarize(h.calls);
  }

  // --- 2. 抽卡结果卡：拒绝 ---------------------------------------------
  {
    const h = makeOwner({});
    await h.owner.handleRefuse(7);
    out.scenarios.drawn_refuse = summarize(h.calls);
  }

  // --- 3. 任务列表：跳过 ------------------------------------------------
  {
    const h = makeOwner({ apiResult: { unlocked_tasks: ['9'] } });
    await h.owner.taskSkip(21);
    out.scenarios.list_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiResult: {} });
    await h.owner.taskSkip(22);
    out.scenarios.list_skip_no_unlock = summarize(h.calls);
  }

  // --- 4. 任务列表：拒绝 ------------------------------------------------
  {
    const h = makeOwner({});
    await h.owner.taskRefuse(23);
    out.scenarios.list_refuse = summarize(h.calls);
  }

  // --- 5. Promise 顺序：反馈未完成前 API 必须为 0 ----------------------
  {
    const entries = ['handleSkip', 'handleRefuse', 'taskSkip', 'taskRefuse'];
    out.scenarios.pending_order = {};
    for (const entry of entries) {
      let resolveFn = null;
      const h = makeOwner({
        promptHandler: function () {
          return new Promise(function (res) { resolveFn = res; });
        }
      });
      const running = h.owner[entry](31);
      await tick(10);
      const during = {
        apiCount: count(h.calls, 'api'),
        steps: names(h.calls),
        promptCount: count(h.calls, 'promptTaskFeedback')
      };
      resolveFn({ saved: false });
      await running;
      out.scenarios.pending_order[entry] = {
        during: during,
        after: summarize(h.calls)
      };
    }
  }

  // --- 6. 反馈 resolve {saved:false} 时业务仍继续 -----------------------
  {
    const h = makeOwner({
      promptHandler: function () { return Promise.resolve({ saved: false }); }
    });
    await h.owner.handleSkip(41);
    out.scenarios.saved_false_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({
      promptHandler: function () { return Promise.resolve({ saved: false }); }
    });
    await h.owner.taskRefuse(42);
    out.scenarios.saved_false_refuse = summarize(h.calls);
  }

  // --- 7. API 失败 ------------------------------------------------------
  {
    const h = makeOwner({ apiError: 'boom' });
    await h.owner.handleSkip(51);
    out.scenarios.api_failed_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: 'boom' });
    await h.owner.handleRefuse(52);
    out.scenarios.api_failed_refuse = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: 'boom' });
    await h.owner.taskSkip(53);
    out.scenarios.api_failed_list_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: 'boom' });
    await h.owner.taskRefuse(54);
    out.scenarios.api_failed_list_refuse = summarize(h.calls);
  }

  // --- 7b. API 失败且 message 为空：走原有 fallback 文案 -----------------
  {
    const h = makeOwner({ apiError: '' });
    await h.owner.handleSkip(55);
    out.scenarios.api_failed_empty_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: '' });
    await h.owner.handleRefuse(56);
    out.scenarios.api_failed_empty_refuse = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: '' });
    await h.owner.taskSkip(57);
    out.scenarios.api_failed_empty_list_skip = summarize(h.calls);
  }
  {
    const h = makeOwner({ apiError: '' });
    await h.owner.taskRefuse(58);
    out.scenarios.api_failed_empty_list_refuse = summarize(h.calls);
  }

  // --- 8. 反馈适配器缺失：fail closed，绝不擅自 POST --------------------
  {
    const calls = [];
    const owner = createTaskLifecycleOwner({
      api: function (url) { calls.push(['api', url]); return Promise.resolve({}); },
      toast: function (m, t) { calls.push(['toast', m, t]); },
      resetReplaceChain: function () { calls.push(['resetReplaceChain']); }
    });
    await owner.handleSkip(61);
    await owner.handleRefuse(62);
    await owner.taskSkip(63);
    await owner.taskRefuse(64);
    out.scenarios.no_feedback_adapter = {
      calls: calls.map(function (c) { return c.map(safe); }),
      apiCount: calls.filter(function (c) { return c[0] === 'api'; }).length
    };
  }
  {
    const calls = [];
    const owner = createTaskLifecycleOwner({
      api: function (url) { calls.push(['api', url]); return Promise.resolve({}); },
      toast: function (m, t) { calls.push(['toast', m, t]); },
      playCardAnim: function () { return Promise.resolve(); },
      getTaskFeedbackContext: function (id) {
        return { taskId: id, plannedMinutes: 25, actualMinutes: null, completionStatus: null };
      },
      promptTaskFeedback: function () { return undefined; }
    });
    await owner.taskSkip(65);
    out.scenarios.no_promise_adapter = {
      calls: calls.map(function (c) { return c.map(safe); }),
      apiCount: calls.filter(function (c) { return c[0] === 'api'; }).length
    };
  }

  // --- 8b. 必要适配器缺失：fail closed ----------------------------------
  // 8b-1. playCardAnim 缺失：四条入口均不得 POST。
  {
    const entries = ['handleSkip', 'handleRefuse', 'taskSkip', 'taskRefuse'];
    out.scenarios.no_play_card_anim = {};
    for (const entry of entries) {
      const h = makeOwner({ omitPlayCardAnim: true });
      await h.owner[entry](71);
      const s = summarize(h.calls);
      out.scenarios.no_play_card_anim[entry] = s;
    }
  }
  // 8b-2. renderDrawnCardResult 缺失：两条抽卡结果卡入口不得 POST；
  //       两条任务列表入口不涉及结果区，必须照常工作。
  {
    const entries = ['handleSkip', 'handleRefuse', 'taskSkip', 'taskRefuse'];
    out.scenarios.no_render_result = {};
    for (const entry of entries) {
      const h = makeOwner({ omitRenderDrawnCardResult: true });
      await h.owner[entry](72);
      out.scenarios.no_render_result[entry] = summarize(h.calls);
    }
  }
  // 8b-3. 反馈上下文 / 反馈提示分别缺失：四条入口均不得 POST。
  {
    const entries = ['handleSkip', 'handleRefuse', 'taskSkip', 'taskRefuse'];
    out.scenarios.no_feedback_context = {};
    out.scenarios.no_prompt_feedback = {};
    for (const entry of entries) {
      const h1 = makeOwner({ omitFeedbackContext: true });
      await h1.owner[entry](73);
      out.scenarios.no_feedback_context[entry] = summarize(h1.calls);
      const h2 = makeOwner({ omitPromptFeedback: true });
      await h2.owner[entry](74);
      out.scenarios.no_prompt_feedback[entry] = summarize(h2.calls);
    }
  }

  // --- 9. app.js facade：null-safe + 委托 ------------------------------
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

  for (const name of ['handleSkip', 'handleRefuse', 'taskSkip', 'taskRefuse']) {
    const code = extractFunction(appSrc, name);
    if (code === null) {
      out.facade[name] = { found: false };
      continue;
    }
    const missing = runFacade(code, {});
    let missingThrew = null;
    try { await missing.ctx[name](123); } catch (e) { missingThrew = String(e && e.message); }

    const delegated = [];
    const ownerObj = {};
    ownerObj[name] = function (id) {
      delegated.push([name, id]);
      return 'delegated-' + name;
    };
    const present = runFacade(code, { __taskLifecycleOwner: ownerObj });
    let presentThrew = null;
    let presentRet = null;
    try { presentRet = await present.ctx[name](123); }
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


class SkipRefuseOwnerTest(unittest.TestCase):
    """G15.3 跳过 / 拒绝 owner 的行为与边界契约。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="lt_g15_3_skiprefuse_")
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

    def test_harness_ran(self):
        """harness 必须真实执行（node 可用、无运行时错误）。"""
        self.assertEqual(0, self.node_returncode,
                         "Node harness 返回码非 0：%s" % self.node_stderr[:2000])
        self.assertIsNone(self.result.get("error"))

    # -- 1. 抽卡结果卡：跳过 ---------------------------------------------
    def test_drawn_skip_full_order(self):
        s = self.scenarios()["drawn_skip"]
        steps = s["steps"]
        self.assertEqual(1, s["resetCount"], "抽卡跳过必须结束换卡链")
        self.assertEqual(1, s["promptCount"], "抽卡跳过必须提示反馈")
        self.assertEqual(1, s["apiCount"], "抽卡跳过必须只发一个业务 API")
        self.assertEqual(1, s["animCount"], "抽卡跳过必须执行卡片动画")
        self.assertEqual(1, s["resultCount"], "抽卡跳过必须写入结果区")
        self.assertEqual(1, s["statsCount"], "抽卡跳过必须刷新抽卡统计")
        self.assertEqual(1, s["loadCount"], "抽卡跳过必须刷新任务列表")
        # 顺序：reset → 反馈 → API → 动画 → 结果区 → 统计 → 列表
        self.assertLess(steps.index("resetReplaceChain"), steps.index("promptTaskFeedback"))
        self.assertLess(steps.index("promptTaskFeedback"), steps.index("api"))
        self.assertLess(steps.index("api"), steps.index("playCardAnim"))
        self.assertLess(steps.index("playCardAnim"), steps.index("renderDrawnCardResult"))
        self.assertLess(steps.index("renderDrawnCardResult"), steps.index("refreshGachaStats"))
        self.assertLess(steps.index("refreshGachaStats"), steps.index("loadTasks"))

    def test_drawn_skip_endpoint_preset_status_and_anim(self):
        s = self.scenarios()["drawn_skip"]
        call = s["api"][0][0]
        self.assertEqual("/api/tasks/7/skip", call["url"], "跳过端点必须保持不变")
        self.assertEqual("POST", call["method"], "跳过必须保持 POST")
        prompt = s["promptTaskFeedback"][0]
        self.assertEqual("skip", prompt[0], "反馈 preset 必须保持 skip")
        self.assertEqual("skipped", prompt[1]["completionStatus"],
                         "抽卡跳过的 completionStatus 必须是 skipped")
        self.assertEqual([[7, "is-skipping"]], s["playCardAnim"], "动画类必须保持不变")
        self.assertEqual([["skipped"]], s["renderDrawnCardResult"],
                         "结果区必须使用 skipped 文案")
        self.assertEqual([[7]], s["getTaskFeedbackContext"],
                         "反馈上下文必须用既有实现按任务 id 构造")

    def test_drawn_skip_unlock_toast(self):
        s = self.scenarios()["drawn_skip"]
        self.assertEqual(
            [["恭喜解锁了新任务: 9", "suc"]],
            s["toasts"],
            "解锁提示文案与类型必须保持不变",
        )
        n = self.scenarios()["drawn_skip_no_unlock"]
        self.assertEqual([], n["toasts"], "没有解锁任务时不得提示解锁")

    # -- 2. 抽卡结果卡：拒绝 ---------------------------------------------
    def test_drawn_refuse_full_order(self):
        s = self.scenarios()["drawn_refuse"]
        steps = s["steps"]
        self.assertEqual(1, s["resetCount"], "抽卡拒绝必须结束换卡链")
        self.assertEqual(1, s["promptCount"], "抽卡拒绝必须提示反馈")
        self.assertEqual(1, s["apiCount"])
        self.assertEqual(1, s["animCount"])
        self.assertEqual(1, s["resultCount"])
        self.assertEqual(1, s["statsCount"], "抽卡拒绝必须刷新抽卡统计")
        self.assertEqual(0, s["loadCount"],
                         "抽卡拒绝的历史行为**不**刷新任务列表，不得擅自增加")
        self.assertLess(steps.index("resetReplaceChain"), steps.index("promptTaskFeedback"))
        self.assertLess(steps.index("promptTaskFeedback"), steps.index("api"))
        self.assertLess(steps.index("api"), steps.index("playCardAnim"))
        self.assertLess(steps.index("playCardAnim"), steps.index("renderDrawnCardResult"))
        self.assertLess(steps.index("renderDrawnCardResult"), steps.index("refreshGachaStats"))

    def test_drawn_refuse_endpoint_preset_status_and_anim(self):
        s = self.scenarios()["drawn_refuse"]
        call = s["api"][0][0]
        self.assertEqual("/api/tasks/7/refuse", call["url"], "拒绝端点必须保持不变")
        self.assertEqual("POST", call["method"])
        prompt = s["promptTaskFeedback"][0]
        self.assertEqual("skip", prompt[0], "拒绝的反馈 preset 历史上也是 skip，不得更改")
        self.assertEqual("refused", prompt[1]["completionStatus"])
        self.assertEqual([[7, "is-refusing"]], s["playCardAnim"])
        self.assertEqual([["refused"]], s["renderDrawnCardResult"])
        self.assertEqual([], s["toasts"], "抽卡拒绝不弹提示（历史行为）")

    # -- 3. 任务列表：跳过 ------------------------------------------------
    def test_list_skip_full_order(self):
        s = self.scenarios()["list_skip"]
        steps = s["steps"]
        self.assertEqual(0, s["resetCount"],
                         "任务列表跳过不结束换卡链，不得擅自增加")
        self.assertEqual(0, s["statsCount"],
                         "任务列表跳过不刷新抽卡统计，不得擅自增加")
        self.assertEqual(1, s["promptCount"])
        self.assertEqual(1, s["apiCount"])
        self.assertEqual(1, s["animCount"])
        self.assertEqual(0, s["resultCount"],
                         "任务列表跳过不写抽卡结果区（UI 差异必须保留）")
        self.assertEqual(1, s["loadCount"], "任务列表跳过必须刷新任务列表")
        self.assertLess(steps.index("promptTaskFeedback"), steps.index("api"))
        self.assertLess(steps.index("api"), steps.index("playCardAnim"))
        self.assertLess(steps.index("playCardAnim"), steps.index("loadTasks"))

    def test_list_skip_endpoint_toasts_and_anim(self):
        s = self.scenarios()["list_skip"]
        call = s["api"][0][0]
        self.assertEqual("/api/tasks/21/skip", call["url"])
        self.assertEqual("POST", call["method"])
        self.assertEqual([[21, "is-skipping"]], s["playCardAnim"])
        self.assertEqual(
            [["已跳过", "suc"], ["恭喜解锁了新任务: 9", "suc"]],
            s["toasts"],
            "任务列表跳过的 toast 文案与顺序必须保持不变",
        )
        n = self.scenarios()["list_skip_no_unlock"]
        self.assertEqual([["已跳过", "suc"]], n["toasts"],
                         "没有解锁任务时只提示「已跳过」")

    # -- 4. 任务列表：拒绝 ------------------------------------------------
    def test_list_refuse_full_order(self):
        s = self.scenarios()["list_refuse"]
        steps = s["steps"]
        self.assertEqual(0, s["resetCount"], "任务列表拒绝不结束换卡链")
        self.assertEqual(0, s["statsCount"], "任务列表拒绝不刷新抽卡统计")
        self.assertEqual(1, s["promptCount"])
        self.assertEqual(1, s["apiCount"])
        self.assertEqual(1, s["animCount"])
        self.assertEqual(0, s["resultCount"], "任务列表拒绝不写抽卡结果区")
        self.assertEqual(1, s["loadCount"], "任务列表拒绝必须刷新任务列表")
        self.assertLess(steps.index("promptTaskFeedback"), steps.index("api"))
        self.assertLess(steps.index("api"), steps.index("playCardAnim"))
        self.assertLess(steps.index("playCardAnim"), steps.index("loadTasks"))

    def test_list_refuse_endpoint_toast_and_anim(self):
        s = self.scenarios()["list_refuse"]
        call = s["api"][0][0]
        self.assertEqual("/api/tasks/23/refuse", call["url"])
        self.assertEqual("POST", call["method"])
        self.assertEqual([[23, "is-refusing"]], s["playCardAnim"])
        self.assertEqual([["已记录", "inf"]], s["toasts"],
                         "任务列表拒绝的 toast 文案与类型必须保持不变")
        prompt = s["promptTaskFeedback"][0]
        self.assertEqual("skip", prompt[0])
        self.assertEqual("refused", prompt[1]["completionStatus"])

    # -- 5. Promise 顺序 --------------------------------------------------
    def test_api_never_fires_before_feedback_promise_resolves(self):
        p = self.scenarios()["pending_order"]
        for entry in FACADE_NAMES:
            self.assertIn(entry, p, "必须验证 %s 的 await 顺序" % entry)
            during = p[entry]["during"]
            self.assertEqual(1, during["promptCount"],
                             "%s 必须先提示反馈" % entry)
            self.assertEqual(0, during["apiCount"],
                             "%s 在反馈 Promise 未完成时绝不能发业务 API" % entry)
            after = p[entry]["after"]
            self.assertEqual(1, after["apiCount"],
                             "%s 在反馈 resolve 之后必须发出业务 API" % entry)
            self.assertLess(after["steps"].index("promptTaskFeedback"),
                            after["steps"].index("api"),
                            "%s 的 API 必须排在反馈之后" % entry)

    def test_feedback_saved_false_still_continues_business(self):
        s = self.scenarios()["saved_false_skip"]
        self.assertEqual(1, s["apiCount"],
                         "反馈 resolve {saved:false} 时跳过业务仍必须继续")
        self.assertEqual(1, s["animCount"])
        self.assertEqual(1, s["loadCount"])
        r = self.scenarios()["saved_false_refuse"]
        self.assertEqual(1, r["apiCount"],
                         "反馈 resolve {saved:false} 时拒绝业务仍必须继续")
        self.assertEqual(1, r["animCount"])
        self.assertEqual(1, r["loadCount"])

    # -- 6. API 失败 ------------------------------------------------------
    def test_api_failure_shows_error_and_stops_success_steps(self):
        # 非空 message：显示实际错误 message（classic 与 owner 一致：
        # toast(e.message || fallback, 'err')）。
        cases = [
            ("api_failed_skip", "boom"),
            ("api_failed_refuse", "boom"),
            ("api_failed_list_skip", "boom"),
            ("api_failed_list_refuse", "boom"),
        ]
        for key, msg in cases:
            with self.subTest(scenario=key):
                s = self.scenarios()[key]
                self.assertEqual(1, s["apiCount"], "%s 必须只发一个 API" % key)
                self.assertEqual([[msg, "err"]], s["toasts"],
                                 "%s 必须显示实际错误 message" % key)
                self.assertEqual(0, s["animCount"],
                                 "%s 失败后不得执行动画" % key)
                self.assertEqual(0, s["resultCount"],
                                 "%s 失败后不得写结果区" % key)
                self.assertEqual(0, s["loadCount"],
                                 "%s 失败后不得刷新任务列表" % key)
                self.assertEqual(0, s["statsCount"],
                                 "%s 失败后不得刷新抽卡统计" % key)

    def test_api_failure_empty_message_uses_fallback_text(self):
        # 空 message：走原有 fallback 文案（跳过失败 / 拒绝失败）。
        cases = [
            ("api_failed_empty_skip", "跳过失败"),
            ("api_failed_empty_refuse", "拒绝失败"),
            ("api_failed_empty_list_skip", "跳过失败"),
            ("api_failed_empty_list_refuse", "拒绝失败"),
        ]
        for key, msg in cases:
            with self.subTest(scenario=key):
                s = self.scenarios()[key]
                self.assertEqual(1, s["apiCount"], "%s 必须只发一个 API" % key)
                self.assertEqual([[msg, "err"]], s["toasts"],
                                 "%s 空 message 必须显示原有 fallback 文案" % key)
                self.assertEqual(0, s["animCount"],
                                 "%s 失败后不得执行动画" % key)
                self.assertEqual(0, s["resultCount"],
                                 "%s 失败后不得写结果区" % key)

    # -- 7. 反馈适配器缺失：fail closed ------------------------------------
    def test_missing_feedback_adapter_never_posts(self):
        s = self.scenarios()["no_feedback_adapter"]
        self.assertEqual(0, s["apiCount"],
                         "反馈适配器缺失时绝不能擅自 POST")
        toasts = [c for c in s["calls"] if c[0] == 'toast']
        self.assertEqual(4, len(toasts), "四条入口都必须给出未就绪提示")
        for t in toasts:
            self.assertEqual("err", t[2], "未就绪提示必须是错误类型")
        p = self.scenarios()["no_promise_adapter"]
        self.assertEqual(0, p["apiCount"],
                         "反馈适配器不返回 Promise 时绝不能擅自 POST")

    # -- 7b. 必要适配器缺失：fail closed（不 POST）------------------------
    def test_missing_play_card_anim_never_posts_on_any_entry(self):
        s = self.scenarios()["no_play_card_anim"]
        for entry in FACADE_NAMES:
            with self.subTest(entry=entry):
                case = s[entry]
                self.assertEqual(0, case["apiCount"],
                                 "playCardAnim 缺失时 %s 绝不能 POST" % entry)
                self.assertEqual(0, case["animCount"],
                                 "playCardAnim 缺失时 %s 不得调用动画" % entry)
                self.assertEqual(0, case["resultCount"],
                                 "playCardAnim 缺失时 %s 不得写结果区" % entry)
                self.assertEqual(1, len(case["toasts"]),
                                 "playCardAnim 缺失时 %s 必须给出错误提示" % entry)
                self.assertEqual("err", case["toasts"][0][1],
                                 "playCardAnim 缺失提示必须是错误类型")

    def test_missing_render_result_blocks_drawn_card_entries_only(self):
        s = self.scenarios()["no_render_result"]
        for entry in ("handleSkip", "handleRefuse"):
            with self.subTest(entry=entry):
                case = s[entry]
                self.assertEqual(0, case["apiCount"],
                                 "renderDrawnCardResult 缺失时 %s 绝不能 POST" % entry)
                self.assertEqual(0, case["resultCount"],
                                 "renderDrawnCardResult 缺失时 %s 不得写结果区" % entry)
                self.assertEqual(1, len(case["toasts"]),
                                 "renderDrawnCardResult 缺失时 %s 必须给出错误提示" % entry)
                self.assertEqual("err", case["toasts"][0][1],
                                 "renderDrawnCardResult 缺失提示必须是错误类型")
        # 任务列表路径不涉及结果区，必须照常工作。
        for entry in ("taskSkip", "taskRefuse"):
            with self.subTest(entry=entry):
                case = s[entry]
                self.assertEqual(1, case["apiCount"],
                                 "renderDrawnCardResult 缺失时 %s 仍必须 POST" % entry)
                self.assertEqual(1, case["animCount"],
                                 "renderDrawnCardResult 缺失时 %s 仍必须执行动画" % entry)
                self.assertEqual(0, case["resultCount"],
                                 "任务列表路径本就不写结果区")
                self.assertEqual(1, case["loadCount"],
                                 "renderDrawnCardResult 缺失时 %s 仍必须刷新任务列表" % entry)

    def test_missing_feedback_adapters_never_posts_on_any_entry(self):
        for key, label in (("no_feedback_context", "getTaskFeedbackContext"),
                           ("no_prompt_feedback", "promptTaskFeedback")):
            s = self.scenarios()[key]
            for entry in FACADE_NAMES:
                with self.subTest(adapter=label, entry=entry):
                    case = s[entry]
                    self.assertEqual(0, case["apiCount"],
                                     "%s 缺失时 %s 绝不能 POST" % (label, entry))
                    self.assertEqual(1, len(case["toasts"]),
                                     "%s 缺失时 %s 必须给出错误提示" % (label, entry))
                    self.assertEqual("err", case["toasts"][0][1],
                                     "%s 缺失提示必须是错误类型" % label)

    # -- 8. app.js facade -------------------------------------------------
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
            self.assertEqual([[name, 123]], f["delegated"],
                             "owner 存在时 %s 必须委托给 owner" % name)

    # -- 9. 架构边界 -------------------------------------------------------
    def test_lifecycle_js_has_no_dom_or_global_access(self):
        src = LIFECYCLE_JS.read_text(encoding="utf-8")
        for token in ("window", "document", "globalThis"):
            self.assertNotIn(
                token, src,
                "lifecycle.js 不得出现 %s（DOM / 全局访问必须经注入适配器）" % token,
            )

    def test_app_entry_injects_skip_refuse_dependencies(self):
        src = APP_ENTRY_JS.read_text(encoding="utf-8")
        for token in (
            "getTaskFeedbackContext",
            "promptTaskFeedback",
            "playCardAnim",
            "renderDrawnCardResult",
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

    def test_presentation_inline_handlers_unchanged(self):
        src = PRESENTATION_JS.read_text(encoding="utf-8")
        self.assertIn('onclick="taskSkip(\'', src,
                      "任务列表跳过按钮的 inline handler 名必须保持")
        self.assertIn('onclick="taskRefuse(\'', src,
                      "任务列表拒绝按钮的 inline handler 名必须保持")

    def test_app_js_no_longer_holds_skip_refuse_business_orchestration(self):
        src = APP_JS.read_text(encoding="utf-8")
        for token in (
            "/skip",
            "/refuse",
            "is-skipping",
            "is-refusing",
            "已跳过",
            "跳过失败",
            "拒绝失败",
        ):
            self.assertNotIn(
                token, src,
                "app.js 不得再持有跳过 / 拒绝业务编排（含 %s）" % token,
            )
        for name in ("getTaskFeedbackContext", "promptTaskFeedback", "playCardAnim",
                     "renderDrawnCardResult"):
            self.assertRegex(
                src,
                r"function\s+" + re.escape(name) + r"\s*\(",
                "app.js 必须保留适配器 %s（DOM / Promise 职责仍在 classic 层）" % name,
            )

    def test_app_js_syntax_is_valid(self):
        self.assertTrue(self.result["syntax"].get("app_js"),
                        "app.js 语法必须有效：%s"
                        % self.result["syntax"].get("app_js_error"))


if __name__ == "__main__":
    unittest.main()
