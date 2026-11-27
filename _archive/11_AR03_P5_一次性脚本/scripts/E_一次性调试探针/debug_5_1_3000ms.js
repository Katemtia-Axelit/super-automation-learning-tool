// Debug 5.1 — EXACT 3000ms replay using Playwright isVisible() and boundingBox().
// READ-ONLY on production source. Does not modify tests/e2e-manual.js.
const { chromium } = require('playwright-core');
const fs = require('fs');

const BASE_URL = 'http://127.0.0.1:5000';
const EXEC_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';
const OUT_PATH = 'd:\\Axelit\\.工作\\trae\\超级自动化学习工具\\.run\\debug_5.1_3000ms.json';

const SELECTORS = ['.know-layout', '#catList', '#noteList', '#knowContent'];
const TIMEPOINTS_MS = [0, 50, 100, 250, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000];

async function snapshotAt(page, t) {
  return await page.evaluate(({ sels, t }) => {
    const out = { t, perSelector: {}, pageState: {}, knowContentTimeline: {}, apiLog: window.__apiLog || [] };
    const pk = document.getElementById('page-knowledge');
    if (pk) {
      const pcs = getComputedStyle(pk);
      out.pageState = {
        exists: true,
        display: pcs.display,
        hasActive: pk.classList.contains('active'),
        className: pk.className,
      };
    } else {
      out.pageState = { exists: false };
    }
    for (const s of sels) {
      const el = document.querySelector(s);
      if (!el) { out.perSelector[s] = { exists: false }; continue; }
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const par = el.parentElement;
      const ps = par ? getComputedStyle(par) : null;
      const pr = par ? par.getBoundingClientRect() : null;
      out.perSelector[s] = {
        exists: true,
        display: cs.display,
        visibility: cs.visibility,
        opacity: cs.opacity,
        width: rect.width, height: rect.height,
        x: rect.x, y: rect.y,
        innerHTML_length: (el.innerHTML || '').length,
        innerText_length: (el.textContent || '').length,
        childCount: el.children.length,
        parent: par ? { tag: par.tagName, id: par.id, class: par.className, display: ps && ps.display, width: pr && pr.width, height: pr && pr.height } : null,
      };
    }
    return out;
  }, { sels: SELECTORS, t });
}

async function probeRun(runIdx) {
  const browser = await chromium.launch({
    headless: true, executablePath: EXEC_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });

  // Per-run: install /api/knowledge/* timing capture by patching fetch.
  await ctx.addInitScript(() => {
    window.__apiLog = [];
    const origFetch = window.fetch;
    window.fetch = function (...args) {
      const url = typeof args[0] === 'string' ? args[0] : args[0].url;
      const start = performance.now();
      return origFetch.apply(this, args).then(async resp => {
        const dur = performance.now() - start;
        if (url && url.includes('/api/knowledge/')) {
          let size = 0;
          try {
            const clone = resp.clone();
            const t = await clone.text();
            size = t.length;
          } catch (e) {}
          window.__apiLog.push({ url, status: resp.status, durationMs: Math.round(dur), respSize: size, atMs: Math.round(performance.now()) });
        }
        return resp;
      });
    };
  });

  const page = await ctx.newPage();
  const net = [];
  page.on('response', async r => {
    if (r.url().includes('/api/knowledge/')) {
      let n = null; try { n = await r.headerValue('content-length'); } catch (e) {}
      net.push({ url: r.url(), status: r.status(), contentLength: n });
    }
  });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e)));
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });

  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => {
    const d = document.getElementById('apiDot');
    return d && d.classList.contains('online');
  }, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);

  const clickAt = Date.now();
  await page.click('[data-page="knowledge"]');

  // Mark page activation moment
  const timeline = [];
  for (const t of TIMEPOINTS_MS) {
    const elapsed = Date.now() - clickAt;
    if (elapsed < t) await page.waitForTimeout(t - elapsed);
    const snap = await snapshotAt(page, t);

    // Also call the EXACT Playwright API used by 5.1
    const playwrightVisible = {};
    for (const s of SELECTORS) {
      const loc = page.locator(s);
      try {
        const v = await loc.isVisible();
        const bb = await loc.boundingBox();
        playwrightVisible[s] = { isVisible: v, bbox: bb };
      } catch (e) {
        playwrightVisible[s] = { isVisible: false, error: e.message };
      }
    }
    snap.playwrightVisible = playwrightVisible;
    timeline.push(snap);
  }

  // Final 5.1-style assertions (MIRROR EXACT TEST CODE)
  const final = {};
  for (const s of SELECTORS) {
    const loc = page.locator(s);
    try {
      final[s] = { isVisible: await loc.isVisible(), bbox: await loc.boundingBox() };
    } catch (e) { final[s] = { error: e.message }; }
  }
  // Replicate the assertion EXACTLY: if first fails, throw with default message
  let firstFail = null;
  for (const s of SELECTORS) {
    if (!final[s].isVisible) { firstFail = s; break; }
  }

  // Get knowledge async chain log
  const apiLog = await page.evaluate(() => window.__apiLog || []);

  await browser.close();
  return {
    run: runIdx,
    startedAt: new Date(clickAt).toISOString(),
    apiLog,
    pageErrors,
    consoleErrors,
    timeline,
    finalPlaywright: final,
    firstFailAt_3000ms: firstFail, // null means PASS
  };
}

(async () => {
  const runs = parseInt(process.argv[2] || '3', 10);
  const all = [];
  for (let i = 1; i <= runs; i++) {
    console.log(`=== Run ${i}/${runs} ===`);
    const r = await probeRun(i);
    all.push(r);
    console.log(`  3000ms firstFail: ${r.firstFailAt_3000ms || 'NONE'}`);
    for (const s of SELECTORS) {
      const pv = r.finalPlaywright[s];
      const bb = pv && pv.bbox;
      console.log(`    ${s}: isVisible=${pv && pv.isVisible} bbox=${bb ? `${Math.round(bb.width)}x${Math.round(bb.height)}` : 'null'}`);
    }
    console.log(`  apiLog: ${JSON.stringify(r.apiLog)}`);
  }
  fs.writeFileSync(OUT_PATH, JSON.stringify(all, null, 2), 'utf8');
  console.log(`\nWrote ${all.length} runs to ${OUT_PATH}`);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
