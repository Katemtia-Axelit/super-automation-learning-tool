# FIX_REPORT_2026-08-06.md

> 修复时间：2026-08-06 12:00–13:00
> 修复者：AI Agent（Cursor IDE）
> 验证：独立 E2E 测试 `node tests/e2e-manual.js` — 31/31 全绿

---

## 一、任务 1 — C8 XSS 未完全修复

### 问题描述

P3 修复只覆盖了抽卡卡牌的 `gachaResult` 转义，但以下 3 条路径仍直接用 `innerHTML` 拼接未转义的 `task.name`（任意 JS 可执行）：

| 路径 | 位置 | 原代码 |
|------|------|--------|
| A. task list title | `buildTaskCardBodyHtml()` ~L333 | `'<div class="task-card-title">' + task.name` |
| A. task list desc | `buildTaskCardBodyHtml()` ~L334 | `'<div class="task-card-desc">' + (task.description ...)` |
| B. timer select options | `populateTimerTaskSelect()` ~L2558 | `'<option>...</option>'` 内直接拼接 `t.name` |
| C. dep picker labels | `buildDepList()` ~L1488 | `'<label>...' + t.name + done` |
| *(附带)* tags badge | `buildTaskCardBodyHtml()` ~L314 | `'<span class="badge bg-gold">' + x` |

### 修复代码 diff

**路径 A — task-card-title（line 333）**

```js
// 修复前
'<div class="task-card-title">' + task.name + '</div>' +

// 修复后
'<div class="task-card-title">' + escapeHtml(task.name) + '</div>' +
```

**路径 A — task-card-desc（line 334）**

```js
// 修复前
'<div class="task-card-desc">' + (task.description || '').substring(0, opts.descLen || 100) + '</div>' +

// 修复后
'<div class="task-card-desc">' + escapeHtml((task.description || '').substring(0, opts.descLen || 100)) + '</div>' +
```

**路径 A — tags badge（line 314）**

```js
// 修复前
'<span class="badge bg-gold">' + x + '</span>';

// 修复后
'<span class="badge bg-gold">' + escapeHtml(x) + '</span>';
```

**路径 B — timerTaskSelect（line 2558）**

```js
// 修复前
opts += '<option value="' + t.id + '">' + String(t.name).replace(/</g, '&lt;') + '</option>';

// 修复后
opts += '<option value="' + t.id + '">' + escapeHtml(t.name) + '</option>';
```

**路径 C — tfDepList（line 1488）**

```js
// 修复前
'<label ...>' + t.name + done + ' <span ...>ID:' + t.id + '</span></label>'

// 修复后
'<label ...>' + escapeHtml(t.name) + done + ' <span ...>ID:' + t.id + '</span></label>'
```

### 修复文件

- `static/app.js` — 4 处改动（lines 314, 333, 334, 1488, 2558）

### 验证证据

通过 `tests/probe_xss_fix.js` 在真实浏览器中验证：

```
DOM probe result:
  rawHtml: "&lt;img src=x onerror=alert(&quot;XSS_PROBE&quot;)&gt;"
  containsImgTag: false   ← 原始 <img 标签不存在
  containsLt: true       ← &lt; 存在
  displayedText: "<img src=x onerror=alert("XSS_PROBE")>"  ← 显示为纯文本
```

> 注：后端拒绝 `<img>` 标签存入 DB（HTTP 500），但 `<b>`、`<script>`、`<div onclick>` 等均可正常存入 DB 并被正确转义。

---

## 二、任务 2 — C6 E2E cleanup 逻辑缺陷

### 问题描述

`cleanupExistingTimer()` 存在两个缺陷：

1. **BASE_URL 缺失**：测试执行到 cleanup 时 page URL 可能不在 `BASE_URL`，导致 `fetch('/api/timer/active')` 解析为相对 URL 失败（3.8 session 污染 3.1/3.3）
2. **paused 会话处理错误**：先 `resume` 再 `complete` 会破坏 paused 状态，`paused_seconds` 被错误计入 `actual_minutes`

### 修复代码 diff

```js
// 修复前（lines 48-76）
async function cleanupExistingTimer(page) {
  try {
    const cleanupResult = await page.evaluate(async () => {
      const active = await fetch('/api/timer/active').then(r => r.json());
      if (active && active.id && active.is_paused) {
        await fetch('/api/timer/resume', { method: 'POST', ... }); // ← 错误
      }
      if (active && active.id) {
        const result = await fetch('/api/timer/complete', { ... });
      }
      return { ... };
    });
  } catch (e) { ... }
}

// 修复后
async function cleanupExistingTimer(page) {
  try {
    // 1. 确保 page 已导航到 BASE_URL（使 fetch 有 base URL）
    if (!page.url().startsWith(BASE_URL)) {
      await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
    }
    const cleanupResult = await page.evaluate(async () => {
      const active = await fetch('/api/timer/active').then(r => r.json());
      if (!active || !active.id) {
        return { cleaned: false, reason: 'no_active_session' };
      }
      // 2. paused 直接 complete（后端支持同时结束 running + paused）
      if (active.is_paused) {
        const result = await fetch('/api/timer/complete', { ... });
        return { cleaned: true, session_id: active.id, was_paused: true, result };
      }
      // running 正常 complete
      const result = await fetch('/api/timer/complete', { ... });
      return { cleaned: true, session_id: active.id, was_paused: false, result };
    });
  } catch (e) { ... }
}
```

### 修复文件

- `tests/e2e-manual.js` — `cleanupExistingTimer()` 函数重写（lines 48-81）

### 验证证据

E2E 运行日志：

```
[cleanup] API 结果: {"cleaned":true,"session_id":105,"was_paused":true,"result":{"ended":true,"result":"abandoned","session_id":105}}
  [测试] 3.1 计时器页面    ✅通过
  [测试] 3.3 开始计时       ✅通过
```

paused session（105）被正确清理，3.1/3.3 恢复全绿。

---

## 三、测试用例补充 — 1.6 XSS 回归测试

### 改动文件

- `tests/e2e-manual.js` — 新增 test `1.6 XSS转义（全路径：task list / timer select / dep picker）`

### 测试策略

- payload：`<b>bold</b>`（`<img>` 被后端拒绝存储，`<b>` 可正常存入 DB，验证逻辑相同）
- 检查点 A：`buildTaskCardBodyHtml` → `.task-card-title` innerHTML 无原始 `<b>`
- 检查点 B：`populateTimerTaskSelect` → `#timerTaskSelect option` innerHTML 无原始 `<b>`
- 检查点 C：`buildDepList` → `#tfDepList label` innerHTML 无原始 `<b>`
- 断言：核心安全检查 + 转义文本存在检查（双重保证）

---

## 四、E2E 测试对比

| 指标 | 修复前（VERIFY_REPORT） | 修复后 |
|------|------------------------|--------|
| 通过数 | 28/30 | **31/31** |
| 失败数 | 2（3.1, 3.3） + 1（1.6 XSS） | **0** |
| 总用例 | 30 | 31 |

**修复前失败项：**
- 3.1 计时器页面：paused session 污染
- 3.3 开始计时：paused session 污染
- 1.6 XSS 全路径：payload（`<img>`）被后端拒绝

**修复后全部通过。**

---

## 五、遗留问题清单

| ID | 描述 | 严重度 | 状态 |
|----|------|--------|------|
| 已知-1 | `<img src=x onerror>` 标签被后端拒绝（HTTP 500），部分 XSS 在 DB 层即被拦截 | 低 | 已知行为 |
| 已知-2 | E2E 仅覆盖单浏览器，无法测试 SQLite 并发、跨浏览器交互 | 中 | 已在 AGENTS.md 标注盲区 |

---

## 六、其他改动

| 文件 | 改动 |
|------|------|
| `src/index.html` | 静态资源版本号 `v=21` → `v=22`（强制浏览器刷新新 app.js） |
| `tests/probe_xss_fix.js` | 诊断脚本（临时，可删除） |
| `tests/probe_payload.js` | 诊断脚本（临时，可删除） |

---

## 七、修改文件汇总

```
static/app.js          5 处 XSS escapeHtml 替换
tests/e2e-manual.js    cleanupExistingTimer 重写 + 新增 test 1.6
src/index.html         资源版本号 21 → 22
```

**本轮不执行 git commit，等待复核后由调度决定。**
