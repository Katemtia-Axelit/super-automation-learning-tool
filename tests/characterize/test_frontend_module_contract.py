"""AR03-P3 — 前端模块化迁移的 **机械契约** 测试。

背景
----
P3 把前端业务逻辑从 classic 单体 ``static/app.js``（2857 行）迁到
``static/modules/*`` 的 ESM owner。本文件机械校验迁移后的结构不变量，
并断言 **行为不回归**（用 Node 在 **合成 DOM** 上跑真实 owner）。

覆盖的迁移批次
--------------
* **P3-A** 自由卡（``static/modules/free-card/``）—— 接受 / 结束全流程；
* **P3-B** 任务域（``static/modules/tasks/``）—— 列表 / 标签 / 筛选；
* **P3-C** 计时器（``static/modules/timer/``）—— 单一 session / tick；
* **P3-D** 内核（``static/core/state.js`` / ``static/shared/*``）；
* **P3-E** 边界检查脚本；
* **P3-F** 装配根（``static/app.entry.js``）。

全程 **不** 触碰生产数据库、不启动浏览器、不访问生产 notes / config。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC = PROJECT_ROOT / "static"
MODULES = STATIC / "modules"
APP_JS = STATIC / "app.js"
APP_ENTRY = STATIC / "app.entry.js"
SCRIPTS = PROJECT_ROOT / "scripts"

#: 必须是 **owner 工厂** 的模块（导出 ``createXxxOwner(deps)``）。
OWNER_MODULES = (
    "free-card",
    "gacha",
    "timer",
)

#: 必须满足 registry 契约（``meta`` / ``mount`` / ``unmount``）的模块。
REGISTRY_MODULES = (
    "gacha",
    "tasks",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_node(script: str, timeout: int = 60) -> dict:
    """在 **合成** 环境里跑一段 Node 脚本，返回其 JSON 输出。

    绝不触碰生产数据库 / notes / config：脚本只 import ``static/`` 下的
    ESM 模块，并在内存里构造 DOM。
    """
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
    env["NODE_OPTIONS"] = ""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        timeout=timeout,
    )
    stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
    stderr = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
    if proc.returncode != 0:
        raise AssertionError(
            f"node 退出码 {proc.returncode}\nSTDOUT:\n{stdout[-4000:]}\n"
            f"STDERR:\n{stderr[-4000:]}"
        )
    lines = [ln for ln in stdout.splitlines() if ln.startswith("PROBE_JSON=")]
    if len(lines) != 1:
        raise AssertionError(f"未捕获 PROBE_JSON:\n{stdout[-4000:]}\n{stderr[-2000:]}")
    return json.loads(lines[0][len("PROBE_JSON=") :])


# ---------------------------------------------------------------------------
# P3-A：自由卡 owner 存在且是唯一实现
# ---------------------------------------------------------------------------


class FreeCardModuleContractTests(unittest.TestCase):
    """P3-A：自由卡已是 **真 owner**（classic 层只剩 facade）。"""

    def test_free_card_module_exists(self):
        index = MODULES / "free-card" / "index.js"
        self.assertTrue(index.is_file(), "static/modules/free-card/index.js 缺失")

    def test_free_card_exports_owner_factory(self):
        text = _read(MODULES / "free-card" / "index.js")
        self.assertIn("export function createFreeCardOwner(", text)
        self.assertIn("export function resolveFreeCardMinutes(", text)
        self.assertIn("export function normalizeFreeCardInputs(", text)

    def test_classic_layer_no_longer_owns_free_card_business_logic(self):
        """classic app.js **不再** 保留自由卡业务实现。

        迁移前 app.js 里有 828 行自由卡逻辑（含第二份时长解析、第二份
        输入规范化、第二份表单构建、第二份提交与补偿）。这些 **必须** 全部
        消失，否则就出现了"两套实现"——正是 P3 要消灭的东西。
        """
        code = _read(APP_JS)
        # 第二份状态容器（防重入标记 / 结束表单状态 / 接受活动缓存）
        for gone in (
            "_pendingFreeCardAcceptId",
            "_pendingFreeCardEndId",
            "_freeCardAcceptedActivities",
            "_freeCardEndState",
        ):
            self.assertNotIn(
                gone, code, "app.js 仍保留自由卡状态容器：" + gone
            )
        # 第二份常量定义
        self.assertNotIn("var FREE_CARD_MINUTES_OPTIONS", code)
        self.assertNotIn("var FREE_CARD_DEFAULT_REASON", code)
        self.assertNotIn("var FREE_CARD_MAX_ACTIVITY_LENGTH", code)
        self.assertNotIn("var FREE_CARD_FORM_ID_PREFIX", code)
        self.assertNotIn("var FREE_CARD_END_FORM_ID_PREFIX", code)
        # 第二份 API 调用点
        self.assertNotIn(
            "/api/gacha/free-card/suggestion",
            code,
            "app.js 仍直接调用建议接口（应只在 owner 内）",
        )

    def test_classic_layer_keeps_thin_facades(self):
        """classic 层保留 **同名** facade（inline handler 依赖这些名字）。"""
        code = _read(APP_JS)
        for name in (
            "openFreeCardAcceptForm",
            "cancelFreeCardAcceptForm",
            "submitFreeCardAccept",
            "suggestFreeCardActivity",
            "openFreeCardEndForm",
            "cancelFreeCardEndForm",
            "submitFreeCardEnd",
            "isFreeCardTask",
            "resolveFreeCardMinutes",
            "normalizeFreeCardInputs",
        ):
            self.assertIn(
                "function " + name + "(",
                code,
                "app.js 丢失 facade：" + name,
            )

    def test_facades_delegate_to_owner(self):
        """facade 必须 **转发** 到 owner，不得各自实现业务。"""
        code = _read(APP_JS)
        # owner 的加载入口必须存在。
        self.assertIn("_getFreeCardOwner", code)
        self.assertIn("import('/static/modules/free-card/index.js')", code)
        # 每个 facade 的函数体里必须出现 owner 调用。
        for name in (
            "openFreeCardAcceptForm",
            "submitFreeCardAccept",
            "openFreeCardEndForm",
            "submitFreeCardEnd",
        ):
            idx = code.index("function " + name + "(")
            body = code[idx : idx + 1200]
            self.assertIn(
                "owner.",
                body,
                name + " 的 facade 未转发到 owner",
            )

    def test_free_card_owner_never_creates_second_timer(self):
        """自由卡 owner **绝不** 自建计时器 —— 一切经 timer owner。"""
        text = _read(MODULES / "free-card" / "index.js")
        self.assertNotIn("setInterval(", text, "owner 自建了计时器")
        self.assertNotIn("/api/timer/", text, "owner 直接调用了计时接口")
        self.assertIn("getTimerOwner", text)
        self.assertIn("startSession", text)
        self.assertIn("completeSession", text)

    def test_free_card_owner_uses_dom_api_not_html_concat_for_inputs(self):
        """活动 / 理由输入框必须用 DOM API 创建（不拼 innerHTML）。"""
        text = _read(MODULES / "free-card" / "index.js")
        self.assertIn("createElement('input')", text)
        # 活动文本进入 DOM 时必须转义。
        self.assertIn("escapeHtml(normalized.activity)", text)


class FreeCardBehaviorTests(unittest.TestCase):
    """P3-A：自由卡 owner 的 **行为** 不回归（合成 DOM 实跑）。"""

    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_node(_FREECARD_PROBE)

    def test_resolve_minutes_fail_closed(self):
        """时长解析 fail closed（非法一律 null）。"""
        p = self.PROBE
        self.assertEqual(p["minutes_ok"], 25, p)
        self.assertEqual(p["minutes_ok_55"], 55, p)
        self.assertIsNone(p["minutes_not_dispatchable"], p)
        self.assertIsNone(p["minutes_bad_value"], p)
        self.assertIsNone(p["minutes_decimal"], p)
        self.assertIsNone(p["minutes_not_number"], p)
        self.assertIsNone(p["minutes_missing"], p)
        self.assertIsNone(p["minutes_null"], p)

    def test_normalize_inputs_semantics(self):
        """输入规范化：trim / 上限 200 / 控制字符 / 缺省理由。"""
        p = self.PROBE
        self.assertTrue(p["norm_ok"], p)
        self.assertEqual(p["norm_activity"], "看纪录片", p)
        self.assertEqual(p["norm_default_reason"], "没有什么理由，我就是想。", p)
        self.assertEqual(p["norm_trimmed_reason"], "想休息", p)
        self.assertFalse(p["norm_empty_ok"], p)
        self.assertEqual(p["norm_empty_error"], "请先填写接下来要做什么", p)
        self.assertFalse(p["norm_too_long_ok"], p)
        self.assertEqual(p["norm_too_long_error"], "活动内容最多 200 字", p)
        self.assertFalse(p["norm_control_char_ok"], p)
        self.assertEqual(p["norm_control_char_error"], "活动内容包含非法字符", p)
        self.assertFalse(p["norm_reason_too_long_ok"], p)
        self.assertEqual(p["norm_reason_too_long_error"], "理由最多 200 字", p)

    def test_is_free_card_task(self):
        """卡型判定沿用既有词表（只有 free 命中）。"""
        p = self.PROBE
        self.assertTrue(p["is_free"], p)
        self.assertFalse(p["is_standard"], p)
        self.assertFalse(p["is_micro"], p)
        self.assertFalse(p["is_goal"], p)
        self.assertFalse(p["is_null"], p)
        self.assertFalse(p["is_unknown"], p)

    def test_accept_form_built_with_dom_api(self):
        """接受表单：DOM API 构建 + 缺省理由 + 无批准时长时 fail closed。"""
        p = self.PROBE
        self.assertTrue(p["accept_form_created"], p)
        self.assertEqual(p["accept_form_default_reason"], "没有什么理由，我就是想。", p)
        self.assertTrue(p["accept_has_activity_input"], p)
        self.assertTrue(p["accept_has_reason_input"], p)
        self.assertTrue(p["accept_has_suggest_button"], p)
        # 无批准时长 → **不** 显示开始路径（fail closed）。
        self.assertTrue(p["accept_fail_closed_no_minutes"], p)
        self.assertFalse(p["accept_fail_closed_has_start"], p)

    def test_end_form_preselects_nothing(self):
        """结束表单：**不** 预选"顺利"（绝不替用户选择）。"""
        p = self.PROBE
        self.assertTrue(p["end_form_created"], p)
        self.assertFalse(p["end_smooth_preselected"], p)
        self.assertFalse(p["end_interrupted_preselected"], p)
        self.assertTrue(p["end_has_both_radios"], p)
        self.assertTrue(p["end_has_activity_input"], p)
        self.assertTrue(p["end_has_reason_input"], p)

    def test_end_form_prefills_accepted_activity(self):
        """结束表单：预填 **接受时** 填的活动（可编辑）。"""
        p = self.PROBE
        self.assertEqual(p["end_prefilled_activity"], "看 20 分钟纪录片", p)

    def test_submit_accept_writes_event_after_starting_timer(self):
        """提交接受：**先** 启动计时，**再** 写 accept 事件。"""
        p = self.PROBE
        self.assertTrue(p["accept_timer_started"], p)
        self.assertTrue(p["accept_event_written"], p)
        self.assertEqual(
            p["accept_call_order"],
            ["timer.start", "feedback.accept"],
            p,
        )
        self.assertEqual(p["accept_event_type"], "accept_task", p)
        self.assertEqual(p["accept_planned_minutes"], 25, p)

    def test_submit_accept_compensates_on_event_failure(self):
        """accept 事件写失败 → 补偿（结束计时）+ 保留输入。"""
        p = self.PROBE
        self.assertTrue(p["accept_fail_timer_started"], p)
        self.assertTrue(p["accept_fail_compensated"], p)
        self.assertEqual(
            p["accept_fail_compensate_result"], "abandoned", p
        )
        self.assertTrue(p["accept_fail_form_reopened"], p)

    def test_submit_end_stops_timer_then_writes_feedback(self):
        """提交结束：**先** 停止计时，**再** 写反馈事件。"""
        p = self.PROBE
        self.assertTrue(p["end_timer_stopped"], p)
        self.assertTrue(p["end_feedback_written"], p)
        # 关键顺序：停止计时 **必须** 早于写反馈事件。
        order = p["end_call_order"]
        self.assertIn("timer.complete", order, p)
        self.assertIn("feedback.end", order, p)
        self.assertLess(
            order.index("timer.complete"),
            order.index("feedback.end"),
            "停止计时必须早于写反馈：" + str(order),
        )

    def test_interrupted_outcome_is_never_recorded_as_completed(self):
        """中断 **绝不** 记为已完成（不调 complete 端点）。"""
        p = self.PROBE
        self.assertTrue(p["end_interrupted_feedback_written"], p)
        self.assertEqual(p["end_interrupted_event_type"], "abandon_task", p)
        self.assertEqual(
            p["end_interrupted_completion_status"], "abandoned", p
        )
        self.assertEqual(p["end_interrupted_task_complete_calls"], 0, p)
        self.assertEqual(
            p["end_interrupted_stop_result"], "abandoned", p
        )
        self.assertEqual(p["end_interrupted_stop_reason"], "early_finish", p)

    def test_smooth_outcome_completes_task(self):
        """顺利 → 复用既有"任务完成"端点。"""
        p = self.PROBE
        self.assertEqual(p["end_smooth_task_complete_calls"], 2, p)
        self.assertEqual(p["end_smooth_stop_result"], "completed", p)

    def test_end_requires_explicit_outcome_choice(self):
        """未选"顺利 / 中断" → 拒绝提交，绝不自动代选。"""
        p = self.PROBE
        self.assertTrue(p["end_no_outcome_rejected"], p)
        self.assertFalse(p["end_no_outcome_feedback_written"], p)

    def test_suggest_only_fills_activity_input(self):
        """「帮我选」：**只** 填活动输入框，不自动提交、不改理由。

        探针先把理由改成 "我的理由"，验证建议 **没有** 覆盖它。
        """
        p = self.PROBE
        self.assertEqual(p["suggest_filled_activity"], "散步 20 分钟", p)
        self.assertEqual(
            p["suggest_reason_unchanged"], "我的理由", p
        )
        self.assertEqual(p["suggest_feedback_calls"], 0, p)
        self.assertEqual(p["suggest_timer_starts"], 0, p)

    def test_suggest_failure_preserves_user_input(self):
        """建议接口失败 → **保留** 用户当前输入与理由。"""
        p = self.PROBE
        self.assertEqual(
            p["suggest_fail_activity_preserved"], "我自己写的", p
        )
        self.assertEqual(p["suggest_fail_reason_preserved"], "我的理由", p)


# ---------------------------------------------------------------------------
# 合成 DOM + 合成 API 的 Node 探针
# ---------------------------------------------------------------------------

_FREECARD_PROBE = r'''
// 合成 DOM：只需要 owner 实际用到的最小 API 面。
//
// 语义要点：
//   - setAttribute('id', ...) 注册节点 → document.getElementById 能找到
//     （owner 正是靠它读回活动 / 理由输入框的值）；
//   - innerHTML 赋值会 **清空** 子节点列表；
//   - querySelector('.cls') 按 className 深度查找后代。
var byId = {};

function makeEl(tag) {
  var el = {
    tagName: String(tag).toUpperCase(),
    style: {},
    children: [],
    attrs: {},
    value: '',
    checked: false,
    disabled: false,
    textContent: '',
    _innerHTML: '',
    className: '',
    listeners: {},
    setAttribute(k, v) {
      this.attrs[k] = String(v);
      if (k === 'id') byId[String(v)] = this;
    },
    getAttribute(k) {
      return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null;
    },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(ev, fn) {
      (this.listeners[ev] = this.listeners[ev] || []).push(fn);
    },
    click() { (this.listeners.click || []).forEach(function (fn) { fn(); }); },
    focus() {},
    querySelector(sel) {
      var wantClass = null;
      var m = /\.([A-Za-z0-9_-]+)/.exec(sel);
      if (m) wantClass = m[1];
      var stack = this.children.slice();
      while (stack.length) {
        var node = stack.shift();
        if (wantClass && node.className &&
            node.className.split(/\s+/).indexOf(wantClass) >= 0) {
          return node;
        }
        stack = stack.concat(node.children || []);
      }
      return null;
    }
  };
  Object.defineProperty(el, 'innerHTML', {
    get: function () { return this._innerHTML; },
    set: function (v) {
      this._innerHTML = String(v);
      if (v === '') this.children = [];
    }
  });
  return el;
}

// 深度查找（探针自己用）：按 id 找节点。
function findById(root, id) {
  if (!root) return null;
  if (root.attrs && root.attrs.id === id) return root;
  var stack = (root.children || []).slice();
  while (stack.length) {
    var node = stack.shift();
    if (node.attrs && node.attrs.id === id) return node;
    stack = stack.concat(node.children || []);
  }
  return null;
}

var card = null;
var rightPanel = null;

function rebuildCard(taskId) {
  rightPanel = makeEl('div');
  rightPanel.className = 'drawn-card-right-panel';
  card = makeEl('div');
  card.className = 'task-card drawn-card';
  card.setAttribute('data-task-id', String(taskId));
  card.children.push(rightPanel);
  return card;
}

var documentRef = {
  createElement: makeEl,
  getElementById: function (id) {
    return Object.prototype.hasOwnProperty.call(byId, id) ? byId[id] : null;
  },
  querySelector: function (sel) {
    var m = /data-task-id="(\d+)"/.exec(sel);
    if (!m) return null;
    if (card && card.getAttribute('data-task-id') === m[1]) return card;
    return null;
  }
};

var out = {};
var apiCalls = [];
var callOrder = [];

function makeApi(failFeedback) {
  return function (url, opts) {
    var o = opts || {};
    apiCalls.push({ url: url, method: o.method || 'GET', body: o.body || null });
    if (url === '/api/gacha/free-card/suggestion') {
      if (failFeedback) return Promise.reject(new Error('422'));
      return Promise.resolve({ suggestion: { activity: '散步 20 分钟' } });
    }
    if (url === '/api/task-feedback') {
      if (failFeedback) return Promise.reject(new Error('写入失败'));
      callOrder.push('feedback.' + (o.body.indexOf('accept_task') >= 0 ? 'accept' : 'end'));
      return Promise.resolve({ saved: true });
    }
    if (url.indexOf('/api/tasks/') >= 0 && url.indexOf('/complete') >= 0) {
      callOrder.push('task.complete');
      return Promise.resolve({ ok: true });
    }
    if (url.indexOf('/api/tasks/') >= 0 && url.indexOf('/move-to-discard') >= 0) {
      callOrder.push('task.discard');
      return Promise.resolve({ ok: true });
    }
    return Promise.resolve({});
  };
}

var toasts = [];
function toast(msg, kind) { toasts.push({ msg: msg, kind: kind }); }

var timerOps = [];
var timerState = { session: null, paused: false, pausedElapsedMs: 0 };

function makeTimerOwner(opts) {
  var o = opts || {};
  return {
    getSnapshot: function () {
      return {
        session: timerState.session ? Object.assign({}, timerState.session) : null,
        paused: timerState.paused,
        pausedElapsedMs: timerState.pausedElapsedMs
      };
    },
    startSession: function (params) {
      if (o.failStart) return Promise.reject(new Error('启动失败'));
      timerOps.push('start');
      callOrder.push('timer.start');
      var session = {
        id: 12345, task_id: params.taskId,
        started_at: new Date(Date.now() - 60000).toISOString(),
        planned_minutes: params.plannedMinutes,
        task_name: params.taskName
      };
      timerState.session = session;
      timerState.paused = false;
      timerState.pausedElapsedMs = 0;
      return Promise.resolve({ ok: true, sessionId: session.id, session: session });
    },
    completeSession: function (params) {
      timerOps.push({ op: 'complete', result: params.result, reason: params.reason });
      callOrder.push('timer.complete');
      if (o.failComplete) return Promise.reject(new Error('停止计时失败'));
      timerState.session = null;
      return Promise.resolve({ ok: true });
    },
    getActualMinutes: function () { return 1; },
    stopInlineTimer: function () { timerOps.push('stopInline'); },
    updateDock: function () {},
    updatePanel: function () {}
  };
}

var mod = await import('./static/modules/free-card/index.js');

// ---- 纯函数：resolveFreeCardMinutes ------------------------------------
out.minutes_ok = mod.resolveFreeCardMinutes({ free_card_dispatchable: true, effective_minutes: 25 });
out.minutes_ok_55 = mod.resolveFreeCardMinutes({ free_card_dispatchable: true, effective_minutes: 55 });
out.minutes_not_dispatchable = mod.resolveFreeCardMinutes({ free_card_dispatchable: false, effective_minutes: 25 });
out.minutes_bad_value = mod.resolveFreeCardMinutes({ free_card_dispatchable: true, effective_minutes: 30 });
out.minutes_decimal = mod.resolveFreeCardMinutes({ free_card_dispatchable: true, effective_minutes: 25.5 });
out.minutes_not_number = mod.resolveFreeCardMinutes({ free_card_dispatchable: true, effective_minutes: '25' });
out.minutes_missing = mod.resolveFreeCardMinutes({ free_card_dispatchable: true });
out.minutes_null = mod.resolveFreeCardMinutes(null);

// ---- 纯函数：normalizeFreeCardInputs ------------------------------------
var n1 = mod.normalizeFreeCardInputs('  看纪录片  ', '');
out.norm_ok = n1.ok;
out.norm_activity = n1.activity;
out.norm_default_reason = n1.reason;
var n2 = mod.normalizeFreeCardInputs('  看纪录片  ', '  想休息  ');
out.norm_trimmed_reason = n2.reason;
var n3 = mod.normalizeFreeCardInputs('   ', '');
out.norm_empty_ok = n3.ok;
out.norm_empty_error = n3.error;
var n4 = mod.normalizeFreeCardInputs('x'.repeat(201), '');
out.norm_too_long_ok = n4.ok;
out.norm_too_long_error = n4.error;
var n5 = mod.normalizeFreeCardInputs('a' + String.fromCharCode(10) + 'b', '');
out.norm_control_char_ok = n5.ok;
out.norm_control_char_error = n5.error;
var n6 = mod.normalizeFreeCardInputs('ok', 'y'.repeat(201));
out.norm_reason_too_long_ok = n6.ok;
out.norm_reason_too_long_error = n6.error;

// ---- 卡型判定 ------------------------------------------------------------
var normType = function (v) {
  var vals = ['standard', 'free', 'micro', 'goal'];
  if (typeof v !== 'string') return 'standard';
  for (var i = 0; i < vals.length; i++) if (v === vals[i]) return v;
  return 'standard';
};

var drawnTask = { id: 7, task_type: 'free', free_card_dispatchable: true, effective_minutes: 25 };

function makeOwner(opts) {
  var o = opts || {};
  var timerOwner = makeTimerOwner(o);
  return mod.createFreeCardOwner({
    documentRef: documentRef,
    api: makeApi(o.failFeedback),
    toast: toast,
    escapeHtml: function (s) { return String(s == null ? '' : s); },
    normalizeCardType: normType,
    getDrawnTask: function () { return o.task === undefined ? drawnTask : o.task; },
    getTimerOwner: function () { return Promise.resolve(timerOwner); },
    timerSnapshot: function () { return timerOwner.getSnapshot(); },
    refreshTimerViews: function () {},
    startInlineTimer: function () { timerOps.push('inline.start'); },
    getActionsCache: function () { return null; },
    setActionsCache: function () {},
    onReturnToGacha: function () { callOrder.push('return.gacha'); }
  });
}

// ---- isFreeCardTask ------------------------------------------------------
var owner0 = makeOwner({});
out.is_free = owner0.isFreeCardTask({ task_type: 'free' });
out.is_standard = owner0.isFreeCardTask({ task_type: 'standard' });
out.is_micro = owner0.isFreeCardTask({ task_type: 'micro' });
out.is_goal = owner0.isFreeCardTask({ task_type: 'goal' });
out.is_null = owner0.isFreeCardTask(null);
out.is_unknown = owner0.isFreeCardTask({ task_type: 'weird' });

// ---- 接受表单 ------------------------------------------------------------
rebuildCard(7);
var owner1 = makeOwner({});
owner1.openFreeCardAcceptForm(7);
out.accept_form_created = rightPanel.children.length > 0;
var acceptBox = rightPanel.children[0];
out.accept_has_activity_input = !!findById(rightPanel, 'freeCardAcceptForm_7_activity');
out.accept_has_reason_input = !!findById(rightPanel, 'freeCardAcceptForm_7_reason');
out.accept_has_suggest_button = !!findById(rightPanel, 'freeCardAcceptForm_7_suggest');
var reasonInput = findById(rightPanel, 'freeCardAcceptForm_7_reason');
out.accept_form_default_reason = reasonInput ? reasonInput.value : null;

// 无批准时长 → fail closed
rebuildCard(7);
var ownerNoMin = makeOwner({ task: { id: 7, task_type: 'free', free_card_dispatchable: false } });
ownerNoMin.openFreeCardAcceptForm(7);
out.accept_fail_closed_no_minutes = rightPanel.innerHTML.indexOf('没有可用的已批准时长') >= 0;
out.accept_fail_closed_has_start = rightPanel.innerHTML.indexOf('submitFreeCardAccept') >= 0;

// ---- 结束表单（不预选）---------------------------------------------------
rebuildCard(7);
var owner2 = makeOwner({});
owner2.setAcceptedActivity(7, '看 20 分钟纪录片');
owner2.openFreeCardEndForm(7);
out.end_form_created = rightPanel.children.length > 0;
var endBox = rightPanel.children[1];
var smooth = findById(rightPanel, 'freeCardEndForm_7_smooth');
var interrupted = findById(rightPanel, 'freeCardEndForm_7_interrupted');
out.end_smooth_preselected = smooth ? smooth.checked : null;
out.end_interrupted_preselected = interrupted ? interrupted.checked : null;
out.end_has_both_radios = !!smooth && !!interrupted;
var endActivity = findById(rightPanel, 'freeCardEndForm_7_activity');
out.end_has_activity_input = !!endActivity;
out.end_has_reason_input = !!findById(rightPanel, 'freeCardEndForm_7_reason');
out.end_prefilled_activity = endActivity ? endActivity.value : null;

// ---- 提交接受（先计时，后事件）------------------------------------------
rebuildCard(7);
apiCalls = []; callOrder = []; timerOps = [];
var owner3 = makeOwner({});
var acceptOwner = makeOwner({});
// 复用 owner3 的 api（makeApi 闭包共享 apiCalls / callOrder）
var owner3b = mod.createFreeCardOwner({
  documentRef: documentRef,
  api: function (url, opts) {
    var o = opts || {};
    apiCalls.push({ url: url, method: o.method || 'GET', body: o.body || null });
    if (url === '/api/task-feedback') {
      callOrder.push('feedback.' + (String(o.body).indexOf('accept_task') >= 0 ? 'accept' : 'end'));
      return Promise.resolve({ saved: true });
    }
    return Promise.resolve({});
  },
  toast: toast,
  escapeHtml: function (s) { return String(s == null ? '' : s); },
  normalizeCardType: normType,
  getDrawnTask: function () { return drawnTask; },
  getTimerOwner: function () { return Promise.resolve(makeTimerOwner({})); },
  timerSnapshot: function () { return { session: null, paused: false, pausedElapsedMs: 0 }; },
  refreshTimerViews: function () {},
  startInlineTimer: function () {},
  getActionsCache: function () { return null; },
  setActionsCache: function () {},
  onReturnToGacha: function () {}
});
// 填入活动 / 理由
owner3b.openFreeCardAcceptForm(7);
var accBox = rightPanel.children[0];
findById(rightPanel, 'freeCardAcceptForm_7_activity').value = '散步';
await owner3b.submitFreeCardAccept(7);
out.accept_timer_started = callOrder.indexOf('timer.start') >= 0;
out.accept_event_written = callOrder.indexOf('feedback.accept') >= 0;
out.accept_call_order = callOrder.slice();
var acceptBody = apiCalls.find(function (c) { return c.url === '/api/task-feedback'; });
var parsedAccept = acceptBody ? JSON.parse(acceptBody.body) : {};
out.accept_event_type = parsedAccept.event_type;
out.accept_planned_minutes = parsedAccept.planned_minutes;

// ---- 提交接受失败 → 补偿 --------------------------------------------------
rebuildCard(7);
apiCalls = []; callOrder = []; timerOps = [];
var ownerFail = mod.createFreeCardOwner({
  documentRef: documentRef,
  api: function (url, opts) {
    if (url === '/api/task-feedback') return Promise.reject(new Error('写入失败'));
    return Promise.resolve({});
  },
  toast: toast,
  escapeHtml: function (s) { return String(s == null ? '' : s); },
  normalizeCardType: normType,
  getDrawnTask: function () { return drawnTask; },
  getTimerOwner: function () { return Promise.resolve(makeTimerOwner({})); },
  timerSnapshot: function () { return { session: null, paused: false, pausedElapsedMs: 0 }; },
  refreshTimerViews: function () {},
  startInlineTimer: function () {},
  getActionsCache: function () { return null; },
  setActionsCache: function () {},
  onReturnToGacha: function () {}
});
ownerFail.openFreeCardAcceptForm(7);
findById(rightPanel, 'freeCardAcceptForm_7_activity').value = '散步';
await ownerFail.submitFreeCardAccept(7);
out.accept_fail_timer_started = timerOps.indexOf('start') >= 0;
var comp = timerOps.find(function (t) { return t && t.op === 'complete'; });
out.accept_fail_compensated = !!comp;
out.accept_fail_compensate_result = comp ? comp.result : null;
out.accept_fail_form_reopened = rightPanel.children.length > 0;

// ---- 提交结束（顺利）-----------------------------------------------------
rebuildCard(7);
apiCalls = []; callOrder = []; timerOps = [];
timerState = { session: { id: 999, task_id: 7, started_at: new Date().toISOString(), planned_minutes: 25 }, paused: false, pausedElapsedMs: 0 };
var ownerEnd = mod.createFreeCardOwner({
  documentRef: documentRef,
  api: function (url, opts) {
    var o = opts || {};
    apiCalls.push({ url: url, method: o.method || 'GET', body: o.body || null });
    if (url === '/api/task-feedback') {
      callOrder.push('feedback.end');
      return Promise.resolve({ saved: true });
    }
    if (url.indexOf('/complete') >= 0) { callOrder.push('task.complete'); return Promise.resolve({}); }
    if (url.indexOf('/move-to-discard') >= 0) { callOrder.push('task.discard'); return Promise.resolve({}); }
    return Promise.resolve({});
  },
  toast: toast,
  escapeHtml: function (s) { return String(s == null ? '' : s); },
  normalizeCardType: normType,
  getDrawnTask: function () { return drawnTask; },
  getTimerOwner: function () { return Promise.resolve(makeTimerOwner({})); },
  timerSnapshot: function () { return timerOwnerSnap(); },
  refreshTimerViews: function () {},
  startInlineTimer: function () {},
  getActionsCache: function () { return null; },
  setActionsCache: function () {},
  onReturnToGacha: function () { callOrder.push('return.gacha'); }
});
function timerOwnerSnap() {
  return {
    session: timerState.session ? Object.assign({}, timerState.session) : null,
    paused: timerState.paused,
    pausedElapsedMs: timerState.pausedElapsedMs
  };
}
ownerEnd.setAcceptedActivity(7, '看 20 分钟纪录片');
ownerEnd.openFreeCardEndForm(7);
var eBox = rightPanel.children[1];
findById(rightPanel, 'freeCardEndForm_7_smooth').checked = true;
findById(rightPanel, 'freeCardEndForm_7_activity').value = '看了一集纪录片';
await ownerEnd.submitFreeCardEnd(7);
out.end_timer_stopped = timerOps.some(function (t) { return t && t.op === 'complete'; });
out.end_feedback_written = callOrder.indexOf('feedback.end') >= 0;
out.end_call_order = callOrder.slice();
out.end_smooth_task_complete_calls = callOrder.filter(function (c) { return c === 'task.complete' || c === 'task.discard'; }).length;
var stopSmooth = timerOps.find(function (t) { return t && t.op === 'complete'; });
out.end_smooth_stop_result = stopSmooth ? stopSmooth.result : null;

// ---- 提交结束（中断）-----------------------------------------------------
rebuildCard(7);
apiCalls = []; callOrder = []; timerOps = [];
timerState = { session: { id: 999, task_id: 7, started_at: new Date().toISOString(), planned_minutes: 25 }, paused: false, pausedElapsedMs: 0 };
var ownerInt = mod.createFreeCardOwner({
  documentRef: documentRef,
  api: function (url, opts) {
    var o = opts || {};
    apiCalls.push({ url: url, method: o.method || 'GET', body: o.body || null });
    if (url === '/api/task-feedback') { callOrder.push('feedback.end'); return Promise.resolve({ saved: true }); }
    if (url.indexOf('/complete') >= 0) { callOrder.push('task.complete'); return Promise.resolve({}); }
    if (url.indexOf('/move-to-discard') >= 0) { callOrder.push('task.discard'); return Promise.resolve({}); }
    return Promise.resolve({});
  },
  toast: toast,
  escapeHtml: function (s) { return String(s == null ? '' : s); },
  normalizeCardType: normType,
  getDrawnTask: function () { return drawnTask; },
  getTimerOwner: function () { return Promise.resolve(makeTimerOwner({})); },
  timerSnapshot: function () { return timerOwnerSnap(); },
  refreshTimerViews: function () {},
  startInlineTimer: function () {},
  getActionsCache: function () { return null; },
  setActionsCache: function () {},
  onReturnToGacha: function () { callOrder.push('return.gacha'); }
});
ownerInt.openFreeCardEndForm(7);
var iBox = rightPanel.children[1];
findById(rightPanel, 'freeCardEndForm_7_interrupted').checked = true;
findById(rightPanel, 'freeCardEndForm_7_activity').value = '被手机打断了';
await ownerInt.submitFreeCardEnd(7);
var intBody = apiCalls.find(function (c) { return c.url === '/api/task-feedback'; });
var parsedInt = intBody ? JSON.parse(intBody.body) : {};
out.end_interrupted_feedback_written = callOrder.indexOf('feedback.end') >= 0;
out.end_interrupted_event_type = parsedInt.event_type;
out.end_interrupted_completion_status = parsedInt.completion_status;
out.end_interrupted_task_complete_calls = callOrder.filter(function (c) { return c === 'task.complete' || c === 'task.discard'; }).length;
var stopInt = timerOps.find(function (t) { return t && t.op === 'complete'; });
out.end_interrupted_stop_result = stopInt ? stopInt.result : null;
out.end_interrupted_stop_reason = stopInt ? stopInt.reason : null;

// ---- 未选结论 → 拒绝 -----------------------------------------------------
rebuildCard(7);
apiCalls = []; callOrder = []; timerOps = [];
timerState = { session: { id: 999, task_id: 7, started_at: new Date().toISOString(), planned_minutes: 25 }, paused: false, pausedElapsedMs: 0 };
var ownerNone = mod.createFreeCardOwner({
  documentRef: documentRef,
  api: function (url, opts) {
    var o = opts || {};
    apiCalls.push({ url: url, method: o.method || 'GET', body: o.body || null });
    if (url === '/api/task-feedback') { callOrder.push('feedback.end'); return Promise.resolve({ saved: true }); }
    return Promise.resolve({});
  },
  toast: toast,
  escapeHtml: function (s) { return String(s == null ? '' : s); },
  normalizeCardType: normType,
  getDrawnTask: function () { return drawnTask; },
  getTimerOwner: function () { return Promise.resolve(makeTimerOwner({})); },
  timerSnapshot: function () { return timerOwnerSnap(); },
  refreshTimerViews: function () {},
  startInlineTimer: function () {},
  getActionsCache: function () { return null; },
  setActionsCache: function () {},
  onReturnToGacha: function () {}
});
ownerNone.openFreeCardEndForm(7);
findById(rightPanel, 'freeCardEndForm_7_activity').value = '做了点事';
await ownerNone.submitFreeCardEnd(7);
out.end_no_outcome_rejected = callOrder.indexOf('feedback.end') < 0;
out.end_no_outcome_feedback_written = callOrder.indexOf('feedback.end') >= 0;

// ---- 「帮我选」 ----------------------------------------------------------
rebuildCard(7);
apiCalls = []; callOrder = []; timerOps = [];
var ownerSug = makeOwner({});
ownerSug.openFreeCardAcceptForm(7);
var sugBox = rightPanel.children[0];
var sugActivity = findById(rightPanel, 'freeCardAcceptForm_7_activity');
var sugReason = findById(rightPanel, 'freeCardAcceptForm_7_reason');
sugActivity.value = '我自己写的';
sugReason.value = '我的理由';
await ownerSug.suggestFreeCardActivity(7);
out.suggest_filled_activity = sugActivity.value;
out.suggest_reason_unchanged = sugReason.value;
out.suggest_feedback_calls = apiCalls.filter(function (c) { return c.url === '/api/task-feedback'; }).length;
out.suggest_timer_starts = timerOps.filter(function (t) { return t === 'start'; }).length;

// 建议失败 → 保留用户输入
rebuildCard(7);
apiCalls = [];
var ownerSugFail = makeOwner({ failFeedback: true });
ownerSugFail.openFreeCardAcceptForm(7);
var sfBox = rightPanel.children[0];
var sfActivity = findById(rightPanel, 'freeCardAcceptForm_7_activity');
var sfReason = findById(rightPanel, 'freeCardAcceptForm_7_reason');
sfActivity.value = '我自己写的';
sfReason.value = '我的理由';
await ownerSugFail.suggestFreeCardActivity(7);
out.suggest_fail_activity_preserved = sfActivity.value;
out.suggest_fail_reason_preserved = sfReason.value;

console.log('PROBE_JSON=' + JSON.stringify(out));
'''


if __name__ == "__main__":
    unittest.main()
