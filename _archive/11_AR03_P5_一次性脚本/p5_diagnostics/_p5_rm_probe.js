/**
 * 临时诊断脚本（AR03-P5 reduced-motion 回归调试用）
 * 目的：确认 (a) reduced-motion 是否真的在浏览器上下文里生效；
 *      (b) responsive.css 的 @media 块是否命中；
 *      (c) cards.css 与 responsive.css 的 pointer-events 叠加结果。
 * 用法：node tests/e2e/_p5_rm_probe.js
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require('@playwright/test');

const ROOT = path.resolve(__dirname, '..', '..');
const CHROMIUM_PATH =
  'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROMIUM_PATH,
  });
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();

  await page.setContent(`<!DOCTYPE html><html><head></head><body>
    <div class="task-card" id="card"><div>x</div></div>
  </body></html>`);

  const responsive = fs.readFileSync(
    path.join(ROOT, 'static', 'css', 'responsive.css'),
    'utf8',
  );
  const cards = fs.readFileSync(path.join(ROOT, 'static', 'css', 'cards.css'), 'utf8');

  await page.addStyleTag({ content: responsive });
  await page.addStyleTag({ content: cards });

  const out = await page.evaluate(() => {
    const el = document.getElementById('card');
    const sheets = Array.from(document.styleSheets).map((s) => ({
      href: s.href,
      rules: (() => {
        try {
          return s.cssRules.length;
        } catch (e) {
          return 'ERR:' + e.message;
        }
      })(),
    }));
    el.classList.add('is-discarding');
    return {
      mediaMatches: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      mediaNoPref: window.matchMedia('(prefers-reduced-motion: no-preference)').matches,
      pointerEvents: getComputedStyle(el).pointerEvents,
      animationDuration: getComputedStyle(el).animationDuration,
      animationName: getComputedStyle(el).animationName,
      sheets,
    };
  });

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})();
