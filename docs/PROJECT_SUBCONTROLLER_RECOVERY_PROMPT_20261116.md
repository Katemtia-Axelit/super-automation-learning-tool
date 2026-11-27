# 主控 → 项目重构副控 C：AR03 G15 收口与提速指令

> 2026-11-18 更新：本文件关于自动物理派发、等待 Relay 唤醒和自动回传的传输假设，已由 `PROJECT_SUBCONTROLLER_MANUAL_HANDOFF_DIRECTIVE_20261118.md` 取代。继续使用本文件中的产品目标、G15 业务边界、Workspace 保护、测试授权和工程验收规则；发生冲突时，以 2026-11-18 人工交接指令为准。

DIRECTIVE_ID: AR03_PROJECT_SUBCONTROLLER_RECOVERY_20261116
发出方：Main Controller
接收方：项目重构副控 C
日期：2026-11-16

你现在接任 AR03 学习工具前端模块化重构的项目 Domain Subcontroller。主控已授权你在本项目范围内自主规划、拆解、派发、验收和集成后续 G15 工作；不需要每完成一个 Worker 就等待主控批准。用户仍是最终决策者；遇到跨域冲突、权限边界、不可逆操作或实质产品语义变更时再升级。

## 1. 必须先读取的主控材料

1. D:\Axelit\.工作\trae\超级自动化学习工具\docs\ENGINEERING_PROGRESS_AUDIT_20261116.md
2. D:\Axelit\.工作\trae\超级自动化学习工具\docs\PROJECT_HANDOFF_REVIEW_RULES_20261116.md

这两份文件是本次 AR03/G15 项目范围内的主控审计与执行规则。遵守其规则，但不得据此修改全局 Controller Loop、Dispatcher、Watcher、Relay、Bridge、Hooks、Loop 绑定、CCGS 角色合同或 Main-owned 治理计划。

## 2. 当前已确认状态

- 唯一产品主线：D:\Axelit\.工作\trae\超级自动化学习工具，branch=main。
- G14/G15 相关成果曾分布于 main 与 AR03 sibling；现在开发目标固定为 main，不再在 sibling 上继续开发。
- G15.1 普通任务生命周期首切片已经有实现，指定 characterization 有 PASS 证据；W01/W02 的历史执行偏差保留，W03 证据纠错 ACCEPTED。
- W06 mainline 源码检查和一次授权 characterization PASS，退出码 0；但 W06 Review=NEEDS_FOLLOWUP，原因包括 23 条 postToolUse 记录对 16 次预算，以及 Handoff workspace_root 标记为 AR03 sibling、合同要求 main。原始工具输入显示源码与测试命令指向 main，未见源文件写入或 sibling 源码读取。不得重跑 W06 测试，不得改写 W06 Review。
- 完整 Token LT_AR03_G15_MAINLINE_EVIDENCE_FOLLOWUP_W07_20261116 的 manifest/prompt 已存在，canonical Closeout Batch 已有对应行，但它尚未正式派发：无 Task State/Receipt，尚未 preflight/run。它是唯一允许执行的一次 mainline 只读证据收口。
- 另有 G15.2 Feedback/Care 的旧准备稿 LT_AR03_G15_FEEDBACK_CARE_OWNER_W07_20261116；它仍以 W06 Review=ACCEPTED 为硬门槛，当前不满足。不要复用这个旧 Token，不要覆盖旧 prompt；通过 W07 mainline follow-up 后，用新 Token 创建 G15.2 合同。
- 旧 Feedback/Care W05 目标是 AR03 sibling，禁止复用。
- W03 已证明 Sleep 符号在 G15.1 W01 开始前就已不存在。不要把它重新归因给 W01，也不要擅自恢复 Sleep/G10 功能。
- main 存在用户保留的 dirty/untracked 文件；绝对禁止 reset、clean、stash、checkout、switch、commit、push、覆盖或删除。

## 3. 先完成一次 W07 mainline evidence follow-up

使用完整 Token：LT_AR03_G15_MAINLINE_EVIDENCE_FOLLOWUP_W07_20261116

严格走官方 controller-dispatch-task 流程：plan → prepare → preflight → run。不要直接向 Cursor 粘贴旧 prompt，不要绕过官方 preflight，不要手工写 Task/State/Receipt/Collection/Review/Batch JSON。

第一条 Shell 必须直接从当前 Cursor Workspace 执行：
- git rev-parse --show-toplevel
- git branch --show-current
- git rev-parse HEAD

同时核对 Cursor Handoff workspace_root。Cursor Workspace metadata、Git root、branch/HEAD 必须符合该任务合同。不得用 git -C、绝对路径跳转或 cd 到 main 来伪造当前 Workspace 身份。

若身份不匹配：
- 立即停止；
- 不读取项目源码、不写文件、不运行测试；
- 不切换 Workspace、不使用其他传输路线、不重试；
- 报告 WORKSPACE_IDENTITY_MISMATCH，并交主控处理。

若身份通过：
- 按现有 W07 prompt 执行，最多 8 次工具调用、0 次测试、0 次写入；
- 复用 W06 已有 Collection、原始 Trace 和测试证据，严禁重跑测试；
- 不读取 sibling 源码，不清理 dirty/untracked 文件；
- 完成后按新规则做一次 Review，明确 Engineering Acceptance / Contract Compliance / Execution Efficiency 三维结论。
- 如果只是软工具预算超出，但身份、源码与既有测试证据可信，不得仅因预算超出否决工程结果；记录偏差即可。
- 如果身份或关键证据仍不可信，才 NEEDS_FOLLOWUP，并明确最小补证动作。

W07 已提交后，只做一次有界状态确认，确认 Receipt 与既有 reconciler/watchdog/relay 健康，然后把观察权交给既有后台机制。不要紧密轮询，不要重复读取同一批文件，不要启动第二套 watcher。当前 visible-tab-relay 的目标 ChatGPT 会话就是本副控；等待该会话收到正式 actionable wake event 后再继续。

## 4. W07 收口后推进 G15.2 Feedback/Care

只有 W07 提供可接受的 mainline 证据后，才开始 G15.2。W06 历史 Review 保持 NEEDS_FOLLOWUP，不得伪造为 ACCEPTED；G15.2 的新合同应以 W07 的正式证据收口结果为前置。

创建全新 Token，建议：LT_AR03_G15_FEEDBACK_CARE_OWNER_W08_20261116。使用官方 plan/prepare/preflight/run，登记到现有 canonical G15 Closeout Batch；不得手工编辑 Ledger。

以 main 当前源码为准，沿用旧 Feedback/Care 准备稿中的业务边界，但重新核对所有依赖和当前文件状态。唯一允许的产品写入范围：
- static/modules/tasks/lifecycle.js
- static/app.js
- static/app.entry.js
- tests/characterize/test_task_feedback_care_owner.py（新文件）

核心目标：
- 将 _feedbackContext、_pendingFeedbackSubmit、feedbackMood（初始 3）、_careContext 和 Feedback/Care 业务顺序迁入唯一 Task Lifecycle owner。
- app.js 只保留同步、null-safe 的 inline-handler facade 与窄 DOM adapter。
- app.entry.js 保留 G13 TaskEditor 与 G14 Gacha 唯一 owner；Gacha 初始化先于 Lifecycle owner；Gacha 依赖使用每次调用时读取 window.drawGachaWithCategory 的晚绑定 wrapper。
- 保留 API 顺序、Promise 可观察时序、成功/失败/取消/重入语义、modal 与 toast 行为。
- lifecycle owner 不直接访问 window/document/DOM。
- 不修改 Gacha/Timer owner、src/index.html、G13 editor、Sleep、Free-card、Skip/Refuse、Discard/Restore、backend/API/config/data/notes。

测试策略：
- 新增 synthetic Node VM/tempfile characterization，覆盖成功、失败、取消、pending 重入、mood 私有状态、Care 分支、动态 Gacha facade。
- 指定测试命令只执行一次；先确认解释器路径存在。若失败，保留完整输出并停止，不在同一 Worker 中重跑或换解释器。
- 不运行其他测试、E2E、Playwright、lint、typecheck、build、smoke 或浏览器。
- max_tool_calls 作为效率目标而非自动验收否决项；建议 24–32 次，0 debug cycle。实际超出时记录计数口径和原因，不能单独据此否决有效工程成果。
- 写入只允许上述四个文件；局部 patch，禁止整文件覆盖、格式化和 Git mutation。

## 5. 继续 G15.3 / G15.4，保持线性

G15.2 工程结果被接受后，你可自主继续，不必等待主控逐项批准：

- G15.3 Skip/Refuse：单独 Token/Worker；保留 drawn-card 与 task-list 两种入口的 toast、结果区、动画、刷新差异；必须保留 promptTaskFeedback await 后才 POST。
- G15.4 Discard/Restore：单独 Token/Worker；只迁移 moveToDiscard/restoreFromDiscard 的业务 API 顺序和确认/失败语义；discard list/modal rendering 留在 presentation。
- 最终 Factory E2E：先审计 main 当前缺少的 fixture/config/sandbox server 依赖，只做最小依赖移植；只有 main 可独立运行时才执行一次定向 E2E。不得整目录复制。
- Free-card accept/end 继续独立为 G16，不纳入 G15。

G15 是线性依赖链，不并行修改同一批后端/前端 owner。每个切片完成后，基于真实证据立即进入下一切片；不要额外制造 Reviewer-of-Reviewer。

## 6. 新交接规则必须落实

- 每个 Worker 的 Handoff 由基础设施生成，不手工伪造。
- Handoff 必须报告实际修改文件、测试命令/次数/退出码、Trace 计数口径、偏差、风险和下一步；不要求逐工具写长篇说明。
- Review 分开判断 Engineering Acceptance、Contract Compliance、Execution Efficiency。工具预算超出不自动等于工程失败。
- Reviewer 按风险使用；普通窄切片由你根据源码、diff、已授权测试完成验收即可。
- 只有工程缺陷、关键证据缺失或硬边界违规才派 Follow-up；不得只为重新统计工具调用派 Auditor。
- Controller 自己提供的 SHA、路径、基线或归因若有错误，明确记录 Controller-side correction；不把错误归给 Worker，不改写历史 Review。
- 历史 Batch/Review/Collection/Receipt/Journal 不手工编辑；用官方 Supervisor 追加 action/resolve。
- 每次派发前核验源文件哈希与路径；无法确认时不要把旧哈希写进合同。
- 只使用官方 Dispatcher / Batch / Collector / Review / Supervisor；不修改 Loop 基础设施或全局规则。

## 7. 交付与停止条件

本轮目标是把 G15 从“第一切片有成果但验收闸门阻塞”推进到至少 G15.2 完成；在资源和证据允许时，继续 G15.3、G15.4 与最终定向验收。

每个切片完成后，更新项目工作日志或新增一份简洁的 AR03 进度记录。最终向主控报告：
1. W07 的身份核验与正式结论；
2. G15.2/3/4 每个完整 Token、Review、Collection SHA 和工程结果；
3. 每个测试的真实执行次数、退出码；
4. 所有硬边界偏差与软预算偏差，分别说明；
5. main dirty/untracked 是否保持未触碰；
6. G15 Closeout Batch 是否仍 OPEN、未完成项与唯一下一动作。

遇到身份 mismatch、未授权副作用、关键证据不可绑定、产品语义不明确或安全边界问题时立即停止并向主控报告；除此以外，在已授权 G15 范围内自主推进，不要把普通过程偏差升级为新的管理项目。

