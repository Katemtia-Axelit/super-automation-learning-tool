// Probe 4: Narrow down XSS source
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
  page.on('dialog', async d => {
    console.log('DIALOG FIRED type=' + d.type() + ' message=' + d.message().substring(0, 100));
    try { await d.accept(); } catch (e) {}
  });
  page.on('pageerror', e => console.log('PAGE_ERR:', e.message));
  page.on('console', m => {
    if (m.type() === 'error' || m.text().includes('XSS')) {
      console.log('CONSOLE:', m.type(), m.text().substring(0, 200));
    }
  });

  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);
  await page.click('button:has-text("新建任务")');
  await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
  const xssName = '<img src=x onerror=alert("P3_XSS_HIT")>';
  await page.fill('#tfName', xssName);
  await page.fill('#tfTime', '15');
  await page.click('#taskModal button:has-text("保存")');
  await page.waitForFunction(() => {
    const el = document.getElementById('taskModal');
    return el && el.classList.contains('hidden');
  }, { timeout: 10000 });
  await page.waitForTimeout(2000);

  // Now check task list DOM in detail
  const probe = await page.evaluate((needle) => {
    const allCards = Array.from(document.querySelectorAll('.task-card, [data-task-id], .task-name, .task-list-item, .task-title'));
    const out = { foundXssName: false, elements: [] };
    document.querySelectorAll('*').forEach(el => {
      const own = Array.from(el.attributes || []).map(a => a.value).join(' ');
      const inner = el.innerHTML || '';
      if (own.includes('onerror') || inner.includes('onerror')) {
        out.elements.push({
          tag: el.tagName,
          id: el.id,
          classes: el.className,
          attrs: own.substring(0, 200),
          inner: inner.substring(0, 200)
        });
      }
    });
    return out;
  }, xssName);
  console.log('PROBE onerror scan:', JSON.stringify(probe, null, 2));

  // Now check the gacha card path with the same task name
  console.log('\n=== Try gacha draw ===');
  await page.click('[data-page="gacha"]');
  await page.waitForTimeout(2000);
  await page.click('button:has-text("抽一张"), button:has-text("抽卡"), #gachaBtn, .btn:has-text("抽")');
  await page.waitForTimeout(3000);
  const gachaProbe = await page.evaluate(() => {
    const drawn = document.querySelectorAll('.drawn-card, .task-card.drawn-card, [data-task-id]');
    const out = [];
    drawn.forEach(d => {
      const inner = d.innerHTML || '';
      const own = Array.from(d.attributes || []).map(a => a.value).join(' ');
      if (inner.includes('onerror') || own.includes('onerror')) {
        out.push({ tag: d.tagName, inner: inner.substring(0, 300) });
      }
    });
    return out;
  });
  console.log('Gacha onerror scan:', JSON.stringify(gachaProbe, null, 2));

  await browser.close();
})();
