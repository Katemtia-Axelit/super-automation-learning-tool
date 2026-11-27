# AR03 重构进度缓慢审计报告

> 审计日期：2026-11-16（UTC+8）
> 审计范围：2026-11-04 至 2026-11-16，约两周
> 对象：学习工具 AR03 前端模块化重构，重点为 G14/G15、main/AR03 Worktree、Controller Loop 交付与验收链
> 性质：基于本机 canonical Batch Ledger、Task/State、Collection、Review、dispatch plan/prompt 与原始 Trace 的事后审计；不是代码全量审计，也不替代当前源码复核

## 0. 结论摘要

本次进度缓慢并非单纯由功能复杂度造成。主要时间损耗来自：

1. main 与 AR03 sibling Worktree 曾长期承载不同的 G14/G15 变更，工程基线和可继承证据不够稳定。
2. Worker 的工具预算、测试预算和停止条件反复超出；但 Controller 又把部分不可强制执行的工具调用预算当作工程验收否决项，制造多轮审计与 Follow-up。
3. Controller 自身出现过源文件 SHA 转录错误和历史代码归因错误，增加了本可避免的复核工作。
4. Cursor Workspace 元数据与实际 Shell/Git 目标不一致，导致技术证据与正式验收身份之间存在缺口。
5. Handoff、Collection、Review、Batch Resolution、Milestone Completion 被混为一个“完成”概念，导致流程状态反过来主导工程节奏。

核心判断：**工程成果并非停滞，但成果转化为可接受、可继承的主线里程碑的速度明显偏低。** 当前最优解不是再做一次基础设施重构，而是用一次有界的主线证据收口，随后恢复 G15.2 → G15.3 → G15.4 的线性开发。

## 1. 当前状态（以本次现场核对为准）

| 项目 | 已确认状态 | 说明 |
|---|---|---|
| G14 Gacha Owner | 有部分有效成果，历史 W01/W02 均 NEEDS_FOLLOWUP；W03 ACCEPTED | W03 是只读验证，不代表早期执行过程合规 |
| G15 生命周期设计 | W03 ACCEPTED | 设计已收敛，可作为第一切片实施依据 |
| Runtime Integrity Repair | ACCEPTED，Batch CLOSED | 工程修复被接受；仍保留 28 条 postToolUse 记录对 24 次预算的偏差，且未声称完成浏览器运行验证 |
| G15.1 生命周期首切片 | 工程实现存在；W01/W02 为 NEEDS_FOLLOWUP；W03 证据纠错 ACCEPTED | W01 的指定 characterization 最终通过，但执行过程有预算偏差 |
| W04 分支验证 | NEEDS_FOLLOWUP | branch-only 结果，不能代替 mainline 验收 |
| W06 mainline 验证 | 源码检查与唯一授权测试 PASS；Review NEEDS_FOLLOWUP | 23 条工具轨迹记录对 16 次合同预算；Worker 自报 22；Handoff workspace_root 指向 AR03 sibling，合同要求 main |
| W07 mainline evidence follow-up | 计划与提示词文件存在；尚未派发 | 本次 status 返回 UNKNOWN_TASK；没有正式 Task State/Receipt；尚未 preflight/run |
| G15.2 Feedback/Care | 有一份 main 版准备稿，但前置条件仍要求 W06 Review=ACCEPTED | 该门槛与当前 W06 NEEDS_FOLLOWUP 冲突；旧 AR03 sibling 版 W05 不可复用 |
| G15 Closeout Batch | OPEN | 仍有 W07 mainline evidence follow-up 待处理；不得手工关闭 |

当前 Dispatcher 现场：delivery_ready=true、无 delivery blockers、目标 heartbeat fresh；Watchdog paused、active_tasks=0。controller-loop.js status W07 返回 UNKNOWN_TASK。这只说明当前投递通道可用、没有活动任务，不证明 Cursor Workspace 已经是 main；Workspace 身份仍须由正式 preflight 和新 Worker 的第一条 Shell 直接核验。

## 2. 关键时间线与原始证据

### 11 月 4 日：G14 Gacha Owner

- G14 W01 被用户中断，487 条 postToolUse 记录、426 个不同 tool_use_id、61 次 Write；留下未接受的部分变更，状态保持 NEEDS_FOLLOWUP / NO_HANDOFF。
- G14 W02 实际提交并执行，但 48 条 postToolUse / 37 个不同 tool_use_id 超过 16 次合同预算，并出现 11 次整文件 Write；Controller 停止 Worker。一次真实 Factory E2E 的多抽反馈计数断言失败。
- G14 W03 只读验证接受了确定性断言修正；指定 Factory E2E 1/1 PASS。该 ACCEPTED 仅覆盖 W03 的只读验证，不追溯改写 W01/W02。

### 11 月 4—11 日：G15 生命周期设计

- W01/W02 出现 NO_HANDOFF、代理不可用、CDP 不就绪和其他 Batch 未结算等派发/接续问题。
- W03 最终完成窄范围设计收敛并 ACCEPTED。设计将 G15 分为普通生命周期、Feedback/Care、Skip/Refuse、Discard/Restore；Free-card 明确排除，另立 G16。
- 这段时间的主要产出是边界与依赖澄清，不应计作 G15 实现进度。

### 11 月 14—15 日：基线对账

- Baseline Reconciliation W01—W05 连续 NEEDS_FOLLOWUP，问题包括证据不足、工具预算超出、临时文件写入合规核验和 Collection/Trace 计数差异。
- W06 最终 ACCEPTED 的是“语义基线结算判断”，不是把 W01—W05 改写为合规通过。
- 可供 G15 消费的来源证据限定为 13 项 ACCEPTED；MIXED 2 项、UNKNOWN 1 项、NOT PRESENT 2 项隔离；W02 Temp 文件按决定保留。
- 该 Batch 已 CLOSED，但历史异常仍保留。不得重放 W01—W05 或手工修改历史 Receipt/Journal。

### 11 月 16 日：Runtime Integrity 与 G15.1

- Runtime Integrity Repair W01 的工程产物 ACCEPTED、Batch CLOSED；同时保留 28 条 postToolUse 对 24 次预算的偏差，不声称浏览器运行验证。
- G15.1 W01 的生命周期实现确实存在，最终指定 characterization 有通过记录；但 W01 有 97 条 postToolUse 记录对 36 次预算，并运行指定 unittest 命令 5 次（合同最多 3 次），因此原 Review 为 NEEDS_FOLLOWUP。
- W02 原始 Trace 有 58 条 postToolUse 记录对 18 次预算；13 次 Write 仅落在 %TEMP%，没有 Worktree 改动、没有产品测试。W02 还继续调查了一个由 Controller 错误转录 SHA 导致的虚假 mismatch。
- W03 只读证据纠错 ACCEPTED：确认 Sleep 相关符号在 W01 开始前的 Runtime Integrity 修复中已经不存在，纠正了 W01 Review 的错误归因；同时修正了 W01/W02 的 Collection、Generation 与 Trace 证据绑定。
- W04 是 sibling branch 的只读验证，源码/测试结果 PASS，但因报告 18、Trace 17、合同上限 16 而 NEEDS_FOLLOWUP；不能把它当作 mainline gate。
- W06 在 mainline 目标路径上完成源码审计与一次授权 characterization，退出码 0、1/1 PASS。原始 Collection 记录 23 次工具调用，Worker 自报 22 次，合同上限 16。Handoff 的 workspace_root 却标记 AR03 sibling；实际源文件和测试工具输入明确指向 main，未见源文件写入、sibling 源码读取或内部 subagent。Review 因预算与 Workspace 元数据偏差保持 NEEDS_FOLLOWUP。
- W07 mainline follow-up 的 manifest/prompt 已存在，canonical Closeout Ledger 也有 W07 行，但正式 Task State 不存在，status 返回 UNKNOWN_TASK；未发现 Receipt，且未 preflight/run。不得称其已派发。
- 另有 G15.2 Feedback/Care W07 准备稿，前置条件写死 W06 Review=ACCEPTED；当前条件不满足。它与 mainline follow-up W07 是两个不同的完整 TASK_TOKEN，不能只用“W07”简称混称。旧 W05 Feedback/Care 目标是 AR03 sibling，不能复用。

## 3. 根因分层：事实与判断

### A. 已确认事实

1. **Worktree/基线复杂度：** G14 与 G15 曾分布在 main 与 AR03 sibling；部分 G14 产物是 main dirty/untracked 工作区内容，不是可直接 cherry-pick 的正式提交。Factory E2E fixture/config 也曾在两个 Worktree 间不一致。
2. **Worker 执行偏差：** 多个 Worker 明显超出工具预算、测试预算或写入约束；工具计数还存在自报与原始 Trace 不一致。
3. **Controller 数据错误：** G15 W02 的测试文件 SHA 预期值由 Controller 错误转录；Sleep 删除归因由后续 W03 证明不属于 W01。
4. **Workspace 身份不一致：** W06 的 Cursor Handoff metadata 指向 sibling，但实际读取/测试工具输入指向 main。不能把绝对路径操作等同于当前 Cursor Workspace 身份正确。
5. **交付状态未分层：** 工程检查 PASS、Review NEEDS_FOLLOWUP、Batch OPEN 是同时成立的，不可将其中任一状态简化为“项目没做”或“项目已完成”。

### B. 合理推断（不是原始记录直接证明）

1. 工具预算过于紧/缺乏可执行的实时停止机制，使 Worker 可能把大量时间花在满足过程约束和自我核算上。
2. Controller 对普通工具预算超出采取过度否决，导致“审计 Worker 的 Worker”增加，降低单位时间的产品产出。
3. 多 Worktree、未提交成果和验证夹具不对称，显著提高了每次交接前的基线核验成本。
4. 交接系统追求证据完整本身有价值；问题在于把每一项过程偏差都升级为新任务，而没有先判断它是否实质影响代码正确性、证据可信度或安全边界。

## 4. 责任归因

- **Worker 责任：** 超预算、超测试次数、超写入范围、未按 stop condition 停止等，必须如实记录；不能用工程结果好掩盖真实执行偏差。
- **Controller 责任：** 合同中的路径、SHA、基线、测试次数和依赖必须在派发前核对；不得把错误的预期值作为 Worker 的失败证据；不得将历史变更归因给错误 Worker。
- **Reviewer 责任：** 必须区分“工程结果是否可信”和“执行过程是否合规”；Review 不能只看工具调用数字，也不能忽略硬边界偏差。
- **基础设施责任：** Cursor Workspace metadata、Dispatcher preflight、Receipt/Trace/Handoff identity 必须一致；发生不一致时应保留 UNKNOWN/NEEDS_FOLLOWUP，而不是通过绝对路径跳转伪造身份确认。

## 5. 对项目进度的实际影响

1. 任务规划和基线确认多次重复，G15 从 11 月 4 日的设计阶段到 11 月 16 日才形成第一切片主线核验。
2. 审计任务与修复任务争用同一个 Cursor 投递通道和 Controller 注意力。
3. 普通过程偏差被升级为 Follow-up 后，后续切片被前置 Review 状态串行阻塞。
4. Controller 自身错误又产生额外核查成本，削弱了审计系统本应提供的确定性。
5. main dirty/untracked 文件仍需保护；不能为了“干净验收”而 reset、clean、stash、覆盖或删除。

## 6. 管理改进决策

1. **先收口，不再扩大审计：** 仅执行一次 W07 mainline evidence follow-up，复用 W06 已有测试证据，不重跑测试、不做全量源码复查。
2. **将 Review 拆成三维判断：** Engineering Acceptance、Contract Compliance、Execution Efficiency 分开记录。工具调用预算超出本身不得自动否决工程成果。
3. **硬边界优先：** 未授权写入、破坏性操作、错误 Workspace 身份、测试未授权、证据链无法绑定、盲目重试，仍是实质阻断项。
4. **Reviewer 风险驱动：** 只对架构敏感、高风险、争议结果或证据独立性不足的任务安排独立 Reviewer；不为普通窄切片制造 Reviewer-of-Reviewer 循环。
5. **线性恢复 G15：** 主线证据确认后，按 G15.2 Feedback/Care → G15.3 Skip/Refuse → G15.4 Discard/Restore 顺序推进；最终再做一次定向 Factory E2E。Free-card 继续独立为 G16。
6. **不重构基础设施：** 不修改 Dispatcher、Watcher、Relay、Bridge、全局 Hooks、Loop 绑定或全局 Controller 角色合同来解决本次进度问题。

## 7. 下一步唯一优先路径

### Step 1 — W07 mainline evidence follow-up（只读、一次）

- 使用现有完整 Token：LT_AR03_G15_MAINLINE_EVIDENCE_FOLLOWUP_W07_20261116。
- 先走官方 plan → prepare → preflight → run；不得直接运行 Cursor prompt，不得绕过 preflight。
- 第一条 Shell 必须从当前 Cursor Workspace 直接检查 Workspace root、Git root、branch、HEAD；不允许用 git -C 或绝对路径跳转来伪装当前 Workspace。
- 若身份不匹配，立即停止并报告 WORKSPACE_IDENTITY_MISMATCH；不读源码、不切换 Workspace、不重试同 Token。
- 若身份通过，最多 8 次工具调用、0 次测试、0 次写入；复用 W06 测试证据。不得重跑测试或清理 dirty/untracked 文件。
- 结果必须区分 W06 的历史过程偏差与当前 main 源码状态。W06 历史 Review 不覆盖、不改写。

### Step 2 — G15.2 Feedback/Care

- 只在 W07 给出可接受的 mainline 证据后，创建新的唯一 Token；不得复用未派发的旧 W05 sibling prompt，也不得直接照搬仍要求 W06 Review=ACCEPTED 的旧 W07 gate。
- 以 main 当前实现重新核对旧准备稿；只写 lifecycle.js、app.js、app.entry.js 和新的 characterization 文件。
- 保留 G14 唯一 Gacha owner、Timer owner、G13 TaskEditor、inline facade、API 顺序、失败/取消/重入语义和晚绑定 Gacha facade。
- 只运行一次预授权 synthetic characterization；失败停止，交付失败证据，不在同一 Worker 中循环调试。

### Step 3 — G15.3 / G15.4 与最终验收

- G15.3 只迁移 Skip/Refuse 业务流程，保留 drawn-card 与 task-list 两种入口的 UI 差异及 promptTaskFeedback await 顺序。
- G15.4 只迁移 Discard/Restore 业务 API 顺序与确认/失败语义；discard list/modal rendering 留在 presentation。
- 最终 Factory E2E 先做 fixture/config 最小依赖审计；仅在当前 main 可独立运行时执行一次定向 E2E。Free-card 不纳入 G15。

## 8. 限制与未决事项

- 本报告不是当前源代码完整性证明；W07 仍需按上述 Workspace 身份门槛完成一次只读核验。
- 当前 main dirty/untracked 文件的精确清单应由后续 Worker 在 main 身份确认后只读核对；不得据此清理。
- W06 的 Review=NEEDS_FOLLOWUP 和 G15 Closeout Batch=OPEN 保持历史事实；不得为了推进而手改 Review、Collection、Receipt、Journal 或 Batch JSON。
- 本报告提出的规则需由项目副控在后续 G15 任务中执行；不得修改全局 Loop 基础设施或 CCGS 所有的角色治理文件。

## 9. 主要依据

- batch-ledgers/LEARNING_TOOL_ARCH_REFACTOR_AR03_G14_GACHA_CORE_20261104.json
- batch-ledgers/LEARNING_TOOL_ARCH_REFACTOR_AR03_G15_TASK_LIFECYCLE_PLAN_20261104.json
- batch-ledgers/LEARNING_TOOL_AR03_BASELINE_RECONCILIATION_20261114.json
- batch-ledgers/LEARNING_TOOL_AR03_BASELINE_RUNTIME_INTEGRITY_REPAIR_20261116.json
- batch-ledgers/LEARNING_TOOL_ARCH_REFACTOR_AR03_G15_TASK_LIFECYCLE_20261116.json
- batch-ledgers/LEARNING_TOOL_ARCH_REFACTOR_AR03_G15_CLOSEOUT_20261116.json
- collections/reviews/tasks/state 中对应 W01/W02/W03/W04/W06 的精确 Token 记录
- dispatch-plans/dispatch-prompts 中 W07 mainline follow-up 与 G15.2 Feedback/Care 的准备稿
- visible-tab-status.js、controller-loop.js status/pending 的本次只读输出

