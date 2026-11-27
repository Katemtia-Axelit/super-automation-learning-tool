const { defineConfig } = require('@playwright/test');
const CHROMIUM_PATH =
  'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /_p5_rm_fixture_probe\.spec\.js/,
  timeout: 60000,
  reporter: [['list']],
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    executablePath: CHROMIUM_PATH,
    reducedMotion: 'reduce',
  },
  projects: [
    { name: 'probe', use: { browserName: 'chromium', reducedMotion: 'reduce' } },
  ],
  workers: 1,
});
