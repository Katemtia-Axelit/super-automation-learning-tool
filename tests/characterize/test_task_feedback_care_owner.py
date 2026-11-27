# -*- coding: utf-8 -*-
"""AR03-G15.2：反馈 / 关怀 owner（Feedback-Care Owner）characterization 测试。

覆盖：

1. ``static/modules/tasks/lifecycle.js`` 的**行为契约** —— 把源码复制到
   ``tempfile`` 临时目录的 ``lifecycle.mjs``，用 Node 内建能力动态 import，
   依赖全部是**合成 stub**（不触碰真实 DB / notes / 配置 / 服务）。
2. ``static/app.entry.js`` 中 ``drawGachaWithCategory`` 的**晚绑定**行为 ——
   在 Node ``vm`` 沙箱里抽取并执行真实包装函数，验证调用时读取当前值。
3. ``static/app.js`` / ``static/app.entry.js`` 的**结构约束**（源码级断言）。

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

# ---------------------------------------------------------------------------
# Node 沙箱 harness（合成依赖 + 行为探针）
# ---------------------------------------------------------------------------
_HARNESS_JS = r"""
import fs from 'node:fs';
import vm from 'node:vm';
import { createTaskLifecycleOwner } from './lifecycle.mjs';

const appEntryPath = process.argv[2];
const out = { scenarios: {}, lateBinding: {}, error: null };

function makeOwner(cfg) {
  cfg = cfg || {};
  const calls = [];
  const rec = function (name, args) { calls.push({ name: name, args: args || [] }); };
  const owner = createTaskLifecycleOwner({
    getTasks: function () { return cfg.allTasks || []; },
    getDrawnTask: function () { return null; },
    getMultiDrawResults: function () { return []; },
    getTimerOwner: function () { return Promise.reject(new Error('no timer')); },
    getCurrentTimerOwner: function () { return null; },
    api: function (url, opts) {
      rec('api', [{
        url: url,
        method: opts ? opts.method : null,
        body: opts ? opts.body : null
      }]);
      if (cfg.apiHandler) return cfg.apiHandler(url, opts);
      return Promise.resolve({});
    },
    toast: function (m, t) { rec('toast', [m, t]); },
    openFeedbackModalForTask: function (id, cat, fe) {
      rec('openFeedbackModalForTask', [id, cat, fe]);
    },
    readFeedbackEnergy: function () {
      rec('readFeedbackEnergy', []);
      return cfg.energy === undefined ? '5' : cfg.energy;
    },
    closeModal: function (id) { rec('closeModal', [id]); },
    renderFeedbackSuccess: function () { rec('renderFeedbackSuccess', []); },
    renderCareModal: function (id, cat, enc, label) {
      rec('renderCareModal', [id, cat, enc, label]);
    },
    renderCareRest: function () { rec('renderCareRest', []); },
    refreshGachaStats: function () { rec('refreshGachaStats', []); },
    drawGachaWithCategory: function (inc, exc) {
      rec('drawGachaWithCategory', [inc, exc]);
    }
  });
  return { owner: owner, calls: calls };
}

function names(calls) { return calls.map(function (c) { return c.name; }); }
function pick(calls, name) {
  return calls.filter(function (c) { return c.name === name; })
    .map(function (c) { return c.args; });
}

async function main() {
  // --- 1. 打开反馈：复位状态 + 调用 DOM 适配器 ---------------------------
  {
    const h = makeOwner({});
    h.owner.openFeedback(7, 'study', false);
    const h2 = makeOwner({});
    h2.owner.openFeedback(8, undefined, undefined);
    out.scenarios.open = {
      steps: names(h.calls),
      domCalls: pick(h.calls, 'openFeedbackModalForTask'),
      ctx: h.owner.getFeedbackContext(),
      mood: h.owner.getMood(),
      ctxNullCategory: h2.owner.getFeedbackContext(),
      domCallsNullCategory: pick(h2.calls, 'openFeedbackModalForTask')
    };
  }

  // --- 2. 成功提交：endpoint / payload / 顺序 / finishEarly --------------
  {
    const h = makeOwner({ energy: '7' });
    h.owner.openFeedback(7, 'study', false);
    h.owner.setMood(4);
    await h.owner.submitFeedback();
    out.scenarios.submit_ok = {
      steps: names(h.calls),
      api: pick(h.calls, 'api'),
      closeModal: pick(h.calls, 'closeModal'),
      ctx: h.owner.getFeedbackContext(),
      care: h.owner.getCareContext()
    };

    const h2 = makeOwner({ energy: '5' });
    h2.owner.openFeedback(9, null, true);
    await h2.owner.submitFeedback();
    out.scenarios.submit_finish_early = {
      steps: names(h2.calls),
      api: pick(h2.calls, 'api')
    };

    // 非法精力值回退 5；非法心情回退 3。
    const h3 = makeOwner({ energy: 'abc' });
    h3.owner.openFeedback(11, 'life', false);
    h3.owner.setMood(99);
    await h3.owner.submitFeedback();
    out.scenarios.submit_invalid_values = {
      api: pick(h3.calls, 'api'),
      mood: h3.owner.getMood()
    };

    // 没有上下文：关闭 modal 且不发请求。
    const h4 = makeOwner({});
    await h4.owner.submitFeedback();
    out.scenarios.submit_no_context = {
      steps: names(h4.calls),
      api: pick(h4.calls, 'api')
    };
  }

  // --- 3. 提交失败：解锁 / toast / 保留上下文 / 可重试 --------------------
  {
    let mode = 'fail';
    const h = makeOwner({
      apiHandler: function () {
        if (mode === 'fail') return Promise.reject(new Error('boom'));
        return Promise.resolve({ ok: true });
      }
    });
    h.owner.openFeedback(21, 'work', false);
    await h.owner.submitFeedback();
    out.scenarios.submit_failed = {
      steps: names(h.calls),
      toasts: pick(h.calls, 'toast'),
      apiCount: pick(h.calls, 'api').length,
      ctx: h.owner.getFeedbackContext(),
      care: h.owner.getCareContext()
    };
    mode = 'ok';
    await h.owner.submitFeedback();
    out.scenarios.submit_retry = {
      steps: names(h.calls),
      apiCount: pick(h.calls, 'api').length,
      api: pick(h.calls, 'api')
    };
  }

  // --- 4. 重入：第一次 POST 未完成时，第二次提交不产生第二个请求 ----------
  {
    let resolveFn = null;
    const h = makeOwner({
      apiHandler: function () {
        return new Promise(function (res) { resolveFn = res; });
      }
    });
    h.owner.openFeedback(31, 'study', false);
    const first = h.owner.submitFeedback();
    const second = h.owner.submitFeedback();
    await second;
    out.scenarios.reentry = {
      apiCountDuringPending: pick(h.calls, 'api').length,
      steps: names(h.calls)
    };
    resolveFn({ ok: true });
    await first;
    out.scenarios.reentry.apiCountAfterResolve = pick(h.calls, 'api').length;
  }

  // --- 5. 取消：零请求 + 关闭反馈 + 打开关怀 ------------------------------
  {
    const h = makeOwner({});
    h.owner.openFeedback(41, 'exercise', false);
    await h.owner.cancelFeedback();
    out.scenarios.cancel = {
      steps: names(h.calls),
      api: pick(h.calls, 'api'),
      closeModal: pick(h.calls, 'closeModal'),
      care: pick(h.calls, 'renderCareModal'),
      careCtx: h.owner.getCareContext(),
      fbCtx: h.owner.getFeedbackContext()
    };

    // 无上下文时取消：不报错、不请求。
    const h2 = makeOwner({});
    await h2.owner.cancelFeedback();
    out.scenarios.cancel_no_context = {
      steps: names(h2.calls),
      api: pick(h2.calls, 'api')
    };
  }

  // --- 6. 关怀三选项 ------------------------------------------------------
  {
    const h = makeOwner({});
    h.owner.openFeedback(51, 'study', false);
    await h.owner.cancelFeedback();
    h.owner.careSameCategory();
    out.scenarios.care_same = {
      draw: pick(h.calls, 'drawGachaWithCategory'),
      closeModal: pick(h.calls, 'closeModal'),
      careCtx: h.owner.getCareContext()
    };

    const h2 = makeOwner({});
    h2.owner.openFeedback(52, 'study', false);
    await h2.owner.cancelFeedback();
    h2.owner.careSwitchCategory();
    out.scenarios.care_switch = {
      draw: pick(h2.calls, 'drawGachaWithCategory'),
      closeModal: pick(h2.calls, 'closeModal'),
      careCtx: h2.owner.getCareContext()
    };

    const h3 = makeOwner({});
    h3.owner.openFeedback(53, 'study', false);
    await h3.owner.cancelFeedback();
    h3.owner.careRest();
    out.scenarios.care_rest = {
      steps: names(h3.calls),
      draw: pick(h3.calls, 'drawGachaWithCategory'),
      rest: pick(h3.calls, 'renderCareRest'),
      closeModal: pick(h3.calls, 'closeModal'),
      careCtx: h3.owner.getCareContext()
    };

    // 缺少科目：无科目信息提示，但仍抽卡（null / null）。
    const h4 = makeOwner({});
    h4.owner.openFeedback(54, null, false);
    await h4.owner.cancelFeedback();
    h4.owner.careSameCategory();
    out.scenarios.care_same_missing_category = {
      draw: pick(h4.calls, 'drawGachaWithCategory'),
      toasts: pick(h4.calls, 'toast')
    };

    // 关怀文案与科目标签由 owner 选定。
    const h5 = makeOwner({});
    h5.owner.openFeedback(55, 'study', false);
    await h5.owner.cancelFeedback();
    out.scenarios.care_render = { care: pick(h5.calls, 'renderCareModal') };
  }

  // --- 7. 晚绑定：app.entry.js 的 drawGachaWithCategory 包装 -------------
  {
    const src = fs.readFileSync(appEntryPath, 'utf-8');
    const marker = 'drawGachaWithCategory:';
    const midx = src.indexOf(marker);
    let wrapperSrc = null;
    if (midx >= 0) {
      const fidx = src.indexOf('function', midx);
      const bstart = src.indexOf('{', fidx);
      let depth = 0;
      let j = bstart;
      for (; j < src.length; j += 1) {
        if (src[j] === '{') depth += 1;
        else if (src[j] === '}') {
          depth -= 1;
          if (depth === 0) break;
        }
      }
      wrapperSrc = src.slice(fidx, j + 1);
    }
    const seen = [];
    const fakeWindow = {
      drawGachaWithCategory: function (a, b) { seen.push(['A', a, b]); }
    };
    const ctx = vm.createContext({ window: fakeWindow });
    let firstCalls = [];
    let secondCalls = [];
    let nonFunctionOk = false;
    if (wrapperSrc) {
      const wrapper = vm.runInContext('(' + wrapperSrc + ')', ctx);
      wrapper('i1', 'x1');
      firstCalls = seen.slice();
      fakeWindow.drawGachaWithCategory = function (a, b) { seen.push(['B', a, b]); };
      wrapper('i2', 'x2');
      secondCalls = seen.slice();
      fakeWindow.drawGachaWithCategory = 42;
      try {
        wrapper('i3', 'x3');
        nonFunctionOk = true;
      } catch (e) {
        nonFunctionOk = false;
      }
    }
    out.lateBinding = {
      found: !!wrapperSrc,
      firstCalls: firstCalls,
      secondCalls: secondCalls,
      nonFunctionSafe: nonFunctionOk
    };
  }
}

main().then(function () {
  process.stdout.write(JSON.stringify(out));
}).catch(function (e) {
  out.error = (e && e.stack) ? e.stack : String(e);
  process.stdout.write(JSON.stringify(out));
});
"""


class FeedbackCareOwnerTest(unittest.TestCase):
    """G15.2 反馈 / 关怀 owner 的行为与边界契约。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="lt_g15_2_fbcare_")
        try:
            shutil.copyfile(str(LIFECYCLE_JS), os.path.join(cls._tmp, "lifecycle.mjs"))
            harness = os.path.join(cls._tmp, "harness.mjs")
            with open(harness, "w", encoding="utf-8") as fh:
                fh.write(_HARNESS_JS)
            proc = subprocess.run(
                ["node", harness, str(APP_ENTRY_JS)],
                cwd=cls._tmp,
                capture_output=True,
                text=True,
                timeout=120,
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

    # -- 1. 打开反馈 -------------------------------------------------------
    def test_open_feedback_resets_state_and_calls_dom_adapter(self):
        s = self.scenarios()["open"]
        self.assertEqual([[7, "study", False]], s["domCalls"],
                         "owner 必须在存好上下文后调用 DOM 适配器，参数保持不变")
        self.assertEqual(
            {"taskId": 7, "category": "study", "finishEarly": False},
            s["ctx"],
            "owner 必须持有唯一的反馈上下文",
        )
        self.assertEqual(3, s["mood"], "打开反馈时心情必须复位为 3")
        self.assertEqual([[8, None, False]], s["domCallsNullCategory"],
                         "缺失科目必须归一为 null")
        self.assertIsNone(s["ctxNullCategory"]["category"])

    # -- 2. 成功提交 -------------------------------------------------------
    def test_successful_submit_endpoint_payload_and_order(self):
        s = self.scenarios()["submit_ok"]
        self.assertEqual(1, len(s["api"]))
        call = s["api"][0][0]
        self.assertEqual("/api/tasks/7/feedback", call["url"])
        self.assertEqual("POST", call["method"])
        body = json.loads(call["body"])
        self.assertEqual({"energy_after": 7, "mood_after": 4}, body,
                         "提交体必须只有 energy_after / mood_after 两个字段")
        steps = s["steps"]
        self.assertLess(steps.index("api"), steps.index("closeModal"))
        self.assertLess(steps.index("closeModal"), steps.index("renderFeedbackSuccess"))
        self.assertLess(steps.index("renderFeedbackSuccess"), steps.index("refreshGachaStats"))
        self.assertLess(steps.index("refreshGachaStats"), steps.index("renderCareModal"))
        self.assertIsNone(s["ctx"], "成功提交后反馈上下文必须被消费")
        self.assertEqual({"taskId": 7, "category": "study"}, s["care"],
                         "成功提交后必须带着上下文进入关怀")

    def test_submit_finish_early_adds_event_type(self):
        s = self.scenarios()["submit_finish_early"]
        body = json.loads(s["api"][0][0]["body"])
        self.assertEqual(5, body["energy_after"])
        self.assertEqual(3, body["mood_after"])
        self.assertEqual("finish_early", body["event_type"],
                         "finishEarly 为真时必须上报 event_type=finish_early")

    def test_invalid_energy_and_mood_fall_back(self):
        s = self.scenarios()["submit_invalid_values"]
        body = json.loads(s["api"][0][0]["body"])
        self.assertEqual(5, body["energy_after"], "非法精力必须回退 5")
        self.assertEqual(3, body["mood_after"], "非法心情必须回退 3")

    def test_submit_without_context_closes_modal_and_does_not_post(self):
        s = self.scenarios()["submit_no_context"]
        self.assertEqual([], s["api"], "缺少上下文不得发请求")
        self.assertIn("closeModal", s["steps"], "缺少上下文时必须关闭反馈 modal")

    # -- 3. 失败提交 -------------------------------------------------------
    def test_failed_submit_keeps_modal_and_context_and_allows_retry(self):
        s = self.scenarios()["submit_failed"]
        self.assertEqual(1, s["apiCount"])
        self.assertEqual(1, len(s["toasts"]))
        self.assertEqual("err", s["toasts"][0][1], "失败必须 toast 错误")
        self.assertNotIn("closeModal", s["steps"], "失败时必须保持反馈 modal 打开")
        self.assertNotIn("renderCareModal", s["steps"], "失败时不得进入关怀流程")
        self.assertIsNotNone(s["ctx"], "失败时必须保留上下文")
        self.assertIsNone(s["care"], "失败时不得写入关怀上下文")

        r = self.scenarios()["submit_retry"]
        self.assertEqual(2, r["apiCount"], "失败后必须解锁，允许再次提交")
        self.assertIn("renderCareModal", r["steps"], "重试成功后必须进入关怀")

    # -- 4. 重入 -----------------------------------------------------------
    def test_reentry_does_not_issue_second_post(self):
        s = self.scenarios()["reentry"]
        self.assertEqual(1, s["apiCountDuringPending"],
                         "第一次 POST 未完成时的第二次提交必须是 no-op")
        self.assertEqual(1, s["apiCountAfterResolve"])

    # -- 5. 取消 -----------------------------------------------------------
    def test_cancel_performs_no_post_and_opens_care(self):
        s = self.scenarios()["cancel"]
        self.assertEqual([], s["api"], "取消必须是零网络请求")
        self.assertIn(["feedbackModal"], s["closeModal"], "取消必须关闭反馈 modal")
        self.assertEqual(1, len(s["care"]))
        self.assertEqual(41, s["care"][0][0])
        self.assertEqual("exercise", s["care"][0][1])
        self.assertIsNone(s["fbCtx"], "取消后反馈上下文必须被清空")
        self.assertEqual({"taskId": 41, "category": "exercise"}, s["careCtx"])

        n = self.scenarios()["cancel_no_context"]
        self.assertEqual([], n["api"])
        self.assertNotIn("renderCareModal", n["steps"])

    # -- 6. 关怀三选项 -----------------------------------------------------
    def test_care_same_category_draws_with_same_category(self):
        s = self.scenarios()["care_same"]
        self.assertEqual([["study", None]], s["draw"])
        self.assertIn(["careModal"], s["closeModal"])
        self.assertIsNone(s["careCtx"], "关怀上下文必须被清空")

    def test_care_switch_category_draws_without_same_category(self):
        s = self.scenarios()["care_switch"]
        self.assertEqual([[None, "study"]], s["draw"])
        self.assertIn(["careModal"], s["closeModal"])

    def test_care_rest_renders_rest_message_without_draw(self):
        s = self.scenarios()["care_rest"]
        self.assertEqual([], s["draw"], "休息不得抽卡")
        self.assertEqual(1, len(s["rest"]), "休息必须渲染既有休息文案")
        self.assertIn(["careModal"], s["closeModal"])

    def test_care_same_category_without_category_still_draws(self):
        s = self.scenarios()["care_same_missing_category"]
        self.assertEqual([[None, None]], s["draw"], "缺少科目时仍然抽卡（null/null）")
        self.assertEqual(1, len(s["toasts"]), "缺少科目时必须给出提示")
        self.assertEqual("inf", s["toasts"][0][1])

    def test_care_render_uses_owner_selected_text_and_label(self):
        s = self.scenarios()["care_render"]
        args = s["care"][0]
        self.assertEqual(55, args[0])
        self.assertEqual("study", args[1])
        encourages = [
            "太棒了！又完成了一项挑战！",
            "坚持就是胜利，你真棒！",
            "今天的你比昨天更优秀！",
            "小步快跑，大目标在前方等你！",
            "完成就是进步，继续加油！",
        ]
        self.assertIn(args[2], encourages, "必须使用既有五句关怀文案之一")
        self.assertEqual("学习", args[3], "科目标签映射必须保持不变")

    # -- 7. 晚绑定 ---------------------------------------------------------
    def test_draw_gacha_with_category_is_late_bound(self):
        lb = self.result["lateBinding"]
        self.assertTrue(lb["found"], "app.entry.js 必须注入 drawGachaWithCategory")
        self.assertEqual([["A", "i1", "x1"]], lb["firstCalls"],
                         "首次调用必须使用当时的实现")
        self.assertEqual(
            [["A", "i1", "x1"], ["B", "i2", "x2"]],
            lb["secondCalls"],
            "替换底层实现后必须调用新函数（晚绑定，不得捕获过期函数值）",
        )
        self.assertTrue(lb["nonFunctionSafe"],
                        "底层值不是函数时必须安全 no-op")

    # -- 8. 静态边界 -------------------------------------------------------
    def test_lifecycle_js_has_no_dom_or_global_access(self):
        src = LIFECYCLE_JS.read_text(encoding="utf-8")
        for token in ("window", "document", "globalThis"):
            self.assertNotIn(
                token, src,
                "lifecycle.js 不得出现 %s（DOM / 全局访问必须经注入适配器）" % token,
            )

    def test_app_js_no_longer_owns_feedback_care_business_state(self):
        src = APP_JS.read_text(encoding="utf-8")
        for token in (
            "_feedbackContext",
            "_pendingFeedbackSubmit",
            "feedbackMood",
            "_careContext",
            "CARE_ENCOURAGES",
            "CARE_CATEGORY_LABELS",
        ):
            self.assertNotIn(
                token, src,
                "app.js 不得再持有反馈 / 关怀业务状态或文案常量：%s" % token,
            )

    def test_app_js_keeps_dom_adapters_and_owner_facades(self):
        src = APP_JS.read_text(encoding="utf-8")
        for name in (
            "openFeedbackModalForTask",
            "readFeedbackEnergy",
            "renderFeedbackSuccess",
            "showCareModal",
            "renderCareRest",
            "submitFeedback",
            "cancelFeedback",
            "setMood",
            "transitionToCareModal",
            "careSameCategory",
            "careSwitchCategory",
            "careRest",
        ):
            self.assertRegex(
                src,
                r"function\s+" + re.escape(name) + r"\s*\(",
                "app.js 必须保留入口名 %s（HTML inline handler 依赖）" % name,
            )
        self.assertNotIn(
            "/api/tasks/' + taskId + '/feedback",
            src,
            "app.js 不得再直接 POST 反馈端点（业务归 owner）",
        )

    def test_app_entry_injects_feedback_care_adapters(self):
        src = APP_ENTRY_JS.read_text(encoding="utf-8")
        for token in (
            "readFeedbackEnergy",
            "openFeedbackModalForTask",
            "closeModal",
            "renderFeedbackSuccess",
            "renderCareModal",
            "renderCareRest",
            "refreshGachaStats",
            "api:",
            "toast:",
            "drawGachaWithCategory",
        ):
            self.assertIn(token, src, "app.entry.js 必须注入 %s" % token)
        self.assertIn(
            "window.drawGachaWithCategory",
            src,
            "drawGachaWithCategory 必须晚绑定（调用时读取 window 上的当前值）",
        )
        self.assertIn(
            "get: function () { return taskLifecycleOwner; }",
            src,
            "window.__taskLifecycleOwner 必须保持只读 getter",
        )


if __name__ == "__main__":
    unittest.main()
