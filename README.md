# 超级自动化学习工具

> **一句话定位**：基于 Flask + SQLite 的本地 Web 应用，把 Obsidian 笔记库与「任务抽卡 + 日程/精力追踪」学习系统合在一处，逼迫时间花在真正的思考上。
>
> **本文档**：2026-08-05 重写的权威 README，替代此前已过时且编码损坏的旧版。所有目录结构、API 列表、脚本名均以代码实测为准。

---

## 一、真实目录结构

```
超级自动化学习工具/
├── server/                                # Web 后端（现行主路径）
│   ├── backend_api.py                     # Flask 应用，端口 5000，全部 /api/* 路由
│   └── serve_static.py                    # 遗留静态服务壳（基本无逻辑）
├── src/                                   # 前端 + 桌面侧领域层 + 笔记知识库
│   ├── index.html                         # 唯一前端页面（内联 CSS + DOM 骨架）
│   ├── tasks/                             # 原 PySide6 桌面领域层（遗留，仍可启动但非主用）
│   │   ├── models/database.py             # 桌面侧 SQLite 模型/迁移声明
│   │   ├── services/                      # gacha / task / state / export / ai_import
│   │   ├── ui/                            # Tkinter / PySide6 主窗口
│   │   └── utils/
│   └── notes/                             # Obsidian Vault + 学习资料 + Agent 提示词（不动）
│       ├── vault/                         # 主知识库（约 1485 个 .md）
│       ├── prompts/                       # Agent 提示词文件
│       ├── 未分类/  已分类/               # Agent 协作输入输出目录
│       ├── PPT/  习题和真题/  Radiances Of Wisdom/  灵感提取报告/
│       ├── audit_examples_raw.txt
│       ├── vault.zip
│       └── 变更日志报告.md
├── static/                                # Flask 静态目录（由 backend_api.py 引用）
│   ├── app.js                             # 前端全部业务逻辑（~2711 行，含双计时器状态机）
│   └── test.js                            # 历史探测脚本（失效，可清理）
├── scripts/                               # 启停、备份、验收、资料处理脚本
│   ├── launch_server.py                   # 启动后端并写 .run/server.pid
│   ├── stop_server.py                     # 根据 .run/server.pid 停止后端
│   ├── 启动学习工具.bat                   # 中文入口（转调 start_web_safe.bat）
│   ├── start.bat / start_web_safe.bat     # 安全启动：自动建 venv、装依赖、健康检查
│   ├── stop_web_safe.bat                  # 安全停止
│   ├── backup_user_data.bat               # 备份 data/db + config + vault + prompts
│   ├── verify_transferred_project.bat     # 校验迁移后的项目结构
│   ├── run_stable_acceptance.bat          # 稳定验收入口
│   ├── export_tasks_for_ai.py             # 导出任务快照 → ai_workspace/00_context/
│   ├── validate_task_patch.py             # 校验 AI 输出的任务修改草稿
│   ├── main.py / start-desktop.bat        # 桌面端入口（PySide6，遗留）
│   ├── check_database.py / verify_tables.py / migrate_fix_missing_tables.py
│   ├── test_api_endpoints.py / test_flask_tags*.py / test_http_detailed.py / test_health_and_tags.py / test_tags.py / test_simple.py
│   ├── extract_*.py / read_doc*.py / filter_extracted_images.py / split_english_course.py
│   ├── _inspect_db.py / _inspect_db2.py / _read_exact.py / debug_tags*.py / test_regex.py / verify_fixes.py / full_verification.py
│   ├── download_python.bat / remove_note_links.ps1 / 批量处理笔记.ps1
│   └── __pycache__/
├── tests/                                 # E2E 测试与运行日志
│   ├── e2e-manual.js                      # 主 E2E（playwright-core + 显式 chromium 路径）
│   ├── e2e.spec.js                        # Playwright Test 风格 spec
│   ├── e2e/playwright.config.js           # Playwright Test 配置
│   └── _run1.log … _run4.log              # 历史 E2E 运行日志
├── config/
│   ├── config.json                        # 运行时配置（端口、vault 路径、API Key、DB 路径）
│   └── config.example.json
├── data/                                  # 用户数据
│   ├── task_publisher.db                  # ★ 现行用户数据库（禁止误删）
│   ├── task_publisher.before_chapter_deps_fix.db   # 章节依赖修复前的快照
│   ├── backup/                            # 运行时自动备份目录
│   ├── physics_questions.txt / physics_answers.txt # 临时提取物
│   └── image_filter_report.md
├── ai_workspace/                          # 外部 AI 协作沙箱（不接自动写入）
│   ├── 00_context/  01_requests/  02_ai_outputs/
│   ├── 03_task_drafts/  04_reviewed/  99_archive/
│   └── README.md                          # 本目录使用规范（含四条红线）
├── docs/                                  # 当前权威文档
│   ├── STRUCTURE_MAP_2026-08-04_auto.md   # 唯一权威结构图（含 API 面、数据模型、前端问题）
│   ├── FRONTEND_BUG_LIST_2026-08-04.md    # 前端 Bug 清单与 P3 修复优先级
│   ├── ACCEPTANCE_TEMPLATE.md             # 验收报告模板（长期复用）
│   └── design-spec.txt                    # 原始设计规格（历史参考，技术栈已脱节）
├── _archive/                              # 2026-07 大规模清理归档（10 个分类子目录）
│   ├── 01_临时脚本/  02_缓存数据/  03_数据库备份/  04_PPT提取物/
│   ├── 05_过时文档/                       # 含 docs/ 旧 Markdown 与本次整理的一次性报告
│   ├── 06_测试脚本/  07_工具脚本/  08_提示词备份/  09_审计报告/  10_其他杂项/
│   ├── 归档执行报告.md  归档报告.json
├── .run/                                  # 运行态（server.pid / server.log，勿当源码）
├── .venv/                                 # Python 虚拟环境（首次启动自动创建）
├── .python/  .cursor/  node_modules/      # 工具运行时缓存
├── 执行归档清理.bat / 执行归档清理.py     # 归档工具（UTF-8 中文文件名）
├── requirements-web.txt                   # 仅 Web 依赖（flask + flask-cors）
├── requirements.txt                       # 全部依赖（含 PySide6）
├── package.json / package-lock.json       # Playwright（仅 E2E 用）
├── PROJECT_CHANGELOG.md                   # 项目变更日志（工单管理）
├── opencode.json                          # opencode 配置
└── README.md                              # ← 本文件
```

---

## 二、启动 / 停止 / 备份

### 启动（一键）

```
双击 scripts/启动学习工具.bat
```

行为：
1. 自动定位 Python（优先 `.venv\Scripts\python.exe` → `py -3` → `python`）。
2. 若无 `.venv` 自动创建并安装 `requirements-web.txt`（失败回退清华镜像）。
3. 杀掉旧 PID（`.run/server.pid`），通过 `scripts/launch_server.py` 拉起 `server/backend_api.py`。
4. 等待 `GET /api/health` 通过（最多 15 秒），自动打开浏览器到 `http://127.0.0.1:5000/`。
5. 服务日志：`.run/server.log`。

### 启动（直接命令）

```powershell
# 前置：确保 .venv 已就绪或系统 Python 3.10+ 可用
.\.venv\Scripts\python.exe server\backend_api.py
# 浏览器访问 http://127.0.0.1:5000/
```

### 停止

```
双击 scripts\stop_web_safe.bat
# 或：scripts\stop_server.py（依据 .run/server.pid）
```

### 备份

```
双击 scripts\backup_user_data.bat
```

输出到 `backups\<时间戳>\` 下，覆盖三类：
- `data/task_publisher.db`
- `config/config.json`
- `src/notes/vault/` 与 `src/notes/prompts/`

### 校验迁移

```
双击 scripts\verify_transferred_project.bat
```

---

## 三、E2E 测试方法

### 前置依赖

- Node.js（带 `npm`，已装本仓 `package.json` 中的 `playwright-core`）。
- Chromium 浏览器：`C:\Users\<user>\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe`（`tests/e2e-manual.js` 与 `tests/e2e/playwright.config.js` 中硬编码此路径，不一致需改两端）。
- 后端在 `127.0.0.1:5000` 已启动且 `/api/health` 返回 healthy。

### 运行

```powershell
node tests\e2e-manual.js
```

该脚本使用 `playwright-core` 直接 API（绕过 headless-shell 兼容问题），覆盖六大功能区 + 全局导航共 26 用例。失败自动截图；成功仅打印汇总。

可选 Playwright Test 风格入口：

```powershell
npx playwright test --config=tests\e2e\playwright.config.js
```

历史日志见 `tests/_run1.log` ~ `tests/_run4.log`。

---

## 四、API 速查（来自 `server/backend_api.py`）

> 详细字段与表关系见 `docs/STRUCTURE_MAP_2026-08-04_auto.md` 第 2、6 节。

| 域 | 端点 |
|----|------|
| 健康 | `GET /api/health` |
| 任务 | `GET/POST /api/tasks`、`GET/PUT/DELETE /api/tasks/<id>`、`GET /api/tasks/<id>/dependents`、`POST /api/tasks/<id>/{complete,skip,refuse,move-to-discard}`、`POST /api/tasks/<id>/feedback` |
| 抽卡 | `GET /api/gacha/pools`、`GET /api/gacha/pools/detail`、`POST /api/gacha/draw`、`POST /api/gacha/care-draw`、`POST /api/gacha/replace`、`GET /api/gacha/statistics` |
| 弃牌堆 | `GET /api/discard-pile`、`POST /api/discard-pile/<id>/restore` |
| 标签 | `GET/POST /api/tags`、`DELETE /api/tags/<id>`、`POST /api/tags/batch` |
| 依赖 / 导出 | `GET /api/dependencies`、`GET /api/export` |
| 日程 | `GET/POST /api/schedule/{weekly,daily,activities}`、`DELETE /api/schedule/activities/<id>`、`GET /api/schedule/slots` |
| 状态 | `GET/POST /api/state/{daily-tone,sleep}`、`POST /api/state/energy`、`GET /api/state/weekly-energy`、`GET/POST /api/state/assessment`、`GET /api/state/assessment/{history,correlate}`、`GET /api/state/questions` |
| 计时 | `POST /api/timer/{start,complete}`、`GET /api/timer/active` |
| 反馈 | `GET/POST /api/task-feedback` |
| 知识库 | `GET /api/knowledge/{categories,points,graph,recent,notes}`、`GET /api/knowledge/note/<path>`、`GET /api/knowledge/note-content/<path>`、`GET /api/knowledge/point-detail/<subject>/<point>`、`POST /api/knowledge/open-in-obsidian` |
| 配置 | `GET /api/config`、`POST /api/config/save` |
| 提示词 | `GET /api/prompts`、`GET /api/prompts/<name>`、`PUT /api/prompts/<name>`、`GET /api/prompts/<name>/backup/latest`、`POST /api/prompts/<name>/restore-latest` |
| Agent | `GET /api/agent/agents`、`GET /api/agent/agents/<id>/prompt`、`GET /api/agent/files/{raw,vault}`、`GET /api/agent/files/{raw,vault}/content`、`POST /api/agent/{process,save-note,import-tasks}` |
| 入口 | `GET /`  → `src/index.html` |

---

## 五、前端功能区

由 `src/index.html` 顶导 + `static/app.js` 驱动：

| 页面 | 能力 |
|------|------|
| `gacha` | 牌堆视觉、抽卡（碎片/番茄/深度卡池）、可用时间、今日统计、抽中卡片操作（开始/跳过/拒绝/换牌）、弃牌堆缩略、计时 dock |
| `tasks` | 任务池搜索/筛选、新建编辑、批量标签、依赖图、弃牌堆列表、第二套计时器面板 |
| `schedule` | 睡眠追踪、近 7 日能量、状态评估与历史、日日程格、活动管理 |
| `knowledge` | 学科分类、笔记列表、Markdown 渲染、Obsidian 打开 |
| `config` | 端口/笔记路径/API、提示词只读+可编辑（带备份）、Agent 只读浏览入口 |

弹窗：任务编辑、弃牌堆、状态评估问卷、任务事件反馈、关怀换牌、活动管理、依赖图、Agent 浏览、提示词 diff 等。

---

## 六、红线（2026-08-05 重写后唯一保留）

- **`src/notes/` 不提交 git**（知识库、提示词、原始资料均为本地内容；任何修改或上传到仓库视为数据泄露）。

> 旧版红线（抽卡算法不可改、勿恢复大段内联 JS 等）已撤销。流程约束以本 README 与 `docs/STRUCTURE_MAP_2026-08-04_auto.md` 第 3.3 节「改动风险标注」为准。

---

## 七、文档导航

| 想了解的内容 | 看哪份文档 |
|--------------|------------|
| 项目结构、数据模型、前端问题区、改动风险、API 全量列表 | [`docs/STRUCTURE_MAP_2026-08-04_auto.md`](docs/STRUCTURE_MAP_2026-08-04_auto.md) |
| 前端已知 Bug 与 P3 修复优先级 | [`docs/FRONTEND_BUG_LIST_2026-08-04.md`](docs/FRONTEND_BUG_LIST_2026-08-04.md) |
| 验收报告模板（每次收尾验收复制粘贴） | [`docs/ACCEPTANCE_TEMPLATE.md`](docs/ACCEPTANCE_TEMPLATE.md) |
| 早期 PySide6 桌面端设计（仅历史参考） | [`docs/design-spec.txt`](docs/design-spec.txt) |
| 一次性审计/测试/修复/验收报告（2026-08-04 系列） | [`_archive/05_过时文档/2026-08-04_一次性报告/`](_archive/05_过时文档/2026-08-04_一次性报告/) |
| 历史归档（产品路线图、开发日志、阶段说明、提取物等） | [`_archive/`](_archive/) |
| 工单与功能变更记录 | [`PROJECT_CHANGELOG.md`](PROJECT_CHANGELOG.md) |
| 外部 AI 协作流程与红线 | [`ai_workspace/README.md`](ai_workspace/README.md) |

---

## 八、历史说明

- 本 README 于 **2026-08-05** 重写，替代此前 `docs/README.md`（编码损坏 + 路径已过时）与 `docs/使用说明.txt`（指向不存在的 `任务发布系统/`、`笔记处理系统/`、`tools/` 等目录）。
- `docs/STRUCTURE_MAP_2026-08-04_auto.md` 为唯一权威结构图；同期同名 `_auto` 之前的 `STRUCTURE_MAP_2026-08-04.md`（无 `_auto` 后缀）内容已被前者在同日期覆盖，本次整理一并归档。
- 旧版 README 中声称的「P1-Stable-1B 封版」叙事停在 2026-06 阶段语言，已不再适用；代码与归档继续演进到 2026-08。
- 任何 AI 助手或开发者进入本仓库的第一入口即为本文档。

---

*生成时间：2026-08-05*  
*依据：`server/backend_api.py`（API）、`src/index.html` + `static/app.js`（前端）、`config/config.json`（运行配置）、`tests/e2e-manual.js`（测试）、`scripts/`（启停备份）、`data/task_publisher.db`（实库）实测。*
