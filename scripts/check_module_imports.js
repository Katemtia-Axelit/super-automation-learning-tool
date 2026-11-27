#!/usr/bin/env node
// scripts/check_module_imports.js - 模块边界机械检查（P1 切片 5 / AR03-P3-E）
//
// 目的
// ----
// 把架构文档 §4.2 的模块边界 **变成可执行断言**，而不是靠人盯：
//
//   ① Feature 模块必须导出 `meta` / `mount` / `unmount`；
//   ② `modules/*` 之间不得直接 import 他模块的 **内部文件**
//      （只允许 `index.js` 公共入口）；
//   ③ `core/*` 不得 import `modules/*`（**内核不反向依赖业务**）；
//   ④ `core/*` 与 `shared/*` 的公共 helper（escapeHtml / toast / api …）
//      **不得**在 classic 层被重复实现（唯一权威）。
//
// AR03-P3-E 新增（消除「边界只靠人盯」的缺口 F）：
//
//   ⑤ **循环依赖检测**：Feature 模块之间的 import 图做 DFS，找环 → 报错。
//   ⑥ **唯一状态所有权**：`modules/*` 内不得出现 `window.<x> = ` 形式的
//      可写全局状态写入（owner 状态必须闭包私有）。
//   ⑦ **app.js 业务收敛白名单**：`static/app.js` 的可写全局 **必须**
//      在白名单里登记；新增未登记的业务实现 → 报错（防止单体重新膨胀）。
//   ⑧ **应用级 / 页面级生命周期分级**：app-scoped 模块不得实现页面级
//      `mount`/`unmount`；页面级模块的 `unmount` 不得清理 app-scoped 状态。
//
// 用法
// ----
//   node scripts/check_module_imports.js          # 人类可读报告
//   node scripts/check_module_imports.js --json   # 机器可读
//
// 退出码
// ----
//   0 = 全部通过；1 = 存在违规（逐条打印）。
//
// 约束
// ----
// 本脚本 **只读** 仓库；不写任何文件；不触碰生产 DB / config / notes。

'use strict';

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const STATIC_ROOT = path.join(PROJECT_ROOT, 'static');
const CORE_DIR = path.join(STATIC_ROOT, 'core');
const SHARED_DIR = path.join(STATIC_ROOT, 'shared');
const MODULES_DIR = path.join(STATIC_ROOT, 'modules');
const APP_JS = path.join(STATIC_ROOT, 'app.js');
const APP_ENTRY_JS = path.join(STATIC_ROOT, 'app.entry.js');

const violations = [];

function fail(rule, file, detail) {
  violations.push({ rule: rule, file: file, detail: detail });
}

function rel(absPath) {
  return path.relative(PROJECT_ROOT, absPath).replace(/\\/g, '/');
}

function listJsFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  const out = [];
  (function walk(current) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile() && entry.name.endsWith('.js')) out.push(full);
    }
  })(dir);
  return out.sort();
}

function read(file) {
  return fs.readFileSync(file, 'utf8');
}

// ---------------------------------------------------------------------------
// import / export 解析（静态 regex；只关心 specifier 形状，不做完整 AST）
// ---------------------------------------------------------------------------

function extractSpecifiers(source) {
  const specs = [];
  const staticRe = /(?:^|[\s;}])(?:import|export)\b[^'";]*?from\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = staticRe.exec(source)) !== null) specs.push(m[1]);
  const dynamicRe = /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
  while ((m = dynamicRe.exec(source)) !== null) specs.push(m[1]);
  return specs;
}

function functionBody(source, name) {
  const re = new RegExp(
    '(?:async\\s+)?function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{'
  );
  const m = re.exec(source);
  if (!m) return null;
  const start = m.index + m[0].length - 1;
  let depth = 0;
  for (let i = start; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    else if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  return source.slice(start);
}

// ---------------------------------------------------------------------------
// 规则 ①：Feature 模块契约
// ---------------------------------------------------------------------------

function featureModuleDirs() {
  if (!fs.existsSync(MODULES_DIR)) return [];
  return fs
    .readdirSync(MODULES_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => path.join(MODULES_DIR, e.name))
    .sort();
}

// ---------------------------------------------------------------------------
// 注册清单：**唯一** 权威 = static/app.entry.js 的 MODULE_CONTRACTS
// ---------------------------------------------------------------------------
// static/modules 下有两类模块，必须区别对待：
//   A. **Registry Feature 模块** —— 在 app.entry.js 的 MODULE_CONTRACTS 里
//      注册；必须满足 meta / mount / unmount 契约（架构文档 §4.1）。
//   B. **Owner 工厂模块** —— 导出 createXxxOwner(deps)；由 classic 层
//      经动态 import 使用，**不** 进入 registry（它们不是"页面模块"，
//      而是"业务 owner"）。
//
// 判定依据是 **机械** 的：app.entry.js 是注册的唯一入口，脚本直接读它。

function readRegistryModuleNames() {
  if (!fs.existsSync(APP_ENTRY_JS)) return [];
  const source = read(APP_ENTRY_JS);
  const block = /const\s+MODULE_CONTRACTS\s*=\s*\[([\s\S]*?)\];/.exec(source);
  if (!block) return [];
  const names = [];
  const re = /name\s*:\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(block[1])) !== null) names.push(m[1]);
  return names;
}

function checkFeatureModuleContract() {
  const registryNames = readRegistryModuleNames();
  const registrySet = new Set(registryNames);

  for (const dir of featureModuleDirs()) {
    const name = path.basename(dir);
    const index = path.join(dir, 'index.js');
    if (!fs.existsSync(index)) {
      fail('contract', rel(dir), '缺少 index.js（Feature 模块必须有公共入口）');
      continue;
    }
    const source = read(index);
    const isRegistryModule = registrySet.has(name);

    if (isRegistryModule) {
      // A. Registry Feature 模块：必须满足 meta / mount / unmount 契约。
      const hasNamed =
        /\bexport\s*\{[^}]*\bmeta\b[^}]*\}/.test(source) ||
        /\bexport\s+(?:const|let|var|function|async function)\s+meta\b/.test(source);
      const hasDefault = /\bexport\s+default\b/.test(source);
      if (!hasNamed && !hasDefault) {
        fail('contract', rel(index), '已注册进 registry，必须导出 meta / mount / unmount');
        continue;
      }
      const defaultBlock = /export\s+default\s*\{([^}]*)\}/.exec(source);
      if (defaultBlock) {
        const keys = defaultBlock[1]
          .split(',')
          .map((s) => s.split(':')[0].trim())
          .filter(Boolean);
        for (const required of ['meta', 'mount', 'unmount']) {
          if (!keys.includes(required)) {
            fail('contract', rel(index), 'default 导出缺少 ' + required);
          }
        }
      }
      for (const required of ['meta', 'mount', 'unmount']) {
        if (!new RegExp('\\b' + required + '\\b').test(source)) {
          fail('contract', rel(index), '缺少契约成员 ' + required);
        }
      }
    } else {
      // B. Owner 工厂模块：必须导出 createXxxOwner(deps)，且 **不得** 带
      //    registry 契约（避免"契约孤儿"：实现了契约却没人注册）。
      const hasOwnerFactory = /\bexport\s+function\s+create\w*Owner\s*\(/.test(source);
      if (!hasOwnerFactory) {
        fail(
          'contract',
          rel(index),
          '未注册进 registry 的模块必须是 owner 工厂（导出 createXxxOwner(deps)）'
        );
      }
      if (/\bexport\s*\{[^}]*\bmeta\b[^}]*\}/.test(source)) {
        fail(
          'contract',
          rel(index),
          '未注册进 registry 的模块不得实现 registry 契约（meta/mount/unmount）'
        );
      }
    }
  }

  // 注册清单里的每个名字都必须有对应模块目录。
  for (const name of registryNames) {
    if (!fs.existsSync(path.join(MODULES_DIR, name, 'index.js'))) {
      fail('contract', 'static/app.entry.js', '注册了不存在的模块：' + name);
    }
  }
}

// ---------------------------------------------------------------------------
// 规则 ②：跨模块不越界 import
// ---------------------------------------------------------------------------

function checkNoCrossModuleInternalImports() {
  const moduleDirs = featureModuleDirs();
  for (const dir of moduleDirs) {
    const owner = path.basename(dir);
    for (const file of listJsFiles(dir)) {
      const source = read(file);
      for (const spec of extractSpecifiers(source)) {
        if (!spec.startsWith('.')) continue;
        const resolved = path.resolve(path.dirname(file), spec);
        const parts = path
          .relative(MODULES_DIR, resolved)
          .split(path.sep)
          .filter(Boolean);
        if (parts.length < 2) continue;     // 同模块内部 import（允许）
        if (parts[0] === owner) continue;   // 自己模块内部（允许）
        const isPublicEntry = parts.length === 2 && parts[1] === 'index.js';
        if (!isPublicEntry) {
          fail(
            'cross-module',
            rel(file),
            '越界 import "' + spec + '"（跨模块只能 import 对方的 index.js 公共入口）'
          );
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 规则 ③：core / shared 不反向依赖 modules
// ---------------------------------------------------------------------------

function checkCoreDoesNotDependOnModules() {
  for (const file of [...listJsFiles(CORE_DIR), ...listJsFiles(SHARED_DIR)]) {
    const source = read(file);
    for (const spec of extractSpecifiers(source)) {
      const normalized = spec.replace(/\\/g, '/');
      if (normalized.includes('modules/') || normalized.startsWith('../modules')) {
        fail('core-no-backdep', rel(file), 'core/shared 不得 import 业务模块：' + spec);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 规则 ④ / ⑤：helper 唯一权威
// ---------------------------------------------------------------------------

//: 由 core/shared 提供的公共 helper（单一权威）。
const CORE_SINGLE_AUTHORITY = [
  { name: 'escapeHtml', file: 'core/ui/xss.js' },
  { name: 'toast', file: 'core/ui/toast.js' },
  { name: 'showModal', file: 'core/ui/modal.js' },
  { name: 'closeModal', file: 'core/ui/modal.js' },
];

//: classic 层允许保留的 **纯委托 facade**（函数体必须转发到 SAL.core.*）。
const ALLOWED_FACADES = ['static/app.js'];

function checkNoDuplicateHelperImplementations() {
  const classicFiles = [
    path.join(STATIC_ROOT, 'app.js'),
    path.join(STATIC_ROOT, 'free-task.js'),
  ].filter((f) => fs.existsSync(f));

  for (const file of classicFiles) {
    const source = read(file);
    const relFile = rel(file);
    const isFacade = ALLOWED_FACADES.includes(relFile);
    for (const helper of CORE_SINGLE_AUTHORITY) {
      const re = new RegExp(
        '(?:async\\s+)?function\\s+' + helper.name + '\\s*\\([^)]*\\)\\s*\\{',
        'g'
      );
      let m;
      while ((m = re.exec(source)) !== null) {
        const body = functionBody(source.slice(m.index), helper.name);
        if (body === null) continue;
        if (isFacade) {
          if (!/SAL\s*\.\s*core/.test(body)) {
            fail(
              'helper-single-authority',
              relFile,
              helper.name + ' 必须委托给 SAL.core.*（不得保留第二份实现）'
            );
          }
        } else {
          fail(
            'helper-single-authority',
            relFile,
            helper.name + ' 已在 ' + helper.file + ' 有唯一权威，不得重复实现'
          );
        }
      }
    }
  }
}

const APP_DELEGATED_HELPERS = ['api', 'toast', 'showModal', 'closeModal', 'escapeHtml'];

function checkAppJsDelegatesOnly() {
  if (!fs.existsSync(APP_JS)) return;
  const source = read(APP_JS);
  for (const name of APP_DELEGATED_HELPERS) {
    const body = functionBody(source, name);
    if (body === null) {
      fail('app-delegation', 'static/app.js', '缺少全局 helper：' + name);
      continue;
    }
    if (!/SAL\s*\.\s*core/.test(body)) {
      fail(
        'app-delegation',
        'static/app.js',
        name + ' 必须委托给 SAL.core.*（P1 切片 4：唯一权威）'
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 规则 ⑥（AR03-P3-E）：循环依赖检测
// ---------------------------------------------------------------------------
// Feature 模块之间的 import 图做 DFS 找环。
//
// 违规案例：modules/tasks/index.js import modules/gacha/index.js，且
// modules/gacha/index.js import modules/tasks/index.js —— 两者互相依赖，
// ESM 的 TDZ / 初始化顺序会让其中一方的顶层状态在对方执行时尚未就绪。
// 这种 bug 在运行时才暴露，且极难定位，因此必须 **机械** 拦截。

function buildModuleImportGraph() {
  const graph = new Map();
  for (const dir of featureModuleDirs()) {
    const name = path.basename(dir);
    const edges = new Set();
    for (const file of listJsFiles(dir)) {
      const source = read(file);
      for (const spec of extractSpecifiers(source)) {
        if (!spec.startsWith('.')) continue;
        const resolved = path.resolve(path.dirname(file), spec);
        const parts = path
          .relative(MODULES_DIR, resolved)
          .split(path.sep)
          .filter(Boolean);
        if (parts.length === 0) continue;
        const target = parts[0];
        if (target === name) continue;   // 自环在文件粒度由规则 ② 处理
        edges.add(target);
      }
    }
    graph.set(name, edges);
  }
  return graph;
}

function checkNoCircularModuleImports() {
  const graph = buildModuleImportGraph();
  const WHITE = 0, GREY = 1, BLACK = 2;
  const color = new Map();
  const stack = [];
  const reported = new Set();

  function reportCycle(node) {
    const idx = stack.indexOf(node);
    const cycle = stack.slice(idx >= 0 ? idx : 0).concat([node]);
    const key = cycle.slice(0, -1).sort().join('|');
    if (reported.has(key)) return;
    reported.add(key);
    fail(
      'circular-import',
      'static/modules/' + node + '/index.js',
      '循环依赖：' + cycle.join(' → ')
    );
  }

  function visit(node) {
    color.set(node, GREY);
    stack.push(node);
    const next = graph.get(node) || new Set();
    for (const child of Array.from(next).sort()) {
      if (!graph.has(child)) continue;
      const c = color.get(child) || WHITE;
      if (c === GREY) {
        reportCycle(child);
      } else if (c === WHITE) {
        visit(child);
      }
    }
    stack.pop();
    color.set(node, BLACK);
  }

  for (const node of Array.from(graph.keys()).sort()) {
    if ((color.get(node) || WHITE) === WHITE) visit(node);
  }
}

// ---------------------------------------------------------------------------
// 规则 ⑦（AR03-P3-E）：唯一状态所有权
// ---------------------------------------------------------------------------
// `modules/*` 内 **不允许** 出现 `window.<x> = ` 形式的可写全局状态写入。
//
// 违规案例：owner 把自己的 session 挂到 window 上（`window.__mySession = …`），
// 于是同一份状态存在两个所有者（闭包 + 全局），谁最后写谁赢，状态随时漂移。
// owner 状态必须 **闭包私有**，经显式 getter / setter 暴露。
//
// 例外：`window.SAL = window.SAL || {}` 是内核命名空间的 **幂等声明**
// （core/shared 层），不是业务状态写入。

function checkModulesHaveNoWritableGlobalState() {
  for (const file of listJsFiles(MODULES_DIR)) {
    const source = read(file);
    const re = /(?:^|[^\w.$])window\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)/g;
    let m;
    while ((m = re.exec(source)) !== null) {
      const name = m[1];
      if (name === 'SAL') continue;            // 内核命名空间幂等声明
      fail(
        'state-ownership',
        rel(file),
        'modules/* 内不得写全局状态 window.' + name +
        '（owner 状态必须闭包私有，经 getter/setter 暴露）'
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 规则 ⑧（AR03-P3-E）：app.js 可写全局白名单
// ---------------------------------------------------------------------------
// `static/app.js` 的 **可写全局** 必须登记在白名单里。
//
// 违规案例：迁移完自由卡后又在 app.js 里写 `window.__gachaCache = …` ——
// 一个未登记的全局业务状态，既逃过了 owner 化，又让"谁是权威"再次模糊。
//
// 白名单里的每一条都注明 **为什么**它必须留在全局（内联 handler 名字 /
// 装配接口 / 兼容别名），可被 review 逐条质疑。

const APP_JS_GLOBAL_WHITELIST = {
  // --- 内联 handler 依赖的既有入口名（src/index.html 的 onclick=…）---
  'resetReplaceChain': '换卡链入口（classic 层既有全局名）',
  'showReplaceReason': '换卡理由弹窗入口（classic 层既有全局名）',
  'readAllowRepeatReplaced': '换卡允许重复读取（classic 层既有全局名）',
  'doReplace': '换卡执行入口（classic 层既有全局名）',
  'renderDrawnCardResult': '抽卡结果渲染入口（classic 层既有全局名）',
  'onerror': '全局错误兜底（window.onerror）',

  // --- 装配接口：app.entry.js 需要它们来注入 owner ---
  '__setFreeCardOwner': '装配接口：注入自由卡 owner',
  '__createFreeCardOwner': '装配接口：创建自由卡 owner（依赖清单单一权威）',
  '__setTasksOwner': '装配接口：注入任务 owner',
  '__createTasksOwner': '装配接口：创建任务 owner（依赖清单单一权威）',
  '__setAllTasks': '装配接口：注入任务列表（窄 setter，owner 权威）',
  '__setAllTags': '装配接口：注入标签列表（窄 setter，owner 权威）',
  '__setTimerOwner': '装配接口：注入应用级计时 owner',
  '__createTimerOwner': '装配接口：创建应用级计时 owner（依赖清单单一权威）',
  '__getTimerOwnerSync': '装配接口：同步读取计时 owner（装配根判重用，避免重复创建）',
  '__getTasksOwnerSync': '装配接口：同步读取任务 owner（装配根判重用，避免重复创建）',
  '__getFreeCardOwnerSync': '装配接口：同步读取自由卡 owner（装配根判重用，避免重复创建）',

  // --- 诊断 / 兼容别名（只读快照或纯转发）---
  '_setMultiDrawResults': '装配接口：写入抽卡多抽结果（owner 权威）',
  '_getMultiDrawResults': '诊断只读 getter',
  '_setCurrentDrawnTask': '装配接口：写入当前抽中的任务（owner 权威）',
  '_getCurrentDrawnTask': '诊断只读 getter',
  '__tasksOwner': '诊断：暴露唯一 owner 实例（只读用途）'
};

//: 白名单里的全局必须是 **纯 facade / 窄 setter / 只读 getter**，
//: 不允许在 app.js 里直接挂一整段业务实现。
function checkAppJsGlobalWhitelist() {
  if (!fs.existsSync(APP_JS)) return;
  const source = read(APP_JS);
  const re = /(?:^|[^\w.$])window\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)/g;
  const seen = new Set();
  let m;
  while ((m = re.exec(source)) !== null) {
    const name = m[1];
    seen.add(name);
    if (!Object.prototype.hasOwnProperty.call(APP_JS_GLOBAL_WHITELIST, name)) {
      fail(
        'app-global-whitelist',
        'static/app.js',
        '未登记的可写全局 window.' + name +
        '（新业务实现必须落到 owner 模块；确需全局时先登记白名单并写明理由）'
      );
    }
  }
  // 白名单里的条目不得全部消失（说明入口被删，whitelist 已腐化）。
  for (const name of Object.keys(APP_JS_GLOBAL_WHITELIST)) {
    if (!seen.has(name)) {
      fail(
        'app-global-whitelist',
        'static/app.js',
        '白名单条目 window.' + name + ' 已不存在（请同步清理白名单）'
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 规则 ⑨（AR03-P3-E / AR03-P3-F）：应用级 vs 页面级生命周期分级
// ---------------------------------------------------------------------------
// 核心约束：**页面切换不得让跨页面的全局能力停止运行。**
//
// 违规案例：用户在任务页启动计时 → 切到别的页 → 若 timer 随任务页 unmount
// 而停 tick / 清 session，Dock 时间会停住，另一页也无法结束计时 ——
// 这是功能回归，不是架构洁癖。
//
// 因此：
//   - app-scoped 模块（timer / gacha）**不实现** 页面级 mount/unmount；
//   - 页面级模块的 unmount **不得** 触碰 app-scoped owner 的 session / tick。

//: app-scoped 模块名单的唯一权威 = app.entry.js 的 APP_SCOPED_MODULES。
const APP_SCOPED_MODULES_FALLBACK = ['timer', 'gacha'];

function readAppScopedModuleNames() {
  if (!fs.existsSync(APP_ENTRY_JS)) return APP_SCOPED_MODULES_FALLBACK.slice();
  const source = read(APP_ENTRY_JS);
  const block = /const\s+APP_SCOPED_MODULES\s*=\s*\[([\s\S]*?)\]/.exec(source);
  if (!block) return APP_SCOPED_MODULES_FALLBACK.slice();
  const names = [];
  const re = /['"]([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(block[1])) !== null) names.push(m[1]);
  return names;
}

function checkAppScopedLifecycleContract() {
  const appScoped = readAppScopedModuleNames();
  const appScopedSet = new Set(appScoped);

  for (const dir of featureModuleDirs()) {
    const name = path.basename(dir);
    const index = path.join(dir, 'index.js');
    if (!fs.existsSync(index)) continue;
    const source = read(index);

    if (appScopedSet.has(name)) {
      // app-scoped：不得实现页面级 mount/unmount 契约。
      const exportsRegistryContract =
        /\bexport\s*\{[^}]*\bmeta\b[^}]*\}/.test(source) ||
        /\bexport\s+default\s*\{[^}]*\bmount\b/.test(source);
      if (exportsRegistryContract) {
        fail(
          'lifecycle-tier',
          rel(index),
          name + ' 是应用级（app-scoped）模块，不得实现页面级 meta/mount/unmount 契约'
        );
      }
      // app-scoped 也不得进 registry 的页面挂载清单。
      const registryNames = readRegistryModuleNames();
      if (registryNames.includes(name)) {
        fail(
          'lifecycle-tier',
          'static/app.entry.js',
          name + ' 是应用级模块，不得注册进页面级 MODULE_CONTRACTS'
        );
      }
    }
  }

  // 页面级模块的 unmount 不得触碰 app-scoped owner 的 session / tick。
  const forbidden = [
    'stopInlineTimer',
    'clearSession',
    'tickHandle',
    'stopTick'
  ];
  for (const dir of featureModuleDirs()) {
    const name = path.basename(dir);
    if (appScopedSet.has(name)) continue;
    const index = path.join(dir, 'index.js');
    if (!fs.existsSync(index)) continue;
    const source = read(index);
    const unmountBody = functionBody(source, 'unmount');
    if (!unmountBody) continue;
    for (const token of forbidden) {
      if (unmountBody.indexOf(token) !== -1) {
        fail(
          'lifecycle-tier',
          rel(index),
          '页面级模块的 unmount 不得触碰应用级计时状态（出现 "' + token + '"）'
        );
      }
    }
    // 页面级 unmount 也不得直接调 owner 的 clear()（会清掉 session）。
    if (/\.\s*clear\s*\(\s*\)/.test(unmountBody)) {
      fail(
        'lifecycle-tier',
        rel(index),
        '页面级模块的 unmount 不得调用 owner.clear()（会清掉应用级 session）'
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 运行
// ---------------------------------------------------------------------------

checkFeatureModuleContract();
checkNoCrossModuleInternalImports();
checkCoreDoesNotDependOnModules();
checkNoDuplicateHelperImplementations();
checkAppJsDelegatesOnly();
checkNoCircularModuleImports();
checkModulesHaveNoWritableGlobalState();
checkAppJsGlobalWhitelist();
checkAppScopedLifecycleContract();

const moduleNames = featureModuleDirs().map((d) => path.basename(d));

if (process.argv.includes('--json')) {
  process.stdout.write(
    JSON.stringify(
      {
        modules: moduleNames,
        appScopedModules: readAppScopedModuleNames(),
        violations: violations,
        ok: violations.length === 0
      },
      null,
      2
    ) + '\n'
  );
} else {
  console.log('[check_module_imports] Feature 模块：' + moduleNames.join(', '));
  console.log(
    '[check_module_imports] 应用级模块：' + readAppScopedModuleNames().join(', ')
  );
  if (violations.length === 0) {
    console.log('[check_module_imports] 通过：模块边界无违规（退出码 0）');
  } else {
    console.error('[check_module_imports] 发现 ' + violations.length + ' 处违规：');
    for (const v of violations) {
      console.error('  [' + v.rule + '] ' + v.file + ' → ' + v.detail);
    }
  }
}

process.exit(violations.length === 0 ? 0 : 1);
