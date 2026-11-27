# P4 → P5 交接文档

- **来源里程碑**：AR03-P4（CSS 模块化 + Theme / Dark Mode 收敛）
- **交接日期**：2026-11-22
- **交付文档**：`docs/P4_CSS_THEME_DELIVERY_20261122.md`
- **交接对象**：AR03-P5（Controller 定义的下一阶段）

---

## 1. 一句话状态

AR03-P4 **已完成并通过全部授权验收**：CSS 扁平分层 6 文件落地，Light Mode 语义化收敛完成，
Dark Mode **在已覆盖元素和属性范围内计算样式等价**，36/36 隔离 E2E + 1701 characterize + 4/4 视觉回归全绿。
**无阻塞 P5 的 P4 缺陷**（1 项后端遗留 500 + 1 项工作区临时文件清理，均不阻塞 P5 启动）。

> **表述纠错（2026-11-22，AR03-P4 独立审查增量审计）** —— 权威口径见
> `docs/P4_AUDIT_CORRECTIONS_20261122.md`：
> 1. 「Dark Mode 逐像素不变」→ **已覆盖元素和属性范围内的计算样式等价**
>    （A/B 计算样式对比，**非**截图像素差异测试；A/B 两阶段均关闭动画与过渡；**未执行 hover 交互验证**）；
> 2. 「无待修缺陷」→ **无阻塞 P5 的 P4 缺陷**；
> 3. `GET /api/tasks/21` → **`/api/tasks/21`，请求方法未确定**；
> 4. `prefers-contrast`：**媒体查询外壳** 在 `responsive.css`，**`:root` Token 重映射** 在 `theme.css`。
>
> P4 的 **Engineering Complete** 与 **Test Acceptance** 成果 **不受影响，继续成立**。

---

## 2. P5 接手时必须知道的三件事

### 2.1 CSS 架构已**冻结**（除非走门禁）

`static/css/` 的文件归属与加载顺序由机械门禁锁定：

```
theme → layout → components → features → cards → responsive
```

- `node scripts/check_css_architecture.js` —— 6 道门禁（token 所有权 / 内联收敛 /
  选择器唯一归属 / 加载顺序 / 语义变量双定义 / 源序等价性）。
- `node scripts/check_layout_utility_conflicts.js` —— 布局工具类与组件类的
  **胜者改变**级冲突扫描（当前 0 冲突）。

**这不是风格偏好，是可执行契约。** P5 若要改样式，必须同步通过这两道门禁。

### 2.2 改 CSS 必须跑视觉回归，且 **Dark 模式在已覆盖范围内计算样式零差异**

```powershell
npx playwright test --config tests/e2e/playwright.css-visual.config.js
```

- Dark 模式：**在已覆盖元素与属性范围内**，任何**非预期**差异 = 回归 = 必须修。
- Light 模式：差异必须**显式登记**在 `LIGHT_EXPECTED_DIFFS` 白名单里。
  白名单是契约 —— 写错选择器会被反向守卫（Light 必须观测到 ≥5 条预期差异）抓到。

> 口径：这是 **A/B 计算样式对比**（同一页面、同一批 DOM 节点、逐属性比对），
> **不是**截图像素差异测试；A/B 两阶段均关闭了动画与过渡；**未执行实际鼠标 hover 交互验证**。

### 2.3 P5 若触碰任务路由，请顺带定位遗留 500

隔离 E2E 36/36 通过的运行中仍会出现 **1 次 `/api/tasks/21` → HTTP 500**（**请求方法未确定**）。
P3 与 P4 两轮均如实记录、**未声称"未复现"**。CSS 迁移不触碰后端路由，故非本次引入。

> **注意**：该观察与 **P2 Stage 8** 的历史诊断（`scripts/_probe_task_get_500.py` 针对 **另一次事件**
> 得出的并发竞态结论）**不合并** —— 那次结论仅适用于它当时调查的事件。
> **根因未确认；不结案。**

---

## 3. P5 改样式时的落点对照

| 你要改的东西 | 落到哪个文件 | 注意 |
|---|---|---|
| 全局主题色 / 语义变量 | `static/css/theme.css` | 必须在 dark + light **两处**都定义（门禁 ⑤）。新增变量还要同步改门禁 ⑤ 的清单与 `tests/characterize/test_theme_contract.py` |
| reset / body / header / nav / main / 工具类 | `static/css/layout.css` | 工具类（`.mt*` / `.gap*` / `.flex` / `.hidden` …）都在这里，且**在 components 之前**加载 |
| 通用组件（button / input / card / modal / toast / badge） | `static/css/components.css` | `.modal` 是**唯一**允许跨文件定义的选择器（基础外观在 components，`::before` 装饰层在 cards） |
| 业务模块（gacha / tasks / schedule / knowledge / sleep / state / agent / prompts / free-task） | `static/css/features.css` | |
| 卡牌系统（`.task-card` / 主题变体 / 翻面 / 卡堆 / 弃牌堆 / 飞卡） | `static/css/cards.css` | **不要**把卡牌 Token（`--card-*`）搬出本文件 |
| 媒体查询 / `prefers-reduced-motion` / `prefers-contrast` | `static/css/responsive.css` | `prefers-contrast` 的 **媒体查询外壳** 在本文件；**`:root` 的 Token 重映射** 在 `theme.css`（保持 `:root` 定义处唯一） |

---

## 4. P5 容易踩的 5 个坑（都已在本里程碑实测踩过并修好）

### 坑 1：为了解决工具类冲突而收窄组件选择器 → 破坏非 modal 场景

**反面教材**（本里程碑真实发生过）：为让 `.modal-actions`（20px）胜过 `.mt16`（16px），
曾把选择器改成 `.modal .modal-actions`。但设置页的 `modal-actions mt16` **不在 `.modal` 内**
→ 该页按钮行丢掉 `display: flex` → 丢掉 `justify-content: flex-end` 右对齐。

**正确做法**（已在 `components.css` 落地）：

```css
:where(.modal-actions) { display: flex; justify-content: flex-end; gap: 8px; }
.modal-actions { margin-top: 20px; }
```

**规则**：**不要**用收窄作用域来提特异度；用 `:where()` 归零 + 同类覆盖规则。

### 坑 2：Chromium 对 flex 子项做 blockify

`.btn` 的 `display: inline-flex`，一旦父级变成 flex 容器，Chromium 会把它 blockify 成 `flex`。
所以"某个按钮的 `display` 从 `flex` 变成 `inline-flex`"通常意味着**父容器不再是 flex**，
而不是按钮自身规则变了。排查要从父级入手。

### 坑 3：`getComputedStyle` 返回的是**上次提交**的样式值

切换 `data-theme` 或替换样式表后，`:root` 上的自定义属性立刻变，但**继承**变量的元素
（`input` / `select` / `button`）要等**下一次渲染更新**才刷新。强制 layout
（读 `offsetHeight`）**无效**。正确做法是等 **double rAF**。

### 坑 4：过渡动画的中间帧被当成样式值

控件普遍 `transition: 0.2s`。切换主题 / 换样式表会触发过渡，`getComputedStyle` 读到的是
**插值中间值**（本里程碑实测读到 `rgba(237,190,63,0.106)` —— 0.1 与 0.18 之间）。
采样前必须 `transition: none !important; animation: none !important`，
且**两个采样阶段都要加**，否则引入偏差。

### 坑 5：bootstrap 遮蔽让页面处于隐藏态

`static/bootstrap-first-card.js` 在 Agent 策略未批准时给 `<html>` 加
`.sal-bootstrap-pending`，并用
`body > *:not(#salBootstrapOverlay){display:none !important}` 隐藏整个应用。
隔离沙箱里 `/api/agent-policy/status` 不会返回 `initialized=true` → 页面永远隐藏 →
所有元素 `display:none` → 采样全是噪声（连新建的 `div` 都算成 `none`）。

**任何**对隔离沙箱做样式采样的测试，都要先解除这个遮蔽，并加"页面可见性"断言。

---

## 5. P5 可直接复用的资产

| 资产 | 位置 | 用途 |
|---|---|---|
| 迁移前完整内联 CSS | `tests/fixtures/css_cascade_baseline.json` → `preMigrationCss` | A/B 视觉对比的"迁移前"一侧；任何新的样式对比测试都可用 |
| 迁移前覆盖对（含 `!important`） | 同文件 → `declarationPairs` | 判定"迁移前谁胜出"；写门禁时的基准 |
| 迁移前卡牌主题基线 | `tests/fixtures/card_theme_baseline.json` | 卡牌配色回归 |
| 迁移前视觉基线 | `tests/fixtures/css_visual_baseline.json` | 关键选择器 / 颜色字面量基线 |
| 基线采集工具 | `scripts/capture_css_baselines.js` | 加了新断言后可重跑刷新基线 |
| 视觉回归 spec | `tests/e2e/css-visual-regression.spec.js` | 扩选择器 / 扩属性 / 扩页面时**直接改这里** |
| 架构门禁 | `scripts/check_css_architecture.js` | 新增文件或新增 Token 时**同步改这里** |
| 合同测试 | `tests/characterize/test_css_architecture_contract.py`（18 条）、`test_theme_contract.py`（30 条） | 新增 Token / 新增文件时**同步改这里** |

---

## 6. P5 启动前建议的最小检查

```powershell
node scripts/check_css_architecture.js                  # 期望 PASS
node scripts/check_layout_utility_conflicts.js          # 期望 PASS（0 冲突）
node scripts/check_module_imports.js                    # 期望退出码 0
.\.venv\Scripts\python.exe -m pytest tests/characterize -q   # 期望 0 failed
npx playwright test --config tests/e2e/playwright.css-visual.config.js  # 期望 4/4
```

需要跑完整隔离 E2E 时：

```powershell
$env:PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
node scripts/run_e2e_isolated.js                        # 期望 36/36
```

> `run_e2e_isolated.js` 用 `process.env.PYTHON` 定位解释器。
> 若机器上只有 venv、`python` 不在 PATH，**必须**先设 `PYTHON`，
> 否则合成 Factory 以退出码 9009（command not found）提前退出。

---

## 7. 状态摘要（供 P5 决策）

| 维度 | 状态 |
|---|---|
| Engineering Complete | ✅ 全部完成 |
| Test Acceptance | ✅ 全部通过（6 门禁 + 1701 characterize + 100250 抽卡等价 + 36/36 E2E + 4/4 视觉回归） |
| Contract Compliance | ✅ 产品合同 / M1.5 美术接缝合同 / 数据红线 / 零构建 / OpenClaw 排除 —— 全部符合 |
| Known Issues | ① `/api/tasks/21` 出现 1 次 500（**请求方法未确定**，遗留，非本里程碑引入；**不结案**）；② 工作区迁移期临时文件待清理（运维动作，无功能影响） |
| 阻塞 P5 的问题 | **无** |
| 独立审查纠错 | 见 `docs/P4_AUDIT_CORRECTIONS_20261122.md`（4 项表述纠错 + 1 项证据缺口移交 P5） |

---

## 8. 相关文档

- `docs/P4_CSS_THEME_DELIVERY_20261122.md` —— 本里程碑完整交付文档
- `docs/P3_HANDOFF_TO_P4.md` —— 上一份交接（P3 → P4），可参考交接文档的结构
- `docs/CURRENT_PROJECT_STATE.md` —— 当前权威状态
- `docs/ARCHITECTURE.md` —— 实时架构与理由
