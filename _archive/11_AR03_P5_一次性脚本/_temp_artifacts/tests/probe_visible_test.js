// Test Playwright isVisible on 0-height div
const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe',
    args: ['--no-sandbox'],
  });
  const ctx = await b.newContext();
  const p = await ctx.newPage();
  await p.setContent('<style>.p{display:none}.p.a{display:block}.c{height:0;width:100px;background:red}</style><div class="p a" id="pk"><div class="c" id="kc"></div></div>');
  const v1 = await p.locator('#pk').isVisible();
  const v2 = await p.locator('#kc').isVisible();
  const v3 = await p.locator('#kc').isHidden();
  console.log('parent (visible):', v1);
  console.log('child 0-height div:', v2);
  console.log('child isHidden:', v3);
  await b.close();
})();