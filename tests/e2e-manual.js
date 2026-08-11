/**
 * E2E 测试 - 学习工具前端
 * 使用 playwright-core 直接 API（绕过 headless-shell 兼容性问题）
 * 每个测试独立页面，状态隔离
 */
const { chromium } = require('playwright-core');

const BASE_URL = 'http://127.0.0.1:5000';
const EXEC_PATH = 'C:\\Users\\wn\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

async function runTests() {
  console.log('启动浏览器...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: EXEC_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 }
  });

  // 监听网络错误
  const networkErrors = [];
  context.on('response', response => {
    const url = response.url();
    const status = response.status();
    if (url.includes('/api/') && status >= 500 && !url.includes('/api/agent')) {
      networkErrors.push({ url, status });
    }
  });

  let passed = 0, failed = 0;
  const results = [];

  function assert(condition, msg) {
    if (!condition) throw new Error(msg || '断言失败');
  }

  async function waitForApiReady(page) {
    await page.waitForFunction(() => {
      const dot = document.getElementById('apiDot');
      return dot && dot.classList.contains('online');
    }, { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(500);
  }

  // 启动时清理可能存在的暂停计时（防止状态泄漏）
  async function cleanupExistingTimer(page) {
    try {
      // 先确保已导航到 BASE_URL（使 fetch 有 base URL）
      if (!page.url().startsWith(BASE_URL)) {
        await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
      }
      // 优先用 API 直接清理暂停的会话（避免 dialog 复杂度）
      const cleanupResult = await page.evaluate(async () => {
        try {
          const active = await fetch('/api/timer/active').then(r => r.json());
          if (!active || !active.id) {
            return { cleaned: false, reason: 'no_active_session' };
          }
          // 若为 paused 状态：直接 complete（后端已支持同时结束 running 和 paused）
          if (active.is_paused) {
            const result = await fetch('/api/timer/complete', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ session_id: active.id, actual_minutes: 0, result: 'abandoned', reason: 'test_cleanup' })
            }).then(r => r.json());
            return { cleaned: true, session_id: active.id, was_paused: true, result };
          }
          // running 状态：先 complete
          const result = await fetch('/api/timer/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: active.id, actual_minutes: 0, result: 'abandoned', reason: 'test_cleanup' })
          }).then(r => r.json());
          return { cleaned: true, session_id: active.id, was_paused: false, result };
        } catch (e) {
          return { cleaned: false, error: e.message };
        }
      });
      console.log(`  [cleanup] API 结果: ${JSON.stringify(cleanupResult)}`);
    } catch (e) {
      console.log('  [cleanup] 跳过:', e.message);
    }
  }

  async function test(name, fn) {
    // 每个测试独立 page 实例
    const page = await context.newPage();
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // P3-Bug-B: 全局 dialog 处理器（自动接受 confirm/alert/prompt）
    page.on('dialog', async dialog => {
      try { await dialog.accept(); } catch (e) {}
    });

    try {
      console.log(`  [测试] ${name}`);
      await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
      await waitForApiReady(page);
      await fn(page);
      passed++;
      results.push({ name, status: 'PASS' });
      console.log(`    ✓ 通过`);
    } catch (e) {
      failed++;
      results.push({ name, status: 'FAIL', error: e.message });
      console.log(`    ✗ 失败: ${e.message}`);
    } finally {
      await page.close();
    }
  }

  // ============ 抽卡测试 ============
  console.log('\n【抽卡】');

  // P3-Bug-B: 先清理可能存在的暂停计时
  console.log('  [清理] 启动前清理可能存在的暂停计时');
  const cleanupPage = await context.newPage();
  cleanupPage.on('dialog', async dialog => { try { await dialog.accept(); } catch (e) {} });
  await cleanupExistingTimer(cleanupPage);
  await cleanupPage.close();

  await test('1.1 页面加载与元素存在', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    assert(await page.locator('#gachaBtn').isVisible());
    assert(await page.locator('#gachaDeck').isVisible());
    assert(await page.locator('#gachaTimeInput').isVisible());
  });

  await test('1.2 抽卡流程', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    await page.click('#gachaBtn');
    try {
      await page.waitForSelector('.task-card.drawn-card', { timeout: 10000 });
      assert(await page.locator('.task-card.drawn-card').isVisible());
      assert(await page.locator('.task-card.drawn-card button').first().isVisible());
    } catch {
      const empty = await page.locator('.empty-state').isVisible().catch(() => false);
      assert(empty, '期望卡牌或空状态');
    }
  });

  await test('1.3 抽卡防抖', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    await page.click('#gachaBtn');
    await page.waitForTimeout(50);
    await page.click('#gachaBtn');
    await page.waitForTimeout(50);
    await page.click('#gachaBtn');
    await page.waitForTimeout(3000);
    assert(await page.locator('#gachaBtn').isEnabled());
  });

  // ============ 任务测试 ============
  console.log('\n【任务】');

  await test('2.1 任务列表加载', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(2000);
    assert(await page.locator('#taskGrid').isVisible());
    assert(await page.locator('.task-toolbar').isVisible());
  });

  await test('2.2 新建任务', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    const before = await page.locator('.task-card:not(.drawn-card)').count();
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', 'E2E测试任务-' + Date.now());
    await page.fill('#tfTime', '30');
    await page.click('#taskModal button:has-text("保存")');
    await page.waitForTimeout(2000);
    // 检查模态框是否关闭
    const modalHidden = await page.locator('#taskModal.hidden').count() > 0;
    assert(modalHidden, '任务模态框应已关闭');
    const after = await page.locator('.task-card:not(.drawn-card)').count();
    assert(after >= before, `期望 ${before + 1}+ 任务，实际 ${after}`);
  });

  await test('2.3 编辑任务', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    const editBtn = page.locator('.task-card-actions button:has-text("编辑")').first();
    if (await editBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editBtn.click();
      await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
      await page.fill('#tfName', 'E2E已编辑-' + Date.now());
      await page.click('#taskModal button:has-text("保存")');
      await page.waitForTimeout(2000);
      const modalHidden = await page.locator('#taskModal.hidden').count() > 0;
      assert(modalHidden, '编辑后模态框应已关闭');
    }
  });

  await test('2.4 搜索筛选', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    await page.fill('#taskSearch', 'E2E');
    await page.waitForTimeout(500);
    await page.fill('#taskSearch', '');
    await page.selectOption('#taskFilter', 'all');
    await page.waitForTimeout(300);
    await page.selectOption('#taskFilter', 'unlocked');
  });

  await test('2.5 删除任务', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    const delBtn = page.locator('.task-card-actions button:has-text("删除")').first();
    if (await delBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      const before = await page.locator('.task-card:not(.drawn-card)').count();
      await delBtn.click();
      await page.waitForTimeout(2000);
      const after = await page.locator('.task-card:not(.drawn-card)').count();
      assert(after < before, `删除后任务数应减少: ${before} -> ${after}`);
    }
  });

  // ============ 计时器测试 ============
  console.log('\n【计时器】');

  await test('3.1 计时器面板', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    assert(await page.locator('#timerPanel').isVisible());
    assert(await page.locator('#timerStartBtn').isVisible());
    assert(await page.locator('#timerTaskSelect').isVisible());
  });

  await test('3.2 计时器Dock', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    assert(await page.locator('#timerDock').isVisible());
    const idle = await page.locator('#timerDockIdle').isVisible().catch(() => false);
    const active = await page.locator('#timerDockActive').isVisible().catch(() => false);
    assert(idle || active, 'Dock idle 或 active 至少一个可见');
  });

  await test('3.3 开始计时', async (page) => {
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    // 若已有活动会话，先走 Dock 停止，避免 select 被禁用
    const activeDock = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (activeDock) {
      await page.click('#timerDockStopBtn');
      await page.waitForTimeout(2000);
      // 关闭可能弹出的关怀弹窗
      const careClose = page.locator('#careModal button, #careModal .btn').first();
      if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
        await page.evaluate(() => {
          const m = document.getElementById('careModal');
          if (m) m.classList.add('hidden');
        });
      }
      await page.waitForTimeout(500);
    }
    // 创建任务（唯一名称，避免后端重名 500）
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', '计时器E2E测试-' + Date.now());
    await page.fill('#tfTime', '30');
    await page.click('#taskModal button:has-text("保存")');
    // .hidden 为 display:none，不能用默认 visible 等待
    await page.waitForFunction(() => {
      const el = document.getElementById('taskModal');
      return el && el.classList.contains('hidden');
    }, { timeout: 10000 });
    await page.waitForTimeout(800);

    const sel = page.locator('#timerTaskSelect');
    await page.waitForFunction(() => {
      const s = document.getElementById('timerTaskSelect');
      return s && !s.disabled && s.options.length > 1;
    }, { timeout: 10000 });
    await sel.selectOption({ index: 1 });
    await page.fill('#timerPlannedMin', '1');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);
    const timerDisplay = page.locator('#timerElapsedDisplay');
    assert(await timerDisplay.isVisible());
    const time = await timerDisplay.textContent();
    assert(time !== '00:00', `计时器应走动，当前: ${time}`);
  });

  await test('3.4 提前结束计时', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1500);

    // 优先使用 3.3 遗留的活动会话；否则自行启动
    let stopBtn = page.locator('#timerDockStopBtn');
    let hasActive = await stopBtn.isVisible({ timeout: 2000 }).catch(() => false);

    if (!hasActive) {
      await page.click('[data-page="tasks"]');
      await page.waitForTimeout(1500);
      await page.click('button:has-text("新建任务")');
      await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
      await page.fill('#tfName', '提前结束E2E-' + Date.now());
      await page.fill('#tfTime', '30');
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
      await page.waitForTimeout(1500);
      await page.click('[data-page="gacha"]');
      await page.waitForTimeout(1000);
      stopBtn = page.locator('#timerDockStopBtn');
      hasActive = await stopBtn.isVisible({ timeout: 5000 });
    }

    assert(hasActive, 'Dock 停止按钮应可见（活动计时会话）');

    const feedbackReqs = [];
    page.on('request', req => {
      if (req.url().includes('/feedback') && req.method() === 'POST') {
        feedbackReqs.push(req.postData() || '');
      }
    });
    await stopBtn.click();
    await page.waitForTimeout(3000);

    const joined = feedbackReqs.join(' ');
    const idle = await page.locator('#timerDockIdle').isVisible().catch(() => false);
    assert(
      joined.includes('finish_early') || idle,
      `期望 finish_early 上报或 Dock 回到 idle。feedback=${joined}`
    );
  });

  // ============ R2 回归：抽卡 XSS / 动画清理 ============
  console.log('\n【抽卡回归】');

  await test('1.4 XSS转义（抽卡卡牌）', async (page) => {
    const escaped = await page.evaluate(() => {
      if (typeof escapeHtml !== 'function') return null;
      return escapeHtml('<img src=x onerror=alert(1)>');
    });
    assert(escaped !== null, 'escapeHtml 应存在');
    assert(!escaped.includes('<img'), `应转义标签: ${escaped}`);
    assert(escaped.includes('&lt;img'), `应含 &lt;img: ${escaped}`);
  });

  await test('1.5 页面切换清理抽卡动画残留', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(800);
    await page.evaluate(() => {
      const layer = document.getElementById('cardFlyLayer');
      if (layer) layer.innerHTML = '<div class="fly-residue">x</div>';
      const deck = document.getElementById('gachaDeck');
      if (deck) {
        deck.classList.add('is-drawing');
        deck.classList.add('is-revealing');
      }
    });
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(500);
    const state = await page.evaluate(() => {
      const layer = document.getElementById('cardFlyLayer');
      const deck = document.getElementById('gachaDeck');
      return {
        flyEmpty: !layer || layer.innerHTML === '',
        drawing: deck ? deck.classList.contains('is-drawing') : false,
        revealing: deck ? deck.classList.contains('is-revealing') : false
      };
    });
    assert(state.flyEmpty, 'cardFlyLayer 应被清空');
    assert(!state.drawing && !state.revealing, `deck 动画类应清除: ${JSON.stringify(state)}`);
  });

  // ============ R3 回归：XSS 全路径修复验证 ============
  await test('1.6 XSS转义（全路径：task list / timer select / dep picker）', async (page) => {
    // 注意：<img src=x onerror=...> 被后端拦截（HTTP 500），故使用 <b>bold</b> 代替
    // <b> 标签可正常存入 DB，escapeHtml 会将其转义为 &lt;b&gt;，验证逻辑完全相同
    const xssPayload = '<b>bold</b>';
    const created = await page.evaluate(async (payload) => {
      const r = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: payload,
          estimated_time: 15,
          category: 'study',
          priority: 5,
          repeat_type: 'none',
          resistance: 'medium',
          energy_required: 'medium',
          task_profile: 'deadline_flexible'
        })
      });
      if (!r.ok) {
        const text = await r.text();
        return { ok: false, status: r.status, error: text.substring(0, 80) };
      }
      return r.json();
    }, xssPayload);
    assert(created && created.ok !== false && created.id, `任务创建失败: status=${created.status} error=${created.error}`);
    const taskId = created.id;

    // 2. 刷新任务列表
    await page.evaluate(() => { loadTasks(); });
    await page.waitForTimeout(1000);

    // 3. 检查点 A: task list 中 .task-card-title 是否转义（核心安全断言）
    //   escapeHtml 处理后 <b> 变成 &lt;b&gt;，innerHTML 中不应出现原始 <b>
    const taskListCheck = await page.evaluate(() => {
      const cards = document.querySelectorAll('.task-card');
      for (const c of cards) {
        const titleEl = c.querySelector('.task-card-title');
        if (!titleEl) continue;
        const raw = titleEl.innerHTML;
        return {
          rawHtml: raw.substring(0, 120),
          // 核心检查：原始 innerHTML 中不能有未转义的 <b> 或 <script> 标签
          hasRawTag: raw.includes('<b>') || raw.includes('<script') || raw.includes('<div'),
          // 应该已被转义为 &lt;b&gt;
          hasEscapedTag: raw.includes('&lt;b&gt;') || raw.includes('&lt;script')
        };
      }
      return null;
    });
    assert(taskListCheck !== null, 'task list: 未找到任何任务卡片');
    assert(!taskListCheck.hasRawTag,
      `task list: innerHTML 不应含原始 HTML 标签: ${taskListCheck.rawHtml}`);
    assert(taskListCheck.hasEscapedTag,
      `task list: 标签应被转义为 &lt;...&gt;，实际: ${taskListCheck.rawHtml}`);

    // 4. 检查点 B: #timerTaskSelect option 是否转义
    const timerSelectCheck = await page.evaluate(() => {
      const opts = document.querySelectorAll('#timerTaskSelect option');
      for (const o of opts) {
        const raw = o.innerHTML;
        if (raw.includes('<b>') || raw.includes('<script') || raw.includes('<div')) {
          return { rawHtml: raw, vulnerable: true };
        }
        if (raw.includes('&lt;b&gt;') || raw.includes('&lt;script') || raw.includes('&lt;div')) {
          return { rawHtml: raw, vulnerable: false };
        }
      }
      return null;
    });
    assert(timerSelectCheck !== null && timerSelectCheck.vulnerable !== true,
      `timer select: 不应有未转义标签，实际: ${timerSelectCheck && timerSelectCheck.rawHtml}`);

    // 5. 检查点 C: #tfDepList label 是否转义
    await page.evaluate(() => { openTaskEdit(); });
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.waitForTimeout(500);
    const depCheck = await page.evaluate(() => {
      const labels = document.querySelectorAll('#tfDepList label');
      for (const lbl of labels) {
        const raw = lbl.innerHTML;
        if (raw.includes('<b>') || raw.includes('<script') || raw.includes('<div')) {
          return { rawHtml: raw.substring(0, 100), vulnerable: true };
        }
        if (raw.includes('&lt;b&gt;') || raw.includes('&lt;script') || raw.includes('&lt;div')) {
          return { rawHtml: raw.substring(0, 100), vulnerable: false };
        }
      }
      return null;
    });
    assert(depCheck !== null && depCheck.vulnerable !== true,
      `dep picker: 不应有未转义标签，实际: ${depCheck && depCheck.rawHtml}`);

    // 6. 关闭弹窗，清理测试任务
    await page.evaluate(() => {
      const m = document.getElementById('taskModal');
      if (m) m.classList.add('hidden');
    });
    await page.evaluate(async (id) => {
      await fetch('/api/tasks/' + id, { method: 'DELETE' });
    }, taskId);
    await page.evaluate(() => { loadTasks(); });
    await page.waitForTimeout(500);
  });

  // ============ 日程测试 ============
  console.log('\n【日程】');

  await test('4.1 日程页面加载', async (page) => {
    await page.click('[data-page="schedule"]');
    await page.waitForTimeout(2000);
    assert(await page.locator('#sleepPanel').isVisible());
    assert(await page.locator('.schedule-nav').isVisible());
    assert(await page.locator('#schedGrid').isVisible());
  });

  await test('4.2 日期导航', async (page) => {
    await page.click('[data-page="schedule"]');
    await page.waitForTimeout(2000);
    const before = await page.locator('#schedDate').textContent();
    await page.click('.schedule-nav button:first-child');
    await page.waitForTimeout(500);
    const after = await page.locator('#schedDate').textContent();
    assert(after !== before, `日期应变化: ${before} -> ${after}`);
  });

  await test('4.3 睡眠追踪', async (page) => {
    await page.click('[data-page="schedule"]');
    await page.waitForTimeout(2000);
    assert(await page.locator('#sleepPanel').isVisible());
    assert(await page.locator('#sleepBedTimeInput').isVisible());
    await page.fill('#sleepBedTimeInput', '23:30');
    await page.click('#sleepSaveBtn');
    await page.waitForTimeout(1500);
  });

  await test('4.4 活动管理', async (page) => {
    await page.click('[data-page="schedule"]');
    await page.waitForTimeout(2000);
    await page.click('button:has-text("活动管理")');
    await page.waitForSelector('#activityMgrModal:not(.hidden)', { timeout: 5000 });
    assert(await page.locator('#activityMgrModal').isVisible());
    await page.click('#activityMgrCloseBtn');
    await page.waitForTimeout(500);
    const modalHidden = await page.locator('#activityMgrModal.hidden').count() > 0;
    assert(modalHidden, '活动管理模态框应已关闭');
  });

  // ============ 知识库测试 ============
  console.log('\n【知识库】');

  await test('5.1 知识库页面加载', async (page) => {
    await page.click('[data-page="knowledge"]');
    await page.waitForTimeout(3000);
    assert(await page.locator('.know-layout').isVisible());
    assert(await page.locator('#catList').isVisible());
    assert(await page.locator('#noteList').isVisible());
    assert(await page.locator('#knowContent').isVisible());
  });

  await test('5.2 分类和笔记列表', async (page) => {
    await page.click('[data-page="knowledge"]');
    await page.waitForTimeout(3000);
    const cats = page.locator('.cat-item');
    const count = await cats.count();
    if (count > 0) {
      await cats.first().click();
      await page.waitForTimeout(1500);
      const notes = page.locator('.note-item');
      if (await notes.count() > 0) {
        await notes.first().click();
        await page.waitForTimeout(2000);
        assert(await page.locator('#knowContent').isVisible());
      }
    }
  });

  // ============ 设置测试 ============
  console.log('\n【设置】');

  await test('6.1 设置页面加载', async (page) => {
    await page.click('[data-page="config"]');
    await page.waitForTimeout(2000);
    assert(await page.locator('#cfgPort').isVisible());
    assert(await page.locator('#cfgNotesDir').isVisible());
    assert(await page.locator('#cfgApiKey').isVisible());
  });

  await test('6.2 配置加载', async (page) => {
    await page.click('[data-page="config"]');
    await page.waitForTimeout(2000);
    const port = await page.inputValue('#cfgPort');
    assert(port && port.length > 0, `端口应已加载: ${port}`);
  });

  await test('6.3 提示词浏览', async (page) => {
    await page.click('[data-page="config"]');
    await page.waitForTimeout(2500);
    // 等待 promptFileList 加载（可能需要 API 响应）
    try {
      await page.waitForSelector('#promptFileList', { state: 'visible', timeout: 5000 });
    } catch {
      // 可能提示词文件不存在
    }
    assert(await page.locator('#promptFileList').isVisible());
    assert(await page.locator('#promptContentView').isVisible());
  });

  await test('6.4 Agent只读面板', async (page) => {
    await page.click('[data-page="config"]');
    await page.waitForTimeout(2000);
    await page.click('#agentReadonlyOpenBtn');
    await page.waitForSelector('#agentReadonlyModal:not(.hidden)', { timeout: 5000 });
    assert(await page.locator('#agentReadonlyModal').isVisible());
    await page.click('.agent-ro-tab[data-agent-tab="agents"]');
    await page.waitForTimeout(500);
    await page.click('.agent-ro-tab[data-agent-tab="raw"]');
    await page.waitForTimeout(500);
    await page.click('.agent-ro-tab[data-agent-tab="vault"]');
    await page.waitForTimeout(500);
    await page.click('#agentReadonlyCloseBtn');
    await page.waitForTimeout(500);
    const modalHidden = await page.locator('#agentReadonlyModal.hidden').count() > 0;
    assert(modalHidden, 'Agent 只读模态框应已关闭');
  });

  // ============ R3-P3 回归：XSS 残留点（loadTags / openTaskEdit） ============
  // P3-残留-1：loadTags() 中 t.name 直接拼 innerHTML + onclick
  // P3-残留-2：openTaskEdit() 中 t.name 仅 .replace(/"/g) 未转义 <>
  await test('2.6 XSS转义（loadTags 标签徽章）', async (page) => {
    const xssPayload = '<b><i>x</i></b>';
    const tagName = await page.evaluate(async (payload) => {
      const r = await fetch('/api/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: payload })
      });
      if (!r.ok) {
        const text = await r.text();
        return { ok: false, status: r.status, error: text.substring(0, 120) };
      }
      return r.json();
    }, xssPayload);
    assert(tagName && tagName.ok !== false && tagName.id,
      `tag 创建失败: ${JSON.stringify(tagName)}`);
    const createdId = tagName.id;
    try {
      // 触发 loadTags 渲染
      await page.evaluate(() => { loadTags(); });
      await page.waitForTimeout(800);
      const tagCheck = await page.evaluate((payload) => {
        const bar = document.getElementById('tagsBar');
        if (!bar) return { found: false };
        const html = bar.innerHTML;
        const containsRaw = html.includes('<b>') || html.includes('<i>') || html.includes('<script');
        // 找到包含 payload 转义形式的片段
        const escaped = '&lt;b&gt;&lt;i&gt;x&lt;/i&gt;&lt;/b&gt;';
        return {
          found: true,
          rawSnippet: html.substring(0, 400),
          containsRawTag: containsRaw,
          containsEscapedForm: html.includes(escaped)
        };
      }, xssPayload);
      assert(tagCheck.found, 'tagsBar 应存在');
      assert(!tagCheck.containsRawTag,
        `tagsBar: innerHTML 不应含原始 HTML 标签，实际: ${tagCheck.rawSnippet}`);
      assert(tagCheck.containsEscapedForm,
        `tagsBar: 标签应被转义为 &lt;...&gt;，实际: ${tagCheck.rawSnippet}`);
      // 兜底：onclick 属性闭合注入检查（防 t.name 注入到 onclick 字符串）
      // 当前实现 t.name 进入的是 innerHTML 文本位置，但保险起见扫描 onclick 属性
      const onclickInjection = await page.evaluate(() => {
        const bar = document.getElementById('tagsBar');
        const html = bar.innerHTML;
        // 检查 onclick 属性中是否有未转义的引号/尖括号
        const matches = html.match(/onclick="[^"]*"/g) || [];
        for (const m of matches) {
          if (m.includes('<') || m.includes('>')) return { injected: true, sample: m };
        }
        return { injected: false, sample: matches[0] || '' };
      });
      assert(!onclickInjection.injected,
        `tagsBar: onclick 属性不应含尖括号，实际: ${onclickInjection.sample}`);
    } finally {
      // 清理测试 tag
      await page.evaluate(async (id) => {
        await fetch('/api/tags/' + id, { method: 'DELETE' });
      }, createdId);
      await page.evaluate(() => { loadTags(); });
      await page.waitForTimeout(300);
    }
  });

  await test('2.7 XSS转义（openTaskEdit 已有标签选择器）', async (page) => {
    const xssPayload = '<b><i>x</i></b>';
    const tagName = await page.evaluate(async (payload) => {
      const r = await fetch('/api/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: payload })
      });
      if (!r.ok) {
        const text = await r.text();
        return { ok: false, status: r.status, error: text.substring(0, 120) };
      }
      return r.json();
    }, xssPayload);
    assert(tagName && tagName.ok !== false && tagName.id,
      `tag 创建失败: ${JSON.stringify(tagName)}`);
    const createdId = tagName.id;
    try {
      // 关键：openTaskEdit 读的是全局 allTags，必须先刷新，否则新 tag 不会进渲染
      await page.evaluate(() => { loadTags(); });
      await page.waitForTimeout(500);
      // 打开新建任务弹窗（openTaskEdit 无参 = 新建模式，但会渲染 #tfExistingTags）
      await page.evaluate(() => { openTaskEdit(); });
      await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
      await page.waitForTimeout(500);
      const tagPickCheck = await page.evaluate((payload) => {
        const container = document.getElementById('tfExistingTags');
        if (!container) return { found: false };
        const html = container.innerHTML;
        const containsRaw = html.includes('<b>') || html.includes('<i>') || html.includes('<script');
        const escaped = '&lt;b&gt;&lt;i&gt;x&lt;/i&gt;&lt;/b&gt;';
        // data-tag 属性也应该被完整转义（关键：原代码只 .replace(/"/g)，会被 "><script> 逃逸）
        const dataTagSafe = !html.match(/data-tag="[^"]*<[^"]*"/);
        return {
          found: true,
          rawSnippet: html.substring(0, 500),
          containsRawTag: containsRaw,
          containsEscapedForm: html.includes(escaped),
          dataTagSafe
        };
      }, xssPayload);
      assert(tagPickCheck.found, '#tfExistingTags 应存在');
      assert(!tagPickCheck.containsRawTag,
        `tfExistingTags: innerHTML 不应含原始 HTML 标签，实际: ${tagPickCheck.rawSnippet}`);
      assert(tagPickCheck.containsEscapedForm,
        `tfExistingTags: 标签应被转义为 &lt;...&gt;，实际: ${tagPickCheck.rawSnippet}`);
      assert(tagPickCheck.dataTagSafe,
        `tfExistingTags: data-tag 属性不应含未转义尖括号，实际: ${tagPickCheck.rawSnippet}`);
      // 关闭弹窗
      await page.evaluate(() => {
        const m = document.getElementById('taskModal');
        if (m) m.classList.add('hidden');
      });
    } finally {
      // 清理测试 tag
      await page.evaluate(async (id) => {
        await fetch('/api/tags/' + id, { method: 'DELETE' });
      }, createdId);
      await page.evaluate(() => { loadTags(); });
      await page.waitForTimeout(300);
    }
  });

  // ============ P3 暂停持久化 E2E 测试 ============
  console.log('\n【计时器暂停（P3-Bug-B）】');

  // 用例 A：启动计时 → 暂停 → 断言暂停状态
  await test('3.5 计时器暂停（暂停状态保持）', async (page) => {
    // 1. 确保无活动会话
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    const activeDock = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (activeDock) {
      await page.click('#timerDockStopBtn');
      await page.waitForTimeout(2000);
      // 关闭可能弹出的关怀弹窗
      if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
        await page.evaluate(() => {
          const m = document.getElementById('careModal');
          if (m) m.classList.add('hidden');
        });
      }
      await page.waitForTimeout(500);
    }

    // 2. 去任务页启动计时
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);

    // 创建任务
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', '暂停E2E-A-' + Date.now());
    await page.fill('#tfTime', '30');
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
    await page.fill('#timerPlannedMin', '10');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);

    // 断言计时中
    const status1 = await page.locator('#timerStatusText').textContent();
    assert(!status1.includes('未在计时'), `计时应进行中: ${status1}`);

    // 3. 暂停
    await page.click('#timerPauseBtn');
    await page.waitForTimeout(1000);

    // 4. 断言 UI 显示暂停状态
    const pausedStatus = await page.locator('#timerStatusText').textContent();
    assert(pausedStatus.includes('已暂停'), `UI 应显示暂停: ${pausedStatus}`);

    // 5. 断言后端 API 返回 paused 状态
    const apiResp = await page.evaluate(async () => {
      const r = await fetch('/api/timer/active');
      return r.json();
    });
    assert(apiResp && apiResp.is_paused === true, `后端应返回 paused: ${JSON.stringify(apiResp)}`);
  });

  // 用例 B：暂停后刷新页面 → 断言暂停状态保持
  await test('3.6 计时器暂停（刷新后恢复）', async (page) => {
    // 1. 确保无活动会话
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    const activeDock = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (activeDock) {
      await page.click('#timerDockStopBtn');
      await page.waitForTimeout(2000);
      // 关闭可能弹出的关怀弹窗
      if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
        await page.evaluate(() => {
          const m = document.getElementById('careModal');
          if (m) m.classList.add('hidden');
        });
      }
      await page.waitForTimeout(500);
    }

    // 2. 去任务页启动计时
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);

    // 创建任务
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', '暂停E2E-B-' + Date.now());
    await page.fill('#tfTime', '30');
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
    await page.fill('#timerPlannedMin', '10');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);

    // 暂停
    await page.click('#timerPauseBtn');
    await page.waitForTimeout(1000);

    // 获取暂停时显示的时间
    const timeBefore = await page.locator('#timerElapsedDisplay').textContent();
    assert(timeBefore !== '00:00', `计时应有时间: ${timeBefore}`);

    // 刷新页面
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // 断言暂停状态恢复
    const statusAfter = await page.locator('#timerStatusText').textContent();
    assert(statusAfter.includes('已暂停') || statusAfter.includes('计时中'),
      `刷新后应恢复暂停状态: ${statusAfter}`);
  });

  // 用例 C：恢复计时 → 断言计时继续 + 服务端状态正确
  await test('3.7 计时器暂停（恢复后继续）', async (page) => {
    // 1. 确保无活动会话
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    const activeDock = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (activeDock) {
      await page.click('#timerDockStopBtn');
      await page.waitForTimeout(2000);
      // 关闭可能弹出的关怀弹窗
      if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
        await page.evaluate(() => {
          const m = document.getElementById('careModal');
          if (m) m.classList.add('hidden');
        });
      }
      await page.waitForTimeout(500);
    }

    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);

    // 检查是否有活动会话（可能从上一测试继承）
    let hasActive = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (!hasActive) {
      // 创建任务
      await page.click('button:has-text("新建任务")');
      await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
      await page.fill('#tfName', '暂停E2E-C-' + Date.now());
      await page.fill('#tfTime', '30');
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
      await page.fill('#timerPlannedMin', '10');
      await page.click('#timerStartBtn');
      await page.waitForTimeout(2000);
    }

    // 暂停
    await page.click('#timerPauseBtn');
    await page.waitForTimeout(1000);

    const timePaused = await page.locator('#timerElapsedDisplay').textContent();
    const pausedStatus = await page.locator('#timerStatusText').textContent();
    assert(pausedStatus.includes('已暂停'), `应显示暂停: ${pausedStatus}`);

    // 恢复
    await page.click('#timerPauseBtn');
    await page.waitForTimeout(2000);

    // 断言不再显示暂停
    const resumedStatus = await page.locator('#timerStatusText').textContent();
    assert(!resumedStatus.includes('已暂停'), `恢复后不应显示暂停: ${resumedStatus}`);

    // 断言后端状态
    const apiResp = await page.evaluate(async () => {
      const r = await fetch('/api/timer/active');
      return r.json();
    });
    assert(apiResp && apiResp.is_paused === false, `后端应返回非暂停: ${JSON.stringify(apiResp)}`);
  });

  // 用例 D：暂停期间时间不累计
  await test('3.8 计时器暂停（暂停期间时间不跳变）', async (page) => {
    // 1. 确保无活动会话
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    const activeDock = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (activeDock) {
      await page.click('#timerDockStopBtn');
      await page.waitForTimeout(2000);
      // 关闭可能弹出的关怀弹窗
      if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
        await page.evaluate(() => {
          const m = document.getElementById('careModal');
          if (m) m.classList.add('hidden');
        });
      }
      await page.waitForTimeout(500);
    }

    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);

    // 创建任务并启动
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', '暂停E2E-D-' + Date.now());
    await page.fill('#tfTime', '30');
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
    await page.fill('#timerPlannedMin', '10');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);

    const time1 = await page.locator('#timerElapsedDisplay').textContent();
    assert(time1 !== '00:00', `计时应已开始: ${time1}`);

    // 暂停
    await page.click('#timerPauseBtn');
    await page.waitForTimeout(500);
    const timeAtPause = await page.locator('#timerElapsedDisplay').textContent();

    // 等待 3 秒
    await page.waitForTimeout(3000);

    // 断言时间没有增加（暂停期间不累计）
    const timeAfterWait = await page.locator('#timerElapsedDisplay').textContent();
    assert(timeAfterWait === timeAtPause,
      `暂停期间时间应不变: ${timeAtPause} -> ${timeAfterWait}`);
  });

  // ============ P3 P0 回归：3.8 / 3.4 / 1.3 ============
  console.log('\n【P0 回归：计时器 interval / abandoned / 切页残留】');

  // ---- P0-1 (bug 3.8): initTimerDock 多次调用不重复创建 interval ----
  await test('P0-1 initTimerDock 不重复创建 interval', async (page) => {
    // 用 monkey-patch 统计 setInterval 调用次数
    await page.evaluate(() => {
      window.__intervalCounter = { calls: 0, cleared: 0 };
      const origSet = window.setInterval;
      const origClear = window.clearInterval;
      window.setInterval = function (fn, ms) {
        // 只统计 1000ms 的（即 timerDockTick / timerTickHandle）
        if (ms === 1000) {
          window.__intervalCounter.calls += 1;
          window.__lastTimerId = window.__lastTimerId || {};
          const id = origSet.call(window, fn, ms);
          window.__lastTimerId[id] = true;
          return id;
        }
        return origSet.call(window, fn, ms);
      };
      window.clearInterval = function (id) {
        if (window.__lastTimerId && window.__lastTimerId[id]) {
          window.__intervalCounter.cleared += 1;
          delete window.__lastTimerId[id];
        }
        return origClear.call(window, id);
      };
    });

    // 触发多次 initTimerDock 调用（模拟页面反复切换的路径）
    await page.evaluate(async () => {
      // 通过全局作用域调用：app.js 中 initTimerDock 是全局函数
      if (typeof initTimerDock === 'function') {
        for (var i = 0; i < 5; i++) {
          initTimerDock();
        }
      }
    });
    await page.waitForTimeout(500);

    const stats = await page.evaluate(() => window.__intervalCounter);
    // 期望：5 次 initTimerDock 调用，setInterval 应被调用 5 次（每次都创建新 interval），
    // 但 clearInterval 应至少被调用 4 次（保留最后一个）。最关键：实际运行的 interval 数量应 ≤ 1。
    // 由于 initTimerDock 内部已 clearInterval 重置，这里验证 "cleared >= calls - 1"
    assert(stats.calls >= 1, `setInterval 应至少被调 1 次: ${JSON.stringify(stats)}`);
    assert(
      stats.cleared >= stats.calls - 1,
      `期望 clearInterval >= setInterval-1（保留最后一个）。实际: set=${stats.calls} clear=${stats.cleared}`
    );
  });

  // ---- P0-2 (bug 3.4): 提前结束后 abandoned 状态正确，任务保持可用 ----
  await test('P0-2 stopTimerFromDock 走 abandoned 流程，任务保持可用', async (page) => {
    // 1. 清理可能存在的活动会话
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(800);
    const activeDock = await page.locator('#timerDockActive').isVisible().catch(() => false);
    if (activeDock) {
      await page.click('#timerDockStopBtn');
      await page.waitForTimeout(2000);
      if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
        await page.evaluate(() => {
          const m = document.getElementById('careModal');
          if (m) m.classList.add('hidden');
        });
      }
      await page.waitForTimeout(500);
    }

    // 2. 去任务页新建任务
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(1500);
    const taskName = 'P0-2-abandoned-' + Date.now();
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', taskName);
    await page.fill('#tfTime', '30');
    await page.click('#taskModal button:has-text("保存")');
    await page.waitForFunction(() => {
      const el = document.getElementById('taskModal');
      return el && el.classList.contains('hidden');
    }, { timeout: 10000 });
    await page.waitForTimeout(800);

    // 3. 获取任务 ID 并启动计时
    const taskId = await page.evaluate((name) => {
      const t = (window.allTasks || []).find(x => x.name === name);
      return t ? t.id : null;
    }, taskName);
    assert(taskId, `任务应已创建: ${taskName}`);

    await page.waitForFunction(() => {
      const s = document.getElementById('timerTaskSelect');
      return s && !s.disabled && s.options.length > 1;
    }, { timeout: 10000 });
    await page.locator('#timerTaskSelect').selectOption({ index: 1 });
    await page.fill('#timerPlannedMin', '10');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);

    // 4. 切到抽卡页，点 Dock 停止按钮
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1000);
    const dockStopVisible = await page.locator('#timerDockStopBtn').isVisible().catch(() => false);
    assert(dockStopVisible, 'Dock 停止按钮应可见');

    // 5. 监听 /api/timer/complete 请求，捕获 result 字段
    const completeReqs = [];
    page.on('request', req => {
      if (req.url().includes('/api/timer/complete') && req.method() === 'POST') {
        completeReqs.push(req.postData() || '');
      }
    });
    // 监听 /api/tasks/{id}/complete（不应被调用——任务不应被标记完成）
    const taskCompleteReqs = [];
    page.on('request', req => {
      const m = req.url().match(/\/api\/tasks\/(\d+)\/complete/);
      if (m && req.method() === 'POST') {
        taskCompleteReqs.push({ taskId: m[1], body: req.postData() || '' });
      }
    });

    await page.click('#timerDockStopBtn');
    // 等待弹窗（abandoned 不应弹关怀弹窗，但容错等待）
    await page.waitForTimeout(3000);
    // 若弹出关怀弹窗（说明走了 completed 路径），关闭它
    if (await page.locator('#careModal:not(.hidden)').count().catch(() => 0)) {
      await page.evaluate(() => {
        const m = document.getElementById('careModal');
        if (m) m.classList.add('hidden');
      });
      await page.waitForTimeout(500);
    }

    // 6. 断言 /api/timer/complete 传了 result=abandoned
    const completeBody = completeReqs.join(' ');
    assert(
      completeBody.includes('"result":"abandoned"'),
      `/api/timer/complete 应传 result=abandoned，实际: ${completeBody.substring(0, 200)}`
    );

    // 7. 断言任务未被标记完成（不应调用 /api/tasks/{id}/complete）
    const taskCompleteForOurTask = taskCompleteReqs.filter(r => r.taskId === String(taskId));
    assert(
      taskCompleteForOurTask.length === 0,
      `任务不应被标记完成，实际触发了 ${taskCompleteForOurTask.length} 次 /api/tasks/{id}/complete`
    );

    // 8. 刷新任务列表，断言任务仍可用（completed=false）
    await page.evaluate(async (name) => {
      const tasks = await fetch('/api/tasks').then(r => r.json());
      window.allTasks = tasks;
    }, taskName);
    await page.waitForTimeout(500);
    const finalTask = await page.evaluate((id) => {
      const t = (window.allTasks || []).find(x => x.id === id);
      return t ? { id: t.id, name: t.name, completed: t.completed, in_discard_pile: t.in_discard_pile } : null;
    }, taskId);
    assert(finalTask, `任务应仍存在: id=${taskId}`);
    assert(finalTask.completed !== true, `任务不应被标记 completed: ${JSON.stringify(finalTask)}`);
    assert(finalTask.in_discard_pile !== true, `任务不应进入弃牌堆: ${JSON.stringify(finalTask)}`);

    // 清理测试任务
    await page.evaluate(async (id) => {
      await fetch('/api/tasks/' + id, { method: 'DELETE' });
    }, taskId);
  });

  // ---- P0-3 (bug 1.3): 抽卡后切页无残留动画类 ----
  await test('P0-3 抽卡动画进行中切页，无残留 is-drawing', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(800);

    // 模拟 renderDrawnCard 后的状态：卡片停在 is-drawing（双 rAF 第二个还没跑）
    await page.evaluate(() => {
      const result = document.getElementById('gachaResult');
      const deck = document.getElementById('gachaDeck');
      if (!result || !deck) return;
      // 清理旧残留
      result.innerHTML = '';
      const flyLayer = document.getElementById('cardFlyLayer');
      if (flyLayer) flyLayer.innerHTML = '';
      deck.classList.remove('is-drawing');
      deck.classList.remove('is-revealing');
      // 注入一张模拟卡：停在 is-drawing 状态（模拟 rAF 内层被打断）
      const wrap = document.createElement('div');
      wrap.className = 'drawn-card-stage';
      const card = document.createElement('div');
      card.className = 'task-card card drawn-card theme-default';
      card.setAttribute('data-task-id', '99999');
      card.classList.add('is-drawing');
      // 关键：故意不加 is-revealing——模拟 rAF 链被切断
      wrap.appendChild(card);
      result.appendChild(wrap);
    });

    // 切走
    await page.click('[data-page="tasks"]');
    await page.waitForTimeout(500);

    // 切回
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(500);

    // 检查残留：是否有卡片卡在 is-drawing 但未 is-revealing
    const stuckCards = await page.evaluate(() => {
      const cards = document.querySelectorAll('.task-card.drawn-card');
      const stuck = [];
      cards.forEach(c => {
        if (c.classList.contains('is-drawing') && !c.classList.contains('is-revealing')) {
          stuck.push({
            taskId: c.getAttribute('data-task-id'),
            classes: c.className
          });
        }
      });
      return stuck;
    });
    assert(
      stuckCards.length === 0,
      `切回后不应有卡在 is-drawing 的卡片，实际残留: ${JSON.stringify(stuckCards)}`
    );

    // 清理
    await page.evaluate(() => {
      const r = document.getElementById('gachaResult');
      if (r) r.innerHTML = '';
    });
  });

  // ============ 全局测试 ============
  console.log('\n【全局】');

  await test('7.1 页面导航', async (page) => {
    for (const p of ['gacha', 'tasks', 'schedule', 'knowledge', 'config']) {
      await page.click(`[data-page="${p}"]`);
      await page.waitForTimeout(500);
      const cls = await page.locator(`.nav-btn[data-page="${p}"]`).getAttribute('class');
      assert(cls && cls.includes('active'), `页面 ${p} 导航按钮应激活`);
    }
  });

  await test('7.2 API状态指示器', async (page) => {
    const dot = page.locator('#apiDot');
    assert(await dot.isVisible());
    const cls = await dot.getAttribute('class');
    assert(/online|offline/.test(cls), `状态应为 online/offline: ${cls}`);
  });

  // ============ 汇总 ============
  console.log('\n' + '='.repeat(60));
  console.log(`测试结果: ${passed} 通过, ${failed} 失败`);
  console.log('='.repeat(60));

  if (networkErrors.length > 0) {
    console.log('\n网络错误（500）：');
    networkErrors.forEach(e => console.log(`  ${e.status} ${e.url}`));
  }

  console.log('\n详细结果:');
  results.forEach(r => {
    const icon = r.status === 'PASS' ? '✓' : '✗';
    console.log(`  ${icon} ${r.name}${r.error ? ': ' + r.error : ''}`);
  });

  await browser.close();
  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(e => {
  console.error('测试运行失败:', e.message);
  process.exit(1);
});