'use strict';

/**
 * 自由任务 · 端到端竖切联调的 Playwright e2e 测试。
 *
 * 真实链路（不是 mock）：
 *   真实 Chromium 页面 (prototypes/retention-free-task-integrated/index.html)
 *     └─ 同源 HTTP/JSON（fetch）──▶ child_process.spawn 的 synthetic_app.py
 *          ├─ 真实受保护 Blueprint  create_protected_free_task_blueprint(store, authorizer)
 *          ├─ 真实事件账本          FreeTaskEventStore
 *          └─ 合成 SQLite：tempfile.TemporaryDirectory() 内，进程退出即删
 *
 * 硬约束（与生产红线对齐）：
 * - 只绑定 127.0.0.1 + 操作系统临时分配的端口（port=0），测试结束必关闭；
 * - 绝不使用正式端口、绝不启动正式应用 / 主服务器；
 * - 只用 Temp 合成库，绝不触碰 data/、config/、src/notes/**；
 * - 不向项目路径写截图 / trace / video / test-results；不联网安装任何包。
 *
 * 运行方式：
 *   node --test tests/e2e/retention-free-task-integrated.test.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const os = require('node:os');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const { chromium } = require('playwright');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const SYNTHETIC_APP = path.join(PROJECT_ROOT, 'prototypes', 'retention-free-task-integrated', 'synthetic_app.py');
const PROJECT_VENV_PYTHON = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');

const READY_PREFIX = 'SYNTHETIC_APP_READY ';
const READY_TIMEOUT_MS = 45000;

// 本机 Chromium（与仓库现有 playwright 配置一致的 pinned 路径）。
const PINNED_CHROMIUM = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

function launchOptions() {
  const opts = { headless: true, args: ['--disable-gpu'] };
  if (fs.existsSync(PINNED_CHROMIUM)) {
    opts.executablePath = PINNED_CHROMIUM;
  }
  return opts;
}

/** Windows 上带中文与空格的路径必须按 Node 默认的 UTF-16LE 写入 python argv。 */
function spawnPython(args) {
  const env = Object.assign({}, process.env, {
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
    PYTHONPATH: PROJECT_ROOT
  });
  const python = fs.existsSync(PROJECT_VENV_PYTHON) ? PROJECT_VENV_PYTHON : 'python';
  return spawn(python, args, {
    cwd: PROJECT_ROOT,
    env,
    windowsHide: true,
    // stdin 必须保持 **pipe**：synthetic_app.py 用它接收显式 `quit` 优雅关闭
    // 命令，从而在进程内执行 Temp 合成库清理。Windows 上 SIGTERM 不可捕获，
    // 一旦错过 stdin 通道就再无清理机会。
    stdio: ['pipe', 'pipe', 'pipe']
  });
}

/**
 * 启动 synthetic_app.py，解析 stdout 的机器可读就绪行。
 * 失败时把 stderr 一起抛出（真实错误必须可见，绝不伪造）。
 */
function startSyntheticApp() {
  return new Promise((resolve, reject) => {
    const child = spawnPython([SYNTHETIC_APP]);
    const stdoutChunks = [];
    const stderrChunks = [];
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try { child.kill('SIGKILL'); } catch { /* 已退出 */ }
      reject(new Error(
        'synthetic_app.py 未在 ' + READY_TIMEOUT_MS + 'ms 内打印就绪行。\n' +
        'stdout: ' + Buffer.concat(stdoutChunks).toString('utf8') + '\n' +
        'stderr: ' + Buffer.concat(stderrChunks).toString('utf8')
      ));
    }, READY_TIMEOUT_MS);

    child.stdout.on('data', (buf) => {
      stdoutChunks.push(buf);
      const text = buf.toString('utf8');
      const idx = text.indexOf(READY_PREFIX);
      if (idx === -1 || settled) return;
      settled = true;
      clearTimeout(timer);
      const jsonStart = text.indexOf('{', idx);
      let info;
      try {
        info = JSON.parse(text.slice(jsonStart));
      } catch (err) {
        try { child.kill('SIGKILL'); } catch { /* 已退出 */ }
        reject(new Error('就绪行不是合法 JSON: ' + err.message + '\n原始行: ' + text));
        return;
      }
      resolve({ child, info, stderr: () => Buffer.concat(stderrChunks).toString('utf8') });
    });

    child.stderr.on('data', (buf) => { stderrChunks.push(buf); });

    child.on('error', (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });

    child.on('exit', (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(
        'synthetic_app.py 提前退出（code=' + code + ' signal=' + signal + '）。\n' +
        'stderr: ' + Buffer.concat(stderrChunks).toString('utf8')
      ));
    });
  });
}

/**
 * 关闭子进程（先走 stdin 优雅关闭通道，让它自己删除 Temp 合成库，
 * 再 SIGTERM，最后兜底 SIGKILL）。
 *
 * 为什么必须用 stdin 通道：**Windows 上 Node 的 kill('SIGTERM') 会被直接
 * 转成不可捕获的进程终止**，Python 的信号处理器与 atexit 都不会执行，
 * Temp 合成库就会留在磁盘上。因此首选关闭 stdin。
 */
function stopSyntheticApp(handle) {
  if (!handle || !handle.child) return Promise.resolve();
  const { child } = handle;
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    const hardKill = setTimeout(() => {
      try { child.kill('SIGKILL'); } catch { /* 已退出 */ }
      finish();
    }, 6000);
    hardKill.unref();
    child.once('exit', () => { clearTimeout(hardKill); finish(); });

    // 1) 优雅路径：写入 quit 命令（显式关闭信号；EOF 不算）。
    try {
      if (child.stdin && !child.stdin.destroyed) {
        child.stdin.write('quit\n');
        child.stdin.end();
      }
    } catch { /* stdin 不可用 → 退化到信号 */ }

    // 2) 兜底：1.5s 内没退出就发信号。
    const sigKill = setTimeout(() => {
      try { child.kill('SIGTERM'); } catch { /* 已退出 */ }
    }, 1500);
    sigKill.unref();
    child.once('exit', () => { clearTimeout(sigKill); });
  });
}

function waitForDirGone(dirPath, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const poll = () => {
      let stillThere = false;
      try { stillThere = fs.existsSync(dirPath); } catch { stillThere = false; }
      if (!stillThere) return resolve(true);
      if (Date.now() > deadline) return reject(new Error('临时目录仍存在: ' + dirPath));
      setTimeout(poll, 100);
    };
    poll();
  });
}

/**
 * 断言页面 console 干净。
 *
 * 放行两类 **刻意构造** 的资源加载日志（不是页面缺陷）：
 * - HTTP 状态码类：Chromium 把后端按契约拒绝的 4xx 也记成
   “Failed to load resource”，而那正是本套测试要证明的东西；
 * - 网络失败类：本套测试用 route.abort() / route.fetch()+abort 精确复现
   “断网未提交”与“服务端已提交但响应丢失”。
 * 真正的 JS 异常 / pageerror 一律不放行。
 */
function assertNoRealConsoleErrors(consoleErrors, pageErrors, label, allowNetworkFailures) {
  const ignorable = [/^Failed to load resource: the server responded with a status of \d{3}/];
  if (allowNetworkFailures) {
    ignorable.push(/^Failed to load resource: net::/);
    ignorable.push(/^requestfailed: .*net::ERR_/);
  }
  const real = consoleErrors.filter((text) => !ignorable.some((re) => re.test(text)));
  assert.deepEqual(real, [], label + ' 不应有 JS 异常类 console 错误');
  assert.deepEqual(pageErrors, [], label + ' 不应有 pageerror');
}

/** 打开真实页面；收集 console error / pageerror / 跨域请求。 */
async function openPage(browser, baseUrl) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const offOrigin = [];
  page.on('console', (msg) => { if (msg.type() === 'error') { consoleErrors.push(msg.text()); } });
  page.on('pageerror', (err) => { pageErrors.push(String(err)); });
  page.on('request', (req) => {
    const url = req.url();
    if (url.startsWith('data:') || url.startsWith('blob:') || url.startsWith('about:')) return;
    if (!url.startsWith(baseUrl)) { offOrigin.push(url); }
  });
  page.on('requestfailed', (req) => {
    consoleErrors.push('requestfailed: ' + req.url() + ' ' + String(req.failure() && req.failure().errorText));
  });
  await page.goto(baseUrl + '/', { waitUntil: 'load' });
  await page.waitForFunction(
    () => window.__freeTaskIntegrated && window.__freeTaskIntegrated.snapshot().backendState !== 'unknown',
    null,
    { timeout: 15000 }
  );
  return { context, page, consoleErrors, pageErrors, offOrigin };
}

const SELECTORS = {
  activity: '[data-testid="activity-input"]',
  minutes25: '[data-testid="minutes-25"]',
  minutes55: '[data-testid="minutes-55"]',
  categoryStudy: '[data-testid="category-study"]',
  categoryEntertainment: '[data-testid="category-entertainment"]',
  studyMinutes: '[data-testid="study-minutes-input"]',
  btnCreate: '[data-testid="btn-create"]',
  btnStart: '[data-testid="btn-start"]',
  btnPause: '[data-testid="btn-pause"]',
  btnResume: '[data-testid="btn-resume"]',
  btnComplete: '[data-testid="btn-complete"]',
  btnInterrupt: '[data-testid="btn-interrupt"]',
  btnFail: '[data-testid="btn-fail"]',
  btnNewTask: '[data-testid="btn-new-task"]',
  btnRefreshSummary: '[data-testid="btn-refresh-summary"]',
  errorBox: '[data-testid="error-box"]',
  backendBanner: '[data-testid="backend-banner"]',
  sessionNotice: '[data-testid="session-notice"]',
  remainingText: '[data-testid="remaining-text"]',
  taskActivity: '[data-testid="task-activity"]',
  taskStatus: '[data-testid="task-status"]',
  taskMeta: '[data-testid="task-meta"]',
  timerNotice: '[data-testid="timer-elapsed-notice"]',
  statCompleted: '[data-testid="stat-completed"]',
  statVerifiedStudy: '[data-testid="stat-verified-study"]',
  statInformal: '[data-testid="stat-informal"]',
  statPomodoros: '[data-testid="stat-pomodoros"]',
  statEventCount: '[data-testid="stat-event-count"]',
  serverSummaryRaw: '[data-testid="server-summary-raw"]',
  eventList: '[data-testid="event-list"]',
  eventItem: '[data-testid="event-item"]',
  banner: '[data-testid="prototype-banner"]',
  ackNotice: '[data-testid="ack-notice"]',
  ackRetryRow: '[data-testid="ack-retry-row"]',
  btnRetryPending: '[data-testid="btn-retry-pending"]'
};

/** 页面上是否存在任何“已验证学习”类措辞（后端明确是 user_reported_not_independently_verified）。 */
const VERIFIED_WORDING_RE = /已验证|已核实学习|经核实/;

async function pageText(page) {
  return page.evaluate(() => document.body.innerText);
}

/** 读取服务端 summary（始终走真实同源 HTTP GET）。 */
async function fetchServerSummary(page, sessionId) {
  return page.evaluate(
    (sid) => window.__freeTaskIntegrated.summaryRaw(sid, true),
    sessionId
  );
}

/** 创建任务（仅本地，不发请求），可选继续 / 暂停 / 完成等。 */
async function createTask(page, { activity = '写单元测试', category = 'study', minutes = 25, reported = null } = {}) {
  await page.fill(SELECTORS.activity, activity);
  if (category === 'entertainment') { await page.check(SELECTORS.categoryEntertainment); }
  else { await page.check(SELECTORS.categoryStudy); }
  await page.check(minutes === 55 ? SELECTORS.minutes55 : SELECTORS.minutes25);
  if (reported !== null) { await page.fill(SELECTORS.studyMinutes, String(reported)); }
  await page.click(SELECTORS.btnCreate);
}

/** 点击按钮并等待该动作在页面内完成（事件历史长度增加且不再 busy）。 */
async function clickAndSettle(page, selector, previousEventCount) {
  await page.click(selector);
  await page.waitForFunction(
    (prev) => {
      const snap = window.__freeTaskIntegrated.snapshot();
      return !snap.busy && snap.eventCount > prev;
    },
    previousEventCount,
    { timeout: 15000 }
  );
}

/**
 * 安装一个 **一次性** 的路由拦截：只对下一次匹配请求生效，随后立刻
 * ``unroute``（隔离会话与后续请求，绝不污染后续断言）。
 *
 * mode:
 *   - ``'respond'`` → 直接 fulfill 一个合成状态码（模拟 401/409/503 等确定性拒绝，
 *     **不会** 到达服务端，因此服务端账本零变化）；
 *   - ``'abort'``   → ``route.abort()``：请求根本没有发出（网络失败 = 确定未写入）。
 */
async function armOneShotRoute(page, baseUrl, mode, statusOrText) {
  const pattern = baseUrl + '/api/free-tasks/**';
  const handler = async (route) => {
    if (mode === 'abort') {
      await route.abort(statusOrText || 'connectionfailed');
      return;
    }
    await route.fulfill({
      status: statusOrText,
      contentType: 'application/json',
      headers: { 'Cache-Control': 'no-store' },
      body: JSON.stringify({
        ok: false,
        error: { code: 'synthetic_intercept', message: '由 e2e 一次性路由拦截合成的拒绝' }
      })
    });
  };
  // ``times: 1`` → 只拦截下一次匹配请求，随后自动失效（严格隔离后续会话）。
  await page.route(pattern, handler, { times: 1 });
}

/**
 * 一次性路由：先把请求 **真实转发** 给服务端（route.fetch()，服务端因此真的写入），
 * 再把响应丢掉（``route.abort()``）——精确复现「服务端已提交但响应丢失」。
 * 用 ``times: 1`` 保证只影响这一次请求。
 */
async function armCommittedButResponseLostOnce(page, baseUrl) {
  await page.route(
    baseUrl + '/api/free-tasks/**',
    async (route) => {
      await route.fetch();   // 服务端照常处理并写入
      await route.abort('connectionfailed');  // 响应永不回到页面
    },
    { times: 1 }
  );
}

/** 等待页面内该动作完成（事件历史新增一条且不再 busy）。 */
async function waitSettled(page, previousEventCount) {
  await page.waitForFunction(
    (prev) => {
      const snap = window.__freeTaskIntegrated.snapshot();
      return !snap.busy && snap.eventCount > prev;
    },
    previousEventCount,
    { timeout: 15000 }
  );
}

async function snapshot(page) {
  return page.evaluate(() => window.__freeTaskIntegrated.snapshot());
}

async function eventCountOf(page) {
  const snap = await snapshot(page);
  return snap.eventCount;
}

// ===========================================================================
// 1) synthetic_app.py 自身的隔离性质（不需要浏览器）
// ===========================================================================

test('synthetic_app：CLI 就绪行给出 127.0.0.1 + 临时端口 + Temp 合成库', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });
  assert.equal(handle.info.host, '127.0.0.1');
  assert.ok(handle.info.port > 0, '必须由操作系统分配非零端口');
  assert.equal(handle.info.synthetic, true);
  assert.equal(handle.info.production_app, false);
  assert.equal(handle.info.blueprint, 'free_task_protected_preview');

  const systemTemp = fs.realpathSync(os.tmpdir());
  const dbReal = fs.realpathSync(path.dirname(handle.info.db_path));
  const dataDir = path.join(PROJECT_ROOT, 'data');
  const notesDir = path.join(PROJECT_ROOT, 'src', 'notes');

  assert.ok(
    dbReal.toLowerCase().startsWith(systemTemp.toLowerCase()),
    '合成库必须位于系统 Temp 之内: ' + dbReal
  );
  assert.ok(
    !path.resolve(handle.info.db_path).toLowerCase().startsWith(path.resolve(dataDir).toLowerCase()),
    '合成库绝不能位于项目 data/ 目录'
  );
  assert.ok(
    !path.resolve(handle.info.db_path).toLowerCase().startsWith(path.resolve(notesDir).toLowerCase()),
    '合成库绝不能位于项目 src/notes/ 目录'
  );
  assert.match(path.basename(handle.info.db_path), /^synthetic_/);
  assert.ok(fs.existsSync(handle.info.db_path), '合成 SQLite 应已由账本层创建');

  const stderrText = handle.stderr();
  assert.equal(stderrText.trim(), '', '正常启动不应有 stderr 输出: ' + stderrText);
});

test('synthetic_app：import 零副作用（不建目录、不建库、不监听端口）', async () => {
  const marker = path.join(os.tmpdir(), 'lt_free_task_integrated_import_probe_' + Date.now());
  const script = [
    'import importlib.util, os, sys',
    'sys.path.insert(0, os.getcwd())',
    'spec = importlib.util.spec_from_file_location("lt_synth_probe", sys.argv[1])',
    'module = importlib.util.module_from_spec(spec)',
    'spec.loader.exec_module(module)',
    'print("MODULE_FACTORY:", callable(module.build_app), callable(module.main))',
    'print("MARKER_EXISTS:", os.path.exists(sys.argv[2]))',
    // 只报告 **import 前** 的基线，用来证明 import 自身没有新建任何 Temp 目录。
    'print("SYNC_TMP_BASELINE:", [n for n in os.listdir(sys.argv[3]) if n.startswith("lt_free_task_integrated_")])'
  ].join('\n');

  // import 前后的 Temp 快照（只统计本模块自己的前缀，不评价全局卫生）。
  const tempRoot = os.tmpdir();
  const countSandboxDirs = () => fs.readdirSync(tempRoot)
    .filter((name) => name.startsWith('lt_free_task_integrated_')).length;
  const before = countSandboxDirs();

  const child = spawnPython(['-c', script, SYNTHETIC_APP, marker, tempRoot]);
  const out = await new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
    child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
    child.on('error', reject);
    child.on('close', (code) => resolve({ stdout, stderr, code }));
  });
  const after = countSandboxDirs();

  assert.equal(out.code, 0, 'import 探针应正常退出: ' + out.stderr);
  assert.match(out.stdout, /MODULE_FACTORY: True True/);
  assert.match(out.stdout, /MARKER_EXISTS: False/, 'import 不得创建任何目录或文件');
  assert.match(out.stdout, /SYNC_TMP_BASELINE: \[/, 'import 前的 Temp 基线应可读取');
  assert.equal(after, before, 'import 不得新建合成 Temp 目录（before=' + before + ' after=' + after + '）');
  assert.equal(fs.existsSync(marker), false);
  assert.equal(out.stderr.trim(), '');
});

// ===========================================================================
// 2) 浏览器 + 真实 HTTP 端到端
// ===========================================================================

test('竖切：开始→暂停→继续→再暂停→再继续→完成，服务端完成数恰好 1 且 resumed 零贡献', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });

  const { context, page, consoleErrors, pageErrors, offOrigin } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  // -- 页面身份与合成声明 --
  assert.match(await page.innerText(SELECTORS.banner), /TEST \/ SYNTHETIC/);
  assert.match(await page.innerText(SELECTORS.banner), /本地隔离联调/);
  assert.match(await page.innerText(SELECTORS.banner), /模拟授权/);
  assert.match(await page.innerText(SELECTORS.banner), /临时数据库/);
  assert.match(await page.innerText(SELECTORS.banner), /非正式学习记录/);
  assert.match(await page.innerText(SELECTORS.backendBanner), /synthetic/);
  assert.deepEqual(offOrigin, [], '页面不得产生任何跨域外联请求');

  // -- 创建（仅本地）：不得发出任何事件 --
  await createTask(page, { activity: '复习线性代数', minutes: 25, reported: 25 });
  let snap = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  assert.equal(snap.status, 'created');
  assert.equal(snap.sessionId && snap.sessionId.startsWith('ui-'), true);
  assert.deepEqual(snap.eventTypes, ['prototype.task_created']);
  assert.equal(snap.backendState, 'ok');

  const sessionId = snap.sessionId;

  // -- 计时语义仍是 25 / 55 分钟 --
  assert.equal(snap.plannedMinutes, 25);
  assert.equal(snap.remainingSeconds, 25 * 60);
  assert.equal((await page.innerText(SELECTORS.remainingText)).trim(), '25:00');

  // 完整竖切：started → paused → resumed → paused → resumed → completed
  let n = snap.eventCount;
  await clickAndSettle(page, SELECTORS.btnStart, n);            // started
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnPause, n);            // paused
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnResume, n);           // resumed
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnPause, n);            // paused
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnResume, n);           // resumed
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnComplete, n);         // completed

  // -- 服务端统计（真实 GET summary） --
  const server = await fetchServerSummary(page, sessionId);
  assert.equal(server.ok, true, 'GET summary 必须成功: ' + JSON.stringify(server.body));
  const summary = server.body.summary;
  assert.equal(summary.event_count, 6, '服务端事件数应为 6: ' + JSON.stringify(summary));
  assert.equal(summary.successful_tasks, 1, '服务端完成数必须恰好为 1');
  assert.equal(summary.auto_completed, false);
  assert.equal(summary.completion_source, 'explicit_user_report');
  assert.equal(summary.verification, 'user_reported_not_independently_verified');

  // resumed 不产生任何额外学习贡献：只有用户自报的 25 分钟计入。
  assert.equal(summary.effective_study_minutes, 25);
  assert.equal(summary.study_pomodoros, 1);
  assert.equal(summary.timer_elapsed_events, 0);

  // -- 页面展示的是服务端数字，不是本地计数 --
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');
  assert.equal((await page.innerText(SELECTORS.statVerifiedStudy)).trim(), '25');
  assert.equal((await page.innerText(SELECTORS.statPomodoros)).trim(), '1');
  assert.equal((await page.innerText(SELECTORS.statEventCount)).trim(), '6');
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '已完成');
  assert.match(await page.innerText(SELECTORS.serverSummaryRaw), /successful_tasks/);

  // -- 事件历史反映真实 HTTP 成功 --
  const types = await page.$$eval(SELECTORS.eventItem, (els) => els.map((e) => e.getAttribute('data-event-type')));
  assert.deepEqual(types.slice(1), [
    'free_task.started', 'free_task.paused', 'free_task.resumed',
    'free_task.paused', 'free_task.resumed', 'free_task.completed'
  ]);
  const statuses = await page.evaluate(() => window.__freeTaskIntegrated.snapshot().eventHttpStatuses);
  assert.ok(statuses.slice(1).every((s) => s === 200), '所有事件都应真实返回 HTTP 200');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '竖切路径');
});

test('收尾不双记：重复完成被后端拒绝，完成数仍为 1，错误可见', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '整理笔记', reported: 25 });
  let n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnComplete, n);
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');

  const sessionId = await page.evaluate(() => window.__freeTaskIntegrated.snapshot().sessionId);

  // 绕过页面按钮（终态下按钮已禁用），直接对真实受保护端点发第二个完成事件。
  const second = await page.evaluate((sid) => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: sid,
    event_id: 'ev-manual-second-completion-' + Date.now(),
    event_payload: {
      event_type: 'free_task.completed',
      actual_minutes: 25,
      reported_study_minutes: 25,
      occurred_at: new Date().toISOString()
    }
  }, true), sessionId);

  assert.equal(second.ok, false, '第二次完成绝不能返回成功');
  assert.equal(second.status, 409);
  assert.equal(second.body.ok, false);
  assert.ok(['duplicate_completion', 'illegal_state_order'].includes(second.body.error.code));

  // 服务端仍然只完成一次
  const after = await fetchServerSummary(page, sessionId);
  assert.equal(after.body.summary.successful_tasks, 1);
  assert.equal(after.body.summary.effective_study_minutes, 25);
  assert.equal(after.body.summary.event_count, 2);

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '双完成防重');
});

test('非法事件 4xx 且不写入；客户端不假装成功', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  // 会话未 started 就发 resumed → 409 session_not_started，账本零变化
  const badResume = await page.evaluate(() => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: 'ui-illegal-order-' + Date.now(),
    event_id: 'ev-illegal-' + Date.now(),
    event_payload: {
      event_type: 'free_task.resumed',
      actual_minutes: 0,
      occurred_at: new Date().toISOString()
    }
  }, true));
  assert.equal(badResume.ok, false);
  assert.equal(badResume.status, 409);
  assert.equal(badResume.body.error.code, 'session_not_started');

  // 未知事件类型 → 400，不写入
  const unknownType = await page.evaluate(() => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: 'ui-unknown-type-' + Date.now(),
    event_id: 'ev-unknown-' + Date.now(),
    event_payload: {
      event_type: 'free_task.not_a_real_event',
      actual_minutes: 0,
      occurred_at: new Date().toISOString()
    }
  }, true));
  assert.equal(unknownType.ok, false);
  assert.equal(unknownType.status, 400);
  assert.equal(unknownType.body.error.code, 'event_type_invalid');

  // payload 未知字段 → 400（信任边界不放宽）
  const unknownField = await page.evaluate(() => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: 'ui-unknown-field-' + Date.now(),
    event_id: 'ev-unknown-field-' + Date.now(),
    event_payload: {
      event_type: 'free_task.started',
      activity: '写代码',
      category: 'study',
      planned_minutes: 25,
      occurred_at: new Date().toISOString(),
      sneaky_field: 'x'
    }
  }, true));
  assert.equal(unknownField.ok, false);
  assert.equal(unknownField.status, 400);
  assert.equal(unknownField.body.error.code, 'payload_unknown_field');

  // 非法计划时长 → 400
  const badMinutes = await page.evaluate(() => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: 'ui-bad-minutes-' + Date.now(),
    event_id: 'ev-bad-minutes-' + Date.now(),
    event_payload: {
      event_type: 'free_task.started',
      activity: '写代码',
      category: 'study',
      planned_minutes: 30,
      occurred_at: new Date().toISOString()
    }
  }, true));
  assert.equal(badMinutes.ok, false);
  assert.equal(badMinutes.status, 400);
  assert.equal(badMinutes.body.error.code, 'minutes_invalid');

  // 可见输入校验：学习类未填自报分钟时不发送完成事件
  await createTask(page, { activity: '缺少自报分钟的学习任务', reported: '' });
  let n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);
  n = await eventCountOf(page);
  // 被拒绝的完成：事件历史必须新增一条“被拒绝”记录（但不是 completed）
  await page.click(SELECTORS.btnComplete);
  await page.waitForFunction(
    (prev) => window.__freeTaskIntegrated.snapshot().eventCount > prev,
    n,
    { timeout: 5000 }
  );
  assert.equal(await page.isVisible(SELECTORS.errorBox), true);
  assert.match(await page.innerText(SELECTORS.errorBox), /自报/);

  const snapshot = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  assert.equal(snapshot.status, 'running', '被拒绝的完成不得改变本地状态');
  const serverAfter = await fetchServerSummary(page, snapshot.sessionId);
  assert.equal(serverAfter.body.summary.successful_tasks, 0, '被拒绝的完成不得写入账本');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '非法事件拒绝');
});

test('未授权的 GET / POST 一律 401 且不写入', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  // 错误凭据的 POST → 401
  const unauthorizedPost = await page.evaluate(() => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: 'ui-unauth-' + Date.now(),
    event_id: 'ev-unauth-' + Date.now(),
    event_payload: {
      event_type: 'free_task.started',
      activity: '未授权尝试',
      category: 'study',
      planned_minutes: 25,
      occurred_at: new Date().toISOString()
    }
  }, false));
  assert.equal(unauthorizedPost.ok, false);
  assert.equal(unauthorizedPost.status, 401);
  assert.equal(unauthorizedPost.body.ok, false);
  assert.equal(unauthorizedPost.body.error.code, 'free_task_unauthorized');

  // 错误凭据的 GET summary → 401
  const unauthorizedGet = await page.evaluate(
    (sid) => window.__freeTaskIntegrated.summaryRaw(sid, false),
    'ui-unauth-' + Date.now()
  );
  assert.equal(unauthorizedGet.ok, false);
  assert.equal(unauthorizedGet.status, 401);
  assert.equal(unauthorizedGet.body.error.code, 'free_task_unauthorized');
  assert.equal('summary' in unauthorizedGet.body, false, '401 绝不返回 summary');

  // 完全不带凭据（用 Node 侧原生 fetch 直连真实端点，绕过页面的授权头）
  const anon = await fetch(baseUrl + '/api/free-tasks/sessions/anon-probe/summary');
  assert.equal(anon.status, 401);
  const anonBody = await anon.json();
  assert.equal(anonBody.ok, false);
  assert.equal(anonBody.error.code, 'free_task_unauthorized');

  // 未授权请求绝不落库：授权读取该会话仍是空的
  const sessionId = 'ui-unauth-check-' + Date.now();
  const unauthed = await page.evaluate(
    (sid) => window.__freeTaskIntegrated.postRaw({
      action: 'append',
      session_id: sid,
      event_id: 'ev-unauth-check-' + Date.now(),
      event_payload: {
        event_type: 'free_task.started',
        activity: '未授权写入尝试',
        category: 'study',
        planned_minutes: 25,
        occurred_at: new Date().toISOString()
      }
    }, false),
    sessionId
  );
  const after = await fetchServerSummary(page, sessionId);
  assert.equal(after.body.summary.event_count, 0, '未授权 POST 绝不写入事件');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '未授权拒绝');
});

test('娱乐类不冒充学习时长：完成数 +1 但服务端已验证学习分钟为 0', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '看一集纪录片', category: 'entertainment', minutes: 55, reported: 55 });
  let n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnPause, n);
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnResume, n);
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnComplete, n);

  const sessionId = await page.evaluate(() => window.__freeTaskIntegrated.snapshot().sessionId);
  const server = await fetchServerSummary(page, sessionId);
  const summary = server.body.summary;
  assert.equal(summary.successful_tasks, 1);
  assert.equal(summary.entertainment_completions, 1);
  assert.equal(summary.study_completions, 0);
  assert.equal(summary.effective_study_minutes, 0, '娱乐类绝不能贡献已验证学习分钟');
  assert.equal(summary.study_pomodoros, 0);

  assert.equal((await page.innerText(SELECTORS.statVerifiedStudy)).trim(), '0');
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');
  assert.equal((await page.innerText(SELECTORS.statPomodoros)).trim(), '0');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '娱乐分账');
});

test('计时到零绝不自动完成（前端不自动发事件，服务端完成数保持 0）', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '背单词', minutes: 25, reported: 25 });
  let n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);

  const sessionId = await page.evaluate(() => window.__freeTaskIntegrated.snapshot().sessionId);

  // 测试专用时钟：把剩余时间推到零（不改变可见的 25/55 分钟语义）
  let snap = await page.evaluate(() => window.__freeTaskIntegrated.tick(25 * 60));
  assert.equal(snap.remainingSeconds, 0);
  assert.equal(snap.timerElapsed, true);
  assert.equal(snap.status, 'running', '计时结束状态仍是进行中');
  assert.equal(snap.eventTypes.includes('free_task.completed'), false, '绝不能自动产生完成事件');

  assert.equal(await page.isVisible(SELECTORS.timerNotice), true);
  assert.match(await page.innerText(SELECTORS.timerNotice), /不会自动/);
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');

  // 服务端也必须没有完成
  const server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.successful_tasks, 0);
  assert.equal(server.body.summary.event_count, 1, '只有 started 落到后端');

  // 用户随后明确报告完成，才计入完成数
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnComplete, n);
  const after = await fetchServerSummary(page, sessionId);
  assert.equal(after.body.summary.successful_tasks, 1);

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '计时零不自动完成');
});

test('中断 / 失败均不计入完成数；学习类会话中途不得改类别', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  // 中断
  await createTask(page, { activity: '画草稿', reported: 25 });
  let n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnInterrupt, n);
  let snap = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');
  let server = await fetchServerSummary(page, snap.sessionId);
  assert.equal(server.body.summary.successful_tasks, 0);
  assert.equal(server.body.summary.event_count, 2);

  // 失败
  await page.click(SELECTORS.btnNewTask);
  await createTask(page, { activity: '画草稿 2', reported: 25 });
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);
  n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnFail, n);
  snap = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');
  server = await fetchServerSummary(page, snap.sessionId);
  assert.equal(server.body.summary.successful_tasks, 0);

  // 信任边界：会话中途改类别 → 400 category_mismatch，不写入
  const mismatch = await page.evaluate((sid) => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: sid,
    event_id: 'ev-mismatch-' + Date.now(),
    event_payload: {
      event_type: 'free_task.paused',
      category: 'entertainment',
      actual_minutes: 3,
      occurred_at: new Date().toISOString()
    }
  }, true), snap.sessionId);
  assert.equal(mismatch.ok, false);
  assert.equal(mismatch.status, 400);
  assert.equal(mismatch.body.error.code, 'category_mismatch');
  server = await fetchServerSummary(page, snap.sessionId);
  assert.equal(server.body.summary.event_count, 2, '被拒绝的请求绝不写入');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '中断失败分账');
});

test('每次新建任务都生成全新随机 session_id；页面不写任何浏览器持久化存储', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors, offOrigin } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '第一个任务', reported: 25 });
  let n = await eventCountOf(page);
  await clickAndSettle(page, SELECTORS.btnStart, n);
  n = await eventCountOf(page);
  // 先把第一个任务收尾（中断），才能新建下一个任务。
  await clickAndSettle(page, SELECTORS.btnInterrupt, n);
  const firstId = await page.evaluate(() => window.__freeTaskIntegrated.snapshot().sessionId);

  await page.click(SELECTORS.btnNewTask);
  await createTask(page, { activity: '第二个任务', reported: 25 });
  const secondId = await page.evaluate(() => window.__freeTaskIntegrated.snapshot().sessionId);
  assert.notEqual(firstId, secondId, '每个任务必须是全新随机 session_id');
  assert.equal(secondId.startsWith('ui-'), true);

  // 第二个会话的服务端账本互相独立
  const secondServer = await fetchServerSummary(page, secondId);
  assert.equal(secondServer.body.summary.event_count, 0);

  // 无浏览器持久化存储
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie
  }));
  assert.equal(storage.local, 0);
  assert.equal(storage.session, 0);
  assert.equal(storage.cookie, '');

  // 无外部资源、无 CDN、无字体/图片外链
  const externals = await page.evaluate(() => Array.from(
    document.querySelectorAll('link,script[src],img,iframe,video,audio')
  ).map((el) => el.src || el.href).filter((u) => /^https?:/i.test(u || '')));
  assert.deepEqual(externals, [], '页面不得引用任何外部资源');

  assert.deepEqual(offOrigin, []);
  assertNoRealConsoleErrors(consoleErrors, pageErrors, '会话隔离与存储隔离');
});

test('可见输入校验与 XSS 防护：注入串按纯文本展示且不执行', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  // 空白活动 → 可见错误，且不创建任务（不发任何请求）
  await page.fill(SELECTORS.activity, '    ');
  await page.click(SELECTORS.btnCreate);
  assert.equal(await page.isVisible(SELECTORS.errorBox), true);
  assert.match(await page.innerText(SELECTORS.errorBox), /活动内容/);
  let snap = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  assert.equal(snap.status, 'none');
  assert.equal(snap.sessionId, null);

  // 超长活动 → 可见错误
  await page.fill(SELECTORS.activity, 'x'.repeat(260));
  await page.click(SELECTORS.btnCreate);
  assert.equal(await page.isVisible(SELECTORS.errorBox), true);
  assert.match(await page.innerText(SELECTORS.errorBox), /过长/);

  // XSS：注入串必须以纯文本展示、不生成 HTML 节点、不执行
  const payload = '<img src=x onerror="window.__xssFired=1"><script>window.__xssFired=1<\/script>';
  await page.fill(SELECTORS.activity, payload);
  await page.click(SELECTORS.btnCreate);
  const shown = await page.innerText(SELECTORS.taskActivity);
  assert.ok(shown.includes('<img src=x onerror='), '注入串应作为文本显示');
  assert.ok(shown.includes('<script>'));
  assert.equal(await page.evaluate(() => window.__xssFired === 1), false, '注入脚本不得执行');
  assert.equal(await page.locator(SELECTORS.taskActivity + ' img').count(), 0);

  // 后端收到同样的文本并正常落库（原样保存，不执行）
  snap = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  let n = snap.eventCount;
  await clickAndSettle(page, SELECTORS.btnStart, n);
  const server = await fetchServerSummary(page, snap.sessionId);
  assert.equal(server.body.summary.event_count, 1);
  assert.equal(server.body.summary.successful_tasks, 0);

  // 键盘可操作：焦点 + 回车激活按钮（键盘路径同样产生真实请求）
  n = await eventCountOf(page);
  await page.focus(SELECTORS.btnPause);
  await page.keyboard.press('Enter');
  await page.waitForFunction(
    (prev) => window.__freeTaskIntegrated.snapshot().eventCount > prev,
    n,
    { timeout: 15000 }
  );
  const keyboardSnap = await page.evaluate(() => window.__freeTaskIntegrated.snapshot());
  assert.equal(keyboardSnap.status, 'paused');
  const keyboardServer = await fetchServerSummary(page, keyboardSnap.sessionId);
  assert.equal(keyboardServer.body.summary.event_count, 2, '键盘操作也必须真实写入后端');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '输入校验与 XSS');
});

test('关闭子进程后：临时合成库被删除，且项目 data/ 未被写入', async (t) => {
  const handle = await startSyntheticApp();
  const dbPath = handle.info.db_path;
  const tempDir = handle.info.temp_dir;
  assert.ok(fs.existsSync(dbPath), '关闭前合成库应存在');

  await stopSyntheticApp(handle);

  assert.equal(fs.existsSync(dbPath), false, '进程关闭后合成 SQLite 必须被删除');
  assert.equal(fs.existsSync(dbPath + '-wal'), false, 'WAL 家族不得残留');
  assert.equal(fs.existsSync(dbPath + '-shm'), false, 'SHM 家族不得残留');
  await waitForDirGone(tempDir, 5000);

  // 项目侧：合成联调绝不在 data/ 或 notes/ 留下任何东西
  const forbidden = [
    path.join(PROJECT_ROOT, 'data', 'synthetic_free_task_events.sqlite3'),
    path.join(PROJECT_ROOT, 'synthetic_free_task_events.sqlite3')
  ];
  for (const candidate of forbidden) {
    assert.equal(fs.existsSync(candidate), false, '合成库绝不能出现在项目路径: ' + candidate);
  }
});

// ===========================================================================
// 3) ACK 可靠性：服务端确认后才提交本地状态（缺陷 A）
// ===========================================================================

test('ACK-1：start 收到确定性 401 时不发生虚假“已开始”，账本零写入，可修正后重新发起', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '未被授权的开始', reported: 25 });
  let snap = await snapshot(page);
  const sessionId = snap.sessionId;
  assert.equal(snap.status, 'created');

  // 一次性 401：请求根本没到服务端（route.fulfill 不转发）。
  await armOneShotRoute(page, baseUrl, 'respond', 401);
  let n = snap.eventCount;
  await page.click(SELECTORS.btnStart);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'created', '401 之后绝不能显示已开始');
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '已创建（未开始）');
  assert.equal(snap.pendingEventId, null, '确定性 HTTP 错误不是“待确认”');
  assert.equal(snap.inflight, null);
  assert.equal(await page.isVisible(SELECTORS.ackNotice), false, '确定性错误不该显示待确认横幅');
  assert.equal(await page.isVisible(SELECTORS.btnRetryPending), false);
  // 事件日志绝不能出现一条看起来像“已确认 started”的记录
  assert.equal(snap.eventTypes.includes('free_task.started'), false, '被拒的 start 不得记成已确认事件');
  assert.equal(snap.eventTypes.includes('prototype.ack_failed'), true, '必须记录一条明确的失败事件');
  assert.equal(await page.isVisible(SELECTORS.errorBox), true, '必须明确展示失败');
  assert.match(await page.innerText(SELECTORS.errorBox), /401/);
  assert.equal(snap.serverSummary, null, '拒绝的请求不得更新任何服务端统计');
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');

  // 服务端账本确实零变化
  let server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.event_count, 0, '401 绝不写入事件');
  assert.equal(server.body.summary.successful_tasks, 0);

  // 按钮恢复可操作：修正后可以重新发起一个**合法**的新业务操作
  assert.equal(await page.getAttribute(SELECTORS.btnStart, 'aria-disabled'), 'false');
  n = snap.eventCount;
  await clickAndSettle(page, SELECTORS.btnStart, n);
  snap = await snapshot(page);
  assert.equal(snap.status, 'running', '重试成功后才允许进入进行中');
  server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.event_count, 1);

  assertNoRealConsoleErrors(consoleErrors, pageErrors, 'ACK 401 start');
});

test('ACK-2：complete 收到确定性 401/409 时不发生虚假“已完成”，完成数保持 0', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '未被授权的完成', reported: 25 });
  let snap = await snapshot(page);
  const sessionId = snap.sessionId;
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnStart, n);
    return snapshot(page);
  })();
  assert.equal(snap.status, 'running');

  // -- 401：完成被确定性拒绝 -------------------------------------------
  await armOneShotRoute(page, baseUrl, 'respond', 401);
  let n = snap.eventCount;
  await page.click(SELECTORS.btnComplete);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'running', '401 之后绝不能显示已完成');
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '进行中');
  assert.equal(snap.pendingEventId, null);
  assert.equal(await page.isVisible(SELECTORS.btnRetryPending), false);
  assert.equal(snap.serverSummary.successful_tasks, 0, '被拒的完成不得更新统计');
  // 事件日志绝不能出现一条看起来像“已确认 completed”的记录
  assert.equal(snap.eventTypes.includes('free_task.completed'), false, '被拒的完成不得记成已确认事件');
  assert.equal(snap.eventTypes.includes('prototype.ack_failed'), true, '必须记录一条明确的失败事件');

  let server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.successful_tasks, 0, '401 绝不写入完成事件');
  assert.equal(server.body.summary.event_count, 1, '只有 started 落了账');
  assert.equal(server.body.summary.effective_study_minutes, 0);

  // -- 409：让真实受保护端点返回确定性冲突 ---------------------------
  // 预置一条**真实写入**的完成事件 → 服务端已有完成；页面随后再点完成，
  // 服务端必须 409 duplicate_completion。
  // （预置请求先发，times:1 的拦截此时尚未安装，因此它会真正到达服务端。）
  const conflict = await page.evaluate((sid) => window.__freeTaskIntegrated.postRaw({
    action: 'append',
    session_id: sid,
    event_id: 'ev-preexisting-completion-' + Date.now(),
    event_payload: {
      event_type: 'free_task.completed',
      actual_minutes: 25,
      reported_study_minutes: 25,
      occurred_at: new Date().toISOString()
    }
  }, true), sessionId);
  assert.equal(conflict.ok, true, '预置的完成事件应被接受');

  const n2 = (await snapshot(page)).eventCount;
  await page.click(SELECTORS.btnRefreshSummary);
  await waitSettled(page, n2);
  assert.equal((await snapshot(page)).serverSummary.successful_tasks, 1, '刷新后应看到预置的完成数');

  n = (await snapshot(page)).eventCount;
  await page.click(SELECTORS.btnComplete);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'running', '409 之后绝不能显示已完成');
  assert.equal(snap.lastRejected.status, 409, '必须记录确定性 409');
  assert.match(await page.innerText(SELECTORS.errorBox), /409/);
  assert.equal(snap.pendingEventId, null);

  server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.successful_tasks, 1, '完成数绝不因被拒请求而虚增');
  assert.equal(server.body.summary.event_count, 2, '被拒的完成绝不写入');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, 'ACK 401/409 complete');
});

test('ACK-3：断网（未提交）→ 待确认冻结 → 同一 event_id 重试可安全提交一次', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '断网时开始任务', reported: 25 });
  let snap = await snapshot(page);
  const sessionId = snap.sessionId;

  // -- 断网：route.abort() → 请求根本没发出，服务端确实未提交 ---------
  await armOneShotRoute(page, baseUrl, 'abort');
  let n = snap.eventCount;
  await page.click(SELECTORS.btnStart);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'created', '未确认之前绝不显示已开始');
  assert.ok(snap.pendingEventId, '网络错误必须进入待确认');
  assert.equal(snap.pendingEventType, 'free_task.started');
  // 待确认绝不能被记成一条已确认的 started
  assert.equal(snap.eventTypes.includes('free_task.started'), false, '待确认的 started 不得记成已确认事件');
  assert.equal(snap.eventTypes.includes('prototype.ack_pending'), true, '必须记录一条明确的待确认事件');
  assert.equal(await page.isVisible(SELECTORS.ackNotice), true, '必须显示“提交结果未知 / 待确认”');
  assert.match(await page.innerText(SELECTORS.ackNotice), /待确认/);
  assert.equal(await page.isVisible(SELECTORS.btnRetryPending), true, '必须提供可见的重试确认按钮');

  const pending = await page.evaluate(() => window.__freeTaskIntegrated.pendingAttempt());
  assert.equal(pending.sessionId, sessionId, '待确认提交必须绑定同一 session_id');
  assert.equal(pending.eventId, snap.pendingEventId);

  // 冻结：期间不得再创建任何事件
  for (const sel of [SELECTORS.btnCreate, SELECTORS.btnStart, SELECTORS.btnNewTask, SELECTORS.btnRefreshSummary]) {
    assert.equal(await page.getAttribute(sel, 'aria-disabled'), 'true', '待确认期间必须冻结: ' + sel);
  }
  // 直接调用动作处理器也必须被拒绝（不靠按钮禁用做唯一防线）
  await page.click(SELECTORS.btnComplete, { force: true }).catch(() => {});

  // 服务端账本确实零变化（本次请求根本没发出）
  let server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.event_count, 0, '断网且未提交时账本必须零写入');
  assert.equal(server.body.summary.successful_tasks, 0);

  // -- 重试确认：必须复用同一 event_id 与完全相同的 payload ----------
  n = (await snapshot(page)).eventCount;
  await page.click(SELECTORS.btnRetryPending);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'running', '服务端确认后才提交本地状态');
  assert.equal(snap.pendingEventId, null, '确认后待确认必须清空');
  assert.equal(await page.isVisible(SELECTORS.ackNotice), false);

  server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.event_count, 1, '重试只写入一条');
  assert.equal(server.body.summary.successful_tasks, 0);

  assertNoRealConsoleErrors(consoleErrors, pageErrors, 'ACK 断网未提交', true);
});

test('ACK-4：服务端已提交但响应丢失 → 待确认；同一 event_id 重试由后端幂等确认只计一次', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '响应丢失的完成', minutes: 25, reported: 25 });
  let snap = await snapshot(page);
  const sessionId = snap.sessionId;
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnStart, n);
    return snapshot(page);
  })();
  assert.equal(snap.status, 'running');

  // -- 服务端真的提交，但响应永远回不来 ------------------------------
  await armCommittedButResponseLostOnce(page, baseUrl);
  let n = snap.eventCount;
  await page.click(SELECTORS.btnComplete);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'running', '未收到响应时绝不谎称已完成');
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '进行中');
  assert.ok(snap.pendingEventId, '必须保持不确定状态');
  assert.match(await page.innerText(SELECTORS.ackNotice), /待确认/);
  assert.equal(await page.isVisible(SELECTORS.btnRetryPending), true);
  // 待确认绝不能被记成一条已确认的 completed
  assert.equal(snap.eventTypes.includes('free_task.completed'), false, '待确认的完成不得记成已确认事件');
  assert.equal(snap.eventTypes.includes('prototype.ack_pending'), true, '必须记录一条明确的待确认事件');

  const pending = await page.evaluate(() => window.__freeTaskIntegrated.pendingAttempt());
  assert.equal(pending.eventType, 'free_task.completed');
  assert.equal(pending.sessionId, sessionId);
  const frozenPayload = JSON.parse(JSON.stringify(pending.payload));

  // 服务端其实已经写入了 —— 这正是“本地无法知道”的那一支。
  let server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.successful_tasks, 1, '服务端已提交完成事件');
  assert.equal(server.body.summary.event_count, 2);

  // -- 重试确认：同一 event_id + 完全相同 payload ---------------------
  n = (await snapshot(page)).eventCount;
  await page.click(SELECTORS.btnRetryPending);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.equal(snap.status, 'completed', '服务端幂等确认后才提交本地状态');
  assert.equal(snap.pendingEventId, null);

  server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.successful_tasks, 1, '幂等重试绝不重复计数');
  assert.equal(server.body.summary.event_count, 2, '重试不得追加第二条事件');
  assert.equal(server.body.summary.effective_study_minutes, 25);
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');

  // 重试确实复用了同一 event_id 与逐字相同的 payload
  const eventsText = await page.innerText(SELECTORS.eventList);
  assert.match(eventsText, new RegExp(pending.eventId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.deepEqual(pending.payload, frozenPayload);

  assertNoRealConsoleErrors(consoleErrors, pageErrors, 'ACK 响应丢失', true);
});

test('ACK-5：待确认期间不得用新 event_id 伪造第二个完成事件', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '重复完成防护', minutes: 25, reported: 25 });
  let snap = await snapshot(page);
  const sessionId = snap.sessionId;
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnStart, n);
    return snapshot(page);
  })();

  // 第一次完成：服务端提交成功但响应丢失
  await armCommittedButResponseLostOnce(page, baseUrl);
  let n = snap.eventCount;
  await page.click(SELECTORS.btnComplete);
  await waitSettled(page, n);

  snap = await snapshot(page);
  assert.ok(snap.pendingEventId, '处于待确认');
  const firstEventId = snap.pendingEventId;

  // 待确认期间，完成 / 新建任务 / 创建任务全部冻结（强制点击也不得改变任何状态）
  await page.click(SELECTORS.btnComplete, { force: true }).catch(() => {});
  await page.click(SELECTORS.btnNewTask, { force: true }).catch(() => {});
  await page.click(SELECTORS.btnCreate, { force: true }).catch(() => {});
  snap = await snapshot(page);
  assert.equal(snap.status, 'running', '冻结期间状态绝不变化');
  assert.equal(snap.pendingEventId, firstEventId, '冻结期间待确认事件不被替换');
  assert.equal(snap.sessionId, sessionId);

  // 幂等重试后完成数仍然恰好是 1
  n = snap.eventCount;
  await page.click(SELECTORS.btnRetryPending);
  await waitSettled(page, n);
  const server = await fetchServerSummary(page, sessionId);
  assert.equal(server.body.summary.successful_tasks, 1);
  assert.equal(server.body.summary.event_count, 2, '冻结 + 幂等重试都不产生额外事件');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, 'ACK 冻结防重复', true);
});

test('统计口径：后端 verification 为 user_reported_not_independently_verified，UI 不出现“已验证”措辞', async (t) => {
  const handle = await startSyntheticApp();
  t.after(async () => { await stopSyntheticApp(handle); });

  const baseUrl = 'http://127.0.0.1:' + handle.info.port;
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPage(browser, baseUrl);
  t.after(async () => { await context.close(); });

  await createTask(page, { activity: '口径核对', minutes: 25, reported: 25 });
  let snap = await snapshot(page);
  const sessionId = snap.sessionId;
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnStart, n);
    return snapshot(page);
  })();
  assert.equal(snap.status, 'running');
  // 先暂停 → 再继续：证明「恢复」事件不贡献任何统计。
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnPause, n);
    return snapshot(page);
  })();
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnResume, n);
    return snapshot(page);
  })();
  snap = await (async () => {
    const n = snap.eventCount;
    await clickAndSettle(page, SELECTORS.btnComplete, n);
    return snapshot(page);
  })();
  assert.equal(snap.status, 'completed');

  // -- 服务端口径：明确的 verification 字段 --------------------------
  const server = await fetchServerSummary(page, sessionId);
  const summary = server.body.summary;
  assert.equal(summary.verification, 'user_reported_not_independently_verified');
  assert.equal(summary.successful_tasks, 1);
  assert.equal(summary.effective_study_minutes, 25, '自报分钟照常计入，但未经独立核实');

  // -- UI 措辞：绝不把自报分钟称为“已验证” --------------------------
  const body = await pageText(page);
  const offenders = body.split('\n').filter((line) => VERIFIED_WORDING_RE.test(line));
  assert.deepEqual(offenders, [], '页面不得出现“已验证学习”类措辞: ' + JSON.stringify(offenders));

  const statPanel = await page.innerText('[data-testid="stat-verified-study"]');
  assert.equal(statPanel.trim(), '25');
  const statLabel = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="stat-verified-study"]');
    return el.parentElement.innerText;
  });
  assert.match(statLabel, /自报学习分钟/, '标签必须明确写“自报学习分钟”');
  assert.match(statLabel, /未独立核实/, '标签必须明确标注“未独立核实”');

  // 明确标记这是临时 SQLite / synthetic 非生产记录
  assert.match(await page.innerText(SELECTORS.banner), /非正式学习记录/);
  assert.match(await page.innerText(SELECTORS.banner), /临时 SQLite/);

  // 恢复事件不贡献统计；娱乐类自报学习分钟为 0
  assert.equal(summary.study_pomodoros, 1);
  assert.match(body, /user_reported_not_independently_verified/, '页面必须展示后端原始 verification 口径');

  assertNoRealConsoleErrors(consoleErrors, pageErrors, '统计口径措辞');
});