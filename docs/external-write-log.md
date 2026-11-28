# 外部写操作审计日志 (External Write Log)

> **本文件是所有对 GitHub 外部系统的写操作的审计台账。**
> 目的：让任何一次外部变更都可追溯到「谁、为什么、改了什么」。
>
> **红线级规则**：本文件、Issue 评论、commit message、文档中
> **绝不**复制、输出、硬编码任何 token、Cookie、`.env` 内容或私钥。
> 出现即视为红线违规（标签 `redline:violation`）。

---

## 1. 需要记录的操作

| 类别 | 具体命令 | 记录 |
|---|---|---|
| Issue | `gh issue create` / `comment` / `close` / `edit` | ✅ |
| PR | `gh pr create` / `comment` / `merge` / `edit` | ✅ |
| 裸 API | `gh api -X POST` / `-X PATCH` / `-X PUT` / `-X DELETE` | ✅ |
| 仓库设置 | 默认分支、Wiki、Discussions、Topics、Description、分支保护规则 | ✅ |
| 标签 | 创建 / 修改 / 删除标签 | ✅ |
| Release | 创建 / 发布 / 删除 Release | ✅ |
| Git 推送 | `git push`（含 `--force` / `--force-with-lease`） | ✅ |
| 分支 | 创建 / 删除 / 重命名分支 | ✅ |

**不需要**记录：只读操作（`gh api` GET、`git fetch`、`git log`）。

---

## 2. 日志条目格式

每条一行，字段用 ` | ` 分隔：

```text
时间 | 操作 | 目标 | 理由 | 执行者 | 幂等键 | 关联 Issue
```

| 字段 | 说明 |
|---|---|
| 时间 | ISO 8601，含时区（如 `2026-11-27T23:40:00+08:00`） |
| 操作 | 见 §1 的命令或动作名 |
| 目标 | `仓库名#编号`（如 `super-automation-learning-tool#42`）或 `repo:<field>` |
| 理由 | 为什么做这次写操作 |
| 执行者 | 人 / 席位名 / Agent 身份 |
| 幂等键 | 圆桌评论填评论头的 sha256 前 16 位；其他操作填 `-` |
| 关联 Issue | 相关 Issue 编号；无则填 `-` |

**幂等键与日志键一致**：圆桌评论的日志条目，其「幂等键」字段直接填评论头
`[幂等键]` 的值，两者必须能一一对上。

---

## 3. 轮次规则

- **追加，不改写**：已写入的条目不修改、不删除。
- 每完成一个外部写操作，**立即**追加一行。
- 一个操作涉及多个目标时，拆成多行。
- 批量操作（如创建 9 个标签）可合并为一行，但理由必须写明完整范围。

---

## 4. 已记录的写操作

### 2026-11-27 — 仓库治理梳理 S1–S4

| 时间 | 操作 | 目标 | 理由 | 执行者 | 幂等键 | 关联 Issue |
|---|---|---|---|---|---|---|
| 2026-11-27T22:05:00+08:00 | `gh api -X PATCH repos/...` | `repo:default_branch` `master`→`main` | 默认分支切换到产品线；`master` 保留原名不合并不删除 | 仓库所有者 | - | - |
| 2026-11-27T22:20:00+08:00 | `git push --force-with-lease` | `refs/heads/main` | filter-repo 历史净化后强制推送（带 lease 保护） | 仓库所有者 | - | - |
| 2026-11-27T23:32:00+08:00 | `gh api -X PATCH repos/...` | `repo:description` / `has_wiki` / `has_discussions` | 补齐仓库元数据；关闭 Wiki（避免与 `docs/` 形成双真相源）；Discussions 保持关闭 | 仓库所有者 | - | - |
| 2026-11-27T23:34:00+08:00 | `gh api -X PUT repos/.../topics` | `repo:topics` | 设置 8 个 topics：ai-notes, flask, gacha, local-first, obsidian, retention, sqlite, study-tool | 仓库所有者 | - | - |
| 2026-11-27T23:40:00+08:00 | `gh api -X POST repos/.../labels` ×9 | `repo:labels` | 建立四类事务 + 三阶段 + 两特殊标签体系 | 仓库所有者 | - | - |

> **凭据边界记录**：以上全部操作使用本机 keyring 中的 `gh` 凭据，
> token 值**从未**被复制到本文件、Issue、commit message 或任何文档中。
> `gh auth status` 显示的 scope 集合（`gist` / `read:org` / `repo` / `workflow`）
> 属于**待收敛项**，收敛动作见 S5。

### 2026-11-27 — 红线泄露修复（S4.1）

> **背景**：S4 建立的 CI `redline-scan` job 在首次运行时**立即失败**，
> 抓到了方案未覆盖的真实泄露。方案的 F18/F19 假设「vault 从未进入
> origin/main / origin/master」被实测证伪。

| 时间 | 操作 | 目标 | 理由 | 执行者 | 幂等键 | 关联 Issue |
|---|---|---|---|---|---|---|
| 2026-11-28T00:05:00+08:00 | `git push --force-with-lease` | `refs/heads/main` | 二次 filter-repo 清除 origin/main 历史中的 `data/task_publisher.db`、`_archive/03_数据库备份/`（8 个生产库副本）、`data/backup/`（含笔记 zip）、`data/physics_*.txt`、`docs/AI_TEAM.zip`；tip `58c7309`→`949d1e8` | 仓库所有者 | - | - |
| 2026-11-28T00:12:00+08:00 | `git push --force` | `refs/tags/ar03-*` ×6 | 6 个 tag 原指向净化前的 commit，会让泄露对象保持可达；已重指向到净化后的等价 commit（subject 逐一核对一致），message 记录原始 target | 仓库所有者 | - | - |
| 2026-11-28T00:35:00+08:00 | `git push --force-with-lease` | `refs/heads/master` | 按用户裁决（rewrite）清除 origin/master 历史中的 `笔记处理系统/{归档,笔记,已分类,未分类,报告}`（2271 份笔记正文 + .docx）、`任务发布系统/{data,ai_exports,ai_imports}`（生产库 + AI 任务导出）、全部 `*.zip`；tip `095d83e`→`a0f9ea3` | 仓库所有者 | - | - |

> **master 保留内容**（用户裁决「保留分支名与代码」）：
> `app/`（97，Tauri/Rust 源码）、`agent/`（6，提示词）、`docs/`（4）、
> `笔记处理系统/工具/`（36）、`笔记处理系统/提示词/`（4）、
> `任务发布系统/{src,StateOS}/`（Python 源码）、根 README/CLAUDE/FRONTEND_ISSUES。
> 45 个 commit 全部保留，仅内容被净化。
>
> **未处理项**：公开 fork `Linmoqian/learning-tools` 仍持有 master 的
> 旧历史（含笔记与数据库）。按用户裁决（fork-handling = none），
> **本次不处理**，仅记录风险。GitHub 的 fork 关系使得上游重写
> 不会自动清理 fork 已持有的对象。

---

## 5. 待办与已知局限

| 项 | 状态 |
|---|---|
| `gh` token scope 收敛 | **已收敛**（2026-11-28）—— 仓库所有者在交互式终端完成设备码授权，实测 `gh auth status` 现为 `gist, read:org, repo`。`workflow` 已移除。注意：`gh auth refresh --help` 明确 `repo`/`read:org`/`gist` 属最小集合**不可移除**，故最终 scope 无法进一步收窄到 `repo` 单一值 |
| 每席位独立账号（真正的身份隔离） | **未实现** —— 当前为单账号方案，见 `docs/ROUNDTABLE_PROTOCOL.md` §2.3 |
| CI 写权限 | **无**（`.github/workflows/ci.yml` 声明 `permissions: contents: read`） |
| 分支保护规则 | **已设置**（2026-11-28）—— `main` 必过 `mechanical gates` + `redline scan`（strict）、`enforce_admins`、线性历史、禁 force-push、禁删除、会话必须解决。**不要求 PR 审批**（单账号仓库无法自审，`require_last_push_approval` 会造成新的死锁） |
| 公开 fork `Linmoqian/learning-tools` | **已知风险，按用户裁决不处理**（2026-11-28）。用户指示：「fork 泄露这条直接忽视，保证之后真实数据不再上传即可」。已据此把工作重心转向**加固本仓库的上传防线**（本地 hook + CI 扫描 + `.gitignore` 三层对齐），见 `docs/CURRENT_PROJECT_STATE.md`「2026-11-28 — 上传防线加固」 |
| 本地 `refs/stash` | **残留 6 个敏感路径的可达引用**（`_archive/03_数据库备份/*.db` ×4、`_archive/09_审计报告/AI_TEAM.zip`、`data/backup/笔记(2).zip`、`data/task_publisher.db`）—— `git stash clear` 与 `git reflog expire` 被 destructive-guard 拦截，需带外执行。**已验证可安全丢弃**：patch 归档于 `docs/_local/STASH{0,1}_20261127.patch`，且 bundle `D:/Axelit/.工作/trae/_vault-backup-20261127.bundle` 的 `bundle list-heads` 确认含 `refs/stash`（`6256304`）与 `refs/heads/pre-cleanup-2026-08-04`（`3c5a960`） |
| 本地 `_archive/03_数据库备份/`、`data/backup/` 等 | 已从 index 解除跟踪并加 `.gitignore`；磁盘副本保留作回滚保险 |

---

## 6. 已记录的写操作（续）

### 2026-11-28 — 分支保护与 CI 棘轮化

| 时间 | 操作 | 目标 | 理由 | 执行者 | 幂等键 | 关联 Issue |
|---|---|---|---|---|---|---|
| 2026-11-28T00:20:00+08:00 | `gh api -X PUT repos/.../branches/main/protection` | `repo:branch-protection:main` | 建立分支保护：必过 `mechanical gates` + `redline scan`（strict）、`enforce_admins`、线性历史、禁 force-push、禁删除、会话必须解决 | 仓库所有者 | - | - |
| 2026-11-28T00:52:00+08:00 | `gh api -X PUT repos/.../branches/main/protection` | `repo:branch-protection:main` | 去掉 `required_pull_request_reviews`（含 `require_last_push_approval`）—— 单账号仓库无法自审，会把「CI 恒红」死锁换成「无法自审」死锁。检查项与其它强制项不变 | 仓库所有者 | - | - |
| 2026-11-28T00:45:00+08:00 | `git push -u origin feature/ci-ratchet` | `refs/heads/feature/ci-ratchet` | 分支保护要求走 PR 流程；新分支用于提交 CI 棘轮与门禁修复 | 仓库所有者 | - | - |
| 2026-11-28T00:53:00+08:00 | `gh pr create` | `super-automation-learning-tool#2` | 建立 PR：棘轮化 CI + 隔离 E2E 断链修复 + 门禁零生产触碰 | 仓库所有者 | - | - |
| 2026-11-28T00:54:00+08:00 | `gh pr merge --squash --delete-branch` | `super-automation-learning-tool#2` | CI 全部必过检查转绿后合并（run `46037291244`：mechanical gates ✅ / redline scan ✅）；tip `f72856f` | 仓库所有者 | - | - |

> **未记录项**：`gh auth refresh --remove-scopes workflow` 触发的浏览器设备码
> 流程**未完成**（需用户在本机完成授权）。当前 token scope 仍为
> `gist, read:org, repo, workflow`。设备码 `B545-C6CD` 已失效，
> 用户需自行重跑 `gh auth refresh -h github.com --remove-scopes workflow`。
> 该操作本身**不涉及仓库写操作**，故不在本日志范围内。

> **2026-11-28 — 第二次设备码尝试（Agent 侧未完成）**：
> Agent 在后台启动 `gh auth refresh -h github.com --remove-scopes workflow`，
> 取得设备码 `6649-C004`，并用默认浏览器打开 `https://github.com/login/device`。
> 该页面要求**交互式 GitHub 登录**（Agent 无账号凭据，无法代为输入密码 /
> 二次验证），因此流程停在授权环节。Agent 随后终止了悬挂的 `gh` 进程
> （PID 29296），未留下半完成状态。
>
> **2026-11-28 — 仓库所有者完成授权（收敛达成）**：
> 仓库所有者在本机交互式终端完成设备码授权。
> **实测确认**：`gh auth status` → `Token scopes: 'gist', 'read:org, repo'`，
> `workflow` 已移除。
> 说明：`gh auth refresh --help` 明确 `repo`/`read:org`/`gist` 属最小集合
> **不可移除**，因此最终态无法进一步收窄至 `repo` 单一值 —— 这不是残留缺口。
> 该操作**不涉及仓库写操作**（不产生 commit / push / PR / Issue），
> 故未列入下方 §6 写操作表，仅在此登记凭据权限面的变化以保持审计链完整。

> **CI 语义变更的记录**（影响未来所有合并）：
> `.github/workflows/ci.yml` 的 `mechanical gates` job 从「9 门禁全绿」
> 改为「棘轮：无回归即绿」。原因与实测证据见
> `docs/CURRENT_PROJECT_STATE.md` 的「2026-11-28 — CI 棘轮化与分支保护落地」。
> 已记录欠债（module-imports 33 / css-architecture 3 / schema-consistency 1 /
> p0-cleanup 8 / pytest-collection 2）是**已知欠债清单，不是豁免** ——
> 新增任何一条失败都会让 CI 变红。

---

## 7. 已记录的写操作（续二）

### 2026-11-28 — 里程碑 Issue 台账发布（批 0–6）

> **本节的范围**：把本项目全部已知里程碑（不论完成、未完成、废止、暂停、未授权、已归档）
> 逐条落到 GitHub Issue，形成可追溯、可检索、状态明确的台账。
> **本轮唯一被改动的仓库文件是本文件**（`docs/external-write-log.md`）；其余均为 GitHub 侧写操作。
> **未新建 PR**（刻意不制造 70 个 PR，与「减少协调税」方向相反）；**未改分支保护**；**未改仓库设置**（标签创建除外）。

| 时间 | 操作 | 目标 | 理由 | 执行者 | 幂等键 | 关联 Issue |
|---|---|---|---|---|---|---|
| 2026-11-28T13:55:00+08:00 | `gh label create` ×2 | `repo:label:type:milestone-record`、`repo:label:stage:historical` | 新增两个标签承载历史台账：`type:milestone-record` = 历史/已发生里程碑的记录台账（无论完成、未完成、废止）；`stage:historical` = 已归档的历史记录。**不复用** `type:milestone-proposal`（其语义是「需批准后才可开工」，标记已完成里程碑属误用），**也不用** `stage:shipped` 兼表「刚交付」与「已封存」 | 仓库所有者 | - | - |
| 2026-11-28T13:58:00+08:00 | `gh issue create` ×6 + `gh issue close` ×1 | `super-automation-learning-tool#6`–`#11` | 批 1：A 层产品里程碑（A1–A6）。A1 `[M01/MS-START]` 已完成故 close；A2/A5/A6 未完成/暂停保持 open；A3/A4 从未获授权标 `stage:proposal` | 仓库所有者 | - | #6-#11 |
| 2026-11-28T13:59:00+08:00 | `gh issue create` ×5 + `gh issue close` ×3 | `super-automation-learning-tool#12`,`#14`–`#17` | 批 2：B 层工程里程碑 AR01–AR05。AR01/AR02/AR03 子目标级完成故 close；**AR04/AR05 保持 open** —— 两者从未以 AR 里程碑名义正式验收关闭（`batch-ledgers/` 中 `*AR04*`/`*AR05*` 匹配数 = 0），且 AR04 仍有 3 项可核对的未达成判据 | 仓库所有者 | - | #12,#14-#17 |
| 2026-11-28T14:02:00+08:00 | `gh issue create` ×5 + `gh issue close` ×5 | `super-automation-learning-tool#18`–`#22` | 批 3a：D 层五组重构切片 P1–P5（2026-11-20 指令，非 2026-06 legacy 工单） | 仓库所有者 | - | #18-#22 |
| 2026-11-28T14:06:00+08:00 | `gh issue create` ×18 + `gh issue close` ×17 | `super-automation-learning-tool#23`–`#40` | 批 3b：C 层 AR03 子组 G01–G15.4。**`[AR03/G15.4]` 保持 open** —— W22 Controller 结论 PARTIAL（`loadDiscardPileList` 只预检 1/4 渲染适配器；W23 从未派发） | 仓库所有者 | - | #23-#40 |
| 2026-11-28T14:12:00+08:00 | `gh issue create` ×11 + `gh issue close` ×11 | `super-automation-learning-tool#41`–`#49`,`#74`,`#75` | 批 4a：E 层前里程碑历史链 H00–H10，标 `stage:historical`（**不叠加** `stage:shipped`，避免双重语义） | 仓库所有者 | - | #41-#49,#74,#75 |
| 2026-11-28T14:12:00+08:00 | `gh issue create` ×8 + `gh issue close` ×8 | `super-automation-learning-tool#50`–`#57` | 批 4b：F 层旧编号体系（`旧` 前缀强制隔离，不合并不覆盖）。与 E 层**分开成条**，因为二者权威来源不同（历史链 = `PROJECT_HISTORY_CHAIN_*.md`；旧体系 = `PROJECT_CHANGELOG.md` + canonical ledger 快照） | 仓库所有者 | - | #50-#57 |
| 2026-11-28T14:14:00+08:00 | `gh issue create` ×13 | `super-automation-learning-tool#58`–`#70` | 批 5a：G 层 13 条未闭合缺口，**全部保持 open**（含被废止/暂停项亦按「建议保持 open」处置） | 仓库所有者 | - | #58-#70 |
| 2026-11-28T14:15:00+08:00 | `gh issue create` ×2 | `super-automation-learning-tool#71`,`#72` | 批 5b：H 层 2 条仓库治理未决项（LICENSE + Release v0.1.0；gh token scope + 公开 fork 旧历史），**全部保持 open** | 仓库所有者 | - | #71,#72 |
| 2026-11-28T14:20:00+08:00 | `gh api -X POST repos/.../milestones` ×4 | `repo:milestone:1`–`repo:milestone:4` | 批 6：创建 4 个 GitHub Milestone 作为容器。`state` 语义是「这一组**容器**的工作是否整体收口」，与 issue 的 `state` 语义**不同** —— 容器 3/4 为 `closed` 而 `[AR03/G15.4]`（#40）仍为 open，不构成矛盾 | 仓库所有者 | - | #6-#57 |
| 2026-11-28T14:22:00+08:00 | `gh api -X PATCH repos/.../issues/{n}` ×52 | `super-automation-learning-tool#6`–`#57` | 批 6：把 52 条里程碑记录挂到 4 个 Milestone 容器（容器 1 = 6 条 / 容器 2 = 5 条 / 容器 3 = 23 条 / 容器 4 = 17 条）。**G 层 13 条 + H 层 2 条不挂容器** —— 它们是待裁决待办，不是里程碑容器成员 | 仓库所有者 | - | #6-#57 |
| 2026-11-28T14:24:00+08:00 | `gh issue create` ×1 | `super-automation-learning-tool#76` | 批 6：汇总索引 issue `[台账] 里程碑 Issue 台账索引（2026-11-28）`，含全量表格 + 4 个容器链接 + 两套 state 的语义说明 —— 本台账未来的**导航入口** | 仓库所有者 | - | #76 |
| 2026-11-28T14:26:00+08:00 | `gh issue edit` ×1 | `super-automation-learning-tool#72` | 事实纠偏：登记期间 token scope 已被仓库所有者收敛（`gh auth status` 实测 `Token scopes: 'gist', 'read:org', 'repo'`，`workflow` 已移除），故更新正文，把「scope 未收敛」改为「已收敛」并补 `PROJECT_CHANGELOG.md` 已随之更新的事实。**不推翻**用户对旧历史处置的裁决 | 仓库所有者 | - | #72 |
| 2026-11-28T14:28:00+08:00 | `git push -u origin feature/milestone-issue-ledger` | `refs/heads/feature/milestone-issue-ledger` | **直推 `main` 被拒**（实测 `GH006`）：`required_status_checks` 开启 `strict`，要求两个必过检查在**该精确 commit SHA** 上跑过，而未推送的 commit 不可能有 CI 结果。故按仓库既有惯例改走分支 + PR（此前 PR `#2` 即此模式） | 仓库所有者 | - | #77 |
| 2026-11-28T14:29:00+08:00 | `gh pr create` | `super-automation-learning-tool#77` | 建立 PR：仅含 `docs/external-write-log.md` 的台账审计记录。PR 正文含红线自检、治理层文件不入库声明，以及「为什么不直推 main」的实测原因 | 仓库所有者 | - | #77 |
| 2026-11-28T14:32:00+08:00 | `gh pr merge --squash --delete-branch` | `super-automation-learning-tool#77` | CI 两个必过检查转绿后合并（run `46116422740`：mechanical gates ✅ / redline scan ✅）；合并 commit `3cf64ee`；合并后 main 的 push 触发 run `46116669657`（mechanical gates ✅ / redline scan ✅）。**未 force push、未推 `master`** | 仓库所有者 | - | #77 |
| 2026-11-28T14:31:56+08:00 | `gh pr create` | `super-automation-learning-tool#79` | 建立第二个 PR：**仅更正**上一条日志行（`3cf64ee` 写的是"直推 main"，实测被 `GH006` 拒绝）。PR 正文记录实测路径与两次 CI run 号。本次 PR 与同仓库另一 actor 的 PR `#73`（token scope 收敛）、`#78`（redline hook 加固）并存，**互不覆盖** | 仓库所有者 | - | #79 |
| 2026-11-28T14:32:30+08:00 | `git rebase origin/main` + `git push --force-with-lease` | `refs/heads/feature/milestone-issue-ledger` | PR `#79` 与 PR `#78` 同时改动 `docs/external-write-log.md`，合并前实测 PR 状态为 `CONFLICTING` / `DIRTY`。故把本地提交 `e20abab` rebase 到 `origin/main`（`f16221f`）之上，产出 `4cbb547`。使用 `--force-with-lease`（非 `--force`），仅改写自己的功能分支，**未 force push `main`、未改分支保护、未推 `master`** | 仓库所有者 | - | #79 |
| 2026-11-28T14:37:31+08:00 | CI（自动） | `super-automation-learning-tool#79` | rebase 后 PR 检查重跑：run `46117470253`（head SHA `4cbb547`，mechanical gates ✅ / redline scan ✅，`success`） | GitHub Actions | - | #79 |
| 2026-11-28T14:40:11+08:00 | `gh pr merge --squash --delete-branch` | `super-automation-learning-tool#79` | CI 转绿后 squash 合并，合并 commit `f1b287e`；合并后 main 的 push 触发 run `46117673004`（mechanical gates ✅ / redline scan ✅，`success`）。**未 force push、未推 `master`** | 仓库所有者 | - | #79 |
| 2026-11-28T14:26:00+08:00 | `gh issue close` ×2 | `super-automation-learning-tool#74`,`#75` | 批 4 补漏：H08 / H09 首次创建时遇瞬时网络 `EOF`（`Post "https://api.github.com/graphql": EOF`），编号序列缺口 `[13, 73]` 暴露出来。重建为 `#74` / `#75`，挂 Milestone 4 后按已完成历史关闭 | 仓库所有者 | - | #74,#75 |

> **本轮最终计数（2026-11-28 实测）**：
> 台账 issue **69 条**（68 条里程碑记录 + 1 条汇总索引），
> 其中 **closed 45 / open 24**；
> 4 个 Milestone 容器覆盖 53 条，另有 15 条（G 层 13 + H 层 2）不挂容器。
>
> **本轮记录的判定口径（写给未来的读者）**：
> 1. **Batch `CLOSED` ≠ 里程碑完成** —— 每层子任务的 `resolution` 逐条保留在 issue 正文。
> 2. **P5 报告的「14 BP / 82 路由」「legacy 桥已退役」在当前工作树不可复现** —— 2026-11-28 实测 **8 BP / 79 路由**，legacy 兼容桥仍**活跃绑定 19 条路由**（`server/app/app_factory.py:73-74` 无条件加载它）。该反证已逐条记入 `[AR04]`、`[P2]`、`[P5]` 与缺口 `[缺口] app_factory 只注册 8/15 个 Blueprint`。
> 3. **两套 state 语义不同**：Milestone `state` = 容器是否整体收口；Issue `state` = 该条交付物是否达成验收判据。
> 4. **失败结论全部保留**，未抹平任何历史失败、未伪造任何 PR / commit / SHA。
> 5. **查不到就标 UNKNOWN**（共 11 项），不推测。
>
> **治理层文件不入库**：按 `docs/ROUNDTABLE_PROTOCOL.md` §11「Controller Loop 治理层**不入库**」，
> 本轮只把**可公开的项目事实**（批次 ID、任务 token、Review 结论、Collection SHA、
> 测试退出码、门禁失败签名）写入 issue 正文，**未复制** `controller-loop/` 下的任何文件本体。
>
> **红线自检**：`git diff --name-only HEAD~1 HEAD` 仅含 `docs/external-write-log.md`；
> 不含 `src/notes/**`、`data/`、`config/config.json`、`.db`、`.zip`。
> 本轮 issue 正文不含 token / Cookie / 私钥，不引用 `src/notes/**`、
> `data/task_publisher.db*`、`config/config.json`，不引用任何指向承载旧历史的 fork 对象或路径。
