"""M02-S03-G02 W03：统一抽卡行为事件 **前端接线** 契约测试。

范围（LT_M02_S03_G02_W03 / TASK_ID M02-S03-G02-FRONTEND-DRAW-REPLACE-EVENTS）：

  A. 静态合同（读 static/app.js 源码）
     - 事件上报只复用既有 ``POST /api/task-feedback``；
     - 请求体形状：``task_id`` / ``event_type`` / ``reason_category:'other'`` /
       ``note``（JSON 字符串，含 schema_version / event_id / session_id /
       source:'unified_gacha' / context）；
     - 四个 W03 事件类型全部接线：``card_drawn`` / ``card_shown`` /
       ``help_me_choose`` / ``card_replaced``；
     - **W04 的 6 个类型必须完全不存在**（task_started / timer_started /
       timer_ended / task_ended / card_discarded / card_restored）；
     - ``GET /api/gacha/free-card/suggestion`` **不得**被当成一次抽卡；
     - 上报点都在"服务端成功返回"分支内，失败分支不上报；
     - 上报 **不 await**（不阻断用户主操作）、不伪造成功、不用 setTimeout。

  B. JS VM 行为模拟（Node VM + 合成 stub，只用 tempfile）
     - 真实正整数 task_id 才会发请求；非法 id **零请求**；
     - 请求体字段逐字正确；
     - 失败 → 可见错误提示 + 未送达状态，**绝不**记成成功；
     - 失败后重发使用 **同一个 event_id**（后端幂等）；
     - session 连续性：同一条换卡链沿用 session；新 draw 换 session；
       离开抽卡页结束 session；
     - card_shown 在同一 session 内对同一张卡只记一次。

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
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
APP_JS = _PROJECT_ROOT / "static" / "app.js"

#: AR03-G14：抽卡行为事件的 **真实 owner**（ESM owner）。静态合同与 VM
#: 行为测试都以它为准 —— classic app.js 只保留极薄 facade。
GACHA_OWNER_JS = _PROJECT_ROOT / "static" / "modules" / "gacha" / "index.js"

#: AR03-P3-A：自由卡流程的 **真实 owner**（ESM owner）。
FREE_CARD_OWNER_JS = _PROJECT_ROOT / "static" / "modules" / "free-card" / "index.js"


#: W03 负责的 4 个事件类型。
W03_EVENT_TYPES = (
    "card_drawn",
    "card_shown",
    "help_me_choose",
    "card_replaced",
)

#: W03 **禁止**接入的 6 个事件类型（留给 W04：计时/弃牌共用其它 UI 路径）。
W04_ONLY_EVENT_TYPES = (
    "task_started",
    "timer_started",
    "timer_ended",
    "task_ended",
    "card_discarded",
    "card_restored",
)

#: 前端上报块在 **真实 owner** 源码中的起止标记（用于把帮助函数抽到
#: Node VM 里跑）。AR03-G14 起，抽卡行为事件的唯一 owner 是
#: ``static/modules/gacha/index.js``（ESM）；classic ``app.js`` 只保留
#: 极薄 facade。因此静态合同 **指向真实 owner**（测试漂移修复，
#: 断言语义完全不变）。
_HELPER_START_MARKER = "var UNIFIED_GACHA_EVENT_SOURCE = 'unified_gacha';"
_HELPER_END_MARKER = "function resetReplaceChain()"


def _read_app_js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _read_gacha_owner() -> str:
    return GACHA_OWNER_JS.read_text(encoding="utf-8")


def _read_free_card_owner() -> str:
    return FREE_CARD_OWNER_JS.read_text(encoding="utf-8")


def _function_body(js: str, name: str) -> str:
    """按花括号配平抽取一个 JS 函数的源码体（含外层花括号）。"""
    match = re.search(
        r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
        js,
    )
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for index in range(start, len(js)):
        char = js[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return js[start:index + 1]
    return js[start:]


def _helper_block(js: str) -> str:
    """抽取前端行为事件帮助函数的整段源码。"""
    start = js.find(_HELPER_START_MARKER)
    if start == -1:
        return ""
    end = js.find(_HELPER_END_MARKER, start)
    if end == -1:
        return ""
    return js[start:end]


# ===========================================================================
# A. 静态合同
# ===========================================================================


class FrontendBehaviorEventStaticContractTests(unittest.TestCase):
    """只读 **真实 owner**（static/modules/gacha/index.js）的静态合同。

    AR03-G14 之后，抽卡行为事件的实现已从 classic app.js 迁到 ESM owner。
    静态合同必须指向真实 owner，否则测试就在验证一段已不存在的代码。
    """

    @classmethod
    def setUpClass(cls):
        cls.js = _read_gacha_owner()
        cls.app_js = _read_app_js()
        cls.helpers = _helper_block(cls.js)

    def test_helper_block_exists(self):
        self.assertTrue(
            self.helpers,
            "抽卡 owner 必须包含 M02-S03-G02-W03 的行为事件帮助函数块",
        )

    # -- 上报通道 ------------------------------------------------------
    def test_reuses_existing_task_feedback_endpoint(self):
        """只能复用既有 POST /api/task-feedback，不新建第二套日志。"""
        body = _function_body(self.js, "sendUnifiedGachaEvent")
        self.assertTrue(body, "sendUnifiedGachaEvent 必须存在")
        self.assertIn("'/api/task-feedback'", body)
        self.assertIn("method: 'POST'", body)
        self.assertNotIn("/api/task-feedback/", body)

    def test_request_payload_shape_is_exact(self):
        """请求体必须是 task_id / event_type / reason_category:'other' / note。"""
        body = _function_body(self.js, "sendUnifiedGachaEvent")
        self.assertIn("task_id: tid", body)
        self.assertIn("event_type: eventType", body)
        self.assertIn("reason_category: 'other'", body)
        self.assertIn("note: JSON.stringify(note)", body)
        # 不得携带虚构的完成状态 / 时间 / 用户文本字段
        for forbidden in (
            "completion_status",
            "actual_minutes",
            "planned_minutes",
            "reason_detail",
        ):
            self.assertNotIn(
                forbidden,
                body,
                f"W03 事件不得携带 {forbidden}（会虚构用户观察）",
            )

    def test_note_structure_matches_backend_contract(self):
        """note = {schema_version:1, event_id, session_id, source, context}。"""
        body = _function_body(self.js, "sendUnifiedGachaEvent")
        for field in (
            "schema_version",
            "event_id",
            "session_id",
            "source",
            "context",
        ):
            self.assertIn(field, body, f"note 必须包含 {field}")
        self.assertIn("UNIFIED_GACHA_EVENT_SCHEMA_VERSION", body)
        self.assertIn("UNIFIED_GACHA_EVENT_SOURCE", body)
        # schema_version 固定为 1；source 固定为 'unified_gacha'
        self.assertIn("UNIFIED_GACHA_EVENT_SCHEMA_VERSION = 1", self.helpers)
        self.assertIn("UNIFIED_GACHA_EVENT_SOURCE = 'unified_gacha'", self.helpers)

    # -- 事件类型覆盖 --------------------------------------------------
    def test_all_four_w03_event_types_are_wired(self):
        for event_type in W03_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                self.assertIn(
                    "'" + event_type + "'",
                    self.js,
                    f"W03 必须接线事件类型 {event_type}",
                )
        # 帮助函数必须能接受这 4 种类型（不是硬编码单一类型）。
        helper = _function_body(self.js, "sendUnifiedGachaEvent")
        self.assertIn("event_type: eventType", helper)

    def test_w04_only_event_types_are_absent(self):
        """W04 的 6 个类型在本工单里必须完全不存在。"""
        for event_type in W04_ONLY_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                self.assertNotIn(
                    "'" + event_type + "'",
                    self.js,
                    f"W03 禁止接入 {event_type}（属于 W04）",
                )

    # -- 各抽卡路径的接线 ----------------------------------------------
    def test_single_draw_reports_card_drawn_and_card_shown(self):
        body = _function_body(self.js, "drawGacha")
        self.assertTrue(body, "drawGacha 必须存在")
        self.assertIn("'card_drawn'", body)
        # card_shown 通过统一帮助函数上报（renderDrawnCard 之后）。
        self.assertIn("reportUnifiedGachaCardShown(", body)
        shown_at = body.find("reportUnifiedGachaCardShown(")
        rendered_at = body.find("renderDrawnCard(")
        self.assertNotEqual(shown_at, -1)
        self.assertNotEqual(rendered_at, -1)
        self.assertGreater(
            shown_at, rendered_at, "card_shown 必须在卡片渲染之后记录"
        )
        # 必须用服务端返回的真实 task id
        self.assertIn("unifiedGachaTaskId(r.task.id)", body)

    def test_multi_draw_reports_every_valid_task(self):
        body = _function_body(self.js, "drawGachaMulti")
        self.assertTrue(body, "drawGachaMulti 必须存在")
        self.assertIn("'card_drawn'", body)
        self.assertIn("r.tasks.forEach", body)
        self.assertIn("unifiedGachaTaskId(task && task.id)", body)

    def test_care_draw_reports_card_drawn_and_help_me_choose(self):
        body = _function_body(self.js, "drawGachaWithCategory")
        self.assertTrue(body, "drawGachaWithCategory 必须存在")
        self.assertIn("'card_drawn'", body)
        self.assertIn("'help_me_choose'", body)
        # help_me_choose 的 context 只放实际 include/exclude category 与 pool
        self.assertIn("include_category: includeCategory || null", body)
        self.assertIn("exclude_category: excludeCategory || null", body)

    def test_replace_reports_card_replaced_on_old_card(self):
        body = _function_body(self.js, "doReplace")
        self.assertTrue(body, "doReplace 必须存在")
        self.assertIn("'card_replaced'", body)
        # task_id 指真实被换出的那张牌
        self.assertIn("unifiedGachaTaskId(rid)", body)
        self.assertIn("sendUnifiedGachaEvent('card_replaced', replacedTaskId", body)
        # context：明确选择的四种换卡理由 + 两个开关 + 真实 pool
        for field in (
            "new_task_id",
            "reason: reason",
            "allow_repeat_replaced: allowRepeat",
            "hide_today: hideToday",
            # owner 内部的抽卡状态是 `state`（AR03-G14 迁出 classic 的
            # `gachaState` 全局副本），语义与迁移前逐字一致。
            "pool: r.pool || state.pool",
        ):
            self.assertIn(field, body, f"card_replaced context 必须含 {field}")

    def test_replace_keeps_new_card_card_drawn_and_card_shown(self):
        body = _function_body(self.js, "doReplace")
        self.assertIn("sendUnifiedGachaEvent('card_drawn', newTaskId", body)
        self.assertIn("reportUnifiedGachaCardShown(r.task.id", body)

    def test_free_card_suggestion_is_not_treated_as_a_draw(self):
        """GET /api/gacha/free-card/suggestion 不得被当成一次抽卡。"""
        # AR03-P3-A：自由卡建议的实现归位到 owner 模块
        # （static/modules/free-card/index.js）；classic app.js 只保留薄 facade。
        # 合同必须锚定 **实现**，否则模块化本身就会让断言变成"测门面壳子"。
        body = _function_body(_read_free_card_owner(), "suggestFreeCardActivity")
        self.assertTrue(
            body, "suggestFreeCardActivity 必须存在（帮我选建议路径）"
        )
        self.assertIn("/api/gacha/free-card/suggestion", body)
        for forbidden in (
            "'card_drawn'",
            "'card_shown'",
            "'help_me_choose'",
            "beginUnifiedGachaSession",
        ):
            self.assertNotIn(
                forbidden,
                body,
                "free-card/suggestion 只是建议，不得记成抽卡事件",
            )

    # -- 成功才上报 / 失败不误报 ---------------------------------------
    def test_reports_live_inside_success_branches(self):
        """上报点必须位于"服务端成功返回"分支内。"""
        cases = (
            ("drawGacha", "if (r.task)"),
            ("drawGachaWithCategory", "if (r.task)"),
            ("doReplace", "if (r.task)"),
        )
        for name, guard in cases:
            with self.subTest(function=name):
                body = _function_body(self.js, name)
                self.assertTrue(body, f"{name} 必须存在")
                guard_index = body.find(guard)
                self.assertNotEqual(guard_index, -1, f"{name} 必须有 {guard} 分支")
                report_index = body.find("sendUnifiedGachaEvent(")
                self.assertNotEqual(report_index, -1, f"{name} 必须有上报点")
                self.assertGreater(
                    report_index,
                    guard_index,
                    f"{name} 的上报点必须位于成功分支 {guard} 之后",
                )

    def test_catch_branches_do_not_report_events(self):
        """失败分支绝不上报成功事件。"""
        for name in ("drawGacha", "drawGachaWithCategory", "doReplace"):
            with self.subTest(function=name):
                body = _function_body(self.js, name)
                catch_index = body.rfind("catch (e)")
                self.assertNotEqual(catch_index, -1, f"{name} 必须有 catch 分支")
                tail = body[catch_index:]
                self.assertNotIn(
                    "sendUnifiedGachaEvent(",
                    tail,
                    f"{name} 的失败分支不得上报事件",
                )

    def test_multi_draw_empty_result_reports_nothing(self):
        body = _function_body(self.js, "drawGachaMulti")
        empty_branch = body.find("} else {")
        self.assertNotEqual(empty_branch, -1, "drawGachaMulti 必须有 else 分支")
        # 上报循环位于成功分支内（forEach 在 if (r.tasks && ...) 之后）
        self.assertIn("r.tasks.forEach", body)
        self.assertIn("if (r.tasks && r.tasks.length > 0)", body)

    # -- 不阻断主操作 / 不伪造成功 ------------------------------------
    def test_reports_are_not_awaited(self):
        """上报不得 await：绝不阻断用户主操作等待事件写入。"""
        for name in (
            "drawGacha",
            "drawGachaMulti",
            "drawGachaWithCategory",
            "doReplace",
        ):
            with self.subTest(function=name):
                body = _function_body(self.js, name)
                self.assertNotIn(
                    "await sendUnifiedGachaEvent(",
                    body,
                    f"{name} 不得 await 上报（不得阻断主操作）",
                )
                self.assertNotIn(
                    "await reportUnifiedGachaCardShown(",
                    body,
                    f"{name} 不得 await card_shown 上报",
                )

    def test_no_settimeout_based_fake_success(self):
        """不得用 setTimeout 伪造成功。"""
        body = _function_body(self.js, "sendUnifiedGachaEvent")
        self.assertNotIn("setTimeout", body)
        self.assertNotIn("setTimeout", _function_body(self.js, "reportUnifiedGachaCardShown"))

    def test_failure_surfaces_visible_error_and_never_claims_saved(self):
        """失败必须可见（toast），且不得谎称保存成功。"""
        body = _function_body(self.js, "sendUnifiedGachaEvent")
        self.assertIn(".catch(", body)
        self.assertIn("toast(", body)
        self.assertIn("_delivery.failed += 1", body)
        self.assertIn("_delivery.lastError", body)
        self.assertIn("lastFailed", body)
        # 成功计数只能出现在 .then 里
        then_part = body.split(".then(", 1)[-1]
        self.assertIn("_delivery.sent += 1", then_part)

    # -- session 生命周期 ----------------------------------------------
    def test_new_draw_starts_new_session(self):
        for name in ("drawGacha", "drawGachaMulti", "drawGachaWithCategory"):
            with self.subTest(function=name):
                body = _function_body(self.js, name)
                self.assertIn(
                    "beginUnifiedGachaSession()",
                    body,
                    f"{name} 必须开启新 session",
                )

    def test_replace_chain_keeps_same_session(self):
        """同一条连续换卡链沿用 session：doReplace 不得开启新 session。"""
        body = _function_body(self.js, "doReplace")
        self.assertNotIn(
            "beginUnifiedGachaSession()",
            body,
            "doReplace 必须沿用当前 session（换卡链不换 session）",
        )
        self.assertIn("newUnifiedGachaActionId(", body)

    def test_leaving_gacha_page_ends_session(self):
        # showPage 仍在 classic app.js（页面切换是 classic 层的职责），
        # 但 session 的结束句柄来自 owner facade。
        body = _function_body(self.app_js, "showPage")
        self.assertTrue(body, "showPage 必须存在")
        self.assertIn("endUnifiedGachaSession()", body)
        self.assertIn("if (id !== 'gacha')", body)

    def test_event_ids_are_unique_per_action_but_stable_on_retry(self):
        """每个真实动作一个 action id；重发同一动作仍是同一个 event_id。"""
        body = _function_body(self.js, "unifiedGachaEventId")
        self.assertIn("actionId", body)
        self.assertIn("eventType", body)
        self.assertNotIn(
            "Math.random", body, "event_id 派生不得掺入随机量（必须可重放）"
        )
        # action id 本身包含随机量 → 不同动作的 event_id 互不相同
        action_body = _function_body(self.js, "newUnifiedGachaActionId")
        self.assertIn("newUnifiedGachaEventId(", action_body)
        gen_body = _function_body(self.js, "newUnifiedGachaEventId")
        self.assertIn("Math.random", gen_body)
        self.assertIn("Date.now()", gen_body)

    def test_task_id_must_be_strict_positive_integer(self):
        body = _function_body(self.js, "unifiedGachaTaskId")
        self.assertTrue(body, "unifiedGachaTaskId 必须存在")
        self.assertIn("isFinite", body)
        self.assertIn("Math.floor", body)
        self.assertIn("n <= 0", body)


# ===========================================================================
# B. JS VM 行为模拟（Node）
# ===========================================================================

_NODE_HARNESS = r"""
'use strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// AR03-G14：真实 owner 是 ESM 模块 static/modules/gacha/index.js。
// 本 harness 用 **真实 owner 实例**（createGachaOwner）跑行为，而不是复刻
// 一份 app.js 里的旧实现。owner 与它的同目录依赖 presentation.js 一并
// 复制到临时目录（临时目录，绝不写回仓库）。
const ownerPath = path.join(__dirname, 'gacha', 'index.mjs');

async function main() {
  const { createGachaOwner } = await import(
    'file://' + ownerPath.replace(/\\/g, '/')
  );

  // ---- 合成 stub：不接任何真实网络 / 真实 DOM ------------------------
  const sent = [];      // 已发出的请求
  const toasts = [];    // 可见提示
  let failNext = false;

  function api(url, opts) {
    if (failNext) {
      failNext = false;
      return Promise.reject(new Error('合成失败'));
    }
    sent.push({ url: url, opts: opts, body: JSON.parse(opts.body) });
    return Promise.resolve({ saved: true, id: sent.length, status: 'created' });
  }
  function toast(msg, type) { toasts.push({ msg: msg, type: type || 'inf' }); }

  const owner = createGachaOwner({
    documentRef: { getElementById: function () { return null; } },
    api: api,
    toast: toast,
    showModal: function () {},
    closeModal: function () {},
    WARM_MESSAGES: {},
    renderDrawnCard: function () { return null; },
    refreshGachaStats: function () {},
    updateDiscardPileVisual: function () {},
    _timerSnapshot: null,
    _timerRunning: false,
    setCurrentDrawnTask: function () {},
    setMultiDrawResults: function () {}
  });

  const out = { sent: sent, toasts: toasts, results: {} };
  const S = owner;

  // ---- 1. 真实正整数 task_id 才发请求 ------------------------------
  S.beginUnifiedGachaSession();
  const actionId = S.newUnifiedGachaActionId('draw');
  await S.sendUnifiedGachaEvent('card_drawn', 42, { pool: 'tomato' },
    S.unifiedGachaEventId(actionId, 'card_drawn', 42));
  out.results.oneRequest = sent.length;
  const first = sent[0];
  out.results.url = first.url;
  out.results.method = first.opts.method;
  out.results.taskId = first.body.task_id;
  out.results.eventType = first.body.event_type;
  out.results.reasonCategory = first.body.reason_category;
  out.results.note = JSON.parse(first.body.note);

  // ---- 2. 非法 task_id → 零请求 -------------------------------------
  const before = sent.length;
  for (const bad of [0, -1, 'abc', null, undefined, 1.5, NaN, '1abc']) {
    await S.sendUnifiedGachaEvent('card_drawn', bad, {}, 'evt-' + String(bad));
  }
  out.results.invalidTaskIdRequests = sent.length - before;

  // ---- 3. session 连续性 --------------------------------------------
  const sessionA = S.getUnifiedGachaSessionId();
  // 换卡链：不开启新 session，沿用同一个
  await S.sendUnifiedGachaEvent('card_replaced', 7, { reason: 'no_time' }, 'evt-rep-1');
  const sessionAfterReplace = S.getUnifiedGachaSessionId();
  out.results.sessionStableInChain = (sessionA === sessionAfterReplace);
  out.results.replaceNoteSession = JSON.parse(sent[sent.length - 1].body.note).session_id;
  out.results.replaceNoteSessionMatches = (out.results.replaceNoteSession === sessionA);

  // 新的一次 draw → 新 session
  S.beginUnifiedGachaSession();
  const sessionB = S.getUnifiedGachaSessionId();
  out.results.newSessionDiffers = (sessionA !== sessionB);
  out.results.sessionIdNonEmpty = (typeof sessionB === 'string' && sessionB.length > 0);

  // 离开抽卡页 → 结束 session；再取时应是新 session
  S.endUnifiedGachaSession();
  const sessionC = S.getUnifiedGachaSessionId();
  out.results.endSessionStartsNew = (sessionC !== sessionB);
  out.results.endSessionIdDiffers = (sessionC !== sessionA);

  // ---- 4. card_shown 去重（同 session 同卡同展示面同动作只记一次）----
  S.beginUnifiedGachaSession();
  const shownBefore = sent.length;
  await S.reportUnifiedGachaCardShown(99, { source: 'single_draw' }, 'act-x');
  await S.reportUnifiedGachaCardShown(99, { source: 'single_draw' }, 'act-x');
  out.results.shownSameCard = sent.length - shownBefore;
  // 换出新牌（新 task id）→ 新的 card_shown
  const shownBefore2 = sent.length;
  await S.reportUnifiedGachaCardShown(100, { source: 'replace' }, 'act-y');
  out.results.shownNewCard = sent.length - shownBefore2;
  // 不同展示面 → 各自记一次
  const shownBefore3 = sent.length;
  await S.reportUnifiedGachaCardShown(99, { surface: 'multi_list' }, 'act-z');
  await S.reportUnifiedGachaCardShown(99, { surface: 'multi_activated' }, 'act-z');
  out.results.shownDistinctSurface = sent.length - shownBefore3;
  // 同一张卡在换牌链上再次被展示（不同动作）→ 各记一次
  const shownBefore4 = sent.length;
  await S.reportUnifiedGachaCardShown(99, { surface: 'result' }, 'act-rep-1');
  await S.reportUnifiedGachaCardShown(99, { surface: 'result' }, 'act-rep-2');
  out.results.shownReshownInChain = sent.length - shownBefore4;

  // ---- 5. 失败 → 可见提示 + 未送达状态；绝不记成成功 ---------------
  const sentBeforeFail = sent.length;
  failNext = true;
  const failResult = await S.sendUnifiedGachaEvent('card_drawn', 55, { pool: 'x' }, 'evt-fail-1');
  out.results.failOk = failResult.ok;
  out.results.failRequests = sent.length - sentBeforeFail;
  out.results.failToastCount = toasts.length;
  out.results.failToastText = toasts.length ? toasts[toasts.length - 1].msg : '';
  out.results.failToastType = toasts.length ? toasts[toasts.length - 1].type : '';
  const delivery = S.getDeliverySnapshot();
  out.results.deliveryFailed = delivery.failed;
  out.results.deliveryLastError = delivery.lastError;
  out.results.deliveryLastFailedEventId =
    delivery.lastFailed ? delivery.lastFailed.event_id : null;

  // ---- 6. 失败后重发：event_id 必须不变（后端幂等）-----------------
  failNext = false;
  await S.sendUnifiedGachaEvent('card_drawn', 55, { pool: 'x' }, 'evt-fail-1');
  out.results.retryEventId =
    JSON.parse(sent[sent.length - 1].body.note).event_id;

  // ---- 7. 同一 action + 事件类型 + task → event_id 稳定 ------------
  out.results.stableEventId = (
    S.unifiedGachaEventId('act-1', 'card_drawn', 5) ===
    S.unifiedGachaEventId('act-1', 'card_drawn', 5)
  );
  out.results.differentActionDiffers = (
    S.unifiedGachaEventId('act-1', 'card_drawn', 5) !==
    S.unifiedGachaEventId('act-2', 'card_drawn', 5)
  );

  // ---- 8. 成功计数只在 .then 里 ------------------------------------
  const finalDelivery = S.getDeliverySnapshot();
  out.results.deliverySent = finalDelivery.sent;
  out.results.deliveryPending = finalDelivery.pending;

  process.stdout.write(JSON.stringify(out));
}

main().catch((e) => {
  process.stderr.write('HARNESS ERROR: ' + (e && e.stack || e));
  process.exit(1);
});
"""


class FrontendBehaviorEventVmTests(unittest.TestCase):
    """在 Node VM 里跑前端帮助函数的真实行为（合成 stub，无网络）。"""

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node 不可用，跳过 JS VM 行为测试")
        cls.node = node
        cls.js = _read_gacha_owner()
        cls.helpers = _helper_block(cls.js)
        if not cls.helpers:
            raise unittest.SkipTest("抽卡 owner 中找不到行为事件帮助函数块")

        cls._tmp = tempfile.TemporaryDirectory(
            prefix="lt_m02_behavior_fe_", ignore_cleanup_errors=True
        )
        tmp_root = Path(cls._tmp.name)
        # 把 **真实 owner** 及其同目录依赖复制到临时目录（只读仓库、只写临时
        # 目录；绝不改回仓库文件）。owner 是 ESM，但仓库 package.json 没有
        # "type": "module"，因此复制为 .mjs，并把内部相对 import 改指 .mjs。
        owner_dir = tmp_root / "gacha"
        owner_dir.mkdir(parents=True, exist_ok=True)
        owner_src = GACHA_OWNER_JS.read_text(encoding="utf-8")
        owner_src = owner_src.replace(
            "from './presentation.js'", "from './presentation.mjs'"
        )
        (owner_dir / "index.mjs").write_text(owner_src, encoding="utf-8")
        shutil.copyfile(
            GACHA_OWNER_JS.parent / "presentation.js",
            owner_dir / "presentation.mjs",
        )
        harness_path = tmp_root / "harness.mjs"
        harness_path.write_text(_NODE_HARNESS, encoding="utf-8")

        result = subprocess.run(
            [cls.node, str(harness_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_root),
        )
        cls.stderr = result.stderr
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

    # -- 请求形状 ------------------------------------------------------
    def test_posts_to_task_feedback_with_post(self):
        self.assertEqual(self.out["results"]["url"], "/api/task-feedback")
        self.assertEqual(self.out["results"]["method"], "POST")

    def test_request_body_matches_backend_contract(self):
        self.assertEqual(self.out["results"]["taskId"], 42)
        self.assertEqual(self.out["results"]["eventType"], "card_drawn")
        self.assertEqual(self.out["results"]["reasonCategory"], "other")

    def test_note_is_valid_backend_note_object(self):
        note = self.out["results"]["note"]
        self.assertEqual(note["schema_version"], 1)
        self.assertEqual(note["source"], "unified_gacha")
        self.assertIsInstance(note["event_id"], str)
        self.assertTrue(note["event_id"].strip())
        self.assertLessEqual(len(note["event_id"]), 128)
        self.assertIsInstance(note["session_id"], str)
        self.assertTrue(note["session_id"].strip())
        self.assertLessEqual(len(note["session_id"]), 128)
        self.assertIsInstance(note["context"], dict)
        self.assertEqual(note["context"]["pool"], "tomato")

    def test_only_one_request_per_successful_event(self):
        self.assertEqual(self.out["results"]["oneRequest"], 1)

    # -- 真实 task id --------------------------------------------------
    def test_invalid_task_ids_never_produce_a_request(self):
        self.assertEqual(
            self.out["results"]["invalidTaskIdRequests"],
            0,
            "非法 / 非正整数 task_id 必须零请求（绝不伪造 id）",
        )

    # -- session 连续性 ------------------------------------------------
    def test_session_is_stable_inside_one_replace_chain(self):
        self.assertTrue(self.out["results"]["sessionStableInChain"])
        self.assertTrue(self.out["results"]["replaceNoteSessionMatches"])

    def test_new_draw_starts_a_new_session(self):
        self.assertTrue(self.out["results"]["newSessionDiffers"])
        self.assertTrue(self.out["results"]["sessionIdNonEmpty"])

    def test_leaving_gacha_page_ends_the_session(self):
        self.assertTrue(self.out["results"]["endSessionStartsNew"])
        self.assertTrue(self.out["results"]["endSessionIdDiffers"])

    # -- card_shown 去重 ------------------------------------------------
    def test_card_shown_is_reported_once_per_card_per_session(self):
        self.assertEqual(
            self.out["results"]["shownSameCard"],
            1,
            "同一 session 内同一张卡在同一展示面只能记一次 card_shown",
        )

    def test_distinct_show_surfaces_are_each_reported(self):
        """连抽列表展示与激活到主卡位是两个真实展示面，各记一条。"""
        self.assertEqual(
            self.out["results"]["shownDistinctSurface"],
            2,
            "不同展示面（列表 / 激活）必须各记一次 card_shown",
        )

    def test_card_reshown_in_replace_chain_is_reported_again(self):
        """换牌链上同一张卡再次被展示（不同动作）→ 各记一次。"""
        self.assertEqual(
            self.out["results"]["shownReshownInChain"],
            2,
            "换牌链上再次展示同一张卡必须各记一次 card_shown",
        )

    def test_new_card_after_replace_gets_its_own_card_shown(self):
        self.assertEqual(self.out["results"]["shownNewCard"], 1)

    # -- 失败不误报 ----------------------------------------------------
    def test_failure_does_not_report_success(self):
        self.assertFalse(self.out["results"]["failOk"], "失败不得被当成成功")
        self.assertEqual(
            self.out["results"]["failRequests"], 0, "失败时不得有额外成功写入"
        )
        self.assertGreaterEqual(self.out["results"]["failToastCount"], 1)
        self.assertIn("未送达", self.out["results"]["failToastText"])
        self.assertEqual(self.out["results"]["failToastType"], "err")

    def test_failure_records_undelivered_state(self):
        self.assertGreaterEqual(self.out["results"]["deliveryFailed"], 1)
        self.assertTrue(self.out["results"]["deliveryLastError"])

    def test_retry_after_failure_reuses_the_same_event_id(self):
        self.assertEqual(
            self.out["results"]["deliveryLastFailedEventId"],
            "evt-fail-1",
        )
        self.assertEqual(
            self.out["results"]["retryEventId"],
            "evt-fail-1",
            "重发同一行为必须使用同一 event_id（后端幂等）",
        )

    # -- event_id 稳定性 ------------------------------------------------
    def test_event_id_is_stable_for_same_action_and_differs_across_actions(self):
        self.assertTrue(self.out["results"]["stableEventId"])
        self.assertTrue(self.out["results"]["differentActionDiffers"])

    def test_delivery_counters_end_balanced(self):
        self.assertEqual(self.out["results"]["deliveryPending"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
