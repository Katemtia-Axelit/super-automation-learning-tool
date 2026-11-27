<!--
本仓库的 Issue 模板只覆盖四类事务：里程碑提案 / 想法 / 圆桌会议 / 独立验收。
空白 Issue 已关闭（见 .github/ISSUE_TEMPLATE/config.yml）。

开始前请先读 docs/CURRENT_PROJECT_STATE.md——多数问题那里已有答案。
-->

## 关联 Issue

<!-- 关联的 Issue 编号与标题。例如：Fixes #123 / 关联 [M-03] 抽卡循环 -->
Closes #

## 变更类型

- [ ] 修复（bug fix）
- [ ] 新功能
- [ ] 重构 / 内部整理（无用户可感知变化）
- [ ] 文档
- [ ] 构建 / CI / 工具链
- [ ] 归档移动（内容移入 `_archive/`）

## 变更说明

<!-- 做了什么，为什么。用户可感知的变化是什么。 -->

## 门禁结果（必填，粘贴实际输出）

<!--
CI 的 `mechanical gates` 执行的是棘轮（scripts/ci/gate_ratchet.js --check）：
出现基线之外的新失败即红；失败集合变小则绿并提示可收紧基线。
基线是「已知欠债清单」，不是豁免。
详见 ci/README.md 与 docs/CURRENT_PROJECT_STATE.md。
-->

```
node scripts/ci/gate_ratchet.js --check         => PASS / FAIL: <签名>

（逐个门禁的实际结果摘要；失败的门禁必须写明失败签名，不要省略。）

node scripts/check_module_imports.js          => PASS / FAIL: <签名>
node scripts/check_css_architecture.js         => PASS / FAIL: <签名>
node scripts/check_layout_utility_conflicts.js => PASS / FAIL: <签名>
python scripts/check_schema_consistency.py     => PASS / FAIL: <签名>
python scripts/verify_p0_cleanup.py            => PASS / FAIL: <签名>
python scripts/phase2_gacha_golden.py          => PASS / FAIL: <签名>
python -m pytest tests/characterize -q         => PASS / FAIL: <签名>
node .cursor/infra-tests/redline-guard/harness.js => PASS / FAIL: <签名>
```

## 棘轮基线（当且仅当失败变少时）

- [ ] 本 PR **未**改变任何门禁的失败集合 —— 无需动 `ci/gate-baseline.json`
- [ ] 本 PR 让失败**变少** —— 已更新 `ci/gate-baseline.json`，并在变更说明中写明少了哪些

> 若新增了基线之外的失败，CI 会变红。这是设计意图：基线记录的是欠债，
> 不是可以新增的豁免项。

## 红线自检（必填）

- [ ] 本 PR **未**新增或修改 `src/notes/**`
- [ ] 本 PR **未**新增或修改 `data/task_publisher.db`、`data/task_publisher.db-wal`、`data/task_publisher.db-shm`
- [ ] 本 PR **未**新增或修改 `config/config.json`
- [ ] 本 PR **未**提交任何凭据、Cookie、`.env` 内容或私钥
- [ ] 本 PR **未**提交 `prototypes/`、课程题库或任何个人学习资产

> 违反任意一项的 PR 会被 `redline-scan` job 直接拒绝。

## 归档移动

- [ ] 本 PR 不含 `_archive/` 移动
- [ ] 本 PR 含 `_archive/` 移动 —— 若勾选，请说明来源目录、目标批次与恢复路径

## 关联交付文档

<!-- 若本次变更对应某个批次，补上 docs/P*_*.md 或 docs/ROUNDTABLE_*.md 的链接。 -->
