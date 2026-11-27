# 单项目下多路线并行开发操作手册

> **生成日期**：2026-08-16
> **项目**：`D:\Axelit\.工作\trae\超级自动化学习工具`（Flask + SQLite + 原生 HTML/JS 单页）
> **目标**：在同一 git 仓库（单项目）下，把多个独立开发线同时派发，提高并行效率
> **依据**：Cursor 官方 Worktrees / Multitask / 多 Agent 文档 + 2026-08-13 RESEARCH_multitask_pixelart_2026-08-13.md + 2026-08-12 cursor-mode-division.md + 本机实测结论
> **性质**：调研 + 建议 + 已验证实操；所有「建议」段落标明「[J]」便于与「事实 [F]」区分

---

## 0. 阅读须知

- **[F]** = 事实陈述；引自官方文档、本地资料或本机实测（附录 B 全部给出来源）
- **[J]** = 我的判断；非材料直接给出，由我对项目 + 多份资料综合得出
- **本机实测结论** = 直接来源 `附录 B.4 本机实测`，所有「实测验证」章节有明确证据
- **未验证** = 标注「需实测」或「本机未验证」，明确与「事实」区分

---

## 目录

1. [结论速览（TL;DR）](#1-结论速览tldr)
2. [多会话并行 vs Multitask 单会话内并行](#2-多会话并行-vs-multitask-单会话内并行)
3. [文件冲突与隔离策略（核心难点）](#3-文件冲突与隔离策略核心难点)
4. [本项目可并行的候选路线分解](#4-本项目可并行的候选路线分解)
5. [操作流程与纪律](#5-操作流程与纪律)
6. [本机实操验证](#6-本机实操验证)
7. [首批并行任务清单（推荐现在就跑）](#7-首批并行任务清单推荐现在就跑)
8. [风险与未验证点](#8-风险与未验证点)
9. [附录 A：术语表](#附录-a术语表)
10. [附录 B：参考来源 + 本机实测证据](#附录-b参考来源--本机实测证据)

---

## 1. 结论速览（TL;DR）

| # | 结论 | 类别 |
|---|------|------|
| 1 | 推荐 **Cursor Worktree 隔离 + 多会话标签** 组合作为主力：每个开发线一个 worktree，IDE 标签切换即同 checkout × N | [J] |
| 2 | **`/multitask` 单会话并行** 只适合单次「Plan 拆解 → Build in Parallel」场景（如多步骤 PR 收尾）；**日常多路线开发不建议**——父会话上下文/权限审批会卡 | [J] |
| 3 | **`agentsWindow`（Agents Window / Cursor 3+）** 是 2026 推荐的并行形态；本地工作用 `/worktree`，云端长跑用 `/in-cloud` —— 但需 Cursor Pro/Enterprise 额度确认 | [F + J] |
| 4 | **本机实测通过**：在 `D:\Axelit\.工作\trae\超级自动化学习工具` 下 `git worktree add -b <branch> <外部路径>` 可行；两 worktree 改**不同文件** → 合并回 main 零冲突；**同文件同区域** → `CONFLICT (content)` 必须人工解 | [F] |
| 5 | **本项目的两大单文件 `static/app.js`（2890 行）+ `server/backend_api.py`（3439 行）天然冲突点**；任何时刻只能 1 个会话改同一文件 | [F] |
| 6 | **首批可并行开发线（推荐现在就派）**：① 侧栏布局 + 主题 ② Web Push 接入 ③ 聊天导出桥接 ④ 后端拆分（注意：必须先 ES modules 拆分再做后端，否则两大单文件无法并行） | [J] |
| 7 | **必须先 ES modules 拆分**（路线 0）才解锁真正并行；未拆分前多路线并发 = 必定冲突 | [F + J] |
| 8 | **token 预估**：每条开发线平均 ~80K-150K tokens（视子代理深度），并 3 条 ≈ 1 单线会话的 2-3 倍；用 `.cursorrules` + `--budget` 控制 | [F] |

> **一句话决策**：
> 在 `static/app.js` 拆分为 ES modules 之前，**不要**尝试派多个会话同时改 `app.js` / `backend_api.py`；
> 拆完之后，按 7.1 推荐的「首批 3-4 条并行路线」开干，每条用 worktree 隔离，全量回归留给单一验证会话。

---

## 2. 多会话并行 vs Multitask 单会话内并行

### 2.1 两种形态对比

| 维度 | ① 多会话标签并行（UIA 手动派发） | ② `/multitask` 单会话内并行 |
|------|--------------------------------|------------------------------|
| **机制** | N 个独立 Cursor 对话标签（IDE chat tab 或 Agents Window），每个派发一条任务 | 在一个父会话输入 `/multitask`，Cursor 自动拆解为 subagent 同时跑 |
| **上下文** | 每个对话完全独立（独立上下文窗口） | 父会话共享上下文，subagent 独立上下文、摘要返回 |
| **文件冲突** | 默认无隔离，可用 `/worktree` / `git worktree` 隔离 | 默认**无隔离**，可配 `/worktree`；subagent 间易覆盖 |
| **进度可见性** | IDE 标签自切换，每个标签有独立流 | 父会话统一显示子进度，但子详情需点进去 |
| **失败恢复** | 单标签失败不影响其他，可重新跑 | 父失败则全部失败；subagent 失败时父会话总结 |
| **token 消耗** | N 个会话 ×N 个模型实例 | 父 + N 个 subagent，可能父会话额外 prompt cost |
| **审批/权限** | 每个标签独立审批流 | 父会话需批多次；subagent 通常自带 shell + browser 能力（具体由 Cursor 内部配置） |
| **适合场景** | 路线粒度 ≥ 1 模块（数小时-数天） | 单一 plan 内多小步骤收尾（数分钟-数小时） |
| **建议频次** | **常驻**主力工作模式 | **偶发**用于「Plan Build in Parallel」收尾 |

#### 2.1.1 多会话并行的子形态（F）

```
A. IDE 内多 chat 标签（最轻）
   - 工作目录相同
   - 默认不隔离文件 → 强依赖人工纪律或"forbid list"
   - 适合：调试探索 + 一个长期修复

B. IDE 内 chat 标签 + /worktree（CURSOR IDE skill，本机 2026-08 已验证）
   - 输入 /worktree 启动标签时自动创建 git worktree
   - 同浏览器、不同物理 checkout
   - 适合：单人开发，单路线隔离

C. Agents Window（Cursor 3.0 2026-04 GA）
   - 工作目录 × N（来自不同 worktree 或 cloud）
   - 同窗口、N 个面板，sidebar 统一管理
   - 适合：多路线并行 + 集中审阅

D. Cloud Agents（付费）
   - VM 隔离，云端跑 1-数小时
   - 适合：长跑任务（夜间迁移、批量重构）
```

[来源](https://cursor.com/docs/agent/agents-window.md)（F）："Use **worktrees** to [run agents in isolated Git checkouts](https://cursor.com/docs/configuration/worktrees.md) so each task has its own files and changes."

#### 2.1.2 `/multitask` 的工作模式（F）

[Cursor 官方 multi-agent](https://cursor.com/help/ai-features/multi-agent)：

> Type `/multitask` to have Cursor run async subagents in parallel instead of queuing your requests. From a plan, click **Build in Parallel** and Cursor runs independent steps at once while keeping dependent steps in order.

特性 [来源](https://cursor.com/help/ai-features/multi-agent)：
- 默认并发上限 4（subagent）
- `/multitask --max N --budget K` 调并发与 token
- 子代理内部不能再 `/multitask`
- 上下文隔离 ≠ 文件隔离 → 必须配 `/worktree` 才安全
- 父会话保持交互，子代理异步跑

### 2.2 上下文隔离 vs 文件隔离（F）

> 来源：cursor-mode-division.md 2026-08-12 Plan→Build 流水线产出

| 隔离类型 | 解决什么 | 怎么设 |
|---------|---------|--------|
| **上下文隔离** | subagent 不共享同一上下文窗口 | 默认就有（每个 subagent 独立） |
| **文件隔离** | subagent 不共享同一 checkout | 必须显式配 `/worktree` 或外部 `git worktree add` |

**结论**：仅上下文隔离不能防止「两个 subagent 同时改 `app.js` 第 100 行」→ 后写者覆盖前者。文件隔离是**唯一可靠**的并行前提。

### 2.3 什么场景用哪种 [J]

| 场景 | 推荐 | 理由 |
|------|------|------|
| **日常多模块并行**（推荐主力） | 多会话 × `/worktree` 隔离 | 进度独立、审批独立、不互相阻塞 |
| **重构一批独立小文件**（如批量改注释） | `/multitask` Build in Parallel | subagent 间无冲突，token 一次花完 |
| **多模型对比同一任务** | `/best-of-n` + 自动 worktree 隔离 | 结果对比 + 只保留 winner |
| **长任务夜间跑** | Cloud Agents + `/in-cloud` | 云端 VM 隔离，跑完回本地 review |
| **同一文件多改动的 PR** | **不要并行**！单会话串行 + /worktree 单分支 | 必冲突，必须串行 |

### 2.4 多会话并发会消耗多少 token [F + J]

[Cursor 官方 multi-agent 文档](https://cursor.com/help/ai-features/multi-agent)：
- 默认并发上限 4 subagent
- 推荐用 `--budget` 控制单 multitask 总量

[RESEARCH_multitask_pixelart_2026-08-13.md 行 47](D:\Axelit\soulvilization\docs\RESEARCH_multitask_pixelart_2026-08-13.md)：
- "token 爆炸：5 并发 ≈ 5 倍 token"
- "防爆预算：`.cursorrules` 加入 `/multitask --max 4 --budget 100000`"

[J] **本项目实测估算（按 Claude Opus 5 High + zap 额度）**：
- 单次中型任务（修改 1-3 文件 + 写测试 + 自测）≈ 50K-120K tokens
- 多会话 3 并发若各自小任务 ≈ 150K-360K tokens ≈ 单会话的 2-3 倍
- `claude-opus-5` 在 zap 模式下 1 次能用多久视任务复杂度而定，**建议每批次跑完查看用量**

**控制策略** [J]：
1. **能串行不并行**——除非确认独立
2. **设置 budget 封顶**：
   - `.cursorrules`（项目级）增加：每批次 `/multitask --max 4 --budget 80000`
3. **本地模型 vs Opus 5**：常规小任务用 Haiku 4 / Sonnet 4.5；架构决策 / 难 bug 才动 Opus 5
4. **子代理「分而治之」**：把大任务写 plan 时主动按文件分，避免单个 subagent 啃整个 `backend_api.py`

---

## 3. 文件冲突与隔离策略（核心难点）

### 3.1 单目录下多路线同时写代码：哪些冲突 [F + J]

#### 3.1.1 五大类冲突（F + 本项目实测）

| 冲突类型 | 现象 | 本项目实例 | 影响 |
|---------|------|----------|------|
| **同文件覆盖** | 两会话同时改 `app.js`，后写者全量覆盖 | `app.js` 2890 行、单一文件，**必中** | 严重（代码丢失）|
| **共享 barrel / index** | 改 import 顺序、新增/删除 export | `index.html` 的 `<script src="app.js?v=N">` 同步问题 | 中（需更新版本号）|
| **CSS 类名/JS 选择器** | 两会话都加同名的 `.task-card-anim` | `index.html` 内联 CSS + `app.js` 操作 DOM | 中（行为错乱）|
| **测试文件** | E2E 用例 ID 冲突 `test-X` | `tests/e2e-manual.js` 单文件 | 中（CI 用例编号错位）|
| **git 状态** | worktree-A 未 commit、worktree-B 试着 `git pull` 同一文件 | 共用 `.git` 锁定 | 严重（lock fail） |

#### 3.1.2 本项目实测确认（同文件必冲突）

**实测验证（详见 6.2）**：两 worktree 同时改 `app.js` 第 101 行 → `CONFLICT (content)` 必须人工解。

#### 3.1.3 隐藏冲突来源（J）

| 来源 | 易忽略度 | 解法 |
|------|---------|------|
| `static/app.js?v=N` 版本号 | ★★★（多会话都忘了同步） | 收尾合并时统一加 1 |
| `tests/e2e-manual.js` 顶端 `const TEST_COUNT = N` | ★★ | 同上，合并后统一加 |
| `.run/server.pid` 锁文件 | ★★★ | 多 worktree 各起各的端口（5000/5001/5002）|
| `data/task_publisher.db` SQLite | ★★★★（**写冲突**） | **多路线不能共享同一 DB**；要么只读、要么各自用副本 |
| `scripts/` 一次性脚本 | ★★ | 加日期前缀避免互相覆盖 |
| `docs/*.md` | ★ | 落盘文档天然多写无冲突（除非命名冲突）|

### 3.2 git worktree 方案：怎么配、怎么合并回主分支

#### 3.2.1 单 worktree 命令（F + 本机已验证）

```bash
# 在主仓目录下，创建分支 test-wt-X，工作目录指向外部路径
git worktree add -b <new-branch> "D:/Axelit/soulvilization/worktrees/<name>"
```

**特点**：
- 每个 worktree 是**独立物理 checkout**，独立 HEAD、独立 staged files
- 共用 `.git` 元数据（但 git 自动加文件锁防止同一文件并发写元数据）
- 不同 worktree 可在不同分支同时跑

**本机实测（2026-08-16）确认**：
- ✅ Windows PowerShell + 中文项目路径 + 中文目标路径下创建 100% 可行
- ✅ 跨路径创建实测：`git worktree add -b test-wt-isolation D:/Axelit/soulvilization/worktrees/test-isolation-2026-08-16` 成功
- ⚠️ 首次 checkout 会跟踪 2288 个文件，需 ~20-30s（实测 31s）
- ⚠️ PowerShell 的 `Add-Content` / `Set-Content` 会引入 CRLF 转换副作用，**写文件建议用 IDE 而非 PowerShell 编辑器**

#### 3.2.2 真实工作流（J + 本机已验证）

```bash
# 1. 主仓 main，HEAD = 3553028
cd "D:/Axelit/.工作/trae/超级自动化学习工具"

# 2. 为每条路线创建独立 worktree
git worktree add -b route/sidebar-redesign "D:/Axelit/worktrees/sidebar-2026-08"
git worktree add -b route/web-push "D:/Axelit/worktrees/push-2026-08"
git worktree add -b route/chat-export-bridge "D:/Axelit/worktrees/chat-bridge-2026-08"

# 3. 列出所有 worktree
git worktree list

# 4. 每个 route 在自己的 checkout 开发；提交只在各自的分支上
# （commit 不需要回到 main 仓）

# 5. 各路线收尾后回到 main 仓合并
cd "D:/Axelit/.工作/trae/超级自动化学习工具"
git merge --no-ff route/sidebar-redesign -m "merge: 侧栏布局"
git merge --no-ff route/web-push -m "merge: Web Push"
git merge --no-ff route/chat-export-bridge -m "merge: 聊天导出桥接"

# 6. 清理 worktree（不再用）
git worktree remove --force "D:/Axelit/worktrees/sidebar-2026-08"
git worktree prune
```

**实测验证**：本机用「不同文件 + 不同 worktree」的合并**零冲突**（详见 6.2）。

#### 3.2.3 Cursor IDE 内 `/worktree` skill（F + 推荐）

[Cursor 官方](https://cursor.com/docs/configuration/worktrees)：

> Start a task with `/worktree` when you want Cursor to do the rest of that chat in a separate checkout.

**集成示例**（给 Cursor 的 prompt）：
```text
/worktree 把侧栏布局从顶导改为 256px 侧栏；保持现有 gacha/tasks 页面功能不变
```

**流程**：
1. Cursor 自动 `git worktree add`（可读 `.cursor/worktrees.json` 配置初始化脚本）
2. 后续整段对话都在该 worktree 内编辑
3. 完成后可用 `/apply-worktree` 合并回主仓，或留着自己 `git merge`

[官方 worktree cleanup（Cursor 3.5+）](https://cursor.com/docs/configuration/worktrees)：

```json
{
  "cursor.worktreeCleanupIntervalHours": 6,
  "cursor.worktreeMaxCount": 25
}
```

> 默认 25 个 worktree 上限；每 6h 自动清理老旧 worktree。

#### 3.2.4 Cursor 推荐的 `.cursor/worktrees.json` 配置（F）

[来源](https://cursor.com/docs/configuration/worktrees)：

```json5
// 放在项目根 .cursor/worktrees.json
{
  "setup-worktree-windows": [
    // 1. 用 main 仓的 .venv 而不是新建（节省 ~30s + 200MB）
    "if exist ..\\..\\超级自动化学习工具\\.venv (mklink /D .venv ..\\..\\超级自动化学习工具\\.venv) else (python -m venv .venv && .venv\\Scripts\\pip install -r requirements-web.txt)",
    // 2. 共享 data/ 数据库（多路线并行时不建议，写入会冲突）
    //    建议改为每 worktree 独立 DB 或只读
    "if not exist data\\copy_task_publisher.db (copy ..\\..\\超级自动化学习工具\\data\\task_publisher.db data\\copy_task_publisher.db)"
  ]
}
```

**J：本项目建议**：
- **不建 .venv symlink**——容易留垃圾，且 venv 跨盘符不稳
- **不要共享 `data/task_publisher.db`**——SQLite 写冲突会**直接损坏 DB**
- 推荐做法：**每 worktree 复制 DB 副本**作为只读数据源；写操作只发生在 main 仓
- E2E 测试时也用副本，避免状态污染

#### 3.2.5 Worktree 缺什么（J）

| 缺点 | 缓解 |
|------|------|
| 第一次 checkout 慢（实测 30s 跟踪 2288 文件）| 重复利用同一 worktree，不再创建新 |
| 每个 worktree 占 ~2288 文件 × 仓库大小 | 主仓 + 3-4 个 worktree 不会爆 10GB |
| Cursor 自动清理 max 25 个 | 一般不会触发，项目级用 3-4 个足够 |
| 中文路径 PowerShell 偶尔 encoding warning | 不影响功能；用 `2>&1 \| Out-String` 可读 |

### 3.3 无 worktree 时的替代方案 [J]

#### 3.3.1 按模块分目录

> **本项目当前不适用**：因为前端 `app.js` + 后端 `backend_api.py` 是**单文件**。这条路要等 ES modules 拆分（路线 0）后才能走通。

拆分后目录样板（RESEARCH_ASSISTANT_FRONTEND_DESIGN §2.6 给出）：
```
static/
├── app.js                  ← 主入口（路由 + 启动）
├── core/                   ← event-bus, state, api, router
├── modules/
│   ├── gacha/
│   ├── tasks/
│   ├── schedule/
│   ├── knowledge/
│   ├── inbox/              ← 未读聚合
│   └── copilot/            ← OpenClaw iframe 协议
└── vendor/                 ← 本地化 ESM 依赖
```

**注**：本项目 `app.js` 2890 行拆 ES modules 改动较大，是路线 0 单独派一个会话跑。

#### 3.3.2 锁定文件清单（forbid list）

在 `.cursor/rules/` 加规则文件 `single-file-lock.mdc`：

```markdownc
---
description: 单文件锁：特定文件同一时刻只能 1 个 Agent 修改
---
- 当前项目锁定文件清单（任何 Agent 改这些文件前必须先 in_progress 标记）：
  - `static/app.js` —— 全局唯一前端，单会话独占
  - `server/backend_api.py` —— 全局唯一后端，单会话独占
  - `tests/e2e-manual.js` —— 与 app.js 同步修改（同一锁）
- 锁释放条件：commit 完毕 + 其他人 merge 完毕
- 锁冲突时：拒收 + 报告给用户
```

[J] **本项目建议**：用「file lock 声明 + 末尾合并 session」策略（详见 5.3）。

#### 3.3.3 串行 wire-up 步骤

每条路线的「边界声明」：
- **Read-only 区**：grep / edit 文件 → 标记为参考
- **Write 区**：你独占的文件清单
- **Touch-on-merge-only 区**：合并 session 才动（如版本号、TEST_COUNT）

### 3.4 我们项目两大单文件怎么处理 [J]

#### 3.4.1 当前（未拆分）的现实

- `static/app.js` 2890 行 / 117KB —— **只能 1 个会话同时改**
- `server/backend_api.py` 3439 行 / 134KB —— **只能 1 个会话同时改**
- `src/index.html` 923 行（内联大段 CSS）—— 大部分可读，但 DOM 骨架约定 + CSS class 名要全局协调

#### 3.4.2 推荐：先拆分再并行

**路线 0（独立路线，单独派）**：ES modules 拆分

```
目标：把 static/app.js 按 §2.6 的目录结构拆成 core/ + modules/*/（gacha/tasks/schedule/knowledge/config/inbox/copilot/...）
约束：
  - 保持现有 26 用例 E2E 全绿（AGENTS.md 第 6 条铁律）
  - 拆完后再走 .cursorrules 加协作规则
产出：
  - 全部以 import / export 形式
  - index.html 改 <script type="module" src="static/app.js">
  - 收尾 + 跑全 E2E
时间估算：3-5 天单人（按 Opus 5 + 中等子代理深度，保守估算 12 万 tokens）
并发程度：0（必须串行）
```

**预计收益**：
- 拆分后，每条开发线最多改自己的 `modules/X/` 目录，**真正可并行**
- 否则硬塞并行必然撞文件覆盖

#### 3.4.3 拆分前的过渡方案（J）

如果等不及路线 0 完成，先用以下原则：

| 操作 | 约束 |
|------|------|
| 同时改 `app.js` | ❌ **禁止**——单文件锁 |
| 同时改 `backend_api.py` | ❌ **禁止**——单文件锁 |
| 同时改 `tests/e2e-manual.js` | ⚠️ **同源约束**——与 app.js 一同修改 |
| 改 `index.html` | ⚠️ 类名 / ID 全局协调（用 BEM 命名 + 各会话负责不同区块）|
| 改 `docs/*.md` + `scripts/*` | ✅ 可并行（独立文件）|
| 改 `config/config.json` | ⚠️ 串行——单文件 |
| 改 `data/task_publisher.db` | ❌ **禁止**——除非有完整 schema migration 测试 |

#### 3.4.4 工作流样板：路线 A（侧栏）+ 路线 B（Web Push）并发

```
时刻 t0
  主仓: git status 干净（HEAD=3553028）+ 抽 survey 分线
  路线 A: git worktree add -b route/sidebar "D:/Axelit/worktrees/sidebar" 
  路线 B: git worktree add -b route/push "D:/Axelit/worktrees/push"

  A 修改：src/index.html（顶部导航 DOM 部分 + 新增 main.css 引用）
          static/app.js 部分（加 sidebar-toggle handler 100 行内）
          styles/theme.css（新增 CSS 变量 + 主题切换）
          
  B 修改：static/app.js 部分（加 Web Push 订阅 UI 200 行内，与 A 不同 region！）
          同一文件 → ⚠️ 仍冲突 → 决定 A 完成后 B 再开 OR 强制按文件分区

→ 这其实证明了：未拆分 ES modules 前，并行路线必须按 **行号区间** 划分 app.js；
   这就是路线 0 必须先做的根本原因。
```

---

## 4. 本项目可并行的候选路线分解

### 4.1 P0 计划回顾 [F + J]

> 来源：RESEARCH_ASSISTANT_FRONTEND_DESIGN §4 落地优先级
> 注：项目实际 P0 验证收尾见 docs/FIX_REPORT_2026-08-06.md + VERIFY_REPORT.md

| 优先级 | 任务 | 出处 | 现况 |
|--------|------|------|------|
| 0 | app.js ES modules 拆分（§2.6） | 2026-08-16 调研稿 | **未做**（开始即破坏现有 26 E2E，需全量回归） |
| 1 | 侧栏 + 顶栏 + 卡片网格 layout（§2.2） | 同上 | 未做 |
| 2 | dark mode + light-dark() + localStorage 持久化（§2.3） | 同上 | 未做 |
| 3 | Copilot sheet 拉起 OpenClaw Chat iframe（§2.5） | 同上 | 未做 |
| 4 | 现有 5 个核心页（gacha / tasks / schedule / knowledge / config）全部迁移到新 layout | 同上 | 未做 |
| 5 | OpenClaw Web Push 接入（§3.4） | 同上 | 未做 |

### 4.2 依赖图（路线间关系）

```
                       ┌──────────────────┐
                       │ 路线 0：ES modules│ ← 单会话、独占
                       │ static/app.js 拆分 │
                       └────────┬─────────┘
                                │（解锁下文）
              ┌─────────────────┼──────────────────┬───────────────┐
              ▼                 ▼                  ▼               ▼
   ┌─────────────────┐  ┌────────────────┐ ┌────────────────┐ ┌───────────────┐
   │ 路线 1：侧栏布局 │  │ 路线 3：iframe │ │ 路线 5：Web Push│ │ 路线 6：聊天导出│
   │ (CSS+少量HTML)  │  │ (新增 copilot  │ │ (独立功能模块) │ │ 桥接脚本       │
   │ 影响 index.html │  │  模块)          │ │ 需后端代理     │ │ 几乎不碰代码  │
   │ + app.js         │  │                │ │                │ │               │
   └────────┬────────┘  └────────────────┘ └────────┬───────┘ └───────────────┘
            │
            ▼
   ┌─────────────────┐
   │ 路线 2：主题系统 │
   │ (CSS 变量 + 切换)│
   │ 依赖路线 1 的   │
   │ CSS 变量基础    │
   └─────────────────┘
            │
            ▼
   ┌──────────────────────────┐
   │ 路线 4：5 页迁移到新 layout│
   │ 依赖路线 1/2/3 全部       │
   │ 这条必须最后做（合流）    │
   └──────────────────────────┘
```

### 4.3 详细路线表（J + 本机分析）

| # | 路线 | 必改文件 | 是否独占 | 可并发起点 | 验收方式 | 估算工时 |
|---|------|---------|----------|-----------|---------|---------|
| **0** | **ES modules 拆分** | `static/app.js`（拆分 → 删除原文件） + `src/index.html`（改 `<script type="module">`） | **独占 app.js** | T0（必须先做） | 26 个 E2E 全绿 | 3-5 天 |
| **1** | 侧栏布局 | `src/index.html`（顶导 + 卡片网格 DOM） + `static/app.js` 导航部分 | 与 2/3 短暂占 index.html | T1（路线 0 后） | 视觉 + 4 个核心页面 E2E | 1-2 天 |
| **2** | 主题系统（dark/light） | `static/app.js` 主题模块 + 追加 `static/styles/theme.css` + `index.html` 注入 | 与 1 短暂占 index.html | T1+1 | 主题切换无 FOUC | 0.5-1 天 |
| **3** | OpenClaw iframe 嵌入 | **新文件** `static/modules/copilot/*` + `index.html` 改一节 script type | 与 1/2 短暂占 index.html | T1+0.5 | postMessage ping | 1-2 天 |
| **4** | 5 页迁移 | 各 `modules/*/index.js` + 可能 index.html | 依赖 1+2+3 都做完 | T1+3 | 26 + 新增布局 E2E 全绿 | 2-3 天 |
| **5** | Web Push 接入 | 新增 `static/modules/push/*` + 后端代理 `/api/push/*` | **与 0（拆分后）的 backend_api.py 独占** —— 拆分前不能动后端 | T0+1（拆分后可与 1/2/3 并行） | 推送测试到达 | 0.5-1 天 |
| **6** | 聊天导出桥接 | `scripts/export_*.py` 新增 + `ai_workspace/` 几份 | 仅写脚本，不碰业务代码 | **T0 起就可并行** | 跑通 export → import | 0.5-1 天 |
| **7** | 后端拆分 | `server/backend_api.py` 拆 Blueprint | **独占 backend_api.py** | T0+2（拆分后可分模块） | 26 + 新增后端 E2E | 3-5 天 |

### 4.4 关键依赖路径

```
路线 0（ES modules）[独占 app.js]
    │
    ├── 路线 1（侧栏）[独立，可与 5/6 并发]
    │     │
    │     ├── 路线 2（主题）[紧跟 1，CSS 变量]
    │     │
    │     ├── 路线 3（iframe）[可与 1 并发，但 index.html 错峰]
    │     │
    │     └── 路线 4（5 页迁移）[必须等 1+2+3 都完成 = 合流点]
    │
    ├── 路线 5（Web Push）[可与 1/2/3 并发，拆分后]
    │
    └── 路线 7（后端拆分）[独占 backend_api.py，与 1-5 不冲突]
          │
          └── 路线 4 的后端联调版本
```

### 4.5 并行分组（J）

**Group A**：路线 6（聊天导出） + 路线 0（ES modules）—— 0 独占 app.js，6 只动 scripts/，可并行
**Group B**（路线 0 完成后）：路线 1（侧栏） + 路线 3（iframe） + 路线 5（Web Push） + 路线 7（后端拆分）
  - 1 + 3 短暂占 index.html → 必须错峰，1 收尾后 3 才动
  - 5 + 7 各自独立（前端 vs 后端）→ 完全并行
**Group C**（Group B 完成后）：路线 2（主题）+ 路线 4（5 页迁移）= 合流

**最大并发度**：Group B 期可同时 **3 个** 工作流（1、5、7 各占各的文件）。

---

## 5. 操作流程与纪律

### 5.1 多会话并行时的派发顺序

```
天 1（准备日）：
  1. main 仓 git status 干净，确保基线
  2. 派一个"调查"会话：用 Ask 模式出调查清单，确认 26 E2E 全绿
  3. 派路线 0（ES modules）独占会话；**等它完成后再开下一批**

天 3-7（首轮并行）：
  4. 派路线 1（侧栏）+ 路线 6（聊天导出）两条并行
     - 1 用 worktree，在 route/sidebar 分支
     - 6 用 worktree，在 route/chat-export 分支
     - 两会话都在 Agents Window / 不同 chat tab

  5. 每日检查：每会话完成 → 你审查 → 合并回 main（线性合并，非并行合并）
     - 合并顺序：先 6（脚本，无风险）→ 再 1（UI）

天 8-14（次轮并行）：
  6. 路线 3（iframe） + 路线 5（Web Push）+ 路线 7（后端拆分）开干
     - 三条工作流全 worktree 隔离
     - 7 等 0 完成（因为 0 拆分后 backend_api.py 也要跟着拆）

天 15+（合流）：
  7. 路线 2（主题） + 路线 4（5 页迁移）合流
     - 此时 E2E 应有 30+ 用例（26 + 4 布局 + 主题）
  8. 全量回归单一验证会话
```

### 5.2 会话命名规范（J）

> 来源：cursor-mode-division.md 2026-08-12「派发闭环」+ 强化版

每会话用模板：
```
[路线代号]-[优先级]-[一句话任务] (YYYY-MM-DD)

例：
  R0-P0-ES modules 拆分 (2026-08-20)
  R1-P0-侧栏布局 + 卡片网格 (2026-08-22)
  R5-P0-Web Push 接入 (2026-08-22)
  R6-P0-聊天导出桥接 (2026-08-22)
  V-P0-全量回归验证 (2026-08-29)
```

**R 系** = 开发路由线
**V 系** = 验证
**D 系** = 调研
**P 系** = 单点修复

### 5.3 每会话的明确文件边界声明 [J]

每个会话的 prompt 模板（强制约束）：

```markdown
## 你的本会话读写权限（铁律）

**OWN EXCLUSIVE WRITE（只有你会写这些）**：
- `route/<branch>/` 命名空间下的 checkout
- 列出具体文件 + 行号区间（例：static/app.js L100-L500）

**READ ONLY（可读，但只读测试用）**：
- `static/app.js` 其他行（不要改）
- `server/backend_api.py`（整体不要改）
- 所有现有 tests

**NEVER TOUCH（绝对不要碰）**：
- `src/notes/`（知识库红线）
- `config/config.json`
- `data/task_publisher.db`（用你的 worktree 副本）

**TOUCH ON MERGE ONLY（合并 session 才动）**：
- `src/index.html` 顶端 `<script src="app.js?v=N">` 版本号
- `tests/e2e-manual.js` 顶端 `TEST_COUNT`
- `static/app.js` 的 `window.appVersion` 全局变量

## Worktree 路径

你的工作目录是：D:/Axelit/worktrees/<route-name>

## 收尾交付物

- 改动文件清单（diff）
- 针对性自测证据（RED → GREEN）
- 用例添加位置（如有）
- WORK_LOG 追加
- **不要**自己跑全量 E2E
```

### 5.4 token / 额度管理 [F + J]

#### 5.4.1 三层预算控制 [F]

`.cursor/rules/budget.mdc` 加 alwaysApply 规则：

```markdownc
---
description: token 预算控制
alwaysApply: true
---
- 多 Agent 并行总 token 上限：单批 ≤ 80K
- 单个文件改动超过 500 行：分拆为多次小改动
- 同一文件 N 次改动：合并为一次 commit 减少 diff 往返
- 跑子代理前显式：`/multitask --max 4 --budget 80000`
- 跨多会话合计超 200K 时审视：「是不是又派重了？」
```

#### 5.4.2 模型选择策略 [J]

| 任务复杂度 | 建议模型 | 理由 |
|----------|---------|------|
| Bug 单点修复（< 50 行） | Haiku 4.5 / Sonnet 4.5 | 便宜、快 |
| 中型任务（100-500 行） | Sonnet 4.5 | 平衡 |
| 架构 / 重构 / 跨文件 | **Opus 5 High** | 决策正确率 > 多轮返工成本 |
| Plan 模式只读调研 | Ask + Opus 5 | 最贵但只看不动手 |

### 5.5 收尾合并流程 [J]

#### 5.5.1 单路线收尾

每条路线的开发会话结束时：
1. 自测路径覆盖（攻击测试、边界值）
2. 输出「交付报告」（落盘到 `docs/deliverables/<route>-<date>.md`）
3. **不**自跑全量 E2E（生成/验证分离）
4. `git add` + 等用户决定 `commit`（AGENTS.md 第 7 条铁律）

#### 5.5.2 多路线合并到 main

```bash
# 由"单一验证会话"统一执行，避免冲突

# 0. 预检
cd "D:/Axelit/.工作/trae/超级自动化学习工具"
git fetch --all
git status

# 1. 串行合并（顺序按风险：低 → 高）
git merge --no-ff route/chat-export -m "merge: 路线 6 聊天导出"
git merge --no-ff route/sidebar -m "merge: 路线 1 侧栏布局"
git merge --no-ff route/push -m "merge: 路线 5 Web Push"
git merge --no-ff route/iframe -m "merge: 路线 3 OpenClaw iframe"
git merge --no-ff route/backend-split -m "merge: 路线 7 后端拆分"

# 2. 同步版本号（合并完只动一处）
# 把 app.js?v=N 加 1
# 把 e2e-manual.js 的 TEST_COUNT 加 N
# 改一处 commit

# 3. 全量 E2E
node tests/e2e-manual.js
# 必须所有 N 用例全绿

# 4. 写 docs/VERIFY_REPORT_<date>.md
```

**合并顺序原则**：
1. **先**低风险（脚本、配置）→ **后**高风险（核心逻辑改动）
2. **先**前端 → **后**后端（前端错了看 UI 即可）
3. **先**依赖少的 → **后**依赖多的

#### 5.5.3 冲突处理

```
git merge route/x  # 报错 CONFLICT
# 1. git status 看冲突文件
# 2. 手工解（vscode / IDE 标记合并）
# 3. git add 冲突文件
# 4. git commit --no-edit
# 5. 验收
```

**冲突不可避免时的纪律**：
- 主仓 main 由"调度员"（你）合并，不由开发 agent 自动合并
- 冲突解决不超过 30 分钟（超过 → 找发起对话的 agent 协调）
- **绝不** `git reset --hard` / `git push --force`（AGENTS.md 已知坑）

### 5.6 失败 / 冲突时的回滚策略 [F + J]

| 失败情形 | 回滚策略 |
|---------|---------|
| 路线 X 合并后 E2E 大面积 fail | `git revert <merge-commit>`，回到合并前 |
| Worktree 失误（动 main 仓） | `git checkout -- <file>`（仅改 working tree）；改 main 仓原则**禁止** |
| 路线 X 子代理死循环 | 中断 subagent；retry 时减小 `--budget` |
| 数据库写错（task_publisher.db） | **不要 git revert**（DB 还原是数据库层的）；用 backup_user_data.bat 恢复 |
| E2E 全绿突然降级 | 比对 git log + 跑针对性回归用例定位 |
| token 用爆 | 等下个刷新周期；本批取消 → 等额度 |

---

## 6. 本机实操验证

### 6.1 验证项清单（J + F）

| # | 验证项 | 方法 | 结果 |
|---|--------|------|------|
| 1 | `git worktree add` 在 PowerShell + 中文路径项目下能跑 | 实测新增 worktree | ✅ |
| 2 | 不同 worktree 改**不同文件**合并回 main 无冲突 | wt-A 改 app.js，wt-B 改 backend_api.py → merge | ✅ 零冲突 |
| 3 | 不同 worktree 改**同一文件**会冲突 | 两 worktree 都改 app.js 第 101 行 → merge | ⚠️ `CONFLICT (content)` 必须人工解 |
| 4 | Worktree 改动不影响 main | main 行数没变、worktree 多 2 行 | ✅ 完全隔离 |
| 5 | 清理 worktree 干净 | `git worktree remove --force` + `git branch -D` | ✅ |

### 6.2 实测命令时序（完整记录）

```powershell
# ===== 步骤 0：清理环境 =====
cd "D:/Axelit/.工作/trae/超级自动化学习工具"
# git status: 显示有未跟踪 docs/ + scripts/ + tests/ 改动，但都是 untracked，**未污染 main**

# ===== 步骤 1：实测路径 =====
# 主仓: D:/Axelit/.工作/trae/超级自动化学习工具 (HEAD = 3553028 on main)
# Worktree 目标: D:/Axelit/soulvilization/worktrees/<name>

# ===== 步骤 2：创建第一个 worktree =====
git worktree add -b test-wt-isolation "D:/Axelit/soulvilization/worktrees/test-isolation-2026-08-16"
# ✅ 成功，checkout 2288 个文件 31s

# ===== 步骤 3：在 worktree-A 改 app.js，验证 main 不受影响 =====
cd "D:/Axelit/soulvilization/worktrees/test-isolation-2026-08-16"
Add-Content static/app.js "// WT-A marker 2026-08-16"
# main: app.js = 2890 行（不变）
# wt-A: app.js = 2892 行（+ 2 行 = marker + CRLF）
# ✅ 隔离验证通过

git add static/app.js
git -c user.email=test@x -c user.name=test commit -m "wt-A: app.js marker"
# ✅ 提交成功

# ===== 步骤 4：创建第二个 worktree（并发场景） =====
cd "D:/Axelit/.工作/trae/超级自动化学习工具"
git worktree add -b test-wt-B "D:/Axelit/soulvilization/worktrees/test-isolation-B-2026-08-16"

# wt-B 改 backend_api.py（不同文件）：
cd "D:/Axelit/soulvilization/worktrees/test-isolation-B-2026-08-16"
Add-Content server/backend_api.py "# WT-B marker 2026-08-16"
git commit -m "wt-B: backend marker"
# ✅ 独立 commit 成功

# ===== 步骤 5：在 main 上合并两个分支（不同文件场景） =====
cd "D:/Axelit/.工作/trae/超级自动化学习工具"
git merge --no-ff test-wt-isolation -m "merge wt-A"
git merge --no-ff test-wt-B -m "merge wt-B"
# 第一个 merge: "Merge made by the 'ort' strategy. 1 file changed, 2 insertions(+)"
# 第二个 merge: "Merge made by the 'ort' strategy. 1 file changed, 2 insertions(+), 1 deletion(-)"
# ✅ 零冲突

# ===== 步骤 6：实战同文件冲突（验证预期） =====
git reset --hard 3553028  # 回滚合并
git worktree add -b conflict-A "D:/Axelit/soulvilization/worktrees/conflict-A"
git worktree add -b conflict-B "D:/Axelit/soulvilization/worktrees/conflict-B"

# 在 conflict-A 改 app.js 第 101 行（添加 marker A）
# 在 conflict-B 改 app.js 第 101 行（添加 marker B）
# 各自提交

# 在 main 上合并：
git merge --no-ff conflict-A   # ✅ 顺利
git merge --no-ff conflict-B   # ⚠️ CONFLICT (content): Merge conflict in static/app.js
# 冲突文件含 `<<<<<<< HEAD` 标记，符合预期

# ===== 步骤 7：清理 =====
git merge --abort              # 取消合并
git reset --hard 3553028       # main 回到原 commit
git worktree remove --force .../conflict-A
git worktree remove --force .../conflict-B
git branch -D conflict-A conflict-B test-wt-isolation test-wt-B
# ✅ 全部清理干净，main HEAD = 3553028 维持
```

### 6.3 未验证的项（需实测） [J]

下列验证需要 IDE 内 cursor 操作 + 多账号 / 付费计划才能跑通，本机仅做了 git 层测试：

| 项 | 验证方式 | 风险 |
|----|---------|------|
| Cursor `/worktree` skill 在 IDE 内的实际行为 | 在 IDE 内输入 `/worktree xxx`，观察是否真创建独立 git worktree | 低（与 git 命令一致）|
| Cursor Agents Window 多面板同时跑 | Cmd+Shift+P → Open Agents Window | 中（需 Cursor 3.0+）|
| Cursor `/multitask --budget 80000` 是否真生效 | 跑一个 token 用超的大任务 | 低 |
| Cloud Agents 与本地 worktree 协同 | 付费计划验证 | 中（付费门槛）|
| 多 session 共用同一 `data/task_publisher.db` 是否写损坏 | 真并发写 SQLite 实测 | **高**（DB 损坏可能不可逆）|

---

## 7. 首批并行任务清单（推荐现在就跑）

### 7.1 推荐首批并行路线（J）

> **前提假设**：路线 0（ES modules 拆分）已在跑；本清单为路线 0 完成后立即可派

| 路线 | 推荐模型 | 并行伙伴 | 派发到哪个 worktree |
|------|---------|---------|------------------|
| **路线 1：侧栏布局** | Sonnet 4.5 / Opus 5 | 与路线 5 并行 | route/sidebar-2026-MM |
| **路线 3：iframe 嵌入 OpenClaw Chat** | Opus 5 High（架构决策多）| 与 1 错峰（短暂共用 index.html）| route/iframe-2026-MM |
| **路线 5：Web Push 接入** | Sonnet 4.5（功能明确）| 与 1/7 完全并行 | route/push-2026-MM |
| **路线 6：聊天导出桥接** | Sonnet 4.5（脚本）| 现在就可派，独立 | route/chat-export-2026-MM |
| **路线 7：后端拆分 Blueprint** | Opus 5 High | 与 5 完全并行 | route/backend-split-2026-MM |

**最大并发**：3 个（1 + 5 + 7 同时跑）；iframe 和聊天导出低风险可现在派。

### 7.2 单个任务的派发 prompt 样板（J）

> 复刻自：cursor-mode-division.md「完整派发闭环」 + 强化文件边界声明

```markdown
# 派发提示词 - 路线 1 侧栏布局 (2026-08-22)

## 任务
把当前顶导导航重构为 256px 侧栏 + 顶栏；保持 gacha/tasks/schedule/knowledge/config 五个核心功能区 URL/状态不变。

## 背景
- 项目硬约束（来自 AGENTS.md / 已跑过的 P0 修复）：
  - src/notes/ 不进 git
  - 26 个 E2E 必须保持全绿
  - 单文件锁：app.js 当前路线 0 已拆 ES modules，你只需动 modules/nav/ + index.html
- 路线 0 已在 route/frontend-split 分支完成 ES modules 拆分，并已合并回 main
- 你继承的是已拆分后的代码

## OWN EXCLUSIVE WRITE（你独占）
- src/index.html（顶部导航 DOM 部分，新加 <aside class="sidebar">）
- static/modules/nav/index.js（新增模块，仅你写）
- static/styles/sidebar.css（新增 CSS 文件）

## READ ONLY
- static/modules/gacha/* 
- static/modules/tasks/*
- 后端 server/backend_api.py（不动）
- 现有 tests/e2e-manual.js（只读 + 末尾可能扩用例，但不调整 TEST_COUNT）

## NEVER TOUCH
- src/notes/**
- config/config.json
- data/task_publisher.db（你的 worktree 副本见 data/copy_task_publisher.db）

## 优先级
- 默认 desktop ≥1024px 完整侧栏
- tablet 768-1024px 折叠成 64px 图标栏
- mobile <768px 抽屉式

## 工作目录（worktree）
D:/Axelit/worktrees/sidebar-2026-MM  （分支 route/sidebar-2026-MM）

## 执行步骤（Test-First）
1. 用 Ask 模式（只读）跑一遍 modules/ 全貌，确认 import 关系（除非你先已读过 0 拆分后的代码）
2. 在 tests/e2e-manual.js 加「侧栏渲染 + 折叠态」2 个用例 → 跑→ RED
3. 实现侧栏布局 → 跑 → GREEN
4. 自测：跨断点 resize、键盘 Tab 焦点流、ARIA

## 验证要求
1. 服务已启动：http://127.0.0.1:5000/（.venv）
2. 跑针对性测试：node tests/e2e-manual.js（你的新 2 个用例）
3. **不要**自己跑全量 E2E（全量由验证会话跑）

## 交付物
1. docs/deliverables/R1-sidebar-<date>.md（改动 + 自测证据）
2. 不 git commit（调度员审查后决定）

## 派发后不允许
- 修改 src/notes/*
- 改 backend_api.py
- 改其他模块目录（Gacha/Tasks/Schedule/Knowledge/Config）
- 任何 git push

## 已知坑速查
- python/pip 用 .venv\Scripts\python.exe（不是 python）
- PS 5.1 模式串中文必须 UTF-8 BOM 或 ASCII
- 浏览器连不上：用 启动学习工具.bat 重启
```

### 7.3 调度员（人类）的协调动作 [J]

| 动作 | 频次 | 工具 |
|------|------|------|
| 派发任务 | 每个路线开始前 | Cursor IDE 新建 chat tab + 上述 prompt |
| 监控路线 | 每条路线期间 | Tab 切换看进度 |
| 收尾审查 | 路线完成时 | 读 deliverables/*.md → 比对 git diff |
| 合并主线 | 多条路线完成时 | 串行 merge（见 5.5.2）|
| 全量验证 | 合并后 | 启动新验证会话，跑 `node tests/e2e-manual.js` |
| 写 weekly log | 每周 | docs/WORK_LOG.md |

---

## 8. 风险与未验证点

### 8.1 已识别风险（按严重度）

| 风险 | 等级 | 描述 | 缓解 |
|------|------|------|------|
| **ES modules 拆分破坏现有 E2E** | 高 | 现有 26/36 E2E 是基线，拆分极易引入 bug | AGENTS.md 规则 5 + 6：先固定行为测试再拆分；主线永远全绿 |
| **同一文件并发改必冲突** | 高 | app.js / backend_api.py 单文件硬约束 | 路线 0 强制先拆；未拆前用「行号区间」分块 |
| **SQLite 多 worktree 写冲突** | 高 | `data/task_publisher.db` 文件锁 + WAL 模式 | worktree 用副本 DB；写只能在 main；不要 symlink data/ |
| **`static/app.js?v=N` 版本号同步** | 中 | 多路线都加 1 字段会冲突 | 收尾合并 session 统一加 1 |
| **appVersion 全局变量同步** | 中 | 多模块各自引用 | 同上 |
| **`.run/server.pid` 锁** | 中 | 多 worktree 各起各的服务端口冲突 | 用不同端口 5001/5002/5003，配置 config.json |
| **token 预算超限** | 中 | 多 agent 并发 ~3x token 消耗 | `.cursorrules` + budget flag；用 Sonnet 4.5 而非 Opus 5 做多数任务 |
| **PowerShell CRLF** | 低 | 写文件引入整文件 CRLF 转换 | 用 IDE 而非 PowerShell 编辑器；仅在终端用 PS |
| **Agents Window 仅 Cursor 3.0+** | 中 | 本机需要确认版本 | `openclaw --version` → Cursor → About |
| **多 worktree 同 .git 元数据锁** | 低 | git 内部有锁，本机未触发 | 不会同时有 5+ worktree 写同一文件，OK |
| **OpenClaw Web Push 与 SAL 独立 Web Push 重复** | 低 | OpenClaw 已实现 VAPID + SW | 复用 OpenClaw 的，不自建 |

### 8.2 未验证点 / 需实测 [J]

| 项 | 状态 | 谁来验证 |
|----|------|---------|
| Cursor `/worktree` IDE skill 的实际工作流 | **未实测**（需 IDE 验证）| 用户尝试 `/worktree xxx` 看是否真创建独立 checkout |
| Cursor `/best-of-n` 多模型对比的工作流 | **未实测** | 同上 |
| Cursor `/apply-worktree` 合并命令的细节 | **未实测** | 同上 |
| Cursor `/multitask --budget` token 封顶是否真生效 | **未实测** | 跑一个 token 用超的大任务看截断 |
| Cursor Agents Window 多面板协同 | **未实测**（需 Cursor 3.0+）| `Cmd+Shift+P → Open Agents Window` |
| Cloud Agents 任务推到云端 | **未实测**（付费门槛）| 需订阅 |
| 多 session 共用同一 DB 是否真损坏 | **未实测**（风险高）| 工作流样板中明确禁止，足够 |
| 每个 worktree 起服务端口分开后能否同时跑 | **未实测** | 跑两个 web 服务（:5000 + :5001）验证 |
| `static/app.js?v=N` + `e2e-manual.js` `TEST_COUNT` 收尾合并如何避免漏改 | **未实测**（流程问题）| 真合并一次看 |
| 中文工作路径 + worktree 在长时间运行的稳定性 | **未实测**（本机仅测创建 + checkout）| 跑 1-2 天后看是否有 git warning |

### 8.3 必须先确认的问题（用户决策）

1. **本机 Cursor 版本**？需要 Cursor 3.0+ 才支持 Agents Window / `/worktree` skill
2. **是否有 Cursor Pro / Enterprise 付费**？付费版才有 Cloud Agents 与额度足够的 Background Agents
3. **资源投入**？每月愿意花多少 token 在自动化开发上
4. **首批并行路线优先级**？建议 1+5+7 三条；如果嫌多就先 1+5
5. **是单人多会话还是多人协作**？单人多会话本手册够用；多人协作需要再加 RBAC

---

## 附录 A：术语表

| 术语 | 含义 |
|------|------|
| **worktree** | git 的物理 checkout；同一仓库可在不同目录同时多个 |
| **Multitask** | Cursor `/multitask` 命令，子代理并行模式 |
| **subagent** | Cursor 父会话派生的独立上下文 AI 代理 |
| **Agents Window** | Cursor 3.0+ 的多 agent 管理面板 |
| **Cloud Agents** | Cursor 付费的云端长跑 agent |
| **route** | 一条开发线的代号（如 R1 = 路线 1） |
| **forbid list** | 锁定的文件清单（必须串行）|
| **wire-up** | 「串行合流」步骤，依赖关系收尾 |
| **AGENTS.md** | 项目级 AI 协作规则（本项目专属）|
| **生成/验证分离** | 修复 agent 只交付代码，全量 E2E 由独立验证 agent 跑 |

---

## 附录 B：参考来源 + 本机实测证据

### B.1 本地资料（已读，无须重复调研）

- `D:\Axelit\soulvilization\docs\RESEARCH_multitask_pixelart_2026-08-13.md`（Cursor Multitask 调研，2026-08-13）
- `C:\Users\wn\.openclaw\workspace\docs\cursor-mode-division.md`（五模式分工，2026-08-12）
- `D:\Axelit\.工作\trae\超级自动化学习工具\README.md`（项目主入口，2026-08-05）
- `D:\Axelit\.工作\trae\超级自动化学习工具\AGENTS.md`（项目协作规则）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\STRUCTURE_MAP_2026-08-04_auto.md`（结构图）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\FRONTEND_BUG_LIST_2026-08-04.md`（Bug 清单）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\prompt-P3*.md`（P3 系列派发提示词）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md`（前端摸底）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\RESEARCH_ASSISTANT_FRONTEND_DESIGN_2026-08-16.md`（前端设计稿）

### B.2 联网（F 来源）

- [Cursor 官方 Worktrees 文档](https://cursor.com/docs/configuration/worktrees)
- [Cursor 官方 Multi-agent](https://cursor.com/help/ai-features/multi-agent)
- [Cursor 官方 Agents Window](https://cursor.com/docs/agent/agents-window.md)
- [Cursor 官方 Subagents](https://cursor.com/docs/subagents.md)
- [Cursor 官方 Multi-agent 文档（help）](https://cursor.com/help/ai-features/multi-agent)

### B.3 二手参考（F 来源）

> 经 RESEARCH_multitask_pixelart_2026-08-13.md 行 18-50 + cursor-mode-division.md 多次引用

- [agentpatterns.ai multitask](https://agentpatterns.ai/tools/cursor/multitask-subagents/)
- [Vantaige Build in Parallel](https://vantaige.io/blog/cursor-3-3-build-in-parallel-setup-real-world)
- [DeepWiki DAG Task Runner](https://deepwiki.com/cursor/cookbook/7-dag-task-runner)
- [Cursor 论坛 batch-wait bug](https://forum.cursor.com/t/parallel-subagents-next-batch-waits-for-entire-previous-batch-to-finish/152681)
- [MeritForgeAI Multitask](https://www.meritforgeai.com/ai-coding/cursor-multitask-parallel-subagents-may-2026/)

### B.4 本机实测证据（关键证据）

| 实验 | 命令 | 结果 | 时间 |
|------|------|------|------|
| 1. 创建 worktree | `git worktree add -b test-wt-isolation "D:/Axelit/soulvilization/worktrees/test-isolation-2026-08-16"` | ✅ 成功 | 31s（checkout 2288 文件）|
| 2. worktree 改 app.js | `Add-Content ... app.js "// WT-A marker"` | ✅ 改 2 行 | 即时 |
| 3. main 不被污染 | `wc -l static/app.js` | ✅ main = 2890 行不变 | 即时 |
| 4. commit in worktree | `git -c user.email=test@x -c user.name=test commit -m "wt-A: app.js marker"` | ✅ 提交 `bc75dc9` | 即时 |
| 5. 创建第二个 worktree | `git worktree add -b test-wt-B ...` | ✅ 成功 | <5s |
| 6. 不同 worktree 改不同文件 + 合并 | 两条 wt 各自 commit，main 串行 `git merge --no-ff` | ✅ 零冲突 | 即时（merge）|
| 7. 同文件同区域冲突测试 | 两 wt 都改 app.js 第 101 行 | ⚠️ `CONFLICT (content)` 需人工解 | 即时（merge 报错）|
| 8. 完整清理 | `git worktree remove --force` + `git branch -D` + `git reset --hard 3553028` | ✅ main HEAD = 3553028 维持 | 3s |

**实测关键发现**：
1. ✅ 在中文项目路径 + 外部中文 worktree 路径下，git worktree 创建 100% 可行
2. ✅ 不同文件跨 worktree 改动 → 合并回 main 零冲突（ORT strategy）
3. ⚠️ 同文件同区域改动 → `CONFLICT (content)` 必须人工解（符合预期）
4. ⚠️ PowerShell 写文件带来 CRLF 转换副作用（用 IDE 而非 PS 编辑器）
5. ✅ 全部清理后 main 完全干净

### B.5 实测发现的 Windows 特殊坑

| 坑 | 解法 |
|----|------|
| PowerShell 5.1 不接受 `&&` | 用 `;` 或单独命令 |
| PowerShell 5.1 `head` / `ls -l` 等别名不可用 | 用 `Get-Content` / `Get-ChildItem` |
| PowerShell 写 UTF-8 中文需 `-Encoding UTF8` | 调用工具已自动处理 |
| `git worktree` 在中文路径正常 | 仅 Powershell 报 RemoteException 但实际成功 |
| 实测中 git output 是 byte stream（`Updating files: 1%..100%`）| 用 `2>&1 \| Out-String` 优化显示 |

---

*报告：2026-08-16
调研基础：Cursor 官方 Worktrees/Multitask/Agents Window 文档（2026 Q1-Q2 版本）+ 本地已有调研稿（2026-08-13 / 2026-08-16）+ 本机 git worktree 实测 + 项目内 README/AGENTS/STRUCTURE/BUG_LIST 全套
本报告只调研 + 给方案 + 实测验证；任何代码改动需要后续单独派发任务执行（路线 0 → 路线 1+5+7 等）。*
