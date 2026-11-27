# 安全策略 (Security Policy)

## 适用范围

本仓库是一个**本地优先**的学习工具：Flask + SQLite 服务运行在用户自己的机器上，
笔记知识库与任务数据库都留在本机。

但仓库本身是 **PUBLIC**，因此以下两类问题都需要认真对待：

1. **仓库内泄露了用户私有数据** —— 笔记正文、笔记路径清单、
   `data/task_publisher.db` 家族、`config/config.json`。
2. **仓库内泄露了凭据** —— GitHub token、API key、Cookie、私钥。

---

## 请勿用公开 Issue 报告安全问题

**公开 Issue、公开 PR、公开 Discussion 都不适合报告漏洞。**
一旦贴出，凭据或私有数据就已经公开，即使你随后删除。

请走下面的私下通道。

---

## 私下报告通道

通过 GitHub 的**私密漏洞报告**功能提交：

```
https://github.com/Katemtia-Axelit/super-automation-learning-tool/security/advisories/new
```

（若该功能对本仓库不可用，请直接联系仓库所有者。）

**请在报告中包含**：

| 项 | 说明 |
|---|---|
| 受影响路径 | 哪个文件 / 哪个目录 / 哪条 API |
| 问题性质 | 私有数据泄露 / 凭据泄露 / 注入 / 越权 / 其他 |
| 复现步骤 | 最小可复现流程 |
| 影响范围 | 是否有其他用户受影响 |
| 你已采取的措施 | 例如是否已轮换凭据 |

**请不要**在报告里直接粘贴完整凭据或整份笔记正文。
如果已经暴露了凭据，**请先自行轮换**，并在报告中说明「已轮换」。

---

## 凭据已泄露时的紧急处置

```bash
# 1. 立即吊销（GitHub → Settings → Developer settings → Tokens）
#    然后在终端执行：
gh auth refresh
gh auth logout

# 2. 检查该凭据是否能读到不该读的东西
gh api user

# 3. 评估影响面：仓库历史、fork、PR、Issue 评论
```

**重要**：吊销 token **不能**从 git 历史里移除已经推送的凭据。
若凭据曾被推送到 `main`，需要：
1. 立即吊销凭据（这是唯一真正有效的动作）；
2. 报告给仓库所有者，由所有者决定是否需要重写历史
   （重写历史会改变所有 commit hash，成本很高，**不能替代吊销**）。

---

## 已知的红线路径

以下路径**永远不应**出现在仓库中。若你在任何 commit、PR 或分支上看到它们，
请立即走上面的私下通道报告：

| 路径 | 内容 |
|---|---|
| `src/notes/**` | 用户 Obsidian 知识库（私有数据） |
| `data/task_publisher.db` | 实时应用数据库 |
| `data/task_publisher.db-wal` / `-shm` | 同一数据库的 WAL 家族 |
| `config/config.json` | 运行配置（密钥与本机路径） |

仓库已具备机械防线：

- `.gitignore` 声明
- CI `redline-scan` job：扫描 PR diff、`git ls-files`、**可达历史**、凭据模式
- `.cursor/hooks/redline-guard.js`：本地 `preToolUse` fail-closed 强制

但这些**不能替代**你的报告。若你发现了绕过，请告诉我们。

---

## 本地应用自身的安全建议

虽然数据不离开本机，仍建议：

- `config/config.json` 使用低权限文件；不要放进网盘同步目录。
- 不要把 `src/notes/` 设为 Git 仓库内的软链接指向同步盘。
- 在共享机器上使用完毕后停止服务（`scripts/stop_web_safe.bat`）。
- 默认监听 `127.0.0.1`；如需局域网访问，请自行确认防火墙与
  `config/config.json` 中的绑定设置。

---

## 响应预期

| 阶段 | 预期 |
|---|---|
| 确认收到 | 尽快 |
| 初步评估 | 视严重程度 |
| 修复 | 视严重程度；涉及历史重写会先与你沟通 |

本仓库的维护容量有限，**凭据泄露与私有数据泄露优先级最高**。
