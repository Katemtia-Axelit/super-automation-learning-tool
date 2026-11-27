"use strict";
/**
 * AR03-P4 / B7 —— 改写 `src/index.html` 的 head：把 3 个内联 <style> 块
 * 替换为 6 个 <link rel="stylesheet">。
 *
 * 硬约束（AR03-P4 Plan §4.2-B7）：
 *   1. 主题早期同步脚本（无 FOUC）必须保持在**所有** CSS 之前 → 它已经在
 *      head 的最前面，本脚本不移动它，只在其后插入 <link>。
 *   2. `<link>` 顺序固定为 theme → layout → components → features → cards
 *      → responsive（cascade 顺序即门禁 ④）。
 *   3. 保留全部 DOM / class / id / inline handler 与 66 处 style="" 属性
 *      → 本脚本**只动 head 中的 <style> 块**，body 一字不改。
 *
 * 用法：node scripts/rewrite_index_head.js [--check]
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const INDEX_HTML = path.join(ROOT, "src", "index.html");

const CSS_ORDER = ["theme", "layout", "components", "features", "cards", "responsive"];

const CSS_LINKS = `<!-- AR03-P4: 样式已从内联 <style> 迁移到 static/css/（扁平分层 6 文件）。
     加载顺序 = cascade 顺序，由 scripts/check_css_architecture.js 门禁 ④ 锁定：
     theme（全局主题 Token 唯一权威）→ layout（骨架）→ components（通用组件）
     → features（业务模块）→ cards（卡牌系统）→ responsive（媒体查询 + 偏好覆盖）。 -->
<link rel="stylesheet" href="/static/css/theme.css?v=1">
<link rel="stylesheet" href="/static/css/layout.css?v=1">
<link rel="stylesheet" href="/static/css/components.css?v=1">
<link rel="stylesheet" href="/static/css/features.css?v=1">
<link rel="stylesheet" href="/static/css/cards.css?v=1">
<link rel="stylesheet" href="/static/css/responsive.css?v=1">`;

function main() {
  const checkOnly = process.argv.includes("--check");
  const html = fs.readFileSync(INDEX_HTML, "utf8");

  // 找出全部 <style> 块
  const styleRe = /<style([^>]*)>([\s\S]*?)<\/style>/g;
  const blocks = [];
  let m;
  while ((m = styleRe.exec(html)) !== null) {
    blocks.push({ attrs: m[1].trim(), css: m[2], start: m.index, end: m.index + m[0].length });
  }

  if (checkOnly) {
    const noComments = html.replace(/<!--[\s\S]*?-->/g, "");
    const styleCount = (noComments.match(/<style[\s>]/g) || []).length;
    console.log(`内联 <style> 块数: ${styleCount} ${styleCount === 0 ? "(OK)" : "(FAIL)"}`);
    const links = [...html.matchAll(/href="\/static\/css\/([a-z]+)\.css/g)].map((x) => x[1]);
    console.log(`CSS <link> 顺序: ${links.join(" -> ")}`);
    const expected = CSS_ORDER.join(" -> ");
    console.log(`期望顺序:      ${expected}`);
    console.log(`顺序匹配: ${links.join(",") === CSS_ORDER.join(",") ? "OK" : "FAIL"}`);
    process.exit(blocks.length === 0 && links.join(",") === CSS_ORDER.join(",") ? 0 : 1);
  }

  if (blocks.length === 0) {
    console.log("内联 <style> 块已为 0，无需改写。");
    return;
  }

  // 保留 head 中 <style> 块之间的其它内容（fontawesome / art-overrides 的
  // <link> 夹在 style 块之间，必须原位保留以维持 cascade 相对顺序）：
  //   原顺序： [style-字体] [link-fontawesome] [link-art-overrides] [style-主] [style-freeTask]
  //   新顺序： [link-fontawesome] [link-art-overrides] [link-css × 6]
  // CSS 链接组插在**最后一个** <style> 块的位置 → 位于 fontawesome 与
  // art-overrides 之后，与迁移前"主样式在它们之后"的相对顺序一致。
  let out = "";
  let cursor = 0;
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    out += html.slice(cursor, b.start);
    if (i === blocks.length - 1) {
      out += CSS_LINKS + "\n";
    }
    cursor = b.end;
  }
  out += html.slice(cursor);

  fs.writeFileSync(INDEX_HTML, out, "utf8");

  // 校验
  const after = fs.readFileSync(INDEX_HTML, "utf8");
  // 统计真实 <style> 块（排除 HTML 注释里出现的 "<style" 字样）
  const styleCount = (after.replace(/<!--[\s\S]*?-->/g, "").match(/<style[\s>]/g) || []).length;
  const links = [...after.matchAll(/href="\/static\/css\/([a-z]+)\.css/g)].map((x) => x[1]);
  const themeScriptAt = after.indexOf("sal.theme");
  const firstCssAt = after.indexOf("/static/css/theme.css");

  console.log(`已删除内联 <style> 块: ${blocks.length} 个`);
  console.log(`剩余 <style> 块: ${styleCount}`);
  console.log(`CSS <link> 顺序: ${links.join(" -> ")}`);
  console.log(
    `主题早期同步脚本在所有 CSS 之前: ${themeScriptAt >= 0 && firstCssAt > themeScriptAt ? "OK" : "FAIL"}`
  );
  console.log(
    `style="" 属性数量: ${(after.match(/\sstyle="/g) || []).length} ` +
      `(迁移前 ${(html.match(/\sstyle="/g) || []).length})`
  );
}

main();
