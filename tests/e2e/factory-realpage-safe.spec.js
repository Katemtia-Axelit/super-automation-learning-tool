/**
 * tests/e2e/factory-realpage-safe.spec.js
 *
 * M1.4A: Real Factory + real frontend page smoke. 100% TEMP synthetic root.
 *
 * Contract (LT_M1_4A_FACTORY_FULLPAGE_BOOT_20261011):
 *   - page.goto('http://127.0.0.1:<random>/') on the live synthetic Factory
 *   - DO NOT use page.setContent for boot smoke
 *   - DO NOT mock /api/gacha/multi-draw for the real-multi-draw case
 *   - DO mock ONLY external-network/fonts/optional AI endpoints for safety
 *   - DO use real /api/tasks and /api/gacha/statistics
 *
 * Server fixture: tests/e2e/factory-sandbox-server.py
 *   - copies server/*.py, run_app.py, src/index.html, static/app.js,
 *     static/app.entry.js, static/core/**, static/shared/**,
 *     static/modules/**, static/vendor/** into a temp root under %TEMP%
 *   - seeds synthetic SQLite + 4 extra unlocked tasks
 *   - binds 127.0.0.1:<random>; never 5000; never public
 *   - terminates child and removes temp on teardown
 *
 * Cases:
 *   1. boot-smoke: real `/` HTML + app.js load + /api/tasks + /statistics
 *   2. multi-draw: click real button, capture real /api/gacha/multi-draw,
 *      confirm >=2 native <button> cards, exactly one aria-pressed="true"
 *   3. pool-size sanity: /api/gacha/pools/detail shows the augmented tasks
 */

const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const E2E_DIR = __dirname;
const FIXTURE_PATH = path.join(E2E_DIR, 'factory-sandbox-server.py');
const ISOLATED_CONFIG = path.join(E2E_DIR, 'playwright.factory-safe.config.js');

if (!fs.existsSync(FIXTURE_PATH)) {
  throw new Error('factory-sandbox-server.py missing at ' + FIXTURE_PATH);
}

/**
 * Boot the synthetic Factory via a Python subprocess and yield the base URL.
 *
 * Uses the Python module form ``python -B -m`` so it runs the fixture as
 * a __main__ script. We expose a tiny CLI in the fixture (see bottom).
 */
function startFactory() {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  // Probe for the project venv first (matches existing test conventions).
  const venvPy = path.join(
    path.resolve(E2E_DIR, '..', '..'),
    '.venv',
    'Scripts',
    'python.exe',
  );
  const candidate = fs.existsSync(venvPy) ? venvPy : py;

  const child = spawn(
    candidate,
    ['-B', FIXTURE_PATH, '--print-url'],
    {
      cwd: E2E_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    },
  );

  let stdoutAll = '';
  let stderrAll = '';
  child.stdout.on('data', (chunk) => { stdoutAll += chunk.toString(); });
  child.stderr.on('data', (chunk) => { stderrAll += chunk.toString(); });

  return new Promise((resolve, reject) => {
    let resolved = false;
    const onExit = (code) => {
      if (resolved) return;
      resolved = true;
      reject(new Error(
        `factory fixture exited early rc=${code}\nstdout:\n${stdoutAll}\nstderr:\n${stderrAll}`
      ));
    };
    child.once('exit', onExit);
    child.once('error', (err) => {
      if (resolved) return;
      resolved = true;
      reject(err);
    });

    // The fixture prints TMPDIR then CHILDPID then URL on separate lines,
// then idles. We capture the temp root + the run_app.py grandchild PID
// so we can guarantee cleanup: TerminateProcess on the python child
// does NOT propagate to its grandchild, so the grandchild keeps the
// temp dir open as CWD. Killing it explicitly is required.
const timer = setInterval(() => {
      if (resolved) return;
      const urlMatch = stdoutAll.match(/^URL:(http:\/\/127\.0\.0\.1:\d+)\s*$/m);
      const tmpMatch = stdoutAll.match(/^TMPDIR:(.+)$/m);
      const pidMatch = stdoutAll.match(/^CHILDPID:(\d+)\s*$/m);
      if (urlMatch) {
        resolved = true;
        clearInterval(timer);
        child.removeListener('exit', onExit);
        const tmpdir = tmpMatch ? tmpMatch[1].trim() : null;
        const grandchildPid = pidMatch ? parseInt(pidMatch[1], 10) : null;
        resolve({
          baseUrl: urlMatch[1],
          tmpdir: tmpdir,
          grandchildPid: grandchildPid,
          stop: () => new Promise((stopResolve) => {
            const purgeTmp = () => {
              if (!tmpdir) return;
              const tryRemove = (attempt) => {
                if (attempt > 12) return;
                try {
                  fs.rmSync(tmpdir, {
                    recursive: true,
                    force: true,
                    maxRetries: 5,
                    retryDelay: 200,
                  });
                } catch (err) {
                  // EBUSY/EPERM = the grandchild run_app.py is still
                  // alive and holds the temp dir as CWD. Keep retrying.
                  setTimeout(() => tryRemove(attempt + 1), 300);
                }
              };
              tryRemove(0);
            };
            const killGrandchild = () => {
              if (!grandchildPid) return;
              try {
                // On Windows, process.kill(pid) invokes TerminateProcess
                // and ignores the signal argument. The grandchild
                // release of CWD happens shortly after.
                process.kill(grandchildPid, 'SIGKILL');
              } catch (_e) { /* noop */ }
            };
            // Kill grandchild first, then parent, then sweep.
            killGrandchild();
            setTimeout(() => {
              try {
                child.kill();
              } catch (_e) { /* noop */ }
            }, 200);
            const onChildExit = () => {
              setTimeout(purgeTmp, 250);
              setTimeout(() => {
                try {
                  fs.rmSync(tmpdir, { recursive: true, force: true });
                } catch (_e) { /* noop */ }
                stopResolve();
              }, 4000);
            };
            child.once('exit', onChildExit);
            setTimeout(() => {
              try {
                fs.rmSync(tmpdir, { recursive: true, force: true });
              } catch (_e) { /* noop */ }
              stopResolve();
            }, 8000);
          }),
        });
      }
    }, 100);
    setTimeout(() => {
      if (resolved) return;
      resolved = true;
      clearInterval(timer);
      child.kill();
      reject(new Error(
        `factory fixture did not print URL within 30s\nstdout:\n${stdoutAll}\nstderr:\n${stderrAll}`
      ));
    }, 30000);
  });
}

let factoryHandle = null;

// AR03-G05: 合成提示词样例（仅在 synthetic Factory 的临时 root 内播种）。
// 绝不触碰真实用户的 src/notes/prompts/**、已批准策略或 Vault。
const SYNTHETIC_PROMPTS = [
  {
    name: 'synthetic-prompt-alpha.md',
    content: 'synthetic alpha line 1\nsynthetic alpha line 2\n',
  },
  {
    name: 'synthetic-prompt-beta.md',
    content: 'synthetic beta line 1\nsynthetic beta line 2\n',
  },
];

function seedSyntheticPrompts(tmpdir) {
  // backend_api.PROMPTS_DIR = <project_root>/src/notes/prompts，而 synthetic
  // root 的 project_root 就是 <tmpdir>/root。
  const promptsDir = path.join(tmpdir, 'root', 'src', 'notes', 'prompts');
  fs.mkdirSync(promptsDir, { recursive: true });
  for (const p of SYNTHETIC_PROMPTS) {
    fs.writeFileSync(path.join(promptsDir, p.name), p.content, 'utf8');
  }
  return promptsDir;
}

// AR03-G06: 合成知识库样例（仅在 synthetic Factory 的临时 root 内播种）。
//
// 绝不触碰真实用户的 src/notes/**、真实 Obsidian Vault、真实数据库或配置。
//
// 合成 root 的 config/config.json 里 obsidian.notes_directory = "vault"，
// 且 Factory 的 _notes_dir 是相对路径 "vault"，run_app.py 子进程的工作目录
// 就是 <tmpdir>/root，因此 vault/ 解析到 <tmpdir>/root/vault —— 绝不会
// 落到真实项目的 src/notes/vault。
//
// 布局需同时满足后端两个真实读取路径：
//   - GET /api/knowledge/categories → note_index_repo 统计
//     <vault>/知识点/<科目>/*.md（固定 5 个科目名）
//   - GET /api/knowledge/notes      → knowledge.list_notes 只遍历
//     <vault>/<科目>/*.md（**一层深**，目录名即 category）
//   - GET /api/knowledge/note-content/<path> → <vault>/<path>
const SYNTHETIC_KNOWLEDGE = {
  高等数学: [
    {
      name: 'synthetic-alpha.md',
      content: '# 合成高数笔记甲\n\n## 合成极限小节\n\n- 合成条目甲一\n- 合成条目甲二\n\n**合成加粗甲**\n',
    },
    {
      name: 'synthetic-beta.md',
      content: '# 合成高数笔记乙\n\n## 合成导数小节\n\n合成导数正文标记-9f3a2b7c\n',
    },
  ],
  大学物理: [
    {
      name: 'synthetic-gamma.md',
      content: '# 合成物理笔记丙\n\n## 合成力学小节\n\n合成力学正文标记-3c8d1e5a\n',
    },
  ],
};

function seedSyntheticKnowledgeNotes(tmpdir) {
  const vaultDir = path.join(tmpdir, 'root', 'vault');
  for (const [subject, notes] of Object.entries(SYNTHETIC_KNOWLEDGE)) {
    // 分类计数路径：<vault>/知识点/<科目>/*.md
    const countDir = path.join(vaultDir, '知识点', subject);
    fs.mkdirSync(countDir, { recursive: true });
    // 笔记列表路径：<vault>/<科目>/*.md
    const noteDir = path.join(vaultDir, subject);
    fs.mkdirSync(noteDir, { recursive: true });
    for (const n of notes) {
      fs.writeFileSync(path.join(countDir, n.name), n.content, 'utf8');
      fs.writeFileSync(path.join(noteDir, n.name), n.content, 'utf8');
    }
  }
  return vaultDir;
}

// AR03-G07: 合成 Agent 只读浏览样例（仅在 synthetic Factory 的临时 root 内播种）。
//
// 绝不触碰真实用户的 src/notes/**、真实 Obsidian Vault、真实数据库或配置。
//
// 合成 root 的 layout：
//   - src/notes/未分类/  → 后端 RAW_DIR（GET /api/agent/files/raw）
//   - src/notes/prompts/ → 后端 PROMPTS_DIR（GET /api/agent/agents/<id>/prompt）
//   - vault/             → 后端 NOTES_DIR（GET /api/agent/files/vault）
function seedSyntheticAgentReadonly(tmpdir) {
  const root = path.join(tmpdir, 'root');
  // 1) Raw（未分类）目录：一个合成 txt 文件（真实 raw 列表 + 正文用）。
  const rawDir = path.join(root, 'src', 'notes', '未分类');
  fs.mkdirSync(rawDir, { recursive: true });
  fs.writeFileSync(
    path.join(rawDir, 'synthetic-agent-raw.txt'),
    '合成原始转写正文标记-5c1d9a4e\n',
    'utf8',
  );
  // 2) Agent 提示词：AGENT_CONFIG 里 note_organizer 的 prompt_file 是
  //    '笔记整理师'（后端解析 <PROMPTS_DIR>/笔记整理师.md）。播种它，
  //    让真实 /api/agent/agents/<id>/prompt 走"文件存在"分支。
  const promptsDir = path.join(root, 'src', 'notes', 'prompts');
  fs.mkdirSync(promptsDir, { recursive: true });
  fs.writeFileSync(
    path.join(promptsDir, '笔记整理师.md'),
    '# 合成笔记整理师提示词\n\n合成提示词正文标记-7b2e4f10\n',
    'utf8',
  );
  // 3) Vault 根目录下的一个合成 Markdown 文件（真实 vault 列表 + 正文用）。
  const vaultDir = path.join(root, 'vault');
  fs.mkdirSync(vaultDir, { recursive: true });
  fs.writeFileSync(
    path.join(vaultDir, 'synthetic-vault-root.md'),
    '# 合成 Vault 根笔记\n\n合成 Vault 正文标记-8a3f6d52\n',
    'utf8',
  );
  return rawDir;
}

test.beforeAll(async () => {
  factoryHandle = await startFactory();
  if (!factoryHandle || !factoryHandle.tmpdir) {
    throw new Error('factory tmpdir undetermined; refuse to write policy outside synthetic TEMP');
  }
  const policyDir = path.join(factoryHandle.tmpdir, 'root', 'data', 'agent-policy');
  fs.mkdirSync(policyDir, { recursive: true });
  fs.writeFileSync(
    path.join(policyDir, 'latest.json'),
    JSON.stringify({ schema_version: 1, version: '2026-10-21.1', approved_by_user: true, approved_at: '2026-10-21T12:00:00Z' }, null, 2),
    'utf8',
  );
  // AR03-G05: 在 synthetic root 内播种合成提示词样例（真实 prompts API 用）。
  seedSyntheticPrompts(factoryHandle.tmpdir);
  // AR03-G06: 在 synthetic root 的 vault/ 内播种合成知识库笔记
  // （真实 /api/knowledge/categories + /notes + /note-content 用）。
  seedSyntheticKnowledgeNotes(factoryHandle.tmpdir);
  // AR03-G07: 在 synthetic root 内播种合成 Raw txt / Agent 提示词 / Vault 根笔记
  // （真实 /api/agent/agents + /files/raw + /files/vault 用）。
  seedSyntheticAgentReadonly(factoryHandle.tmpdir);
});

test.afterAll(async () => {
  if (factoryHandle) {
    await factoryHandle.stop();
    factoryHandle = null;
  }
});

/**
 * Block external network / fonts / optional AI endpoints for safety.
 * Everything inside 127.0.0.1 (our own synthetic Factory) is allowed.
 */
async function installSafetyRoutes(context, baseUrl) {
  await context.route('**/*', async (route) => {
    const url = route.request().url();
    // Allow our synthetic server and its static assets.
    if (url.startsWith(baseUrl + '/')) {
      return route.continue();
    }
    // Allow data: and blob: (inline UI fragments, no network).
    if (url.startsWith('data:') || url.startsWith('blob:')) {
      return route.continue();
    }
    // Block everything else (external fonts, AI APIs, etc).
    return route.abort();
  });
}

test.describe('M1.4A real Factory full-page boot', () => {
  test('A) real / HTML + app.js boot, smoke API', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    const consoleErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    const appJsResponses = [];
    page.on('response', (res) => {
      if (res.url().endsWith('/static/app.js') ||
          res.url().includes('/static/app.js?')) {
        appJsResponses.push({ status: res.status(), url: res.url() });
      }
    });

    // /api/tasks is fired by the top-level loadTasks() call in app.js on
    // boot. Register the waiter BEFORE goto so we don't miss the response.
    const tasksApi = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/tasks' ||
              r.url().startsWith(baseUrl + '/api/tasks?')) &&
             r.request().method() === 'GET',
      { timeout: 15000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });

    // Title is served from src/index.html (real Factory legacy_compat).
    await expect(page).toHaveTitle(/学习/);

    // Synthetic approved policy unlocks the real bootstrap gate.
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });
    const bootState = await page.evaluate(() => window.SAL_BOOTSTRAP && window.SAL_BOOTSTRAP.state());
    expect(bootState.locked).toBe(false);
    await expect(page.locator('#gachaMultiBtn')).toBeVisible();
    await expect(page.locator('.nav-btn[data-page="gacha"]')).toBeVisible();

    // Required DOM hooks must be present.
    await expect(page.locator('#gachaBtn')).toHaveCount(1);
    await expect(page.locator('#gachaMultiBtn')).toHaveCount(1);
    await expect(page.locator('#gachaResult')).toHaveCount(1);
    await expect(page.locator('#timerDock')).toHaveCount(1);
    await expect(page.locator('#gachaTimeInput')).toHaveCount(1);
    await expect(page.locator('#gachaMultiCount')).toHaveCount(1);
    await expect(page.locator('.nav-btn[data-page="gacha"]')).toHaveCount(1);

    // Real /static/app.js must have loaded with 200.
    expect(appJsResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of appJsResponses) {
      expect(r.status).toBe(200);
    }

    // /api/tasks fires from top-level loadTasks() in app.js on boot.
    const tasksResp = await tasksApi;
    expect(tasksResp.status()).toBe(200);
    const tasksBody = await tasksResp.json();
    const tasksArr = Array.isArray(tasksBody) ? tasksBody : (tasksBody.tasks || []);
    expect(tasksArr.length).toBeGreaterThanOrEqual(3);

    // /api/gacha/statistics is fired when the gacha tab is active. The
    // default page is gacha, but to be deterministic we re-click the
    // gacha nav-btn and wait for the response.
    const statsApi = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/gacha/statistics' ||
              r.url().startsWith(baseUrl + '/api/gacha/statistics?')) &&
             r.request().method() === 'GET',
      { timeout: 15000 },
    );
    await page.click('.nav-btn[data-page="gacha"]');
    const statsResp = await statsApi;
    expect(statsResp.status()).toBe(200);
    const statsBody = await statsResp.json();
    expect(statsBody).toHaveProperty('total_draws');

    // AR03-G01: prove the new ESM owner really executes via classic facade.
    const expectedDraws = String(statsBody.total_draws || 0);
    await page.evaluate(() => { document.getElementById('statDraws').textContent = '__AR03_SENTINEL__'; });
    await page.evaluate(() => window.refreshGachaStats());
    await expect(page.locator('#statDraws')).toHaveText(expectedDraws, { timeout: 15000 });
    const pileResp = await page.request.get(baseUrl + '/api/discard-pile');
    expect(pileResp.status()).toBe(200);
    const pileBody = await pileResp.json();
    const pileItems = Array.isArray(pileBody) ? pileBody : (pileBody.items || []);
    await page.evaluate(() => window.updateDiscardPileVisual());
    await page.waitForFunction(
      (n) => document.querySelectorAll('#discardPileStack .discard-pile-visual-card').length === Math.min(n, 5),
      pileItems.length,
      { timeout: 15000 },
    );
    const emptyDisplay = await page.evaluate(() => document.getElementById('discardPileEmpty').style.display);
    expect(emptyDisplay).toBe(pileItems.length > 0 ? 'none' : 'flex');

    // No uncaught page errors. (console.error is allowed for vendor noise.)
    expect(pageErrors).toEqual([]);
    // Sanity: at most 1 console error and it must NOT be a JS exception.
    for (const ce of consoleErrors) {
      expect(ce).not.toMatch(/Uncaught|TypeError|ReferenceError/);
    }
  });


  test('B) real multi-draw via /api/gacha/multi-draw with native buttons', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // Capture the multi-draw request for assertion.
    const multiDrawRequest = page.waitForRequest(
      (req) => req.url() === baseUrl + '/api/gacha/multi-draw' &&
                req.method() === 'POST',
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');
    // Make sure the gacha page is active and the multi input has a budget
    // large enough to give us multiple distinct cards.
    const timeInput = page.locator('#gachaTimeInput');
    await timeInput.fill('60');
    await page.click('#gachaMultiBtn');

    const req = await multiDrawRequest;
    expect(req.method()).toBe('POST');
    const reqBody = JSON.parse(req.postData() || '{}');
    expect(typeof reqBody.available_time).toBe('number');
    expect(reqBody.available_time).toBeGreaterThanOrEqual(1);

    // Wait for multi-result cards to render.
    await page.waitForSelector('.gacha-multi-item', { timeout: 10000 });

    const items = page.locator('.gacha-multi-item');
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // Verify they are real native <button> elements.
    const tagNames = await items.evaluateAll(
      (els) => els.map((el) => el.tagName.toLowerCase()),
    );
    for (const t of tagNames) {
      expect(t).toBe('button');
    }

    // None pressed initially (drawGachaMulti does not auto-select).
    const initialPressed = await items.evaluateAll(
      (els) => els.map((el) => el.getAttribute('aria-pressed')),
    );
    expect(initialPressed.every((v) => v === 'false')).toBe(true);

    // Activate the first card by clicking it.
    await items.nth(0).click();
    await page.waitForFunction(
      () => document.querySelectorAll('.gacha-multi-item[aria-pressed="true"]').length === 1,
      null,
      { timeout: 5000 },
    );
    const afterPressed = await items.evaluateAll(
      (els) => els.map((el) => el.getAttribute('aria-pressed')),
    );
    const trueCount = afterPressed.filter((v) => v === 'true').length;
    expect(trueCount).toBe(1);

    // Sanity: the card face contains a task title.
    const title = await items.nth(0).locator('.gacha-multi-item-title').innerText();
    expect(title.trim().length).toBeGreaterThan(0);

    // No uncaught page errors during the real multi-draw lifecycle.
    expect(pageErrors).toEqual([]);
  });


  test('C) pool-size sanity: /api/gacha/pools/detail shows augmented tasks', async ({ request }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    const resp = await request.get(baseUrl + '/api/gacha/pools/detail');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    // The augmented tasks have estimated_time 8/10/12/14 -> fragment pool
    // (per _TIME_RANGES: fragment = 0..15).
    const fragmentTasks = (body.fragment && body.fragment.tasks) || [];
    expect(fragmentTasks.length).toBeGreaterThanOrEqual(4);
    const names = fragmentTasks.map((t) => t.name);
    expect(names).toEqual(expect.arrayContaining([
      'synthetic-multi-alpha',
      'synthetic-multi-beta',
      'synthetic-multi-gamma',
      'synthetic-multi-delta',
    ]));
  });

  test('D) real timer start/pause/resume/complete full flow', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // AR03-G04: real ESM owner for Dock / task-page timer presentation.
    // Register before goto so the boot-time facade import is not missed.
    const timerEsmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/timer/presentation.js')) {
        timerEsmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const timerEsmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/timer/presentation.js'),
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');

    // ESM owner must load successfully (initTimerDock → updateTimerDockDisplay facade).
    const timerEsmResp = await timerEsmResponseWait;
    expect(timerEsmResp.status()).toBe(200);
    expect(timerEsmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of timerEsmResponses) {
      expect(r.status).toBe(200);
    }
    const timerEsmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/timer/presentation.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(timerEsmResourceNames)).toBe(true);
    expect(timerEsmResourceNames.some(
      (n) => n.includes('/static/modules/timer/presentation.js'),
    )).toBe(true);

    // Step 1: real multi-draw to populate >=2 candidate cards.
    const multiDrawReq = page.waitForRequest(
      (req) => req.url() === baseUrl + '/api/gacha/multi-draw' &&
                req.method() === 'POST',
    );
    await page.locator('#gachaTimeInput').fill('60');
    await page.click('#gachaMultiBtn');
    await multiDrawReq;
    await page.waitForSelector('.gacha-multi-item', { timeout: 10000 });
    const items = page.locator('.gacha-multi-item');
    const itemCount = await items.count();
    expect(itemCount).toBeGreaterThanOrEqual(2);

    // Step 2: click the first multi card → real drawn card appears.
    await items.nth(0).click();
    await page.waitForFunction(() => {
      const sel = document.querySelector('.gacha-multi-item[aria-pressed="true"]');
      const drawn = document.querySelector('.task-card.drawn-card');
      return !!sel && !!drawn;
    }, null, { timeout: 5000 });
    const taskIdAttr = await page.locator('.task-card.drawn-card').first()
      .getAttribute('data-task-id');
    expect(taskIdAttr).not.toBeNull();
    const expectedTaskId = Number(taskIdAttr);
    expect(Number.isFinite(expectedTaskId) && expectedTaskId > 0).toBe(true);

    // Wait until the drawn card's right panel exposes the "开始任务" button.
    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick^="startTask"], button[onclick*="startTask("]') !== null;
    }, expectedTaskId, { timeout: 5000 });

    // Step 3: click the real "开始任务" button → real /api/timer/start.
    const startApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/start' ||
               r.url().startsWith(baseUrl + '/api/timer/start?')) &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      const btn = card.querySelector(
        '.drawn-card-right-panel button[onclick*="startTask("]');
      btn.click();
    }, expectedTaskId);
    const startResp = await startApiResp;
    expect(startResp.status()).toBe(200);
    const startBody = await startResp.json();
    expect(typeof startBody.session_id).toBe('number');
    expect(Number.isFinite(startBody.session_id) && startBody.session_id > 0).toBe(true);
    expect(Number(startBody.task_id)).toBe(expectedTaskId);
    expect(typeof startBody.started_at).toBe('string');
    expect(startBody.planned_minutes).toBeGreaterThanOrEqual(1);

    // Step 4: Dock becomes active (idle hidden, active visible with task name).
    // AR03-G04: assert ESM-owned Dock DOM (time mm:ss + running pause icon).
    await expect(page.locator('#timerDockIdle')).toBeHidden({ timeout: 5000 });
    await expect(page.locator('#timerDockActive')).toBeVisible();
    await expect(page.locator('#timerDockTaskName')).not.toHaveText('');
    await expect(page.locator('#timerDockTime')).toBeVisible();
    await expect(page.locator('#timerDockTime')).toHaveText(/^\d{2}:\d{2}$/);
    await expect(page.locator('#timerDockPauseBtn i.fa-pause')).toHaveCount(1);
    await expect(page.locator('#timerDockPauseBtn')).toHaveAttribute('title', '暂停计时器');

    // Cross-check: GET /api/timer/active reflects the same session, running.
    const activeAfterStart = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterStart.status).toBe(200);
    expect(activeAfterStart.body).not.toBeNull();
    expect(activeAfterStart.body.id).toBe(startBody.session_id);
    expect(activeAfterStart.body.task_id).toBe(expectedTaskId);
    // status field is the source of truth for pause UI:
    expect(activeAfterStart.body.status).toBe('running');
    expect(activeAfterStart.body.is_paused).toBe(false);

    // Step 5: real click on #timerDockPauseBtn → POST /api/timer/pause.
    // Let the running timer accrue real wall-clock seconds first so
    // /api/timer/pause returns a non-zero paused_seconds. The pause
    // path computes `existing_paused_seconds + elapsed_since_started_at`
    // from a live clock on the server, so a sub-second click legitimately
    // returns 0. We are NOT mocking anything — we just give the
    // already-running session real elapsed seconds to record.
    await page.waitForTimeout(1500);
    const pauseApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/pause' ||
               r.url().startsWith(baseUrl + '/api/timer/pause?')) &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.click('#timerDockPauseBtn');
    const pauseResp = await pauseApiResp;
    expect(pauseResp.status()).toBe(200);
    const pauseBody = await pauseResp.json();
    expect(pauseBody.session_id).toBe(startBody.session_id);
    expect(pauseBody.is_paused).toBe(true);
    expect(typeof pauseBody.paused_seconds).toBe('number');
    expect(pauseBody.paused_seconds).toBeGreaterThanOrEqual(1);

    // Active endpoint now reports the same session in 'paused' status.
    const activeAfterPause = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterPause.status).toBe(200);
    expect(activeAfterPause.body.id).toBe(startBody.session_id);
    expect(activeAfterPause.body.status).toBe('paused');
    expect(activeAfterPause.body.is_paused).toBe(true);
    expect(activeAfterPause.body.paused_seconds).toBeGreaterThanOrEqual(1);

    // AR03-G04: Dock pause presentation (play icon) + task-page timer panel.
    await expect(page.locator('#timerDockPauseBtn i.fa-play')).toHaveCount(1, { timeout: 5000 });
    await expect(page.locator('#timerDockPauseBtn')).toHaveAttribute('title', '继续计时器');
    await expect(page.locator('#timerDockTime')).toHaveText(/^\d{2}:\d{2}$/);
    await page.click('.nav-btn[data-page="tasks"]');
    await expect(page.locator('#page-tasks')).toHaveClass(/active/);
    await expect(page.locator('#timerStatusText')).toContainText('已暂停', { timeout: 8000 });
    await expect(page.locator('#timerStatusText')).toHaveClass(/timer-paused/);
    await expect(page.locator('#timerElapsedDisplay')).toHaveText(/^\d{2}:\d{2}$/);
    await expect(page.locator('#timerPauseBtn')).toBeVisible();
    await expect(page.locator('#timerPauseBtn i.fa-play')).toHaveCount(1);
    await expect(page.locator('#timerStartBtn')).toBeHidden();
    await expect(page.locator('#timerStopBtn')).toBeVisible();
    // Return to gacha so subsequent Dock clicks stay in the drawn-card flow.
    await page.click('.nav-btn[data-page="gacha"]');
    await expect(page.locator('#page-gacha')).toHaveClass(/active/);

    // Step 6: click pause button again → POST /api/timer/resume.
    const resumeApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/resume' ||
               r.url().startsWith(baseUrl + '/api/timer/resume?')) &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.click('#timerDockPauseBtn');
    const resumeResp = await resumeApiResp;
    expect(resumeResp.status()).toBe(200);
    const resumeBody = await resumeResp.json();
    expect(resumeBody.session_id).toBe(startBody.session_id);
    expect(resumeBody.is_paused).toBe(false);

    const activeAfterResume = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterResume.body.id).toBe(startBody.session_id);
    expect(activeAfterResume.body.status).toBe('running');
    expect(activeAfterResume.body.is_paused).toBe(false);

    // AR03-G04: Dock resume presentation restores pause icon.
    await expect(page.locator('#timerDockPauseBtn i.fa-pause')).toHaveCount(1, { timeout: 5000 });
    await expect(page.locator('#timerDockPauseBtn')).toHaveAttribute('title', '暂停计时器');
    await expect(page.locator('#timerDockTime')).toHaveText(/^\d{2}:\d{2}$/);

    // Step 7: click the real "确认完成任务" button on the drawn card.
    // confirmComplete first calls /api/timer/complete, then, on success,
    // clears the dock and triggers completeWithFeedback which surfaces
    // feedbackModal. We must capture the request and the request body
    // because we want to assert no duplicate POST after this completes.
    let completeCallCount = 0;
    const completeApiReqs = [];
    const completeApiResps = [];
    page.on('request', (req) => {
      if (req.url() === baseUrl + '/api/timer/complete' &&
          req.method() === 'POST') {
        completeCallCount += 1;
        completeApiReqs.push(req);
      }
    });
    page.on('response', (res) => {
      if (res.url() === baseUrl + '/api/timer/complete') {
        completeApiResps.push(res);
      }
    });

    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick*="confirmComplete("]') !== null;
    }, expectedTaskId, { timeout: 8000 });

    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      const btn = card.querySelector(
        '.drawn-card-right-panel button[onclick*="confirmComplete("]');
      btn.click();
    }, expectedTaskId);

    // Wait until at least one /api/timer/complete response lands.
    await page.waitForFunction(() => {
      // Cross-check via fetch: by the time this resolves, the timer
      // session has been ended server-side.
      return true;
    }, null, { timeout: 100 });
    // Drain: poll until count stable (max 3s).
    const deadline = Date.now() + 3000;
    let lastCount = -1;
    while (Date.now() < deadline) {
      if (completeApiResps.length === lastCount && completeApiResps.length > 0) break;
      lastCount = completeApiResps.length;
      await page.waitForTimeout(150);
    }
    expect(completeApiResps.length).toBeGreaterThanOrEqual(1);
    const firstComplete = completeApiResps[0];
    expect(firstComplete.status()).toBe(200);

    // Step 8: server-side, the session is gone from /api/timer/active.
    const activeAfterComplete = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterComplete.status).toBe(200);
    // No running/paused sessions → endpoint returns null.
    expect(activeAfterComplete.body).toBeNull();

    // AR03-G04: Dock returns to idle after complete (ESM idle presentation).
    await expect(page.locator('#timerDockIdle')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#timerDockActive')).toBeHidden();

    // Step 9: re-click the same "确认完成任务" button must NOT post
    // again. confirmComplete() in app.js guards on
    // `if (timerDockSession && timerDockSession.id)`. After a successful
    // complete, the dock session is nulled, so the second click takes
    // the no-timer-branch and simply calls completeWithFeedback without
    // re-POSTing. This is the user-visible "no accidental double
    // completion" defense; assert it directly.
    const c0 = completeApiResps.length;
    const cardStillDrawn = await page.evaluate((tid) => {
      return !!document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
    }, expectedTaskId);
    // After completeWithFeedback the drawn card often flies to the
    // discard pile. If still present, click again; if not, we trust
    // the dock-null guard already proven by the assertion above.
    if (cardStillDrawn) {
      const hasConfirmBtn = await page.evaluate((tid) => {
        const card = document.querySelector(
          '.task-card.drawn-card[data-task-id="' + tid + '"]');
        if (!card) return false;
        const panel = card.querySelector('.drawn-card-right-panel');
        if (!panel) return false;
        return !!panel.querySelector('button[onclick*="confirmComplete("]');
      }, expectedTaskId);
      if (hasConfirmBtn) {
        await page.evaluate((tid) => {
          const card = document.querySelector(
            '.task-card.drawn-card[data-task-id="' + tid + '"]');
          const btn = card.querySelector(
            '.drawn-card-right-panel button[onclick*="confirmComplete("]');
          btn.click();
        }, expectedTaskId);
        // No new /api/timer/complete request should land within 1s.
        await page.waitForTimeout(1000);
      }
    }
    const c1 = completeApiResps.length;
    // At most ONE /api/timer/complete POST from the user-driven path.
    // completeWithFeedback's downstream /api/tasks/<id>/complete POST
    // is a different endpoint and must not be misread here.
    expect(c1 - c0).toBeLessThanOrEqual(0);

    // Step 10: dismiss any surfaced feedbackModal so the spec does not
    // hang. The user-facing 取消 button triggers cancelFeedback,
    // which transitions to careModal; we then hit Escape to close it.
    const feedbackVisible = await page.evaluate(() => {
      const m = document.getElementById('feedbackModal');
      return m && !m.classList.contains('hidden');
    });
    if (feedbackVisible) {
      await page.evaluate(() => {
        // Click the real 取消 button (real user cancel path).
        const m = document.getElementById('feedbackModal');
        const btns = m.querySelectorAll('button');
        for (const b of btns) {
          if (b.textContent && b.textContent.trim() === '取消') {
            b.click();
            return;
          }
        }
        // Fallback to global cancelFeedback (M1.3D path).
        if (typeof cancelFeedback === 'function') cancelFeedback();
      });
      await page.waitForTimeout(300);
    }
    // If a careModal was opened by the cancel path, close it.
    const careVisible = await page.evaluate(() => {
      const m = document.getElementById('careModal');
      return m && !m.classList.contains('hidden');
    });
    if (careVisible) {
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
    }

    // No uncaught page errors through the full timer lifecycle.
    expect(pageErrors).toEqual([]);
  });

  test('E) real cancel path: feedback modal zero-POST, care modal 休息', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');

    // Step 1: real multi-draw → ≥2 cards.
    const multiDrawReq = page.waitForRequest(
      (req) => req.url() === baseUrl + '/api/gacha/multi-draw' &&
               req.method() === 'POST',
    );
    await page.locator('#gachaTimeInput').fill('60');
    await page.click('#gachaMultiBtn');
    await multiDrawReq;
    await page.waitForSelector('.gacha-multi-item', { timeout: 10000 });
    const items = page.locator('.gacha-multi-item');
    expect(await items.count()).toBeGreaterThanOrEqual(2);

    // Step 2: select first card → drawn card visible.
    await items.nth(0).click();
    await page.waitForFunction(() => {
      const sel = document.querySelector('.gacha-multi-item[aria-pressed="true"]');
      const drawn = document.querySelector('.task-card.drawn-card');
      return !!sel && !!drawn;
    }, null, { timeout: 5000 });
    const taskIdAttr = await page.locator('.task-card.drawn-card').first()
      .getAttribute('data-task-id');
    expect(taskIdAttr).not.toBeNull();
    const expectedTaskId = Number(taskIdAttr);
    expect(Number.isFinite(expectedTaskId) && expectedTaskId > 0).toBe(true);

    // Required DOM hooks must exist (no vacuous skip).
    await expect(page.locator('#feedbackModal')).toHaveCount(1);
    await expect(page.locator('#fbEnergy')).toHaveCount(1);
    await expect(page.locator('#feedbackModal .feedback-emoji button')).toHaveCount(3);
    await expect(page.locator('#careModal')).toHaveCount(1);
    await expect(page.locator('#feedbackModal button[onclick="cancelFeedback()"]')).toHaveCount(1);
    await expect(page.locator('#feedbackModal button[onclick="submitFeedback()"]')).toHaveCount(1);

    // Register feedback POST listener BEFORE we open feedbackModal by
    // completing the task. This is the central contract: if feedback
    // ever fires without explicit user 确认, this listener catches it.
    const feedbackPosts = [];
    page.on('request', (req) => {
      if (req.url() === baseUrl + '/api/tasks/' + expectedTaskId + '/feedback' &&
          req.method() === 'POST') {
        feedbackPosts.push({
          method: req.method(),
          url: req.url(),
          body: req.postData(),
        });
      }
    });

    // Step 3: wait until drawn-card has a startTask button.
    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick*="startTask("]') !== null;
    }, expectedTaskId, { timeout: 5000 });

    // Step 4: click startTask → /api/timer/start.
    const startApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/start' ||
               r.url().startsWith(baseUrl + '/api/timer/start?')) &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      const btn = card.querySelector(
        '.drawn-card-right-panel button[onclick*="startTask("]');
      btn.click();
    }, expectedTaskId);
    const startResp = await startApiResp;
    expect(startResp.status()).toBe(200);

    await expect(page.locator('#timerDockActive')).toBeVisible({ timeout: 5000 });

    // Step 5: real confirmComplete → feedbackModal surfaces.
    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick*="confirmComplete("]') !== null;
    }, expectedTaskId, { timeout: 8000 });

    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      const btn = card.querySelector(
        '.drawn-card-right-panel button[onclick*="confirmComplete("]');
      btn.click();
    }, expectedTaskId);

    // Wait until feedbackModal is visible (cancel path does not POST).
    await page.waitForFunction(() => {
      const m = document.getElementById('feedbackModal');
      return m && !m.classList.contains('hidden');
    }, null, { timeout: 8000 });
    await expect(page.locator('#feedbackModal')).toBeVisible();
    // careModal must NOT be visible yet.
    await expect(page.locator('#careModal')).toBeHidden();

    // Step 6: assert zero feedback POSTs before the user clicks 取消.
    expect(feedbackPosts.length).toBe(0);

    // Step 7: real user click on 取消 → careModal surfaces, still zero POSTs.
    await page.evaluate(() => {
      const m = document.getElementById('feedbackModal');
      const btns = m.querySelectorAll('button');
      for (const b of btns) {
        if (b.textContent && b.textContent.trim() === '取消') {
          b.click();
          return;
        }
      }
      throw new Error('cancel button not found in feedbackModal');
    });

    await page.waitForFunction(() => {
      const c = document.getElementById('careModal');
      return c && !c.classList.contains('hidden');
    }, null, { timeout: 5000 });
    await expect(page.locator('#feedbackModal')).toBeHidden();
    await expect(page.locator('#careModal')).toBeVisible();

    // Still zero POSTs after the cancel transition.
    expect(feedbackPosts.length).toBe(0);

    // Step 8: click 休息一下 (the real third button inside careModal)
    // and verify no new feedback POST fires.
    const restClicked = await page.evaluate(() => {
      const m = document.getElementById('careModal');
      const btns = m.querySelectorAll('button');
      for (const b of btns) {
        const t = (b.textContent || '').replace(/\s+/g, '');
        if (t.indexOf('休息一下') !== -1) {
          b.click();
          return true;
        }
      }
      return false;
    });
    expect(restClicked).toBe(true);

    // Wait for careModal to actually close.
    await page.waitForFunction(() => {
      const c = document.getElementById('careModal');
      return c && c.classList.contains('hidden');
    }, null, { timeout: 5000 });
    await expect(page.locator('#careModal')).toBeHidden();

    // Drain a moment to let any straggling POST fly (it must not).
    await page.waitForTimeout(500);
    expect(feedbackPosts.length).toBe(0);

    expect(pageErrors).toEqual([]);
  });

  test('F) real submit path: user-set energy/mood, exactly one feedback POST, care rest closes', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');

    // Step 1: real multi-draw → ≥2 cards.
    const multiDrawReq = page.waitForRequest(
      (req) => req.url() === baseUrl + '/api/gacha/multi-draw' &&
               req.method() === 'POST',
    );
    await page.locator('#gachaTimeInput').fill('60');
    await page.click('#gachaMultiBtn');
    await multiDrawReq;
    await page.waitForSelector('.gacha-multi-item', { timeout: 10000 });
    const items = page.locator('.gacha-multi-item');
    expect(await items.count()).toBeGreaterThanOrEqual(2);

    // Step 2: select first card.
    await items.nth(0).click();
    await page.waitForFunction(() => {
      const sel = document.querySelector('.gacha-multi-item[aria-pressed="true"]');
      const drawn = document.querySelector('.task-card.drawn-card');
      return !!sel && !!drawn;
    }, null, { timeout: 5000 });
    const taskIdAttr = await page.locator('.task-card.drawn-card').first()
      .getAttribute('data-task-id');
    expect(taskIdAttr).not.toBeNull();
    const expectedTaskId = Number(taskIdAttr);
    expect(Number.isFinite(expectedTaskId) && expectedTaskId > 0).toBe(true);

    // Required DOM hook checks (no vacuous skip).
    await expect(page.locator('#feedbackModal')).toHaveCount(1);
    await expect(page.locator('#fbEnergy')).toHaveCount(1);
    // Inspect the REAL emoji buttons exposed by src/index.html. The
    // shipped UI ships 3 mood buttons (data-mood = 3/2/1). Any other
    // value (e.g. data-mood=4) does not exist in the real DOM, so we
    // must pick from the real legal set. We use data-mood=2 (一般) as
    // a legitimate non-default value distinct from the openFeedback
    // default of 3 (满意). Energy goes to 7, also non-default (default 5).
    const moodButtonCounts = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll(
        '.feedback-emoji button'));
      return btns.map((b) => b.getAttribute('data-mood'));
    });
    expect(moodButtonCounts.length).toBeGreaterThanOrEqual(2);
    expect(moodButtonCounts).toContain('2');
    // Verify the cancel and submit buttons by their onclick handlers,
    // independent of any i18n / whitespace concerns.
    await expect(page.locator('#feedbackModal button[onclick="cancelFeedback()"]')).toHaveCount(1);
    await expect(page.locator('#feedbackModal button[onclick="submitFeedback()"]')).toHaveCount(1);

    // Step 3: startTask → /api/timer/start.
    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick*="startTask("]') !== null;
    }, expectedTaskId, { timeout: 5000 });
    const startApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/start' ||
               r.url().startsWith(baseUrl + '/api/timer/start?')) &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      card.querySelector('.drawn-card-right-panel button[onclick*="startTask("]').click();
    }, expectedTaskId);
    const startResp = await startApiResp;
    expect(startResp.status()).toBe(200);
    await expect(page.locator('#timerDockActive')).toBeVisible({ timeout: 5000 });

    // Step 4: confirmComplete → feedbackModal surfaces.
    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick*="confirmComplete("]') !== null;
    }, expectedTaskId, { timeout: 8000 });
    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      card.querySelector('.drawn-card-right-panel button[onclick*="confirmComplete("]').click();
    }, expectedTaskId);
    await page.waitForFunction(() => {
      const m = document.getElementById('feedbackModal');
      return m && !m.classList.contains('hidden');
    }, null, { timeout: 8000 });
    await expect(page.locator('#feedbackModal')).toBeVisible();
    await expect(page.locator('#careModal')).toBeHidden();

    // Step 5: explicitly set #fbEnergy = 7 (user input) and fire the
    // 'input' event so the existing listener updates #fbEnergyVal.
    await page.evaluate(() => {
      const el = document.getElementById('fbEnergy');
      el.value = '7';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(await page.locator('#fbEnergy').inputValue()).toBe('7');
    expect(await page.locator('#fbEnergyVal').innerText()).toBe('7');

    // Step 6: click the data-mood=2 button via its onclick handler
    // (setMood(2, this)). setMood updates gachaState.feedbackMood AND
    // toggles the .sel class. Click the real button by data-mood=2,
    // the only legal non-default value present in the real DOM.
    await page.click('.feedback-emoji button[data-mood="2"]');
    const moodStateAfter = await page.evaluate(() => {
      const sel = document.querySelector('.feedback-emoji button.sel');
      return {
        selMood: sel ? sel.getAttribute('data-mood') : null,
        gachaStateMood: (typeof window.gachaState !== 'undefined'
          && window.gachaState)
          ? window.gachaState.feedbackMood : null,
      };
    });
    expect(moodStateAfter.selMood).toBe('2');
    expect(moodStateAfter.gachaStateMood).toBe(2);

    // Step 7: register POST listener BEFORE the click.
    const feedbackPosts = [];
    page.on('request', (req) => {
      if (req.url() === baseUrl + '/api/tasks/' + expectedTaskId + '/feedback' &&
          req.method() === 'POST') {
        feedbackPosts.push({
          method: req.method(),
          url: req.url(),
          body: req.postData(),
        });
      }
    });
    // Also wait for the response so we can validate that the success
    // branch closes feedbackModal and opens careModal deterministically.
    const feedbackRespWait = page.waitForResponse(
      (r) => r.url() === baseUrl + '/api/tasks/' + expectedTaskId + '/feedback' &&
             r.request().method() === 'POST',
      { timeout: 8000 },
    );

    // Step 8: click the real 确认 button by its onclick handler. This
    // invokes submitFeedback() which builds body =
    // {energy_after, mood_after} from current DOM/gachaState and POSTs.
    await page.evaluate(() => {
      const m = document.getElementById('feedbackModal');
      const btns = m.querySelectorAll('button');
      for (const b of btns) {
        if (typeof b.onclick === 'function' &&
            b.onclick.toString().indexOf('submitFeedback') !== -1) {
          b.click();
          return;
        }
      }
      throw new Error('submit button not found in feedbackModal');
    });

    const feedbackResp = await feedbackRespWait;
    // Per task contract: if the real Factory feedback backend refuses,
    // keep this RED with honest evidence; do NOT modify the backend or
    // forge success. Capture status + body so future triage knows the
    // shape of the refusal (likely a backend schema gap on
    // task_completion_feedback table rather than a frontend bug).
    const feedbackStatus = feedbackResp.status();
    let feedbackBodyText = '';
    try {
      feedbackBodyText = await feedbackResp.text();
    } catch (_e) { /* swallow */ }
    expect(feedbackStatus, `feedback backend returned ${feedbackStatus} body=${feedbackBodyText.slice(0, 500)}`).toBe(200);

    // Step 9: assert exactly one POST with the user-explicit body 7/2.
    expect(feedbackPosts.length).toBe(1);
    const captured = feedbackPosts[0];
    expect(captured.method).toBe('POST');
    expect(captured.url).toBe(baseUrl + '/api/tasks/' + expectedTaskId + '/feedback');
    const sentBody = JSON.parse(captured.body || '{}');
    expect(sentBody).toEqual({ energy_after: 7, mood_after: 2 });

    // Step 10: after success, feedbackModal closes and careModal opens.
    await page.waitForFunction(() => {
      const f = document.getElementById('feedbackModal');
      const c = document.getElementById('careModal');
      return f && c &&
             f.classList.contains('hidden') &&
             !c.classList.contains('hidden');
    }, null, { timeout: 5000 });
    await expect(page.locator('#feedbackModal')).toBeHidden();
    await expect(page.locator('#careModal')).toBeVisible();

    // Step 11: click 休息一下 → careModal closes, no additional POST.
    const restClicked = await page.evaluate(() => {
      const m = document.getElementById('careModal');
      const btns = m.querySelectorAll('button');
      for (const b of btns) {
        const t = (b.textContent || '').replace(/\s+/g, '');
        if (t.indexOf('休息一下') !== -1) {
          b.click();
          return true;
        }
      }
      return false;
    });
    expect(restClicked).toBe(true);

    await page.waitForFunction(() => {
      const c = document.getElementById('careModal');
      return c && c.classList.contains('hidden');
    }, null, { timeout: 5000 });
    await expect(page.locator('#careModal')).toBeHidden();

    // Drain for stray POSTs.
    await page.waitForTimeout(500);
    expect(feedbackPosts.length).toBe(1);

    expect(pageErrors).toEqual([]);
  });

  test('G) #timerDockStopBtn: cancel一次 no POST, accept one /api/timer/complete (abandoned, early_finish)', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');

    // Step 1: real multi-draw → ≥2 candidate cards.
    const multiDrawReq = page.waitForRequest(
      (req) => req.url() === baseUrl + '/api/gacha/multi-draw' &&
               req.method() === 'POST',
    );
    await page.locator('#gachaTimeInput').fill('60');
    await page.click('#gachaMultiBtn');
    await multiDrawReq;
    await page.waitForSelector('.gacha-multi-item', { timeout: 10000 });
    const items = page.locator('.gacha-multi-item');
    expect(await items.count()).toBeGreaterThanOrEqual(2);

    // Step 2: select first card → drawn card visible.
    await items.nth(0).click();
    await page.waitForFunction(() => {
      const sel = document.querySelector('.gacha-multi-item[aria-pressed="true"]');
      const drawn = document.querySelector('.task-card.drawn-card');
      return !!sel && !!drawn;
    }, null, { timeout: 5000 });
    const taskIdAttr = await page.locator('.task-card.drawn-card').first()
      .getAttribute('data-task-id');
    expect(taskIdAttr).not.toBeNull();
    const expectedTaskId = Number(taskIdAttr);
    expect(Number.isFinite(expectedTaskId) && expectedTaskId > 0).toBe(true);

    // Required DOM hooks must exist (no vacuous skip).
    await expect(page.locator('#timerDockStopBtn')).toHaveCount(1);

    // Step 3: register ALL network listeners BEFORE the first click so
    // we cannot miss a stray POST fired from a synchronous code path.
    const completePosts = [];
    const completeResps = [];
    const taskCompletePosts = [];
    const feedbackPosts = [];
    const filter = (url) => url.startsWith(baseUrl + '/api');
    page.on('request', (req) => {
      if (!filter(req.url())) return;
      const u = req.url();
      const m = req.method();
      if (u === baseUrl + '/api/timer/complete' && m === 'POST') {
        completePosts.push({ url: u, body: req.postData() });
      } else if (u === baseUrl + '/api/tasks/' + expectedTaskId + '/complete' && m === 'POST') {
        taskCompletePosts.push({ url: u, body: req.postData() });
      } else if (u === baseUrl + '/api/tasks/' + expectedTaskId + '/feedback' && m === 'POST') {
        feedbackPosts.push({ url: u, body: req.postData() });
      }
    });
    page.on('response', (res) => {
      if (res.url() === baseUrl + '/api/timer/complete') {
        completeResps.push(res);
      }
    });

    // Step 4: click startTask → real /api/timer/start.
    await page.waitForFunction((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      if (!card) return false;
      const panel = card.querySelector('.drawn-card-right-panel');
      if (!panel) return false;
      return panel.querySelector('button[onclick*="startTask("]') !== null;
    }, expectedTaskId, { timeout: 5000 });
    const startApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/start' ||
               r.url().startsWith(baseUrl + '/api/timer/start?')) &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.evaluate((tid) => {
      const card = document.querySelector(
        '.task-card.drawn-card[data-task-id="' + tid + '"]');
      card.querySelector('.drawn-card-right-panel button[onclick*="startTask("]').click();
    }, expectedTaskId);
    const startResp = await startApiResp;
    expect(startResp.status()).toBe(200);
    const startBody = await startResp.json();
    expect(typeof startBody.session_id).toBe('number');
    expect(startBody.session_id).toBeGreaterThan(0);
    expect(Number(startBody.task_id)).toBe(expectedTaskId);

    // Step 5: Dock active, idle hidden. Use the same DOM contract as D.
    await expect(page.locator('#timerDockIdle')).toBeHidden({ timeout: 5000 });
    await expect(page.locator('#timerDockActive')).toBeVisible();
    await expect(page.locator('#timerDockTaskName')).not.toHaveText('');
    await expect(page.locator('#timerDockStopBtn')).toBeVisible();

    // Cross-check: GET /api/timer/active reflects the running session.
    const activeAfterStart = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterStart.status).toBe(200);
    expect(activeAfterStart.body).not.toBeNull();
    expect(activeAfterStart.body.id).toBe(startBody.session_id);
    expect(activeAfterStart.body.task_id).toBe(expectedTaskId);
    expect(activeAfterStart.body.status).toBe('running');

    // Step 6: install the dialog state machine. First dialog → dismiss,
    // second dialog → accept. Anything else must surface as a fail.
    let dialogCount = 0;
    let unexpectedDialogMsg = null;
    const dialogHandler = async (dlg) => {
      dialogCount += 1;
      try {
        if (dialogCount === 1) {
          await dlg.dismiss();
        } else if (dialogCount === 2) {
          await dlg.accept();
        } else {
          unexpectedDialogMsg = dlg.message();
          await dlg.dismiss();
        }
      } catch (_e) { /* swallow; page may already be closing */ }
    };
    page.on('dialog', dialogHandler);

    // Step 7: FIRST click on #timerDockStopBtn — native confirm must
    // be dismissed. Assert no /api/timer/complete POST was issued.
    const completeCountBeforeFirst = completePosts.length;
    await page.click('#timerDockStopBtn');

    // Drain 1.2s so any stray async POST would have time to land.
    await page.waitForTimeout(1200);
    expect(completeCountBeforeFirst).toBe(0);  // precondition still true
    expect(completePosts.length).toBe(0);  // CRITICAL: cancel → no POST
    expect(completeResps.length).toBe(0);
    expect(taskCompletePosts.length).toBe(0);
    expect(feedbackPosts.length).toBe(0);

    // Dialog must have fired exactly once so far.
    expect(dialogCount).toBe(1);

    // Dock must still be active: the active session is preserved.
    await expect(page.locator('#timerDockIdle')).toBeHidden();
    await expect(page.locator('#timerDockActive')).toBeVisible();
    const activeAfterCancel = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterCancel.status).toBe(200);
    expect(activeAfterCancel.body).not.toBeNull();
    expect(activeAfterCancel.body.id).toBe(startBody.session_id);
    expect(activeAfterCancel.body.task_id).toBe(expectedTaskId);
    expect(activeAfterCancel.body.status).toBe('running');

    // Step 8: SECOND click on #timerDockStopBtn — accept the dialog.
    // Wait for the single /api/timer/complete POST + HTTP 200 response.
    const completeRespWait = page.waitForResponse(
      (r) => r.url() === baseUrl + '/api/timer/complete' &&
             r.request().method() === 'POST',
      { timeout: 10000 },
    );
    await page.click('#timerDockStopBtn');
    const completeResp = await completeRespWait;
    expect(completeResp.status()).toBe(200);
    expect(dialogCount).toBe(2);

    // Drain a moment to let request side of the body flush into the
    // listener buffer; stopTimerFromDock then runs loadTasks +
    // refreshGafpaStats which fire GET requests but no extra POSTs.
    await page.waitForTimeout(800);

    // Step 9: EXACTLY ONE POST landed, with the abandoned payload.
    expect(completePosts.length).toBe(1);
    const captured = completePosts[0];
    expect(captured.url).toBe(baseUrl + '/api/timer/complete');
    const sentBody = JSON.parse(captured.body || '{}');
    expect(sentBody.result).toBe('abandoned');
    expect(sentBody.reason).toBe('early_finish');
    expect(Number(sentBody.session_id)).toBe(startBody.session_id);
    expect(typeof sentBody.actual_minutes).toBe('number');
    expect(sentBody.actual_minutes).toBeGreaterThanOrEqual(1);
    expect(sentBody.actual_minutes).toBeLessThanOrEqual(60);

    // And NO other forbidden POSTs.
    expect(completeResps.length).toBeGreaterThanOrEqual(1);
    expect(taskCompletePosts.length).toBe(0);
    expect(feedbackPosts.length).toBe(0);

    // Step 10: /api/timer/active is now null (server cleared the session).
    const activeAfterAbandon = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return { status: r.status, body: await r.json() };
    }, baseUrl);
    expect(activeAfterAbandon.status).toBe(200);
    expect(activeAfterAbandon.body).toBeNull();

    // Step 11: Dock returns to idle, idle visible, active hidden.
    await expect(page.locator('#timerDockIdle')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#timerDockActive')).toBeHidden();

    // Step 12: the interrupted task remains NOT in the discard pile.
    const taskStateAfter = await page.evaluate(async (args) => {
      const r = await fetch(args.base + '/api/tasks/' + args.id, {
        method: 'GET',
      });
      return { status: r.status, body: await r.json() };
    }, { base: baseUrl, id: expectedTaskId });
    expect(taskStateAfter.status).toBe(200);
    expect(Number(taskStateAfter.body.id)).toBe(expectedTaskId);
    expect(taskStateAfter.body.completed).toBe(0);
    expect(taskStateAfter.body.in_discard_pile).toBe(0);

    // Step 13: no unexpected third dialog (e.g. a stray feedbackModal).
    expect(unexpectedDialogMsg).toBeNull();

    // Step 14: final drain so any spurious POST from refreshGafpaStats
    // could land (it must not be a complete POST).
    await page.waitForTimeout(500);
    expect(completePosts.length).toBe(1);
    expect(taskCompletePosts.length).toBe(0);
    expect(feedbackPosts.length).toBe(0);

    // No uncaught page errors through the abandon lifecycle.
    expect(pageErrors).toEqual([]);
  });

  test('I) real prompts panel: ESM owner loaded, list/content/copy/edit/diff/save', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // 剪贴板权限（真实 Chromium）：主路径 navigator.clipboard 需要。
    try {
      await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: baseUrl });
    } catch (_e) { /* noop: 下面还有 execCommand fallback 覆盖 */ }

    // 真实 ESM owner 的资源请求 + 真实 /api/prompts（不 mock）。
    // 两者都在**进入设置页时**才首次发生（模块 import 由 classic facade 触发），
    // 因此 waiter 必须在点击导航**之前**注册，否则会漏掉。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/prompts/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/prompts/index.js'),
      { timeout: 20000 },
    );
    const promptsApi = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/prompts' ||
              r.url().startsWith(baseUrl + '/api/prompts?')) &&
             r.request().method() === 'GET',
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    // --- 1. ESM owner 真的被加载成功 ---
    await page.click('.nav-btn[data-page="config"]');
    await expect(page.locator('#page-config')).toHaveClass(/active/);

    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/prompts/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/prompts/index.js'),
    )).toBe(true);

    // --- 2. 真实 GET /api/prompts 返回合成提示词文件 ---
    const promptsResp = await promptsApi;
    expect(promptsResp.status()).toBe(200);
    const promptsBody = await promptsResp.json();
    const promptNames = Array.from(promptsBody).map((f) => String(f.name));
    expect(promptNames).toEqual(expect.arrayContaining([
      'synthetic-prompt-alpha.md',
      'synthetic-prompt-beta.md',
    ]));

    // --- 3. 真实列表 DOM（ESM owner 渲染，名字已转义） ---
    await expect(page.locator('#promptFileList .prompt-file-item')).toHaveCount(
      promptNames.length, { timeout: 15000 },
    );
    const renderedNames = await page.locator('#promptFileList .prompt-file-item')
      .allTextContents();
    expect(renderedNames.map((s) => s.trim()).sort()).toEqual(promptNames.slice().sort());

    // --- 4. 真实点击文件项 → 正文 ---
    await page.locator('#promptFileList .prompt-file-item', {
      hasText: 'synthetic-prompt-alpha.md',
    }).first().click();
    await expect(page.locator('#promptCurrentLabel')).toHaveText(
      'synthetic-prompt-alpha.md', { timeout: 10000 },
    );
    await expect(page.locator('#promptContentView')).toHaveValue(
      /synthetic alpha line 1/,
    );
    // 只读模式下 textarea 仍然 readonly。
    expect(await page.locator('#promptContentView').getAttribute('readonly')).not.toBeNull();

    // --- 5. 复制交互（主路径：navigator.clipboard，真剪贴板回读） ---
    await page.click('#promptCopyBtn');
    await expect(page.locator('#toastContainer .toast')).toContainText(
      /已复制到剪贴板|复制失败/, { timeout: 8000 },
    );
    const clipText = await page.evaluate(async () => {
      try {
        if (!navigator.clipboard || !navigator.clipboard.readText) return null;
        return await navigator.clipboard.readText();
      } catch (_e) { return null; }
    });
    // 已授权 clipboard-read → 必须真的读回内容（不是恒真空断言）。
    expect(clipText, 'clipboard read-back must return the copied prompt body').not.toBeNull();
    expect(clipText).toContain('synthetic alpha line 1');

    // --- 5b. 复制 fallback 路径（无 navigator.clipboard → execCommand） ---
    await page.evaluate(() => {
      try {
        Object.defineProperty(navigator, 'clipboard', {
          value: undefined, configurable: true,
        });
      } catch (_e) { /* 浏览器不允许覆盖时，保留主路径 */ }
    });
    await page.click('#promptCopyBtn');
    await expect(page.locator('#toastContainer .toast').last()).toContainText(
      /已复制到剪贴板|复制失败/, { timeout: 8000 },
    );

    // --- 6. 进入编辑模式：按钮组切换 + textarea 可写 ---
    await page.click('#promptEditBtn');
    await expect(page.locator('#promptReadBtns')).toBeHidden({ timeout: 5000 });
    await expect(page.locator('#promptEditBtns')).toBeVisible();
    await expect(page.locator('#promptModeHint')).toContainText('编辑模式');
    expect(await page.locator('#promptContentView').getAttribute('readonly')).toBeNull();

    // --- 6b. 编辑期间禁止切换文件（真实用户路径） ---
    const contentBeforeSwitch = await page.locator('#promptContentView').inputValue();
    await page.locator('#promptFileList .prompt-file-item', {
      hasText: 'synthetic-prompt-beta.md',
    }).first().click();
    await expect(page.locator('#toastContainer .toast').last()).toContainText(
      '请先保存或取消编辑', { timeout: 8000 },
    );
    expect(await page.locator('#promptContentView').inputValue()).toBe(contentBeforeSwitch);
    await expect(page.locator('#promptCurrentLabel')).toHaveText('synthetic-prompt-alpha.md');

    // --- 7. 差异预览（真实渲染 + 真实模态） ---
    // 注意：逐行差异按行序号对齐（与迁移前 computePromptDiff 完全一致），
    // 因此"多出的一行"只有在**行数变多**时才呈现为 add 类型。
    await page.fill('#promptContentView',
      'synthetic alpha line 1\nsynthetic alpha line 2 CHANGED\nsynthetic alpha line 3\nsynthetic alpha line 4');
    await page.click('#promptPreviewBtn');
    await expect(page.locator('#promptDiffModal')).toBeVisible({ timeout: 8000 });
    const summary = await page.locator('#promptDiffSummary').textContent();
    expect(summary).toContain('原内容');
    expect(summary).toContain('新增行');
    expect(summary).toContain('修改行');
    await expect(page.locator('#promptDiffLines .diff-line-chg').first()).toContainText(
      'synthetic alpha line 2', { timeout: 5000 },
    );
    await expect(page.locator('#promptDiffLines .diff-line-add').first()).toContainText(
      'synthetic alpha line 4', { timeout: 5000 },
    );

    // --- 8. 取消差异模态 → 关闭（不保存） ---
    await page.click('#promptDiffCancelBtn');
    await expect(page.locator('#promptDiffModal')).toBeHidden({ timeout: 5000 });

    // --- 9. 再次预览并确认真实 PUT 保存 ---
    const putWait = page.waitForResponse(
      (r) => r.url().startsWith(baseUrl + '/api/prompts/') &&
             r.request().method() === 'PUT',
      { timeout: 10000 },
    );
    await page.click('#promptPreviewBtn');
    await expect(page.locator('#promptDiffModal')).toBeVisible({ timeout: 8000 });
    await page.click('#promptDiffConfirmBtn');
    const putResp = await putWait;
    expect(putResp.status()).toBe(200);
    await expect(page.locator('#promptDiffModal')).toBeHidden({ timeout: 5000 });
    await expect(page.locator('#toastContainer .toast').last()).toContainText(
      '保存成功', { timeout: 8000 },
    );
    // 保存后回到只读模式，且正文 = 保存内容。
    await expect(page.locator('#promptReadBtns')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#promptEditBtns')).toBeHidden();
    await expect(page.locator('#promptContentView')).toHaveValue(/synthetic alpha line 3/);

    // --- 10. 服务端真相：真实 GET 回读为保存后的内容 ---
    const readBack = await page.request.get(
      baseUrl + '/api/prompts/synthetic-prompt-alpha.md',
    );
    expect(readBack.status()).toBe(200);
    const readBackBody = await readBack.json();
    expect(String(readBackBody.content)).toContain('synthetic alpha line 3');

    // --- 11. 备份状态：保存后应存在最近备份（恢复按钮可见） ---
    await expect(page.locator('#promptRestoreBtn')).toBeVisible({ timeout: 8000 });

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('J) real knowledge page: ESM owner loaded, categories/notes/content/switch', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // 真实 ESM owner 的资源请求：必须在 goto 之前注册，否则会漏掉。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/knowledge/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/knowledge/index.js'),
      { timeout: 20000 },
    );

    // 真实 /api/knowledge/*（不 mock）。categories 在进入「知识库」页时首次
    // 触发，因此 waiter 必须在点击导航**之前**注册。
    const categoriesApi = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/knowledge/categories' ||
              r.url().startsWith(baseUrl + '/api/knowledge/categories?')) &&
             r.request().method() === 'GET',
      { timeout: 20000 },
    );
    const notesApi = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/knowledge/notes' ||
              r.url().startsWith(baseUrl + '/api/knowledge/notes?')) &&
             r.request().method() === 'GET',
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    // --- 1. 真实进入「知识库」页，触发 ESM owner 加载 ---
    await page.click('.nav-btn[data-page="knowledge"]');
    await expect(page.locator('#page-knowledge')).toHaveClass(/active/);

    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/knowledge/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/knowledge/index.js'),
    )).toBe(true);

    // --- 2. 真实 API 返回合成分类 / 笔记（期望值完全来自 API 数据） ---
    const categoriesResp = await categoriesApi;
    expect(categoriesResp.status()).toBe(200);
    const categories = await categoriesResp.json();
    expect(Array.isArray(categories)).toBe(true);
    const mathCat = categories.find((c) => c.name === '高等数学');
    const physicsCat = categories.find((c) => c.name === '大学物理');
    expect(mathCat, 'synthetic 高等数学 category must exist').toBeTruthy();
    expect(physicsCat, 'synthetic 大学物理 category must exist').toBeTruthy();
    // 分类计数来自真实文件扫描（<vault>/知识点/<科目>/*.md）。
    expect(Number(mathCat.count)).toBe(2);
    expect(Number(physicsCat.count)).toBe(1);

    const notesResp = await notesApi;
    expect(notesResp.status()).toBe(200);
    const notes = await notesResp.json();
    expect(Array.isArray(notes)).toBe(true);
    const mathNotes = notes
      .filter((n) => n.category === '高等数学')
      .map((n) => String(n.name));
    const physicsNotes = notes
      .filter((n) => n.category === '大学物理')
      .map((n) => String(n.name));
    expect(mathNotes).toEqual(expect.arrayContaining([
      'synthetic-alpha', 'synthetic-beta',
    ]));
    expect(physicsNotes).toEqual(expect.arrayContaining(['synthetic-gamma']));

    // --- 3. 真实 DOM：分类列表 + 首分类的笔记列表 ---
    await expect(page.locator('#catList .cat-item')).toHaveCount(
      categories.length, { timeout: 15000 },
    );
    // 首次加载自动选中首个分类（这里就是 高等数学）。
    await expect(page.locator('#catList .cat-item.active')).toHaveCount(1);
    await expect(page.locator('#catList .cat-item.active')).toContainText('高等数学');
    await expect(page.locator('#noteList .note-item')).toHaveCount(
      mathNotes.length, { timeout: 15000 },
    );
    // 首分类下的笔记集合必须与真实 API 数据一致（顺序由文件系统决定，
    // 因此按集合比较而不是按顺序）。
    const renderedMathNotes = (await page.locator('#noteList .note-item')
      .allTextContents()).map((s) => s.trim()).sort();
    expect(renderedMathNotes).toEqual(mathNotes.slice().sort());

    // --- 4. 真实点击第二篇笔记 → Markdown 正文呈现 ---
    await page.locator('#noteList .note-item', { hasText: 'synthetic-beta' }).first().click();
    await expect(page.locator('#knowTitle')).toContainText('synthetic-beta.md', { timeout: 10000 });
    await expect(page.locator('#knowContent')).toContainText('合成导数正文标记-9f3a2b7c', { timeout: 10000 });
    // Markdown 真实渲染：# 标题 → <h1>，## 标题 → <h2>
    await expect(page.locator('#knowContent h1')).toHaveCount(1);
    await expect(page.locator('#knowContent h1')).toContainText('合成高数笔记乙');
    await expect(page.locator('#knowContent h2')).toHaveCount(1);
    // 操作区在成功加载后可见（迁移前语义保持不变）。
    await expect(page.locator('#knowActions')).toBeVisible({ timeout: 5000 });

    // --- 5. 真实切换分类 → 标题与正文**对应切换** ---
    await page.locator('#catList .cat-item', { hasText: '大学物理' }).first().click();
    await expect(page.locator('#catList .cat-item.active')).toContainText('大学物理', { timeout: 10000 });
    await expect(page.locator('#noteList .note-item')).toHaveCount(
      physicsNotes.length, { timeout: 10000 },
    );
    await expect(page.locator('#knowTitle')).toContainText('synthetic-gamma.md', { timeout: 10000 });
    await expect(page.locator('#knowContent')).toContainText('合成力学正文标记-3c8d1e5a', { timeout: 10000 });
    // 旧内容必须已经被替换掉（不是残留）。
    await expect(page.locator('#knowContent')).not.toContainText('合成导数正文标记-9f3a2b7c');

    // --- 6. 唯一状态归属：currentNotePath 只在 ESM owner 里持有一份 ---
    const state = await page.evaluate(() => {
      const w = window;
      return {
        classicCurrentNotePath: typeof w.currentNotePath === 'undefined'
          ? null : w.currentNotePath,
        classicNoteCache: typeof w._noteCache === 'undefined' ? null : w._noteCache,
        classicNoteCacheCat: typeof w._noteCacheCat === 'undefined'
          ? null : w._noteCacheCat,
      };
    });
    // classic 层不得再持有第二份 currentNotePath / 缓存镜像。
    expect(state.classicCurrentNotePath).toBeNull();
    expect(state.classicNoteCache).toBeNull();
    expect(state.classicNoteCacheCat).toBeNull();

    // --- 7. Obsidian 打开 endpoint 的调用合同：**静态检查，不发真实请求** ---
    // 该 endpoint 后端会 spawn `start obsidian://...`，自动化测试中禁止调用。
    const obsidianPosts = [];
    page.on('request', (req) => {
      if (req.url() === baseUrl + '/api/knowledge/open-in-obsidian' &&
          req.method() === 'POST') {
        obsidianPosts.push(req);
      }
    });
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    const knowledgeEsmText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'modules', 'knowledge', 'index.js'), 'utf8');
    // classic facade 与 ESM owner 都必须存在该 endpoint 与 {file_path} body。
    expect(appJsText).toContain('openCurrentInObsidian');
    expect(appJsText).toContain('openNoteFromCard');
    expect(knowledgeEsmText).toContain('/api/knowledge/open-in-obsidian');
    expect(knowledgeEsmText).toContain('file_path');

    // 全程绝不能真的发出 Obsidian 打开请求。
    await page.waitForTimeout(500);
    expect(obsidianPosts.length).toBe(0);

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('K) real agent readonly panel: ESM owner loaded, agents/prompt/raw/vault browse', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // 真实 ESM owner 的资源请求：必须在 goto 之前注册，否则会漏掉。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/agent-readonly/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/agent-readonly/index.js'),
      { timeout: 20000 },
    );

    // 写入型 Agent endpoint 的绝对禁止监听（只读语义回归防线）。
    const forbiddenPosts = [];
    page.on('request', (req) => {
      const u = req.url();
      if (u === baseUrl + '/api/agent/process' ||
          u === baseUrl + '/api/agent/save-note' ||
          u === baseUrl + '/api/agent/import-tasks') {
        forbiddenPosts.push({ url: u, method: req.method() });
      }
    });

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    // --- 0. 进入「设置」页（Agent 只读面板所在页） ---
    await page.click('.nav-btn[data-page="config"]');
    await expect(page.locator('#page-config')).toHaveClass(/active/);

    // --- 1. 真实打开 Agent 只读浏览模态，触发 ESM owner 加载 ---
    await expect(page.locator('#agentReadonlyOpenBtn')).toHaveCount(1);
    await page.click('#agentReadonlyOpenBtn');
    await expect(page.locator('#agentReadonlyModal')).toBeVisible({ timeout: 10000 });

    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/agent-readonly/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/agent-readonly/index.js'),
    )).toBe(true);

    // --- 2. 真实 Agent 列表：期望集合**完全来自真实 API** ---
    const agentsResp = await page.request.get(baseUrl + '/api/agent/agents');
    expect(agentsResp.status()).toBe(200);
    const agentsBody = await agentsResp.json();
    expect(Array.isArray(agentsBody)).toBe(true);
    expect(agentsBody.length).toBeGreaterThanOrEqual(1);
    const expectedAgentNames = agentsBody.map((a) => String(a.name));
    const expectedAgentIds = agentsBody.map((a) => String(a.id));

    // --- 3. 真实 DOM：#agentRoList 渲染出与 API 一致的 Agent 项 ---
    await expect(page.locator('#agentRoList .agent-ro-item')).toHaveCount(
      agentsBody.length, { timeout: 15000 },
    );
    const renderedAgentNames = (await page.locator('#agentRoList .agent-ro-item')
      .allTextContents()).map((s) => s.trim());
    expect(renderedAgentNames.slice().sort()).toEqual(expectedAgentNames.slice().sort());
    const renderedAgentIds = (await page.locator('#agentRoList .agent-ro-item')
      .evaluateAll((els) => els.map((e) => e.getAttribute('data-id'))));
    expect(renderedAgentIds).toEqual(expectedAgentIds);

    // --- 4. 真实默认选中首个 Agent → 详情 + 提示词正文 ---
    // 默认选中的是列表首项（与迁移前语义一致）。
    const firstAgent = agentsBody[0];
    await expect(page.locator('#agentRoDetail')).toContainText(
      String(firstAgent.name), { timeout: 10000 },
    );
    await expect(page.locator('#agentRoDetail')).toContainText('写操作（本模式禁用）');
    // 提示词 textarea：等真实 GET .../prompt 返回（不是恒真断言）。
    await page.waitForFunction(() => {
      const ta = document.getElementById('agentRoPromptView');
      return ta && ta.value !== '' && ta.value !== '加载中...';
    }, null, { timeout: 15000 });
    const promptText = await page.locator('#agentRoPromptView').inputValue();
    const promptResp = await page.request.get(
      baseUrl + '/api/agent/agents/' + encodeURIComponent(String(firstAgent.id)) + '/prompt',
    );
    expect(promptResp.status()).toBe(200);
    const promptBody = await promptResp.json();
    // 合成 root 里为 note_organizer 播种了提示词文件 → 首个 Agent（列表首项）
    // 的提示词必须走"文件存在"分支，否则就是回归。
    expect(promptBody.exists, 'synthetic agent prompt file must exist').toBe(true);
    expect(promptText).toContain(String(promptBody.content).slice(0, 20));
    await expect(page.locator('#agentRoPromptLabel')).toContainText('提示词内容（只读）');
    await expect(page.locator('#agentRoPromptLabel')).toContainText('字符');

    // --- 5. 真实切换到「Raw 文件」tab → 真实 Raw 列表 + 真实文件正文 ---
    await page.click('.agent-ro-tab[data-agent-tab="raw"]');
    await expect(page.locator('#agentTabRaw')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#agentTabAgents')).toBeHidden();

    const rawResp = await page.request.get(baseUrl + '/api/agent/files/raw');
    expect(rawResp.status()).toBe(200);
    const rawBody = await rawResp.json();
    const rawFiles = rawBody.files || [];
    const rawSubdirs = rawBody.subdirs || [];
    // 合成 root 里**确定**播种了一个 Raw txt 文件 → 空列表就是回归，必须 RED。
    expect(rawFiles.length, 'synthetic raw txt file must be visible').toBeGreaterThanOrEqual(1);

    await expect(page.locator('#agentRawPath')).toContainText('当前目录', { timeout: 10000 });
    // Raw 目录项 + 文件项的数量必须与真实 API 完全一致。
    await expect(page.locator('#agentRawList [data-raw-dir]')).toHaveCount(
      rawSubdirs.length, { timeout: 15000 },
    );
    await expect(page.locator('#agentRawList [data-raw-file]')).toHaveCount(
      rawFiles.length, { timeout: 15000 },
    );
    {
      // 真实点击第一个 Raw 文件 → 真实正文（合成内容，绝不涉及真实用户数据）。
      const firstRaw = rawFiles[0];
      await page.locator('#agentRawList [data-raw-file]').first().click();
      await page.waitForFunction(() => {
        const box = document.getElementById('agentRawContent');
        return box && box.textContent !== '加载中...' && box.textContent !== '';
      }, null, { timeout: 15000 });
      const rawContent = await page.locator('#agentRawContent').textContent();
      const rawContentResp = await page.request.get(
        baseUrl + '/api/agent/files/raw/content?path=' +
        encodeURIComponent(String(firstRaw.path)),
      );
      expect(rawContentResp.status()).toBe(200);
      const rawContentBody = await rawContentResp.json();
      expect(rawContent.trim()).toContain(String(rawContentBody.content).trim().slice(0, 20));
      await expect(page.locator('#agentRawPath')).toContainText('文件：');
    }

    // --- 6. 真实切换到「Vault 文件」tab → 真实 Vault 列表 + 真实文件正文 ---
    await page.click('.agent-ro-tab[data-agent-tab="vault"]');
    await expect(page.locator('#agentTabVault')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#agentTabRaw')).toBeHidden();

    const vaultResp = await page.request.get(baseUrl + '/api/agent/files/vault');
    expect(vaultResp.status()).toBe(200);
    const vaultBody = await vaultResp.json();
    const vaultFiles = vaultBody.files || [];
    const vaultDirs = vaultBody.dirs || [];
    // 合成 root 的 vault/ 里**确定**播种了一个 Markdown 文件 → 空列表即回归。
    expect(vaultFiles.length, 'synthetic vault md file must be visible').toBeGreaterThanOrEqual(1);

    await expect(page.locator('#agentVaultPath')).toContainText('当前目录', { timeout: 10000 });
    await expect(page.locator('#agentVaultList [data-vault-dir]')).toHaveCount(
      vaultDirs.length, { timeout: 15000 },
    );
    await expect(page.locator('#agentVaultList [data-vault-file]')).toHaveCount(
      vaultFiles.length, { timeout: 15000 },
    );
    {
      const firstVault = vaultFiles[0];
      await page.locator('#agentVaultList [data-vault-file]').first().click();
      await page.waitForFunction(() => {
        const box = document.getElementById('agentVaultContent');
        return box && box.textContent !== '加载中...' && box.textContent !== '';
      }, null, { timeout: 15000 });
      const vaultContent = await page.locator('#agentVaultContent').textContent();
      const vaultContentResp = await page.request.get(
        baseUrl + '/api/agent/files/vault/content?path=' +
        encodeURIComponent(String(firstVault.path)),
      );
      expect(vaultContentResp.status()).toBe(200);
      const vaultContentBody = await vaultContentResp.json();
      expect(vaultContent.trim()).toContain(String(vaultContentBody.content).trim().slice(0, 20));
      await expect(page.locator('#agentVaultPath')).toContainText('文件：');
    }

    // --- 7. 关闭模态（真实关闭按钮） ---
    await page.click('#agentReadonlyCloseBtn');
    await expect(page.locator('#agentReadonlyModal')).toBeHidden({ timeout: 5000 });

    // --- 8. 唯一状态归属：classic 层不得再持有第二份镜像 ---
    // 注意：#agentRoList 是 HTML id，浏览器会把它作为「named window
    // property」暴露为 window.agentRoList（DOM 元素）。迁移前 classic 层
    // 顶层 `var agentRoList = []` 会以 own property 覆盖该 named property，
    // 因此 window.agentRoList 会是一个**数组**。迁移后它必须仍然是 DOM
    // 元素（不是数组）→ 证明 classic 层已不再持有列表镜像。
    const state = await page.evaluate(() => {
      const w = window;
      const ro = w.agentRoList;
      return {
        classicAgentRoListIsArray: Array.isArray(ro),
        classicAgentRoListIsElement: !!(ro && ro.nodeType === 1),
        classicAgentRawSubdir: typeof w.agentRawSubdir === 'undefined'
          ? null : w.agentRawSubdir,
        classicAgentVaultSubject: typeof w.agentVaultSubject === 'undefined'
          ? null : w.agentVaultSubject,
      };
    });
    expect(state.classicAgentRoListIsArray).toBe(false);
    expect(state.classicAgentRoListIsElement).toBe(true);
    expect(state.classicAgentRawSubdir).toBeNull();
    expect(state.classicAgentVaultSubject).toBeNull();

    // 静态补充：classic 层源码里不得再出现这三个状态变量的声明。
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    expect(appJsText).not.toMatch(/^\s*var\s+agentRoList\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+agentRawSubdir\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+agentVaultSubject\s*=/m);

    // --- 9. 只读语义：整个生命周期内零写入型 Agent 请求 ---
    await page.waitForTimeout(500);
    expect(forbiddenPosts.length).toBe(0);

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('L) timer ESM owner: single session drives Dock + task panel, pause/resume/complete, failure keeps session', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // ESM owner 的资源请求：必须在 goto 之前注册。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/timer/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/timer/index.js'),
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');

    // --- 1. ESM timer owner 真的被加载成功 ---
    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/timer/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/timer/index.js'),
    )).toBe(true);

    // --- 2. 从真实 API 建立一个合成 timer session ---
    // 用真实 /api/tasks 里的合成任务 id，POST 真实的 /api/timer/start。
    const tasksResp = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/tasks');
      return await r.json();
    }, baseUrl);
    const apiTasks = Array.isArray(tasksResp) ? tasksResp : (tasksResp.tasks || []);
    expect(apiTasks.length).toBeGreaterThanOrEqual(1);
    const syntheticTask = apiTasks.find((t) => !t.completed && t.is_unlocked !== false);
    expect(syntheticTask).toBeTruthy();
    expect(Number.isFinite(Number(syntheticTask.id)) && Number(syntheticTask.id) > 0).toBe(true);

    const startApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/start' ||
               r.url().startsWith(baseUrl + '/api/timer/start?')) &&
             r.request().method() === 'POST',
      { timeout: 15000 },
    );
    // 走 **真实用户路径**：任务页面板的「开始」按钮（真实 POST /api/timer/start，
    // 由 app.js 的 ESM timer owner 发起）。
    await page.click('.nav-btn[data-page="tasks"]');
    await expect(page.locator('#page-tasks')).toHaveClass(/active/);
    // <option> 不可见 → 用 option 列表 + waitForFunction 等待任务下拉被填充。
    await page.waitForFunction(() => {
      const sel = document.getElementById('timerTaskSelect');
      if (!sel) return false;
      return sel.querySelectorAll('option[value]:not([value=""])').length > 0;
    }, null, { timeout: 15000 });
    const selectedTaskValue = await page.locator('#timerTaskSelect option[value]:not([value=""])')
      .first().getAttribute('value');
    expect(Number(selectedTaskValue)).toBeGreaterThan(0);
    await page.selectOption('#timerTaskSelect', selectedTaskValue);
    await page.fill('#timerPlannedMin', '30');
    await page.click('#timerStartBtn');
    const startResp = await startApiResp;
    expect(startResp.status()).toBe(200);
    const startBody = await startResp.json();
    const sessionId = Number(startBody.session_id);
    expect(Number.isFinite(sessionId) && sessionId > 0).toBe(true);
    expect(Number(startBody.task_id)).toBe(Number(selectedTaskValue));

    // 服务端确实有活动 session。
    const activeAfterStart = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return await r.json();
    }, baseUrl);
    expect(activeAfterStart).toBeTruthy();
    expect(activeAfterStart.id).toBe(sessionId);
    expect(activeAfterStart.is_paused).toBe(false);

    // --- 3. 刷新后从真实 API 恢复：Dock 与任务页显示同一任务 ---
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#gachaMultiBtn');

    // Dock（抽卡页常驻）：恢复出活动 session。
    await expect(page.locator('#timerDockIdle')).toBeHidden({ timeout: 15000 });
    await expect(page.locator('#timerDockActive')).toBeVisible();
    await expect(page.locator('#timerDockTime')).toHaveText(/^\d{2}:\d{2}$/);
    const dockTaskName = (await page.locator('#timerDockTaskName').textContent()).trim();
    expect(dockTaskName.length).toBeGreaterThan(0);

    // 任务页面板：同一 session（同一任务名 + 同样的运行中状态）。
    await page.click('.nav-btn[data-page="tasks"]');
    await expect(page.locator('#page-tasks')).toHaveClass(/active/);
    await expect(page.locator('#timerStatusText')).toContainText('计时中', { timeout: 15000 });
    await expect(page.locator('#timerStatusText')).not.toContainText('已暂停');
    await expect(page.locator('#timerElapsedDisplay')).toHaveText(/^\d{2}:\d{2}$/);
    await expect(page.locator('#timerStartBtn')).toBeHidden();
    await expect(page.locator('#timerStopBtn')).toBeVisible();
    const panelStatusText = (await page.locator('#timerStatusText').textContent()).trim();
    // 任务页与 Dock 显示 **同一个任务**（同一个名字）。
    expect(panelStatusText).toContain(dockTaskName);

    // --- 4. pause → 两处 UI 同步显示"已暂停" ---
    await page.waitForTimeout(1200);
    const pauseApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/pause' ||
               r.url().startsWith(baseUrl + '/api/timer/pause?')) &&
             r.request().method() === 'POST',
      { timeout: 15000 },
    );
    // 任务页面板的「暂停」按钮 → 与 Dock 共用同一个 owner。
    await page.click('#timerPauseBtn');
    const pauseResp = await pauseApiResp;
    expect(pauseResp.status()).toBe(200);
    const pauseBody = await pauseResp.json();
    expect(pauseBody.session_id).toBe(sessionId);
    expect(pauseBody.is_paused).toBe(true);

    await expect(page.locator('#timerStatusText')).toContainText('已暂停', { timeout: 10000 });
    await expect(page.locator('#timerStatusText')).toHaveClass(/timer-paused/);
    await expect(page.locator('#timerPauseBtn i.fa-play')).toHaveCount(1);
    await expect(page.locator('#timerStartBtn')).toBeHidden();

    // Dock（同一 owner 的另一处呈现）也必须同步为"已暂停"。
    const dockPausedState = await page.evaluate(() => {
      const dockActive = document.getElementById('timerDockActive');
      const idle = document.getElementById('timerDockIdle');
      const pauseBtn = document.getElementById('timerDockPauseBtn');
      return {
        activeHidden: !!(dockActive && dockActive.classList.contains('hidden')),
        idleHidden: !!(idle && idle.classList.contains('hidden')),
        pauseTitle: pauseBtn ? pauseBtn.getAttribute('title') : null,
        pauseHasPlayIcon: !!(pauseBtn && pauseBtn.querySelector('i.fa-play')),
      };
    });
    expect(dockPausedState.activeHidden).toBe(false);
    expect(dockPausedState.idleHidden).toBe(true);
    expect(dockPausedState.pauseTitle).toBe('继续计时器');
    expect(dockPausedState.pauseHasPlayIcon).toBe(true);

    // 服务端确实是 paused。
    const activeAfterPause = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return await r.json();
    }, baseUrl);
    expect(activeAfterPause.id).toBe(sessionId);
    expect(activeAfterPause.is_paused).toBe(true);

    // --- 5. resume → 两处 UI 同步回到运行中 ---
    const resumeApiResp = page.waitForResponse(
      (r) => (r.url() === baseUrl + '/api/timer/resume' ||
               r.url().startsWith(baseUrl + '/api/timer/resume?')) &&
             r.request().method() === 'POST',
      { timeout: 15000 },
    );
    await page.click('#timerPauseBtn');
    const resumeResp = await resumeApiResp;
    expect(resumeResp.status()).toBe(200);
    const resumeBody = await resumeResp.json();
    expect(resumeBody.session_id).toBe(sessionId);
    expect(resumeBody.is_paused).toBe(false);

    await expect(page.locator('#timerStatusText')).not.toContainText('已暂停', { timeout: 10000 });
    await expect(page.locator('#timerStatusText')).toContainText('计时中');
    await expect(page.locator('#timerPauseBtn i.fa-pause')).toHaveCount(1);

    // Dock 同步回到运行中。
    const dockResumedState = await page.evaluate(() => {
      const pauseBtn = document.getElementById('timerDockPauseBtn');
      return {
        pauseTitle: pauseBtn ? pauseBtn.getAttribute('title') : null,
        pauseHasPauseIcon: !!(pauseBtn && pauseBtn.querySelector('i.fa-pause')),
      };
    });
    expect(dockResumedState.pauseTitle).toBe('暂停计时器');
    expect(dockResumedState.pauseHasPauseIcon).toBe(true);

    // --- 6. complete 故障 → 活动 session **不丢失** ---
    // 用真实路由拦截让 /api/timer/complete 返回 500（只在这一段生效）。
    let completeFailing = true;
    await context.route('**/api/timer/complete', async (route) => {
      if (completeFailing) {
        return route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: '合成故障：计时结束失败' }),
        });
      }
      return route.continue();
    });

    // 在任务页面板上点「停止」→ 打开结果模态 → 选择「已完成」。
    await page.click('#timerStopBtn');
    await expect(page.locator('#timerOutcomeModal')).toBeVisible({ timeout: 10000 });
    const completeFailedResp = page.waitForResponse(
      (r) => r.url() === baseUrl + '/api/timer/complete' &&
             r.request().method() === 'POST',
      { timeout: 15000 },
    );
    await page.click('#timerOutcomeModal button[data-timer-outcome="completed"]');
    const failedComplete = await completeFailedResp;
    expect(failedComplete.status()).toBe(500);

    // 失败后：活动 session **不丢失** —— 任务页面板仍显示运行中
    // （该 DOM 由 owner 的 getter 直接驱动，等价于 owner 仍持有 session）。
    await expect(page.locator('#timerStatusText')).toContainText('计时中', { timeout: 10000 });
    await expect(page.locator('#timerStopBtn')).toBeVisible();
    await expect(page.locator('#timerStartBtn')).toBeHidden();
    await expect(page.locator('#timerStatusText')).not.toContainText('已暂停');
    // Dock 也仍然是"进行中"。
    const dockAfterFailure = await page.evaluate(() => {
      const active = document.getElementById('timerDockActive');
      const idle = document.getElementById('timerDockIdle');
      const nameEl = document.getElementById('timerDockTaskName');
      return {
        activeHidden: !!(active && active.classList.contains('hidden')),
        idleHidden: !!(idle && idle.classList.contains('hidden')),
        taskName: nameEl ? (nameEl.textContent || '').trim() : '',
      };
    });
    expect(dockAfterFailure.activeHidden).toBe(false);
    expect(dockAfterFailure.idleHidden).toBe(true);
    expect(dockAfterFailure.taskName.length).toBeGreaterThan(0);

    // 服务端 session 仍然活着（没有被误标完成）。
    const activeAfterFailedComplete = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return await r.json();
    }, baseUrl);
    expect(activeAfterFailedComplete).toBeTruthy();
    expect(activeAfterFailedComplete.id).toBe(sessionId);

    // --- 7. 故障恢复后 complete 成功 → 两处 UI 同步回到 idle ---
    completeFailing = false;
    const completeOkResp = page.waitForResponse(
      (r) => r.url() === baseUrl + '/api/timer/complete' &&
             r.request().method() === 'POST',
      { timeout: 15000 },
    );
    await page.click('#timerStopBtn');
    await expect(page.locator('#timerOutcomeModal')).toBeVisible({ timeout: 10000 });
    await page.click('#timerOutcomeModal button[data-timer-outcome="completed"]');
    const okComplete = await completeOkResp;
    expect(okComplete.status()).toBe(200);
    const okCompleteBody = await okComplete.json();
    expect(okCompleteBody.ended).toBe(true);
    expect(okCompleteBody.session_id).toBe(sessionId);

    // owner 状态清空（任务页与 Dock 都回到 idle）。
    await expect(page.locator('#timerStatusText')).toHaveText('未在计时', { timeout: 10000 });
    await expect(page.locator('#timerStartBtn')).toBeVisible();
    await expect(page.locator('#timerStopBtn')).toBeHidden();
    await expect(page.locator('#timerElapsedDisplay')).toHaveText('00:00');

    // 服务端没有活动 session 了。
    const activeAfterComplete = await page.evaluate(async (b) => {
      const r = await fetch(b + '/api/timer/active', { method: 'GET' });
      return await r.json();
    }, baseUrl);
    expect(activeAfterComplete).toBeNull();

    // Dock 也回到 idle。
    await page.click('.nav-btn[data-page="gacha"]');
    await expect(page.locator('#page-gacha')).toHaveClass(/active/);
    await expect(page.locator('#timerDockIdle')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#timerDockActive')).toBeHidden();

    // --- 8. window 上不再存在旧的状态镜像 ---
    const legacyMirror = await page.evaluate(() => {
      const w = window;
      return {
        timerDockSession: typeof w.timerDockSession,
        timerActiveSession: typeof w.timerActiveSession,
        timerDockPaused: typeof w.timerDockPaused,
        timerDockPausedElapsed: typeof w.timerDockPausedElapsed,
        inlineTimerHandle: typeof w._inlineTimerHandle,
      };
    });
    for (const [key, typeName] of Object.entries(legacyMirror)) {
      expect(typeName).toBe('undefined');
    }

    // 静态补充：classic 层源码里不得再声明这些镜像状态，也不得直连计时接口。
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    expect(appJsText).not.toMatch(/^\s*var\s+timerDockSession\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+timerActiveSession\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+timerDockPaused\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+timerDockPausedElapsed\s*=/m);
    // classic 层不得再 **写入** 内嵌计时句柄（注释里提及名字不算）。
    expect(appJsText).not.toMatch(/window\._inlineTimerHandle\s*=[^=]/);
    // 计时端点必须集中在 owner 模块里。
    expect(appJsText).not.toMatch(/['"]\/api\/timer\//);

    const ownerJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'modules', 'timer', 'index.js'), 'utf8');
    expect(ownerJsText).toContain('/api/timer/active');
    expect(ownerJsText).toContain('/api/timer/start');
    expect(ownerJsText).toContain('/api/timer/pause');
    expect(ownerJsText).toContain('/api/timer/resume');
    expect(ownerJsText).toContain('/api/timer/complete');

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('M) real state assessment: ESM owner loaded, slider edit, real POST, summary updated', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // ESM owner 的资源请求：必须在 goto 之前注册（启动即触发 facade import）。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/state-assessment/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/state-assessment/index.js'),
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    // --- 1. ESM owner 真的被加载成功 ---
    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/state-assessment/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/state-assessment/index.js'),
    )).toBe(true);

    // --- 2. 真实进入「日程」页，打开评估模态 ---
    await page.click('.nav-btn[data-page="schedule"]');
    await expect(page.locator('#page-schedule')).toHaveClass(/active/);
    // 真实题目集合来自真实 API（GET /api/state/questions）。
    const questionsResp = await page.request.get(baseUrl + '/api/state/questions');
    expect(questionsResp.status()).toBe(200);
    const questionsBody = await questionsResp.json();
    const expectedQuestions = questionsBody.questions || [];
    expect(expectedQuestions.length).toBeGreaterThanOrEqual(1);

    await page.click('#stateAssessmentOpenBtn');
    await expect(page.locator('#stateAssessmentModal')).toBeVisible({ timeout: 10000 });
    // 至少一个问题滑块出现，且数量与真实题目数一致。
    await expect(page.locator('#stateAssessmentForm .assess-range')).toHaveCount(
      expectedQuestions.length, { timeout: 15000 },
    );
    // 滑块刻度契约不变：min=1 / max=5 / step=1，初始默认 3。
    const sliderMeta = await page.locator('#stateAssessmentForm .assess-range')
      .first().evaluate((el) => ({
        min: el.getAttribute('min'),
        max: el.getAttribute('max'),
        step: el.getAttribute('step'),
        value: el.value,
      }));
    expect(sliderMeta.min).toBe('1');
    expect(sliderMeta.max).toBe('5');
    expect(sliderMeta.step).toBe('1');
    expect(sliderMeta.value).toBe('3');
    // 「当前: N」数值随滑块呈现。
    await expect(page.locator('#stateAssessmentForm .assess-val-num').first())
      .toHaveText('3');

    // --- 3. 修改一个答案（真实 input 事件）→ 真实 POST ---
    const firstQid = String(expectedQuestions[0].id);
    await page.locator('#stateAssessmentForm .assess-range').first()
      .evaluate((el) => {
        el.value = '5';
        el.dispatchEvent(new Event('input', { bubbles: true }));
      });
    // input 后「当前: N」必须立刻更新为 5。
    await expect(page.locator('#stateAssessmentForm .assess-val-num').first())
      .toHaveText('5');

    const postWaiter = page.waitForResponse(
      (r) => r.url() === baseUrl + '/api/state/assessment' &&
             r.request().method() === 'POST',
      { timeout: 15000 },
    );
    // 走真实用户路径：模态里的「保存」按钮。
    await page.click('#stateAssessmentSaveBtn');
    const postResp = await postWaiter;
    expect(postResp.status()).toBe(200);
    const postBody = JSON.parse(postResp.request().postData() || '{}');
    expect(postBody.answers).toBeTruthy();
    expect(Object.prototype.hasOwnProperty.call(postBody.answers, firstQid)).toBe(true);
    expect(Number(postBody.answers[firstQid])).toBe(5);
    // 其余题目保持默认 3（语义不变）。
    for (const q of expectedQuestions.slice(1)) {
      expect(Number(postBody.answers[String(q.id)])).toBe(3);
    }

    // --- 4. 保存成功后 modal 关闭，summary 变为「已完成」 ---
    await expect(page.locator('#stateAssessmentModal')).toBeHidden({ timeout: 10000 });
    await expect(page.locator('#stateAssessmentSummary .state-scores')).toHaveCount(
      1, { timeout: 15000 },
    );
    // 按钮文案切换为「修改评估」（真实 API 返回 completed=true）。
    await expect(page.locator('#stateAssessmentOpenBtn')).toContainText('修改评估');
    // 历史表出现今日记录。
    await expect(page.locator('#stateAssessmentHistory table.energy-table')).toHaveCount(
      1, { timeout: 15000 },
    );

    // --- 5. 唯一状态归属：classic 层不得再持有状态镜像 ---
    const mirrors = await page.evaluate(() => {
      const w = window;
      return {
        assessmentQuestions: typeof w.assessmentQuestions,
        assessmentAnswers: typeof w.assessmentAnswers,
      };
    });
    expect(mirrors.assessmentQuestions).toBe('undefined');
    expect(mirrors.assessmentAnswers).toBe('undefined');

    // 静态补充：classic 层源码里不得再出现题目/答案状态声明与评分表渲染，
    // 也不得直连 /api/state/assessment 与 /api/state/questions。
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    expect(appJsText).not.toMatch(/^\s*var\s+assessmentQuestions\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+assessmentAnswers\s*=/m);
    expect(appJsText).not.toMatch(/^\s*var\s+TONE_LABELS\s*=/m);
    expect(appJsText).not.toMatch(/['"]\/api\/state\/assessment/);
    expect(appJsText).not.toMatch(/['"]\/api\/state\/questions/);
    // 旧全局入口名必须继续可用。
    expect(appJsText).toContain('loadStateAssessmentPanel');
    expect(appJsText).toContain('openStateAssessmentModal');
    expect(appJsText).toContain('saveStateAssessment');
    expect(appJsText).toContain('closeStateAssessmentModal');

    const ownerJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'modules', 'state-assessment', 'index.js'), 'utf8');
    expect(ownerJsText).toContain('/api/state/assessment');
    expect(ownerJsText).toContain('/api/state/questions');
    expect(ownerJsText).toContain('/api/state/assessment/history?days=7');

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('O) real config form: ESM owner loaded, GET fills fields without api key backfill, save POST payload exact', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // --- synthetic 配置返回值 ---
    // 故意 **不返回** port / vault_path / model → 断言既有默认值；
    // 故意 **返回** openai_api_key（伪值）→ 断言 GET **绝不回填** API Key。
    const syntheticConfig = {
      notes_directory: 'synthetic-notes-dir',
      api_base: 'https://synthetic.invalid/v1',
      openai_api_key: 'sk-synthetic-must-never-be-filled',
      has_openai_key: true,
      has_claude_key: false
    };

    const configGetHits = [];
    const configPostBodies = [];

    // 注册在 installSafetyRoutes **之后**：最后注册的 handler 优先匹配。
    await context.route(/\/api\/config$/, async (route) => {
      const req = route.request();
      if (req.method() !== 'GET') return route.fallback();
      configGetHits.push({ url: req.url(), method: req.method() });
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(syntheticConfig),
      });
    });

    await context.route(/\/api\/config\/save$/, async (route) => {
      const req = route.request();
      if (req.method() !== 'POST') return route.fallback();
      let parsed = null;
      try { parsed = JSON.parse(req.postData() || '{}'); } catch (_e) { parsed = null; }
      configPostBodies.push(parsed);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    // ESM owner 的资源请求：必须在 goto 之前注册，否则会漏掉。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/config/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/config/index.js'),
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    // --- 1. 进入「设置」页 → 触发 GET /api/config + ESM owner import ---
    await page.click('.nav-btn[data-page="config"]');
    await expect(page.locator('#page-config')).toHaveClass(/active/);

    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/config/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/config/index.js'),
    )).toBe(true);

    // --- 2. GET 真的发生（synthetic 注入） ---
    await expect.poll(() => configGetHits.length, { timeout: 15000 }).toBeGreaterThan(0);
    for (const h of configGetHits) {
      expect(h.method).toBe('GET');
      expect(h.url).toContain('/api/config');
    }

    // --- 3. 字段按既有默认值 / 返回值填充 ---
    await expect(page.locator('#cfgPort')).toHaveValue('5000', { timeout: 10000 });
    await expect(page.locator('#cfgNotesDir')).toHaveValue('synthetic-notes-dir', { timeout: 10000 });
    await expect(page.locator('#cfgVaultPath')).toHaveValue('', { timeout: 10000 });
    await expect(page.locator('#cfgApiBase')).toHaveValue('https://synthetic.invalid/v1', { timeout: 10000 });
    await expect(page.locator('#cfgModel')).toHaveValue('gpt-4o-mini', { timeout: 10000 });

    // --- 4. GET **不回填** API Key（即使服务端返回了 key 字段） ---
    await expect(page.locator('#cfgApiKey')).toHaveValue('', { timeout: 10000 });

    // --- 5. 注入的 refreshAgentReadonlyHint 委托生效（Agent 只读 owner 的既有实现） ---
    await expect(page.locator('#agentReadonlyHint')).toContainText(
      '只读浏览模式', { timeout: 10000 },
    );

    // --- 6. 填入明显的 fake key + 改端口 → 点击保存 → 捕获 POST ---
    await page.fill('#cfgApiKey', 'sk-test-not-a-real-secret');
    await page.fill('#cfgPort', '6123');
    await page.click('button[onclick="saveConfigForm()"]');

    await expect.poll(() => configPostBodies.length, { timeout: 15000 }).toBe(1);
    expect(configPostBodies[0]).toEqual({
      port: 6123,
      notes_directory: 'synthetic-notes-dir',
      vault_path: '',
      openai_api_key: 'sk-test-not-a-real-secret',
      api_base: 'https://synthetic.invalid/v1',
      model: 'gpt-4o-mini',
    });

    // --- 7. 成功 toast 可见 ---
    await expect(page.locator('#toastContainer .toast').last()).toContainText(
      '已保存，重启服务器后生效', { timeout: 8000 },
    );
    // 加载未失败（不出现加载错误 toast）。
    const toastTexts = await page.locator('#toastContainer .toast').allTextContents();
    expect(toastTexts.some((t) => t.includes('加载配置失败'))).toBe(false);

    // --- 8. 唯一实现归属：classic 层不得再持有配置表单业务实现 ---
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    expect(appJsText).not.toMatch(/['"]\/api\/config/);
    expect(appJsText).not.toMatch(/cfgPort/);
    expect(appJsText).not.toMatch(/cfgApiKey/);
    // 旧全局入口名必须继续可用（导航调用点 + HTML inline onclick）。
    expect(appJsText).toContain('loadConfigForm');
    expect(appJsText).toContain('saveConfigForm');

    const ownerJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'modules', 'config', 'index.js'), 'utf8');
    expect(ownerJsText).toContain('/api/config');
    expect(ownerJsText).toContain('/api/config/save');
    expect(ownerJsText).toContain('openai_api_key');
    // GET 路径**不得**回填 API Key 字段。
    expect(ownerJsText).not.toMatch(/cfgApiKey'\)\.value\s*=/);

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('P) real schedule: ESM owner loaded, schedule edited and activities managed', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // --- synthetic 日程数据 ---
    const today = new Date();
    const todayStr = today.toISOString().slice(0, 10);
    const dow = today.getDay();
    const dayIndex = String(dow === 0 ? 6 : dow - 1);

    const syntheticSlots = [
      { slot_id: 'am1', name: '上午第一节', start_time: '08:00', end_time: '08:45' },
      { slot_id: 'pm1', name: '下午第一节', start_time: '14:00', end_time: '14:45' },
    ];
    // weekly 以当前星期为 key：pm1 只有 weekly activity（回退路径）。
    const syntheticWeekly = {};
    syntheticWeekly[dayIndex] = { pm1: { activity: '合成周计划' } };
    // daily 命中 am1（daily 优先路径）。
    const syntheticDaily = [{ slot_id: 'am1', activity: '合成每日阅读' }];

    const activities = [
      { id: 7, name: '合成晨读', type: 'study', duration_minutes: 25 },
    ];

    const scheduleRequests = [];
    const dailyPostBodies = [];
    const activityPostBodies = [];
    const activityDeleteUrls = [];

    // 注册在 installSafetyRoutes **之后**：最后注册的 handler 优先匹配。
    await context.route(/\/api\/schedule\//, async (route) => {
      const req = route.request();
      const url = req.url();
      const method = req.method();
      const pathname = url.split('?')[0];

      if (pathname.endsWith('/api/schedule/slots') && method === 'GET') {
        scheduleRequests.push({ method, url });
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(syntheticSlots),
        });
      }
      if (pathname.endsWith('/api/schedule/weekly') && method === 'GET') {
        scheduleRequests.push({ method, url });
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(syntheticWeekly),
        });
      }
      if (pathname.endsWith('/api/schedule/daily') && method === 'GET') {
        scheduleRequests.push({ method, url });
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(syntheticDaily),
        });
      }
      if (pathname.endsWith('/api/schedule/daily') && method === 'POST') {
        let parsed = null;
        try { parsed = JSON.parse(req.postData() || '{}'); } catch (_e) { parsed = null; }
        dailyPostBodies.push(parsed);
        scheduleRequests.push({ method, url });
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ success: true }),
        });
      }
      if (pathname.endsWith('/api/schedule/activities') && method === 'GET') {
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify(activities),
        });
      }
      if (pathname.endsWith('/api/schedule/activities') && method === 'POST') {
        let parsed = null;
        try { parsed = JSON.parse(req.postData() || '{}'); } catch (_e) { parsed = null; }
        activityPostBodies.push(parsed);
        const id = 100 + activities.length;
        activities.push({
          id,
          name: (parsed && parsed.name) || '',
          type: (parsed && parsed.type) || 'custom',
          duration_minutes: (parsed && parsed.duration_minutes) || 30,
        });
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ success: true, id }),
        });
      }
      if (/\/api\/schedule\/activities\/\d+$/.test(pathname) && method === 'DELETE') {
        activityDeleteUrls.push(pathname);
        const delId = parseInt(pathname.split('/').pop(), 10);
        const idx = activities.findIndex((a) => a.id === delId);
        if (idx !== -1) activities.splice(idx, 1);
        return route.fulfill({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({ success: true }),
        });
      }
      return route.fallback();
    });

    // 原生 prompt / confirm 走真实对话框（不 mock DOM）。
    const dialogs = [];
    page.on('dialog', async (dialog) => {
      dialogs.push({ type: dialog.type(), message: dialog.message() });
      if (dialog.type() === 'prompt') {
        await dialog.accept('合成槽位活动');
      } else {
        await dialog.accept();
      }
    });

    // ESM owner 的资源请求：必须在 goto 之前注册（app.js 启动即调用
    // renderSchedule() 触发 facade import）。
    const esmResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/schedule/index.js')) {
        esmResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const esmResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/schedule/index.js'),
      { timeout: 20000 },
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    // --- 1. ESM owner 真的被加载成功（HTTP 200） ---
    const esmResp = await esmResponseWait;
    expect(esmResp.status()).toBe(200);
    expect(esmResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of esmResponses) {
      expect(r.status).toBe(200);
    }
    const esmResourceNames = await page.waitForFunction(() => {
      const names = performance.getEntriesByType('resource').map((e) => e.name);
      return names.some((n) => n.indexOf('/static/modules/schedule/index.js') !== -1)
        ? names : null;
    }, null, { timeout: 15000 }).then((handle) => handle.jsonValue());
    expect(Array.isArray(esmResourceNames)).toBe(true);
    expect(esmResourceNames.some(
      (n) => n.includes('/static/modules/schedule/index.js'),
    )).toBe(true);

    // --- 2. 进入「日程」页：slots → weekly → daily 的既有请求顺序 ---
    await page.click('.nav-btn[data-page="schedule"]');
    await expect(page.locator('#page-schedule')).toHaveClass(/active/);

    await expect.poll(() => scheduleRequests.length, { timeout: 15000 })
      .toBeGreaterThanOrEqual(3);
    const firstSlots = scheduleRequests.findIndex(
      (r) => r.method === 'GET' && r.url.includes('/api/schedule/slots'));
    const firstWeekly = scheduleRequests.findIndex(
      (r) => r.method === 'GET' && r.url.includes('/api/schedule/weekly'));
    const firstDaily = scheduleRequests.findIndex(
      (r) => r.method === 'GET' && r.url.includes('/api/schedule/daily'));
    expect(firstSlots).toBeGreaterThanOrEqual(0);
    expect(firstWeekly).toBeGreaterThan(firstSlots);
    expect(firstDaily).toBeGreaterThan(firstWeekly);
    // daily 请求带当前日期参数（UTC 日期字符串语义保持不变）。
    const firstDailyUrl = scheduleRequests[firstDaily].url;
    expect(firstDailyUrl).toContain('/api/schedule/daily?date=');
    expect(decodeURIComponent(firstDailyUrl)).toContain(todayStr);

    // --- 3. 日期标签与日程格渲染 ---
    await expect(page.locator('#schedDate')).toHaveText(todayStr, { timeout: 10000 });
    await expect(page.locator('#schedGrid .sched-slot')).toHaveCount(2, { timeout: 10000 });
    // daily 优先（am1）
    await expect(page.locator('#schedGrid .sched-slot[data-slot="am1"] .slot-act'))
      .toHaveValue('合成每日阅读', { timeout: 10000 });
    // weekly 回退（pm1）
    await expect(page.locator('#schedGrid .sched-slot[data-slot="pm1"] .slot-act'))
      .toHaveValue('合成周计划', { timeout: 10000 });

    // --- 4. 点击日程格 → 原生 prompt 被接受 → POST /api/schedule/daily ---
    await page.click('#schedGrid .sched-slot[data-slot="am1"]');
    await expect.poll(() => dailyPostBodies.length, { timeout: 15000 }).toBe(1);
    expect(dailyPostBodies[0]).toEqual({
      date: todayStr,
      slot_id: 'am1',
      activity: '合成槽位活动',
    });
    expect(dialogs.some((d) => d.type === 'prompt' && d.message === '活动名称:')).toBe(true);
    await expect(page.locator('#toastContainer .toast').last())
      .toContainText('已保存', { timeout: 8000 });

    // --- 5. 打开活动管理器 → GET /api/schedule/activities → 列表渲染 ---
    await page.click('#page-schedule button[onclick="openActivityMgr()"]');
    await expect(page.locator('#activityMgrModal')).not.toHaveClass(/hidden/, { timeout: 10000 });
    await expect(page.locator('#activityList .activity-row')).toHaveCount(1, { timeout: 15000 });
    await expect(page.locator('#activityList')).toContainText('合成晨读', { timeout: 10000 });

    // --- 6. 添加活动 → 捕获 POST payload 精确为 name/type/duration_minutes ---
    await page.fill('#activityNewName', '合成新增活动');
    await page.fill('#activityNewType', 'study');
    await page.fill('#activityNewDuration', '45');
    await page.click('#activityAddBtn');
    await expect.poll(() => activityPostBodies.length, { timeout: 15000 }).toBe(1);
    expect(activityPostBodies[0]).toEqual({
      name: '合成新增活动',
      type: 'study',
      duration_minutes: 45,
    });
    await expect(page.locator('#toastContainer .toast').last())
      .toContainText('活动已添加', { timeout: 8000 });
    // 列表刷新（真实 GET 再次发生），新增活动可见。
    await expect(page.locator('#activityList .activity-row')).toHaveCount(2, { timeout: 15000 });
    await expect(page.locator('#activityList')).toContainText('合成新增活动', { timeout: 10000 });
    // 名称输入框被清空。
    await expect(page.locator('#activityNewName')).toHaveValue('', { timeout: 10000 });

    // --- 7. 删除活动：确认对话框被接受 → DELETE /api/schedule/activities/:id ---
    await page.click('#activityList .activity-del-btn[data-id="7"]');
    await expect.poll(() => activityDeleteUrls.length, { timeout: 15000 }).toBe(1);
    expect(activityDeleteUrls[0]).toMatch(/\/api\/schedule\/activities\/7$/);
    expect(dialogs.some(
      (d) => d.type === 'confirm' && d.message.includes('合成晨读'),
    )).toBe(true);
    await expect(page.locator('#toastContainer .toast').last())
      .toContainText('已删除', { timeout: 8000 });
    // 列表刷新：被删活动消失。
    await expect(page.locator('#activityList .activity-row')).toHaveCount(1, { timeout: 15000 });
    await expect(page.locator('#activityList')).not.toContainText('合成晨读', { timeout: 10000 });

    // --- 8. 唯一实现归属：classic 层不得再直连 /api/schedule/* ---
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    expect(appJsText).not.toMatch(/['"]\/api\/schedule/);
    // 旧全局入口名必须继续可用（HTML inline onclick + app.js 调用点）。
    expect(appJsText).toContain('renderSchedule');
    expect(appJsText).toContain('shiftDate');
    expect(appJsText).toContain('openActivityMgr');
    expect(appJsText).toContain('closeActivityMgr');
    expect(appJsText).toContain('addActivity');

    const ownerJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'modules', 'schedule', 'index.js'), 'utf8');
    expect(ownerJsText).toContain('/api/schedule/slots');
    expect(ownerJsText).toContain('/api/schedule/weekly');
    expect(ownerJsText).toContain('/api/schedule/daily');
    expect(ownerJsText).toContain('/api/schedule/activities');

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });

  test('Q) real task editor: ESM owner loaded and card type semantics preserved', async ({ page, context }) => {
    test.skip(!factoryHandle, 'factory fixture not booted');
    const baseUrl = factoryHandle.baseUrl;
    await installSafetyRoutes(context, baseUrl);

    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // --- synthetic 受测 API（注册在 installSafetyRoutes 之后）---
    const taskPosts = [];
    const taskPuts = [];
    // 一张 task_type='normal' 的旧任务（历史值 → 显示侧归一为 standard）。
    const legacyTask = {
      id: 7,
      name: '合成旧卡',
      description: '合成描述',
      category: 'study',
      priority: 5,
      estimated_time: 30,
      repeat_type: 'none',
      task_profile: 'deadline_flexible',
      resistance: 'medium',
      energy_required: 'medium',
      deadline: null,
      tags: [],
      prerequisite_ids: [],
      task_type: 'normal',
      completed: false,
      is_unlocked: true
    };

    await context.route(/\/api\/tasks(\?|$)/, async (route) => {
      const req = route.request();
      const method = req.method();
      if (method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([legacyTask])
        });
      }
      if (method === 'POST') {
        let parsed = null;
        try { parsed = JSON.parse(req.postData() || '{}'); } catch (_e) { parsed = null; }
        taskPosts.push(parsed);
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 101, name: (parsed && parsed.name) || '' })
        });
      }
      return route.fallback();
    });

    await context.route(/\/api\/tasks\/\d+$/, async (route) => {
      const req = route.request();
      if (req.method() !== 'PUT') return route.fallback();
      let parsed = null;
      try { parsed = JSON.parse(req.postData() || '{}'); } catch (_e) { parsed = null; }
      taskPuts.push(parsed);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });

    await context.route(/\/api\/tags(\?|$)/, async (route) => {
      if (route.request().method() !== 'GET') return route.fallback();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await context.route(/\/api\/knowledge\/notes(\?|$)/, async (route) => {
      if (route.request().method() !== 'GET') return route.fallback();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    // --- 1. editor.js 真的被加载（HTTP 200）---
    const editorResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/static/modules/tasks/editor.js')) {
        editorResponses.push({ status: res.status(), url: res.url() });
      }
    });
    const editorResponseWait = page.waitForResponse(
      (r) => r.url().includes('/static/modules/tasks/editor.js'),
      { timeout: 20000 }
    );

    await page.goto(baseUrl + '/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#salBootstrapOverlay')).toBeHidden({ timeout: 15000 });

    const editorResp = await editorResponseWait;
    expect(editorResp.status()).toBe(200);
    expect(editorResponses.length).toBeGreaterThanOrEqual(1);
    for (const r of editorResponses) {
      expect(r.status).toBe(200);
    }

    // --- 2. app.entry.js 在页面可交互前完成 owner 绑定 ---
    await page.waitForFunction(
      () => typeof window.openTaskEdit === 'function' &&
            typeof window.buildDepList === 'function' &&
            typeof window.addTagChip === 'function' &&
            typeof window.saveTask === 'function' &&
            typeof window.deleteCurrentTask === 'function',
      null,
      { timeout: 15000 }
    );

    // --- 3. 新建任务：模态框同步打开，卡类型默认 standard ---
    await page.click('.nav-btn[data-page="tasks"]');
    await expect(page.locator('#page-tasks')).toHaveClass(/active/);
    await page.click('#page-tasks button[onclick="openTaskEdit()"]');
    await expect(page.locator('#taskModal')).not.toHaveClass(/hidden/, { timeout: 10000 });
    await expect(page.locator('#tfCardType')).toHaveValue('standard', { timeout: 10000 });

    // 模态框是**同步**打开的：openTaskEdit 返回后 modal 已经可见。
    const syncOpen = await page.evaluate(() => {
      window.openTaskEdit();
      const modal = document.getElementById('taskModal');
      return {
        hidden: modal.classList.contains('hidden'),
        cardType: document.getElementById('tfCardType').value,
        original: window._tfOriginalCardType
      };
    });
    expect(syncOpen.hidden).toBe(false);
    expect(syncOpen.cardType).toBe('standard');
    expect(syncOpen.original).toBeNull();

    // --- 4. 新建保存 → POST 必须显式包含合法 task_type ---
    await page.fill('#tfName', '合成新任务');
    await page.selectOption('#tfCardType', 'standard');
    await page.click('#taskModal button[onclick="saveTask()"]');
    await expect.poll(() => taskPosts.length, { timeout: 15000 }).toBe(1);
    expect(taskPosts[0].task_type).toBe('standard');
    expect(['standard', 'free', 'micro', 'goal']).toContain(taskPosts[0].task_type);

    // --- 5. 编辑旧卡：下拉显示 standard，_tfOriginalCardType 为 standard ---
    const legacyState = await page.evaluate(() => {
      window.openTaskEdit(7);
      return {
        selectValue: document.getElementById('tfCardType').value,
        original: window._tfOriginalCardType
      };
    });
    expect(legacyState.selectValue).toBe('standard');
    expect(legacyState.original).toBe('standard');

    // --- 6. 不改卡类型直接保存 → PUT 必须**省略** task_type ---
    await page.fill('#tfName', '合成旧卡改个名');
    await page.click('#taskModal button[onclick="saveTask()"]');
    await expect.poll(() => taskPuts.length, { timeout: 15000 }).toBe(1);
    expect(taskPuts[0]).not.toHaveProperty('task_type');
    expect(taskPuts[0].name).toBe('合成旧卡改个名');

    // --- 7. 再次编辑并明确改为 free → PUT 必须含 task_type='free' ---
    await page.evaluate(() => { window.openTaskEdit(7); });
    await page.selectOption('#tfCardType', 'free');
    await page.fill('#tfName', '合成旧卡改自由卡');
    await page.click('#taskModal button[onclick="saveTask()"]');
    await expect.poll(() => taskPuts.length, { timeout: 15000 }).toBe(2);
    expect(taskPuts[1].task_type).toBe('free');

    // --- 8. 唯一实现归属：classic 层不得保留任务编辑器的影子实现 ---
    const appJsText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'app.js'), 'utf8');
    expect(appJsText).not.toMatch(/function\s+openTaskEdit\s*\(/);
    expect(appJsText).not.toMatch(/function\s+saveTask\s*\(/);
    expect(appJsText).not.toMatch(/function\s+buildDepList\s*\(/);
    expect(appJsText).not.toMatch(/function\s+deleteCurrentTask\s*\(/);
    expect(appJsText).toContain('function normalizeCardType(');

    const editorOwnerText = fs.readFileSync(
      path.join(E2E_DIR, '..', '..', 'static', 'modules', 'tasks', 'editor.js'), 'utf8');
    expect(editorOwnerText).toContain('export function createTaskEditorOwner(');

    // 全程无未捕获页面异常。
    expect(pageErrors).toEqual([]);
  });
});