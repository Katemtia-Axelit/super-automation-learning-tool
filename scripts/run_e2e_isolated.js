#!/usr/bin/env node
// scripts/run_e2e_isolated.js - 隔离复现 tests/e2e-manual.js（Stage 0 / AR03-P2）
//
// 目的
// ----
// `tests/e2e-manual.js` 会写任务 / 计时器状态（`cleanupExistingTimer` 调
// `/api/timer/complete`），因此 **不能** 直接对生产库跑。本脚本提供隔离
// 复现路径：
//   1. 用 `tests/e2e/factory-sandbox-server.py` 起一个 **随机端口** 的合成
//      Factory（100% TEMP 合成根 + 合成 SQLite + 合成 vault）；
//   2. 把合成 BASE_URL 通过环境变量传给 `tests/e2e-manual.js`；
//   3. **证明**隔离：Node 侧 fs 守卫（事前阻断）+ 合成服务器侧
//      `sys.addaudithook` 审计（事中记录）+ 合成根启动自检；
//   4. 透传 e2e-manual.js 的退出码。
//
// 零触碰证明方式（Stage 0 修正）
// ---------------------------
// 旧版本用 `fs.readFileSync()` **读取并 SHA-256** 生产
// `data/task_publisher.db{,-wal,-shm}`、`config/config.json`、`src/notes/**`
// 来"证明"它们没变。这本身就违反红线 —— **不读取、不写入、不复制、
// 不哈希、不恢复**真实生产数据。
//
// 现在改为三重证明，**全程不打开任何生产文件**：
//   A. Node fs 守卫（`scripts/guard/protected_paths_guard.js`）
//      —— 任何对 `data/**`、`config/**`、`src/notes/**` 的读取尝试
//         立即抛错，触碰即失败（事前阻断，而非事后观测）。
//   B. Python 审计钩子（`tests/e2e/synthetic_audit.py`）
//      —— 合成服务器进程内记录真实的 sqlite3.connect / 文件访问，
//         runner 断言这些访问全部落在合成根内。
//   C. 合成根启动自检（`tests/e2e/synthetic_root_selfcheck.py`）
//      —— 服务器启动前断言解析出的 db / notes / config 路径全部在合成根内，
//         否则拒绝启动（fail closed）。
//
// 用法
// ----
//   node scripts/run_e2e_isolated.js
//   node scripts/run_e2e_isolated.js --keep-temp     # 保留合成根（调试用）
//
// 约束
// ----
// * **绝不**读取 / 写入 / 复制 / 哈希生产 DB、WAL/SHM、Vault、config；
// * 不改 git 历史、不动工作区文件（除 %TEMP% 下的合成根）；
// * 本脚本不自己判定"36/36"是否达标 —— 结论由 e2e-manual.js 的退出码
//   与明细给出。

'use strict';

const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const SANDBOX_SERVER = path.join(
  PROJECT_ROOT, 'tests', 'e2e', 'factory-sandbox-server.py'
);
const E2E_SCRIPT = path.join(PROJECT_ROOT, 'tests', 'e2e-manual.js');
const GUARD = require('./guard/protected_paths_guard.js');

// ---------------------------------------------------------------------------
// A. Node fs 守卫：事前阻断生产数据访问
// ---------------------------------------------------------------------------

// 安装守卫（受保护区域：data/**、config/**、src/notes/**）。
// 一旦有任何代码试图打开这些路径 → 立即抛错 → 本次运行失败。
const guardState = GUARD.install({ projectRoot: PROJECT_ROOT });

// ---------------------------------------------------------------------------
// 合成 Factory 生命周期
// ---------------------------------------------------------------------------

function startSandboxServer() {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.PYTHON || 'python',
      ['-B', SANDBOX_SERVER, '--print-url'],
      { cwd: PROJECT_ROOT, env: { ...process.env } }
    );
    let buffer = '';
    let baseUrl = null;
    let tmpDir = null;

    const timer = setTimeout(() => {
      child.kill();
      reject(new Error('合成 Factory 启动超时（30s）'));
    }, 30000);

    child.stdout.on('data', (chunk) => {
      buffer += chunk.toString();
      let index;
      while ((index = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (line.startsWith('URL:')) {
          baseUrl = line.slice(4).trim();
        } else if (line.startsWith('TMPDIR:')) {
          tmpDir = line.slice(7).trim();
        }
        if (baseUrl && tmpDir) {
          clearTimeout(timer);
          resolve({ child, baseUrl, tmpDir });
          return;
        }
      }
    });
    child.stderr.on('data', (chunk) => {
      process.stderr.write('[sandbox-server] ' + chunk.toString());
    });
    child.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
    child.on('exit', (code) => {
      clearTimeout(timer);
      if (!baseUrl) reject(new Error('合成 Factory 提前退出 (code=' + code + ')'));
    });
  });
}

//: 合成"已批准策略"文档。
//
// P0 引导卡（LT_BOOTSTRAP_FIRST_CARD_20261021_A）在 **没有** 经用户明确
// 批准的策略时，会用覆盖层锁死整个页面（body 下除覆盖层外全部
// display:none）。这属于产品设计，而不是缺陷。
//
// 因此要复现"正常抽卡 / 计时 / 知识库 / 设置"这些 E2E 用例，合成根里
// 必须存在一份 **已批准的合成策略**。这里生成的文档只写入 %TEMP%
// 下的合成根，永远不会触碰生产的 data/agent-policy/。
function syntheticApprovedPolicy() {
  return {
    schema_version: 1,
    version: 'synthetic-e2e',
    approved_by_user: true,
    approved_at: '2026-01-01T00:00:00+00:00',
    source: 'synthetic-e2e-harness'
  };
}

function writeSyntheticPolicy(tmpDir) {
  if (!tmpDir) throw new Error('缺少 TMPDIR，无法写入合成策略');
  const root = path.join(tmpDir, 'root');
  const policyDir = path.join(root, 'data', 'agent-policy');
  fs.mkdirSync(policyDir, { recursive: true });
  fs.writeFileSync(
    path.join(policyDir, 'latest.json'),
    JSON.stringify(syntheticApprovedPolicy(), null, 2),
    'utf8'
  );
  return path.join(policyDir, 'latest.json');
}

//: 合成 vault（知识库）内容。
//
// E2E 5.1 / 5.2 会断言：
//   - `#knowContent` 可见且有实际内容；
//   - 第一个分类下有笔记（`.note-item` 数量 > 0）。
// 合成根默认是 **空 vault**（``vault/`` 下没有任何 .md），因此这两个断言
// 必然失败 —— 这属于"没有数据"而不是产品缺陷。
//
// 这里在 %TEMP% 合成根里写入 **纯合成** 的 Markdown 笔记：
//   vault/<学科>/<笔记>.md              → 被 /api/knowledge/notes 列出
//   vault/知识点/<学科>/<笔记>.md       → 被 /api/knowledge/categories 计数
// 永远不触碰生产的 src/notes/**。
const SYNTHETIC_VAULT = {
  '高等数学': ['合成笔记-极限', '合成笔记-积分'],
  '大学物理': ['合成笔记-力学'],
  '线性代数': ['合成笔记-矩阵']
};

function writeSyntheticVault(tmpDir) {
  if (!tmpDir) throw new Error('缺少 TMPDIR，无法写入合成 vault');
  const vault = path.join(tmpDir, 'root', 'vault');
  const written = [];
  Object.keys(SYNTHETIC_VAULT).forEach((subject) => {
    const notes = SYNTHETIC_VAULT[subject];
    const subjectDir = path.join(vault, subject);
    const pointDir = path.join(vault, '知识点', subject);
    fs.mkdirSync(subjectDir, { recursive: true });
    fs.mkdirSync(pointDir, { recursive: true });
    notes.forEach((noteName, index) => {
      const body = [
        '# ' + noteName,
        '',
        '合成 E2E 笔记（仅存在于 %TEMP% 合成根，不属于生产知识库）。',
        '',
        '- subject: ' + subject,
        '- index: ' + index,
        '',
        '## 正文',
        '',
        '这是用于隔离复现知识库页面的占位内容。'
      ].join('\n');
      fs.writeFileSync(path.join(subjectDir, noteName + '.md'), body, 'utf8');
      fs.writeFileSync(path.join(pointDir, noteName + '.md'), body, 'utf8');
      written.push(path.join(subjectDir, noteName + '.md'));
    });
  });
  return written;
}

// ---------------------------------------------------------------------------
// B. 合成服务器审计：验证进程内真实访问全部落在合成根内
// ---------------------------------------------------------------------------

function readAudit(tmpDir) {
  // 审计清单位于合成根内（不是生产路径），可以安全读取。
  const auditPath = path.join(tmpDir, 'root', '_sandbox_audit.json');
  if (!fs.existsSync(auditPath)) {
    return { missing: true, path: auditPath };
  }
  try {
    return { missing: false, path: auditPath, data: JSON.parse(fs.readFileSync(auditPath, 'utf8')) };
  } catch (err) {
    return { missing: false, path: auditPath, parseError: String(err) };
  }
}

function assertAuditClean(audit, tmpDir) {
  const problems = [];
  if (audit.missing) {
    problems.push('审计清单缺失：' + audit.path + '（合成服务器未产出访问记录）');
    return problems;
  }
  if (audit.parseError) {
    problems.push('审计清单无法解析：' + audit.parseError);
    return problems;
  }
  const data = audit.data || {};
  const violations = data.protected_violations || [];
  const outside = data.sqlite_outside_synthetic || [];
  violations.forEach((v) => {
    problems.push('服务器触碰了生产受保护路径：' + v.kind + ' ' + v.path);
  });
  outside.forEach((v) => {
    problems.push('服务器在合成根之外打开了 SQLite：' + v.path);
  });
  // 审计清单自身必须位于合成根内
  const synthRoot = path.resolve(tmpDir, 'root');
  const auditAbs = path.resolve(audit.path);
  const rel = path.relative(synthRoot, auditAbs);
  if (rel.startsWith('..') || path.isAbsolute(rel)) {
    problems.push('审计清单不在合成根内：' + auditAbs);
  }
  return problems;
}

// ---------------------------------------------------------------------------
// E2E 执行
// ---------------------------------------------------------------------------

function runE2E(baseUrl) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [E2E_SCRIPT], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, SAL_E2E_BASE_URL: baseUrl }
    });
    child.stdout.on('data', (c) => process.stdout.write(c));
    child.stderr.on('data', (c) => process.stderr.write(c));
    child.on('exit', (code) => resolve(code === null ? 1 : code));
  });
}

// ---------------------------------------------------------------------------
// 主流程
// ---------------------------------------------------------------------------

async function main() {
  const keepTemp = process.argv.includes('--keep-temp');

  console.log('[run_e2e_isolated] 安装生产数据 fs 守卫（事前阻断）…');
  console.log(
    '[run_e2e_isolated] 受保护区域：' + (guardState.blocked || []).join('、')
  );

  console.log('[run_e2e_isolated] 启动合成 Factory（随机端口，%TEMP% 合成根）…');
  const sandbox = await startSandboxServer();
  console.log('[run_e2e_isolated] 合成 BASE_URL = ' + sandbox.baseUrl);

  // 写入"已批准的合成策略"，解除 P0 引导卡覆盖层（仅限 %TEMP% 合成根）。
  const policyFile = writeSyntheticPolicy(sandbox.tmpDir);
  console.log('[run_e2e_isolated] 合成已批准策略 = ' + policyFile);
  const vaultFiles = writeSyntheticVault(sandbox.tmpDir);
  console.log('[run_e2e_isolated] 合成 vault 笔记 ' + vaultFiles.length + ' 篇');

  let code = 1;
  let audit = { missing: true, path: '(未启动)' };
  try {
    console.log('[run_e2e_isolated] 运行 tests/e2e-manual.js …\n');
    code = await runE2E(sandbox.baseUrl);
  } finally {
    // 关闭合成 Factory（含其 run_app.py 子进程）
    try { sandbox.child.kill('SIGTERM'); } catch (e) { /* ignore */ }
    // 给子进程一点时间把审计快照落盘
    await new Promise((resolve) => setTimeout(resolve, 400));
    // **先读审计**（清单在合成根内），再清理合成根。
    audit = readAudit(sandbox.tmpDir);
    if (sandbox.tmpDir && !keepTemp) {
      try {
        fs.rmSync(sandbox.tmpDir, { recursive: true, force: true });
      } catch (e) { /* ignore */ }
    } else if (sandbox.tmpDir) {
      console.log('[run_e2e_isolated] --keep-temp：保留 ' + sandbox.tmpDir);
    }
  }

  // ---- B. 审计断言（读取的是合成根内的清单，不是生产文件） ----
  console.log('\n[run_e2e_isolated] 校验合成服务器访问审计…');
  const auditProblems = assertAuditClean(audit, sandbox.tmpDir);
  if (!audit.missing && !audit.parseError) {
    console.log(
      '[run_e2e_isolated] 审计记录数 = ' +
      ((audit.data && audit.data.record_count) || 0)
    );
  }
  if (auditProblems.length) {
    console.error('[run_e2e_isolated] ❌ 隔离审计失败：');
    auditProblems.forEach((p) => console.error('   ' + p));
    process.exit(1);
  }
  console.log('[run_e2e_isolated] ✅ 合成服务器未触碰任何生产受保护路径');

  // ---- A. 守卫断言（本次运行没有触发任何阻断） ----
  const guardViolations = GUARD.describe().violations;
  if (guardViolations.length) {
    console.error('[run_e2e_isolated] ❌ 生产数据 fs 守卫被触发：');
    guardViolations.forEach((v) => console.error('   ' + v.message));
    process.exit(1);
  }
  console.log('[run_e2e_isolated] ✅ 生产数据 fs 守卫全程未被触发（未读取任何生产文件）');

  console.log(
    '[run_e2e_isolated] e2e-manual.js 退出码 = ' + code +
    '（0 = 全部通过）'
  );
  process.exit(code);
}

main().catch((err) => {
  console.error('[run_e2e_isolated] 失败：' + (err && err.stack || err));
  process.exit(1);
});
