# 项目交付与交接规则补充（2026-11-16）

> 适用范围：学习工具 AR03/G14/G15 项目交付、Worker Handoff、Collection、Review 与 Batch 收口。
> 性质：Main Controller 对本项目的补充执行规则；不修改或取代 Controller Governance Kernel、START_HERE_CONTROLLER.md、全局 Dispatcher/Watcher/Relay/Bridge 或 CCGS 角色治理规则。
> 目标：保留可追溯性和安全边界，同时阻止普通过程偏差制造无收益的审计循环。

## 1. 总原则

**交接的目的是让下一个责任人可以安全、准确地继续工程，而不是让每个 Worker 生产尽可能多的审计材料。**

任何任务都要区分以下四种状态：

1. Transport：是否真实提交、是否有唯一 Conversation/Generation、是否形成正式 Handoff。
2. Engineering：交付物是否满足目标，测试/源码证据是否可信。
3. Process：是否遵守 Workspace、写入范围、授权、测试预算和执行约束。
4. Batch/Milestone：官方 Batch 是否结算、整体里程碑是否完成。

其中任何一项都不能替代其他项。Handoff 不等于工程验收；工程 PASS 不等于 Batch CLOSED；Batch CLOSED 不等于整个 Milestone 完成。

## 2. Review 必须分开记录三个评价维度

每次 Review/Controller 裁决应在现有 Review note 或关联 Batch action 中明确写出：

- **Engineering Acceptance**：PASS / FAIL / UNKNOWN。只判断代码、测试、行为和交付物是否达到目标。
- **Contract Compliance**：PASS / DEVIATION / BREACH。判断 Workspace、write scope、授权、数据边界、测试许可、重试规则和 subagent 禁令。
- **Execution Efficiency**：ON_TARGET / OVER_BUDGET / LOW_PROGRESS。判断工具调用、重复读取、调试轮数和任务时间是否合理。

不得新增或伪造 Controller Loop 不支持的 Review 状态。正式 Review 仍使用当前系统支持的 ACCEPTED、REJECTED、NEEDS_FOLLOWUP；三维评价写在说明中，不修改状态枚举。

### 2.1 ACCEPTED

当交付物满足验收标准、关键证据链可信、没有影响成果可信度的硬边界违规时，可以 ACCEPTED。

即使存在非阻断的预算偏差，也可以 ACCEPTED，但必须在 Review note / Batch action 明确记录偏差、计数口径、影响和后续改进。ACCEPTED 不代表过程完全合规。

### 2.2 NEEDS_FOLLOWUP

仅在以下情况使用：

- 关键证据缺失、身份无法绑定或存在实质冲突；
- 有明确、可定位的工程缺陷；
- 需要补充一项有限证据才能判断工程结果；
- 现有结果可能正确，但尚不足以安全继承。

必须写明“缺少什么、为什么影响判断、最小补证动作是什么”。不得仅写“工具调用超预算”而不说明它如何损害成果或证据。

### 2.3 REJECTED

用于交付物存在实质性错误，或发生影响成果可信度的硬边界违规，例如未授权写入、破坏性操作、读取/修改错误项目、绕过授权测试限制、伪造证据或盲目重放。

如过程违规与工程成果可分离，应明确保留可用成果与不可接受的执行记录，不得把两者混为一谈。

## 3. 硬边界与软预算

### 3.1 硬边界（必须遵守）

- 唯一目标 Workspace、Git root、branch/commit 身份必须符合合同；身份不一致时先停止，不得通过绝对路径跳转、git -C 或切换目录伪造身份。
- 只能写入合同明确授权的文件；不得修改受保护数据、notes、Vault、凭据、用户数据或未授权源码。
- 不执行未经授权的测试、真实服务操作或 Git mutation。
- 不执行 destructive 操作；不得 reset、clean、stash、checkout、switch、commit、push，除非另有明确授权。
- 一个 Token 只对应一次正式提交；不确定提交不得盲目重试。
- 禁止 Cursor 内部 subagent 和 /multitask。
- Handoff 必须由现有基础设施生成；Worker 不得手工伪造 Handoff/Collection/Receipt/Review。

硬边界违规必须停止并保留 UNKNOWN/NEEDS_FOLLOWUP/REJECTED 中最符合证据的状态，不得为了赶进度绕过。

### 3.2 软预算（用于效率管理，不自动否决工程成果）

- max_tool_calls 默认是执行目标/诊断阈值，不是自动的工程验收门槛；当前系统无法保证在精确第 N 次工具调用时强制停止。
- expected_minutes / review_after_minutes 是计划和诊断参考，不是 Worker 的后台执行承诺。
- 工具调用超出预算时，记录原始 Trace 计数、计数来源、自报差异、是否存在重复探索、是否产生未授权副作用；再判断是否影响工程证据。
- 单纯超出工具调用预算，不得自动触发新的 Auditor Worker，也不得自动将 Engineering Acceptance 判为 FAIL。
- 明确约定的“一次测试”属于测试执行约束；一旦运行，不得在同一 Worker 中重复试跑。若发生额外测试，记录偏差并判断是否影响结果可信度；不能只因次数超出就忽略已经存在的有效测试结果。
- 工具调用统计必须说明口径：postToolUse records、unique tool_use_id、Worker 自报次数不是同一概念。postToolUse 也可能遗漏被阻断调用，不得混用或伪称为精确总调用数。

## 4. 派发前 Controller 自检

派发者必须先检查合同正确性，不能把 Controller 的数据错误转嫁给 Worker：

1. 确认唯一 Workspace、branch、HEAD、目标文件路径和依赖。
2. 如果合同引用 SHA-256，必须从正确文件、正确 Worktree、正确时间点现场计算；不得复制旧 Handoff 中的过期哈希。
3. 对关键源文件快照，记录路径、SHA、文件大小和采集时间；派发前再次确认没有被后续写入覆盖。
4. 若 SHA 不匹配，先核实路径、换行规范、采集时点和最近一次 Write；未证明前不得归因于源文件漂移或 Worker 篡改。
5. 明确唯一业务目标、write scope、允许测试命令和执行次数、成功/失败判据、停止条件。
6. 预算应按任务复杂度设为合理目标；不要用极低预算迫使 Worker 在“完成工程”和“满足计数”之间取舍。
7. 在 Prompt 中给出最少但足够的上下文；不要要求 Worker 重新扫描已被可靠记录的全部历史。

若 Controller 后续发现自己提供的路径、SHA、代码归因或验收条件有误，应在新记录中明确标注“Controller-side correction”，并引用准确证据；不得让 Worker 背负该错误，也不得改写旧 Review。

## 5. Worker 执行与停止规则

- 一个正式 Worker = 一个新 top-level Cursor chat = 一个唯一 TASK_TOKEN = 一个正式 Handoff。
- 一个 Worker 只承担一个可验收的业务切片；不得自行扩展邻近模块、创建子任务或改变架构方向。
- 先读合同指定的文件与依赖，不做全仓扫描；已由可信 Collection/Review 证明的事实可直接引用。
- 到达验收条件后立即停止，不额外运行 lint/build/E2E/smoke 或第二套测试。
- 指定测试失败时，保留第一次完整失败输出并停止；由 Controller 判断是否需要一个新 Token 和一个明确改变因素的修复任务。
- 不在同一个 Worker 中用重复测试试错。不得把“多跑几次直到绿”作为默认策略。
- Worker 遇到合同错误、Workspace mismatch、写入范围不足、关键依赖缺失时，应停止并报告，不得自行扩大权限。

## 6. Handoff 最小充分结构

Handoff 由基础设施自动生成。Worker 的最终答复应简短、可核验，不重复长篇过程叙述；至少包含：

1. 原始 TASK_TOKEN / TASK_ID，以及实际 Conversation ID / Generation ID（若已绑定）。
2. 一句话目标与最终结果：PASS / FAIL / BLOCKED / UNKNOWN。
3. 实际修改文件清单；每个文件说明新增/修改/删除与关键函数/模块。只读任务明确写“无修改”。
4. 测试命令、实际执行次数、退出码和关键 PASS/FAIL 摘要；未运行的测试写 SKIP/NOT RUN。
5. 原始 Trace 的计数口径和数量：postToolUse records、unique tool_use_id、Worker 自报值分别列出，不得混称。
6. 合同偏差：工具预算、测试次数、Workspace、write scope、重试、subagent 等；没有则写 NONE。
7. 未完成事项、风险、当前阻塞和建议的下一步。
8. 不输出隐藏推理或冗长的逐步工具日志；提供精确文件路径和可追溯证据即可。

Worker 不需要为每个工具调用写解释，也不需要在 Handoff 中复述所有已知背景。

## 7. Reviewer 与 Follow-up 规则

### 7.1 Reviewer 按风险使用

独立 Reviewer 优先用于：
- 架构边界/跨模块所有权发生变化；
- 真实数据、权限、安全、持久化或高风险行为；
- 结果与预期冲突、证据链存在争议；
- 主控明确需要独立复核的关键里程碑。

普通窄范围、可重复验证的单文件/单模块改动，可由拥有该任务的 Controller 根据 Worker 证据和指定测试完成验收，不强制再派一个 Reviewer。

### 7.2 禁止 Reviewer-of-Reviewer 常态化

- 不因 Worker 超出软工具预算而派发一个 Auditor。
- 不因 Auditor 自己超预算而继续派发 Auditor 的 Auditor。
- 只有发现影响工程正确性、身份可信度、权限边界或证据绑定的实质问题，才创建一个窄范围 Follow-up。
- 复核任务必须说明新增证据价值；如果只是重新统计已经存在的 Trace，不应成为新 Worker。
- 如果前一 Reviewer 出现事实错误，优先由 Controller 用已存在的原始证据做纠错，并追加 Controller-side correction 记录；只有原始证据不足时才派发独立复核。

### 7.3 Follow-up 必须有明确停止点

每个 Follow-up 只解决一个已确认缺陷或一项关键证据缺口；不得重新扫描全仓、重跑已通过测试或重审无关模块。Follow-up 完成后立即返回原工程主线。

## 8. Batch 与证据记录

- 只使用官方 batch-supervisor / controller-dispatch-task / controller-loop / Collector / Review 流程。
- 在派发前将 Token 登记到正确的 canonical Batch；每次正式派发使用新 Token。
- Batch Ledger、Task、State、Receipt、Collection、Review 都由官方工具维护；不得手工编辑 JSON、伪造状态或回写历史结果。
- 发现历史 Review/Collection 有误时，不覆盖历史文件；使用新 Review 或 Batch action 记录纠错与 supersession 关系。
- 一个 Token 的提交状态不明确时，保留 UNKNOWN，不重试；先按 START_HERE_CONTROLLER.md 规定做一次有界只读对账，然后把观察权交给既有 reconciler/watcher。
- 结算时逐项核对 canonical Batch 中所有任务与 Follow-up；不能因为当前工程切片已完成就擅自关闭尚未结算的 Batch。

## 9. Workspace 与 mainline 身份规则

涉及 AR03 mainline 的任务，第一条 Shell 必须直接在当前 Cursor Workspace 中执行：

- git rev-parse --show-toplevel
- git branch --show-current
- git rev-parse HEAD

同时核对 Cursor Handoff 的 workspace_root。三者必须与合同目标一致。若 Cursor metadata 与 Git root 不一致，立即停止，不读取项目源码、不写文件、不运行测试。

禁止：
- 在 sibling Workspace 中使用 main 的绝对路径来声称当前 Workspace 是 main；
- 使用 git -C、cd 到另一 Worktree 或切换窗口绕过 Workspace 身份门槛；
- 把 sibling branch-only 测试结果当作 mainline 验收；
- 清理、reset、stash、checkout、switch、覆盖或删除 main dirty/untracked 文件。

当前 AR03 产品主线目标为：
D:\Axelit\.工作\trae\超级自动化学习工具
branch=main
基线 HEAD 以当前 canonical task/Review 的授权快照为准；历史 HEAD 不得直接当作永久常量。

## 10. G15 当前执行顺序

1. **W07 mainline evidence follow-up：** 只读、一次、最多 8 次工具调用、0 测试、0 写入；通过当前 Workspace 身份门槛后复核 W06 已有证据，不重跑测试。
2. **G15.2 Feedback/Care：** 仅在有可接受的 mainline 证据后使用新 Token；只迁移 feedback/care 私有状态和业务流程，保留 G14 唯一 Gacha owner、Timer、G13 editor、API/失败/取消/重入语义。
3. **G15.3 Skip/Refuse：** 单独切片，保留 drawn-card 与 task-list 入口的 UI 差异以及 promptTaskFeedback await 顺序。
4. **G15.4 Discard/Restore：** 单独切片，仅迁移业务 API 顺序与确认/失败语义；discard list/modal rendering 留在 presentation。
5. **最终 Factory E2E：** 先审查 main 缺失的 fixture/config/server 依赖并做最小移植；只执行一次定向验证。Free-card 作为独立 G16，不纳入 G15。

不得以旧 G15.2 准备稿中“W06 Review 必须 ACCEPTED”这一历史门槛自动阻断后续工作。新的 G15.2 Token 应以本规则认可的 mainline 证据收口结果为前置；不得伪造 W06 Review=ACCEPTED，也不得改写 W06 历史记录。

## 11. 明确禁止的反模式

- 为了让所有记录看起来整齐而反复派发审计 Worker。
- 把工具调用预算当成工程质量的替代指标。
- 将 Controller 自己的 SHA、路径、基线或归因错误记到 Worker 名下。
- 为了通过验收重复运行已经通过的测试。
- 以“Workspace 已打开”代替真实 Workspace/Git 身份核验。
- 把 Handoff=存在、Review=ACCEPTED、Batch=CLOSED 或 Milestone=完成混为一谈。
- 通过直接编辑历史 JSON 或 Review 来修复流程问题。
- 以治理改进为由修改全局 Dispatcher、Watcher、Relay、Bridge、Hooks、权限或 Loop 绑定。

