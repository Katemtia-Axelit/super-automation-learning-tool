// Debug probe for 5.1 — knowledge page visibility
const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();
  page.on('console', msg => console.log('[console]', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('[pageerror]', err.message));

  await page.goto('http://127.0.0.1:5000/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => {
    const dot = document.getElementById('apiDot');
    return dot && dot.classList.contains('online');
  }, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);

  console.log('--- before click ---');
  console.log('knowledge btn:', await page.locator('[data-page="knowledge"]').isVisible());
  console.log('page-knowledge hidden class:', await page.locator('#page-knowledge').evaluate(el => el.classList.contains('hidden')));

  await page.click('[data-page="knowledge"]');
  await page.waitForTimeout(3000);

  console.log('--- after click ---');
  console.log('know-layout count:', await page.locator('.know-layout').count());
  console.log('know-layout visible:', await page.locator('.know-layout').isVisible().catch(e => 'ERR: ' + e.message));
  console.log('catList count:', await page.locator('#catList').count());
  console.log('catList visible:', await page.locator('#catList').isVisible().catch(e => 'ERR: ' + e.message));
  console.log('noteList count:', await page.locator('#noteList').count());
  console.log('noteList visible:', await page.locator('#noteList').isVisible().catch(e => 'ERR: ' + e.message));
  console.log('knowContent count:', await page.locator('#knowContent').count());
  console.log('knowContent visible:', await page.locator('#knowContent').isVisible().catch(e => 'ERR: ' + e.message));
  console.log('page-knowledge class:', await page.locator('#page-knowledge').evaluate(el => el.className));

  await browser.close();
})();