# Main Controller → AR03 Project Refactor Subcontroller
# 全项目架构重构：五组 Plan + Agent 总指令

- DIRECTIVE_ID: AR03_FULL_PROJECT_REFACTOR_FIVE_GROUP_20261120
- ISSUER: Main Controller（依据用户 2026-11-20 最新明确指令）
- RECIPIENT: AR03 Project Refactor Subcontroller C
- STATUS: ACTIVE
- DATE: 2026-11-20（UTC+8）
- SUPERSEDES: AR03_G15_FIVE_GROUP_PLAN_AGENT_PILOT_20261120

> **范围纠正：本指令目标是整个项目重构里程碑，不是 G15。G15 只是整个重构中的一个前端生命周期迁移切片。** 旧 G15-only 指令已标记 SUPERSEDED，只保留审计记录，不得再作为当前目标范围。

## 0. 用户的最终决定

用户明确要求：**在五组 Cursor Agent 执行批次内，彻底完成整个「超级自动化学习工具」项目重构里程碑，包括代码迁移、模块化划分、高内聚低耦合的代码架构实现，并确保重构前已有功能不丢失。**

本次交付不是“完成 G15”，不是只完成前端生命周期迁移，也不是再做一轮架构讨论。必须覆盖 Main Controller 已定义的整个项目架构重构范围；G15 及其遗留问题只是其中一部分。

五组是整个项目重构的总执行预算，不是五组 G15，也不是允许删除功能、缩减验收或把未完成工作移到第六组的借口。

### 0.1 五组执行定义

- 先使用 Cursor **Plan** 模式，对整个项目重构做一次真实 Recon、依赖梳理和五组切片规划。
- Plan 必须覆盖整个项目重构目标；不能只围绕 G15 规划。
- 随后使用 Cursor **Agent** 模式，严格按 G1 → G5 顺序执行五组真实工程批次。
- 每组都必须有可验收的工程交付物；G5 必须完成全项目集成、功能等价验收和最终收口。
- 五组可以分别覆盖多个紧密相关的内部切片；内部切片由 Cursor 在授权范围内自主安排，不应再拆成大量微型外部 Worker。
- 一次只允许一组处于活动修改状态。存在依赖的模块必须顺序执行；不得为了并行而制造共享工作区冲突。
- 当前仍采用 MANUAL HANDOFF FALLBACK：每组使用新的顶层 Cursor Chat、唯一 TASK_TOKEN，由用户手动粘贴并执行，自动 Handoff 回传。不得假装当前 Loop 已原生支持一个里程碑 Task 聚合五个 Session Attempt。
- 不使用 Cursor 内部 Subagent 或 /multitask；现行 Kernel 仍禁止它们。
- 五组之外不得另设“补测组”“集成组”或隐性第六组。必要的最终验收必须纳入 G5。

## 1. 主控依据与资料优先级

### 1.1 本次已定位并读取的项目重构依据

1. 项目架构目标与 P1–P5 阶段路线：
   docs/ARCHITECTURE_REDESIGN_2026-08-16.md
2. 当前项目实现状态入口：
   docs/CURRENT_PROJECT_STATE.md
3. 当前架构实现描述（需注意其历史快照日期）：
   docs/ARCHITECTURE.md
4. 近期工程进度和 G15 交付审计：
   docs/ENGINEERING_PROGRESS_AUDIT_20261116.md
5. 项目执行、Workspace、Review 和数据保护规则：
   docs/PROJECT_HANDOFF_REVIEW_RULES_20261116.md
6. 当前人工交接运输规则：
   docs/PROJECT_SUBCONTROLLER_MANUAL_HANDOFF_DIRECTIVE_20261118.md
7. 最新工程工作记录：
   docs/WORK_LOG.md
8. Main Controller 对新 Agent 模块化开发体系的确认事实基线：
   C:\Users\wn\.cursor\controller-loop\docs\AGENT_MODULAR_DEVELOPMENT_CONFIRMED_BASELINE_20261120.md
9. Gemini 协作成果的结构化归档：
   C:\Users\wn\.cursor\controller-loop\docs\gemini-collaboration-archive\05_确认成果与未决事项.md

### 1.2 主控详细 Cursor Plan 的定位状态

docs/ARCHITECTURE_REDESIGN_2026-08-16.md 第 8 节指向一个更详细的 Main Controller Cursor Plan：

C:\Users\wn\.cursor\plans\全盘模块化重构（双文件锁_+_多路线并行）_8b4393f9.plan.md

截至本指令编写时，已检查 C:\Users\wn\.cursor\plans 目录，该文件未出现在当前目录清单中；按该精确路径读取也返回 ENOENT。因此**不能声称已经读取该独立 Plan，也不能凭空补写其中可能存在的细则**。

你在正式 Plan 前应做一次有界定位：检查该 Plan 是否被移动、归档或有等价的 Main-owned 里程碑文件。如果仍不可用：
- 以本指令列出的架构重设计文档、当前项目状态、实际代码和工作记录为已知依据；
- 将“缺失的详细 Plan 可能含有额外约束”列为明确来源缺口；
- 不得编造其内容；
- 如果某项关键决策只能由缺失 Plan 决定，列出精确冲突并升级 Main；其余已有明确依据的部分继续规划，不要因此重复扫描全仓。

### 1.3 资料权威顺序

- 用户当前明确指令优先。
- Main Controller 当前项目重构目标和本文件定义本次里程碑范围。
- CURRENT_PROJECT_STATE.md、ARCHITECTURE.md 和当前源码决定当前实现事实；注意旧文档中的历史快照不能冒充当前状态。
- WORK_LOG.md、Handoff、Trace、Review 是特定日期的历史执行证据；不得重写历史结论。
- ARCHITECTURE_REDESIGN_2026-08-16.md 是明确的目标架构和 P1–P5 路线来源，但应与当前代码和更详细 Main Plan 对齐。
- Gemini V1.0 是新开发体系的架构协议来源；它不自动意味着 Controller Loop 的目标能力已经实现。

## 2. 整个项目重构的目标范围

### 2.1 已冻结的总体架构方向

项目架构重设计文档选择的是：

**Flask Blueprint + Application Factory + Service/Repository + 原生 Feature ESM**

目标是贴合现有 Flask + SQLite + 原生浏览器 JavaScript 技术栈，不引入不必要的框架和构建链。

后端目标分层：
- Blueprint：HTTP 参数解析、调用 Service、返回响应；不直接执行 SQL。
- Service：业务逻辑和编排；不绑定 Flask request/response。
- Repository：SQL/文件系统访问与映射；不承载业务规则。
- Schema：集中定义并由统一入口编排。
- Application Factory：统一配置、资源、Schema 初始化和 Blueprint 注册。
- Legacy compatibility：在功能等价前保留兼容和对照能力；不得提前删除 parity oracle。

前端目标分层：
- app.js：轻量入口和注册/启动，不再承载全部业务。
- core：API、Event Bus、State、Router、UI、常量等基础设施。
- modules：按业务 Feature 自包含，公开 mount/unmount 契约。
- shared：跨模块确有必要的纯共享能力；共享可变状态必须有唯一 owner。
- css：主题、布局、模块样式分离。
- 使用浏览器原生 ESM；保持零构建约束。
- 跨模块不得直接导入其他模块的内部文件；按已冻结规则通过公开接口、事件总线或共享状态通信。
- 模块边界由脚本/测试尽可能机械检查。

### 2.2 Main 重构文档的 P1–P5 交付范围

以下是 ARCHITECTURE_REDESIGN_2026-08-16.md 第 8 节明示的全项目阶段路线，必须全部纳入本次五组总计划：

| 原阶段 | Main 文档定义的范围 | 原文硬门槛 |
|---|---|---|
| P1 | 后端骨架 + 前端 Kernel + 桌面端归档 + 抽卡接口隔离 + Schema 集中 | 36/36 E2E |
| P2 | 后端按域拆分 Blueprint、Repository、Service | 36/36 E2E |
| P3 | 前端 Feature 模块拆分 + 双计时器合并 + 模块边界脚本 | 36/36 E2E |
| P4 | CSS 拆分 + OpenClaw sandbox + theme dark mode | 36/36 E2E |
| P5 | Legacy 化 + scripts 归档 + Schema 一致性脚本 + 交付报告 | 36/36 E2E + 新补回归 |

这五阶段是**整个项目重构范围**，不是 G15 的五个小阶段。你必须根据真实代码确认每项已完成、部分完成、未完成或历史证据不足，再决定如何装入五组 Agent。

### 2.3 目标架构的具体交付物

#### Backend
- Application Factory / 配置 / extensions / Schema 初始化骨架。
- 按业务域迁移现存路由到真实 Blueprint。
- Service 层承接业务逻辑；Repository 层成为数据库/文件系统访问边界。
- 抽卡权重与抽卡流程有明确接口隔离，保持算法行为和历史语义。
- Agent / LLM / Prompts / Config / Discard / Dependencies / Export 等现有功能必须逐项盘点，不能因为 Factory 暂缺或某 BP 当前是 shim 就视为可以删除。
- 后端路由注册、错误响应、状态码、响应字段、事务与副作用保持等价。
- 旧 backend_api.py 只有在 parity 被证明后才能退役；不得先删后补。

#### Frontend
- 将 app.js 中的业务逻辑迁入 Feature 模块，形成清晰 owner。
- Gacha、Tasks/Lifecycle、Timer、Schedule、Sleep/State（以当前真实产品行为为准）、Knowledge、Config/Agent 等现存业务边界逐项核对。
- G15 的 Task Lifecycle、Feedback/Care、Skip/Refuse、Discard/Restore 是整个前端模块迁移的一部分，不是整个重构里程碑。
- 计时器 dock 与任务面板必须使用同一计时状态 owner；保留暂停、恢复、完成、取消、刷新和重入等实际语义。
- Event Bus / State / Router / API / UI 等 core 机制应实际被业务模块使用，而不是只有空壳或 boot report。
- app.js 收敛为入口/兼容 facade；只有迁移和 parity 验收通过后才移除旧业务实现。

#### CSS / HTML / Runtime / Embed
- 将 src/index.html 中的内联 CSS 拆分为 theme/layout/module 样式。
- 保留页面 DOM、语义、可访问交互和现有视觉功能；不允许因样式拆分丢失交互状态或页面区块。
- OpenClaw 嵌入适配遵守项目原设计：明确独立/嵌入态、postMessage 协议版本、显式 targetOrigin、ResizeObserver 尺寸通信。
- iframe sandbox 不允许 allow-same-origin + allow-scripts 的危险组合。
- 保持主题/暗色模式行为。

#### Schema / Desktop / Scripts / Legacy
- Schema 定义集中且可一致性检查；对历史表、索引、外键和默认值进行覆盖核对。
- 桌面端 src/tasks 的归档按已确认方案核实实际状态；归档不是无证据删除，历史实现应可追溯。
- scripts 归档只处理确认属于旧/临时/重复的脚本；启动、停止、迁移、验收、备份和运维脚本不得误删。
- Legacy compatibility 只在新实现功能等价后逐步移除。
- 交付报告必须列出迁移映射、功能保全证据、仍存在的兼容层和未解决项。

## 3. 必须在 Plan 阶段识别的源文件内部不一致

当前已读取的 ARCHITECTURE_REDESIGN_2026-08-16.md 存在目标结构和阶段表述不完全一致的地方：
- 后端目标树列出的 Blueprint 文件数量与“P2 拆 8 个 Blueprint”表述不一致。
- 前端目标树列出的 Feature 目录数量与“P3 拆 5 个模块”表述不一致。
- 详细 Cursor Plan 当前无法按文档中的精确路径读取。

不得擅自选择一个数字并把另一个数字当成过时内容。你必须结合可恢复的详细 Plan、当前代码、现有模块和业务边界，形成一份明确的**最终模块清单及归属**。如果详细 Plan 缺失且无法从其他权威材料确认，应把它作为 Plan 中的待裁决差异，向 Main 提交具体选择，而不是凭空扩张或缩减范围。

## 4. 功能零丢失：本次最高工程验收条件

用户要求重构不发生功能丢失。你必须将其变成可审计的功能保全合同，而不是一句口头保证。

### 4.1 建立重构前功能基线

以本次开始时的**当前真实代码和当前产品行为**为基线，建立一份简洁的 Feature / Contract Matrix。至少逐项覆盖：
- 所有现有 HTTP 路由：方法、路径、参数、状态码、响应结构、错误语义和副作用。
- 所有用户可见页面、控件、操作流程、弹窗、Toast、空态/错误态和导航。
- Gacha 抽卡权重、过滤、换卡、拒绝记录、重抽、冷却、统计和反馈语义。
- Task 创建/编辑/完成/跳过/拒绝/丢弃/恢复、依赖解锁、标签和历史。
- Timer 的 dock / task panel 统一状态、开始/暂停/恢复/完成/取消、持久化和刷新恢复。
- Schedule、daily state、energy/sleep assessment、feedback/care 等当前确实存在的行为。
- Knowledge 浏览、分类、笔记读取、Markdown 渲染、Obsidian 跳转和双目录布局现状。
- Agent / LLM / Prompts / Config / Export / Dependencies 等现有 API 与 UI 能力。
- Schema 表、字段、索引、外键、约束和数据兼容行为。
- OpenClaw 独立运行与嵌入运行、消息协议、主题和样式行为。
- 关键异步顺序、Promise 可观察时序、重入、取消、失败和回滚语义。

基线以当前源码、可复核的历史行为和安全的合成运行结果为准。**不要把已经明确移除的历史功能自动当作当前功能恢复**；例如历史 Sleep 符号已被证据确认在 G15.1 之前就不存在，不得错误归因给后续 Worker，也不得未经产品决定恢复。

### 4.2 迁移映射与唯一 owner

每项基线功能都必须映射到：
- 迁移前实现位置；
- 迁移后唯一业务 owner；
- 对外公开接口或事件；
- 数据读写权；
- 对应的 characterization / contract / integration test；
- 兼容层是否仍保留及移除条件。

禁止出现“旧代码删了，但新模块没有对应实现”的空档。禁止多个模块同时写同一权威业务状态。

### 4.3 Parity gate

任何旧模块、旧路由、兼容层或旧入口的删除/归档都必须满足：
- 新实现覆盖全部对应 Feature Matrix 条目；
- API/DOM/事件/异步/数据语义的关键差异已逐项解释并获准；
- 合成环境的 characterization 和集成验证通过；
- 相关 golden / regression 证据通过；
- 失败路径、空态、取消、重复调用和异常情况不被静默省略。

未满足时保留旧实现作为 parity oracle 或 compatibility layer。不得用“新架构更干净”作为删功能理由。

### 4.4 测试与环境安全

- 36/36 E2E 是 Main 架构重设计文档列出的阶段硬门槛；历史 36/36 Legacy 结果不是当前 Factory 的新验收证据。
- 当前 tests/e2e-manual.js 有会修改任务/计时器状态的场景；严禁在真实生产 SQLite 上运行。
- 必须使用隔离的 synthetic DB、临时文件系统/notes fixture 和 disposable browser/server。
- 任何无法安全隔离的测试先解决测试环境依赖，不得触碰真实 DB/WAL/SHM、Vault 或生产配置。
- 每组在 Prompt 中列出唯一授权的测试命令和执行次数；默认一次。失败保留完整输出并停止，不在同一 Worker 中试错重跑。
- G5 必须执行一次有授权的全项目最终验收；不能把历史测试结果冒充当前通过。

### 4.5 不能作出的承诺

工程上不能仅凭“五组”或一套测试宣称数学意义上的绝对零风险。我们能承诺的是：**功能基线完整、每项迁移可追溯、关键行为有等价证据、旧实现未通过 parity 前不删除、最终验收没有已知回归。** 若仍有未验证项，必须明确标记，不能声称“保证完成且零丢失”。

## 5. 五组 Agent 的总体规划要求

你必须根据当前代码和现有证据真实切片，不由 Main 预先虚构每组文件清单。但最终 Plan 必须恰好有 G1–G5，并且覆盖第 2 节全部 P1–P5 交付物。

建议的规划思路（不是强制一组对应一个旧 Phase）：
- 将已完成且有可信证据的 P1/P2 工作继承，不重做；将未完成的后端 parity/迁移工作安排进有依赖的组。
- 将前端完整 Feature 模块迁移（含 G15 剩余部分）放入一个或多个有明确 owner 边界的组。
- 将 CSS/HTML/OpenClaw sandbox/theme 等剩余工作作为独立或紧密关联的组。
- 将 Legacy 退役、scripts 归档、Schema 一致性和交付报告安排在前置 parity 通过之后。
- G5 必须保留足够预算做跨层集成、功能矩阵核对、全量安全 E2E、回归分析和里程碑收口。

每组必须写明：
1. 业务/架构目标与明确交付物；
2. Non-Goals；
3. 前置依赖与已继承成果；
4. 模块边界、唯一 owner、数据写者；
5. 精确 write allowlist；
6. 冻结的公开接口、事件、异步顺序和跨模块不变量；
7. Feature Matrix 对应条目；
8. 唯一授权测试命令、次数和 PASS 判据；
9. 失败停止条件；
10. 工程风险、复杂度和完成定义。

不得将五组变成五次重复的全仓扫描。只做一次总 Recon，之后每组只读该组必要上下文。

## 6. 新架构执行协议：Plan → Recon → Contract Freeze → Agent

### 6.1 Plan / Recon

- 使用 Cursor Plan 模式对全项目重构进行一次规划。
- 先列出已可信的事实和证据位置，再只读补充当前代码所需的信息。
- 对照 P1–P5 交付范围、当前架构、CURRENT_PROJECT_STATE、WORK_LOG、G14/G15 历史和真实代码。
- 核对已有实现、dirty/untracked 资产和历史迁移；不得重复审计已接受成果。
- 不在 Plan 阶段修改代码或测试。
- 输出一份完整的 Feature Matrix / 迁移映射与五组执行计划；不写成数百行重复文档。

### 6.2 Contract Freeze

由你根据 Recon 结果冻结：
- 最终模块清单和每个模块负责/不负责的业务；
- 每个聚合/权威状态的唯一写者；
- 模块公开接口、事件、DTO、错误和依赖方向；
- Timer / Gacha / Task Lifecycle 等关键状态和异步不变量；
- Backend BP → Service → Repository 的单向边界；
- Frontend core → feature modules 的公开边界；
- Protected Paths 与每组 write scope；
- 旧实现何时可以退役的 parity 条件。

合同以代码接口和测试表达为主；Markdown 只保留目标、取舍、Non-Goals 和机器无法表达的边界，不重复维护代码已明确的事实。

### 6.3 Agent Autonomous Execution

- 每组 Cursor Agent 在冻结合同和精确写入范围内，自主组织内部切片、编码、调试和授权测试。
- 模块内部函数和私有文件布局由 Agent 决定；跨模块合同、唯一写者和架构边界由你冻结。
- 不允许静默扩大 write scope、改变产品语义、改变公开接口或弱化冻结测试。
- 合同确需变更时，先记录 Proposed → Approved → Frozen；未批准不得继续跨界修改。

## 7. 效率升级：本次必须实际执行

- 一次有效 Recon，不重复扫描整个仓库。
- 不要求每个 Worker 重复理解整个项目；只提供与本组相关的最小充分上下文。
- 同一文件未变化、同一事实已有可信证据时，不重复读取或测试。
- 不做几十分钟实时轨迹监控；Agent 派发后按人工 Handoff 等待。
- 只在结果到达后做有界核验：Token/Conversation/Generation/Workspace、实际 Diff、授权测试和关键风险。
- 不增加 Reviewer-of-Reviewer；Subcontroller 对普通切片直接验收，高风险跨模块合同变化才使用独立复核。
- 工具调用预算是效率指标，不是自动工程失败条件；但未授权写入、测试超权、Workspace 身份不符、数据红线和证据链失真仍是硬问题。
- 每组分别报告 Engineering Acceptance、Contract Compliance、Execution Efficiency。
- 达到验收条件立即停止，不追加无决策价值的保险检查。

## 8. 现有进度与不可误读事项

- G15 是前端生命周期/模块化迁移中的一个切片，不是全项目重构。
- G15.1–G15.4 的已验收成果必须继承；W22 的 Discard/Restore 仍有 PARTIAL 项，若当前源码/记录证实尚未关闭，应在五组计划中安排修复。
- W19–W22 历史工具效率偏差应保留，但不得仅因工具预算超出而重开已经 Engineering Accepted 的工作。
- G16 Free-card 是独立产品功能方向，不自动纳入本次架构重构；除非 Main-owned 详细里程碑明确要求，否则不得把新功能开发混入重构。
- RPG Progression 当前为 PARKED / NOT AUTHORIZED TO START，不纳入本次重构。
- CURRENT_PROJECT_STATE.md 顶部有较新增量；其下仍包含 2026-10-04 历史快照。不得将旧表格中的 Legacy/Factory 默认关系直接当作当前事实。
- ARCHITECTURE.md 明确标注主体是 2026-10-04 历史架构快照；当前启动入口、路由和 Factory parity 必须查当前代码。
- 旧文档中提到的 Factory 缺路由、Gacha 简化算法、Tasks parity 等是历史已知风险，需核对当前代码和后续工作记录，不能未经核验直接判定仍存在或已解决。
- 36/36 E2E 的历史 PASS 是 Legacy 运行时结果，不代表 Factory 完整 parity。
- 真实 Obsidian Vault、SQLite 数据库及 WAL/SHM、生产配置均为保护对象，不可用来跑破坏性 E2E。

## 9. 工程和数据保护红线

- 唯一产品 Workspace：D:\Axelit\.工作\trae\超级自动化学习工具，branch=main。
- 每个 Worker 第一条 Shell 必须从当前 Cursor Workspace 直接检查 Git root、branch、HEAD，并核对 Workspace metadata；身份不匹配立即停止。
- 保留全部现有 dirty/untracked 文件；不得 reset、clean、stash、checkout、switch、commit、push、覆盖或删除。
- 不使用 sibling Worktree，不以 git -C 或绝对路径跳转伪造 Workspace 身份。
- 永不写入或提交 src/notes/**。
- 不读写/复制/哈希/恢复真实 data/task_publisher.db、-wal、-shm；不修改 config/config.json 和凭据。
- 测试必须使用合成 SQLite、临时 Vault/notes fixture 和 disposable server/browser。
- Schema 重构只在合成数据库验证；不得对生产 DB 进行结构实验或迁移。
- 不新增 npm 包、Vite、Rollup、Webpack、TypeScript 编译链或其他打包构建系统；零构建约束保持。
- 不修改 Controller Loop、Kernel、Dispatcher、Runner、Watchdog、Hooks、Relay、Bridge、插件绑定、全局规则、CCGS 或 Main-owned 治理计划。
- 桌面端 src/tasks 归档必须保留可追溯性；未经单独授权不得永久删除归档。
- 不混入 G16、RPG Progression 等未授权产品功能。

## 10. 每组 Agent 的人工派发合同

继续使用 MANUAL HANDOFF FALLBACK：
1. 每组使用全新唯一 TASK_TOKEN；先核对 Token 未提交、未尝试且无状态歧义。
2. 每组一个新的顶层 Cursor Chat；不使用内部 Subagent / multitask。
3. 明确 Workspace、branch、精确 write allowlist、冻结合同、唯一授权测试命令/次数、Non-Goals 和停止条件。
4. 第一条 Shell 直接验证当前 Workspace 身份；失败立即停止，不读源码、不写入、不测试。
5. 保留现有 dirty/untracked 状态；禁止 Git 破坏性操作。
6. Handoff 必须由基础设施自动生成；Worker 不得手写或伪造 Handoff、Receipt、Collection、Review 或 Batch 状态。
7. 用户回传 Handoff 后，你先核对 Token、Conversation、Generation、Workspace，再做有界 Diff/测试 Review。
8. 更新 MANUAL_HANDOFF_LOG 和项目 WORK_LOG；不手工编辑 canonical JSON。
9. 每组完成并验收后才启动下一组。

## 11. 全项目重构完成定义

只有以下条件全部满足，才能向 Main Controller 报告全项目重构完成：

- P1–P5 所有交付范围均已完成，或有明确批准的等价实现；不存在因把 G15 当成总范围而遗漏后端、CSS、Embed、Scripts、Schema 或 Legacy 收口。
- 后端形成真实可运行的 Factory + Blueprint + Service + Repository + Schema 分层；不再存在未经授权的业务逻辑双源。
- 前端业务实际由 Feature modules 承担；core、event/state、router、shared、CSS 不是仅有空壳。
- 模块边界、唯一写者、依赖方向、事务策略和异步不变量有代码/测试约束；没有新增模块级静态循环依赖。
- 所有 Feature Matrix 条目均映射到新 owner，并有对应的 characterization / contract / integration 证据。
- 现有 API、UI、业务流程、算法、状态转换、数据语义、失败/取消/重入行为无已知回归。
- 旧实现只在对应新实现通过 parity 后才退役；必要兼容层有明确清理条件。
- 双计时器统一状态行为通过测试；Gacha golden 与关键算法行为保持。
- Schema 一致性检查覆盖当前权威定义；无生产 DB 数据丢失或未授权迁移。
- CSS / HTML / OpenClaw sandbox / theme 行为保持；嵌入安全约束落实。
- scripts 归档安全，启动/停止/验收/运维路径不丢失。
- 在合成环境完成最终 36/36 E2E 或 Main 详细 Plan 指定的等价/更强完整回归；历史 Legacy PASS 不可替代。
- 真实 DB、Vault、配置、凭据、notes 和既有 dirty/untracked 文件未被破坏。
- 五组实际修改、Handoff 身份、测试结果、合同偏差和三维评价可追溯。
- 交付报告包含迁移映射、最终模块图、遗留兼容层、测试证据、已知限制和下一条产品主线。
- 如有任何未覆盖功能、无法隔离的测试或关键证据缺口，结论必须为 PARTIAL / BLOCKED / INCONCLUSIVE，不得宣称零丢失或重构完成。

## 12. 现在立即执行

1. 读取本指令；明确废止旧 G15-only 五组计划。
2. 以 ARCHITECTURE_REDESIGN 的 P1–P5 为整个项目重构范围；对照当前源码、CURRENT_PROJECT_STATE、ARCHITECTURE、WORK_LOG 和已有 G14/G15 证据。
3. 有界定位 Main 详细 Plan；若确实缺失，明确报告该来源缺口及上述模块数量不一致，不得编造。
4. 只做一次全项目 Recon，建立简洁 Feature Matrix / Migration Map。
5. 使用 Cursor Plan 模式制定恰好五组 Agent 的完整执行计划，覆盖全部 P1–P5 交付物，并把 G15 放回它正确的子范围。
6. 先冻结模块清单、唯一写者、公开接口、跨模块不变量、Protected Paths 和五组 write scope。
7. Plan 冻结后按 G1 → G5 顺序执行；每组验收后再启动下一组。
8. 现在只向用户交付 G1 的完整 Agent Prompt 和简短操作说明；不要一次输出五份 Worker Prompt。

**最终目标：五组 Agent 完成整个项目重构，而不是五组 Agent 完成 G15。任何情况下都不能用删功能、弱化验收或隐藏未完成项来换取“按时完成”。**
