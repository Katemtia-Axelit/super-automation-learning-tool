"use strict";
/**
 * AR03-P4 / B1–B6 —— CSS 迁移器。
 *
 * 把 `src/index.html` 的 3 个内联 <style> 块拆分为 `static/css/` 下的
 * 6 个扁平分层样式文件，**严格保持原始源序**。
 *
 * 分工（见 AR03-P4 Plan §2.2 选择器唯一归属表）：
 *   theme.css        全局主题 Token 唯一权威 + @font-face
 *   layout.css       页面骨架 + 通用工具类 + 5 个通用 keyframes
 *   components.css   通用组件
 *   features.css     业务模块专属（含 freeTaskStyle 全部）
 *   cards.css        任务卡系统 + 卡牌 9 keyframes + 美术接缝 cards 侧
 *   responsive.css   全部 @media
 *
 * 特殊处理：
 *   1. 竖版翻牌死规则（`.task-card-inner { aspect-ratio: 3.5/2.2 }` 那一组）
 *      被后面的横版完整覆盖 → 整段删除（视觉不变）。
 *   2. `.drawn-card-stage` 有两条：前一条无 scale、后一条带 scale。
 *      后者生效 → 归 cards.css，前者作为死规则删除。
 *   3. Theme 收敛（§3.3）：7 处 hover/边框 + 11 处金色交互态 + 3 处徽标
 *      + 危险操作底 → 改用语义化变量（变量定义在 theme.css）。
 *
 * 该脚本**只写** `static/css/**`；**不改** `src/index.html`（由 B7 步骤改）。
 *
 * 用法：node scripts/migrate_css_split.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const INDEX_HTML = path.join(ROOT, "src", "index.html");
const CSS_DIR = path.join(ROOT, "static", "css");

// ---------------------------------------------------------------------------
// 解析：把 CSS 切成有序的顶层条目（规则 / at-rule）
// ---------------------------------------------------------------------------

/**
 * 解析顶层条目，保留原始文本片段（含空白），以便原样搬迁。
 * 返回 [{ type:'rule'|'at', selector, text, inner }]，text 是原始源码片段。
 *
 * 关键技巧 —— **掩码（masking）**：
 *   解析前把 CSS 注释（/* ... *\/）与 HTML 风格注释（<!-- ... -->）
 *   替换成**等长空白**。这样：
 *     1. 注释文本不会污染选择器（前缀）→ 归属判定正确；
 *     2. 所有字符偏移量保持不变 → 可以从**原始** CSS 中切出文本片段，
 *        注释天然随片段一起被搬运，无需占位符 / 还原机制。
 */
function parseEntries(css) {
  // 掩码：注释 → 等长空白（保留换行以维持行号与排版）
  const masked = css
    .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));

  const out = [];
  let i = 0;

  function skipWs() {
    while (i < masked.length && /\s/.test(masked[i])) i++;
  }

  function readBlock(start) {
    let depth = 0;
    let j = start;
    for (; j < masked.length; j++) {
      if (masked[j] === "{") depth++;
      else if (masked[j] === "}") {
        depth--;
        if (depth === 0) return { inner: masked.slice(start + 1, j), end: j };
      }
    }
    return { inner: masked.slice(start + 1), end: masked.length };
  }

  while (i < masked.length) {
    const start = i;
    skipWs();
    if (i >= masked.length) break;

    const braceAt = masked.indexOf("{", i);
    if (braceAt === -1) break;
    const prelude = masked.slice(i, braceAt).trim();
    const { inner, end } = readBlock(braceAt);
    // 文本片段取自**原始** CSS（偏移一致）→ 注释随片段被原样搬运。
    const text = css.slice(start, end + 1);

    if (prelude.startsWith("@")) {
      out.push({
        type: "at",
        selector: prelude,
        text,
        atName: prelude.split(/\s/)[0],
        inner,
        props: [],
      });
    } else {
      out.push({
        type: "rule",
        selector: prelude,
        text,
        inner,
        props: declProps(inner),
      });
    }
    i = end + 1;
  }
  return out;
}

/** 提取声明块中的属性名集合（用于死规则判定）。 */
function declProps(inner) {
  const props = new Set();
  let depth = 0;
  let buf = "";
  const flush = () => {
    const s = buf.trim();
    buf = "";
    if (!s) return;
    const idx = s.indexOf(":");
    if (idx === -1) return;
    const prop = s.slice(0, idx).trim();
    if (prop) props.add(prop);
  };
  for (const ch of inner) {
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    if (ch === ";" && depth === 0) flush();
    else buf += ch;
  }
  flush();
  return [...props];
}

// ---------------------------------------------------------------------------
// 归属判定
// ---------------------------------------------------------------------------

/** 选择器归一化（用于匹配，去空白）。 */
function norm(sel) {
  return sel.replace(/\s+/g, " ").trim();
}

// --- 归属谓词 -------------------------------------------------------------

const SELECTORS = {
  ROOT: (s) => s === ":root" || s.startsWith(":root[data-theme"),
  CARD: (s) =>
    /^\.task-card/.test(s) ||
    /^\.card-deck/.test(s) ||
    /^\.discard-/.test(s) ||
    /^\.card-fly-layer/.test(s) ||
    /^\.flying-card/.test(s) ||
    /^\.drawn-card/.test(s) ||
    /^\.card-back-/.test(s) ||
    /^\.card-act-btn/.test(s),
  FEATURE: (s) =>
    /^#freeTaskPanel/.test(s) ||
    /^#freeTaskHomeStatus/.test(s) ||
    /^\.free-task-/.test(s) ||
    /^\.gacha-/.test(s) ||
    /^\.task-toolbar/.test(s) ||
    /^\.task-grid/.test(s) ||
    /^\.tag-chip/.test(s) ||
    /^\.tag-input-wrap/.test(s) ||
    /^\.schedule-nav/.test(s) ||
    /^\.sched-/.test(s) ||
    /^\.know-/.test(s) ||
    /^\.cat-item/.test(s) ||
    /^\.note-item/.test(s) ||
    /^\.md-content/.test(s) ||
    /^\.lang-word/.test(s) ||
    /^\.sleep-/.test(s) ||
    /^\.state-/.test(s) ||
    /^\.assess-/.test(s) ||
    /^\.agent-ro-/.test(s) ||
    /^\.prompt-file-/.test(s) ||
    /^\.energy-table/.test(s) ||
    /^\.feedback-emoji/.test(s) ||
    /^\.feedback-option/.test(s) ||
    /^\.replace-reason/.test(s) ||
    /^\.task-info-row/.test(s) ||
    /^\.timer-dock/.test(s) ||
    /^\.timer-progress/.test(s) ||
    /^\.timer-task-name/.test(s) ||
    /^\.timer-time/.test(s),
  COMPONENT: (s) =>
    /^(input|select|textarea|label)/.test(s) ||
    /^\.btn/.test(s) ||
    /^\.badge/.test(s) ||
    /^\.bg-/.test(s) ||
    /^\.card(-|\s|\.|$)/.test(s) ||
    /^\.section-title/.test(s) ||
    /^\.empty-state/.test(s) ||
    /^\.toast/.test(s) ||
    /^\.modal(\s|$|\.|\[)/.test(s) ||
    /^\.diff-/.test(s) ||
    /^\.activity-row/.test(s) ||
    /^\.timer-panel-status/.test(s) ||
    /^\.timer-idle/.test(s) ||
    /^\.timer-outcome-btns/.test(s),
  LAYOUT: (s) =>
    /^(body|header|nav|main|\.nav-btn|\.header-status|\.dot|\.theme-toggle|\.page|\.grid|\.g[234]|\.flex|\.fc|\.gap8|\.gap16|\.jc|\.ac|\.sb|\.wrap|\.grow|\.mt8|\.mt16|\.mt24|\.mb8|\.mb16|\.hidden|\.gradient-text|\.glass|\*|::-webkit-scrollbar)/.test(s),
};

// 手工指定归属的精确选择器。
const EXACT_OWNER = new Map();

function own(list, file) {
  for (const s of list) EXACT_OWNER.set(norm(s), file);
}

// theme.css
own([":root", ':root[data-theme="light"]'], "theme");

// layout.css
own([
  "*",
  "::-webkit-scrollbar",
  "::-webkit-scrollbar-track",
  "::-webkit-scrollbar-thumb",
  "body",
  ".gradient-text",
  ".glass",
  "header",
  "header h1",
  "nav",
  ".nav-btn",
  ".nav-btn:hover",
  ".nav-btn.active",
  ".header-status",
  ".dot.online",
  ".dot.offline",
  ".theme-toggle",
  ".theme-toggle:hover",
  ".theme-toggle i",
  "main",
  ".page",
  ".page.active",
  ".grid",
  ".g2",
  ".g3",
  ".g4",
  ".flex",
  ".fc",
  ".gap8",
  ".gap16",
  ".jc",
  ".ac",
  ".sb",
  ".wrap",
  ".grow",
  ".mt8",
  ".mt16",
  ".mt24",
  ".mb8",
  ".mb16",
  ".hidden",
], "layout");

// components.css
own([
  ".btn",
  ".btn:hover",
  ".btn.pri",
  ".btn.pri:hover",
  ".btn.danger",
  ".btn.sm",
  ".btn.ic",
  ".btn:disabled",
  "input, select, textarea",
  "input:focus, select:focus, textarea:focus",
  "select option",
  "textarea",
  "label",
  "input[type=number]",
  "input.full-width, select.full-width, textarea.full-width",
  ".badge",
  ".badge:hover",
  ".bg-gold",
  ".bg-blue",
  ".bg-green",
  ".bg-red",
  ".bg-purple",
  ".card",
  ".card:hover",
  ".card-head",
  ".card-title",
  ".card-meta",
  ".card-body",
  ".card-actions",
  ".section-title",
  ".section-title i",
  ".empty-state",
  ".empty-state i",
  ".toast-container",
  ".toast",
  ".toast.suc",
  ".toast.err",
  ".toast.inf",
  ".modal-overlay",
  ".modal",
  ".modal h2",
  ".modal .form-group",
  ".modal .frow",
  ".modal .frow > *",
  ".modal-actions",
  ".modal .modal-actions",
  ".diff-summary",
  ".diff-lines",
  ".diff-line-add",
  ".diff-line-rem",
  ".diff-line-chg",
  ".activity-row",
  ".activity-row:last-child",
  ".timer-panel-status",
  ".timer-idle",
  ".timer-outcome-btns",
], "components");

// features.css
own([
  ".gacha-container",
  ".gacha-energy, .gacha-pools",
  ".gacha-main-btn",
  ".gacha-main-btn i",
  ".gacha-main-btn:hover",
  ".gacha-main-btn:active",
  ".gacha-main-btn:disabled",
  ".gacha-draw-stage",
  ".gacha-stats-bar",
  ".gacha-stats-bar span",
  ".gacha-stats-bar strong",
  ".card-size-control",
  ".card-size-control:hover",
  ".card-size-control label",
  ".card-size-control input[type=range]",
  ".gacha-tag-row",
  ".gacha-controls-row",
  ".gacha-time-row",
  ".gacha-multi-row",
  ".gacha-multi-row.hidden",
  ".gacha-multi-btn",
  ".gacha-multi-btn:hover",
  ".gacha-multi-btn:disabled",
  ".gacha-multi-count-wrap",
  ".gacha-multi-count-wrap label",
  ".gacha-multi-count-wrap select",
  ".gacha-multi-result",
  ".gacha-multi-result.hidden",
  ".gacha-multi-summary",
  ".gacha-multi-summary strong",
  ".gacha-multi-list",
  "button.gacha-multi-item,\n.gacha-multi-item",
  "button.gacha-multi-item:hover,\n.gacha-multi-item:hover",
  "button.gacha-multi-item:focus-visible,\n.gacha-multi-item:focus-visible",
  'button.gacha-multi-item[aria-pressed="true"],\n.gacha-multi-item.activated',
  "button.gacha-multi-item:disabled,\n.gacha-multi-item:disabled",
  ".gacha-multi-item-title",
  ".gacha-multi-item-meta",
  ".gacha-multi-item-tag",
  ".gacha-draw-stage .timer-dock",
  ".gacha-draw-stage .timer-dock-idle",
  ".gacha-draw-stage .timer-dock-active .timer-task-name",
  ".gacha-draw-stage .timer-dock-active .timer-time",
  ".gacha-draw-stage .timer-dock-active .timer-progress",
  ".gacha-draw-stage .timer-dock-active .timer-progress-bar",
  ".gacha-draw-stage .timer-dock-btns",
  ".gacha-draw-stage .timer-dock::before",
  ".gacha-draw-stage .timer-dock .timer-task-name,\n.gacha-draw-stage .timer-dock .timer-time,\n.gacha-draw-stage .timer-dock .timer-progress,\n.gacha-draw-stage .timer-dock .timer-progress-bar,\n.gacha-draw-stage .timer-dock .timer-dock-btns,\n.gacha-draw-stage .timer-dock > *",
  ".replace-reason",
  ".replace-reason label",
  ".replace-reason input[type=radio]",
  ".replace-reason input:checked + label",
  ".task-info-row",
  ".task-info-row span",
  ".task-toolbar",
  ".task-grid",
  ".tag-chip",
  ".tag-chip .remove",
  ".tag-chip .remove:hover",
  ".tag-input-wrap",
  ".tag-input-wrap input",
  ".schedule-nav",
  ".schedule-nav button",
  ".schedule-nav button:hover",
  ".schedule-nav .date-label",
  ".sched-grid",
  ".sched-time",
  ".sched-slot",
  ".sched-slot:hover",
  ".sched-slot input.slot-act",
  ".know-layout",
  ".know-side",
  ".know-main",
  ".cat-item",
  ".cat-item:hover",
  ".cat-item.active",
  ".note-item",
  ".note-item:hover",
  ".note-item.active",
  ".note-item .note-meta",
  ".md-content",
  ".md-content h1, .md-content h2, .md-content h3",
  ".md-content p",
  ".md-content ul, .md-content ol",
  ".md-content code",
  ".md-content pre",
  ".md-content a",
  ".md-content blockquote",
  ".md-content table",
  ".md-content th, .md-content td",
  ".feedback-emoji",
  ".feedback-emoji button",
  ".feedback-emoji button:hover, .feedback-emoji button.sel",
  ".feedback-option",
  ".feedback-option:hover, .feedback-option.sel",
  ".feedback-option input",
  ".prompt-file-item",
  ".prompt-file-item:hover, .prompt-file-item.active",
  ".prompt-file-list",
  ".energy-table",
  ".agent-ro-tabs",
  ".agent-ro-tab",
  ".agent-ro-tab.active",
  ".agent-ro-layout",
  ".agent-ro-list, .agent-ro-files",
  ".agent-ro-item",
  ".agent-ro-item:hover, .agent-ro-item.active",
  ".agent-ro-detail",
  ".agent-ro-content",
  ".sleep-grid",
  ".sleep-stats",
  ".sleep-stat",
  ".sleep-stat .num",
  ".sleep-stat .lbl",
  ".state-scores",
  ".state-score",
  ".state-score .num",
  ".state-score .lbl",
  ".assess-q",
  ".assess-q label",
  ".assess-q input[type=range]",
  ".assess-q-val",
], "features");

// cards.css
own([
  ".task-card",
  ".task-card::before",
  ".task-card::after",
  ".task-card-ornament",
  ".task-card-ornament.tl",
  ".task-card-ornament.tr",
  ".task-card-ornament.bl",
  ".task-card-ornament.br",
  ".task-card-header",
  ".task-card-header-main",
  ".task-card-corner",
  ".task-card-mark",
  ".task-card-body-zone",
  ".task-card-title",
  ".task-card-desc",
  ".task-card-meta",
  ".task-card-stat",
  ".task-card-stat i",
  ".task-card-stat.stat-priority",
  ".task-card-pattern",
  ".task-card-pattern > span",
  ".task-card-pattern.lang-pattern",
  ".lang-word",
  ".task-card-tags",
  ".task-card-tags .badge",
  ".task-card-footer",
  ".task-card-actions",
  ".task-card-actions .btn",
  ".task-card-actions .btn.card-act-btn",
  ".task-card-actions .btn.card-act-btn.pri",
  ".task-card-actions .btn.card-act-btn.danger",
  ".task-card-actions .btn.card-act-btn:hover",
  ".task-card.status-completed",
  ".task-card.status-discarded",
  ".task-card.status-blocked",
  ".task-card.theme-math",
  ".task-card.theme-math::before",
  ".task-card.theme-lang",
  ".task-card.theme-history",
  ".task-card.theme-code",
  ".task-card.theme-write",
  ".task-card.theme-science",
  ".task-card.theme-review",
  ".task-card.theme-default",
  ".task-card.drawn-card",
  ".task-card.drawn-card.urgent",
  ".task-card.is-revealing .task-card-inner",
  ".task-card-face",
  ".task-card-back",
  ".task-card-back .card-back-emblem",
  ".task-card-back .card-back-pattern",
  ".task-card-front",
  ".task-card-front .task-card-header",
  ".task-card-front .task-card-body-zone",
  ".task-card-front .task-card-footer",
  ".drawn-card-stage",
  ".drawn-card",
  ".drawn-card.urgent",
  ".drawn-card .task-card-title",
  ".drawn-card .task-card-desc",
  ".drawn-card .task-card-stat",
  ".drawn-card .task-card-corner",
  ".drawn-card .task-card-mark",
  ".drawn-card .card-act-btn",
  ".task-card.is-drawing",
  ".task-card.is-completing",
  ".task-card.is-evaporating, .task-card.is-fly-to-pile",
  ".task-card.is-discarding",
  ".task-card.is-skipping",
  ".task-card.is-refusing",
  ".task-card.is-burning",
  ".card-deck",
  ".card-deck:hover",
  ".card-deck-card",
  ".card-deck-card::after",
  ".card-deck-card::before",
  ".card-deck.is-drawing",
  ".card-deck.is-drawing .card-deck-card:nth-child(5)",
  ".discard-pile",
  ".discard-pile-label",
  ".discard-pile-stack",
  ".discard-pile-empty",
  ".discard-visual-card, .discard-pile-visual-card",
  ".discard-visual-card::before,\n.discard-pile-visual-card::before",
  ".card-fly-layer",
  ".card-fly-layer .flying-card",
  ".flying-card::before",
  "#timerPanel",
  "#timerPanel::before",
  "#timerPanel > *",
  "#timerDockBar",
  ".modal::before",
  ".modal > *",
], "cards");

/**
 * 判定一个顶层条目的归属文件。
 */
function ownerOf(entry) {
  const sel = entry.selector;

  if (entry.type === "at" && entry.atName === "@font-face") return "theme";
  if (entry.type === "at" && entry.atName === "@media") return "responsive";

  if (entry.type === "at" && entry.atName === "@keyframes") {
    const name = sel.replace("@keyframes", "").trim();
    const CARD_KF = [
      "deckBreath", "deckPop", "cardDrawOut", "cardCompleteGlow", "cardEvaporate",
      "cardDiscardFly", "cardSkipAway", "cardRefuseAway", "cardBurn",
    ];
    return CARD_KF.includes(name) ? "cards" : "layout";
  }

  // 精确匹配（键已归一化）
  if (EXACT_OWNER.has(norm(sel))) return EXACT_OWNER.get(norm(sel));

  // 全部选择器都命中同一谓词
  const sels = sel.split(",").map(norm);
  if (sels.every((s) => SELECTORS.ROOT(s))) return "theme";
  if (sels.every((s) => SELECTORS.CARD(s))) return "cards";
  if (sels.every((s) => SELECTORS.FEATURE(s))) return "features";
  if (sels.every((s) => SELECTORS.COMPONENT(s))) return "components";
  if (sels.every((s) => SELECTORS.LAYOUT(s))) return "layout";

  // 混合 → 优先 card / feature / component
  for (const s of sels) {
    if (SELECTORS.CARD(s)) return "cards";
    if (SELECTORS.FEATURE(s)) return "features";
    if (SELECTORS.COMPONENT(s)) return "components";
    if (SELECTORS.LAYOUT(s)) return "layout";
  }
  return "layout";
}

// ---------------------------------------------------------------------------
// 选择器重写（源序等价性修复）
// ---------------------------------------------------------------------------

/**
 * 选择器重写表。
 *
 * 迁移前所有规则在**同一段**内联 <style> 中，相对顺序即 cascade 顺序。
 * 拆成 6 个文件后，工具类（layout.css）会排到组件类（components.css）
 * **之前**，同特异度下胜者可能翻转 → 视觉回归。
 *
 * 这里对确实存在"工具类会翻转组件类胜者"的规则提高特异度，使其**恒定**
 * 胜出，与文件加载顺序无关 → 视觉与迁移前逐像素一致。
 */
const SELECTOR_REWRITES = [
  {
    from: ".modal-actions",
    to: ".modal .modal-actions",
    reason:
      "迁移前 .modal-actions（idx 111）在 .mt16（idx 91）之后 → margin-top:20px 胜出；" +
      "拆文件后工具类在前会翻转成 16px。改用 .modal .modal-actions（0,2,0）恒定胜出。",
  },
];

// ---------------------------------------------------------------------------
// Theme 收敛替换（Plan §3.3 / §3.4）
// ---------------------------------------------------------------------------

const THEME_REPLACEMENTS = [
  // C 类：白色低透明度 hover / 边框（7 处）
  { selector: ".nav-btn:hover", find: "background: rgba(255,255,255,0.05);", replace: "background: var(--hover-veil);" },
  { selector: ".card:hover", find: "border-color: rgba(255,255,255,0.1);", replace: "border-color: var(--hover-veil-strong);" },
  { selector: ".sched-slot:hover", find: "background: rgba(255,255,255,0.03);", replace: "background: var(--hover-veil-subtle);" },
  { selector: ".cat-item:hover", find: "background: rgba(255,255,255,0.03);", replace: "background: var(--hover-veil-subtle);" },
  { selector: ".note-item:hover", find: "background: rgba(255,255,255,0.03);", replace: "background: var(--hover-veil-subtle);" },
  { selector: ".prompt-file-item:hover, .prompt-file-item.active", find: "background: rgba(255,255,255,0.05);", replace: "background: var(--active-veil);" },
  { selector: ".agent-ro-item:hover, .agent-ro-item.active", find: "background: rgba(255,255,255,0.05);", replace: "background: var(--active-veil);" },

  // B 类：金色强调交互态（8 处）
  { selector: ".nav-btn.active", find: "background: rgba(240,192,64,0.1);", replace: "background: var(--accent-veil);" },
  { selector: ".cat-item.active", find: "background: rgba(240,192,64,0.1);", replace: "background: var(--accent-veil);" },
  { selector: ".feedback-emoji button:hover, .feedback-emoji button.sel", find: "background: rgba(240,192,64,0.1);", replace: "background: var(--accent-veil);" },
  { selector: ".feedback-option:hover, .feedback-option.sel", find: "background: rgba(240,192,64,0.08);", replace: "background: var(--accent-veil-soft);" },
  { selector: ".agent-ro-tab.active", find: "background: rgba(240,192,64,0.1);", replace: "background: var(--accent-veil);" },
  { selector: ".replace-reason input:checked + label", find: "background: rgba(240,192,64,0.15);", replace: "background: var(--accent-veil-chip);" },
  { selector: "button.gacha-multi-item:hover,\n.gacha-multi-item:hover", find: "background: rgba(240,192,64,0.08);", replace: "background: var(--accent-veil-soft);" },
  { selector: 'button.gacha-multi-item[aria-pressed="true"],\n.gacha-multi-item.activated', find: "background: rgba(240,192,64,0.18);", replace: "background: var(--accent-veil-strong);" },

  // B 类：金色徽标底（3 处）
  { selector: ".bg-gold", find: "background: rgba(240,192,64,0.15);", replace: "background: var(--accent-veil-chip);" },
  { selector: ".tag-chip", find: "background: rgba(240,192,64,0.15);", replace: "background: var(--accent-veil-chip);" },
  { selector: ".gacha-multi-item-tag", find: "background: rgba(240,192,64,0.15);", replace: "background: var(--accent-veil-chip);" },

  // D 类：危险操作底（1 处）
  { selector: ".btn.danger", find: "background: rgba(231,76,60,0.1);", replace: "background: var(--danger-veil);" },
];

function applyThemeReplacements(entry) {
  const key = norm(entry.selector);
  let text = entry.text;
  const applied = [];

  for (const rep of THEME_REPLACEMENTS) {
    if (norm(rep.selector) !== key) continue;
    if (!text.includes(rep.find)) {
      console.warn(`  ! 主题替换未命中: ${rep.selector} (期望包含 ${rep.find})`);
      continue;
    }
    text = text.split(rep.find).join(rep.replace);
    applied.push(rep.selector);
  }
  return { text, applied };
}

// ---------------------------------------------------------------------------
// 死规则识别
// ---------------------------------------------------------------------------

/**
 * 真死规则：被**后面**同选择器完整覆盖的规则。
 *
 * 不能用"后面存在同选择器"这种启发式判定 —— 例如 `.task-card.theme-lang`
 * 出现两次，但第二次只**新增** `--art-card-front-layer` 声明，并不是覆盖；
 * `.drawn-card-stage` 也出现两次，第二次**新增** `transform` / `transform-origin`。
 *
 * 判定规则（按属性集合包含关系精确判断）：
 *   规则 A 在前、规则 B 在后、**选择器相同**：
 *     - 若 B 声明的属性 ⊇ A 的属性  →  A 是死规则（被完全覆盖）
 *     - 若 A 声明的属性 ⊇ B 的属性  →  B 是死规则（被 A 覆盖）
 *     - 否则                          →  两者都保留（各自声明了对方没有的属性）
 *
 * 注意：CSS 同特异度下**后者胜**，所以"后者被前者覆盖"在渲染上等价于
 * "后者是死规则"（它的声明不会生效，因为前者已设定同样的属性且优先级相同）。
 */
function findDeadRules(entries) {
  const dead = new Set();

  const bySelector = new Map();
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e.type !== "rule") continue;
    const key = norm(e.selector);
    if (!bySelector.has(key)) bySelector.set(key, []);
    bySelector.get(key).push({ index: i, props: new Set(e.props || []) });
  }

  for (const [, occ] of bySelector) {
    if (occ.length < 2) continue;

    // 逐对比较：只有"相邻的两条同选择器规则"才可能构成完全覆盖
    for (let k = 0; k + 1 < occ.length; k++) {
      const a = occ[k];     // 较早
      const b = occ[k + 1]; // 较晚

      const aHas = (p) => a.props.has(p);
      const bHas = (p) => b.props.has(p);

      const bCoversA = [...a.props].every(bHas);
      const aCoversB = [...b.props].every(aHas);

      if (bCoversA && a.props.size > 0) {
        // 后者完全覆盖前者 → 前者是死规则
        dead.add(a.index);
      } else if (aCoversB && b.props.size > 0) {
        // 前者完全覆盖后者 → 后者是死规则（其声明不生效）
        dead.add(b.index);
      }
      // 否则：属性集合互不包含 → 两条都保留
    }
  }
  return dead;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

const HEADERS = {
  theme: `/* ============================================================
 * theme.css —— 全局主题 Token 唯一权威 + 自托管字体声明
 * AR03-P4（CSS 模块化 + Theme 收敛）
 *
 * 职责：
 *   - :root / :root[data-theme="light"] —— 全站**唯一**的主题变量定义处
 *   - @font-face —— 自托管字体（Cinzel / Cinzel Decorative / Cormorant Garamond）
 *   - 语义化交互变量（hover / active / accent / danger）的 dark + light 双套值
 *
 * 所有权边界（AR03-P4 Plan §2.1）：
 *   - 本文件**只**拥有「全局主题 Token」。
 *   - 卡牌变量（--card-*）只在 cards.css 定义。
 *   - 美术变量（--art-*）由 static/assets/art-overrides.css 定义，此处**不出现**。
 *   - 运行时变量（--card-scale / --deck-i）由 JS / DOM 提供，此处**不定义**。
 *
 * dark 值为迁移前的原硬编码字面量 → **Dark 模式视觉逐像素不变**。
 * ============================================================ */`,
  layout: `/* ============================================================
 * layout.css —— 页面骨架与通用布局工具类
 * AR03-P4（CSS 模块化）
 *
 * 职责：reset、body、header / nav、main / page 切换、网格与间距工具类、
 *       5 个通用 keyframes（pulse / float / cardIn / fadeIn / slideUp）。
 *
 * 选择器唯一归属：见 AR03-P4 Plan §2.2。
 * ============================================================ */`,
  components: `/* ============================================================
 * components.css —— 通用组件样式
 * AR03-P4（CSS 模块化）
 *
 * 职责：btn / input / select / textarea / badge / card（容器）/ modal（基础）
 *       / toast / 空态 / 表单 / diff / activity-row / timer 状态行。
 *
 * 注意：\`.modal\` 的**基础外观**在本文件；其 \`::before\` 美术装饰层与
 *       \`> *\` 的 z-index 提升在 cards.css（--art-modal-frame 消费端）——
 *       这是选择器唯一归属表的**唯一显式豁免**。
 * ============================================================ */`,
  features: `/* ============================================================
 * features.css —— 业务模块专属样式
 * AR03-P4（CSS 模块化）
 *
 * 职责：gacha（含 timer-dock / gacha-multi 全套）/ tasks / schedule /
 *       knowledge / sleep / state / agent / prompts / feedback /
 *       自由任务面板（原 freeTaskStyle 全部内容）。
 *
 * 注意：\`.drawn-card-stage\` **不在**本文件 —— 它是卡牌舞台，归 cards.css。
 * ============================================================ */`,
  cards: `/* ============================================================
 * cards.css —— 任务卡系统 + 卡牌动画 + 美术接缝（cards 侧）
 * AR03-P4（CSS 模块化）
 *
 * 职责：.task-card 全套 + 8 个 theme 变体 + 翻牌系统（含 .drawn-card-stage）
 *       + 牌堆 / 弃牌堆 / 飞牌 + 卡牌 9 个 keyframes
 *       + M1.5 美术接缝的 cards 侧消费层。
 *
 * 所有权边界（AR03-P4 Plan §2.1）：
 *   - 本文件**拥有**卡牌 Token（--card-*），仅在 .task-card / .task-card.theme-* 内。
 *   - 美术 Token（--art-*）**不在**本文件定义，只在 var() 的 fallback 位消费；
 *     定义方是 static/assets/art-overrides.css。
 *   - 卡牌是**独立的深色设计语言**：不被浅色主题重映射。
 * ============================================================ */`,
  responsive: `/* ============================================================
 * responsive.css —— 全部媒体查询 + 动效/对比度偏好
 * AR03-P4（CSS 模块化 + Theme 收敛）
 *
 * 职责：全部 @media（900px / 600px / freeTask 600px）
 *       + prefers-reduced-motion（尊重动效减弱偏好）
 *       + prefers-contrast: more（提升边框对比度）。
 * ============================================================ */`,
};

function main() {
  const html = fs.readFileSync(INDEX_HTML, "utf8");

  const blocks = [];
  const re = /<style([^>]*)>([\s\S]*?)<\/style>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    blocks.push({ attrs: m[1].trim(), css: m[2] });
  }
  if (blocks.length === 0) {
    console.log(
      "src/index.html 中已无内联 <style> 块（迁移已完成）。\n" +
        "本脚本用于**从迁移前的 index.html** 生成 static/css/**；重复运行无意义。\n" +
        "如需重建，请从 git 恢复迁移前的 src/index.html（git show HEAD:src/index.html）。"
    );
    return;
  }
  if (blocks.length !== 3) {
    console.error(`FAIL: 期望 3 个 <style> 块，实际 ${blocks.length}`);
    process.exit(1);
  }

  const fontBlock = blocks.find((b) => /@font-face/.test(b.css)) || blocks[0];
  const mainBlock = blocks.find((b) => /:root\s*\{/.test(b.css));
  const freeBlock = blocks.find((b) => /freeTaskPanel/.test(b.css));
  if (!mainBlock || !freeBlock) {
    console.error("FAIL: 无法识别主样式块 / freeTaskStyle 块");
    process.exit(1);
  }

  const buckets = {
    theme: [],
    layout: [],
    components: [],
    features: [],
    cards: [],
    responsive: [],
  };

  const appliedReplacements = [];
  const droppedDead = [];
  const selectorRewrites = [];

  function processBlock(css, blockLabel) {
    const entries = parseEntries(css);
    const dead = findDeadRules(entries);

    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      if (dead.has(i)) {
        droppedDead.push({ block: blockLabel, selector: norm(e.selector) });
        continue;
      }
      const owner = ownerOf(e);
      // 文本片段取自原始 CSS（掩码解析保证偏移一致）→ 注释已随片段搬运。
      let text = e.text;

      if (e.type === "rule") {
        // 选择器重写（源序等价性修复）
        for (const rw of SELECTOR_REWRITES) {
          if (norm(e.selector) !== norm(rw.from)) continue;
          if (!text.includes(rw.from)) {
            console.warn(`  ! 选择器重写未命中: ${rw.from}`);
            continue;
          }
          text = text.replace(rw.from, rw.to);
          selectorRewrites.push({ from: rw.from, to: rw.to, reason: rw.reason });
        }

        const res = applyThemeReplacements(e);
        text = res.text;
        if (res.applied.length) {
          appliedReplacements.push(
            ...res.applied.map((s) => ({ selector: s, file: owner }))
          );
        }
      }

      buckets[owner].push(text.trim());
    }
  }

  // 字体块 → theme.css（放最前）
  for (const e of parseEntries(fontBlock.css)) buckets.theme.push(e.text.trim());

  processBlock(mainBlock.css, "main");
  processBlock(freeBlock.css, "freeTask");

  fs.mkdirSync(CSS_DIR, { recursive: true });

  const ORDER = ["theme", "layout", "components", "features", "cards", "responsive"];
  const written = [];

  for (const key of ORDER) {
    const body = buckets[key].join("\n");
    const file = path.join(CSS_DIR, `${key}.css`);
    const content = `${HEADERS[key]}\n\n${body}\n`;
    fs.writeFileSync(file, content, "utf8");
    written.push({
      file: `static/css/${key}.css`,
      rules: buckets[key].length,
      chars: content.length,
    });
  }

  console.log("=== 迁移产物 ===");
  for (const w of written) {
    console.log(`  ${w.file.padEnd(28)} 规则 ${String(w.rules).padStart(4)}  ${w.chars} chars`);
  }

  console.log("");
  console.log(`选择器重写（源序等价性修复）: ${selectorRewrites.length} 处`);
  for (const r of selectorRewrites) {
    console.log(`  ${r.from}  ->  ${r.to}`);
    console.log(`    理由: ${r.reason}`);
  }

  console.log("");
  console.log(`主题替换: ${appliedReplacements.length} 处`);
  const byFile = {};
  for (const r of appliedReplacements) byFile[r.file] = (byFile[r.file] || 0) + 1;
  for (const [f, n] of Object.entries(byFile)) console.log(`  ${f}: ${n}`);

  console.log("");
  console.log(`删除的覆盖死规则: ${droppedDead.length} 条`);
  for (const d of droppedDead) console.log(`  [${d.block}] ${d.selector}`);
}

main();
