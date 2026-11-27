const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const E2E_DIR = __dirname;
const FIXTURE_PATH = path.join(E2E_DIR, 'factory-sandbox-server.py');

test('debug bootstrap', async () => {
  const venvPy = path.join(path.resolve(E2E_DIR, '..', '..'), '.venv', 'Scripts', 'python.exe');
  const child = spawn(venvPy, ['-B', FIXTURE_PATH, '--print-url'], {
    cwd: E2E_DIR, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
  });
  let out = '';
  child.stdout.on('data', (c) => { out += c.toString(); });
  const base = await new Promise((res, rej) => {
    const t = setInterval(() => {
      const m = out.match(/^URL:(http:\/\/127\.0\.0\.1:\d+)\s*$/m);
      if (m) { clearInterval(t); res(m[1]); }
    }, 100);
    setTimeout(() => rej(new Error('no url ' + out)), 30000);
  });

  const { chromium } = require('@playwright/test');
  const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe' });
  const page = await browser.newPage();
  page.on('console', (m) => console.log('CONSOLE', m.type(), m.text()));
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  page.on('requestfailed', (r) => console.log('REQFAIL', r.url(), r.failure() && r.failure().errorText));
  page.on('response', (r) => { if (r.url().includes('agent-policy')) console.log('STATUSRESP', r.status(), r.url()); });
  await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const info = await page.evaluate(() => {
    const ov = document.getElementById('salBootstrapOverlay');
    return {
      exists: !!ov,
      hidden: ov ? ov.hidden : null,
      htmlClass: document.documentElement.className,
      hasSAL: typeof window.SAL_BOOTSTRAP,
      state: window.SAL_BOOTSTRAP ? window.SAL_BOOTSTRAP.state() : null,
      bodyChildren: Array.from(document.body.children).map((c) => c.id || c.tagName),
    };
  });
  console.log('INFO', JSON.stringify(info, null, 2));
  const st = await page.evaluate(async (b) => {
    try { const r = await fetch(b + '/api/agent-policy/status'); return { status: r.status, body: await r.text() }; }
    catch (e) { return { err: String(e) }; }
  }, base);
  console.log('DIRECT', JSON.stringify(st));
  await browser.close();
  child.kill();
});
