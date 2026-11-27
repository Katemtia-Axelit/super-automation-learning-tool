"use strict";
/**
 * AR03-P4 —— 布局工具类与组件类的**属性级冲突**扫描。
 *
 * 背景：六文件重组把通用布局工具类（.grid / .g2 / .flex / .fc / .gap8 /
 * .gap16 / .jc / .ac / .sb / .wrap / .grow / .mt* / .mb* / .hidden）从
 * 原位置移到了 layout.css，而 layout.css 在 components.css **之前**加载。
 *
 * 若某个元素同时带 `btn` 与 `gap16` 这类组合，两个规则都会命中 `gap`
 * 属性，胜者会从「工具类」变成「组件类」→ 视觉变化。本脚本：
 *   1. **从真实 CSS 解析**每个选择器实际声明的属性（不硬编码，避免误报）；
 *   2. 扫描 HTML 静态类名 + JS 字符串/模板字符串类名；
 *   3. **判定胜者是否真的改变** —— 只有「迁移前」与「迁移后」胜出的一方
 *      不同才算冲突。单纯的属性重叠（哪怕同属性）**不是**冲突：
 *      例如 `.modal-actions mt16` 两者都声明 margin-top，但
 *      `.modal-actions` 在 components.css（后）→ 胜者与迁移前一致 → 无冲突。
 *
 * 胜者判定规则（与 CSS 层叠一致，也与 scripts/check_css_architecture.js
 * 的门禁 ⑥ 保持同一套逻辑）：
 *   1. 任一方对该属性带 !important → 带的那方恒定胜出；
 *   2. 否则特异度高者胜；
 *   3. 同特异度 → 源序靠后者胜。
 *
 * 用法：node scripts/check_layout_utility_conflicts.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const CSS_DIR = path.join(ROOT, "static", "css");
const CSS_ORDER = ["theme", "layout", "components", "features", "cards", "responsive"];

const SOURCES = [
  "src/index.html",
  "static/app.js",
  "static/core/ui.js",
  "static/core/ui/toast.js",
  "static/core/ui/modal.js",
  "static/modules/free-task.js",
];

/** 布局工具类。 */
const UTILITIES = new Set([
  "grid", "g2", "g3", "g4", "flex", "fc", "gap8", "gap16",
  "jc", "ac", "sb", "wrap", "grow",
  "mt8", "mt16", "mt24", "mb8", "mb16", "hidden",
]);

// ---------------------------------------------------------------------------
// 从真实 CSS 解析选择器 → 声明的属性集合
// ---------------------------------------------------------------------------

/**
 * 迁移前基线里的**同特异度覆盖对**。
 *
 * 来源：tests/fixtures/css_cascade_baseline.json 的 declarationPairs
 * （由 scripts/capture_css_baselines.js 在迁移前抓取）。
 *
 * 语义：key = "utility|component|prop" 存在 → 迁移前 utility 在前、
 * component 在后 → **component 胜出**；key = "component|utility|prop"
 * 存在 → utility 胜出。
 */
const BASELINE_PAIRS = (() => {
  /** key → { aImportant, bImportant } */
  const map = new Map();
  const p = path.join(ROOT, "tests", "fixtures", "css_cascade_baseline.json");
  if (!fs.existsSync(p)) return map;
  try {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    for (const pair of data.declarationPairs || []) {
      // 基线里 a / b 带前导点（".mt16"），这里统一去掉
      const key = `${String(pair.a).replace(/^\./, "")}|${String(pair.b).replace(/^\./, "")}|${pair.prop}`;
      map.set(key, {
        aImportant: !!pair.aImportant,
        bImportant: !!pair.bImportant,
      });
    }
  } catch (e) {
    // 基线不可用 → 退化为"无法判定迁移前胜者" → 不报冲突（保守）
  }
  return map;
})();

function maskComments(css) {
  return css
    .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

/** 解析 CSS → [{ selector, props:Set, importantProps:Set, order }]。 */
function parseRules(css) {
  const masked = maskComments(css);
  const rules = [];
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
    skipWs();
    if (i >= masked.length) break;
    const braceAt = masked.indexOf("{", i);
    if (braceAt === -1) break;
    const prelude = masked.slice(i, braceAt).trim();
    const { inner, end } = readBlock(braceAt);

    const props = new Set();
    const important = new Set();
    let depth = 0;
    let buf = "";
    const flush = () => {
      const s = buf.trim();
      buf = "";
      if (!s) return;
      const idx = s.indexOf(":");
      if (idx === -1) return;
      const prop = s.slice(0, idx).trim();
      const value = s.slice(idx + 1).trim();
      if (!prop || prop.startsWith("--")) return; // 自定义属性不算冲突
      props.add(prop);
      if (/!important/i.test(value)) important.add(prop);
    };
    for (const ch of inner) {
      if (ch === "(") depth++;
      else if (ch === ")") depth--;
      if (ch === ";" && depth === 0) flush();
      else buf += ch;
    }
    flush();

    rules.push({ selector: prelude, props, important, order: rules.length });
    i = end + 1;
  }
  return rules;
}

/** 计算选择器的特异度 [id, class/attr/pseudo, type]。 */
function specificityOf(sel) {
  const ids = (sel.match(/#[\w-]+/g) || []).length;
  const classes =
    (sel.match(/\.[\w-]+/g) || []).length +
    (sel.match(/\[[^\]]+\]/g) || []).length +
    (sel.match(/:(?!:)[\w-]+/g) || []).length;
  const types = (sel.match(/(^|[\s>+~])[a-zA-Z][\w-]*/g) || []).length;
  return [ids, classes, types];
}

/**
 * 构建：选择器（单类名）→ 该类名**逐属性**的"最强声明"。
 *
 * 记录内容：{ specificity, important, order }。
 * 便于判断"同一个 (类, 属性) 最终由谁胜出"。
 */
function buildSelectorIndex() {
  /** className → prop → { specificity, important, order } */
  const index = new Map();
  let order = 0;

  const betterThan = (a, b) => {
    if (!b) return true;
    if (a.important !== b.important) return a.important;
    for (let i = 0; i < 3; i++) {
      if (a.specificity[i] !== b.specificity[i]) {
        return a.specificity[i] > b.specificity[i];
      }
    }
    return a.order > b.order;
  };

  for (const name of CSS_ORDER) {
    const p = path.join(CSS_DIR, `${name}.css`);
    if (!fs.existsSync(p)) continue;
    const rules = parseRules(fs.readFileSync(p, "utf8"));
    for (const r of rules) {
      for (const sel of r.selector.split(",")) {
        const s = sel.trim();
        // 只处理"纯单类名"选择器（工具类 / 组件类都是单类）
        if (!/^\.[a-zA-Z][\w-]*$/.test(s)) continue;
        const cls = s.slice(1);
        const spec = specificityOf(s);
        if (!index.has(cls)) index.set(cls, new Map());
        const byProp = index.get(cls);
        for (const prop of r.props) {
          const cand = {
            specificity: spec,
            important: r.important.has(prop),
            order: order++,
          };
          if (betterThan(cand, byProp.get(prop))) byProp.set(prop, cand);
        }
      }
    }
  }
  return index;
}

// ---------------------------------------------------------------------------
// 扫描
// ---------------------------------------------------------------------------

/**
 * 扫描。
 *
 * 判定标准：**"迁移前胜者" vs "迁移后胜者"是否不同**。
 *
 * 迁移前的层叠：所有 CSS 在同一段内联 <style> 里，顺序 = 原文件里的规则序
 * （基线 tests/fixtures/css_cascade_baseline.json 的 declarationPairs 记录
 * 了同特异度下的覆盖对：utility → component 表示 component 原本就在后面，
 * 即 component 原本胜出）。
 *
 * 迁移后的层叠：按 CSS_ORDER 拼接，工具类在 layout.css（早），组件类在
 * components.css / features.css / cards.css（晚）→ component 胜出。
 *
 * 因此只有当"迁移前 utility 胜出"而"迁移后 component 胜出"时，才是真冲突。
 */
function scan() {
  const index = buildSelectorIndex();
  const conflicts = [];
  const seen = new Set();
  let scanned = 0;
  let classAttrs = 0;

  /** 迁移前：组件类是否胜出（依据基线覆盖对 + !important）。 */
  const beforeComponentWins = (utility, component, prop) => {
    const uRec = index.get(utility);
    const cRec = index.get(component);
    if (!uRec || !cRec) return null;
    const uInfo = uRec.get(prop);
    const cInfo = cRec.get(prop);
    if (!uInfo || !cInfo) return null;

    // 基线里若存在 (utility → component, prop) 覆盖对 → component 在后 → 胜出
    const fwd = BASELINE_PAIRS.get(`${utility}|${component}|${prop}`);
    const rev = BASELINE_PAIRS.get(`${component}|${utility}|${prop}`);
    if (fwd && !rev) {
      // 同特异度 → 后者胜；但若 utility 带 !important 则 utility 恒定胜出
      if (fwd.aImportant !== fwd.bImportant) return fwd.bImportant;
      return true;
    }
    if (rev && !fwd) {
      if (rev.aImportant !== rev.bImportant) return rev.aImportant;
      return false;
    }
    // 基线里没有这对 → 用当前 CSS 的 !important 判断（特异度差异场景）
    if (uInfo.important !== cInfo.important) return cInfo.important;
    return null; // 无法判定 → 不算冲突（保守）
  };

  /** 迁移后：组件类是否胜出（按 CSS_ORDER 的实际层叠）。 */
  const afterComponentWins = (utility, component, prop) => {
    const uRec = index.get(utility);
    const cRec = index.get(component);
    if (!uRec || !cRec) return null;
    const uInfo = uRec.get(prop);
    const cInfo = cRec.get(prop);
    if (!uInfo || !cInfo) return null;
    if (uInfo.important !== cInfo.important) return cInfo.important;
    for (let i = 0; i < 3; i++) {
      if (uInfo.specificity[i] !== cInfo.specificity[i]) {
        return cInfo.specificity[i] > uInfo.specificity[i];
      }
    }
    return cInfo.order > uInfo.order;
  };

  /** 检查一个 class 列表是否与工具类发生**胜者改变**级别的冲突。 */
  function checkClasses(classStr, file, kind) {
    const cls = classStr.split(/\s+/).filter(Boolean);
    const utils = cls.filter((c) => UTILITIES.has(c));
    if (!utils.length) return;

    const comps = cls.filter((c) => !UTILITIES.has(c) && index.has(c));
    if (!comps.length) return;

    for (const u of utils) {
      const uRec = index.get(u);
      if (!uRec) continue;
      for (const c of comps) {
        const cRec = index.get(c);
        if (!cRec) continue;
        for (const prop of uRec.keys()) {
          if (!cRec.has(prop)) continue;
          const key = `${file}|${classStr}|${u}|${c}|${prop}`;
          if (seen.has(key)) continue;
          seen.add(key);

          const before = beforeComponentWins(u, c, prop);
          const after = afterComponentWins(u, c, prop);
          if (before === null || after === null) continue;
          if (before === after) continue; // 胜者未变 → 无冲突

          conflicts.push({
            file,
            kind,
            classes: classStr,
            utility: u,
            component: c,
            property: prop,
            beforeWinner: before ? c : u,
            afterWinner: after ? c : u,
          });
        }
      }
    }
  }

  for (const rel of SOURCES) {
    const p = path.join(ROOT, rel);
    if (!fs.existsSync(p)) continue;
    const text = fs.readFileSync(p, "utf8");
    scanned++;

    const patterns = [
      { re: /class\s*=\s*"([^"]*)"/g, kind: "attr" },
      { re: /class\s*=\s*'([^']*)'/g, kind: "attr" },
      { re: /class\s*=\s*`([^`]*)`/g, kind: "template" },
      { re: /className\s*=\s*["']([^"']+)["']/g, kind: "className" },
    ];
    for (const { re, kind } of patterns) {
      let m;
      while ((m = re.exec(text)) !== null) {
        classAttrs++;
        checkClasses(m[1], rel, kind);
      }
    }
  }

  return { conflicts, scanned, classAttrs, index };
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

function main() {
  const { conflicts, scanned, classAttrs, index } = scan();
  console.log("=== 布局工具类 / 组件类 属性冲突扫描 ===");
  console.log(`扫描文件数: ${scanned}`);
  console.log(`扫描 class 属性数: ${classAttrs}`);
  console.log(`已索引类名数: ${index.size}`);
  console.log(`冲突数: ${conflicts.length}`);
  if (conflicts.length) {
    console.log("");
    for (const c of conflicts) {
      console.log(
        `  [${c.kind}] ${c.file}: class="${c.classes}"\n` +
          `         ${c.utility} 与 ${c.component} 同时声明 "${c.property}"\n` +
          `         胜者改变：迁移前 ${c.beforeWinner} 胜 → 迁移后 ${c.afterWinner} 胜 → 视觉会变`,
      );
    }
    console.log("");
    console.log("FAIL —— 需调整文件归属（把工具类移回 components 之后）或引入特异性修正。");
    process.exit(1);
  }
  console.log("PASS —— 未发现胜者改变的属性级冲突，重排不改变任何元素的计算样式。");
  process.exit(0);
}

main();
