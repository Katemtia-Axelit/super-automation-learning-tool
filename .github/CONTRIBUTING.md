# 参与贡献

感谢参与。本文件是**参与规范与红线声明**的权威入口。

---

## 1. 红线声明（最高优先级，不可协商）

以下路径是**项目红线**，任何情况下都不得进入版本库、不得在 PR 中被触碰：

| 路径 | 内容 |
|---|---|
| `src/notes/**` | 本地 Obsidian 知识库——**用户私有数据** |
| `data/task_publisher.db` | 实时应用数据库 |
| `data/task_publisher.db-wal` / `.db-shm` | 同一数据库的 WAL 家族 |
| `config/config.json` | 运行配置（含密钥与本机路径） |

同时**永不提交**：

- 任何凭据、Cookie、`.env` 内容、私钥（`ghp_*` / `gho_*` / `github_pat_*` / `-----BEGIN * PRIVATE KEY-----`）
- `prototypes/`、课程题库（`data/*.txt`、`data/*.md`）、个人学习资产
- 真实用户笔记的正文或路径清单

**这不是「请不要提交」，而是有机械强制力**：

| 层 | 机制 |
|---|---|
| L1 声明 | 本文件、`.gitignore`、`AGENTS.md`、`SECURITY.md` |
| L2 仓库 | CI `redline-scan` job：扫描 PR diff、`git ls-files`、**可达历史**、**所有 remote-tracking ref**、凭据模式 |
| L3 强制 | `main` 分支保护：禁止直推，`ci/gates` + `ci/redline-scan` 必过 |
| L4 本地 | `.cursor/hooks/redline-guard.js`（`preToolUse`，fail closed） |

> **红线是内容类别，不是单一文件名。** L2 的扫描范围**刻意宽于**上面三条
> 规范路径，因为 2026-11-28 的审计证明窄扫描会漏掉同一类内容的其他落点：
> `_archive/` 下的生产数据库副本、打包成 `.zip` 的笔记、`data/` 下的课程题库
> 都不在三条规范路径里，却同样是私有数据。
>
> L2 的四点扫描能发现「先加后删」的绕过；历史扫描能发现已入库的红线对象；
> remote-ref 扫描能发现只在非默认分支上的泄露。

**若红线对象确实需要变更**：由仓库所有者在本机带外处理，
**不要**尝试绕过或削弱任何一层强制。

---

## 2. 门禁清单（PR 必过）

```bash
node   scripts/check_module_imports.js           # 模块边界
node   scripts/check_css_architecture.js          # CSS 六层架构
node   scripts/check_layout_utility_conflicts.js  # 布局类冲突
python scripts/check_schema_consistency.py       # Schema 唯一权威
python scripts/verify_p0_cleanup.py              # legacy 收敛与路由核对
python scripts/route_inventory.py                # 路由清单
python scripts/phase2_gacha_golden.py            # 抽卡黄金快照
python -m pytest tests/characterize -q           # 行为表征
node   .cursor/infra-tests/redline-guard/harness.js  # 红线契约
```

E2E（可选，需 Chromium）：

```bash
$env:PYTHON="$PWD\.venv\Scripts\python.exe"   # 必须显式指向 venv，否则 9009
node scripts/run_e2e_isolated.js
```

> E2E 走隔离合成根，**全程不打开生产数据文件**。

**当前基线不是全绿**：截至 2026-11-27 有 4 个门禁为 RED（原因见
[`docs/CURRENT_PROJECT_STATE.md`](../docs/CURRENT_PROJECT_STATE.md) 的「已知缺口」）。
提交 PR 时请如实粘贴**实际输出**，失败时写明失败签名，不要伪造绿灯。

---

## 3. 开发环境

- Python 3.11+，Node 18+
- 依赖：`pip install -r requirements-web.txt -r requirements.txt`
- **工作目录不变量**：任何解析项目相对配置的运行时，**必须以项目根为工作目录**。
  产品默认入口是 `scripts/启动学习工具.bat` → `scripts/start_web_safe.bat` →
  `scripts/launch_server.py` → `server/backend_api.py`。
  `run_app.py` 是**验证 / 迁移入口**，不是产品默认入口。

---

## 4. 提交粒度与 tag 约定

**粒度**：一个提交 = 一个可独立回滚的意图。分批交付时按批次提交，
每批一个 tag。不要把重构与功能混进同一提交。

**格式**：`type(scope): 摘要`，type 取值：

```
feat | fix | refactor | test | docs | build | ci | chore | archive | perf | style
```

**tag 体系**（一律 **annotated**，`git tag -a`）：

| Tag | 含义 |
|---|---|
| `ar03-baseline-infra` | 基础设施与红线强制器入库 |
| `ar03-p1-architecture` … `ar03-p5-convergence` | AR03 各 P 分批交付 |
| `v0.1.0-public-fact-source` | 公开事实源冻结点 |

Tag message 必须写清**冻结了什么内容**与**对应哪些 commit**。

**不要**在 tag message、commit message、Issue 评论或文档中写入凭据。

---

## 5. Issue 规范

四类事务，四种模板，见 `.github/ISSUE_TEMPLATE/`：

| 事务 | 标题前缀 | 模板 |
|---|---|---|
| 里程碑提案 | `[M-<ID>]` | `milestone-proposal.md` |
| 想法 | `[IDEA]` | `idea.md` |
| 圆桌会议 | `[RT-<YYYYMMDD>-<nn>]` | `roundtable.md` |
| 独立验收 | `[AUDIT]` | `audit.md` |

标签体系：

| 标签 | 含义 |
|---|---|
| `type:milestone-proposal` / `type:idea` / `type:roundtable` / `type:audit` | 事务类型 |
| `stage:proposal` / `stage:approved` / `stage:shipped` | 生命周期 |
| `needs:user-decision` | 需用户拍板 |
| `redline:violation` | 红线违规（机器维护，人类不可关闭） |

**里程碑批准只能由用户在 Issue 内明确表态构成。** CI 通过、Agent 建议、
评论投票都**不构成**批准。

---

## 6. 圆桌会议

规范见 [`docs/ROUNDTABLE_PROTOCOL.md`](../docs/ROUNDTABLE_PROTOCOL.md)。
要点：

- Issue = **过程权威**；`docs/ROUNDTABLE_<date>.md` = **结论权威**；tag = 时间锚点。
- **席位 Agent 必须自己发自己的评论**，编排器不得代写评论内容。
- 席位标识用**固定席位名**，禁用 Tab 序号。
- 每条评论首行必须是固定头部，否则视为无效发言。
- 所有对 GitHub 的写操作必须记入
  [`docs/external-write-log.md`](../docs/external-write-log.md)。

---

## 7. 文档权威顺序

```
docs/CURRENT_PROJECT_STATE.md / docs/ARCHITECTURE.md   # 现状与架构
→ 当前源码与运行时证据
→ 带日期的报告 / WORK_LOG / deliverables / research / 旧 prompt
```

**不要**因为文档过时就去删除或批量改写它——它们是审计证据。
冲突时以现状权威为准，旧报告降级为历史上下文。

**不要**把会变的计数（测试数、路由数、文件数）复制进 Rules、Skills 或 README——
它们属于 `docs/CURRENT_PROJECT_STATE.md`。

---

## 8. 文档与代码冲突时

以**当前源码与运行时证据**为准。任何一方不一致时，先跑门禁复现，
再更新文档；若确实是代码缺陷，开 `[BUG]` Issue 并贴复现步骤。

---

## 9. 许可

本仓库尚未添加 LICENSE 文件（见 `docs/CURRENT_PROJECT_STATE.md` 的待决项）。
在 LICENSE 确定前，默认**保留全部权利**，不授予复制或再分发许可。
