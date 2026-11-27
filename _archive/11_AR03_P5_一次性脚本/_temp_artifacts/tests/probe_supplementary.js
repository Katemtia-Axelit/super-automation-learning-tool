// Probe: supplementary tests
// 1. XSS via task name in card HTML (already covered by 1.4 but test with stronger payload)
// 2. _noteCache A -> B -> A behavior
// 3. stopTimerFromDock clears both timerDockSession and timerActiveSession
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

  // ============ Test 1: XSS via task name in task list ============
  console.log('=== Test 1: XSS via task name (task list) ===');
  {
    const page = await ctx.newPage();
    page.on('dialog', async d => { try { await d.accept(); } catch (e) {} });
    let alertFired = false;
    page.on('dialog', d => { if (d.type() === 'alert') alertFired = true; });
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    const xssName = '<img src=x onerror=alert(1)>';
    await page.fill('#tfName', xssName);
    await page.fill('#tfTime', '15');
    await page.click('#taskModal button:has-text("保存")');
    await page.waitForFunction(() => {
      const el = document.getElementById('taskModal');
      return el && el.classList.contains('hidden');
    }, { timeout: 10000 });
    await page.waitForTimeout(1500);

    // Check the DOM contains the raw tag (unescaped) or escaped entity
    const domCheck = await page.evaluate((needle) => {
      const cards = document.querySelectorAll('.task-card:not(.drawn-card)');
      const out = { cardCount: cards.length, containsRaw: false, containsEscaped: false, sampleHTML: null };
      cards.forEach(c => {
        if (c.outerHTML.includes(needle)) out.containsRaw = true;
        if (c.outerHTML.includes('&lt;img')) out.containsEscaped = true;
        if (!out.sampleHTML) out.sampleHTML = c.outerHTML.substring(0, 400);
      });
      return out;
    }, xssName);
    console.log('XSS check:', JSON.stringify(domCheck, null, 2));
    console.log('alertFired (raw tag in DOM = vulnerable):', alertFired);
    await page.close();
  }

  // ============ Test 2: _noteCache A->B->A ============
  console.log('\n=== Test 2: _noteCache A->B->A ===');
  {
    const page = await ctx.newPage();
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.click('[data-page="knowledge"]');
    await page.waitForTimeout(1500);

    // Get categories
    const cats = await page.evaluate(async () => {
      const r = await fetch('/api/knowledge/categories').then(r => r.json());
      return r;
    });
    console.log('Categories count:', Array.isArray(cats) ? cats.length : 'not-array');

    // Track calls to /api/knowledge/notes
    let noteCount = 0;
    page.on('request', req => {
      if (req.url().endsWith('/api/knowledge/notes')) {
        noteCount++;
        console.log(`  [REQ #${noteCount}] ${new Date().toISOString()} ${req.url()}`);
      }
    });

    // Reset counters and visit each category
    noteCount = 0;
    // Try first 3 categories
    const catsArr = Array.isArray(cats) ? cats : [];
    if (catsArr.length === 0) {
      console.log('No categories available, cannot test cache');
    } else {
      const tryVisit = async (catName) => {
        try {
          // Categories may be rendered as elements - try clicking via locator
          const loc = page.locator(`.cat-item:has-text("${catName}")`).first();
          if (await loc.isVisible({ timeout: 2000 }).catch(() => false)) {
            await loc.click();
            await page.waitForTimeout(800);
            return true;
          }
        } catch (e) {}
        return false;
      };

      const visited = [];
      for (let i = 0; i < Math.min(3, catsArr.length); i++) {
        const ok = await tryVisit(catsArr[i].name || catsArr[i].path);
        if (ok) visited.push(catsArr[i].name || catsArr[i].path);
      }
      console.log('Visited:', visited);
      console.log('Total /api/knowledge/notes calls during A->B->A sequence:', noteCount);

      // Visit A again if we have at least 2
      if (visited.length >= 2) {
        const before = noteCount;
        const ok = await tryVisit(visited[0]);
        console.log(`Re-visited A (${visited[0]}): ok=${ok}, requests since=${noteCount - before}`);

        // Inspect cache state directly
        const cacheState = await page.evaluate(() => {
          return {
            cacheKeys: Object.keys(_noteCache || {}),
            cacheCat: _noteCacheCat,
            cacheSizes: Object.fromEntries(Object.entries(_noteCache || {}).map(([k, v]) => [k, Array.isArray(v) ? v.length : 'non-array']))
          };
        });
        console.log('Cache state:', JSON.stringify(cacheState, null, 2));
      }
    }
    await page.close();
  }

  // ============ Test 3: stopTimerFromDock -> timerActiveSession cleared ============
  console.log('\n=== Test 3: stopTimerFromDock sync to tasks page ===');
  {
    const page = await ctx.newPage();
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // First ensure no active session
    await page.evaluate(async () => {
      const active = await fetch('/api/timer/active').then(r => r.json());
      if (active && active.id) {
        await fetch('/api/timer/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: active.id, actual_minutes: 0, result: 'abandoned', reason: 'probe3_cleanup' }) });
      }
    });

    // Start a timer on tasks page
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', 'syncProbe-' + Date.now());
    await page.fill('#tfTime', '10');
    await page.click('#taskModal button:has-text("保存")');
    await page.waitForFunction(() => {
      const el = document.getElementById('taskModal');
      return el && el.classList.contains('hidden');
    }, { timeout: 10000 });
    await page.waitForTimeout(800);
    await page.waitForFunction(() => {
      const s = document.getElementById('timerTaskSelect');
      return s && !s.disabled && s.options.length > 1;
    }, { timeout: 10000 });
    await page.locator('#timerTaskSelect').selectOption({ index: 1 });
    await page.fill('#timerPlannedMin', '5');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);

    // Now go to gacha, then click dock stop
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1500);
    const dockActiveVisible = await page.locator('#timerDockActive').isVisible();
    console.log('Dock active visible after switch:', dockActiveVisible);

    // Click dock stop (will trigger confirm dialog, handler accepts)
    await page.click('#timerDockStopBtn');
    await page.waitForTimeout(3000);

    // Check API state
    const apiAfter = await page.evaluate(async () => {
      return fetch('/api/timer/active').then(r => r.json());
    });
    console.log('After dock stop, API active:', JSON.stringify(apiAfter));

    // Now go back to tasks page and check UI
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(2000);
    const tasksState = await page.evaluate(() => {
      const statusEl = document.getElementById('timerStatusText');
      const startBtn = document.getElementById('timerStartBtn');
      const stopBtn = document.getElementById('timerStopBtn');
      return {
        statusText: statusEl ? statusEl.textContent : null,
        startVisible: startBtn ? !startBtn.classList.contains('hidden') : null,
        stopVisible: stopBtn ? !stopBtn.classList.contains('hidden') : null
      };
    });
    console.log('Tasks page after dock stop:', JSON.stringify(tasksState));

    await page.close();
  }

  await browser.close();
  console.log('\n=== Probe complete ===');
})();
