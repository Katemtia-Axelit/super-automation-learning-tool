'use strict';
/**
 * scripts/guard/protected_paths_guard.js
 * ---------------------------------------------------------------------------
 * 生产数据隔离守卫（Node 侧）。
 *
 * 为什么存在
 * ----------
 * 旧版 `scripts/run_e2e_isolated.js` 用 `fs.readFileSync()` **读取**生产
 * `data/task_publisher.db{,-wal,-shm}`、`config/config.json`、`src/notes/**`
 * 并计算 SHA-256，再比较运行前后是否一致。这违反了项目的最高数据保护要求：
 * **不读取、不写入、不复制、不哈希、不恢复**真实生产 SQLite 及其 WAL/SHM。
 * "用读取来证明没变"本身就是一次读取。
 *
 * 本守卫把证明方式从「事后观测」改成「**事前阻断**」：
 * 只要有任何代码试图打开受保护路径，立即抛错 —— 触碰即失败。
 *
 * 覆盖的调用面
 * ------------
 * - `fs.readFileSync` / `fs.openSync` / `fs.createReadStream`
 * - `fs.readdirSync` / `fs.readlinkSync` / `fs.realpathSync`
 * - `fs.promises.readFile` / `fs.promises.open` / `fs.promises.readdir`
 *
 * 受保护区域（相对项目根）
 * ------------------------
 * - `data/**`      —— 整个生产数据目录（含 `task_publisher.db` 三件套与任何备份）
 * - `config/**`    —— 整个生产配置目录（含 `config/config.json`）
 * - `src/notes/**` —— Obsidian 知识库
 *
 * 用法
 * ----
 *   // 作为模块
 *   const guard = require('./scripts/guard/protected_paths_guard.js');
 *   guard.install({ projectRoot: process.cwd() });
 *
 *   // 作为预加载（给子进程用）
 *   NODE_OPTIONS="--require <abs path>/scripts/guard/protected_paths_guard.js" \
 *   SAL_GUARD_ROOT="<abs project root>" node some-child.js
 *
 *   // 自检（证明守卫本身有效）
 *   node scripts/guard/protected_paths_guard.js --self-test
 */

const fs = require('fs');
const path = require('path');

/** 项目根目录下的受保护顶层目录。 */
const BLOCKED_TOP_DIRS = Object.freeze(['data', 'config']);

/** 项目根目录下的受保护子路径（多段）。 */
const BLOCKED_SUBPATHS = Object.freeze([['src', 'notes']]);

const STATE = {
  installed: false,
  projectRoot: null,
  violations: [],
  blocked: []
};

/** 依据 `__dirname` 推导默认项目根：`scripts/guard/x.js` → `<root>`。 */
function defaultProjectRoot() {
  return path.resolve(__dirname, '..', '..');
}

/** 把任意 fs 参数规范化为绝对路径；无法判定时返回 null。 */
function toAbsolute(candidate) {
  if (candidate === null || candidate === undefined) return null;
  if (typeof candidate === 'number') return null; // file descriptor
  let raw = candidate;
  try {
    if (Buffer.isBuffer(raw)) raw = raw.toString('utf8');
    else if (raw instanceof URL) raw = raw.pathname;
  } catch (err) {
    return null;
  }
  if (typeof raw !== 'string' || raw.length === 0) return null;
  try {
    return path.resolve(raw);
  } catch (err) {
    return null;
  }
}

/**
 * 判定绝对路径是否落在受保护区域内。
 *
 * 只有当路径确实位于 `projectRoot` **之内**时才可能受保护；项目根之外
 * 的路径（合成根、TEMP、系统目录）一律放行。
 */
function isProtected(absPath) {
  const root = STATE.projectRoot;
  if (!root) return false;
  const target = toAbsolute(absPath);
  if (!target) return false;

  let rel;
  try {
    rel = path.relative(root, target);
  } catch (err) {
    return false;
  }
  if (rel === '' || rel.startsWith('..') || path.isAbsolute(rel)) return false;

  const parts = rel.split(/[\\/]+/).filter(Boolean);
  if (parts.length === 0) return false;

  if (BLOCKED_TOP_DIRS.indexOf(parts[0]) !== -1) return true;
  for (const sub of BLOCKED_SUBPATHS) {
    if (parts.length >= sub.length) {
      let match = true;
      for (let i = 0; i < sub.length; i += 1) {
        if (parts[i] !== sub[i]) { match = false; break; }
      }
      if (match) return true;
    }
  }
  return false;
}

/** 记录一次违规尝试并抛出，使调用方立刻失败。 */
function refuse(absPath, api) {
  const message =
    '[isolation-guard] ISOLATION VIOLATION: ' + api + ' refused to touch ' +
    'protected path: ' + absPath;
  STATE.violations.push({ path: absPath, api: api, message: message });
  const err = new Error(message);
  err.code = 'SAL_ISOLATION_VIOLATION';
  throw err;
}

/** 为某个 fs API 生成包装器。 */
function wrapSync(name) {
  const original = fs[name];
  if (typeof original !== 'function') return;
  fs[name] = function guardedSync(...args) {
    const abs = toAbsolute(args[0]);
    if (abs && isProtected(abs)) refuse(abs, 'fs.' + name);
    return original.apply(this, args);
  };
}

/** 为某个 fs.promises API 生成包装器。 */
function wrapPromise(name) {
  if (!fs.promises || typeof fs.promises[name] !== 'function') return;
  const original = fs.promises[name];
  fs.promises[name] = function guardedPromise(...args) {
    const abs = toAbsolute(args[0]);
    if (abs && isProtected(abs)) refuse(abs, 'fs.promises.' + name);
    return original.apply(this, args);
  };
}

/**
 * 安装守卫。幂等：重复调用只更新 projectRoot。
 *
 * @param {{projectRoot?: string}} options
 */
function install(options) {
  const opts = options || {};
  STATE.projectRoot = path.resolve(opts.projectRoot || process.env.SAL_GUARD_ROOT || defaultProjectRoot());

  if (STATE.installed) return STATE;

  ['readFileSync', 'openSync', 'createReadStream', 'readdirSync', 'readlinkSync', 'realpathSync']
    .forEach(wrapSync);
  ['readFile', 'open', 'readdir'].forEach(wrapPromise);

  STATE.installed = true;
  STATE.blocked = ['data/**', 'config/**', 'src/notes/**'];
  return STATE;
}

/** 供自检与报告使用。 */
function describe() {
  return {
    installed: STATE.installed,
    projectRoot: STATE.projectRoot,
    blocked: STATE.blocked,
    violations: STATE.violations
  };
}

// 被 `--require` 预加载时自动安装（root 来自 SAL_GUARD_ROOT 或默认推导）。
if (require.main !== module) {
  install({ projectRoot: process.env.SAL_GUARD_ROOT || defaultProjectRoot() });
} else if (process.argv.indexOf('--self-test') !== -1) {
  const root = path.resolve(process.env.SAL_GUARD_ROOT || defaultProjectRoot());
  install({ projectRoot: root });

  const mustBlock = [
    path.join(root, 'data', 'task_publisher.db'),
    path.join(root, 'data', 'task_publisher.db-wal'),
    path.join(root, 'data', 'task_publisher.db-shm'),
    path.join(root, 'config', 'config.json'),
    path.join(root, 'src', 'notes', 'vault', 'anything.md')
  ];
  const mustAllow = [
    path.join(root, 'tests', 'e2e-manual.js'),
    path.join(root, 'scripts', 'run_e2e_isolated.js'),
    path.join(require('os').tmpdir(), 'synthetic', 'data', 'synthetic.sqlite3')
  ];

  let failed = 0;
  mustBlock.forEach((target) => {
    if (!isProtected(target)) {
      console.error('[isolation-guard] 自检失败：本应被拦截却放行了 ' + target);
      failed += 1;
    }
  });
  mustAllow.forEach((target) => {
    if (isProtected(target)) {
      console.error('[isolation-guard] 自检失败：本应放行却拦截了 ' + target);
      failed += 1;
    }
  });

  if (failed === 0) {
    // 真实触发一次，确认拦截确实会抛错（只针对受保护路径，不读取内容）。
    let threw = false;
    try {
      fs.readFileSync(path.join(root, 'data', 'task_publisher.db'));
    } catch (err) {
      threw = err && err.code === 'SAL_ISOLATION_VIOLATION';
    }
    if (!threw) {
      console.error('[isolation-guard] 自检失败：受保护路径读取未触发拦截');
      failed += 1;
    }
  }

  if (failed === 0) {
    console.log('[isolation-guard] 自检通过：受保护路径全部拦截，合法路径全部放行');
    process.exit(0);
  }
  process.exit(1);
}

module.exports = {
  install: install,
  isProtected: isProtected,
  describe: describe,
  BLOCKED_TOP_DIRS: BLOCKED_TOP_DIRS,
  BLOCKED_SUBPATHS: BLOCKED_SUBPATHS,
  defaultProjectRoot: defaultProjectRoot
};
