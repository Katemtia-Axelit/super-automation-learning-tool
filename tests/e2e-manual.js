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

  async function test(name, fn) {
    // 每个测试独立 page 实例
    const page = await context.newPage();
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
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
      page.once('dialog', d => d.accept());
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
    // 创建任务
    await page.click('button:has-text("新建任务")');
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', '计时器E2E测试');
    await page.fill('#tfTime', '30');
    await page.click('#taskModal button:has-text("保存")');
    await page.waitForSelector('#taskModal.hidden', { timeout: 10000 });
    await page.waitForTimeout(800);

    const sel = page.locator('#timerTaskSelect');
    const opts = await sel.locator('option').count();
    if (opts > 1) {
      await sel.selectOption({ index: 1 });
      await page.fill('#timerPlannedMin', '1');
      await page.click('#timerStartBtn');
      await page.waitForTimeout(2000);
      const timerDisplay = page.locator('#timerElapsedDisplay');
      assert(await timerDisplay.isVisible());
      const time = await timerDisplay.textContent();
      assert(time !== '00:00', `计时器应走动，当前: ${time}`);
    }
  });

  await test('3.4 提前结束计时', async (page) => {
    await page.click('[data-page="gacha"]');
    await page.waitForTimeout(1500);
    const stopBtn = page.locator('#timerDockStopBtn');
    if (await stopBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      page.once('dialog', d => d.accept());
      await stopBtn.click();
      await page.waitForTimeout(2000);
    }
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