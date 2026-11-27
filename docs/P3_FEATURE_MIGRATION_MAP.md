# P3 前端 Feature 迁移地图（AR03-P3）

> 日期：2026-11-21
> 范围：**前端**（`static/`）Feature 模块化 —— P3-A / P3-B / P3-C / P3-D /
> P3-E / P3-F 六个切片。
> 性质：**新增** 文档，**不覆盖** 任何历史交付记录。

---

## 0. 阅读指引

本文件回答一个问题：**每一条前端业务逻辑现在归谁所有？**

判定口径只有两条，且都是 **机械** 的：

1. **状态所有权**：一份状态有且只有一个 owner（闭包私有），其余地方只经
   getter / setter 访问。
2. **实现所有权**：一段业务实现有且只有一个落点；classic 层只保留
   **纯委托 facade**。

凡是"两边都有一份实现"或"两边各有一份状态"，都算迁移 **未完成**。

---

## 1. 总览：六个切片的迁移结果

| 切片 | 主题 | 迁移前 | 迁移后 |
|---|---|---|---|
| **P3-A** | 自由卡接受 / 结束全流程 | 全部在 `static/app.js`（≈800 行） | `static/modules/free-card/index.js` 的 `createFreeCardOwner`；`app.js` 只剩 7 个薄 facade |
| **P3-B** | 任务列表 / 标签 / 筛选 / 网格渲染 | `app.js` 持有 `allTasks` / `allTags` / `selectedTagFilter` 三个数组副本 | `static/modules/tasks/index.js` 的 `createTasksOwner` 闭包持有；`window.*` 退化为 **只读实时 getter** |
| **P3-C** | 计时器 | 两个 session getter（`getSession` + `getActiveSession`）、两个 interval（Dock + 任务面板） | 单一 `getSession` + 单一主节拍 `tickHandle`；任务面板编排归位 `static/modules/timer/index.js` |
| **P3-D** | 内核 / 共享层 | `core/state.js` 的 `createStore` 从未被真实调用；`shared/formatters.js` 与 `app.js` 各自一份时间格式化 | `createDerivedMap` 首次真实启用（id → name 只读派生映射）；格式化收敛为 `shared/formatters.js` 单一权威 |
| **P3-E** | 模块边界机械检查 | `scripts/check_module_imports.js` 只查 4 类边界，缺口 F 未消 | 新增循环依赖检测、唯一状态所有权、`app.js` 可写全局白名单、生命周期分级检查；`--json` 机读输出 |
| **P3-F** | 装配根与生命周期分级 | `app.entry.js` 与 `app.js` 都在创建 owner；页面切换会 unmount 全局能力 | `app.entry.js` = **唯一装配根**；显式 `APP_SCOPED_MODULES = ['timer', 'gacha']` |

---

## 2. P3-A：自由卡（Free-Card）

### 2.1 唯一 owner

`static/modules/free-card/index.js` → `createFreeCardOwner(deps)`

闭包私有状态（owner 内部，与 classic 层零共享）：

- 接受表单的 DOM 构造与当前编辑中的 `taskId`；
- 结束表单的 outcome / 中断原因 / 备注；
- 建议缓存与建议请求的 in-flight 标记。

### 2.2 classic 层保留的 facade（**全部返回 Promise**）

| facade | 说明 |
|---|---|
| `openFreeCardAcceptForm(taskId, values)` | 打开接受表单 |
| `cancelFreeCardAcceptForm(taskId)` | 取消接受表单 |
| `submitFreeCardAccept(taskId)` | 提交接受（**必须 return promise**，否则 `await` 落空） |
| `suggestFreeCardActivity(taskId)` | 「帮我选」建议 |
| `openFreeCardEndForm(taskId)` | 打开结束反馈表单 |
| `cancelFreeCardEndForm(taskId)` | 取消结束反馈表单 |
| `submitFreeCardEnd(taskId)` | 提交结束反馈（**必须 return promise**） |

> **踩坑记录（已修）**：`app.js` 的 facade 一开始写成
> `owner.submitFreeCardAccept(taskId)`（**没有 return**）。调用方
> `await app.submitFreeCardAccept(42)` 会 **同步** 拿到 `undefined`，
> 于是 HTTP 请求还没发出就被判定为"已完成"。测试表现为 41 条失败。
> 修复：所有异步 facade **必须 return** owner 返回的 promise。

### 2.3 静态源码合同的锚点迁移

AR03-P3 之后，自由卡实现的落点从 `app.js` 变成 owner 模块。原合同测试
（`test_free_card_acceptance_contract.py`、`test_m02_behavior_frontend_core.py`、
`test_task_discard_restore_owner.py`）若继续断言 `app.js` 的源码文本，
就会变成 **测门面壳子** 的假绿 / 假红。

处置：新增 `_free_card_impl_body(name)` 解析器 —— **owner 模块优先**，
其次才回落到 `app.js`（dock 编排等仍在 classic 层的实现）。
**语义保证不变**，只是锚点跟着实现走。

---

## 3. P3-B：任务（Tasks）

### 3.1 唯一 owner

`static/modules/tasks/index.js` → `createTasksOwner(deps)`

闭包私有状态：

| 状态 | 说明 |
|---|---|
| `tasks` | 任务列表（**唯一权威**） |
| `tags` | 标签集合（**唯一权威**） |
| `selectedTagFilter` | 当前标签筛选（**唯一权威**） |
| `rendering` | 渲染防重入标志 |

### 3.2 classic 层的兼容面（**只读实时 getter，不是副本**）

```javascript
Object.defineProperty(window, 'allTasks',          { get: ... });  // → owner.getTasks()
Object.defineProperty(window, 'allTags',           { get: ... });  // → owner.getTags()
Object.defineProperty(window, 'selectedTagFilter', { get: ... });  // → owner.getSelectedTagFilter()
```

**为什么是 getter 而不是数组**：如果 classic 层保留一份数组副本，就会出现
两个权威 —— 一份改了另一份没改，"谁是真相"立刻模糊。getter 每次读取直达
owner 闭包，**不存在第二份状态**。

**代价（已处理）**：直接赋值 `app.allTasks = [...]` 会被 **静默忽略**
（non-writable getter）。这正是我们要的 —— 权威数据只有一处 ——
但 **测试夹具** 必须改用显式窄 setter：

```javascript
app.__setAllTasks([...])   // → owner.setTasks([...])
app.__setAllTags([...])    // → owner.setTags([...])
```

> **踩坑记录（已修）**：`test_card_type_frontend.py` 里有 11 处
> `app.allTasks = [...]`，在 P3-B 之后全部静默失效 → 5 条测试失败。
> 修复：机械迁移到 `app.__setAllTasks([...])`，并在该沙箱里注入真实
> tasks owner（`vm.SourceTextModule` + `--experimental-vm-modules`）。

### 3.3 任务下拉框的 DOM 归属

`#timerTaskSelect`（计时面板的任务下拉框）是 **计时面板的 DOM** →
归 **Timer Owner** 渲染；Tasks Owner 只提供数据（`getTasks()`）。
classic 层 **不** 保留第二份下拉框渲染实现。

---

## 4. P3-C：计时器（Timer）

### 4.1 单一 session getter

| 迁移前 | 迁移后 |
|---|---|
| `getSession()`（owner 内）<br>`getActiveSession()`（presentation 内） | **只有** `getSession()` |

presentation 层改为调用 owner 的 `getSession()`，不再有第二套读取路径。

### 4.2 单一主节拍句柄

| 迁移前 | 迁移后 |
|---|---|
| Dock 的 `setInterval`<br>任务面板的 `setInterval` | **单一** `tickHandle`（`startTick()` / `stopTick()` / `hasTick()`） |

`inlineTickHandle` 保留 —— 它是 **卡内局部显示** 的节拍（"已抽出的卡片上那个
小计时器"），读 **同一个** session，但句柄独立。

### 4.3 渲染层 / 服务层解耦（关键）

> 「**是否重绘任务面板**」是 **渲染层** 判断；
> 「**计时是否继续运行**」是 **服务层** 判断 —— 两者不得互相牵连。

单一 tick 每秒执行：`owner.updateDock()`（**总是**）+ `owner.updatePanel()`
（**仅当** `#page-tasks` 处于 `active`）。因此任务面板切换不打断计时，
计时也不强迫非活动页面重绘。

### 4.4 任务面板编排归位

以下原本在 `app.js` 的编排逻辑迁入 `static/modules/timer/index.js`：

- `startTimerFromPanel()` —— 开始计时（含「已有进行中的计时」「请选择任务」
  「分钟数兜底 30」）；
- `stopTimerFromPanel()` —— 停止计时（无 session → toast；有 → 弹结论模态）；
- `handleTimerOutcome(outcome)` —— 结束结论（`completed` / `abandoned`，
  `actual_minutes` 由 owner 统一计算；失败 **必须保留** 活动 session）。

注入依赖：`toast` / `showModal` / `closeModal` / `warmMessages` /
`submitTaskFeedbackEvent` / `onTasksChanged` / `onGachaStatsChanged` /
`reloadTimerPanel`。

### 4.5 新增契约测试

`tests/characterize/test_timer_single_source_contract.py`（23 条断言）：

- 单一 session getter 声明；
- 单一主 interval 节拍句柄；
- 面板编排归属 owner；
- 合成 DOM 上的行为探针（含 **活跃 interval 计数** 探针 —— 只数
  `setInterval` 调用次数会把"已清除的旧句柄"也算进去，必须跟踪
  **存活** 的 interval）。

---

## 5. P3-D：内核 / 共享层（Core / Shared）

### 5.1 `core/state.js` → `createDerivedMap` 首次真实启用

`createStore` 一直是"写了但没人用"。P3-D 引入并 **真实启用**
`createDerivedMap(readSource, options)`：

```javascript
// app.js
var taskNameById = SAL.core.state.createDerivedMap(function () {
  return _getTaskNameMap();     // ← Tasks Owner 的 getter
});
// 使用
taskNameById.lookup(id);        // → 任务名（未命中回落）
```

**为什么不是 `createStore` 镜像整个 `allTasks`**：镜像 = 第二份状态 =
双权威。派生映射只保存 **id → name** 的只读查找缓存，**不** 复制任务对象，
刷新时机由 source 决定（`refresh()`）。

提供的能力：`refresh()` / `lookup(key, fallback)` / `has(key)` /
`snapshot()` / `size()`。

### 5.2 `shared/formatters.js` 收敛为唯一权威

新增 / 收敛：

| 函数 | 语义 | 备注 |
|---|---|---|
| `formatElapsedMs(ms)` | 时长格式化 | 计时器唯一实现 |
| `formatDiscardTimestamp(ts)` | **绝对** 时间戳 | "2026-11-21 23:00" |
| `formatRelativeTime(ts)` | **相对** 时间 | "X 分钟前" |
| `formatTimerMMSS(ms)` | `MM:SS` | |
| `todayDateStr()` | 今天日期 | |
| `formatHHMM(ts)` | `HH:MM` | |

> **踩坑记录（已修）**：`shared/formatters.js` 里的相对时间格式化与
> `app.js` 里的绝对时间格式化 **语义相撞**，差点造成行为漂移。
> 修复：拆成 `formatDiscardTimestamp`（绝对）与 `formatRelativeTime`（相对）
> 两个语义明确的函数，`app.js` 的 `formatDiscardTime` 委托给前者。

### 5.3 `shared/timer.js` 去重

`shared/timer.js` 保持 **只读适配** 角色：它只提供纯计算，不持有任何
计时状态。计时状态 **全部** 归 `modules/timer/index.js` 的 owner 闭包。

---

## 6. P3-E：模块边界机械检查强化

### 6.1 新增规则

| 规则 | 名 | 违规案例 |
|---|---|---|
| ⑥ | **循环依赖检测** | `modules/tasks/index.js` ↔ `modules/gacha/index.js` 互相 import → ESM 初始化顺序让一方顶层状态未就绪。**只在运行时暴露，极难定位** → 必须机械拦截。 |
| ⑦ | **唯一状态所有权** | owner 把 session 挂到 `window.__mySession` → 同一份状态两个所有者，谁最后写谁赢。 |
| ⑧ | **`app.js` 白名单** | 迁移完自由卡后又写 `window.__gachaCache` → 逃过 owner 化，"谁是权威"再次模糊。 |
| ⑨ | **生命周期分级** | 页面级模块的 `unmount` 调了 timer owner 的 `clear()` → 切页时清掉进行中的计时。 |

### 6.2 白名单的可 review 性

白名单每一条都 **必须写明为什么它必须留在全局**（内联 handler 名字 /
装配接口 / 兼容别名 / 诊断只读 getter）：

```javascript
const APP_JS_GLOBAL_WHITELIST = {
  'renderDrawnCardResult': '抽卡结果渲染入口（classic 层既有全局名）',
  '__setTimerOwner': '装配接口：注入应用级计时 owner',
  // ...
};
```

**没有理由的白名单条目 = 形式主义登记 = 单体重新膨胀的入口** ——
`test_module_boundary_contract.py` 有一条断言专门守这个。

### 6.3 `--json` 机读输出

```json
{
  "modules": ["agent-readonly", "...", "timer"],
  "appScopedModules": ["timer", "gacha"],
  "violations": [],
  "ok": true
}
```

可直接作为 CI / 回归门禁输入。

---

## 7. P3-F：装配根与生命周期分级

### 7.1 生命周期分级表（**本次装配的核心约束**）

| 级别 | 模块 | 生命周期语义 |
|---|---|---|
| **应用级（app-scoped）** | **`timer`**、**`gacha`** | **应用启动即创建，页面切换永不 unmount。** 计时 session / paused / tick handle / 抽卡 session / 换卡链在整个应用生命周期内持续有效。 |
| **页面级（page-scoped）** | `tasks` / `lifecycle` / `free-card` / `schedule` / `knowledge` / `config` / `prompts` / `agent-readonly` / `sleep` / `state-assessment` | `page:change` → `mount` / `unmount`；`unmount` 只释放 **本模块自己的** interval / 监听，**不得** 清掉其他模块的状态。 |

### 7.2 为什么 `timer` 必须是应用级

> 用户在 **任务页** 启动计时 → 切到 **其他页** → Dock 仍在显示、计时仍在走
> → 用户在另一页完成 / 取消计时。

若 timer 随任务页 `unmount` 而停止 tick 或清空 session，会导致：
Dock 时间停住、刷新后恢复不到、另一页无法结束计时 ——
**这是功能回归，不是架构洁癖**。

### 7.3 为什么 `gacha` 也是应用级

抽卡 session / 换卡链是 **跨页面的连续概念**：换卡链必须沿用同一个
session，离开抽卡页才结束。因此 `modules/gacha/index.js` **不再** 导出
`meta` / `mount` / `unmount`，改用 **应用级启动钩子** `initAppScoped()`
（**幂等**：只做一次性全局接线）。

### 7.4 装配根的收敛

`static/app.entry.js` 现在是 **唯一装配根**：

- **静态 import** 全部 owner 模块（含新增的 `timerModule`）；
- 在 **模块入口执行阶段** 创建唯一实例（**同步**，不依赖动态 import 的
  异步时序）；
- 经 `window.__set<X>Owner` 注入 classic 层；
- `APP_SCOPED_MODULES = ['timer', 'gacha']` 是生命周期分级的 **唯一权威**。

**经典层只暴露窄装配接口**（依赖清单只保留一份，避免两处漂移）：

| 装配接口 | 作用 |
|---|---|
| `window.__createFreeCardOwner(module)` / `window.__setFreeCardOwner(owner)` | 自由卡 owner |
| `window.__createTasksOwner(deps)` / `window.__setTasksOwner(owner)` | 任务 owner |
| `window.__createTimerOwner(module)` / `window.__setTimerOwner(owner)` | 计时 owner（**新增**，应用级） |
| `window.__getFreeCardOwnerSync()` / `window.__getTasksOwnerSync()` / `window.__getTimerOwnerSync()` | **同步探针**：装配根在创建前先问 classic 层「是否已有 owner」（**唯一实例** 不变式，验收期新增） |

> **为什么需要同步探针**：classic `app.js`（同步执行）与 ESM `app.entry.js`
> （deferred）**都能**创建 owner，动态 import 又是异步的 → 两条路径可能
> 各建一个实例 → 旧实例的 interval 每秒用空状态覆盖 DOM →
> **「状态对但界面不动」**。三层防护见 `docs/P3_HANDOFF_TO_P4.md` §4.4。

---

## 8. 未迁移的部分（如实记录）

| 项 | 状态 | 说明 |
|---|---|---|
| `static/free-task.js` | ⏳ **有意保持不动** | 用户明确选择 `leave_untouched`。该文件是既有隔离原型，**不是** 已批准的卡优先用户旅程的证据。 |
| `src/index.html` 的 inline handler | ⏳ 保持 | 内联 handler 依赖既有全局名（`drawGacha()` / `openTaskEdit()` / …）。这些名字由 `app.entry.js` 的 facade 提供，**语义不变**。 |
| `modules/*/presentation.js` | ✅ 保持 | 纯渲染层，无状态。 |
| `app.js` 的其余业务 | ⏳ **部分保留** | `app.js` 仍是 `3482 → 2935` 行。剩余部分以 **DOM 适配器 / 纯 facade / 既有全局入口** 为主，详见 `docs/P3_FRONTEND_MODULARIZATION_DELIVERY_20261121.md` §4。 |

---

## 9. 保护边界（本轮全程）

**零触碰**：

- `src/notes/**`
- `data/task_publisher.db` / `data/task_publisher.db-wal` / `data/task_publisher.db-shm`
- `config/config.json`

**未执行**：commit / push / reset / clean / stash / checkout / switch。

**未绕过**任何 hook / 门禁；`[destructive-guard]` 拦截的删除操作保持拦截
（临时文件留在工作区，由 Controller / 用户带外处理）。
