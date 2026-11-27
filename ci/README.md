# CI 门禁棘轮配置

本目录存放**机械门禁的棘轮（ratchet）基线**。

## 为什么要棘轮

本仓库的机械门禁在 AR03 P1–P5 交付时即为 **RED**（接线未完成，
逐项见 `docs/CURRENT_PROJECT_STATE.md`「已知缺口」）。因此：

- CI 直接要求「9 门禁全绿」→ CI 从第一天起就是红的，**没有门禁意义**；
- CI 忽略门禁失败 → CI **纯属装饰**，任何回归都能合入。

棘轮方案取两者之间：**不允许变差，但允许变好**。

## 工作方式

`scripts/ci/gate_ratchet.js` 重跑每个门禁，提取**稳定失败签名**
（不含时间戳、耗时、临时路径、端口、内存地址），与
`gate-baseline.json` 中已记录的失败集合比较：

| 情况 | 含义 | CI 结果 |
|---|---|---|
| 出现基线之外的失败 | **回归** | ❌ 失败 |
| 失败集合缩小 | 门禁变好 | ✅ 通过（提示可收紧基线） |
| 与基线完全一致 | 无变化 | ✅ 通过 |
| 门禁异常退出且无法解析签名 | 门禁本身崩了 | ❌ 失败（fail-closed） |

剩余欠债数量**始终原样打印**，不掩盖。

## 收紧基线

只有**显式更新基线文件**才能收紧，且该改动在 PR 中完全可见：

```bash
node scripts/ci/gate_ratchet.js --update              # 全部门禁
node scripts/ci/gate_ratchet.js --update --only p0-cleanup   # 单个门禁
```

## 重要限制

- 基线**不是豁免**。它记录的是「已知欠债」，不是「允许失败」。
  新增任何一条失败都会让 CI 变红。
- 基线里列出的失败**必须逐项修复**。修复 AR03 接线债属于后续工程批次，
  需按 `AGENTS.md` 的 MNN-SNN-GNN 证书制派工。
- `pytest tests/characterize` 当前有 **2 个 collection error**
  （`REQUIRED_TABLES` 缺失），导致整个套件无法收集。
  该门禁暂未纳入棘轮（无法产出稳定签名），
  但它被 `test_schema_consistency_gate.py` 等文件间接覆盖。
