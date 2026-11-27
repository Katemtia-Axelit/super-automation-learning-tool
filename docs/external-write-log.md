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

---

## 5. 待办与已知局限

| 项 | 状态 |
|---|---|
| `gh` token scope 收敛为 `repo` | **待办**（S5） |
| 每席位独立账号（真正的身份隔离） | **未实现** —— 当前为单账号方案，见 `docs/ROUNDTABLE_PROTOCOL.md` §2.3 |
| CI 写权限 | **无**（`.github/workflows/ci.yml` 声明 `permissions: contents: read`） |
| 分支保护规则 | **待设置**（需 `ci/gates` + `ci/redline-scan` 两个检查建立后再启用） |
