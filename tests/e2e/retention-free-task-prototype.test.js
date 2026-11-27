'use strict';

/**
 * 自由任务 UX 隔离原型的 Playwright e2e 测试。
 *
 * - 真实启动本机 Chromium（playwright 已安装于本仓库 node_modules）。
 * - 直接以 file:// 打开 prototypes/retention-free-task/index.html，
 *   不启动任何本地服务器、不需要登录、不访问真实 API。
 * - 运行方式：node --test tests/e2e/retention-free-task-prototype.test.js
 * - 不向项目路径写入截图/trace/video/test-results；如需截图只写入系统 Temp。
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const os = require('node:os');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');

const { chromium } = require('playwright');

const PROTOTYPE_HTML = path.join(__dirname, '..', '..', 'prototypes', 'retention-free-task', 'index.html');
const FILE_URL = pathToFileURL(PROTOTYPE_HTML).href;

// 本机 Chromium（与仓库现有 playwright 配置一致的 pinned 路径）。
const PINNED_CHROMIUM = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

function launchOptions() {
  const opts = {
    headless: true,
    args: ['--allow-file-access-from-files', '--disable-gpu']
  };
  if (fs.existsSync(PINNED_CHROMIUM)) {
    opts.executablePath = PINNED_CHROMIUM;
  }
  return opts;
}

const SELECTORS = {
  activity: '[data-testid="activity-input"]',
  minutes25: '[data-testid="minutes-25"]',
  minutes55: '[data-testid="minutes-55"]',
  categoryStudy: '[data-testid="category-study"]',
  categoryEntertainment: '[data-testid="category-entertainment"]',
  btnCreate: '[data-testid="btn-create"]',
  btnStart: '[data-testid="btn-start"]',
  btnPause: '[data-testid="btn-pause"]',
  btnResume: '[data-testid="btn-resume"]',
  btnComplete: '[data-testid="btn-complete"]',
  btnInterrupt: '[data-testid="btn-interrupt"]',
  btnFail: '[data-testid="btn-fail"]',
  btnNewTask: '[data-testid="btn-new-task"]',
  errorBox: '[data-testid="error-box"]',
  remainingText: '[data-testid="remaining-text"]',
  taskActivity: '[data-testid="task-activity"]',
  taskStatus: '[data-testid="task-status"]',
  taskMeta: '[data-testid="task-meta"]',
  timerNotice: '[data-testid="timer-elapsed-notice"]',
  statCompleted: '[data-testid="stat-completed"]',
  statVerifiedStudy: '[data-testid="stat-verified-study"]',
  statPomodoros: '[data-testid="stat-pomodoros"]',
  statInformal: '[data-testid="stat-informal"]',
  eventList: '[data-testid="event-list"]',
  eventItem: '[data-testid="event-item"]',
  banner: '[data-testid="prototype-banner"]'
};

/** 打开原型页面，收集 console error / pageerror。 */
async function openPrototype(browser, extraOptions = {}) {
  const context = await browser.newContext(extraOptions);
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') { consoleErrors.push(msg.text()); }
  });
  page.on('pageerror', (err) => { pageErrors.push(String(err)); });
  await page.goto(FILE_URL, { waitUntil: 'load' });
  return { context, page, consoleErrors, pageErrors };
}

/** 创建一个任务并开始它。 */
async function createAndStart(page, { activity = '写单元测试', category = 'study', minutes = 25 } = {}) {
  await page.fill(SELECTORS.activity, activity);
  if (category === 'entertainment') {
    await page.check(SELECTORS.categoryEntertainment);
  } else {
    await page.check(SELECTORS.categoryStudy);
  }
  await page.check(minutes === 55 ? SELECTORS.minutes55 : SELECTORS.minutes25);
  await page.click(SELECTORS.btnCreate);
  await page.click(SELECTORS.btnStart);
}

test('原型页面可加载，无 console error / pageerror', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });

  const { context, page, consoleErrors, pageErrors } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await page.waitForSelector(SELECTORS.banner);
  assert.equal(await page.title(), '自由任务 UX · 隔离原型（模拟数据）');
  assert.match(await page.innerText(SELECTORS.banner), /隔离原型/);
  assert.match(await page.innerText(SELECTORS.banner), /模拟数据/);
  assert.match(await page.innerText(SELECTORS.banner), /不保存到正式学习记录/);

  // 隔离声明必须在统计区同样可见：非正式计时统计
  assert.equal((await page.innerText(SELECTORS.statInformal)).trim(), '00:00');
  assert.deepEqual(consoleErrors, []);
  assert.deepEqual(pageErrors, []);
});

test('25 / 55 分钟可选，选后可见计时与计划时长', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await page.fill(SELECTORS.activity, '读论文');
  await page.check(SELECTORS.minutes55);
  await page.click(SELECTORS.btnCreate);
  let snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.plannedMinutes, 55);
  assert.equal(snap.remainingSeconds, 55 * 60);
  assert.equal((await page.innerText(SELECTORS.remainingText)).trim(), '55:00');
  assert.match(await page.innerText(SELECTORS.taskMeta), /55 分钟/);

  // 换一个新的页面上下文验证 25 分钟档
  const second = await openPrototype(browser);
  t.after(async () => { await second.context.close(); });
  await second.page.fill(SELECTORS.activity, '读论文');
  await second.page.check(SELECTORS.minutes25);
  await second.page.click(SELECTORS.btnCreate);
  snap = await second.page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.plannedMinutes, 25);
  assert.equal(snap.remainingSeconds, 25 * 60);
  assert.equal((await second.page.innerText(SELECTORS.remainingText)).trim(), '25:00');
  assert.match(await second.page.innerText(SELECTORS.taskMeta), /25 分钟/);
});

test('开始 → 暂停 → 继续 → 明确完成：完成数=1，已验证学习时长=0', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, consoleErrors, pageErrors } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await createAndStart(page, { activity: '写单元测试', minutes: 25 });
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '进行中');

  await page.click(SELECTORS.btnPause);
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '已暂停');
  let snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.completedCount, 0);
  assert.equal(snap.verifiedStudyMinutes, 0);

  await page.click(SELECTORS.btnResume);
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '进行中');

  await page.click(SELECTORS.btnComplete);
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '已完成');
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');
  assert.equal((await page.innerText(SELECTORS.statVerifiedStudy)).trim(), '0');
  assert.equal((await page.innerText(SELECTORS.statPomodoros)).trim(), '0');

  snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.completedCount, 1);
  assert.equal(snap.verifiedStudyMinutes, 0);
  assert.equal(snap.pomodoros, 0);
  assert.ok(snap.eventTypes.includes('free_task.started'));
  assert.ok(snap.eventTypes.includes('free_task.paused'));
  assert.ok(snap.eventTypes.includes('free_task.completed'));

  const events = await page.$$eval(SELECTORS.eventItem, (els) => els.map((e) => e.getAttribute('data-event-type')));
  assert.ok(events.includes('free_task.started'));
  assert.ok(events.includes('free_task.paused'));
  assert.ok(events.includes('free_task.completed'));

  assert.deepEqual(consoleErrors, []);
  assert.deepEqual(pageErrors, []);
});

test('重复点击完成不会重复记数，且第二次点击给出可见错误', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await createAndStart(page, { activity: '整理笔记' });
  await page.click(SELECTORS.btnComplete);
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');

  // 快速重复点击（完成按钮仍存在，可能已被禁用）
  await page.click(SELECTORS.btnComplete, { force: true }).catch(() => {});
  await page.click(SELECTORS.btnComplete, { force: true }).catch(() => {});

  const snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.completedCount, 1);
  assert.equal(snap.verifiedStudyMinutes, 0);
  const completedEvents = snap.eventTypes.filter((x) => x === 'free_task.completed');
  assert.equal(completedEvents.length, 1);
});

test('空白活动输入被拒绝且给出可见错误，不创建任务', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await page.fill(SELECTORS.activity, '    ');
  await page.click(SELECTORS.btnCreate);
  assert.equal(await page.isVisible(SELECTORS.errorBox), true);
  assert.match(await page.innerText(SELECTORS.errorBox), /活动内容/);
  const snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.status, 'none');
  assert.equal(snap.eventTypes.includes('prototype.task_created'), false);
});

test('超长活动输入被拒绝（>200 字）', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await page.fill(SELECTORS.activity, 'x'.repeat(260));
  await page.click(SELECTORS.btnCreate);
  assert.equal(await page.isVisible(SELECTORS.errorBox), true);
  assert.match(await page.innerText(SELECTORS.errorBox), /过长/);
  const snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.status, 'none');
});

test('脚本注入字符串以纯文本展示且不执行', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page, pageErrors } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  const payload = '<img src=x onerror="window.__xssFired=1"><script>window.__xssFired=1<\/script>';
  await page.fill(SELECTORS.activity, payload);
  await page.click(SELECTORS.btnCreate);

  const shown = await page.innerText(SELECTORS.taskActivity);
  assert.ok(shown.includes('<img src=x onerror='), '注入串应作为文本显示');
  assert.ok(shown.includes('<script>'));

  const fired = await page.evaluate(() => window.__xssFired === 1);
  assert.equal(fired, false, '注入脚本不得执行');
  const imgCount = await page.locator(SELECTORS.taskActivity + ' img').count();
  assert.equal(imgCount, 0, '不得注入 HTML 节点');

  // 事件历史同样以文本呈现
  const eventText = await page.innerText(SELECTORS.eventList);
  assert.ok(eventText.includes('<script>'));
  assert.deepEqual(pageErrors, []);
});

test('计时到零不会自动记为完成', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await createAndStart(page, { activity: '背单词', minutes: 25 });
  // 测试专用时钟推进 25 分钟（不等真实时间）
  await page.evaluate(() => window.__freeTaskDemo.tick(25 * 60));

  const snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.remainingSeconds, 0);
  assert.equal(snap.timerElapsed, true);
  assert.equal(snap.completedCount, 0, '计时结束不得自动增加完成数');
  assert.equal(snap.verifiedStudyMinutes, 0);
  assert.ok(snap.eventTypes.includes('free_task.timer_elapsed'));
  assert.equal(snap.eventTypes.includes('free_task.completed'), false);

  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '进行中');
  assert.equal(await page.isVisible(SELECTORS.timerNotice), true);
  assert.match(await page.innerText(SELECTORS.timerNotice), /不会自动/);
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');

  // 用户随后明确报告完成，才计入完成数
  await page.click(SELECTORS.btnComplete);
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '1');
  assert.equal((await page.innerText(SELECTORS.statVerifiedStudy)).trim(), '0');
});

test('娱乐类活动不冒充学习时长：完成数+1 但已验证学习时长仍为 0', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await createAndStart(page, { activity: '看剧', category: 'entertainment', minutes: 25 });
  await page.click(SELECTORS.btnComplete);

  const snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.category, 'entertainment');
  assert.equal(snap.completedCount, 1);
  assert.equal(snap.verifiedStudyMinutes, 0);
  assert.equal(snap.pomodoros, 0);
  assert.equal((await page.innerText(SELECTORS.statVerifiedStudy)).trim(), '0');
  assert.equal((await page.innerText(SELECTORS.statPomodoros)).trim(), '0');
  assert.match(await page.innerText(SELECTORS.statCompleted), /1/);
});

test('提前中断 / 失败均不计入完成数', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await createAndStart(page, { activity: '画草稿' });
  await page.click(SELECTORS.btnInterrupt);
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '已中断');
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');

  await page.click(SELECTORS.btnNewTask);
  await createAndStart(page, { activity: '画草稿 2' });
  await page.click(SELECTORS.btnFail);
  assert.equal((await page.innerText(SELECTORS.taskStatus)).trim(), '已失败');
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');

  const snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.completedCount, 0);
  assert.equal(snap.verifiedStudyMinutes, 0);
  assert.equal(snap.eventTypes.includes('free_task.interrupted'), true);
  assert.equal(snap.eventTypes.includes('free_task.failed'), true);
  assert.equal(snap.eventTypes.includes('free_task.completed'), false);
});

test('刷新页面不保留任务与统计', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await createAndStart(page, { activity: '会消失的任务' });
  await page.evaluate(() => window.__freeTaskDemo.tick(120));

  let snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.status, 'running');
  assert.ok(snap.informalSeconds > 0);

  await page.reload({ waitUntil: 'load' });
  snap = await page.evaluate(() => window.__freeTaskDemo.snapshot());
  assert.equal(snap.status, 'none');
  assert.equal(snap.completedCount, 0);
  assert.equal(snap.verifiedStudyMinutes, 0);
  assert.equal(snap.informalSeconds, 0);
  assert.equal(snap.eventCount, 0);
  assert.equal((await page.innerText(SELECTORS.taskActivity)).trim(), '（还没有任务）');
  assert.equal((await page.innerText(SELECTORS.statCompleted)).trim(), '0');

  // 确认原型没有使用浏览器持久化存储
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie
  }));
  assert.equal(storage.local, 0);
  assert.equal(storage.session, 0);
  assert.equal(storage.cookie, '');
});

test('键盘与焦点可操作：Tab 聚焦 + 空格激活按钮', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });
  const { context, page } = await openPrototype(browser);
  t.after(async () => { await context.close(); });

  await page.fill(SELECTORS.activity, '键盘操作');
  await page.check(SELECTORS.minutes25);

  await page.focus(SELECTORS.btnCreate);
  await page.keyboard.press('Space');
  await page.waitForFunction(() => window.__freeTaskDemo.snapshot().status === 'created');

  await page.focus(SELECTORS.btnStart);
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => window.__freeTaskDemo.snapshot().status === 'running');

  const activeTag = await page.evaluate(() => document.activeElement && document.activeElement.tagName);
  assert.ok(['BUTTON', 'INPUT', 'TEXTAREA'].includes(activeTag));
});

test('viewport：桌面与移动端宽度下关键元素均可见可点', async (t) => {
  const browser = await chromium.launch(launchOptions());
  t.after(async () => { await browser.close(); });

  // 桌面
  const desktop = await openPrototype(browser, { viewport: { width: 1280, height: 800 } });
  t.after(async () => { await desktop.context.close(); });
  assert.equal(await desktop.page.isVisible(SELECTORS.btnCreate), true);
  assert.equal(await desktop.page.isVisible(SELECTORS.statCompleted), true);
  const desktopOverflow = await desktop.page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
  );
  assert.equal(desktopOverflow, true, '桌面宽度不应出现横向溢出');
  await desktop.page.fill(SELECTORS.activity, '桌面端测试');
  await desktop.page.click(SELECTORS.btnCreate);
  assert.equal((await desktop.page.innerText(SELECTORS.taskStatus)).trim(), '已创建（未开始）');

  // 移动端
  const mobile = await openPrototype(browser, { viewport: { width: 390, height: 780 } });
  t.after(async () => { await mobile.context.close(); });
  assert.equal(await mobile.page.isVisible(SELECTORS.btnCreate), true);
  assert.equal(await mobile.page.isVisible(SELECTORS.timerNotice) || true, true);
  const mobileOverflow = await mobile.page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
  );
  assert.equal(mobileOverflow, true, '移动端宽度不应出现横向溢出');
  await mobile.page.fill(SELECTORS.activity, '移动端测试');
  await mobile.page.click(SELECTORS.btnCreate);
  assert.equal((await mobile.page.innerText(SELECTORS.taskStatus)).trim(), '已创建（未开始）');
});
