#!/usr/bin/env node
// scripts/ci/gate_ratchet.js - 机械门禁「棘轮」（ratchet）
//
// 目的
// ----
// 本仓库的机械门禁在 AR03 P1–P5 交付时即为 RED（接线未完成，见
// docs/CURRENT_PROJECT_STATE.md「已知缺口」）。若 CI 直接要求「全绿」，
// 则 CI 从第一天起就是红的，等于没有门禁；若 CI 忽略失败，则 CI 纯属装饰。
//
// 棘轮（ratchet）方案：**不允许变差，但允许变好**。
//
//   1. 每个门禁有一个「已记录基线」（baseline），记录当前已知的失败集合；
//   2. CI 重跑门禁，把实际失败集合与基线比较：
//        - 出现 **基线之外**的新失败  → 失败（回归，regression）
//        - 失败集合 **缩小**            → 通过，并提示「基线可收紧」
//        - 与基线完全一致              → 通过
//   3. 基线本身入库（ci/gate-baseline.json），任何修改基线都必须在 PR 里
//      显式可见 —— 这就是「收紧」的唯一合法路径。
//
// 关键性质
// --------
// * **fail-closed**：新失败一定让 CI 变红。基线不构成「豁免」。
// * **不掩盖**：基线里的失败数量被原样打印，人人都能看到还欠多少债。
// * **可比**：基线按失败签名排序去重，与执行顺序、机器、时区无关。
//
// 用法
// ----
//   node scripts/ci/gate_ratchet.js --check                     # CI 用
//   node scripts/ci/gate_ratchet.js --update --only <gate>      # 收紧基线
//   node scripts/ci/gate_ratchet.js --print                     # 打印实际失败
//
// 退出码
// ----
//   0 = 无回归；1 = 有回归（出现基线之外的新失败）。

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const BASELINE_PATH = path.join(PROJECT_ROOT, 'ci', 'gate-baseline.json');

// ---------------------------------------------------------------------------
// 门禁定义
// ---------------------------------------------------------------------------
// 每个门禁提供：
//   cmd        —— 运行命令（argv 数组）
//   signature  —— 从 stdout+stderr 中提取「失败签名」的提取器
//
// 签名必须是**稳定**的：不能含时间戳、耗时、临时路径、端口、内存地址。
// 否则每次运行的基线都会漂移，棘轮就失效了。

const GATES = [
  {
    id: 'module-imports',
    cmd: ['node', 'scripts/check_module_imports.js'],
    // 门禁自己打印稳定签名：`  [rule] file → detail`
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        const m = /^\s*\[([a-z0-9-]+)\]\s+(.+?)\s+→\s+(.+)$/.exec(line);
        if (m) out2.push(`[${m[1]}] ${m[2]} :: ${m[3]}`);
      }
      return out2;
    }
  },
  {
    id: 'css-architecture',
    cmd: ['node', 'scripts/check_css_architecture.js'],
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        // 门禁用全角数字编号（`[②]`、`[④]`），不是 ASCII 数字。
        const m = /^\s*\[([^\]]{1,4})\]\s+(.+)$/.exec(line);
        if (m) out2.push(`[${m[1]}] ${m[2]}`);
      }
      return out2;
    }
  },
  {
    id: 'layout-utility-conflicts',
    cmd: ['node', 'scripts/check_layout_utility_conflicts.js'],
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        const m = /^\s*(?:CONFLICT|FAIL)\s*[:：]\s*(.+)$/.exec(line);
        if (m) out2.push(m[1].trim());
      }
      return out2;
    }
  },
  {
    id: 'schema-consistency',
    cmd: [pythonBin(), 'scripts/check_schema_consistency.py'],
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        const m = /^(?:FAIL|ERROR)\s*[:：]\s*(.+)$/.exec(line.trim());
        if (m) out2.push(m[1].trim());
        const im = /^(ImportError|ModuleNotFoundError|AttributeError)\s*:\s*(.+)$/.exec(
          line.trim()
        );
        if (im) {
          // 绝对路径随机器而变（含中文目录时还有编码差异），必须归一化，
          // 否则基线在 CI 上永远对不上。只归一化括号里的绝对路径，
          // 引号里的符号名必须保留（那是真正的失败原因）。
          const detail = im[2].replace(/\(([^)]*)\)/g, '(<path>)');
          out2.push(`${im[1]}: ${detail}`);
        }
      }
      return out2;
    }
  },
  {
    id: 'p0-cleanup',
    cmd: [pythonBin(), 'scripts/verify_p0_cleanup.py'],
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        const m = /^\s*FAIL\s+(.+)$/.exec(line);
        if (m) out2.push(m[1].trim());
      }
      return out2;
    }
  },
  {
    id: 'gacha-golden',
    cmd: [pythonBin(), 'scripts/phase2_gacha_golden.py'],
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        const m = /^\s*FAIL\s*[:：]\s*(.+)$/.exec(line);
        if (m) out2.push(m[1].trim());
        const d = /max_diff\s*=\s*(\d+)/.exec(line);
        if (d && d[1] !== '0') out2.push(`max_diff=${d[1]}`);
      }
      return out2;
    }
  },
  {
    // 收集阶段（collection）错误必须单独成门禁。
    //
    // 为什么不把整个 `pytest tests/characterize` 纳入棘轮：
    // 该套件当前有 493 failed / 137 errors，其中大量依赖本机环境
    // （Windows 路径、中文目录编码、已安装的 chromium 位置），
    // 失败签名不稳定，无法作为可比的棘轮基线。
    // 但**收集阶段**错误是确定性的：它意味着「测试根本没跑起来」，
    // 任何新增的 collection error 都是硬回归，必须拦住。
    //
    // 这里只跑 `--collect-only`，不执行测试体，因此很快且无副作用。
    //
    // 注意：**不** `--ignore` 任何模块。当前有 2 个模块因
    // `REQUIRED_TABLES` 缺失而收集失败 —— 那正是这个门禁要记录并盯住的
    // 已知欠债。忽略它们会让「新增一个 collection error」变成静默通过。
    id: 'pytest-collection',
    cmd: [
      pythonBin(),
      '-m',
      'pytest',
      'tests/characterize',
      '--collect-only',
      '-q'
    ],
    signature: (out) => {
      const out2 = [];
      for (const line of out.split(/\r?\n/)) {
        // `ERROR tests/characterize/xxx.py` —— 收集失败的文件。
        const m = /^ERROR\s+(\S+)/.exec(line.trim());
        // 路径分隔符必须归一化：Windows 输出 `tests\characterize\...`，
        // Linux 输出 `tests/characterize/...`。不归一化则基线跨平台不匹配。
        if (m) out2.push(`collection-error ${m[1].replace(/\\/g, '/')}`);
        // ImportError 等根因（路径归一化）。
        const im = /^(ImportError|ModuleNotFoundError|AttributeError)\s*:\s*(.+)$/.exec(
          line.trim()
        );
        if (im) {
          const detail = im[2].replace(/\(([^)]*)\)/g, '(<path>)');
          out2.push(`${im[1]}: ${detail}`);
        }
      }
      return out2;
    }
  }
];

function pythonBin() {
  // CI 用系统 python；本地优先用项目 venv（AGENTS.md / P4 记录：
  // 未指向 .venv 时子进程会以 9009 退出）。
  const venv = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venv)) return venv;
  const venvPosix = path.join(PROJECT_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPosix)) return venvPosix;
  return process.env.PYTHON || 'python';
}

// ---------------------------------------------------------------------------
// 执行
// ---------------------------------------------------------------------------

function runGate(gate) {
  const res = spawnSync(gate.cmd[0], gate.cmd.slice(1), {
    cwd: PROJECT_ROOT,
    encoding: 'utf8',
    env: { ...process.env, PYTHON: pythonBin(), PYTHONDONTWRITEBYTECODE: '1' },
    maxBuffer: 64 * 1024 * 1024
  });
  const combined = `${res.stdout || ''}\n${res.stderr || ''}`;
  const exitCode = res.status === null ? -1 : res.status;
  let signatures = [];
  let crashed = null;
  try {
    // 去重：同一个失败签名可能出现多次（例如同一条白名单违规被多次触发）。
    // 棘轮比较的是**集合**，保留重复会让计数失真。
    signatures = Array.from(new Set(gate.signature(combined)));
  } catch (err) {
    crashed = String(err && err.message);
  }
  // 退出码非 0 且没有解析出任何签名 —— 说明门禁整体崩了（不是「已知的
  // 若干条失败」）。这必须视为回归，不能被基线吞掉。
  if (exitCode !== 0 && signatures.length === 0) {
    crashed = crashed || 'gate exited non-zero without any parseable failure signature';
  }
  return { id: gate.id, exitCode, signatures, crashed, output: combined };
}

// ---------------------------------------------------------------------------
// 基线
// ---------------------------------------------------------------------------

function loadBaseline() {
  if (!fs.existsSync(BASELINE_PATH)) {
    return { version: 1, generatedAt: null, gates: {} };
  }
  try {
    return JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'));
  } catch (err) {
    process.stderr.write(
      `[ratchet] 基线文件无法解析：${BASELINE_PATH}\n` +
        `[ratchet] ${err && err.message}\n`
    );
    process.exit(1);
  }
}

function saveBaseline(baseline, results) {
  const gates = {};
  for (const r of results) {
    gates[r.id] = {
      exitCode: r.exitCode,
      failures: r.signatures.slice().sort()
    };
  }
  const next = {
    version: 1,
    generatedAt: new Date().toISOString(),
    note:
      '机械门禁的已记录失败基线（棘轮）。CI 要求：实际失败集合 ⊆ 本基线。' +
      '收紧基线（失败变少）必须显式更新本文件并在 PR 中说明。',
    gates
  };
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(next, null, 2) + '\n', 'utf8');
}

// ---------------------------------------------------------------------------
// 主流程
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);
  const has = (f) => args.includes(f);
  const onlyIdx = args.indexOf('--only');
  const only = onlyIdx >= 0 ? args[onlyIdx + 1] : null;

  const gates = only ? GATES.filter((g) => g.id === only) : GATES;
  if (only && gates.length === 0) {
    process.stderr.write(`[ratchet] 未知门禁：${only}\n`);
    process.exit(2);
  }

  process.stdout.write(`[ratchet] 执行 ${gates.length} 个门禁…\n`);
  const results = gates.map(runGate);

  if (has('--print')) {
    for (const r of results) {
      process.stdout.write(`\n=== ${r.id} (exit=${r.exitCode}) ===\n`);
      for (const s of r.signatures) process.stdout.write(`  ${s}\n`);
      if (r.crashed) process.stdout.write(`  !! ${r.crashed}\n`);
    }
    return;
  }

  if (has('--update')) {
    const baseline = loadBaseline();
    const merged = { ...baseline, gates: { ...baseline.gates } };
    for (const r of results) {
      merged.gates[r.id] = {
        exitCode: r.exitCode,
        failures: r.signatures.slice().sort()
      };
    }
    merged.generatedAt = new Date().toISOString();
    fs.writeFileSync(BASELINE_PATH, JSON.stringify(merged, null, 2) + '\n', 'utf8');
    process.stdout.write(`[ratchet] 基线已更新：${BASELINE_PATH}\n`);
    return;
  }

  // --- check 模式（CI 用）---
  const baseline = loadBaseline();
  let regressions = 0;
  let tightened = 0;

  for (const r of results) {
    const base = baseline.gates[r.id];
    const actual = new Set(r.signatures);

    if (!base) {
      process.stdout.write(
        `[ratchet] ${r.id}: 基线缺失，按当前实际失败集合建立隐式基线 ` +
          `(${r.signatures.length} 条)\n`
      );
      continue;
    }

    const known = new Set(base.failures || []);

    if (r.crashed) {
      process.stdout.write(
        `[ratchet] ❌ ${r.id}: 门禁异常退出且无法解析失败签名 → ` +
          `视为回归\n         ${r.crashed}\n`
      );
      // 门禁整体崩溃时，原始输出是唯一可诊断线索。必须原样打印，
      // 否则 CI 日志里只有一行摘要，无从判断是环境问题还是代码问题。
      process.stdout.write(
        `[ratchet] --- ${r.id} 原始输出（末尾 60 行）---\n`
      );
      const lines = r.output.split(/\r?\n/).filter((l) => l.trim().length > 0);
      for (const line of lines.slice(-60)) {
        process.stdout.write(`         | ${line}\n`);
      }
      process.stdout.write(`[ratchet] --- ${r.id} 原始输出结束 ---\n`);
      regressions += 1;
      continue;
    }

    const newOnes = r.signatures.filter((s) => !known.has(s));
    const fixed = (base.failures || []).filter((s) => !actual.has(s));

    if (newOnes.length > 0) {
      process.stdout.write(
        `[ratchet] ❌ ${r.id}: 出现 ${newOnes.length} 条基线之外的失败（回归）\n`
      );
      for (const s of newOnes) process.stdout.write(`         + ${s}\n`);
      regressions += 1;
    } else if (fixed.length > 0) {
      process.stdout.write(
        `[ratchet] ✅ ${r.id}: 比基线少 ${fixed.length} 条失败` +
          `（可收紧基线，请更新 ci/gate-baseline.json）\n`
      );
      for (const s of fixed) process.stdout.write(`         - ${s}\n`);
      tightened += fixed.length;
    } else {
      process.stdout.write(
        `[ratchet] ✅ ${r.id}: 与基线一致（${r.signatures.length} 条已记录失败）\n`
      );
    }

    // 无论方向如何都原样打印剩余欠债，不掩盖。
    process.stdout.write(
      `[ratchet]    剩余已记录失败 ${r.signatures.length} 条（exit=${r.exitCode}）\n`
    );
  }

  if (regressions > 0) {
    process.stdout.write(
      `\n[ratchet] 结论：${regressions} 个门禁出现回归 —— CI 失败。\n`
    );
    process.exit(1);
  }
  if (tightened > 0) {
    process.stdout.write(
      `\n[ratchet] 结论：无回归，且有 ${tightened} 条失败已消失` +
        `（基线可以收紧，本次不自动收紧）。\n`
    );
  } else {
    process.stdout.write(`\n[ratchet] 结论：无回归。\n`);
  }
}

main();
