# RPG Progression 集成路线图与待办登记

- 更新日期：2026-11-15
- 候选里程碑：MS-RPG-PROGRESSION（暂定识别名，不是正式 MNN-SNN-GNN 证书）
- 状态：PRODUCT DESIGN FROZEN / ENGINEERING BACKLOG / PARKED
- 当前执行状态：未启动；无活动 Batch、Token、Worker 或代码实现

## 1. 目的与权威来源

本文件把已冻结的 RPG Progression 产品设计纳入项目长期路线与交接体系，防止它因当前 AR03 / AR04 工程主线而遗失，也防止未来 Controller 将“设计完成”误认为“功能已实现”。

权威材料：

- 产品设计事实：`docs/RPG_PROGRESSION_PRODUCT_SPEC_V1.0.md`（V1.0 冻结版）
- 原始产品讨论收敛与工程交接：`docs/deliverables/RPG_PROGRESSION_CONTROLLER_HANDOFF_20261115.md`
- 当前实现事实：`docs/CURRENT_PROJECT_STATE.md`、`docs/ARCHITECTURE.md`、当前源码与运行证据
- 项目里程碑治理：`C:\Users\wn\.cursor\controller-loop\handoff\PRODUCT_MILESTONES_20261023.md`

产品规范是 RPG Progression 的目标产品契约；它不覆盖当前代码事实，也不预先决定 SQL、API、公式或 UI 实现。

## 2. 当前决定：登记并搁置工程启动

**将 RPG Progression 作为独立的候选产品里程碑保留；当前不启动工程实施。**

理由：

1. 当前已授权产品重构主线是 G15 → AR03 → AR04，Product Controller 应连续完成 AR03 与 AR04，不被新专项分流。
2. RPG Progression 横跨 Quest / Task、Gacha、AI 任务生成、Assessment、Evidence、EXP、奖励和 UI；这些现有 Owner、依赖和数据边界仍需以重构后的真实系统为准。
3. 在 AR03 / AR04 尚未完成时提前实现，容易围绕正在变化的模块边界建立重复 Owner 或产生二次迁移。

这是项目优先级与返工成本判断，不代表 RPG 在技术上不可开发，也不意味着产品设计需要重新讨论。

**重新启动条件：**

- AR03 与 AR04 均已完成正式里程碑验收；
- 主控重新比较 MS-RPG-PROGRESSION 与其他候选产品方向（如 MS-RECORD、MS-ART、MS-AGENT）的优先级；
- 用户确认该里程碑的启动方向和边界后，才创建正式目标、Batch 与 Worker Token。

本路线图的保存与规划授权不等于提前批准源码、数据库、配置或真实数据变更。

## 3. 候选里程碑的用户价值

在现有学习工具上增加可信的能力成长系统，使用户能够区分：

- 自己完成过哪些行动；
- 哪些成果真正证明了哪些能力；
- 当前能力估值、掌握状态和证据可靠程度；
- 哪些能力需要补强或重新校准；
- 行动投入得到肯定，但不会被虚报为能力掌握。

必须复用现有 Quest、Task、Gacha 和用户交互体系。RPG Progression 不是第二套任务管理器、任务调度器或抽卡系统。

## 4. 建议的线性阶段门

以下 RP 编号只是路线图阶段标签，不是已注册 Batch / Task / Token；每阶段具体范围须在前一阶段证据充分后再冻结。

### RP0 — 现有系统只读审计与功能映射

启动条件：MS-RPG-PROGRESSION 获得用户确认，且 AR03 / AR04 已完成。

审计范围：

- 当前真实运行入口、Factory / Blueprint / Service / Repository 结构；
- Quest / Task 数据模型、状态流、依赖与历史记录；
- Gacha 候选池、抽取、接受、换卡、拒绝和已启动任务保护；
- 现有行动奖励、事件日志与幂等处理；
- AI Task Generation、提示词和现有人工审核边界；
- SQLite 结构、版本迁移、真实数据保护；
- 当前 UI 页面、用户可见状态和反馈。

交付：一份“现有能力可复用 / 需要扩展 / 尚不存在 / 与产品规范冲突”的映射矩阵，并标注证据路径和 UNKNOWN。只读 reconnaissance，不修改源码、数据库、配置，不运行产品测试。

### RP1 — 集成架构与数据契约冻结

根据 RP0 证据，确定：

- 现有模块与 Progression 的职责 Owner；
- Action、Assessment、Evidence、Capability、Progression 的事件和状态边界；
- CU / OC 与 Task、Quest、Evidence 的关联方式；
- AI 建议与确定性正式结算的权限边界；
- 版本、不可变证据、审计、幂等、纠错和迁移原则；
- 用户审核点及真实数据操作边界。

交付：一份经主控审查的集成架构和分期实现计划。概念实体不要求一对一成为数据库表；不得在审计前机械确定 DDL。

### RP2 — 能力图谱与 Evidence 基础

围绕已冻结规范建立最小必要基础：

- Domain / Cluster / 全局唯一 CU / OC 及版本；
- CU 跨 Domain / Cluster 引用；
- 用户审核正式节点创建、拆分、合并和重大修改；
- 原始 Evidence 不可变及其 OC / CU 多对多映射；
- 证据来源、参与方式、Rubric 版本与审计溯源。

交付：能够可靠表达能力图谱和可追溯证据的基础闭环。是否需要新增或复用存储结构由 RP0 / RP1 决定。

### RP3 — Assessment 与三态生命周期

实现或接通：

- Task、Assessment、Capability 三个独立状态维度；
- 普通练习与独立考核卡的不同完成语义；
- 首次有效尝试、空白/无效提交、失败归档和重测规则；
- Assessment 对 OC 的结构化核验；
- AI 分析作为证据建议，不拥有正式 EXP 结算权；
- 行动奖励与能力 EXP 分轨，并落实单实例、同目标限领、拆卡预算守恒和幂等纠错。

交付：用户完成行动、参加考核、通过或失败时，系统不会混淆任务完成与能力掌握。

### RP4 — Progression 估值、掌握与校准

实现：

- Current EXP 与 Peak EXP；
- OC 证据到 CU 估值的确定性结算；
- Core OC 与 Mastered 分离；
- Domain Current / Peak Level 及核心能力门槛；
- 证据充分性、可靠程度、新鲜度、覆盖度的独立表达；
- Slip、Forgetting、Overestimate、Revalidation 的不同归因；
- 追加式纠错、历史重算与可解释溯源。

具体公式、权重、阈值和校准参数必须结合实际证据及合成样本设计，不得伪装成 V1.0 已经冻结的数值。

### RP5 — Quest / Gacha / AI / UI 集成

在现有模块 Owner 内完成：

- Quest 消费能力缺口并组织补强、校准和后续任务；
- Task 关联目标 CU / OC，但完成不自动证明能力；
- Gacha 继续从已有可执行任务中选择，不接管复杂规划；
- AI 生成图谱、任务和考核草案，正式能力节点及 EXP 仍由用户审核与确定性代码控制；
- UI 分别呈现行动反馈、能力估值、证据、短板、等级和校准提示；
- 初始能力探测、既有成果审查与已证明内容豁免；
- 仅在确有独立价值时引入 Synthesis CU。

交付：现有用户流程中可实际使用 RPG Progression，而不是独立演示面板或平行系统。

### RP6 — 端到端验收与受控迁移

通过真实用户场景验证行动、考核、证据、EXP、校准、任务补强和 UI 的完整闭环；覆盖重复结算、无效尝试、历史证据纠错、跨 Quest / Domain 复用等关键案例。

优先使用合成数据和隔离环境。任何真实 SQLite 数据迁移、历史证据导入或 Vault / 配置写入必须单独明确授权、备份和审计，不因里程碑批准而自动获得权限。

## 5. 不可破坏的产品边界

所有后续工程必须遵守 V1.0 冻结规范，尤其：

- Action、Evidence、Progression 分离；Task 完成不等于能力掌握。
- EXP 只由可信能力证据支持；AI 不直接结算正式 EXP。
- CU 全局唯一、可跨领域引用；Evidence 映射必须有逐项依据。
- 证据表现与证据质量分离；时间流逝不直接扣 EXP。
- Core OC 门控 Mastered / Level，不封顶整个 CU 的 EXP。
- Current EXP、Peak EXP、Current Level、Peak Level 及历史纠错各自保持语义。
- Quest、Task、Gacha、Assessment、Evidence、Progression 各守职责，不重复建设任务池或抽卡系统。
- 正式能力图谱重大变更必须经过用户审核。
- 不把概念数据实体机械映射成数据库表；不在现状审计前决定迁移方案。
- 不触碰真实用户数据、Vault、生产 SQLite 和运行配置，除非获得明确的单独授权。

## 6. Controller 接手要求

未来接手的 Main / Product Controller 应：

1. 先读取 V1.0 规范与本路线图，不重新讨论已经冻结的产品哲学。
2. 在 RP0 之前不得把任何 RPG 功能标为已实现或已验收。
3. 不得因本路线图存在就中断 AR03 / AR04 当前授权工作。
4. 启动时先复核用户优先级及其他候选里程碑，再请用户确认正式启动方向。
5. 正式启动后按依赖线性派发，Worker 负责源码探索和实施，Controller 负责决策、合同、Review 与结算。
6. 每阶段交付记录真实用户行为、复用成果、剩余差距和技术债；测试数量不是里程碑完成标准。

---

**当前结论：产品设计已冻结；工程集成已进入长期待办；候选里程碑已登记但未获开工授权。下一动作不是写 RPG 代码，而是在 AR03 / AR04 完成并获得用户启动确认后执行 RP0。**
