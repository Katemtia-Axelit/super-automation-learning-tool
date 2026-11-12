"""M02-S01-G02-W03: 正式网页卡类型入口与显示（前端契约测试）。

范围与红线
----------
- **只读**  ``static/app.js`` 与 ``src/index.html``；**不碰** 任何生产
  API / DB / 策略 / 笔记 / 配置。
- 全部前端逻辑在 **Node + 合成 DOM mock** 里执行：``static/app.js`` 被
  读入后在一个受控沙箱里求值，``fetch`` 被替换为记录调用的 stub，
  ``document`` 被替换为最小 DOM 实现。
- **绝不** 硬编码用户绝对目录：项目根由 ``__file__`` 推导。
- 真实后端契约（``task_type`` 的接受/拒绝、旧值归一）由 W02 的
  ``tests/characterize/test_card_type_pool.py`` 覆盖；本文件只覆盖
  **前端** 行为与前端安全。

核心契约
--------
1. ``#tfCardType`` 下拉存在，四个枚举 ``standard/free/micro/goal``
   各自对应清晰的中文标签；**原 ``#tfCat`` 内容类别下拉保持不变**。
2. ``normalizeCardType`` 是**纯展示侧**归一：只有严格小写的四个正式值
   被保留；历史值 ``normal``/``other``/``NULL``/空串/未知值/非字符串/
   大小写变体 **全部** → ``standard``。
3. 编辑旧卡时显示归一后的值，但 **PUT 必须省略** ``task_type``
   （不得因为显示归一把 legacy ``normal`` 静默写成 ``standard``）；
   用户确实改型时才提交。
4. 新建任务必须提交一个**合法** 的 ``task_type``。
5. 抽卡卡面同时有**内容类别**角标和**独立的卡类型**角标（四类均可显示）。
6. XSS 安全：用户 ``task_type`` 异常值不进入 ``innerHTML``；不把不可信
   字符串当 ``onclick`` 参数。
7. Bootstrap 423 fail-closed 闸门**未被改动**。
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "static" / "app.js"
EDITOR_JS = PROJECT_ROOT / "static" / "modules" / "tasks" / "editor.js"
INDEX_HTML = PROJECT_ROOT / "src" / "index.html"

CARD_TYPE_VALUES = ("standard", "free", "micro", "goal")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(js: str, name: str) -> str:
    """Return the body of ``function <name>(...) { ... }`` from ``js``."""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", js)
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


class _SandboxRunner:
    """Load ``static/app.js`` into a Node VM with a synthetic DOM.

    The DOM mock is intentionally minimal but sufficient for the code paths
    this task touches (task modal + card rendering).  No network, no real
    files, no production data.
    """

    def __init__(self, tmp_root: Path):
        self.tmp_root = tmp_root
        self.node_script = tmp_root / "sandbox.mjs"
        self._counter = 0

    # ------------------------------------------------------------------
    def available(self) -> bool:
        return shutil.which("node") is not None

    # ------------------------------------------------------------------
    def run(self, snippet: str, *, timeout: int = 120) -> dict:
        """Execute ``snippet`` inside the sandbox and return its JSON result.

        ``snippet`` may use the injected globals:
          ``app``      — the evaluated ``static/app.js`` scope
          ``dom``      — the synthetic document implementation
          ``calls``    — recorded fetch calls
          ``results``  — object the snippet must fill
        """
        self._counter += 1
        self.node_script.write_text(_HARNESS_TEMPLATE, encoding="utf-8")
        env = dict(os.environ)
        env["SAL_APP_JS"] = str(APP_JS)
        env["SAL_EDITOR_JS"] = str(EDITOR_JS)
        env["SAL_INDEX_HTML"] = str(INDEX_HTML)
        env["SAL_SNIPPET"] = snippet
        env["NODE_OPTIONS"] = ""
        try:
            proc = subprocess.run(
                [shutil.which("node"), str(self.node_script)],
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

    # ------------------------------------------------------------------
    def _read_harness(self) -> str:
        return _HARNESS_TEMPLATE


# ---------------------------------------------------------------------------
# Node sandbox harness
# ---------------------------------------------------------------------------

_HARNESS_TEMPLATE = r"""
import fs from 'node:fs';
import vm from 'node:vm';

// Evaluate application definitions; omit unrelated automatic network loading.
const APP_JS = fs.readFileSync(process.env.SAL_APP_JS, 'utf8')
  .split('// ============ 启动加载 ============')[0];

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
    this.style = { setProperty() {}, cssText: '' };
    this.classList = new FakeClassList(this);
    this._innerHTML = '';
    this.textContent = '';
    this.value = '';
    this.options = [];
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this._listeners = {};
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(v) { this._innerHTML = String(v); }
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
  click() {}
  focus() {}
  setSelectionRange() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { top: 0, left: 0, width: 0, height: 0, right: 0, bottom: 0 }; }
  scrollIntoView() {}
  getContext() { return null; }
  closest() { return null; }
  contains() { return false; }
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
  getElementById(id) { return this.byId.get(id) || null; }
  createElement(tag) { return new FakeElement(tag, this); }
  createTextNode(t) { const n = new FakeElement('#text', this); n.textContent = String(t); return n; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  addEventListener() {}
  removeEventListener() {}
}

function makeDom() {
  const doc = new FakeDocument();
  // Auto-derive every id that the real page declares, so the app's
  // top-level `document.getElementById(...).addEventListener(...)` calls
  // all resolve. Ids are read from the real src/index.html — read-only.
  const html = fs.readFileSync(process.env.SAL_INDEX_HTML, 'utf8');
  const seen = new Set();
  const re = /\bid="([^"]+)"/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (!seen.has(m[1])) { seen.add(m[1]); doc._mk(m[1]); }
  }
  // The card-type select needs real <option> children so that assigning an
  // arbitrary string is observable (a real <select> clamps to its options).
  const ct = doc.getElementById('tfCardType');
  ct.options = ['standard', 'free', 'micro', 'goal'].map((v) => {
    const o = new FakeElement('option', doc);
    o.value = v;
    o.textContent = v;
    return o;
  });
  const cat = doc.getElementById('tfCat');
  cat.options = ['study', 'exercise', 'work', 'life', 'other'].map((v) => {
    const o = new FakeElement('option', doc);
    o.value = v;
    o.textContent = v;
    return o;
  });
  // A real <select> only accepts a value that one of its <option>s carries.
  Object.defineProperty(ct, 'value', {
    configurable: true,
    get() { return this._value === undefined ? 'standard' : this._value; },
    set(v) {
      const allowed = this.options.map((o) => o.value);
      this._value = allowed.indexOf(String(v)) >= 0 ? String(v) : '';
    },
  });
  Object.defineProperty(cat, 'value', {
    configurable: true,
    get() { return this._value === undefined ? 'study' : this._value; },
    set(v) {
      const allowed = this.options.map((o) => o.value);
      this._value = allowed.indexOf(String(v)) >= 0 ? String(v) : '';
    },
  });
  return doc;
}

// ---------------------------------------------------------------- fetch stub
const calls = [];
const fetchResponses = new Map(); // url -> {ok, status, body}
function installFetchStub(ctx) {
  ctx.fetch = function (url, opts) {
    const method = (opts && opts.method) || 'GET';
    const rec = { url: String(url), method: String(method).toUpperCase(), body: null };
    if (opts && typeof opts.body === 'string') {
      try { rec.body = JSON.parse(opts.body); } catch (e) { rec.body = opts.body; }
    }
    calls.push(rec);
    const key = String(url);
    const scripted = fetchResponses.get(key);
    if (scripted) {
      return Promise.resolve({
        ok: scripted.ok,
        status: scripted.status,
        json: function () { return Promise.resolve(scripted.body); },
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({}); } });
  };
}

// ---------------------------------------------------------------- bootstrap
const dom = makeDom();
const sandbox = {
  window: null,
  document: dom,
  console: console,
  fetch: null,
  setInterval: function () { return 0; },
  clearInterval: function () {},
  // Toast dismiss timers must not fire before assertions.
  setTimeout: function () { return 0; },
  clearTimeout: function () {},
  requestAnimationFrame: function (fn) { if (typeof fn === 'function') fn(); return 0; },
  localStorage: { getItem: function () { return null; }, setItem: function () {} },
  navigator: { clipboard: null },
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
  Reflect: Reflect,
  console: console,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.onerror = function () { return false; };
installFetchStub(sandbox);

const ctx = vm.createContext(sandbox);
vm.runInContext(APP_JS, ctx, { filename: 'app.js' });

// ---------------------------------------------------------------- AR03-G13
// 任务编辑器的真实业务实现已迁至 static/modules/tasks/editor.js（ESM owner）。
// 这里用 Node 原生 data-URL 动态 import 该模块源码（仓库 package.json 没有
// type=module，editor.js 也不依赖任何相对 import），并在合成 DOM 上实例化
// 唯一 owner，把它的方法绑定到 sandbox，使既有 runtime snippet 仍能同步
// 调用 app.openTaskEdit / app.buildDepList / app.saveTask。
const EDITOR_JS = fs.readFileSync(process.env.SAL_EDITOR_JS, 'utf8');
const editorModuleUrl = 'data:text/javascript;base64,' +
  Buffer.from(EDITOR_JS, 'utf8').toString('base64');
const editorModule = await import(editorModuleUrl);

// 依赖全部来自 classic 层（app.js 在 VM 里求值后的真实全局），owner 不
// 通过 window 私自查找私有依赖。
const classicDeps = vm.runInContext(`({
  api: api,
  toast: toast,
  showModal: showModal,
  closeModal: closeModal,
  escapeHtml: escapeHtml,
  normalizeCardType: normalizeCardType,
  loadTasks: loadTasks,
  loadTags: loadTags,
  deleteTask: deleteTask,
  getTasks: function () { return allTasks; },
  getTags: function () { return allTags; }
})`, ctx);

const editorOwner = editorModule.createTaskEditorOwner(Object.assign({
  windowRef: sandbox,
  documentRef: dom
}, classicDeps));

sandbox.openTaskEdit = editorOwner.openTaskEdit;
sandbox.buildDepList = editorOwner.buildDepList;
sandbox.addTagChip = editorOwner.addTagChip;
sandbox.saveTask = editorOwner.saveTask;
sandbox.deleteCurrentTask = editorOwner.deleteCurrentTask;

const app = sandbox;
const results = { ok: true };

const SNIPPET = process.env.SAL_SNIPPET;
(async () => {
  try {
    // eslint-disable-next-line no-new-func
    const fn = new Function('app', 'dom', 'calls', 'results', 'fetchResponses',
      'return (async () => {' + SNIPPET + '})();');
    await fn(app, dom, calls, results, fetchResponses);
  } catch (err) {
    results.ok = false;
    results.error = String((err && err.stack) || err);
  }
  process.stdout.write(JSON.stringify(results) + '\n');
})();
"""


class _SandboxCase(unittest.TestCase):
    """Base class providing a Node sandbox fixture."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="sal-cardtype-")
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


# ---------------------------------------------------------------------------
# 1. HTML contract (static)
# ---------------------------------------------------------------------------
class CardTypeHtmlContractTests(unittest.TestCase):
    """``src/index.html`` must expose an independent card-type select."""

    @classmethod
    def setUpClass(cls):
        cls.html = _read(INDEX_HTML)

    def test_card_type_select_exists(self):
        self.assertRegex(
            self.html,
            r'id=["\']tfCardType["\']',
            "index.html must contain the independent card-type select #tfCardType",
        )

    def test_card_type_select_has_exactly_four_formal_options(self):
        m = re.search(
            r'<select[^>]*id=["\']tfCardType["\'][^>]*>(.*?)</select>',
            self.html,
            re.S,
        )
        self.assertTrue(m, "#tfCardType select must exist in index.html")
        values = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', m.group(1))
        self.assertEqual(
            sorted(values),
            sorted(CARD_TYPE_VALUES),
            "#tfCardType must offer exactly standard/free/micro/goal, got " + repr(values),
        )

    def test_card_type_options_have_readable_chinese_labels(self):
        m = re.search(
            r'<select[^>]*id=["\']tfCardType["\'][^>]*>(.*?)</select>',
            self.html,
            re.S,
        )
        self.assertTrue(m, "#tfCardType select must exist in index.html")
        pairs = re.findall(
            r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>([^<]*)</option>',
            m.group(1),
        )
        self.assertEqual(len(pairs), 4, "expected four options, got " + repr(pairs))
        expected_labels = {
            "standard": "标准卡",
            "free": "自由卡",
            "micro": "微型卡",
            "goal": "目标卡",
        }
        for value, label in pairs:
            self.assertEqual(
                label.strip(),
                expected_labels[value],
                f"option {value!r} must carry the label {expected_labels[value]!r}, got {label!r}",
            )

    def test_content_category_select_is_unchanged(self):
        """The original content-category select #tfCat must be untouched."""
        m = re.search(
            r'<select[^>]*id=["\']tfCat["\'][^>]*>(.*?)</select>',
            self.html,
            re.S,
        )
        self.assertTrue(m, "#tfCat must still exist")
        values = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', m.group(1))
        self.assertEqual(
            sorted(values),
            sorted(["study", "exercise", "work", "life", "other"]),
            "#tfCat content-category options must be unchanged, got " + repr(values),
        )

    def test_card_type_is_documented_as_distinct_from_category(self):
        """The modal must explain that card type != activity category."""
        idx = self.html.find('id="tfCardType"')
        self.assertTrue(idx > 0, "#tfCardType must exist")
        window = self.html[max(0, idx - 900): idx + 900]
        self.assertIn("卡类型不同于活动类别", window)
        self.assertIn("类别", window)

    def test_no_new_free_task_panel_is_introduced_by_this_change(self):
        """The card-type UI must not add a parallel free-task panel/system.

        The historical isolated ``#freeTaskPanel`` prototype already exists in
        ``src/index.html`` (Q/R/S/T transition code) and is **out of scope**.
        The contract for this task is therefore a *no-new-surface* check:
        ``static/app.js`` (the file this task may edit) must not reference the
        isolated prototype at all, and the task modal must not grow a second
        free-task entry point.
        """
        self.assertNotIn(
            "freeTaskPanel",
            _read(APP_JS),
            "static/app.js must not wire the isolated free-task prototype "
            "(a second free-task system is explicitly forbidden)",
        )
        # The historical isolated prototype already loads free-task.js; this
        # task must not add *another* free-task entry point or dependency.
        script_srcs = re.findall(r'<script[^>]*src="([^"]+)"', self.html)
        free_task_scripts = [s for s in script_srcs if "free-task" in s]
        self.assertEqual(
            len(free_task_scripts),
            len(set(free_task_scripts)),
            "index.html must not gain a second free-task script dependency",
        )
        modal = re.search(
            r'<div class="modal-overlay hidden" id="taskModal">(.*?)</div>\s*</div>\s*</div>',
            self.html,
            re.S,
        )
        self.assertTrue(modal, "the task modal must exist")
        self.assertNotIn(
            "freeTaskPanel",
            modal.group(1),
            "the task modal must not embed the isolated free-task panel",
        )


# ---------------------------------------------------------------------------
# 2. Static source contract of static/app.js
# ---------------------------------------------------------------------------
class CardTypeJsSourceContractTests(unittest.TestCase):
    """Static checks over ``static/app.js`` and the ESM editor owner."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read(APP_JS)
        # AR03-G13：任务编辑器的真实实现已迁至 ESM owner
        # （static/modules/tasks/editor.js）；app.js 只保留
        # normalizeCardType / 任务数据加载 / 任务卡渲染 / deleteTask。
        cls.editor_js = _read(EDITOR_JS)

    def test_normalize_card_type_is_defined(self):
        self.assertIn("function normalizeCardType(", self.js)
        self.assertIn("function cardTypeLabel(", self.js)

    def test_normalize_card_type_falls_back_to_standard(self):
        body = _function_body(self.js, "normalizeCardType")
        self.assertTrue(body, "normalizeCardType must exist")
        self.assertRegex(body, r"'standard'")
        self.assertRegex(body, r"typeof\s+\w+\s*!==\s*'string'")

    def test_card_type_labels_mapping_is_static_and_complete(self):
        body = _function_body(self.js, "cardTypeLabel")
        self.assertTrue(body, "cardTypeLabel must exist")
        # Labels must come from the static table, never from user input.
        self.assertRegex(body, r"CARD_TYPE_LABELS")

    def test_card_corner_labels_semantics_preserved(self):
        """CARD_CORNER_LABELS must keep its original content-category meaning."""
        m = re.search(r"var CARD_CORNER_LABELS\s*=\s*\{([^}]*)\}", self.js)
        self.assertTrue(m, "CARD_CORNER_LABELS must still exist")
        body = m.group(1)
        for key in ("study", "exercise", "work", "life", "other"):
            self.assertIn(key, body, f"CARD_CORNER_LABELS must keep {key!r}")
        for forbidden in ("free", "micro", "goal", "standard"):
            self.assertNotIn(
                forbidden,
                body,
                f"CARD_CORNER_LABELS is the content-category map; {forbidden!r} "
                "must not be added to it",
            )

    def test_render_drawn_card_shows_both_category_and_card_type(self):
        body = _function_body(self.js, "renderDrawnCard")
        self.assertTrue(body, "renderDrawnCard must exist")
        self.assertIn("cardTypeLabel(", body)
        self.assertIn("task.category", body)
        # The card type badge must be rendered as its own element.
        self.assertRegex(body, r"title=\"卡类型\"")

    def test_render_drawn_card_escapes_card_type_label(self):
        body = _function_body(self.js, "renderDrawnCard")
        self.assertRegex(
            body,
            r"escapeHtml\(\s*cardType\s*\)",
            "the card-type badge text must be escaped via escapeHtml()",
        )

    def test_render_drawn_card_does_not_use_raw_task_type_in_html(self):
        body = _function_body(self.js, "renderDrawnCard")
        offenders = re.findall(r"innerHTML[^;]{0,400}?\+\s*task\.task_type", body)
        self.assertEqual(
            offenders, [],
            "raw task.task_type must never be concatenated into HTML, got " + repr(offenders),
        )
        offenders2 = re.findall(r"onclick[^;]{0,200}task\.task_type", body)
        self.assertEqual(
            offenders2, [],
            "task.task_type must never be used inside an onclick handler, got " + repr(offenders2),
        )

    def test_save_task_omits_task_type_for_unchanged_legacy_cards(self):
        # AR03-G13：saveTask 的真实实现已迁至 ESM owner。
        body = _function_body(self.editor_js, "saveTask")
        self.assertTrue(body, "saveTask must exist in the ESM editor owner")
        self.assertIn("task_type", body)
        self.assertIn("originalCardType", body)

    def test_editor_owner_is_the_only_task_editor_implementation(self):
        """classic 层不得再保留任务编辑器的影子实现。"""
        for name in (
            "openTaskEdit",
            "buildDepList",
            "saveTask",
            "deleteCurrentTask",
            "addTagChip",
            "setCardTypeSelect",
            "getCardTypeSelect",
            "loadNoteOptionsForTaskModal",
            "toggleExistingTag",
            "readSelectedPrereqs",
            "validatePrereqsLocal",
        ):
            self.assertEqual(
                _function_body(self.js, name),
                "",
                f"static/app.js must not keep a shadow implementation of {name}()",
            )
            self.assertTrue(
                _function_body(self.editor_js, name),
                f"static/modules/tasks/editor.js must implement {name}()",
            )
        # normalizeCardType 必须仍然只存在于 classic 层（唯一实现）。
        self.assertTrue(_function_body(self.js, "normalizeCardType"))
        self.assertEqual(_function_body(self.editor_js, "normalizeCardType"), "")

    def test_bootstrap_fail_closed_gate_untouched(self):
        """The Bootstrap 423 lock must remain fail-closed (no bypass added)."""
        bootstrap = _read(PROJECT_ROOT / "static" / "bootstrap-first-card.js")
        self.assertIn("LOCKED_STATUS_CODE", (PROJECT_ROOT / "server" / "services" / "agent_policy.py").read_text(encoding="utf-8"))
        self.assertIn("bootstrap-locked", bootstrap)
        self.assertIn("'/api/tasks'", bootstrap)
        # The frontend must not add a way around the lock.
        self.assertNotIn(
            "__salBootstrapGuard",
            self.js,
            "static/app.js must not disable or bypass the bootstrap write guard",
        )
        self.assertNotIn(
            "SAL_BOOTSTRAP",
            self.js,
            "static/app.js must not manipulate the bootstrap lock state",
        )

    def test_free_card_ui_does_not_promise_25_55_mode(self):
        """Free cards must not claim the 25/55 auto-duration mode exists yet."""
        body = _function_body(self.js, "renderDrawnCard")
        self.assertNotIn(
            "自由卡模式已实现",
            body,
            "the free-card badge must not claim the 25/55 mode is implemented",
        )
        self.assertIn(
            "即将上线",
            body,
            "the free-card notice must say the 25/55 mode is not yet available",
        )


# ---------------------------------------------------------------------------
# 3. Behavioural tests in the Node DOM sandbox
# ---------------------------------------------------------------------------
class CardTypeBehaviourSandboxTests(_SandboxCase):
    """Execute the real ``static/app.js`` against a synthetic DOM."""

    def test_normalize_card_type_keeps_only_four_formal_values(self):
        result = self.sandbox(
            """
            const kept = ['standard', 'free', 'micro', 'goal'];
            const legacy = ['normal', 'other', 'daily', 'weekly', 'accumulation',
              'deadline', 'note', 'exercise', 'note_review', 'chapter_review',
              'chapter_exam', 'exam_question', 'exam_review', '', '   ',
              'FREE', 'Free', ' goal', 'free ', 'unknown_value', '未知',
              '__proto__', 'constructor', 'toString', 'hasOwnProperty'];
            results.kept = kept.map((v) => app.normalizeCardType(v));
            results.legacy = legacy.map((v) => app.normalizeCardType(v));
            results.nonStrings = [
              app.normalizeCardType(null),
              app.normalizeCardType(undefined),
              app.normalizeCardType(42),
              app.normalizeCardType(true),
              app.normalizeCardType({}),
              app.normalizeCardType(['free']),
            ];
            """
        )
        self.assertEqual(
            result["kept"], list(CARD_TYPE_VALUES),
            "the four formal lowercase values must be preserved verbatim",
        )
        self.assertTrue(
            all(v == "standard" for v in result["legacy"]),
            "every legacy/unknown value must normalise to standard, got " + repr(result["legacy"]),
        )
        self.assertTrue(
            all(v == "standard" for v in result["nonStrings"]),
            "non-string values must normalise to standard, got " + repr(result["nonStrings"]),
        )

    def test_card_type_label_is_static_and_injection_safe(self):
        result = self.sandbox(
            """
            results.labels = ['standard', 'free', 'micro', 'goal']
              .map((v) => app.cardTypeLabel(v));
            results.hostile = app.cardTypeLabel('<script>alert(1)</script>');
            results.hostile2 = app.cardTypeLabel('"><img src=x onerror=alert(1)>');
            """
        )
        self.assertEqual(result["labels"], ["标准卡", "自由卡", "微型卡", "目标卡"])
        self.assertEqual(result["hostile"], "标准卡")
        self.assertEqual(result["hostile2"], "标准卡")
        self.assertNotIn("<", result["hostile"])
        self.assertNotIn("<", result["hostile2"])

    def test_open_task_edit_new_defaults_to_standard(self):
        result = self.sandbox(
            """
            app.allTasks = [];
            app.allTags = [];
            app.openTaskEdit(null);
            results.selectValue = dom.getElementById('tfCardType').value;
            results.original = app.window._tfOriginalCardType;
            """
        )
        self.assertEqual(result["selectValue"], "standard")
        self.assertIsNone(result["original"])

    def test_open_task_edit_legacy_card_shows_normalised_standard(self):
        result = self.sandbox(
            """
            app.allTasks = [{ id: 7, name: '旧卡', category: 'study', priority: 5,
              estimated_time: 30, task_type: 'normal', tags: [], prerequisite_ids: [] }];
            app.allTags = [];
            app.openTaskEdit(7);
            results.selectValue = dom.getElementById('tfCardType').value;
            results.original = app.window._tfOriginalCardType;
            """
        )
        self.assertEqual(result["selectValue"], "standard")
        self.assertEqual(result["original"], "standard")

    def test_open_task_edit_each_legacy_value_normalises_to_standard(self):
        result = self.sandbox(
            """
            const values = ['normal', 'other', null, undefined, '', 'daily',
              'unknown_future', '__proto__'];
            results.seen = [];
            values.forEach((v, i) => {
              app.allTasks = [{ id: 100 + i, name: 'x', category: 'study',
                priority: 5, estimated_time: 30, task_type: v, tags: [],
                prerequisite_ids: [] }];
              app.allTags = [];
              app.openTaskEdit(100 + i);
              results.seen.push(dom.getElementById('tfCardType').value);
            });
            """
        )
        self.assertTrue(
            all(v == "standard" for v in result["seen"]),
            "every legacy task_type must display as standard, got " + repr(result["seen"]),
        )

    def test_save_task_new_submits_legal_task_type(self):
        result = self.sandbox(
            """
            dom.getElementById('tfId').value = '';
            dom.getElementById('tfName').value = '新任务';
            dom.getElementById('tfCardType').value = 'free';
            app.allTasks = [];
            app.allTags = [];
            app.openTaskEdit(null);
            dom.getElementById('tfName').value = '新任务';
            dom.getElementById('tfCardType').value = 'free';
            await app.saveTask();
            const post = calls.filter((c) => c.method === 'POST' && c.url === '/api/tasks');
            results.count = post.length;
            results.body = post.length ? post[0].body : null;
            """
        )
        self.assertEqual(result["count"], 1, "saveTask must POST exactly once")
        body = result["body"]
        self.assertIsNotNone(body)
        self.assertEqual(
            body.get("task_type"),
            "free",
            "creating a task must submit the selected legal task_type",
        )
        self.assertIn(body.get("task_type"), CARD_TYPE_VALUES)

    def test_save_task_new_defaults_to_standard_task_type(self):
        result = self.sandbox(
            """
            app.allTasks = [];
            app.allTags = [];
            app.openTaskEdit(null);
            dom.getElementById('tfName').value = '默认类型';
            await app.saveTask();
            const post = calls.filter((c) => c.method === 'POST' && c.url === '/api/tasks');
            results.body = post.length ? post[0].body : null;
            """
        )
        self.assertEqual(result["body"].get("task_type"), "standard")

    def test_save_task_edit_legacy_card_omits_task_type(self):
        result = self.sandbox(
            """
            app.allTasks = [{ id: 7, name: '旧卡', category: 'study', priority: 5,
              estimated_time: 30, task_type: 'normal', tags: [], prerequisite_ids: [] }];
            app.allTags = [];
            app.openTaskEdit(7);
            dom.getElementById('tfName').value = '旧卡改个名';
            await app.saveTask();
            const put = calls.filter((c) => c.method === 'PUT' && /\\/api\\/tasks\\//.test(c.url));
            results.count = put.length;
            results.body = put.length ? put[0].body : null;
            """
        )
        self.assertEqual(result["count"], 1, "saveTask must PUT exactly once")
        body = result["body"]
        self.assertNotIn(
            "task_type",
            body,
            "editing a legacy card without changing the type must OMIT task_type "
            "(otherwise a legacy 'normal' row would be silently rewritten to 'standard')",
        )
        self.assertEqual(body.get("name"), "旧卡改个名")

    def test_save_task_edit_when_user_changes_type_submits_task_type(self):
        result = self.sandbox(
            """
            app.allTasks = [{ id: 7, name: '旧卡', category: 'study', priority: 5,
              estimated_time: 30, task_type: 'normal', tags: [], prerequisite_ids: [] }];
            app.allTags = [];
            app.openTaskEdit(7);
            dom.getElementById('tfName').value = '改成自由卡';
            dom.getElementById('tfCardType').value = 'free';
            await app.saveTask();
            const put = calls.filter((c) => c.method === 'PUT' && /\\/api\\/tasks\\//.test(c.url));
            results.body = put.length ? put[0].body : null;
            """
        )
        self.assertEqual(
            result["body"].get("task_type"),
            "free",
            "when the user genuinely changes the type, task_type must be submitted",
        )

    def test_save_task_edit_can_change_legacy_card_to_each_new_type(self):
        result = self.sandbox(
            """
            const targets = ['free', 'micro', 'goal'];
            results.bodies = [];
            for (const target of targets) {
              calls.length = 0;
              app.allTasks = [{ id: 9, name: '普通任务', category: 'study',
                priority: 5, estimated_time: 30, task_type: 'other', tags: [],
                prerequisite_ids: [] }];
              app.allTags = [];
              app.openTaskEdit(9);
              dom.getElementById('tfName').value = '普通任务';
              dom.getElementById('tfCardType').value = target;
              await app.saveTask();
              const put = calls.filter((c) => c.method === 'PUT');
              results.bodies.push(put.length ? put[0].body.task_type : null);
            }
            """
        )
        self.assertEqual(result["bodies"], ["free", "micro", "goal"])

    def test_save_task_edit_keeps_existing_type_when_unchanged(self):
        """A card already stored as 'free' must not be re-submitted as 'standard'."""
        result = self.sandbox(
            """
            app.allTasks = [{ id: 11, name: '自由卡', category: 'study', priority: 5,
              estimated_time: 30, task_type: 'free', tags: [], prerequisite_ids: [] }];
            app.allTags = [];
            app.openTaskEdit(11);
            dom.getElementById('tfName').value = '自由卡';
            await app.saveTask();
            const put = calls.filter((c) => c.method === 'PUT');
            results.body = put.length ? put[0].body : null;
            """
        )
        self.assertNotIn(
            "task_type",
            result["body"],
            "an unchanged 'free' card must not have task_type submitted (it would "
            "otherwise be rewritten to the displayed 'free' — harmless here, but the "
            "contract is to omit when unchanged)",
        )

    def test_backend_400_is_surfaced_via_toast(self):
        result = self.sandbox(
            """
            fetchResponses.set('/api/tasks', { ok: false, status: 400,
              body: { error: 'task_type must be one of: standard, free, micro, goal' } });
            app.allTasks = [];
            app.allTags = [];
            app.openTaskEdit(null);
            dom.getElementById('tfName').value = '坏类型';
            dom.getElementById('tfCardType').value = 'free';
            await app.saveTask();
            const toastEl = dom.getElementById('toastContainer');
            results.toasts = toastEl.children.map((c) => c.textContent);
            results.modalHidden = dom.getElementById('taskModal').classList.contains('hidden');
            """
        )
        self.assertTrue(
            any("task_type must be one of" in (t or "") for t in result["toasts"]),
            "a backend 400 must be surfaced to the user via the existing toast, got "
            + repr(result["toasts"]),
        )
        self.assertFalse(
            result["modalHidden"],
            "the modal must stay open when the save failed",
        )

    def test_render_drawn_card_shows_both_category_and_card_type(self):
        result = self.sandbox(
            """
            const mk = (task_type, category) => ({
              id: 3, name: '卡面任务', description: '描述', category: category || 'study',
              priority: 5, estimated_time: 25, repeat_type: 'none', tags: [],
              task_type: task_type, is_unlocked: 1
            });
            results.html = {};
            ['standard', 'free', 'micro', 'goal'].forEach((t) => {
              const stage = app.renderDrawnCard(mk(t), 0);
              const card = stage.children[0];
              results.html[t] = card.innerHTML;
              results.attrs = results.attrs || {};
              results.attrs[t] = card.getAttribute('data-card-type');
            });
            const legacyStage = app.renderDrawnCard(mk('normal'), 0);
            results.html.legacy = legacyStage.children[0].innerHTML;
            """
        )
        html_by_type = result["html"]
        for value in CARD_TYPE_VALUES:
            html = html_by_type[value]
            self.assertIn(
                {"standard": "标准卡", "free": "自由卡", "micro": "微型卡", "goal": "目标卡"}[value],
                html,
                f"drawn card must show the {value} card-type badge",
            )
            self.assertIn(
                "学习",
                html,
                f"drawn card must still show the content-category badge for {value}",
            )
        self.assertIn("标准卡", html_by_type["legacy"])
        self.assertIn("学习", html_by_type["legacy"])

    def test_render_drawn_card_escapes_hostile_task_type(self):
        result = self.sandbox(
            """
            const hostile = '<script>alert(1)</script>';
            const stage = app.renderDrawnCard({
              id: 4, name: 'x', description: 'd', category: 'study', priority: 5,
              estimated_time: 25, repeat_type: 'none', tags: [], task_type: hostile
            }, 0);
            results.html = stage.children[0].innerHTML;
            results.attr = stage.children[0].getAttribute('data-card-type');
            """
        )
        html = result["html"]
        self.assertNotIn("<script>", html, "hostile task_type must not be injected")
        self.assertNotIn("alert(1)", html.replace("&lt;", "<"), "hostile payload must be escaped")
        self.assertIn("标准卡", html)
        self.assertEqual(result["attr"], "standard")

    def test_render_drawn_card_uses_data_attr_not_raw_type_in_onclick(self):
        result = self.sandbox(
            """
            const stage = app.renderDrawnCard({
              id: 5, name: 'x', description: 'd', category: 'study', priority: 5,
              estimated_time: 25, repeat_type: 'none', tags: [], task_type: 'free'
            }, 0);
            results.html = stage.children[0].innerHTML;
            """
        )
        html = result["html"]
        self.assertNotIn("task_type", html, "the raw task_type field must not leak into HTML")
        self.assertRegex(html, r"onclick=\"startTask\(\d+\)\"")

    def test_task_list_card_shows_card_type_badge(self):
        result = self.sandbox(
            """
            results.html = app.buildTaskCardHtml({
              id: 6, name: '列表任务', description: 'd', category: 'exercise',
              priority: 5, estimated_time: 25, repeat_type: 'none', tags: [],
              task_type: 'micro', is_unlocked: 1
            }, {});
            """
        )
        html = result["html"]
        self.assertIn("微型卡", html)
        self.assertIn("运动", html)


if __name__ == "__main__":
    unittest.main()
