# M1.5A 美术资产接入合同（合同草案）

> 任务：`LT_M1_5A_ASSET_SEAM_CONTRACT_20261012_M`
> 批次：`OPEN Batch LEARNING_TOOL_M1_CORE_LOOP_20261011`
> 状态：**合同草案**。所有对位、命名、尺寸、回退与动效都是尚未落地的可执行约定，**不宣称**仓库里已有任何卡面 / 卡背 / 卡牌纹样 / 计时组件 / 进度条 / 装饰动效的图片资源；**只有真实 DOM/CSS 选择器被认定为已存在**。真实美术资源就绪后方可接入。

---

## 0. 阅读说明与红线

- 本文件**唯一可写入的文件**就是本 Markdown；未对项目源码 / 配置 / 数据库 / 笔记 / 钩子做任何写入。
- 当前已有：纯内联 CSS 渐变 + Unicode 字符（Σ / Aa / ⏳ / { } / ✎ / ⚛ / ↻ / ◆）+ 重复线性渐变纹理 + CSS Keyframes（已在 `src/index.html`、`static/app.js` 验证为真实存在）。
- 当前**未存在**（以下所有"建议 / 候选"在没有真实图片前不算实现）：`static/assets/cards/**`、`static/assets/icons/**`、`static/assets/dock/**`、`static/assets/spine/**` 路径下的任何文件、`<img>` `src`、CSS `background-image: url()` 引用、SVG `<image>`。
- 红线（来自 `.cursor/rules/data-redlines.mdc`、`runtime-cwd.mdc`、`AGENTS.md`）：不可读取/写入 `src/notes/**`、`data/task_publisher.db*`、`config/config.json`、`.cursor/hooks/**`。本文件**只引用它们的存在事实，不触碰**。
- 不改造：JS 选择器、HTML 结构、CSS 动画 keyframes、已有渐变卡背 / 复选框 / 滑块 / 计时器 DOM hook、现有 `/api/timer/*` 接口契约、任务状态机。

---

## 1. 只读现状映射（"已存在"才能写）

> 表 1 的所有"真实选择器 / 函数 / 状态"列均来自 `static/app.js`、`src/index.html`、`static/modules/*`、`static/core/*`、`static/shared/*`、`server/blueprints/timer_bp.py` 的精确读取；"建议视觉层"是合同草案入口，**不是承诺已存在**。

| # | 视觉类别 | 现有真实 DOM 钩子（已验证） | 现有真实 JS / CSS 入口 | 现有真实状态来源 | 建议插入的视觉层（草案） | **不允许影响的交互层** |
|---|----------|------------------------------|-------------------------|------------------|---------------------------|------------------------|
| 1 | 卡面（任务列表） | `static/app.js` L353-357 → `<div class="task-card card {theme} {status}" data-task-id="{id}">`；`buildTaskCardBodyHtml` L314-352 | CSS L374-433 `.task-card / .theme-* / .task-card-header / .task-card-body-zone / .task-card-footer / .task-card-ornament .tl/tr/bl/br`；结构：`task-card-header-main / task-card-corner / task-card-mark / task-card-title / task-card-desc / .task-card-meta / .task-card-stat / .task-card-tags / .task-card-actions` | `task` 对象：`{ id, name, description, category, priority, estimated_time, repeat_type, tags[], deadline, completed, in_discard_pile, is_unlocked }`；主题解析 `resolveTaskCardTheme()` L268-280 → `theme-math/lang/history/code/write/science/review/default`；`CARD_CORNER_LABELS` 类别中文 | 卡面背景层 `::before / ::after`（已有 insets）；可替换为内嵌 SVG / `<img>` 背景；角章 `.task-card-ornament` 可替换为 SVG 角饰 | 内部可点击节点、`.task-card-actions .btn`、状态 class (`status-completed / status-discarded / status-blocked`)、`data-task-id` 必须保留 |
| 2 | 卡背（弃牌堆） | `src/index.html` L629-636：`<div id="discardPile">` → `.discard-pile-label` + `<div id="discardPileStack">` → `#discardPileEmpty` 或 `.discard-pile-visual-card`（由 `updateDiscardPileVisual()` 动态追加 ≤5 张）；CSS L254-265 | `updateDiscardPileVisual()` 调用 `/api/discard-pile`；`flyCardToDiscard(cardEl)` L1480 飞行→移位 | 弃牌堆任务列表（items[]） | 卡背 SVG / 图片层插入 `.discard-pile-visual-card` 内部；建议 `::before` 占位 + 右上角戳记 | 元素点击 / hover 行为、可访问性 label（aria-hidden=true 已存在） |
| 3 | 牌堆（备用堆） | `src/index.html` L626-629：`<div id="gachaDeck">` → `.card-deck-card` ×5，自定义属性 `--deck-i: 0..4`；CSS L239-251 | CSS `.card-deck.is-drawing .card-deck-card:nth-child(5) { deckPop }`；由 `drawGacha()` 触发 | 当前抽卡请求与 `--deck-i` 索引 | 可在 `.card-deck-card` 上覆盖背景为美术纹样；保持现有 5 张堆叠参数 | 牌堆动画（`deckBreath`、`deckPop` 触发链） |
| 4 | 卡牌正面 / 背面翻转（已抽出卡） | `renderDrawnCard(task, idx)` L938-1014：构建 `<div class="drawn-card-stage"><div class="task-card card drawn-card {theme}{urgent}{isOneOff}" data-task-id="{id}">`；内部结构 `.task-card-inner > .task-card-face.task-card-back / .task-card-front`；CSS L448-471（含 horizontal landscape 版本） | 翻转类 `is-drawing / is-revealing / is-oneoff / urgent / status-…`；CSS Keyframes `cardIn / cardDrawOut / cardCompleteGlow / cardEvaporate / cardDiscardFly / cardSkipAway / cardRefuseAway / cardBurn`（L482-489） | 任务对象 + `urgent = deadline < 1 天`；外层 `--card-scale`（CSS 变量由 `cardSizeRange` L1601 控制） | 卡背 `.task-card-back` 当前是渐变 + emblem `✦` + linear pattern，可整体替换为美术 SVG；卡面 `.task-card-front` 已经按横向布局：左 1.5fr 信息 / 右 1fr 操作 | 双 rAF 翻牌时机、操作按钮（开始 / 跳过 / 拒绝 / 换一张） |
| 5 | 卡面"主题"变体 | CSS L435-440 七套 `theme-math / theme-lang / theme-history / theme-code / theme-write / theme-science / theme-review / theme-default`：各套 `--card-bg / --card-accent / --card-border / --card-glow` 变量；`task-card.theme-math::before` 已有 grid 数学纹理 | `resolveTaskCardTheme()` 用 `taskTextBlob()` 关键词正则匹配；`CARD_THEME_SYMBOLS` L257-260 Σ / Aa / ⏳ / { } / ✎ / ⚛ / ↻ / ◆；`buildLangPatternHtml()` 网格字 L309-311 | `task` 文本 + `tags[]` + `repeat_type` | 七套美术主题资产应**共用同一画板** + 不同色板 / 纹样（保留原渐变作为 fallback）；`theme-lang` 有特殊 `lang-pattern` 9 词 grid | 主题解析字符串；选择器 `.theme-*` 不可改 |
| 6 | 飞行卡牌 / 飞向弃牌堆 | `src/index.html` L1043：`<div class="card-fly-layer" id="cardFlyLayer">`；CSS L491-497 `.card-fly-layer` + `.flying-card` | `playCardFlyAnimation(task)` L901-931（抽卡→中央）；`flyCardToDiscard(cardEl)` L1480-1513（飞向弃牌堆） | `getBoundingClientRect()` of `#gachaDeck / .drawn-card-stage / #discardPile` | 飞行卡牌本身渲染的是临时克隆（无 data-*）；可由美术提供"飞行中"版本的卡面，临时覆盖内层内容 | 飞行层 z-index 500、700ms 时长、cubic-bezier 曲线 |
| 7 | 计时器主页面控制台（任务页） | `src/index.html` L707-722：`#timerPanel > #timerStatusText / #timerElapsedDisplay / #timerControls`；控件：`#timerTaskSelect / #timerPlannedMin / #timerStartBtn / #timerPauseBtn / #timerStopBtn` | 见 §4；连接 `/api/timer/active`、`/api/timer/start`、`/api/timer/pause`、`/api/timer/resume`、`/api/timer/complete` | 见 §4 | 计时器外框 / 数字字体可装饰；**数字读出仍走 `00:00` 文本** | 控件 `id`、`disabled / hidden`、计时器状态机；回调 `_pendingStartTaskId` 重入守卫（M1.3A） |
| 8 | 计时器 Dock（抽卡页常驻） | `src/index.html` L638-651：`<div id="timerDock">` → `#timerDockIdle` / `#timerDockActive > #timerDockTaskName / #timerDockTime / #timerDockBar / .timer-dock-btns`（含 `#timerDockPauseBtn / #timerDockStopBtn`） | `initTimerDock()`、`loadTimerDockActive()`、`updateTimerDockDisplay()`、`toggleTimerDockPause()`、`stopTimerFromDock()` L408-605；1 秒 `setInterval` | `/api/timer/active` → `{ id, session_id, task_id, task_name, started_at, planned_minutes, paused_seconds, is_paused }` | 怀表 / 齿轮 / 刻度盘可整体装饰 `<div id="timerDockActive">` 背景；**数字位置、宽度、`#timerDockTime` `textContent` 与进度条 `#timerDockBar` `style.width` 是契约** | 任何导致 dock 文本 / 进度条 `style.width` 失真的覆盖；按钮触发的后端调用链；与后端 `/api/timer/*` 的字段映射 |
| 9 | 进度条（dock + in-card 计时） | dock：`#timerDockBar`（`.timer-progress > .timer-progress-bar`，线性渐变 `gold-dark → gold`，CSS L275）；卡片内嵌 `.card-timer-display` 文字 + `startInlineTimer()` L1118-1133（每秒仅更新文本） | CSS `transition: width 1s linear`（已存在） | dock：`(elapsed / 1000 / 60 / planned) * 100` clamp 0-100；卡片：仅文字 | 美术可将 `linear-gradient` 替换为 SVG 渐变 / 重复斜纹；可加虚线 tick | 进度条宽度递增方向（0% → 100%）、与倒计时 `planned_minutes` 的数学关系 |
| 10 | 任务完成关怀（care modal） | `src/index.html` L1025-1041：`<div id="careModal">` → `#careEncourage`（金黄色祝福语）/ `#careTaskInfo`（当前科目灰字） / `#careSameBtn / #careSwitchBtn / 第三个休息按钮`（裸按钮） | `showCompleteCare(task)` L1389 之后，`careSameCategory() / careSwitchCategory() / careRest()` L1408-1428 | `_careContext = { task, category }`；`CARE_ENCOURAGES[]` 随机一句；`CARE_CATEGORY_LABELS` 中文 | 可作为正文插画（手绘奖杯 / 茶壶 / 书本），但只作为独立子元素，**不可遮挡按钮**；建议留出 ≥3 个按钮高度的下方空白 | `#careEncourage / #careTaskInfo` 文本节点；按钮文字 |
| 11 | 反馈 modal（旧能量 / 心情 / 任务反馈） | `src/index.html` L1003-1021：`#feedbackModal` → `#fbEnergy` range / `#fbEnergyVal` 数字 / `#feedbackModal .feedback-emoji` 三个按钮；L946-956 `#taskFeedbackModal` 含 `#taskFeedbackQuestion / #taskFeedbackOptions / #taskFeedbackNote`；`#taskFeedbackConfirmBtn / #taskFeedbackCancelBtn` | `openFeedbackModalForTask(taskId, category, finishEarly)` L1309；`setMood(v, el)` / `submitFeedback / cancelFeedback` L1518-1522；`promptTaskFeedback('skip', ctx)` 反馈收集 | `gachaState.feedbackMood = 3`；`task.category` | 模态框背景可以换成"羊皮纸"风格材质；emoji / 表情按钮标签**保持文字** | 模态 `id`、输入控件 `name / data-mood` / XSS 包裹（`escapeHtml`） |
| 12 | 状态评估 modal | `src/index.html` L960-967：`#stateAssessmentModal` → `#stateAssessmentForm`（动态生成 `assess-q`，每个含 `input[type=range]` + `.assess-q-val`） | 评估题动态注入；提交按钮 `#stateAssessmentSaveBtn` | 后端提交评估题分数 | 可将背景设成复古纸张；**range 控件必须保持原生 type=range** | `id`、表单字段 `name/required`、题面文字 |
| 13 | 弃牌堆 modal（恢复） | `src/index.html` L972-983：`#discardPileModal` → `#discardPileList` → `.activity-row.discard-row[data-id]` | `openDiscardPileModal() / loadDiscardPileList()` L1762-1780；状态徽章 `discardTaskStatus(t)` | `/api/discard-pile` | 列表项图标可美术化；保留 `#discardPileList data-id` | data-id 属性 |
| 14 | 连抽结果列表 | `src/index.html` L669-687：`#gachaMultiRow` → `#gachaMultiCount` / `#gachaMultiBtn`；`#gachaMultiResult > #gachaMultiSummary / #gachaMultiList` → `.gacha-multi-item`（原生 `<button>`，含 `data-task-id / data-idx / aria-pressed / title`） | `renderMultiResults(response)` L764+；按钮 `class="gacha-multi-item"`，节标题 `.gacha-multi-item-title`，元信息 `.gacha-multi-item-meta` 含 `.gacha-multi-item-tag` | `response.tasks[]`、`total_minutes / remaining_minutes` | 小缩略图可放进 `.gacha-multi-item`；**保持原生 `<button>` + `aria-pressed`** | data-task-id、data-idx、aria-pressed 三元组；键盘 Enter/Space 激活 |

### 1.1 真实存在的 CSS Keyframes（已全部在 `src/index.html` 内联）

- 卡面入场：`cardIn / fadeIn / slideUp`
- 抽卡 / 弃牌 / 跳过 / 拒绝 / 完成 / 燃烧：`cardDrawOut / cardCompleteGlow / cardEvaporate / cardDiscardFly / cardSkipAway / cardRefuseAway / cardBurn / deckBreath / deckPop / pulse / float`
- **合同要点**：美术动效应基于这一组 keyframes 收敛，**不要新增** keyframe 名（避免与现有动画管线冲突）；新增动画只能通过改 CSS 变量 `--card-scale / --card-accent / --card-glow` 或 transform 增量。

### 1.2 主题 / 资产接入位置候选（草案；未落地）

| 注入位 | 在 DOM 中的位置 | 已存在的同级节点 | 行为约束 |
|--------|----------------|------------------|----------|
| 卡面底图 | `.task-card` 内 `::before`（已有内嵌 11×12 grid）或新增 `<span class="task-card-bg" aria-hidden="true">` | `.task-card-inner / .task-card-pattern / .task-card-back-pattern` | `pointer-events: none / z-index: 0` |
| 卡角装饰 | `.task-card-ornament` （4 个角） | `.task-card-ornament.tl/tr/bl/br` | 不能覆盖点击/键盘焦点 |
| 卡背纹样 | `.task-card-back` 全屏；现有 `.card-back-pattern`（inset 12px）+ `.card-back-emblem` | 翻牌背面在 `.task-card-face` 内 | 翻面后仍可见 180° 翻转 |
| 弃牌卡背 | `.discard-pile-visual-card`（绝对定位偏移） | 同级最多 5 张 | 灰阶 `.filter: grayscale(0.6) brightness(0.8)`（已有） |
| 计时器 Dock 装饰 | `#timerDockActive` 背景层；新增 `<div class="dock-bg" aria-hidden="true">` | `#timerDockTaskName / #timerDockTime / #timerDockBar` | 不遮挡数字 / 进度条 / 按钮 |
| 怀表刻度盘 | `#timerDockTime` 外包络 `<div class="pocket-watch">` | 怀表可选；数字仍 `#timerDockTime` | 数字字号 / 位置不可改 |
| 进度条纹理 | `.timer-progress-bar` 已有 `linear-gradient(90deg, var(--gold-dark), var(--gold))` | 由 dock `#timerDockBar` 控制 `style.width` | 渐变方向 0%→100% 不变 |
| 飞行卡 / 燃烧卡 | `.flying-card`（独立 div，无 data-*） | z-index 500 | 飞行 / 燃烧不影响 DOM 状态机 |

---

## 2. 资产清单与命名约定（合同草案）

### 2.1 资产根目录（建议新建，未落地）

```
static/assets/
  cards/
    faces/
      theme-math/
        front-bg.svg
        corner-tl.svg
        corner-tr.svg
        corner-bl.svg
        corner-br.svg
        header-band.svg        # 上方装饰带
        body-pattern.svg       # 中部纹样 (对应 .task-card-pattern)
      theme-lang/
        ...
      theme-history/ theme-code/ theme-write/ theme-science/ theme-review/ theme-default/
    backs/
      common/
        back-pattern.svg       # 卡背斜纹
        emblem.svg             # 中央徽记
      per-theme/                # 类别专属卡背（可复用 common）
    deck/                       # 牌堆
      deck-base.svg
      deck-edge.svg
    discard/                    # 弃牌堆
      discard-back.svg
  dock/
    pocket-watch.svg            # 怀表底盘
    watch-ticks.svg             # 刻度
    watch-hands.svg             # 指针（不强制动效）
    frame.svg
  progress/
    progress-ticks.svg
    progress-fill.svg
  feedback/
    feedback-paper.svg          # 复古纸 / 羊皮纸背景
  care/
    care-illust-success.svg     # 完成关怀插画
  ui/
    modal-frame.svg             # 模态外框
```

> 本合同**不要求立刻到位**；上表供独立美术对话产出文件时参照。文件未到位期间，所有插入位继续用现有 CSS 渐变 / Unicode 字符作为 fallback。

### 2.2 命名约定（稳定，不允许美术对话重命名）

- 主题 token 与现有 CSS 选择器一一对应：`theme-math / theme-lang / theme-history / theme-code / theme-write / theme-science / theme-review / theme-default`。
- 类别中文映射沿用 `CARD_CORNER_LABELS`（`study / exercise / work / life / other`），不引入新类别键。
- 文件名：`<role>-<variant>.svg` 或 `<role>-<theme>.svg`，全部小写、连字符分隔；`<role>` 必须是 §2.1 表里的小写英文名。
- 文件落盘路径必须固定为 `static/assets/...`，**不写** `src/`、`static/vendor/`、`/data/`、仓库根目录。
- 透明：所有 SVG 资源要求 `viewBox` + 透明背景（无底色矩形），便于浅深主题叠加。
- 文件引用：CSS 只能引用相对 `static/assets/` 的 SVG；不引入外链；不引入二进制 PNG（避免透明 + 多分辨率管理难题）。
- `prefers-reduced-motion` 必须被尊重（见 §5.3）。

### 2.3 建议格式 / 分辨率 / 性能预算

| 资产类型 | 格式 | 尺寸（CSS 像素） | 实际 viewBox | 文件大小上限 | 备注 |
|----------|------|-------------------|---------------|-------------|------|
| 卡面底图 / 卡背 | SVG | 350×220 (logic, scale-safe) | 700×440 (2×) | ≤ 24 KB / 张 | 同 viewBox 可在 `.task-card.drawn-card` (5:3 landscape) 中拉伸 |
| 卡角装饰 | SVG | 14×14 | 28×28 | ≤ 2 KB | 4 个角分别独立文件 |
| 卡背 emblem | SVG | 72×72 | 144×144 | ≤ 6 KB | 与现有 `.card-back-emblem` 同占位 |
| 牌堆 / 弃牌 | SVG | 140×98 | 280×196 | ≤ 16 KB | 与现有 `.card-deck-card` / `.discard-pile-visual-card` 一致 |
| 怀表 / Dock 装饰 | SVG | 240×80（横向 dock） | 480×160 | ≤ 18 KB | 横向长条 |
| 进度条纹理 | SVG 平铺或 inline gradient | 4 px 高 × N 平铺 | n/a | ≤ 4 KB | 不阻塞 `style.width` |
| 反馈羊皮纸 | SVG | 520×360 (modal 内部) | 1040×720 | ≤ 32 KB | 透明中心 + 边角，仅作背景 |
| 完成关怀插画 | SVG | 320×200 | 640×400 | ≤ 28 KB | 居中，不遮挡 3 个按钮 |

总预算：首版全套合计 ≤ 500 KB；首屏（gacha 页）首字渲染 ≤ 250 KB。`prefers-reduced-data: reduce` 时，资源应可被浏览器 / 项目级策略跳过。

### 2.4 主题兼容性

- 浅色 / 深色模式：当前 `data-theme` 切换由 `static/core/theme.js` 触发；CSS 变量 `--card-bg / --card-accent / --card-border / --card-glow` 重映射。
- 美术资源**只提供亮纹样**（色相固定为 `--card-accent` 系列金/蓝/绿/紫/橙，不嵌入硬编码颜色值）；通过 `currentColor` 或 CSS 变量传递主题色（在 SVG `style` 内联 `fill: currentColor` 或 `currentColor` 引用）。
- 高对比度模式：检测 `@media (prefers-contrast: more)` 时，渐变卡背应叠加 1px 边框（已有 `--card-border`），资源可叠加更高对比度替身。

---

## 3. 卡面 / 卡背及任务类型视觉变体与回退规则

### 3.1 卡面变体映射（草案）

| 当前 CSS 主题 | 视觉风格倾向（用户意图） | 美术可注入资产 | 现有 fallback（资源未到位） |
|----------------|---------------------------|----------------|------------------------------|
| `theme-math` | 数学 / 蓝青 / 米字格 / 表格 | `cards/faces/theme-math/*` | 当前 `linear-gradient(145deg,#121a32,#1a2848)` + 11×12 grid `::before` + Σ unicode |
| `theme-lang` | 自然 / 绿色 / 词汇 | `cards/faces/theme-lang/*`（含 `lang-pattern.svg` 9 词 grid 可换） | 当前渐变 + `.lang-pattern` 网格英文词 |
| `theme-history` | 琥珀 / 羊皮纸 / 怀旧 | `cards/faces/theme-history/*` | 当前 `#241a12 / #322418` 渐变 + ⏳ |
| `theme-code` | 青绿 / 终端 / { } | `cards/faces/theme-code/*` | 当前 `#0e1418 / #152028` 渐变 + `{ }` |
| `theme-write` | 紫 / 羽毛笔 / 创作 | `cards/faces/theme-write/*` | 当前 `#1e1828 / #2a2238` 渐变 + ✎ |
| `theme-science` | 蓝紫 / 化学符号 | `cards/faces/theme-science/*` | 当前 `#121828 / #1a2240` 渐变 + ⚛ |
| `theme-review` | 金 / 复古封面 / ↻ | `cards/faces/theme-review/*` | 当前 `#221c14 / #2e2618` 渐变 + ↻ |
| `theme-default` | 中性 / 金色装饰 | `cards/faces/theme-default/*` | 当前 `#181c28 / #222838` 渐变 + ◆ |

### 3.2 卡背变体

| 用途 | 美术可注入资产 | fallback |
|------|----------------|----------|
| 抽中牌背面（统一） | `cards/backs/common/back-pattern.svg` + `emblem.svg` | 当前 `linear-gradient(135deg,#1a2240,#0f1422)` + 斜纹 + ✦ 圆徽 |
| 弃牌堆（去饱和） | `cards/discard/discard-back.svg` | 当前 `linear-gradient(145deg,#3a3a3a,#252525)` + `grayscale(0.6) brightness(0.8)`（CSS 已带） |
| 任务列表卡 | 共享抽中背面 | 直接渲染卡面（不需要背面） |

### 3.3 默认回退规则（保证任何资源缺失都不会空白）

1. **渐进加载**：`<img>` / `background-image: url()` 命中 `404` 时，浏览器自然不显示，回退到现有 CSS 渐变 / 字符。
2. **CSS 内嵌回退**：在 `static/app.js` 中**不修改**任何已有 className / 选择器；美术资源通过新增 `<span class="task-card-bg" aria-hidden="true">` 子节点插入，CSS 用 `background-image: var(--asset-url, none);` 提供显式 fallback 链：
   ```
   background-image: url(/static/assets/cards/faces/theme-math/front-bg.svg),
                     linear-gradient(145deg, #121a32, #1a2848);
   ```
   资源 404 时浏览器仅跳过第一层，第二层（CSS 渐变）仍然显示。
3. **优先级**：所有美术资产均为 `aria-hidden="true"`，仅做视觉装饰，不参与语义；可访问性数据来自已有 `<span class="task-card-title">` / `<span class="task-card-mark">` 等真实节点。
4. **不可逆变换**：现有 `--card-scale / --card-bg / --card-accent / --card-border / --card-glow` CSS 变量保持兼容；美术资产通过 `currentColor` / 透明度叠加，绝不修改这些变量的默认值。

### 3.4 任务类别（corner label）对应表（沿用现有）

```
study: 学习   exercise: 运动   work: 工作   life: 生活   other: 其他
repeat: 单次 / 每日 / 每周（仅显示，不参与美术）
priority: 1..10（显示为 P{priority}，美术仅装饰，不参与判定）
```

---

## 4. 计时器权威边界（**关键**）

> 美术可以装饰外框和刻度，但**下列字段是契约**。任何美术实现不得破坏它们。

### 4.1 计时器权威会话（`timer_sessions`）接口契约

| 字段 | 来源 | 写入点 | 读出点（前端需要） |
|------|------|--------|---------------------|
| `id` (`session_id`) | `POST /api/timer/start` 后端生成 | `timer_service.start()` (`server/services/timer.py`) | `timerDockSession.id` |
| `task_id` | 客户端提供（`parseInt` 强校验） | `startTimer()` | `#timerDockTaskName` 渲染 |
| `started_at` (ISO 字符串) | 后端 `start / resume` 生成 | `timer_service.start / resume` | `timerDockSession.started_at`（`Date.parse` 后 `Date.now() - started` 算 elapsed） |
| `planned_minutes` | 客户端 `integer 1..480`；服务端 fallback 30 | `startTimer()` | `progress = min(100, elapsed / 60000 / planned * 100)` |
| `paused_seconds` (int) | `pause` 累加 / `complete` 累加 | `pause / complete` | 客户端 `Date.now()-started + paused_seconds*1000` 还原"真实秒数" |
| `is_paused` | 后端布尔 | `pause / resume` | `timerDockPaused` |
| `result` | `complete` 调用时设置：`completed / abandoned`（含 `early_finish / timeout` reason） | `timer_service.complete` | 后端日志 |
| `actual_minutes` | 客户端 `max(1, round(elapsed/60000))` | `complete` | 日志 |

### 4.2 状态机与按钮边界

| 前端动作 | 后端接口 | 客户端重入守卫 | 美术相关 |
|----------|----------|----------------|----------|
| `#timerStartBtn` (开始) | `POST /api/timer/start {task_id:int, planned_minutes:int}` | `_pendingStartTaskId` (M1.3A) | 按钮**任何视觉变化不得破坏 `id` 与事件 `click`**；可加图标 |
| `#timerPauseBtn` | `POST /api/timer/pause {session_id}` | `toggleTimerDockPause` 内部守卫 | 按钮图标切换 ⏸↔▶ 已有，可加金色边框装饰 |
| `#timerStartBtn` (Dock 内的) | `POST /api/timer/resume {session_id}` | 同上 | 同上 |
| `#timerStopBtn` (Dock 提前结束) | `POST /api/timer/complete {session_id, actual_minutes, result:'abandoned', reason:'early_finish'}` | `stopTimerFromDock()` L557-605 | 按钮**必须保持 `danger` red**，可加图标 |
| 任务页"停止"按钮 | `POST /api/timer/complete {session_id, actual_minutes:int, result:'completed'/'unfinished'/'abandoned', reason}` | `confirmComplete()` 调用前需 stop 计时器 | 同上 |
| 计时自然结束（前端不知道） | 后端依赖客户端轮询 `/api/timer/active`；出现 `result` | n/a | 客户端基于 `/api/timer/active` 响应文本判断 → 弹出 `#timerOutcomeModal` |
| 任务页"完成"按钮 | `completeWithFeedback(id)` → 先 `confirmComplete` → `openFeedbackModalForTask` | 同上 | 图标 ✅ 已存在 |

### 4.3 契约红线

1. **秒数显示必须来自后端权威**。前端显示 `Math.floor(elapsed/1000)`，其中 `elapsed = (timerDockPaused ? pausedElapsed : Date.now()-started) + paused_seconds*1000`（已实现于 `updateTimerDockDisplay()` L470-475 / `startInlineTimer()` L1118-1133 / `confirmComplete()` L1167-1175 三处）。
2. **进度条方向单调递增**：`progress = min(100, elapsed_seconds / 60 / planned * 100)`；美术资产必须假设宽度从 0 → 100%。
3. **`#timerDockTime` 文本格式**：`mm:ss`，左零补齐（`0${m}` 与 `0${s}`）。任何美术外框不得遮挡。
4. **`#timerDockBar` 单点写入**：`barEl.style.width = progress + '%'`；仅一处。
5. **暂停状态数值冻结**：暂停时 `elapsed = pausedElapsed`（已冻结），不是 `Date.now() - started`。
6. **`completeWithFeedback` 与 `stopTimerFromDock` 互斥**：同一 `session_id` 不能并发两次 `complete`。前端已通过 `confirmComplete` 串行；后端按 `session_id` 唯一锁。
7. **不引入新接口**：美术资产接入**禁止**新增 `/api/timer/*` 路径或字段；与后端契约见 `server/blueprints/timer_bp.py`（start/complete/active/pause/resume）。

---

## 5. 尺寸 / 响应式 / z-index / 可访问性 / 减少动效 / 失败回退

### 5.1 尺寸

| 元素 | 桌面（≥900px） | 中型（600–900px） | 移动（<600px） | 缩放控制 |
|------|----------------|--------------------|----------------|----------|
| 任务列表卡（`.task-card`） | 320px 起步，auto-fill grid，`--card-scale: 1` | 同左 | 单列 | 无 |
| 抽出卡（`.task-card.drawn-card`） | max-width 500px（默认）/ 420px（CSS 双声明里靠后者覆盖） | `min(500px, 90vw)` | 同 600-900px | `--card-scale ∈ [0.6, 1.5]`，`#cardSizeRange` L1604 即时设置 |
| 牌堆 / 弃牌 | 140×98 | 140×98 | 100×140（.card-deck 旋转 90° 但 CSS 仅改容器，children 未旋转；以 `@media (max-width:600px)` L587-595 现有声明为准，**美术不要新增断点**） | 无 |
| Dock | 240–280 px 宽 | 同 | 全宽 | 无 |
| 模态（feedback/care/discard/stateAssessment） | 600 / 460 / 640 / 560 / 560 px | 同 | 90vw | 无 |

合同要点：美术资产**不应**强制最小宽高；遇到 100×140 窄容器，纹样应能 `background-size: cover` 缩放，不溢出。

### 5.2 z-index 分层（已有，确保美术插入不被遮挡）

```
toast-container:        9999
modal-overlay:           999
header:                 100   (sticky top)
card-fly-layer:         500
gacha-main-btn:           2    (与 .gacha-draw-stage 中 stage z-index 一致)
.gacha-draw-stage .timer-dock: 默认，未显式 z-index（被卡片内部覆盖）
.discard-pile:            3
.task-card-ornament:      2
.task-card-pattern:       0    (CSS L412 注释）
```

美术插入位一般 **≤ 装饰 ≤ z-index 0**，**绝不超过 modal 999**。

### 5.3 可访问性

1. **装饰元素必须 `aria-hidden="true"`**（沿用现有 `.task-card-pattern / .card-back-pattern` 写法）。
2. **焦点环**：原生 `<button>` / `<input>` / `<a>` 不被覆盖；金色 `:focus-visible` 在 `.gacha-multi-item`（CSS L562）已存在；新增插画不得吞掉焦点环。
3. **键盘**：所有现有快捷键 / 焦点跳转不变（`Enter` / `Space` 触发原生 `<button>`）；美术不引入新的 keyboard event listener。
4. **不依赖颜色**：状态（已完成 / 弃牌 / 阻塞）已经用 class + 文本标签（`已完成 / 弃牌堆 / 阻塞`），美术不要去掉。
5. **`<img>` 必须带 `alt=""`** 或 `role="presentation"`（SVG 装饰用 `aria-hidden`）。

### 5.4 减少动效（关键无障碍约束）

```css
@media (prefers-reduced-motion: reduce) {
  .task-card.is-drawing,
  .task-card.is-completing,
  .task-card.is-evaporating,
  .task-card.is-discarding,
  .task-card.is-skipping,
  .task-card.is-refusing,
  .task-card.is-burning,
  .task-card.is-fly-to-pile,
  .drawn-card,
  .flying-card,
  .card-deck,
  .timer-progress-bar { animation: none !important; transition: none !important; }
}
```

**建议（草案，待美术到位后实现）**：美术资源到位时，绝不绑定 SVG `<animate>` / `<animateTransform>`（不能因 `prefers-reduced-motion` 被全局覆盖）。

### 5.5 图片加载失败 / 无资源的回退

| 美术插入位 | 加载失败回退 | 完全无资源回退 |
|------------|--------------|------------------|
| 卡面底图 | 跳过首层 `background-image`，保留第二层 CSS 渐变 | 仅 CSS 渐变 + Unicode 字符（**已有**） |
| 卡背纹样 | 跳过 SVG，保留现有 `.card-back-pattern` CSS 重复斜纹 + `.card-back-emblem` ✦ | 同上 |
| 弃牌卡 | 失败时无 SVG，外层 `.discard-pile-visual-card` 仍是灰阶 CSS 渐变 | 同 |
| 怀表 | `<div id="timerDockActive">` 无背景，仍然显示文字 / 进度条 | 同 |
| 进度条纹理 | `style.width` 仍生效，仅背景图缺失 | 同 |
| 反馈羊皮纸 | `.modal` 默认 `var(--bg-primary)` 仍是深色面板 | 同 |
| 完成关怀插画 | modal 显示三个按钮 | 同 |

合同要点：客户端**禁止** `Image.onerror` 抛错 / 全局 `console.error`；资源缺失应静默回退（日志仅一次警告）。

---

## 6. 分阶段接入方案与验收

> 所有阶段都**不动 API、不动任务状态、不动真实数据库**。每个阶段独立可回滚。

### 阶段 0（当前）— 静态合同（本文档）

- 产物：`docs/M1_5_ASSET_SEAM_CONTRACT_20261012.md`（唯一写入文件）。
- 验收：本文件由 Controller 审阅；现存 7/7 E2E（A-G）、115 Python characterize 不破。

### 阶段 1 — 静态装饰（仅美术对话 + index.html CSS 增量，无 JS 改动）

- 接入位：§1.2 全部"草案插入位"。
- 范围：
  1. 新增 `static/assets/cards/...` SVG 资产（按 §2.1 路径与命名）。
  2. 在 `src/index.html` 的 `<style>` 块新增 `.task-card-bg` / `.card-deck-card::before` / `.card-back-pattern` 等 CSS 规则，加 `background-image: url(/static/assets/...)`。
  3. `static/app.js` **不动**。`static/modules/*` **不动**。API **不动**。
- 验收：
  - 真实 Factory 页面继续 7/7 通过（`tests/e2e/factory-realpage-safe.spec.js` + `e2e-manual.js`）。
  - 浅色 / 深色模式切换 `data-theme="light"/dark"` 资源仍然显示，无 `console.error`。
  - `prefers-reduced-motion: reduce` 下视觉帧静止。

### 阶段 2 — 独立动效（仅 CSS keyframes / SVG 内部）

- 范围：
  1. 美术可在 SVG 内部使用 `<animate>` 或 CSS keyframes；但**新增 keyframe 名不能与现有 11 个冲突**。
  2. 与计时器同步的"指针走动"严格基于 `--card-scale` / 现有 `transition`，不引入 JS 时间驱动。
- 验收：
  - Phase-1 的 `cardIn / fadeIn / slideUp / cardDrawOut` 等保持原有时长（0.45–0.9 s）。
  - `prefers-reduced-motion` 测试通过。

### 阶段 3 — 与数据层无关的可选扩展

- 范围（草案，超出本 M1.5A；待独立批）：
  1. 卡牌主题可由后端 `task.theme_override` 字段驱动（M1.5B/C 后续任务）。
  2. 用户可在 `#page-config` 上传自定义卡背（独立任务，避免污染本合同）。
- 前置依赖：阶段 1 + 2 全部通过；后端契约变更需要新 MDP / 单独合同。

### 验收通用清单

1. `tests/e2e/factory-realpage-safe.spec.js` 7/7 通过（A-G）。
2. `tests/characterize/test_http_characterization.py` 至少 115 项不破。
3. `node --check static/app.js && node --check static/app.entry.js` 通过（已在本任务中执行）。
4. 没有新文件被写入到 `src/notes / data / config / .cursor/hooks / docs/...` 之外。
5. 没有 CSS / JS / HTML 现有选择器 / 函数被重命名。
6. `prefers-reduced-motion / prefers-contrast / prefers-color-scheme` 切换均无视觉破裂。

---

## 7. 给独立美术对话与代码实现者的简明交付标准

### 给独立美术对话（必须遵守）

1. **只产出 SVG** + 透明背景 + 命名遵循 §2.1 / 2.2；总包 ≤ 500 KB。
2. 文件落点：`static/assets/...`，不要写其他任何目录。
3. 颜色全部走 CSS 变量 / `currentColor`，不在 SVG 内嵌入 hard-coded `#xxxxxx`。
4. **不要**新增 JS / HTML / CSS 选择器；只提供 SVG。视觉整合由后续工程 Agent 完成。
5. 不需要触碰计时器 / 进度条 / 反馈 / 关怀 modal 的真实行为；只画插画。
6. 交付清单（最终 zip 内至少含）：
   - `cards/faces/<theme>/*`（7 主题 × {front-bg, 4× corner, header-band, body-pattern} ≈ 56 文件，可压缩为单 sprite SVG）
   - `cards/backs/common/{back-pattern,emblem}.svg`
   - `cards/deck/*` + `cards/discard/*`
   - `dock/{pocket-watch,watch-ticks,frame}.svg`
   - `progress/{progress-ticks,progress-fill}.svg`
   - `feedback/feedback-paper.svg`
   - `care/care-illust-success.svg`
   - `ui/modal-frame.svg`

### 给代码实现者（独立 M1.5B+ 任务）

1. 在 `src/index.html` 的 `<style>` 块增加：
   ```
   .task-card-bg { background-image: var(--card-bg-url, none), var(--card-bg); background-size: cover; background-position: center; }
   .theme-math .task-card-bg { --card-bg-url: url(/static/assets/cards/faces/theme-math/front-bg.svg); }
   /* ... 其他 7 主题同理 */
   ```
2. 在 `renderDrawnCard` 和 `buildTaskCardHtml` 中新增一个 `<span class="task-card-bg" aria-hidden="true">` 子元素（**不替换**现有结构）。所有现有 `class` / `id` 必须保留。
3. 在 `updateDiscardPileVisual` 动态创建的 `.discard-pile-visual-card` 中追加 `background-image: url(...)`（保持现有 `--di` 错位偏移、CSS `filter`）。
4. 在 `static/app.js` 的 `playCardFlyAnimation` 中（飞行 `<div class="flying-card">`），追加 `background-image: url(...)`；不在 DOM 添加 `data-*`。
5. 不修改 `_currentDrawnTask`、`_pendingStartTaskId`、`timerDockSession`、`timerDockPaused`、`timerDockPausedElapsed`、`gachaState.*`。
6. 任何新增监听应经过 `window.SAL.core.eventBus`（已有总线，Phase 1 stub），不在全局 `addEventListener` 重复声明已绑事件。
7. 不引入新依赖（不引 JS / 不引 npm）。

### 红线（两份都看）

- ❌ 不写 `src/notes`、`data/task_publisher.db*`、`config/config.json`、`.cursor/hooks`、`docs/*.md`（除 `M1_5_ASSET_SEAM_CONTRACT` 及后续 M1.5B/C 文档）。
- ❌ 不动 `tests/characterize/*`、`tests/e2e/*`。
- ❌ 不动 `server/` 任何 `.py`。
- ❌ 不动 `static/app.js`、`static/app.entry.js`、`static/core/*`、`static/shared/*`、`static/modules/*` 的真实选择器或事件流。
- ❌ 不动 `src/index.html` 的 `<script>` 顺序 / 已声明的 `<link>`。
- ❌ 不联网下载图片；不调用外部 CDN；不触碰 `static/vendor/`。

---

## 8. 现存不确定性 / 已知 Open Issues

> 美术对话与后续工程 Agent 在动手前请向 Controller 确认。

1. **是否引入 `<canvas>` 全局渲染**：当前合同默认 SVG + DOM 子节点；若需更高动态（如真实可拖拽、动态纹理合成），应另立合同。
2. **怀表"指针"是否随时间转动**：当前时钟驱动是 1 秒一次的文本 / 进度条更新，没有任何指针 / 角度变量；引入指针将动效落在 `requestAnimationFrame` 还是 SVG `<animate>`，需确认。
3. **手绘 / 复古画板是否在刻度上带听觉 / 触觉反馈**：现行 UI 无任何 `audio` / `vibrate` 集成；合同默认**不加**。
4. **完成关怀插画是否随科目切换**：当前 3 个按钮与 `_careContext.category` 决定后端 `care-draw` 类别；插画若也随类别切换，需要后端返回类别键，建议保持中性画面。
5. **多语言 / 中文 UI 文案混排**：CSS `--font-display` / `--font-heading` / `--font-body` 均为 `Cinzel / Cinzel Decorative / Cormorant Garamond`（Latin serif）。中文卡面装饰不应再依赖这些字体。

---

## 9. 变更记录

| 版本 | 日期 | 作者 | 摘要 |
|------|------|------|------|
| v1 草案 | 2026-10-12 | M1.5A Agent | 初版合同，仅写入本文档；不修改任何源码 / 配置 / 数据库。 |

TASK_TOKEN: LT_M1_5A_ASSET_SEAM_CONTRACT_20261012_M
