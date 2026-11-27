# AR03-P4 独立审查 —— 增量审计纠错记录

- **日期**：2026-11-22
- **来源**：AR03-P4 独立审查（外部审查意见）
- **执行方**：AR03-P5 Cursor Agent（单一会话，连续执行 P4 收尾 + P5 主体）
- **性质**：**增量纠错记录**。本文件 **不重写** P4 的原始 Cursor Trace、Handoff 与正式交付文档的历史正文；
  下游文档中与本文件冲突的表述，一律以本文件的 **统一口径** 为准。

---

## 0. 一句话结论

P4 的 **工程成果与测试成果全部成立**（CSS 六文件分层、Theme 收敛、6 道门禁、4/4 视觉回归、
36/36 隔离 E2E、1701 characterize）。本轮纠错的是 **4 项表述性错误** 与 **1 项证据缺口**：

1. HTTP 500 的 **请求方法** 被写成 `GET`（证据未确定方法）；
2. 视觉回归被表述为「**逐像素**不变」（实际是 **计算样式** A/B 对比）；
3. `@font-face` 数量被写成 14（实际 **11**）；
4. `prefers-contrast` 的 **媒体查询外壳** 与 **Token 重映射** 归属被写反；
5. `prefers-reduced-motion` 缺 **真实浏览器交互验证**（由 P5 补齐，见 §5）。

**历史最终响应中的错误表述不追溯篡改**；本文件即为那部分「以新增审计纠错记录说明」的载体。

---

## 1. 统一口径（下游一律照此书写）

### 1.1 HTTP 500

> **`/api/tasks/21` 出现一次 HTTP 500，请求方法未确定，根因未确认。**

**禁止**的写法：

- ❌ 写成 `GET /api/tasks/21` —— 现有证据**没有**确定请求方法；
- ❌ 声称该问题由 CSS 迁移引入 —— CSS 迁移不触碰任何后端路由；
- ❌ 擅自认定为「已经结案的并发竞态」。

**与 P2 历史诊断的区分（重要）**：

`scripts/_probe_task_get_500.py` 是 AR03-P2 / Stage 8 针对 **另一次事件** 所做的诊断，
其结论为「并发删除与读取竞态」。该结论 **仅适用于它当时调查的那一次事件**，
**未经证据** 不得与 P3 / P4 观察到的两次 500 合并为同一问题，也不得据此宣称 P3/P4 的观察已结案。

**状态**：**不结案、不宣称未复现**。P3 与 P4 两轮各观察到 **1 次**，发生频次一致。
归属：P5 记录为「已知限制 + 明确归属」，不阻塞 P5 交付。

### 1.2 视觉回归

> **已覆盖元素和属性范围内的计算样式等价。**

**准确的覆盖面**：

- 多个页面（6 页）；
- 两种主题（dark / light）；
- 桌面与移动视口（2 种）；
- **同一批 DOM 节点**；
- **25 个计算样式属性**。

**它不是**：截图像素差异测试（pixel-diff）。

**必须同时声明的三条限制**：

1. **A/B 两阶段均关闭了动画和过渡**（`transition: none !important; animation: none !important`）——
   否则读到的是插值中间帧；
2. **没有实际执行鼠标 hover 交互验证**；
3. 因此「Dark 零差异」的准确含义是：**在已覆盖的元素与属性范围内，计算样式等价**。

**保留**：原有 **4/4 测试通过**记录不因此推翻。

### 1.3 `@font-face` 数量

> **11 条。**

- 迁移前 `preMigrationCss`（`tests/fixtures/css_cascade_baseline.json`）实测 **11** 条；
- 当前 `static/css/theme.css` 实测 **11** 条（第 23–33 行）；
- 交付文档原写的「14 条」是 **计数错误**，与「9 个语义化交互变量」串行。

### 1.4 `prefers-contrast` 归属

> **媒体查询外壳位于 `static/css/responsive.css`；`:root` 的 Token 重映射位于 `static/css/theme.css`。**

- `responsive.css` 只提供 **条件外壳**（`@media (prefers-contrast: more) { … }` 的容器）；
- `theme.css` 提供 **具体变量值**（`:root` 的 `--border` 重映射）；
- 理由：全局主题 Token 的 **定义处唯一**（CSS 架构门禁 ①a）。
- `responsive.css` 内 **仅** 提升 `--border` **一个**变量（不引入 `--border-strong` 等第二个边框变量）；
  卡牌边框走独立的 `--card-border`，**不受影响**。

---

## 2. 逐条纠错对照表

| # | 文件 | 位置 | 错误表述 | 修正后表述 |
|---|---|---|---|---|
| 1 | `docs/P4_CSS_THEME_DELIVERY_20261122.md` | §0 一句话结论 | 「**Dark Mode 逐像素不变**」 | 「已覆盖元素和属性范围内的 **计算样式等价**」（附 §1.2 的三条限制） |
| 2 | 同上 | §1.1 `theme.css` 行 | 「**14 条** `@font-face`」 | 「**11 条** `@font-face`」 |
| 3 | 同上 | §6.1 结尾 | 「Dark 模式逐像素不变（门禁 ⑤ 锁定这一点）」 | 「Dark 模式在已覆盖元素/属性范围内计算样式等价（门禁 ⑤ 锁定）」 |
| 4 | 同上 | §8.1 清单 | 「Dark Mode 逐像素不变」 | 同 #1 |
| 5 | 同上 | §8.4 Known Issues #1 | 「`GET /api/tasks/21` 在隔离 E2E 中偶发 1 次 HTTP 500」 | 「`/api/tasks/21` 出现 1 次 HTTP 500（**请求方法未确定**）」 |
| 6 | `docs/P4_HANDOFF_TO_P5.md` | §1 一句话状态 | 「**Dark Mode 逐像素不变**」 | 同 #1 |
| 7 | 同上 | §1 一句话状态 | 「**无待修缺陷**」 | 「**无阻塞 P5 的 P4 缺陷**」 |
| 8 | 同上 | §2.2 标题与正文 | 「改 CSS 必须跑视觉回归，且 **Dark 模式零差异**」 | 「**Dark 模式零差异（计算样式等价口径）**」 |
| 9 | 同上 | §2.3 | 「1 次 `GET /api/tasks/21` → HTTP 500」 | 「1 次 `/api/tasks/21` → HTTP 500（**请求方法未确定**）」 |
| 10 | 同上 | §3 落点对照表 `responsive.css` 行 | 「`prefers-contrast` 的 `:root` 块 **在 theme.css**」 | 「`prefers-contrast` 的 **媒体查询外壳** 在 `responsive.css`；**`:root` Token 重映射** 在 `theme.css`」 |
| 11 | 同上 | §7 状态摘要 Known Issues | 「`GET /api/tasks/21` 偶发 1 次 500」 | 同 #5 |
| 12 | `docs/P2_FINAL_CLOSURE_20261121.md` | §6 未决项 #10 / #11 | Stage 8 诊断「**已结案（并发竞态）**」 | 加 **增量审计纠错**：该结论 **仅针对当时调查的那一次事件**；P3/P4 两次观察 **不结案**、不合并 |
| 13 | `docs/deliverables/P2_HANDOFF.md` | §6 未决项 #8 | 同 #12 | 同 #12 |
| 14 | `docs/CURRENT_PROJECT_STATE.md` | 顶部 P5 增量段 | — | **新增** 2026-11-22 增量段，记录本文件为口径权威 |

---

## 3. 未变更的部分（明确继承，不推翻）

以下 P4 成果 **保持原样**，本轮不重新验证、不重跑、不改写：

- CSS 六文件分层（`theme` → `layout` → `components` → `features` → `cards` → `responsive`）；
- Theme Token 收敛（19 处 Light Mode 硬编码 → 9 个语义化交互变量）；
- 卡牌深色设计语言 + M1.5 美术接缝合同；
- **CSS 架构门禁 6/6**、**布局冲突扫描 0 冲突**；
- **characterize 1701 passed / 0 failed**；
- **隔离 E2E 36/36 PASS**；
- **CSS 视觉回归 4/4 PASS**（A/B 计算样式对比，含正反双向守卫）；
- P0 契约 `ALL ASSERTIONS PASSED`；Gacha Golden 100250 等价。

> P4 的 **Engineering Complete** 与 **Test Acceptance** 两项结论 **继续成立**。

---

## 4. 本轮 **未** 追溯修改的内容（原则）

按「历史 Handoff / Trace / Collection / Review / 正式状态记录不允许被重写」的原则：

- **原始 Cursor Trace** —— 不动；
- **`docs/P4_HANDOFF_TO_P5.md` 的历史正文** —— 仅做 **事实性表述修正**（不删历史结论、不改结构、不改日期）；
- **`docs/P4_CSS_THEME_DELIVERY_20261122.md`** —— 同上；
- **P2 / P3 的历史交付文档** —— 仅追加 **增量审计纠错小节**。

---

## 5. 移交给 P5 的唯一实质缺口

| # | 缺口 | 处置 |
|---|---|---|
| 1 | `prefers-reduced-motion` 缺 **真实浏览器交互验证**（此前只有静态契约证据） | **P5 补齐**：新增隔离 Playwright 测试，真实启用 `prefers-reduced-motion: reduce`，覆盖抽卡/跳过/拒绝/弃牌四条关键流程 |

P5 的该项交付见 `docs/P5_FINAL_DELIVERY_REPORT_20261122.md`。

---

## 6. 相关文档

- `docs/P4_CSS_THEME_DELIVERY_20261122.md` —— P4 交付文档（本纠错已并入其事实性表述）
- `docs/P4_HANDOFF_TO_P5.md` —— P4 → P5 交接（本纠错已并入其事实性表述）
- `docs/P2_FINAL_CLOSURE_20261121.md` / `docs/deliverables/P2_HANDOFF.md` —— 已追加增量审计纠错
- `docs/CURRENT_PROJECT_STATE.md` —— 顶部 P5 增量段已记录本文件为口径权威
- `docs/P5_FINAL_DELIVERY_REPORT_20261122.md` —— P5 最终交付报告
