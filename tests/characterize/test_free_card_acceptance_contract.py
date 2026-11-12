"""M02-S02-G01-W08: 正式抽卡页面的自由卡接受与活动记录（契约测试）。

唯一可独立验收目标
------------------
在 **完全合成隔离目录** 内验证两件事：

A. **后端**：``POST /api/task-feedback`` 能接受新的 ``accept_task`` 事件，
   并把用户填写���活动 + 理由 + 计时会话绑定进既有追加式 ``task_feedback_events``；
   非法输入一律 400 且 **零写入**；既有事件类型的行为 **逐字不变**。

B. **前端**：正式抽卡页面里，自由卡的主操作是"接受自由卡"，点击后在
   **同一张卡片内** 展开接受表单；活动必填；合法输入会调用既有
   ``POST /api/timer/start``（``planned_minutes`` 严格等于本次发行的
   ``effective_minutes``）并随后写 ``accept_task`` 事件；没有可派发时长时
   **绝不** 启动计时；普通/微型/目标卡仍走原有普通 ``startTask`` 路径。

范围与红线
----------
- 全部状态在 ``tempfile`` 临时目录内：合成 SQLite + 合成 Flask app。
  **绝不** 读写真实 ``data/task_publisher.db``(±wal/shm)、``config/config.json``、
  ``src/notes/**``、``data/agent-policy/**``。
- 前端在 **Node 合成 DOM mock** 里执行 ``static/app.js``（沿用既有
  ``tests/characterize/test_card_type_frontend.py`` 的沙箱模式）：``fetch``
  被替换为记录调用的 stub，``document`` 被替换为最小 DOM 实现。
- 本文件是本工单 **唯一新增** 测试文件，只写测试、不改生产代码。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(SOURCE_ROOT), str(SOURCE_ROOT / "scripts")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from flask import Flask  # noqa: E402

from server.blueprints.feedback_bp import feedback_bp  # noqa: E402
from server.blueprints.timer_bp import timer_bp  # noqa: E402
from server.services import feedback as feedback_service  # noqa: E402
from server.services import free_task  # noqa: E402

APP_JS = SOURCE_ROOT / "static" / "app.js"
INDEX_HTML = SOURCE_ROOT / "src" / "index.html"

#: 自由卡合法时长（唯一权威来自生产领域模块，本文件不另立一套）。
LEGAL_FREE_MINUTES = tuple(free_task.FREE_TASK_MINUTES_OPTIONS)

#: 缺省理由（产品约定的精确文本）。
DEFAULT_REASON = free_task.DEFAULT_FREE_TASK_REASON

#: 与真实 ``server/schema/feedback.py`` 逐字一致的合成 schema（只建本文件
#: 用到的表）。**不** 引入任何生产 DB。
_SYNTH_SCHEMA = """
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, category TEXT DEFAULT 'daily',
  task_type TEXT DEFAULT 'normal', description TEXT,
  estimated_time INTEGER DEFAULT 25, repeat_type TEXT DEFAULT 'none',
  priority INTEGER DEFAULT 5, tags TEXT, is_unlocked INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE task_feedback_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  planned_minutes INTEGER,
  actual_minutes INTEGER,
  completion_status TEXT,
  reason_category TEXT NOT NULL,
  reason_detail TEXT,
  note TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);
CREATE TABLE task_completion_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  energy_after INTEGER,
  mood_after TEXT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE timer_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  planned_minutes INTEGER DEFAULT 30,
  paused_seconds INTEGER DEFAULT 0,
  status TEXT DEFAULT 'running',
  ended_at TEXT,
  actual_minutes INTEGER,
  result TEXT,
  reason TEXT
);
"""


class _FeedbackHarness:
    """一次性的合成 app + 合成 DB（全部在临时目录内）。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.db_path = root / "synthetic.sqlite3"
        with sqlite3.connect(self.db_path) as db:
            db.executescript(_SYNTH_SCHEMA)
            db.execute(
                "INSERT INTO tasks (id, name, category, task_type, estimated_time) "
                "VALUES (1, 'free-card', 'study', 'free', 80)"
            )
            db.commit()
        self.app = Flask(__name__)
        self.app.config["_db_path"] = str(self.db_path)
        self.app.register_blueprint(feedback_bp)
        self.app.register_blueprint(timer_bp)
        self.client = self.app.test_client()

    # --- 断言辅助 ---------------------------------------------------------
    def post_feedback(self, payload):
        return self.client.post("/api/task-feedback", json=payload)

    def events(self):
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM task_feedback_events ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def event_count(self) -> int:
        return len(self.events())

    def timer_rows(self):
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM timer_sessions ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]


def _accept_payload(**overrides):
    """一个合法的 ``accept_task`` 请求体。"""
    payload = {
        "task_id": 1,
        "event_type": "accept_task",
        "planned_minutes": 25,
        "completion_status": "accepted",
        "reason_category": "other",
        "reason_detail": DEFAULT_REASON,
        "note": json.dumps(
            {"schema_version": 1, "session_id": 7, "activity": "看纪录片"},
            ensure_ascii=False,
        ),
    }
    payload.update(overrides)
    return payload


# ===========================================================================
# A. 后端契约：accept_task
# ===========================================================================


class AcceptTaskBackendContractTests(unittest.TestCase):
    """合法 ``accept_task`` 写入 201；非法输入 400 且零写入。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(
            prefix="lt_fc_accept_", ignore_cleanup_errors=True
        )
        self.harness = _FeedbackHarness(Path(self._tmp.name))

    def tearDown(self):
        try:
            self._tmp.cleanup()
        except Exception:
            pass

    # --- 合法路径 -------------------------------------------------------
    def test_valid_accept_task_is_saved_with_expected_fields(self):
        response = self.harness.post_feedback(_accept_payload())
        self.assertEqual(response.status_code, 201, response.get_json())

        rows = self.harness.events()
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual(row["task_id"], 1, row)
        self.assertEqual(row["event_type"], "accept_task", row)
        self.assertEqual(row["planned_minutes"], 25, row)
        self.assertEqual(row["completion_status"], "accepted", row)
        self.assertEqual(row["reason_category"], "other", row)
        self.assertEqual(row["reason_detail"], DEFAULT_REASON, row)

        note = json.loads(row["note"])
        self.assertEqual(note["schema_version"], 1, note)
        self.assertEqual(note["session_id"], 7, note)
        self.assertEqual(note["activity"], "看纪录片", note)

    def test_both_legal_durations_are_accepted(self):
        for minutes in LEGAL_FREE_MINUTES:
            with self.subTest(minutes=minutes):
                response = self.harness.post_feedback(
                    _accept_payload(planned_minutes=minutes)
                )
                self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), len(LEGAL_FREE_MINUTES), rows)
        self.assertEqual(
            sorted(r["planned_minutes"] for r in rows),
            sorted(LEGAL_FREE_MINUTES),
            rows,
        )

    def test_blank_reason_is_normalised_to_default(self):
        response = self.harness.post_feedback(_accept_payload(reason_detail="   "))
        self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["reason_detail"], DEFAULT_REASON, rows[0])

    def test_missing_reason_is_normalised_to_default(self):
        payload = _accept_payload()
        payload.pop("reason_detail")
        response = self.harness.post_feedback(payload)
        self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(rows[0]["reason_detail"], DEFAULT_REASON, rows[0])

    def test_activity_is_trimmed_in_note(self):
        response = self.harness.post_feedback(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": 1, "session_id": 7, "activity": "  看纪录片  "},
                    ensure_ascii=False,
                )
            )
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        note = json.loads(self.harness.events()[0]["note"])
        self.assertEqual(note["activity"], "看纪录片", note)

    # --- 非法路径（全部 400 + 零写入） -----------------------------------
    def _assert_rejected(self, payload, *, label):
        before = self.harness.event_count()
        response = self.harness.post_feedback(payload)
        body = response.get_json() or {}
        self.assertEqual(
            response.status_code, 400, f"{label}: expected 400, got {response.status_code} {body}"
        )
        self.assertIn("error", body, f"{label}: a clear error message is required")
        self.assertEqual(
            self.harness.event_count(),
            before,
            f"{label}: a rejected event must NOT be written",
        )

    def test_empty_activity_is_rejected(self):
        self._assert_rejected(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": 1, "session_id": 7, "activity": "   "},
                    ensure_ascii=False,
                )
            ),
            label="empty activity",
        )

    def test_missing_activity_is_rejected(self):
        self._assert_rejected(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": 1, "session_id": 7}, ensure_ascii=False
                )
            ),
            label="missing activity",
        )

    def test_activity_over_200_chars_is_rejected(self):
        self._assert_rejected(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": 1, "session_id": 7, "activity": "x" * 201},
                    ensure_ascii=False,
                )
            ),
            label="over-long activity",
        )

    def test_activity_with_control_chars_is_rejected(self):
        self._assert_rejected(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": 1, "session_id": 7, "activity": "看纪录片\x07"},
                    ensure_ascii=False,
                )
            ),
            label="control chars in activity",
        )

    def test_invalid_session_ids_are_rejected(self):
        for bad in (0, -1, "7", 7.5, True, None):
            with self.subTest(session_id=bad):
                self._assert_rejected(
                    _accept_payload(
                        note=json.dumps(
                            {"schema_version": 1, "session_id": bad, "activity": "看纪录片"},
                            ensure_ascii=False,
                        )
                    ),
                    label=f"session_id={bad!r}",
                )

    def test_invalid_durations_are_rejected(self):
        for bad in (30, 0, -25, "25", 25.0, True, None, 55.5):
            with self.subTest(planned_minutes=bad):
                self._assert_rejected(
                    _accept_payload(planned_minutes=bad),
                    label=f"planned_minutes={bad!r}",
                )

    def test_bad_json_note_is_rejected(self):
        self._assert_rejected(_accept_payload(note="{not json"), label="bad json note")

    def test_non_object_note_is_rejected(self):
        for bad in ("[]", '"text"', "123", "null"):
            with self.subTest(note=bad):
                self._assert_rejected(_accept_payload(note=bad), label=f"note={bad}")

    def test_missing_note_is_rejected(self):
        payload = _accept_payload()
        payload.pop("note")
        self._assert_rejected(payload, label="missing note")

    def test_wrong_schema_version_is_rejected(self):
        self._assert_rejected(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": 2, "session_id": 7, "activity": "看纪录片"},
                    ensure_ascii=False,
                )
            ),
            label="schema_version=2",
        )

    def test_boolean_schema_version_is_rejected(self):
        """``True == 1`` in Python — schema_version must be a strict int."""
        self._assert_rejected(
            _accept_payload(
                note=json.dumps(
                    {"schema_version": True, "session_id": 7, "activity": "看纪录片"},
                    ensure_ascii=False,
                )
            ),
            label="schema_version=True",
        )

    def test_wrong_completion_status_is_rejected(self):
        self._assert_rejected(
            _accept_payload(completion_status="completed"), label="bad status"
        )

    def test_wrong_reason_category_is_rejected(self):
        self._assert_rejected(
            _accept_payload(reason_category="not_a_category"), label="bad category"
        )

    # --- reason_category 严格语义（M02-S02-G01-W11）----------------------
    def test_state_issue_reason_category_is_rejected_for_accept_task(self):
        """``state_issue`` 是全局合法类别，但对 accept_task 必须 400 + 零写入。"""
        self.assertIn("state_issue", feedback_service.TASK_FEEDBACK_REASON_CATEGORIES)
        self._assert_rejected(
            _accept_payload(reason_category="state_issue"), label="state_issue"
        )

    def test_external_interrupt_reason_category_is_rejected_for_accept_task(self):
        """``external_interrupt`` 是全局合法类别，但对 accept_task 必须 400 + 零写入。"""
        self.assertIn(
            "external_interrupt", feedback_service.TASK_FEEDBACK_REASON_CATEGORIES
        )
        self._assert_rejected(
            _accept_payload(reason_category="external_interrupt"),
            label="external_interrupt",
        )

    def test_every_non_other_reason_category_is_rejected_for_accept_task(self):
        """除 'other' 外的每个全局合法类别都必须被明确拒绝且零写入。"""
        for category in sorted(feedback_service.TASK_FEEDBACK_REASON_CATEGORIES):
            if category == "other":
                continue
            with self.subTest(reason_category=category):
                self._assert_rejected(
                    _accept_payload(reason_category=category), label=category
                )

    def test_other_reason_category_is_still_accepted(self):
        """``other`` 仍然是 accept_task 的唯一合法类别 → 201 + 1 行写入。"""
        response = self.harness.post_feedback(_accept_payload(reason_category="other"))
        self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["reason_category"], "other", rows[0])

    def test_missing_reason_category_is_rejected_for_accept_task(self):
        payload = _accept_payload()
        payload.pop("reason_category")
        self._assert_rejected(payload, label="missing reason_category")

    def test_other_event_types_keep_accepting_state_issue(self):
        """其它 5 类事件的 reason_category 语义 **逐字不变**。"""
        for event_type in sorted(feedback_service.TASK_FEEDBACK_EVENT_TYPES):
            if event_type == "accept_task":
                continue
            with self.subTest(event_type=event_type):
                response = self.harness.post_feedback(
                    {
                        "task_id": 1,
                        "event_type": event_type,
                        "planned_minutes": 30,
                        "actual_minutes": 25,
                        "completion_status": "completed",
                        "reason_category": "state_issue",
                        "reason_detail": "随便",
                        "note": "原有 note 语义保持不变",
                    }
                )
                self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), 5, rows)
        for row in rows:
            self.assertEqual(row["reason_category"], "state_issue", row)

    # --- 既有事件类型逐字不变 -------------------------------------------
    def test_existing_event_types_still_pass(self):
        for event_type in sorted(feedback_service.TASK_FEEDBACK_EVENT_TYPES):
            if event_type == "accept_task":
                continue
            with self.subTest(event_type=event_type):
                response = self.harness.post_feedback(
                    {
                        "task_id": 1,
                        "event_type": event_type,
                        "planned_minutes": 30,
                        "actual_minutes": 25,
                        "completion_status": "completed",
                        "reason_category": "other",
                        "reason_detail": "随便",
                        "note": "原有 note 语义保持不变",
                    }
                )
                self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), 5, rows)
        # 其它事件的 note **不被** 改写成 JSON。
        for row in rows:
            self.assertEqual(row["note"], "原有 note 语义保持不变", row)
            self.assertEqual(row["planned_minutes"], 30, row)

    def test_accept_task_is_registered_in_event_types(self):
        self.assertIn("accept_task", feedback_service.TASK_FEEDBACK_EVENT_TYPES)
        for legacy in (
            "skip_task",
            "finish_early",
            "finish_on_time",
            "timer_timeout_unfinished",
            "abandon_task",
        ):
            self.assertIn(legacy, feedback_service.TASK_FEEDBACK_EVENT_TYPES)

    # --- 隔离性 ---------------------------------------------------------
    def test_synthetic_state_stays_inside_temp_root(self):
        self.assertTrue(
            str(self.harness.db_path.resolve()).startswith(
                str(Path(self._tmp.name).resolve())
            )
        )
        self.assertNotIn("task_publisher.db", str(self.harness.db_path))


# ===========================================================================
# B. 前端契约（Node 合成 DOM 沙箱）
# ===========================================================================

_HARNESS_TEMPLATE = r"""
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';

const APP_JS = fs.readFileSync(process.env.SAL_APP_JS, 'utf8')
  .split('// ============ 启动加载 ============')[0];

// ESM 模块的真实磁盘根：app.js 用 '/static/...' 形式动态 import，
// 这里把它映射回 <project>/static/...。
const STATIC_ROOT = process.env.SAL_STATIC_ROOT;

// ---------------------------------------------------------------- DOM mock
class FakeClassList {
  constructor(node) { this.node = node; this.set = new Set(); }
  add(...names) { names.forEach((n) => this.set.add(n)); }
  remove(...names) { names.forEach((n) => this.set.delete(n)); }
  contains(n) { return this.set.has(n); }
  toggle(n, on) { if (on === undefined) { this.set.has(n) ? this.set.delete(n) : this.set.add(n); } else if (on) { this.set.add(n); } else { this.set.delete(n); } }
}

class FakeElement {
  constructor(tag, doc) {
    this.tagName = String(tag || 'div').toUpperCase();
    this.ownerDocument = doc;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.style = { setProperty() {}, cssText: '', width: '' };
    this.classList = new FakeClassList(this);
    this._innerHTML = '';
    this._ownText = '';
    this.value = '';
    this.options = [];
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this._listeners = {};
  }
  get textContent() {
    let out = this._ownText || '';
    for (const child of this.children) out += child.textContent;
    return out;
  }
  set textContent(v) {
    this._ownText = String(v == null ? '' : v);
    this._dropRegisteredIds(this.children);
    this.children = [];
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(v) {
    this._innerHTML = String(v);
    this._dropRegisteredIds(this.children);
    this.children = [];
    this._ownText = '';
    this._rebuildFromHtml(this._innerHTML);
  }
  // Removing a subtree must also drop its ids from the document registry,
  // otherwise getElementById() would keep returning detached elements.
  _dropRegisteredIds(nodes) {
    const doc = this.ownerDocument;
    if (!doc || !doc.byId) return;
    const walk = (node) => {
      const id = node.getAttribute && node.getAttribute('id');
      if (id && doc.byId.get(id) === node) doc.byId.delete(id);
      for (const child of (node.children || [])) walk(child);
    };
    for (const node of (nodes || [])) walk(node);
  }
  _rebuildFromHtml(html) {
    const stack = [this];
    const re = /<\/?([a-zA-Z][a-zA-Z0-9]*)([^>]*)>|([^<]+)/g;
    let m;
    while ((m = re.exec(html)) !== null) {
      const [full, tag, attrs, text] = m;
      if (text !== undefined) {
        const t = text.trim();
        if (t) stack[stack.length - 1]._ownText += t;
        continue;
      }
      const closing = full.startsWith('</');
      const name = String(tag || '').toLowerCase();
      if (closing) {
        if (stack.length > 1) stack.pop();
        continue;
      }
      const node = new FakeElement(name, this.ownerDocument);
      const idMatch = /id=["']([^"']+)["']/.exec(attrs || '');
      if (idMatch) node.setAttribute('id', idMatch[1]);
      const forMatch = /for=["']([^"']+)["']/.exec(attrs || '');
      if (forMatch) node.setAttribute('for', forMatch[1]);
      const clsMatch = /class=["']([^"']+)["']/.exec(attrs || '');
      if (clsMatch) node.className = clsMatch[1];
      const valueMatch = /value=["']([^"']*)["']/.exec(attrs || '');
      if (valueMatch) node.value = valueMatch[1];
      const parent = stack[stack.length - 1];
      parent.appendChild(node);
      if (!/^(input|img|br|hr|meta|link)$/.test(name)) stack.push(node);
    }
  }
  get className() { return this.attributes['class'] || ''; }
  set className(v) { this.attributes['class'] = String(v); }
  get id() { return this.attributes['id'] || ''; }
  set id(v) { this.attributes['id'] = String(v); }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === 'id') this._id = String(v);
    if (k.startsWith('data-')) this.dataset[k.slice(5)] = String(v);
  }
  getAttribute(k) {
    if (k === 'id') return this.attributes['id'] || null;
    return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null;
  }
  removeAttribute(k) { delete this.attributes[k]; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k); }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  removeChild(child) {
    const i = this.children.indexOf(child);
    if (i >= 0) this.children.splice(i, 1);
    child.parentNode = null;
    return child;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); }
  removeEventListener() {}
  dispatchEvent() { return true; }
  click() {
    const fns = this._listeners['click'] || [];
    fns.forEach((fn) => fn({ target: this, preventDefault() {}, stopImmediatePropagation() {} }));
  }
  focus() {}
  setSelectionRange() {}
  querySelector(sel) {
    const all = this.querySelectorAll(sel);
    return all.length ? all[0] : null;
  }
  querySelectorAll(sel) {
    const match = compileSelector(sel);
    const out = [];
    const walk = (node) => {
      for (const child of node.children) {
        if (match(child)) out.push(child);
        walk(child);
      }
    };
    walk(this);
    return out;
  }
  getBoundingClientRect() { return { top: 0, left: 0, width: 0, height: 0, right: 0, bottom: 0 }; }
  scrollIntoView() {}
  getContext() { return null; }
  closest() { return null; }
  contains() { return false; }
}

// Serialize a DOM subtree into HTML (attributes + text), so tests can assert
// that user input never lands in markup.
function serialize(node) {
  let out = '<' + String(node.tagName || 'div').toLowerCase();
  for (const [k, v] of Object.entries(node.attributes || {})) {
    out += ' ' + k + '="' + String(v).replace(/"/g, '&quot;') + '"';
  }
  out += '>';
  if (node._innerHTML && !node.children.length) {
    // The subtree came from parsed HTML: keep the original markup verbatim.
    return out + node._innerHTML + '</' + String(node.tagName || 'div').toLowerCase() + '>';
  }
  out += (node._ownText || '');
  for (const child of node.children) out += serialize(child);
  out += '</' + String(node.tagName || 'div').toLowerCase() + '>';
  return out;
}

// Compile a CSS-ish selector (tag / .class / #id / [attr] / [attr="value"])
// into a matcher function. Only the subset used by static/app.js is supported.
function compileSelector(sel) {
  const s = String(sel).trim();
  const parts = s.split(/(?=[.#[])/).map((p) => p.trim()).filter(Boolean);
  const checks = [];
  for (const part of parts) {
    if (part.startsWith('.')) {
      const cls = part.slice(1);
      checks.push((el) => String(el.className || '').split(/\s+/).includes(cls));
    } else if (part.startsWith('#')) {
      const id = part.slice(1);
      checks.push((el) => el.getAttribute('id') === id);
    } else if (part.startsWith('[')) {
      const m = /^\[([^\]=]+)(?:=["']?([^\]"']*)["']?)?\]$/.exec(part);
      if (m) {
        const attr = m[1];
        const val = m[2];
        checks.push((el) => {
          const got = el.getAttribute(attr);
          if (val === undefined) return got !== null;
          return got === val;
        });
      }
    } else {
      const tag = part.toLowerCase();
      checks.push((el) => String(el.tagName || '').toLowerCase() === tag);
    }
  }
  if (!checks.length) return () => false;
  return (el) => checks.every((c) => c(el));
}

class FakeDocument {
  constructor() {
    this.byId = new Map();
    this.documentElement = new FakeElement('html', this);
    this.documentElement.style = { setProperty() {}, cssText: '' };
    this.body = new FakeElement('body', this);
    this.head = new FakeElement('head', this);
  }
  _mk(id, tag) {
    const el = new FakeElement(tag || 'div', this);
    el.setAttribute('id', id);
    this.byId.set(id, el);
    return el;
  }
  getElementById(id) {
    // Only real, registered elements are returned (a missing id → null).
    return this.byId.get(id) || null;
  }
  createElement(tag) {
    const el = new FakeElement(tag, this);
    const self = this;
    const origSetAttribute = el.setAttribute.bind(el);
    el.setAttribute = function (k, v) {
      origSetAttribute(k, v);
      if (k === 'id') self.byId.set(String(v), el);
    };
    return el;
  }
  createTextNode(t) { const n = new FakeElement('#text', this); n.textContent = String(t); return n; }
  querySelector(sel) {
    const all = this.querySelectorAll(sel);
    return all.length ? all[0] : null;
  }
  querySelectorAll(sel) {
    const match = compileSelector(sel);
    const out = [];
    const seen = new Set();
    // Registered elements (the ids declared in src/index.html) act as the
    // document's roots, so elements appended into them are reachable.
    const roots = [];
    for (const el of this.byId.values()) roots.push(el);
    roots.push(this.documentElement, this.body, this.head);
    for (const root of roots) {
      if (!root) continue;
      const walk = (node) => {
        for (const child of node.children) {
          if (match(child) && !seen.has(child)) { seen.add(child); out.push(child); }
          walk(child);
        }
      };
      walk(root);
    }
    return out;
  }
  addEventListener() {}
  removeEventListener() {}
}

function makeDom() {
  const doc = new FakeDocument();
  const html = fs.readFileSync(process.env.SAL_INDEX_HTML, 'utf8');
  const seen = new Set();
  const re = /\bid="([^"]+)"/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (!seen.has(m[1])) { seen.add(m[1]); doc._mk(m[1]); }
  }
  return doc;
}

// ---------------------------------------------------------------- fetch stub
const calls = [];
const confirmCalls = [];        // 记录 app 打开过的每一个 confirm() 对话框
const fetchResponses = new Map(); // url -> {ok, status, body}
function installFetchStub(ctx) {
  ctx.fetch = function (url, opts) {
    const method = (opts && opts.method) || 'GET';
    const rec = { url: String(url), method: String(method).toUpperCase(), body: null, responseOk: true };
    if (opts && typeof opts.body === 'string') {
      try { rec.body = JSON.parse(opts.body); } catch (e) { rec.body = opts.body; }
    }
    calls.push(rec);
    const key = String(url);
    const scripted = fetchResponses.get(key);
    if (scripted) {
      rec.responseOk = !!scripted.ok;
      return Promise.resolve({
        ok: scripted.ok,
        status: scripted.status,
        json: function () { return Promise.resolve(scripted.body); }
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({}); } });
  };
}

// ---------------------------------------------------------------- bootstrap
const dom = makeDom();
const intervalCalls = [];
const sandbox = {
  window: null,
  document: dom,
  console: console,
  fetch: null,
  // 注意：句柄必须是 **真值**（旧 stub 返回 0）。ESM timer owner 用
  // `if (inlineTickHandle)` 判断"内嵌计时是否在跑"，返回 0 会让
  // owner.hasInlineTimer() 永远为 false。
  setInterval: function (fn, ms) { intervalCalls.push(ms); return intervalCalls.length; },
  clearInterval: function () {},
  setTimeout: function () { return 0; },
  clearTimeout: function () {},
  requestAnimationFrame: function (fn) { if (typeof fn === 'function') fn(); return 0; },
  localStorage: { getItem: function () { return null; }, setItem: function () {} },
  navigator: { clipboard: null },
  confirmCalls: confirmCalls,
  // confirm() 在真实浏览器里是同步阻塞对话框；这里记录调用并默认同意，
  // 让 "旧的提前结束确认" 路径可被断言。
  confirm: function (msg) { confirmCalls.push(String(msg)); return true; },
  Promise: Promise,
  JSON: JSON,
  Math: Math,
  Date: Date,
  Object: Object,
  Array: Array,
  String: String,
  Number: Number,
  Boolean: Boolean,
  Error: Error,
  parseInt: parseInt,
  parseFloat: parseFloat,
  isFinite: isFinite,
  isNaN: isNaN,
  encodeURIComponent: encodeURIComponent,
  decodeURIComponent: decodeURIComponent,
  RegExp: RegExp,
  Map: Map,
  Set: Set,
  Symbol: Symbol,
  Proxy: Proxy,
  Reflect: Reflect
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.onerror = function () { return false; };
installFetchStub(sandbox);

const ctx = vm.createContext(sandbox);

// ---------------------------------------------------------------- ESM loader
// app.js 通过 `import('/static/modules/timer/index.js')` 动态加载 **真实生产**
// ESM timer owner。为了让 owner 与 app.js 运行在 **同一个** vm context
// （因此共享同一份 synthetic document 与同一套 timer stub），这里用
// vm.SourceTextModule 把磁盘上的 ESM 模块加载进 ctx，而不是用宿主 realm 的
// 原生 import()——那会让 owner 看到宿主全局 document，而不是合成 DOM。
// 需要 node --experimental-vm-modules（vm.Module 系列 API 仍是 experimental）。
const moduleCache = new Map();

// **同步** linker：Node 的 link() 会自己处理整个依赖图，所以回调必须直接
// 返回 Module 实例（返回 Promise 会破坏 link 的同步契约）。
function esmLinker(specifier, referencingModule) {
  const base = path.dirname(fileURLToPath(referencingModule.identifier));
  return createEsmModule(path.resolve(base, specifier));
}

function createEsmModule(absPath) {
  if (moduleCache.has(absPath)) return moduleCache.get(absPath);
  const src = fs.readFileSync(absPath, 'utf8');
  const mod = new vm.SourceTextModule(src, {
    context: ctx,
    identifier: pathToFileURL(absPath).href
  });
  moduleCache.set(absPath, mod);
  return mod;
}

async function evaluateEsmModule(mod) {
  if (mod.status === 'unlinked') await mod.link(esmLinker);
  if (mod.status === 'linked') await mod.evaluate();
  return mod;
}

async function importModuleDynamically(specifier) {
  const spec = String(specifier);
  const prefix = '/static/';
  if (spec.indexOf(prefix) !== 0) {
    throw new Error('unsupported dynamic import specifier: ' + spec);
  }
  const abs = path.join(STATIC_ROOT, spec.slice(prefix.length));
  return evaluateEsmModule(createEsmModule(abs));
}

if (typeof vm.SourceTextModule !== 'function') {
  throw new Error('vm.SourceTextModule is unavailable: node needs --experimental-vm-modules');
}

vm.runInContext(APP_JS, ctx, {
  filename: 'app.js',
  importModuleDynamically: importModuleDynamically
});

const app = sandbox;
const results = { ok: true };
sandbox.serialize = serialize;

// ------------------------------------------------- ESM timer owner 公共快照
// AR03-G08：计时状态 **唯一** 归 ESM timer owner 所有；app.js 侧不再保留任何
// legacy 镜像全局（timerDockSession / timerActiveSession / timerDockPaused /
// timerDockPausedElapsed / _inlineTimerHandle）。
//
// 这里通过 app.js 的薄 facade（_timerSnapshot / _timerOwner）读取 owner 的
// **真实公开快照**（getSnapshot / hasInlineTimer），以此替代已删除的镜像断言。
// 读取的是 owner 闭包内的真实状态，不是测试自己伪造的状态。
function timerState() {
  const snap = (typeof app._timerSnapshot === 'function')
    ? app._timerSnapshot()
    : null;
  const owner = app._timerOwner || null;
  return {
    session: (snap && snap.session) ? snap.session : null,
    paused: !!(snap && snap.paused),
    pausedElapsedMs: (snap && snap.pausedElapsedMs) ? snap.pausedElapsedMs : 0,
    hasInlineTimer: owner ? !!owner.hasInlineTimer() : false,
    ownerReady: !!owner
  };
}

// 被 G08 有意移除的 legacy 镜像全局：必须 **全部不存在**。
function legacyTimerMirrors() {
  return {
    timerDockSession: 'timerDockSession' in app,
    timerActiveSession: 'timerActiveSession' in app,
    timerDockPaused: 'timerDockPaused' in app,
    timerDockPausedElapsed: 'timerDockPausedElapsed' in app,
    inlineTimerHandle: '_inlineTimerHandle' in app
  };
}

const SNIPPET = process.env.SAL_SNIPPET;
(async () => {
  try {
    const fn = new Function('app', 'dom', 'calls', 'results', 'fetchResponses',
      'intervalCalls', 'confirmCalls', 'timerState', 'legacyTimerMirrors',
      'return (async () => {' + SNIPPET + '})();');
    await fn(app, dom, calls, results, fetchResponses, intervalCalls, confirmCalls,
      timerState, legacyTimerMirrors);
  } catch (err) {
    results.ok = false;
    results.error = String((err && err.stack) || err);
  }
  process.stdout.write(JSON.stringify(results) + '\n');
})();
"""


class _SandboxRunner:
    """Load ``static/app.js`` into a Node VM with a synthetic DOM."""

    def __init__(self, tmp_root: Path):
        self.tmp_root = tmp_root
        self.node_script = tmp_root / "sandbox.mjs"
        self._counter = 0

    def available(self) -> bool:
        return shutil.which("node") is not None

    def run(self, snippet: str, *, timeout: int = 120) -> dict:
        self._counter += 1
        self.node_script.write_text(_HARNESS_TEMPLATE, encoding="utf-8")
        env = dict(os.environ)
        env["SAL_APP_JS"] = str(APP_JS)
        env["SAL_INDEX_HTML"] = str(INDEX_HTML)
        env["SAL_STATIC_ROOT"] = str(SOURCE_ROOT / "static")
        env["SAL_SNIPPET"] = snippet
        env["NODE_OPTIONS"] = ""
        # ESM timer owner 必须用 vm.SourceTextModule 加载进 **同一个** vm
        # context，因此 Node 需要 --experimental-vm-modules。
        node_args = [
            "--experimental-vm-modules",
            "--no-warnings",
            str(self.node_script),
        ]
        try:
            proc = subprocess.run(
                [shutil.which("node"), *node_args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(self.tmp_root),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "sandbox timeout"}
        out = (proc.stdout or "").strip()
        if not out:
            return {
                "ok": False,
                "error": "no sandbox output",
                "stderr": (proc.stderr or "")[-4000:],
            }
        try:
            return json.loads(out.splitlines()[-1])
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "sandbox output is not JSON",
                "stdout": out[-4000:],
                "stderr": (proc.stderr or "")[-2000:],
            }


class _SandboxCase(unittest.TestCase):
    """Base class providing the Node sandbox fixture."""

    #: 挂载一张已抽出的自由卡到 DOM（与 ``renderDrawnCard`` 的真实路径一致）。
    _MOUNT = """
        const task = %s;
        app._currentDrawnTask = task;
        app.allTasks = [task];
        app.gachaState = app.gachaState || {};
        app.gachaState.canReplace = false;
        const stage = app.renderDrawnCard(task, 0);
        const result = dom.getElementById('gachaResult');
        result.innerHTML = '';
        result.appendChild(stage);
        app._testCard = result.querySelector('.task-card.drawn-card');
        results.cardHtml = app._testCard ? app._testCard.innerHTML : '';
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(
            prefix="lt_fc_fe_", ignore_cleanup_errors=True
        )
        cls.tmp_root = Path(cls._tmp.name)
        cls.runner = _SandboxRunner(cls.tmp_root)
        if not cls.runner.available():
            raise unittest.SkipTest("node is not available on PATH")

    @classmethod
    def tearDownClass(cls):
        try:
            cls._tmp.cleanup()
        except Exception:
            pass

    def sandbox(self, snippet: str) -> dict:
        self.assertTrue(self.runner.available(), "node must be available")
        result = self.runner.run(snippet)
        self.assertTrue(
            result.get("ok"),
            "sandbox snippet failed: " + json.dumps(result, ensure_ascii=False)[:4000],
        )
        return result

    def _free_task(self, **overrides):
        task = {
            "id": 42,
            "name": "自由卡",
            "description": "自由卡描述",
            "category": "study",
            "priority": 5,
            "estimated_time": 80,
            "repeat_type": "none",
            "tags": [],
            "task_type": "free",
            "is_unlocked": 1,
            "effective_minutes": 25,
            "free_card_dispatchable": True,
        }
        task.update(overrides)
        return task

    def _mount_snippet(self, task: dict) -> str:
        return self._MOUNT % json.dumps(task, ensure_ascii=False)


# ---------------------------------------------------------------------------
# B0. 夹具自检（AR03-G08-W04）：ESM timer owner 真的被加载了吗？
# ---------------------------------------------------------------------------
class TimerOwnerEsmHarnessTests(_SandboxCase):
    """证明 harness **真的** 把生产 ESM timer owner 加载进了同一执行环境。

    这是一道 **防空洞** 闸门：如果 ESM loader 失效（例如 Node 缺少
    ``--experimental-vm-modules``，或 dynamic import 未被拦截），owner 永远
    不会被创建，下面所有针对 owner 快照的断言都会 **空洞地** 通过。
    """

    def test_the_production_esm_timer_owner_is_actually_loaded(self):
        """owner 必须来自 ``static/modules/timer/index.js`` 且暴露真实 API。"""
        result = self.sandbox(
            """
            // owner 是 **惰性** 加载的（app.js 的薄 facade 只在第一次需要时
            // import）；这里显式触发一次，验证 ESM import 真的成功。
            await app._getTimerOwner();
            results.ownerReady = !!app._timerOwner;
            results.ownerApiKeys = app._timerOwner
              ? Object.keys(app._timerOwner).sort() : null;
            """
        )
        self.assertTrue(
            result["ownerReady"],
            "the production ESM timer owner must be loaded by the harness",
        )
        self.assertIsInstance(result["ownerApiKeys"], list)
        # owner 的公开 API 面（来自 static/modules/timer/index.js 的返回值）。
        for api in (
            "getSnapshot",
            "startSession",
            "pauseSession",
            "resumeSession",
            "completeSession",
            "clear",
            "getActualMinutes",
            "hasInlineTimer",
            "startInlineTimer",
            "stopInlineTimer",
        ):
            self.assertIn(api, result["ownerApiKeys"], result["ownerApiKeys"])

    def test_the_removed_legacy_timer_mirrors_do_not_exist(self):
        """G08 有意移除的 legacy 镜像全局必须 **全部不存在**。"""
        result = self.sandbox(
            """
            results.legacyMirrors = legacyTimerMirrors();
            """
        )
        self.assertEqual(
            result["legacyMirrors"],
            {
                "timerDockSession": False,
                "timerActiveSession": False,
                "timerDockPaused": False,
                "timerDockPausedElapsed": False,
                "inlineTimerHandle": False,
            },
            "the legacy timer mirrors removed by AR03-G08 must stay removed",
        )

    def test_the_esm_owner_and_app_js_share_the_same_synthetic_dom(self):
        """owner 的 ESM presentation 层必须写进 app.js 的 **同一份** DOM。

        如果 owner 运行在另一个 realm / 另一份 document 上，Dock 的时间与
        任务名就永远是空的 —— 这里直接断言真实 DOM 写入。
        """
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
              session_id: 991, task_id: 42,
              started_at: new Date(Date.now() - 600000).toISOString(),
              planned_minutes: 25
            }});
            await app.startTask(42);
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            activity.value = '看纪录片';
            await app.submitFreeCardAccept(42);
            results.dockTime = (dom.getElementById('timerDockTime') || {}).textContent;
            results.dockTaskName = (dom.getElementById('timerDockTaskName') || {}).textContent;
            results.dockIdleHidden = dom.getElementById('timerDockIdle')
              .classList.contains('hidden');
            results.dockActiveHidden = dom.getElementById('timerDockActive')
              .classList.contains('hidden');
            """
        )
        self.assertEqual(result["dockTime"], "10:00", result)
        self.assertEqual(result["dockTaskName"], "看纪录片", result)
        self.assertTrue(result["dockIdleHidden"], result)
        self.assertFalse(result["dockActiveHidden"], result)


# ---------------------------------------------------------------------------
# B1. 静态源码合同（不执行）
# ---------------------------------------------------------------------------
class FreeCardAcceptSourceContractTests(unittest.TestCase):
    """``static/app.js`` 的静态形状检查。"""

    @classmethod
    def setUpClass(cls):
        cls.js = APP_JS.read_text(encoding="utf-8")

    def test_accept_task_is_a_known_feedback_event_type(self):
        """``accept_task`` 必须是服务端已知事件类型。"""
        self.assertIn("accept_task", feedback_service.TASK_FEEDBACK_EVENT_TYPES)

    def test_free_card_primary_action_is_accept_label(self):
        self.assertIn("接受自由卡", self.js)

    def test_free_card_form_uses_dom_value_not_inline_js(self):
        """活动 / 理由必须通过 DOM value 读取，不拼进 inline JS。"""
        self.assertIn(".value", self.js)
        # 用户输入绝不进入 onclick / innerHTML 字符串拼接。
        self.assertNotIn("onclick=\"submitFreeCardAccept(' +", self.js)
        self.assertNotIn("onclick=\"openFreeCardAcceptForm(' +", self.js)

    def test_free_card_reminder_text_is_present(self):
        self.assertIn(
            "开始后请同时为手机手动设置计时器；网页计时不应替代手机提醒。",
            self.js,
        )

    def test_free_card_default_reason_is_exact(self):
        self.assertIn(
            "var FREE_CARD_DEFAULT_REASON = '没有什么理由，我就是想。';",
            self.js,
        )

    def test_free_card_never_falls_back_to_estimated_time(self):
        """自由卡时长绝不来自 estimated_time。"""
        body = self._function_body("resolveFreeCardMinutes")
        self.assertTrue(body, "resolveFreeCardMinutes must exist")
        self.assertIn("effective_minutes", body)
        self.assertNotIn("estimated_time", body)
        self.assertIn("free_card_dispatchable", body)

    def _function_body(self, name: str) -> str:
        m = re.search(
            r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
            self.js,
        )
        if not m:
            return ""
        start = m.end() - 1
        depth = 0
        for i in range(start, len(self.js)):
            ch = self.js[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return self.js[start:i + 1]
        return self.js[start:]


# ---------------------------------------------------------------------------
# B2. 行为合同（Node 沙箱执行真实的 static/app.js）
# ---------------------------------------------------------------------------
class FreeCardAcceptBehaviourTests(_SandboxCase):
    """自由卡接受表单的交互行为。"""

    def test_free_card_card_face_shows_effective_minutes_not_inline_estimate(self):
        task = self._free_task()
        result = self.sandbox(self._MOUNT % json.dumps(task, ensure_ascii=False))
        html = result["cardHtml"]
        self.assertIn("自由卡", html)
        self.assertIn("25分", html)
        self.assertNotIn("80分", html)

    def test_free_card_primary_button_is_accept_free_card(self):
        task = self._free_task()
        result = self.sandbox(self._MOUNT % json.dumps(task, ensure_ascii=False))
        html = result["cardHtml"]
        self.assertIn("接受自由卡", html)
        self.assertNotIn(">开始任务<", html)

    def test_opening_accept_form_shows_activity_and_reason_fields(self):
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            await app.startTask(42);
            const panel = app._testCard.querySelector('.drawn-card-right-panel');
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            const reason = dom.getElementById('freeCardAcceptForm_42_reason');
            results.hasActivity = !!activity;
            results.hasReason = !!reason;
            results.defaultReason = reason ? reason.value : null;
            results.reminder = panel ? panel.textContent : '';
            results.activityLabel = panel ? panel.textContent : '';
            """
        )
        self.assertTrue(result["hasActivity"], "the accept form must contain an activity input")
        self.assertTrue(result["hasReason"], "the accept form must contain a reason input")
        self.assertEqual(
            result["defaultReason"],
            DEFAULT_REASON,
            "the reason input must default to the exact product default text",
        )
        self.assertIn("请同时为手机手动设置计时器", result["reminder"])

    def test_empty_activity_does_not_start_timer(self):
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            await app.startTask(42);
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            activity.value = '   ';
            await app.submitFreeCardAccept(42);
            results.posts = calls.filter((c) => c.method === 'POST').map((c) => c.url);
            """
        )
        self.assertEqual(
            result["posts"], [], "an empty activity must NOT start a timer or write feedback"
        )

    def test_valid_activity_starts_timer_with_effective_minutes_and_writes_accept_event(self):
        task = self._free_task(effective_minutes=55)
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
              session_id: 991, task_id: 42, started_at: '2026-10-25T00:00:00',
              planned_minutes: 55
            }});
            await app.startTask(42);
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            activity.value = '看纪录片';
            await app.submitFreeCardAccept(42);
            results.posts = calls.filter((c) => c.method === 'POST');
            results.timerBody = (results.posts.find((c) => c.url === '/api/timer/start') || {}).body;
            results.fbBody = (results.posts.find((c) => c.url === '/api/task-feedback') || {}).body;
            results.panelText = app._testCard.querySelector('.drawn-card-right-panel').textContent;
            """
        )
        timer_body = result["timerBody"]
        self.assertIsNotNone(timer_body, "the free card must call POST /api/timer/start")
        self.assertEqual(timer_body["planned_minutes"], 55, timer_body)
        self.assertEqual(timer_body["task_id"], 42, timer_body)

        fb_body = result["fbBody"]
        self.assertIsNotNone(fb_body, "the free card must write an accept_task feedback event")
        self.assertEqual(fb_body["event_type"], "accept_task", fb_body)
        self.assertEqual(fb_body["planned_minutes"], 55, fb_body)
        self.assertEqual(fb_body["completion_status"], "accepted", fb_body)
        self.assertEqual(fb_body["reason_category"], "other", fb_body)
        self.assertEqual(fb_body["reason_detail"], DEFAULT_REASON, fb_body)
        note = json.loads(fb_body["note"])
        self.assertEqual(note["schema_version"], 1, note)
        self.assertEqual(note["session_id"], 991, note)
        self.assertEqual(note["activity"], "看纪录片", note)

        self.assertIn("看纪录片", result["panelText"], "the running panel must show the activity")
        self.assertIn("请同时为手机手动设置计时器", result["panelText"])

    def test_no_approved_duration_never_starts_timer(self):
        for overrides in (
            {"effective_minutes": None},
            {"effective_minutes": 30},
            {"effective_minutes": 25.0},
            {"free_card_dispatchable": False},
            {"effective_minutes": None, "free_card_dispatchable": False},
        ):
            with self.subTest(overrides=overrides):
                task = self._free_task(**overrides)
                result = self.sandbox(
                    self._MOUNT % json.dumps(task, ensure_ascii=False)
                    + """
                    await app.startTask(42);
                    await app.submitFreeCardAccept(42);
                    results.posts = calls.filter((c) => c.method === 'POST').map((c) => c.url);
                    """
                )
                self.assertEqual(
                    result["posts"],
                    [],
                    "a free card without an approved dispatchable duration must NOT start",
                )

    def test_non_free_cards_keep_the_original_start_task_path(self):
        for task_type in ("standard", "micro", "goal"):
            with self.subTest(task_type=task_type):
                task = {
                    "id": 43,
                    "name": "普通卡",
                    "description": "d",
                    "category": "study",
                    "priority": 5,
                    "estimated_time": 30,
                    "repeat_type": "none",
                    "tags": [],
                    "task_type": task_type,
                    "is_unlocked": 1,
                }
                result = self.sandbox(
                    self._MOUNT % json.dumps(task, ensure_ascii=False)
                    + """
                    fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
                      session_id: 5, task_id: 43, started_at: '2026-10-25T00:00:00',
                      planned_minutes: 30
                    }});
                    await app.startTask(43);
                    results.posts = calls.filter((c) => c.method === 'POST').map((c) => c.url);
                    results.timerBody = (calls.find((c) => c.url === '/api/timer/start') || {}).body;
                    results.hasAcceptForm = !!dom.getElementById('freeCardAcceptForm_43_activity');
                    """
                )
                self.assertIn("/api/timer/start", result["posts"], result["posts"])
                self.assertNotIn(
                    "/api/task-feedback",
                    result["posts"],
                    "a non-free card must not write an accept_task event",
                )
                self.assertEqual(result["timerBody"]["planned_minutes"], 30, result["timerBody"])
                self.assertFalse(
                    result["hasAcceptForm"],
                    "a non-free card must not open the free-card accept form",
                )

    def test_cancel_restores_the_card_actions(self):
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            const before = app._testCard.querySelector('.drawn-card-right-panel').textContent;
            await app.startTask(42);
            const during = app._testCard.querySelector('.drawn-card-right-panel').textContent;
            app.cancelFreeCardAcceptForm(42);
            const after = app._testCard.querySelector('.drawn-card-right-panel').textContent;
            results.before = before;
            results.during = during;
            results.after = after;
            """
        )
        self.assertIn("接受自由卡", result["before"])
        self.assertIn("取消", result["during"])
        self.assertIn("接受自由卡", result["after"])
        self.assertNotIn("取消", result["after"])

    def test_activity_is_not_injected_into_inline_javascript(self):
        hostile = '"><script>alert(1)</script>'
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
              session_id: 12, task_id: 42, started_at: '2026-10-25T00:00:00',
              planned_minutes: 25
            }});
            await app.startTask(42);
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            activity.value = %s;
            await app.submitFreeCardAccept(42);
            const panel = app._testCard.querySelector('.drawn-card-right-panel');
            results.panelHtml = app.serialize(panel);
            results.panelText = panel.textContent;
            """
            % json.dumps(hostile)
        )
        # The hostile activity must never become live markup.
        self.assertNotIn("<script", result["panelHtml"])
        self.assertNotIn("<script", result["panelText"])
        self.assertIn("&lt;script&gt;", result["panelHtml"])


# ---------------------------------------------------------------------------
# B3. timer/start 返回缺失 / 非法 session_id（M02-S02-G01-W11）
# ---------------------------------------------------------------------------
class FreeCardInvalidSessionIdBehaviourTests(_SandboxCase):
    """session_id 缺失 / 非法时，绝不"假装成功"，绝不结束无效计时。"""

    #: 明确的警告文案（必须逐字出现）。
    _WARNING = "无法确认计时已停止，请检查计时状态/必要时手动处理"

    #: 曾经的"成功"措辞（已停止并保留你的填写）——绝不能再出现。
    _FORBIDDEN_STOP_CLAIM = "已停止并保留"

    _SUBMIT = """
        await app.startTask(42);
        const activity = dom.getElementById('freeCardAcceptForm_42_activity');
        activity.value = '看纪录片';
        const reason = dom.getElementById('freeCardAcceptForm_42_reason');
        reason.value = '想放松一下';
        const before = intervalCalls.length;
        await app.submitFreeCardAccept(42);
        results.intervalDelta = intervalCalls.length - before;
        results.posts = calls.filter((c) => c.method === 'POST');
        results.postUrls = results.posts.map((c) => c.url);
        results.completeBodies = results.posts
          .filter((c) => c.url === '/api/timer/complete')
          .map((c) => c.body);
        // AR03-G08：计时状态的唯一真相是 ESM timer owner 的公开快照。
        results.timerState = timerState();
        results.legacyMirrors = legacyTimerMirrors();
        results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
        const panel = app._testCard.querySelector('.drawn-card-right-panel');
        results.panelText = panel ? panel.textContent : '';
        const activityEl = dom.getElementById('freeCardAcceptForm_42_activity');
        const reasonEl = dom.getElementById('freeCardAcceptForm_42_reason');
        results.activityValue = activityEl ? activityEl.value : null;
        results.reasonValue = reasonEl ? reasonEl.value : null;
    """

    def _run_with_timer_body(self, body_obj):
        task = self._free_task()
        body_literal = json.dumps(body_obj, ensure_ascii=False)
        return self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: %s });
            """
            % body_literal
            + self._SUBMIT
        )

    def _assert_fail_closed(self, result, label):
        # 1. 绝不向 /api/timer/complete 发送（更不用说无效 ID）。
        self.assertEqual(
            result["completeBodies"], [], f"{label}: must NOT call /api/timer/complete"
        )
        # 2. 绝不启动内嵌计时器（startInlineTimer 会新增一个 interval）。
        self.assertEqual(
            result["intervalDelta"], 0, f"{label}: must NOT start the inline timer"
        )
        # 3. ESM timer owner 绝 **不** 设置活动 session（fail closed）。
        state = result["timerState"]
        self.assertIsNone(
            state["session"], f"{label}: the timer owner must NOT hold a session"
        )
        self.assertFalse(
            state["hasInlineTimer"],
            f"{label}: the timer owner must NOT hold an inline timer",
        )
        # 4. G08 有意移除的 legacy 镜像全局必须 **全部不存在**。
        for name, present in result["legacyMirrors"].items():
            self.assertFalse(
                present, f"{label}: the removed legacy mirror {name} must not exist"
            )
        # 5. 绝不显示"已停止"这类成功措辞。
        self.assertNotIn(
            self._FORBIDDEN_STOP_CLAIM,
            result["toastText"],
            f"{label}: must not claim the timer was stopped",
        )
        self.assertNotIn(
            self._FORBIDDEN_STOP_CLAIM,
            result["panelText"],
            f"{label}: must not claim the timer was stopped in the card panel",
        )
        # 6. 必须显示明确的"无法确认计时已停止"警告。
        self.assertIn(
            self._WARNING, result["toastText"], f"{label}: a clear warning is required"
        )
        # 7. 活动 / 理由必须保留。
        self.assertEqual(
            result["activityValue"], "看纪录片", f"{label}: the activity must be preserved"
        )
        self.assertEqual(
            result["reasonValue"], "想放松一下", f"{label}: the reason must be preserved"
        )
        # 8. 绝不显示"执行中"状态（计时并未被我们确认启动）。
        self.assertNotIn(
            "执行中", result["panelText"], f"{label}: must not show the running state"
        )

    def test_missing_session_id_is_rejected_fail_closed(self):
        result = self._run_with_timer_body(
            {"task_id": 42, "started_at": "2026-10-25T00:00:00", "planned_minutes": 25}
        )
        self._assert_fail_closed(result, "missing session_id")

    def test_invalid_session_id_values_are_rejected_fail_closed(self):
        for bad in (
            None,
            "",
            "   ",
            True,
            False,
            "abc",
            "12abc",
            "1.5",
            "-3",
            0,
            -5,
            1.5,
            "0",
            {"id": 3},
            [3],
        ):
            with self.subTest(session_id=bad):
                result = self._run_with_timer_body(
                    {
                        "session_id": bad,
                        "task_id": 42,
                        "started_at": "2026-10-25T00:00:00",
                        "planned_minutes": 25,
                    }
                )
                self._assert_fail_closed(result, f"session_id={bad!r}")

    def test_valid_session_id_still_follows_the_original_success_path(self):
        """有效 session_id 的成功路径 **不变**。"""
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
              session_id: 991, task_id: 42, started_at: '2026-10-25T00:00:00',
              planned_minutes: 25
            }});
            await app.startTask(42);
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            activity.value = '看纪录片';
            const before = intervalCalls.length;
            await app.submitFreeCardAccept(42);
            results.intervalDelta = intervalCalls.length - before;
            results.postUrls = calls.filter((c) => c.method === 'POST').map((c) => c.url);
            results.timerState = timerState();
            results.legacyMirrors = legacyTimerMirrors();
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            const panel = app._testCard.querySelector('.drawn-card-right-panel');
            results.panelText = panel ? panel.textContent : '';
            """
        )
        self.assertIn("/api/timer/start", result["postUrls"], result["postUrls"])
        self.assertIn("/api/task-feedback", result["postUrls"], result["postUrls"])
        self.assertNotIn("/api/timer/complete", result["postUrls"], result["postUrls"])
        self.assertEqual(result["intervalDelta"], 1, "the inline timer must start")
        state = result["timerState"]
        self.assertIsNotNone(state["session"], state)
        self.assertEqual(state["session"]["id"], 991, state)
        self.assertTrue(state["hasInlineTimer"], state)
        for name, present in result["legacyMirrors"].items():
            self.assertFalse(
                present, f"the removed legacy mirror {name} must not exist"
            )
        self.assertIn("执行中", result["panelText"], result["panelText"])
        self.assertNotIn(self._WARNING, result["toastText"], result["toastText"])

    def test_numeric_string_session_id_is_accepted(self):
        """仅由数字组成且代表正整数的字符串是合法的 session_id。"""
        task = self._free_task()
        result = self.sandbox(
            self._MOUNT % json.dumps(task, ensure_ascii=False)
            + """
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
              session_id: '4242', task_id: 42, started_at: '2026-10-25T00:00:00',
              planned_minutes: 25
            }});
            await app.startTask(42);
            const activity = dom.getElementById('freeCardAcceptForm_42_activity');
            activity.value = '看纪录片';
            await app.submitFreeCardAccept(42);
            results.timerState = timerState();
            results.postUrls = calls.filter((c) => c.method === 'POST').map((c) => c.url);
            """
        )
        state = result["timerState"]
        self.assertIsNotNone(state["session"], state)
        self.assertEqual(state["session"]["id"], 4242, state)
        self.assertIn("/api/task-feedback", result["postUrls"], result["postUrls"])


# ---------------------------------------------------------------------------
# B4. "帮我选"（M02-S02-G02）：一次点击 → 一个具体活动
# ---------------------------------------------------------------------------
class HelpMeChooseBehaviourTests(_SandboxCase):
    """"帮我选" 的交互合同。

    - 成功：活动输入框被填入建议；理由 **不变**；**不** 自动提交、
      **不** 启动计时、**不** 写事件；
    - 失败（422 / 网络失败 / 响应缺合法 activity）：保留用户当前输入与理由，
      给出简短提示，用户可手动填写继续。
    """

    #: 合成建议接口的成功响应（只读接口，**不** 发行卡、**不** 写库）。
    _SUGGEST_OK = {
        "ok": True,
        "status": 200,
        "body": {
            "suggestion": {"activity": "看一集纪录片", "category": "娱乐"},
            "candidate_count": 3,
        },
    }

    #: 合成失败响应：没有合法获批候选（后端稳定 422 + 错误码）。
    _SUGGEST_422 = {
        "ok": False,
        "status": 422,
        "body": {"error": "free_card_activity_candidates_missing"},
    }

    #: 公共前置：挂载自由卡、打开接受表单并写入用户当前输入。
    _PREP = """
        await app.startTask(42);
        const activity = dom.getElementById('freeCardAcceptForm_42_activity');
        const reason = dom.getElementById('freeCardAcceptForm_42_reason');
        activity.value = '我自己写的活动';
        reason.value = '想放松一下';
        const flush = async () => { for (let i = 0; i < 50; i++) { await Promise.resolve(); } };
    """

    def _prep(self) -> str:
        return self._MOUNT % json.dumps(
            self._free_task(), ensure_ascii=False
        ) + self._PREP

    def test_accept_form_has_a_help_me_choose_button(self):
        """接受表单里必须有清晰的"帮我选"按钮。"""
        result = self.sandbox(
            self._prep()
            + """
            const btn = dom.getElementById('freeCardAcceptForm_42_suggest');
            results.hasButton = !!btn;
            results.buttonText = btn ? btn.textContent : null;
            results.panelText = app._testCard.querySelector('.drawn-card-right-panel').textContent;
            """
        )
        self.assertTrue(result["hasButton"], "the accept form must contain a 帮我选 button")
        self.assertEqual(result["buttonText"], "帮我选", result["buttonText"])
        self.assertIn("帮我选", result["panelText"], result["panelText"])

    def test_help_me_choose_fills_activity_and_changes_nothing_else(self):
        """成功：只填活动输入框；理由不变；不自动提交、不启动计时。"""
        result = self.sandbox(
            self._prep()
            + """
            fetchResponses.set('/api/gacha/free-card/suggestion', %s);
            const btn = dom.getElementById('freeCardAcceptForm_42_suggest');
            btn.click();
            await flush();
            results.activityValue = dom.getElementById('freeCardAcceptForm_42_activity').value;
            results.reasonValue = dom.getElementById('freeCardAcceptForm_42_reason').value;
            results.posts = calls.filter((c) => c.method === 'POST').map((c) => c.url);
            results.gets = calls.filter((c) => c.url === '/api/gacha/free-card/suggestion');
            results.panelText = app._testCard.querySelector('.drawn-card-right-panel').textContent;
            """
            % json.dumps(self._SUGGEST_OK, ensure_ascii=False)
        )
        self.assertEqual(
            result["activityValue"],
            "看一集纪录片",
            "the suggestion must be written into the activity input",
        )
        self.assertEqual(
            result["reasonValue"],
            "想放松一下",
            "the reason must NOT be touched by 帮我选",
        )
        self.assertEqual(
            result["posts"],
            [],
            "帮我选 must NOT auto-submit the form nor start a timer",
        )
        self.assertEqual(len(result["gets"]), 1, result["gets"])
        self.assertEqual(result["gets"][0]["method"], "GET", result["gets"][0])
        # 表单仍在等待用户自己点"开始"。
        self.assertIn("开始", result["panelText"], result["panelText"])
        self.assertNotIn("执行中", result["panelText"], result["panelText"])

    def test_help_me_choose_keeps_user_input_when_there_is_no_candidate(self):
        """422（没有合法获批候选）：保留用户当前输入与理由，并给出提示。"""
        result = self.sandbox(
            self._prep()
            + """
            fetchResponses.set('/api/gacha/free-card/suggestion', %s);
            const btn = dom.getElementById('freeCardAcceptForm_42_suggest');
            btn.click();
            await flush();
            results.activityValue = dom.getElementById('freeCardAcceptForm_42_activity').value;
            results.reasonValue = dom.getElementById('freeCardAcceptForm_42_reason').value;
            results.posts = calls.filter((c) => c.method === 'POST').map((c) => c.url);
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
            % json.dumps(self._SUGGEST_422, ensure_ascii=False)
        )
        self.assertEqual(
            result["activityValue"],
            "我自己写的活动",
            "the user's activity must be preserved when there is no candidate",
        )
        self.assertEqual(
            result["reasonValue"],
            "想放松一下",
            "the user's reason must be preserved when there is no candidate",
        )
        self.assertEqual(result["posts"], [], "no candidate must NOT start a timer")
        self.assertIn("建议", result["toastText"], result["toastText"])

    def test_help_me_choose_keeps_user_input_on_network_failure(self):
        """网络失败：保留用户当前输入与理由，并给出提示。"""
        result = self.sandbox(
            self._prep()
            + """
            app.fetch = function () { return Promise.reject(new Error('network down')); };
            const btn = dom.getElementById('freeCardAcceptForm_42_suggest');
            btn.click();
            await flush();
            results.activityValue = dom.getElementById('freeCardAcceptForm_42_activity').value;
            results.reasonValue = dom.getElementById('freeCardAcceptForm_42_reason').value;
            results.posts = calls.filter((c) => c.method === 'POST').map((c) => c.url);
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(
            result["activityValue"],
            "我自己写的活动",
            "the user's activity must be preserved on a network failure",
        )
        self.assertEqual(
            result["reasonValue"],
            "想放松一下",
            "the user's reason must be preserved on a network failure",
        )
        self.assertEqual(result["posts"], [], "a network failure must NOT start a timer")
        self.assertIn("建议", result["toastText"], result["toastText"])

    def test_help_me_choose_never_invents_an_activity(self):
        """响应缺少合法 activity → 保留用户输入，绝不编造活动。"""
        result = self.sandbox(
            self._prep()
            + """
            fetchResponses.set('/api/gacha/free-card/suggestion', {
              ok: true, status: 200, body: { suggestion: {}, candidate_count: 0 }
            });
            const btn = dom.getElementById('freeCardAcceptForm_42_suggest');
            btn.click();
            await flush();
            results.activityValue = dom.getElementById('freeCardAcceptForm_42_activity').value;
            results.reasonValue = dom.getElementById('freeCardAcceptForm_42_reason').value;
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(
            result["activityValue"],
            "我自己写的活动",
            "the user's activity must be preserved when the response has no activity",
        )
        self.assertEqual(result["reasonValue"], "想放松一下", result["reasonValue"])
        self.assertIn("建议", result["toastText"], result["toastText"])


# ===========================================================================
# C. G03：自由卡主动结束与真实反馈（前端合同）
# ===========================================================================
#
# 合同要点（M02-S02-G03）：
#   1. 只对 **正式自由卡** 增加结束反馈；普通/微型/目标卡的完成、关怀、
#      计时行为逐字不变。
#   2. 用户 **主动结束** 自由卡 → 明确反馈（是否顺利 / 是否被中断 /
#      实际活动 / 可选原因）→ 用户确认提交后才保存。
#   3. 只复用既有 ``POST /api/task-feedback`` 与既有合法 event_type /
#      reason_category；实际活动与结论放进既有 note 字段。
#   4. 中断绝不记为已完成；计时停止失败 → 保留现状；避免重复提交；
#      保存失败 → 保留表单内容并允许重试；取消不谎报保存成功。
#   5. 成功保存后回到统一抽卡。


def _extract_function_body(js: str, name: str) -> str:
    """取出 ``static/app.js`` 里某个具名函数的源码体（找不到 → 空串）。"""
    m = re.search(
        r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
        js,
    )
    if not m:
        return ""
    start = m.end() - 1
    depth = 0
    for i in range(start, len(js)):
        ch = js[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return js[start:i + 1]
    return js[start:]


class FreeCardEndFeedbackSourceContractTests(unittest.TestCase):
    """``static/app.js`` 的 G03 静态形状检查（不执行）。"""

    @classmethod
    def setUpClass(cls):
        cls.js = APP_JS.read_text(encoding="utf-8")

    def test_end_feedback_functions_exist(self):
        for name in (
            "openFreeCardEndForm",
            "submitFreeCardEnd",
            "cancelFreeCardEndForm",
            "returnToUnifiedGachaAfterFreeCard",
            "resolveDockFreeCardTaskId",
            "openFreeCardEndFormFromDock",
        ):
            self.assertTrue(
                _extract_function_body(self.js, name),
                f"{name} must exist in static/app.js",
            )

    def test_dock_stop_free_card_path_reuses_only_existing_apis(self):
        """Dock → 自由卡结束反馈的辅助函数 **绝不** 引入新端点。"""
        allowed = ("/api/task-feedback", "/api/timer/complete", "/api/tasks/")
        for name in ("resolveDockFreeCardTaskId", "openFreeCardEndFormFromDock"):
            body = _extract_function_body(self.js, name)
            self.assertTrue(body, f"{name} must exist")
            for url in set(re.findall(r"['\"](/api/[^'\"]*)['\"]", body)):
                self.assertTrue(
                    any(url.startswith(a) for a in allowed),
                    f"{name} must not introduce a new endpoint: {url}",
                )

    def test_dock_stop_free_card_path_never_calls_timer_complete_directly(self):
        """Dock 停止 **绝不** 自己停止计时（完全交给 submitFreeCardEnd）。"""
        for name in ("resolveDockFreeCardTaskId", "openFreeCardEndFormFromDock"):
            body = _extract_function_body(self.js, name)
            self.assertNotIn(
                "/api/timer/complete",
                body,
                f"{name} must not stop the timer itself",
            )
            # AR03-G08：legacy 镜像全局已移除；清空 owner session 的唯一入口
            # 是 owner.clear()。这两个辅助函数 **绝不** 清空活动 session。
            self.assertNotIn(
                "timerDockSession = null",
                body,
                f"{name} must not clear the dock session itself",
            )
            self.assertNotIn(
                ".clear()",
                body,
                f"{name} must not clear the timer owner session itself",
            )

    def test_dock_stop_dispatches_to_the_free_card_end_form_before_the_old_confirm(self):
        """Dock 停止的 **源码顺序**：先判自由卡 → 打开表单 → 再走旧确认。"""
        body = _extract_function_body(self.js, "stopTimerFromDock")
        self.assertTrue(body, "stopTimerFromDock must exist")
        free_pos = body.index("resolveDockFreeCardTaskId")
        open_pos = body.index("openFreeCardEndFormFromDock")
        confirm_pos = body.index("confirm(")
        self.assertLess(free_pos, open_pos, body)
        self.assertLess(open_pos, confirm_pos, body)
        # 自由卡分支必须在旧确认 **之前** 直接 return（绝不落到旧路径）。
        branch = body[free_pos:confirm_pos]
        self.assertIn("return;", branch, "the free-card branch must return early")

    def test_end_feedback_reuses_only_existing_apis(self):
        """G03 只允许复用既有已注册端点，绝不新增 API。"""
        allowed = ("/api/task-feedback", "/api/timer/complete", "/api/tasks/")
        used = set()
        for name in (
            "openFreeCardEndForm",
            "submitFreeCardEnd",
            "cancelFreeCardEndForm",
            "returnToUnifiedGachaAfterFreeCard",
        ):
            body = _extract_function_body(self.js, name)
            used.update(re.findall(r"['\"](/api/[^'\"]*)['\"]", body))
        self.assertTrue(used, "the G03 functions must reference existing endpoints")
        for url in used:
            self.assertTrue(
                any(url.startswith(a) for a in allowed),
                f"G03 must not introduce a new endpoint: {url}",
            )

    def test_end_feedback_uses_only_known_event_types(self):
        """只使用服务端已注册的 event_type / reason_category。"""
        body = _extract_function_body(self.js, "submitFreeCardEnd")
        self.assertTrue(body, "submitFreeCardEnd must exist")
        used_events = set(re.findall(r"eventType\s*=\s*'([a-z_]+)'", body))
        self.assertTrue(used_events, "submitFreeCardEnd must select an event_type")
        for event_type in used_events:
            self.assertIn(
                event_type,
                feedback_service.TASK_FEEDBACK_EVENT_TYPES,
                f"{event_type} is not a registered event_type",
            )
        used_categories = set(re.findall(r"reasonCategory\s*=\s*'([a-z_]+)'", body))
        for category in used_categories:
            self.assertIn(
                category,
                feedback_service.TASK_FEEDBACK_REASON_CATEGORIES,
                f"{category} is not a registered reason_category",
            )
        # 中断绝不能被写成 "completed"。
        self.assertIn("'abandoned'", body, "the interrupted outcome must not be completed")

    def test_end_feedback_note_carries_the_activity(self):
        """实际活动必须进入既有 note 字段（可读、兼容的 JSON）。"""
        body = _extract_function_body(self.js, "submitFreeCardEnd")
        self.assertIn("note", body, "submitFreeCardEnd must write the note field")
        self.assertIn("activity", body, "the note must carry the actual activity")

    def test_end_feedback_does_not_autopick_smooth(self):
        """绝不自动替用户选择"顺利"（默认两者都不选中）。"""
        body = _extract_function_body(self.js, "openFreeCardEndForm")
        # 渲染路径（单选创建 → 第一次 click 监听器之前）**不得** 触碰
        # ``.checked``：绝不预选任何一项。
        marker = "smoothInput.addEventListener('click'"
        self.assertIn(marker, body, "the outcome radios must be mutually exclusive on click")
        render_path = body.split(marker)[0]
        self.assertNotIn(
            ".checked",
            render_path,
            "no outcome may be pre-selected when the form is rendered",
        )
        # 提交时必须要求用户明确选择（默认空，绝不预填"顺利"）。
        submit_body = _extract_function_body(self.js, "submitFreeCardEnd")
        default_part = submit_body.split("if (!outcome)")[0]
        self.assertIn("var outcome = '';", default_part, "the outcome must start empty")
        # 任何把 outcome 设成 'smooth' 的地方都 **必须** 由用户的
        # ``.checked`` 显式选择来守卫（绝不自动替用户选"顺利"）。
        for line in default_part.splitlines():
            if "outcome = 'smooth'" in line:
                self.assertIn(
                    ".checked",
                    line,
                    "the smooth outcome must be guarded by an explicit user choice",
                )
        self.assertIn(
            "if (!outcome)",
            submit_body,
            "the submission must refuse to continue without an explicit outcome",
        )


class FreeCardEndFeedbackBehaviourTests(_SandboxCase):
    """自由卡结束反馈的交互行为（Node 合成 DOM 沙箱）。"""

    #: 挂载自由卡 → 走既有接受流程 → 打开结束反馈表单。
    _PREP = """
        fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
          session_id: 991, task_id: 42,
          started_at: new Date(Date.now() - %d).toISOString(),
          planned_minutes: 25
        }});
        await app.startTask(42);
        const acceptActivity = dom.getElementById('freeCardAcceptForm_42_activity');
        acceptActivity.value = '看纪录片';
        await app.submitFreeCardAccept(42);
        // AR03-G08：接受成功的判据来自 ESM timer owner 的公开快照。
        const acceptedState = timerState();
        results.accepted = !!(acceptedState.session && acceptedState.session.id === 991);
        results.runningPanelText = app._testCard
          ? app._testCard.querySelector('.drawn-card-right-panel').textContent
          : '';
        app.openFreeCardEndForm(42);
        results.panelText = app._testCard
          ? app._testCard.querySelector('.drawn-card-right-panel').textContent
          : '';
    """

    def _prep(self, elapsed_ms: int = 25 * 60 * 1000) -> str:
        return self._MOUNT % json.dumps(self._free_task(), ensure_ascii=False) + (
            self._PREP % elapsed_ms
        )

    def test_end_form_is_offered_only_for_free_cards(self):
        """自由卡出现"结束并记录反馈"（点击后才展开反馈表单）。"""
        result = self.sandbox(self._prep())
        self.assertTrue(result["accepted"], "the free card must be running")
        self.assertIn("结束并记录反馈", result["runningPanelText"], result["runningPanelText"])
        self.assertIn("是否顺利", result["panelText"], result["panelText"])

    def test_opening_the_form_is_not_a_saved_feedback(self):
        """打开反馈框 **不等于** 反馈已保存（零写入）。"""
        result = self.sandbox(
            self._prep()
            + """
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            """
        )
        self.assertEqual(
            result["feedbackPosts"],
            ["accept_task"],
            "opening the end form must NOT write any new feedback event",
        )
        self.assertEqual(
            result["timerComplete"],
            0,
            "opening the end form must NOT stop the timer",
        )

    def test_no_outcome_selected_writes_nothing(self):
        """用户没有明确选择时：绝不替用户选择"顺利"，也绝不写入。"""
        result = self.sandbox(
            self._prep()
            + """
            await app.submitFreeCardEnd(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(
            result["feedbackPosts"],
            ["accept_task"],
            "no explicit outcome must NOT write a feedback event",
        )
        self.assertEqual(result["timerComplete"], 0, "no explicit outcome must NOT stop the timer")
        self.assertIn("请先选择", result["toastText"], result["toastText"])

    def test_empty_activity_is_never_faked_as_a_fact(self):
        """没填实际活动 → 绝不写入（也不伪装成事实）。"""
        result = self.sandbox(
            self._prep()
            + """
            dom.getElementById('freeCardEndForm_42_smooth').click();
            const activity = dom.getElementById('freeCardEndForm_42_activity');
            activity.value = '   ';
            await app.submitFreeCardEnd(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(result["feedbackPosts"], ["accept_task"], result["feedbackPosts"])
        self.assertEqual(result["timerComplete"], 0, "the timer must not be stopped")
        self.assertIn("请填写", result["toastText"], result["toastText"])

    def test_smooth_outcome_records_activity_and_returns_to_gacha(self):
        """顺利：活动 / 结论正确写入既有事件；成功后回到统一抽卡。"""
        result = self.sandbox(
            self._prep()
            + """
            dom.getElementById('freeCardEndForm_42_smooth').click();
            const activity = dom.getElementById('freeCardEndForm_42_activity');
            activity.value = '看了一集纪录片';
            const reason = dom.getElementById('freeCardEndForm_42_reason');
            reason.value = '状态不错';
            await app.submitFreeCardEnd(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body);
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete' && c.responseOk
            ).map((c) => c.body);
            results.gachaHtml = dom.getElementById('gachaResult').innerHTML;
            results.currentTaskId = app.gachaState.currentTaskId;
            results.timerState = timerState();
            """
        )
        posts = result["feedbackPosts"]
        self.assertEqual(len(posts), 2, posts)
        end_post = posts[1]
        self.assertEqual(end_post["event_type"], "finish_on_time", end_post)
        self.assertEqual(end_post["completion_status"], "completed", end_post)
        self.assertEqual(end_post["reason_category"], "other", end_post)
        self.assertEqual(end_post["reason_detail"], "状态不错", end_post)
        self.assertEqual(end_post["task_id"], 42, end_post)
        note = json.loads(end_post["note"])
        self.assertEqual(note["activity"], "看了一集纪录片", note)
        self.assertEqual(note["outcome"], "smooth", note)
        self.assertFalse(note["interrupted"], note)

        # 计时按"已完成"停止。
        self.assertEqual(len(result["timerComplete"]), 1, result["timerComplete"])
        self.assertEqual(result["timerComplete"][0]["result"], "completed", result["timerComplete"])

        # 成功保存后回到统一抽卡。
        self.assertIn("继续抽卡", result["gachaHtml"], result["gachaHtml"])
        self.assertIsNone(result["currentTaskId"], result["currentTaskId"])
        # AR03-G08：计时结束后 owner 的活动 session 必须被清空。
        self.assertIsNone(result["timerState"]["session"], result["timerState"])
        self.assertFalse(result["timerState"]["hasInlineTimer"], result["timerState"])

    def test_interrupted_outcome_is_never_recorded_as_completed(self):
        """中断：绝不记为已完成（事件、计时、任务完成端点都不许）。"""
        result = self.sandbox(
            self._prep()
            + """
            dom.getElementById('freeCardEndForm_42_interrupted').click();
            const activity = dom.getElementById('freeCardEndForm_42_activity');
            activity.value = '看了一集纪录片';
            const reason = dom.getElementById('freeCardEndForm_42_reason');
            reason.value = '手机响了';
            await app.submitFreeCardEnd(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body);
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete' && c.responseOk
            ).map((c) => c.body);
            results.taskComplete = calls.filter(
              (c) => c.method === 'POST' && /\\/api\\/tasks\\/42\\/complete$/.test(c.url)
            ).length;
            """
        )
        posts = result["feedbackPosts"]
        self.assertEqual(len(posts), 2, posts)
        end_post = posts[1]
        self.assertEqual(end_post["event_type"], "abandon_task", end_post)
        self.assertEqual(end_post["completion_status"], "abandoned", end_post)
        self.assertEqual(end_post["reason_category"], "external_interrupt", end_post)
        self.assertEqual(end_post["reason_detail"], "手机响了", end_post)
        note = json.loads(end_post["note"])
        self.assertTrue(note["interrupted"], note)
        self.assertEqual(note["outcome"], "interrupted", note)
        self.assertEqual(note["activity"], "看了一集纪录片", note)

        self.assertEqual(len(result["timerComplete"]), 1, result["timerComplete"])
        self.assertEqual(result["timerComplete"][0]["result"], "abandoned", result["timerComplete"])
        self.assertNotEqual(
            result["timerComplete"][0]["result"],
            "completed",
            "an interrupted free card must never be stopped as completed",
        )
        self.assertEqual(
            result["taskComplete"],
            0,
            "an interrupted free card must NOT be marked as a completed task",
        )

    def test_cancelled_form_saves_nothing_and_restores_the_running_panel(self):
        """取消：不谎报保存成功，原样恢复"执行中"面板（计时继续）。"""
        result = self.sandbox(
            self._prep()
            + """
            dom.getElementById('freeCardEndForm_42_smooth').click();
            dom.getElementById('freeCardEndForm_42_activity').value = '看了一集纪录片';
            app.cancelFreeCardEndForm(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            results.panelText = app._testCard
              ? app._testCard.querySelector('.drawn-card-right-panel').textContent
              : '';
            results.formStillOpen = !!dom.getElementById('freeCardEndForm_42_activity');
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(result["feedbackPosts"], ["accept_task"], result["feedbackPosts"])
        self.assertEqual(result["timerComplete"], 0, "cancel must NOT stop the timer")
        self.assertFalse(result["formStillOpen"], "cancel must close the end form")
        self.assertIn("执行中", result["panelText"], result["panelText"])
        self.assertNotIn("是否顺利", result["panelText"], result["panelText"])
        self.assertIn("没有保存", result["toastText"], result["toastText"])

    def test_failed_save_keeps_the_input_and_allows_a_retry(self):
        """保存失败：保留表单内容 + 允许重试；不谎报成功。"""
        result = self.sandbox(
            self._prep()
            + """
            dom.getElementById('freeCardEndForm_42_smooth').click();
            const activity = dom.getElementById('freeCardEndForm_42_activity');
            activity.value = '看了一集纪录片';
            const reason = dom.getElementById('freeCardEndForm_42_reason');
            reason.value = '状态不错';
            fetchResponses.set('/api/task-feedback', {
              ok: false, status: 500, body: { error: '保存失败' }
            });
            await app.submitFreeCardEnd(42);
            results.afterFailActivity = dom.getElementById('freeCardEndForm_42_activity').value;
            results.afterFailReason = dom.getElementById('freeCardEndForm_42_reason').value;
            results.afterFailToast = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            results.afterFailFormOpen = !!dom.getElementById('freeCardEndForm_42_activity');
            results.afterFailGachaHtml = dom.getElementById('gachaResult').innerHTML;
            // 重试（服务端恢复正常）。
            fetchResponses.delete('/api/task-feedback');
            await app.submitFreeCardEnd(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.retryGachaHtml = dom.getElementById('gachaResult').innerHTML;
            """
        )
        self.assertEqual(
            result["afterFailActivity"],
            "看了一集纪录片",
            "the activity must be preserved when the save fails",
        )
        self.assertEqual(
            result["afterFailReason"],
            "状态不错",
            "the reason must be preserved when the save fails",
        )
        self.assertTrue(result["afterFailFormOpen"], "the form must stay open for a retry")
        self.assertIn("请重试", result["afterFailToast"], result["afterFailToast"])
        self.assertNotIn(
            "继续抽卡",
            result["afterFailGachaHtml"],
            "a failed save must NOT claim the feedback was saved",
        )
        # 重试后只多写 **一条** 结束事件（绝不重复写同一次反馈）。
        self.assertEqual(
            result["feedbackPosts"],
            ["accept_task", "finish_on_time"],
            result["feedbackPosts"],
        )
        self.assertIn("继续抽卡", result["retryGachaHtml"], result["retryGachaHtml"])

    def test_timer_stop_failure_keeps_the_state_and_saves_nothing(self):
        """计时停止失败 → 保留现状：不写反馈、不清 dock、表单内容保留。"""
        result = self.sandbox(
            self._prep()
            + """
            dom.getElementById('freeCardEndForm_42_smooth').click();
            const activity = dom.getElementById('freeCardEndForm_42_activity');
            activity.value = '看了一集纪录片';
            fetchResponses.set('/api/timer/complete', {
              ok: false, status: 500, body: { error: '停止失败' }
            });
            await app.submitFreeCardEnd(42);
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.timerState = timerState();
            results.activityValue = dom.getElementById('freeCardEndForm_42_activity').value;
            results.formStillOpen = !!dom.getElementById('freeCardEndForm_42_activity');
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(
            result["feedbackPosts"],
            ["accept_task"],
            "a failed timer stop must NOT write a feedback event",
        )
        # AR03-G08：停止失败 → owner **保留** 活动 session（绝不伪清空）。
        state = result["timerState"]
        self.assertIsNotNone(
            state["session"],
            "a failed timer stop must keep the current state (owner session not cleared)",
        )
        self.assertEqual(state["session"]["id"], 991, state)
        self.assertEqual(
            result["activityValue"],
            "看了一集纪录片",
            "the activity must be preserved when the timer stop fails",
        )
        self.assertTrue(result["formStillOpen"], "the form must stay open for a retry")
        self.assertIn("停止失败", result["toastText"], result["toastText"])

    def test_non_free_cards_keep_the_original_completion_flow(self):
        """普通卡的完成 / 关怀 / 计时行为逐字不变。"""
        task = {
            "id": 43,
            "name": "普通卡",
            "description": "d",
            "category": "study",
            "priority": 5,
            "estimated_time": 30,
            "repeat_type": "none",
            "tags": [],
            "task_type": "standard",
            "is_unlocked": 1,
        }
        result = self.sandbox(
            self._MOUNT
            % json.dumps(task, ensure_ascii=False)
            + """
            app.setTimeout = function (fn, ms) { if (ms === 720) { fn(); } return 0; };
            fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
              session_id: 5, task_id: 43, started_at: '2026-10-25T00:00:00', planned_minutes: 30
            }});
            await app.startTask(43);
            results.panelText = app._testCard
              ? app._testCard.querySelector('.drawn-card-right-panel').textContent
              : '';
            results.hasEndButton = results.panelText.indexOf('结束并记录反馈') >= 0;
            await app.confirmComplete(43);
            results.taskComplete = calls.filter(
              (c) => c.method === 'POST' && /\\/api\\/tasks\\/43\\/complete$/.test(c.url)
            ).length;
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback'
            ).map((c) => c.body.event_type);
            results.feedbackModalOpen = !dom.getElementById('feedbackModal')
              .classList.contains('hidden');
            """
        )
        self.assertIn("确认完成任务", result["panelText"], result["panelText"])
        self.assertFalse(
            result["hasEndButton"],
            "a non-free card must NOT get the free-card end-feedback button",
        )
        self.assertEqual(result["taskComplete"], 1, "the original completion flow must be intact")
        self.assertEqual(
            result["feedbackPosts"],
            [],
            "a non-free card must NOT write a free-card feedback event",
        )
        self.assertTrue(
            result["feedbackModalOpen"],
            "the original feedback modal must still open for non-free cards",
        )


# ---------------------------------------------------------------------------
# C2. Dock 停止按钮（M02-S02-G03-W02）：自由卡必须走结束反馈表单
# ---------------------------------------------------------------------------
class FreeCardDockStopBehaviourTests(_SandboxCase):
    """Dock 停止按钮对自由卡 / 非自由卡的行为合同。

    - 自由卡：先打开 **既有** G03 结束反馈表单；表单提交前 **绝不** 停止
      计时、**绝不** 写结束事件、Dock session 保留、**绝不** 弹旧的
      "提前结束"确认；
    - 表单提交后：完全复用 submitFreeCardEnd 现有流程（只停止一次计时、
      只写一次结束事件）；
    - 非自由卡：保持既有 Dock 提前结束语义（abandoned + 清 Dock + 刷新），
      **绝不** 出现 G03 表单；
    - 自由卡但找不到表单：**fail closed**（保留计时与 Dock + 明确提示），
      绝不静默退回旧的"直接中断"路径。
    """

    #: 自由卡接受并开始计时（既有 G03 前置流程，零改动）。
    _ACCEPT = """
        fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
          session_id: 991, task_id: 42,
          started_at: new Date(Date.now() - %d).toISOString(),
          planned_minutes: 25
        }});
        await app.startTask(42);
        const acceptActivity = dom.getElementById('freeCardAcceptForm_42_activity');
        acceptActivity.value = '看纪录片';
        await app.submitFreeCardAccept(42);
    """

    def _free_prep(self, elapsed_ms: int = 25 * 60 * 1000) -> str:
        return self._MOUNT % json.dumps(self._free_task(), ensure_ascii=False) + (
            self._ACCEPT % elapsed_ms
        )

    #: 非自由卡（标准卡）开始计时的既有流程。
    _STANDARD = """
        fetchResponses.set('/api/timer/start', { ok: true, status: 200, body: {
          session_id: 5, task_id: 43,
          started_at: new Date(Date.now() - %d).toISOString(),
          planned_minutes: 30
        }});
        await app.startTask(43);
    """

    def _standard_task(self) -> dict:
        return {
            "id": 43,
            "name": "普通卡",
            "description": "d",
            "category": "study",
            "priority": 5,
            "estimated_time": 30,
            "repeat_type": "none",
            "tags": [],
            "task_type": "standard",
            "is_unlocked": 1,
        }

    def _standard_prep(self, elapsed_ms: int = 10 * 60 * 1000) -> str:
        return self._MOUNT % json.dumps(
            self._standard_task(), ensure_ascii=False
        ) + (self._STANDARD % elapsed_ms)

    # --- 自由卡：Dock 停止 → 打开 G03 表单（不停止计时、不写事件）--------
    def test_dock_stop_on_free_card_opens_the_g03_end_form_only(self):
        result = self.sandbox(
            self._free_prep()
            + """
            await app.stopTimerFromDock(991);
            results.confirmCalls = confirmCalls.slice();
            results.formOpen = !!dom.getElementById('freeCardEndForm_42_activity');
            results.panelText = app._testCard
              ? app._testCard.querySelector('.drawn-card-right-panel').textContent
              : '';
            results.timerState = timerState();
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            """
        )
        self.assertTrue(
            result["formOpen"], "the dock stop must open the G03 end-feedback form"
        )
        self.assertIn("是否顺利", result["panelText"], result["panelText"])
        self.assertEqual(
            result["confirmCalls"],
            [],
            "the free-card dock stop must NOT show the old early-finish confirm",
        )
        self.assertEqual(
            result["timerComplete"],
            0,
            "opening the form must NOT stop the timer",
        )
        self.assertEqual(
            result["feedbackPosts"],
            ["accept_task"],
            "opening the form must NOT write an end-feedback event",
        )
        # AR03-G08：owner 的活动 session 必须被保留（计时仍在继续）。
        state = result["timerState"]
        self.assertIsNotNone(state["session"], "the owner session must be preserved")
        self.assertEqual(state["session"]["id"], 991, state)

    # --- 自由卡：通过 Dock 打开后提交（复用既有 G03 路径）---------------
    def test_dock_opened_form_submits_through_the_existing_g03_path(self):
        for outcome, expected_event, expected_result in (
            ("smooth", "finish_on_time", "completed"),
            ("interrupted", "abandon_task", "abandoned"),
        ):
            with self.subTest(outcome=outcome):
                result = self.sandbox(
                    self._free_prep()
                    + """
                    await app.stopTimerFromDock(991);
                    dom.getElementById('freeCardEndForm_42_%s').click();
                    const activity = dom.getElementById('freeCardEndForm_42_activity');
                    activity.value = '看了一集纪录片';
                    const reason = dom.getElementById('freeCardEndForm_42_reason');
                    reason.value = '状态不错';
                    await app.submitFreeCardEnd(42);
                    results.feedbackPosts = calls.filter(
                      (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
                    ).map((c) => c.body);
                    results.timerComplete = calls.filter(
                      (c) => c.method === 'POST' && c.url === '/api/timer/complete'
                    ).map((c) => c.body);
                    results.timerState = timerState();
                    results.taskComplete = calls.filter(
                      (c) => c.method === 'POST' && /\\/api\\/tasks\\/42\\/complete$/.test(c.url)
                    ).length;
                    """
                    % outcome
                )
                # 只写 **一条** 结束事件（绝不重复写）。
                posts = result["feedbackPosts"]
                self.assertEqual(len(posts), 2, posts)
                end_post = posts[1]
                self.assertEqual(end_post["event_type"], expected_event, end_post)
                self.assertEqual(end_post["task_id"], 42, end_post)
                note = json.loads(end_post["note"])
                self.assertEqual(note["activity"], "看了一集纪录片", note)
                self.assertEqual(
                    note["interrupted"], outcome == "interrupted", note
                )

                # 只停止 **一次** 计时（绝不重复停止）。
                completes = result["timerComplete"]
                self.assertEqual(len(completes), 1, completes)
                self.assertEqual(completes[0]["result"], expected_result, completes)
                # AR03-G08：既有 G03 流程清空 owner 的活动 session。
                self.assertIsNone(
                    result["timerState"]["session"],
                    "the owner session must be cleared by the existing G03 flow",
                )
                if outcome == "interrupted":
                    self.assertEqual(
                        result["taskComplete"],
                        0,
                        "an interrupted free card must NOT be marked as completed",
                    )

    # --- 非自由卡：保持既有 Dock 提前结束语义 ---------------------------
    def test_dock_stop_on_a_non_free_card_keeps_the_original_semantics(self):
        result = self.sandbox(
            self._standard_prep()
            + """
            await app.stopTimerFromDock(5);
            results.confirmCalls = confirmCalls.slice();
            results.formOpen = !!dom.getElementById('freeCardEndForm_43_activity');
            results.panelText = app._testCard
              ? app._testCard.querySelector('.drawn-card-right-panel').textContent
              : '';
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).map((c) => c.body);
            results.timerState = timerState();
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback'
            ).length;
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(
            result["confirmCalls"],
            ["确定提前结束此任务？"],
            "a non-free card must keep the old early-finish confirmation",
        )
        self.assertFalse(
            result["formOpen"],
            "a non-free card must NOT open the free-card end-feedback form",
        )
        self.assertNotIn("是否顺利", result["panelText"], result["panelText"])
        completes = result["timerComplete"]
        self.assertEqual(len(completes), 1, completes)
        self.assertEqual(completes[0]["result"], "abandoned", completes)
        self.assertEqual(completes[0]["reason"], "early_finish", completes)
        # AR03-G08：非自由卡的 Dock 停止同样清空 owner 的活动 session。
        self.assertIsNone(
            result["timerState"]["session"],
            "a non-free dock stop must clear the owner session",
        )
        self.assertEqual(
            result["feedbackPosts"],
            0,
            "a non-free dock stop must NOT write a free-card feedback event",
        )
        self.assertIn("已中断任务", result["toastText"], result["toastText"])

    # --- 自由卡但找不到表单：fail closed ---------------------------------
    def test_dock_stop_fails_closed_when_the_free_card_form_cannot_be_located(self):
        result = self.sandbox(
            self._free_prep()
            + """
            // 卡片从 DOM 移除（模拟"卡片已不在屏幕上"），但缓存里仍能
            // 识别出它是自由卡 → 必须 fail closed，**绝不** 直接中断。
            const holder = dom.getElementById('gachaResult');
            holder.innerHTML = '';
            await app.stopTimerFromDock(991);
            results.confirmCalls = confirmCalls.slice();
            results.timerState = timerState();
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            results.feedbackPosts = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/task-feedback' && c.responseOk
            ).map((c) => c.body.event_type);
            results.toastText = (dom.getElementById('toastContainer') || { textContent: '' }).textContent;
            """
        )
        self.assertEqual(
            result["confirmCalls"],
            [],
            "a free card must never fall back to the old early-finish confirm",
        )
        self.assertEqual(
            result["timerComplete"],
            0,
            "a free card must never be interrupted without the G03 form",
        )
        self.assertEqual(
            result["feedbackPosts"],
            ["accept_task"],
            "a free card must never write an end event without the G03 form",
        )
        # AR03-G08：fail closed 必须保留 owner 的活动 session（计时继续）。
        state = result["timerState"]
        self.assertIsNotNone(
            state["session"],
            "fail closed must keep the owner session (the timer keeps running)",
        )
        self.assertEqual(state["session"]["id"], 991, state)
        self.assertIn("找不到", result["toastText"], result["toastText"])
        self.assertIn("计时仍在继续", result["toastText"], result["toastText"])

    def test_dock_stop_uses_the_card_type_attribute_as_a_free_card_fallback(self):
        """缓存里找不到任务对象时，卡片的 data-card-type="free" 仍然算数。"""
        result = self.sandbox(
            self._free_prep()
            + """
            // 清空既有任务缓存（模拟 /api/tasks 尚未加载），
            // 只剩屏幕上的卡片（data-card-type="free"）这一依据。
            app.allTasks = [];
            app.multiDrawResults = [];
            app._currentDrawnTask = null;
            await app.stopTimerFromDock(991);
            results.formOpen = !!dom.getElementById('freeCardEndForm_42_activity');
            results.timerComplete = calls.filter(
              (c) => c.method === 'POST' && c.url === '/api/timer/complete'
            ).length;
            results.timerState = timerState();
            """
        )
        self.assertTrue(
            result["formOpen"],
            "data-card-type=\"free\" must be enough to route the dock stop to the G03 form",
        )
        self.assertEqual(result["timerComplete"], 0, result)
        self.assertIsNotNone(result["timerState"]["session"], result)


if __name__ == "__main__":
    unittest.main()
