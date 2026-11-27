# P3 前端 Bug 修复独立验证报告

> **验证者角色**：独立 QA 验证工程师。不信任开发 Agent 自报，只信证据。
> **验证日期**：2026-08-05（UTC+8：~23:30-次日 00:15）
> **分支**：`main`（未合并 P3 改动，文件 `M` 状态）
> **Python**：`C:\Users\wn\AppData\Local\Programs\Python\Python312\python.exe`

---

## 一、验证范围

### 改动文件（`git diff` 统计）

| 文件 | 改动行 |
|------|--------|
| `server/backend_api.py` | +78 / -3 |
| `src/index.html` | +4 / -2 |
| `static/app.js` | +158 / -11 |
| `tests/e2e-manual.js` | +304 / -11 |

### P3 Bug 修复对照（来自 `docs/FRONTEND_BUG_LIST_2026-08-04.md`）

| Bug ID | 描述 | 状态 |
|--------|------|------|
| 3.1 | 双计时器状态机（timerDockSession vs timerActiveSession） | ✅ 已修复（统一状态源） |
| 3.2 | 暂停本地模拟 vs 服务端脱节 | ✅ 已修复（pause/resume API） |
| 3.4 | 提前结束状态不一致 | ✅ 已修复（completeWithFeedback） |
| 3.8 | interval 未清理（计时加倍） | ✅ 已修复（clearInterval 在 setInterval 前） |
| 1.1 | repeat_type 'single' → 'none' | ✅ 已修复（commit 7e4aacf） |
| 1.5 | XSS 风险（task.name innerHTML） | ⚠️ 部分修复（仅 gacha drawn card，未覆盖 task list） |
| 5.3 | Markdown 解析简陋 | ✅ 已修复（marked.js） |
| 5.1 | 笔记全量加载再过滤 | ✅ 已修复（_noteCache） |

---

## 二、代码审查发现（13 条）

> 证据：`tests/diff_appjs.txt`、`tests/diff_backend.txt`、`tests/diff_index.txt`、`tests/diff_e2e.txt`

### 2.1 代码逻辑缺陷

| # | 文件 | 行号 | 问题 | 严重度 | 证据 |
|---|------|------|------|--------|------|
| C1 | `static/app.js` | ~L1761–L1796 | **`_noteCache` 缓存仅"单分类"有效**：`_noteCacheCat === catName` 检查只看"上一次加载的分类"，A→B 后再切回 A 时 `_noteCacheCat='B'`，不会命中 A 的缓存，需重新请求。实际退化为"只缓存最后一次"而非"按分类缓存" | 中 | `tests/probe_supplementary_run.log`：访问高等数学→大学物理→线性代数→高等数学，共产生 3 次 `/api/knowledge/notes` 请求；3 个分类均在 `cacheKeys` 中（因为每次都重新拉），缓存命中条件需同分类连续访问才生效 |
| C2 | `server/backend_api.py` | ~L3067–L3126 | **`api_timer_pause`/`resume` 忽略请求 body 中的 `session_id`**：服务端用 `ORDER BY started_at DESC LIMIT 1` 选最近一条。攻击者 POST 任意 `session_id` 可暂停/恢复他人计时器（本地单用户场景低风险） | 中 | diff_backend.txt L56：`body: JSON.stringify({ session_id: timerDockSession.id })`，但后端 L3075+ 无 `session_id` 参数绑定 |
| C3 | `static/app.js` | ~L414 | **`loadTimerDockActive` 同步条件无效**：`if (timerActiveSession !== timerDockSession)` 比较对象引用，但两者都是 `r && r.id ? r : null` 赋值，**引用相同**，分支永远不触发 | 低 | diff_appjs.txt L420+：引用相等，逻辑不执行；属于无效代码 |
| C4 | `static/app.js` | ~L421, L500, L523 | **`timerActiveSession = timerDockSession` 同步语义不清**：每次都直接赋值覆盖，未比较 ID；`loadTimerDockActive` 中的同步会导致 `timerActiveSession` 指向最新的 dock session（可能与 task page 的 local timer 冲突） | 低 | 同上，两处都执行 `timerActiveSession = timerDockSession`，无 ID 比对保护 |
| C5 | `static/app.js` | ~L2630 | **`loadTimerPanel` 中 paused 状态同步有条件**：`if (timerDockSession?.id === timerActiveSession?.id)` — 刷新后若 `timerDockSession=null`（dock 页未初始化），分支不进，`timerDockPaused` 不会从后端恢复。刷新后从 task 页独立打开时，可能不显示 paused 状态 | 中 | `tests/probe_3_1_run.log`：`timerPauseBtn` 显示 `title:"继续计时器"` + `fa-play`，说明 paused 状态被正确读取；但这是 `loadTimerDockActive` 初始化的，单独进 task 页时依赖 dock 的 `timerDockSession` |
| C6 | `tests/e2e-manual.js` | ~L49–L76 | **`cleanupExistingTimer` 清理逻辑破坏 paused 状态**：总是先 `resume` 再 `complete`，把 paused 会话当 running 处理，导致 `paused_seconds` 被计入 `actual_minutes`（E2E cleanup 清理不干净）。测试 3.8（暂停期间时间不跳变）结束后遗留 paused 会话，后继测试 3.1 受影响 | 中 | `tests/verify_run.log` L5：`{"cleaned":false,"error":"Failed to execute 'fetch' on 'Window': Failed to parse URL from /api/timer/active"}` — cleanup page 未加载 BASE_URL，`fetch` 无 base URL；导致 session 未被清理，后续 3.1 断言失败 |
| C7 | `static/app.js` | ~L2630 | **`updateTimerDockDisplay` 在 dock hidden 时提前 return**：`if (!idleEl || !activeEl) return;` — 若 `#timerDockIdle`/`#timerDockActive` 未渲染，dock 计时不更新；dock pause/resume 按钮在 hidden 时也会被跳过 | 低 | `app.js:434-448` |

### 2.2 边界与安全

| # | 文件 | 行号 | 问题 | 严重度 | 证据 |
|---|------|------|------|--------|------|
| **C8** | `static/app.js` | **~L333** | **⚠️ XSS 未修复（task list）**：`renderTasks()` 中 `.task-card-title` 用 `task.name` 直接 innerHTML 拼接，未调用 `escapeHtml()`。测试 payload `<img src=x onerror=alert("P3_XSS_HIT")>` 在 task list 渲染时触发浏览器 alert，**5 次**（task list + gacha deck + dep picker + timer select options 等多路径）。P3 只修复了 `renderDrawnCard`（gacha card），**task list、dependency picker、timer select option** 均未覆盖 | **高** | `tests/probe_xss_run.log`：`PROBE onerror scan` 显示 `<div class="task-card-title"><img src="x" onerror="alert(&quot;P3_XSS_HIT&quot;)"></div>`，alert fired 多次；源代码 `app.js:333`：`'<div class="task-card-title">' + task.name + '</div>'` |
| C9 | `server/backend_api.py` | ~L3086 | **`int()` 截断小数秒**：paused 时间四舍五入到秒，每次暂停丢弃 <1s。与前端 `Math.floor(elapsed/1000)` 对齐，无可见偏差 | 低 | `app.js:33-37` 与 `backend_api.py:3086` |
| C10 | `server/backend_api.py` | ~L3034 | **`api_timer_complete` 扩展到 paused**：允许结束 paused 状态会话（合理，cleanup 场景），但无权限校验（同 C2） | 低 | diff_backend.txt L28：`WHERE id=? AND status IN ("running", "paused")` |
| C11 | `tests/e2e-manual.js` | ~L559–L578 | **用例 3.5–3.8 的"已有会话"清理依赖 dialog 处理**：全局 `page.on('dialog', d => d.accept())` 在 cleanup 时已执行，测试 3.8 结束后遗留 paused 会话。清理步骤本身依赖 cleanup page 导航到 BASE_URL（见 C6） | 低 | `tests/verify_run.log` |

### 2.3 设计/注释问题

| # | 文件 | 行号 | 问题 | 严重度 | 证据 |
|---|------|------|------|--------|------|
| C12 | `static/app.js` | ~L128, L130, L132 | **`_noteCache` 注释与实际不符**：`// P3-Bug-D: 前端缓存已加载的笔记数据（按分类）` — 实际缓存效果是"按最近加载分类"，不是"按所有已访问分类"；注释高估了实现 | 低 | `tests/probe_supplementary_run.log`：访问 3 个分类后 `cacheKeys` 有 3 个 key，但访问顺序为 A→B→C→A，A 被访问了两次（A→B 时无命中，C→A 时无命中），3 个 key 存在但每次都重新拉数据 |
| C13 | `src/index.html` | ~L917–L919 | **`marked.min.js` 无 onerror 兜底**：若 CDN 或本地 vendor 路径失败，`mdToHtml` 进入 `typeof marked !== 'undefined'` 分支后才会回退；但 `marked` 本身未加载时 HTML 解析失败后代码继续执行；回退正则存在，但用户可能不会注意到渲染变化 | 低 | diff_index.txt L17 |

---

## 三、E2E 测试结果

> 证据：`tests/verify_run.log`
> **基线**（_run4.log）：26/26 全绿
> **本次**：30 项（含 4 项新增 P3 pause 测试）

### 3.1 测试摘要

| 测试组 | 用例 | 结果 |
|--------|------|------|
| 抽卡 | 1.1, 1.2, 1.3 | ✅ 3/3 通过 |
| 任务 | 2.1, 2.2, 2.3, 2.4, 2.5 | ✅ 5/5 通过 |
| **计时器** | **3.1** ⚠️, **3.2** ✅, **3.3** ⚠️ | ❌ 2 失败（见 3.2） |
| 计时器提前结束 | 3.4 | ✅ 通过 |
| 抽卡回归 | 1.4 XSS, 1.5 动画残留 | ✅ 2/2 通过 |
| 日程 | 4.1, 4.2, 4.3, 4.4 | ✅ 4/4 通过 |
| 知识库 | 5.1, 5.2 | ✅ 2/2 通过 |
| 设置 | 6.1, 6.2, 6.3, 6.4 | ✅ 4/4 通过 |
| **计时器暂停（P3-Bug-B）** | 3.5, 3.6, 3.7, 3.8 | ✅ 4/4 通过 |
| 全局 | 7.1, 7.2 | ✅ 2/2 通过 |
| **合计** | 30 | **28 通过 / 2 失败** |

### 3.2 失败用例分析

#### 失败 1：`3.1 计时器面板`（断言失败）

```
[测试] 3.1 计时器面板    ✗ 失败: 断言失败
```

**根因**：测试 3.8 结束后遗留 paused session 69（未清理），进入 3.1 时 `loadTimerPanel` 检测到活跃会话，`updateTimerDisplay()` 执行：`#timerStartBtn` 加 `hidden` 类 → `isVisible()` 返回 `false` → 断言失败。

**证据**：`tests/probe_3_1_run.log`
```
timerStartBtn: { classes: "btn pri sm hidden", visible: false }
timerStatusText: "计时中· 暂停E2E-D-1785985341979（计划 10 分） (已暂停)"
```

**是否 P3 相关**：否。是由 C6（cleanup 失效）引起的测试隔离问题，属测试脚本缺陷，非业务代码 bug。

**证据**：`tests/probe_3_3_run.log` 显示"修复后"（手动 cleanup）则 3.1 重跑通过：
```
3.1 retry: panel=true startBtn=true select=true
```

#### 失败 2：`3.3 开始计时`（超时）

```
[测试] 3.3 开始计时    ✗ 失败: page.waitForFunction: Timeout 30000ms exceeded.
```

**根因**：同失败 1 — 测试 3.1 的 paused session 阻塞了 `#timerTaskSelect`，使其保持 `disabled` 状态。`waitForFunction(() => s && !s.disabled && s.options.length > 1)` 永不满足，30s 超时。

**证据**：`tests/probe_3_1_run.log`
```
timerTaskSelect: { disabled: true, options: 377, firstOpt: "选择任务...", secondOpt: "暂停E2E-D-1785985341979" }
```

**是否 P3 相关**：否。同上，由测试隔离问题引起。

### 3.3 P3 新增测试（暂停功能）

| 测试 | 结果 | 证据 |
|------|------|------|
| 3.5 暂停状态保持 | ✅ | `verify_run.log` |
| 3.6 刷新后恢复 | ✅ | `verify_run.log` |
| 3.7 恢复后继续 | ✅ | `verify_run.log` |
| 3.8 暂停期间时间不跳变 | ✅ | `verify_run.log` |

4/4 通过。但需注意：测试在 cleanup 页未正确导航的条件下仍通过，说明 **pause/resume API 本身工作正常**（跨页面/跨 session 边界均有效）。

---

## 四、补充探测（超出清单）

### 补充 1：XSS 多路径验证 ⚠️ 新发现

**Payload**：`<img src=x onerror=alert("P3_XSS_HIT")>`
**方法**：E2E probe 脚本，在 task list + task modal + timer select + dep picker 中验证

**发现**：3 个路径均未转义：

| 路径 | 证据 |
|------|------|
| **task list（renderTasks）** `.task-card-title` | `tests/probe_xss_run.log`：`"<div class="task-card-title"><img src="x" onerror="alert(&quot;P3_XSS_HIT&quot;)"></div>"` + alert fired |
| **timer select options** `#timerTaskSelect option` | `tests/probe_xss_run.log`：`"<option value="488">&lt;img src=x onerror=alert("P3_XSS_HIT")&gt;</option>"` — innerHTML 在 option 内，浏览器解析 |
| **dep picker labels** `#tfDepList label` | `tests/probe_xss_run.log`：`"<label>... <img src="x" onerror="alert(1)"> ..."` |

**严重度**：高（任意用户输入的任务名均可执行 JS）

**证据源码**：`app.js:333` — `'<div class="task-card-title">' + task.name + '</div>'`（无 `escapeHtml`）

### 补充 2：`_noteCache` 行为验证

**方法**：访问分类 A→B→C→A，监控 `/api/knowledge/notes` 请求次数

**结果**：
- 3 次请求（A→B、B→C、C→A 各触发一次）
- `_noteCache` 字典有 3 个 key，但缓存命中条件为 `_noteCacheCat === catName`
- 连续访问同一分类可复用；切换后再切回则需重新请求

**结论**：缓存有效，但注释夸大。实测符合"单分类单次有效缓存"实现。

**证据**：`tests/probe_supplementary_run.log`

### 补充 3：dock → tasks 同步验证（stopTimerFromDock）

**方法**：tasks 页启动计时 → gacha 页 dock stop → tasks 页检查 UI 状态

**结果**：
- `stopTimerFromDock` 正确调用 `/api/timer/complete`
- 正确清空 `timerDockSession` 和 `timerActiveSession`
- 正确触发 `updateTimerDockDisplay()` 和 `updateTimerDisplay()`

**结论**：P3-A 同步修复有效。

---

## 五、总结

### 5.1 P3 修复质量评估

| 维度 | 评价 |
|------|------|
| **计时器暂停持久化（核心 P3）** | ✅ 优秀：后端 API 正确设计（pause/resume），前端调用链路完整，4 项 E2E 全绿 |
| **双状态机统一（P3-A）** | ✅ 基本正确：dock → tasks 同步基本生效；边缘情况（C5）存在但不阻断 |
| **计时器 interval 清理（P0-1）** | ✅ 已修复：`clearInterval(timerDockTick)` 在 `setInterval` 前执行 |
| **XSS 防护（P1-3）** | ⚠️ **不完整**：gacha drawn card 已修复，但 task list、timer select、dep picker 均未覆盖 |
| **marked.js 集成** | ✅ 正确：vendor 文件存在（`static/vendor/marked.min.js`，36054 字节），fallback 正则保留 |
| **E2E 覆盖率** | ✅ 良好：新增 4 个 pause 场景，清理逻辑完善（但有 bug，见 C6） |

### 5.2 优先级建议

| # | 问题 | 严重度 | 行动 |
|---|------|--------|------|
| **1** | XSS：task list / timer select / dep picker 未转义 | **高** | 紧急：修复 `renderTasks` 中 `task.name` + `task.description` 的 innerHTML 拼接 |
| **2** | `cleanupExistingTimer` 清理逻辑破坏 paused 状态（e2e 测试隔离 bug） | 中 | 修复：cleanup page 应先导航到 BASE_URL，或在 cleanup 后验证 API 状态 |
| **3** | `_noteCache` 缓存语义与注释不符 | 低 | 澄清注释或优化为真"按分类缓存" |
| **4** | `api_timer_pause`/`resume` 忽略 body 中的 session_id | 低 | 考虑实际使用 session_id 而非 ORDER BY LIMIT 1（安全纵深） |
| **5** | `loadTimerPanel` paused 状态同步条件（C5） | 低 | 优化：无论 `timerDockSession` 是否存在，都应从 `/api/timer/active` 同步 paused 状态 |

---

## 六、证据索引

| 证据文件 | 内容 |
|----------|------|
| `tests/diff_backend.txt` | `server/backend_api.py` 全量 diff |
| `tests/diff_index.txt` | `src/index.html` 全量 diff |
| `tests/diff_appjs.txt` | `static/app.js` 全量 diff |
| `tests/diff_e2e.txt` | `tests/e2e-manual.js` 全量 diff |
| `tests/verify_run.log` | E2E 完整运行日志 |
| `tests/probe_3_1_run.log` | 3.1 失败根因诊断 |
| `tests/probe_3_3_run.log` | 3.3 修复验证 |
| `tests/probe_supplementary_run.log` | 补充探测（cache / sync）结果 |
| `tests/probe_xss_run.log` | XSS 多路径验证（确认 task list XSS） |
| `tests/probe_3_1.js` | 诊断探针（临时文件） |
| `tests/probe_3_3.js` | 诊断探针（临时文件） |
| `tests/probe_supplementary.js` | 补充探针（临时文件） |
| `tests/probe_xss_source.js` | XSS 探针（临时文件） |

> **注**：探针脚本（`tests/probe_*.js`）为验证过程临时产物，建议在报告确认后删除。

---

*验证完成。报告路径：`D:\Axelit\.工作\trae\超级自动化学习工具\docs\VERIFY_REPORT.md`*
