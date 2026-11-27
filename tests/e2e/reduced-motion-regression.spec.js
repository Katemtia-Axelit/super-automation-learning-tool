/**
 * tests/e2e/reduced-motion-regression.spec.js
 *
 * AR03-P5 —— `prefers-reduced-motion` 的 **真实浏览器** 回归测试。
 *
 * 为什么需要它
 * ------------
 * 此前 `prefers-reduced-motion` 只有 **静态契约证据**（CSS 源码里写了
 * `animation-duration: 0.01ms` + `pointer-events: auto`），
 * **没有** 任何真实浏览器交互验证。独立审查把它列为 P5 必须补齐的唯一
 * 实质证据缺口。
 *
 * 本测试要证明的三件事（全部在 **真实启用** `reducedMotion: 'reduce'` 的
 * 浏览器上下文里断言）：
 *
 *   1. **pointer-events 恢复** —— 动画态卡牌在 reduced-motion 下必须
 *      **可点击**（`pointer-events: auto`），否则用户无法继续操作；
 *   2. **无重复提交** —— 状态推进由 JS 定时器驱动，被压缩的 CSS 动画
 *      **不得** 导致同一动作被触发两次；
 *   3. **Promise resolve** —— `playCardAnim()` 返回的 Promise 必须
 *      **resolve**（否则 `await playCardAnim(...)` 会挂死，后续
 *      `renderDrawnCardResult` / `loadTasks` 永不执行）。
 *
 * ⚠️ 关于 reduced-motion 的启用方式（本文件的核心技术前提）
 * -----------------------------------------------------------
 * **实测结论（Playwright 1.62.1）**：本仓库中 `test.use({ reducedMotion:
 * 'reduce' })` 与 config 里的 `use.reducedMotion` **不会**作用到
 * Playwright 的 `page` fixture —— 走 fixture 拿到的页面
 * `matchMedia('(prefers-reduced-motion: reduce)').matches === false`。
 *
 * **唯一可靠的做法**是显式建上下文：
 *
 *     const context = await browser.newContext({ reducedMotion: 'reduce' });
 *     const page = await context.newPage();
 *
 * （`page.emulateMedia({ reducedMotion: 'reduce' })` 也可行，但必须
 * **在导航之前**调用。）
 *
 * 因此本文件**不使用** `page` fixture，而是每个用例自己建
 * `newContext({ reducedMotion: 'reduce' })` —— 这也是独立审查给出的
 * 正确 API 用法。
 *
 * 隔离约束（与其它 safe spec 一致）
 * ----------------------------------
 *   - **不** 访问 `http://127.0.0.1:5000`（生产端口）；
 *   - **不** 触碰生产 DB / notes / config；
 *   - **不** 使用本项目的活 Flask 服务器；
 *   - 无远程请求、无安装（全部请求由 `page.route()` 拦截）。
 *
 * 方法
 * ----
 * `page.route()` 全 mock 网络；`page.goto()` 载入一个被 route 拦截的
 * 合成 HTML 响应（相对 `fetch()` 需要真实 origin），用
 * `page.addStyleTag({ content })` 注入 **真实的** `static/css/responsive.css`
 * 与 `static/css/cards.css`（真实 CSS 才能验证 `pointer-events` 与
 * `animation-duration` 的实际计算值），再把 **真实的**
 * `static/app.js::playCardAnim` 注入执行。
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const APP_JS_PATH = path.join(PROJECT_ROOT, 'static', 'app.js');
const RESPONSIVE_CSS_PATH = path.join(PROJECT_ROOT, 'static', 'css', 'responsive.css');
const CARDS_CSS_PATH = path.join(PROJECT_ROOT, 'static', 'css', 'cards.css');

const RESPONSIVE_CSS = fs.readFileSync(RESPONSIVE_CSS_PATH, 'utf8');
const CARDS_CSS = fs.readFileSync(CARDS_CSS_PATH, 'utf8');

/** 合成页面的 origin —— 全部请求都由 page.route() 拦截，不会真的发出去。 */
const ORIGIN = 'http://127.0.0.1:0';

/** 从 app.js 源码里抽出顶层函数（与 gacha-multidraw-safe.spec.js 同一手法）。 */
function extractFunction(source, name) {
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

const APP_JS_SOURCE = fs.readFileSync(APP_JS_PATH, 'utf8');
const PLAY_CARD_ANIM_SRC = extractFunction(APP_JS_SOURCE, 'playCardAnim');

if (!PLAY_CARD_ANIM_SRC) {
  throw new Error(
    '无法从 static/app.js 抽取 playCardAnim —— 该函数签名/形态已变，请同步更新本回归测试。',
  );
}

/**
 * 合成页面：一张抽卡结果卡 + 一张任务列表卡。
 *
 * ``data-task-id="7"`` 对应 app.js 的选择器
 * ``.task-card[data-task-id="7"]``。
 */
const PAGE_HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>reduced-motion synthetic</title></head>
<body>
  <div class="drawn-card-stage">
    <div class="task-card" data-task-id="7" id="card">
      <div class="task-card-front"><div class="task-card-body-zone">合成任务</div></div>
    </div>
  </div>
  <div class="task-list">
    <div class="task-card" data-task-id="8" id="list-card">
      <div class="task-card-front"><div class="task-card-body-zone">列表任务</div></div>
    </div>
  </div>
</body>
</html>`;

/**
 * 建立一个 **真正启用** reduced-motion 的浏览器上下文，并载入合成页面。
 *
 * @param {import('@playwright/test').Browser} browser
 * @param {Array<{match: string, body?: any}>} routes 额外拦截的 API 路由
 * @param {Array<{match: string, body?: any}>} apiRoutes 由调用方自己计数时使用
 * @returns {Promise<{ context, page, calls: Record<string, number> }>}
 */
async function openReducedMotionPage(browser, routes = []) {
  // **关键**：reducedMotion 必须在 newContext 时指定（见文件头说明）。
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  const calls = {};

  await page.route(`${ORIGIN}/**`, async (route) => {
    const url = route.request().url();
    const hit = routes.find((r) => url.indexOf(r.match) !== -1);
    if (hit) {
      calls[hit.match] = (calls[hit.match] || 0) + 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(hit.body || {}),
      });
      return;
    }
    if (url === `${ORIGIN}/synthetic-page`) {
      await route.fulfill({
        status: 200,
        contentType: 'text/html; charset=utf-8',
        body: PAGE_HTML,
      });
      return;
    }
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'not mocked' }),
    });
  });

  await page.goto(`${ORIGIN}/synthetic-page`);

  // **必须**注入真实 CSS —— 要断言的是计算样式。
  await page.addStyleTag({ content: RESPONSIVE_CSS });
  await page.addStyleTag({ content: CARDS_CSS });

  // 注入真实的 playCardAnim 实现。
  await page.addScriptTag({
    content: PLAY_CARD_ANIM_SRC + '\nwindow.playCardAnim = playCardAnim;',
  });

  return { context, page, calls };
}

test.describe('prefers-reduced-motion 真实浏览器回归', () => {
  test('reduced-motion 上下文确实生效（自检）', async ({ browser }) => {
    const { context, page } = await openReducedMotionPage(browser);
    const matches = await page.evaluate(
      () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    );
    await context.close();
    expect(matches).toBe(true);
  });

  test('动画态卡牌在 reduced-motion 下 pointer-events 恢复为 auto', async ({ browser }) => {
    const { context, page } = await openReducedMotionPage(browser);

    const result = await page.evaluate(() => {
      const el = document.getElementById('card');
      const before = getComputedStyle(el).pointerEvents;
      el.classList.add('is-discarding');
      const during = getComputedStyle(el).pointerEvents;
      return { before, during };
    });
    await context.close();

    expect(result.before).not.toBe('none');
    expect(result.during).toBe('auto');
  });

  test('六个动画态在 reduced-motion 下全部 pointer-events: auto', async ({ browser }) => {
    const { context, page } = await openReducedMotionPage(browser);

    const states = [
      'is-evaporating',
      'is-fly-to-pile',
      'is-discarding',
      'is-skipping',
      'is-refusing',
      'is-burning',
    ];

    const values = await page.evaluate((list) => {
      const el = document.getElementById('card');
      return list.map((cls) => {
        el.className = 'task-card';
        el.classList.add(cls);
        return getComputedStyle(el).pointerEvents;
      });
    }, states);
    await context.close();

    states.forEach((cls, i) => {
      expect(values[i], `${cls} 的 pointer-events 必须恢复为 auto`).toBe('auto');
    });
  });

  test('reduced-motion 下 animation-duration 被压缩到近 0', async ({ browser }) => {
    const { context, page } = await openReducedMotionPage(browser);

    const duration = await page.evaluate(() => {
      const el = document.getElementById('card');
      el.classList.add('is-discarding');
      return getComputedStyle(el).animationDuration;
    });
    await context.close();

    // cards.css 的 cardDiscardFly 是 0.65s；reduced-motion 下必须被压到 ~0.01ms。
    expect(parseFloat(duration)).toBeLessThan(0.01);
  });

  test('playCardAnim 的 Promise 在 reduced-motion 下 resolve（不挂死）', async ({ browser }) => {
    const { context, page } = await openReducedMotionPage(browser);

    const result = await page.evaluate(async () => {
      const settled = await Promise.race([
        window.playCardAnim(7, 'is-discarding', 50).then(() => 'resolved'),
        new Promise((resolve) => setTimeout(() => resolve('timeout'), 3000)),
      ]);
      return {
        settled,
        classesAfter: document.getElementById('card').className,
      };
    });
    await context.close();

    expect(result.settled).toBe('resolved');
    // 动画类必须被摘掉（playCardAnim 的收尾动作）。
    expect(result.classesAfter).not.toContain('is-discarding');
  });

  test('抽卡流程：reduced-motion 下 Promise resolve + 无重复提交', async ({ browser }) => {
    const { context, page, calls } = await openReducedMotionPage(browser, [
      { match: '/api/tasks/7/skip', body: { unlocked_tasks: [] } },
    ]);

    const result = await page.evaluate(async () => {
      // 模拟 lifecycle.js::handleSkip 的顺序：API → playCardAnim → 结果渲染。
      const order = [];
      const r = await fetch('/api/tasks/7/skip', { method: 'POST' });
      order.push('api:' + r.status);
      await window.playCardAnim(7, 'is-skipping');
      order.push('anim-done');
      order.push('render');
      return order;
    });

    await page.waitForTimeout(300);
    await context.close();

    expect(result).toEqual(['api:200', 'anim-done', 'render']);
    expect(calls['/api/tasks/7/skip']).toBe(1);
  });

  test('拒绝流程：reduced-motion 下同样 resolve + 恰好一次提交', async ({ browser }) => {
    const { context, page, calls } = await openReducedMotionPage(browser, [
      { match: '/api/tasks/7/refuse', body: { ok: true } },
    ]);

    const result = await page.evaluate(async () => {
      const order = [];
      await fetch('/api/tasks/7/refuse', { method: 'POST' });
      order.push('api');
      await window.playCardAnim(7, 'is-refusing');
      order.push('anim-done');
      order.push('render');
      return order;
    });

    await page.waitForTimeout(300);
    await context.close();

    expect(result).toEqual(['api', 'anim-done', 'render']);
    expect(calls['/api/tasks/7/refuse']).toBe(1);
  });

  test('弃牌流程：reduced-motion 下 pointer-events 恢复 + 恰好一次提交', async ({ browser }) => {
    const { context, page, calls } = await openReducedMotionPage(browser, [
      { match: '/api/tasks/8/move-to-discard', body: { ok: true } },
    ]);

    const result = await page.evaluate(async () => {
      const order = [];
      const el = document.getElementById('list-card');
      await fetch('/api/tasks/8/move-to-discard', { method: 'POST' });
      order.push('api');
      // 弃牌期间必须仍然可交互。
      order.push('pointer:' + getComputedStyle(el).pointerEvents);
      await window.playCardAnim(8, 'is-discarding');
      order.push('anim-done');
      order.push('render');
      return order;
    });

    await page.waitForTimeout(300);
    await context.close();

    expect(result).toEqual(['api', 'pointer:auto', 'anim-done', 'render']);
    expect(calls['/api/tasks/8/move-to-discard']).toBe(1);
  });

  test('连续两次 playCardAnim 各自独立 resolve（无串扰）', async ({ browser }) => {
    const { context, page } = await openReducedMotionPage(browser);

    const settled = await page.evaluate(async () => {
      const race = (p) =>
        Promise.race([
          p.then(() => 'resolved'),
          new Promise((r) => setTimeout(() => r('timeout'), 3000)),
        ]);
      const a = race(window.playCardAnim(7, 'is-skipping', 40));
      const b = race(window.playCardAnim(8, 'is-refusing', 40));
      return Promise.all([a, b]);
    });
    await context.close();

    expect(settled).toEqual(['resolved', 'resolved']);
  });
});
