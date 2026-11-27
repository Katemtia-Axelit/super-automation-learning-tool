/**
 * 临时诊断脚本（AR03-P5 reduced-motion 回归调试用）
 * 目的：确认 Playwright test fixture 的 `page` 上 reduced-motion 是否生效，
 *      以及 `test.use({ reducedMotion })` / config `use.reducedMotion`
 *      / project `use.reducedMotion` 三处到底哪一处生效。
 */
const path = require('path');
const fs = require('fs');
const { test, expect } = require('@playwright/test');

test.use({ reducedMotion: 'reduce' });

test('fixture page 的 reduced-motion 状态', async ({ page }) => {
  await page.setContent('<html><body>x</body></html>');
  const out = await page.evaluate(() => ({
    reduce: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    noPref: window.matchMedia('(prefers-reduced-motion: no-preference)').matches,
  }));
  console.log('FIXTURE PAGE =>', JSON.stringify(out));
  expect(out.reduce).toBe(true);
});
