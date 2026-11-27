// Debug 5.1 repro probe (READ-ONLY on source).
// - Does NOT modify tests/e2e-manual.js
// - Does NOT modify any source
// - Launches a fresh browser context for each run
// - Records visibility/DOM state for 4 selectors at multiple time points
// - Captures network responses for /api/knowledge/*
// - Writes results to a JSON file (path: D:\\Axelit\\...\\.run\\debug_5.1_runs.json)

const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://127.0.0.1:5000';
const EXEC_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';
const OUT_PATH = 'd:\\Axelit\\.工作\\trae\\超级自动化学习工具\\.run\\debug_5.1_runs.json';

const SELECTORS = ['.know-layout', '#catList', '#noteList', '#knowContent'];
const TIMEPOINTS_MS = [0, 50, 150, 300, 800, 1500, 3000, 5000];

async function probeOne(runIdx) {
  const browser = await chromium.launch({
    headless: true,
    executablePath: EXEC_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();

  // Capture network for knowledge endpoints
  const net = [];
  page.on('response', async resp => {
    const u = resp.url();
    if (u.includes('/api/knowledge/')) {
      let body = null;
      try { body = await resp.text(); } catch (e) {}
      net.push({ url: u, status: resp.status(), body: body ? body.slice(0, 200) : null });
    }
  });
  page.on('pageerror', e => net.push({ url: 'PAGE_ERROR', status: 0, body: String(e) }));
  page.on('console', m => { if (m.type() === 'error') net.push({ url: 'CONSOLE_ERROR', status: 0, body: m.text() }); });

  const runRecord = { run: runIdx, startedAt: new Date().toISOString(), net, timeline: [], finalAssert: {} };

  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  // Match e2e-manual waitForApiReady
  await page.waitForFunction(() => {
    const d = document.getElementById('apiDot');
    return d && d.classList.contains('online');
  }, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);

  const clickAt = Date.now();
  await page.click('[data-page="knowledge"]');

  // Sample visibility at multiple time points
  for (const t of TIMEPOINTS_MS) {
    const elapsed = Date.now() - clickAt;
    if (elapsed < t) await page.waitForTimeout(t - elapsed);
    const snap = await page.evaluate((sels) => {
      const out = {};
      for (const s of sels) {
        const el = document.querySelector(s);
        if (!el) { out[s] = { exists: false }; continue; }
        const cs = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const par = el.parentElement;
        const ps = par ? getComputedStyle(par) : null;
        out[s] = {
          exists: true,
          display: cs.display,
          visibility: cs.visibility,
          opacity: cs.opacity,
          width: rect.width, height: rect.height,
          x: rect.x, y: rect.y,
          childCount: el.children.length,
          textLen: (el.textContent || '').length,
          parentTag: par ? par.tagName : null,
          parentId: par ? par.id : null,
          parentClass: par ? par.className : null,
          parentDisplay: ps ? ps.display : null,
          parentActive: par ? par.classList.contains('active') : null,
        };
      }
      // page-knowledge state
      const pk = document.getElementById('page-knowledge');
      const pcs = pk ? getComputedStyle(pk) : null;
      out.__page_knowledge = pk ? {
        exists: true,
        display: pcs.display,
        hasActive: pk.classList.contains('active'),
        className: pk.className
      } : { exists: false };
      return out;
    }, SELECTORS);
    runRecord.timeline.push({ tMs: Date.now() - clickAt, snapshot: snap });
  }

  // Final 5.1-style assertions
  runRecord.finalAssert = await page.evaluate((sels) => {
    const out = {};
    for (const s of sels) {
      const el = document.querySelector(s);
      if (!el) { out[s] = { exists: false, visible: false, reason: 'no_element' }; continue; }
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0;
      out[s] = {
        exists: true,
        display: cs.display,
        visibility: cs.visibility,
        opacity: cs.opacity,
        width: rect.width, height: rect.height,
        visible_manual: visible
      };
    }
    return out;
  }, SELECTORS);

  // Also: list .cat-item / .note-item / md-content innerHTML snippet
  runRecord.innerState = await page.evaluate(() => {
    return {
      catListHtml: (document.getElementById('catList') || {}).innerHTML || null,
      noteListHtml: (document.getElementById('noteList') || {}).innerHTML || null,
      knowContentHtml: (document.getElementById('knowContent') || {}).innerHTML || null,
      catItemCount: document.querySelectorAll('.cat-item').length,
      noteItemCount: document.querySelectorAll('.note-item').length,
    };
  });

  await browser.close();
  return runRecord;
}

(async () => {
  const args = process.argv.slice(2);
  const runs = parseInt(args[0] || '5', 10);
  const all = [];
  for (let i = 1; i <= runs; i++) {
    console.log(`=== Run ${i}/${runs} ===`);
    try {
      const r = await probeOne(i);
      all.push(r);
      // Print summary
      for (const sel of SELECTORS) {
        const a = r.finalAssert[sel];
        console.log(`  ${sel}: exists=${a && a.exists} display=${a && a.display} vis=${a && a.visibility} w/h=${a && a.width}x${a && a.height}`);
      }
    } catch (e) {
      console.log(`Run ${i} ERROR: ${e.message}`);
      all.push({ run: i, error: e.message });
    }
  }
  fs.writeFileSync(OUT_PATH, JSON.stringify(all, null, 2), 'utf8');
  console.log(`\nWrote ${all.length} runs to ${OUT_PATH}`);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
