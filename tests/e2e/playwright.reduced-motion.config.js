/**
 * tests/e2e/playwright.reduced-motion.config.js
 *
 * AR03-P5 —— `prefers-reduced-motion` 回归测试的专用 Playwright 配置。
 *
 * 与其它 safe config 的差异只有一个关键点：
 *
 *   - `reducedMotion: 'reduce'` 放在 **`use` 顶层**，因此
 *     `browser.newContext({ reducedMotion: 'reduce' })` 之外的
 *     `context.newPage()`（test fixture 默认路径）也会真正启用
 *     reduced-motion —— 这正是我们要验证的场景；
 *   - 真实浏览器（pinned local chromium），**不是** jsdom / 手写
 *     media query 文本。
 *
 * 隔离
 * ----
 * 本 config 下的 spec **不** 启动 Flask、不访问 `127.0.0.1:5000`、
 * 不触碰生产 DB / notes / config；网络层由 `page.route()` 全 mock。
 */

const { defineConfig } = require('@playwright/test');

const CHROMIUM_PATH =
  'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /reduced-motion-regression\.spec\.js/,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: [['list']],
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    screenshot: 'only-on-failure',
    executablePath: CHROMIUM_PATH,
    // **关键**：在真实浏览器上下文中启用 reduced motion。
    reducedMotion: 'reduce',
  },
  projects: [
    {
      name: 'chromium-reduced-motion',
      use: { browserName: 'chromium', reducedMotion: 'reduce' },
    },
  ],
  workers: 1,
});
