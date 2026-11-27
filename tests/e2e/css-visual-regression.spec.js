/**
 * tests/e2e/css-visual-regression.spec.js
 *
 * AR03-P4 —— CSS 视觉回归对比（6 页 × 2 主题 × 2 视口）。
 *
 * 目的
 * ----
 * 六文件重组会改变**规则在 cascade 中的全局位置**。仅比对"迁移前 / 迁移后
 * 的规则文本"不足以证明没有视觉回归 —— 必须验证**最终计算样式**一致。
 *
 * 方法（A/B 同页对比）
 * ---------------------
 *   在**同一个页面、同一份 DOM、同一套主题与视口**下：
 *     1. 先加载**迁移后的 6 个 CSS 文件**，采样所有关键选择器的计算样式；
 *     2. 再**移除这 6 个 <link>**，注入**迁移前的内联 CSS**（来自
 *        tests/fixtures/css_visual_baseline.json 记录的原始 CSS 文本），
 *        在**完全相同的状态**下再采样一次；
 *     3. 逐属性比对两次采样。
 *
 *   这样比对的双方是**同一状态下的计算样式**，避开了"声明 vs 计算值"的
 *   不可比性（rem→px、hex→rgb()、状态相关选择器等），
 *   也天然排除了隔离沙箱布局差异的影响。
 *
 *   Dark 主题必须**完全一致**。
 *   Light 主题允许**仅限预期白名单**内的差异（本次 Theme 收敛刻意
 *   修改的 19 处 hover / 强调态），其余必须一致。
 *
 * Server fixture: tests/e2e/factory-sandbox-server.py
 *   - 100% TEMP 合成根；静态白名单已包含 'css' 与 'assets'
 *   - 绑定 127.0.0.1:<random>；绝不 5000；绝不公网
 *
 * 约束
 * ----
 * - **绝不**读取 / 写入生产 DB、WAL/SHM、Vault、config。
 * - 本 spec **不写**任何生产文件；只读 fixtures。
 */

const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const E2E_DIR = __dirname;
const FIXTURE_PATH = path.join(E2E_DIR, 'factory-sandbox-server.py');
const PROJECT_ROOT = path.resolve(E2E_DIR, '..', '..');
const BASELINE_PATH = path.join(
  PROJECT_ROOT,
  'tests',
  'fixtures',
  'css_visual_baseline.json',
);
const CASCADE_BASELINE_PATH = path.join(
  PROJECT_ROOT,
  'tests',
  'fixtures',
  'css_cascade_baseline.json',
);

if (!fs.existsSync(FIXTURE_PATH)) {
  throw new Error('factory-sandbox-server.py missing at ' + FIXTURE_PATH);
}
if (!fs.existsSync(BASELINE_PATH)) {
  throw new Error('css_visual_baseline.json missing at ' + BASELINE_PATH);
}

const BASELINE = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'));

/** 6 个代表性页面（对应 .page 切换）。 */
const PAGES = ['gacha', 'tasks', 'schedule', 'knowledge', 'schedule', 'config'];

/** 2 个视口。 */
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 720 },
  { name: 'mobile', width: 390, height: 844 },
];

/** 抽样比对的关键属性（覆盖颜色 / 间距 / 边框 / 排版 / 布局）。 */
const PROPS = [
  'color',
  'background-color',
  'border-top-color',
  'border-top-width',
  'border-top-left-radius',
  'border-radius',
  'margin-top',
  'margin-bottom',
  'padding-top',
  'padding-left',
  'gap',
  'display',
  'font-size',
  'font-weight',
  'font-family',
  'line-height',
  'opacity',
  'flex-direction',
  'justify-content',
  'align-items',
  'text-align',
  'box-shadow',
  'transition-duration',
  'z-index',
  'position',
];

/**
 * Light 主题下**预期**会变化的选择器（AR03-P4 §3.3 的语义化收敛）。
 * key = 选择器，value = 允许变化的属性列表（kebab-case）。
 */
const LIGHT_EXPECTED_DIFFS = {
  '.nav-btn:hover': ['background-color'],
  '.card:hover': ['border-top-color', 'border-top-width'],
  '.sched-slot:hover': ['background-color'],
  '.cat-item:hover': ['background-color'],
  '.note-item:hover': ['background-color'],
  '.prompt-file-item:hover, .prompt-file-item.active': ['background-color'],
  '.agent-ro-item:hover, .agent-ro-item.active': ['background-color'],
  '.nav-btn.active': ['background-color'],
  '.cat-item.active': ['background-color'],
  '.feedback-emoji button:hover, .feedback-emoji button.sel': ['background-color'],
  '.feedback-option:hover, .feedback-option.sel': ['background-color'],
  '.agent-ro-tab.active': ['background-color'],
  '.replace-reason input:checked + label': ['background-color'],
  'button.gacha-multi-item:hover, .gacha-multi-item:hover': ['background-color'],
  'button.gacha-multi-item[aria-pressed="true"], .gacha-multi-item.activated': [
    'background-color',
  ],
  '.bg-gold': ['background-color'],
  '.tag-chip': ['background-color'],
  '.gacha-multi-item-tag': ['background-color'],
  '.btn.danger': ['background-color'],
};

// ---------------------------------------------------------------------------
// 迁移前的内联 CSS（从基线重建）
// ---------------------------------------------------------------------------

/**
 * 重建迁移前的内联 CSS 文本。
 *
 * 来源：tests/fixtures/css_cascade_baseline.json 的 `preMigrationCss`
 * 字段（由 scripts/capture_css_baselines.js 在迁移前抓取）。
 * 若该字段缺失 → 直接失败（不能跳过，否则测试会"永远通过"）。
 */
function loadPreMigrationCss() {
  if (!fs.existsSync(CASCADE_BASELINE_PATH)) {
    throw new Error('css_cascade_baseline.json missing');
  }
  const cascade = JSON.parse(fs.readFileSync(CASCADE_BASELINE_PATH, 'utf8'));
  const css = cascade.preMigrationCss;
  if (!css || typeof css !== 'string' || css.length < 1000) {
    throw new Error(
      'css_cascade_baseline.json 缺少 preMigrationCss —— 无法做 A/B 对比',
    );
  }
  return css;
}

// ---------------------------------------------------------------------------
// 合成服务器 fixture
// ---------------------------------------------------------------------------

function startFactory() {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const venvPy = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
  const candidate = fs.existsSync(venvPy) ? venvPy : py;

  const child = spawn(candidate, ['-B', FIXTURE_PATH, '--print-url'], {
    cwd: E2E_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

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
        `factory fixture exited early rc=${code}\nstdout:\n${stdoutAll}\nstderr:\n${stderrAll}`,
      ));
    };
    child.once('exit', onExit);
    child.once('error', (err) => {
      if (resolved) return;
      resolved = true;
      reject(err);
    });

    const timer = setInterval(() => {
      const lines = stdoutAll.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      // fixture 打印 "URL:http://127.0.0.1:<port>"
      const urlLine = lines.find((l) => /^URL:https?:\/\/127\.0\.0\.1:\d+/.test(l));
      if (urlLine) {
        clearInterval(timer);
        resolved = true;
        const baseURL = urlLine.replace(/^URL:/, '').replace(/\/$/, '');
        resolve({
          baseURL,
          tempRoot: (lines.find((l) => l.startsWith('TMPDIR:')) || '').replace(
            /^TMPDIR:/,
            '',
          ),
          stop: () => {
            try { child.kill(); } catch (e) { /* ignore */ }
          },
        });
      }
    }, 120);

    // 启动超时守卫
    setTimeout(() => {
      if (resolved) return;
      resolved = true;
      clearInterval(timer);
      reject(new Error(
        `factory fixture 未在 90s 内就绪\nstdout:\n${stdoutAll}\nstderr:\n${stderrAll}`,
      ));
    }, 90000);
  });
}

let factory = null;

test.beforeAll(async () => {
  factory = await startFactory();
});

test.afterAll(async () => {
  if (factory && factory.stop) factory.stop();
});

// ---------------------------------------------------------------------------
// 页面内采样
// ---------------------------------------------------------------------------

/**
 * 采样当前页面的计算样式。
 *
 * 关键：**返回元素引用**（而非仅样式值），让"迁移前"与"迁移后"两次采样
 * 比对**完全相同的 DOM 节点**。否则应用 JS 的异步渲染（任务列表等）
 * 会在两次采样之间改变 DOM，导致比对的是不同元素 → 假差异。
 *
 * 可见性判定：**不依赖布局**（getBoundingClientRect / getClientRects）——
 * 隔离沙箱里某些容器（timer-dock 等）尚未被 JS 填充，布局尺寸为 0，
 * 用尺寸判可见会让采样近乎空跑 → 测试"永远通过"而失去意义。
 * 改为：元素存在且 display !== none 且 visibility !== hidden 即采。
 */
async function sampleElements(page, selectors) {
  return page.evaluate((sels) => {
    const scope = document.querySelector('.page.active') || document.body;
    const picked = [];
    for (const sel of sels) {
      let els = [];
      try {
        els = Array.from(scope.querySelectorAll(sel));
      } catch (e) {
        els = [];
      }
      if (!els.length) {
        try {
          els = Array.from(document.querySelectorAll(sel));
        } catch (e) {
          els = [];
        }
      }
      if (!els.length) continue;

      let el = null;
      for (const cand of els) {
        const c = getComputedStyle(cand);
        if (c.display === 'none' || c.visibility === 'hidden') continue;
        el = cand;
        break;
      }
      if (el) picked.push({ sel, el });
    }
    // 给元素打上唯一标记，供第二次采样按标记定位同一节点
    picked.forEach((p, i) => {
      p.el.setAttribute('data-cssvr-idx', String(i));
    });
    return picked.map((p) => p.sel);
  }, selectors);
}

/** 按标记读取已定位元素的计算样式。 */
async function readStylesOfMarked(page, props) {
  return page.evaluate((ps) => {
    const out = {};
    const nodes = document.querySelectorAll('[data-cssvr-idx]');
    for (const n of nodes) {
      const idx = n.getAttribute('data-cssvr-idx');
      const cs = getComputedStyle(n);
      const rec = {};
      for (const p of ps) rec[p] = cs.getPropertyValue(p);
      out[idx] = rec;
    }
    return out;
  }, props);
}

/** 逐页切换并采样，返回 { pageName: { selector: { prop: value } } }。 */
async function sampleAllPages(page, selectors) {
  const perPage = {};
  for (const pageName of PAGES) {
    const activated = await page.evaluate((p) => {
      const all = Array.from(document.querySelectorAll('.page'));
      const el = all.find(
        (x) => x.id === p || x.id === `page-${p}` ||
               x.getAttribute('data-page') === p,
      );
      if (!el) return false;
      all.forEach((x) => x.classList.remove('active'));
      el.classList.add('active');
      return true;
    }, pageName);

    if (!activated) continue;

    await page.waitForTimeout(450); // 等 fadeIn (0.3s) 结束
    perPage[pageName] = await sampleElements(page, selectors);
  }
  return perPage;
}

// ---------------------------------------------------------------------------
// 视觉回归
// ---------------------------------------------------------------------------

test.describe('CSS 视觉回归 A/B 对比（6 页 × 2 主题 × 2 视口）', () => {
  for (const viewport of VIEWPORTS) {
    for (const theme of ['dark', 'light']) {
      test(`视口 ${viewport.name} / 主题 ${theme} —— 迁移前后计算样式一致`, async ({ browser }) => {
        const preMigrationCss = loadPreMigrationCss();

        const context = await browser.newContext({
          viewport: { width: viewport.width, height: viewport.height },
        });
        const page = await context.newPage();

        // CSS 文件加载错误（404 等）—— 任何失败都必须让测试失败。
        //
        // ⚠️ 只把 **4xx / 5xx** 当作错误：304 Not Modified 是**成功**的
        // 条件请求响应。禁用再启用 <link> 会让浏览器重新校验，
        // 从而拿到 304 —— 那是正常行为，不是加载失败。
        const cssErrors = [];
        page.on('response', (res) => {
          const url = res.url();
          if (!url.includes('/static/css/')) return;
          const st = res.status();
          if (st >= 400) cssErrors.push(`${st} ${url}`);
        });

        await page.goto(factory.baseURL + '/', { waitUntil: 'networkidle' });

        // 首次启动引导（bootstrap-first-card.js）在 Agent 策略未批准时会给
        // <html> 加 .sal-bootstrap-pending，并用
        //   html.sal-bootstrap-pending body > *:not(#salBootstrapOverlay)
        //     { display: none !important; }
        // 隐藏整个应用。隔离沙箱里 /api/agent-policy/status 不会返回
        // initialized=true → 页面永远处于"隐藏"态 → 所有元素 display:none
        // → 计算样式采样全是噪声（连新建的 div 都算成 none）。
        //
        // 本测试只关心**样式层**，因此移除该遮蔽类，露出真实 DOM。
        await page.evaluate(() => {
          document.documentElement.classList.remove('sal-bootstrap-pending');
          const ov = document.getElementById('salBootstrapOverlay');
          if (ov && ov.parentNode) ov.parentNode.removeChild(ov);
        });
        await page.waitForTimeout(200);

        await page.evaluate((props) => { window.__CSS_PROPS__ = props; }, PROPS);

        // 切换主题
        await page.evaluate((t) => {
          document.documentElement.setAttribute('data-theme', t);
        }, theme);

        // ⚠️ 关闭所有过渡 / 动画。
        //
        // 应用的很多控件带 `transition: 0.2s`。切换主题、替换样式表都会
        // 触发过渡动画，而 getComputedStyle 返回的是**动画中间值**
        // （实测 .nav-btn.active 的 background-color 被读成
        //  rgba(237,190,63,0.106) —— 0.1 与 0.18 之间的插值帧）。
        // 这会让 A/B 比对出现**假差异**。
        //
        // 该覆盖样式在 A / B 两个阶段**都生效**，因此不引入偏差 ——
        // 它只是把"过渡动画"这个与迁移无关的时间维度从比对中剔除。
        await page.evaluate(() => {
          const s = document.createElement('style');
          s.id = '__cssvr_no_transition__';
          s.textContent =
            '*, *::before, *::after { transition: none !important; animation: none !important; }';
          document.head.appendChild(s);
        });

        // ⚠️ 必须等一次**渲染更新**（double rAF）后再采样。
        //
        // Chromium 的 getComputedStyle 返回的是**上次提交**的样式值，不是
        // 立即重算的值。切换 data-theme 后，:root 上的自定义属性会立刻变，
        // 但**继承**这些变量的元素（input / select / button 等）的计算样式
        // 要等到下一次渲染更新才刷新 —— 实测：
        //   setAttribute('data-theme','dark') 后立即读 → 仍是 light 的颜色
        //   300ms 后再读        → 才是 dark 的颜色
        // 强制 layout（offsetHeight）**无效**。因此用双 rAF 等渲染生命周期。
        await page.evaluate(
          () =>
            new Promise((resolve) => {
              requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
            }),
        );

        const selectors = Object.keys(BASELINE.declarations);

        // --- A/B 对比：分三段，每段之间等一次渲染更新 ---
        //
        // ① 定位元素 + 采样 A（迁移后的 6 个 CSS 文件）
        // ② 换成迁移前的内联 CSS
        // ③ 采样 B（迁移前的内联 CSS）
        //
        // 两处关键点：
        //
        // (a) **元素引用存在 window 上跨 evaluate 复用** —— 比对必须是
        //     同一批 DOM 节点，否则应用 JS 的异步重绘会让两次采样落在
        //     不同元素上 → 假差异。
        //
        // (b) **每段之间等一次 double rAF** —— Chromium 的 getComputedStyle
        //     返回的是**上次提交**的样式值。替换样式表 / 切换主题后，
        //     继承变量的元素要等下一次渲染更新才刷新（实测强制 layout
        //     无效，必须走 rAF）。不等就会读到过期值 → 假差异。

        // ① 定位元素（跨 evaluate 保存引用）+ 采样 A
        await page.evaluate(
          ([sels]) => {
            window.__cssvrNodes = {};
            window.__cssvrSels = {};
            const collectNodes = () => {
              const scope = document.querySelector('.page.active') || document.body;
              const picked = [];
              for (const sel of sels) {
                let els = [];
                try {
                  els = Array.from(scope.querySelectorAll(sel));
                } catch (e) {
                  els = [];
                }
                if (!els.length) {
                  try {
                    els = Array.from(document.querySelectorAll(sel));
                  } catch (e) {
                    els = [];
                  }
                }
                if (!els.length) continue;
                for (const cand of els) {
                  const c = getComputedStyle(cand);
                  if (c.display === 'none' || c.visibility === 'hidden') continue;
                  picked.push({ sel, el: cand });
                  break;
                }
              }
              return picked;
            };

            const allPages = Array.from(document.querySelectorAll('.page'));
            for (const pg of allPages) {
              allPages.forEach((x) => x.classList.remove('active'));
              pg.classList.add('active');
              const nodes = collectNodes();
              nodes.forEach((p, i) => {
                p.el.__cssvrIdx = String(i);
              });
              window.__cssvrNodes[pg.id] = nodes.map((p) => p.el);
              window.__cssvrSels[pg.id] = nodes.map((p) => p.sel);
            }
            return true;
          },
          [selectors],
        );

        const afterByPage = await page.evaluate(
          ([props]) => {
            const out = {};
            const allPages = Array.from(document.querySelectorAll('.page'));
            for (const pg of allPages) {
              allPages.forEach((x) => x.classList.remove('active'));
              pg.classList.add('active');
              const rec = {};
              for (const el of window.__cssvrNodes[pg.id] || []) {
                const cs = getComputedStyle(el);
                const r = {};
                for (const p of props) r[p] = cs.getPropertyValue(p);
                rec[el.__cssvrIdx] = r;
              }
              out[pg.id] = rec;
            }
            return out;
          },
          [PROPS],
        );

        // ② 换成迁移前的内联 CSS
        //
        // 用 `link.disabled = true` **禁用**迁移后的样式表，而不是 remove()。
        // remove() 后再 append 会触发重新请求（304 Not Modified），
        // 既污染"CSS 加载失败"断言，又多一次网络往返。
        // `<link rel="stylesheet" disabled>` 会完整地退出层叠。
        await page.evaluate(
          ([preCss]) => {
            const links = Array.from(
              document.querySelectorAll('link[href*="/static/css/"]'),
            );
            links.forEach((l) => {
              l.dataset.cssvrWasDisabled = l.disabled ? '1' : '';
              l.disabled = true;
            });
            const preStyle = document.createElement('style');
            preStyle.id = '__premigration_css__';
            preStyle.textContent = preCss;
            document.head.appendChild(preStyle);
            window.__cssvrRestore = () => {
              preStyle.remove();
              links.forEach((l) => {
                l.disabled = l.dataset.cssvrWasDisabled === '1';
              });
            };
            return true;
          },
          [preMigrationCss],
        );

        // 等一次渲染更新，让新样式真正生效
        await page.evaluate(
          () =>
            new Promise((resolve) => {
              requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
            }),
        );

        // ③ 采样 B（迁移前的内联 CSS，**同一批元素引用**）
        const beforeByPage = await page.evaluate(
          ([props]) => {
            const out = {};
            const allPages = Array.from(document.querySelectorAll('.page'));
            for (const pg of allPages) {
              allPages.forEach((x) => x.classList.remove('active'));
              pg.classList.add('active');
              const rec = {};
              for (const el of window.__cssvrNodes[pg.id] || []) {
                const cs = getComputedStyle(el);
                const r = {};
                for (const p of props) r[p] = cs.getPropertyValue(p);
                rec[el.__cssvrIdx] = r;
              }
              out[pg.id] = rec;
            }
            return out;
          },
          [PROPS],
        );

        // 还原迁移后的 CSS（保持页面状态干净）
        await page.evaluate(() => {
          if (window.__cssvrRestore) window.__cssvrRestore();
        });

        const selsByPage = await page.evaluate(() => window.__cssvrSels || {});

        expect(cssErrors, 'CSS 文件加载失败（404 等）').toEqual([]);

        // 页面必须处于"可见"态：否则所有元素 display:none，采样全是噪声。
        const appVisible = await page.evaluate(() => {
          const probe = document.createElement('div');
          probe.style.display = 'inline-flex';
          document.body.appendChild(probe);
          const d = getComputedStyle(probe).display;
          probe.remove();
          return d === 'inline-flex';
        });
        expect(
          appVisible,
          '应用仍处于隐藏态（bootstrap 遮蔽未解除？）→ 采样无意义',
        ).toBe(true);

        // 采样覆盖率守卫：比对不能是空跑
        const sampledCount = Object.values(beforeByPage)
          .reduce((n, s) => n + Object.keys(s).length, 0);
        expect(
          sampledCount,
          `采样到的元素过少（${sampledCount}）→ 比对近乎空跑，测试无意义`,
        ).toBeGreaterThanOrEqual(15);

        // --- 逐属性比对（同一批 DOM 节点） ---
        const diffs = [];
        for (const pageId of Object.keys(beforeByPage)) {
          const beforeRec = beforeByPage[pageId] || {};
          const afterRec = afterByPage[pageId] || {};
          const sels = selsByPage[pageId] || [];
          for (const [idx, bRec] of Object.entries(beforeRec)) {
            const aRec = afterRec[idx];
            if (!bRec || !aRec) continue;
            const sel = sels[Number(idx)];
            for (const prop of PROPS) {
              const bv = bRec[prop];
              const av = aRec[prop];
              if (bv === undefined || av === undefined) continue;
              if (bv === av) continue;

              const allowed =
                theme === 'light' &&
                LIGHT_EXPECTED_DIFFS[sel] &&
                LIGHT_EXPECTED_DIFFS[sel].includes(prop);

              diffs.push({
                page: pageId,
                selector: sel,
                property: prop,
                before: bv,
                after: av,
                allowed,
              });
            }
          }
        }

        const unexpected = diffs.filter((d) => !d.allowed);
        expect(
          unexpected,
          `发现非预期的计算样式差异（${unexpected.length} 项）：\n` +
            unexpected
              .slice(0, 25)
              .map(
                (d) =>
                  `  [${d.page}] ${d.selector} { ${d.property}: ` +
                  `${d.before} → ${d.after} }`,
              )
              .join('\n'),
        ).toEqual([]);

        // 反向守卫：Light 模式**必须真的观测到**语义化收敛带来的差异。
        //
        // 如果一条都没观测到，说明 ① 白名单写错了选择器，或 ② 采样根本没
        // 覆盖到那些元素 —— 那样这个测试就退化成"什么都没比对"的空跑，
        // 失去意义。所以这里要求 light 至少命中 N 条预期差异。
        if (theme === 'light') {
          const allowedDiffs = diffs.filter((d) => d.allowed);
          expect(
            allowedDiffs.length,
            'Light 模式未观测到任何预期的语义化收敛差异 → ' +
              '白名单选择器可能写错，或采样未覆盖（测试退化为空跑）',
          ).toBeGreaterThanOrEqual(5);
        }

        await context.close();
      });
    }
  }
});
