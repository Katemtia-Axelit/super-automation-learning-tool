# AR03-P4 交付文档 —— CSS 模块化 + Theme / Dark Mode 收敛

- **里程碑**：AR03-P4
- **交付日期**：2026-11-22
- **范围**：CSS 扁平分层模块化（6 文件）+ Theme / Light Mode 语义化收敛
- **前置**：P3 前端模块化交付（`docs/P3_FRONTEND_MODULARIZATION_DELIVERY_20261121.md`）
- **性质**：纯前端样式层重构。**零构建**（纯 ESM + `<link>`，无 Webpack / Vite / npm 构建步骤）。
- **OpenClaw 集成**：本里程碑**明确排除**，未触及。

---

## 0. 一句话结论

`src/index.html` 的 3 段内联 `<style>`（约 820 行）已迁移为 `static/css/` 下 6 个扁平分层文件，
全站主题 Token 收归单一权威，Light Mode 的 19 处硬编码低透明度/金色底色改为语义化变量，
**Dark Mode 在已覆盖元素和属性范围内计算样式等价**，Light Mode 的可读性缺陷被定向修复；
全部验收门禁通过（架构门禁 6/6、characterize 1701 passed、隔离 E2E 36/36、视觉回归 4/4）。

> **表述纠错（2026-11-22，AR03-P4 独立审查增量审计）**
> 权威口径见 `docs/P4_AUDIT_CORRECTIONS_20261122.md`。
> 1. 「逐像素不变」已更正为「**已覆盖元素和属性范围内的计算样式等价**」——
>    实际覆盖面为 6 页 × 2 主题 × 2 视口 × 同一批 DOM 节点 × 25 个计算样式属性；
>    **不是**截图像素差异测试；**A/B 两阶段均关闭了动画与过渡**；**未执行实际鼠标 hover 交互验证**。
> 2. `theme.css` 的 `@font-face` 数量已由「14 条」更正为 **11 条**（与迁移前 `preMigrationCss` 一致）。
> 3. Known Issues 中的 500 已改为 **不带请求方法** 的表述（方法未被现有证据确定）。
> 4. `prefers-contrast` 的 **媒体查询外壳** 在 `responsive.css`，**`:root` Token 重映射** 在 `theme.css`。
> 5. P4 的 Engineering Complete 与 Test Acceptance 成果 **不受本纠错影响**，继续成立。

---

## 1. 交付物清单

### 1.1 新增 CSS 文件（`static/css/`）

| 文件 | 字节 | 行 | 职责 |
|---|---:|---:|---|
| `theme.css` | 6 496 | 117 | **全局主题 Token 唯一权威**：`:root` / `:root[data-theme="light"]`、11 条 `@font-face`、9 个语义化交互变量、`@media (prefers-contrast: more)` |
| `layout.css` | 3 916 | 81 | reset、body、header/nav、main、page 显示/动画、网格与间距工具类、5 个通用 keyframes |
| `components.css` | 7 447 | 120 | button / input / select / textarea / badge / card / modal（基础外观）/ toast / empty state / diff / activity-row |
| `features.css` | 22 697 | 276 | gacha（含 timer-dock、多抽）、tasks、schedule、knowledge、sleep、state、agent、prompts、free-task |
| `cards.css` | 25 104 | 311 | `.task-card` + 8 个主题变体、翻面系统（独占 `.drawn-card-stage`）、卡堆、弃牌堆、飞卡、9 个卡牌 keyframes、M1.5 装饰 `--art-*` 消费钩子 |
| `responsive.css` | 4 489 | 91 | 媒体查询（900px / 600px / freeTask 600px）+ `prefers-reduced-motion` |
| **合计** | **70 149** | **996** | — |

### 1.2 新增机械门禁 / 工具

| 脚本 | 作用 |
|---|---|
| `scripts/check_css_architecture.js` | CSS 架构机械门禁（6 道，见 §3） |
| `scripts/check_layout_utility_conflicts.js` | 布局工具类 / 组件类的**胜者改变**级冲突扫描 |
| `scripts/capture_css_baselines.js` | 迁移前基线采集（3 份 JSON），含 `preMigrationCss` 与 `!important` 标记 |
| `scripts/rebuild_premigration_index.js` | 由迁移前 3 段 CSS 重建 `.tmp_premigration_index.html`（离线基线核对用） |
| `scripts/migrate_css_split.js` / `scripts/rewrite_index_head.js` | 一次性迁移工具（保留供追溯） |

### 1.3 新增测试

| 文件 | 内容 |
|---|---|
| `tests/characterize/test_css_architecture_contract.py` | 18 条断言，Python 侧复核 6 道门禁 |
| `tests/characterize/test_theme_contract.py` | 30 条断言，C/B/D 类收敛 + Light Mode 对比度 + 卡牌深色语言保护 + reduced-motion + 对比度媒体查询 |
| `tests/e2e/css-visual-regression.spec.js` | **A/B 计算样式对比**（见 §4） |
| `tests/e2e/playwright.css-visual.config.js` | Playwright 配置（合成 Factory，随机端口） |
| `tests/fixtures/css_cascade_baseline.json` | 迁移前基线（含 `preMigrationCss` 完整内联 CSS） |
| `tests/fixtures/css_visual_baseline.json` / `card_theme_baseline.json` | 迁移前视觉 / 卡牌主题基线 |

### 1.4 修改文件

| 文件 | 修改 |
|---|---|
| `src/index.html` | 删除 3 段内联 `<style>`，改为 6 个 `<link rel="stylesheet">`；**主题早期同步脚本保持在最前**（无 FOUC） |
| `static/css/components.css` | `.modal-actions` 拆为 `:where(.modal-actions)` + `.modal-actions`（见 §5.1） |
| `static/css/responsive.css` | `prefers-reduced-motion` 用 `animation-duration: 0.01ms` 而非 `animation: none`（保事件派发），并恢复动画态 `pointer-events: auto` |
| `tests/e2e/factory-sandbox-server.py` | `_STATIC_DIR_ALLOWLIST` 增加 `css`（**必须**）与 `assets`（保险） |

---

## 2. 架构不变量（Token 所有权分层）

```
static/assets/art-overrides.css   →  定义 --art-*        （美术接缝资产，唯一定义方）
static/css/theme.css              →  定义 全局主题 Token  （唯一权威）
static/css/cards.css              →  定义 --card-*        （卡牌 Token 唯一权威）
static/css/layout|components|features|responsive.css
                                  →  只消费，不定义全局 Token
JS / DOM                          →  定义运行时变量 --card-scale / --deck-i
```

- `:root` / `:root[data-theme="..."]` **只允许**出现在 `theme.css`。
- `--card-*` **只允许**定义在 `cards.css`。
- `--art-*` **只允许**定义在 `art-overrides.css`；消费方限定 `cards.css` / `features.css`
  （唯一豁免：`--art-card-front-layer` 在 `.task-card.theme-*` 内的逐主题再映射，已在门禁中显式登记）。
- `--card-scale` / `--deck-i` 在任何 CSS 文件中都**不得**出现定义形式
  （迁移前 `:root { --card-scale: 1 }` 的兜底已移除；所有消费点写作 `var(--card-scale, 1)` 自带 fallback，行为不变）。

---

## 3. 机械门禁（`node scripts/check_css_architecture.js`）

| 门禁 | 内容 | 结果 |
|---|---|---|
| ① | Token 所有权分层（①a 全局 token / ①b `--card-*` / ①c `--art-*` / ①d 运行时变量） | 0 违规 |
| ② | HTML 内联样式收敛：`src/index.html` 内 `<style>` 块数 = 0 | 0 违规 |
| ③ | 选择器唯一归属：同一选择器不得在 2 个 CSS 文件各定义一次（豁免名单：仅 `.modal`） | 0 违规 |
| ④ | 加载顺序 = theme→layout→components→features→cards→responsive，且主题同步脚本在 CSS 之前 | 0 违规 |
| ⑤ | 9 个语义化变量 dark + light 双定义，且 dark 值 = 迁移前原硬编码字面量 | 0 违规 |
| ⑥ | 源序等价性：迁移前覆盖对的胜者未改变 | 0 违规 |

辅助扫描 `node scripts/check_layout_utility_conflicts.js`：扫描 5 个文件 / 466 处 class 属性 /
143 个类名，**冲突数 0**。

> **门禁 ⑥ 的实现注意**：判定"迁移前谁胜出"时必须**同时**考虑
> ①`!important` ②特异度 ③源序。只看源序会误判
> （例：`.hidden { display: none !important }` 源序在前但恒定胜出
> `.modal-overlay { display: flex }`）。基线 `declarationPairs` 因此新增了
> `aImportant` / `bImportant` 字段。

---

## 4. 视觉回归：为什么是 A/B 计算样式对比

### 4.1 做法

不使用"静态基线声明字符串 vs 浏览器计算值"的比对 —— 那条路线需要手工解 `var()`、
归一化颜色、还会被浏览器 UA 归一化（`<button>` 的 `display`）和元素状态差异反复误报。

改为**同一页面、同一批 DOM 节点、同一次会话内**做 A/B：

1. 采样 A：页面加载 6 个 `<link>` 的迁移后 CSS，逐选择器读 `getComputedStyle`。
2. `link.disabled = true` 禁用迁移后的样式表 + 注入迁移前的内联 CSS（基线 `preMigrationCss`）。
3. 等一次渲染更新（double rAF）。
4. 采样 B：读**同一批元素引用**的计算样式。
5. 逐属性比对：Dark 模式要求**零差异**；Light 模式只允许白名单内的语义化收敛差异。

覆盖 6 页 × 2 主题 × 2 视口 = 4 个 Playwright 用例。

### 4.2 三个必须处理的技术陷阱（实测踩坑，代码中已注释固化）

| 陷阱 | 现象 | 处理 |
|---|---|---|
| **bootstrap 遮蔽** | `bootstrap-first-card.js` 在 Agent 策略未批准时给 `<html>` 加 `.sal-bootstrap-pending`，并用 `body > *:not(#salBootstrapOverlay){display:none !important}` 隐藏整个应用 → 隔离沙箱里页面永远隐藏，所有元素 `display:none`，采样全是噪声 | 采样前移除该类并删掉覆盖层；另加"页面可见性"断言 |
| **样式重算滞后** | Chromium 的 `getComputedStyle` 返回**上次提交**的样式值。切换 `data-theme` 后 `:root` 变量立刻变，但**继承**变量的元素（`input` / `select`）要等下一次渲染更新才刷新；强制 layout（`offsetHeight`）**无效** | 每段之间等 double rAF |
| **过渡动画插值** | 控件普遍带 `transition: 0.2s`，切换主题 / 换样式表会触发过渡，读到的是**中间帧**（实测 `.nav-btn.active` 背景被读成 `rgba(237,190,63,0.106)`） | A / B 两阶段**都**注入 `transition: none !important; animation: none !important`（对两阶段同等生效，不引入偏差） |

### 4.3 结果

| 视口 | 主题 | 结果 |
|---|---|---|
| desktop | dark | 通过（0 差异） |
| desktop | light | 通过（仅白名单内的语义化收敛差异） |
| mobile | dark | 通过（0 差异） |
| mobile | light | 通过（仅白名单内的语义化收敛差异） |

测试内置**双向守卫**：
- 正向：出现非预期差异 → 失败。
- 反向：Light 模式必须**真的观测到** ≥5 条预期差异，否则判为"退化为空跑" → 失败。

---

## 5. 迁移过程中发现并修复的真实缺陷

### 5.1 `.modal-actions` 在设置页丢失 `display: flex`（真实视觉回归）

**现象**：A/B 对比稳定报告 `.btn` / `.btn.pri` 的 `display` 由 `flex` 变为 `inline-flex`。

**根因**（两层）：

1. **Chromium 对 flex 子项做 blockify**：`.modal-actions` 是 `display: flex` 容器，其子 `.btn`
   的 `inline-flex` 会被 blockify 成 `flex`。一旦 `.modal-actions` 不再是 flex 容器，
   `.btn` 就回落成 `inline-flex` —— **同时丢掉 `justify-content: flex-end` 的右对齐**。
2. 迁移中为解决 `.mt16`（16px）与 `.modal-actions`（20px）的同特异度冲突，
   曾把选择器收窄成 `.modal .modal-actions`。但 `src/index.html` 的**设置页**
   `modal-actions mt16` **不在 `.modal` 内部** → 该页按钮行失去 flex 容器身份。

**修复**（`static/css/components.css`）：

```css
:where(.modal-actions) { display: flex; justify-content: flex-end; gap: 8px; }
.modal-actions { margin-top: 20px; }
```

- 基座用 `:where()` 把特异度压到 0 → 覆盖规则 `.modal-actions` 的有效特异度为 **0,1,0 + 自身**，
  恒定胜过单类工具类 `.mt16`（0,1,0），与文件加载顺序无关 → `margin-top` 恒为 20px。
- **保持全站匹配**（不收窄到 `.modal`）→ 设置页按钮行仍是 flex 容器。

**验证**：A/B 对比中该差异归零；`margin-top` 实测迁移前后均为 `20px`。

### 5.2 门禁 ⑥ 的基线查表 bug（假阳性）

`declarationPairs` 里 `a` / `b` 存的是**带前导点**的完整选择器（`".mt16"`），
而门禁查表用的是**裸类名**（`"mt16"`）→ 永远查不到 → `beforeComponentWins` 恒为 `false`
→ 任何"组件本来就该胜出"的组合都被误报成"胜者改变"。

修复：查表时补 `.` 前缀；同时把基线扩展为记录 `aImportant` / `bImportant`，
让"迁移前谁胜出"的判定与 CSS 层叠规范一致（见 §3 末）。

### 5.3 布局冲突扫描器的假阳性

原扫描器把"两个类声明了同一属性"直接判为冲突，未判断实际胜者，
对 `.modal-actions mt16` 报假阳性。

修复：改为比较**迁移前胜者 vs 迁移后胜者**，只有胜者**改变**才算冲突；
并支持 `:where()` 特异度归零。修复后冲突数从 1 → **0**。

---

## 6. Theme / Light Mode 收敛

### 6.1 新增 9 个语义化交互变量（`static/css/theme.css`）

| 变量 | Dark（原硬编码字面量） | Light（可读性修复值） |
|---|---|---|
| `--hover-veil` | `rgba(255,255,255,0.05)` | `rgba(0,0,0,0.05)` |
| `--hover-veil-subtle` | `rgba(255,255,255,0.03)` | `rgba(0,0,0,0.035)` |
| `--hover-veil-strong` | `rgba(255,255,255,0.1)` | `rgba(0,0,0,0.12)` |
| `--active-veil` | `rgba(255,255,255,0.05)` | `rgba(0,0,0,0.05)` |
| `--accent-veil` | `rgba(240,192,64,0.1)` | `rgba(201,159,46,0.18)` |
| `--accent-veil-soft` | `rgba(240,192,64,0.08)` | `rgba(201,159,46,0.14)` |
| `--accent-veil-strong` | `rgba(240,192,64,0.18)` | `rgba(201,159,46,0.26)` |
| `--accent-veil-chip` | `rgba(240,192,64,0.15)` | `rgba(201,159,46,0.16)` |
| `--danger-veil` | `rgba(231,76,60,0.1)` | `rgba(231,76,60,0.12)` |

**Dark 值 = 迁移前的原硬编码字面量** → Dark 模式在 **已覆盖元素和属性范围内计算样式等价**（门禁 ⑤ 锁定这一点）。

> 口径说明：视觉回归是 **A/B 计算样式对比**（同一页面、同一批 DOM 节点、逐属性比对），
> **不是**截图像素差异测试；A/B 两阶段均关闭了动画与过渡；**未执行实际鼠标 hover 交互验证**。
> 详见 `docs/P4_AUDIT_CORRECTIONS_20261122.md` §1.2。

### 6.2 收敛的 19 处

分类与落点：

- **C 类（hover 低透明度底）**：白底上 `rgba(255,255,255,α)` 不可见 → 改用黑色低透明度底。
  涉及 `.nav-btn:hover` / `.card:hover` / `.sched-slot:hover` / `.cat-item:hover` /
  `.note-item:hover` / `.prompt-file-item:hover` / `.agent-ro-item:hover` /
  `.feedback-emoji button:hover` / `.feedback-option:hover` /
  `button.gacha-multi-item:hover` 等。
- **B 类（金色 accent 底）**：`rgba(240,192,64,α)` 在浅底上对比不足 → 改用更饱和的深金。
  涉及 `.nav-btn.active` / `.cat-item.active` / `.agent-ro-tab.active` /
  `.replace-reason input:checked + label` / `button.gacha-multi-item[aria-pressed="true"]` /
  `.bg-gold` / `.tag-chip` / `.gacha-multi-item-tag`。
- **D 类（danger 按钮底）**：`.btn.danger` → `--danger-veil`。
- **Light Mode 对比度**：底色、边框、文字三件套按浅底重新映射（见 `theme.css` 的 light 块）。
- **卡牌深色设计语言保护**：`.task-card` / `.task-card-back` 的深色渐变与金色边框
  **不走**语义化变量，**保持深色不变**；M1.5 合同 §2.4「渐变卡背叠加 1px 边框」不受影响。

### 6.3 `prefers-contrast: more`

只提升 `--border` **一个**变量（dark `rgba(255,255,255,0.2)` / light `rgba(0,0,0,0.22)`），
不引入第二个边框变量（避免制造新的 Token 权威歧义）。
卡牌边框走独立的 `--card-border`，**不受影响**。

**归属**：`responsive.css` 提供 **媒体查询外壳**（条件容器），
`theme.css` 提供 **`:root` 的 Token 重映射**（具体变量值），
以保证 `:root` 定义处唯一（CSS 架构门禁 ①a）。

### 6.4 `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .task-card.is-evaporating,
  .task-card.is-fly-to-pile,
  .task-card.is-discarding,
  .task-card.is-skipping,
  .task-card.is-refusing,
  .task-card.is-burning { pointer-events: auto !important; }
}
```

- 用 `animation-duration: 0.01ms` 而非 `animation: none`：`animation: none` 会移除动画，
  **连带不再派发 `animationend` 事件**。当前 `static/**` 中 **零** `animationend` / `transitionend`
  监听器，卡牌状态推进由 **JS 定时器** 驱动（`static/app.js::playCardAnim` 的 `setTimeout(ms)`），
  与 CSS 动画时长 **解耦** —— 因此压缩动画时长 **不会** 打断抽卡 / 跳过 / 拒绝 / 弃牌的状态机。
  选 `0.01ms`（而非 `animation: none`）的目的是 **缩短视觉动效** 同时
  **保留 `animationend` 的派发能力**（万一将来新增监听器），**不是**因为当前状态机依赖它。
- 同时把动画态的 `pointer-events` 恢复为 `auto`，避免元素在动画期间不可点击。

> **口径纠错（2026-11-22）**：本节原文写作「导致依赖 `animationend` 事件的状态机……收不到事件 → 卡牌卡在中间态」，
> 该表述把 `animationend` 说成状态机的必要条件，**与「零监听器 + JS 定时器驱动」的实际实现不符**，已更正。
> 真实浏览器交互验证由 **P5** 补齐（见 `docs/P5_FINAL_DELIVERY_REPORT_20261122.md`）。
> 权威口径见 `docs/P4_AUDIT_CORRECTIONS_20261122.md`。

---

## 7. 验收结果

| 验收项 | 命令 | 要求 | 实际 | 结果 |
|---|---|---|---|---|
| CSS 架构门禁 | `node scripts/check_css_architecture.js` | 6/6 通过 | 6 门禁各 0 违规 | ✅ |
| 模块导入门禁 | `node scripts/check_module_imports.js` | 退出码 0 | 退出码 0 | ✅ |
| 布局冲突扫描 | `node scripts/check_layout_utility_conflicts.js` | 0 冲突 | 0 冲突 | ✅ |
| characterize 测试 | `.\.venv\Scripts\python.exe -m pytest tests/characterize -q` | 0 failed，passed ≥ 1653 | **1701 passed, 10 skipped, 442 subtests passed**（0 failed） | ✅ |
| P0 清理校验 | `.\.venv\Scripts\python.exe scripts/verify_p0_cleanup.py` | ALL ASSERTIONS PASSED | ALL ASSERTIONS PASSED | ✅ |
| 抽卡黄金等价 | `.\.venv\Scripts\python.exe scripts/phase2_gacha_golden.py` | 1:1 等价 | `pass=100250 fail=0 max_diff=0.000e+00`，`RESULT: OK` | ✅ |
| 隔离 E2E | `node scripts/run_e2e_isolated.js` | 36/36 | **36 通过, 0 失败**，退出码 0 | ✅ |
| CSS 视觉回归 | `npx playwright test --config tests/e2e/playwright.css-visual.config.js` | 4/4 | **4 passed** | ✅ |

> **运行提示**：`run_e2e_isolated.js` 通过 `process.env.PYTHON` 定位解释器。
> 在只装了 venv、`python` 不在 PATH 的机器上需先设置：
> ```powershell
> $env:PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
> ```

### 隔离 E2E 的 500 记录（如实）

本轮 36/36 通过的运行中，**再次出现 1 次 HTTP 500**：

```
500 http://127.0.0.1:<port>/api/tasks/21
```

与 P3 交付时记录一致（同一路径、同一发生频次），属**已知遗留问题**，非本次 CSS 迁移引入
（CSS 迁移不触碰任何后端路由）。**不声称"未复现"**。处理归属见 §9。

---

## 8. 状态区分

### 8.1 Engineering Complete（工程完成）

- [x] 3 段内联 `<style>` → 6 个 `static/css/` 扁平分层文件，`src/index.html` 内 `<style>` 块数 = 0
- [x] 全局主题 Token 收归 `theme.css` 单一权威（`--card-*` / `--art-*` / 运行时变量边界清晰）
- [x] 19 处 Light Mode 硬编码颜色改为 9 个语义化变量
- [x] Dark Mode 在已覆盖元素和属性范围内计算样式等价（dark 语义变量值 = 迁移前原字面量，门禁 ⑤ 锁定）
- [x] 任务卡深色设计语言 + M1.5 美术接缝合同不变
- [x] `prefers-reduced-motion` 修正（保事件派发 + 恢复 `pointer-events`）
- [x] 隔离 E2E 沙箱静态白名单补 `css` / `assets`
- [x] 零构建：纯 ESM + `<link>`，无 npm 构建步骤

### 8.2 Test Acceptance（测试验收）

- [x] CSS 架构机械门禁 6/6
- [x] 布局冲突扫描 0 冲突
- [x] characterize 1701 passed / 0 failed
- [x] `verify_p0_cleanup` ALL ASSERTIONS PASSED
- [x] `phase2_gacha_golden` 100250/100250 等价
- [x] 隔离 E2E 36/36
- [x] CSS 视觉回归 A/B 对比 4/4（含正反双向守卫）

### 8.3 Contract Compliance（合同符合性）

- [x] **产品意图合同**（`LEARNING_TOOL_RETENTION_PRODUCT_CONTRACT_20261021.md`）：
      本里程碑**未改动**任何任务 / 自由任务 / 抽卡 / 计时 / 策略 / 引导流程，
      仅样式层重构；自由任务仍是"同一 gacha/task 系统里的策略卡片类型"。
- [x] **M1.5 美术接缝合同**（`M1_5_ASSET_SEAM_CONTRACT_20261012.md`）：
      `--art-*` 定义方未变（`static/assets/art-overrides.css`）；
      消费方限定 `cards.css` / `features.css`；卡牌边框合同未变。
- [x] **数据红线**（`.cursor/rules/data-redlines.mdc`）：
      `src/notes/**`、`data/task_publisher.db`(+`-wal`/`-shm`)、`config/config.json`
      **本次未修改**（隔离 E2E 的 fs 守卫全程未触发，审计 3994 条记录零越界）。
- [x] **零构建约束**：无 Webpack / Vite / npm 构建步骤。
- [x] **OpenClaw 集成**：明确排除，未触及。
- [x] **运行时 CWD 不变量**：产品启动链未改动
      （`scripts/启动学习工具.bat` → `scripts/start_web_safe.bat` → `scripts/launch_server.py` → `run_app.py`）。
      > **勘误（2026-11-22）**：此处原文写作 `→ server/backend_api.py`。
      > 真实启动链的末端入口是 **`run_app.py`**（`launch_server.py::select_entrypoint` 默认 `factory`，
      > 且 `LEARNING_TOOL_BACKEND=legacy` 被 **fail closed 拒绝**）。
      > `server/backend_api.py` 已收口为 290 行薄别名，**不**在生产启动链上。
      > 详见 `docs/P5_FINAL_DELIVERY_REPORT_20261122.md` 与 `docs/ARCHITECTURE.md`。

### 8.4 Known Issues（已知问题）

| # | 问题 | 现状 | 归属 |
|---|---|---|---|
| 1 | `/api/tasks/21` 在隔离 E2E 中出现 **1 次 HTTP 500**（**请求方法未确定**） | 36/36 用例仍全部通过；**非本次迁移引入**（CSS 迁移不触碰后端路由）；**根因未确认** | 记录为 **已知限制 + 明确归属**（P5 交付报告已登记）；**不结案、不宣称未复现**。与 P2 Stage 8 的历史诊断 **不合并** —— 详见 `docs/P4_AUDIT_CORRECTIONS_20261122.md` §1.1 |
| 2 | 工作区残留迁移期临时文件（`.tmp_block_*.css`、`.tmp_vr*.log`、`.tmp_extract_diffs.js`、`tests/e2e/.tmp_debug_sampling.js`、`tests/e2e/.tmp_probe_button.js` 等） | Cursor 的 destructive-guard **禁止**在会话内删除工作区文件 → 需由 Controller / 用户在 Cursor 外清理 | 运维清理（无功能影响；均在 git 未跟踪区）。**P5 归档方案见 `docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md`** |
| 3 | `scripts/migrate_css_split.js` / `scripts/rewrite_index_head.js` 为一次性迁移工具 | 保留供追溯；**非**运行时依赖 | **P5 已明确**：归档到 `_archive/11_AR03_P5_一次性脚本/`，附来源/用途/替代工具说明 |

---

## 9. 给 P5 的交接要点

1. **不要再改 `static/css/` 的文件归属顺序**。门禁 ④ 锁定了
   `theme→layout→components→features→cards→responsive`，门禁 ⑥ 锁定了源序等价性。
   任何"把工具类挪到 components 之后"的想法都会撞门禁，且**没有必要**——
   `.modal-actions` 的 20px margin 已由 `:where()` + `.modal-actions` 双规则稳定解决。
2. **新增样式请落到正确的文件**：
   - 全局主题变量 → `theme.css`（并同步补 light 映射，门禁 ⑤ 会校验双定义）。
   - 通用组件外观 → `components.css`。
   - 业务模块 → `features.css`。
   - 卡牌系统 → `cards.css`。
   - 媒体查询 / 偏好覆盖 → `responsive.css`。
3. **新增选择器前先查重**：同一选择器不得在 2 个文件各定义一次（门禁 ③；唯一豁免 `.modal`）。
4. **新增颜色前先找语义变量**：不要新造硬编码白/金低透明度。
   现有 9 个语义变量不够时，**在 `theme.css` 里新增并同时给 dark + light 两套值**，
   然后更新门禁 ⑤ 的变量清单与 `test_theme_contract.py`。
5. **视觉改动的验收方式**：改完 CSS 后必须跑
   `npx playwright test --config tests/e2e/playwright.css-visual.config.js`。
   Dark 模式要求 **在已覆盖元素与属性范围内计算样式零差异** —— 若出现非预期差异，是回归，必须修；
   Light 模式的差异必须在 `LIGHT_EXPECTED_DIFFS` 白名单里显式登记
   （**登记即契约**：写错选择器会被反向守卫抓到）。
   口径说明：这是 **A/B 计算样式对比**（非截图像素差异测试），
   A/B 两阶段均关闭动画与过渡，且 **未执行实际鼠标 hover 交互验证**。
6. **浏览器采样陷阱**（已在 spec 中注释固化，改 spec 时勿丢）：
   bootstrap 遮蔽、`getComputedStyle` 样式重算滞后（需 double rAF）、
   过渡动画插值（需 `transition: none`）。
7. **`/api/tasks/21` 的 500** 未解决，属遗留（**请求方法未确定、根因未确认**）；
   P5 若触碰任务路由，请顺带定位。
   **注意**：与 P2 Stage 8 的历史诊断 **不合并** —— 那次结论只适用于它当时调查的那一次事件。

---

## 10. 表述纠错索引（2026-11-22）

| # | 纠错项 | 权威口径 |
|---|---|---|
| 1 | 「Dark Mode 逐像素不变」 | 已覆盖元素和属性范围内的 **计算样式等价** |
| 2 | `theme.css` 「14 条 `@font-face`」 | **11 条** |
| 3 | Known Issues #1 的 `GET /api/tasks/21` | **`/api/tasks/21`**，请求方法未确定 |
| 4 | `prefers-contrast` 归属 | 外壳在 `responsive.css`，`:root` 重映射在 `theme.css` |
| 5 | §6.4 把 `animationend` 说成状态机必要条件 | 零监听器 + JS 定时器驱动；`0.01ms` 是为了缩短动效并保留派发能力 |

完整对照表见 `docs/P4_AUDIT_CORRECTIONS_20261122.md`。

详见 `docs/P4_HANDOFF_TO_P5.md`。

---

## 10. 复现命令清单

```powershell
# 机械门禁
node scripts/check_css_architecture.js
node scripts/check_module_imports.js
node scripts/check_layout_utility_conflicts.js

# 测试
.\.venv\Scripts\python.exe -m pytest tests/characterize -q
.\.venv\Scripts\python.exe scripts/verify_p0_cleanup.py
.\.venv\Scripts\python.exe scripts/phase2_gacha_golden.py

$env:PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
node scripts/run_e2e_isolated.js

npx playwright test --config tests/e2e/playwright.css-visual.config.js

# 重建迁移前基线（仅在需要重新核对时）
node scripts/rebuild_premigration_index.js
node scripts/capture_css_baselines.js --source .tmp_premigration_index.html
```

---

## 11. 相关文档

- `docs/P3_HANDOFF_TO_P4.md` —— P3 → P4 的交接（本里程碑的输入）
- `docs/P3_FRONTEND_MODULARIZATION_DELIVERY_20261121.md` —— P3 交付
- `docs/P4_HANDOFF_TO_P5.md` —— P4 → P5 的交接
- `docs/CURRENT_PROJECT_STATE.md` —— 当前权威状态
- `docs/M1_5_ASSET_SEAM_CONTRACT_20261012.md` —— 美术接缝合同
- `docs/ARCHITECTURE.md` —— 实时架构与理由
