/**
 * tests/e2e/playwright.bootstrap-safe.config.js
 *
 * Isolated Playwright config for tests/e2e/bootstrap-first-card.spec.js
 * (P0 引导卡 / LT_BOOTSTRAP_FIRST_CARD_20261021_A).
 *
 * The spec boots a real synthetic Factory under %TEMP% via
 * tests/e2e/factory-sandbox-server.py and drives the REAL src/index.html
 * in a pinned local chromium. No mocking of the policy status endpoint
 * except in the explicit "API 断线 fail closed" case, which aborts the
 * request on purpose.
 */

const { defineConfig } = require('@playwright/test');

const CHROMIUM_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /bootstrap-first-card\.spec\.js/,
  timeout: 90000,
  expect: { timeout: 10000 },
  reporter: [['list']],
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    screenshot: 'only-on-failure',
    executablePath: CHROMIUM_PATH,
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  workers: 1,
});
