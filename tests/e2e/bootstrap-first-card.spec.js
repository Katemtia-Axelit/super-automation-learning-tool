/**
 * tests/e2e/bootstrap-first-card.spec.js
 *
 * P0 引导卡隔离浏览器测试 (LT_BOOTSTRAP_FIRST_CARD_20261021_A).
 *
 * Server fixture: tests/e2e/factory-sandbox-server.py
 *   - 100% %TEMP% synthetic root, 127.0.0.1:<random> port
 *   - copies real server/*.py, real src/index.html, real static allowlist
 *     (now including bootstrap-first-card.js + bootstrap-steward-prompt.txt)
 *   - seeds synthetic SQLite; the real DB / notes / config are never used
 *
 * Cases:
 *   A) 首次唯一卡：无有效策略时，正式界面只暴露引导卡，隐藏普通抽卡入口
 *   B) 开始任务：展示 25 分钟倒计时 + 完整可复制提示词 + 打开 ChatGPT 指引
 *   C) 复制动作：点击复制后能得到完整提示词文本
 *   D) 无暂停 / 换卡 / 拒绝 / 跳过：引导层内不存在这些控件
 *   E) 刷新依旧锁定：刷新后仍停在引导流程（不因计时结束解锁）
 *   F) 无配置禁止解锁：引导期间普通抽卡写请求被拒绝（fail closed）
 *   G) 配置有效后正常页面恢复：写入合法的 latest.json 后覆盖层移除
 *   H) API 断线 fail closed：status 端点不可达时不得误入正常抽卡
 *   I) 服务端权威闸门：非浏览器 HTTP 客户端直接 POST 同样被 423 拒绝
 */

const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const E2E_DIR = __dirname;
const FIXTURE_PATH = path.join(E2E_DIR, 'factory-sandbox-server.py');

// 浏览器会把 textarea 的值标准化为 LF，而磁盘上的提示词文件是 CRLF。
// 逐字符比较会因为换行符差异而误报，因此统一换行后再做文本同一性验证。
function normalizeNewlines(value) {
  return typeof value === 'string' ? value.replace(/\r\n/g, '\n') : value;
}

const VALID_POLICY = {
  schema_version: 1,
  version: '2026-10-21.1',
  approved_by_user: true,
  approved_at: '2026-10-21T12:00:00Z',
};

function startFactory(envOverrides) {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const venvPy = path.join(
    path.resolve(E2E_DIR, '..', '..'), '.venv', 'Scripts', 'python.exe',
  );
  const candidate = fs.existsSync(venvPy) ? venvPy : py;

  const child = spawn(
    candidate,
    ['-B', FIXTURE_PATH, '--print-url'],
    {
      cwd: E2E_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      env: Object.assign({}, process.env, envOverrides || {}),
    },
  );

  let stdoutAll = '';
  let stderrAll = '';
  child.stdout.on('data', (c) => { stdoutAll += c.toString(); });
  child.stderr.on('data', (c) => { stderrAll += c.toString(); });

  return new Promise((resolve, reject) => {
    let resolved = false;
    const onExit = (code) => {
      if (resolved) return;
      resolved = true;
      reject(new Error(
        `factory fixture exited early rc=${code}\n${stdoutAll}\n${stderrAll}`,
      ));
    };
    child.once('exit', onExit);
    child.once('error', (err) => {
      if (resolved) return;
      resolved = true;
      reject(err);
    });

    const timer = setInterval(() => {
      if (resolved) return;
      const urlMatch = stdoutAll.match(/^URL:(http:\/\/127\.0\.0\.1:\d+)\s*$/m);
      const tmpMatch = stdoutAll.match(/^TMPDIR:(.+)$/m);
      const pidMatch = stdoutAll.match(/^CHILDPID:(\d+)\s*$/m);
      if (!urlMatch) return;
      resolved = true;
      clearInterval(timer);
      child.removeListener('exit', onExit);
      const tmpdir = tmpMatch ? tmpMatch[1].trim() : null;
      const grandchildPid = pidMatch ? parseInt(pidMatch[1], 10) : null;
      resolve({
        baseUrl: urlMatch[1],
        tmpdir,
        grandchildPid,
        stop: () => new Promise((stopResolve) => {
          const killGrandchild = () => {
            if (!grandchildPid) return;
            try { process.kill(grandchildPid, 'SIGKILL'); } catch (_e) { /* noop */ }
          };
          killGrandchild();
          setTimeout(() => {
            try { child.kill(); } catch (_e) { /* noop */ }
          }, 200);
          const purge = () => {
            if (!tmpdir) return;
            try {
              fs.rmSync(tmpdir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
            } catch (_e) { /* noop */ }
          };
          setTimeout(purge, 400);
          setTimeout(() => { purge(); stopResolve(); }, 4000);
        }),
      });
    }, 100);
    setTimeout(() => {
      if (resolved) return;
      resolved = true;
      clearInterval(timer);
      child.kill();
      reject(new Error(`fixture did not print URL\n${stdoutAll}\n${stderrAll}`));
    }, 30000);
  });
}

let factoryHandle = null;

test.beforeAll(async () => {
  factoryHandle = await startFactory();
});

test.afterAll(async () => {
  if (factoryHandle) {
    await factoryHandle.stop();
    factoryHandle = null;
  }
});

async function installSafetyRoutes(context, baseUrl) {
  await context.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.startsWith(baseUrl + '/')) return route.continue();
    if (url.startsWith('data:') || url.startsWith('blob:')) return route.continue();
    return route.abort();
  });
}

function policyDirFor(handle) {
  // factory-sandbox-server.py prints the temp PARENT dir; the synthetic
  // project root is <TMPDIR>/root inside it.
  return path.join(handle.tmpdir, 'root', 'data', 'agent-policy');
}

function policyDir() {
  return policyDirFor(factoryHandle);
}

function writePolicyTo(handle, doc) {
  const dir = policyDirFor(handle);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(
    path.join(dir, 'latest.json'),
    JSON.stringify(doc, null, 2),
    'utf8',
  );
}

function writePolicy(doc) {
  writePolicyTo(factoryHandle, doc);
}

function removePolicyFrom(handle) {
  const file = path.join(policyDirFor(handle), 'latest.json');
  if (fs.existsSync(file)) fs.rmSync(file, { force: true });
}

function removePolicy() {
  removePolicyFrom(factoryHandle);
}

async function gotoBoot(page, baseUrl) {
  await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#salBootstrapOverlay', { timeout: 15000 });
}

test.describe('P0 引导卡 (LT_BOOTSTRAP_FIRST_CARD_20261021_A)', () => {
  test.beforeEach(() => { removePolicy(); });

  test('A) 首次唯一卡：无有效策略时只暴露引导卡，普通抽卡入口不可用', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await gotoBoot(page, baseUrl);

    // 覆盖层可见
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();
    await expect(page.locator('#salBootstrapCard')).toBeVisible();

    // 唯一可操作按钮是「开始任务」
    await expect(page.locator('#salBootstrapStartBtn')).toHaveCount(1);
    await expect(page.locator('#salBootstrapStartBtn')).toBeVisible();
    await expect(page.locator('#salBootstrapStartBtn')).toHaveText('开始任务');

    // 普通界面元素被强制覆盖隐藏
    await expect(page.locator('#gachaBtn')).toBeHidden();
    await expect(page.locator('#gachaMultiBtn')).toBeHidden();
    await expect(page.locator('#timerDock')).toBeHidden();
    await expect(page.locator('.nav-btn[data-page="tasks"]')).toBeHidden();

    // 提示词面板在点击「开始任务」之前不暴露
    await expect(page.locator('#salBootstrapPromptText')).toBeHidden();

    // 覆盖层里不存在暂停 / 换卡 / 拒绝 / 跳过 **可交互控件**。
    //
    // 注意：不能对整段 innerHTML 做关键词搜索——「拒绝率统计」这类
    // 说明性文案是**不可操作**的纯文本，搜整段 HTML 会误报。
    // 契约要保证的是「用户点不到这些出口」，因此这里只检索真正
    // 可交互且可见的控件。
    const forbidden = await page.evaluate(() => {
      const overlay = document.getElementById('salBootstrapOverlay');
      if (!overlay) return { noOverlay: true, hits: [], visibleIds: [] };
      const SELECTOR =
        'button, a[href], input, select, textarea, [role="button"], ' +
        '[onclick], [contenteditable="true"]';
      const isVisible = (el) => {
        if (el.closest('[hidden]')) return false;
        const cs = window.getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      };
      const describe = (el) => [
        el.tagName.toLowerCase(),
        el.id || '',
        el.getAttribute('title') || '',
        el.getAttribute('aria-label') || '',
        el.textContent || '',
        el.value || '',
      ].join(' ');
      const all = Array.from(overlay.querySelectorAll(SELECTOR));
      const PATTERNS = {
        pause: /暂停/,
        replace: /换卡|换一张|重新抽|再抽/,
        refuse: /拒绝/,
        skip: /跳过/,
      };
      const hits = [];
      for (const el of all) {
        if (!isVisible(el)) continue;
        const label = describe(el);
        for (const key of Object.keys(PATTERNS)) {
          if (PATTERNS[key].test(label)) {
            hits.push({ key, id: el.id || '', label: label.slice(0, 60) });
          }
        }
      }
      return {
        noOverlay: false,
        hits,
        visibleIds: all.filter(isVisible).map((el) => el.id || el.tagName),
      };
    });
    expect(forbidden.noOverlay).toBe(false);
    expect(forbidden.hits).toEqual([]);

    // 第一阶段可见的可交互控件有且只有「开始任务」。
    expect(forbidden.visibleIds).toEqual(['salBootstrapStartBtn']);

    // 真实 DOM 中对应的暂停 / 跳过出口必须被覆盖层强制隐藏。
    for (const sel of [
      '#timerDockPauseBtn',
      '#timerPauseBtn',
      '#taskFeedbackCancelBtn',
    ]) {
      await expect(page.locator(sel)).toBeHidden();
    }

    expect(pageErrors).toEqual([]);
  });

  test('B) 开始任务：展示 25 分钟倒计时 + 完整提示词 + 打开 ChatGPT 指引', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await gotoBoot(page, baseUrl);
    await page.click('#salBootstrapStartBtn');

    // 倒计时出现，初始为 25:00 附近
    await expect(page.locator('#salBootstrapTimer')).toBeVisible();
    const clock = await page.locator('#salBootstrapTimer').innerText();
    expect(clock).toMatch(/^2[45]:\d{2}$/);

    // 提示词面板可见且内容完整。
    // 注意：textarea 先变为可见，内容随后才由 fetch 填充；
    // 直接读 inputValue() 会偶发读到空串（竞态，不是内容问题）。
    // 这里**等真实内容到位**，仍然要求完整长度，不放宽要求。
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();
    await expect
      .poll(
        async () => (await page.locator('#salBootstrapPromptText').inputValue()).length,
        { timeout: 15000 },
      )
      .toBeGreaterThan(200);
    const promptText = await page.locator('#salBootstrapPromptText').inputValue();
    expect(promptText.length).toBeGreaterThan(200);
    for (const kw of ['管家', '批准', '自由任务', '番茄钟', 'DC']) {
      expect(promptText).toContain(kw);
    }

    // 打开 ChatGPT 的明确指引
    const chatHref = await page.locator('#salBootstrapChatLink').getAttribute('href');
    expect(chatHref).toContain('chatgpt.com');
    await expect(page.locator('#salBootstrapChatLink')).toBeVisible();

    // 唯一入口按钮在第二阶段隐藏
    await expect(page.locator('#salBootstrapStartBtn')).toBeHidden();

    expect(pageErrors).toEqual([]);
  });

  test('C) 复制动作：可复制完整提示词', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], {
      origin: baseUrl,
    });

    await gotoBoot(page, baseUrl);
    await page.click('#salBootstrapStartBtn');
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();

    // 权威来源：直接从 /static 拉取原始提示词（磁盘上是 CRLF）。
    const rawPrompt = await page.evaluate(async () => {
      const r = await fetch('/static/bootstrap-steward-prompt.txt', {
        cache: 'no-store',
      });
      return r.ok ? r.text() : '';
    });
    expect(rawPrompt.length).toBeGreaterThan(200);

    // textarea.inputValue() 会被浏览器标准化为 LF，所以这里
    // 统一换行后再比较（不是放宽要求，仍然要求逐字符同一）。
    const shown = await page.locator('#salBootstrapPromptText').inputValue();
    expect(normalizeNewlines(shown)).toBe(normalizeNewlines(rawPrompt));

    await page.click('#salBootstrapCopyBtn');

    await expect(page.locator('#salBootstrapCopyStatus')).not.toHaveText('');

    // 复制内容经由 window 句柄暴露（供隔离断言），应与提示词一致
    const copied = await page.evaluate(() => window.SAL_BOOTSTRAP_LAST_COPIED || '');
    expect(copied.length).toBeGreaterThan(200);
    expect(normalizeNewlines(copied)).toBe(normalizeNewlines(rawPrompt));
    expect(normalizeNewlines(copied)).toBe(normalizeNewlines(shown));
    expect(copied).toContain('管家');

    // 实物剪贴板必须与提示词一致（读取失败即视为失败，不得用固定字符串
    // 伪造成功——那只能证明测试自己写了个常量）。
    const clip = await page.evaluate(async () => {
      try {
        return await navigator.clipboard.readText();
      } catch (e) {
        return null;
      }
    });
    expect(clip, '实物剪贴板必须可读').not.toBeNull();
    expect(clip.length).toBeGreaterThan(200);
    expect(normalizeNewlines(clip)).toBe(normalizeNewlines(rawPrompt));

    // -------------------------------------------------------------------
    // 产品契约语义断言 (G-START-2)。
    //
    // 断言对象是**页面上真实展示 / 真实复制出去的文本**，不是文件存在性，
    // 也不是假 DOM。因此：先证明剪贴板与 /static 原文逐字符同一（上面已证），
    // 下面的关键词/语义断言因此就是对"用户真正粘进 ChatGPT 的那段话"的断言。
    // 任何一条缺失都说明管家 Prompt 与用户已批准的产品合同发生偏离。
    // -------------------------------------------------------------------
    const text = normalizeNewlines(clip);

    // (1) 自由卡 = 统一抽卡池里策略主动派发的卡牌类型，而不是独立小工具。
    expect(text, '自由卡必须被描述为统一卡池里的卡').toMatch(
      /自由卡[\s\S]{0,80}(统一|同一)[^\n]{0,40}(卡池|系统)/,
    );
    expect(text).toContain('不是让用户自己另建');
    expect(text).toMatch(/由策略主动派发/);
    expect(
      text.match(/微型任务[^。\n]{0,40}目标任务[^。\n]{0,40}(同一个|同一套)/) || [],
      '微型任务与目标任务必须声明属于同一系统',
    ).not.toHaveLength(0);
    // 策略决定 25/55，而不是抽到后让用户手动二选一。
    expect(text).toMatch(/由有效策略在抽卡时抽定/);
    expect(text, '禁止把时长选择抛回给用户').toContain('抽到之后不再手动二选一');
    // 初期高自由权重 + 娱乐是合法默认承接。
    expect(text).toMatch(/权重可以\s*\*\*故意很高\*\*/);
    for (const entertainment of ['打游戏', '看视频', '读小说']) {
      expect(text, entertainment).toContain(entertainment);
    }
    expect(text, '不能把大量娱乐当成失败').toContain('不是失败');

    // (2) 默认理由必须严格是用户原文。
    expect(text).toContain('没有什么理由，我就是想。');

    // (3) 手机自行设定定时器 + 时间到不自动判完成 + 用户主动结束反馈。
    expect(text).toMatch(/自己在手机上设定定时器/);
    expect(text, '时间到不得自动判定完成').toMatch(
      /不会[\s\S]{0,20}自动判定完成/,
    );
    expect(text).toMatch(/主动点结束/);
    for (const feedback of ['是否顺利', '是否有中断', '实际做了什么']) {
      expect(text, feedback).toContain(feedback);
    }
    expect(text, '必须有“帮我选”给一个具体行动').toMatch(
      /点「帮我选」[\s\S]{0,60}给 \*\*一个\*\*/,
    );

    // (4) 首次启动必须先收集真实目标，而不是直接给日程。
    expect(text, '必须先问再建议').toContain('先问，再建议');
    expect(text, '一次最多 2-3 个问题').toMatch(/一次最多问\s*2–3 个/);
    for (const target of ['番茄', 'ml', '圈']) {
      expect(text, '必须询问目标：' + target).toContain(target);
    }
    expect(text, '必须询问真实限制').toContain('真实限制');

    // (5) 学习 / 娱乐统计必须分开，且不得一律归零，必须区分自报与核实。
    expect(text).toMatch(/娱乐类自由卡完成[\s\S]{0,40}算一次成功任务/);
    expect(text, '娱乐不得冒充学习番茄').toMatch(
      /不计入有效学习番茄钟[\s\S]{0,60}绝不能把娱乐冒充成学习/,
    );
    expect(text, '不能把自由任务一律判为零学习').toMatch(
      /不要反过来把所有自由任务一律判成「零学习」/,
    );
    expect(text).toContain('用户自报');
    expect(text).toContain('核实记录');
    expect(text, '不得仅凭活动类型无条件标已验证').toMatch(
      /绝不因为「活动类型看起来像学习」就无条件标成「客观已验证」/,
    );

    // (6) 用户批准优先于一切写入，且不得让用户参与参数细节。
    expect(text).toMatch(/明确表示批准/);
    expect(text, '含糊回应不算批准').toContain('不算批准');
    expect(text, '发布必须走受控发布器').toContain(
      'scripts/agent_policy_publisher.py',
    );
    expect(text, '提案必须兼容既有 publisher schema').toContain('schema_version');
    expect(text, '历史不可变、程序只读 latest').toMatch(/程序只读取\s*`latest`/);
    expect(text, '不得让用户决定 0.4 / 0.6').toMatch(
      /\*\*绝对不要\*\*问用户「这个参数调到 0\.4/,
    );
    expect(text, '禁止编造已批准配置').toContain(
      '绝对不要编造一份「已批准」的配置',
    );

    // (7) 换卡 / 弃牌 / 记录 / 情绪线索：只作假设，不作诊断。
    expect(text).toMatch(/每一次换卡 \*\*必须填写理由\*\*/);
    expect(text, '可多次换卡、每次独立记录').toMatch(
      /可以换很多次[\s\S]{0,30}每一次都要独立记录/,
    );
    expect(text).toContain('可以再抽一次');
    expect(text).toContain('我今天不想再看到这张卡');
    expect(text).toMatch(/弃牌堆在服务启动时按各自周期/);
    expect(text).toMatch(
      /只是假设，\*\*不是诊断\*\*[\s\S]{0,40}你不能武断地下结论[\s\S]{0,40}不许推断/,
    );

    // (8) 先问后建议 / DC 核实 / 不得编造历史 / 不得绕红线等既有约束不得被删。
    for (const kept of ['先核实实际的数据路径', '不得编造用户历史', 'src/notes/**']) {
      expect(text, kept).toContain(kept);
    }

    // (9) 负面断言：不得把"过密日程"当成首要目标，也不得诱导用户选参数。
    expect(text, '首要目标是留存与降低决策负担').toContain('少替他做决定');
    expect(text, '明确反对密不透风的日程').toContain('日程排得多满、计划多详细');
    // 数值计算示例可以出现；真正禁止的是让用户决定技术系数。
    for (const line of text.split('\n')) {
      if (!/0\.\d/.test(line) || !/问用户|让用户|请用户|你觉得|合适吗/.test(line)) continue;
      expect(line, '不得要求用户选择技术参数: ' + line).toMatch(
        /绝对不要|不要问|禁止|不得/,
      );
    }
    expect(
      text.match(/0\.4/g) || [],
      '必须明确点名禁止把 0.4 这类系数丢给用户',
    ).toHaveLength(1);

    // (10) 权威合同优先 + 中文 + 不膨胀成法律文本。
    expect(text).toContain('以权威产品合同为准');
    expect(text).toContain('全程使用中文');
    expect(text.length, '不得膨胀成法律文本').toBeLessThan(9000);
  });

  test('D) 刷新依旧锁定：刷新后仍停在引导流程', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    await gotoBoot(page, baseUrl);
    await page.click('#salBootstrapStartBtn');
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();

    // 模拟"25 分钟到时"：把已用时长推到 25 分钟以上，刷新后不得解锁
    await page.evaluate(() => {
      const raw = window.localStorage.getItem('sal.bootstrap.v1');
      if (!raw) return;
      const state = JSON.parse(raw);
      state.stage = 'prompt';
      state.startedAt = Date.now() - 26 * 60 * 1000;
      state.elapsed = 0;
      window.localStorage.setItem('sal.bootstrap.v1', JSON.stringify(state));
    });

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#salBootstrapOverlay', { timeout: 15000 });

    // 仍然锁定：覆盖层在，普通抽卡不可见
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();
    await expect(page.locator('#gachaBtn')).toBeHidden();

    // 计时到 0 也不会解锁
    const clock = await page.locator('#salBootstrapTimer').innerText();
    expect(clock).toMatch(/^00:0\d$/);

    // 仍然处于提示词阶段（localStorage 恢复）
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();
  });

  test('F) 无配置禁止解锁：引导期间普通抽卡写请求被拒绝', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const drawRequests = [];
    page.on('request', (req) => {
      if (req.url().includes('/api/gacha/draw') ||
          req.url().includes('/api/gacha/multi-draw')) {
        drawRequests.push(req.method());
      }
    });

    await gotoBoot(page, baseUrl);

    // 直接尝试抽卡写请求 —— 必须被前端守卫拒绝，且不发出网络请求
    const result = await page.evaluate(async () => {
      try {
        await fetch('/api/gacha/draw', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ energy: 'medium' }),
        });
        return 'sent';
      } catch (e) {
        return 'blocked';
      }
    });
    expect(result).toBe('blocked');

    // 也不能启动计时器
    const timerResult = await page.evaluate(async () => {
      try {
        await fetch('/api/timer/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_id: 1, planned_minutes: 25 }),
        });
        return 'sent';
      } catch (e) {
        return 'blocked';
      }
    });
    expect(timerResult).toBe('blocked');

    await page.waitForTimeout(600);
    expect(drawRequests.length).toBe(0);

    // 覆盖层依然存在（未解锁）
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();
  });

  test('G) 配置有效后正常页面恢复', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    // 先确认无配置时被锁
    await gotoBoot(page, baseUrl);
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();

    // 写入合法的、已批准的策略（写入的是 %TEMP% 合成目录）
    writePolicy(VALID_POLICY);

    // 批准后覆盖层会被移除，等待「安全状态」而不是等覆盖层重新可见
    //（后者在 releaseLock() 之后永远不会发生，只会超时）。
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({
      timeout: 15000,
    });

    // 正常抽卡页面恢复
    await expect(page.locator('#gachaBtn')).toBeVisible();
    await expect(page.locator('.nav-btn[data-page="gacha"]')).toBeVisible();
    await expect(page.locator('#salBootstrapPromptText')).toHaveCount(0);

    // 正常抽卡写请求不再被前端守卫阻断
    const guardState = await page.evaluate(() => window.SAL_BOOTSTRAP.state());
    expect(guardState.locked).toBe(false);
    expect(guardState.initialized).toBe(true);

    // 真实抽卡写请求必须成功——证明是「经批准后恢复正常抽卡」，
    // 而不是绕过批准后误入。
    const drawn = await page.evaluate(async () => {
      const r = await fetch('/api/gacha/draw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ energy: 'medium' }),
      });
      return { status: r.status, ok: r.ok };
    });
    expect(drawn.status).toBe(200);
    expect(drawn.ok).toBe(true);
  });

  test('H) API 断线 fail closed：status 不可达时不得误入正常抽卡', async ({ page, context }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    // 主动中断 status 端点（模拟断线）
    await context.route('**/api/agent-policy/status', (route) => route.abort());

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#salBootstrapOverlay', { timeout: 15000 });

    // 覆盖层仍在，且显示错误提示 + 重新检测按钮
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();
    await expect(page.locator('#salBootstrapErrorText')).toBeVisible();
    await expect(page.locator('#salBootstrapErrorText')).not.toHaveText('');
    await expect(page.locator('#salBootstrapRetryBtn')).toBeVisible();

    // 不得误入正常抽卡
    await expect(page.locator('#gachaBtn')).toBeHidden();

    const guardState = await page.evaluate(() => window.SAL_BOOTSTRAP.state());
    expect(guardState.locked).toBe(true);
    expect(guardState.initialized).toBe(false);
  });

  test('I) 服务端权威闸门：非浏览器 HTTP 客户端直接 POST 也会被拒绝', async ({
    page,
    context,
  }) => {
    // 单独起一个开启了服务端闸门的合成 Factory。
    const handle = await startFactory({ SAL_ENFORCE_AGENT_POLICY: '1' });
    try {
      removePolicyFrom(handle);
      await installSafetyRoutes(context, handle.baseUrl);
      await page.goto(handle.baseUrl + '/', { waitUntil: 'domcontentloaded' });

      // 无策略：覆盖层仍然存在（UI 层 fail closed）
      await expect(page.locator('#salBootstrapOverlay')).toBeVisible({
        timeout: 15000,
      });

      // 关键证据：context.request 是**页外 HTTP 客户端**，
      // 不经过前端的 fetch / click 守卫。服务端必须自行拒绝。
      for (const endpoint of [
        '/api/gacha/draw',
        '/api/gacha/multi-draw',
        '/api/gacha/replace',
        '/api/timer/start',
        '/api/tasks',
      ]) {
        const resp = await context.request.post(
          handle.baseUrl + endpoint,
          { data: {} },
        );
        expect(resp.status(), endpoint).toBe(423);
        const body = JSON.parse(await resp.text());
        expect(body.error, endpoint).toBe('bootstrap-locked');
        expect(body.initialized, endpoint).toBe(false);
      }

      // 只读端点不受影响（引导卡仍需读取数据）。
      const pools = await context.request.get(
        handle.baseUrl + '/api/gacha/pools',
      );
      expect(pools.status()).toBe(200);

      // 未批准 / 伪造的策略不得解锁服务端闸门。
      writePolicyTo(handle, { ...VALID_POLICY, approved_by_user: false });
      const forged = await context.request.post(
        handle.baseUrl + '/api/gacha/draw',
        { data: {} },
      );
      expect(forged.status()).toBe(423);
      removePolicyFrom(handle);

      // 只有合法且已批准的策略才放行（%TEMP% 合成目录，不碰真实数据）。
      writePolicyTo(handle, VALID_POLICY);
      const allowed = await context.request.post(
        handle.baseUrl + '/api/gacha/draw',
        { data: { energy: 'medium' } },
      );
      expect(allowed.status()).toBe(200);
    } finally {
      await handle.stop();
    }
  });

  // ==========================================================================
  // MS-START G-START-3：批准并发布之后的「重新检测配置」入口
  // (LT_MS_START_POLICY_RECHECK_UX_20261023_V)
  //
  // 产品语义：这个按钮**只做只读复查**。点击 = 重新 GET
  // /api/agent-policy/status。网页既不代替用户批准，也不代替受控
  // Publisher 发布，更不能因此跳过引导进入抽卡。
  //
  // 注意：下面的 writePolicy() 写入的是 %TEMP% 合成 Fixture 目录，
  // 它只是"合法的已批准策略长什么样"的**合成输入**，不代表也不构成
  // 任何真实用户批准，也绝不触碰生产 data/agent-policy/latest.json。
  // ==========================================================================

  test('J) 重新检测配置：未发布时仍停留引导、给出可见提醒，抽卡写请求继续被阻断', async ({
    page,
    context,
  }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    // 只允许 status 的**读取**，任何写请求都不该从按钮发出。
    const writesFromButton = [];
    page.on('request', (req) => {
      if (req.method() === 'GET') return;
      writesFromButton.push(`${req.method()} ${new URL(req.url()).pathname}`);
    });

    await gotoBoot(page, baseUrl);
    await page.click('#salBootstrapStartBtn');
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();

    const promptBefore = await page.locator('#salBootstrapPromptText').inputValue();
    const timerBefore = await page.locator('#salBootstrapTimer').innerText();

    // 入口必须显眼、可键盘聚焦，且文案不暗示"点击即批准"。
    const recheckBtn = page.locator('#salBootstrapRecheckBtn');
    await expect(recheckBtn).toBeVisible();
    const recheckLabel = await recheckBtn.innerText();
    expect(recheckLabel).toContain('检查配置');
    expect(recheckLabel).not.toMatch(/^批准/);          // 不得暗示点一下即批准
    expect(recheckLabel).not.toMatch(/我已批准|已为你发布|立即发布/);
    expect(await recheckBtn.getAttribute('aria-label')).toContain('不会批准');
    await expect(recheckBtn).toBeEnabled();
    // 键盘可用：Tab 可达且为原生 button（可被 Enter/Space 触发）。
    expect(await recheckBtn.evaluate((el) => el.tagName)).toBe('BUTTON');
    await recheckBtn.focus();
    expect(
      await page.evaluate(() => document.activeElement.id),
    ).toBe('salBootstrapRecheckBtn');
    await recheckBtn.press('Enter');

    // 尚未发布 → 仍停留引导，显示简明可见提醒。
    await expect(page.locator('#salBootstrapRecheckNote')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('#salBootstrapRecheckNote')).toContainText(
      '尚未检测到已生效配置',
    );
    await expect(page.locator('#salBootstrapRecheckNote')).toContainText('批准');
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();
    await expect(page.locator('#gachaBtn')).toBeHidden();

    // 阶段、已填写内容与计时都不得被清空。
    const guardState = await page.evaluate(() => window.SAL_BOOTSTRAP.state());
    expect(guardState.stage).toBe('prompt');
    expect(guardState.locked).toBe(true);
    expect(guardState.initialized).toBe(false);
    expect(await page.locator('#salBootstrapPromptText').inputValue()).toBe(promptBefore);
    expect(await page.locator('#salBootstrapTimer').innerText()).toBe(timerBefore);
    await expect(page.locator('#salBootstrapTimer')).toHaveText(/^2[45]:\d{2}$/);

    // 按钮本身不得发出任何写请求（不得伪造批准 / 自动发布）。
    expect(writesFromButton).toEqual([]);

    // 抽卡写调用依然被前端守卫阻断。
    const result = await page.evaluate(async () => {
      try {
        await fetch('/api/gacha/draw', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ energy: 'medium' }),
        });
        return 'sent';
      } catch (e) {
        return 'blocked';
      }
    });
    expect(result).toBe('blocked');
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible();

    expect(pageErrors).toEqual([]);
  });

  test('K) 重新检测配置：合法已批准策略生效后无需刷新即解锁并可用正常抽卡', async ({
    page,
    context,
  }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await gotoBoot(page, baseUrl);
    await page.click('#salBootstrapStartBtn');
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();

    // 合成 Fixture 人工写入"合法的已批准策略"：只是模拟用户已在管家中
    // 批准并通过受控 Publisher 发布完毕，不刷新页面。
    writePolicy(VALID_POLICY);

    // **不刷新**，直接点击「检查配置」。
    await page.click('#salBootstrapRecheckBtn');

    // 覆盖层被移除，回到正式页面。
    await expect(page.locator('#salBootstrapOverlay')).toHaveCount(0, { timeout: 15000 });
    await expect(page.locator('#gachaBtn')).toBeVisible();
    await expect(page.locator('#salBootstrapRecheckBtn')).toHaveCount(0);

    const guardState = await page.evaluate(() => window.SAL_BOOTSTRAP.state());
    expect(guardState.locked).toBe(false);
    expect(guardState.initialized).toBe(true);

    // 正常抽卡写请求恢复可用（真实 200）。
    const drawn = await page.evaluate(async () => {
      const r = await fetch('/api/gacha/draw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ energy: 'medium' }),
      });
      return { status: r.status, ok: r.ok };
    });
    expect(drawn.status).toBe(200);
    expect(drawn.ok).toBe(true);

    // 引导阶段的 localStorage 状态在解锁时被清掉。
    const stored = await page.evaluate(() => window.localStorage.getItem('sal.bootstrap.v1'));
    expect(stored).toBe(null);

    removePolicy();
    expect(pageErrors).toEqual([]);
  });

  test('L) 重新检测配置：status API 故障时保持锁定且保留原重新检测', async ({
    page,
    context,
  }) => {
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    // 先正常进入提示词阶段，再让 status 端点在按钮点击时故障。
    await gotoBoot(page, baseUrl);
    await page.click('#salBootstrapStartBtn');
    await expect(page.locator('#salBootstrapPromptText')).toBeVisible();

    await context.route('**/api/agent-policy/status', (route) => route.abort());

    await page.click('#salBootstrapRecheckBtn');

    // Fail closed：仍锁定，不得误入抽卡；原有 fail closed 出口仍在。
    await expect(page.locator('#salBootstrapOverlay')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('#gachaBtn')).toBeHidden();
    await expect(page.locator('#salBootstrapErrorText')).toBeVisible();
    await expect(page.locator('#salBootstrapErrorText')).not.toHaveText('');
    await expect(page.locator('#salBootstrapRetryBtn')).toBeVisible();

    const guardState = await page.evaluate(() => window.SAL_BOOTSTRAP.state());
    expect(guardState.locked).toBe(true);
    expect(guardState.initialized).toBe(false);

    // 恢复网络后，原「重新检测状态」仍可用并能正常解锁（写合法策略模拟）。
    await context.unroute('**/api/agent-policy/status');
    writePolicy(VALID_POLICY);
    await page.click('#salBootstrapRetryBtn');
    await expect(page.locator('#salBootstrapOverlay')).toHaveCount(0, { timeout: 15000 });
    await expect(page.locator('#gachaBtn')).toBeVisible();

    removePolicy();
  });
});
