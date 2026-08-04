# 超级自动化学习工具 — 完整项目文档

> **版本**: P1-Stable-1B | **日期**: 2026-06-05 | **状态**: 持续开发中

---

## 目录

1. [项目概述](#1-项目概述)
2. [目录结构](#2-目录结构)
3. [核心功能模块](#3-核心功能模块)
4. [API 接口完整清单](#4-api-接口完整清单)
5. [数据库设计](#5-数据库设计)
6. [门禁系统](#6-门禁系统)
7. [可移植性设计](#7-可移植性设计)
8. [前端架构](#8-前端架构)
9. [配置文件说明](#9-配置文件说明)
10. [开发与调试](#10-开发与调试)
11. [已知待解决问题](#11-已知待解决问题)
12. [代码规范](#12-代码规范)

---

## 1. 项目概述

### 1.1 项目定位

超级自动化学习工具是一个面向大学生期末复习的个人学习管理系统。核心创新：通过**游戏化抽卡**机制驱动任务执行，配合**多维状态评估**和**知识库导航**，将枯燥的复习任务转化为可追踪、有成就感的流程。

不是普通的 Todo 应用，也非纯抽卡小游戏。

### 1.2 核心价值

| 维度 | 说明 |
|------|------|
| 任务管理 | 支持依赖链、加权随机抽卡、弃牌堆、标签筛选 |
| 状态追踪 | 7 维度被动采集（每日评估、计时、睡眠、反馈） |
| 知识资产 | 148 篇 Markdown 笔记 + ~150 个知识点，Wikilink 图谱 |
| 视觉激励 | 8 套卡牌主题、翻转/消散/飞走/滑出/飞行 5 类动画 |
| 可移植 | 内置 Python 3.11.9，解压即用，无需系统预装 Python |

### 1.3 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Python Flask 3.x + flask-cors | `server/backend_api.py` (3295 行) |
| 数据库 | SQLite3 | `data/task_publisher.db` (31 张表) |
| 前端 | 原生 HTML/CSS/JS | `index.html` (595 行) + `static/app.js` (2260+ 行) |
| 内置 Python | Python 3.11.9 embed | `.python/` 目录 (12MB) |
| 备用桌面端 | PySide6 | `src/tasks/ui/` (5 个窗口, 4000+ 行) |

### 1.4 当前版本状态

- **封版状态**: P1-Stable-1B 已解封，进入持续开发
- **已锁定阶段**: P0 ~ P1-Visual-1/1A ~ P1-Stable-1/1B
- **Agent 状态**: 默认保守，逐步向受控处理 / 受控写入能力演进
- **红线**: 不改 DB 结构、不改抽卡算法、不改 `task_feedback_events` 结构、不恢复大段内联 JS

---

## 2. 目录结构

```
超级自动化学习工具/
├── 启动学习工具.bat              # 一键启动入口
├── index.html                    # 前端单页应用 (595 行, 5 个标签页)
├── main.py                       # 桌面端入口 (PySide6, 备用)
├── README.md                     # 项目说明
├── PROJECT_DOCUMENTATION.md      # 本文档
│
├── config/
│   ├── config.json               # 主配置 (gitignored, 含密钥)
│   └── config.example.json       # 配置模板
│
├── server/
│   └── backend_api.py            # Flask 后端 (3295 行, 62 个 API)
│
├── src/
│   ├── __init__.py
│   ├── notes/                    # 笔记系统
│   │   ├── prompts/              # AI Agent 提示词文件
│   │   │   ├── AI_assistant_prompt.md
│   │   │   ├── 笔记整理师.md
│   │   │   ├── 知识点整理师.md
│   │   │   ├── 结构审查师.md
│   │   │   └── 内容审查师.md
│   │   ├── vault/                # Obsidian Vault (121 篇笔记 + 150 知识点)
│   │   │   ├── 知识索引.md
│   │   │   ├── 概念映射表.json
│   │   │   ├── 知识点/           # 按学科组织的知识点 Markdown
│   │   │   └── 高等数学/ 大学物理/ 线性代数/ 电子技术/ 计算机/ 英语四级/
│   │   ├── 未分类/               # 原始转写素材
│   │   └── 已分类/               # 按学科分类的课堂笔记
│   └── tasks/                    # 桌面端任务系统 (与 Web 共享 DB)
│       ├── models/
│       │   ├── database.py       # SQLite 数据层 (846 行)
│       │   └── task.py           # Task 模型 + 枚举
│       ├── services/
│       │   ├── task_service.py   # 任务 CRUD + 权重算法
│       │   ├── gacha_service.py  # 抽卡逻辑
│       │   ├── state_service.py  # 状态管理
│       │   ├── export_service.py # JSON 导出
│       │   ├── ai_import_service.py
│       │   └── ai_import_processor.py
│       └── ui/
│           ├── main_window.py    # 主窗口 (1370+ 行)
│           ├── gacha_window.py   # 抽卡窗口 (1247 行)
│           ├── schedule_window.py
│           ├── filter_dialog.py
│           └── dependency_graph.py
│
├── static/
│   ├── app.js                    # 前端核心 JS (2260+ 行)
│   └── test.js                   # JS 测试
│
├── scripts/
│   ├── start_web_safe.bat        # 启动脚本 (含软门禁)
│   ├── stop_web_safe.bat         # 停止脚本
│   ├── run_stable_acceptance.bat # 回归验收 (含硬门禁)
│   ├── backup_user_data.bat      # 数据备份
│   ├── verify_transferred_project.bat # 换机验证
│   ├── download_python.bat       # 下载嵌入式 Python
│   ├── check_portability.py      # 核心门禁检测器
│   ├── launch_server.py          # 启动服务器
│   ├── stop_server.py            # 停止服务器
│   ├── inspect_db_schema.py      # DB 结构检查
│   ├── p0_*.py / p1_*.py         # 各阶段 E2E + Acceptance 测试
│   ├── export_tasks_for_ai.py    # 导出任务给外部 AI
│   ├── validate_task_patch.py    # 校验 AI 生成的 patch
│   ├── import_tasks.py           # 导入任务
│   └── generate_tasks.py         # 批量生成考试复习任务
│
├── tools/                        # 30 个笔记处理工具脚本
│   ├── add_wikilinks.py
│   ├── check_links.py
│   ├── convert_md_to_wikilinks.py
│   ├── rename_files.py
│   └── ... (共 34 个脚本)
│
├── data/
│   ├── task_publisher.db         # 主 SQLite 数据库 (gitignored)
│   ├── backup/                   # 数据库备份
│   └── ai_exports/               # AI 导出快照
│
├── ai_workspace/                  # 外部 AI 协作目录
│   ├── 00_context/               # 任务快照上下文
│   ├── 01_requests/              # AI 请求池
│   ├── 02_ai_outputs/            # AI 输出暂存
│   ├── 03_task_drafts/           # 任务补丁草稿
│   ├── 04_reviewed/              # 已审核
│   └── 99_archive/               # 归档
│
├── docs/                         # 12+ 篇架构/使用文档
├── .python/                      # 嵌入式 Python 3.11.9 (12MB)
├── .venv/                        # 虚拟环境 (gitignored)
├── requirements-web.txt          # Web 依赖: flask, flask-cors
├── requirements.txt              # 完整依赖: flask, flask-cors, PySide6
└── .gitignore
```

### 2.1 核心文件说明

| 文件 | 用途 | 大小 |
|------|------|------|
| `server/backend_api.py` | Flask 主后端，所有 API + DB 操作 | 126KB / 3295 行 |
| `static/app.js` | 前端业务逻辑，抽卡/任务/动画 | 2260+ 行 |
| `index.html` | 单页应用 HTML + 内联 CSS | 595 行 |
| `scripts/check_portability.py` | 门禁检测器，7+ 项检查 | 420+ 行 |
| `data/task_publisher.db` | SQLite 数据库 | ~500KB |
| `scripts/start_web_safe.bat` | 启动脚本 (含软门禁) | 170+ 行 |
| `scripts/run_stable_acceptance.bat` | 回归验收脚本 (含硬门禁) | 70+ 行 |

---

## 3. 核心功能模块

### 3.1 任务管理系统

#### 3.1.1 任务 CRUD

- **创建**: `POST /api/tasks` → 自动关联标签、初始化依赖状态
- **读取**: `GET /api/tasks` (支持 `include_completed`、`unlocked_only`、标签过滤)
- **更新**: `PUT /api/tasks/<id>` → 同步更新依赖关系
- **删除**: `DELETE /api/tasks/<id>` → 级联清理依赖引用

#### 3.1.2 抽卡系统 (Gacha)

**3 个卡池**:

| 卡池 | 预估时间 | 适用场景 |
|------|----------|----------|
| 碎片 (Fragment) | 0-15 分钟 | 快速复习/碎片化任务 |
| 番茄 (Tomato) | 15-45 分钟 | 中等难度/专题训练 |
| 深度 (Deep) | 45+ 分钟 | 系统复习/大型任务 |

**加权随机算法** (`_calculate_full_weight`):

```
权重 = priority/5
     × deadline_urgency (逾期 3.0x / 1天 2.5x / 3天 1.5x / 7天 1.0x / 远 0.5x)
     × energy_match (1.5 - 0.3 × |diff|, ≥ 0.5)
     × resistance_penalty (低 1.0 / 中 0.8 / 高 0.6)
     × success_factor (0.5 + success_rate × 0.5)
     × refusal_penalty (max(0.3, 1.0 - refusal_count × 0.1))
     × profile_strategy
     × cooldown (同任务 0 / 同类别 0.3x / >=3次抽卡 0.2x)
```

**抽卡 API**:
- `POST /api/gacha/draw` — 单抽 (body: `{pool, energy, available_time}`)
- `POST /api/gacha/replace` — 换牌 (消耗一次替换机会)
- `GET /api/gacha/pools` — 卡池信息
- `GET /api/gacha/statistics` — 统计 (成功率/拒绝率/偏好分布)

#### 3.1.3 弃牌堆

- `GET /api/discard-pile` — 查看弃牌堆任务
- `POST /api/tasks/<id>/move-to-discard` — 移入弃牌堆
- `POST /api/discard-pile/<id>/restore` — 恢复到任务列表

#### 3.1.4 依赖系统

- 基于 `task_dependencies` 表的 BFS 循环检测
- `compute_is_unlocked()` — 所有前置任务完成才解锁
- `chain_unlock()` — 完成任务时级联解锁后续任务
- `detect_cycle()` — 拒绝创建循环依赖
- `delete_task()` — 清理所有依赖引用

### 3.2 状态检测体系

| 维度 | 采集方式 | API |
|------|----------|-----|
| 每日状态评估 | 6 题问卷 → energy/focus/mood score | `POST /api/state/assessment` |
| 时段精力 | 早/中/晚三段记录 | `POST /api/state/energy` |
| 睡眠追踪 | 手动记录就寝时间 + 早睡连续天数 | `POST /api/state/sleep` |
| 计时器 | 计划 vs 实际时长 | `POST /api/timer/start` / `complete` |
| 任务反馈 | 跳过/提前完成/未完成/放弃 + 分类原因 | `POST /api/task-feedback` |
| 日间基调 | 高/正常/低/休息四档 | `POST /api/state/daily-tone` |
| 周能量趋势 | 过去 7 天能量曲线 | `GET /api/state/weekly-energy` |

### 3.3 知识库系统

- **121 篇笔记**: 按 6 个学科文件夹组织 (`src/notes/vault/`)
- **~150 个知识点**: 独立 Markdown 文件, Wikilink 交叉引用
- **知识图谱**: `GET /api/knowledge/graph` → 真实 `[[Wikilink]]` 解析，非随机图
- **Obsidian 集成**: `POST /api/knowledge/open-in-obsidian` → 调用本地 Obsidian

#### 3.3.1 笔记内容来源说明

> ⚠️ 本节说明各学科笔记的来源可靠性差异，2026-06-15 P5.3 审查新增。

**高等数学（AI vs AII）**：

| 学期 | 内容来源 | 例题来源 | 状态 |
|------|---------|--------|------|
| **高数 AI**（第一学期） | 宋浩网课转写 | 无习题/真题 | ⚠️ 可搁置 |
| **高数 AII**（第二学期） | AII 真题（2023/2024/2025 春） | 标注为"高等数学AII期末考试" | 🟡 需核实 |

- 高数 AI 的 71 处"高等数学**AI**"标注是**课程错误**（课程实际为 AII），且可能存在自创例题
- 高数 AII 有 3 套真实 AII 期末试卷，但笔记中的具体题号**尚未逐题核实验证**
- 建议：高数 AI 笔记暂不处理；高数 AII 笔记需对照 PDF 逐题核验

**其他学科**：

| 学科 | 来源 | 可靠性 | 备注 |
|------|------|--------|------|
| 大学物理 | 大学物理A期末复习题库.docx | 🟢 可靠 | 23 篇引用真实题库 |
| 线性代数 | 课堂录音 + 7 套真题（未引用） | 🟡 中等 | 例题来自课堂，真题资源未利用 |
| 电子技术 | PPT 截图 | 🟢 可靠（电路图） | 17 篇无例题，侧重概念讲解 |
| 计算机 | 课堂录音 | 🟡 中等 | 无对应真题资料 |

#### 3.3.2 vault 目录结构（实际文件数）

> ⚠️ 以下数据为 2026-06-15 扫描结果，与历史版本可能有差异。

```
vault/
├── 大学物理/          # 34 篇（76% 含例题，68% 有真实来源）
├── 高等数学/          # 55 篇（分 AI/AII，来源复杂，详见上方说明）
├── 线性代数/          # 17 篇（47% 含例题，来源为课堂录音）
├── 电子技术/          # 18 篇（6% 含例题，PPT 引用 100% 真实）
├── 计算机/            # 16 篇（13% 含例题，来源为课堂录音）
├── 英语四级/          # 30 篇（不在审查范围）
├── 知识点/            # ~8 篇索引页（不在审查范围）
├── diagrams/          # ~15 个 SVG 电路图
└── .obsidian/        # Obsidian 配置
```

**API**:

| 端点 | 功能 |
|------|------|
| `GET /api/knowledge/categories` | 学科分类列表 |
| `GET /api/knowledge/points` | 知识点列表 |
| `GET /api/knowledge/notes` | 笔记列表 |
| `GET /api/knowledge/graph` | 知识图谱 (nodes + edges) |
| `GET /api/knowledge/note-content/<path>` | 笔记 Markdown 内容 |
| `GET /api/knowledge/point-detail/<subject>/<name>` | 知识点详情 |

### 3.4 提示词编辑器

- `GET /api/prompts` — 列表所有提示词文件
- `GET /api/prompts/<name>` — 读取文件内容
- `PUT /api/prompts/<name>` — 保存 (自动备份)
- `POST /api/prompts/<name>/restore-latest` — 一键恢复最新备份
- 路径穿越防护: `_safe_prompt_basename()` + `_prompt_file_path()`

### 3.5 智能体系统 (只读模式)

**5 个 Agent**:

| Agent | 提示词文件 | 用途 |
|-------|-----------|------|
| 笔记整理师 | `笔记整理师.md` | 将原始讲稿重建为结构化 Markdown |
| 知识点整理师 | `知识点整理师.md` | 从笔记提取独立知识点 |
| 结构审查师 | `结构审查师.md` | 审核知识图谱结构完整性 |
| 内容审查师 | `内容审查师.md` | 审核知识点内容准确性 |
| AI任务发布 | `AI_assistant_prompt.md` | 基于知识图谱生成学习任务 |

**API**:
- `GET /api/agent/agents` — Agent 列表
- `GET /api/agent/agents/<id>/prompt` — 查看 Agent 提示词
- `GET /api/agent/files/raw` / `vault` — 浏览文件
- `POST /api/agent/process` — 执行 Agent (LLM 调用, 前端标注"只读")

### 3.6 日程管理

- **10 个时间槽**: 上午 4 个 (08:00-11:45), 中午 1 个, 下午 4 个 (14:00-17:45), 晚上 1 个 (19:00-21:30)
- **周日程**: `GET/POST /api/schedule/weekly`
- **日日程**: `GET/POST /api/schedule/daily`
- **活动管理**: `GET/POST /api/schedule/activities`

### 3.7 计时器系统

- `POST /api/timer/start` — 开始计时 (body: `{task_id, planned_minutes}`)
- `POST /api/timer/complete` — 结束计时 (body: `{result: completed/early/abandoned}`)
- `GET /api/timer/active` — 获取当前活跃计时器
- 跟踪: 计划分钟 vs 实际分钟, 完成/提前/放弃 结果

### 3.8 卡牌视觉系统

**8 套主题** (关键词自动匹配):

| 主题 | CSS 类 | 匹配关键词 | 符号 |
|------|--------|-----------|------|
| 数学 | `theme-math` | 高数/线代/微积分/数学 | ◆ |
| 语言 | `theme-lang` | 英语/四级/单词/阅读 | ♠ |
| 历史 | `theme-history` | 历史/政治 | ♛ |
| 代码 | `theme-code` | 编程/代码/算法/计算机 | ◈ |
| 写作 | `theme-write` | 写作/作文/论文/报告 | ✎ |
| 科学 | `theme-science` | 物理/化学/生物/实验 | ⚗ |
| 复习 | `theme-review` | 复习/总结/回顾/巩固 | ↻ |
| 默认 | `theme-default` | 其他 | ◆ |

**5 种动画**:

| 动画 | CSS keyframe | 触发 | 时长 | 效果 |
|------|-------------|------|------|------|
| 抽卡翻转 | `cardDrawOut` + `rotateY(180deg)` | `is-drawing` → `is-revealing` | 650ms | 从下方滑入 + 3D 翻转显正面 |
| 飞行动画 | `requestAnimationFrame` 逐帧 | `flyCardToResult()` | 600ms | 卡堆→屏幕上方→结果区 |
| 完成消散 | `completeDisappear` | `is-completing` / `is-evaporating` | 500ms | 淡出+缩小+旋转+阴影消失 |
| 弃牌飞走 | `flyToDiscard` | `is-discarding` | 500ms | 抛物线轨迹飞向弃牌区 |
| 跳过滑出 | `skipSlide` | `is-skipping` | 400ms | 向左滑出+旋转+淡出 |

---

## 4. API 接口完整清单

### 4.1 任务 CRUD (8 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET | `/api/tasks` | `?include_completed=&unlocked_only=` | `[{task}]` | 列表，支持过滤 |
| GET | `/api/tasks/<id>` | — | `{task}` | 详情 |
| POST | `/api/tasks` | `{name, category, ...}` | `{task}` | 创建 |
| PUT | `/api/tasks/<id>` | `{name, ...}` | `{task}` | 更新 |
| DELETE | `/api/tasks/<id>` | — | `{deleted: id}` | 删除（级联清理依赖） |
| POST | `/api/tasks/<id>/complete` | — | `{task}` | 完成（触发级联解锁） |
| POST | `/api/tasks/<id>/skip` | — | `{task}` | 跳过 |
| POST | `/api/tasks/<id>/refuse` | — | `{task}` | 拒绝 |

### 4.2 抽卡系统 (5 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| POST | `/api/gacha/draw` | `{pool, energy, available_time}` | `{task, can_replace}` | 抽一张卡 |
| POST | `/api/gacha/replace` | `{task_id}` | `{task}` | 换牌 |
| GET | `/api/gacha/pools` | — | `[{name, count}]` | 卡池信息 |
| GET | `/api/gacha/pools/detail` | — | `{pool: [tasks]}` | 池内任务列表 |
| GET | `/api/gacha/statistics` | — | `{total_draws, ...}` | 统计 |

### 4.3 弃牌堆 (2 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET | `/api/discard-pile` | — | `[{task}]` | 列表 |
| POST | `/api/discard-pile/<id>/restore` | — | `{task}` | 恢复 |

### 4.4 依赖系统 (2 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET | `/api/tasks/<id>/dependents` | — | `[{task}]` | 依赖该任务的任务 |
| GET | `/api/dependencies` | — | `{nodes, edges}` | 完整依赖图 |

### 4.5 标签管理 (3 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET | `/api/tags` | — | `[{id, name}]` | 标签列表 |
| POST | `/api/tags` | `{name}` | `{id}` | 创建标签 |
| POST | `/api/tags/batch` | `{task_ids, tag_ids}` | `{ok}` | 批量分配 |

### 4.6 日程系统 (4 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET `/api/schedule/slots` | — | 时间槽定义 |
| GET `/POST` | `/api/schedule/weekly` | 操作周日程 |
| GET `/POST` | `/api/schedule/daily` | 操作日日程 |
| GET `/POST` | `/api/schedule/activities` | 活动 CRUD |

### 4.7 状态系统 (7 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET `/POST` | `/api/state/daily-tone` | `{tone}` | 日间基调 |
| POST | `/api/state/energy` | `{period, level}` | 记录精力 |
| GET `/POST` | `/api/state/sleep` | `{bed_time}` | 睡眠追踪 |
| GET | `/api/state/weekly-energy` | — | 周能量趋势 |
| GET | `/api/state/questions` | — | 评估问题 |
| GET `/POST` | `/api/state/assessment` | `{answers}` | 状态评估 |
| GET | `/api/state/assessment/history` | — | 评估历史 |
| GET | `/api/state/assessment/correlate` | — | 相关性分析 |

### 4.8 计时器 (3 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| POST | `/api/timer/start` | `{task_id, planned_minutes}` | 开始计时 |
| POST | `/api/timer/complete` | `{result, reason}` | 结束计时 |
| GET | `/api/timer/active` | — | 活跃计时器 |

### 4.9 任务反馈 (2 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| POST | `/api/tasks/<id>/feedback` | `{energy, mood}` | 提交反馈 |
| GET | `/api/task-feedback` | — | 反馈列表 |
| POST | `/api/task-feedback` | `{task_id, event_type, reason}` | 创建反馈事件 |

### 4.10 提示词 (4 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET | `/api/prompts` | — | `[{name, size, modified}]` | 文件列表 |
| GET | `/api/prompts/<name>` | — | `{content}` | 读取内容 |
| PUT | `/api/prompts/<name>` | `{content}` | `{saved}` | 保存（自动备份） |
| POST | `/api/prompts/<name>/restore-latest` | — | `{restored}` | 恢复最新备份 |

### 4.11 智能体 (7 个)

| 方法 | 路径 | 参数 | 返回 | 说明 |
|------|------|------|------|------|
| GET | `/api/agent/agents` | — | `[{id, name, description}]` | Agent 列表 |
| GET | `/api/agent/agents/<id>/prompt` | — | `{content}` | 提示词内容 |
| GET | `/api/agent/files/raw` | — | `[{name, path}]` | 未分类文件 |
| GET | `/api/agent/files/vault` | — | `[{name, path}]` | Vault 文件 |
| GET | `/api/agent/files/raw/content` | `?path=` | `{content}` | 文件内容 |
| GET | `/api/agent/files/vault/content` | `?path=` | `{content}` | 文件内容 |
| POST | `/api/agent/process` | `{agent_id, input}` | `{output}` | 执行 Agent |

### 4.12 知识库 (7 个)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge/categories` | 学科分类 |
| GET | `/api/knowledge/points` | 知识点列表 |
| GET | `/api/knowledge/notes` | 笔记列表 |
| GET | `/api/knowledge/graph` | 知识图谱 |
| GET | `/api/knowledge/note-content/<path>` | 笔记内容 |
| GET | `/api/knowledge/point-detail/<subject>/<name>` | 知识点详情 |
| POST | `/api/knowledge/open-in-obsidian` | 在 Obsidian 打开 |

### 4.13 系统 (4 个)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取配置 |
| POST | `/api/config/save` | 保存配置 |
| GET | `/api/export` | 全量导出 |
| GET | `/api/health` | 健康检查 → `{"status":"healthy"}` |

---

## 5. 数据库设计

### 5.1 核心表结构

**tasks** (主表, 25+ 列):

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 任务 ID |
| name | TEXT | NOT NULL | 任务名称 |
| description | TEXT | | 描述 |
| category | TEXT | NOT NULL | 类别 (daily/weekly/flexible_ddl/accumulation) |
| estimated_time | INTEGER | | 预估分钟 |
| resistance | TEXT | | 阻力 (low/medium/high) |
| energy_required | TEXT | | 所需精力 (low/medium/high) |
| priority | INTEGER | DEFAULT 3 | 优先级 (1-5) |
| deadline | TEXT | | 截止日期 (ISO8601) |
| repeat_type | TEXT | | 重复类型 (none/daily/weekly/accumulation) |
| task_profile | TEXT | | 任务画像 |
| prerequisite_ids | TEXT | | 前置任务 ID JSON 数组 |
| is_unlocked | INTEGER | DEFAULT 1 | 是否解锁 |
| in_discard_pile | INTEGER | DEFAULT 0 | 是否在弃牌堆 |
| completed_count | INTEGER | DEFAULT 0 | 完成次数 |
| completed | INTEGER | DEFAULT 0 | 是否已完成 |
| draw_count_today | INTEGER | DEFAULT 0 | 今日被抽次数 |
| last_draw_date | TEXT | | 最后被抽日期 |
| success_rate | REAL | DEFAULT 0.5 | 成功率 |
| refusal_count | INTEGER | DEFAULT 0 | 拒绝次数 |
| created_at | TEXT | | 创建时间 |
| updated_at | TEXT | | 更新时间 |
| last_completed_at | TEXT | | 最后完成时间 |
| next_available_at | TEXT | | 下次可用时间 |
| tags | (关联) | | 通过 task_tags 关联 |

**task_dependencies**:

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| task_id | INTEGER | FK→tasks.id | 任务 |
| depends_on_task_id | INTEGER | FK→tasks.id | 依赖的前置任务 |

**tags / task_tags**:

| 表 | 列 | 说明 |
|----|-----|------|
| tags | id, name | 标签 |
| task_tags | task_id, tag_id | 多对多关联 |

**gacha_records**:

| 列名 | 说明 |
|------|------|
| id, task_id, pool, energy, drawn_at, replaced | 抽卡记录 |

**state_assessments**:

| 列名 | 说明 |
|------|------|
| id, date, answers, energy_score, focus_score, mood_score, daily_tone, formula_version | 每日评估 |

**timers**:

| 列名 | 说明 |
|------|------|
| id, task_id, started_at, ended_at, planned_minutes, actual_minutes, status, result | 计时器 |

**task_feedback_events** (红线表, 不可破坏):

| 列名 | 说明 |
|------|------|
| id, task_id, event_type, reason, created_at | 任务事件反馈 |

### 5.2 完整表列表

| 表名 | 用途 |
|------|------|
| tasks | 核心任务表 |
| tags | 标签 |
| task_tags | 任务-标签关联 |
| task_dependencies | 任务依赖关系 |
| task_completions | 完成记录 |
| task_completion_feedback | 完成反馈 (旧版) |
| task_feedback_events | 任务事件反馈 (红线) |
| task_rejection_log | 拒绝记录 |
| task_milestones | 里程碑 |
| gacha_records | 抽卡记录 |
| daily_user_state | 每日状态 |
| daily_schedules | 日日程 |
| user_schedule | 周日程 |
| weekly_schedule | 周日程 (旧) |
| daily_schedule | 日日程 (旧) |
| activities | 活动列表 |
| activity_options | 活动选项 |
| rest_days | 休息日 |
| state_assessments | 状态评估 |
| timer_sessions | 计时器会话 |
| user_state / user_states | 用户状态 |
| user_health_profile | 健康档案 |
| user_profile | 用户档案 |
| time_currency | 时间货币 |
| time_logs | 时间日志 |
| formula_weights | 加权公式参数 |
| ai_analysis_imports | AI 导入记录 |
| schedule_slots | 时间槽定义 |
| _meta | 元数据 |

---

## 6. 门禁系统

### 6.1 check_portability.py (核心检测器)

**7 大检查项**:

| # | 检查项 | 函数 | 说明 |
|---|--------|------|------|
| 1 | 项目结构 | `check_required_paths()` | 9 个关键文件/目录是否存在 |
| 2 | 配置检查 | `check_config()` | config.json 可读性 + 路径可移植性 |
| 3 | 前端引用 | `check_index_app_js()` | index.html 是否正确引用 app.js |
| 4 | Bat 脚本锚定 | `check_bat_relative()` | 所有 bat 是否使用 `%~dp0` |
| 5 | 环境检查 | `check_venv_validity()` | .venv python.exe 可用性 |
| 5b | Python 版本 | `check_python_version()` | >= 3.8 |
| 5c | Python 来源 | `check_python_source()` | 嵌入式 Python 状态 |
| 6 | 依赖检查 | `check_requirements()` | requirements-web.txt 包是否可导入 |
| 7 | 后端检查 | `check_backend_entry()` | backend_api.py 存在 + 语法检查 |
| 8 | 路径扫描 | `scan_absolute_paths()` | 10 种绝对路径模式检测 |

**退出码**:

| 码 | 含义 | 触发条件 |
|----|------|----------|
| 0 | PASS | 无 BLOCKER, 无 WARN |
| 1 | FAIL | 存在任意 BLOCKER |
| 2 | PASS_WITH_WARNINGS | 仅存在 WARN/INFO |

### 6.2 run_stable_acceptance.bat (硬门禁)

```
流程:
1. .venv 存在性检查 → 不存在则中止
2. GATE CHECK → run check_portability.py
3. BLOCKER → 中止 (exit 1)
4. PASS_WITH_WARNINGS → 警告继续
5. PASS → 继续
6. 依次执行 21 个 acceptance/E2E 测试脚本
```

### 6.3 start_web_safe.bat (软门禁)

```
流程:
1. .venv 存在 → 使用
2. .python/python.exe 存在 → 创建 .venv
3. 系统 Python → 创建 .venv
4. 都没有 → 提示下载嵌入式 Python
5. PREFLIGHT CHECK → run check_portability.py
6. BLOCKER → 阻止启动 (pause + exit 1)
7. PASS_WITH_WARNINGS → 提示继续
8. 安装依赖 → 启动服务器 → 健康检查 → 打开浏览器
```

---

## 7. 可移植性设计

### 7.1 内置 Python

`.python/` 目录包含 Python 3.11.9 嵌入式发行版:

| 文件 | 用途 |
|------|------|
| `python.exe` | 解释器 (3.11.9) |
| `python311.zip` | 标准库压缩包 |
| `python311._pth` | 已启用 `import site` |
| `*.pyd` / `*.dll` | 扩展模块 (含 sqlite3, ssl) |

### 7.2 启动优先级

```
1. 已有 .venv/Scripts/python.exe → 直接使用
2. .python/python.exe → 用它创建 .venv
3. 系统 py -3 / python → 创建 .venv
4. 都没有 → 提示运行 scripts/download_python.bat
```

### 7.3 换机步骤

```
1. 解压 zip 到任意位置
2. （如无 Python）双击 scripts/download_python.bat
3. 双击 启动学习工具.bat
4. 浏览器自动打开 http://localhost:5000
```

### 7.4 路径策略

- 所有脚本使用 `Path(__file__).resolve().parent` 定位项目根
- 配置文件使用相对路径
- 禁止硬编码盘符/用户名

---

## 8. 前端架构

### 8.1 单页应用结构

`index.html` 包含 5 个标签页:

| 标签 | ID | 说明 |
|------|-----|------|
| 抽卡 | `page-gacha` | 精力选择、卡池选择、抽卡按钮、结果显示 |
| 任务 | `page-tasks` | 任务列表、搜索、标签过滤、弃牌堆入口 |
| 日程 | `page-schedule` | 日期导航、时间槽网格、睡眠/评估 |
| 知识库 | `page-knowledge` | 分类浏览、笔记预览、Obsidian 打开 |
| 设置 | `page-config` | 服务器配置、API Key、提示词编辑器 |

### 8.2 核心函数列表 (app.js)

**抽卡模块**:

| 函数 | 行号 | 说明 |
|------|------|------|
| `drawGacha()` | 392 | 主抽卡流程 |
| `renderDrawnCard()` | 508+ | 创建翻转卡 DOM |
| `flyCardToResult()` | 424 | rAF 飞行动画 |
| `handleReplace()` | 565+ | 换牌逻辑 |
| `refreshGachaStats()` | 571+ | 刷新卡池统计 |

**任务操作**:

| 函数 | 说明 |
|------|------|
| `completeWithFeedback()` | 完成任务 + 收集反馈 |
| `handleSkip()` | 跳过任务 |
| `handleRefuse()` | 拒绝任务 |
| `moveToDiscard()` | 移入弃牌堆 |
| `restoreFromDiscard()` | 恢复任务 |

**动画系统**:

| 函数 | 说明 |
|------|------|
| `playCardAnim()` | 通用动画触发器 (add class → setTimeout → remove) |
| `flyCardToResult()` | rAF 逐帧飞行 (left/top 插值) |
| CSS 类: `.is-drawing` / `.is-revealing` | 翻转动画 |
| CSS 类: `.is-completing` / `.is-evaporating` | 完成消散 |
| CSS 类: `.is-discarding` | 弃牌飞走 |
| CSS 类: `.is-skipping` | 跳过滑出 |

**状态管理**:

| 变量 | 说明 |
|------|------|
| `gachaState` | `{energy, pool, canReplace, replacedTaskId, feedbackMood}` |
| 全局访问 | 通过 `api()` 函数实时查询，无需前端缓存 |

### 8.3 卡牌 DOM 结构

```
div.drawn-card-stage
  div.task-card.card.drawn-card (data-task-id)
    div.task-card-inner
      div.task-card-face.task-card-back     ← 卡背 (图案+徽章)
        div.card-back-pattern                ← 菱形纹理
        div.card-back-emblem                 ← ✦ 金色徽章
      div.task-card-face.task-card-front    ← 卡片正面
        span.task-card-ornament              ← 四角装饰
        div.task-card-header                 ← 标题栏
        div.task-card-body-zone              ← 任务内容
        div.task-card-footer                 ← 操作按钮
```

---

## 9. 配置文件说明

### 9.1 config.json 结构

```json
{
    "server": {
        "port": 5000,
        "host": "0.0.0.0",
        "debug": false
    },
    "obsidian": {
        "vault_path": "src/notes/vault",
        "notes_directory": "src/notes/vault"
    },
    "api": {
        "openai_api_key": "",
        "claude_api_key": "",
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini"
    },
    "database": {
        "task_db_path": "data/task_publisher.db"
    }
}
```

### 9.2 可配置项

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `server.port` | 5000 | Flask 监听端口 |
| `server.host` | 0.0.0.0 | 绑定地址 |
| `obsidian.vault_path` | src/notes/vault | Obsidian Vault 路径 |
| `database.task_db_path` | data/task_publisher.db | 数据库路径 |
| `api.openai_api_key` | "" | OpenAI API Key (Web 界面可设置) |
| `api.model` | gpt-4o-mini | LLM 模型 |

> **注意**: `config/config.json` 包含密钥，已加入 `.gitignore`。模板文件: `config/config.example.json`

---

## 10. 开发与调试

### 10.1 启动项目

```bat
# 方式 1: 一键启动
双击: 启动学习工具.bat

# 方式 2: 命令行
.venv\Scripts\python.exe server\backend_api.py
```

浏览器访问: `http://localhost:5000`

### 10.2 运行门禁

```bat
.venv\Scripts\python.exe scripts\check_portability.py
```

预期: `VERDICT: PASS` (退出码 0)

### 10.3 运行验收测试

```bat
# 全量回归
scripts\run_stable_acceptance.bat

# 单独测试
.venv\Scripts\python.exe scripts\p0_acceptance_http.py
.venv\Scripts\python.exe scripts\p1_2_e2e_prompt_sleep.py
```

### 10.4 外部 AI 协作改任务

```bat
# 1. 导出快照
.venv\Scripts\python.exe scripts\export_tasks_for_ai.py

# 2. 将 ai_workspace/00_context/ 内容发给网页 AI
# 3. AI 输出 task_patch.json → 放到 ai_workspace/03_task_drafts/

# 4. 校验格式
.venv\Scripts\python.exe scripts\validate_task_patch.py

# 5. 人工在 Web"任务"页逐条修改
# 6. 备份
scripts\backup_user_data.bat
```

### 10.5 常见问题

| 问题 | 解决方案 |
|------|----------|
| 页面打不开 | 先 `scripts\stop_web_safe.bat` 再重启 |
| `/api/health` 不通 | 确认端口未被占用, 查看 `.run\server.log` |
| `.venv` 损坏 | 删除 `.venv`, 重跑 `启动学习工具.bat` |
| SQLite 锁 | 关闭所有浏览器窗口, 重启服务 |
| 换电脑跑不起来 | 不要复制 `.venv`, 在新电脑双击 `启动学习工具.bat` |
| 抽卡无结果 | 检查 DB 中是否有未完成的任务 |

---

## 11. 已知待解决问题

### 11.1 待修复

| ID | 问题 | 影响 | 建议 |
|----|------|------|------|
| P1-ANIM-001 | 抽卡飞行动画与最终卡片未完全复用同一 DOM 元素 | 飞行结束后有短暂闪烁 | 统一卡片元素创建流程 |
| P1-TOOLS-001 | 30+ 工具脚本旧路径已失效 | 工具脚本不可用 | 仅 `extract_clips.py` 等少数脚本已修复 |
| P1-CONFIG-001 | `config.json` gitignored 后新环境需手动创建 | 首次启动可能报错 | 已提供 `config.example.json` 模板 |

### 11.2 暂不进入

| 阶段 | 原因 |
|------|------|
| P1-7 (Agent 受控执行) | 需先确定 API Key 安全策略和 vault 写入权限 |
| P2 (番茄钟深度/任务拆解/多端同步) | 等待产品经理决策 |

---

## 12. 代码规范

### 12.1 Python 后端

- **单文件架构**: `server/backend_api.py` (当前, 未来可拆分)
- **路径**: 使用 `os.path.join(os.path.dirname(__file__), ...)` 动态定位
- **配置**: 从 `config/config.json` 加载, 所有路径保持相对
- **DB 操作**: 通过 `get_db_connection()` 获取连接, 使用 `row_factory`
- **迁移**: `ensure_*_schema()` 系列函数, 幂等, 只增不改

### 12.2 JavaScript 前端

- **文件**: 业务逻辑在 `static/app.js`, 不在 `index.html` 内联
- **API 调用**: 统一使用 `api()` 函数 (fetch 封装)
- **动画**: 使用 CSS class toggling + `requestAnimationFrame`
- **命名**: camelCase 函数, snake_case 后端变量
- **DOM**: 通过 ID/class 选择, 动态创建元素

### 12.3 提交信息格式

```
<type>: <简短描述>

type: feat / fix / refactor / chore / debug / docs
```

示例:
```
feat: 添加抽卡飞行动画
fix: 飞行动画改用left/top transition
chore: 初始提交 - 项目恢复自 stable 备份
```

---

> **文档版本**: 1.0 | **生成时间**: 2026-06-05 | **下次审查**: P2 阶段启动前
