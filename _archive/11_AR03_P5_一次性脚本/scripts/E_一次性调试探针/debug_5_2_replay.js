// Reproduce EXACT 5.2 — record which branch the test follows
const { chromium } = require('playwright-core');
const fs = require('fs');

const BASE_URL = 'http://127.0.0.1:5000';
const EXEC_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: EXEC_PATH, args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();

  const apiLog = [];
  page.on('response', async r => { if (r.url().includes('/api/knowledge/')) {
    let sz = 0; try { sz = (await r.text()).length; } catch(e) {}
    apiLog.push({ url: r.url(), status: r.status(), size: sz });
  }});

  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => { const d = document.getElementById('apiDot'); return d && d.classList.contains('online'); }, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);

  // EXACT 5.2 body
  await page.click('[data-page="knowledge"]');
  await page.waitForTimeout(3000);
  const cats = page.locator('.cat-item');
  const count = await cats.count();
  console.log('cats count after 3000ms:', count);

  if (count > 0) {
    await cats.first().click();
    await page.waitForTimeout(1500);
    const notes = page.locator('.note-item');
    const nCount = await notes.count();
    console.log('notes count after cat click + 1500ms:', nCount);
    if (nCount > 0) {
      await notes.first().click();
      await page.waitForTimeout(2000);
      const v = await page.locator('#knowContent').isVisible();
      const bb = await page.locator('#knowContent').boundingBox();
      console.log('would assert: knowContent.isVisible =', v, 'bbox =', bb);
    } else {
      console.log('notes.count == 0 → outer if (nCount > 0) is FALSE → assert NEVER EXECUTED → 5.2 trivially passes');
    }
  } else {
    console.log('cats.count == 0 → outer if (count > 0) is FALSE → assert NEVER EXECUTED → 5.2 trivially passes');
  }

  console.log('\napiLog:', JSON.stringify(apiLog));
  await browser.close();
})();
