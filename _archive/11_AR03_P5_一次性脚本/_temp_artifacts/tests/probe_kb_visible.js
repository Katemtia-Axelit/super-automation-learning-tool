// Test isVisible on empty elements
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe',
    args: ['--no-sandbox'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:5000/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await page.click('[data-page="knowledge"]');
  await page.waitForTimeout(2000);
  const info = await page.locator('#knowContent').evaluate(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      width: r.width, height: r.height,
      display: cs.display, visibility: cs.visibility,
      innerText: el.innerText,
      innerHTML: el.innerHTML,
      offsetParent: el.offsetParent ? el.offsetParent.tagName : null,
    };
  });
  console.log('knowContent info:', JSON.stringify(info, null, 2));
  await browser.close();
})();