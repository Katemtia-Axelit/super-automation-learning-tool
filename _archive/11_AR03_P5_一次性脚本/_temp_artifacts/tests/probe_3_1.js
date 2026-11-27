// Probe: minimal test to diagnose 3.1 / 3.3 failures
const { chromium } = require('playwright-core');
const BASE_URL = 'http://127.0.0.1:5000';
const EXEC_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: EXEC_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();

  page.on('console', m => {
    if (m.type() === 'error') console.log('CONSOLE_ERR:', m.text());
  });
  page.on('pageerror', e => console.log('PAGE_ERR:', e.message));

  console.log('=== Loading home ===');
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  console.log('=== /api/timer/active ===');
  const active = await page.evaluate(async () => {
    return fetch('/api/timer/active').then(r => r.json());
  });
  console.log('active session:', JSON.stringify(active));

  console.log('=== Click [data-page="tasks"] ===');
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(2000);

  console.log('=== Probe tasks page ===');
  const probe = await page.evaluate(() => {
    const out = {};
    const panel = document.getElementById('timerPanel');
    out.timerPanel = panel ? {
      exists: true,
      visible: !!(panel.offsetWidth || panel.offsetHeight),
      display: getComputedStyle(panel).display,
      classes: panel.className
    } : { exists: false };

    const startBtn = document.getElementById('timerStartBtn');
    out.timerStartBtn = startBtn ? {
      exists: true,
      visible: !!(startBtn.offsetWidth || startBtn.offsetHeight),
      classes: startBtn.className,
      disabled: startBtn.disabled
    } : { exists: false };

    const stopBtn = document.getElementById('timerStopBtn');
    out.timerStopBtn = stopBtn ? {
      exists: true,
      visible: !!(stopBtn.offsetWidth || stopBtn.offsetHeight),
      classes: stopBtn.className
    } : { exists: false };

    const pauseBtn = document.getElementById('timerPauseBtn');
    out.timerPauseBtn = pauseBtn ? {
      exists: true,
      visible: !!(pauseBtn.offsetWidth || pauseBtn.offsetHeight),
      classes: pauseBtn.className,
      title: pauseBtn.title,
      innerHTML: pauseBtn.innerHTML
    } : { exists: false };

    const sel = document.getElementById('timerTaskSelect');
    out.timerTaskSelect = sel ? {
      exists: true,
      options: sel.options.length,
      disabled: sel.disabled,
      firstOpt: sel.options[0]?.textContent,
      secondOpt: sel.options[1]?.textContent
    } : { exists: false };

    const status = document.getElementById('timerStatusText');
    out.timerStatusText = status ? status.textContent : null;

    const pages = document.querySelectorAll('.page');
    out.pages = Array.from(pages).map(p => ({ id: p.id, classes: p.className }));

    return out;
  });
  console.log('PROBE_TASKS:', JSON.stringify(probe, null, 2));

  // Now check what 3.1 actually asserts
  const panelVisible = await page.locator('#timerPanel').isVisible();
  const startBtnVisible = await page.locator('#timerStartBtn').isVisible();
  const selVisible = await page.locator('#timerTaskSelect').isVisible();
  console.log('3.1 CHECKS: timerPanel.isVisible=%s, timerStartBtn.isVisible=%s, timerTaskSelect.isVisible=%s', panelVisible, startBtnVisible, selVisible);

  await browser.close();
})();
