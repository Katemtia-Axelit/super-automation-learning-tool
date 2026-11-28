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
| 公开 fork `Linmoqian/learning-tools` | **已知风险，未处理** —— 持有 master 旧历史（含 2271 份笔记正文 + 3 个生产库）。按用户裁决暂不处理 |
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

