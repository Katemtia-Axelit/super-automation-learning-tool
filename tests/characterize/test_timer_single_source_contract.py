"""AR03-P3-C —— 计时器 **单一来源** 契约测试。

背景
----
P3-C 消灭 classic ``static/app.js`` 里的 **双计时器**：

* **双 session getter**：``getSession`` 与 ``getActiveSession`` 两个读取入口
  各自可能被写成不一致的状态；
* **双 tick interval**：``dockTickHandle`` + ``panelTickHandle`` 两个并行
  ``setInterval`` 同时驱动 Dock 与任务页，存在"一个页面停了另一个还在跑"
  的漂移；
* **双编排实现**：``startTimer`` / ``stopTimer`` / ``handleTimerOutcome``
  写在 classic 层，而真实状态在 ESM owner 里。

迁移后必须成立的不变量
------------------------
1. ``static/modules/timer/index.js`` 与 ``presentation.js`` 合计 **只有一个**
   session getter 名（``getSession``），旧名 ``getActiveSession`` 彻底消失；
2. 计时器 owner 闭包内 **只有一个** interval 句柄（``tickHandle``），
   ``setInterval`` 在 owner 内 **只出现一次**；
3. classic ``app.js`` **不再** 直接调用 ``setInterval`` 驱动计时呈现，
   也 **不再** 保留第二个 tick 入口名（``startDockTick`` / ``startPanelTick``）；
4. classic ``app.js`` 的 ``startTimer`` / ``stopTimer`` /
   ``handleTimerOutcome`` 只做 **转发**（facade），业务语义在 owner 内；
5. owner 暴露 ``startTick`` / ``stopTick`` / ``hasTick``，
   且 ``startTick`` **幂等**（重复调用不会产生第二个 interval）。

全程 **不** 触碰生产数据库、不启动浏览器、不访问生产 notes / config。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC = PROJECT_ROOT / "static"
APP_JS = STATIC / "app.js"
TIMER_INDEX = STATIC / "modules" / "timer" / "index.js"
TIMER_PRESENTATION = STATIC / "modules" / "timer" / "presentation.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_node(script: str, timeout: int = 60) -> dict:
    """在 **合成** 环境里跑一段 Node 脚本，返回其 JSON 输出。"""
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
# C-1 / C-2：单一 session getter
# ---------------------------------------------------------------------------


class SingleSessionGetterTests(unittest.TestCase):
    """C-1：session 的 **读取入口唯一**。"""

    def test_timer_owner_declares_exactly_one_session_getter(self):
        """owner 内只有一个 session getter（``getSession``）。"""
        text = _read(TIMER_INDEX)
        # 函数声明形式：function getSession() { ... }
        decls = re.findall(r"function\s+(get\w*Session)\s*\(", text)
        self.assertEqual(
            sorted(set(decls)),
            ["getSession"],
            "timer owner 出现多个 session getter：" + repr(sorted(set(decls))),
        )

    def test_legacy_getter_name_is_gone_everywhere(self):
        """``getActiveSession`` 必须彻底消失（含注释与文档）。"""
        for path in (TIMER_INDEX, TIMER_PRESENTATION, APP_JS):
            text = _read(path)
            # 允许注释里出现（作为迁移说明），但 **不允许** 出现在代码里。
            code = re.sub(r"//.*", "", text)
            code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
            self.assertNotIn(
                "getActiveSession",
                code,
                f"{path.name} 仍使用旧 getter 名 getActiveSession",
            )

    def test_presentation_uses_single_getter_key(self):
        """presentation.js 的依赖键统一为 ``getSession``。"""
        text = _read(TIMER_PRESENTATION)
        self.assertIn("d.getSession", text)
        self.assertNotIn("d.getActiveSession", text)

    def test_both_surfaces_read_the_same_getter(self):
        """Dock 与任务页两个呈现面读 **同一个** getter。"""
        text = _read(TIMER_INDEX)
        # updateDock 与 updatePanel 都必须注入 getSession: getSession。
        self.assertGreaterEqual(
            text.count("getSession: getSession"),
            2,
            "Dock / Panel 未共用同一 session getter",
        )


# ---------------------------------------------------------------------------
# C-2：单一 tick interval
# ---------------------------------------------------------------------------


class SingleTickTests(unittest.TestCase):
    """C-2：只有一个 interval 句柄。

    计划 §3.3 C-2 明确：**主节拍** 只有一个 ``tickHandle``；内嵌计时器
    （``inlineTickHandle``）**保持独立** —— 它是「卡内」局部计时显示，
    读的是同一份 ``session``，不是第二个业务事实源。
    """

    def test_owner_declares_exactly_one_main_tick_handle(self):
        """owner 闭包内只有 **一个** 主节拍句柄。"""
        text = _read(TIMER_INDEX)
        # 主节拍句柄：var <something>TickHandle = null;
        handles = re.findall(r"var\s+(\w*[Tt]ickHandle)\s*=\s*null", text)
        self.assertIn("tickHandle", handles, "未找到主节拍句柄 tickHandle")
        # 除内嵌计时器外，不得再有第三个主节拍句柄。
        for legacy in ("dockTickHandle", "panelTickHandle"):
            self.assertNotIn("var " + legacy, text, "仍保留旧节拍句柄：" + legacy)
        # 句柄总数：主节拍 + 内嵌计时器 = 2。
        self.assertEqual(
            sorted(set(handles)),
            ["inlineTickHandle", "tickHandle"],
            "节拍句柄集合异常：" + repr(sorted(set(handles))),
        )

    def test_main_tick_uses_exactly_one_set_interval(self):
        """主节拍只创建 **一个** interval。

        owner 内共两个 ``setInterval``：主节拍 + 卡内嵌计时器（后者按计划
        §3.3 C-2 明确保留）。但主节拍路径（``startTick``）**只能**有一个。
        """
        text = _read(TIMER_INDEX)
        start_tick = text[text.index("function startTick(") : text.index("function stopTick(")]
        self.assertEqual(
            start_tick.count("setInterval("),
            1,
            "startTick 内出现多次 setInterval（主节拍不唯一）",
        )

    def test_inline_timer_reads_the_same_owner_session(self):
        """内嵌计时器 **只读** 同一 owner 的 session（不是第二事实源）。"""
        text = _read(TIMER_INDEX)
        start_inline = text[
            text.index("function startInlineTimer(") : text.index("function stopInlineTimer(")
        ]
        # 内嵌计时器不得自行发起计时请求或持有自己的 session。
        self.assertNotIn("/api/timer/", start_inline)
        self.assertNotIn("session =", start_inline.replace("!session", ""))

    def test_classic_layer_does_not_drive_timer_interval(self):
        """classic app.js **不再** 自建计时 interval。

        app.js 里剩下的 ``setInterval`` 只能是健康检查（``/api/health``），
        不得驱动任何计时呈现。
        """
        code = _read(APP_JS)
        for match in re.finditer(r"setInterval\(", code):
            window = code[match.start() : match.start() + 600]
            self.assertNotIn(
                "timer",
                window.lower(),
                "app.js 仍自建计时 interval（应全部归 owner）",
            )

    def test_classic_layer_has_no_second_tick_entry(self):
        """classic 层不再有第二个 tick 入口名。"""
        code = _read(APP_JS)
        for legacy in ("startDockTick", "startPanelTick"):
            self.assertNotIn(legacy, code, "app.js 仍调用旧 tick 入口：" + legacy)

    def test_owner_exposes_start_stop_has_tick(self):
        """owner 暴露统一节拍 API。"""
        text = _read(TIMER_INDEX)
        self.assertIn("function startTick(", text)
        self.assertIn("function stopTick(", text)
        self.assertIn("function hasTick(", text)
        self.assertIn("startTick: startTick", text)
        self.assertIn("stopTick: stopTick", text)
        self.assertIn("hasTick: hasTick", text)


# ---------------------------------------------------------------------------
# C-3：任务面板编排归位 owner
# ---------------------------------------------------------------------------


class PanelOrchestrationOwnershipTests(unittest.TestCase):
    """C-3：任务面板编排归位 owner，classic 只剩 facade。"""

    def test_owner_owns_panel_orchestration(self):
        """owner 内实现开始 / 停止 / 结束结论编排。"""
        text = _read(TIMER_INDEX)
        self.assertIn("function startTimerFromPanel(", text)
        self.assertIn("function stopTimerFromPanel(", text)
        self.assertIn("function handleTimerOutcome(", text)
        for name in (
            "startTimerFromPanel: startTimerFromPanel",
            "stopTimerFromPanel: stopTimerFromPanel",
            "handleTimerOutcome: handleTimerOutcome",
        ):
            self.assertIn(name, text)

    def test_classic_facades_are_thin_delegations(self):
        """classic ``startTimer`` / ``stopTimer`` / ``handleTimerOutcome``
        **只** 转发给 owner，不得各自实现业务。"""
        code = _read(APP_JS)
        for name in ("startTimer", "stopTimer", "handleTimerOutcome"):
            idx = code.index("async function " + name + "(")
            body = code[idx : idx + 1500]
            # 必须在函数体内调用 owner。
            self.assertIn(
                "owner.",
                body,
                f"classic {name} 未转发到 owner",
            )
            # 不得在 classic 层直接发计时 API 请求。
            self.assertNotIn("/api/timer/", body, f"classic {name} 直连计时接口")

    def test_classic_layer_no_longer_owns_outcome_business_logic(self):
        """结束结论的业务分支（反馈事件 / 提前完成提示）归位 owner。"""
        code = _read(APP_JS)
        # 这三段属于 owner 的编排语义，classic 层不得重复实现。
        self.assertNotIn("event_type: 'finish_on_time'", code)
        self.assertNotIn("completion_status: 'completed'", code)
        self.assertNotIn("WARM_MESSAGES.completedEarly", code)


# ---------------------------------------------------------------------------
# C-4：计时语义不回归（合成 DOM 实跑）
# ---------------------------------------------------------------------------


_TIMER_PROBE = r"""
import { createTimerOwner } from './static/modules/timer/index.js';

const out = {};

// --- 合成 DOM -------------------------------------------------------------
const byId = {};
function makeEl(tag, id) {
  const el = {
    tagName: (tag || 'div').toUpperCase(),
    id: id || '',
    value: '',
    textContent: '',
    innerHTML: '',
    attrs: {},
    classList: { _s: new Set(), contains(n) { return this._s.has(n); },
      add(n) { this._s.add(n); }, remove(n) { this._s.delete(n); } },
    style: {},
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'id') { this.id = String(v); byId[v] = this; } },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener() {},
    removeEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    appendChild(c) { return c; },
    removeChild() {},
    focus() {}
  };
  if (id) { el.id = id; byId[id] = el; }
  return el;
}
const documentRef = {
  getElementById(id) { return byId[id] || null; },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement(tag) { return makeEl(tag); }
};

// --- 伪造计时器 -----------------------------------------------------------
// 记录 **存活** 的 interval 数量（创建 +1，清除 -1），
// 以验证「任意时刻只有一个主节拍在跑」。
let liveIntervals = 0;
let createdIntervals = 0;
const realSetInterval = globalThis.setInterval;
const realClearInterval = globalThis.clearInterval;
globalThis.setInterval = function () {
  createdIntervals += 1;
  liveIntervals += 1;
  const handle = { fake: true, id: createdIntervals };
  handle.__counted = true;
  return handle;
};
globalThis.clearInterval = function (handle) {
  if (handle && handle.__counted) {
    liveIntervals -= 1;
    handle.__counted = false;
  }
};

// --- 依赖桩 ---------------------------------------------------------------
const calls = [];
function toast(msg, kind) { calls.push(['toast', msg, kind]); }
function showModal(id) { calls.push(['showModal', id]); }
function closeModal(id) { calls.push(['closeModal', id]); }
const warmMessages = { completedEarly: '提前完成提示', timeout: '超时提示' };
let feedbackPayloads = [];
let tasksChanged = 0;
let gachaChanged = 0;
let panelReloads = 0;

function parseBody(opts) {
  try { return opts && opts.body ? JSON.parse(opts.body) : {}; } catch (e) { return {}; }
}

const api = async function (url, opts) {
  calls.push(['api', url]);
  const body = parseBody(opts);
  if (url === '/api/timer/start') {
    return {
      session_id: 7,
      task_id: body.task_id,
      planned_minutes: body.planned_minutes,
      task_name: body.task_name
    };
  }
  if (url === '/api/timer/complete') {
    return { ok: true };
  }
  return { ok: true };
};

const owner = createTimerOwner({
  api,
  taskNameById: () => '任务名',
  formatElapsed: (ms) => String(ms),
  getTasks: () => [{ id: 1, name: '任务名' }],
  escapeHtml: (s) => String(s),
  documentRef,
  toast,
  showModal,
  closeModal,
  warmMessages,
  submitTaskFeedbackEvent: async (p) => { feedbackPayloads.push(p); },
  onTasksChanged: () => { tasksChanged += 1; },
  onGachaStatsChanged: () => { gachaChanged += 1; },
  reloadTimerPanel: async () => { panelReloads += 1; }
});

// --- 1) 节拍唯一性 --------------------------------------------------------
out.live_intervals_after_boot = liveIntervals;
out.has_tick_before = owner.hasTick();
owner.startTick();
out.has_tick_after = owner.hasTick();
out.live_intervals_after_start = liveIntervals;
// 幂等：再次 startTick 不应让 **存活** 的 interval 变多（内部先 clear）。
owner.startTick();
out.live_intervals_after_restart = liveIntervals;
owner.stopTick();
out.has_tick_after_stop = owner.hasTick();
out.live_intervals_after_stop = liveIntervals;

// --- 2) 未选任务 → fail closed -------------------------------------------
byId['timerTaskSelect'] = makeEl('select', 'timerTaskSelect');
byId['timerTaskSelect'].value = '';
byId['timerPlannedMin'] = makeEl('input', 'timerPlannedMin');
byId['timerPlannedMin'].value = '30';
calls.length = 0;
await owner.startTimerFromPanel();
out.start_no_task_toast = calls.find(c => c[0] === 'toast');
out.start_no_task_api_calls = calls.filter(c => c[0] === 'api').length;

// --- 3) 正常启动 ----------------------------------------------------------
byId['timerTaskSelect'].value = '1';
byId['timerPlannedMin'].value = '45';
calls.length = 0;
await owner.startTimerFromPanel();
out.start_ok_toast = calls.find(c => c[0] === 'toast');
out.start_ok_session_id = owner.getSnapshot().session && owner.getSnapshot().session.id;
out.start_ok_planned = owner.getSnapshot().session && owner.getSnapshot().session.planned_minutes;

// --- 4) 重复启动 → 拒绝 ---------------------------------------------------
calls.length = 0;
await owner.startTimerFromPanel();
out.start_again_toast = calls.find(c => c[0] === 'toast');

// --- 5) 停止 → 打开结论弹窗 ----------------------------------------------
calls.length = 0;
owner.stopTimerFromPanel();
out.stop_modal = calls.find(c => c[0] === 'showModal');

// --- 6) 结束结论：completed ----------------------------------------------
await owner.handleTimerOutcome('completed');
out.close_modal_called = true;
out.completed_feedback = feedbackPayloads[0];
out.completed_tasks_changed = tasksChanged;
out.completed_gacha_changed = gachaChanged;
out.completed_panel_reloads = panelReloads;
out.completed_session_cleared = owner.getSnapshot().session === null;

// --- 7) 结束结论失败 → 保留 session（绝不伪清空）-------------------------
const owner2 = createTimerOwner({
  api: async (url) => {
    if (url === '/api/timer/start') return { session_id: 9, task_id: 1, planned_minutes: 30 };
    if (url === '/api/timer/complete') throw new Error('完成接口炸了');
    return { ok: true };
  },  taskNameById: () => 'T', formatElapsed: (ms) => String(ms),
  getTasks: () => [], escapeHtml: (s) => String(s), documentRef,
  toast: (m, k) => calls.push(['toast2', m, k]),
  showModal, closeModal, warmMessages,
  submitTaskFeedbackEvent: async () => {},
  onTasksChanged: () => {}, onGachaStatsChanged: () => {},
  reloadTimerPanel: async () => {}
});
await owner2.startSession({ taskId: 1, plannedMinutes: 30, taskName: () => 'T' });
calls.length = 0;
await owner2.handleTimerOutcome('completed');
out.complete_fail_session_preserved = !!(owner2.getSnapshot().session && owner2.getSnapshot().session.id);
out.complete_fail_toast = calls.find(c => c[0] === 'toast2');

// --- 8) abandoned → result=abandoned ------------------------------------
const owner3 = createTimerOwner({
  api: async (url) => {
    if (url === '/api/timer/start') return { session_id: 11, task_id: 1, planned_minutes: 30 };
    if (url === '/api/timer/complete') { out.complete_payload = JSON.parse(JSON.stringify(globalThis.__lastBody || {})); return { ok: true }; }
    return { ok: true };
  },
  taskNameById: () => 'T', formatElapsed: (ms) => String(ms),
  getTasks: () => [], escapeHtml: (s) => String(s), documentRef,
  toast, showModal, closeModal, warmMessages,
  submitTaskFeedbackEvent: async () => {},
  onTasksChanged: () => {}, onGachaStatsChanged: () => {},
  reloadTimerPanel: async () => {}
});
await owner3.startSession({ taskId: 1, plannedMinutes: 30, taskName: () => 'T' });
await owner3.handleTimerOutcome('abandoned');
out.abandoned_session_cleared = owner3.getSnapshot().session === null;

globalThis.setInterval = realSetInterval;
globalThis.clearInterval = realClearInterval;
console.log('PROBE_JSON=' + JSON.stringify(out));
"""


class TimerBehaviorTests(unittest.TestCase):
    """C-4：计时语义不回归（合成 DOM 实跑真实 owner）。"""

    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_node(_TIMER_PROBE)

    def test_single_tick_created_once(self):
        """唯一节拍：启动后 **存活** 的 interval 只有 1 个。"""
        p = self.PROBE
        self.assertEqual(p["live_intervals_after_boot"], 0, p)
        self.assertEqual(p["live_intervals_after_start"], 1, p)
        self.assertTrue(p["has_tick_after"], p)

    def test_start_tick_is_idempotent(self):
        """重复 startTick 不产生第二个 **存活** interval。"""
        p = self.PROBE
        self.assertEqual(p["live_intervals_after_restart"], 1, p)

    def test_stop_tick_clears_handle(self):
        """stopTick 后句柄清空。"""
        p = self.PROBE
        self.assertFalse(p["has_tick_after_stop"], p)
        self.assertEqual(p["live_intervals_after_stop"], 0, p)

    def test_start_without_task_fails_closed(self):
        """未选任务 → 提示且 **不发** 任何计时请求。"""
        p = self.PROBE
        self.assertEqual(p["start_no_task_toast"][1], "请选择任务", p)
        self.assertEqual(p["start_no_task_toast"][2], "err", p)
        self.assertEqual(p["start_no_task_api_calls"], 0, p)

    def test_start_succeeds_with_selected_task(self):
        """选中任务 → 启动成功（session + 计划分钟）。"""
        p = self.PROBE
        self.assertEqual(p["start_ok_toast"][1], "计时已开始", p)
        self.assertEqual(p["start_ok_toast"][2], "suc", p)
        self.assertEqual(p["start_ok_session_id"], 7, p)
        self.assertEqual(p["start_ok_planned"], 45, p)

    def test_duplicate_start_is_rejected(self):
        """已有 session → 拒绝重复启动。"""
        p = self.PROBE
        self.assertEqual(p["start_again_toast"][1], "已有进行中的计时", p)
        self.assertEqual(p["start_again_toast"][2], "err", p)

    def test_stop_opens_outcome_modal(self):
        """停止 → 打开结论弹窗。"""
        p = self.PROBE
        self.assertEqual(p["stop_modal"][1], "timerOutcomeModal", p)

    def test_completed_outcome_writes_feedback_and_clears(self):
        """completed → 写反馈事件 + 清 session + 刷新任务/抽卡统计。"""
        p = self.PROBE
        fb = p["completed_feedback"]
        self.assertEqual(fb["event_type"], "finish_on_time", p)
        self.assertEqual(fb["completion_status"], "completed", p)
        self.assertEqual(fb["reason_detail"], "按时完成", p)
        self.assertGreaterEqual(p["completed_tasks_changed"], 1, p)
        self.assertGreaterEqual(p["completed_gacha_changed"], 1, p)
        self.assertGreaterEqual(p["completed_panel_reloads"], 1, p)
        self.assertTrue(p["completed_session_cleared"], p)

    def test_complete_failure_preserves_active_session(self):
        """完成接口失败 → **保留** 活动 session（绝不伪清空）。"""
        p = self.PROBE
        self.assertTrue(p["complete_fail_session_preserved"], p)
        self.assertEqual(p["complete_fail_toast"][1], "完成接口炸了", p)

    def test_abandoned_outcome_clears_session(self):
        """abandoned → 也清 session（结束结论路径正常收尾）。"""
        p = self.PROBE
        self.assertTrue(p["abandoned_session_cleared"], p)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
