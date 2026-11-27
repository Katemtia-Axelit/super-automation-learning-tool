// 诊断脚本：打开页面，看为什么 taskSearch 不可见
const { chromium } = require('playwright-core');
const EXEC = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: EXEC, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('console', msg => console.log('[console]', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('[pageerror]', err.message));
  await page.goto('http://127.0.0.1:5000/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // 1. apiDot 状态
  const apiState = await page.evaluate(() => {
    const d = document.getElementById('apiDot');
    return d ? d.className : 'NOT FOUND';
  });
  console.log('apiDot:', apiState);

  // 2. SAL 全局
  const sal = await page.evaluate(() => ({
    hasSAL: !!window.SAL,
    hasApi: !!(window.SAL && window.SAL.core && window.SAL.core.api),
    hasTheme: !!(window.SAL && window.SAL.core && window.SAL.core.theme),
    hasBus: !!(window.SAL && window.SAL.core && window.SAL.core.eventBus),
    dataTheme: document.documentElement.getAttribute('data-theme'),
  }));
  console.log('SAL:', JSON.stringify(sal));

  // 3. taskSearch 可见性
  const tSearch = await page.evaluate(() => {
    const el = document.getElementById('taskSearch');
    if (!el) return 'NOT FOUND';
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
      rect: { w: r.width, h: r.height, x: r.x, y: r.y },
      display: cs.display,
      visibility: cs.visibility,
      page: el.closest('.page')?.id,
      pageActive: el.closest('.page')?.classList.contains('active'),
    };
  });
  console.log('taskSearch:', JSON.stringify(tSearch));

  // 4. 切到 tasks
  await page.click('button[data-page="tasks"]');
  await page.waitForTimeout(800);
  const tSearch2 = await page.evaluate(() => {
    const el = document.getElementById('taskSearch');
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
      pageActive: el.closest('.page')?.classList.contains('active'),
    };
  });
  console.log('taskSearch (after click tasks):', JSON.stringify(tSearch2));

  // 5. 截图
  await page.screenshot({ path: 'tests/diag_stepA.png', fullPage: false });
  console.log('screenshot saved');

  await browser.close();
})();
