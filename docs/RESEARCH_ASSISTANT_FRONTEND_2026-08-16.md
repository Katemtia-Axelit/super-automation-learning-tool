# 摸底报告：超级自动化学习工具 → 升格「个人助理前端」

> 调研时间：2026-08-16  
> 调研人：Cursor AI（代码实测版，非 README 照抄）  
> 落盘路径：`docs/RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md`  
> 依据：所有结论均引用文件路径/行号/API 名/配置字段，不编造。

---

## 第一趴：学习工具现状摸底

### 1.1 后端 API 面（`server/backend_api.py`，Flask，端口 5000）

#### 路由清单（按功能域分组）

**健康检查**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/health` | GET | 返回 `{status: "healthy"}` 供前端连接状态指示 |

**任务 CRUD**（证据：`backend_api.py` 行 1292-1425）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/tasks` | GET | 列表，含 `include_completed`、`unlocked_only` 参数 |
| `/api/tasks` | POST | 创建，`Task` 对象输入（名称/类别/阻力/精力/优先级/标签/依赖等 30+ 字段） |
| `/api/tasks/<id>` | GET | 单条，含 tags 附加 |
| `/api/tasks/<id>` | PUT | 更新，含 `prerequisite_ids` 级联更新 + `is_unlocked` 重算 |
| `/api/tasks/<id>` | DELETE | 删除，清理 `task_dependencies` + 重算下游 `is_unlocked`（行 894-950） |
| `/api/tasks/<id>/dependents` | GET | 查依赖此任务的下游 |
| `/api/tasks/<id>/complete` | POST | 完成，含成功率提升 |
| `/api/tasks/<id>/skip` | POST | 跳过 |
| `/api/tasks/<id>/refuse` | POST | 拒绝 |
| `/api/tasks/<id>/move-to-discard` | POST | 移入弃牌堆 |
| `/api/tasks/<id>/feedback` | POST | 任务级反馈 |

**抽卡系统**（证据：`backend_api.py` 行 1469-2490）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/gacha/pools` | GET | 碎片/番茄/深度三大卡池元信息 |
| `/api/gacha/pools/detail` | GET | 卡池详细（含各池任务数/今日抽数/统计） |
| `/api/gacha/draw` | POST | 抽卡核心：时间约束 + 优先级评分 + 难度过滤 |
| `/api/gacha/care-draw` | POST | 关怀换牌抽（不扣次数） |
| `/api/gacha/replace` | POST | 替换抽（每日1次，选择原因） |
| `/api/gacha/statistics` | GET | 今日统计（抽数/接受率/拒绝数） |

**弃牌堆**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/discard-pile` | GET | 当前弃牌堆列表 |
| `/api/discard-pile/<id>/restore` | POST | 恢复 |

**标签系统**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/tags` | GET | 全标签列表 |
| `/api/tags` | POST | 创建标签 |
| `/api/tags/<id>` | DELETE | 删除标签（级联删除 task_tags） |
| `/api/tags/batch` | POST | 批量分配标签给多个任务 |

**依赖/导出**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/dependencies` | GET | 全量依赖关系图（任务 ID → 依赖 ID[]） |
| `/api/export` | GET | 完整系统状态快照（任务+标签+依赖+时间记录） |

**日程系统**（证据：`backend_api.py` 行 2046-2217）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/schedule/slots` | GET | 时间槽列表（固定槽位） |
| `/api/schedule/weekly` | GET/POST | 周日程模板 |
| `/api/schedule/daily` | GET/POST | 单日日程 |
| `/api/schedule/activities` | GET/POST/DELETE | 活动 CRUD |

**状态追踪**（证据：`backend_api.py` 行 2217-2420）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/state/daily-tone` | GET/POST | 今日基调（normal/energetic/tired/relaxed） |
| `/api/state/energy` | POST | 记录精力（morning/afternoon/evening 三个时间点） |
| `/api/state/sleep` | GET/POST | 睡眠记录（入睡时间 + 早起连续天数） |
| `/api/state/weekly-energy` | GET | 近7日精力表 |
| `/api/state/assessment` | GET/POST | 今日状态评估问卷（能量/专注/情绪） |
| `/api/state/assessment/history` | GET | 近7日评估历史 |
| `/api/state/assessment/questions` | GET | 评估问题列表 |
| `/api/state/assessment/correlate` | GET | 评估与行为相关性 |

**计时器系统**（证据：`backend_api.py` 行 3001-3192）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/timer/start` | POST | 启动计时（任务ID + 计划时长） |
| `/api/timer/complete` | POST | 完成计时（实际时长 + 结果） |
| `/api/timer/active` | GET | 当前进行中的计时 |
| `/api/timer/pause` | POST | 暂停（含 `paused_seconds` 持久化） |
| `/api/timer/resume` | POST | 恢复 |

**任务反馈事件**（证据：`backend_api.py` 行 2329-2410）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/task-feedback` | POST/GET | 事件级反馈记录 |

**知识库**（证据：`backend_api.py` 行 1558-1910）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/knowledge/categories` | GET | 学科分类树 |
| `/api/knowledge/points` | GET | 知识点列表 |
| `/api/knowledge/graph` | GET | 知识图谱（节点+边） |
| `/api/knowledge/note/<path>` | GET | 笔记内容（自动 Markdown 渲染） |
| `/api/knowledge/note-content/<path>` | GET | 笔记原始内容 |
| `/api/knowledge/recent` | GET | 最近浏览 |
| `/api/knowledge/notes` | GET | 笔记列表（按分类） |
| `/api/knowledge/point-detail/<subject>/<point>` | GET | 知识点详情 |
| `/api/knowledge/open-in-obsidian` | POST | 调用 Obsidian URI 打开笔记 |

**配置**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/config` | GET | 读配置 |
| `/api/config/save` | POST | 写配置 |

**提示词管理**
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/prompts` | GET | 提示词文件列表 |
| `/api/prompts/<name>` | GET/PUT | 读/写提示词（含自动备份） |
| `/api/prompts/<name>/backup/latest` | GET | 最新备份内容 |
| `/api/prompts/<name>/restore-latest` | POST | 从备份恢复 |

**Agent 只读浏览**（证据：`backend_api.py` 行 2660-3001）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/agent/agents` | GET | Agent 列表（从 workspace 目录扫描） |
| `/api/agent/agents/<id>/prompt` | GET | Agent 系统提示词 |
| `/api/agent/files/raw` | GET | Raw 文件列表 |
| `/api/agent/files/vault` | GET | Vault 文件列表 |
| `/api/agent/files/raw/content` | GET | Raw 文件内容 |
| `/api/agent/files/vault/content` | GET | Vault 文件内容 |
| `/api/agent/process` | POST | 进程 Agent 请求 |
| `/api/agent/save-note` | POST | 保存笔记到 vault |
| `/api/agent/import-tasks` | POST | 从笔记导入任务 |

**入口**
| 端点 | 方法 | 用途 |
|------|------|------|
| `GET /` | — | 返回 `src/index.html`（Flask static） |

#### 核心数据模型（证据：`backend_api.py` 行 63-238 + SQLite schema 查询结果）

**`tasks` 表**（核心，532行数据）
主要字段：
- `id, name, category, description, estimated_time, deadline`（基础）
- `resistance, energy_required, priority, difficulty`（元信息）
- `rarity, success_rate, refusal_count`（抽卡用）
- `is_daily, completed, completed_count`（生命周期）
- `repeat_type`（none/daily/weekly/accumulation）
- `task_profile`（deadline_flexible/deadline_progressive/daily_habit/weekly_routine）
- `prerequisite_ids`（JSON 数组，缓存用）
- `is_unlocked`（0/1，前置依赖均完成=1）
- `in_discard_pile`（0/1）
- `linked_note_path`（关联 Obsidian 笔记）
- `tags`（JSON 数组）
- `created_at, updated_at, last_completed_at, next_available_at, last_drawn_at`

**`task_dependencies` 表**（规范存储，507行数据）
- `task_id → depends_on_task_id` 双向记录
- 用于循环依赖检测（`detect_cycle`，行 552-584）和级联解锁（`chain_unlock`，行 969-1016）

**`task_tags` 表**（912行数据）+ `tags` 表（44行）
- many-to-many 关联

**`gacha_records` 表**（0行，待抽卡历史）
- `pool_name, available_time, task_id, accepted, refusal_reason`

**`timer_sessions` 表**（167行数据）
- `task_id, started_at, ended_at, planned_minutes, actual_minutes`
- `status`（running/paused/completed）
- `result`（completed/unfinished/abandoned）
- `reason, notes`
- `paused_seconds`（累计暂停时长）

**`task_feedback_events` 表**（8行数据）
- `task_id, event_type, planned_minutes, actual_minutes, completion_status`
- `reason_category, reason_detail, note`

**`state_assessments` 表**（3行数据）
- `date, answers(JSON), energy_score, focus_score, mood_score, daily_tone`

**`daily_user_state` 表**（11行数据）
- `date, daily_tone, energy_morning/afternoon/evening, bed_time, sleep_early_streak`

**`user_schedule` + `daily_schedules` + `activities` 表**（0行，框架存在但无数据）

**`time_currency` + `time_logs` 表**（0行，未启用）

**`task_milestones` + `task_completions` + `task_rejection_log` 表**（0行，遗留）

**`user_states` 表**（0行，遗留）

---

### 1.2 前端结构（`src/index.html` + `static/app.js`）

#### 页面结构（5大功能区）

**导航栏**（`index.html` 行 497-508）
```
[学习工具] [抽卡] [任务] [日程] [知识库] [设置] [●连接状态]
```

**`gacha` 页面**（行 511-566）
- 牌堆视觉（5张牌的堆叠动画，`card-deck`，CSS 行 190-206）
- 主抽卡按钮（64×64px 圆形，`gacha-main-btn`，CSS 行 175-184）
- 弃牌堆缩略（行 521-526）
- 计时器 Dock（常驻右下角，行 532-543）
- 卡牌缩放滑块（行 528-531）
- 抽卡统计栏（今日已抽/接受率/拒绝，行 560-564）
- 标签选择 + 可用时间输入（行 546-559）

**`tasks` 页面**（行 568-598）
- 工具栏：新建/搜索/筛选/批量标签/依赖图/弃牌堆
- 计时器面板（第二套，行 584-595）
- 标签筛选栏（行 596）
- 任务卡片网格（`task-grid`，行 597）

**`schedule` 页面**（行 600-635）
- 睡眠追踪面板（行 601-614）
- 近7日能量表（行 615-616）
- 状态评估面板（行 618-626）
- 日程导航 + 时间槽格（行 628-634）
- 活动管理（行 632，弹窗）

**`knowledge` 页面**（行 637-653）
- 左侧：学科分类 + 笔记列表
- 右侧：笔记渲染区（`md-content` 样式，行 276-285）
- Obsidian 打开按钮

**`config` 页面**（行 655-701）
- 服务器配置（端口/笔记目录/vault路径）
- AI 接口配置（API Key/Base URL/模型）
- 提示词文件浏览（只读+编辑模式+备份/恢复）
- Agent 只读浏览入口

#### `app.js` 模块划分（`static/app.js`，约 2811 行）

| 模块 | 行 | 职责 |
|------|-----|------|
| 全局错误捕获 + API Client | 4-31 | fetch 封装、toast、全局异常 |
| 温情文案库 | 44-54 | 任务完成关怀文案 |
| 任务事件反馈 | 55-157 | 简化的 feedback 事件机制 |
| 页面切换 + 导航 | 159-256 | `showPage()` + 导航事件 + 健康检查 |
| 卡牌主题 + 动画 | 255-360 | 主题色（math/lang/history/code/write等）+ 动画类 |
| 抽卡模块 | 360-1050 | 标签选择/抽卡流程/卡牌飞行动画/关怀问询 |
| 计时器 Dock | 404-591 | 主页面常驻计时器（`timer-dock`） |
| 任务管理 | 1206-1646 | CRUD/筛选/弃牌堆/依赖图/批量标签 |
| 日程 | 1646-1768 | 渲染/编辑槽/活动管理 |
| 知识库 | 1768-1895 | 分类/笔记列表/Markdown渲染/Obsidian打开 |
| 配置 + Agent只读 | 1895-2150 | 配置读写/prompt浏览 |
| 睡眠/状态评估 | 2391-2560 | 睡眠面板 + 问卷 + 历史 |
| 计时器面板 | 2632-2820 | 第二套计时器（独立于Dock） |

---

### 1.3 现状短板识别（mock/半成品/遗留）

**明确遗留/半成品：**

1. **`serve_static.py`**（证据：`README.md` 行 15）——遗留静态服务壳，基本无逻辑。Flask 主服务已由 `backend_api.py` 的 `app = Flask(__name__, static_folder=_STATIC_DIR, static_url_path='/static')` 替代。

2. **`src/tasks/` 桌面端 PySide6 领域层**（证据：`README.md` 行 18-22）——已不再主用，但代码仍存。

3. **`static/test.js`**（证据：`README.md` 行 33）——历史探测脚本，失效，可清理。

4. **`src/index.html` 的 Agent 只读浏览**（行 696-701 + `app.js` 行 1896-2150）——**目前仅支持只读浏览**，`/api/agent/process` 虽然存在但前端无实际调用入口（证据：grep 搜索 `api_agent_process` 在 app.js 中无实际调用）。

5. **`daily_schedules`/`user_schedule`/`activities` 三表均 0 行数据**（证据：SQLite 查询）——日程功能框架完整但无实际数据，**可能是未来扩展方向**。

6. **`time_currency`/`time_logs` 表**（0行）——未启用，可能是早期设计遗留。

7. **`task_milestones`/`task_completions`/`task_rejection_log`/`user_states` 表**（均为0行）——历史遗留表，未使用。

8. **提示词编辑模式**（`app.js` 行 2213-2370）——有 diff 预览和备份恢复功能，但实际使用率未知（证据：无 `promptContentView` 的实际调用日志）。

9. **依赖图**（`app.js` 行 1614-1646，`openDepGraph`）——存在但可能为半成品（需进一步验证功能完整性）。

10. **HUD**（在 app.js 中未找到 `hud` 相关代码）——可能已移除或未实现。

---

### 1.4 配置（`config/config.json`）

```json
{
  "server": { "port": 5000, "host": "0.0.0.0", "debug": false },
  "obsidian": { "vault_path": "src/notes/vault", "notes_directory": "src/notes/vault" },
  "api": { "openai_api_key": "", "claude_api_key": "", "api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini" },
  "database": { "task_db_path": "data/task_publisher.db" }
}
```

**关键发现：** 所有 API Key 均为空字符串——系统目前**未连接任何外部 LLM**。

---

## 第二趴：OpenClaw 可对接能力摸底

### 2.1 嵌入机制：Control UI Hosted Embeds（证据：`control-ui.md` 行 326-354）

OpenClaw Control UI 支持**托管嵌入**（Hosted Embeds），通过 `[embed]` shortcode 在 Assistant 消息中内嵌网页内容：

#### iframe sandbox 策略（`gateway.controlUi.embedSandbox`）

| 模式 | 说明 |
|------|------|
| `strict` | 完全禁用脚本执行 |
| `scripts`（默认） | 允许交互嵌入，保持 origin 隔离，适合自包含游戏/控件 |
| `trusted` | 在 `scripts` 基础上额外加 `allow-same-origin`，用于需要更强权限的同站文档 |

配置示例（`control-ui.md` 行 343-350）：
```json5
{
  gateway: {
    controlUi: {
      embedSandbox: "scripts",
    },
  },
}
```

#### 外部 URL 嵌入许可（`gateway.controlUi.allowExternalEmbedUrls`）

默认状态下，绝对外部 `http(s)://` URL 的 `[embed]` 被阻止。若需加载第三方页面：
```json5
{ gateway: { controlUi: { allowExternalEmbedUrls: true } } }
```

#### `[embed]` shortcode 语法

证据：`reference/rich-output-protocol.md` 行 49-66——在 assistant 消息中渲染时，web UI 将 shortcode 替换为 iframe。URL 格式：
```json
{ "url": "/__openclaw__/canvas/documents/cv_123/index.html" }
```

#### Canvas Host 服务（证据：`platforms/ios.md` 行 218 + `network.md` 行 22）

Gateway 在同一端口（默认 18789）提供 canvas 服务：
- `/__openclaw__/canvas/` —— 托管 HTML/JS 内容的服务路径
- `/__openclaw__/a2ui/` —— 另一 UI 路径

#### 学习工具前端嵌入 OpenClaw 的可行路径

**路径一：通过 `[embed]` shortcode 嵌入学习工具页面**
- 在 OpenClaw 对话中输入 `[embed url="http://127.0.0.1:5000/"]`
- 若 `embedSandbox: "scripts"`，学习工具前端可在 iframe 内运行（但需注意 origin 隔离限制）
- 学习工具的 JS（抽卡/计时器等）正常执行
- 问题：Cookie/Session 跨 origin 无法共享，学习工具的 `fetch('/api/...')` 正常（同 origin）

**路径二：让学习工具成为 OpenClaw 的 canvas 内容**
- 将学习工具的某个页面构建为可嵌入的 HTML（如 `/app/embeddable.html`）
- 通过 OpenClaw 的 canvas host 提供：`/__openclaw__/canvas/learning-tool/`
- 或通过 `openclaw-weixin` 通道等间接接入

**路径三：双端同屏（推荐）**
- OpenClaw Control UI 提供 Split View（`control-ui.md` 行 249-251）——可在同一界面左侧 Chat、右侧知识库/工具面板
- 学习工具以独立页面存在，通过 OpenClaw 的 iframe 嵌入或超链接导航
- 这是**最干净**的整合方式：**不把学习工具塞进 OpenClaw，而是让 OpenClaw 的 Chat 作为主入口，右侧 panel/新建 tab 展示学习工具内容**

**嵌入结论：** 学习工具前端（Flask :5000）**完全可以**作为 OpenClaw Control UI 的 iframe 嵌入目标，但建议：
1. 设置 `embedSandbox: "scripts"`（默认）
2. 学习工具前端需支持**无 Cookie 环境**下的正常 API 调用（已满足，因为 `fetch('/api/...')` 不依赖 cookie）
3. 优先使用 Split View 方案（路径三），而非深度 iframe 嵌入

---

### 2.2 能力面：Memory（记忆系统）

#### 机制（证据：`memory.md`）

**文件结构（`~/.openclaw/workspace/`）**
- `MEMORY.md` —— 长期记忆，持久事实/偏好/决策，会话启动时加载
- `memory/YYYY-MM-DD.md` —— 每日笔记，详细上下文，可被 `memory_search` 索引
- `DREAMS.md` —— 梦境日记，用于人工复审

**记忆工具**
- `memory_search` —— 语义搜索（混合向量+关键词）
- `memory_get` —— 读取指定记忆文件

**记忆后端**
- Builtin（默认，SQLite）
- QMD（本地优先侧车 + reranking）
- Honcho（AI 原生跨会话记忆）
- LanceDB（插件）
- Wiki（插件，将记忆编译为知识库）

**Dreaming**（可选后台整合）
- 启用后自动管理一个 cron 任务做整夜梦想清理
- 从短期 recall 中提升qualified项目到 `MEMORY.md`
- 评审输出写入 `DREAMS.md`

#### 与学习工具的关联
- **强关联**：OpenClaw 的 `MEMORY.md` 可记录学习偏好（精力低谷时间段、任务类别偏好、学习节奏等），供学习工具抽卡算法参考
- **实现路径**：OpenClaw Agent 在 `MEMORY.md` 写入偏好，学习工具后端通过文件系统直接读取 `MEMORY.md` 内容，或通过 Gateway RPC 暴露
- **注意**：当前 `backend_api.py` 无 Memory 读取能力，需扩展

---

### 2.3 能力面：Automation（自动化）

#### 调度任务 Cron（证据：`cron-jobs.md`）

| 特性 | 详情 |
|------|------|
| 执行方式 | Gateway 进程内运行，不是模型内 |
| 持久化 | SQLite（`~/.openclaw/` 下），重启不丢失 |
| 任务记录 | 每次执行创建 background task 记录 |
| 执行风格 | main session / isolated / current / custom session |
| 投递模式 | announce（回话）/ webhook / none |

**Payload 类型**
- System event —— 进入主会话，无模型调用
- Agent message —— 模型支持回合
- Command —— Gateway 主机 shell 脚本（无模型调用）

**Webhook 投递**
```bash
curl -X POST http://127.0.0.1:18789/hooks/wake \
  -H 'Authorization: Bearer SECRET' \
  -d '{"text":"New email received","mode":"now"}'
```

#### Heartbeat（证据：`gateway/heartbeat.md`）

**机制**：每 30 分钟（可配置）在主会话中运行一个 agent turn，批量检查（inbox/calendar/notifications）

**配置**（当前本机配置，行 14-19）：
```json
"heartbeat": {
  "every": "30m",
  "lightContext": true,        // 只注入 HEARTBEAT.md
  "isolatedSession": true,     // 独立会话（无对话历史）
  "skipWhenBusy": true         // 有其他工作时跳过
}
```

**HEARTBEAT.md**：位于 agent workspace，可包含结构化 `tasks:` 块（`heartbeat.md` 行 416-429）：
```md
tasks:
- name: inbox-triage
  interval: 30m
  prompt: "Check for urgent unread emails and flag anything time sensitive."
```

#### Hooks（证据：`automation/hooks.md`）

事件驱动脚本，触发时机：
- `/new` / `/reset` / `/stop`
- Session compaction
- Gateway 启动
- 消息流

#### Task Flow（证据：`automation/taskflow.md`）

多步流的编排子层，管理 durable 多步流，支持 managed/mirrored sync 模式 + revision tracking。

#### 与学习工具的关联
- **Cron 可驱动学习工具任务**：通过 webhook 调用学习工具的 Flask API（`/api/tasks/POST`）创建每日任务
- **Heartbeat 可整合 inbox/calendar**：OpenClaw 的 `HEARTBEAT.md` 检查可注入到学习工具的日程系统
- **当前本机**：`heartbeat` 已配置但无 `HEARTBEAT.md` 文件——需创建并指向学习工具 API

---

### 2.4 能力面：Webhooks

#### Webhooks Plugin（证据：`plugins/webhooks.md`）

HTTP 认证路由，允许外部系统（Zapier/n8n/CI）通过 HTTP 创建和管理 OpenClaw TaskFlow。

**路由配置**：
```json5
plugins.entries.webhooks.config.routes = {
  myroute: {
    path: "/plugins/webhooks/myroute",
    sessionKey: "agent:main:main",
    secret: { source: "env", id: "OPENCLAW_WEBHOOK_SECRET" },
  }
}
```

**安全模型**：
- 每个路由以绑定 session 的 TaskFlow 权限运行
- 强 secret + 固定窗口限流（120 req/60s）+ 并发限制（8 concurrent/path）

**Webhook 触发 OpenClaw Agent 方式**（`cron-jobs.md` 行 392-449）：
```bash
curl -X POST http://127.0.0.1:18789/hooks/agent \
  -H 'Authorization: Bearer SECRET' \
  -d '{"message":"Summarize inbox","name":"Email","model":"openai/gpt-5.6"}'
```

#### Gateway Hooks（`hooks.*` 配置，证据：`cron-jobs.md` 行 391-462）

Gateway 可暴露 HTTP webhook 端点：

| 端点 | 用途 |
|------|------|
| `POST /hooks/wake` | 为主会话入队 system event |
| `POST /hooks/agent` | 运行隔离 agent turn |
| `POST /hooks/<name>` | 自定义映射 |

#### 与学习工具的关联
- 学习工具后端（Flask :5000）可通过 `curl` 调用 `http://127.0.0.1:18789/hooks/agent` 触发 OpenClaw 执行任务（如"处理未读邮件"）
- 学习工具也可通过 `/hooks/wake` 唤醒 OpenClaw 主会话

---

### 2.5 能力面：Workboard（看板）

证据：`plugins/workboard.md` + `plugins/reference/workboard.md`

**性质**：可选 Kanban 风格看板，绑定 Control UI（Dashboard）

**卡片状态**：`triage` / `backlog` / `todo` / `scheduled` / `ready` / `running` / `review` / `blocked` / `done`

**Agent 工具**（约 30+ 工具）：
- `workboard_list` / `workboard_read` / `workboard_create`
- `workboard_claim` / `workboard_heartbeat` / `workboard_release`
- `workboard_complete` / `workboard_block`
- `workboard_link`（父子卡依赖链）
- `workboard_decompose`（父卡分解为子卡）
- `workboard_notify_*`（订阅/推送通知）
- 等

**存储**：插件自有的 SQLite（`workboard.cards` 等命名空间）

**当前本机**：已启用（`config.json` 行 112-113：`workboard: { enabled: true }`）

#### 与学习工具的关联
- **强互补**：学习工具的"任务"（tasks 表）与 OpenClaw Workboard 的"卡片"（cards）是不同抽象层
  - 学习工具任务 = 个人学习任务（教育向）
  - Workboard 卡片 = Agent 工作追踪（操作向）
- **整合建议**：学习工具可把 Agent 产生的任务同步到 Workboard，或反过来把 Workboard 的卡片同步为学习工具任务
- **需 API 层桥接**：当前两个系统独立，需要一个桥接服务同步数据

---

### 2.6 能力面：Channels（通道）现状

#### 已安装通道（`C:\Users\wn\.openclaw\openclaw.json` 行 158-161）
```json
"channels": {
  "openclaw-weixin": {
    "channelConfigUpdatedAt": "2026-08-10T12:23:20.818Z"
  }
}
```

#### 已安装插件（`openclaw.json` 行 86-148）

| 插件 | 用途 | 与学习工具关联 |
|------|------|------------|
| `openai` | 模型供应商 | 可用 |
| `codex` | Codex agent | 待探索 |
| `moonshot`（kimi-k2.6）| 模型供应商 | 可用 |
| `active-memory` | 活跃会话记忆 | 核心能力 |
| `memory-wiki` | 记忆编译为知识库 | 可替代/补充 Obsidian |
| `logbook` | 日志记录 | 可用 |
| `workboard` | 看板 | 强关联（见上） |
| `llm-task` | LLM 任务 | 需探索 |
| `codex-supervisor` | Codex 监督 | 需探索 |
| `webhooks` | Webhook 路由 | 核心（见上） |
| `memory-core`（+ dreaming）| 记忆核心 + 梦境 | 核心（见上） |
| `searxng`（本机 localhost:8888）| 搜索引擎 | 可用 |
| `openclaw-weixin` | 微信公众号通道 | **已通** |
| `deepseek` | 模型供应商 | 可用 |

#### 邮件/日程/未读 能力评估

**邮件**：OpenClaw **无内置邮件通道**，但支持：
- Gmail PubSub 集成（`automation/gmail-pubsub.md`）——需要 Google Cloud + Gmail API + Tailscale 公开 HTTPS
- Webhook 注入 ——外部系统推送邮件内容到 OpenClaw

**日程**：OpenClaw **无内置日程系统**，但支持：
- Heartbeat 检查（`HEARTBEAT.md` 可包含日程检查 prompt）
- 插件扩展（无内置日历插件）
- Cron 任务可向 channel 投递日程提醒

**未读消息**：OpenClaw **无统一未读聚合**，但通道各自处理：
- WeChat 通道（`openclaw-weixin` 已装）可接收微信消息
- Heartbeat 的 `HEARTBEAT.md` 可包含"检查未读"任务

**结论**：OpenClaw 的邮件/日程/未读能力**高度依赖外部集成**：
- 最可行的路线：**通过 Webhook（`/hooks/agent`）让外部系统将邮件/日历/未读内容注入 OpenClaw**，由 Agent 统一处理
- OpenClaw 自身是**推理/编排引擎**，不是邮件/日历的直接消费者——需要外部插件或 API 桥接

---

### 2.7 本机 OpenClaw 配置详情

**配置文件**：`C:\Users\wn\.openclaw\openclaw.json`

**Gateway**
```json
{
  "mode": "local",
  "port": 18789,
  "bind": "lan",         // 监听 LAN，可从网络访问
  "auth": { "mode": "token", "token": "6d118e987c..." },  // Token 已配置
  "controlUi": { "allowInsecureAuth": true },
  "nodes": { "denyCommands": ["camera.*", "screen.record", "calendar.add", "reminders.add", "sms.*"] }
}
```

**Agent**
- Workspace：`C:\Users\wn\.openclaw\workspace`
- 主模型：`deepseek/deepseek-v4-flash`
- 备用：`openai/gpt-5.6`（alias: GPT）
- Heartbeat：每 30 分钟，独立会话，轻量上下文

**Memory**
- 本地嵌入模型：`C:\Users\wn\.node-llama-cpp\models\embeddinggemma-300M-Q8_0.gguf`
- Provider：`local`（本地 Ollama 等价）
- Dreaming：已启用，时区 Asia/Shanghai，频率 `0 */2 * * *`（每2小时一次）

**工具**
- Web search：SearXNG（localhost:8888），8 结果，30s 超时
- 工具 Profile：`coding`

**Webhooks**
- `plugins.entries.webhooks.enabled: true`
- Cron triggers：`enabled: true`

**已装通道**：仅 `openclaw-weixin`（微信公众号）

---

## 第三趴：升格方案雏形

### 3.1 目标形态

> **一个前端 = 个人助理统一视图**，包含：
> 1. 学习（已有抽卡 + 任务 + 计时器）
> 2. 知识库（已有 Obsidian vault 浏览）
> 3. OpenClaw 能力面板（邮件摘要/未读/日程/记忆/任务）

### 3.2 数据流架构

```
┌─────────────────────────────────────────────────────────────┐
│                    个人助理前端（Flask :5000）                 │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  抽卡学习   │  │   知识库     │  │  OpenClaw 能力面板  │ │
│  │  任务/计时  │  │  Obsidian   │  │  (iFrame 嵌入)     │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬─────────┘ │
│         │                │                      │           │
│         └────────────────┼──────────────────────┘           │
│                          │                                  │
│                   /api/* (Flask)                           │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────────────┐ │
│  │           学习工具后端（Flask :5000）                   │ │
│  │  任务/日程/状态/知识库/计时器/配置                      │ │
│  └───────────────────────┬───────────────────────────────┘ │
│                          │                                  │
│         ┌───────────────┼────────────────┐                │
│         ▼               ▼                ▼                │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐       │
│  │  知识库     │  │  SQLite DB  │  │  OpenClaw   │       │
│  │  (vault)   │  │  (task_pub) │  │  Gateway    │       │
│  └─────────────┘  └─────────────┘  │  (:18789)   │       │
│                                   └──────┬───────┘       │
│                                          │               │
│                     ┌────────────────────┼──────────────┐ │
│                     ▼                    ▼              ▼ │
│               Memory (MEMORY.md)  Cron/Heartbeat  Channels │
│               /hooks/agent       TaskFlow         (WeChat)  │
│               Workboard (SQLite)  Tools (MCP/内置)           │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 前端与 OpenClaw 的对接方式

#### 方案 A：OpenClaw Chat 作为主入口 + 学习工具作为右侧 Panel（推荐）

**架构**：
- OpenClaw Control UI（`http://127.0.0.1:18789/`）作为**主导航**
- 学习工具（`http://127.0.0.1:5000/`）通过 **iframe 嵌入** 或 **超链接跳转**
- Control UI 的 **Split View** 功能（`control-ui.md` 行 249）支持左侧 Chat、右侧工具面板

**优点**：
- 不改动 OpenClaw 本身
- 学习工具完全独立，可独立访问
- Chat 可以调用 Agent 处理邮件/日程，Agent 引用学习工具中的笔记和任务

**缺点**：
- 两个 UI 风格可能不一致（学习工具是深色主题 + 金色字体，OpenClaw 是自己的主题）
- iframe 嵌入时 session 隔离

#### 方案 B：学习工具前端内嵌 OpenClaw WebChat（不推荐）

**架构**：
- 学习工具的 `index.html` 增加一个"OpenClaw Chat" tab
- 通过 `window.open` 或 iframe 嵌入 OpenClaw WebSocket Chat
- 技术难度：OpenClaw Chat 需要与 Gateway WebSocket 交互，有认证要求

**问题**：
- 认证处理复杂（需要透传 Gateway token）
- 两个聊天界面可能冲突
- **Control UI 不支持嵌入式子页面**，只有 `[embed]` shortcode

#### 方案 C：统一导航页面（最优）

**架构**：
- 重构学习工具前端，增加一个 **OpenClaw Panel 页面**（第六个 tab）
- 该 tab 通过 **iframe 加载** OpenClaw Control UI（或其子路径）
- 共享顶部导航，学习工具在 `/`，OpenClaw 在 `/openclaw` 子路径

**实现**：
```html
<!-- index.html 新增 -->
<section class="page" id="page-openclaw">
  <div class="know-layout">
    <div class="know-side">
      <!-- OpenClaw 快捷操作 -->
      <button onclick="openOpenClawPanel('chat')">💬 Chat</button>
      <button onclick="openOpenClawPanel('memory')">🧠 Memory</button>
      <button onclick="openOpenClawPanel('workboard')">📋 Workboard</button>
      <button onclick="openOpenClawPanel('cron')">⏰ Cron</button>
    </div>
    <div class="know-main">
      <iframe id="openclawFrame" src="http://127.0.0.1:18789/" 
              sandbox="allow-scripts allow-same-origin"
              style="width:100%;height:80vh;border:none"></iframe>
    </div>
  </div>
</section>
```

**优点**：
- 单页面体验
- 学习工具 + OpenClaw 同一界面
- iframe 的 `allow-scripts` 允许 OpenClaw UI 正常执行

**注意**：OpenClaw Control UI 本身是 SPA，带有 WebSocket 连接，iframe 嵌入需要处理认证 token 透传。

#### 推荐的混合路径

1. **短期（MVP）**：保持现状——学习工具独立（`localhost:5000`），OpenClaw 独立（`localhost:18789`），通过书签/标签页切换
2. **中期**：在 `config.json` 增加 OpenClaw Gateway URL 配置，前端增加 OpenClaw 快捷面板（通过 iframe 嵌入 Control UI 特定 tab）
3. **长期**：统一前端框架，学习工具组件化为 OpenClaw 的一个 Panel

### 3.4 后端分工（Flask :5000 vs OpenClaw :18789）

| 能力 | 负责方 | 理由 |
|------|--------|------|
| 任务抽卡/计时/日程 | Flask 后端 | 已有完整实现，SQLite 数据 |
| Obsidian 知识库 | Flask 后端 | 已有 `/api/knowledge/*` 路由 |
| AI 推理/自然语言交互 | OpenClaw Gateway | Agent 运行时，LLM 调用 |
| 记忆（偏好/习惯） | OpenClaw | `MEMORY.md` + `memory_search` |
| 自动化（Cron/Heartbeat） | OpenClaw Gateway | 内置调度器 |
| 邮件/日历/未读聚合 | 外部桥接 → OpenClaw | OpenClaw 无内置，需 webhook 注入 |
| Webhook 触发 | OpenClaw Gateway | `/hooks/agent` 等 HTTP 入口 |
| 工作看板 | OpenClaw Workboard | 独立 SQLite，Agent 工具驱动 |

**关键桥接点**：
- 学习工具后端 **可以**调用 `http://127.0.0.1:18789/hooks/agent` 触发 OpenClaw 处理邮件/日程
- OpenClaw Agent **可以**通过 `tools.exec` 调用学习工具后端 API（需要 `exec` 权限）
- `memory_search` 可以索引学习工具的 Obsidian 笔记路径（需配置 QMD 引擎）

### 3.5 独立访问 + 嵌入两用实现

学习工具前端天然支持两种访问模式：
1. **直接访问**：`http://localhost:5000/` —— 完整 SPA
2. **嵌入访问**：作为 iframe 嵌入 OpenClaw Control UI

关键实现点：
- 所有 API 调用使用**相对路径**（`fetch('/api/...')`）—— 在 iframe 内自动同 origin
- 不依赖 cookie——JWT/session-free 设计
- 可通过 URL 参数切换主题（`?theme=embedded`）或隐藏顶部导航
- 推荐：添加 `?embed=1` 参数，学习工具前端隐藏 header nav，仅保留核心功能

### 3.6 架构三性原则

**精简（最小实现）**
- 不引入新框架——继续用原生 HTML/CSS/JS
- 不抽象出"个人助理"通用层——先实现具体整合
- OpenClaw 的能力通过 iframe 引入，不复制逻辑

**可维护**
- `static/app.js` 按功能模块组织（已有良好分隔）
- 新增 OpenClaw panel 作为独立模块（`renderOpenClawPanel()`）
- API 路由按域分组（已有良好结构）

**可扩展**
- OpenClaw 能力面板为**注册式**：配置文件中声明可用的 Panel tab，每个 tab 独立加载
- 新能力通过新增 tab 接入，不重写核心
- Webhook 入口支持外部系统随时接入

### 3.7 分阶段路线

#### Phase 0：基线确认（不做代码改动）
**交付物**：本报告 `docs/RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md`
**验证方式**：用户阅读报告，确认方案方向

#### Phase 1：最小整合 MVP（1-2天）
**目标**：实现 OpenClaw Chat 入口 + 学习工具快捷跳转

**具体内容**：
1. 在 `config.json` 增加 OpenClaw 配置：
```json
{
  "openclaw": {
    "gateway_url": "http://127.0.0.1:18789",
    "gateway_token": "从 openclaw.json 读取"
  }
}
```
2. 在 `app.js` 增加 `openOpenClawChat()` 函数：
   - 新窗口/标签页打开 `http://127.0.0.1:18789/`
   - 传递 auth token
3. 在 `config` 页面增加"打开 OpenClaw"按钮

**验证方式**：点击按钮 → 浏览器新标签打开 OpenClaw Chat → 能正常对话

#### Phase 2：统一导航整合（3-5天）
**目标**：在现有五大功能区基础上，**增加第六个 tab**（"助理"），提供 OpenClaw 能力快捷面板

**具体内容**：
1. 新增 `#page-assistant` section（参考 knowledge 页面布局）
2. 左栏：OpenClaw 快捷操作（Chat / Memory / Workboard / Cron / HEARTBEAT.md / 通道状态）
3. 右栏：OpenClaw Control UI 嵌入（`iframe` + token 注入）
4. 路由 `/api/openclaw/*` ——学习工具后端代理 OpenClaw Gateway 请求（解决 CORS + 认证）
   ```python
   @app.route('/api/openclaw/rpc', methods=['POST'])
   def api_openclaw_rpc():
       # 转发到 Gateway WebSocket 或 HTTP API
   ```
5. 记忆同步：定期读取 `MEMORY.md` 内容，在前端展示（编辑偏好 / 长期目标）

**验证方式**：
- 打开"助理" tab → 看到 OpenClaw 快捷操作
- 点击 "Memory" → 显示 MEMORY.md 内容
- 点击 "Chat" → iframe 内加载 OpenClaw Chat（或新标签）
- HEARTBEAT.md 在 OpenClaw workspace 中存在并可读

#### Phase 3：深度数据流整合（5-10天）
**目标**：OpenClaw Agent 能看到学习工具数据，学习工具能展示 OpenClaw 处理结果

**具体内容**：
1. **OpenClaw 侧**：
   - 在 `~/.openclaw/workspace/MEMORY.md` 中记录学习偏好（精力低谷、最佳学习时间等）
   - 配置 `HEARTBEAT.md` 包含"检查邮件"和"查看学习任务"提示
   - 通过 `webhooks` 插件暴露 HTTP 端点供学习工具后端调用

2. **学习工具侧**：
   - `/api/agent/memory` ——读取 MEMORY.md（按天或按类型）
   - `/api/agent/tasks` ——将 OpenClaw 处理产生的任务同步到 tasks 表
   - `/api/openclaw/inject` ——通过 webhook 触发 OpenClaw 执行特定任务

3. **Webhook 桥接服务**：
   - Flask 后端暴露 `/api/webhook/trigger` → curl `http://127.0.0.1:18789/hooks/agent`
   - OpenClaw Agent 执行结果写回学习工具任务系统

4. **Workboard 整合**（可选）：
   - 学习工具任务完成时，通过 Workboard API 通知 Agent
   - Workboard 卡片状态变化时，同步到学习工具

**验证方式**：
- OpenClaw Chat 说"查看我的学习偏好" → 正确读取 MEMORY.md
- 在 OpenClaw 中说"检查未读邮件" → Agent 触发 webhook → 学习工具收到任务
- 学习工具完成任务 → 通过 webhook 通知 OpenClaw → Agent 记录到 MEMORY.md

#### Phase 4：知识库统一（进阶）
**目标**：将学习工具的 Obsidian vault 与 OpenClaw 的 `memory-wiki` 插件整合

**具体内容**：
1. 配置 OpenClaw `memory-wiki` 指向 `src/notes/vault`（已有约 1485 个 md）
2. `memory-wiki` 编译 vault 为 wiki 结构（claims/dashboards/digests）
3. 学习工具前端 `/api/knowledge/*` 路由 + OpenClaw `wiki_search/wiki_get` 工具共存
4. 用户可选择通过 OpenClaw Agent 问答 vault（`wiki_search`）或直接浏览（`/api/knowledge/`）

**验证方式**：
- OpenClaw Chat："查找关于 [主题] 的笔记" → `wiki_search` 正确返回
- 知识库页面 → 直接浏览，渲染 Markdown

---

## 风险与未知点

### 需要用户拍板

1. **UI 风格统一问题**：学习工具是深色主题（`#0a0e1a` + 金色字体 `#f0c040`），OpenClaw Control UI 有自己的主题（Claw/Knot/Dash）。整合后用哪套？
   - 选项 A：OpenClaw 风格为主，学习工具适配
   - 选项 B：学习工具风格为主，OpenClaw iframe 保持原样
   - 选项 C：完全重构，统一主题（成本最高）

2. **认证方案**：OpenClaw Gateway 需要 token 认证（当前本机 `6d118e987c...`）。学习工具前端嵌入 OpenClaw iframe 时，token 如何传递？
   - 选项 A：学习工具后端代理（`/api/openclaw/*` 路由转发，含 token）
   - 选项 B：用户在 OpenClaw UI 中手动认证一次，浏览器缓存
   - 选项 C：OpenClaw 配置 `allowInsecureAuth: true`（本机已设），iframe 内无需额外认证

3. **邮件/日历具体方案**：OpenClaw 无内置。用户使用什么邮件服务？需要 Gmail API 吗？还是通用 IMAP？日历用哪个（Google Calendar / Apple Calendar / 其他）？

4. **OpenClaw 的 WeChat 通道**（`openclaw-weixin`）已装——是否已有实际连接？微信消息是否已经在 OpenClaw 中可用？

5. **数据所有权**：OpenClaw 的 `MEMORY.md` / `memory/YYYY-MM-DD.md` 是 OpenClaw workspace 的文件，学习工具后端读取需要文件路径。当前 workspace 在 `C:\Users\wn\.openclaw\workspace`——这是固定路径还是可配置？

6. **Phase 3 的 Webhook 桥接**：谁来写这个桥接服务？
   - 选项 A：Flask 后端（学习工具已有）增加 OpenClaw 代理路由
   - 选项 B：OpenClaw Agent 通过 `tools.exec` 直接调用 Flask API
   - 选项 C：新建独立微服务（成本最高）

7. **Workboard vs 学习工具任务**：两者功能重叠度如何？是否需要合并？建议保持独立——Workboard 是 Agent 操作向，学习工具任务是个人学习向。

### 技术不确定性

1. **OpenClaw Control UI iframe 嵌入可行性**：Control UI 本身是 SPA，带 WebSocket 连接。在 iframe 内运行是否有 origin 隔离问题（`allow-same-origin` 会合并 origin，可能影响 cookie/storage 隔离）？需实测。

2. **`[embed]` shortcode 的渲染位置**：`[embed]` 只能在 Assistant 消息中渲染，不能作为独立 UI 入口。是否需要改造 OpenClaw？目前看不需要，Split View 已足够。

3. **HEARTBEAT.md 的 cron dreaming 频率**（当前每 2 小时一次）：是否影响性能？dreaming 是在后台安静的，是否需要调整为更低的频率？

4. **学习工具 Obsidian vault（~1485 个 md）与 OpenClaw memory-wiki 的关系**：memory-wiki 是否会修改 vault 内容？需要确认 memory-wiki 的行为（只读还是读写）。

5. **OpenClaw `gateway.controlUi.allowExternalEmbedUrls: true` 的安全影响**：允许加载任意外部 URL 到 iframe。需要评估是否必须。

6. **Playwright E2E 测试**：现有 26 用例全部针对学习工具。OpenClaw 整合后是否需要扩展 E2E？

---

## 附录：关键文件索引

| 文件 | 用途 |
|------|------|
| `server/backend_api.py` | Flask 后端全部路由 |
| `static/app.js` | 前端全部业务逻辑（约 2811 行） |
| `src/index.html` | 前端页面结构 + CSS（约 924 行） |
| `config/config.json` | 学习工具运行时配置 |
| `data/task_publisher.db` | SQLite 数据库（20 张表） |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\web\control-ui.md` | Control UI 完整文档（含嵌入机制） |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\concepts\memory.md` | Memory 系统文档 |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\automation\cron-jobs.md` | Cron + Heartbeat 文档 |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\plugins\webhooks.md` | Webhooks 插件文档 |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\plugins\workboard.md` | Workboard 看板文档 |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\channels\index.md` | 通道系统文档 |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\automation\index.md` | 自动化概览 |
| `D:\Axelit\工作软件\node_modules\openclaw\docs\gateway\heartbeat.md` | Heartbeat 详细配置 |
| `C:\Users\wn\.openclaw\openclaw.json` | 本机 OpenClaw 完整配置 |
