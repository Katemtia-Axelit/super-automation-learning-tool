// Isolated Playwright config for tests/e2e/css-visual-regression.spec.js
//
// AR03-P4 —— CSS 视觉回归。
//
// This spec boots a real Flask Factory via tests/e2e/factory-sandbox-server.py
// inside a Python subprocess (100% TEMP synthetic root). Tests navigate to
// http://127.0.0.1:<random> using ``baseURL`` set in beforeAll. We MUST NOT
// inherit baseURL:5000 from tests/e2e/playwright.config.js.
//
// We point at the same pinned local chromium executable the other isolated
// spec uses and run a single spec file in this directory.

const { defineConfig } = require('@playwright/test');

const CHROMIUM_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /css-visual-regression\.spec\.js/,
  timeout: 120000,
  expect: { timeout: 10000 },
  reporter: [['list']],
  use: {
    // baseURL is overridden per-case in beforeAll to the per-invocation
    // random port of the synthetic Factory server.
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    screenshot: 'only-on-failure',
    executablePath: CHROMIUM_PATH,
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  // The synthetic Factory is single-process; do not race it.
  workers: 1,
});
