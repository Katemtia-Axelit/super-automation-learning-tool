// 诊断脚本：验证主题切换
const { chromium } = require('playwright-core');
const EXEC = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: EXEC, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('console', msg => console.log('[console]', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('[pageerror]', err.message));
  await page.goto('http://127.0.0.1:5000/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // 1. 初始主题
  const t1 = await page.evaluate(() => ({
    attr: document.documentElement.getAttribute('data-theme'),
    stored: localStorage.getItem('sal.theme'),
    bgColor: getComputedStyle(document.body).backgroundColor,
    btnExists: !!document.getElementById('themeToggle'),
    iconClass: document.getElementById('themeToggleIcon')?.className
  }));
  console.log('Before toggle:', JSON.stringify(t1));

  // 2. 点击切换
  await page.click('#themeToggle');
  await page.waitForTimeout(500);
  const t2 = await page.evaluate(() => ({
    attr: document.documentElement.getAttribute('data-theme'),
    stored: localStorage.getItem('sal.theme'),
    bgColor: getComputedStyle(document.body).backgroundColor,
    iconClass: document.getElementById('themeToggleIcon')?.className
  }));
  console.log('After toggle:', JSON.stringify(t2));

  // 3. 截图
  await page.screenshot({ path: 'tests/diag_theme.png', fullPage: false });

  // 4. 刷新看持久化
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const t3 = await page.evaluate(() => ({
    attr: document.documentElement.getAttribute('data-theme'),
    stored: localStorage.getItem('sal.theme'),
    iconClass: document.getElementById('themeToggleIcon')?.className
  }));
  console.log('After reload:', JSON.stringify(t3));

  await browser.close();
})();
