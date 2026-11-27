# P3 前端模块化交付说明（AR03-P3）

> 日期：2026-11-21
> 范围：**前端**（`static/`）Feature 模块化 —— P3-A / P3-B / P3-C / P3-D /
> P3-E / P3-F 六个切片 + P2 最终收尾。
> 性质：**新增** 文档，**不覆盖** 任何历史交付记录。

---

## 0. 本文档的定位与边界

### 0.1 为什么单独出这份文档

- `docs/P1_FEATURE_MIGRATION_MAP.md` 记录的是 **P1**（前端内核）阶段；
- `docs/P2_FEATURE_MIGRATION_MAP.md` / `P2_BACKEND_MODULARIZATION_DELIVERY_20261121.md`
  记录的是 **P2**（后端分层）；
- `docs/P2_FINAL_CLOSURE_20261121.md` 记录的是 **P2 收尾**。

本文档记录 **P3**（前端 Feature 模块化）的完成状态、验证证据与遗留事项。
**历史文档不被改写**；两者并存，不冲突。

### 0.2 本轮 **没有** 做的事

- **没有** 触碰 `src/notes/**` / `data/task_publisher.db{,-wal,-shm}` /
  `config/config.json`；
- **没有** 改任何 API 路径、请求体、响应体、状态码、业务规则；
- **没有** 改 `src/index.html` 的 inline handler 名字；
- **没有** commit / push / reset / clean / stash / checkout / switch；
- **没有** 绕过任何 hook / 门禁（`[destructive-guard]` 拦截的删除保持拦截）；
- **没有** 追溯修改 P1 / P2 的任何历史执行记录；
- **没有** 动 `static/free-task.js`（用户明确选择 `leave_untouched`）。

---

## 1. 状态总览（如实记录）

| 项 | 状态 | 说明 |
|---|---|---|
| **P3-A 自由卡 owner 化** | ✅ 完成 | `static/modules/free-card/index.js` → `createFreeCardOwner`；`app.js` 只剩 7 个薄 facade。 |
| **P3-B 任务 owner 化** | ✅ 完成 | `allTasks` / `allTags` / `selectedTagFilter` 全部归 `createTasksOwner` 闭包；`window.*` 退化为只读实时 getter。 |
| **P3-C 统一双计时器** | ✅ 完成 | 单一 `getSession` + 单一主节拍 `tickHandle`；任务面板编排归位 owner；新增 23 条契约断言。 |
| **P3-D 内核真实启用** | ✅ 完成 | `createDerivedMap` 首次真实启用；`shared/formatters.js` 收敛为唯一格式化权威。 |
| **P3-E 边界检查强化** | ✅ 完成 | 新增 4 类规则（循环依赖 / 唯一状态所有权 / `app.js` 白名单 / 生命周期分级）；`--json` 机读输出；新增 15 条 pytest 断言。 |
| **P3-F 装配根与生命周期分级** | ✅ 完成 | `app.entry.js` = 唯一装配根；`APP_SCOPED_MODULES = ['timer', 'gacha']`；新增 22 条生命周期断言。 |
| **P2 收尾** | ✅ 完成 | Blueprint 事务职责归位 + `app_factory.py` 注释修正 + `docs/P2_FINAL_CLOSURE_20261121.md`。 |
| **P1 独立验收** | ⏳ **`READY_FOR_INDEPENDENT_ACCEPTANCE` —— 外部待会签** | 证据包已交付（`docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md`），签字尚未记录。**不追溯修改**。 |
| **P2 门禁违规** | ⚠️ **如实在案** | P2 未取得 P1 会签即进入 Stage 1–8。既成事实，仅登记。 |
| **E2E 500（观察项）** | ⏳ **不结案、不重跑** | P3 最终隔离 E2E：**36/36 测试通过**；**同一份运行内观察到一次 HTTP 500**（路径 `/api/tasks/21`，见 `.tmp_e2e_p2.log` L106 与 L110）。**根因未确认**；**不确定是否与历史 500 属于同一问题**。保留为**非阻塞观察项**。 |
| **P1 遗留带外事项** | ⏳ **保留带外** | `server/app/legacy_compat.py`（墓碑）与 `scripts/_probe_task_get_500.py` 受 `[destructive-guard]` 约束，不绕过。 |

---

## 2. 验证证据

### 2.1 模块边界门禁

```console
$ node scripts/check_module_imports.js
[check_module_imports] Feature 模块：agent-readonly, config, free-card, gacha, knowledge, prompts, schedule, sleep, state-assessment, tasks, timer
[check_module_imports] 应用级模块：timer, gacha
[check_module_imports] 通过：模块边界无违规（退出码 0）

$ echo $?
0
```

`--json` 输出可机读（`violations: []` / `ok: true` / `appScopedModules: ["timer","gacha"]`）。

### 2.2 特征化测试套件

```console
$ python -m pytest tests/characterize -q
1653 passed, 10 skipped, 442 subtests passed in 290.61s (0:04:50)
```

（**0 failed**。计数含 P3 新增的门禁：`test_module_boundary_contract.py`、
`test_module_lifecycle_contract.py`、`test_timer_single_source_contract.py`、
`test_derived_map_contract.py`。）

### 2.3 P0 清理验证

```console
$ python scripts/verify_p0_cleanup.py
...
ALL ASSERTIONS PASSED
EXIT=0
```

### 2.4 隔离 E2E

```console
$ node scripts/run_e2e_isolated.js
...
测试结果: 36 通过, 0 失败
...
[run_e2e_isolated] ✅ 合成服务器未触碰任何生产受保护路径
[run_e2e_isolated] ✅ 生产数据 fs 守卫全程未被触发（未读取任何生产文件）
[run_e2e_isolated] e2e-manual.js 退出码 = 0（0 = 全部通过）
```

### 2.5 最终验收结果

| 项 | 命令 | 结果 |
|---|---|---|
| 模块边界门禁 | `node scripts/check_module_imports.js` | 退出码 **0** |
| 全量 characterization | `python -m pytest tests/characterize -q` | **1653 passed / 0 failed / 10 skipped** |
| P0 契约 | `python scripts/verify_p0_cleanup.py` | **ALL ASSERTIONS PASSED**，退出码 0 |
| 隔离 E2E | `node scripts/run_e2e_isolated.js` | **36/36 PASS**，退出码 0 |

> **验收不是一次通过**：首次最终验收暴露了两处功能回归（§3.0），修复并
> 加闸门后重跑全绿。这是「门禁真的在拦东西」的证据，不是流程瑕疵。

---

## 3. 本轮代码改动清单

### 3.0 最终验收期间发现并修复的两处 **功能回归**

> 这两处是 **验收过程中真实暴露** 的回归，不是重构引入的「设计问题」。
> 两者都表现为 **用户可见的功能失效**，因此按功能回归处理并加了契约闸门。

#### 3.0.1 唯一实例不变式被破坏 → 计时器不走动（🔴 高）

**症状**：E2E 3.3「开始计时」失败 —— 面板一直显示 `未在计时` / `00:00`，
即使后端已返回 `session_id`、owner 内部 `session` 已就绪。

**根因**（两条路径各创建一个计时 owner）：

| 路径 | 时机 | 行为 |
|---|---|---|
| classic `app.js` | **同步**执行体末尾 `loadTimerPanel()` / `initTimerDock()` → `_getTimerOwner()` → **动态 import（异步）** | 创建 **实例 A**，`tickHandle` 在 A 上 |
| 装配根 `app.entry.js` | `type=module` → **deferred** → 在 app.js 同步体 **之后** 执行 | 创建 **实例 B**，`session` 写进 B |

`app.js` 的 `_setTimerOwner` 无条件覆盖 `_timerOwner`，于是：

- 用户点「开始」→ session 写进 **B** → B 渲染 `计时中`（**一瞬间是对的**）；
- 下一秒 **A 的 tick** 执行 `updatePanel()`，而 **A 没有 session**
  → 面板被覆盖回 `未在计时`。

**用户看到的症状就是「计时器不走动」** —— 这是功能回归，不是架构洁癖。

**修复**（三层防护）：

1. `app.js` 的 `_setTimerOwner` / `_setTasksOwner` / `_setFreeCardOwner`
   → **已有 owner 时绝不替换**（并 `console.warn` 显式告警，不得静默）；
2. `app.js` 的 `_get*Owner()` 动态 import 兜底 → 创建 **前** 先检查是否
   已有 owner（有则复用）；
3. `app.entry.js` 装配根 → 创建 **前** 先问 classic 层
   `__get*OwnerSync()`（新增的同步探针），有则 **复用**。

**闸门**：`tests/characterize/test_module_lifecycle_contract.py`
新增 `SingleOwnerInstanceTests`（13 条断言），锁定「唯一实例」不变式。

#### 3.0.2 `createDerivedMap` 的原型链陷阱 → 任务列表渲染整体抛错（🔴 高）

**症状**：浏览器控制台
`[tasks] renderTasks TypeError: Cannot convert undefined or null to object`
→ 任务卡片渲染不出来。

**根因**：

```js
const opts = options || {};                       // {} —— 继承 Object.prototype
const valueOf = typeof opts.valueOf === 'function' // ← Object.prototype.valueOf
  ? opts.valueOf                                  //   **本身就是一个函数**！
  : function (item) { return item && item.name; };
```

`options` 省略 → `opts = {}` → `opts.valueOf` **继承自 `Object.prototype`**，
而 `Object.prototype.valueOf` **本身就是一个函数** → `typeof` 判定通过
→ 取值器变成 `Object.prototype.valueOf` → 对 `null` 项调用时抛
`Cannot convert undefined or null to object`。

（这也解释了「栈顶看起来像 `Object.keys`」的迷惑现象：真正的抛点在派生
映射内部对 `null` 项取值。）

**修复**：判定必须用 **自有属性**（`hasOwnProperty.call(opts, …)`），
不能用 `typeof` —— 原型链上的内置方法同样是函数。

**闸门**：`tests/characterize/test_derived_map_contract.py`（新增，11 条断言），
含 **Node 合成页面运行期** 验证（默认选项必须不抛错、refresh 幂等、
null 来源不清空映射、显式选项被采纳、null 项被跳过）。

### 3.1 新增文件

| 文件 | 行数 | 作用 |
|---|---|---|
| `static/modules/free-card/index.js` | 880 | **P3-A** 自由卡接受 / 结束全流程的唯一 owner |
| `tests/characterize/test_timer_single_source_contract.py` | — | **P3-C** 单一 session / 单一节拍 / 面板编排归属的契约测试 |
| `tests/characterize/test_module_boundary_contract.py` | — | **P3-E** 模块边界规则的 pytest 门禁 |
| `tests/characterize/test_module_lifecycle_contract.py` | — | **P3-F** 应用级 vs 页面级生命周期的契约测试（含 `SingleOwnerInstanceTests` 唯一实例不变式） |
| `tests/characterize/test_derived_map_contract.py` | — | **P3-D** 只读派生映射（含原型链陷阱）的契约测试 + 运行期验证 |
| `docs/P3_FRONTEND_MODULARIZATION_DELIVERY_20261121.md` | — | 本文档 |
| `docs/P3_FEATURE_MIGRATION_MAP.md` | — | 前端迁移地图 |
| `docs/P3_HANDOFF_TO_P4.md` | — | 交给 P4 的交接 |

### 3.2 修改文件

| 文件 | 改动 |
|---|---|
| `static/app.js` | **3482 → 2935 行**（−547）。自由卡实现迁出；任务状态所有权迁出；计时 owner 工厂化（`_createTimerOwnerFromModule` / `_setTimerOwner`）；facade 全部 **return promise**；`window.allTasks/allTags/selectedTagFilter` 改为只读 getter；**验收期**补「唯一实例」三层防护（≈315 行含注释）。 |
| `static/app.entry.js` | 唯一装配根。静态 import `timerModule` / `gacha`；新增 `APP_SCOPED_MODULES`；`MODULE_CONTRACTS` 收敛为页面级模块；装配阶段同步创建并注入 timer / gacha / free-card / tasks owner。 |
| `static/modules/timer/index.js` | **P3-C** 面板编排归位（`startTimerFromPanel` / `stopTimerFromPanel` / `handleTimerOutcome`）；单一 `tickHandle`（`startTick` / `stopTick` / `hasTick`）；`getActiveSession` → `getSession`。 |
| `static/modules/timer/presentation.js` | `getActiveSession` → `getSession`（单一 session getter）。 |
| `static/modules/tasks/index.js` | **P3-B** 增 `setTasks(list)` / `setTags(list)` 窄 setter（供装配与测试夹具注入权威状态，**不** 创建第二份全局数组）。 |
| `static/modules/gacha/index.js` | **P3-F** 移除页面级 `meta` / `mount` / `unmount`；新增幂等的应用级启动钩子 `initAppScoped()`。 |
| `static/core/state.js` | **P3-D** 新增 `createDerivedMap(readSource, options)`（只读派生映射，id → name）。**验收期修复**：选项判定改用 `hasOwnProperty.call(opts, …)`（原型链陷阱修复，见 §3.0.2）。 |
| `static/shared/formatters.js` | **P3-D** 新增 `formatElapsedMs` / `formatDiscardTimestamp` / `formatRelativeTime` / `formatTimerMMSS` / `todayDateStr` / `formatHHMM`。 |
| `scripts/check_module_imports.js` | **P3-E** 新增规则 ⑥–⑨ + `--json` 的 `appScopedModules` 字段 + `APP_JS_GLOBAL_WHITELIST`（**验收期**补登记 3 个同步探针：`__getTimerOwnerSync` / `__getTasksOwnerSync` / `__getFreeCardOwnerSync`）。 |

### 3.3 测试文件修改（**契约锚点跟随实现**）

| 文件 | 改动 |
|---|---|
| `tests/characterize/test_free_card_acceptance_contract.py` | 新增 `_free_card_impl_body()`（owner 优先解析）；6 条源码合同改锚点；沙箱注入 tasks owner + free-card owner；`app.allTasks =` → `app.__setAllTasks(`。 |
| `tests/characterize/test_card_type_frontend.py` | 11 处 `app.allTasks/allTags =` → `app.__setAllTasks/__setAllTags`；沙箱注入真实 tasks owner（`vm.SourceTextModule` + `--experimental-vm-modules`）。 |
| `tests/characterize/test_m02_behavior_frontend_core.py` | 自由卡建议合同改锚点到 free-card owner。 |
| `tests/characterize/test_task_discard_restore_owner.py` | `move-to-discard` 断言改锚点到 free-card owner。 |

> **为什么这些测试要改**：模块化把实现搬到了 owner 模块。若合同测试继续
> 断言 `app.js` 的源码文本，它们就变成 **测门面壳子** 的假绿 / 假红 ——
> 断言 `app.js` 里有一行 `/api/gacha/free-card/suggestion`，并不能证明
> 这个端点真被调用。改锚点后，**语义保证不变**，只是断言跟着实现走。

---

## 4. `static/app.js` 收敛现状（如实记录）

迁移后 `app.js` **仍然保留** 2935 行。它们是：

| 类别 | 说明 |
|---|---|
| **纯委托 facade** | 自由卡 7 个、任务若干、计时若干 —— 全部转发 owner，无第二份实现。 |
| **DOM 适配器** | 既有 inline handler 依赖的入口名（`playCardAnim` / `renderDrawnCardResult` / `confirmDiscardRestore` / …）。 |
| **既有全局入口** | `src/index.html` 内联 handler 依赖的名字（`drawGacha` / `openTaskEdit` / `saveTask` / `loadTasks` / …）。 |
| **启动加载段** | 启动时的一次性 DOM / 数据加载。 |

**边界门禁如何防止它重新膨胀**（P3-E 规则 ⑧）：

- `app.js` 的每个 **可写全局** 必须在 `APP_JS_GLOBAL_WHITELIST` 里登记；
- 每条登记 **必须写明理由**（否则测试失败）；
- 未登记的新全局 → 门禁报错；
- 已失效的白名单条目 → 门禁报错（whitelist 腐化检测）。

因此 `app.js` **不可能无声地长胖**：任何新增的全局业务状态都会立刻红。

---

## 5. 架构不变式（本轮确立）

### 5.1 单一状态所有权

> 一份状态有且只有一个 owner（闭包私有），其余地方只经 getter / setter 访问。

机械保障：
- `modules/*` 内 **禁止** `window.<x> =`（规则 ⑦）；
- `window.allTasks` / `allTags` / `selectedTagFilter` 是 **只读实时 getter**
  （不是副本）；
- 计时状态全部在 `createTimerOwner` 闭包内（`session` / `paused` /
  `pausedElapsedMs` / `tickHandle`）。

### 5.2 单一节拍

> 一个应用只有一个 **主** 节拍句柄。

- `tickHandle` —— 主节拍，驱动 Dock（总是）+ 任务面板（仅当 `#page-tasks` active）。
- `inlineTickHandle` —— 卡内局部显示节拍，读同一个 session，句柄独立。

### 5.3 生命周期分级

> **页面切换不得让跨页面的全局能力停止运行。**

- 应用级（`timer` / `gacha`）：应用启动即创建，**页面切换永不 unmount**。
- 页面级：���`page:change` → `mount` / `unmount`；`unmount` 只释放 **本模块
  自己的** interval / 监听。

机械保障（规则 ⑨ + `test_module_lifecycle_contract.py`）：
- 应用级模块 **不得** 导出 `meta` / `mount` / `unmount`；
- 应用级模块 **不得** 出现在 `MODULE_CONTRACTS`；
- 页面级 `unmount` 体内 **不得** 出现 `stopInlineTimer` / `clearSession` /
  `tickHandle` / `stopTick` / `endUnifiedGachaSession` / `.clear()`。

### 5.4 唯一实例不变式（验收期新增）

> 每个 owner 在整个应用生命周期内 **只允许存在一个实例**。

这是 P3-F 装配根与 classic 降级路径并存时 **最容易破** 的不变式 ——
而且破掉时症状极其迷惑（"状态明明对，界面却不动"）。

机械保障（`SingleOwnerInstanceTests`，13 条断言）：
- 注入 setter 在 **已有 owner 时绝不替换**（并显式告警）；
- 动态 import 兜底在创建 **前** 先检查是否已有 owner；
- 装配根在创建 **前** 先问 classic 层同步探针；
- classic 层 **只能有一个** owner 引用变量（`var _timerOwner` 唯一）。

> **给 P4 的提醒**：凡是「classic 降级路径 + ESM 装配根」并存的模块，
> 都必须满足这条不变式。新增模块时照抄 `__get*OwnerSync` + 复用分支。

### 5.5 渲染层 / 服务层解耦

> 「是否重绘任务面板」是 **渲染层** 判断；「计时是否继续运行」是 **服务层**
> 判断 —— 两者不得互相牵连。

---

## 6. 验收结果

见 `docs/P3_HANDOFF_TO_P4.md` §1 的验收表（本轮实际运行结果）。

---

## 7. 遗留事项与风险

| 项 | 级别 | 说明 |
|---|---|---|
| **P1 独立验收未会签** | 🟡 流程 | 技术侧全部结论由本轮证据支撑；流程侧会签仍缺。**不追溯修改**。 |
| **P2 门禁违规** | 🟡 流程 | 如实在案。 |
| **`app.js` 仍有 2935 行** | 🟢 已设防 | 边界门禁已阻止无声回涨。进一步瘦身属于后续切片，**不在本轮范围**。 |
| **`static/free-task.js` 未动** | 🟢 有意 | 用户明确 `leave_untouched`。它是既有隔离原型，**不是** 已批准的卡优先用户旅程的证据。 |
| **历史一次性 `/api/tasks/{id}` 500** | 🟡 观察项 | P3 最终隔离 E2E：**36/36 测试通过**；**同一份运行内观察到一次 HTTP 500**（路径 `/api/tasks/21`）。**根因未确认**；**不确定是否与历史 500 属于同一问题**。历史事件不结案、不重跑。 |
| **临时文件** | 🟢 带外 | `.tmp_*.log` / `.tmp_migrate_setters.py` 等为本轮调试产物，删除受 `[destructive-guard]` 约束，**留带外**由 Controller / 用户处理。 |

---

## 8. 保护边界（本轮全程）

**零触碰**（红线路径）：

- `src/notes/**`
- `data/task_publisher.db` / `data/task_publisher.db-wal` / `data/task_publisher.db-shm`
- `config/config.json`

**未执行**：commit / push / reset / clean / stash / checkout / switch。

**未绕过**任何 hook / 门禁。`[destructive-guard]` 拦截的操作保持拦截
（本轮尝试删除临时文件被拒 → 保留文件，带外处理）。
