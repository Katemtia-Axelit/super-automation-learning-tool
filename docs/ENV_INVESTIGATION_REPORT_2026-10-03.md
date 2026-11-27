# BUILD / RUN / TEST REPORT

> 本报告为只读工程环境调查结果。
> 仓库路径：`D:\Axelit\.工作\trae\超级自动化学习工具`
> 调查日期：2026-10-03
> 所有结论均附文件路径；推断项标注「静态推断」。

---

## 1. Development Environment

### 1.1 主要语言与运行时

| 维度 | 结论 | 证据 |
|------|------|------|
| 主语言（后端） | Python（≥3.10 推荐；脚本中检查 `py -3` 与 `Python 3.10+`） | `scripts/start_web_safe.bat:60`、`scripts/verify_transferred_project.bat:48` |
| 主语言（前端） | JavaScript（ES2020+，浏览器原生 + ES Modules） | `static/app.entry.js`（`type=module`）、`src/index.html` |
| 标记语言 | HTML5 + 内联 CSS + 外部 woff2 字体 | `src/index.html`（`@font-face`、`@keyframes` 内联） |
| 数据交换 | JSON（API）+ SQLite（持久化） | `server/backend_api.py`、`config/config.json` |

> 本机已知坑（AGENTS.md §9）：Windows 系统 `python`/`python3` 是 WindowsApps stub（exit 9009），开发机应使用 `.venv\Scripts\python.exe`（Python 3.12.6 已装）。

### 1.2 后端栈（Flask 单体应用）

| 组件 | 用途 | 证据 |
|------|------|------|
| Flask（`flask>=2.0`） | Web 框架 / 路由 | `requirements.txt:1`、`server/backend_api.py:1` |
| flask-cors | 跨域 | `requirements.txt:2`、`server/backend_api.py:2` |
| sqlite3（标准库） | 数据库 | `server/backend_api.py:3` |
| Python 标准库（`json`/`re`/`enum`/`math`/`random`/`datetime`） | 业务工具 | `server/backend_api.py:4-11` |
| PySide6（≥6.5.0）— **仅桌面端归档使用** | 已被归档（`scripts/main.py` 当前 import 失败） | `requirements.txt:3`、`scripts/main.py:23` |

> 关键事实：**PySide6 桌面端在 2026-08-16 已被归档至 `_archive/src_tasks_legacy/`，主用入口是 Web。**
> 详见 `src/tasks/README.md`、`scripts/main.py` 顶部警告。

### 1.3 前端栈（无构建步骤）

- 直接在浏览器加载 ES2020+ 原生 JS；无 webpack/vite/rollup。
- 模块化通过 `type="module"` 与 `static/core/*` + `static/modules/*` + `static/shared/*` 拆分。
- 主题/字体：**vendor 完全本地化**（`static/vendor/fonts/*.woff2`、`static/vendor/marked.min.js`、`static/vendor/fontawesome/all.min.css`）。
- 来源证据：`src/index.html:21-32`（字体声明）、`.gitignore:57-60`（`static/vendor/*` 例外保留 `marked.min.js`）。

### 1.4 数据库

- **SQLite**（文件 `data/task_publisher.db`，相对路径）
- 启用 **WAL journal** + 30 秒 `busy_timeout` + 单 BP 全局 `foreign_keys=ON`
- 证据：`server/app/extensions.py:14,30,65-92`、`server/extensions.py:90`

### 1.5 测试运行时（E2E）

| 工具 | 版本 | 证据 |
|------|------|------|
| Node.js | ≥20（来自 playwright 引擎要求） | `package-lock.json:25`（`@playwright/test` engines: `node >=20`） |
| Playwright | `1.62.1` | `package.json:5`、`package-lock.json:5` |
| Chromium | 本地固定路径（playwright-core headless） | `tests/e2e-manual.js:9`、`tests/e2e/playwright.config.js:13` |

### 1.6 工具链

- 启动脚本：Windows `.bat` + `.py` 双轨
- 启停管理：`.run/server.pid` + `.run/server.log`
- PowerShell 强制走 PS7（`D:\Axelit\software\PowerShell-7.6.5-win-x64\pwsh.exe`）— 由 `~/.cursor/hooks.json` + `force-pwsh.js` 硬约束
- 证据：`AGENTS.md` §10（硬执行层 hook 说明）

---

## 2. Dependencies

### 2.1 Python 依赖（`requirements*.txt`）

| 文件 | 内容 |
|------|------|
| `requirements.txt`（全量，**含已归档的桌面端**） | `flask>=2.0`、`flask-cors`、`PySide6>=6.5.0` |
| `requirements-web.txt`（**Web 主入口真正用到**） | `flask>=2.0`、`flask-cors` |

> ⚠️ **新建开发者易踩坑**：直接 `pip install -r requirements.txt` 会拉 PySide6（~150MB）。
> `scripts/start_web_safe.bat:75` 使用的是 **`requirements-web.txt`**，不是 `requirements.txt`。

### 2.2 Node 依赖（仅 E2E 用）

```json
// package.json
{
  "devDependencies": {
    "@playwright/test": "^1.62.1",
    "playwright": "^1.62.1"
  }
}
```

> `package.json` 与 `package-lock.json` 仅声明两个 devDependency，**没有构建/打包依赖**。

### 2.3 数据来源/资产

| 资产 | 来源 | 处理 |
|------|------|------|
| 自托管字体（`Cinzel`/`Cormorant Garamond`） | Google Fonts（CN 域名） | `scripts/download_vendor.py` 一次性下载至 `static/vendor/fonts/` |
| FontAwesome CSS | FontAwesome | 本地化至 `static/vendor/fontawesome/` |
| `marked.min.js` | marked.js | 本地化（`.gitignore` 显式保留） |

### 2.4 关键事实

- **无 submodules**（无 `.gitmodules`、无 vendor SDK、无 CGo）。
- **无 Rust/Go/Java/C++ 组件**。
- **无 `pyproject.toml` / `setup.py` / `setup.cfg` / `Makefile` / `CMakeLists.txt`**。

---

## 3. Build Procedure

### 3.1 构建入口

**本项目没有「构建」步骤。** 后端是纯 Python（Flask 直接 run）；前端是浏览器加载（无打包器、无 transpiler、无 typecheck）。

### 3.2 「构建」实际做的事

后端 Web 主入口只做 4 件事（按 `server/backend_api.py:3533-3571` 推断）：
1. 加载 `config/config.json`
2. 注册 Phase 2 蓝图（state / schedule / timer / feedback / knowledge）—— 5 个 `app.register_blueprint(...)`
3. 跑 schema 迁移函数（task_dependency / schedule / timer / assessment / daily_state / task_feedback_events / indexes）
4. `app.run(host, port, debug)`

### 3.3 构建命令

| 路径 | 命令 | 证据 |
|------|------|------|
| 启动 venv | `py -3 -m venv .venv` | `scripts/start_web_safe.bat:27` |
| 安装依赖（Web 入口） | `.venv\Scripts\python.exe -m pip install -r requirements-web.txt` | `scripts/start_web_safe.bat:75` |
| 启动服务 | `.venv\Scripts\python.exe server\backend_api.py` | `scripts/launch_server.py:20` |
| Phase 2 验证入口（替代 backend_api.py） | `.venv\Scripts\python.exe run_app.py` | `run_app.py:30`、`scripts/start_learn_phase2.bat:7` |

> ⚠️ **Phase 2 的两条入口**（`backend_api.py` 仍可启动；`run_app.py` 通过 `server.app.create_app()` 装配所有 8 个 BP）。两者并存：legacy 兼容 vs 工厂版。`server/app/app_factory.py:9-17` 显式说明。

### 3.4 构建配置

无 `Debug`/`Release` 等模式区分。`config/config.json` 中：
```json
"server": { "port": 5000, "host": "0.0.0.0", "debug": false }
```
（`.env` 文件被 `.gitignore:6` 忽略，**项目当前不读取 `.env`**，所有配置走 `config/config.json`）

### 3.5 输出位置

| 产出 | 路径 |
|------|------|
| SQLite 数据库 | `data/task_publisher.db` |
| 服务运行日志 | `.run/server.log` |
| PID 文件 | `.run/server.pid` |
| 备份目录 | `backups\<时间戳>\` |

### 3.6 环境变量

| 变量 | 用途 | 证据 |
|------|------|------|
| `PYTHONPATH` | `scripts/start_learn_phase2.bat:6` 设置为 `%CD%`（让 `from server.app` 可解析） |
| `FLASK_DEBUG=0` | `scripts/start_learn_phase2.bat:7` 显式设置 |

> **静态推断**：未发现读取环境变量 `OPENAI_API_KEY`/`CLAUDE_API_KEY` 的代码——所有密钥字段仅来自 `config/config.json` 的 `api.*` 段（**`config/config.json` 在 `.gitignore:2`，不会被提交**）。

---

## 4. Run Procedure

### 4.1 启动方式（推荐顺序）

#### 方式 A：一键启动（推荐新开发者）

```bat
双击 scripts\启动学习工具.bat
```
该脚本：
1. 切换 UTF-8 代码页（`chcp 65001`）
2. 自动定位 Python（`.venv` → `py -3` → `python`）
3. 若无 `.venv`，用 `py -3 -m venv .venv` 创建
4. `.venv\Scripts\python.exe -m pip install -r requirements-web.txt`（默认源失败回退清华镜像）
5. 杀掉旧 PID（`scripts\stop_web_safe.bat`）
6. 启动 `scripts\launch_server.py` → 拉起 `server/backend_api.py`
7. 等待 `GET /api/health` 通过（最多 15 秒）
8. `start http://127.0.0.1:5000/`

证据：`scripts/启动学习工具.bat:1-3`、`scripts/start_web_safe.bat:9-130`。

#### 方式 B：手动启动

```bat
.\.venv\Scripts\python.exe server\backend_api.py
```
然后浏览器访问 `http://127.0.0.1:5000/`。

#### 方式 C：Phase 2 验证入口（使用 application factory）

```bat
.\.venv\Scripts\python.exe run_app.py
```
证据：`run_app.py:23-33`、`scripts/start_learn_phase2.bat`。

### 4.2 端口 / Host

- 默认端口：**5000**（`config/config.json:2`、`server/backend_api.py:30`）
- 默认 host：**0.0.0.0**（`server/backend_api.py:30`）

### 4.3 停止

```bat
双击 scripts\stop_web_safe.bat
# 或：.venv\Scripts\python.exe scripts\stop_server.py
```
`scripts/stop_server.py:30-40` 实现：读 `.run/server.pid` → `taskkill /PID` → 清掉 5000 端口的所有监听进程（防旧实例残留）。

### 4.4 启动哪个程序？

- 主入口：Flask app at `server/backend_api.py`
- 入口路由：`GET /` → `src/index.html`（后端单页面 SPA，导航靠客户端 JS）
- API：`/api/health`、`/api/tasks*`、`/api/gacha/*`、`/api/timer/*`、`/api/state/*`、`/api/schedule/*`、`/api/feedback`、`/api/knowledge/*`、`/api/prompts/*`、`/api/config/*`、`/api/agent/*`、`/api/tags/*`、`/api/discard-pile/*`、`/api/dependencies`、`/api/export`

### 4.5 是否需要其他服务？

| 服务 | 是否必需 | 说明 |
|------|---------|------|
| SQLite | 必需（嵌入式，无进程） | `data/task_publisher.db` |
| Obsidian | **非必需**（仅前端「在 Obsidian 中打开」按钮调用） | 通过 `POST /api/knowledge/open-in-obsidian` 触发本地 URI |
| OpenAI / Claude API | **非必需**（密钥留空也不阻塞） | `config/api.*` 字段 |
| 硬件 | 无（本地 Web 应用） | — |
| 网络（出站） | 仅在调用 AI 时（可选） | — |

### 4.6 数据库依赖

- 路径相对项目根：`data/task_publisher.db`
- 首次启动自动迁移：`server/backend_api.py:3563-3569` 调用 `ensure_*_schema` 系列
- schema 定义位于：`server/schema/{tasks,gacha,state,schedule,feedback,notes,__init__}.py`

### 4.7 健康检查

```bat
curl http://127.0.0.1:5000/api/health
# 期望：{"phase": 1, "status": "ok"}（legacy backend_api.py 也返回 ok）
```
证据：`server/app/app_factory.py:62-64`、旧 backend_api.py 中相同端点。

---

## 5. Configuration

### 5.1 主配置文件：`config/config.json`（**`.gitignore` 忽略**）

```json
{
  "server":   { "port": 5000, "host": "0.0.0.0", "debug": false },
  "obsidian": { "vault_path": "src/notes/vault", "notes_directory": "src/notes/vault" },
  "api": {
    "openai_api_key": "",       // 留空
    "claude_api_key": "",       // 留空
    "api_base": "https://api.openai.com/v1",
    "model": "gpt-4o-mini"
  },
  "database": { "task_db_path": "data/task_publisher.db" }
}
```

### 5.2 示例配置：`config/config.example.json`

（**未在 `.gitignore` 中忽略**——纯模板，新开发者复制并改名为 `config.json`）

### 5.3 配置加载逻辑

| 路径 | 函数 | 行为 |
|------|------|------|
| `server/backend_api.py:21` | `load_config()`（行内定义） | 缺文件则用默认 dict；这是 **legacy 入口** 用的 |
| `server/app/config.py:35` | `load_config()` | Phase 1/2 工厂入口；同样支持默认值回退；返回 dict 含 `_project_root`/`_static_dir`/`_db_path`/`_notes_dir` |

> **关键差异**：两个 `load_config()` 行为差异极小，但 `server/app/config.py` 返回的是带绝对路径的 dict，更安全。

### 5.4 Secrets 占位

- `config/config.json` 的 `api.openai_api_key`、`api.claude_api_key` 是 secrets 字段。
- **本仓库当前没有真实密钥**（仅空字符串 + 默认 `gpt-4o-mini` 模型）。
- `opencode.json`（**也被 `.gitignore:3` 忽略**）存放外部 AI 协作的 API key 配置——本报告**不**记录其内容。

### 5.5 数据库 schema 配置

- `data/task_publisher.db` 是用户数据，**`.gitignore:25-27` 显式忽略**。
- 自动迁移函数位置：`server/backend_api.py:3563-3569`。

### 5.6 不读以下配置形式

- ❌ 无 `.env` 文件读取（虽然 `.gitignore` 忽略 `.env`，但代码未使用 `dotenv`/`os.getenv`）
- ❌ 无 `yaml`/`toml` 解析
- ❌ 无 `compile-time defines` / 宏 / board config（这是 Python/JS 项目）
- ❌ 无 `submodule`

---

## 6. Tests

### 6.1 测试结构

| 路径 | 类型 | 框架 | 入口 | 状态 |
|------|------|------|------|------|
| `tests/e2e-manual.js` | E2E | `playwright-core`（直接 API，绕开 headless-shell） | `node tests\e2e-manual.js` | 26 用例（README 写 36 案，**有出入——见 §11**） |
| `tests/e2e.spec.js` | E2E | `@playwright/test`（官方 Test runner） | `npx playwright test --config=tests\e2e\playwright.config.js` | 与 `e2e-manual.js` 同源，简化版 |
| `tests/e2e/playwright.config.js` | 配置 | — | — | baseURL=127.0.0.1:5000、chromium、headless、executablePath 硬编码 |

### 6.2 测试前置

- **后端必须在 5000 端口跑起来**（`tests/e2e-manual.js:8` 硬编码 `BASE_URL = 'http://127.0.0.1:5000'`）
- **Chromium 路径必须存在**（`C:\Users\wn\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe`）— 用户名硬编码，**迁移到新用户需修改**
- **Node ≥20**

### 6.3 单元测试 / 集成测试 / 仿真测试 / 硬件测试 / Benchmark

| 类型 | 存在？ | 备注 |
|------|--------|------|
| 单元测试 | ❌（无 pytest 框架、无 tests/test_*.py） | — |
| 集成测试 | ⚠️ 部分（`scripts/test_api_endpoints.py`、`scripts/test_*.py` 散落） | 这些是**手动验证脚本**而非 CI 套件；AGENTS §7 规定禁止 self-E2E-passing |
| E2E | ✅（见 6.1） | 26 用例覆盖：抽卡、任务、计时、日程、知识库、设置、XSS 回归、P0 回归 |
| 仿真测试 | ❌ | — |
| 硬件测试 | ❌ | — |
| Benchmark | ❌ | — |

### 6.4 自动化回归机制

- 大量 `tests/_run*.log`、`tests/_e2e_gacha_run*.log` 是历史运行产物（非测试源码）。
- `scripts/verify_todo5.bat`、`scripts/run_stable_acceptance.bat`、`scripts/_run_verify*.ps1` 是历史验收脚本。
- **没有 CI 触发**（无 `.github/`、无 `.gitlab-ci.yml`、无 Jenkinsfile）。

### 6.5 已知测试风险

- AGENTS.md §3：E2E 是「单浏览器测不出 SQLite 并发、大数据量、跨浏览器」
- README §E2E 提到「26 用例全绿（2026-08-05 R3）」，但 AGENTS/CHANGELOG 提到「36/36」— **数字冲突待验证**

---

## 7. CI/CD

### 7.1 调查结果

| 类型 | 结论 | 证据 |
|------|------|------|
| GitHub Actions | ❌ 无（无 `.github/workflows/`） | Glob 返回 0 |
| GitLab CI | ❌ 无（无 `.gitlab-ci.yml`） | Glob 返回 0 |
| Jenkins | ❌ 无（无 `Jenkinsfile`） | Glob 返回 0 |
| Docker | ❌ 无（无 `Dockerfile`、`docker-compose.yml`） | Glob 返回 0 |
| 包管理配置 | ❌ 无 `pyproject.toml`/`setup.py`/`setup.cfg`/`Makefile`/`CMakeLists.txt` | Glob 返回 0 |
| Git submodules | ❌ 无 `.gitmodules` | — |

### 7.2 「自动化」实际形态

- **脚本驱动**——`scripts/` 下 60+ 个 `.bat` + `.py`，由开发者手动或交互式触发。
- **没有自动化部署/发布流水线**。
- 启停链路是手动的：
  - `scripts/启动学习工具.bat`（一键盘启动）
  - `scripts/stop_web_safe.bat`（一键停止）
  - `scripts/backup_user_data.bat`（一键备份 → `backups/<时间戳>/`）

### 7.3 数据库备份自动化

- `scripts/backup_user_data.bat:1-66` 手动触发；备份 `data/task_publisher.db`、`config/config.json`、`src/notes/vault/`、`src/notes/prompts/`
- **未发现 cron / Task Scheduler 配置**（属于本机运维，未提交仓库）。

---

## 8. Hardware / External Dependencies

### 8.1 硬件

- **无 GPU/CPU/外设要求**。
- 本机 Chromium 路径硬编码到 `C:\Users\wn\...`（**不可移植**，详见 §11）。

### 8.2 外部服务（**仅可选**）

| 服务 | 是否必需 | 用途 |
|------|---------|------|
| OpenAI API | 否 | AI 辅助任务生成（密钥空时功能降级） |
| Claude API | 否 | 同上 |
| Obsidian | 否 | 「在 Obsidian 中打开」按钮（通过 URI scheme） |

### 8.3 网络

- 仅在调用 AI 时需要外网。
- 字体/JS/CSS 已 100% vendor 本地化（断网可用）。

### 8.4 文件系统

- `src/notes/`（Obsidian vault + 提示词 + 临时资料）— **`.gitignore` 显式忽略，绝不提交零散笔记
- `data/task_publisher.db` — 用户数据库，**`.gitignore` 忽略**
- `config/config.json` — 含 API Key 字段，**`.gitignore` 忽略**
- `backups/` — 手动备份产物
- `.run/` — 运行时 PID/日志，**`.gitignore` 忽略**

---

## 9. Static-confirmed Facts

> 这些结论**仅靠阅读代码/配置即可确认**，无需运行。

### A. 依赖与构建
1. `requirements-web.txt` 是真正安装的依赖文件（`scripts/start_web_safe.bat:75`）。
2. `package.json` 仅有 `playwright`/`@playwright/test` 两个 devDep（无前端构建链）。
3. `config/config.json` 是唯一被代码读取的配置；`.env` 不读取。
4. 入口有 3 条：`server/backend_api.py`（legacy）、`run_app.py`（Phase 2 工厂）、`scripts/main.py`（**已失效**——PySide6 归档）。
5. 无构建步骤、无类型检查、无打包。

### B. 启动链路
6. 默认端口 5000，host `0.0.0.0`。
7. 启动流程：`.venv` Python → 装依赖 → `launch_server.py` 启动子进程 → `/api/health` 探活 → 自动开浏览器。
8. 停止流程：`.run/server.pid` + `taskkill` + 端口清理（`scripts/stop_server.py:18-29`）。
9. 健康检查：`GET /api/health` 超时 2 秒，重试 15 次（`scripts/start_web_safe.bat:111-114`）。

### C. 数据库
10. SQLite + WAL + `busy_timeout=30s` + `foreign_keys=ON`（`server/app/extensions.py:88-93`）。
11. 启动时自动迁移 7 类 schema（`server/backend_api.py:3563-3569`）。

### D. 测试
12. E2E 路径硬编码 Chromium：`C:\Users\wn\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe`（`tests/e2e-manual.js:9`、`tests/e2e/playwright.config.js:13`）。
13. E2E `BASE_URL` 硬编码 `http://127.0.0.1:5000`（`tests/e2e-manual.js:8`）。

### E. 架构
14. Phase 2 重构中，`server/backend_api.py` 大段路由被注释（行号 ~3399-3509 出现 `# @app.route...` 块），由 `server/blueprints/*` 接管。
15. PySide6 桌面端已归档到 `_archive/src_tasks_legacy/`（`src/tasks/README.md`、`scripts/main.py:1-13`）。

### F. CI/CD
16. 仓库内**无任何 CI/CD 配置文件**（`.github/`、`.gitlab-ci.yml`、`Jenkinsfile`、`Dockerfile`、`docker-compose.yml` 全部缺失）。

---

## 10. Requires Runtime Verification

> 这些结论需要真正执行才能确认；本报告**未做**验证。

### A. 启动链路
1. ⚠️ `.venv` 是否已存在于仓库？仓库内无 `.venv/` 文件（Glob 返回 0），需要首次启动时自动创建。
2. ⚠️ Python 3.10+ 是否在本机 PATH？需 `py -3 --version` 验证。
3. ⚠️ `pip install -r requirements-web.txt` 在默认源是否成功？是否触发清华镜像回退？
4. ⚠️ 服务启动后 `/api/health` 是否在 15 秒内响应？
5. ⚠️ 浏览器自动打开后 `src/index.html` 是否能正常加载（无 CORS、字体 404、JS 报错）？

### B. 端到端
6. ⚠️ `node tests\e2e-manual.js` 在新机器上是否全绿（README 说 26/26）？
7. ⚠️ `npx playwright test --config=tests\e2e\playwright.config.js` 是否可用？
8. ⚠️ 数据库迁移在已有旧库（`data/task_publisher.before_chapter_deps_fix.db`）上是否平滑？

### C. 路径与硬编码
9. ⚠️ 用户名路径硬编码（`C:\Users\wn\...`）在非 wn 用户下是否需要批量替换？
10. ⚠️ `.venv\Scripts\python.exe` 在 PowerShell 5.1 下执行 `.bat` 中文是否乱码？（AGENTS.md §9 提到 PS5.1 中文模式静默失配，但 `.bat` 用 `chcp 65001` 处理）

### D. 端口冲突
11. ⚠️ 5000 端口被占用时，`scripts/stop_server.py:18-29` 是否能正确清掉旧实例？
12. ⚠️ 多实例同时启动会发生什么？

### E. 数据库/迁移
13. ⚠️ `ensure_indexes(conn)`、`sync_all_unlock_states(conn)` 等迁移函数（`server/backend_api.py:3568-3569`）在已有库上的幂等性？
14. ⚠️ `migrate_dependency_data()`（`server/backend_api.py:3561`）的具体行为？

### F. Phase 1/2 入口并存
15. ⚠️ `server/backend_api.py` 与 `run_app.py` 两条入口都能跑，但行为差异（前者注册 5 个 BP + 行内路由；后者通过 `create_app()` 注册 8 个 BP）是否会导致某些端点只在其中一个入口下可用？

---

## 11. Environment Risks / Missing Information

### 11.1 风险（按严重度排序）

| # | 等级 | 风险 | 影响 |
|---|------|------|------|
| 1 | 🔴 阻断 | Chromium 路径硬编码到 `C:\Users\wn\...` | 任何非 wn 用户必须改源码（`tests/e2e-manual.js:9` + `tests/e2e/playwright.config.js:13`） |
| 2 | 🔴 阻断 | `python`/`python3` 是 WindowsApps stub | 开发者必须直接用 `.venv\Scripts\python.exe`；AGENTS.md §9 已记录 |
| 3 | 🟠 警告 | `data/task_publisher.db` 首次启动才自动创建 | 新机器首次启动需要 `data/` 目录；schema 迁移是否完全幂等未验证 |
| 4 | 🟠 警告 | `scripts/main.py` 顶端 `from src.tasks.ui.main_window import MainWindow`（已注释）但代码本体仍尝试 import（`scripts/main.py:23`） | 误跑 `python scripts/main.py` 会崩；建议改入口直接 raise |
| 5 | 🟠 警告 | E2E 用例数不一致 | README 说 26/26，CHANGELOG 提到 36/36；实际 `tests/e2e-manual.js` 函数数量约为 26 个 case（手数约 26 项）— **静态推断，待运行验证** |
| 6 | 🟡 提示 | 大量 `tests/_run*.log`、`tests/_e2e_*_log` 在仓库根（**未在 `.gitignore` 显式忽略**） | 体积噪声，不影响运行 |
| 7 | 🟡 提示 | `.tmp_envprobe.py`、`tmp_*.log`、`tmp_*.txt` 散落（git 状态显示 70+ 未跟踪临时文件） | 需要一次 `.gitignore` 清理或 `git clean` |
| 8 | 🟡 提示 | `scripts/check_portability.py` 被 `verify_transferred_project.bat:111` 调用，但文件不存在（Glob 返回 0） | 迁移校验脚本链断裂 |
| 9 | 🟡 提示 | `opencode.json` 暴露了外部 LLM 网关的 API key | 已在 `.gitignore:3`，但开发者必须确保不要 `git add -f` |

### 11.2 缺失的关键信息

1. **Python 最低版本号**——`scripts/start_web_safe.bat` 只说 `Python 3.10+`，但 `opencode.json:53` 声称「Python 3.12.6 已正确安装到 .venv」；两者一致（3.10+ 包含 3.12.6）。
2. **Phase 2 是否完成**——`server/blueprints/*` 8 个蓝图都已注册到 `create_app()`，但 `server/backend_api.py` 中仍有 legacy 路由被注释——是否「Phase 2 全部跑通」需运行验证。
3. **真实依赖图**——除 `requirements-web.txt`，`server/services/ai.py` 可能依赖 `openai` 等外部包，但该包未在 `requirements*.txt` 中列出（**需运行时 import 失败验证**）。
4. **生产部署流程**——完全没有 CI/CD，无部署说明。
5. **跨平台兼容性**——所有启动脚本是 `.bat` + PowerShell 5.1/7 的脚；Mac/Linux 不可直接运行（需要转换）。

### 11.3 与 README/AGENTS.md 的不一致（**标记为「静态推断」**）

- README §一描述的「真实目录结构」与 git status 实际显示有偏差：
  - `static/app.entry.js`、新 `static/core/*`、`static/shared/*`、`static/modules/*` 在 README §一 未列出（README 是 2026-08-05 版本）
  - `static/test.js` README 标「可清理」，但实际仍在仓库
- README §二启动用「`scripts/启动学习工具.bat`」，但 `scripts/start.bat` 和 `scripts/start_web_safe.bat` 才是真实入口；README 已对齐。
- AGENTS.md §「真实目录结构（2026-08-05 核对）」与 README §一几乎相同；都未列出 Phase 2 后的 Blueprint 树。

---

## 12. Most Relevant Files

> 按重要性排序。**新开发者必读 12 个文件**：

### 必读入口（1-3）

| # | 路径 | 用途 |
|---|------|------|
| 1 | `README.md` | 项目入口、API 速查、脚本清单 |
| 2 | `AGENTS.md` | Cursor/AI 协作规则（本仓库唯一权威指南） |
| 3 | `requirements-web.txt` | 真正的 Python 依赖（Web 入口） |

### 启动链路（4-6）

| # | 路径 | 用途 |
|---|------|------|
| 4 | `scripts/启动学习工具.bat` | 一键启动入口（中文文件名） |
| 5 | `scripts/start_web_safe.bat` | 启动逻辑全在这里（venv 创建/依赖安装/启停/健康检查） |
| 6 | `scripts/launch_server.py` | 拉起后端子进程 + 写 PID/日志 |

### 后端核心（7-9）

| # | 路径 | 用途 |
|---|------|------|
| 7 | `server/backend_api.py` | Legacy 主入口（注册 5 BP + 行内路由 + schema 迁移） |
| 8 | `server/app/app_factory.py` | Phase 1/2 工厂入口（注册 8 BP） |
| 9 | `server/app/config.py` | 配置加载（带默认值回退） |

### 前端核心（10-12）

| # | 路径 | 用途 |
|---|------|------|
| 10 | `src/index.html` | 唯一 HTML（~990 行；含内联 CSS、字体、SVG、DOM 骨架） |
| 11 | `static/app.js` | 唯一前端逻辑（~2811 行；主导 UI） |
| 12 | `static/app.entry.js` | Phase 1 模块化薄入口（验证 core+shared 完整） |

### 测试与配置（13-15）

| # | 路径 | 用途 |
|---|------|------|
| 13 | `tests/e2e-manual.js` | E2E 入口（playwright-core；26 用例） |
| 14 | `tests/e2e/playwright.config.js` | Playwright Test 配置 |
| 15 | `config/config.example.json` | 配置模板（复制改名为 `config.json`） |

### 红线与约束（参考）

| # | 路径 | 用途 |
|---|------|------|
| R1 | `.gitignore` | 哪些文件**绝不**提交（`config.json` / `data/` / `src/notes/`） |
| R2 | `opencode.json` | 外部 LLM 协作配置（含 key 字段，已在 `.gitignore`） |

### 附加参考（了解 Phase 1/2 重构）

| # | 路径 | 用途 |
|---|------|------|
| P1 | `docs/ARCHITECTURE_REDESIGN_2026-08-16.md` | 架构重设计方案 C（Blueprint + Factory + Repo） |
| P2 | `src/tasks/README.md` | PySide6 桌面端归档说明 |
| P3 | `run_app.py` | Phase 2 工厂入口（与 `backend_api.py` 并存） |

---

## 附录：快速复现命令（仅参考，不实际执行）

> 新开发者拿到仓库后的**理论**步骤（按 1 → 7 顺序，**静态推断**）：

```bat
:: 1. 进入项目根
cd "D:\Axelit\.工作\trae\超级自动化学习工具"

:: 2. 确认 Python 3.10+
py -3 --version

:: 3. 一键启动（自动建 venv + 装依赖 + 健康检查 + 开浏览器）
scripts\启动学习工具.bat

:: 4. 浏览器访问
:: http://127.0.0.1:5000/

:: 5. 手动停止
scripts\stop_web_safe.bat

:: 6. 数据备份
scripts\backup_user_data.bat

:: 7. E2E 测试（先启动服务）
node tests\e2e-manual.js
```

> ⚠️ 第 3 步会调用 `.venv\Scripts\python.exe`，路径在中文 Windows 用户目录下，**实际是否成功需运行验证**。

---

*报告生成时间：2026-10-03*
*所有路径相对 `D:\Axelit\.工作\trae\超级自动化学习工具\`*
*本报告为只读调查，不修改任何文件*