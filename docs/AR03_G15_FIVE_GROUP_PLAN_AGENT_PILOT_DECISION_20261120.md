> **SUPERSEDED 2026-11-20:** 本文件曾错误地把 G15 当成整个项目重构里程碑。用户已明确纠正：目标是完整的项目级架构重构（代码迁移、模块化划分、高内聚低耦合实现、功能等价与最终集成），G15 只是其中一部分。不得再把本文件的 G15-only 范围作为当前授权；请以 `AR03_FULL_PROJECT_REFACTOR_FIVE_GROUP_DIRECTIVE_20261120.md` 为准。原文仅保留作决策纠错记录。

# Main Controller → AR03 Project Refactor Subcontroller
# G15 五组 Plan + Agent 里程碑试点决策（历史版本，已废止）

- DIRECTIVE_ID: AR03_G15_FIVE_GROUP_PLAN_AGENT_PILOT_20261120
- ISSUER: Main Controller（基于用户 2026-11-20 明确决定）
- RECIPIENT: AR03 Project Refactor Subcontroller C
- STATUS: SUPERSEDED — retained for audit only
- DATE: 2026-11-20（UTC+8）

> 本文件是新的用户级项目决策。它更新 G15 的规划方式、执行分组和效率要求；不授权修改 Controller Loop、全局 Kernel、Dispatcher、Watcher、Relay、Bridge、Hooks、CCGS 或其他基础设施，也不改变 G15 产品语义和数据保护红线。

## 0. 用户已经作出的决定（不得再次要求用户确认）

用户决定：**以当前 AR03 前端模块化重构里程碑 G15 作为新架构的第一个真实工程试点；采用 Cursor Plan + Agent 工作模式，由你根据真实源码和依赖进行切片；整个 G15 必须在五组 Agent 执行批次内完成。**

这不是再做一轮架构讨论，也不是重新规划一个新项目。现在应当把已讨论的架构和效率改进应用到现有 G15，继承已验收成果，解决明确遗留问题，完成剩余实现、集成和最终验收。

### 0.1 对“五组 Agent”的操作定义

- 规划阶段使用一次 Cursor **Plan**：基于你刚刚完成的当前情况总结、最新 G15 记录和必要的定点源码证据，形成一个完整的五组执行计划。
- 执行阶段使用 Cursor **Agent**：按依赖顺序逐组执行，最多五组，**一次只允许一组处于活动修改状态**。
- 每组是一个有清晰边界、可以独立验收的执行批次。你负责决定每组的真实切片、文件范围、依赖、测试和验收条件；不要由 Main Controller 预先替你虚构模块切片。
- 不使用 Cursor 内部 Subagent，不使用 /multitask，不并行修改同一模块或存在依赖关系的代码。
- 当前 G15 采用 MANUAL HANDOFF FALLBACK：每个正式 Worker 仍按现行规则使用新的顶层 Cursor Chat、唯一 TASK_TOKEN、用户手动粘贴执行和自动 Handoff 回传。五组在你的项目计划中属于**同一个逻辑 G15 里程碑下的五个执行组**。
- 当前 Controller Loop 尚无证据支持一个逻辑 Task 原生聚合五个 Session Attempt。不要伪称 V1.0 的 Task Identity / Attempt 生命周期已实现；正式 Loop 生命周期仍按现行事实记录为 NOT_REPRESENTED。不要手工编辑 canonical JSON。
- 每组只在前一组完成并被你验收后开始。不得同时提交两个修改任务，不得重叠 write scope。
- 五组计划必须覆盖 G15 完成所需的全部必要工作；第 5 组必须保留给最终集成、定向验收和里程碑收口。若你发现真实范围无法在五组内安全完成，先说明具体冲突和最小取舍，不得隐瞒未完成项或擅自扩成第六组。

## 1. 角色与责任：按新架构工作

### L1 — Main Controller（本指令发出方）

负责产品哲学、系统级架构、里程碑目标、跨里程碑边界和最终关单。已经明确的 G15 目标不需要逐组重新向 Main Controller 请示。仅在跨域冲突、产品语义变化、权限/数据红线、不可逆操作或五组范围无法安全收敛时升级。

### L2 — Project Refactor Subcontroller（你）

负责：
- 继承当前真实状态并完成有限 Recon；
- 在 Plan 中确定五组的模块边界、依赖顺序和每组验收；
- 基于真实代码冻结接口、模块职责、唯一写者和跨模块不变量；
- 为每组准备最小充分的 Agent Prompt；
- 审查每组的实际 Diff、测试输出和 Handoff；
- 将已接受成果集成到 G15 主线；
- 维护简洁、可交接的进度和最终收口记录。

你是项目领域负责人，不是每个工具调用都要向 Main Controller 汇报的操作员。普通切片、局部实现和正常验收由你自主推进。

### L3 — Cursor Agent（每组的执行者）

在冻结的组级合同和精确 write scope 内，自主完成该组内部的工程切片、编码、调试和被授权测试。不得改变模块公开合同、跨组依赖或产品语义；发现合同冲突时停止并报告。

### 确定性控制面

控制面是基础设施，不是第四个智能体。负责已有系统能够提供的状态、身份、证据、Handoff、哈希和机械检查。不要假设当前 Loop 已经实现 V1.0 所有能力。

## 2. 新架构的工作协议

### 2.1 两阶段合同握手

执行顺序固定为：

**Recon → Contract Freeze → Autonomous Execution**

- **Recon**：Agent/你只读检查真实代码、依赖、历史债务、当前 owner 和已有测试；产出简洁契约草案。禁止脱离源码设计“象牙塔合同”。
- **Contract Freeze**：你基于真实源码裁决模块边界、公开接口、数据所有权、依赖方向、跨模块不变量和 Protected Paths。五组计划及组级合同确定后，不得静默扩大范围。
- **Autonomous Execution**：Agent 在组级合同内自主组织内部工作，不需要把每个函数、每个文件编辑动作都升级成一个外部任务。

若真实实现迫使跨组合同变化，记录 Proposed → Approved → Frozen 的修订过程；不得覆盖旧决定或悄悄改变后续组的输入。

### 2.2 契约四件套与零重复原则

需要时使用以下四种载体，不要为了形式给每个模块都生产冗长文档：

1. **MMC 架构摘要**：目标与 Non-Goals、模块职责/不负责事项、聚合数据所有权、事务/一致性策略、Protected Paths。
2. **真实接口代码**：公开类型、Protocol/Interface、DTO、错误定义。以真实代码为准。
3. **冻结契约测试**：跨模块行为、边界条件、异常合同和系统不变量。
4. **轻量 ADR**：仅记录反直觉权衡、历史妥协或正式合同修订原因。

代码和测试已经精确表达的事实，不要在 Markdown 中重复维护。MMC 不以“一页”为硬限制，以信息完整、无重复、可执行为准。

### 2.3 模块治理

- 以聚合/权威数据实体为单位确立**唯一写者**；不得让多个模块同时维护同一业务状态。
- A → B → C 不被绝对禁止：若 B 承担业务编排、状态机、权限、事务或防腐层职责，可以保留；纯参数透传壳应消除。
- Common 只放纯技术原语和归属明确的共享契约，不得反向依赖业务模块。
- 不新增模块级静态循环依赖；历史例外登记并逐步减少。
- 跨模块事务必须说明由统一工作单元编排，还是采用事件驱动最终一致性；若是后者，说明幂等和补偿语义。
- 模块内部实现细节由 Agent 自主决策；跨模块公开接口、数据写权和不变量由你冻结。

### 2.4 状态、恢复与验收原则

V1.0 提出的 Task.status / Task.phase / Attempt.status 正交模型、追加式 Contract Revision Ledger、Stable Checkpoint、Recovery Snapshot、隔离 Worktree 验收，是目标架构原则。当前 G15 只采用现有基础设施能可靠支持的部分；不要为试点假装这些 Loop 能力已落地，也不要在本次 G15 里擅自改造 Loop。

- Stable Checkpoint 代表已完成且验证通过的状态；Recovery Snapshot 只保留中断现场，不代表验收通过。
- 不允许无前置检查的自动 git reset --hard。
- Liveness、Progress、Circuit Breaker 职责分离；但本次不建设新 Watchdog、不做高频轮询、不持续采集 Cursor 轨迹。
- 验收应以实际 Diff、冻结合同、真实测试输出和风险审查为依据，不以 Agent 自报结论代替证据。
- 高风险跨模块合同变化做强制重点审查；普通窄范围切片由你直接审查，不新增独立 Reviewer Agent，不形成 Reviewer-of-Reviewer 循环。

## 3. 当前 G15 状态：继承，不推倒重来

以下来自截至 2026-11-19 的项目 docs/WORK_LOG.md、W19–W22 记录和现行交接规则。你刚刚完成的当前情况总结如包含更新、更可靠的证据，应先对照并补充；不要机械照抄旧快照。

- G15.1 普通任务生命周期已有实现和指定 characterization 通过证据；不要无理由重做。
- G15.2 Feedback/Care：W19 的指定 M1.3D A/B Chromium 验证通过，Controller 记录为 Engineering Acceptance PASS、Contract Compliance PASS、Execution Efficiency OVER_BUDGET。W19 的历史偏差保留，不重复执行。
- G15.3 Skip/Refuse：W21 记录为 Engineering Acceptance PASS、Contract Compliance PASS、Execution Efficiency OVER_BUDGET。不得因预算超出而重开已验收切片。
- G15.4 Discard/Restore：W22 主体迁移已完成，但 Controller 最终结论为 PARTIAL。已确认缺陷：loadDiscardPileList() 只在 GET 前检查 renderDiscardPileLoading；renderDiscardPileEmpty、renderDiscardPileItems、renderDiscardPileError 中任意一个单独缺失时，仍可能发起 GET，导致结果无法呈现。旧测试只证明所有适配器一起缺失时不请求，没有逐项覆盖。
- W22 还存在一次额外测试重跑的 Contract Compliance 偏差，历史记录应保留。不要重写 W22 记录，也不要将该偏差归咎于后续 Worker。
- W22 的明确下一步是窄范围 W23 remediation：在 GET 前预检全部必要列表渲染适配器，分别覆盖单个适配器缺失的情况，并保持既有行为。
- G15 后续还包含最终 Factory E2E / 集成收口；Free-card 属于 G16，明确不纳入本次 G15。

**第一组优先处理当前仍未关闭的最高依赖阻塞项（很可能是 W23 remediation）。** 但派发前必须先检查你刚刚的现状总结、MANUAL_HANDOFF_LOG、是否已有 W23 prompt/Token/提交迹象及精确 Handoff。若 W23 已经提交、正在执行或状态不明，绝不复用 Token、绝不盲目重发；先按现行规则对账。若它已完成，则第一组应转为下一项真实未完成依赖。

## 4. 五组 Plan 必须由你真实切片

不要由 Main Controller 预设五组的文件清单。请在 Plan 中根据真实源码和依赖确定每组内容，但必须满足：

- 恰好五组，编号 G1–G5；每组都是有明确业务结果的可验收闭环，而不是按文件数量机械切分。
- G1 解决当前最高优先级、阻止后续安全推进的已确认缺陷/合同阻塞。
- G2–G4 按真实模块依赖、唯一写者和接口冻结顺序安排剩余 G15 工作；允许将强耦合的相关模块放在同一组，禁止把同一 owner 的互相依赖改动拆成并行任务。
- G5 负责最终集成、定向 Factory E2E/回归证据、G15 完成条件核对和最终交接。不得把关键验收留到五组之外。
- 已通过的 G15.1、G15.2、G15.3 只做必要的集成兼容性检查，不重跑历史测试，不为了“统一风格”重构它们。
- 每组写明：目标、Non-Goals、前置依赖、模块/数据 owner、精确 write scope、冻结接口/不变量、唯一授权测试命令及次数、验收标准、停止条件、预估复杂度和风险。
- 五组之间的 write scope 尽量不重叠。确需修改共享接口时，将接口变更和所有直接依赖放在同一组，或明确先后顺序。
- 计划阶段只做只读 Recon；不要在 Plan 中提前修改源码或测试。
- Plan 冻结后，按 G1 → G5 顺序执行。除非发现真实合同冲突，不要每组结束后重新扫描全仓或重做整套 Plan。

## 5. 效率升级：这次必须实际执行

以下不是口号，是本次试点的执行约束。

### 5.1 一次有效 Recon，禁止重复探索

- 以你刚刚完成的当前情况总结为起点；对照最新 WORK_LOG、MANUAL_HANDOFF_LOG 和必要的源码/测试，不从零重新扫描整个仓库。
- 先列出已可信的事实和证据位置；只读取当前组需要的代码、依赖和测试。
- 同一文件已读且没有发生变化，不重复读取；同一事实已有可靠记录，不再次独立测试证明。
- 不要求 Worker 重复 Main Controller 或 Subcontroller 已完成的全量调查。

### 5.2 测试只为验收服务

- 每组在 Prompt 中明确唯一授权测试命令和允许执行次数；默认一次。
- 测试前检查解释器/命令存在，并一次性设计好测试输入和断言。
- 首次运行失败：保留完整原始输出，停止该 Worker；不得在同一 Worker 中修补后重跑、换解释器重跑或不断试到绿色。由你判断是否需要在剩余五组预算内安排一个有明确改变因素的后续组。
- 不额外运行未授权的 lint、build、typecheck、E2E、smoke、浏览器检查或“保险测试”。
- 已通过的历史测试不重复运行。最终 E2E 只在 G5 按明确授权执行。
- 不把“测试越多越好”当成目标；选择能验证当前合同和风险的最小充分测试。

### 5.3 主控/副控停止式协作

- Worker 完成派发后，按人工 Handoff 流程等待结果；不要持续轮询、反复读取状态或实时追踪 Cursor 每一步。
- 不做几十分钟的独立实时测试来观察 Agent 轨迹；Agent 的授权测试输出、自动 Handoff 和原始 Trace 是证据来源。
- 你只在结果到达后做有界核验：Token/Conversation/Generation/Workspace 身份、实际 Diff、指定测试结果和必要风险点。
- 达到验收条件就停止，不追加无收益的检查。
- 不因“想确认一下”而重复执行已经有证据的动作。

### 5.4 审查与工具预算

- 不新增 Reviewer-of-Reviewer；你是本里程碑的审查责任人。
- 仅在跨模块公开合同、数据写权、安全/持久化或证据争议等高风险场景增加独立复核；普通窄切片直接审查。
- 工具调用预算是效率目标/诊断阈值，不是自动工程否决条件。记录实际 Trace 口径、重复探索和自报差异；不得仅因超预算将 Engineering Acceptance 判 FAIL。
- 每组都分别报告 Engineering Acceptance、Contract Compliance、Execution Efficiency。正式 Review 状态仍使用现有系统支持的枚举。
- 任务 Prompt 提供最少但足够的上下文；不要复制数百行历史作为默认输入。

## 6. 每组 Agent 的派发合同

继续使用现行 MANUAL HANDOFF FALLBACK，不依赖 Loop 自动物理派发、Relay 唤醒或 CIG 修复。

每组 Worker 必须：
1. 使用一个全新、唯一 TASK_TOKEN；先核对该 Token 从未提交或状态不明。
2. 明确目标 Workspace：D:\Axelit\.工作\trae\超级自动化学习工具，预期 branch=main。
3. 第一条 Shell 在当前 Cursor Workspace 直接核验 git rev-parse --show-toplevel、git branch --show-current、git rev-parse HEAD，并核对 Workspace metadata；身份不匹配立即停止，不读源码、不写入、不测试。
4. 明确精确 write allowlist，不使用通配符，不擅自扩大路径。
5. 明确唯一授权测试命令、次数、退出码和 PASS 判据。
6. 明确 Non-Goals、禁止触碰文件、停止条件和最终回复结构。
7. 保留现有 dirty/untracked 文件；不得 reset、clean、stash、checkout、switch、commit、push、覆盖或删除。
8. 不使用 Cursor 内部 Subagent 或 /multitask。
9. 完成后由基础设施自动生成 Handoff；Worker 不手写/伪造 Handoff、Receipt、Collection、Review 或 Batch 状态。

你向用户每次只交付当前一组的完整 Prompt 和简短操作说明。用户执行并回传 Handoff 后，你核验并推进下一组。不要一次向用户倾倒五份长 Prompt，也不要并行提交五组。

## 7. 工程与数据保护红线

- 唯一产品目标：D:\Axelit\.工作\trae\超级自动化学习工具，branch=main。
- 历史记录在 2026-11-20 17:49 曾观察到 main HEAD=2236ac2e2ffe8aa06030aa07b141d7f3bd69633b，Git status 有 246 项（25 tracked dirty、221 untracked）；这是历史观察值，不是新的永久基线。每组 Worker 都必须现场核验。
- 所有既有 dirty/untracked 状态视为用户资产，原样保留。不得清理、覆盖或删除。
- 不切换到 sibling 超级自动化学习工具-ar03 Worktree，不以绝对路径或 git -C 伪造 Workspace 身份。
- 不读取/修改真实 SQLite、WAL/SHM、Obsidian Vault、notes、凭据、配置和用户数据；测试使用合成数据/临时隔离环境。
- 不改后端 API、数据库 Schema、生产配置或非 G15 模块，除非用户另行明确批准并重新冻结合同。
- 不修改 Controller Loop、Kernel、Dispatcher、Runner、Watchdog、Hooks、Relay、Bridge、插件绑定、全局规则、CCGS 文件或 Main-owned 治理计划。
- G16 Free-card 明确不在 G15 范围内。

## 8. 当前基础设施与 V1.0 的适配边界

已知现状：
- G15 目前是 MANUAL HANDOFF FALLBACK；你准备 Prompt，用户手动粘贴到新顶层 Cursor Chat 并执行，再将自动 Handoff 返回。
- 正式 Handoff 必须由基础设施生成；全局 LATEST_HANDOFF 是 last-writer-wins 指针，不能仅凭最新时间或文件名认定归属，必须匹配 TASK_TOKEN 和 Conversation/Generation/Workspace。
- 现有 Kernel 禁止 Cursor 内部 Subagent 和 /multitask。
- 现有 Controller Loop 尚无已证实的 Milestone Task Identity / 多 Attempt 原生聚合能力；不得伪造支持。
- 当前 Watchdog 是观察型机制，不是自动停止、自动重试或自动唤醒系统。

因此，本次只把新架构中可直接应用于 G15 的部分落地：L1/L2/L3 职责、Plan/Recon、Contract Freeze、内部真实切片、唯一写者、接口/依赖治理、最小充分测试、风险导向验收和低协调开销。

Task/Attempt 数据模型、自动 Contract Ledger、外置 MILESTONE_STATE、Recovery Snapshot 自动化、Circuit Breaker、隔离 Worktree 验收、Loop 十项兼容性改造，均不属于本次 G15 代码交付范围。不要为了“完整实施 V1.0”而扩张 G15 或修改基础设施。

## 9. G15 完成定义（G5 必须逐项核对）

只有以下条件全部满足，才可以向 Main Controller 报告 G15 完成：

- G15.1–G15.4 已有的业务迁移和 owner 边界均可继承，所有明确的 PARTIAL 项已在本次五组内关闭。
- Task Lifecycle、Feedback/Care、Skip/Refuse、Discard/Restore 的唯一 owner 与 presentation/DOM adapter 边界清晰，无重复写者。
- 跨模块依赖方向、公开接口、状态所有权和关键异步顺序符合冻结合同；没有新增模块级静态循环依赖。
- W22 已确认的列表渲染适配器 fail-closed 缺陷得到修复，并有逐项缺失的 characterization 证据。
- 最终 Factory E2E 在安全的合成环境中完成一次有授权的定向验证；未覆盖项明确列出，不以历史 Legacy 36/36 冒充 Factory 验收。
- 所有五组的实际修改文件、测试结果、Handoff 身份、合同偏差和三维评价可追溯。
- 用户原有 dirty/untracked 文件、真实 DB/WAL/SHM、Vault、配置和 notes 未被触碰。
- G15 之外的 G16 Free-card 没有混入。
- 项目 WORK_LOG / 简洁进度记录更新，交接文档说明 G15 最终状态、未解决事项（如有）和下一条主线。
- 若有未完成项或环境阻塞，必须如实报告 PARTIAL / BLOCKED / INCONCLUSIVE，不得为了满足“五组”目标伪造 PASS。

## 10. 现在立即执行的下一步

1. 以你刚刚完成的当前情况总结为起点，读取本指令；只补足影响五组切片的必要事实。
2. 核对 W22 后是否已有 W23 Token、Prompt、提交尝试、执行会话或 Handoff；精确身份对账，不盲目重发。
3. 使用 Plan 模式提交一份**恰好五组**的 G15 真实执行计划。计划应简洁但可执行，包含组目标、依赖、write scope、授权测试、验收和风险。
4. Plan 完成后冻结总体分组，不再重复全仓 Recon；按 G1 → G5 顺序执行。
5. 只向用户交付 G1 的完整 Worker Prompt；等待用户手动执行和回传 Handoff，完成有界 Review 后再进入 G2。
6. 每组结束后更新你自己的 G15 进度记录；五组全部完成后提交 G15 最终收口报告。

**不要把这条指令变成新的治理项目。现在的任务就是：用五组 Agent，按真实依赖完成现有 G15。**
