"use strict";
/**
 * AR03-P4 / B10 —— CSS 迁移**前**基线快照生成器。
 *
 * 目的：在改动 `src/index.html` / 新建 `static/css/**` **之前**，把当前内联
 * CSS 的可机器比对基线落盘，供阶段 C（源序等价性门禁）与阶段 C2（计算样式
 * 对比）使用。
 *
 * 产出（**只写新增**文件，不修改任何既有文件）：
 *   tests/fixtures/card_theme_baseline.json   —— 卡牌 8 变体的 --card-* 变量
 *   tests/fixtures/css_cascade_baseline.json —— 主样式块的有序规则序列
 *   tests/fixtures/css_visual_baseline.json  —— 关键选择器的原始声明 + 颜色字面量
 *
 * 用法：
 *   node scripts/capture_css_baselines.js            # 生成三份基线
 *   node scripts/capture_css_baselines.js --check    # 只校验，不写文件
 *
 * 该脚本**只读** `src/index.html`，不触碰生产数据与 Protected Paths。
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
/**
 * 基线来源文件。默认是当前的 src/index.html（迁移前运行时它含 3 个内联
 * <style> 块）；迁移完成后需要用
 *   node scripts/rebuild_premigration_index.js
 *   node scripts/capture_css_baselines.js --source .tmp_premigration_index.html
 * 从保存的迁移前块重建基线。
 */
const SOURCE_FILE =
  (() => {
    const i = process.argv.indexOf("--source");
    if (i !== -1 && process.argv[i + 1]) return process.argv[i + 1];
    return path.join("src", "index.html");
  })();
const INDEX_HTML = path.join(ROOT, SOURCE_FILE);
const FIXTURES = path.join(ROOT, "tests", "fixtures");

// ---------------------------------------------------------------------------
// 1. 提取内联样式块
// ---------------------------------------------------------------------------

/** 读取 index.html 中所有 <style> 块的 CSS 文本（按出现顺序）。 */
function readInlineStyleBlocks(html) {
  const blocks = [];
  const re = /<style([^>]*)>([\s\S]*?)<\/style>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    blocks.push({ attrs: m[1].trim(), css: m[2] });
  }
  return blocks;
}

/**
 * 主样式块 = 第一个包含 `:root {` 的块（字体块是第 0 个 <style>，
 * 主样式块紧随其后）。按内容判定，避免依赖顺序假设。
 */
function pickMainBlock(blocks) {
  return blocks.find((b) => /:root\s*\{/.test(b.css)) || blocks[0] || { css: "" };
}

// ---------------------------------------------------------------------------
// 2. 极简 CSS 解析（够用即可：规则序列 + 声明解析）
// ---------------------------------------------------------------------------

/** 去掉注释。 */
function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/**
 * 把 CSS 文本切成**有序**的顶层规则列表。
 * at-rule（@media / @keyframes）作为独立条目，带上其内部规则。
 *
 * 返回：[{ kind: 'rule'|'at', selector, decls, children?, atName?, params? }]
 */
function parseTopLevel(css) {
  const src = stripComments(css);
  const out = [];
  let i = 0;

  function skipWs() {
    while (i < src.length && /\s/.test(src[i])) i++;
  }

  /** 读取到匹配的 } 为止，返回内部文本。 */
  function readBlock(start) {
    let depth = 0;
    let j = start;
    for (; j < src.length; j++) {
      if (src[j] === "{") depth++;
      else if (src[j] === "}") {
        depth--;
        if (depth === 0) return { inner: src.slice(start + 1, j), end: j };
      }
    }
    return { inner: src.slice(start + 1), end: src.length };
  }

  while (i < src.length) {
    skipWs();
    if (i >= src.length) break;

    const braceAt = src.indexOf("{", i);
    if (braceAt === -1) break;
    const prelude = src.slice(i, braceAt).trim();

    // at-rule（@media / @keyframes / @supports ...）
    if (prelude.startsWith("@")) {
      const { inner, end } = readBlock(braceAt);
      const sp = prelude.indexOf(" ");
      const atName = sp === -1 ? prelude : prelude.slice(0, sp);
      const params = sp === -1 ? "" : prelude.slice(sp + 1).trim();
      out.push({
        kind: "at",
        atName,
        params,
        selector: prelude,
        children: parseTopLevel(inner),
      });
      i = end + 1;
      continue;
    }

    // 普通规则
    const { inner, end } = readBlock(braceAt);
    out.push({
      kind: "rule",
      selector: prelude,
      decls: parseDecls(inner),
    });
    i = end + 1;
  }
  return out;
}

/** 解析声明块 → [{ prop, value, important }]。 */
function parseDecls(text) {
  const decls = [];
  let depth = 0;
  let buf = "";
  const push = () => {
    const s = buf.trim();
    buf = "";
    if (!s) return;
    const idx = s.indexOf(":");
    if (idx === -1) return;
    const prop = s.slice(0, idx).trim();
    let value = s.slice(idx + 1).trim();
    if (!prop) return;
    // 剥离 !important，并单独标记（层叠胜负要看它）
    let important = false;
    if (/!important\s*$/i.test(value)) {
      important = true;
      value = value.replace(/!important\s*$/i, "").trim();
    }
    decls.push({ prop, value, important });
  };
  for (const ch of text) {
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    if (ch === ";" && depth === 0) {
      push();
    } else {
      buf += ch;
    }
  }
  push();
  return decls;
}

// ---------------------------------------------------------------------------
// 3. 基线 1：卡牌主题配色
// ---------------------------------------------------------------------------

/** 从 CSS 文本里抽取 `.task-card` 与 `.task-card.theme-*` 的 --card-* 变量声明。 */
function extractCardThemeVars(css) {
  const rules = parseTopLevel(stripComments(css));
  const result = {};

  function collectVarDecls(text) {
    const out = {};
    const re = /(--card-[a-z-]+)\s*:\s*([^;]+);/g;
    let m;
    while ((m = re.exec(text)) !== null) out[m[1]] = m[2].trim();
    return out;
  }

  function walk(list) {
    for (const r of list) {
      if (r.kind === "at") {
        walk(r.children || []);
        continue;
      }
      const sels = r.selector.split(",").map((s) => s.trim());
      for (const s of sels) {
        // 形如 ".task-card" / ".task-card.theme-math"
        const m = s.match(/^\.task-card(?:\.(theme-[\w-]+))?$/);
        if (!m) continue;
        const key = m[1] || "base";
        const vars = collectVarDecls(
          r.decls.map((d) => `${d.prop}:${d.value};`).join("")
        );
        result[key] = Object.assign(result[key] || {}, vars);
      }
    }
  }
  walk(rules);
  return result;
}

// ---------------------------------------------------------------------------
// 4. 基线 2：源序规则序列 + 关键选择器声明
// ---------------------------------------------------------------------------

/** 把规则树拍平成有序的"签名"列表。 */
function flattenRuleOrder(rules) {
  const out = [];
  for (const r of rules) {
    if (r.kind === "at") {
      const kids = flattenRuleOrder(r.children || []);
      out.push({
        kind: "at",
        signature: r.selector.replace(/\s+/g, " "),
        childCount: kids.length,
      });
      out.push(...kids);
    } else {
      const sels = r.selector.split(",").map((s) => s.trim());
      for (const s of sels) {
        out.push({
          kind: "rule",
          signature: s.replace(/\s+/g, " "),
          declCount: r.decls.length,
        });
      }
    }
  }
  return out;
}

/** 关键选择器集合（用于值层面的 Dark 模式比对）。 */
const IMPORTANT_SELECTORS = new Set([
  "body", "header", "nav", "main", ".nav-btn", ".nav-btn:hover", ".nav-btn.active",
  ".btn", ".btn:hover", ".btn.pri", ".btn.danger", ".btn.sm", ".btn.ic",
  ".card", ".card:hover", ".card-title", ".card-meta",
  "input", "select", "textarea", "select option",
  ".badge", ".bg-gold", ".bg-blue", ".bg-green", ".bg-red", ".bg-purple",
  ".empty-state", ".section-title",
  ".toast", ".toast.suc", ".toast.err", ".toast.inf",
  ".modal-overlay", ".modal",
  ".sched-slot", ".sched-slot:hover", ".cat-item", ".cat-item:hover", ".cat-item.active",
  ".note-item", ".note-item:hover",
  ".prompt-file-item", ".prompt-file-item:hover", ".prompt-file-item.active",
  ".agent-ro-item", ".agent-ro-item:hover", ".agent-ro-item.active",
  ".agent-ro-tab", ".agent-ro-tab.active",
  ".tag-chip", ".replace-reason", ".feedback-emoji", ".feedback-option",
  ".gacha-main-btn", ".gacha-main-btn:hover", ".gacha-multi-item", ".gacha-multi-item:hover",
  ".gacha-multi-item.activated", ".gacha-multi-btn", ".gacha-multi-btn:hover",
  ".gacha-multi-item-tag", ".diff-line-add", ".diff-line-rem",
]);

/** 关键选择器的原始声明（值层面）—— 用于 Dark 模式逐字段比对。 */
function collectKeyDeclarations(css) {
  const rules = parseTopLevel(stripComments(css));
  const out = {};

  function walk(list) {
    for (const r of list) {
      if (r.kind === "at") {
        walk(r.children || []);
        continue;
      }
      for (const s of r.selector.split(",").map((x) => x.trim())) {
        if (!IMPORTANT_SELECTORS.has(s)) continue;
        const decls = {};
        for (const d of r.decls) decls[d.prop] = d.value;
        out[s] = Object.assign(out[s] || {}, decls);
      }
    }
  }
  walk(rules);
  return out;
}

/**
 * 构建"覆盖对"集合：形如 `${a}|${b}|${prop}`。
 * 含义：选择器 a 与 b **同特异度**且 a 在 b 之前，b 声明了 a 也声明的
 * 属性 prop → 迁移前 b 胜出（覆盖 a）。
 *
 * 只考虑**单类名**选择器之间的比较（不同特异度层级不参与源序竞争）。
 */
function buildDeclarationPairs(css) {
  const rules = parseTopLevel(stripComments(css));
  const simple = [];
  for (const r of rules) {
    if (r.kind === "at") continue;
    const sels = r.selector.split(",").map((x) => x.trim());
    if (sels.length !== 1) continue;
    const s = sels[0];
    if (!/^\.[a-zA-Z][\w-]*$/.test(s)) continue;
    simple.push({
      sel: s,
      props: declPropsOf(r.decls),
      important: importantPropsOf(r.decls),
    });
  }

  const pairs = [];
  const seen = new Set();
  for (let i = 0; i < simple.length; i++) {
    for (let j = i + 1; j < simple.length; j++) {
      const a = simple[i];
      const b = simple[j];
      for (const prop of b.props) {
        if (!a.props.has(prop)) continue;
        const key = `${a.sel}|${b.sel}|${prop}`;
        if (seen.has(key)) continue;
        seen.add(key);
        // ⚠️ 必须带上 !important 标记，否则消费方无法判断"迁移前谁真的胜出"：
        //    例如 `.hidden { display: none !important }` 与
        //    `.modal-overlay { display: flex }` 源序上后者在后，
        //    但 !important 让**前者**恒定胜出。只看源序会误判成"胜者改变"。
        pairs.push({
          a: a.sel,
          b: b.sel,
          prop,
          aImportant: a.important.has(prop),
          bImportant: b.important.has(prop),
        });
      }
    }
  }
  return pairs;
}

/** 从声明列表提取带 !important 的属性名集合。 */
function importantPropsOf(decls) {
  const props = new Set();
  for (const d of decls) {
    if (!d.prop || d.prop.startsWith("--")) continue;
    if (d.important) props.add(d.prop);
  }
  return props;
}

/** 从声明列表提取属性名集合（不含自定义属性）。 */
function declPropsOf(decls) {
  const props = new Set();
  for (const d of decls) {
    if (!d.prop || d.prop.startsWith("--")) continue;
    props.add(d.prop);
  }
  return props;
}

/**
 * 提取 `:root` 块中的**全局主题变量**取值（dark）。
 * 视觉回归用它在浏览器侧把 `var(--x)` 还原成实际值。
 */
function extractRootTokens(css) {
  const tokens = {};
  const rules = parseTopLevel(stripComments(css));
  for (const r of rules) {
    if (r.kind !== "rule") continue;
    const sels = r.selector.split(",").map((s) => s.trim());
    if (!sels.includes(":root")) continue;
    for (const d of r.decls) {
      if (!d.prop.startsWith("--")) continue;
      tokens[d.prop] = d.value;
    }
  }
  return tokens;
}

/**
 * 提取 `:root[data-theme="light"]` 块中的**全局主题变量**取值（light）。
 * 浅色主题会重映射 --bg-* / --text-* / --border 等全局 Token，
 * 因此视觉回归在 light 模式下必须用 light 取值表来解析 var()。
 */
function extractLightTokens(css) {
  const tokens = {};
  const rules = parseTopLevel(stripComments(css));
  for (const r of rules) {
    if (r.kind !== "rule") continue;
    const sels = r.selector.split(",").map((s) => s.trim());
    if (!sels.includes(':root[data-theme="light"]')) continue;
    for (const d of r.decls) {
      if (!d.prop.startsWith("--")) continue;
      tokens[d.prop] = d.value;
    }
  }
  return tokens;
}

// ---------------------------------------------------------------------------
// 5. 颜色字面量（非卡牌审计用）
// ---------------------------------------------------------------------------

/** 抽取所有颜色字面量 → [{ selector, prop, value, at }]。 */
function extractColorLiterals(css) {
  const rules = parseTopLevel(stripComments(css));
  const out = [];
  const COLOR_RE = /#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|\bhsla?\([^)]*\)/g;

  function walk(list, atCtx) {
    for (const r of list) {
      if (r.kind === "at") {
        walk(r.children || [], r.selector.replace(/\s+/g, " "));
        continue;
      }
      for (const s of r.selector.split(",").map((x) => x.trim())) {
        for (const d of r.decls) {
          COLOR_RE.lastIndex = 0;
          if (COLOR_RE.test(d.value)) {
            out.push({
              selector: s,
              prop: d.prop,
              value: d.value,
              at: atCtx || null,
            });
          }
        }
      }
    }
  }
  walk(rules, null);
  return out;
}

// ---------------------------------------------------------------------------
// 6. main
// ---------------------------------------------------------------------------

function main() {
  const checkOnly = process.argv.includes("--check");
  const html = fs.readFileSync(INDEX_HTML, "utf8");
  const blocks = readInlineStyleBlocks(html);
  const mainBlock = pickMainBlock(blocks);

  if (!mainBlock.css) {
    console.error("FAIL: 未能在 src/index.html 中找到主样式块");
    process.exit(1);
  }

  // freeTaskStyle 块（id="freeTaskStyle"）—— 与主样式块合并为比对主体
  const freeTaskBlocks = blocks.filter(
    (b) => b !== mainBlock && /freeTask|free-task/i.test(b.css)
  );
  const combined = mainBlock.css + "\n" + freeTaskBlocks.map((b) => b.css).join("\n");

  const cardTheme = extractCardThemeVars(mainBlock.css);
  const now = new Date().toISOString();

  const cascade = {
    generatedAt: now,
    source: "src/index.html <style> blocks (pre-migration)",
    inlineBlockCount: blocks.length,
    order: flattenRuleOrder(parseTopLevel(stripComments(combined))),
    keyDeclarations: collectKeyDeclarations(combined),
    // 覆盖对：a 在前、b 在后、b 声明了 a 也声明的 prop（同特异度 → b 胜）。
    // 迁移后门禁 ⑥ 用它验证"相对顺序未被翻转"或"特异度已提升"。
    declarationPairs: buildDeclarationPairs(combined),
    // 迁移前的**主题变量取值表**（dark）。视觉回归用它在浏览器侧把
    // `var(--x)` 还原成实际颜色 / 长度，再与迁移后的计算样式比对。
    darkTokenValues: extractRootTokens(stripComments(combined)),
    // 迁移前的**完整内联 CSS 文本**（3 个 <style> 块按原顺序拼接）。
    // E2E 视觉回归用它做 A/B 对比：同一页面、同一 DOM、同一状态下，
    // 先采样迁移后的 6 文件计算样式，再换成这份 CSS 采样一次，逐属性比对。
    preMigrationCss: blocks.map((b) => b.css).join("\n"),
  };

  // 视觉基线：附带 dark 变量取值，便于在浏览器里解析 var()
  const visual = {
    generatedAt: now,
    source: "src/index.html <style> blocks (pre-migration)",
    note:
      "关键选择器的原始声明值。Dark 主题迁移后必须逐字一致；" +
      "Light 主题的差异必须完全落在预期白名单内。",
    declarations: collectKeyDeclarations(combined),
    colorLiterals: extractColorLiterals(combined),
    darkTokenValues: extractRootTokens(stripComments(combined)),
    lightTokenValues: extractLightTokens(stripComments(combined)),
  };

  const payloads = {
    "card_theme_baseline.json": {
      generatedAt: now,
      source: "src/index.html <style> main block (pre-migration)",
      note:
        "卡牌 8 变体 + base 的 --card-* 变量；迁移后必须逐字一致" +
        "（卡牌深色设计语言保护）。",
      cardThemeVars: cardTheme,
    },
    "css_cascade_baseline.json": cascade,
    "css_visual_baseline.json": visual,
  };

  fs.mkdirSync(FIXTURES, { recursive: true });

  if (checkOnly) {
    let ok = true;
    for (const [name, payload] of Object.entries(payloads)) {
      const p = path.join(FIXTURES, name);
      if (!fs.existsSync(p)) {
        console.error(`MISSING: tests/fixtures/${name}`);
        ok = false;
        continue;
      }
      const prev = JSON.parse(fs.readFileSync(p, "utf8"));
      if (name === "card_theme_baseline.json") {
        const a = JSON.stringify(prev.cardThemeVars);
        const b = JSON.stringify(payload.cardThemeVars);
        if (a !== b) {
          console.error(`CHANGED: ${name} — 卡牌变量与基线不一致`);
          ok = false;
        } else {
          console.log(`OK: ${name} — 卡牌变量一致`);
        }
      } else {
        console.log(`OK: ${name} — 存在`);
      }
    }
    process.exit(ok ? 0 : 1);
  }

  for (const [name, payload] of Object.entries(payloads)) {
    const p = path.join(FIXTURES, name);
    fs.writeFileSync(p, JSON.stringify(payload, null, 2) + "\n", "utf8");
    console.log(`WROTE: tests/fixtures/${name}`);
  }

  console.log("");
  console.log(`内联 style 块数: ${blocks.length}`);
  console.log(`卡牌主题变体数: ${Object.keys(cardTheme).length} -> ${Object.keys(cardTheme).join(", ")}`);
  console.log(`源序规则条目数: ${cascade.order.length}`);
  console.log(`关键选择器数: ${Object.keys(visual.declarations).length}`);
  console.log(`颜色字面量条目数: ${visual.colorLiterals.length}`);
}

main();
