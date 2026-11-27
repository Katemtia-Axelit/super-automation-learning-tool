# 派发提示词 - P3 残留 XSS 修复（2026-08-09，prompt-template v2.1）

## 任务
修复 static/app.js 中两处残留的 XSS 注入点，并补回归测试。

## 背景（为什么做）
2026-08-06 已修复 5 处 XSS（FIX_REPORT_2026-08-06.md 可查），但独立复核发现仍有 2 处残留：
- 标签名/ID 未转义直接拼进 innerHTML，恶意任务/标签名可注入脚本
- 属于"全路径修复不完整"的遗留，必须补齐

## 先理解，后动手（v2 铁律）
1. **先不要修改代码**。先读 static/app.js 相关函数：`loadTags()`（约 L1210）、`openTaskEdit()`（约 L1408）、`escapeHtml()`（L2301 已有定义）
2. 复述两处问题 + 最小改动方案，确认后动手（本任务已确认，直接按下面方案执行）

## 修复范围（只做这些）
### 残留 1：static/app.js L1214 附近（loadTags 函数）
- 现状：`'onclick="filterByTag(' + t.id + ')">' + t.name + ...` 裸拼接
- 要求：`t.name` 用 `escapeHtml()` 转义；`t.id` 若是数字可保留、若是字符串需转义或改为 data 属性+事件委托
- 判定标准：标签名含 `<img src=x onerror=alert(1)>` 或 `"><script>` 时渲染为纯文本，不执行

### 残留 2：static/app.js L1415 附近（openTaskEdit 函数）
- 现状：`t.name.replace(/"/g, '&quot;')` 只转义引号，未转义尖括号
- 要求：改用 `escapeHtml(t.name)`（或完整转义 < > & " '）；若该处是展示用途优先考虑 textContent
- 判定标准：标签名含 `<img onerror=...>` 不触发

### 回归测试（必须）
- 在 tests/e2e-manual.js 增加或完善 XSS 回归用例：创建名称含 `<img src=x onerror=window.__xss=1>` 的任务/标签 → 加载 → 断言 `window.__xss` 未定义
- **先写测试并确认 RED（修复前测试失败）**，再修复到 GREEN

## 硬约束（违反即返工）
1. **禁止修改** src/notes/（知识库，红线）
2. 禁止修改除 static/app.js、tests/e2e-manual.js 以外的文件（若确实需要动其他文件，先说明理由）
3. 代码 UTF-8 编码
4. 修改前确认 git 基线（当前 HEAD=3e04447）；**不要 git commit**（调度员复核后决定）
5. **过程记录（强制）**：错误/异常/重试用中文记录到 docs/WORK_LOG.md
6. **三连败即停**：同一操作连续失败 3 次 → 停下分析根因并报告，禁止盲目重试
7. **TODO 清单**：本任务步骤多，维护执行清单（未完成/进行中/已完成）

## 执行步骤（Test-First）
### Step 1: 先写测试（RED）
- 在 tests/e2e-manual.js 增加 XSS 回归用例（创建恶意名 → 断言未执行）
- 跑一次确认测试失败（RED）——证明测试真实能抓住 bug
### Step 2: 修复（GREEN）
- 用 escapeHtml() 修复两处，直到测试通过（GREEN）

## 验证要求
1. 服务已启动（http://127.0.0.1:5000/，用 .venv 启动）
2. 跑针对性测试：`node tests/e2e-manual.js` 中 XSS 相关用例（RED→GREEN 全程记录）
3. **禁止**自己跑全量 E2E 并自报"全绿"（生成/验证分离铁律：全量回归由独立验证 Agent 执行）
4. 报告改动位置：文件+行号+改了什么

## 交付物
1. static/app.js 修复（两处）
2. tests/e2e-manual.js XSS 回归用例（RED→GREEN 证据）
3. docs/WORK_LOG.md 过程记录
4. 变更清单（改动点/行号/逻辑/针对性自测证据）

## 输出格式
```
【完成】P3 残留 XSS 修复
- 残留1: 改动+行号+验证结果
- 残留2: 改动+行号+验证结果
- 回归测试: RED(修复前) → GREEN(修复后) 证据
- WORK_LOG: 路径+踩坑摘要
- 变更清单
```
