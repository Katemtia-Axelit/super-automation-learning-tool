"use strict";
/**
 * AR03-P4 —— 从**保存的迁移前 CSS 块**重建一个临时的 pre-migration
 * index.html，供 `capture_css_baselines.js` 生成基线使用。
 *
 * 背景：迁移后 `src/index.html` 已无内联 <style>，无法再从它生成基线。
 * 本脚本用迁移前**逐字保存**的 3 个块（`.tmp_block_0/1/2.css`）重建一个
 * 临时文件，结构与原文件一致（字体块 → 主样式块 → freeTaskStyle 块）。
 *
 * 该临时文件写到 `.tmp_premigration_index.html`，**不改动** src/index.html。
 *
 * 用法：node scripts/rebuild_premigration_index.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, ".tmp_premigration_index.html");

const BLOCKS = [
  { file: ".tmp_block_0.css", attrs: "" },
  { file: ".tmp_block_1.css", attrs: "" },
  { file: ".tmp_block_2.css", attrs: ' id="freeTaskStyle"' },
];

function main() {
  const parts = [];
  for (const b of BLOCKS) {
    const p = path.join(ROOT, b.file);
    if (!fs.existsSync(p)) {
      console.error(`FAIL: 缺少 ${b.file} —— 无法重建迁移前 index.html`);
      process.exit(1);
    }
    const css = fs.readFileSync(p, "utf8");
    parts.push(`<style${b.attrs}>${css}</style>`);
  }

  const html =
    `<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n` +
    `<title>PRE-MIGRATION BASELINE (AR03-P4)</title>\n${parts.join("\n")}\n` +
    `</head>\n<body></body>\n</html>\n`;

  fs.writeFileSync(OUT, html, "utf8");
  console.log(`WROTE: ${path.basename(OUT)} (${html.length} chars)`);
  console.log(`内联 style 块数: ${BLOCKS.length}`);
}

main();
