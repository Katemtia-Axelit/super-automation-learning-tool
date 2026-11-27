// Debug test - just open the page and check what happens on click.
const { test } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const APP_JS_PATH = path.join(PROJECT_ROOT, 'static', 'app.js');

function extractFunction(source, name) {
  const re = new RegExp('function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{');
  const m = source.match(re);
  if (!m) return null;
  const start = m.index;
  let depth = 0;
  for (let i = m.index + m[0].length - 1; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  return null;
}

test('debug - check console', async ({ page }) => {
  page.on('console', (msg) => console.log('[console]', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));
  page.on('request', (req) => console.log('[req]', req.method(), req.url()));
  page.on('response', (res) => console.log('[res]', res.status(), res.url()));

  const appJs = fs.readFileSync(APP_JS_PATH, 'utf-8');
  const rmr = extractFunction(appJs, 'renderMultiResults');
  const amc = extractFunction(appJs, 'activateMultiCard');
  const dgm = extractFunction(appJs, 'drawGachaMulti');

  await page.context().route('**/*', async (route) => {
    const url = route.request().url();
    if (url.includes('/api/gacha/multi-draw')) {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({
          tasks: [
            { id: 1, name: 'T1', estimated_time: 10, tags: ['x'] },
            { id: 2, name: 'T2', estimated_time: 15, tags: ['y'] },
            { id: 3, name: 'T3', estimated_time: 20, tags: ['z'] },
          ],
          total_minutes: 45,
          remaining_minutes: 100,
        }),
      });
    }
    if (url.startsWith('data:') || url.startsWith('about:')) {
      return route.fulfill({ status: 200, contentType: 'text/html', body: 'ok' });
    }
    return route.abort();
  });

  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head><body>
  <input type="number" id="gachaTimeInput" value="25">
  <select id="gachaMultiCount"><option value="3" selected>3</option></select>
  <button id="gachaMultiBtn">go</button>
  <button id="gachaBtn" style="display:none">single</button>
  <div class="gacha-multi-result hidden" id="gachaMultiResult">
    <div id="gachaMultiSummary"></div>
    <div id="gachaMultiList"></div>
  </div>
  <div id="gachaResult"></div>
<script>
  var gachaState = { energy: 'medium', pool: 'fragment', canReplace: true, replacedTaskId: null, feedbackMood: 3, currentTaskId: null, selectedTag: '' };
  var isDrawing = false;
  var multiDrawResults = [];
  function toast() {}
  function refreshGachaStats() {}
  async function api(url, opts) {
    var r = await fetch(url, opts);
    return await r.json();
  }
  function getGachaAvailableMinutes() { return 25; }
  function renderDrawnCard(t) {
    var s = document.createElement('div'); s.className = 'drawn-card-stage';
    var c = document.createElement('div'); c.className = 'task-card'; c.setAttribute('data-task-id', t.id);
    s.appendChild(c); return s;
  }
  ${rmr}
  ${amc}
  ${dgm}
  document.getElementById('gachaMultiBtn').addEventListener('click', drawGachaMulti);
  window.__loaded = true;
</script>
</body></html>`;

  await page.setContent(html, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.__loaded === true);
  console.log('[debug] page loaded; clicking button');
  await page.click('#gachaMultiBtn');
  await page.waitForTimeout(1500);
  const html2 = await page.content();
  console.log('[debug] HTML after click (first 1500 chars):');
  console.log(html2.slice(0, 1500));
  const items = await page.locator('.gacha-multi-item').count();
  console.log('[debug] gacha-multi-item count:', items);
});
