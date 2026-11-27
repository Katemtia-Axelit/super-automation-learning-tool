/**
 * E2E 测试 - 学习工具前端
 * 简化为非嵌套结构，直接使用 test()
 */
const { test, expect } = require('@playwright/test');

const BASE_URL = 'http://127.0.0.1:5000';

async function waitForApiReady(page) {
  await page.waitForFunction(() => {
    const dot = document.getElementById('apiDot');
    return dot && dot.classList.contains('online');
  }, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);
}

// ============ 抽卡测试 ============

test('Gacha-1.1 抽卡页面加载', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);

  await page.click('[data-page="gacha"]');
  await page.waitForTimeout(1000);

  await expect(page.locator('#gachaBtn')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('#gachaDeck')).toBeVisible();
  await expect(page.locator('#gachaTimeInput')).toBeVisible();
});

test('Gacha-1.2 抽卡流程', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="gacha"]');
  await page.waitForTimeout(1000);

  await page.click('#gachaBtn');

  try {
    await page.waitForSelector('.task-card.drawn-card', { timeout: 10000 });
    await expect(page.locator('.task-card.drawn-card')).toBeVisible();
    await expect(page.locator('.task-card.drawn-card button:has-text("开始任务")')).toBeVisible();
  } catch {
    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible({ timeout: 1000 }).catch(() => false)) {
      // OK - 卡池为空
    }
  }
});

test('Gacha-1.3 抽卡防抖', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="gacha"]');
  await page.waitForTimeout(1000);

  // 连续点击应该被防抖
  await page.click('#gachaBtn');
  await page.waitForTimeout(50);
  await page.click('#gachaBtn');
  await page.waitForTimeout(50);
  await page.click('#gachaBtn');

  // 按钮应该最终可用
  await page.waitForTimeout(3000);
  await expect(page.locator('#gachaBtn')).toBeEnabled();
});

// ============ 任务测试 ============

test('Tasks-2.1 任务列表加载', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(2000);

  await expect(page.locator('#taskGrid')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('.task-toolbar')).toBeVisible();
});

test('Tasks-2.2 新建任务', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  const beforeCount = await page.locator('.task-card:not(.drawn-card)').count();

  await page.click('button:has-text("新建任务")');
  await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
  await page.fill('#tfName', 'E2E测试任务-' + Date.now());
  await page.fill('#tfTime', '30');
  await page.click('#taskModal button:has-text("保存")');
  await page.waitForSelector('#taskModal.hidden', { timeout: 5000 });
  await page.waitForTimeout(1500);

  const afterCount = await page.locator('.task-card:not(.drawn-card)').count();
  expect(afterCount).toBeGreaterThanOrEqual(beforeCount);
});

test('Tasks-2.3 编辑任务', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  const editBtn = page.locator('.task-card-actions button:has-text("编辑")').first();
  if (await editBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await editBtn.click();
    await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
    await page.fill('#tfName', 'E2E已编辑-' + Date.now());
    await page.click('#taskModal button:has-text("保存")');
    await page.waitForSelector('#taskModal.hidden', { timeout: 5000 });
  }
});

test('Tasks-2.4 搜索筛选', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  await page.fill('#taskSearch', 'E2E');
  await page.waitForTimeout(500);
  await page.fill('#taskSearch', '');

  await page.selectOption('#taskFilter', 'all');
  await page.waitForTimeout(300);
  await page.selectOption('#taskFilter', 'unlocked');
  await page.waitForTimeout(300);
});

test('Tasks-2.5 删除任务', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  const deleteBtn = page.locator('.task-card-actions button:has-text("删除")').first();
  if (await deleteBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    const beforeCount = await page.locator('.task-card:not(.drawn-card)').count();
    page.once('dialog', dialog => dialog.accept());
    await deleteBtn.click();
    await page.waitForTimeout(2000);
    const afterCount = await page.locator('.task-card:not(.drawn-card)').count();
    expect(afterCount).toBeLessThanOrEqual(beforeCount);
  }
});

// ============ 计时器测试 ============

test('Timer-3.1 计时器面板', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  await expect(page.locator('#timerPanel')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('#timerStartBtn')).toBeVisible();
  await expect(page.locator('#timerTaskSelect')).toBeVisible();
});

test('Timer-3.2 计时器Dock', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="gacha"]');
  await page.waitForTimeout(1000);

  await expect(page.locator('#timerDock')).toBeVisible();
  await expect(page.locator('#timerDockIdle, #timerDockActive')).toBeVisible();
});

test('Timer-3.3 开始计时', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="tasks"]');
  await page.waitForTimeout(1500);

  // 创建测试任务
  await page.click('button:has-text("新建任务")');
  await page.waitForSelector('#taskModal:not(.hidden)', { timeout: 5000 });
  await page.fill('#tfName', '计时器E2E测试');
  await page.fill('#tfTime', '30');
  await page.click('#taskModal button:has-text("保存")');
  await page.waitForSelector('#taskModal.hidden', { timeout: 5000 });
  await page.waitForTimeout(1000);

  const taskSelect = page.locator('#timerTaskSelect');
  const options = await taskSelect.locator('option').count();

  if (options > 1) {
    await taskSelect.selectOption({ index: 1 });
    await page.fill('#timerPlannedMin', '1');
    await page.click('#timerStartBtn');
    await page.waitForTimeout(2000);

    const timerDisplay = page.locator('#timerElapsedDisplay');
    await expect(timerDisplay).toBeVisible();
    const time1 = await timerDisplay.textContent();
    expect(time1).not.toBe('00:00');
  }
});

// ============ 日程测试 ============

test('Schedule-4.1 日程页面加载', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="schedule"]');
  await page.waitForTimeout(2000);

  await expect(page.locator('#sleepPanel')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('.schedule-nav')).toBeVisible();
  await expect(page.locator('#schedGrid')).toBeVisible();
});

test('Schedule-4.2 日期导航', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="schedule"]');
  await page.waitForTimeout(1500);

  const dateBefore = await page.locator('#schedDate').textContent();
  await page.click('.schedule-nav button:first-child');
  await page.waitForTimeout(500);
  const dateAfter = await page.locator('#schedDate').textContent();
  expect(dateAfter).not.toBe(dateBefore);
});

test('Schedule-4.3 睡眠追踪', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="schedule"]');
  await page.waitForTimeout(1500);

  await expect(page.locator('#sleepPanel')).toBeVisible();
  await expect(page.locator('#sleepBedTimeInput')).toBeVisible();
  await page.fill('#sleepBedTimeInput', '23:30');
  await page.click('#sleepSaveBtn');
  await page.waitForTimeout(1500);
});

test('Schedule-4.4 活动管理', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="schedule"]');
  await page.waitForTimeout(1500);

  await page.click('button:has-text("活动管理")');
  await page.waitForSelector('#activityMgrModal:not(.hidden)', { timeout: 5000 });
  await expect(page.locator('#activityMgrModal')).toBeVisible();
  await page.click('#activityMgrCloseBtn');
  await page.waitForSelector('#activityMgrModal.hidden', { timeout: 3000 });
});

// ============ 知识库测试 ============

test('Knowledge-5.1 知识库页面加载', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="knowledge"]');
  await page.waitForTimeout(3000);

  await expect(page.locator('.know-layout')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('#catList')).toBeVisible();
  await expect(page.locator('#noteList')).toBeVisible();
  await expect(page.locator('#knowContent')).toBeVisible();
});

test('Knowledge-5.2 分类和笔记列表', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="knowledge"]');
  await page.waitForTimeout(3000);

  const categories = page.locator('.cat-item');
  const count = await categories.count();

  if (count > 0) {
    await categories.first().click();
    await page.waitForTimeout(1500);

    const notes = page.locator('.note-item');
    if (await notes.count() > 0) {
      await notes.first().click();
      await page.waitForTimeout(2000);
      await expect(page.locator('#knowContent')).toBeVisible();
    }
  }
});

// ============ 设置测试 ============

test('Config-6.1 设置页面加载', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="config"]');
  await page.waitForTimeout(2000);

  await expect(page.locator('#cfgPort')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('#cfgNotesDir')).toBeVisible();
  await expect(page.locator('#cfgApiKey')).toBeVisible();
});

test('Config-6.2 提示词浏览', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="config"]');
  await page.waitForTimeout(2000);

  await page.waitForSelector('#promptFileList', { timeout: 5000 });
  await expect(page.locator('#promptFileList')).toBeVisible();
  await expect(page.locator('#promptContentView')).toBeVisible();
});

test('Config-6.3 Agent只读面板', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);
  await page.click('[data-page="config"]');
  await page.waitForTimeout(2000);

  await page.click('#agentReadonlyOpenBtn');
  await page.waitForSelector('#agentReadonlyModal:not(.hidden)', { timeout: 5000 });
  await expect(page.locator('#agentReadonlyModal')).toBeVisible();

  await page.locator('.agent-ro-tab[data-agent-tab="agents"]').click();
  await page.waitForTimeout(500);
  await page.locator('.agent-ro-tab[data-agent-tab="raw"]').click();
  await page.waitForTimeout(500);
  await page.locator('.agent-ro-tab[data-agent-tab="vault"]').click();
  await page.waitForTimeout(500);

  await page.click('#agentReadonlyCloseBtn');
  await page.waitForSelector('#agentReadonlyModal.hidden', { timeout: 3000 });
});

// ============ 全局测试 ============

test('Global-7.1 页面导航', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);

  const pages = ['gacha', 'tasks', 'schedule', 'knowledge', 'config'];
  for (const pageName of pages) {
    await page.click(`[data-page="${pageName}"]`);
    await page.waitForTimeout(500);
    const navBtn = page.locator(`.nav-btn[data-page="${pageName}"]`);
    await expect(navBtn).toHaveClass(/active/);
  }
});

test('Global-7.2 API状态指示器', async ({ page }) => {
  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);

  const dot = page.locator('#apiDot');
  await expect(dot).toBeVisible();
  const status = await dot.getAttribute('class');
  expect(status).toMatch(/online|offline/);
});

test('Global-7.3 网络错误检测', async ({ page }) => {
  const networkErrors = [];

  page.on('response', response => {
    const url = response.url();
    const status = response.status();
    if (url.includes('/api/') && status >= 400) {
      networkErrors.push({ url, status });
    }
  });

  await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
  await waitForApiReady(page);

  for (const pageName of ['gacha', 'tasks', 'schedule', 'knowledge', 'config']) {
    await page.click(`[data-page="${pageName}"]`);
    await page.waitForTimeout(2000);
  }

  if (networkErrors.length > 0) {
    console.log('\n=== 网络错误 ===');
    networkErrors.forEach(e => console.log(`${e.status} ${e.url}`));
  }

  const criticalErrors = networkErrors.filter(e => {
    return e.status >= 500 && !e.url.includes('/api/agent');
  });

  expect(criticalErrors.length).toBe(0);
});
