// Isolated Playwright config for tests/e2e/gacha-multidraw-safe.spec.js
//
// This spec uses page.setContent and page.route to fully mock the backend,
// so it must NOT inherit baseURL: http://127.0.0.1:5000 from the existing
// tests/e2e/playwright.config.js. We point it at the existing local
// chromium executable and run the single spec file in this directory.

const { defineConfig } = require('@playwright/test');

const CHROMIUM_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /gacha-multidraw-safe\.spec\.js|debug\.spec\.js/,
  timeout: 30000,
  expect: { timeout: 8000 },
  reporter: [['list']],
  use: {
    // NO baseURL on purpose: this spec is fully isolated via page.setContent.
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    screenshot: 'only-on-failure',
    executablePath: CHROMIUM_PATH,
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  // Do NOT launch the project's live Flask server.
  workers: 1,
});
