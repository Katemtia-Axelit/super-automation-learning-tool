# P3 → P4 交接说明（AR03-P3 → AR03-P4）

> 日期：2026-11-21
> 性质：**新增** 文档，**不覆盖** 任何历史交付记录。

---

## 1. 验收表（本轮实际运行结果）

| 项 | 命令 | 结果 |
|---|---|---|
| 模块边界门禁 | `node scripts/check_module_imports.js` | 退出码 **0**（`violations: []`） |
| 模块边界门禁（机读） | `node scripts/check_module_imports.js --json` | `ok: true`，`appScopedModules: ["timer","gacha"]` |
| 全量 characterization | `python -m pytest tests/characterize -q` | **1653 passed / 0 failed / 10 skipped / 442 subtests** |
| P0 契约 | `python scripts/verify_p0_cleanup.py` | **ALL ASSERTIONS PASSED**（T1–T6），退出码 0 |
| 隔离 E2E | `node scripts/run_e2e_isolated.js` | **36/36 PASS**（退出码 0；fs 守卫 + server 侧审计 + 合成根自证三重零触碰） |

### 1.1 验收期间修复的两处功能回归

最终验收 **不是一次通过** —— 它真实暴露了两处功能回归（详见交付说明 §3.0）：

| 回归 | 症状 | 修复 | 闸门 |
|---|---|---|---|
| **唯一实例不变式被破坏** | 计时器不走动（面板一直 `未在计时`，而后端已返回 `session_id`、owner 内部 session 已就绪） | classic 降级路径与 ESM 装配根两层防护 + 装配根复用已有 owner | `SingleOwnerInstanceTests`（13 条） |
| **`createDerivedMap` 原型链陷阱** | 任务列表渲染整体抛 `TypeError: Cannot convert undefined or null to object` | 取值器改判 **自有属性**（`hasOwnProperty.call`） | `test_derived_map_contract.py`（11 条，含 Node 运行期验证） |

> **P4 提示**：这两处都不是「重构风格问题」，而是 **用户可见的功能失效**。
> 症状迷惑性极强（状态对、界面不动），因此都以契约测试锁定。

### 1.2 characterization 结果

> 本轮实际运行结果记录在 `docs/CURRENT_PROJECT_STATE.md` 的最新基线段落。
> **不** 把动态计数硬编码进 Rules 或 Skills。

---

## 2. P3 交付了什么（交接摘要）

### 2.1 前端 Feature owner 化

| 模块 | owner 工厂 | 落点 |
|---|---|---|
| 自由卡 | `createFreeCardOwner` | `static/modules/free-card/index.js` |
| 任务 | `createTasksOwner` | `static/modules/tasks/index.js` |
| 计时（**应用级**） | `createTimerOwner` | `static/modules/timer/index.js` |
| 抽卡（**应用级**） | `createGachaOwner` | `static/modules/gacha/index.js` |
| 任务编辑器 | `createTaskEditorOwner` | `static/modules/tasks/editor.js` |
| 任务生命周期 | `createTaskLifecycleOwner` | `static/modules/tasks/lifecycle.js` |

### 2.2 唯一装配根

`static/app.entry.js` —— 静态 import 全部 owner 模块 → 装配阶段 **同步**
创建唯一实例 → 经 `window.__set<X>Owner` 注入 classic 层。

装配接口（classic 层只暴露这些窄接口，依赖清单唯一）：

```javascript
window.__createFreeCardOwner(module) / window.__setFreeCardOwner(owner)
window.__createTasksOwner(deps)      / window.__setTasksOwner(owner)
window.__createTimerOwner(module)    / window.__setTimerOwner(owner)
window.__getFreeCardOwnerSync()       // 同步探针：装配根判「是否已有 owner」
window.__getTasksOwnerSync()          // 同上
window.__getTimerOwnerSync()          // 同上（**唯一实例** 不变式，见 §4.4）
window.__setAllTasks(list)            // 窄 setter（owner 权威）
window.__setAllTags(list)             // 窄 setter（owner 权威）
```

### 2.3 生命周期分级（**P4 必须继承的核心约束**）

```javascript
// static/app.entry.js
const APP_SCOPED_MODULES = ['timer', 'gacha'];
```

| 级别 | 模块 | 约束 |
|---|---|---|
| **应用级** | `timer` / `gacha` | 应用启动即创建；**页面切换永不 unmount**；**不得**导出 `meta`/`mount`/`unmount`；**不得**进 `MODULE_CONTRACTS` |
| **页面级** | 其余 | `page:change` → `mount`/`unmount`；`unmount` **不得**触碰应用级状态 |

### 2.4 内核真实启用

- `core/state.js::createDerivedMap(readSource, options)` —— 首次真实启用
  （id → name 只读派生映射，**不** 镜像整个 `allTasks`）。
- `shared/formatters.js` —— 唯一格式化权威（绝对时间 `formatDiscardTimestamp`
  与相对时间 `formatRelativeTime` **语义分离**）。

### 2.5 边界门禁强化

`scripts/check_module_imports.js` 新增 4 类规则 + `--json` 机读输出：

| 规则 | 名 | 拦截什么 |
|---|---|---|
| ⑥ | 循环依赖 | Feature 模块 import 图成环 |
| ⑦ | 唯一状态所有权 | `modules/*` 内 `window.<x> =` 写全局状态 |
| ⑧ | `app.js` 白名单 | 未登记的可写全局（每条必须写明理由） |
| ⑨ | 生命周期分级 | 应用级模块实现页面级契约 / 页面级 `unmount` 清理应用级状态 |

---

## 3. 新增 / 修改的测试

| 文件 | 类型 | 作用 |
|---|---|---|
| `tests/characterize/test_timer_single_source_contract.py` | 新增 | 单一 session getter / 单一主节拍 / 面板编排归属 |
| `tests/characterize/test_module_boundary_contract.py` | 新增 | P3-E 规则的 pytest 门禁 |
| `tests/characterize/test_module_lifecycle_contract.py` | 新增 | P3-F 生命周期分级 + **唯一实例不变式**（`SingleOwnerInstanceTests`） |
| `tests/characterize/test_derived_map_contract.py` | 新增 | **P3-D** 只读派生映射契约 + **运行期**验证（原型链陷阱） |
| `tests/characterize/test_free_card_acceptance_contract.py` | 修改 | 契约锚点跟随实现（owner 优先解析） |
| `tests/characterize/test_card_type_frontend.py` | 修改 | 沙箱注入真实 tasks owner + 窄 setter 迁移 |
| `tests/characterize/test_m02_behavior_frontend_core.py` | 修改 | 自由卡建议合同改锚点 |
| `tests/characterize/test_task_discard_restore_owner.py` | 修改 | `move-to-discard` 断言改锚点 |

---

## 4. P4 必须知道的三件事（**易踩坑**）

### 4.1 `window.allTasks` / `allTags` / `selectedTagFilter` 是 **只读 getter**

```javascript
app.allTasks = [ ... ];      // ❌ 静默失败（non-writable getter）
app.__setAllTasks([ ... ]);  // ✅ 显式窄 setter → owner.setTasks()
```

**为什么**：如果 classic 层保留一份数组副本，就会出现两个权威。getter 每次
读取直达 owner 闭包，**不存在第二份状态**。

**新代码一律用 getter 读、用 `__setAllTasks` / `__setAllTags` 写。**

### 4.2 `app.js` 的 facade **必须 return promise**

```javascript
// ❌ 调用方 await 到 undefined，HTTP 请求还没发出就被判定为"完成"
function submitFreeCardAccept(taskId) {
  owner.submitFreeCardAccept(taskId);
}
// ✅
function submitFreeCardAccept(taskId) {
  return owner.submitFreeCardAccept(taskId);
}
```

这曾导致 41 条测试失败。**任何转发到 owner 的异步 facade 都必须
`return`。**

### 4.3 静态源码合同必须锚定 **实现**，不能锚定 facade

模块化把实现搬进了 owner 模块。若合同测试继续断言 `app.js` 的源码文本，
它们就变成 **测门面壳子** 的假绿 / 假红。

**新增合同测试时的做法**：用 `_free_card_impl_body(name)` 这样的解析器
（owner 模块优先 → 回落到 `app.js`），或直接断言 owner 模块源码。

### 4.4 🔴 **唯一实例** 不变式（装配根与 classic 降级路径并存时的头号坑）

`static/app.js` 是 **classic script**（同步执行），`static/app.entry.js` 是
**`type=module`**（deferred）。两者都能创建 owner：

| 路径 | 时机 | 是否异步 |
|---|---|---|
| classic `app.js` | 同步执行体末尾 `loadTimerPanel()` / `initTimerDock()` → `_get*Owner()` → 动态 import | **是** |
| 装配根 `app.entry.js` | app.js 同步体 **之后** | 否 |

**若两条路径各建一个实例**：

- 用户操作写进 **实例 B**（session / 状态），
- **实例 A** 的 interval 仍在跑，每秒用 **A 的空状态** 覆盖同一份 DOM。

症状极其迷惑：**「状态明明对，界面却不动」**。P3 验收期就撞上了这个 ——
E2E 3.3「开始计时」失败（面板一直 `未在计时`），而后端已返回
`session_id`、owner 内部 `session` 也已就绪。

**P4 新增任何 owner 模块时，必须照抄这套三层防护**：

```javascript
// 1) classic 层：注入 setter —— 已有 owner 时绝不替换
function _setXOwner(owner) {
  if (_xOwner) { /* 告警 */ return; }
  _xOwner = owner;
}

// 2) classic 层：动态 import 兜底 —— 创建前先检查
.then(function (mod) {
  if (_xOwner) return _xOwner;      // ← 绝不创建第二个
  _xOwner = _createXOwner(mod);
  return _xOwner;
});

// 3) 装配根：创建前先问 classic 层
const existing = window.__getXOwnerSync ? window.__getXOwnerSync() : null;
const xOwner = existing || window.__createXOwner(xNamespace);
window.__setXOwner(xOwner);
```

闸门：`test_module_lifecycle_contract.py::SingleOwnerInstanceTests`
（13 条断言，含「classic 层只能有一个 owner 引用变量」）。

### 4.5 🔴 `options` 的取值器必须判 **自有属性**

```javascript
// ❌ Object.prototype.valueOf 本身就是一个函数 → typeof 判定通过
const valueOf = typeof opts.valueOf === 'function' ? opts.valueOf : def;

// ✅ 原型链上的内置方法同样是函数，必须先判自有属性
const hasValueOf = Object.prototype.hasOwnProperty.call(opts, 'valueOf');
const valueOf = hasValueOf && typeof opts.valueOf === 'function' ? opts.valueOf : def;
```

**症状**：`TypeError: Cannot convert undefined or null to object`，
抛点藏在派生映射内部，栈顶却像 `Object.keys` —— 极易误判方向。

闸门：`test_derived_map_contract.py`（11 条断言，含 Node 运行期验证）。

---

## 5. P4 的候选方向（本轮 **未** 实施，需主控 / 用户确认）

| 方向 | 说明 | 现状 |
|---|---|---|
| **进一步瘦身 `app.js`** | 当前 2935 行，主体是 DOM 适配器 / 纯 facade / 既有全局入口 | 边界门禁已阻止无声回涨；进一步瘦身需独立切片 |
| **`src/index.html` inline handler 收敛** | 内联 handler 依赖既有全局名 | 需要与 E2E 同步；本轮 **零改动** |
| **`static/free-task.js` 处置** | 既有隔离原型 | 用户明确 `leave_untouched`；**不是** 已批准卡优先旅程的证据 |
| **M05 外部 Agent 交互** | 无模型 API 的一键复制 / 同意预览导出 / 手动粘贴提案 | 按 `NO_API_AGENT_INTERACTION_PRODUCT_DIRECTION_20261023.md`；**尚未授权实施** |
| **M03 全日历** | — | **已延期** |
| **M04 视觉改版** | — | **已延期** |

> 正式授权仍遵循 **里程碑审批规则**：P4 的具体范围需由主控在确认当前
> 里程碑与目标后授权。

---

## 6. 保护边界（P4 同样适用）

**零触碰**：

- `src/notes/**`
- `data/task_publisher.db` / `data/task_publisher.db-wal` / `data/task_publisher.db-shm`
- `config/config.json`

**约束**：

- 不 commit / push / reset / clean / stash / checkout / switch；
- 不绕过任何 hook / 门禁；
- 既有 dirty / untracked 工作区内容一律保护，不清理、不归因。

---

## 7. 未决项（移交主控 / 用户）

| 项 | 类型 | 说明 |
|---|---|---|
| **P1 独立验收会签** | 流程 | 状态 `READY_FOR_INDEPENDENT_ACCEPTANCE`（外部待会签）。**不追溯修改**。 |
| **P2 门禁违规** | 流程 | 未取得 P1 会签即进入 Stage 1–8。如实在案。 |
| **`server/app/legacy_compat.py` 物理删除** | 带外 | 受 `[destructive-guard]` 约束。 |
| **`scripts/_probe_task_get_500.py`** | 带外 | 受 `[destructive-guard]` 约束。 |
| **本轮临时文件** | 带外 | `.tmp_*.log` / `.tmp_migrate_setters.py` 等；删除被 `[destructive-guard]` 拦截，留带外处理。 |
| **历史一次性 `/api/tasks/{id}` 500** | 观察 | P3 最终隔离 E2E：**36/36 测试通过**；**同一份运行内观察到一次 HTTP 500**（路径 `/api/tasks/21`）。**根因未确认**；**不确定是否与历史 500 属于同一问题**。不结案、不重跑。 |
| **`/api/health` 形状统一** | P5 | 沿用 P2 移交项。 |
| **legacy 换牌历史缺陷的数据修复** | 需单独评估 | P2 / P3 均不触碰生产数据。 |
| **Gacha 策略系数产品语义** | 待用户裁决 | 沿用 P2 移交项。 |
| **dual-vault 布局契约** | 历史未决 | 沿用 P2 移交项。 |
