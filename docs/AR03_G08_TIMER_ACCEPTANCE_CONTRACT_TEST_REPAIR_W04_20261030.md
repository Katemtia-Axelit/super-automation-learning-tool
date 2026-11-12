# AR03-G08 Timer ESM Owner：接受合同测试夹具修复（W04）

**TASK_TOKEN**: `LT_AR03_G08_TIMER_ACCEPTANCE_CONTRACT_TEST_REPAIR_W04_20261030`
**TASK_ID**: `AR03-G08-TIMER-ACCEPTANCE-CONTRACT-TEST-REPAIR-W04`
**日期**: 2026-10-30
**性质**: 有界测试基础设施修复（不改生产代码、不扩大 G08 产品范围）

---

## 1. 实际修改文件

仅以下白名单内文件被修改（`git status` 确认，其余工作树改动均为本任务之前既有的脏改动，未被触碰）：

| 文件 | 改动性质 |
| --- | --- |
| `tests/characterize/test_free_card_acceptance_contract.py` | 测试夹具与断言迁移 |
| `docs/AR03_G08_TIMER_ACCEPTANCE_CONTRACT_TEST_REPAIR_W04_20261030.md` | 本报告（新增） |

**未修改**（明确遵守红线）：`static/app.js`、`static/modules/timer/index.js`、
`static/modules/timer/presentation.js`、`tests/e2e/factory-real-page-safe.spec.js`、
任何 `server/**`、`config/config.json`、`data/**`、`src/notes/**`、
Controller 工具链、历史任务/Batch 证据。未执行 git add/commit/reset/clean/stash，
未启动真实 server，未触碰真实 DB/Vault。

---

## 2. 根因与修复方案

### 2.1 W03 报告的两个根因

1. **旧 Node VM harness 不支持 ESM dynamic import**。
   `static/app.js` 通过 `import('/static/modules/timer/index.js')` 惰性加载
   **真实生产 ESM timer owner**。旧 harness 用
   `vm.runInContext(APP_JS, ctx, { filename: 'app.js' })`，**没有**提供
   `importModuleDynamically` 回调，Node 直接抛
   `A dynamic import callback was not specified.` → owner 永远加载不了。

2. **部分断言仍读取 G08 已有意移除的 legacy timer globals**
   （`app.timerDockSession` / `app.timerActiveSession` / `app.timerDockPaused` /
   `app.timerDockPausedElapsed` / `app.window._inlineTimerHandle`）。
   这些全局在 `static/app.js` 中已 **完全不存在**（全文件 grep 无匹配），
   断言因此恒为 `undefined`/`null`，属于 **空洞断言**。

### 2.2 ESM loader 与 DOM 隔离方案

**方案**：用 Node 的 `vm.SourceTextModule` 把磁盘上的真实 ESM 模块加载进
**与 app.js 完全相同的 vm context**。

关键点与理由：

- **为什么不能用宿主 realm 的原生 `import()`**：原生 `import()` 加载的模块运行在
  宿主 realm，其 `document` 是宿主全局对象，**不是** 合成 DOM。ESM timer owner
  内部用全局 `document`（`startInlineTimer` 里 `document.querySelector(...)`），
  因此原生 import 会让 owner "看到"错误的 DOM。
  探针实测：原生 `import()` 路径下 owner 侧 `document` 与 app.js 侧 DOM 不同源。
- **为什么用 `vm.SourceTextModule` + 同一个 `ctx`**：`SourceTextModule` 可指定
  `context: ctx`，模块代码因此与 app.js **共享同一个 global object**
  （同一个 `document`、同一套 `setInterval` stub、同一份 `fetch` stub）。
  探针实测：模块内 `typeof document !== 'undefined'` 为真且取到合成 DOM 标记。
- **DOM 隔离**：合成 DOM 依然完全由本文件内的 `FakeDocument` / `FakeElement`
  提供（并由 `src/index.html` 的 `id=` 声明构建），不引入任何真实浏览器、
  真实 DOM API 或真实网络。`fetch` 仍被替换为记录调用的 stub。
- **模块解析**：`/static/...` specifier 映射回 `<project>/static/...`，
  相对 import（`./presentation.js`）由 **同步** linker 按 `referencingModule`
  的 identifier 目录解析（Node 的 `link()` 需要同步返回 Module 实例；
  异步 linker 会破坏 link 的同步契约 —— 这是探针中实测到的失败点）。
- **运行标志**：Node 需要 `--experimental-vm-modules`（`vm.SourceTextModule`
  至今仍是 experimental API）。已在 `_SandboxRunner.run()` 中固定传入
  `--experimental-vm-modules --no-warnings`，并保留 `NODE_OPTIONS=""` 以免
  外部环境污染。

**同时修复的一个夹具缺陷**：旧 stub 的 `setInterval` 返回 `0`（假值）。
ESM owner 的 `hasInlineTimer()` 用 `!!inlineTickHandle` 判断，返回 `0` 会让
它 **永远** 为 false。已把 stub 改为返回真值（递增计数）。这是夹具侧缺陷，
不是生产缺陷。

### 2.3 owner 状态读取通道

新增两个注入到 snippet 作用域的只读辅助函数（测试侧，**不**改生产代码）：

- `timerState()` —— 通过 app.js 的薄 facade `_timerSnapshot()`（内部即
  `owner.getSnapshot()`）与 `owner.hasInlineTimer()` 读取 **ESM timer owner
  闭包内的真实状态**，返回
  `{ session, paused, pausedElapsedMs, hasInlineTimer, ownerReady }`。
- `legacyTimerMirrors()` —— 返回 5 个被 G08 移除的 legacy 镜像全局的
  **存在性**布尔值，用于 **断言它们不存在**。

---

## 3. 断言迁移映射表

原断言读取的 legacy mirror → 迁移到的 owner 公开快照 / 行为合同：

| 原断言 | 迁移后 | 覆盖语义是否保留 |
| --- | --- | --- |
| `app.timerDockSession` 非空 | `timerState().session` 非空 | 保留（并加强：额外断言 `session.id`） |
| `app.timerDockSession["id"] == 991` | `timerState().session["id"] == 991` | 保留 |
| `app.timerDockSession["id"] == 4242`（数字字符串 session_id） | `timerState().session["id"] == 4242` | 保留 |
| `app.timerDockSession is None`（成功后回抽卡） | `timerState().session is None` | 保留 |
| `app.timerDockSession is None`（非自由卡 Dock 停止） | `timerState().session is None` | 保留 |
| `app.timerDockSession is None`（fail closed） | `timerState().session is None` | 保留 |
| `app.timerDockSession` 非空（计时停止失败 → 保留现状） | `timerState().session` 非空 + `session.id == 991` | 保留（并加强） |
| `app.timerDockSession` 非空（Dock 停止后表单打开） | `timerState().session` 非空 + `session.id == 991` | 保留 |
| `app.window._inlineTimerHandle` | `timerState().hasInlineTimer`（owner 真实句柄状态） | 保留（语义更准确） |
| `app.timerDockPaused` / `app.timerDockPausedElapsed` | `timerState().paused` / `.pausedElapsedMs` | 保留（owner 真实值） |
| `app.timerActiveSession` | `timerState().session`（owner 唯一活动 session） | 保留 |

**新增的"必须不存在"断言**（替代被删镜像的显式负向合同）：

- `legacyTimerMirrors()` 的 5 个镜像全局全部断言为 `False`
  （`timerDockSession` / `timerActiveSession` / `timerDockPaused` /
  `timerDockPausedElapsed` / `_inlineTimerHandle`）。
  这满足"被移除的 legacy mirror 应明确断言不存在，而不是重新引入"。

**新增的夹具自检（防空洞闸门）** — `TimerOwnerEsmHarnessTests`：

1. 生产 ESM owner **真的被加载**（显式触发 `app._getTimerOwner()`，断言
   `ownerReady` 为真且暴露 owner 的 10 个公开 API：
   `getSnapshot` / `startSession` / `pauseSession` / `resumeSession` /
   `completeSession` / `clear` / `getActualMinutes` / `hasInlineTimer` /
   `startInlineTimer` / `stopInlineTimer`）。
   —— 若 ESM loader 失效，此测试 **直接失败**，而不是让下游断言空洞通过。
2. 5 个 legacy 镜像全局必须全部不存在。
3. **owner 与 app.js 共享同一份合成 DOM**：接受自由卡后，断言由 ESM
   `presentation.js` 写入的 Dock DOM 真实变化
   （`#timerDockTime == "10:00"`、`#timerDockTaskName == "看纪录片"`、
   `#timerDockIdle` 隐藏、`#timerDockActive` 显示）。
   —— 若 owner 运行在别的 realm / 别的 document 上，这三项必然为空/false。

**唯一一处源码形状断言的迁移**：
`test_dock_stop_free_card_path_never_calls_timer_complete_directly` 原先断言
源码里不出现 `"timerDockSession = null"`（该字符串在 G08 后已不存在，断言已成
恒真空洞）。现保留该断言，并 **追加** `assertNotIn(".clear()", body)` ——
即 Dock 停止的两个辅助函数 **绝不** 清空 owner 的活动 session
（清空 session 的唯一入口是 `owner.clear()`）。这保持了原断言的 **意图**
（"这两个辅助函数不自己清 session"）而非其失效的字面形式。

---

## 4. 原有行为覆盖是否保留

**全部保留，无删除、无 skip、无 xfail、无放宽。**

- 测试方法数：修复前 **74** → 修复后 **77**（净增 3 条 = 上述夹具自检）。
- 全文件 `skip` / `xfail` 关键字扫描：仅 2 处命中，且均为既有内容 ——
  第 471 行是事件类型字面量 `"skip_task"`（后端合法 event_type），
  第 1038 行是既有的 `raise unittest.SkipTest("node is not available on PATH")`
  环境守卫。**未新增任何 skip / xfail / 弱化。**

逐项核对任务点名的行为覆盖：

| 行为覆盖 | 状态 | 迁移后的断言 |
| --- | --- | --- |
| 接受自由卡（表单展开、活动/理由字段、默认理由、手机提醒文案） | 保留 | 未改动 |
| 计时启动（`planned_minutes` 严格等于 `effective_minutes`、`task_id` 正确） | 保留 | 未改动 |
| 无已批准时长绝不启动计时（5 组 subTest） | 保留 | 未改动 |
| 普通/微型/目标卡走原 `startTask` 路径 | 保留 | 未改动 |
| 非法 / 缺失 `session_id` fail-closed（15 组 subTest：绝不发 complete、绝不启内嵌计时、owner 绝不持有 session、绝不谎报"已停止"、必显警告、活动/理由保留、绝不显示"执行中"） | 保留 | 镜像断言 → `timerState().session is None` + `hasInlineTimer` 为假 + legacy 镜像必须不存在 |
| 合法 `session_id` 成功路径（含内嵌计时启动、owner 持有 session id 991） | 保留 | 迁移到 owner 快照 + `hasInlineTimer` |
| 数字字符串 `session_id` 被接受（4242） | 保留 | 迁移到 owner 快照 |
| **先停止 timer 再保存 feedback**（`submitFreeCardEnd` 先 `completeSession` 再写事件） | 保留 | 未改动（`timerComplete` 断言仍基于真实 HTTP 调用记录） |
| **反馈失败重试不重复 complete** | 保留 | 未改动（`feedbackPosts == ["accept_task", "finish_on_time"]`、`timerComplete` 计数） |
| 中断绝不记为已完成（事件类型/`result`/任务完成端点三重） | 保留 | 未改动 |
| 计时停止失败 → 保留现状、不写反馈、表单保留 | 保留 | 迁移到 `timerState().session` 保留 + `session.id == 991` |
| Dock 停止：自由卡走 G03 表单、非自由卡保留旧提前结束语义、找不到表单 fail closed、`data-card-type="free"` 兜底 | 保留 | 镜像断言 → owner 快照 |
| "帮我选"成功/422/网络失败/缺 activity 四条路径 | 保留 | 未改动 |
| XSS：活动绝不进入 inline JS | 保留 | 未改动 |
| 后端 `accept_task` 契约（22+ 条：字段、默认值、非法输入 400 + 零写入、reason_category 严格语义、既有事件类型逐字不变、隔离性） | 保留 | 未改动（纯 Python + 合成 SQLite/Flask） |

---

## 5. 测试证据

**精确命令**（项目现有 Python 环境 `.venv`）：

```
cd "d:\Axelit\.工作\trae\超级自动化学习工具"
.\.venv\Scripts\python.exe -m pytest tests/characterize/test_free_card_acceptance_contract.py -q
```

**结果**：

```
.................................... [ 46%]
.........................................              [100%]
77 passed, 61 subtests passed in 8.62s
EXITCODE=0
```

- **PASS: 77** 个测试方法 + **61** 个 subTest。
- **FAIL: 0**
- **SKIP: 0**
- **exit code: 0**

### 5.1 ESM loader 的独立实证（防空洞验证）

除 pytest 之外，用同一 harness 做了一次直接探针，确认 ESM owner 与合成 DOM
的共享关系不是空话：

```
snapshotAfter = {
  "session": { "id": 991, "task_id": 42, "started_at": "2026-10-25T00:00:00",
               "planned_minutes": 25, "task_name": "看纪录片" },
  "paused": false, "pausedElapsedMs": 0,
  "hasInlineTimer": true, "ownerReady": true
}
legacyMirrors = { timerDockSession: false, timerActiveSession: false,
                  timerDockPaused: false, timerDockPausedElapsed: false,
                  inlineTimerHandle: false }
postUrls = ["/api/timer/start", "/api/task-feedback"]
```

DOM 共享实证（由 ESM `presentation.js` 写入合成 DOM）：

```
DOM-SHARE-PROOF: {
  "dockTime": "10:00",
  "dockTaskName": "看纪录片",
  "dockIdleHidden": true,
  "dockActiveHidden": false,
  "panelStatus": "计时中 · 看纪录片（计划 25 分）"
}
```

`dockTime` / `dockTaskName` / `panelStatus` 只可能由 ESM
`static/modules/timer/presentation.js` 写入 —— 它是 owner 内部调用的，
若 owner 与 app.js 不共享同一份 DOM，这三项必然为空字符串。

### 5.2 未执行的验证（明确声明"未跑"，不声称通过）

按任务约束，**未**运行：完整 AR02 baseline、完整 characterize suite、
Bootstrap、真实项目 server、真实 DB/Vault、Factory 全套 E2E。
生产代码 **未** 修改，因此无需也未做生产侧回归。

---

## 6. 未完成事项与风险

### 6.1 未完成事项

- **无未完成的修复项**：白名单内的修复已全部落地并通过验证。
- 未做：把同一套 ESM loader 复用到其它仍使用旧 Node VM harness 的
  characterize 测试文件（如 `test_card_type_frontend.py` 等）。**这超出本
  工单白名单**（只允许改本文件），未实施。

### 6.2 风险

1. **依赖 Node experimental API**：`vm.SourceTextModule` 需要
   `--experimental-vm-modules`。已在 harness 内固定传入该标志，并在
   sandbox 启动时显式检查 `typeof vm.SourceTextModule === 'function'`，
   缺失即抛出明确错误而非静默降级。
   风险等级：低（Node 24 内该 API 稳定存在）。
   **残余风险**：若未来 Node 移除/改名该 experimental API，或项目 CI 使用
   定制 Node 构建，需同步调整 `_HARNESS_TEMPLATE` 的 loader 段。

2. **`--experimental-vm-modules` 是进程级标志**：本 harness 每个 snippet
   启动一个独立 `node` 子进程，标志只作用于该子进程，不影响宿主进程或
   其它测试。

3. **ESM loader 的同步 linker 契约**：Node 的 `Module.link()` 要求 linker
   **同步**返回 Module 实例。实现已遵守（`esmLinker` 为同步函数，
   `evaluateEsmModule` 另行处理 evaluate）。若后续有人把 linker 改成
   `async`，`link()` 会以
   `Provided module is not an instance of Module` 失败 —— 这是探针实测到的
   失败模式，已在实现中规避并加了注释。

4. **`_timerSnapshot` / `_timerOwner` 属 app.js 内部（虽非下划线私有）**：
   测试读取 `app._timerSnapshot()` 与 `app._timerOwner` 来获得 owner 的
   **真实**公开快照。若将来 app.js 重命名这两个内部名，测试会失败（fail
   loud，而非空洞通过）——这是可接受的失败模式，但属于测试对内部结构的
   耦合。

5. **owner 惰性加载**：`ownerReady` 在第一次 `await _getTimerOwner()` 之前
   为假。测试中 `timerState()` 在 owner 未就绪时返回空快照。
   所有依赖 session 的断言都在 owner **必然已就绪**的操作之后取值
   （`startTask` / `submitFreeCardAccept` / `submitFreeCardEnd` 均会
   `await _getTimerOwner()`），因此不存在"未就绪导致断言空洞通过"的窗口。

6. **interval 计数语义的改变**：夹具 `setInterval` 现返回真值。既有断言
   `intervalDelta == 1`（内嵌计时启动）与 `== 0`（绝不启动）依赖 **计数** 而
   非句柄值，故语义不变；但若将来新增断言去检查句柄值本身，基线已变。

7. **生产代码未动**：W03 Controller Review 对生产代码的结论（12/12 真实页
   E2E PASS）未被本工单推翻，也未被重新验证。本工单仅修复测试夹具。

---

## 7. Historical Handoff 摘要

- **实际修改文件**（仅 2 个，均在白名单内）：
  - `tests/characterize/test_free_card_acceptance_contract.py`
  - `docs/AR03_G08_TIMER_ACCEPTANCE_CONTRACT_TEST_REPAIR_W04_20261030.md`
- **测试证据**：`.\.venv\Scripts\python.exe -m pytest tests/characterize/test_free_card_acceptance_contract.py -q`
  → **77 passed, 61 subtests passed, 0 failed, 0 skipped, exit code 0**
- **工具调用数**：约 33 次（其中 1 次为有界诊断周期：Node ESM loader 能力
  探针 + 共享 DOM 实证探针；未重复运行整套测试追求全绿）。
- **未完成事项**：见 §6.1（无阻断项；其它 characterize 测试文件的旧 harness
  未迁移，因超出白名单）。
- **风险**：见 §6.2，主要为 Node experimental API 依赖与对 app.js 内部名的
  测试耦合，两者均为 fail-loud 失败模式。

LT_AR03_G08_TIMER_ACCEPTANCE_CONTRACT_TEST_REPAIR_W04_20261030
