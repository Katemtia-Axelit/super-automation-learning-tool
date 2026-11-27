"use strict";
/**
 * AR03-P4 / 阶段 C —— CSS 架构机械门禁。
 *
 * 只读脚本：不修改任何文件。退出码 0 = 全部通过，1 = 有违规。
 * 用法：
 *   node scripts/check_css_architecture.js
 *   node scripts/check_css_architecture.js --json
 *
 * 门禁清单（AR03-P4 Plan §4.3 / §4.4）：
 *   ① Token 所有权分层
 *      ①a :root / :root[data-theme=...] 只允许出现在 theme.css
 *      ①b --card-* 只允许**定义**在 cards.css
 *      ①c --art-* 只允许**消费**在 cards.css / features.css；
 *          **定义**只允许来自 static/assets/art-overrides.css
 *      ①d --card-scale / --deck-i 在任何 CSS 文件中都**不得**出现定义形式
 *   ② HTML 内联样式收敛：src/index.html 内 <style> 块数 = 0
 *   ③ 选择器唯一归属：同一选择器不得在 2 个 CSS 文件中各定义一次
 *      （豁免名单：仅 `modal`）
 *   ④ 样式文件加载顺序：<link> 顺序 = theme→layout→components→features→cards→responsive
 *   ⑤ 主题语义变量双向定义：9 个语义变量在 dark + light 两处都有定义，
 *      且 dark 值 = 迁移前的原硬编码字面量
 *   ⑥ 源序等价性：6 个文件按约定顺序拼接后的规则序列 vs 迁移前基线
 *      （相对顺序不得被打乱）
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const CSS_DIR = path.join(ROOT, "static", "css");
const INDEX_HTML = path.join(ROOT, "src", "index.html");
const ART_OVERRIDES = path.join(ROOT, "static", "assets", "art-overrides.css");
const FIXTURES = path.join(ROOT, "tests", "fixtures");

const CSS_ORDER = ["theme", "layout", "components", "features", "cards", "responsive"];

/** 9 个语义化交互变量（AR03-P4 §3.2）。 */
const SEMANTIC_VARS = [
  "--hover-veil",
  "--hover-veil-subtle",
  "--hover-veil-strong",
  "--active-veil",
  "--accent-veil",
  "--accent-veil-soft",
  "--accent-veil-strong",
  "--accent-veil-chip",
  "--danger-veil",
];

/** 语义变量的 dark 值 = 迁移前的原硬编码字面量（Dark 模式视觉不变）。 */
const EXPECTED_DARK = {
  "--hover-veil": "rgba(255,255,255,0.05)",
  "--hover-veil-subtle": "rgba(255,255,255,0.03)",
  "--hover-veil-strong": "rgba(255,255,255,0.1)",
  "--active-veil": "rgba(255,255,255,0.05)",
  "--accent-veil": "rgba(240,192,64,0.1)",
  "--accent-veil-soft": "rgba(240,192,64,0.08)",
  "--accent-veil-strong": "rgba(240,192,64,0.18)",
  "--accent-veil-chip": "rgba(240,192,64,0.15)",
  "--danger-veil": "rgba(231,76,60,0.1)",
};

/**
 * 美术 Token 的**允许定义点**例外。
 *
 * `--art-card-front-layer` 是 M1.5C 的**per-theme 路由变量**：cards.css 在
 * `.task-card.theme-*` 上把它重新指向各自的 `--art-card-<theme>-front` 槽位，
 * 并保留原始 sheen 渐变作为 fallback。这是**消费侧再映射**，不是美术资产
 * 的定义方 —— 真正的资产由 static/assets/art-overrides.css 提供。
 *
 * 例外仅限这一个变量，且必须出现在 `.task-card.theme-*` 选择器内。
 */
const ART_DEF_EXCEPTIONS = new Set(["--art-card-front-layer"]);

/** 运行时变量（由 JS / DOM 提供，CSS 不得定义）。 */
const RUNTIME_VARS = ["--card-scale", "--deck-i"];

/** 选择器唯一归属豁免名单（唯一例外，逐条附理由）。 */
const SELECTOR_EXEMPTIONS = {
  modal:
    ".modal 基础外观在 components.css；其 ::before 美术装饰层（--art-modal-frame " +
    "消费端）与 > * 的 z-index 提升在 cards.css。",
};

// ---------------------------------------------------------------------------
// 解析工具
// ---------------------------------------------------------------------------

function maskComments(css) {
  return css
    .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

/** 解析 CSS → 有序的顶层条目列表。 */
function parseEntries(css) {
  const masked = maskComments(css);
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
    skipWs();
    if (i >= masked.length) break;
    const braceAt = masked.indexOf("{", i);
    if (braceAt === -1) break;
    const prelude = masked.slice(i, braceAt).trim();
    const { inner, end } = readBlock(braceAt);
    out.push({ type: "at", selector: prelude, inner });
    i = end + 1;
  }
  return out;
}

/** 归一化选择器（去伪类/伪元素/空白），用于跨文件唯一性比对。 */
function normalizeSelector(sel) {
  return sel
    .split(",")
    .map((s) =>
      s
        .trim()
        .replace(/\s+/g, " ")
        .replace(
          /::?(hover|active|focus|focus-visible|focus-within|checked|disabled|selected|first-child|last-child|only-child|before|after|placeholder)\b/g,
          ""
        )
        .replace(/\s+/g, " ")
        .trim()
    )
    .filter(Boolean)
    .sort()
    .join(",");
}

/** 提取 CSS 中的变量定义（`--name: value;`）。 */
function extractVarDefinitions(css) {
  const defs = new Map();
  const masked = maskComments(css);
  const re = /(--[a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);/g;
  let m;
  while ((m = re.exec(masked)) !== null) {
    defs.set(m[1], m[2].trim());
  }
  return defs;
}

/**
 * 提取**指定选择器块内**的变量定义。
 * 必须按块提取：theme.css 里 `:root` 与 `:root[data-theme="light"]`
 * 定义同名变量，全文件扫描会让 light 值覆盖 dark 值，门禁就失去意义。
 */
function extractVarDefinitionsInBlock(css, selector) {
  const masked = maskComments(css);
  const idx = masked.indexOf(selector);
  if (idx === -1) return null;
  const braceAt = masked.indexOf("{", idx);
  if (braceAt === -1) return null;
  let depth = 0;
  let end = -1;
  for (let j = braceAt; j < masked.length; j++) {
    if (masked[j] === "{") depth++;
    else if (masked[j] === "}") {
      depth--;
      if (depth === 0) {
        end = j;
        break;
      }
    }
  }
  if (end === -1) return null;
  return extractVarDefinitions(masked.slice(braceAt + 1, end));
}

// ---------------------------------------------------------------------------
// 门禁实现
// ---------------------------------------------------------------------------

const violations = [];
function fail(gate, message) {
  violations.push({ gate, message });
}

function readCssFiles() {
  const files = {};
  for (const name of CSS_ORDER) {
    const p = path.join(CSS_DIR, `${name}.css`);
    files[name] = fs.existsSync(p) ? fs.readFileSync(p, "utf8") : null;
  }
  return files;
}

/** ① Token 所有权分层 */
function gate1(files) {
  const names = CSS_ORDER.filter((n) => files[n] !== null);

  for (const name of names) {
    const css = files[name];
    const masked = maskComments(css);

    // ①a :root 只允许在 theme.css
    if (name !== "theme") {
      const rootRe = /(^|[},;])\s*:root\b/g;
      let m;
      while ((m = rootRe.exec(masked)) !== null) {
        fail("①a", `${name}.css 定义了 :root —— 全局主题 Token 只能在 theme.css`);
      }
    }

    const defs = extractVarDefinitions(css);

    // ①b --card-* 只允许定义在 cards.css
    for (const varName of defs.keys()) {
      if (varName.startsWith("--card-") && name !== "cards") {
        fail("①b", `${name}.css 定义了 ${varName} —— 卡牌 Token 只能在 cards.css`);
      }
    }

    // ①c --art-* 不得在 CSS 中定义（只能消费），除非在显式例外名单中
    for (const varName of defs.keys()) {
      if (!varName.startsWith("--art-")) continue;
      if (ART_DEF_EXCEPTIONS.has(varName)) {
        // 例外：必须定义在 .task-card.theme-* 上（per-theme 路由）
        const themeScoped = new RegExp(
          `\\.task-card\\.theme-[a-z-]+\\s*\\{[^}]*${varName}\\s*:`,
          "s"
        ).test(masked);
        if (!themeScoped) {
          fail(
            "①c",
            `${name}.css 定义了 ${varName}，但不在 .task-card.theme-* 作用域内` +
              ` —— 例外仅允许 per-theme 路由`
          );
        }
        continue;
      }
      fail(
        "①c",
        `${name}.css **定义**了 ${varName} —— 美术 Token 的定义方只能是 static/assets/art-overrides.css`
      );
    }
    // --art-* 消费只允许在 cards.css / features.css
    if (name !== "cards" && name !== "features" && /var\(--art-/.test(masked)) {
      fail("①c", `${name}.css 消费了 --art-* —— 消费只允许在 cards.css / features.css`);
    }

    // ①d 运行时变量不得在 CSS 中定义
    for (const v of RUNTIME_VARS) {
      if (defs.has(v)) {
        fail("①d", `${name}.css 定义了运行时变量 ${v} —— 必须由 JS / DOM 提供`);
      }
    }
  }

  // art-overrides.css 应当定义全部 --art-*
  if (!fs.existsSync(ART_OVERRIDES)) {
    fail("①c", "缺少 static/assets/art-overrides.css —— 美术 Token 的定义方不存在");
  }
}

/** ② HTML 内联样式收敛 */
function gate2() {
  const html = fs.readFileSync(INDEX_HTML, "utf8");
  const noComments = html.replace(/<!--[\s\S]*?-->/g, "");
  const styleCount = (noComments.match(/<style[\s>]/g) || []).length;
  if (styleCount !== 0) {
    fail("②", `src/index.html 仍有 ${styleCount} 个内联 <style> 块（应为 0）`);
  }
}

/** ③ 选择器唯一归属 */
function gate3(files) {
  const owner = new Map();
  const names = CSS_ORDER.filter((n) => files[n] !== null);

  for (const name of names) {
    const entries = parseEntries(files[name]);
    for (const e of entries) {
      if (e.type !== "at") continue;
      for (const sel of e.selector.split(",").map((s) => s.trim())) {
        const norm = normalizeSelector(sel);
        if (!norm) continue;
        if (!owner.has(norm)) owner.set(norm, new Set());
        owner.get(norm).add(name);
      }
    }
  }

  for (const [norm, fileSet] of owner) {
    if (fileSet.size <= 1) continue;
    const filesList = [...fileSet];
    const base = norm.split(",").map((s) => s.trim());
    const isOnlyModal = base.length === 1 && base[0] === ".modal";
    if (isOnlyModal && filesList.length === 2) {
      const expected = ["cards", "components"];
      if (expected.every((x) => filesList.includes(x))) continue; // 显式豁免
    }
    fail(
      "③",
      `选择器 "${norm}" 在多个文件中重复定义: ${filesList.join(", ")} —— ` +
        `违反选择器唯一归属（豁免名单: ${Object.keys(SELECTOR_EXEMPTIONS).join(", ") || "无"}）`
    );
  }
}

/** ④ 加载顺序 */
function gate4() {
  const html = fs.readFileSync(INDEX_HTML, "utf8");
  const links = [...html.matchAll(/href="\/static\/css\/([a-z]+)\.css/g)].map((x) => x[1]);
  if (links.join(",") !== CSS_ORDER.join(",")) {
    fail(
      "④",
      `CSS <link> 顺序错误：实际 [${links.join(", ")}]，期望 [${CSS_ORDER.join(", ")}]`
    );
  }

  const themeScriptAt = html.indexOf("sal.theme");
  const firstCssAt = html.indexOf("/static/css/theme.css");
  if (themeScriptAt < 0) {
    fail("④", "src/index.html 找不到主题早期同步脚本（sal.theme）");
  } else if (firstCssAt < 0) {
    fail("④", "src/index.html 找不到 CSS <link>");
  } else if (themeScriptAt > firstCssAt) {
    fail("④", "主题早期同步脚本必须位于所有 CSS 之前（否则会闪烁）");
  }
}

/** ⑤ 语义变量双向定义 + dark 值 == 迁移前字面量 */
function gate5(files) {
  const theme = files.theme;
  if (theme === null) {
    fail("⑤", "缺少 static/css/theme.css");
    return;
  }

  // 按块提取：:root（dark）与 :root[data-theme="light"]（light）
  const darkDefs = extractVarDefinitionsInBlock(theme, ":root {");
  if (!darkDefs) {
    fail("⑤", "theme.css 缺少 :root 块");
    return;
  }
  const lightDefs = extractVarDefinitionsInBlock(theme, ':root[data-theme="light"]');
  if (!lightDefs) {
    fail("⑤", 'theme.css 缺少 :root[data-theme="light"] 块');
    return;
  }

  for (const v of SEMANTIC_VARS) {
    if (!darkDefs.has(v)) {
      fail("⑤", `theme.css 的 :root 缺少语义变量 ${v} 的定义`);
    } else if (darkDefs.get(v) !== EXPECTED_DARK[v]) {
      fail(
        "⑤",
        `${v} 的 dark 值应为 ${EXPECTED_DARK[v]}（= 迁移前原字面量，保证 Dark 视觉不变），实际 ${darkDefs.get(v)}`
      );
    }
  }

  for (const v of SEMANTIC_VARS) {
    if (!lightDefs.has(v)) {
      fail("⑤", `theme.css 的 light 主题缺少语义变量 ${v}`);
    } else if (lightDefs.get(v) === EXPECTED_DARK[v]) {
      fail("⑤", `${v} 的 light 值与 dark 值相同 —— Light Mode 修复未生效`);
    }
  }
}

/**
 * 构建"覆盖对"集合：形如 `${a}|${b}|${prop}`。
 * 含义：选择器 a 与 b **同特异度**且 a 在 b 之前，b 声明了 a 也声明的
 * 属性 prop → 迁移前 b 胜出（覆盖 a）。
 *
 * 只考虑**单类名**选择器之间的比较（不同特异度层级不参与源序竞争）。
 */
function buildDeclarationPairs(css) {
  const entries = parseEntries(css);
  const pairs = [];
  const seen = new Set();

  const simple = [];
  entries.forEach((e) => {
    const sels = e.selector.split(",").map((x) => x.trim());
    if (sels.length !== 1) return;
    const s = sels[0];
    if (!/^\.[a-zA-Z][\w-]*$/.test(s)) return;
    simple.push({ sel: s, props: declPropsOf(e.inner) });
  });

  for (let i = 0; i < simple.length; i++) {
    for (let j = i + 1; j < simple.length; j++) {
      const a = simple[i];
      const b = simple[j];
      for (const prop of b.props) {
        if (!a.props.has(prop)) continue;
        const key = `${a.sel}|${b.sel}|${prop}`;
        if (seen.has(key)) continue;
        seen.add(key);
        pairs.push({ a: a.sel, b: b.sel, prop });
      }
    }
  }
  return pairs;
}

/** 提取声明块中的属性名集合（不含自定义属性）。 */
function declPropsOf(inner) {
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
    if (prop && !prop.startsWith("--")) props.add(prop);
  };
  for (const ch of inner) {
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    if (ch === ";" && depth === 0) flush();
    else buf += ch;
  }
  flush();
  return props;
}

/** 当前 6 文件拼接后的单类名选择器顺序（用于相对位置比较）。 */
const currentOrder = [];

/**
 * ⑥ 源序等价性（对比迁移前基线）
 *
 * 关键点：**六文件重组必然改变"全局位置"**（工具类从原位置移到 layout.css，
 * 排在组件类之前）。因此不能简单地比较"选择器在序列中的索引"。
 *
 * 真正要保证的是：**对同时命中同一元素的规则，胜者不变**。
 *
 * 判定分两层：
 *   1. **共现层**（决定性）：只有当两个类**出现在同一个元素上**时，
 *      它们的相对顺序才有意义。`scripts/check_layout_utility_conflicts.js`
 *      扫描 HTML / JS 的全部 class 属性，得出"工具类 × 组件类"共现且
 *      **属性有交集**的对 —— 那些才是需要保护的对。
 *   2. **覆盖层**：对第 1 层筛出的共现对，检查当前 CSS 中"后者的属性
 *      是否仍然胜出"（同特异度时靠后；不同特异度时靠特异度）。
 *
 * 本门禁 ⑥ 复用第 1 层的结论 + 第 2 层的顺序/特异度核验。
 * 判据：共现对 (util, comp, prop) 在迁移前由 comp 胜出（comp 在后），
 * 迁移后必须仍然由 comp 胜出 —— 要么顺序未翻转，要么 comp 的特异度
 * 已提升到足以压过 util。
 */
function gate6(files) {
  const baselinePath = path.join(FIXTURES, "css_cascade_baseline.json");
  if (!fs.existsSync(baselinePath)) {
    fail("⑥", "缺少 tests/fixtures/css_cascade_baseline.json —— 无法做源序等价性校验");
    return;
  }
  const baseline = JSON.parse(fs.readFileSync(baselinePath, "utf8"));

  // --- 基线的覆盖对（用于判定"迁移前谁胜"） ---
  //
  // ⚠️ 基线里 a / b 存的是**带前导点的完整选择器**（如 ".mt16"），而下面
  // 的共现对里 utility / component 是**裸类名**（如 "mt16"）。查表时必须
  // 补上 "."，否则永远查不到 → beforeComponentWins 恒为 false → 任何
  // "组件本来就该胜出"的组合都会被误报成"胜者改变"。
  const basePairs = baseline.declarationPairs || [];
  const baseMap = new Map();
  for (const p of basePairs) {
    baseMap.set(`${p.a}|${p.b}|${p.prop}`, p);
  }

  /** 基线里是否存在 (utility 在前, component 在后) 的覆盖对 → 需要结合 !important 判断。 */
  const baselinePair = (utility, component, property) =>
    baseMap.get(`.${utility}|.${component}|${property}`) || null;

  /**
   * 迁移前谁胜出？
   *
   * 层叠规则（与 CSS 规范一致）：
   *   1. 任一方带 !important → 带的那方恒定胜出。
   *   2. 否则同特异度下源序靠后者胜。
   *
   * ⚠️ 只看源序会误判：`.hidden { display: none !important }` 源序在前，
   *    但 !important 让它恒定胜出 `.modal-overlay { display: flex }`。
   */
  const baselineWinnerIsComponent = (utility, component, property) => {
    const fwd = baselinePair(utility, component, property); // utility 在前
    if (fwd) {
      if (fwd.aImportant !== fwd.bImportant) return fwd.bImportant;
      return true; // 同为非 important → 源序靠后的 component 胜
    }
    const rev = baselinePair(component, utility, property); // component 在前
    if (rev) {
      if (rev.aImportant !== rev.bImportant) return rev.aImportant;
      return false; // 源序靠后的 utility 胜
    }
    return false; // 基线里没有这对 → 视为 utility 胜（保守）
  };

  // --- 当前：每个类 × 每个属性的"最强声明" ---
  //
  // 门禁要回答的是："迁移后，这个属性上 utility 和 component 谁胜出？"
  // 因此必须**逐属性**记录，而不是给整个类一个笼统的特异度。
  //
  // 支持两种写法：
  //   1. 裸单类选择器 `.cls`          → 特异度 [0,1,0]
  //   2. `:where(.cls)` 特异度归零写法 → 特异度 [0,0,0]
  //      （用于"基座 + 覆盖"双规则模式：`:where(.cls)` 管外观、`.cls` 管覆盖，
  //        两条规则按 CSS 规范是**并列**参与层叠，各自声明不同属性）
  //
  // 对同一个 (类, 属性)，保留**胜出者**：
  //   - 有 !important 的优先
  //   - 否则特异度高者胜
  //   - 同特异度 → 源序靠后者胜
  const combined = CSS_ORDER.map((n) => files[n] || "").join("\n");
  /** className → prop → { idx, specificity, important } */
  const curInfo = new Map();
  let idx = 0;
  const betterThan = (a, b) => {
    if (!b) return true;
    if (a.important !== b.important) return a.important;
    const as = a.specificity;
    const bs = b.specificity;
    for (let i = 0; i < 3; i++) {
      if (as[i] !== bs[i]) return as[i] > bs[i];
    }
    return a.idx > b.idx;
  };

  for (const e of parseEntries(combined)) {
    const sels = e.selector.split(",").map((x) => x.trim());
    if (sels.length !== 1) continue;
    const s = sels[0];

    const whereMatch = s.match(/^:where\(\.([a-zA-Z][\w-]*)\)$/);
    let cls = null;
    let spec = null;
    if (whereMatch) {
      cls = whereMatch[1];
      spec = [0, 0, 0];
    } else if (/^\.[a-zA-Z][\w-]*$/.test(s)) {
      cls = s.slice(1);
      spec = specificityOf(s);
    } else {
      continue;
    }

    const importantProps = importantPropsOf(e.inner);
    const props = declPropsOf(e.inner);
    if (!curInfo.has(cls)) curInfo.set(cls, new Map());
    const byProp = curInfo.get(cls);

    for (const p of props) {
      const cand = {
        idx: idx++,
        specificity: spec,
        important: importantProps.has(p),
      };
      if (betterThan(cand, byProp.get(p))) byProp.set(p, cand);
    }
  }

  // --- 共现对（来自 check_layout_utility_conflicts 的同一套数据） ---
  const cooccurring = findCooccurringUtilityComponentPairs();

  for (const co of cooccurring) {
    const { utility, component, property } = co;

    // 迁移前谁胜出？
    const beforeComponentWins = baselineWinnerIsComponent(utility, component, property);

    const uByProp = curInfo.get(utility);
    const cByProp = curInfo.get(component);
    const uInfo = uByProp && uByProp.get(property);
    const cInfo = cByProp && cByProp.get(property);
    if (!uInfo || !cInfo) {
      fail(
        "⑥",
        `共现对 "${utility}" + "${component}" (${property}) 的选择器在迁移后缺失`
      );
      continue;
    }

    // 迁移后谁胜出？同一套规则：!important > 特异度 > 源序。
    const afterComponentWins = betterThan(cInfo, uInfo);

    if (beforeComponentWins !== afterComponentWins) {
      fail(
        "⑥",
        `共现对 "${utility}" + "${component}" (${property}) 的胜者改变：` +
          `迁移前 ${beforeComponentWins ? component : utility} 胜，` +
          `迁移后 ${afterComponentWins ? component : utility} 胜 → 视觉会变`
      );
    }
  }
}

/** 提取声明块中带 !important 的属性名集合。 */
function importantPropsOf(inner) {
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
    const value = s.slice(idx + 1).trim();
    if (prop && !prop.startsWith("--") && /!important/i.test(value)) props.add(prop);
  };
  for (const ch of inner) {
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    if (ch === ";" && depth === 0) flush();
    else buf += ch;
  }
  flush();
  return props;
}

/** 计算选择器的特异度 [id, class, type]。 */
function specificityOf(sel) {
  const ids = (sel.match(/#[\w-]+/g) || []).length;
  const classes = (sel.match(/\.[\w-]+/g) || []).length;
  const attrs = (sel.match(/\[[^\]]+\]/g) || []).length;
  const pseudoClasses = (sel.match(/:(?!:)[\w-]+/g) || []).length;
  const types = (sel.match(/(^|[\s>+~])[a-zA-Z][\w-]*/g) || []).length;
  return [ids, classes + attrs + pseudoClasses, types];
}

/**
 * 找出"工具类 × 组件类"的**共现对**（同一元素上同时出现）且**属性有交集**。
 * 与 scripts/check_layout_utility_conflicts.js 使用同一套判定逻辑。
 */
function findCooccurringUtilityComponentPairs() {
  const UTILITIES = new Set([
    "grid", "g2", "g3", "g4", "flex", "fc", "gap8", "gap16",
    "jc", "ac", "sb", "wrap", "grow",
    "mt8", "mt16", "mt24", "mb8", "mb16", "hidden",
  ]);

  // 从 CSS 反查每个类声明的属性
  const propIndex = new Map();
  for (const name of CSS_ORDER) {
    const p = path.join(CSS_DIR, `${name}.css`);
    if (!fs.existsSync(p)) continue;
    for (const e of parseEntries(fs.readFileSync(p, "utf8"))) {
      const sels = e.selector.split(",").map((x) => x.trim());
      if (sels.length !== 1) continue;
      const s = sels[0];
      if (!/^\.[a-zA-Z][\w-]*$/.test(s)) continue;
      const cls = s.slice(1);
      if (!propIndex.has(cls)) propIndex.set(cls, new Set());
      for (const prop of declPropsOf(e.inner)) propIndex.get(cls).add(prop);
    }
  }

  // 扫描 HTML / JS 的 class 属性
  const sources = [
    "src/index.html",
    "static/app.js",
    "static/core/ui.js",
    "static/core/ui/toast.js",
    "static/core/ui/modal.js",
    "static/modules/free-task.js",
    "static/modules/tasks/index.js",
  ];
  const seen = new Set();
  const pairs = [];
  for (const rel of sources) {
    const p = path.join(ROOT, rel);
    if (!fs.existsSync(p)) continue;
    const text = fs.readFileSync(p, "utf8");
    const patterns = [
      /class\s*=\s*"([^"]*)"/g,
      /class\s*=\s*'([^']*)'/g,
      /class\s*=\s*`([^`]*)`/g,
      /className\s*=\s*["']([^"']+)["']/g,
    ];
    for (const re of patterns) {
      let m;
      while ((m = re.exec(text)) !== null) {
        const cls = m[1].split(/\s+/).filter(Boolean);
        const utils = cls.filter((c) => UTILITIES.has(c));
        if (!utils.length) continue;
        for (const u of utils) {
          for (const c of cls) {
            if (c === u || UTILITIES.has(c)) continue;
            const up = propIndex.get(u);
            const cp = propIndex.get(c);
            if (!up || !cp) continue;
            for (const prop of up) {
              if (!cp.has(prop)) continue;
              const key = `${u}|${c}|${prop}`;
              if (seen.has(key)) continue;
              seen.add(key);
              pairs.push({ utility: u, component: c, property: prop });
            }
          }
        }
      }
    }
  }
  return pairs;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

function main() {
  const asJson = process.argv.includes("--json");
  const files = readCssFiles();

  for (const name of CSS_ORDER) {
    if (files[name] === null) fail("①", `缺少 static/css/${name}.css`);
  }

  gate1(files);
  gate2();
  gate3(files);
  gate4();
  gate5(files);
  gate6(files);

  const result = { ok: violations.length === 0, violations, checkedFiles: CSS_ORDER };

  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    const count = (g) => violations.filter((v) => v.gate === g).length;
    console.log("=== CSS 架构门禁 ===");
    console.log(`门禁 ① Token 所有权分层  : ${count("①a") + count("①b") + count("①c") + count("①d")} 违规`);
    console.log(`门禁 ② HTML 内联样式收敛 : ${count("②")} 违规`);
    console.log(`门禁 ③ 选择器唯一归属    : ${count("③")} 违规`);
    console.log(`门禁 ④ 加载顺序          : ${count("④")} 违规`);
    console.log(`门禁 ⑤ 语义变量双向定义  : ${count("⑤")} 违规`);
    console.log(`门禁 ⑥ 源序等价性        : ${count("⑥")} 违规`);
    console.log("");
    if (violations.length === 0) {
      console.log("PASS —— 全部门禁通过");
    } else {
      console.log(`FAIL —— ${violations.length} 项违规:`);
      for (const v of violations) console.log(`  [${v.gate}] ${v.message}`);
    }
  }

  process.exit(violations.length === 0 ? 0 : 1);
}

main();
