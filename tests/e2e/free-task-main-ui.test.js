'use strict';

/**
 * 自由任务 · 正式主界面 MVP 端到端测试
 * (LT_RETENTION_FREE_TASK_MAIN_UI_MVP_20261023_Q)
 *
 * 真实链路：
 *   真实 Chromium → 正式 src/index.html（未经改写的正式页面）
 *   ← 测试进程内启动的**只读** localhost 静态服务器
 *       · "/"           → src/index.html
 *       · "/static/*"   → static/（只读）
 *       · "/api/*"      → **隔离 mock**：只对旧 app.js / 引导卡的既有 GET 请求
 *                         返回内存常量，绝不触碰正式 Flask / 正式 DB / Vault / config
 *
 * 硬约束：
 * - 不启动正式 Flask，不访问 data/、config/、src/notes/**，不写任何项目文件；
 * - 不伪造本轮自由任务面板的 DOM 交互：所有断言都来自真实点击 / 输入；
 * - 端口固定绑定 127.0.0.1 且使用操作系统分配的临时端口（port=0），测试结束必关闭。
 *
 * 运行方式：
 *   node --test tests/e2e/free-task-main-ui.test.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const http = require('node:http');

const { chromium } = require('playwright');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const INDEX_HTML = path.join(PROJECT_ROOT, 'src', 'index.html');
const STATIC_DIR = path.join(PROJECT_ROOT, 'static');

const PINNED_CHROMIUM = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

const STORAGE_KEY = 'SAL_FREE_TASK_LOCAL_V1';

const SEL = {
  panel: '#freeTaskPanel',
  summary: '#freeTaskPanel > summary',
  name: '#freeTaskName',
  form: '#freeTaskForm',
  error: '#freeTaskError',
  storageError: '#freeTaskStorageError',
  categoryStudy: '#freeTaskPanel input[name="freeTaskCategory"][value="study"]',
  categoryFun: '#freeTaskPanel input[name="freeTaskCategory"][value="entertainment"]',
  minutes25: '#freeTaskPanel input[name="freeTaskMinutes"][value="25"]',
  minutes55: '#freeTaskPanel input[name="freeTaskMinutes"][value="55"]',
  create: '#freeTaskCreateBtn',
  reset: '#freeTaskResetBtn',
  current: '#freeTaskCurrent',
  currentName: '#freeTaskCurrentName',
  remaining: '#freeTaskRemaining',
  meta: '#freeTaskMeta',
  notice: '#freeTaskNotice',
  badge: '#freeTaskStateBadge',
  start: '#freeTaskStartBtn',
  pause: '#freeTaskPauseBtn',
  resume: '#freeTaskResumeBtn',
  complete: '#freeTaskCompleteBtn',
  interrupt: '#freeTaskInterruptBtn',
  fail: '#freeTaskFailBtn',
  selfMinutes: '#freeTaskSelfMinutes',
  selfHint: '#freeTaskSelfHint',
  statDone: '#freeTaskStatDone',
  statSelf: '#freeTaskStatSelf',
  history: '#freeTaskHistoryList',
  clearBtn: '#freeTaskClearBtn',
  clearConfirm: '#freeTaskClearConfirmBtn',
  clearCancel: '#freeTaskClearCancelBtn',
  confirmBox: '#freeTaskConfirmBox',
  oldTimerPanel: '#timerPanel',
  oldTaskGrid: '#taskGrid',
  navTasks: 'button.nav-btn[data-page="tasks"]',
  navGacha: 'button.nav-btn[data-page="gacha"]',
  homeShortcut: '#freeTaskHomeShortcutBtn',
  homeShortcutRow: '.free-task-shortcut-row',
  pageGacha: '#page-gacha',
  pageTasks: '#page-tasks',
  gachaBtn: '#gachaBtn'
};

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon'
};

/**
 * 既有 GET 接口的隔离 mock：只覆盖旧 app.js / 引导卡在首屏会发出的请求。
 * 全部是内存常量，不读写任何正式数据库。
 */
const API_MOCKS = {
  '/api/health': { status: 'healthy' },
  '/api/agent-policy/status': { initialized: true },
  '/api/tasks': [],
  '/api/tags': [],
  '/api/timer/active': {},
  '/api/gacha/statistics': { total_draws: 0, acceptance_rate: null, rejections: 0 },
  '/api/discard-pile': [],
  '/api/schedule/slots': [],
  '/api/schedule/weekly': {},
  '/api/schedule/daily': {},
  '/api/state/sleep': [],
  '/api/state/weekly-energy': [],
  '/api/state/assessment': { completed: false },
  '/api/state/assessment/history': []
};

function apiMockFor(pathname) {
  if (Object.prototype.hasOwnProperty.call(API_MOCKS, pathname)) {
    return API_MOCKS[pathname];
  }
  if (pathname.indexOf('/api/state/assessment/history') === 0) return [];
  if (pathname.indexOf('/api/schedule/daily') === 0) return {};
  if (pathname.indexOf('/api/tasks') === 0) return [];
  return [];
}

/** 只读静态服务器：/ → src/index.html，/static/* → static/，/api/* → 隔离 mock。 */
function startStaticServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, 'http://127.0.0.1');
      const pathname = decodeURIComponent(url.pathname);

      if (pathname.indexOf('/api/') === 0) {
        const body = JSON.stringify(apiMockFor(pathname));
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(body);
        return;
      }

      if (pathname === '/' || pathname === '/index.html') {
        fs.readFile(INDEX_HTML, (err, data) => {
          if (err) { res.writeHead(500); res.end('index read error'); return; }
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(data);
        });
        return;
      }

      if (pathname.indexOf('/static/') === 0) {
        const rel = pathname.slice('/static/'.length);
        const target = path.resolve(STATIC_DIR, rel);
        if (target.indexOf(path.resolve(STATIC_DIR)) !== 0) { res.writeHead(403); res.end('forbidden'); return; }
        fs.readFile(target, (err, data) => {
          if (err) { res.writeHead(404); res.end('not found'); return; }
          const ext = path.extname(target).toLowerCase();
          res.writeHead(200, { 'Content-Type': CONTENT_TYPES[ext] || 'application/octet-stream' });
          res.end(data);
        });
        return;
      }

      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('not found');
    });

    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address();
      resolve({
        server,
        port: addr.port,
        origin: 'http://127.0.0.1:' + addr.port,
        close: () => new Promise((r) => server.close(() => r()))
      });
    });
  });
}

function launchOptions() {
  const opts = { headless: true, args: ['--disable-gpu'] };
  if (fs.existsSync(PINNED_CHROMIUM)) opts.executablePath = PINNED_CHROMIUM;
  return opts;
}

/** 打开正式页面并进入「任务」页。 */
async function openTasksPage(browser, ctxOptions = {}) {
  const context = await browser.newContext(ctxOptions);
  const page = await context.newPage();
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  await page.goto(ctxOptions.url, { waitUntil: 'load' });
  await page.waitForSelector(SEL.navTasks, { state: 'attached' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  return { context, page, pageErrors, consoleErrors };
}

function readStore(page) {
  return page.evaluate((key) => {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  }, STORAGE_KEY);
}

/** 创建任务（真实输入 + 真实点击）。 */
async function createTask(page, { name, category = 'study', minutes = 25 } = {}) {
  if (name !== undefined) await page.fill(SEL.name, name);
  await page.check(category === 'entertainment' ? SEL.categoryFun : SEL.categoryStudy);
  await page.check(minutes === 55 ? SEL.minutes55 : SEL.minutes25);
  await page.click(SEL.create);
}

test('正式「任务」页内存在自由任务面板，旧计时器与任务列表不受影响', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page, pageErrors } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  // 面板在正式页面里、位于旧任务工具条之后
  assert.equal(await page.locator(SEL.panel).count(), 1);
  assert.equal(await page.locator(SEL.panel).evaluate((n) => n.tagName.toLowerCase()), 'details');
  // 默认可发现：面板默认展开
  assert.equal(await page.locator(SEL.panel).evaluate((n) => n.hasAttribute('open')), true);

  // 旧计时器与旧任务列表仍然存在
  assert.equal(await page.locator(SEL.oldTimerPanel).count(), 1);
  assert.equal(await page.locator(SEL.oldTaskGrid).count(), 1);
  assert.equal(await page.locator(SEL.oldTimerPanel).isVisible(), true);

  // 旧 app.js 全局未被本轮改动破坏
  assert.equal(await page.evaluate(() => typeof window.showPage), 'function');

  const freeTaskErrors = pageErrors.filter((e) => /free-task|freeTask/i.test(e));
  assert.deepEqual(freeTaskErrors, []);
});

test('创建 → 开始 → 暂停 → 继续 → 明确完成，完成只记一次', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  await createTask(page, { name: '复习第三章', minutes: 55 });
  assert.equal((await page.innerText(SEL.badge)).trim(), '未开始');
  assert.equal((await page.innerText(SEL.remaining)).trim(), '55:00');
  assert.match(await page.innerText(SEL.meta), /计划时长：55 分钟/);
  assert.equal(await page.locator(SEL.current).isVisible(), true);
  assert.equal(await page.locator(SEL.form).isVisible(), false);

  await page.click(SEL.start);
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');

  await page.click(SEL.pause);
  assert.equal((await page.innerText(SEL.badge)).trim(), '已暂停');
  const pausedRemaining = (await page.innerText(SEL.remaining)).trim();

  await page.click(SEL.resume);
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');
  assert.ok(pausedRemaining.match(/^\d{2}:\d{2}$/), '暂停后仍显示剩余时间');

  // 手动自报学习分钟（未独立核实）
  await page.fill(SEL.selfMinutes, '30');
  await page.click(SEL.complete);
  assert.equal((await page.innerText(SEL.badge)).trim(), '已完成');

  // 统计：本地完成数=1，自报分钟=30，服务端已验证分钟恒为 0
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
  assert.equal((await page.innerText(SEL.statSelf)).trim(), '30');
  const stats = await page.locator('#freeTaskPanel .free-task-stats').innerText();
  // 数值在前、标签在后（DOM 顺序 num → lbl）
  assert.match(stats, /0\s*\n\s*服务端已验证学习分钟/);
  assert.match(stats, /0\s*\n\s*计入番茄数/);

  // 防重复完成：完成后按钮禁用
  assert.equal(await page.locator(SEL.complete).isDisabled(), true);

  // 存储中只记了一次 completed 事件
  const store = await readStore(page);
  const completedEvents = store.events.filter((e) => e.s === 'completed');
  assert.equal(completedEvents.length, 1);
  assert.equal(store.history.filter((h) => h.status === 'completed').length, 1);

  // 完成后可再次创建
  assert.equal(await page.locator(SEL.reset).isVisible(), true);
  await page.click(SEL.reset);
  assert.equal(await page.locator(SEL.form).isVisible(), true);
  assert.equal((await page.innerText(SEL.badge)).trim(), '未开始');
});

test('娱乐类任务不产生自报学习分钟', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  await createTask(page, { name: '看纪录片', category: 'entertainment', minutes: 25 });
  await page.click(SEL.start);
  // 娱乐类即使手填也不该计入
  assert.equal(await page.locator(SEL.selfMinutes).isDisabled(), true);
  assert.match(await page.innerText(SEL.selfHint), /娱乐类不计自报学习分钟/);
  await page.click(SEL.complete);

  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
  assert.equal((await page.innerText(SEL.statSelf)).trim(), '0');
  const store = await readStore(page);
  const entry = store.history.find((h) => h.status === 'completed');
  assert.equal(entry.selfReportedMinutes, 0);
  assert.equal(entry.category, 'entertainment');
});

test('空白活动名被拒绝；XSS 文本按字面渲染且不执行', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  // 空白（含纯空格）必须被拒绝
  await page.fill(SEL.name, '   ');
  await page.click(SEL.create);
  assert.equal(await page.locator(SEL.error).isVisible(), true);
  assert.match(await page.innerText(SEL.error), /不能为空/);
  assert.equal(await page.locator(SEL.current).isVisible(), false);

  // XSS 载荷：必须按字面文本显示，不产生元素、不执行脚本
  const payload = '<img src=x onerror="window.__salFreeTaskXss=1">';
  await page.fill(SEL.name, payload);
  await page.click(SEL.create);
  assert.equal(await page.locator(SEL.current).isVisible(), true);
  assert.equal(await page.innerText(SEL.currentName), payload);
  assert.equal(await page.locator(SEL.currentName + ' img').count(), 0);
  assert.equal(await page.evaluate(() => window.__salFreeTaskXss), undefined);
});

test('计时到 0 只停止，不自动完成', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const context = await browser.newContext();
  const page = await context.newPage();
  t.after(async () => { await context.close(); });

  // 用真实 Chromium 的时钟快进 25 分钟（真实定时器到期，不是伪造状态）
  await page.clock.install({ time: new Date('2026-01-01T00:00:00Z') });
  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.waitForSelector(SEL.navTasks, { state: 'attached' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  await createTask(page, { name: '长时间任务', minutes: 25 });
  await page.click(SEL.start);
  await page.clock.fastForward(25 * 60 * 1000 + 2000);

  await page.waitForFunction(
    () => {
      const el = document.getElementById('freeTaskStateBadge');
      return el && el.textContent.trim() === '已到计划时长';
    },
    null,
    { timeout: 10000 }
  );

  assert.equal((await page.innerText(SEL.badge)).trim(), '已到计划时长');
  assert.equal((await page.innerText(SEL.remaining)).trim(), '00:00');
  // 没有自动完成
  assert.equal((await page.innerText(SEL.statDone)).trim(), '0');
  assert.match(await page.innerText(SEL.notice), /不会自动完成|不自动完成/);

  // 用户仍可明确完成
  assert.equal(await page.locator(SEL.complete).isDisabled(), false);
  await page.click(SEL.complete);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
});

test('刷新后恢复本地历史，可显式确认后清理本地记录', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  await createTask(page, { name: '持久化验证', minutes: 25 });
  await page.click(SEL.start);
  await page.fill(SEL.selfMinutes, '12');
  await page.click(SEL.complete);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');

  // 刷新后读取本地历史
  await page.reload({ waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
  assert.equal((await page.innerText(SEL.statSelf)).trim(), '12');
  const historyText = await page.innerText(SEL.history);
  assert.match(historyText, /持久化验证/);
  assert.match(historyText, /已完成/);

  // 清理需要显式确认
  await page.click(SEL.clearBtn);
  assert.equal(await page.locator(SEL.confirmBox).isVisible(), true);
  await page.click(SEL.clearCancel);
  assert.equal(await page.locator(SEL.confirmBox).isVisible(), false);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');

  await page.click(SEL.clearBtn);
  await page.click(SEL.clearConfirm);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '0');
  assert.equal((await page.innerText(SEL.statSelf)).trim(), '0');
  const store = await readStore(page);
  assert.equal(store, null);
});

test('localStorage 写入失败时显示可见错误，不假装已保存', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const context = await browser.newContext();
  const page = await context.newPage();
  t.after(async () => { await context.close(); });

  // 模拟容量/权限错误：setItem 抛出
  await page.addInitScript(() => {
    const proto = window.Storage.prototype;
    const original = proto.setItem;
    proto.setItem = function (k, v) {
      if (String(k).indexOf('SAL_FREE_TASK_LOCAL_V1') === 0) {
        const err = new Error('QuotaExceededError');
        err.name = 'QuotaExceededError';
        throw err;
      }
      return original.call(this, k, v);
    };
  });

  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.waitForSelector(SEL.navTasks, { state: 'attached' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  await createTask(page, { name: '存储失败验证', minutes: 25 });
  assert.equal(await page.locator(SEL.storageError).isVisible(), true);
  const errText = await page.innerText(SEL.storageError);
  assert.match(errText, /本地保存失败|仅保存在内存|刷新后会丢失/);
  // 不得假装已保存：存储中不应出现本次任务
  const store = await readStore(page);
  assert.equal(store, null);
});

test('键盘可操作，移动端视口下面板可用且不横向溢出', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  // --- 键盘 ---
  {
    const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
    t.after(async () => { await context.close(); });

    await page.focus(SEL.name);
    await page.keyboard.type('键盘创建的任务');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator(SEL.current).isVisible(), true);
    assert.equal(await page.innerText(SEL.currentName), '键盘创建的任务');

    // Tab 顺序可达：类别 → 时长 → 创建
    await page.focus(SEL.name);
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? (el.name || el.id || el.tagName) : null;
    });
    assert.ok(focused, 'Tab 后仍有可聚焦元素');
  }

  // --- 移动端 ---
  {
    const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await mobile.newPage();
    t.after(async () => { await mobile.close(); });
    await page.goto(srv.origin + '/', { waitUntil: 'load' });
    await page.click(SEL.navTasks);
    await page.waitForSelector(SEL.panel, { state: 'visible' });
    assert.equal(await page.locator(SEL.panel).isVisible(), true);
    // 面板自身不得造成横向溢出（页头导航的历史溢出不计入本轮范围）
    const panelOverflow = await page.evaluate(() => {
      const panel = document.getElementById('freeTaskPanel');
      const limit = document.documentElement.clientWidth;
      let worst = 0;
      panel.querySelectorAll('*').forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.width > 0) worst = Math.max(worst, r.right - limit);
      });
      return Math.round(worst);
    });
    assert.ok(panelOverflow <= 4, '自由任务面板不应造成横向溢出，实际=' + panelOverflow);
  }
});

/**
 * 以下 2 例覆盖 LT_RETENTION_FREE_TASK_HOME_SHORTCUT_20261023_R：
 * 默认「抽卡」首页的自由任务入口（唯一新增产品面）。
 * 硬约束：不新增 mock、不新增 Temp 脚本；沿用上方同一台只读静态服务器与隔离 GET mock。
 */

/** 打开默认首页（page-gacha），并记录本轮点击后新增的 HTTP 请求（方法+路径）。 */
async function openGachaHome(browser, srv, ctxOptions = {}, opts = {}) {
  const context = await browser.newContext(ctxOptions);
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  const posts = [];
  if (opts.trackPosts !== false) {
    page.on('request', (r) => {
      if (r.method() === 'POST') posts.push(new URL(r.url()).pathname);
    });
  }
  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.waitForSelector(SEL.homeShortcut, { state: 'visible' });
  return { context, page, pageErrors, posts };
}

test('默认「抽卡」首页可发现自由任务入口：鼠标与键盘均可激活，进入任务页后面板可见可操作', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page, pageErrors, posts } = await openGachaHome(browser, srv);
  t.after(async () => { await context.close(); });

  // --- 1) 默认首页就是抽卡页，入口真实存在且可发现 ---
  assert.equal(await page.locator(SEL.pageGacha).isVisible(), true);
  assert.equal(await page.locator(SEL.homeShortcut).isVisible(), true);
  // 入口紧邻既有抽卡控件（想抽 / 我有 / 连抽），不得替换或搬走它们
  const nearControls = await page.locator(SEL.homeShortcut).evaluate((n) => {
    return !!n.closest('#page-gacha') && !!n.closest('#page-gacha').querySelector('.gacha-controls-row');
  });
  assert.equal(nearControls, true);
  // 语义明确：文案点明「不想抽卡」这一意图
  const label = (await page.innerText(SEL.homeShortcut)).replace(/\s+/g, '');
  assert.match(label, /自由任务/);
  assert.match(label, /不想抽卡/);
  // 旧抽卡 DOM 未被移除
  assert.equal(await page.locator(SEL.gachaBtn).count(), 1);
  assert.equal(await page.locator(SEL.oldTimerPanel).count(), 1);

  const storeBefore = await readStore(page);

  // --- 2) 鼠标激活 ---
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal(await page.locator(SEL.pageTasks).isVisible(), true);
  assert.equal(await page.locator(SEL.panel).evaluate((n) => n.hasAttribute('open')), true);
  // 滚动到可见处
  const inView = await page.locator(SEL.panel).evaluate((n) => {
    const r = n.getBoundingClientRect();
    return r.top < window.innerHeight && r.bottom > 0;
  });
  assert.equal(inView, true, '面板应被滚动到视口内');
  // 旧任务列表仍在
  assert.equal(await page.locator(SEL.oldTaskGrid).count(), 1);

  // 入口本身：不抽卡、不建本地记录
  assert.deepEqual(posts.filter((p) => /gacha/.test(p)), [], '入口不得触发任何抽卡 POST');
  assert.deepEqual(await readStore(page), storeBefore, '入口不得产生活动数据');

  // --- 3) 面板可操作：输入并创建，再开始 ---
  await page.fill(SEL.name, '从首页直接开始的活动');
  await page.check(SEL.categoryStudy);
  await page.check(SEL.minutes25);
  await page.click(SEL.create);
  assert.equal(await page.locator(SEL.current).isVisible(), true);
  assert.equal((await page.innerText(SEL.badge)).trim(), '未开始');
  await page.click(SEL.start);
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');

  // --- 4) 键盘激活：焦点可落在入口上并用 Enter 触发 ---
  await page.click(SEL.navGacha);
  await page.waitForSelector(SEL.homeShortcut, { state: 'visible' });
  await page.focus(SEL.homeShortcut);
  assert.equal(
    await page.evaluate(() => document.activeElement && document.activeElement.id),
    'freeTaskHomeShortcutBtn',
    '入口必须可键盘聚焦'
  );
  await page.keyboard.press('Enter');
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal(await page.locator(SEL.pageTasks).isVisible(), true);

  // --- 5) 回抽卡再点入口：不清空正在进行的活动 ---
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');
  await page.click(SEL.navGacha);
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中', '往返首页不得清空进行中的活动');
  assert.equal(await page.innerText(SEL.currentName), '从首页直接开始的活动');
  const store = await readStore(page);
  assert.ok(store && store.current, 'localStorage 中的进行中活动仍在');
  assert.equal(store.current.name, '从首页直接开始的活动');
  assert.equal(store.current.status, 'running');
  assert.equal(store.history.length, 0, '往返不得写入历史记录');

  assert.deepEqual(pageErrors.filter((e) => /free-task|freeTask/i.test(e)), []);
});

test('390px 移动宽度下首页入口可见可激活，且新入口不新增横向溢出', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  t.after(async () => { await mobile.close(); });
  const page = await mobile.newPage();

  const posts = [];
  page.on('request', (r) => { if (r.method() === 'POST') posts.push(new URL(r.url()).pathname); });
  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.waitForSelector(SEL.homeShortcut, { state: 'visible' });

  // 入口在 390px 下完整可见且完全在视口内
  assert.equal(await page.locator(SEL.homeShortcut).isVisible(), true);
  const rowOverflow = await page.locator(SEL.homeShortcutRow).evaluate((n) => {
    const limit = document.documentElement.clientWidth;
    let worst = 0;
    n.querySelectorAll('*').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0) worst = Math.max(worst, r.right - limit, -r.left);
    });
    return Math.round(worst);
  });
  assert.ok(rowOverflow <= 4, '首页入口自身不得造成横向溢出，实际=' + rowOverflow);

  // 激活后仍能进入任务页并操作（既有面板在移动宽度的行为保持不变）
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal(await page.locator(SEL.panel).isVisible(), true);
  await page.fill(SEL.name, '移动端临时活动');
  await page.check(SEL.categoryStudy);
  await page.check(SEL.minutes25);
  await page.click(SEL.create);
  assert.equal(await page.locator(SEL.current).isVisible(), true);

  assert.deepEqual(posts.filter((p) => /gacha/.test(p)), [], '移动端入口不得触发抽卡 POST');
});

/**
 * 以下用例覆盖 LT_RETENTION_FREE_TASK_LOCAL_BACKUP_20261023_S：
 * 自由任务本地 JSON 备份（导出下载 / 二次确认导入恢复）。
 *
 * 硬约束：
 * - 全部内存操作：导出用 Playwright download event + readable bytes；
 *   导入用 setInputFiles({ name, mimeType, buffer })，**不写任何临时文件**；
 * - 不新增 mock、不新增第三方库、不触碰正式后端 / DB / 笔记 / config；
 * - 沿用上方同一台只读静态服务器与隔离 GET mock。
 */

const BACKUP = {
  exportBtn: '#freeTaskExportBtn',
  importBtn: '#freeTaskImportBtn',
  importFile: '#freeTaskImportFile',
  status: '#freeTaskBackupStatus',
  error: '#freeTaskBackupError',
  importConfirmBox: '#freeTaskImportConfirmBox',
  importConfirmText: '#freeTaskImportConfirmText',
  importConfirm: '#freeTaskImportConfirmBtn',
  importCancel: '#freeTaskImportCancelBtn'
};

/** 点击导出并把下载内容读回内存（不落盘）。 */
async function exportBackupBytes(page) {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click(BACKUP.exportBtn)
  ]);
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return { suggestedFilename: download.suggestedFilename(), buffer: Buffer.concat(chunks) };
}

/** 把内存里的 JSON 文本交给隐藏的 file input。 */
async function importFromBuffer(page, text, name = 'sal-free-task-backup-test.json') {
  await page.setInputFiles(BACKUP.importFile, {
    name,
    mimeType: 'application/json',
    buffer: Buffer.from(text, 'utf8')
  });
  // File.text()/FileReader resolves asynchronously after the input change event.
  // Wait for either a validated import confirmation or a visible rejection.
  await page.waitForFunction(() => {
    const confirmation = document.getElementById('freeTaskImportConfirmBox');
    const error = document.getElementById('freeTaskBackupError');
    return !!((confirmation && !confirmation.hidden) || (error && !error.hidden));
  });
}

function makeBackup({ current = null, history = [], events = [] } = {}) {
  return JSON.stringify({ v: 1, current, history, events });
}

test('导出备份：只含 v/current/history/events 与本地统计，不含其它字段，也不产生额外 POST', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const context = await browser.newContext();
  const page = await context.newPage();
  t.after(async () => { await context.close(); });

  const posts = [];
  page.on('request', (r) => { if (r.method() === 'POST') posts.push(new URL(r.url()).pathname); });

  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  // 空记录时导出必须可见报错，不得伪称成功
  await page.click(BACKUP.exportBtn);
  assert.equal(await page.locator(BACKUP.error).isVisible(), true);
  assert.match(await page.innerText(BACKUP.error), /没有可导出的|没有可导出/);

  // 创建 → 完成一个真实活动
  await createTask(page, { name: '备份验证活动', minutes: 25 });
  await page.click(SEL.start);
  await page.fill(SEL.selfMinutes, '15');
  await page.click(SEL.complete);

  const before = await readStore(page);
  const dl = await exportBackupBytes(page);
  assert.match(dl.suggestedFilename, /^sal-free-task-backup-\d{4}-\d{2}-\d{2}\.json$/);

  const data = JSON.parse(dl.buffer.toString('utf8'));
  assert.deepEqual(Object.keys(data).sort(), ['current', 'events', 'history', 'v']);
  assert.equal(data.v, 1);
  assert.equal(data.history.length, 1);
  assert.equal(data.history[0].name, '备份验证活动');
  assert.equal(data.history[0].status, 'completed');
  assert.equal(data.history[0].selfReportedMinutes, 15);
  assert.ok(Array.isArray(data.events) && data.events.length > 0);
  assert.equal(data.events.filter((e) => e.s === 'completed').length, 1);
  assert.ok(dl.buffer.length < 256 * 1024, '导出文件远小于 256 KiB 上限');

  // 导出只是读取：内存状态与存储都不变
  const after = await readStore(page);
  assert.deepEqual(after, before, '导出不得改变任何记录');
  assert.deepEqual(posts, [], '导出不得产生任何 HTTP POST');
  assert.match(await page.innerText(BACKUP.status), /已.*在浏览器下载|已在浏览器下载/);
});

test('清理后导入恢复：显式二次确认才写入，刷新后仍持久', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  await createTask(page, { name: '恢复验证活动', minutes: 25 });
  await page.click(SEL.start);
  await page.fill(SEL.selfMinutes, '20');
  await page.click(SEL.complete);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');

  const backupText = (await exportBackupBytes(page)).buffer.toString('utf8');

  // 清理本地记录
  await page.click(SEL.clearBtn);
  await page.click(SEL.clearConfirm);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '0');
  assert.equal(await readStore(page), null);

  // 导入：先出现二次确认，且确认前不得动数据
  await importFromBuffer(page, backupText);
  assert.equal(await page.locator(BACKUP.importConfirmBox).isVisible(), true);
  assert.match(await page.innerText(BACKUP.importConfirmText), /覆盖现有本地记录/);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '0', '确认前统计不应变化');

  await page.click(BACKUP.importConfirm);
  assert.equal(await page.locator(BACKUP.importConfirmBox).isVisible(), false);
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
  assert.equal((await page.innerText(SEL.statSelf)).trim(), '20');
  assert.match(await page.innerText(SEL.history), /恢复验证活动/);

  // 刷新后仍持久
  await page.reload({ waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
  assert.equal((await page.innerText(SEL.statSelf)).trim(), '20');
  assert.match(await page.innerText(SEL.history), /恢复验证活动/);
  // 导入提示只反映本次操作，刷新后清空属预期；持久性以上述统计与记录为准
  assert.equal((await page.innerText(BACKUP.status)).trim(), '');
});

test('导入取消保持原数据不变', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  await createTask(page, { name: '原有活动', minutes: 25 });
  await page.click(SEL.start);
  await page.click(SEL.complete);
  const before = await readStore(page);

  await importFromBuffer(page, makeBackup({
    history: [{
      name: '外来记录', category: 'study', plannedMinutes: 25, status: 'completed',
      endedAt: Date.now(), day: '2026-10-23', selfReportedMinutes: 99
    }],
    events: [{ t: Date.now(), s: 'completed', n: '外来记录', m: 99 }]
  }));
  assert.equal(await page.locator(BACKUP.importConfirmBox).isVisible(), true);

  await page.click(BACKUP.importCancel);
  assert.equal(await page.locator(BACKUP.importConfirmBox).isVisible(), false);
  assert.match(await page.innerText(BACKUP.status), /已取消导入/);

  const after = await readStore(page);
  assert.deepEqual(after, before, '取消导入不得修改任何数据');
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
  assert.match(await page.innerText(SEL.history), /原有活动/);
  assert.doesNotMatch(await page.innerText(SEL.history), /外来记录/);
});

test('非法备份一律拒绝：坏 JSON / 错版本 / 超限 / 结构错，且不覆盖原存储', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page } = await openTasksPage(browser, { url: srv.origin + '/' });
  t.after(async () => { await context.close(); });

  await createTask(page, { name: '原始活动', minutes: 25 });
  await page.click(SEL.start);
  await page.click(SEL.complete);
  const before = await readStore(page);

  const cases = [
    { label: '坏 JSON', text: '{ not json at all', expect: /无法解析|不是有效的备份文件/ },
    { label: '版本错误', text: JSON.stringify({ v: 2, current: null, history: [], events: [] }), expect: /版本不支持/ },
    { label: 'history 非数组', text: JSON.stringify({ v: 1, current: null, history: {}, events: [] }), expect: /history/ },
    { label: '状态枚举非法', text: makeBackup({ events: [{ t: 1, s: 'teleported', n: 'x', m: 0 }] }), expect: /事件格式不合法/ },
    { label: '历史超限', text: makeBackup({ history: Array.from({ length: 31 }, () => ({
      name: 'x', category: 'study', plannedMinutes: 25, status: 'completed',
      endedAt: 1, day: '2026-10-23', selfReportedMinutes: 0
    })) }), expect: /超过上限/ },
    { label: '事件超限', text: makeBackup({ events: Array.from({ length: 101 }, () => ({ t: 1, s: 'draft', n: 'x', m: 0 })) }), expect: /超过上限/ },
    { label: 'current 非法', text: JSON.stringify({ v: 1, current: { name: 'x' }, history: [], events: [] }), expect: /current/ }
  ];

  for (const c of cases) {
    await importFromBuffer(page, c.text);
    assert.equal(await page.locator(BACKUP.importConfirmBox).isVisible(), false, c.label + '：不得出现确认框');
    assert.equal(await page.locator(BACKUP.error).isVisible(), true, c.label + '：必须显示可见错误');
    assert.match(await page.innerText(BACKUP.error), c.expect, c.label);
    const now = await readStore(page);
    assert.deepEqual(now, before, c.label + '：不得覆盖原存储');
  }

  // 超大文件（> 256 KiB）同样拒绝
  const huge = makeBackup({ events: Array.from({ length: 99 }, (_, i) => ({ t: i, s: 'draft', n: 'x'.repeat(60), m: 0 })) })
    .padEnd(300 * 1024, ' ');
  await importFromBuffer(page, huge);
  assert.match(await page.innerText(BACKUP.error), /备份文件过大/);
  assert.deepEqual(await readStore(page), before, '超大文件不得覆盖原存储');
  assert.equal((await page.innerText(SEL.statDone)).trim(), '1');
});

test('备份中 running 任务导入后变为已暂停，不跨备份时间流逝、不自动完成', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const context = await browser.newContext();
  const page = await context.newPage();
  t.after(async () => { await context.close(); });

  await page.clock.install({ time: new Date('2026-05-01T00:00:00Z') });
  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  // 运行 5 分钟后导出（快照冻结已用时）
  await createTask(page, { name: '跨设备运行中', minutes: 55 });
  await page.click(SEL.start);
  await page.clock.fastForward(5 * 60 * 1000 + 1000);
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');

  const backupText = (await exportBackupBytes(page)).buffer.toString('utf8');
  const exported = JSON.parse(backupText);
  assert.equal(exported.current.status, 'running');
  assert.equal(exported.current.startedAt, 0, '导出快照不应保留墙钟起点');

  // 清理，然后「三天后」导入同一份备份
  await page.click(SEL.clearBtn);
  await page.click(SEL.clearConfirm);
  await page.clock.fastForward(3 * 24 * 60 * 60 * 1000);

  await importFromBuffer(page, backupText);
  const confirmText = await page.innerText(BACKUP.importConfirmText);
  assert.match(confirmText, /导出时为进行中/);
  assert.match(confirmText, /不会.*流逝|不按导入时的墙钟流逝/);
  await page.click(BACKUP.importConfirm);

  // 计时器是墙钟驱动，不是事件驱动：导出本身不额外流逝时间。
  // 断言的是「不按备份时间流逝」这个性质：导入后剩余时间必须几乎等于导出时的剩余，
  // 而不是「3 天后」应有的 4:59:00，也绝不是自动完成。
  assert.equal((await page.innerText(SEL.badge)).trim(), '已暂停', 'running 必须转为 paused');
  const remaining = (await page.innerText(SEL.remaining)).trim();
  assert.ok(remaining === '50:00' || remaining === '49:59',
    '已用时应按导出快照（5 分钟）保留，实际=' + remaining);
  assert.notEqual(remaining, '04:59', '不得按导入时的墙钟流逝');
  assert.equal((await page.innerText(SEL.statDone)).trim(), '0', '导入不得自动完成');
  const store = await readStore(page);
  assert.equal(store.current.status, 'paused');
  assert.equal(store.current.startedAt, 0);

  // 导入不新增事件：事件数与导出时完全一致
  assert.equal(store.events.length, exported.events.length, '导入不得新增事件');
  assert.deepEqual(store.events, exported.events);
  assert.match(await page.innerText(BACKUP.status), /已暂停/);
});

test('导入备份全程不产生任何 HTTP POST，且面板在 390px 下不新增横向溢出', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await mobile.newPage();
  t.after(async () => { await mobile.close(); });

  const posts = [];
  const pageErrors = [];
  page.on('request', (r) => { if (r.method() === 'POST') posts.push(new URL(r.url()).pathname); });
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  await createTask(page, { name: '移动端备份', minutes: 25 });
  await page.click(SEL.start);
  await page.click(SEL.pause);
  const backupText = (await exportBackupBytes(page)).buffer.toString('utf8');

  await page.click(SEL.clearBtn);
  await page.click(SEL.clearConfirm);
  await importFromBuffer(page, backupText);
  await page.click(BACKUP.importConfirm);

  assert.equal((await page.innerText(SEL.statDone)).trim(), '0');
  assert.match(await page.innerText(SEL.history), /移动端备份/);
  assert.deepEqual(posts, [], '备份导入不得产生任何 HTTP POST');

  // 备份区自身不造成横向溢出
  const backupOverflow = await page.locator('#freeTaskPanel .free-task-backup').evaluate((n) => {
    const limit = document.documentElement.clientWidth;
    let worst = 0;
    n.querySelectorAll('*').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) worst = Math.max(worst, r.right - limit);
    });
    return Math.round(worst);
  });
  assert.ok(backupOverflow <= 4, '备份区不应造成横向溢出，实际=' + backupOverflow);

  // 键盘可用：确认/取消按钮均可聚焦并用 Enter 触发
  await page.evaluate(() => document.getElementById('freeTaskImportBtn').focus());
  assert.equal(await page.evaluate(() => document.activeElement.id), 'freeTaskImportBtn');
  assert.deepEqual(pageErrors.filter((e) => /free-task|freeTask/i.test(e)), []);
});

test('导入写入失败时报告真实失败并保留原数据（不静默覆盖）', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const context = await browser.newContext();
  const page = await context.newPage();
  t.after(async () => { await context.close(); });

  await page.addInitScript(() => {
    const proto = window.Storage.prototype;
    const original = proto.setItem;
    proto.setItem = function (k, v) {
      if (String(k).indexOf('SAL_FREE_TASK_LOCAL_V1') === 0) {
        const err = new Error('QuotaExceededError');
        err.name = 'QuotaExceededError';
        throw err;
      }
      return original.call(this, k, v);
    };
  });

  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  await importFromBuffer(page, makeBackup({
    history: [{
      name: '不应写入', category: 'study', plannedMinutes: 25, status: 'completed',
      endedAt: Date.now(), day: '2026-10-23', selfReportedMinutes: 7
    }],
    events: [{ t: Date.now(), s: 'completed', n: '不应写入', m: 7 }]
  }));
  await page.click(BACKUP.importConfirm);

  assert.equal(await page.locator(BACKUP.error).isVisible(), true);
  assert.match(await page.innerText(BACKUP.error), /写入本地存储失败|导入未保存/);
  assert.equal(await readStore(page), null, '写入失败不得留下任何数据');
  assert.equal((await page.innerText(SEL.statDone)).trim(), '0');
  assert.doesNotMatch(await page.innerText(SEL.history), /不应写入/, '页面内存也不得被失败写入污染');
});

/**
 * 以下用例覆盖 LT_RETENTION_FREE_TASK_HOME_STATUS_20261023_T：
 * 首页「抽卡」页的**当前自由任务只读状态条**（#freeTaskHomeStatus）。
 *
 * 硬约束：
 * - 沿用上方同一台只读静态服务器与隔离 GET mock，不新增 mock、不写任何文件；
 * - 展示层复用 free-task.js 已有的 current / tick：不新增定时器、不新增数据源；
 * - 断言全部来自真实点击 / 输入 / 真实 DOM 文本，不伪造状态。
 */

const HOME = {
  status: '#freeTaskHomeStatus',
  text: '#freeTaskHomeStatusText',
  clock: '#freeTaskHomeStatusClock'
};

/** 读首页状态条的可听文本区（名称 + 状态），归一空白。 */
async function homeHead(page) {
  return (await page.innerText(HOME.text)).replace(/\s+/g, ' ').trim();
}

/** 读首页状态条里 aria-hidden 的视觉倒计时。 */
async function homeClock(page) {
  return (await page.innerText(HOME.clock)).replace(/\s+/g, ' ').trim();
}

function clockSeconds(text) {
  const m = String(text).match(/(\d{2}):(\d{2})/);
  return m ? (Number(m[1]) * 60 + Number(m[2])) : -1;
}

test('首页状态条：无活动隐藏；运行显示真实名/状态/递减剩余；暂停固定、恢复继续；三种终态隐藏；HTML 名按字面显示；无 POST、无自动事件、旧 DOM 不变', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const { context, page, pageErrors, posts } = await openGachaHome(browser, srv);
  t.after(async () => { await context.close(); });

  // --- 1) 没有活动时：状态条存在但隐藏；a11y 分工正确 ---
  assert.equal(await page.locator(HOME.status).count(), 1, '首页必须有只读状态条节点');
  assert.equal(await page.locator(HOME.status).isVisible(), false, '无活动时必须隐藏');
  assert.equal(await page.locator(HOME.text).getAttribute('aria-live'), 'polite',
    '状态变化才播报：aria-live 应在状态文本 span 上');
  assert.equal(await page.locator(HOME.text).getAttribute('aria-atomic'), 'true');
  assert.equal(await page.locator(HOME.clock).getAttribute('aria-hidden'), 'true',
    '每秒变动的剩余时间不得高频播报');

  // --- 2) 创建并开始 → 回首页：显示真实名 + 运行状态 + 剩余时间 ---
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await createTask(page, { name: '复习第三章', minutes: 25 });
  await page.click(SEL.start);
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');

  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：复习第三章 · 进行中');
  const run1 = await homeClock(page);
  assert.match(run1, /剩余 \d{2}:\d{2}/);
  assert.ok(clockSeconds(run1) > 24 * 60 && clockSeconds(run1) <= 25 * 60,
    '刚开始时剩余应接近 25:00，实际=' + run1);

  // --- 3) 运行中：首页剩余时间持续递减（既有 tick，不是第二计时器）---
  await page.waitForTimeout(1600);
  const run2 = await homeClock(page);
  assert.ok(clockSeconds(run2) < clockSeconds(run1),
    '运行中剩余时间必须递减：' + run1 + ' → ' + run2);
  assert.equal(await homeHead(page), '自由任务：复习第三章 · 进行中', '名称/状态不得跳变');

  // --- 4) 点既有快捷入口回任务页：同一个 current 未丢 ---
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  assert.equal(await page.innerText(SEL.currentName), '复习第三章');
  assert.equal((await page.innerText(SEL.badge)).trim(), '进行中');
  const storeMid = await readStore(page);
  assert.equal(storeMid.current.name, '复习第三章');
  assert.equal(storeMid.current.status, 'running');

  // --- 5) 只读展示层不会自动写任何本地记录（往返导航零写入）---
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.deepEqual(await readStore(page), storeMid, '往返导航不得写入任何本地记录');

  // --- 6) 暂停：回首页剩余时间固定 ---
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await page.click(SEL.pause);
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：复习第三章 · 已暂停');
  const p1 = await homeClock(page);
  await page.waitForTimeout(1700);
  const p2 = await homeClock(page);
  assert.equal(p2, p1, '暂停时剩余时间必须固定：' + p1 + ' vs ' + p2);

  // --- 7) 恢复：继续递减 ---
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await page.click(SEL.resume);
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  const r1 = await homeClock(page);
  await page.waitForTimeout(1700);
  const r2 = await homeClock(page);
  assert.ok(clockSeconds(r2) < clockSeconds(r1) && clockSeconds(r1) <= clockSeconds(p1),
    '恢复后剩余时间应继续递减，实际=' + r1 + ' → ' + r2);

  // --- 8) 三种终态（完成 / 中断 / 失败）后首页状态条一律隐藏 ---
  const terminals = [
    { name: '终态-完成', btn: SEL.complete, label: '已完成' },
    { name: '终态-中断', btn: SEL.interrupt, label: '已中断' },
    { name: '终态-失败', btn: SEL.fail, label: '失败' }
  ];
  for (const term of terminals) {
    await page.click(SEL.homeShortcut);
    await page.waitForSelector(SEL.panel, { state: 'visible' });
    // 先回到「无当前活动」：已有活动若是进行中需先中断，终态则直接再次创建
    if (await page.locator(SEL.reset).isVisible()) {
      await page.click(SEL.reset);
    } else {
      await page.click(SEL.interrupt);
      await page.click(SEL.reset);
    }
    await page.waitForSelector(SEL.form, { state: 'visible' });
    await createTask(page, { name: term.name, minutes: 25 });
    await page.click(SEL.start);
    await page.click(SEL.navGacha);
    await page.waitForSelector(HOME.status, { state: 'visible' });
    assert.equal(await homeHead(page), '自由任务：' + term.name + ' · 进行中');
    await page.click(SEL.homeShortcut);
    await page.waitForSelector(SEL.panel, { state: 'visible' });
    await page.click(term.btn);
    assert.equal((await page.innerText(SEL.badge)).trim(), term.label);
    await page.click(SEL.navGacha);
    await page.waitForSelector(HOME.status, { state: 'hidden' });
    assert.equal(await page.locator(HOME.status).isVisible(), false,
      term.label + ' 后首页状态条必须隐藏');
  }

  // --- 9) HTML 注入的活动名：按字面文本显示，不生成元素、不执行 ---
  const payload = '<img src=x onerror="window.__salFreeTaskHomeXss=1">';
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  if (await page.locator(SEL.reset).isVisible()) await page.click(SEL.reset);
  else { await page.click(SEL.interrupt); await page.click(SEL.reset); }
  await page.waitForSelector(SEL.form, { state: 'visible' });
  await createTask(page, { name: payload, minutes: 25 });
  await page.click(SEL.start);
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：' + payload + ' · 进行中');
  assert.equal(await page.locator(HOME.status + ' img').count(), 0, '活动名不得被解析为 HTML');
  assert.equal(await page.evaluate(() => window.__salFreeTaskHomeXss), undefined);

  // --- 10) 旧抽卡 DOM / dock 保留；展示层不产生任何 POST ---
  assert.equal(await page.locator(SEL.pageGacha).isVisible(), true);
  assert.equal(await page.locator(SEL.gachaBtn).count(), 1, '旧抽卡按钮必须保留');
  assert.equal(await page.locator('#gachaMultiBtn').count(), 1, '旧连抽按钮必须保留');
  assert.equal(await page.locator('#page-gacha .gacha-draw-stage').count(), 1, '旧抽卡 dock 必须保留');
  assert.equal(await page.locator(SEL.oldTimerPanel).count(), 1);
  assert.deepEqual(posts.filter((p) => /gacha/i.test(p)), [], '只读状态条不得触发任何抽卡 POST');
  assert.deepEqual(posts, [], '自由任务展示层不得产生任何 HTTP POST');
  assert.deepEqual(pageErrors.filter((e) => /free-task|freeTask/i.test(e)), []);
});

test('刷新与备份导入后首页状态条正确：running 恢复并递减、paused 固定、导入 running→paused 不跨备份时间流逝', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const context = await browser.newContext();
  const page = await context.newPage();
  t.after(async () => { await context.close(); });
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  await page.clock.install({ time: new Date('2026-06-01T00:00:00Z') });
  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });

  await createTask(page, { name: '刷新验证活动', minutes: 55 });
  await page.click(SEL.start);
  await page.clock.fastForward(5 * 60 * 1000 + 1000);

  // 首页：running，剩余 50:00 附近
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：刷新验证活动 · 进行中');
  const beforeReload = clockSeconds(await homeClock(page));
  assert.ok(beforeReload >= 49 * 60 && beforeReload <= 50 * 60,
    '运行 5 分钟后剩余应约 50:00，实际=' + beforeReload);

  // 刷新：running 按真实墙钟恢复，并在首页继续递减
  await page.clock.fastForward(60 * 1000);
  await page.reload({ waitUntil: 'load' });
  await page.waitForSelector(SEL.homeShortcut, { state: 'visible' });
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：刷新验证活动 · 进行中',
    '刷新后 running 必须恢复');
  const afterReload = clockSeconds(await homeClock(page));
  assert.ok(afterReload >= 48 * 60 && afterReload <= 49 * 60 + 2,
    '刷新后应按墙钟继续（约 49:00），实际=' + afterReload);
  await page.clock.fastForward(60 * 1000);
  const afterForward = clockSeconds(await homeClock(page));
  assert.ok(afterForward < afterReload, '刷新后首页剩余必须继续递减');

  // 暂停 → 刷新：paused 保持，剩余固定
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await page.click(SEL.pause);
  await page.reload({ waitUntil: 'load' });
  await page.waitForSelector(SEL.homeShortcut, { state: 'visible' });
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：刷新验证活动 · 已暂停');
  const pausedNow = await homeClock(page);
  await page.clock.fastForward(2 * 60 * 60 * 1000);
  assert.equal(await homeClock(page), pausedNow, 'paused 刷新后剩余必须固定');
  assert.equal(await homeHead(page), '自由任务：刷新验证活动 · 已暂停');

  // S 的导入语义：备份里 running → 导入后 paused，首页提示正确且不跨备份时间流逝
  await page.click(SEL.navTasks);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await page.click(SEL.resume);
  await page.clock.fastForward(30 * 1000);
  const exported = JSON.parse((await exportBackupBytes(page)).buffer.toString('utf8'));
  assert.equal(exported.current.status, 'running');

  await page.click(SEL.clearBtn);
  await page.click(SEL.clearConfirm);
  await page.waitForSelector(HOME.status, { state: 'hidden' });
  assert.equal(await page.locator(HOME.status).isVisible(), false, '清空后首页状态条隐藏');

  await page.clock.fastForward(3 * 24 * 60 * 60 * 1000);
  await importFromBuffer(page, JSON.stringify(exported));
  await page.waitForSelector(BACKUP.importConfirmBox, { state: 'visible' });
  await page.click(BACKUP.importConfirm);
  await page.waitForSelector(BACKUP.importConfirmBox, { state: 'hidden' });

  // 状态条在首页（#page-gacha）内：先回抽卡页再断言可见性
  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await homeHead(page), '自由任务：刷新验证活动 · 已暂停',
    '导入的 running 必须显示为已暂停');
  const imported = clockSeconds(await homeClock(page));
  // 期望值直接由备份快照推导：导入后剩余 = 计划时长 - 快照已用时
  const expectedFromSnapshot = 55 * 60 - Math.floor(exported.current.accumulatedMs / 1000);
  assert.ok(Math.abs(imported - expectedFromSnapshot) <= 1,
    '导入后剩余必须等于导出快照剩余（' + expectedFromSnapshot + 's），实际=' + imported + 's');
  assert.ok(imported > 24 * 60, '绝不得按 3 天后的墙钟流逝（那样会直接到时/清零）');
  assert.ok(imported < afterForward, '导出前还在继续递减，导入值应小于更早的读数');
  const storeAfterImport = await readStore(page);
  assert.equal(storeAfterImport.current.status, 'paused', '导入 running 必须落为 paused');

  assert.deepEqual(pageErrors.filter((e) => /free-task|freeTask/i.test(e)), []);
});

test('390px 下首页状态条可见可读、不新增横向溢出，旧抽卡控件布局不变', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const srv = await startStaticServer();
  t.after(async () => { await srv.close(); });

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await mobile.newPage();
  t.after(async () => { await mobile.close(); });

  const posts = [];
  const pageErrors = [];
  page.on('request', (r) => { if (r.method() === 'POST') posts.push(new URL(r.url()).pathname); });
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  await page.goto(srv.origin + '/', { waitUntil: 'load' });
  await page.waitForSelector(SEL.homeShortcut, { state: 'visible' });
  assert.equal(await page.locator(HOME.status).isVisible(), false);

  // 故意用接近上限的超长活动名，逼出换行压力
  const longName = '复习第三章'.repeat(7);
  await page.click(SEL.homeShortcut);
  await page.waitForSelector(SEL.panel, { state: 'visible' });
  await createTask(page, { name: longName, minutes: 25 });
  await page.click(SEL.start);

  await page.click(SEL.navGacha);
  await page.waitForSelector(HOME.status, { state: 'visible' });
  assert.equal(await page.locator(SEL.pageGacha).isVisible(), true);
  assert.equal(await homeHead(page), '自由任务：' + longName + ' · 进行中');
  assert.match(await homeClock(page), /剩余 \d{2}:\d{2}/);

  // 状态条自身（含超长名字）不得造成横向溢出
  const worst = await page.locator(HOME.status).evaluate((n) => {
    const limit = document.documentElement.clientWidth;
    let out = 0;
    n.querySelectorAll('*').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) out = Math.max(out, r.right - limit, -r.left);
    });
    return Math.round(out);
  });
  assert.ok(worst <= 4, '首页状态条不应造成横向溢出，实际=' + worst);

  // 入口行与既有抽卡控件在 390px 下同样不溢出
  const rowOverflow = await page.locator(SEL.homeShortcutRow).evaluate((n) => {
    const limit = document.documentElement.clientWidth;
    let out = 0;
    n.querySelectorAll('*').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) out = Math.max(out, r.right - limit, -r.left);
    });
    return Math.round(out);
  });
  assert.ok(rowOverflow <= 4, '首页入口自身不得造成横向溢出，实际=' + rowOverflow);
  assert.equal(await page.locator(SEL.gachaBtn).isVisible(), true);
  assert.equal(await page.locator('#gachaMultiBtn').isVisible(), true);

  assert.deepEqual(posts, [], '移动端只读状态条不得产生任何 HTTP POST');
  assert.deepEqual(pageErrors.filter((e) => /free-task|freeTask/i.test(e)), []);
});
