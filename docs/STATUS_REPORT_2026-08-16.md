# 全盘状态报告 + 指导意见 — 2026-08-16 16:41

> 适用项目：`超级自动化学习工具`
> 父会话直写（基于已核实的物理事实 + 显式 bug 推论），不做"应该如此"推断。
> 本报告 = 全盘状态 + 指导意见一份合并文档。WORK_LOG.md 保留为过程日志，本报告是**快照**。
>
> 关联文档：
> - `docs/ARCHITECTURE_REDESIGN_2026-08-16.md` — 目标架构（方案 C 选定）
> - `docs/deliverables/phase-1-skeleton.md` — Phase 1 worker 交付详情
> - `docs/WORK_LOG.md` — Phase 1 worker 过程日志
> - `tests/baseline_2026-08-16.summary.txt` — 基线 36/36

---

## 0. TL;DR（一句话）

**Phase 1 已交付，物理落地，但内含 3 处 P0 隐患需立即修复；E2E 36/36 验证仍待用户新开会话跑（生成/验证分离铁律）；Phase 2-5 计划已排，但全部未启动。**

---

## 1. 已做完的事实清单

### 1.1 探查与基线

- `docs/ARCHITECTURE_REDESIGN_2026-08-16.md` 已落盘（方案 C 选定）
- `tests/baseline_2026-08-16.summary.txt` 已重写为真 36/36（原占位文件已修正）
- 支持探查 agent `def2e3a9-0bf6-49a0-bc13-676a60272c9e` 已完成（基线核对 + 桌面端调研）

### 1.2 Phase 1 主 worker（`197f648d-c454-4a7b-86e3-d27d7653395a`）已交付

**后端**（父会话 16:38 实地核实）：

| 路径 | 字节 / 行数 | 状态 |
|---|---|---|
| `server/app/__init__.py` | 404 B | ✓ |
| `server/app/app_factory.py` | 2206 B | ✓ Flask Application Factory |
| `server/app/config.py` | 2162 B | ✓ `load_config()` 读 `config/config.json` |
| `server/app/extensions.py` | 1574 B | ✓ DB 单例 + WAL 配置 |
| `server/schema/__init__.py` | 10934 B / 327 行 | ✓ 7 ensure_* + `ensure_all` 编排 |
| `server/schema/{feedback,gacha,notes,state,tasks}.py` | 712–5990 B | 占位 stub |
| `server/services/gacha.py` | 6932 B / 191 行 | ✓ `GachaAlgo` Protocol + `DefaultGachaAlgo` |
| `server/services/{ai,knowledge,schedule,timer}.py` | 192–240 B | 占位 stub |
| `server/blueprints/tasks_bp.py` | 12889 B / 368 行 | ✓ 9 endpoints |
| `server/blueprints/gacha_bp.py` | 7659 B / 251 行 | ✓ 6 endpoints |
| `server/blueprints/tags_bp.py` | 3676 B / 122 行 | ✓ 4 endpoints |
| `server/blueprints/{state,schedule,feedback,timer,knowledge,config,prompts,agent,discard}_bp.py` | 272–877 B | ⚠️ **stub re-export**（见 §3 bug 3） |
| `server/blueprints/__init__.py` | 868 B | ⚠️ **P0 隐患**（见 §3 bug 3） |
| `server/blueprints/_common.py` | 646 B | 占位 stub |
| `server/backend_api.py` | **3466 行**（实测） | ✓ 修改 — 加 12 处 TODO 注释，**未删任何代码** |

**前端**：

| 路径 | 字节 | 状态 |
|---|---|---|
| `static/app.entry.js` | 3648 B / 65 行 | ✓ 薄入口（type=module bootstrap） |
| `static/core/state.js` | 1066 B | ✓ Proxy+EventTarget 状态 |
| `static/core/constants.js` | 687 B | ✓ 共享常量 |
| `static/core/ui/modal.js` | 613 B | ✓ 模态对话框 |
| `static/core/ui/toast.js` | 649 B | ✓ 轻量提示 |
| `static/core/ui/theme.js` | 952 B | ✓ 重导出 core/theme.js |
| `static/core/ui/sandbox.js` | 1450 B | ✓ Phase 4 stub |
| `static/shared/timer.js` | 已建 | ✓ Phase 3 stub |
| `static/shared/xss.js` | 已建 | ✓ 重导出 |
| `static/shared/formatters.js` | 已建 | ✓ 时间/日期格式化 |
| `static/modules/gacha/index.js` | 已建 / 51 行 | ✓ 模块契约 |
| `static/modules/tasks/index.js` | 已建 / 32 行 | ✓ 模块契约 |
| `src/index.html` | 989 行 | ✓ 修改 — 在 `app.js?v=23` 之后追加 `<script type="module" src="/static/app.entry.js?v=1">`（行 985–986） |
| `static/app.js` | 117592 B | ✓ **未动**（2890 行原 IIFE 主导） |

**桌面端归档**：

- `_archive/src_tasks_legacy/` = **45 文件** ✓
- `src/tasks/README.md` banner ✓
- `scripts/main.py` **未改**（仍指向 `_archive`，**见 §3 bug 8**）

**自测脚本 + 交付文档**：

- `scripts/phase1_{smoke,py_check,node_check,db_check,import_check}.{py,sh}` ✓
- `scripts/phase1_{py_compile,node_check}.ps1` ✓
- `docs/deliverables/phase-1-skeleton.md` 310 行 ✓
- `docs/WORK_LOG.md` 重写为 Phase 1 worker 日志 ✓（**⚠️ 原 P3 日志丢失**）

### 1.3 物理验证结果（父会话直做）

| 检查项 | 结果 |
|---|---|
| 桌面端 `_archive/src_tasks_legacy/` 真存在 | ✅ 45 文件 |
| `static/app.entry.js` 真存在 | ✅ 3648 B |
| `src/index.html` 真加 `<script type="module">` | ✅ 行 985–986（在 `app.js` 之后） |
| `static/app.js` 仍 ~2700 行未动 | ✅ 117592 B |
| `static/core/` 5 个新核 module 全在 | ✅ |
| `server/blueprints/__init__.py` 强制 import 12 BP | ⚠️ **P0 隐患**（见 §3 bug 3） |
| `server/blueprints/state_bp.py` re-export backend_api 函数 | ⚠️ **P0 隐患**（见 §3 bug 3） |
| `server/backend_api.py` 顶部 import 新 BP？ | ❌ **不 import** — 旧入口完全独立（重要安全结论） |

---

## 2. 漏洞清单（按风险等级）

### 🔴 P0 — 立即修复（Phase 2 启动前必做）

#### bug 1：启动脚本可能破坏 schema

- **位置**：`server/app/extensions.py` 引入 WAL 但未启用 `PRAGMA foreign_keys=ON`
- **风险**：SQLite 默认不强制外键（`task_dependencies`/`timer_sessions` 等表的外键约束被忽略）→ 孤儿引用
- **缓解**：基线 DB 已存在，未立即触发；新功能写入时可能产生孤儿引用
- **修复**：在 `ensure_all(conn)` 跑前加 `conn.execute("PRAGMA foreign_keys=ON")`

#### bug 2：`create_app()` 与 backend_api.py 共用 DB 但 conn 不共享

- **位置**：`server/app/app_factory.py` 行 45–50：`get_db_connection` → `ensure_all` → `conn.close()`，**schema 跑完就关**。但 `tasks_bp.py` 行 33–39 在每次请求时**新开 conn**（`sqlite3.connect(db_path, timeout=30.0)`），无 WAL 设置、无 foreign_keys、无 row_factory
- **风险**：与 backend_api.py 旧 conn 的 PRAGMA 配置不一致 → 并发下 `SQLITE_BUSY`
- **修复**：扩展 `extensions.py` 提供 `make_request_conn()` helper，被所有 BP 复用

#### bug 3：BOMBSHELL — `server/blueprints/__init__.py` 触发 backend_api.py 二次加载

- **位置**：`server/blueprints/__init__.py` 行 11–24 显式 `from . import state_bp, schedule_bp, ..., agent_bp`；每个 stub BP 文件顶部 `from server.backend_api import ... as api_xxx`
- **触发链**：`任何代码 import server.blueprints.*` → `__init__.py` 行 11–24 触发 → 9 个 stub BP 文件模块级 `from server.backend_api import ...` 触发 → **整个 backend_api.py（3500+ 行 Flask app + 21 个 route 注册 + 全部 schema + 全部业务代码）强制加载**
- **现状**：E2E 链路只走 `python server/backend_api.py`，**没人 import server.blueprints**，所以**现状安全**
- **风险**：Phase 2 一旦有人写 `from server.blueprints import state_bp`（极常见），立刻：
  - `backend_api.py` 被 import 2 次（一次作为主入口，一次作为 stub BP 的依赖源）→ module-level `app = Flask(...)` 注册 21 route 2 次 → `View function mapping is overwriting` warning + 启动时间翻倍 + 内存 ~2 倍
  - 抽卡算法模块级副作用跑 2 次
  - 日志混乱
- **修复**：删除 `server/blueprints/__init__.py` 行 11–24 的 `from . import ...`；改为 lazy import 或移除 stub BP 文件直到 Phase 2 真要注册

### 🟡 P1 — Phase 2 启动前修复

#### bug 4：state_bp 等 stub BP 是"无 Blueprint 实例的死 re-export"

- **位置**：`server/blueprints/state_bp.py` 全文**没有任何** `Blueprint(...)` 实例或 `@state_bp.route(...)` 装饰器，只有 `__all__` 列表
- **风险**：未来 Phase 2 工人看到这个文件会**以为这是有效 BP**，实际只是死代码
- **修复**：stub BP 文件顶部加醒目 `# ⚠️ Phase 2 STUB: 无 Blueprint 实例，勿注册 ⚠️`

#### bug 5：`config.py` 默认端口硬编码 5000

- **位置**：`server/app/config.py` 行 17 `"server": {"port": 5000, "host": "0.0.0.0", "debug": True}`
- **风险**：未来 dev worker 改 backend_api.py 端口忘了同步 config.py
- **修复**：删除 `_default_config()` 中的硬编码值或加注释强制只用 json

### 🟢 P2 — Phase 3 启动前修复

#### bug 6：`static/app.entry.js` 与 `app.js` 并存，无冲突检测

- **位置**：`src/index.html` 行 985–986
- **风险**：Phase 3 modules 接管后可能与旧 app.js 全局函数冲突（如 `window.showPage`）
- **修复**：Phase 3 真接管时删 `<script src="/static/app.js?v=23">`

#### bug 7：抽卡算法 `DefaultGachaAlgo` 行为未 1:1 验证

- **位置**：`server/services/gacha.py` 191 行
- **风险**：worker §5.3 自报 `weight(plain)=0.75, weight(mismatch energy)=0.6, pick(3,[1,2,3],random)=1` —— 这是单测抽样的 1 次输出，**未与 backend_api.py 旧函数对比黄金数据集**
- **修复**：Phase 2 切流前**必须**做黄金对比测试（生成 1000 个任务 + 100 种 energy 组合，对比 weight 输出），耗时约 30 分钟

### ⚪ P3 — 长期债务

#### bug 8：`scripts/main.py` 行 4 `from src.tasks.ui.main_window import MainWindow` 必 ImportError

- **位置**：`scripts/main.py` 行 4
- **风险**：桌面端启动必 ImportError
- **现状**：**没人跑桌面端**，所以不紧急
- **修复**：在 `scripts/main.py` 顶部加 `# ⚠️ 桌面端已归档，需 PySide6 请改 from _archive.src_tasks_legacy...`

#### bug 9：`docs/WORK_LOG.md` 原 P3 日志丢失

- **位置**：worker 重写为 Phase 1 日志
- **修复**：git reflog / 备份 / 接受丢失

#### bug 10：未做 Chromium 启动回归

- **位置**：E2E 测试硬依赖 `chromium-1234` 路径
- **风险**：跨机/容器化必挂
- **修复**：读取 `process.env.PLAYWRIGHT_BROWSERS_PATH`（已是 Phase 0 已知坑）

---

## 3. 接下来必须做的事情（按 P0-P3）

### P0 — 今天必做（Phase 2 启动门槛）

1. **修复 bug 3**（BOMBSHELL）：删 `server/blueprints/__init__.py` 行 11–24 那 12 个 stub 的强制 import；或重命名为 `__init__-disabled.py` 防误用。**工作量 5 分钟**。
2. **用户新开会话跑 E2E**：`node tests/e2e-manual.js` 验证 36/36。**铁律不可违**。预计 5–15 分钟。
3. **落盘 `docs/VERIFY_REPORT_2026-08-16.md`**：E2E 跑完后由验证会话写，含 36/36 截图 + DB 表数 + src/notes 完整性。

### P1 — Phase 2 启动时必做（预计本周内）

4. **修复 bug 1+2**：扩展 `extensions.py` 提供 `make_request_conn()` helper；确保 `PRAGMA foreign_keys=ON` + `journal_mode=WAL` + `busy_timeout=30000ms` 在**每个请求 conn** 都生效。**工作量 30 分钟**。
5. **Phase 2 主 worker**（独立会话，串行）：
   - 迁移 `state_bp`（最复杂，含 11 endpoints）→ 验证 E2E → 下一个
   - 顺序：`state → schedule → feedback → timer → knowledge → config → prompts → agent → discard`
   - 抽卡算法切流：删 backend_api.py 的 `_calculate_*` + 调 `DefaultGachaAlgo().compute_weight()`
   - schema 切流：删 backend_api.py 7 个 `ensure_*` + 改 `if __name__ == '__main__'` 入口用 `ensure_all(conn)`
6. **删 backend_api.py 全部 `@app.route`**：只在 `if __name__ == '__main__'` 留 `create_app().run()` 启动行。

### P2 — Phase 3 启动时必做（下周内）

7. **Phase 3 主 worker**（独立会话）：
   - 拆 5 个模块：`schedule / sleep-state / knowledge / config / timer-dock`
   - 双计时器合并：`timerDockSession + timerActiveSession` → `shared/timer.get()` 单一 store
   - characterization test 先冻行为
   - `scripts/check_module_imports.js` 模块边界检查
8. **修复 bug 7**：抽卡算法黄金对比测试（必做）。

### P3 — 长期收尾

9. **Phase 4**：CSS 拆分 + OpenClaw sandbox 接入
10. **Phase 5**：backend_api.py → legacy.py（re-export create_app 默认实例）；scripts/ 一次性脚本归档；schema 一致性脚本
11. **最终交付报告**：`docs/delivery-report.md` + `docs/VERIFY_REPORT_<date>.md`
12. **修复 bug 6+8+10**

---

## 4. 给用户的指导意见

### 4.1 我的建议：先把 P0 全清掉再开 Phase 2

**不要立刻派 Phase 2 主 worker**。原因是 bug 3（BOMBSHELL）：一旦 Phase 2 工人写 `from server.blueprints import state_bp` 这种**必然的正常 import**，立刻会触发 backend_api.py 二次加载。即使 Phase 2 工人自己测 OK，未来维护者早晚被坑。

**推荐路径**：

1. **你**（人类用户）在 IDE 里手动删 `server/blueprints/__init__.py` 行 11–24 那 12 个 stub 的强制 import（**5 分钟**）；或派一个**纯写、不跑**的 fix worker 做这事
2. **你**开新会话跑 `node tests/e2e-manual.js`（5–15 分钟）—— 验证 36/36
3. **你**落盘 `docs/VERIFY_REPORT_2026-08-16.md`
4. **你**新开会话派 Phase 2 worker（参考 `docs/deliverables/phase-1-skeleton.md` §7 + 本报告 §3 P1）

### 4.2 不建议立刻做的事

- ❌ **不要**让一个 worker 同时改 backend_api.py + app.js + schema/ + 多个 BP。文件锁仍未完全解开（backend_api.py 21 个 `@app.route` 还在）。
- ❌ **不要**跳过独立验证会话直接让 dev worker 自报 E2E 全绿（生成/验证分离铁律）。
- ❌ **不要**让 Phase 2 工人继续走 `from server.backend_api import ...` re-export 模式（bug 4）。

### 4.3 乐观 vs 悲观工时估计

| 项 | 乐观 | 悲观 |
|---|---|---|
| Phase 2 主 worker | 4h | 8h |
| 抽卡算法切流验证 | 30 min | 2h |
| Phase 3 主 worker | 6h | 12h |
| **总剩余工时** | **~10–15h** | **~25–30h** |

### 4.4 给 Phase 2 主 worker 的 prompt 草案（参考）

```text
你是 Phase 2 唯一主 worker。
工作路径：d:\Axelit\.工作\trae\超级自动化学习工具\

【前置必读】
- docs/STATUS_REPORT_2026-08-16.md（本报告）— 必读 §2 漏洞清单 + §3 P0/P1 必做
- docs/deliverables/phase-1-skeleton.md §7 — Phase 1 worker 给 Phase 2 的建议
- docs/VERIFY_REPORT_2026-08-16.md — 用户已跑 36/36 E2E（基线确认）

【硬约束】
1. 不要 import server.blueprints.* — bug 3 BOMBSHELL 仍未清；只 import server.blueprints.<具体 BP 名>（且该 BP 已 migrate）
2. 不要碰 static/app.js — Phase 3 范围
3. 不要重写 DefaultGachaAlgo 权重公式 — 必须 1:1 等价
4. 不要 Start-Process 启后端 — 第一版 worker 死因
5. python 路径：C:\Users\wn\AppData\Local\Programs\Python\Python312\python.exe

【Phase 2 任务】
- 9 个 BP 顺序迁移：state → schedule → feedback → timer → knowledge → config → prompts → agent → discard
- 抽卡算法切流：DefaultGachaAlgo().compute_weight() 替代 backend_api.py 旧 _calculate_*
- schema 切流：删 backend_api.py 7 个 ensure_* + __main__ 入口用 ensure_all(conn)
- 删 backend_api.py 全部 @app.route，仅留 create_app().run()

【自测】
- python -m py_compile <file> 验语法
- python -c "from server.app import create_app; create_app()" 不抛异常
- node --check <file> 验 JS 语法
- 不跑 E2E（验证分离铁律）

【三连败即停】
- 连续失败 3 次 → 立刻停手，写 WORK_LOG.md 记录根因，回报父会话

【输出】
- 改动文件清单（路径 + 增/改/删行数）
- 9 个 BP 迁移后 url_map 计数
- 抽卡算法黄金对比测试结果
- 未做完的已知项
- 红线验证（grep src/notes/ 0 命中 + DB 表数 ≥ baseline）
```

---

## 5. 红线证据

| 红线 | 状态 | 证据 |
|---|---|---|
| `src/notes/` 永不动 | ✅ | `find src/notes -type f \| wc -l` = 2046（worker §8.1） |
| `data/task_publisher.db` 不破坏 | ✅ | 20 张表 ≥ baseline（worker §8.2） |
| 零构建（无 npm install / 无新 pip 依赖） | ✅ | worker §8.3 |
| python 路径硬约束 | ✅ | worker §8.4（始终走 .venv/Scripts/python.exe） |
| 生成/验证分离 | ✅ | worker **未**自跑 E2E；待用户新会话验证 |

---

## 6. 一句话总结

**Phase 1 物理落地，但留了 1 个 BOMBSHELL（bug 3：`blueprints/__init__.py` 触发 backend_api.py 二次加载）+ 2 个 P1 schema 连接隐患 + 1 个 P0 验证缺口（用户新会话跑 E2E）。在用户跑完 E2E 之前，phase1-verify todo 不能 close，Phase 2 不能启动。**

---

**报告完毕。等待用户决策下一步（建议先手动清 bug 3 BOMBSHELL + 开新会话跑 E2E）。**