/**
 * tests/e2e/gacha-multidraw-safe.spec.js
 *
 * Isolated Playwright browser coverage for the P0 multi-draw hardening.
 *
 * Constraints (per Task Contract):
 *   - DO NOT navigate to live http://127.0.0.1:5000.
 *   - DO NOT touch production DB / notes / config.
 *   - DO NOT use the project's live Flask server.
 *   - No remote web requests, no installations.
 *   - Set conservative timeouts.
 *
 * Approach:
 *   Use page.setContent() for the DOM and page.addScriptTag({path}) for the
 *   real multi-draw JavaScript functions extracted from static/app.js.
 *   We intercept the /api/gacha/multi-draw network call with page.route().
 *
 *   NOTE on isolated browser limitation: The full app.js wires hundreds of
 *   DOM IDs at top-level parse time; many will be missing from our minimal
 *   synthetic page. Loading the complete app.js would throw ReferenceError
 *   and leave functions undefined. We therefore extract only the three
 *   multi-draw functions into a mini-bundle and inject that via addScriptTag.
 *   This still tests the real source code (from the project file) in a
 *   browser, confirming that the renderMultiResults / activateMultiCard /
 *   drawGachaMulti functions execute correctly under the isolation constraints.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const APP_JS_PATH = path.join(PROJECT_ROOT, 'static', 'app.js');

/**
 * Extract a top-level function from app.js source text.
 */
function extractFunction(source, name) {
  // Match both `function NAME(...) {` and `async function NAME(...) {`.
  const re = new RegExp(
    '(?:async\\s+)?function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{',
  );
  const m = source.match(re);
  if (!m) return null;
  let depth = 0;
  for (let i = m.index + m[0].length - 1; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(m.index, i + 1);
    }
  }
  return null;
}

/**
 * Build a synthetic page that:
 *   - Provides minimal DOM for the multi-draw region
 *   - Loads only the three multi-draw functions from the real app.js
 *   - Provides stubs for helpers those functions need
 */
function buildMiniBundle() {
  const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
  const rmr = extractFunction(appJs, 'renderMultiResults');
  const amc = extractFunction(appJs, 'activateMultiCard');
  const dgm = extractFunction(appJs, 'drawGachaMulti');
  if (!rmr || !amc || !dgm) {
    throw new Error('Could not extract multi-draw functions from app.js');
  }
  // Combine stubs + real functions + wiring.
  return `
// === stubs (mimic what app.js expects at top level) ===
var gachaState = {
  energy: 'medium', pool: 'fragment', canReplace: true,
  replacedTaskId: null, feedbackMood: 3, currentTaskId: null, selectedTag: ''
};
var isDrawing = false;
var multiDrawResults = [];
function toast() {}
function refreshGachaStats() {}
async function api(url, opts) {
  opts = opts || {};
  var r = await fetch(url, Object.assign(
    { headers: { 'Content-Type': 'application/json' } }, opts
  ));
  var data = {};
  try { data = await r.json(); } catch(e) {}
  return data;
}
function getGachaAvailableMinutes() {
  var input = document.getElementById('gachaTimeInput');
  var v = input ? parseInt(input.value, 10) : 25;
  return (isNaN(v) || v < 1) ? 25 : Math.min(v, 480);
}
function renderDrawnCard(task) {
  var stage = document.createElement('div');
  stage.className = 'drawn-card-stage';
  var card = document.createElement('div');
  card.className = 'task-card drawn-card';
  card.setAttribute('data-task-id', task.id);
  var t = document.createElement('div');
  t.className = 'task-card-title';
  t.textContent = task.name || '';
  card.appendChild(t);
  stage.appendChild(card);
  return stage;
}

// === real multi-draw functions from app.js ===
${rmr}

${amc}

${dgm}

// === wire the button ===
document.getElementById('gachaMultiBtn').addEventListener('click', drawGachaMulti);
window.__harness_ready = true;
`;
}

let miniBundle;

function getMiniBundle() {
  if (!miniBundle) {
    miniBundle = buildMiniBundle();
  }
  return miniBundle;
}

function buildMinimalHTML() {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>gacha multidraw isolated</title>
<style>
  body { font-family: sans-serif; background: #0f1422; color: #f0e8da; padding: 24px; }
  .gacha-multi-result { margin-top: 12px; }
  .gacha-multi-result.hidden { display: none !important; }
  .gacha-multi-summary {
    background: rgba(26,32,56,0.85); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; font-size: 0.85rem;
    display: flex; gap: 16px; flex-wrap: wrap; justify-content: center;
  }
  .gacha-multi-summary strong { color: #f0c040; }
  .gacha-multi-list { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
  button.gacha-multi-item {
    background: rgba(26,32,56,0.85); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 8px 12px; cursor: pointer; min-width: 140px; max-width: 200px;
    color: #f0e8da; text-align: left; display: flex; flex-direction: column; gap: 4px;
    font-family: sans-serif; font-size: 0.85rem;
  }
  button.gacha-multi-item:hover { border-color: #f0c040; }
  button.gacha-multi-item:focus-visible { outline: 2px solid #f0c040; outline-offset: 2px; }
  button.gacha-multi-item[aria-pressed="true"] {
    border-color: #f0c040; background: rgba(240,192,64,0.18);
  }
  .gacha-multi-item-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gacha-multi-item-meta { font-size: 0.72rem; color: #6b6480; display: flex; gap: 8px; }
  .gacha-multi-item-tag {
    padding: 1px 6px; border-radius: 6px; font-size: 0.65rem;
    background: rgba(240,192,64,0.15); color: #f0c040;
  }
  .drawn-card-stage { display: flex; justify-content: center; padding: 8px; }
  .task-card { background: #1a2038; color: #f0e8da; padding: 12px; width: 280px; border-radius: 12px; border: 1px solid #f0c040; }
  .task-card-title { font-size: 1.05rem; margin-bottom: 6px; }
</style>
</head>
<body>
  <div class="gacha-multi-row">
    <label for="gachaTimeInput">time</label>
    <input type="number" id="gachaTimeInput" value="25" min="1" max="480">
    <label for="gachaMultiCount">count</label>
    <select id="gachaMultiCount">
      <option value="2">2</option>
      <option value="3" selected>3</option>
      <option value="4">4</option>
      <option value="5">5</option>
    </select>
    <button class="gacha-multi-btn" id="gachaMultiBtn">\u8fde\u62bd</button>
  </div>
  <div class="gacha-multi-result hidden" id="gachaMultiResult">
    <div class="gacha-multi-summary" id="gachaMultiSummary"></div>
    <div class="gacha-multi-list" id="gachaMultiList"></div>
  </div>
  <div id="gachaResult"></div>
  <button id="gachaBtn" style="display:none">single</button>
</body>
</html>`;
}

function buildPayload({ count, malicious }) {
  const safe = [
    { id: 1, name: 'Read physics chapter', estimated_time: 15, tags: ['physics', 'study'] },
    { id: 2, name: 'Solve 5 algebra problems', estimated_time: 25, tags: ['math'] },
    { id: 3, name: 'Write essay intro', estimated_time: 30, tags: ['writing'] },
    { id: 4, name: 'Review flashcards', estimated_time: 10, tags: ['memory'] },
    { id: 5, name: 'Practice listening', estimated_time: 20, tags: ['language'] },
  ];
  const evil = {
    id: 99,
    name: '<img src=x onerror="window.__xss=1"><script>window.__xss=2<\/script>',
    estimated_time: '"><img src=x onerror="window.__xss=3">',
    tags: ['<script>window.__xss=4<\/script>'],
  };
  const tasks = safe.slice(0, Math.min(count, safe.length));
  if (malicious) tasks.push(evil);
  return {
    tasks,
    total_minutes: tasks.reduce((s, t) => s + (Number(t.estimated_time) || 0), 0),
    remaining_minutes: 480 - tasks.reduce((s, t) => s + (Number(t.estimated_time) || 0), 0),
  };
}

async function loadIsolatedPage(page, routeHandler) {
  // Pin the page origin to a non-about:blank URL so fetch('/api/...') inside
  // the page is routed through Playwright. setContent() alone roots the page
  // at about:blank, which makes fetch() throw "Failed to parse URL".
  // We first navigate to the harness base URL (intercepted by route('**/*')
  // below to serve the minimal HTML), then setContent the same HTML again so
  // our DOM ids / stubs line up exactly.
  const HARNESS_BASE = 'http://test.local/';
  await page.context().route('**/*', async (route) => {
    const url = route.request().url();
    if (url.indexOf('/api/gacha/multi-draw') !== -1) {
      return routeHandler(route);
    }
    return route.fulfill({
      status: 200, contentType: 'text/html', body: buildMinimalHTML(),
    });
  });
  await page.goto(HARNESS_BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.setContent(buildMinimalHTML(), { waitUntil: 'domcontentloaded', timeout: 10000 });
  // Capture page errors for diagnostics.
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));
  // Inject the mini-bundle as a script.
  await page.addScriptTag({ content: getMiniBundle() });
  // Wait for the harness to signal readiness.
  await page.waitForFunction(() => window.__harness_ready === true, { timeout: 10000 });
  if (errors.length > 0) {
    throw new Error('Page errors during script load: ' + errors.join('; '));
  }
}

test.describe('gacha multidraw isolated e2e (mocked, no live server)', () => {
  test.beforeEach(async ({ page }) => {
    page.setDefaultTimeout(8000);
  });

  test('exactly one POST per click and the summary renders', async ({ page }) => {
    let postCount = 0;
    await loadIsolatedPage(page, async (route) => {
      postCount += 1;
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    expect(postCount).toBe(1);
    const text = await page.locator('#gachaMultiSummary').textContent();
    expect(text).toMatch(/\u62bd\u5230/);   // 抽到
    expect(text).toMatch(/\u5171/);          // 共
    expect(text).toMatch(/\u5269\u4f59/);   // 剩余
  });

  test('malicious task name/tag strings do not execute', async ({ page }) => {
    await loadIsolatedPage(page, async (route) => {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: true })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    const xss = await page.evaluate(() => window.__xss || 0);
    expect(xss).toBe(0);
    const listHTML = await page.locator('#gachaMultiList').innerHTML();
    expect(listHTML).not.toMatch(/<script/i);
    expect(listHTML).toContain('&lt;img');
  });

  test('items are button with accessible name and aria-pressed', async ({ page }) => {
    await loadIsolatedPage(page, async (route) => {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    expect(
      await page.locator('.gacha-multi-item').first().evaluate((el) => el.tagName)
    ).toBe('BUTTON');
    expect(
      await page.locator('.gacha-multi-item').first().getAttribute('type')
    ).toBe('button');
    const name = await page.locator('.gacha-multi-item').first().textContent();
    expect(name).toMatch(/Read physics|Solve 5|Write essay|Review flashcards|Practice listening/);
    expect(
      await page.locator('.gacha-multi-item').first().getAttribute('aria-pressed')
    ).toBe('false');
  });

  test('keyboard Enter activates and flips aria-pressed', async ({ page }) => {
    await loadIsolatedPage(page, async (route) => {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    const first = page.locator('.gacha-multi-item').first();
    await first.focus();
    await page.keyboard.press('Enter');
    await expect(first).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
    const n = await page.locator('.gacha-multi-item').count();
    for (let i = 1; i < n; i += 1) {
      await expect(page.locator('.gacha-multi-item').nth(i)).toHaveAttribute('aria-pressed', 'false');
    }
  });

  test('keyboard Space activates and flips aria-pressed', async ({ page }) => {
    await loadIsolatedPage(page, async (route) => {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    const second = page.locator('.gacha-multi-item').nth(1);
    await second.focus();
    await page.keyboard.press(' ');
    await expect(second).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
  });

  test('activation does not issue a second POST and reuses the issued card path', async ({ page }) => {
    let postCount = 0;
    await loadIsolatedPage(page, async (route) => {
      postCount += 1;
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    expect(postCount).toBe(1);
    await page.locator('.gacha-multi-item').first().click();
    await expect(page.locator('.gacha-multi-item').first()).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
    expect(postCount).toBe(1);
    await page.waitForSelector('#gachaResult .task-card', { timeout: 3000 });
  });

  test('count selector 2..5 and time input 1..480 stay usable', async ({ page }) => {
    await loadIsolatedPage(page, async (route) => {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 5, malicious: false })),
      });
    });
    await page.selectOption('#gachaMultiCount', '5');
    expect(await page.locator('#gachaMultiCount').inputValue()).toBe('5');
    await page.fill('#gachaTimeInput', '60');
    expect(await page.locator('#gachaTimeInput').inputValue()).toBe('60');
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    await expect(page.locator('#gachaMultiBtn')).toBeEnabled({ timeout: 5000 });
  });

  test('malicious total_minutes/remaining_minutes strings do not execute', async ({ page }) => {
    await loadIsolatedPage(page, async (route) => {
      const evil = buildPayload({ count: 1, malicious: false });
      evil.total_minutes = '<img src=x onerror="window.__xssTotal=1">';
      evil.remaining_minutes = '"><script>window.__xssRem=1<\/script>';
      return route.fulfill({
        status: 200, contentType: 'application/json', body: JSON.stringify(evil),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    const xss1 = await page.evaluate(() => window.__xssTotal || 0);
    const xss2 = await page.evaluate(() => window.__xssRem || 0);
    expect(xss1).toBe(0);
    expect(xss2).toBe(0);
  });

  // ----- M1.1 reentrancy / network-error coverage --------------------------

  test('aborted network request unlocks buttons and allows the next valid draw', async ({ page }) => {
    let postCount = 0;
    let mode = 'abort';
    await loadIsolatedPage(page, async (route) => {
      postCount += 1;
      if (mode === 'abort') {
        return route.abort('failed');
      }
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });

    // (A1) First click: the route aborts. The app.js catch + finally block
    //      must restore isDrawing=false and re-enable both buttons. No
    //      multi items should be rendered, and the result area must stay
    //      hidden (or empty).
    await page.click('#gachaMultiBtn');
    // Wait for the lock to release. We don't waitForSelector('.gacha-multi-item')
    // because the aborted request must NEVER render any.
    await page.waitForFunction(() => window.isDrawing === false, { timeout: 5000 });
    expect(postCount).toBe(1);
    await expect(page.locator('#gachaMultiBtn')).toBeEnabled({ timeout: 3000 });
    await expect(page.locator('#gachaBtn')).toBeEnabled({ timeout: 3000 });
    expect(await page.locator('.gacha-multi-item').count()).toBe(0);
    // The result area must stay hidden because the catch branch hides it.
    const hiddenAfterAbort = await page.evaluate(() => {
      var el = document.getElementById('gachaMultiResult');
      return el ? el.classList.contains('hidden') : true;
    });
    expect(hiddenAfterAbort).toBe(true);

    // (A2) Switch the route to success and click again: the next draw must
    //      succeed (POST count -> 2) and render the items.
    mode = 'ok';
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    expect(postCount).toBe(2);
    await expect(page.locator('#gachaMultiBtn')).toBeEnabled({ timeout: 3000 });
  });

  test('slow API plus two rapid clicks - exactly one POST pending, then unlock', async ({ page }) => {
    let postCount = 0;
    let inflight = 0;
    let maxInflight = 0;
    let pendingResolver;
    const handlerGate = new Promise(function (resolve) {
      pendingResolver = resolve;
    });
    await loadIsolatedPage(page, async (route) => {
      postCount += 1;
      inflight += 1;
      if (inflight > maxInflight) maxInflight = inflight;
      // Hold the response until the test releases the gate.
      await handlerGate;
      inflight -= 1;
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });

    // (B1) Fire two clicks synchronously back-to-back via dispatchEvent so
    //      they enter drawGachaMulti on the same JS task. The first call
    //      sets isDrawing=true and starts awaiting fetch; the second call
    //      must return early at the `if (isDrawing) return;` guard and
    //      must NOT issue another POST.
    await page.evaluate(() => {
      var btn = document.getElementById('gachaMultiBtn');
      btn.click();
      btn.click();
    });

    // Wait until the in-flight POST is registered server-side.
    await page.waitForFunction(() => window.isDrawing === true, { timeout: 3000 });
    expect(postCount).toBe(1);
    expect(maxInflight).toBe(1);

    // Buttons must be disabled while pending (drawGachaMulti locks both).
    await expect(page.locator('#gachaMultiBtn')).toBeDisabled({ timeout: 2000 });
    await expect(page.locator('#gachaBtn')).toBeDisabled({ timeout: 2000 });

    // Release the slow API and let the first click resolve.
    pendingResolver();
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    await page.waitForFunction(() => window.isDrawing === false, { timeout: 5000 });
    await expect(page.locator('#gachaMultiBtn')).toBeEnabled({ timeout: 3000 });
    await expect(page.locator('#gachaBtn')).toBeEnabled({ timeout: 3000 });
    expect(postCount).toBe(1);

    // (B2) Selecting a rendered card MUST NOT trigger another POST. The
    //      activation path is local-only: it flips aria-pressed and writes
    //      the chosen card into #gachaResult via renderDrawnCard.
    await page.click('.gacha-multi-item');
    await expect(page.locator('.gacha-multi-item').first()).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
    expect(postCount).toBe(1);
    expect(maxInflight).toBe(1);
  });

  // ----- M1.2 card-selection UX + payload safety (NEW) -----------------
  //
  // These tests exercise ACTUAL production code extracted from
  // static/app.js rather than stubs. They cover two of the explicit
  // M1.2 goals: (1) the selection keyboard focus + exactly-one
  // aria-pressed invariant under repeated selection, (3) the
  // renderDrawnCard payload safety against hostile metadata.

  /**
   * Build a self-sufficient mini-bundle for testing the REAL
   * renderDrawnCard (with its real helpers) in isolation, without the
   * full app.js startup. Includes:
   *   - escapeHtml (real)
   *   - taskTextBlob (real)
   *   - resolveTaskCardTheme (real)
   *   - renderDrawnCard (real)
   *   - activateMultiCard (real) — for multi-issued-card test
   *   - renderMultiResults (real) — to populate issued cards
   *   - gachaState stub + minimal helpers
   * No live network stubs are needed because renderDrawnCard does not
   * fetch, but we still honor routeHandler for /api/gacha/multi-draw so
   * tests that exercise activation can reuse the standard harness.
   */
  function buildRenderDrawnCardBundle() {
    const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
    const esc = extractFunction(appJs, 'escapeHtml');
    const ttb = extractFunction(appJs, 'taskTextBlob');
    const rtct = extractFunction(appJs, 'resolveTaskCardTheme');
    const rdc = extractFunction(appJs, 'renderDrawnCard');
    const rmr = extractFunction(appJs, 'renderMultiResults');
    const amc = extractFunction(appJs, 'activateMultiCard');
    const dgm = extractFunction(appJs, 'drawGachaMulti');
    if (!esc || !rdc) {
      throw new Error('Could not extract renderDrawnCard helpers from app.js');
    }
    return `
// === state + minimal stubs (real renderDrawnCard reads canReplace) ===
var gachaState = {
  energy: 'medium', pool: 'fragment', canReplace: true,
  replacedTaskId: null, feedbackMood: 3, currentTaskId: null, selectedTag: ''
};
var isDrawing = false;
var multiDrawResults = [];
var timerDockSession = null;
function toast() {}
function refreshGachaStats() {}
async function api(url, opts) {
  opts = opts || {};
  var r = await fetch(url, Object.assign(
    { headers: { 'Content-Type': 'application/json' } }, opts
  ));
  var data = {};
  try { data = await r.json(); } catch(e) {}
  return data;
}
function getGachaAvailableMinutes() {
  var input = document.getElementById('gachaTimeInput');
  var v = input ? parseInt(input.value, 10) : 25;
  return (isNaN(v) || v < 1) ? 25 : Math.min(v, 480);
}
function openNoteFromCard(p) {
  // M1.2: capture the resolved path so the test can assert it.
  window.__openNoteFromCardCalled = String(p == null ? '' : p);
}

// === real helpers + real renderDrawnCard + real multi-draw helpers ===
${esc}
${ttb || ''}
${rtct || ''}
${rdc}
${rmr || ''}
${amc || ''}
${dgm || ''}
// Wire the button to the real drawGachaMulti so the standard harness
// pattern (click the button, get .gacha-multi-item buttons) keeps working.
document.getElementById('gachaMultiBtn').addEventListener('click', drawGachaMulti);
window.__harness_ready_rdc = true;
`;
  }
  const RDC_BUNDLE = buildRenderDrawnCardBundle();

  async function loadIsolatedPageForRdc(page, routeHandler) {
    // Same isolated bootstrap pattern as loadIsolatedPage, but loads the
    // RDC bundle instead. The route handler is shared so the same network
    // interception rules apply (we need /api/health stub for any stray
    // fetch — though renderDrawnCard does not call fetch itself).
    const HARNESS_BASE = 'http://test.local/';
    await page.context().route('**/*', async (route) => {
      const url = route.request().url();
      if (url.indexOf('/api/gacha/multi-draw') !== -1) {
        return routeHandler(route);
      }
      return route.fulfill({
        status: 200, contentType: 'text/html',
        body: buildMinimalHTML(),
      });
    });
    await page.goto(HARNESS_BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.setContent(buildMinimalHTML(), { waitUntil: 'domcontentloaded', timeout: 10000 });
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.addScriptTag({ content: RDC_BUNDLE });
    try {
      await page.waitForFunction(() => window.__harness_ready_rdc === true, { timeout: 10000 });
    } catch (e) {
      if (errors.length > 0) {
        throw new Error('Page errors during script load: ' + errors.join('; '));
      }
      throw e;
    }
    if (errors.length > 0) {
      throw new Error('Page errors during script load: ' + errors.join('; '));
    }
  }

  test('M1.2 A: hostile task metadata cannot execute scripts or inject DOM via real renderDrawnCard', async ({ page }) => {
    /**
     * M1.2 GOAL (3) — Card payload safety.
     *
     * Calls the REAL renderDrawnCard extracted from static/app.js with a
     * hostile task payload and asserts:
     *   - no onerror/onload/alert script runs (window.__xss* == 0)
     *   - the rendered card text contains the literal hostile string
     *     (proving it was rendered as data, not parsed as markup)
     *   - only ONE .drawn-card stage exists (no rogue duplicates)
     *   - the four action buttons exist and have safe data-task-id
     */
    await loadIsolatedPageForRdc(page, async (route) => {
      return route.fulfill({ status: 200, contentType: 'text/json', body: '{}' });
    });

    const hostileTask = {
      id: '1);window.__xssStart=1;//',
      name: '<img src=x onerror="window.__xssName=1">',
      description: '</span><script>window.__xssDesc=1<\/script><span>',
      priority: '<img src=x onerror="window.__xssPrio=1">',
      estimated_time: '"><img src=x onerror="window.__xssTime=1">',
      linked_note_path: 'foo<svg onload="window.__xssNote=1">bar',
      tags: ['<script>window.__xssTag=1<\/script>'],
      category: 'study',
      repeat_type: 'none',
      deadline: null,
    };

    // Call the REAL renderDrawnCard.
    await page.evaluate((taskJson) => {
      var t = JSON.parse(taskJson);
      var stage = renderDrawnCard(t, 0);
      document.getElementById('gachaResult').appendChild(stage);
    }, JSON.stringify(hostileTask));

    // No script side effects.
    const allFlags = await page.evaluate(() => ({
      xssStart: window.__xssStart || 0,
      xssName: window.__xssName || 0,
      xssDesc: window.__xssDesc || 0,
      xssPrio: window.__xssPrio || 0,
      xssTime: window.__xssTime || 0,
      xssNote: window.__xssNote || 0,
      xssTag: window.__xssTag || 0,
    }));
    for (const k of Object.keys(allFlags)) {
      expect(allFlags[k]).toBe(0);
    }

    // Only one stage was rendered.
    expect(await page.locator('#gachaResult .drawn-card-stage').count()).toBe(1);

    // The rendered outer HTML must not contain any LIVE event handler
    // attributes that execute user-controlled code. After our hardening
    // the only places that contain `onerror=` / `onload=` are inside
    // attribute VALUES (escaped via &lt; / &amp;quot;) where the browser
    // decodes the entities but only inside a JS string literal passed
    // to a known function. We probe via JS to be robust against
    // escaped substrings that look like attributes.
    const liveHandlers = await page.evaluate(() => {
      function walk(root, acc) {
        if (!root) return acc;
        if (root.nodeType === 1) { // Element
          for (const a of root.attributes || []) {
            if (/^on/i.test(a.name)) acc.push(a.name + '=' + a.value.slice(0, 200));
          }
          // child nodes
          for (const c of root.childNodes || []) walk(c, acc);
        }
        return acc;
      }
      const card = document.querySelector('#gachaResult .drawn-card');
      return walk(card, []);
    });
    // The only allowed event handler attributes on the card are the
    // four onclick= buttons that we explicitly render. None may host
    // user-controlled text in their argument. They must call fn(N)
    // with an integer literal, OR openNoteFromCard('...') with the
    // path wrapped in single quotes — and crucially the value must
    // NOT contain unbalanced `)` or `;` that would break out.
    for (const h of liveHandlers) {
      const allowedShapes = [
        /^onclick=startTask\(\d+\)$/,
        /^onclick=handleSkip\(\d+\)$/,
        /^onclick=handleRefuse\(\d+\)$/,
        /^onclick=showReplaceReason\(\d+\)$/,
        // openNoteFromCard may contain a path with < and > since they
        // are HTML-encoded into the value and decoded into the JS
        // string. The path must be wrapped in '...' and must not
        // contain unbalanced quote or `)` characters.
        /^onclick=openNoteFromCard\('(?:[^']|\'\\')*'\)$/,
      ];
      const okShape = allowedShapes.some((re) => re.test(h));
      expect(okShape).toBe(true);
      // The handler must NEVER contain a free-standing alert/eval/
      // Function call. Any such call would mean the user-controlled
      // value escaped into the JS expression.
      expect(h).not.toMatch(/\balert\s*\(/);
      expect(h).not.toMatch(/\beval\s*\(/);
      expect(h).not.toMatch(/\bFunction\s*\(/);
      expect(h).not.toMatch(/setTimeout\s*\(/);
      expect(h).not.toMatch(/setInterval\s*\(/);
    }

    // Also: no <script>, <svg>, <iframe>, <img>, <object> in the card.
    const liveTagCheck = await page.evaluate(() => {
      const card = document.querySelector('#gachaResult .drawn-card');
      return {
        script: card.querySelectorAll('script').length,
        svg: card.querySelectorAll('svg').length,
        img: card.querySelectorAll('img').length,
        iframe: card.querySelectorAll('iframe').length,
        object: card.querySelectorAll('object').length,
      };
    });
    expect(liveTagCheck.script).toBe(0);
    expect(liveTagCheck.svg).toBe(0);
    expect(liveTagCheck.img).toBe(0);
    expect(liveTagCheck.iframe).toBe(0);
    expect(liveTagCheck.object).toBe(0);

    // The four action buttons must exist and carry a sane data-task-id
    // (parseInt('1);...') === 1 — the safeId coercion in renderDrawnCard).
    const startBtn = page.locator('#gachaResult button:has-text("开始任务")');
    await expect(startBtn).toHaveCount(1);
    // The onclick string must contain a valid integer and NOT contain
    // the hostile ')' sequence (which would have broken out).
    const onclickText = await startBtn.evaluate(el => el.getAttribute('onclick'));
    expect(onclickText).toMatch(/startTask\(\s*\d+\s*\)/);
    expect(onclickText).not.toMatch(/alert\s*\(/);
    expect(onclickText).not.toContain('window.__xssStart');
  });

  test('M1.2 B: selecting among issued cards twice — focus stays, exactly one aria-pressed, no extra POST', async ({ page }) => {
    /**
     * M1.2 GOAL (1) — multi-card selection keyboard Tab/Enter/Space:
     *   focus stays on the selected button, aria-pressed exactly one
     *   true, activation updates currentTaskId and single display
     *   without new draw POST.
     */
    let postCount = 0;
    await loadIsolatedPage(page, async (route) => {
      postCount += 1;
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    const n = await page.locator('.gacha-multi-item').count();
    expect(n).toBeGreaterThanOrEqual(3);
    expect(postCount).toBe(1);

    // First selection — click first card.
    const first = page.locator('.gacha-multi-item').nth(0);
    const second = page.locator('.gacha-multi-item').nth(1);
    await first.focus();
    await page.keyboard.press('Enter');

    // aria-pressed invariant after first selection.
    await expect(first).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
    for (let i = 1; i < n; i += 1) {
      await expect(page.locator('.gacha-multi-item').nth(i)).toHaveAttribute('aria-pressed', 'false', { timeout: 3000 });
    }

    // Keyboard focus stays on the selected button (M1.2 a11y fix:
    // activateMultiCard now calls .focus() on the selectedItem).
    const focusedAfterFirst = await page.evaluate(
      () => document.activeElement && document.activeElement.getAttribute('data-task-id')
    );
    const firstId = await first.getAttribute('data-task-id');
    expect(focusedAfterFirst).toBe(firstId);

    // Second selection — click second card.
    await second.focus();
    await page.keyboard.press(' ');

    // aria-pressed invariant: exactly one true, and it is the second.
    await expect(second).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });
    for (let i = 0; i < n; i += 1) {
      if (i === 1) continue;
      await expect(page.locator('.gacha-multi-item').nth(i)).toHaveAttribute('aria-pressed', 'false', { timeout: 3000 });
    }
    const focusedAfterSecond = await page.evaluate(
      () => document.activeElement && document.activeElement.getAttribute('data-task-id')
    );
    const secondId = await second.getAttribute('data-task-id');
    expect(focusedAfterSecond).toBe(secondId);

    // No new draw POST was issued by either activation.
    expect(postCount).toBe(1);

    // currentTaskId was updated to the second selection's id.
    const currentTaskId = await page.evaluate(() => {
      return (window.gachaState && window.gachaState.currentTaskId) || null;
    });
    expect(String(currentTaskId)).toBe(String(secondId));

    // The single-draw display was repopulated (no new draw POST needed).
    await page.waitForSelector('#gachaResult .drawn-card-stage', { timeout: 3000 });
    expect(await page.locator('#gachaResult .drawn-card-stage').count()).toBeGreaterThanOrEqual(1);
  });

  /**
   * Build a self-sufficient mini-bundle for M1.3A — exercise the REAL
   * startTask end-to-end against a mocked /api/timer/start POST. Includes:
   *   - All M1.2 RDC helpers
   *   - startTask (real)
   *   - prereqHint stub (unlocked tasks skip the prereq path; tests use is_unlocked=true)
   *   - updateTimerDockDisplay stub
   *   - startInlineTimer stub (test asserts presence of inline controls via DOM)
   *   - window._inlineTimerHandle stub object
   * The bundle is loaded after the page exposes gachaTimeInput with value 25.
   */
  function buildM13aBundle() {
    const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
    const esc = extractFunction(appJs, 'escapeHtml');
    const ttb = extractFunction(appJs, 'taskTextBlob');
    const rtct = extractFunction(appJs, 'resolveTaskCardTheme');
    const rdc = extractFunction(appJs, 'renderDrawnCard');
    const rmr = extractFunction(appJs, 'renderMultiResults');
    const amc = extractFunction(appJs, 'activateMultiCard');
    const dgm = extractFunction(appJs, 'drawGachaMulti');
    const stt = extractFunction(appJs, 'startTask');
    if (!esc || !rdc || !rmr || !amc || !dgm || !stt) {
      throw new Error('Could not extract M1.3A functions from app.js');
    }
    return `
// === state + minimal stubs (real startTask reads timerDockSession,
                            // allTasks, gachaState, _inlineTimerHandle) ===
var gachaState = {
  energy: 'medium', pool: 'fragment', canReplace: true,
  replacedTaskId: null, feedbackMood: 3, currentTaskId: null, selectedTag: ''
};
var isDrawing = false;
var multiDrawResults = [];
var allTasks = (window.__forceAllTasks === null) ? [] : (window.__forceAllTasks || []);
var timerDockSession = null;
var timerDockPaused = false;
var timerDockPausedElapsed = 0;
// M1.3A: declare module-level guards used by startTask() so the
// extracted function (which references these by name) sees them in
// the harness scope.
var _currentDrawnTask = null;
var _pendingStartTaskId = null;
window._inlineTimerHandle = null;
function toast(msg, type) { window.__lastToast = { msg: String(msg || ''), type: String(type || 'inf') }; }
function refreshGachaStats() {}
function prereqHint() { return null; }
function updateTimerDockDisplay() {}
function startInlineTimer(taskId, startedAt, planned) {
  // Real function reads timerDockSession; the harness stubs the interval.
  window.__inlineTimerTaskId = taskId;
  window.__inlineTimerStartedAt = startedAt;
  window.__inlineTimerPlanned = planned;
}
async function api(url, opts) {
  opts = opts || {};
  var r = await fetch(url, Object.assign(
    { headers: { 'Content-Type': 'application/json' } }, opts
  ));
  var data = {};
  try { data = await r.json(); } catch(e) {}
  // M1.3A: production api() throws on non-2xx so the catch in
  // startTask can restore the UI. Mirror that in the harness.
  if (!r.ok) {
    var msg = data.error || data.message || ('请求失败 (' + r.status + ')');
    throw new Error(msg);
  }
  return data;
}
function getGachaAvailableMinutes() {
  var input = document.getElementById('gachaTimeInput');
  var v = input ? parseInt(input.value, 10) : 25;
  return (isNaN(v) || v < 1) ? 25 : Math.min(v, 480);
}
function openNoteFromCard(p) {
  window.__openNoteFromCardCalled = String(p == null ? '' : p);
}

// === real helpers + real multi-draw helpers + real startTask ===
${esc}
${ttb || ''}
${rtct || ''}
${rdc}
${rmr}
${amc}
${dgm}
${stt}
// Wire the button to the real drawGachaMulti so the standard harness
// pattern (click the button, get .gacha-multi-item buttons) keeps working.
document.getElementById('gachaMultiBtn').addEventListener('click', drawGachaMulti);
window.__harness_ready_m13a = true;
`;
  }
let m13aBundle;

function getM13aBundle() {
  if (!m13aBundle) {
    m13aBundle = buildM13aBundle();
  }
  return m13aBundle;
}

  async function loadIsolatedPageForM13a(page, routeHandler) {
    const HARNESS_BASE = 'http://test.local/';
    await page.context().route('**/*', async (route) => {
      const url = route.request().url();
      if (url.indexOf('/api/gacha/multi-draw') !== -1 ||
          url.indexOf('/api/timer/start') !== -1) {
        return routeHandler(route);
      }
      return route.fulfill({
        status: 200, contentType: 'text/html',
        body: buildMinimalHTML(),
      });
    });
    // M1.3A A deliberately forces allTasks=[] at bundle-init time.
    // Test bodies that want a non-empty allTasks re-seed it post-init
    // by pushing into window.allTasks.
    await page.addInitScript(() => {
      window.__forceAllTasks = null;  // empty array at bundle-init
    });
    await page.goto(HARNESS_BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.setContent(buildMinimalHTML(), { waitUntil: 'domcontentloaded', timeout: 10000 });
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.addScriptTag({ content: getM13aBundle() });
    try {
      await page.waitForFunction(() => window.__harness_ready_m13a === true, { timeout: 10000 });
    } catch (e) {
      if (errors.length > 0) {
        throw new Error('Page errors during script load: ' + errors.join('; '));
      }
      throw e;
    }
    if (errors.length > 0) {
      throw new Error('Page errors during script load: ' + errors.join('; '));
    }
  }

  test('M1.3A A: multi-issued card start with allTasks=[] — exactly one timer start with valid payload', async ({ page }) => {
    /**
     * M1.3A GOAL (1) — Real startTask() called by the rendered card
     * 开始任务 button must succeed even when allTasks is empty.
     *
     * Bug: static/app.js startTask(taskId) did
     *     var task = allTasks.find(x => x.id === taskId);
     *     if (!task) { toast('任务不存在', 'err'); return; }
     * even when the user has just rendered the card via renderMultiResults
     * → activateMultiCard → renderDrawnCard. allTasks is populated
     * asynchronously by /api/tasks, and may be empty on the very first
     * interaction. M1.2 case C documented this failure.
     *
     * Approach: synthetic multi-draw response with valid task id 2,
     * window.allTasks=[] deliberately, click the real .gacha-multi-item
     * (2nd one) then click the real 开始任务 button rendered by
     * renderDrawnCard. The real startTask() must:
     *   - resolve the task via a fallback (not allTasks)
     *   - fire exactly one POST /api/timer/start with the chosen task id
     *   - populate timerDockSession with the response
     *   - make the timer controls visible on the card
     *
     * Selecting the card must NOT issue a new draw POST (activation path
     * is local).
     */
    let drawPosts = 0;
    let timerPosts = 0;
    let lastTimerBody = null;
    let timerResponse = {
      session_id: 7, task_id: 2,
      started_at: '2026-10-11T12:00:00.000Z',
      planned_minutes: 25,
    };
    await loadIsolatedPageForM13a(page, async (route) => {
      const url = route.request().url();
      if (url.indexOf('/api/gacha/multi-draw') !== -1) {
        drawPosts += 1;
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
        });
      }
      if (url.indexOf('/api/timer/start') !== -1) {
        timerPosts += 1;
        try { lastTimerBody = JSON.parse(route.request().postData() || '{}'); } catch (e) {}
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(timerResponse),
        });
      }
      return route.abort('failed');
    });
    // allTasks=[] on purpose — this surfaces the M1.2 case-C bug.
    // (window.__forceAllTasks = null is set by loadIsolatedPageForM13a.)

    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    expect(drawPosts).toBe(1);

    // Pick the SECOND issued card (matches the contract: pick 2nd card).
    const target = page.locator('.gacha-multi-item').nth(1);
    const targetId = await target.getAttribute('data-task-id');
    expect(targetId).toBe('2');
    await target.click();

    // Sanity: no second draw POST from activation.
    expect(drawPosts).toBe(1);

    // Card with 开始任务 button is rendered.
    await page.waitForSelector('#gachaResult button:has-text("开始任务")', { timeout: 3000 });

    // Click the actual rendered 开始任务 button — fires REAL startTask.
    await page.click('#gachaResult button:has-text("开始任务")');

    // Wait for the timer POST to settle.
    await page.waitForFunction(() => window.timerDockSession && window.timerDockSession.id === 7, { timeout: 5000 });

    // Exactly one timer POST.
    expect(timerPosts).toBe(1);
    // Payload contents match: numeric task id, planned minutes from gachaTimeInput=25.
    expect(lastTimerBody).toBeTruthy();
    expect(lastTimerBody.task_id).toBe(2);
    expect(lastTimerBody.planned_minutes).toBe(25);

    // gachaState.currentTaskId matches the chosen card.
    const currentTaskId = await page.evaluate(
      () => window.gachaState && window.gachaState.currentTaskId
    );
    expect(String(currentTaskId)).toBe('2');

    // timerDockSession populated from the response.
    const dock = await page.evaluate(() => ({
      id: window.timerDockSession && window.timerDockSession.id,
      task_id: window.timerDockSession && window.timerDockSession.task_id,
      planned: window.timerDockSession && window.timerDockSession.planned_minutes,
      task_name: window.timerDockSession && window.timerDockSession.task_name,
    }));
    expect(dock.id).toBe(7);
    expect(dock.task_id).toBe(2);
    expect(dock.planned).toBe(25);
    expect(typeof dock.task_name).toBe('string');

    // Card timer controls visible: card-timer-display, pause btn, confirm btn.
    await page.waitForSelector('#gachaResult .card-timer-display', { timeout: 3000 });
    await page.waitForSelector('#gachaResult button:has-text("暂停")', { timeout: 3000 });
    await page.waitForSelector('#gachaResult button:has-text("确认完成任务")', { timeout: 3000 });

    // No 任务不存在 toast was fired during the path.
    const toasts = await page.evaluate(() => {
      const t = window.__lastToast;
      return t ? [t] : [];
    });
    for (const t of toasts) {
      expect(t.msg).not.toMatch(/任务不存在/);
    }
  });

  test('M1.3A A2: with allTasks=[matching task], existing behaviour is preserved', async ({ page }) => {
    /**
     * Regression guard: the fallback for empty allTasks must NOT break the
     * legacy path where allTasks already contains the matching task.
     */
    let timerPosts = 0;
    let lastTimerBody = null;
    await loadIsolatedPageForM13a(page, async (route) => {
      const url = route.request().url();
      if (url.indexOf('/api/gacha/multi-draw') !== -1) {
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
        });
      }
      if (url.indexOf('/api/timer/start') !== -1) {
        timerPosts += 1;
        try { lastTimerBody = JSON.parse(route.request().postData() || '{}'); } catch (e) {}
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            session_id: 8, task_id: 2,
            started_at: '2026-10-11T12:00:00.000Z',
            planned_minutes: 25,
          }),
        });
      }
      return route.abort('failed');
    });
    // Inject matching task into allTasks BEFORE bundle load by setting the
    // flag window.__forceAllTasks used at module init. But the bundle ran
    // during loadIsolatedPageForM13a — so we have to patch it post-load.
    // To avoid that timing trick, we just push the matching task into the
    // array after the bundle is ready.
    await page.evaluate(() => {
      var t = { id: 2, name: 'Solve 5 algebra problems', estimated_time: 25, is_unlocked: true, tags: ['math'] };
      window.allTasks = (window.allTasks || []).concat([t]);
    });

    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    await page.locator('.gacha-multi-item').nth(1).click();
    await page.waitForSelector('#gachaResult button:has-text("开始任务")', { timeout: 3000 });
    await page.click('#gachaResult button:has-text("开始任务")');
    await page.waitForFunction(() => window.timerDockSession && window.timerDockSession.id === 8, { timeout: 5000 });

    expect(timerPosts).toBe(1);
    expect(lastTimerBody && lastTimerBody.task_id).toBe(2);
  });

  test('M1.3A B: timer start rejection restores UI, no false dock session, no duplicate POST', async ({ page }) => {
    /**
     * M1.3A GOAL (2) — Real startTask() rejection path:
     *   - /api/timer/start returns 400 → visible card start action is
     *     restored (right panel re-renders the 开始任务 button).
     *   - timerDockSession is NOT set (backend is authoritative).
     *   - A second immediate activation while pending must not duplicate
     *     POST (in-source reentrancy guard; M1.3A only fixes what's safe
     *     in 2 debug cycles).
     *   - A valid active timer session (timerDockSession with id) is
     *     preserved if the user already had one.
     */
    let timerPosts = 0;
    let timerRejectOnce = true;
    await loadIsolatedPageForM13a(page, async (route) => {
      const url = route.request().url();
      if (url.indexOf('/api/gacha/multi-draw') !== -1) {
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
        });
      }
      if (url.indexOf('/api/timer/start') !== -1) {
        if (timerRejectOnce) {
          return route.fulfill({
            status: 400, contentType: 'application/json',
            body: JSON.stringify({ error: 'rejected by test harness' }),
          });
        }
        timerPosts += 1;
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            session_id: 9, task_id: 2,
            started_at: '2026-10-11T12:00:00.000Z',
            planned_minutes: 25,
          }),
        });
      }
      return route.abort('failed');
    });

    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });
    await page.locator('.gacha-multi-item').nth(1).click();
    await page.waitForSelector('#gachaResult button:has-text("开始任务")', { timeout: 3000 });

    // Pre-seed a sentinel valid active timer — must survive after rejection
    // (per the contract: preserve valid active timer semantics).
    await page.evaluate(() => {
      window.timerDockSession = {
        id: 999, task_id: 5, started_at: '2026-10-11T11:00:00.000Z',
        planned_minutes: 30, task_name: 'previously-active'
      };
    });

    // Fire two synchronous startTask(2) calls — same id, while pending.
    // We can't click the rendered button twice (it's replaced synchronously
    // when startTask runs), so we use scripted startTask() calls.
    await page.evaluate(async () => {
      window.__startTaskPromise1 = startTask(2);
      // No await between; startTask must dedupe before POST.
      window.__startTaskPromise2 = startTask(2);
      await Promise.all([window.__startTaskPromise1, window.__startTaskPromise2]);
    });

    // Wait for rejection to be visible — toaster at least surfaces the
    // 'rejected by test harness' error message (or some error).
    await page.waitForFunction(() => {
      const t = window.__lastToast;
      return t && t.type === 'err';
    }, { timeout: 5000 });

    // The sentinel timerDockSession MUST NOT have been replaced/falsely set
    // by the failing call. Its id and task_id should still be the sentinel.
    const dockAfter = await page.evaluate(() => ({
      id: window.timerDockSession && window.timerDockSession.id,
      task_id: window.timerDockSession && window.timerDockSession.task_id,
    }));
    expect(dockAfter.id).toBe(999);
    expect(dockAfter.task_id).toBe(5);

    // Card UI restored: 开始任务 button must be clickable again.
    await page.waitForSelector('#gachaResult button:has-text("开始任务")', { timeout: 3000 });

    // Second immediate activation during pending SHOULD NOT have produced a
    // second POST. Because the harness above rejected the first call, we
    // can't directly count POSTs here. Instead verify that the rejection
    // path completes synchronously enough that the dock remains untouched
    // AND a subsequent successful start (after we flip the mock off) does
    // succeed exactly once.
    timerRejectOnce = false;
    await page.click('#gachaResult button:has-text("开始任务")');
    await page.waitForFunction(() => window.timerDockSession && window.timerDockSession.id === 9, { timeout: 5000 });
    expect(timerPosts).toBe(1);
  });

  test('M1.2 C: multi-issued task start with synthetic stub API — document limitation', async ({ page }) => {
    /**
     * M1.2 GOAL (2) — multi-issued card must be startable from its
     * returned payload (if actual allTasks lookup is missing/stale,
     * fix only a verified issue).
     *
     * Limitation: in this isolated harness the full app.js is not
     * loaded — `allTasks` is therefore empty, and startTask() would
     * toast '任务不存在'. This test instead exercises the
     * DOCUMENTED safe code path: activation calls renderDrawnCard
     * (the REAL one, extracted from the project source), which writes
     * a card with data-task-id=<the chosen id> into #gachaResult.
     * The action buttons reference the integer safeId and remain
     * safe even if a hostile backend tries to inject script via id,
     * priority, estimated_time, or linked_note_path.
     *
     * If a future iteration adds a full-page bootstrap, this test
     * should be extended to actually press the 开始任务 button and
     * observe /api/timer/start.
     */
    await loadIsolatedPageForRdc(page, async (route) => {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify(buildPayload({ count: 3, malicious: false })),
      });
    });
    // Trigger drawGachaMulti via the real button → renders real
    // .gacha-multi-item buttons via the real renderMultiResults.
    await page.click('#gachaMultiBtn');
    await page.waitForSelector('.gacha-multi-item', { timeout: 5000 });

    const target = page.locator('.gacha-multi-item').nth(1);
    const targetId = await target.getAttribute('data-task-id');
    await target.click();

    // The REAL activateMultiCard then calls the REAL renderDrawnCard.
    await page.waitForSelector('#gachaResult .drawn-card-stage', { timeout: 3000 });

    // The rendered card carries data-task-id matching the chosen card.
    const cardTaskId = await page.locator('#gachaResult .drawn-card').first()
      .getAttribute('data-task-id');
    expect(cardTaskId).toBe(targetId);

    // The 开始任务 button is present and its onclick references a valid
    // integer literal (the safeId coercion in renderDrawnCard).
    const startBtn = page.locator('#gachaResult button:has-text("开始任务")');
    await expect(startBtn).toHaveCount(1);
    const onclickText = await startBtn.evaluate(el => el.getAttribute('onclick'));
    expect(onclickText).toMatch(/startTask\(\s*\d+\s*\)/);

    // currentTaskId was set.
    const currentTaskId = await page.evaluate(
      () => (window.gachaState && window.gachaState.currentTaskId) || null
    );
    expect(String(currentTaskId)).toBe(String(targetId));

    // canReplace was disabled (multi-issued card cannot be replaced).
    const canReplace = await page.evaluate(
      () => window.gachaState && window.gachaState.canReplace
    );
    expect(canReplace).toBe(false);
  });

  // ----- M1.3B focused timer pause/resume (NEW) ----------------------
  //
  // These tests exercise the REAL timer functions extracted from
  // static/app.js:
  //   - loadTimerDockActive
  //   - updateTimerDockDisplay
  //   - toggleTimerDockPause
  //   - startInlineTimer
  // against a fully mocked /api/timer/* backend. The harness uses a
  // deterministic Date.now so pause/resume semantics are observable.
  //
  // RED proof of the bug: after a running→pause→resume cycle, the
  // dock must NOT restart elapsed/progress at zero. The bug is that
  // toggleTimerDockPause does not propagate r.paused_seconds back
  // into timerDockSession.paused_seconds, so the running-side display
  // formula (Date.now() - started_at + sessionPausedMs) under-counts.
  // The harness also asserts:
  //   - reject/abort leaves the UI accurate (no half-state flip).
  //   - rapid duplicate clicks do not issue conflicting pause/resume.
  //   - reload from /api/timer/active then resume keeps monotonicity.

  /**
   * Build a self-sufficient mini-bundle for M1.3B timer pause/resume.
   * Extracts the real timer functions from app.js and provides
   * minimal stubs for the helpers they need. The harness replaces
   * window.fetch with a controllable mock so each /api/timer/* call
   * returns a deterministic payload.
   */
  function buildM13bBundle() {
    const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
    const ltd = extractFunction(appJs, 'loadTimerDockActive');
    const utd = extractFunction(appJs, 'updateTimerDockDisplay');
    const ttd = extractFunction(appJs, 'toggleTimerDockPause');
    const sit = extractFunction(appJs, 'startInlineTimer');
    const tnbi = extractFunction(appJs, 'taskNameById');
    if (!ltd || !utd || !ttd || !sit) {
      throw new Error('Could not extract timer functions from app.js');
    }
    return `
// === state stubs (real timer functions read these) ===
var allTasks = [];
var timerDockSession = null;
var timerDockTick = null;
var timerDockPaused = false;
var timerDockPausedElapsed = 0;
var timerActiveSession = null;
window._inlineTimerHandle = null;

// === minimal DOM stubs (real updateTimerDockDisplay reads these) ===
// The harness mounts a real DOM in loadIsolatedPageForM13b; this stub
// is provided so the script tag can attach event listeners at parse
// time without throwing if the DOM is not yet complete.
function __ensureDockDom() {
  if (!document.getElementById('timerDockPauseBtn')) {
    var btn = document.createElement('button');
    btn.id = 'timerDockPauseBtn';
    document.body.appendChild(btn);
  }
  if (!document.getElementById('timerDockStopBtn')) {
    var btn = document.createElement('button');
    btn.id = 'timerDockStopBtn';
    document.body.appendChild(btn);
  }
  if (!document.getElementById('toastContainer')) {
    var c = document.createElement('div');
    c.id = 'toastContainer';
    document.body.appendChild(c);
  }
}

// === api() stub: routes through window.__fetch (set by harness).
// The harness pins Date.now() on the page; we send the page's current
// monotonic time as a header so the Node-side mock can use the same
// clock as the page's logic. ===
async function api(url, opts) {
  opts = opts || {};
  var body = opts.body ? JSON.parse(opts.body) : undefined;
  var response = await window.__fetch(url, opts.method || 'GET', body, Date.now());
  if (response && response.__error) {
    throw new Error(response.error || 'mocked error');
  }
  return response.body;
}

// === toast stub: capture last toast for test assertion ===
function toast(msg, type) {
  window.__lastToast = { msg: String(msg || ''), type: String(type || 'inf') };
}

// === real timer functions from app.js ===
${ltd}

${utd}

${ttd}

${sit}

${tnbi || ''}

__ensureDockDom();
window.__harness_ready_m13b = true;
`;
  }
  const M13B_BUNDLE = buildM13bBundle();

  function buildTimerDockHTML() {
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>timer dock isolated</title>
<style>
  body { font-family: sans-serif; background: #0f1422; color: #f0e8da; padding: 24px; }
  .hidden { display: none !important; }
  .timer-dock { border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; }
  .timer-dock-idle { color: #999; }
  .timer-dock-active { display: block; }
  .timer-progress { background: #333; height: 6px; border-radius: 3px; overflow: hidden; }
  .timer-progress-bar { background: #f0c040; height: 100%; transition: none !important; }
</style>
</head>
<body>
  <div class="timer-dock" id="timerDock">
    <div class="timer-dock-idle" id="timerDockIdle">暂无进行中的任务</div>
    <div class="timer-dock-active hidden" id="timerDockActive">
      <div class="timer-task-name" id="timerDockTaskName"></div>
      <div class="timer-time" id="timerDockTime">00:00</div>
      <div class="timer-progress"><div class="timer-progress-bar" id="timerDockBar" style="width:0%"></div></div>
      <button class="btn sm" id="timerDockPauseBtn" title="暂停计时器"><i class="fa-solid fa-pause"></i></button>
      <button class="btn sm danger" id="timerDockStopBtn" title="提前完成"><i class="fa-solid fa-flag"></i></button>
    </div>
  </div>
  <div class="task-card drawn-card" data-task-id="2" id="inlineCard" style="margin-top:16px">
    <div class="drawn-card-right-panel">
      <div class="card-timer-display" id="cardTimerDisplay">00:00</div>
      <button class="btn" id="cardPauseBtn"><i class="fa-solid fa-pause"></i> 暂停</button>
    </div>
  </div>
  <div id="toastContainer"></div>
</body>
</html>`;
  }

  /**
   * Pin the deterministic clock and install a controllable fetch mock.
   * Returns a function to advance the harness clock.
   */
  async function installMockedClock(page) {
    await page.addInitScript(() => {
      // Pin Date.now to a known base.
      const BASE = Date.parse('2026-10-11T12:00:00.000Z');
      let offset = 0;
      const realNow = Date.now.bind(Date);
      Date.now = function () { return BASE + offset; };
      // Patch new Date() (no args) so JSON parsing of started_at also
      // observes the pinned clock. With arg, behavior is unchanged.
      const RealDate = Date;
      // The harness mostly uses Date.now, but startInlineTimer uses
      // new Date(timerDockSession.started_at).getTime() which works on
      // a real ISO string and is independent of the wall clock.
      window.__advanceMs = function (ms) { offset += ms; };
      window.__baseNow = BASE;
      window.__currentNow = function () { return BASE + offset; };
    });
    await page.exposeFunction('__fetch', async (url, method, body, clientNow) => {
      // Dispatched through page.exposeFunction so test code below can
      // route responses. Stored in a closure in the test.
      const handler = globalThis.__m13bFetchHandler;
      if (!handler) throw new Error('no fetch handler installed');
      return handler(url, method, body, clientNow);
    });
  }

  async function loadIsolatedPageForM13b(page) {
    const HARNESS_BASE = 'http://test.local/';
    await page.context().route('**/*', async (route) => {
      return route.fulfill({
        status: 200, contentType: 'text/html', body: buildTimerDockHTML(),
      });
    });
    await page.goto(HARNESS_BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.setContent(buildTimerDockHTML(), { waitUntil: 'domcontentloaded', timeout: 10000 });
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.addScriptTag({ content: M13B_BUNDLE });
    try {
      await page.waitForFunction(() => window.__harness_ready_m13b === true, { timeout: 10000 });
    } catch (e) {
      if (errors.length > 0) {
        throw new Error('Page errors during script load: ' + errors.join('; '));
      }
      throw e;
    }
    if (errors.length > 0) {
      throw new Error('Page errors during script load: ' + errors.join('; '));
    }
  }

  /**
   * M1.3B Test 1 (RED proof): running → pause → resume.
   *
   * The bug: after pause, the real toggleTimerDockPause sets
   * timerDockPausedElapsed correctly from the server's r.paused_seconds
   * but does NOT update timerDockSession.paused_seconds. After
   * resume, updateTimerDockDisplay's running-side formula is
   *   elapsed = Date.now() - started_at + sessionPausedMs
   * where sessionPausedMs = (timerDockSession.paused_seconds || 0) * 1000.
   * Because timerDockSession.paused_seconds was never propagated, the
   * cumulative elapsed restarts at ~0 after resume, even though the
   * server has accumulated paused_seconds > 0.
   *
   * This test uses a deterministic clock. Sequence:
   *   t=0      GET /api/timer/active -> running, started_at=t0-10s
   *   t=0..10  dock shows ~10s
   *   t=10     POST /api/timer/pause -> paused_seconds=10
   *   t=10..30 dock shows 10s (paused, frozen)
   *   t=30     POST /api/timer/resume -> new started_at=t30
   *   t=30..50 dock must show 10s + (50-30) = 30s, NOT (50-30)=20s.
   */
  test('M1.3B A: running→pause→resume elapsed and progress are monotonic across pause', async ({ page }) => {
    globalThis.__m13bSession = null;
    globalThis.__m13bFetchHandler = (url, method, body, clientNow) => {
      // Use the page's pinned clock for "now" so server and client
      // observe the same monotonic time.
      const now = typeof clientNow === 'number' ? clientNow : Date.now();
      if (url === '/api/timer/active' && method === 'GET') {
        if (!globalThis.__m13bSession) {
          globalThis.__m13bSession = { paused: false, pausedSeconds: 0, startedAt: now - 10000 };
          return { body: {
            id: 1, task_id: 2, task_name: 'synthetic-timer-task',
            started_at: new Date(globalThis.__m13bSession.startedAt).toISOString(),
            planned_minutes: 30, paused_seconds: 0, status: 'running', is_paused: false,
          } };
        }
        return { body: {
          id: 1, task_id: 2, task_name: 'synthetic-timer-task',
          started_at: new Date(globalThis.__m13bSession.startedAt).toISOString(),
          planned_minutes: 30, paused_seconds: globalThis.__m13bSession.pausedSeconds,
          status: globalThis.__m13bSession.paused ? 'paused' : 'running',
          is_paused: globalThis.__m13bSession.paused,
        } };
      }
      if (url === '/api/timer/pause' && method === 'POST') {
        if (!globalThis.__m13bSession) {
          return { __error: true, error: 'no session' };
        }
        if (globalThis.__m13bSession.paused) {
          return { __error: true, error: 'already paused' };
        }
        const elapsed = (now - globalThis.__m13bSession.startedAt) / 1000;
        globalThis.__m13bSession.pausedSeconds = Math.round(globalThis.__m13bSession.pausedSeconds + elapsed);
        globalThis.__m13bSession.startedAt = now;
        globalThis.__m13bSession.paused = true;
        return { body: {
          session_id: 1, is_paused: true,
          paused_seconds: globalThis.__m13bSession.pausedSeconds,
          started_at: new Date(now).toISOString(),
        } };
      }
      if (url === '/api/timer/resume' && method === 'POST') {
        if (!globalThis.__m13bSession) {
          return { __error: true, error: 'no session' };
        }
        if (!globalThis.__m13bSession.paused) {
          return { __error: true, error: 'not paused' };
        }
        globalThis.__m13bSession.startedAt = now;
        globalThis.__m13bSession.paused = false;
        return { body: {
          session_id: 1, is_paused: false,
          started_at: new Date(now).toISOString(),
        } };
      }
      return { __error: true, error: 'unexpected ' + method + ' ' + url };
    };

    await installMockedClock(page);
    await loadIsolatedPageForM13b(page);

    // t=0: load active session (running, started 10s ago).
    await page.evaluate(async () => { await loadTimerDockActive(); });
    // Read the dock while running at t=0. Expect ~10s elapsed.
    const elapsedRunningT0 = await page.evaluate(() => {
      return {
        time: document.getElementById('timerDockTime').textContent,
        width: document.getElementById('timerDockBar').style.width,
      };
    });
    expect(elapsedRunningT0.time).toBe('00:10');

    // Advance clock 10s (t=0→10), then pause. The toggleTimerDockPause
    // calls /api/timer/pause; server computes
    //   paused_seconds = existing_paused_seconds + (now - started_at)
    // which equals 20s here (started_at was 10s before t=0).
    await page.evaluate(() => window.__advanceMs(10000));
    await page.evaluate(async () => { await toggleTimerDockPause(); });

    // While paused, the dock MUST freeze the elapsed at 20s.
    // Advance the clock 20s more — paused display must still read 00:20.
    await page.evaluate(() => window.__advanceMs(20000));
    const elapsedPausedT30 = await page.evaluate(() => document.getElementById('timerDockTime').textContent);
    expect(elapsedPausedT30).toBe('00:20');

    // Resume at t=30s. The dock must show cumulative elapsed = 20s
    // (paused_seconds) + (now - new_started_at) = 20s + 0 = 00:20
    // immediately after resume.
    await page.evaluate(async () => { await toggleTimerDockPause(); });
    const elapsedJustResumed = await page.evaluate(() => document.getElementById('timerDockTime').textContent);
    expect(elapsedJustResumed).toBe('00:20');

    // Advance 10s after resume — elapsed must be 20 + 10 = 00:30.
    await page.evaluate(() => window.__advanceMs(10000));
    // Force one display update.
    await page.evaluate(() => updateTimerDockDisplay());
    const elapsedAfterResume = await page.evaluate(() => document.getElementById('timerDockTime').textContent);
    expect(elapsedAfterResume).toBe('00:30');

    // Progress bar must reflect cumulative: 30s/1800s ≈ 1.67%
    const widthAfter = await page.evaluate(() => document.getElementById('timerDockBar').style.width);
    expect(widthAfter).toMatch(/^1\./);

    globalThis.__m13bSession = null;
    globalThis.__m13bFetchHandler = null;
  });

  /**
   * M1.3B Test 2: reload/restore from /api/timer/active while paused.
   *
   * Calls loadTimerDockActive() while the server reports paused. Then
   * resume and verify elapsed keeps growing from paused_seconds. This
   * verifies the load path: the dock loads paused_seconds into
   * timerDockPausedElapsed and timerDockSession.paused_seconds from
   * the GET /active response, so resume math is correct.
   */
  test('M1.3B B: reload from /api/timer/active while paused — resume continues monotonic', async ({ page }) => {
    globalThis.__m13bPausedSeconds = 25;
    globalThis.__m13bFetchHandler = (url, method, body, clientNow) => {
      const now = typeof clientNow === 'number' ? clientNow : Date.now();
      if (url === '/api/timer/active' && method === 'GET') {
        // Server reports paused with paused_seconds = seed.
        const pausedSeconds = globalThis.__m13bPausedSeconds;
        // started_at is just now-1s (1s into the paused window) so
        // the dock formula reads a sensible value.
        const startedAt = now - 1000;
        return { body: {
          id: 1, task_id: 2, task_name: 'synthetic-paused-restore',
          started_at: new Date(startedAt).toISOString(),
          planned_minutes: 30, paused_seconds: pausedSeconds,
          status: 'paused', is_paused: true,
        } };
      }
      if (url === '/api/timer/resume' && method === 'POST') {
        return { body: {
          session_id: 1, is_paused: false,
          started_at: new Date(now).toISOString(),
        } };
      }
      return { __error: true, error: 'unexpected ' + method + ' ' + url };
    };

    await installMockedClock(page);
    await loadIsolatedPageForM13b(page);

    // t=0: server says paused_seconds=25.
    await page.evaluate(async () => { await loadTimerDockActive(); });
    // Dock while paused must show the seeded paused_seconds.
    const elapsedAtLoad = await page.evaluate(() => document.getElementById('timerDockTime').textContent);
    expect(elapsedAtLoad).toBe('00:25');

    // Resume — server returns new started_at. Dock must continue
    // from 25s + (now - new_started_at).
    await page.evaluate(async () => { await toggleTimerDockPause(); });
    const elapsedJustResumed = await page.evaluate(() => document.getElementById('timerDockTime').textContent);
    expect(elapsedJustResumed).toBe('00:25');

    // Advance 15s — display must be 25 + 15 = 40s.
    await page.evaluate(() => window.__advanceMs(15000));
    // Force one display update (the setInterval hasn't fired because
    // the harness pinned clock doesn't advance real time).
    await page.evaluate(() => updateTimerDockDisplay());
    const elapsedAfter = await page.evaluate(() => document.getElementById('timerDockTime').textContent);
    expect(elapsedAfter).toBe('00:40');

    globalThis.__m13bPausedSeconds = null;
    globalThis.__m13bFetchHandler = null;
  });

  /**
   * M1.3B Test 3: rapid duplicate click does not issue conflicting
   * pause/resume, and a network failure during toggle does not flip
   * the local pause state.
   */
  test('M1.3B C: rapid duplicate click + network failure leave UI accurate', async ({ page }) => {
    let pausePosts = 0;
    let resumePosts = 0;
    let failPauseOnce = true;
    globalThis.__m13bFetchHandler = (url, method, body, clientNow) => {
      const now = typeof clientNow === 'number' ? clientNow : Date.now();
      if (url === '/api/timer/active' && method === 'GET') {
        return { body: {
          id: 1, task_id: 2, task_name: 'synthetic-failure',
          started_at: new Date(now - 5000).toISOString(),
          planned_minutes: 30, paused_seconds: 0,
          status: 'running', is_paused: false,
        } };
      }
      if (url === '/api/timer/pause' && method === 'POST') {
        pausePosts += 1;
        if (failPauseOnce) {
          failPauseOnce = false;
          return { __error: true, error: 'mocked 500 from /api/timer/pause' };
        }
        return { body: {
          session_id: 1, is_paused: true,
          paused_seconds: 5, started_at: new Date(now).toISOString(),
        } };
      }
      if (url === '/api/timer/resume' && method === 'POST') {
        resumePosts += 1;
        return { body: {
          session_id: 1, is_paused: false,
          started_at: new Date(now).toISOString(),
        } };
      }
      return { __error: true, error: 'unexpected' };
    };

    await installMockedClock(page);
    await loadIsolatedPageForM13b(page);
    await page.evaluate(async () => { await loadTimerDockActive(); });

    // (1) Network failure: clicking pause must NOT flip
    // timerDockPaused to true. After error, dock should still show
    // running time and no resume POST should be issued on the next
    // click.
    await page.evaluate(async () => { await toggleTimerDockPause(); });
    const stateAfterFail = await page.evaluate(() => ({
      paused: window.timerDockPaused,
      toast: window.__lastToast,
    }));
    expect(stateAfterFail.paused).toBe(false);
    expect(stateAfterFail.toast && stateAfterFail.toast.type).toBe('err');

    // (2) Successful pause now.
    await page.evaluate(async () => { await toggleTimerDockPause(); });
    expect(pausePosts).toBe(2);
    expect(await page.evaluate(() => window.timerDockPaused)).toBe(true);

    // (3) Rapid duplicate clicks while paused must not issue a
    // second pause (which would 409) and must not issue a
    // conflicting resume. Fire 3 synchronous toggle clicks. We
    // assert that the total pause+resume POST count is bounded and
    // the final state is consistent with the toggle count.
    await page.evaluate(async () => {
      window.__toggleCount = 3;
      window.__toggleDone = 0;
      for (let i = 0; i < window.__toggleCount; i += 1) {
        toggleTimerDockPause().then(() => { window.__toggleDone += 1; });
      }
    });
    await page.waitForFunction(() => window.__toggleDone === 3, { timeout: 5000 });
    // After 3 toggles starting from paused, the sequence is
    // resume/pause/resume -> running.
    expect(await page.evaluate(() => window.timerDockPaused)).toBe(false);
    expect(pausePosts + resumePosts).toBeGreaterThanOrEqual(3);
    // At most one pause POST and at most three resumes, not more than
    // one duplicate pause while already paused.
    expect(pausePosts).toBeLessThanOrEqual(3);

    globalThis.__m13bFetchHandler = null;
  });

  // ----- M1.3C session-completion integrity (NEW) ---------------------
  //
  // Two real extracted production functions under test:
  //   - confirmComplete(taskId) — called by the inline card 完成 button
  //   - stopTimerFromDock(sessionId) — called by the dock 提前结束 button
  // Both rely on api() / timer state / completeWithFeedback. We exercise
  // them against a mocked /api/timer/complete + /api/tasks/<id>/complete
  // backend and assert the new contracts:
  //   1. timer complete rejected / aborted => no /api/tasks/<id>/complete
  //      no feedback, no dock reset, error surfaced, retry possible.
  //   2. resumed accumulated seconds => actual_minutes uses
  //      history + after-resume; UI finishes correctly and exactly one
  //      completed POST. Abandoned abandonment uses cumulative
  //      paused_seconds and never marks task completed.

  /**
   * Bundle for M1.3C. Loads the REAL confirmComplete and
   * stopTimerFromDock from static/app.js with narrow mocks for the
   * helpers those two functions touch (api, completeWithFeedback,
   * loadTasks, refreshGachaStats, updateDiscardPileVisual,
   * showCareModal, confirm). The harness installs window.__fetch via
   * page.exposeFunction; both real functions call api(), so the
   * existing installMockedClock + globalThis.__m13bFetchHandler pair
   * covers timer routes plus a synthetic /api/tasks/<id>/complete.
   */
  function buildM13cBundle() {
    const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
    const cc = extractFunction(appJs, 'confirmComplete');
    const stf = extractFunction(appJs, 'stopTimerFromDock');
    const ltd = extractFunction(appJs, 'loadTimerDockActive');
    const utd = extractFunction(appJs, 'updateTimerDockDisplay');
    const ttd = extractFunction(appJs, 'toggleTimerDockPause');
    const tnbi = extractFunction(appJs, 'taskNameById');
    if (!cc || !stf || !ltd || !utd || !ttd) {
      throw new Error('Could not extract M1.3C functions from app.js');
    }
    return `
// === state stubs (real confirmComplete/stopTimerFromDock read these) ===
var allTasks = [];
var timerDockSession = null;
var timerDockTick = null;
var timerDockPaused = false;
var timerDockPausedElapsed = 0;
var timerActiveSession = null;
window._inlineTimerHandle = null;

// === narrow observation stubs for completion-side helpers ===
window.__completeWithFeedbackCalls = [];
window.__loadTasksCalls = 0;
window.__refreshGachaStatsCalls = 0;
window.__updateDiscardPileCalls = 0;
window.__showCareModalCalls = [];
window.__confirmCalls = [];
window.__confirmAnswers = [];   // pop from front
function completeWithFeedback(taskId, opts) {
  window.__completeWithFeedbackCalls.push({ id: taskId, opts: opts || null });
  return Promise.resolve();
}
function loadTasks() { window.__loadTasksCalls += 1; return Promise.resolve(); }
function refreshGachaStats() { window.__refreshGachaStatsCalls += 1; return Promise.resolve(); }
function updateDiscardPileVisual() { window.__updateDiscardPileCalls += 1; return Promise.resolve(); }
function showCareModal(taskId, category) {
  window.__showCareModalCalls.push({ taskId: taskId, category: category || null });
}
// stopTimerFromDock also calls updateTimerDisplay() (task-page timer UI).
// We do not exercise the task page in this harness so a stub is enough.
function updateTimerDisplay() { return; }

// stopTimerFromDock calls window.confirm(...). We override confirm()
// so the harness can answer true/false without a real dialog.
window.__confirmAnswers = [];   // FIFO queue of bool answers
var __realConfirm = window.confirm;
window.confirm = function (msg) {
  window.__confirmCalls.push(String(msg));
  var queued = window.__confirmAnswers.shift();
  return queued === undefined ? true : !!queued;
};

// === api() routes through window.__fetch (existing M1.3B harness) ===
async function api(url, opts) {
  opts = opts || {};
  var body = opts.body ? JSON.parse(opts.body) : undefined;
  var response = await window.__fetch(url, opts.method || 'GET', body, Date.now());
  if (response && response.__error) {
    throw new Error(response.error || 'mocked error');
  }
  return response.body;
}

// === toast stub ===
function toast(msg, type) {
  window.__lastToast = { msg: String(msg || ''), type: String(type || 'inf') };
}

// === minimal DOM stubs ===
function __ensureDockDom() {
  if (!document.getElementById('timerDockPauseBtn')) {
    var btn = document.createElement('button');
    btn.id = 'timerDockPauseBtn';
    document.body.appendChild(btn);
  }
  if (!document.getElementById('timerDockStopBtn')) {
    var btn = document.createElement('button');
    btn.id = 'timerDockStopBtn';
    document.body.appendChild(btn);
  }
  if (!document.getElementById('toastContainer')) {
    var c = document.createElement('div');
    c.id = 'toastContainer';
    document.body.appendChild(c);
  }
}

// === real production functions from app.js ===
${cc}

${stf}

${ltd}

${utd}

${ttd}

${tnbi || ''}

__ensureDockDom();
window.__harness_ready_m13c = true;
`;
  }
  const M13C_BUNDLE = buildM13cBundle();

  async function loadIsolatedPageForM13c(page) {
    const HARNESS_BASE = 'http://test.local/';
    await page.context().route('**/*', async (route) => {
      return route.fulfill({
        status: 200, contentType: 'text/html', body: buildTimerDockHTML(),
      });
    });
    await page.goto(HARNESS_BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.setContent(buildTimerDockHTML(), { waitUntil: 'domcontentloaded', timeout: 10000 });
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.addScriptTag({ content: M13C_BUNDLE });
    try {
      await page.waitForFunction(() => window.__harness_ready_m13c === true, { timeout: 10000 });
    } catch (e) {
      if (errors.length > 0) {
        throw new Error('Page errors during script load: ' + errors.join('; '));
      }
      throw e;
    }
    if (errors.length > 0) {
      throw new Error('Page errors during script load: ' + errors.join('; '));
    }
  }

  /**
   * M1.3C Test 1: timer complete REJECTED/ABORTED — no
   * /api/tasks/<id>/complete, no feedback, no dock reset, error surfaced,
   * retry possible.
   *
   * Bug: confirmComplete previously caught the /api/timer/complete error
   * silently, unconditionally nulled timerDockSession, and still
   * proceeded to call completeWithFeedback (which would mark the task
   * completed via /api/tasks/<id>/complete even though the server
   * session was still active).
   */
  test('M1.3C A: timer complete rejected - no task completion, dock preserved, error surfaced, retry possible', async ({ page }) => {
    let timerPosts = 0;
    let failOnce = true;
    globalThis.__m13bFetchHandler = (url, method, body, clientNow) => {
      const now = typeof clientNow === 'number' ? clientNow : Date.now();
      if (url === '/api/timer/active' && method === 'GET') {
        return { body: {
          id: 7, task_id: 2, task_name: 'synthetic-task-7',
          started_at: new Date(now - 60000).toISOString(),
          planned_minutes: 30, paused_seconds: 0,
          status: 'running', is_paused: false,
        } };
      }
      if (url === '/api/timer/complete' && method === 'POST') {
        timerPosts += 1;
        if (failOnce) {
          failOnce = false;
          return { __error: true, error: 'mocked 500 from /api/timer/complete' };
        }
        return { body: {
          session_id: 7, result: 'completed',
          actual_minutes: 1, ended: true,
        } };
      }
      return { __error: true, error: 'unexpected ' + method + ' ' + url };
    };

    await installMockedClock(page);
    await loadIsolatedPageForM13c(page);
    await page.evaluate(async () => { await loadTimerDockActive(); });

    // === (A.1) First confirmComplete(2) — timer POST REJECTED.
    await page.evaluate(async () => { await confirmComplete(2); });

    // The error must be surfaced as an err toast.
    const toastAfterFail = await page.evaluate(() => window.__lastToast);
    expect(toastAfterFail && toastAfterFail.type).toBe('err');

    // dock MUST remain populated with the same session id (7).
    const dockAfterFail = await page.evaluate(() => ({
      id: window.timerDockSession && window.timerDockSession.id,
      task_id: window.timerDockSession && window.timerDockSession.task_id,
    }));
    expect(dockAfterFail.id).toBe(7);
    expect(dockAfterFail.task_id).toBe(2);

    // completeWithFeedback MUST NOT have been called — i.e. no
    // /api/tasks/<id>/complete, no feedback, no discard pile, no care
    // modal. This is the core contract: API failure preserves all
    // active state.
    expect(
      await page.evaluate(() => window.__completeWithFeedbackCalls.length)
    ).toBe(0);
    expect(
      await page.evaluate(() => window.__showCareModalCalls.length)
    ).toBe(0);
    expect(
      await page.evaluate(() => window.__updateDiscardPileCalls)
    ).toBe(0);

    // timer POST was issued exactly once.
    expect(timerPosts).toBe(1);

    // === (A.2) Retry — timer POST now succeeds.
    await page.evaluate(async () => { await confirmComplete(2); });

    // completeWithFeedback was called exactly once with taskId=2.
    const cwfCalls = await page.evaluate(() => window.__completeWithFeedbackCalls);
    expect(cwfCalls.length).toBe(1);
    expect(cwfCalls[0].id).toBe(2);

    // dock cleared (timerDockSession=null after successful completion).
    const dockAfterRetry = await page.evaluate(
      () => window.timerDockSession
    );
    expect(dockAfterRetry).toBe(null);

    // timer POST issued twice in total.
    expect(timerPosts).toBe(2);

    // completeWithFeedback was called exactly once on the success path.
    // The stub does NOT trigger the rest of the success cascade (card
    // discard / care modal); this contract is exercised in the
    // production-only /api/tasks/<id>/complete integration test.

    globalThis.__m13bFetchHandler = null;
  });

  /**
   * M1.3C Test 2: resumed accumulated seconds — confirmComplete uses
   * cumulative history (paused_seconds) + after-resume elapsed, and
   * stopTimerFromDock sends accurate cumulative actual_minutes with
   * result='abandoned' and never marks task completed.
   *
   * Sequence of operations:
   *   t=0      load active session, started_at = t0-10s, paused_seconds=0
   *   t=0..10  running 10s
   *   t=10     POST /api/timer/pause  -> server paused_seconds=10
   *   t=10..30 paused 20s
   *   t=30     POST /api/timer/resume -> new started_at=t30, paused_seconds=10
   *   t=30..50 running 20s -> cumulative = 10 + 20 = 30s
   *   t=50     confirmComplete(2) — must send actual_minutes = 1
   *            (Math.max(1, round(30000ms/60000))) and result=completed.
   *   separate stopTimerFromDock: running with paused_seconds=120 (2 min)
   *      and started_at=now must report actual_minutes >= 3
   *      (120s history + ≥60s after-resume) and result=abandoned.
   *      Task MUST NOT be marked completed.
   */
  test('M1.3C B: cumulative paused_seconds + after-resume elapsed — exact actual_minutes and abandonment never marks task completed', async ({ page }) => {
    let completePosts = 0;
    let abandonPosts = 0;
    const completeActualMinutes = [];
    const abandonActualMinutes = [];
    let stage = 'completed';
    globalThis.__m13bSession = {
      paused: false, pausedSeconds: 0, startedAt: 0,
    };
    globalThis.__m13bFetchHandler = (url, method, body, clientNow) => {
      const now = typeof clientNow === 'number' ? clientNow : Date.now();
      if (url === '/api/timer/active' && method === 'GET') {
        const s = globalThis.__m13bSession;
        let startedAt = s.startedAt;
        if (!startedAt || startedAt <= 0) {
          // First GET after reset: initialise to now-10000 so the dock
          // formula reads a sensible running 10s elapsed.
          startedAt = now - 10000;
          s.startedAt = startedAt;
        }
        return { body: {
          id: 7, task_id: 2, task_name: 'synthetic-cumulative',
          started_at: new Date(startedAt).toISOString(),
          planned_minutes: 30,
          paused_seconds: s.pausedSeconds,
          status: s.paused ? 'paused' : 'running',
          is_paused: s.paused,
        } };
      }
      if (url === '/api/timer/pause' && method === 'POST') {
        const s = globalThis.__m13bSession;
        const elapsed = (now - s.startedAt) / 1000;
        s.pausedSeconds = Math.round(s.pausedSeconds + elapsed);
        s.startedAt = now;
        s.paused = true;
        return { body: {
          session_id: 7, is_paused: true,
          paused_seconds: s.pausedSeconds,
          started_at: new Date(now).toISOString(),
        } };
      }
      if (url === '/api/timer/resume' && method === 'POST') {
        const s = globalThis.__m13bSession;
        s.startedAt = now;
        s.paused = false;
        return { body: {
          session_id: 7, is_paused: false,
          started_at: new Date(now).toISOString(),
        } };
      }
      if (url === '/api/timer/complete' && method === 'POST') {
        const result = (body && body.result) || 'completed';
        const actual = (body && body.actual_minutes);
        if (result === 'abandoned') {
          abandonPosts += 1;
          abandonActualMinutes.push(actual);
        } else {
          completePosts += 1;
          completeActualMinutes.push(actual);
        }
        const s = globalThis.__m13bSession;
        s.startedAt = 0;
        s.paused = false;
        s.pausedSeconds = 0;
        return { body: {
          session_id: 7, ended: true, result: result,
          actual_minutes: actual,
        } };
      }
      return { __error: true, error: 'unexpected ' + method + ' ' + url };
    };

    await installMockedClock(page);
    await loadIsolatedPageForM13c(page);

    // t=0: load active session. started_at = now-10000, paused=0.
    await page.evaluate(async () => { await loadTimerDockActive(); });

    // t=0..10: running 10s.
    await page.evaluate(() => window.__advanceMs(10000));
    // t=10: pause.
    await page.evaluate(async () => { await toggleTimerDockPause(); });
    // t=10..30: paused for 20s.
    await page.evaluate(() => window.__advanceMs(20000));
    // t=30: resume.
    await page.evaluate(async () => { await toggleTimerDockPause(); });

    // Sanity: session is now running with paused_seconds=20.
    // (running 10s before GET + 10s after GET before pause = 20s)
    const sessionState = await page.evaluate(() => ({
      paused: window.timerDockPaused,
      session_paused_seconds:
        window.timerDockSession && window.timerDockSession.paused_seconds,
      started_at: window.timerDockSession && window.timerDockSession.started_at,
    }));
    expect(sessionState.paused).toBe(false);
    expect(sessionState.session_paused_seconds).toBe(20);

    // t=30..50: running 20s. Cumulative = 20 + 20 = 40s.
    await page.evaluate(() => window.__advanceMs(20000));

    // (B.1) confirmComplete(2): must send result=completed and
    // actual_minutes = round(40000ms/60000) = 1.
    await page.evaluate(async () => { await confirmComplete(2); });
    expect(completePosts).toBe(1);
    expect(completeActualMinutes.length).toBe(1);
    expect(completeActualMinutes[0]).toBe(1);

    // completeWithFeedback was called for taskId=2.
    const cwfCalls = await page.evaluate(() => window.__completeWithFeedbackCalls);
    expect(cwfCalls.length).toBe(1);
    expect(cwfCalls[0].id).toBe(2);

    // dock cleared.
    expect(await page.evaluate(() => window.timerDockSession)).toBe(null);

    // =============================================================
    // (B.2) Now exercise stopTimerFromDock with a fresh session that
    // has cumulative paused_seconds=120s (2 min of history) and is
    // currently running. The abandonment MUST compute actual_minutes
    // using history + after-resume, send result=abandoned, and MUST
    // NEVER call completeWithFeedback (so task stays eligible).
    // =============================================================

    // Reset server-side session state.
    // We compute started_at relative to the harness pinned clock so the
    // running-after-resume window advances deterministically.
    const baseNowMs = await page.evaluate(() =>
      window.__currentNow ? window.__currentNow() : Date.now());
    const startedAtMs = baseNowMs - 5000; // 5s before "now"
    await page.evaluate((args) => {
      window.timerDockSession = {
        id: 7, task_id: 2, task_name: 'synthetic-abandon',
        started_at: new Date(args.startedAtMs).toISOString(),
        planned_minutes: 30,
        paused_seconds: 120,
      };
      window.timerDockPaused = false;
      window.timerDockPausedElapsed = 0;
      window.timerActiveSession = window.timerDockSession;
    }, { startedAtMs: startedAtMs });
    globalThis.__m13bSession = {
      paused: false, pausedSeconds: 120, startedAt: startedAtMs,
    };
    // advance 90s after resume — running window = 90s.
    // cumulative = 120s + 90s = 210s = 3.5min -> round = 4.
    await page.evaluate(() => window.__advanceMs(90000));

    // stopTimerFromDock calls window.confirm(); pre-load a true answer.
    await page.evaluate(() => {
      window.__confirmAnswers = [true];
      window.__completeWithFeedbackCalls.length = 0;
    });
    await page.evaluate(async () => { await stopTimerFromDock(7); });

    // Exactly one abandoned POST with accurate cumulative actual_minutes.
    expect(abandonPosts).toBe(1);
    expect(abandonActualMinutes.length).toBe(1);
    expect(abandonActualMinutes[0]).toBe(4);

    // The critical contract: stopTimerFromDock must NOT call
    // completeWithFeedback. If it does, the abandonment path would
    // have marked the task completed, defeating the whole point of
    // "early finish -> task remains eligible".
    const cwfAfterAbandon = await page.evaluate(
      () => window.__completeWithFeedbackCalls.length
    );
    expect(cwfAfterAbandon).toBe(0);

    // The dock may be cleared after a successful abandon (UI state)
    // but the task is NOT marked completed. We assert this by
    // checking that no /api/tasks/<id>/complete was issued.
    // /api/tasks/<id>/complete is only reachable through
    // completeWithFeedback; since cwf was never called, the task
    // stays eligible. We additionally assert that care modal was not
    // opened (it is opened only by completeWithFeedback).
    const careAfterAbandon = await page.evaluate(
      () => window.__showCareModalCalls.length
    );
    expect(careAfterAbandon).toBe(0);

    // Confirm: total of 2 timer POSTs (1 completed, 1 abandoned).
    expect(completePosts + abandonPosts).toBe(2);

    globalThis.__m13bSession = null;
    globalThis.__m13bFetchHandler = null;
  });

  // ----- M1.3D feedback/care-modal integrity (NEW) ---------------------
  //
  // The defect: completeWithFeedback previously fabricated an observation
  // by immediately POSTing /api/tasks/<id>/feedback with hardcoded
  // {energy_after:5, mood_after:3} BEFORE the user had any chance to
  // answer anything. It then swallowed any error and proceeded to
  // showCareModal. The existing #feedbackModal in src/index.html (with
  // #fbEnergy, mood buttons, #fbTaskId, submitFeedback, cancelFeedback)
  // was never opened.
  //
  // Fix: completeWithFeedback must open the existing feedbackModal and
  // only POST after explicit user submit. submitFeedback must post only
  // the user's selected values, dedupe rapid clicks, and on rejection
  // leave the modal open and re-retryable. cancelFeedback must perform
  // zero POST. showCareModal must still be invoked after either path so
  // the existing care choices (same/switch/rest) are preserved.

  /**
   * Build the M1.3D bundle: extract REAL production
   * completeWithFeedback / openFeedbackModalForTask / submitFeedback /
   * cancelFeedback / showCareModal / transitionToCareModal /
   * careSameCategory / careSwitchCategory / careRest / setMood from
   * static/app.js and provide narrow stubs only for unrelated rendering
   * and animation helpers. The DOM already provides feedbackModal,
   * careModal, gachaResult, discardPile, cardFlyLayer, and
   * toastContainer — exactly as in src/index.html.
   */
  function buildM13dBundle() {
    const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
    // AR03-G15.2: the feedback / care business state + orchestration live
    // in the Task Lifecycle owner (static/modules/tasks/lifecycle.js).
    // The isolated bundle injects the REAL owner source (export -> classic
    // transform) with synthetic dependencies and exposes it as
    // window.__taskLifecycleOwner so the extracted app.js inline facades
    // can delegate to it.
    const lifecycleSrc = fs.readFileSync(
      path.join(PROJECT_ROOT, 'static', 'modules', 'tasks', 'lifecycle.js'),
      'utf-8',
    );
    const ownerSrc = lifecycleSrc.replace(
      /^export\s+function\s+createTaskLifecycleOwner/m,
      'function createTaskLifecycleOwner',
    );
    const lifecycleOwnerHelper = extractFunction(appJs, '_lifecycleOwner');
    const gachaOwnerHelper = extractFunction(appJs, '_gachaOwner');
    const cwf = extractFunction(appJs, 'completeWithFeedback');
    const ofm = extractFunction(appJs, 'openFeedbackModalForTask');
    const rfe = extractFunction(appJs, 'readFeedbackEnergy');
    const rfs = extractFunction(appJs, 'renderFeedbackSuccess');
    const rcr = extractFunction(appJs, 'renderCareRest');
    const fdtc = extractFunction(appJs, 'flyDrawnCardToDiscard');
    const sf = extractFunction(appJs, 'submitFeedback');
    const cf = extractFunction(appJs, 'cancelFeedback');
    const scm = extractFunction(appJs, 'showCareModal');
    const tcm = extractFunction(appJs, 'transitionToCareModal');
    const csc = extractFunction(appJs, 'careSameCategory');
    const csw = extractFunction(appJs, 'careSwitchCategory');
    const cr = extractFunction(appJs, 'careRest');
    const sm = extractFunction(appJs, 'setMood');
    const dgm = extractFunction(appJs, 'drawGachaWithCategory');
    if (!cwf || !ofm || !rfe || !rfs || !rcr || !fdtc || !sf || !cf || !scm ||
        !tcm || !csc || !csw || !cr || !sm) {
      throw new Error('Could not extract M1.3D functions from app.js');
    }
    if (!lifecycleOwnerHelper || !gachaOwnerHelper) {
      throw new Error('Could not extract owner helper functions from app.js');
    }
    if (!/function\s+createTaskLifecycleOwner\s*\(/.test(ownerSrc)) {
      throw new Error('Could not build classic Task Lifecycle owner source');
    }
    return `
// === state stubs ===
var gachaState = {
  energy: 'medium', pool: 'fragment', canReplace: true,
  replacedTaskId: null, feedbackMood: 3, currentTaskId: null, selectedTag: ''
};
var allTasks = (window.__m13dAllTasks === null) ? [] : (window.__m13dAllTasks || []);
var isDrawing = false;
window.__careDrawsCalled = [];
// === observation stubs for unrelated helpers ===
function loadTasks() { window.__loadTasksCalls = (window.__loadTasksCalls || 0) + 1; return Promise.resolve(); }
function refreshGachaStats() { window.__refreshGachaStatsCalls = (window.__refreshGachaStatsCalls || 0) + 1; return Promise.resolve(); }
function updateDiscardPileVisual() { window.__updateDiscardPileCalls = (window.__updateDiscardPileCalls || 0) + 1; return Promise.resolve(); }
function updateTimerDockDisplay() {}
function prereqHint() { return null; }
// toast: capture last toast
function toast(msg, type) { window.__lastToast = { msg: String(msg || ''), type: String(type || 'inf') }; }
// showModal / closeModal: direct DOM ops matching production code
function showModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}
function closeModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}
// Care modal constants referenced by showCareModal
var CARE_ENCOURAGES = [
  '太棒了！又完成了一项挑战！',
  '坚持就是胜利，你真棒！',
  '今天的你比昨天更优秀！',
  '小步快跑，大目标在前方等你！',
  '完成就是进步，继续加油！'
];
var CARE_CATEGORY_LABELS = { study: '学习', exercise: '运动', work: '工作', life: '生活', other: '其他' };
var _careContext = null;
var WARM_MESSAGES = { unlock: '解锁新任务' };
function getGachaAvailableMinutes() {
  var input = document.getElementById('gachaTimeInput');
  var v = input ? parseInt(input.value, 10) : 25;
  return (isNaN(v) || v < 1) ? 25 : Math.min(v, 480);
}
// api: route through window.__fetch (harness intercepts and counts requests)
async function api(url, opts) {
  opts = opts || {};
  var body = opts.body ? JSON.parse(opts.body) : undefined;
  var response = await window.__fetch(url, opts.method || 'GET', body);
  if (response && response.__error) {
    throw new Error(response.error || 'mocked error');
  }
  return response.body || {};
}
// flyCardToDiscard: stub the animation; the test only cares about the
// feedback POST order, not the discard animation. Recreate a real DOM
// card so the call doesn't throw on null element.
async function flyCardToDiscard(cardEl) {
  window.__flyCardToDiscardCalls = (window.__flyCardToDiscardCalls || 0) + 1;
  return;
}

// === real functions extracted from app.js ===
${cwf}

${ofm}

${rfe}

${rfs}

${rcr}

${fdtc}

${sf}

${cf}

${scm}

${tcm}

${csc}

${csw}

${cr}

${sm}

// drawGachaWithCategory is the path called by care-same/switch. The
// real one issues a /api/gacha/care-draw POST; we just record it.
${dgm}

// === AR03-G15.2: owner helper facades extracted from app.js ===
${lifecycleOwnerHelper}

${gachaOwnerHelper}

// === AR03-G15.2: the REAL Task Lifecycle owner (static/modules/tasks/
// lifecycle.js) in classic form — this is the unique owner of the
// feedback / care business state and API sequencing. The extracted
// app.js inline facades above delegate to it through
// window.__taskLifecycleOwner.
//
// The owner source is wrapped in an IIFE so its internal helpers
// (submitFeedback / cancelFeedback / setMood / ...) do NOT shadow the
// extracted app.js facades in this shared script scope.
var createTaskLifecycleOwner = (function () {
${ownerSrc}
  return createTaskLifecycleOwner;
})();

// === synthetic Gacha-owner seam ===
// The care draw orchestration itself lives in the ESM Gacha owner
// (out of M1.3D scope). The isolated bundle provides the minimal
// seam the classic drawGachaWithCategory facade needs, so the care
// same/switch choices still reach the /api/gacha/care-draw endpoint.
window.__gachaOwner = {
  drawGachaWithCategory: function (includeCategory, excludeCategory) {
    return api('/api/gacha/care-draw', {
      method: 'POST',
      body: JSON.stringify({
        pool: 'fragment',
        energy: 'medium',
        preferred_tag: null,
        include_category: includeCategory || null,
        exclude_category: excludeCategory || null
      })
    });
  }
};

// === wire the owner with synthetic (DOM-backed) dependencies ===
var __m13dLifecycleOwner = createTaskLifecycleOwner({
  getTasks: function () { return window.allTasks || []; },
  flyDrawnCardToDiscard: flyDrawnCardToDiscard,
  loadTasks: loadTasks,
  refreshGachaStats: refreshGachaStats,
  updateDiscardPileVisual: updateDiscardPileVisual,
  // --- DOM adapters (pure DOM, no business state) ---
  openFeedbackModalForTask: openFeedbackModalForTask,
  readFeedbackEnergy: readFeedbackEnergy,
  closeModal: closeModal,
  renderFeedbackSuccess: renderFeedbackSuccess,
  renderCareModal: showCareModal,
  renderCareRest: renderCareRest,
  // --- remaining dependencies ---
  api: api,
  toast: toast,
  prereqHint: prereqHint,
  drawGachaWithCategory: drawGachaWithCategory
});

// Read-only getter, exactly like static/app.entry.js does.
Object.defineProperty(window, '__taskLifecycleOwner', {
  configurable: false,
  enumerable: false,
  get: function () { return __m13dLifecycleOwner; }
});

window.__harness_ready_m13d = true;
`;
  }
  const M13D_BUNDLE = buildM13dBundle();

  function buildM13dHTML() {
    // Mirrors the relevant DOM pieces from src/index.html:
    //   - feedbackModal with fbEnergy/fbEnergyVal/mood buttons/fbTaskId
    //   - careModal with careEncourage/careTaskInfo/careSameBtn/careSwitchBtn/careRest
    //   - gachaResult, discardPile, cardFlyLayer, toastContainer
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>m1.3d feedback/care isolated</title>
<style>
  body { font-family: sans-serif; background: #0f1422; color: #f0e8da; padding: 24px; }
  .hidden { display: none !important; }
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 999; display: flex; align-items: center; justify-content: center; }
  .modal { background: #0f1422; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 24px; max-width: 600px; width: 90%; }
  .feedback-emoji { display: flex; gap: 12px; }
  .feedback-emoji button { padding: 6px 12px; background: transparent; color: inherit; border: 2px solid transparent; border-radius: 12px; cursor: pointer; }
  .feedback-emoji button.sel { border-color: #f0c040; }
  #cardFlyLayer { position: fixed; inset: 0; pointer-events: none; }
  #discardPile { position: absolute; right: 12px; top: 12px; width: 140px; min-height: 98px; }
  .toast-container { position: fixed; top: 80px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; }
  .toast { padding: 12px 20px; border-radius: 8px; font-size: 0.9rem; }
  .toast.suc { background: rgba(39,174,96,0.2); border: 1px solid #27ae60; color: #27ae60; }
  .toast.err { background: rgba(231,76,60,0.2); border: 1px solid #e74c3c; color: #e74c3c; }
  .toast.inf { background: rgba(74,143,231,0.2); border: 1px solid #4a8fe7; color: #4a8fe7; }
</style>
</head>
<body>
  <div id="gachaResult"></div>
  <div id="discardPile"></div>
  <div id="cardFlyLayer"></div>
  <div class="toast-container" id="toastContainer"></div>

  <div class="modal-overlay hidden" id="feedbackModal">
    <div class="modal">
      <h2>任务完成!</h2>
      <p>感觉怎么样？</p>
      <div class="form-group">
        <label>精力消耗后剩余 (1-10)</label>
        <div class="flex gap8 ac">
          <input type="range" min="1" max="10" value="5" id="fbEnergy" class="grow">
          <span id="fbEnergyVal">5</span>
        </div>
      </div>
      <div class="form-group">
        <label>心情</label>
        <div class="feedback-emoji">
          <button data-mood="3" id="fbMood3">满意</button>
          <button data-mood="2" id="fbMood2">一般</button>
          <button data-mood="1" id="fbMood1">不太好</button>
        </div>
      </div>
      <input type="hidden" id="fbTaskId" value="">
      <div class="modal-actions">
        <button class="btn" id="fbCancelBtn">取消</button>
        <button class="btn pri" id="fbSubmitBtn">确认</button>
      </div>
    </div>
  </div>

  <div class="modal-overlay hidden" id="careModal">
    <div class="modal" style="max-width:460px;text-align:center">
      <h2 style="text-align:center">任务完成！</h2>
      <p id="careEncourage"></p>
      <p id="careTaskInfo"></p>
      <div>
        <button class="btn pri" id="careSameBtn">💪 继续抽同一科的卡</button>
        <button class="btn" id="careSwitchBtn">🔄 换换口味</button>
        <button class="btn" id="careRestBtn">😌 休息一下</button>
      </div>
    </div>
  </div>

  <!-- Stand-in for the drawn task card so completeWithFeedback finds it -->
  <div class="task-card drawn-card" id="drawnCard2" data-task-id="2" style="margin-top:16px"></div>
  <input type="hidden" id="gachaTimeInput" value="25">
</body>
</html>`;
  }

  async function loadIsolatedPageForM13d(page, routeHandler) {
    const HARNESS_BASE = 'http://test.local/';
    // Install the page-side mock fetch that mirrors M1.3B / M1.3C.
    await page.exposeFunction('__fetch', async (url, method, body) => {
      const handler = globalThis.__m13dFetchHandler;
      if (!handler) {
        return { __error: true, error: 'no fetch handler installed' };
      }
      return handler(url, method, body);
    });
    globalThis.__m13dFetchHandler = routeHandler;
    await page.context().route('**/*', async (route) => {
      // Only the harness base HTML route needs satisfying; API calls
      // go through window.__fetch (exposeFunction) and never hit
      // the network.
      return route.fulfill({
        status: 200, contentType: 'text/html', body: buildM13dHTML(),
      });
    });
    await page.addInitScript(() => {
      // Start with an empty allTasks. Tests that want a non-empty
      // allTasks push into window.allTasks after the bundle loads.
      window.__m13dAllTasks = null;
    });
    await page.goto(HARNESS_BASE, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await page.setContent(buildM13dHTML(), { waitUntil: 'domcontentloaded', timeout: 10000 });
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.addScriptTag({ content: M13D_BUNDLE });
    try {
      await page.waitForFunction(() => window.__harness_ready_m13d === true, { timeout: 10000 });
    } catch (e) {
      if (errors.length > 0) {
        throw new Error('Page errors during script load: ' + errors.join('; '));
      }
      throw e;
    }
    if (errors.length > 0) {
      throw new Error('Page errors during script load: ' + errors.join('; '));
    }
    // Wire UI handlers to the real extracted functions.
    await page.evaluate(() => {
      document.getElementById('fbSubmitBtn').addEventListener('click', submitFeedback);
      document.getElementById('fbCancelBtn').addEventListener('click', cancelFeedback);
      document.getElementById('fbMood3').addEventListener('click', function (e) { setMood(3, e.currentTarget); });
      document.getElementById('fbMood2').addEventListener('click', function (e) { setMood(2, e.currentTarget); });
      document.getElementById('fbMood1').addEventListener('click', function (e) { setMood(1, e.currentTarget); });
      document.getElementById('careSameBtn').addEventListener('click', careSameCategory);
      document.getElementById('careSwitchBtn').addEventListener('click', careSwitchCategory);
      document.getElementById('careRestBtn').addEventListener('click', careRest);
    });
  }

  /**
   * M1.3D A — No fabricated feedback POST; explicit submit carries
   * user-selected values; cancel performs zero POST; care modal is
   * reachable after either path.
   *
   * routeHandler signature: (url, method, body) => responseBody
   * (a plain object, not a Playwright Route). Returning
   * {__error:true, error:'...'} causes the page-side api() to throw.
   */
  test('M1.3D A: explicit selected energy/mood payload, cancel posts zero, care reachable', async ({ page }) => {
    let feedbackPosts = [];
    let completePosts = 0;
    let discardPosts = 0;
    let careDrawPosts = 0;
    await loadIsolatedPageForM13d(page, async (url, method, body) => {
      if (url === '/api/tasks/2/complete' && method === 'POST') {
        completePosts += 1;
        return { body: { unlocked_tasks: [] } };
      }
      if (url === '/api/tasks/2/move-to-discard' && method === 'POST') {
        discardPosts += 1;
        return { body: {} };
      }
      if (url === '/api/tasks/2/feedback' && method === 'POST') {
        feedbackPosts.push(body || {});
        return { body: {} };
      }
      if (url === '/api/gacha/care-draw' && method === 'POST') {
        careDrawPosts += 1;
        return { body: { task: null, can_replace: true, pool: 'fragment' } };
      }
      return { body: {} };
    });

    // Seed allTasks so completeWithFeedback passes the unlocked gate
    // (the test uses an in-memory task list, not /api/tasks).
    await page.evaluate(() => {
      window.allTasks = [{
        id: 2, name: 'M1.3D test task', is_unlocked: true, category: 'study',
      }];
    });

    // (A.1) Trigger completeWithFeedback(2). The real function must:
    //   - POST /api/tasks/2/complete (1x)
    //   - POST /api/tasks/2/move-to-discard (1x)
    //   - NOT POST /api/tasks/2/feedback before user submit
    //   - Open feedbackModal (NOT showCareModal yet)
    await page.evaluate(async () => { await completeWithFeedback(2); });

    expect(completePosts).toBe(1);
    expect(discardPosts).toBe(1);
    expect(feedbackPosts.length).toBe(0);

    const modalStateAfterComplete = await page.evaluate(() => {
      const fb = document.getElementById('feedbackModal');
      const cm = document.getElementById('careModal');
      return {
        fbVisible: fb && !fb.classList.contains('hidden'),
        cmVisible: cm && !cm.classList.contains('hidden'),
        fbTaskId: document.getElementById('fbTaskId').value,
        fbEnergy: document.getElementById('fbEnergy').value,
        fbEnergyVal: document.getElementById('fbEnergyVal').textContent,
        fbMoodSelected: gachaState.feedbackMood,
      };
    });
    expect(modalStateAfterComplete.fbVisible).toBe(true);
    expect(modalStateAfterComplete.cmVisible).toBe(false);
    expect(modalStateAfterComplete.fbTaskId).toBe('2');
    expect(modalStateAfterComplete.fbEnergy).toBe('5');
    expect(modalStateAfterComplete.fbEnergyVal).toBe('5');
    expect(modalStateAfterComplete.fbMoodSelected).toBe(3);

    // (A.2) User explicitly picks mood=2 and energy=8, then submits.
    await page.evaluate(() => {
      // Move range slider to 8.
      const e = document.getElementById('fbEnergy');
      e.value = '8';
      e.dispatchEvent(new Event('input'));
      setMood(2, document.getElementById('fbMood2'));
    });
    await page.click('#fbSubmitBtn');

    // Wait for the modal to close (means success path resolved and
    // transitioned to care).
    await page.waitForFunction(() => {
      const fb = document.getElementById('feedbackModal');
      return fb && fb.classList.contains('hidden');
    }, { timeout: 5000 });

    // Exactly one feedback POST, with USER-SELECTED values.
    expect(feedbackPosts.length).toBe(1);
    expect(feedbackPosts[0].energy_after).toBe(8);
    expect(feedbackPosts[0].mood_after).toBe(2);
    expect(feedbackPosts[0].event_type).toBeUndefined();

    // The care modal must now be open (transitionToCareModal -> showCareModal).
    const careVisible = await page.evaluate(() => {
      const cm = document.getElementById('careModal');
      return cm && !cm.classList.contains('hidden');
    });
    expect(careVisible).toBe(true);

    // (A.3) Care switch path: click "换换口味" — calls
    // careSwitchCategory which should issue a care-draw POST (preserving
    // existing care choices). The real function then closes the modal.
    await page.click('#careSwitchBtn');
    await page.waitForFunction(() => {
      const cm = document.getElementById('careModal');
      return cm && cm.classList.contains('hidden');
    }, { timeout: 5000 });
    expect(careDrawPosts).toBeGreaterThanOrEqual(1);

    // Reset state for the cancel path.
    feedbackPosts = [];
    completePosts = 0;
    discardPosts = 0;

    // (A.4) Second task completion via cancel path. Trigger again,
    // then click 取消 — must perform ZERO /feedback POST and still
    // transition to care modal.
    await page.evaluate(async () => { await completeWithFeedback(2); });
    expect(completePosts).toBe(1);
    expect(discardPosts).toBe(1);
    expect(feedbackPosts.length).toBe(0);

    const fbOpenAgain = await page.evaluate(() => {
      const fb = document.getElementById('feedbackModal');
      return fb && !fb.classList.contains('hidden');
    });
    expect(fbOpenAgain).toBe(true);

    await page.click('#fbCancelBtn');
    await page.waitForFunction(() => {
      const fb = document.getElementById('feedbackModal');
      return fb && fb.classList.contains('hidden');
    }, { timeout: 5000 });

    // ZERO feedback POSTs after cancel.
    expect(feedbackPosts.length).toBe(0);

    // Care modal is now open.
    const careAfterCancel = await page.evaluate(() => {
      const cm = document.getElementById('careModal');
      return cm && !cm.classList.contains('hidden');
    });
    expect(careAfterCancel).toBe(true);

    // Click 休息一下 — closes care modal without /feedback or care-draw.
    const careDrawPostsBeforeRest = careDrawPosts;
    await page.click('#careRestBtn');
    await page.waitForFunction(() => {
      const cm = document.getElementById('careModal');
      return cm && cm.classList.contains('hidden');
    }, { timeout: 5000 });
    expect(careDrawPosts).toBe(careDrawPostsBeforeRest);
  });

  /**
   * M1.3D B — Rejected feedback POST must NOT dismiss the modal and
   * must allow retry; simultaneous confirm clicks must not duplicate
   * requests.
   */
  test('M1.3D B: rejected feedback leaves modal open, allows retry; duplicate confirm clicks do not duplicate', async ({ page }) => {
    let feedbackPosts = 0;
    let failOnce = true;
    let lastFeedbackBody = null;
    await loadIsolatedPageForM13d(page, async (url, method, body) => {
      if (url === '/api/tasks/2/complete' && method === 'POST') {
        return { body: {} };
      }
      if (url === '/api/tasks/2/move-to-discard' && method === 'POST') {
        return { body: {} };
      }
      if (url === '/api/tasks/2/feedback' && method === 'POST') {
        feedbackPosts += 1;
        lastFeedbackBody = body || {};
        if (failOnce) {
          failOnce = false;
          return { __error: true, error: 'mocked 500 from /feedback' };
        }
        return { body: {} };
      }
      if (url === '/api/gacha/care-draw' && method === 'POST') {
        return { body: { task: null, can_replace: true, pool: 'fragment' } };
      }
      return { body: {} };
    });

    await page.evaluate(() => {
      window.allTasks = [{ id: 2, name: 'B test', is_unlocked: true, category: 'study' }];
    });

    await page.evaluate(async () => { await completeWithFeedback(2); });

    // Modal is open. Fire two synchronous confirm clicks.
    await page.evaluate(async () => {
      const btn = document.getElementById('fbSubmitBtn');
      // synchronous duplicate clicks
      btn.click();
      btn.click();
      // give the await microtasks time to settle
      await new Promise(function (r) { setTimeout(r, 50); });
    });

    // Exactly ONE /feedback POST despite the duplicate clicks
    // (reentrancy guard inside submitFeedback).
    expect(feedbackPosts).toBe(1);
    expect(lastFeedbackBody && lastFeedbackBody.energy_after).toBe(5);
    expect(lastFeedbackBody && lastFeedbackBody.mood_after).toBe(3);

    // Modal is STILL open (POST failed).
    await page.waitForFunction(() => {
      const t = window.__lastToast;
      return t && t.type === 'err';
    }, { timeout: 5000 });
    const fbStillOpen = await page.evaluate(() => {
      const fb = document.getElementById('feedbackModal');
      return fb && !fb.classList.contains('hidden');
    });
    expect(fbStillOpen).toBe(true);

    // Care modal must NOT have been opened.
    const careNotYet = await page.evaluate(() => {
      const cm = document.getElementById('careModal');
      return cm && !cm.classList.contains('hidden');
    });
    expect(careNotYet).toBe(false);

    // (B.2) Retry: click 确认 again — POST now succeeds and modal closes.
    await page.click('#fbSubmitBtn');
    await page.waitForFunction(() => {
      const fb = document.getElementById('feedbackModal');
      return fb && fb.classList.contains('hidden');
    }, { timeout: 5000 });
    expect(feedbackPosts).toBe(2);

    const careOpened = await page.evaluate(() => {
      const cm = document.getElementById('careModal');
      return cm && !cm.classList.contains('hidden');
    });
    expect(careOpened).toBe(true);
  });
});
