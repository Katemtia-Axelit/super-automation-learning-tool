// Probe: simulate exactly what 3.1 / 3.3 do
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

  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // ---- Probe 3.1 ----
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);
  const panelV = await page.locator('#timerPanel').isVisible();
  const startV = await page.locator('#timerStartBtn').isVisible();
  const selV = await page.locator('#timerTaskSelect').isVisible();
  console.log('3.1: panel=%s startBtn=%s select=%s', panelV, startV, selV);

  // The real failure is startBtn
  if (!startV) {
    console.log('--> Confirmed: startBtn is hidden because timerActiveSession exists in DB.');
  }

  // ---- Probe 3.3 path (after timer stop) ----
  console.log('\n=== Attempting to clear paused session via API ===');
  const cleanupResult = await page.evaluate(async () => {
    const active = await fetch('/api/timer/active').then(r => r.json());
    if (active && active.id) {
      const r = await fetch('/api/timer/resume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: active.id }) }).then(r => r.json());
      const r2 = await fetch('/api/timer/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: active.id, actual_minutes: 0, result: 'abandoned', reason: 'probe_cleanup' }) }).then(r => r.json());
      return { resume: r, complete: r2 };
    }
    return null;
  });
  console.log('cleanupResult:', JSON.stringify(cleanupResult));

  // reload page to pick up the cleared state
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  const panelV2 = await page.locator('#timerPanel').isVisible();
  const startV2 = await page.locator('#timerStartBtn').isVisible();
  const selV2 = await page.locator('#timerTaskSelect').isVisible();
  console.log('3.1 retry: panel=%s startBtn=%s select=%s', panelV2, startV2, selV2);

  // ---- Now run 3.3 ----
  await page.click('button:has-text("新建任务")');
  await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
  await page.fill('#tfName', '计时器Probe-' + Date.now());
  await page.fill('#tfTime', '30');
  await page.click('#taskModal button:has-text("保存")');
  await page.waitForFunction(() => {
    const el = document.getElementById('taskModal');
    return el && el.classList.contains('hidden');
  }, { timeout: 10000 });
  await page.waitForTimeout(800);

  // Probe the waitForFunction target
  try {
    await page.waitForFunction(() => {
      const s = document.getElementById('timerTaskSelect');
      return s && !s.disabled && s.options.length > 1;
    }, { timeout: 10000 });
    console.log('3.3 waitForFunction: PASSED');
  } catch (e) {
    console.log('3.3 waitForFunction: FAILED -', e.message);
    const state = await page.evaluate(() => {
      const s = document.getElementById('timerTaskSelect');
      return s ? { disabled: s.disabled, options: s.options.length, firstOpt: s.options[0]?.textContent } : null;
    });
    console.log('select state at failure:', JSON.stringify(state));
  }

  await browser.close();
})();
