"""AR03-P3-D：**只读派生映射**（``SAL.core.state.createDerivedMap``）契约测试。

背景（真实功能回归）
--------------------
P3-D 让 ``core/state.js::createDerivedMap`` 首次 **真实启用**（用途：任务
id → 任务名称的轻量派生映射）。首次实现里有一个**极隐蔽**的 bug：

```js
const opts = options || {};
const valueOf = typeof opts.valueOf === 'function'
  ? opts.valueOf
  : function (item) { return item && item.name; };
```

``options`` 为 ``undefined`` → ``opts = {}`` → ``opts.valueOf`` **继承自
``Object.prototype``**，而 ``Object.prototype.valueOf`` **本身就是一个
函数**！于是 ``typeof opts.valueOf === 'function'`` 判定通过，取值器变成
``Object.prototype.valueOf``。

后果：``Object.prototype.valueOf.call(null)`` 抛
``TypeError: Cannot convert undefined or null to object`` → 任务列表渲染
（``renderTasks`` → ``prereqHint`` → ``taskNameById`` → ``map.refresh()``）
**整体抛错** → 任务卡片渲染不出来。

同时它也解释了「`Object.keys` 出现在栈顶」的迷惑现象：真正的抛点是
派生映射内部对 ``null`` 项的取值。

修复
----
``keyOf`` / ``valueOf`` 的判定必须用 **自有属性**（``hasOwnProperty``），
不能用 ``typeof`` —— 因为原型链上的内置方法同样是函数。

保护边界
--------
本文件 **只读** 仓库；只在 ``tempfile`` 临时目录里写 Node 脚本；
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
STATE_JS = STATIC_ROOT / "core" / "state.js"
APP_JS = STATIC_ROOT / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_js_comments(source: str) -> str:
    """剥离 JS 行注释与块注释（保留字符串字面量里的内容）。

    用于「源码里 **不得** 出现某种写法」这类断言 —— 注释里出现是允许的
    （注释常用来解释为什么不能那样写）。
    """
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                out.append(source[i])
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i + 1])
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# A. 静态契约：不得用 typeof 判定 keyOf / valueOf
# ---------------------------------------------------------------------------
class DerivedMapOptionGuardTests(unittest.TestCase):
    """``createDerivedMap`` 的选项判定必须用 **自有属性** 判定。"""

    @classmethod
    def setUpClass(cls):
        cls.state_source = _read(STATE_JS)

    def test_derived_map_exists(self):
        self.assertIn(
            "createDerivedMap",
            self.state_source,
            "core/state.js 必须提供 createDerivedMap（只读派生映射）",
        )

    def test_option_accessors_must_use_has_own_property(self):
        """``keyOf`` / ``valueOf`` 必须用 hasOwnProperty 判定，不得用 typeof。"""
        self.assertIn(
            "hasOwnProperty.call(opts",
            self.state_source,
            "createDerivedMap 必须用 hasOwnProperty 判定选项（原型链上的 "
            "Object.prototype.valueOf 也是函数，typeof 判定会误判）",
        )

    def test_option_accessors_must_not_be_selected_by_typeof_alone(self):
        """取值器必须 **先判自有属性** 再判类型，不得只靠 typeof。

        正确形态：``hasValueOf && typeof opts.valueOf === 'function'``
        错误形态：``typeof opts.valueOf === 'function'``（直接三元）
        """
        code = _strip_js_comments(self.state_source)
        # 取出 createDerivedMap 的函数体（到文件末尾的 SAL 导出之前）。
        body = code.split("function createDerivedMap", 1)[-1]
        body = body.split("window.SAL = window.SAL || {};", 1)[0]

        # 正确形态必须存在：先判自有属性。
        self.assertIn(
            "hasOwnProperty.call(opts, 'valueOf')",
            body,
            "createDerivedMap 必须先判 valueOf 是否为 **自有属性**",
        )
        self.assertIn(
            "hasOwnProperty.call(opts, 'keyOf')",
            body,
            "createDerivedMap 必须先判 keyOf 是否为 **自有属性**",
        )

        # 错误形态：typeof 判定出现在三元条件里，且 **没有** 与 has* 守卫
        # 用 && 连接（守卫变量名必须出现在同一条件表达式里）。
        for accessor in ("valueOf", "keyOf"):
            pattern = re.compile(
                r"(?<!has)" + accessor + r"\s*=\s*typeof\s+opts\." + accessor + r"\s*===\s*'function'",
                re.DOTALL,
            )
            self.assertIsNone(
                pattern.search(body),
                "createDerivedMap 的 %s 不得只靠 typeof 判定（必须先判自有属性）"
                % accessor,
            )

    def test_derived_map_must_not_expose_a_writable_set(self):
        """派生映射 **绝不** 暴露 set（它不是权威状态容器）。"""
        self.assertIn(
            "createDerivedMap",
            self.state_source,
            "createDerivedMap 必须存在",
        )
        # createDerivedMap 返回的 API 里不得出现 set:
        body = self.state_source.split("function createDerivedMap", 1)[-1]
        self.assertNotIn(
            "set: set,",
            body.split("window.SAL = window.SAL || {};", 1)[0],
            "派生映射不得暴露 set（它是只读派生，不是第二状态源）",
        )


# ---------------------------------------------------------------------------
# B. 运行期契约：Node 合成页面真的跑通
# ---------------------------------------------------------------------------
class DerivedMapRuntimeTests(unittest.TestCase):
    """在 Node 合成页面里真的调用 ``createDerivedMap``，验证行为。"""

    def _run_node(self, body: str) -> dict:
        tmp = Path(tempfile.mkdtemp(prefix="sal_derived_map_"))
        try:
            script = tmp / "probe.js"
            script.write_text(
                "const fs = require('fs');\n"
                "const vm = require('vm');\n"
                "const statePath = %s;\n"
                "const sandbox = { console: console, window: {} };\n"
                "sandbox.window.SAL = { core: {} };\n"
                "vm.createContext(sandbox);\n"
                "const code = fs.readFileSync(statePath, 'utf8');\n"
                "vm.runInContext(code, sandbox, { filename: 'core/state.js' });\n"
                "const state = sandbox.window.SAL.core.state;\n"
                "const out = { ok: true, result: null };\n"
                "try {\n"
                "  out.result = (function () {\n%s\n  })();\n"
                "} catch (e) {\n"
                "  out.ok = false;\n"
                "  out.error = String(e && e.message || e);\n"
                "}\n"
                "process.stdout.write(JSON.stringify(out));\n" % (json.dumps(str(STATE_JS)), body),
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["node", str(script)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(PROJECT_ROOT),
                env={**os.environ},
            )
            self.assertEqual(
                0,
                proc.returncode,
                "Node 探针执行失败：%s" % (proc.stderr or proc.stdout),
            )
            return json.loads(proc.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_default_options_do_not_throw_and_map_id_to_name(self):
        """**默认选项**（不传 options）必须正常工作 —— 这正是回归点。"""
        result = self._run_node(
            """
    const map = state.createDerivedMap(function () {
      return [{ id: 1, name: '读英语' }, { id: 2, name: '写代码' }];
    });
    map.refresh();
    return {
      size: map.size(),
      one: map.lookup(1, null),
      two: map.lookup(2, null),
      missing: map.lookup(99, 'none'),
      hasOne: map.has(1),
      snapshot: map.snapshot()
    };
"""
        )
        self.assertTrue(result["ok"], "createDerivedMap 抛错：%s" % result.get("error"))
        payload = result["result"]
        self.assertEqual(2, payload["size"])
        self.assertEqual("读英语", payload["one"])
        self.assertEqual("写代码", payload["two"])
        self.assertEqual("none", payload["missing"])
        self.assertTrue(payload["hasOne"])

    def test_refresh_is_idempotent_and_reports_change(self):
        """refresh 幂等：内容不变时返回 false（不发无谓通知）。"""
        result = self._run_node(
            """
    let data = [{ id: 1, name: 'A' }];
    const map = state.createDerivedMap(function () { return data; });
    const first = map.refresh();
    const second = map.refresh();
    data = [{ id: 1, name: 'A' }, { id: 2, name: 'B' }];
    const third = map.refresh();
    return { first: first, second: second, third: third, size: map.size() };
"""
        )
        self.assertTrue(result["ok"], result.get("error"))
        payload = result["result"]
        self.assertTrue(payload["first"])
        self.assertFalse(payload["second"], "内容未变时 refresh 必须返回 false")
        self.assertTrue(payload["third"])
        self.assertEqual(2, payload["size"])

    def test_null_source_does_not_clear_the_mapping(self):
        """来源返回 null/undefined → 视为「暂无数据」，**不**清空既有映射。"""
        result = self._run_node(
            """
    let data = [{ id: 1, name: 'A' }];
    const map = state.createDerivedMap(function () { return data; });
    map.refresh();
    data = null;
    map.refresh();
    return { size: map.size(), one: map.lookup(1, null) };
"""
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(1, result["result"]["size"])
        self.assertEqual("A", result["result"]["one"])

    def test_explicit_options_are_honoured(self):
        """显式传入 keyOf / valueOf 时必须被采纳。"""
        result = self._run_node(
            """
    const map = state.createDerivedMap(
      function () { return [{ key: 'k1', title: 'T1' }]; },
      {
        keyOf: function (item) { return item.key; },
        valueOf: function (item) { return item.title; }
      }
    );
    map.refresh();
    return { size: map.size(), value: map.lookup('k1', null) };
"""
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(1, result["result"]["size"])
        self.assertEqual("T1", result["result"]["value"])

    def test_null_items_in_the_source_are_skipped(self):
        """来源里混入 null / undefined 项时必须跳过，不得抛错。"""
        result = self._run_node(
            """
    const map = state.createDerivedMap(function () {
      return [null, { id: 1, name: 'A' }, undefined];
    });
    map.refresh();
    return { size: map.size(), one: map.lookup(1, null) };
"""
        )
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(1, result["result"]["size"])
        self.assertEqual("A", result["result"]["one"])


# ---------------------------------------------------------------------------
# C. 真实生产用法：app.js 的 taskNameById 必须走派生映射
# ---------------------------------------------------------------------------
class DerivedMapProductionUsageTests(unittest.TestCase):
    """``app.js`` 的任务名查找必须真的用上派生映射（P3-D 的目的）。"""

    @classmethod
    def setUpClass(cls):
        cls.app_source = _read(APP_JS)

    def test_app_js_uses_create_derived_map(self):
        self.assertIn(
            "core.createDerivedMap",
            self.app_source,
            "app.js 必须真实启用 createDerivedMap（P3-D 的目标）",
        )

    def test_task_name_lookup_uses_the_derived_map(self):
        self.assertIn(
            "map.refresh()",
            self.app_source,
            "taskNameById 必须经派生映射读取（不得每次线性扫描）",
        )
        self.assertIn(
            "map.lookup(id, null)",
            self.app_source,
            "taskNameById 必须经派生映射 lookup",
        )


if __name__ == "__main__":
    unittest.main()
