# P1 独立验收证据包（AR03-P2 / Stage 0）

> **目的**：把 P1 的安全违规修复与复验结果整理成 **可独立审阅、可会签** 的证据包。
> **执行方**：AR03-P2 Cursor Agent（单一会话串行执行）
> **日期**：2026-11-21
> **门禁作用**：本证据包 + 会签签字到位，是 AR03-P2 实质迁移（Stage 1 起）的
> **硬前置**。签字未到位时，P2 实质迁移 **不得启动**。

---

## 1. 待验收项（逐条对照任务书 §4.1）

任务书对 E2E 隔离验证器提出四项禁止：

| # | 禁止项 | 本次处置 | 证据位置 |
|---|---|---|---|
| 1 | 不得继续用 **读取生产文件** 的方式证明文件没有变化 | `fingerprintFile()` / `fingerprintTree()` 已从 `scripts/run_e2e_isolated.js` **完全删除**；改为 Node fs 守卫事前阻断 | §2.1 / §3.1 / §4.3 |
| 2 | 不得通过 **重新计算生产文件哈希** 验证隔离 | runner 源码中已无 `createHash('sha256')`，无任何 `sha256` 计算 | §2.1 / §4.3 |
| 3 | 不得通过 **读取真实数据库** 的方式生成测试 fixture | 合成 fixture 由 `tests/characterize/sandbox_env.py::seed()` 在 **合成根** 内建库生成；审计证明 server 的 3 次 `sqlite3.connect` 全部指向合成根 | §3.2 |
| 4 | 必须从 **测试环境构造方式、路径隔离与运行约束本身** 证明只访问合成环境 | 三重机制：路径守卫（运行约束）+ 进程内审计（运行期观测）+ 启动自检（构造方式），全部 **不打开生产文件** | §2.1 / §3.1 / §3.3 |

**另需确认的边界**：项目最高数据保护要求「不读取、不写入、不复制、不哈希、
不恢复真实生产 SQLite 及其 WAL/SHM」。

---

## 2. 修复前后的机制对比

### 2.1 修复前（违规）

```
runner ──fs.readFileSync()──► 生产 data/task_publisher.db{,-wal,-shm}
       ──fs.readFileSync()──► 生产 config/config.json
       ──fs.readFileSync()──► 生产 src/notes/**（递归）
       └──► 计算 SHA-256，前后比对是否一致
```

证明手段与被保护对象冲突：**读取本身就是违规**。

### 2.2 修复后（三重证明，全程不打开生产文件）

```
┌─ runner ────────────────────────────────────────────────┐
│ A. 事前阻断                                             │
│    scripts/guard/protected_paths_guard.js               │
│    fs.readFileSync / openSync / createReadStream /      │
│    readdirSync / readlinkSync / realpathSync /          │
│    fs.promises.{readFile,open,readdir}                  │
│    → data/**、config/**、src/notes/**  ⇒ 立即抛错        │
│                                                        │
│ B. 事中记录（合成服务器进程内）                          │
│    tests/e2e/synthetic_audit.py                         │
│    sys.addaudithook ⇒ 记录 sqlite3.connect / open /    │
│    os.listdir / os.scandir / os.stat 的真实目标路径      │
│                                                        │
│ C. fail closed（启动前）                                │
│    tests/e2e/synthetic_root_selfcheck.py                │
│    合成根 ≠ 真实根、互不包含、db/notes/config 全在合成根 │
│    ⇒ 任一不成立即拒绝启动                                │
└────────────────────────────────────────────────────────┘
```

**关键**：runner **不再对生产路径发起任何 fs 调用**。隔离性由守卫、审计、
自检证明，而不是由"读取后比对"证明。

---

## 3. 三重机制的运行期证据

### 3.1 A. Node fs 守卫

- 安装位置：`scripts/run_e2e_isolated.js` 启动时（`GUARD.install({ projectRoot })`）。
- 自检输出：`[isolation-guard] 自检通过：受保护路径全部拦截，合法路径全部放行`（退出码 0）。
- 自检内容：5 条受保护路径必须被拦截、3 条合法路径必须放行、**真实触发一次**确认确实抛 `SAL_ISOLATION_VIOLATION`。
- 隔离 E2E 运行输出：`✅ 生产数据 fs 守卫全程未被触发（未读取任何生产文件）`。

### 3.2 B. Python 进程内审计

- 安装位置：合成服务器子进程（`tests/e2e/_sandbox_bootstrap.py`）启动前。
- 独立探测结果（合成根内）：

```
审计记录数 = 351（启动探测） / 3478（完整 E2E 运行）
protected_violations = 0
sqlite_outside_synthetic = 0
sqlite3.connect 样本（全部在合成根内）：
  ...\Temp\lt_m14a_...\root\data\synthetic.sqlite3
  ...\Temp\lt_m14a_...\root\data\synthetic.sqlite3
  ...\Temp\lt_m14a_...\root\data\synthetic.sqlite3
```

### 3.3 C. 合成根启动自检

- 安装位置：`tests/e2e/factory-sandbox-server.py` spawn 子进程 **之前**。
- 断言项：合成根 ≠ 真实项目根；两者互不包含；`db_path` / `notes_dir` /
  `config_path` 全部落在合成根内；合成根不指向真实受保护目录。

---

## 4. 机械守卫（防止回退）

### 4.1 新增文件

| 文件 | 行数级 | 作用 |
|---|---|---|
| `scripts/guard/protected_paths_guard.js` | ~240 | Node 侧事前阻断守卫 + `--self-test` |
| `tests/e2e/synthetic_audit.py` | ~180 | 合成服务器进程内访问审计 |
| `tests/e2e/synthetic_root_selfcheck.py` | ~150 | 合成根启动自检（fail closed） |
| `tests/characterize/test_e2e_isolation_guard.py` | ~280 | 17 项隔离机制契约 |

### 4.2 改造文件

| 文件 | 改动 |
|---|---|
| `scripts/run_e2e_isolated.js` | **重写**：删除 `crypto` / `fingerprintFile` / `fingerprintTree` / `snapshotProtected` / `diffProtected`；接入守卫 + 审计断言 |
| `tests/e2e/factory-sandbox-server.py` | 新增 `_install_synthetic_bootstrap()` / `_child_env()` / `_self_check()`；子进程入口改为 `_sandbox_bootstrap.py` |

### 4.3 契约测试覆盖（17 项，全绿）

```
IsolationGuardContractTests
  · guard 模块存在且导出 install/isProtected/describe
  · guard 自检子进程退出码 0
  · 每条受保护路径都被拦截、每条合法路径都放行（node 探针）
IsolationRunnerContractTests
  · runner 不含 readFileSync(生产路径拼接) / createHash('sha256') / fingerprintFile / fingerprintTree
  · runner 安装守卫
  · runner 断言 protected_violations 与 sqlite_outside_synthetic
  · runner 的审计清单路径由合成根拼出
SyntheticAuditContractTests
  · 审计模块语法有效
  · 记录 sqlite3.connect 与文件访问
  · 受保护路径判定函数对真实 data/ config/ src/notes 全部命中，对普通源码路径不命中
SyntheticRootSelfCheckContractTests
  · 真实项目根被拒绝
  · 嵌套根被拒绝
  · 越界路径被拒绝
  · 规范合成根被接受
SandboxServerWiringTests
  · 合成服务器语法有效
  · 安装 bootstrap 与自检
  · 传递审计环境变量
```

---

## 5. 复验执行记录

全部在合成环境执行；生产 DB / WAL / SHM / Vault / config 零读取零写入零哈希零复制。

| # | 命令 | 结果 | 退出码 |
|---|---|---|---|
| 1 | `node scripts/guard/protected_paths_guard.js --self-test` | 自检通过 | 0 |
| 2 | `node scripts/check_module_imports.js` | 模块边界无违规 | 0 |
| 3 | `.\.venv\Scripts\python.exe scripts/phase2_gacha_golden.py` | `pass=100250 fail=0 max_diff=0.000e+00` → `RESULT: OK` | 0 |
| 4 | `.\.venv\Scripts\python.exe -m pytest tests/characterize/test_schema_authority.py test_factory_bootstrap.py test_legacy_route_full_parity.py test_gacha_service_boundary.py test_kernel_contract.py test_desktop_archive_integrity.py -q` | **78 passed, 47 subtests passed** | 0 |
| 5 | `.\.venv\Scripts\python.exe -m pytest tests/characterize/test_e2e_isolation_guard.py -q` | **17 passed** | 0 |
| 6 | `.\.venv\Scripts\python.exe -m pytest tests/characterize -q` | **1370 passed, 10 skipped, 1 xfailed, 441 subtests passed**（P1 基线 1353 + 新增 17；0 failed） | 0 |
| 7 | `$env:PYTHON="$PWD\.venv\Scripts\python.exe"; node scripts/run_e2e_isolated.js` | `36 通过, 0 失败`；`审计记录数 = 3478`；`✅ 合成服务器未触碰任何生产受保护路径`；`✅ 生产数据 fs 守卫全程未被触发` | 0 |

### 5.1 与 P1 基线的对照

| 项 | P1 交付基线 | 本次复验 | 差异说明 |
|---|---|---|---|
| 全量 characterization | 1353 passed / 0 failed | **1370 passed / 0 failed** | +17 = 新增隔离契约 |
| P1 专项 6 文件 | 78 passed / 47 subtests | **78 passed / 47 subtests** | 一致 |
| Gacha Golden | 100250 / max_diff 0 | **100250 / max_diff 0** | 一致 |
| 36/36 E2E | 36/36（哈希比对证明） | **36/36（守卫 + 审计 + 自检证明）** | 证明方式升级，结论不变 |
| 模块边界 | 退出码 0 | **退出码 0** | 一致 |

---

## 6. P1 纠错事项的处置（与本证据包一并会签）

| 项 | 处置 | 位置 |
|---|---|---|
| E2E 隔离器生产数据库读取 | ✅ 已修复 + 17 项机械守卫 | 本文件 §1–§4 |
| `SAL_ENFORCE_AGENT_POLICY` 启动安全状态表述 | ✅ 已纠错（官方启动链 **强制开启** 服务端闸门；Factory 默认关闭仅在绕过启动器时成立） | `docs/P1_ADDENDUM_20261121.md` §2 |
| Schema「14 + 1」归属 | ✅ 已澄清（14 张集中 Schema 表 + 1 张 `FreeTaskEventStore` 自管表） | `docs/P1_ADDENDUM_20261121.md` §3 |
| Gacha 权重方向语义歧义 | ⏳ **保留为待用户裁决事项**（保留现有实际行为，不改算法，不改 Golden） | `docs/P1_ADDENDUM_20261121.md` §4 |

---

## 7. 会签清单

> 请独立会话的执行者在核对上述证据后勾选并签署。

### 7.1 审查项

- [ ] **7.1.1** 确认 `scripts/run_e2e_isolated.js` 不再读取 / 哈希生产 DB、WAL/SHM、config、Vault
- [ ] **7.1.2** 确认守卫（`scripts/guard/protected_paths_guard.js`）能阻断全部受保护路径且不误伤合法路径
- [ ] **7.1.3** 确认审计（`tests/e2e/synthetic_audit.py`）在合成服务器进程内真实生效，且违规判定逻辑正确
- [ ] **7.1.4** 确认自检（`tests/e2e/synthetic_root_selfcheck.py`）在不合规时 fail closed（拒绝启动）
- [ ] **7.1.5** 确认合成服务器确实经由 `_sandbox_bootstrap.py` 启动，审计钩子在 `run_app.py` 之前安装
- [ ] **7.1.6** 确认 `tests/characterize/test_e2e_isolation_guard.py` 的 17 项契约能阻止后续重构把隔离方式改回"读生产文件比对哈希"
- [ ] **7.1.7** 确认 §5 的 7 条复验命令可在独立会话中复现相同结果
- [ ] **7.1.8** 确认 `docs/P1_ADDENDUM_20261121.md` 的三项纠错表述与代码事实一致
- [ ] **7.1.9** 确认未发生任何未经授权的 Git 破坏性操作（无 reset / clean / stash / checkout / switch / commit / push）

### 7.2 结论

- [ ] **P1 独立验收通过** —— 允许 AR03-P2 启动 Stage 1（实质迁移）
- [ ] **P1 独立验收不通过** —— 需返工项：______________________________

### 7.3 签署

| 项 | 内容 |
|---|---|
| 会签人 | ______________________________ |
| 角色 | 主控 / 副 Controller（独立会话） |
| 日期 | ______________________________ |
| 会话 / Conversation ID | ______________________________ |
| 备注 | ______________________________ |

---

## 8. 门禁状态

| 状态 | 含义 |
|---|---|
| `READY_FOR_INDEPENDENT_ACCEPTANCE` | **当前状态** —— 修复完成、自审完成、复验全绿、证据包已备齐；等待外部会签 |
| `ACCEPTED` | 会签完成 —— AR03-P2 可启动 Stage 1 |
| `REWORK_REQUIRED` | 会签不通过 —— 按 §7.1 的返工项修复后重新提交 |

**在 `ACCEPTED` 之前，AR03-P2 的实质迁移（Stage 1 起）不得启动。**
