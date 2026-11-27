// Test Playwright isVisible with sized and unsized divs
const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe',
    args: ['--no-sandbox'],
  });
  const ctx = await b.newContext();
  const p = await ctx.newPage();
  // Test cases:
  //  1. Empty parent (display:block) - 0 size
  //  2. Sized parent (display:block, min-height)
  //  3. Sized parent + empty child
  await p.setContent(`
    <style>.p{display:none}.p.a{display:block;min-height:60vh;background:cyan}
    .empty{height:0;width:100px}
    </style>
    <div class="p" id="emptyParent"></div>
    <div class="p a" id="sizedParent"><div class="empty" id="emptyChild"></div></div>
  `);
  console.log('emptyParent (display:none):', await p.locator('#emptyParent').isVisible());
  console.log('sizedParent (display:block, 60vh):', await p.locator('#sizedParent').isVisible());
  console.log('emptyChild (inside sized, 0h):', await p.locator('#emptyChild').isVisible());
  await b.close();
})();