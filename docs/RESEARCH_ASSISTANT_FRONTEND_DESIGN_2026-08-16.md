# 调研报告：Agent 个人助理前端形态 + HTML 前端设计方案 + 外部工程经验方向

> 生成时间：2026-08-16
> 调研方式：联网（@web / Perplexity 系列检索）+ 本地 OpenClaw docs（`D:\Axelit\工作软件\node_modules\openclaw\docs`）双源交叉
> 范围：仅调研、不写实现；所有推荐带出处；明确区分"事实（来源标注）"与"建议（我的判断）"
> 项目锚点：现有 `超级自动化学习工具`（Flask + SQLite + 原生 HTML/JS 单页，`static/app.js` ~2711 行，含双计时器状态机；目标升级为可嵌入 OpenClaw Control UI 的"个人助理前端"）。

---

## 目录

- [0. 阅读须知 / 缩写表](#0-阅读须知--缩写表)
- [1. 项目现状锚点（极简复述）](#1-项目现状锚点极简复述)
- [方向一 · Agent 个人助理产品形态与能力全景](#方向一--agent-个人助理产品形态与能力全景)
  - [1.1 业界成熟形态对比](#11-业界成熟形态对比)
  - [1.2 能力全景清单（自建 vs 集成 vs 桥接）](#12-能力全景清单自建-vs-集成-vs-桥接)
  - [1.3 local-first 实践（隐私/同步）](#13-local-first-实践隐私同步)
  - [1.4 前端信息架构可借鉴模式](#14-前端信息架构可借鉴模式)
- [方向二 · HTML 前端设计开发方案](#方向二--html-前端设计开发方案)
  - [2.1 技术选型](#21-技术选型)
  - [2.2 信息架构与布局](#22-信息架构与布局)
  - [2.3 设计系统 / CSS / 主题 / 图标](#23-设计系统--css--主题--图标)
  - [2.4 Markdown / 全文搜索 / 图表](#24-markdown--全文搜索--图表)
  - [2.5 嵌入 OpenClaw 的 iframe 工程模式](#25-嵌入-openclaw-的-iframe-工程模式)
  - [2.6 可维护性：原生大单页的拆分策略](#26-可维护性原生大单页的拆分策略)
- [方向三 · 外部工程经验方向（12 项逐一调研）](#方向三--外部工程经验方向12-项逐一调研)
  - [3.1 邮件集成](#31-邮件集成)
  - [3.2 未读消息聚合（多通道）](#32-未读消息聚合多通道)
  - [3.3 日程/日历（ICS / Google Calendar / 与现有 schedule 整合）](#33-日程日历ics--google-calendar--与现有-schedule-整合)
  - [3.4 通知推送（Web Push + OpenClaw 能力）](#34-通知推送web-push--openclaw-能力)
  - [3.5 数据可视化（学习统计 / 能量曲线 / 知识图谱）](#35-数据可视化学习统计--能量曲线--知识图谱)
  - [3.6 知识库渲染（Obsidian vault / 双链图 / 全文搜索）](#36-知识库渲染obsidian-vault--双链图--全文搜索)
  - [3.7 安全与隐私（SQLCipher / Token 管理 / iframe 沙箱 / 局域网鉴权）](#37-安全与隐私sqlcipher--token-管理--iframe-沙箱--局域网鉴权)
  - [3.8 PWA / 离线（manifest + service worker + IndexedDB）](#38-pwa--离线manifest--service-worker--indexeddb)
  - [3.9 跨设备 / 移动适配（响应式 + OpenClaw iOS/Android canvas 配合）](#39-跨设备--移动适配响应式--openclaw-iosandroid-canvas-配合)
  - [3.10 语音 / 朗读（Web Speech + 后续 OpenClaw voice/talk 整合）](#310-语音--朗读web-speech--后续-openclaw-voicetalk-整合)
  - [3.11 备份 / 同步（SQLite 备份 + Syncthing + 配置导出）](#311-备份--同步sqlite-备份--syncthing--配置导出)
  - [3.12 自动化对接（cron / webhook / OpenClaw memory / Hooks）](#312-自动化对接cron--webhook--openclaw-memory--hooks)
- [4. 落地优先级排序（对 MVP 而言）](#4-落地优先级排序对-mvp-而言)
- [5. 风险与未知点](#5-风险与未知点)
- [6. 一句话决策建议](#6-一句话决策建议)
- [附录 A · 全部来源清单（去重、按方向分组）](#附录-a--全部来源清单去重按方向分组)

---

## 0. 阅读须知 / 缩写表

| 缩写 | 全称 / 出处 |
|---|---|
| **OpenClaw** | 本地 AI 个人助理平台（Gateway + Nodes + Channels + WebChat/Control UI）；本文档来源 `D:\Axelit\工作软件\node_modules\openclaw\docs`，文档根目录有 `index.md`、`docs.json`、`docs_map.md` 等 |
| **Control UI** | OpenClaw Gateway 内置的浏览器仪表盘，位于 `http://<host>:18789/`，技术栈 Vite + Lit 单页；详见 `docs/web/control-ui.md` |
| **WebChat** | macOS/iOS SwiftUI 原生聊天客户端 + Control UI 内聊天 Tab；走 Gateway WebSocket，详见 `docs/web/webchat.md` |
| **Gateway** | OpenClaw 主进程，统一 WebSocket / HTTP / 鉴权 / 调度入口；详见 `docs/web/dashboard.md` |
| **MCP** | Model Context Protocol；OpenClaw 用它接入第三方工具，详见 `docs/concepts/mcp.md`（concepts 目录存在但本调研未深读） |
| **CJK** | Chinese / Japanese / Korean；SQLite FTS5 默认 unicode61 不支持、需 trigram 兜底 |
| **VAPID** | Voluntary Application Server Identification；Web Push 鉴权签名机制 |
| **MEMORY.md / memory/YYYY-MM-DD.md** | OpenClaw 默认记忆文件布局；详见 `docs/concepts/memory.md`、`docs/concepts/memory-builtin.md` |
| **IDLE / IMAP IDLE** | IMAP 协议的实时推送扩展（服务器主动通知新邮件） |

**文中标记约定**：

- **[F]** = 事实陈述，引自源材料原文或近原文；附 URL/路径
- **[J]** = 我的判断 / 建议；非材料直接给出，由我对项目 + 多份资料综合得出

---

## 1. 项目现状锚点（极简复述）

> 只列出与本调研直接相关的 6 条事实，其余见 `README.md`。

1. **前端形态**：原生 HTML/JS 单页，`src/index.html` + `static/app.js`（~2711 行，含双计时器状态机）`[F — README.md 32 行]`
2. **后端**：Flask 单文件 `server/backend_api.py`，端口 5000，全部 `/api/*` 路由 + SQLite `[F — README.md 14 行]`
3. **现有 API 域**：tasks / gacha / discard / tags / dependencies / export / schedule / state / timer / feedback / knowledge / config / prompts / agent `[F — README.md 173–189 行]`
4. **知识库**：Obsidian vault，`src/notes/vault/` 约 1485 个 `.md`，**红线：绝不提交 git** `[F — README.md 23–28 行 + AGENTS.md 红线]`
5. **配置**：`config/config.json`（端口/vault 路径/API Key/DB 路径）`[F — README.md 57–59 行]`
6. **目标**：升级为"统一界面 = 抽卡学习 + 工作流知识库 + OpenClaw 可处理项（邮件/未读/日程/提醒/记忆/任务调度）"，且要能**嵌入 OpenClaw Control UI 的对话界面** `[F — 用户 prompt 开头]`

> 注：用户描述的"嵌入 OpenClaw 的对话界面"在 OpenClaw 文档里对应 Control UI 的 "Chat" Tab（`docs/web/webchat.md`），它是 Gateway WebSocket + `chat.send/chat.history` 的前端容器；侧边栏 `+` 拖拽可开启分屏聊天面板（`docs/web/control-ui.md` 第 249 行起的 split-pane 段）。`[F]`

---

# 方向一 · Agent 个人助理产品形态与能力全景

## 1.1 业界成熟形态对比

### 1.1.1 三类主流开源产品的差异（[F] 多份 2026 对比文章交叉验证）

| 维度 | Open WebUI | LibreChat | AnythingLLM |
|---|---|---|---|
| 主要定位 | Ollama 优先的 AI 门户 | 多 provider agent 工作台 | RAG 优先的知识工作台 |
| Stars | ~124K | ~22K | ~54K |
| 部署 | 单 Docker 容器（多 worker 需 PG/Redis） | Docker Compose 多容器 | Docker 或单用户桌面 Electron |
| 鉴权 | 本地/LDAP/OAuth；RBAC admin/user/pending | OAuth2/LDAP/邮件 + token 用量追踪 | 本地账号，3 角色（仅 Docker 模式） |
| RAG | 内置 ChromaDB | 基础文件 + RAG API service | 工作区原生，支持 LanceDB/ChromaDB/Pinecone/Qdrant/Weaviate/pgvector |
| Agent | Pipelines 体系，工具/函数调用 | Agent + MCP + 代码沙箱（Py/Node/Go/Rust） | 内置 agent 框架 + 工具构建 UI |
| 桌面 | 无 | 无 | 有（Electron） |

来源：
- https://open-techstack.com/blog/open-webui-vs-librechat-vs-anythingllm-2026/
- https://dreaming.press/posts/open-webui-vs-librechat-vs-anythingllm.html
- https://toolhalla.ai/blog/open-webui-vs-anythingllm-vs-librechat-2026
- https://onyx.app/insights/openwebui-vs-librechat-vs-onyx
- https://www.local-llm.net/compare/open-webui-vs-librechat-vs-anythingllm/

**Open WebUI 的定位与本项目最契合的事实依据** `[F]`：

- "the cleanest 'self-hosted AI front door' with broad provider support, built-in RAG, strong auth options, and a simple Docker-first start" `[open-techstack.com]`
- "easiest start, but the Redis documentation makes it clear that multi-worker and multi-node deployments need shared state infrastructure" `[open-techstack.com]`

### 1.1.2 新兴"AI 助理中心"形态（2025-2026）`[F]`

通过检索 `vllm.ai / vellum.ai / arah.ai` 和 GitHub 整理：

- **Mission Control**（ProfFroggo/froggo-mission-control）`[F — GitHub]`
  - 显式模块化卡片：**Kanban / Analytics / Approvals / Chat Rooms / Schedule / Gmail Inbox / Finance / Library / Projects / Voice / Writing / Meetings**
  - 内置 Memory vault（Obsidian 兼容）
  - 信任分层（trust tiers / 模型 / 人格），可视化 Agent 管理
  - "Approvals"作为**人类在环**审批队列，对外部写入必经审批
  - URL：https://github.com/ProfFroggo/froggo-mission-control

- **Aura**（kevinreber/aura）`[F — GitHub]`
  - monorepo：React Router v7 + LangChain + MCP Server
  - 一个统一仪表盘聚合 weather / calendar / tasks / markets / commute
  - 21+ MCP 工具 + GPT-4o-mini 编排
  - **Google OAuth + email allowlist** 是 UI 的鉴权边界
  - **Slash 命令**：/summary /weather /finance /help 等上下文命令（surfaces-aware）
  - URL：https://github.com/kevinreber/aura

- **Sentient-OS**（gestas666/Sentient-OS）`[F — GitHub]`
  - "One dark commanding dashboard for Claude Code, OpenClaw, Hermes, Codex and any other CLI agent"
  - "Local-first runs on localhost, talks to your CLIs directly. Your data never leaves the machine"
  - 内嵌 KITT 风格的语音存在感（ElevenLabs）、XP 引擎（agents 升级）、Vault 写入到 Obsidian
  - URL：https://github.com/gestas666/Sentient-OS

- **Arahi AI**（商业 SaaS，对照组）`[F — arah.ai]`
  - 1,500+ 应用集成：Gmail / Google Calendar / Outlook / Slack / MS Teams / Notion / Asana / Trello / HubSpot / Salesforce / Zoom / Pipedrive / Intercom / Stripe / Jira
  - "加密 end-to-end，never used to train third-party models"
  - URL：https://arah.ai/personal-assistant

- **Vellum**（vellum.ai 评测中描述）`[F]`
  - 跨表面共享 memory：native Mac / iOS / web app / voice / email / Telegram / Slack
  - URL：https://www.vellum.ai/blog/best-ai-assistants-to-automate-your-work

### 1.1.3 local-first 隐私至上的几款产品 `[F]`

| 项目 | 关键架构 | 来源 |
|---|---|---|
| **semblance-core** | "AI Core 进程零网络访问"；Gateway 单一可审计出口；hash-chained append-only audit；knowledge graph + embeddings 全本地 | https://github.com/skygkruger/semblance-core |
| **FRIDAY** | hash-chained audit ledger；OS-keystore secrets（KeyringVault / EnvVault / FileVault 0600）；fail-closed security broker | https://github.com/LakshyaBadjatya/Friday |
| **Wylde** | 全部服务暴露 Windows named pipe `\\.\pipe\wylde-*`；Gateway 是唯一 HTTP trust boundary（127.0.0.1:8005）；出网走单通道 + kill switch；WireGuard tunnel + mDNS；按设备 bearer + 三层权限 | https://github.com/PeopleWonder/wylde |
| **NEOTH** | WASM 插件沙箱 + 多层记忆（5 tier）；WAL-backed audit；`neoth privacy audit --last 30d` 类命令 | https://github.com/The-Geek-Freaks/NEOTH |
| **PROMETHEUS** | UE5 Metahuman 化身 + 8B/70B 本地核心；XTTS v2 声音克隆 + 出向目的标签审计；strict ToolRegistry（Pydantic 校验） | https://github.com/HarshkumarG007/PROMETHEUS |

> 这五款都强调"single egress / kill switch / hash-chained audit"三件套，本项目接入 OpenClaw 后天然继承该模式（详见 §3.12）。

### 1.1.4 我的判断 / 可借鉴 `[J]`

1. **不要试图复刻 Open WebUI / LibreChat 的完整 RAG + 多 provider 矩阵**——OpenClaw 已经替我们做这件事（默认 OpenAI embedding，多 provider 切换 `memorySearch.provider` `[F — docs/concepts/memory-builtin.md 67-82]`）。我们的"个人助理前端"应该把 OpenClaw 当作"大脑"，**只做面板和编排**，不重复实现 RAG 引擎。
2. **模块化卡片架构**（Mission Control）是匹配本项目的形态：每个能力一个清晰命名的卡片，"对话"作为常驻 + 上下文聚合层（"Copilot sheet" 模式，Aura）。这与现有 `gacha / tasks / schedule / knowledge / config` 顶导结构同构。
3. **信任分层 + 审批队列**（Mission Control Approvals）是后续接入 OpenClaw 时绕不开的——`docs/automation/hooks.md` 第 47-69 行列出 `message:sent / message:received / command:*` 等 13 个事件，其中 `message:sent` 是出向写入的可拦截点。但 v1 不必做：先把 OpenClaw 现有的 `exec.approvals.*` 暴露在我们的前端即可（`[F — docs/web/control-ui.md 150]`）。
4. **Aura 的"上下文 slash 命令"模式**（`/summary /weather /finance`）值得学——可以在聊天框旁给"今日能量 / 今日任务 / 本周统计 / 提醒队列"做一组 quick chip，让用户用 0 击键就拿到 OpenClaw 编排结果。

---

## 1.2 能力全景清单（自建 vs 集成 vs 桥接）

> 表中"实现方式"分三档：**自建** = 我们自己写后端 + 前端；**集成** = 调用外部服务 API；**桥接** = 把 OpenClaw 已有的能力用一层薄前端包出来。

| 能力 | 实现方式（建议） | 现有 OpenClaw 能力 | 业界方案参考 | 备注 / 出处 |
|---|---|---|---|---|
| 对话（多模型 / 流式） | 桥接 | Control UI Chat + WebChat；`chat.send / chat.history` + WebSocket | Open WebUI / LibreChat / Aura | `[F — docs/web/control-ui.md 127-134] [F — docs/web/webchat.md 25-34]` |
| 任务管理（Kanban / 待办） | 自建（已有）/ 桥接 | OpenClaw `tasks.*` 实时任务账本 + `cron.*` | Mission Control Tasks / Kanban | `[F — docs/web/control-ui.md 147]` |
| 抽卡 / 学习机制（独有） | 自建 | 无（OpenClaw 没有该域） | 无直接对照 | 本项目特色，保留 |
| 知识库浏览（vault / Markdown） | 自建（已有） | `MEMORY.md / memory/YYYY-MM-DD.md` 可作为附加 vault | AnythingLLM 工作区 / Obsidian | `[F — docs/concepts/memory.md]` |
| RAG / 向量检索 | 桥接 | `memorySearch.provider` 默认 OpenAI，可换本地 Ollama/llama.cpp | AnythingLLM LanceDB / OpenClaw builtin sqlite-vec | `[F — docs/concepts/memory-builtin.md 17-19]` |
| 邮件收发（Gmail / Outlook） | 自建后端 + IMAPClient | `automation/gmail-pubsub`（PubSub 推送）+ `hooks.gmail` 配置预设 | Unipile / IMAPClient / Gmail API | `[F — docs/automation/cron-jobs.md 463-512]`（详见 §3.1） |
| 日程 / 日历 | 自建后端 + ICS 解析 | 无原生 calendar channel，但 schedule 模块已有 | AnythingLLM / Google Calendar API / ical / icalendar | （详见 §3.3） |
| 未读消息聚合 | 桥接（OpenClaw channels.status） | 内置 42 个 channels：discord / slack / telegram / whatsapp / imessage / matrix / feishu / 飞书 / lark / 邮件 等 | Froggo Mission Control Gmail Inbox | `[F — docs/channels/index.md 42 文件]` |
| 提醒 / 通知 / Web Push | 桥接（OpenClaw 已实现） | Control UI 内置 PWA + VAPID，方法 `push.web.*` | OpenClaw 自身（详见 §3.4） | `[F — docs/web/control-ui.md 296-324]` |
| 自动化工作流 | 桥接（OpenClaw cron + hooks） | `cron.*` + `hooks.*` + `clawflow` / `taskflow` / `standing-orders` | Mission Control Schedule / n8n | `[F — docs/automation/index.md 13 文件]` |
| 记忆（长期 / 每日） | 桥接 | MEMORY.md + memory/YYYY-MM-DD.md + active-memory 插件 | Sentient-OS / Vellum | `[F — docs/concepts/memory.md 15-26]` |
| 文件管理（Library / 库） | 自建（已有 prompts / files） | `files.raw / files.vault` API 已存在 | Mission Control Library / AnythingLLM | `[F — README.md 188]` |
| 语音 / Talk / TTS | 桥接 | `talk.*` 5 种 runtime；`voicewake.*`；`talk.speak`；Edge TTS/Coqui/ElevenLabs provider | Sentient-OS KITT / OpenClaw native Talk | `[F — docs/nodes/talk.md 7-22]` |
| 移动端（iOS/Android 节点） | 桥接 | iOS/Android 节点 + canvas | OpenClaw iOS/Android 应用 | `[F — docs/nodes/index.md]` |
| OAuth / 多 provider | 桥接 | `oauth.md` + `concepts/oauth.md` | — | `[F — concepts 列表第 19 项]` |

**出处（独立交叉验证）**：
- 控制面板能力表（侧栏 + 卡片）→ `docs/web/control-ui.md` 124-189 行
- OpenClaw 自身 channel 列表 → `docs/channels/index.md`（42 个文件：discord / slack / telegram / whatsapp / imessage / matrix / feishu / lark / googlechat / msteams / signal / line / irc / twitch / nextcloud-talk / mattermost / synology-chat / sms / clickclack / tlon / raft / nostr / zalo / zaloclawbot / zalouser / qqbot / yuanbao / googlechat / location / broadcast-groups / ambient-room-events / imessage-from-bluebubbles / group-messages / channel-routing / bot-loop-protection / pairing / access-groups / groups / troubleshooting / index）`[F — Glob 输出]`

### 1.2.1 我的判断 `[J]`

- **第一档必须自建/已有**：抽卡 + 任务池 + schedule + knowledge（这是项目自有领域）
- **第二档桥接（不动后端逻辑）**：对话 / 记忆 / 提醒 / 自动化 / 未读 / 语音（OpenClaw 已经实现）
- **第三档自建后端 + 桥接 UI**：邮件 / 日历 / 跨通道未读聚合 / 库浏览——因为 OpenClaw 没有 deep Gmail/Outlook IMAP 持久化和日历的现成实现
- **永远不要做**：RAG 引擎、模型路由、向量数据库（这些 OpenClaw 已经做）

---

## 1.3 local-first 实践（隐私/同步）

> **事实依据**：本项目现有 `data/task_publisher.db`（SQLite）+ `src/notes/vault/`（Obsidian vault）`[F — README.md 23-32, 60-64]`；未来加上 OpenClaw 的 `~/.openclaw/agents/<agentId>/agent/openclaw-agent.sqlite` 内存数据库 `[F — docs/concepts/memory-builtin.md 89-92]`。**默认就是 local-first**。

### 1.3.1 业界数据落本地 + 同步的成熟模式 `[F]`

- **semblance-core**：knowledge graph / embeddings / preferences / action history 全本地；"If your device is off, your data is inaccessible. That is the point." `[F — github.com/skygkruger/semblance-core]`
- **FRIDAY**：OS-keystore secret（KeyringVault / EnvVault / FileVault 0600 / MemoryVault fallback）；hash-chained audit ledger `[F — github.com/LakshyaBadjatya/Friday]`
- **Wylde**：默认全 loopback，WireGuard tunnel + mDNS 配对才允许移动端连入；Gateway 是唯一 HTTP trust boundary（127.0.0.1:8005）`[F — github.com/PeopleWonder/wylde]`
- **NEOTH**：`neoth privacy audit --last 30d`（provider calls + profile writes + channel egress 全部可审计）；WASM 插件沙箱 `[F — github.com/The-Geek-Freaks/NEOTH]`
- **OpenClaw 自身**：默认 OpenClaw state 数据库 `~/.openclaw/state/openclaw.sqlite`，**默认不让 Control UI 暴露到非 loopback**——需用 Tailscale Serve / Funnel / SSH tunnel / 共享密钥 + 非 loopback bind 才能外网访问 `[F — docs/web/dashboard.md 30-50]`

### 1.3.2 多端同步 / 局域网暴露的三种主流模式 `[F]`

来源：
- https://dev.to/selfhostingsh/nextcloud-vs-syncthing-which-file-sync-to-use-5bk2
- https://appmus.com/vs/syncthing-vs-freefilesync
- https://zipdo.co/best/folder-sync-software/
- https://cloudbasedbackup.com/en/blog/nextcloud-vs-syncthing-which-self-hosted-solution-is-right-for-you
- https://knightli.com/en/2026/05/31/syncthing-multi-device-folder-management/

| 方案 | 形态 | 适合 |
|---|---|---|
| **Syncthing** | 纯 P2P 同步，单二进制 / Docker；BEP 协议 over TLS；零中心服务器 | 个人多设备同步；**本项目推荐**（详见 §3.11） |
| **Nextcloud** | 完整云平台：文件 + 协作 + Office + 400+ 应用 | 家庭/团队共享 + 多用户 |
| **rclone** | 命令行，多 backend（云/本地），checksum 校验 | 跨云备份 / 脚本化归档 |
| **FreeFileSync** | GUI，手动/调度对比与单向镜像 | Windows 工作站一次性镜像 |

### 1.3.3 我的判断 `[J]`

1. **本项目天然 local-first**：DB + vault + 配置全在本地文件夹，零改动。
2. **多端同步不要用 Nextcloud**——过重，且会引入第二个 HTTP 服务。本机开 Syncthing 把 `data/`、`src/notes/vault/`、`config/` 三目录同步到备用机即可（详见 §3.11）。
3. **对外暴露严格遵守 OpenClaw 规范**：不要让 Control UI 走 `bind 0.0.0.0` 公网。要么 Tailscale Serve、要么 SSH 反代、要么 `bind 局域网 IP + gateway.auth.token`（最小权限原则）；OpenClaw 文档自身反复警告 "The Control UI is an admin surface ... Do not expose it publicly" `[F — docs/web/dashboard.md 31-32]`。

---

## 1.4 前端信息架构可借鉴模式

> 三类原型都把自己的导航骨架做得很扎实，模式高度收敛，可以直接抄。

### 1.4.1 模式 A：左侧固定侧栏 + 顶导（Open WebUI / LibreChat / Mission Control / OpenClaw Control UI）`[F]`

来源：
- https://artofstyleframe.com/blog/dashboard-design-patterns-web-apps/
- https://getcraftly.dev/blog/build-admin-dashboard-nextjs
- https://thefrontkit.com/blogs/react-dashboard-template-guide
- https://kostra.io/features/responsive-design
- `docs/web/control-ui.md` 119-122（OpenClaw 自家设计）

**OpenClaw 自己就是这套** `[F]`：

> "The sidebar pins navigation above a scrollable recent-session list split into **Pinned**, one section per custom group, and **Ungrouped** ... The sidebar collapse toggle sits at the left edge of the top bar, macOS style; collapsing shrinks the sidebar to an icon rail. At drawer breakpoints, the same top bar button opens the sidebar as a slide-over drawer instead." `[docs/web/control-ui.md 119-122]`

**业界量化建议** `[F]`：

- 侧栏宽 240-280px，折叠后 64-72px 图标栏；侧栏 < 240px 时中等长度的导航项（如 "Integrations"）开始截断；> 300px 时挤压 1366px 笔记本的内容区（1366px 仍占 ~10% 桌面流量）`[artofstyleframe.com]`
- 顶栏高固定、内容区用 CSS Grid `auto-rows: minmax(200px, auto)`，卡片网格 `repeat(auto-fit, minmax(300px, 1fr))` `[artofstyleframe.com]`
- 移动端 = off-canvas drawer + backdrop overlay + focus trap + Escape 关闭 + `role="dialog" aria-modal="true"` `[thefrontkit.com]`
- 激活态用 `aria-current="page"` `[thefrontkit.com]`
- dark mode 是 power user 默认需求——一项 2,514 票 Android Authority 调研：81.9% 使用 dark mode `[artofstyleframe.com]`

### 1.4.2 模式 B：聊天为常驻 + 上下文卡片矩阵（Aura）`[F]`

> Aura 的 Copilot sheet 是一个 bottom sheet，在任何 surface 上都能呼起 `/summary /weather /finance /help`，**上下文感知**——在 Tasks 页 `/finance` 自动跳到对应上下文。`[F — github.com/kevinreber/aura]`

### 1.4.3 模式 C：mission control 卡片网格 + 信任分层（Mission Control）`[F]`

> "Install what you need: Kanban, Analytics, Approvals, Chat Rooms, Schedule, Gmail Inbox, Finance, Library, Projects, Voice, Writing, Meetings, and more" — 卡片即插件，每个卡片独立可装可卸。`[F — github.com/ProfFroggo/froggo-mission-control]`

### 1.4.4 我的判断 / 推荐信息架构 `[J]`

**选 A+B 混合**：

```
┌─────────────────────────────────────────────────────────────────┐
│ TopBar:  [≡] 学习助手 · 我的世界       🔔3  💬2  ⚙           │ ← OpenClaw 控制点
├─────────┬───────────────────────────────────────────────────────┤
│ 侧栏    │  Hero: 今日能量环 + 下一个建议任务                     │
│ - 抽卡  │ ──────────────────────────────────────────────────── │
│ - 任务  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ - 日程  │  │ 任务池   │ │ 知识库   │ │ 未读聚合 │ │ OpenClaw │ │
│ - 状态  │  │ 待办 8  │ │ 12 篇新 │ │ ✉3 💬5   │ │ 待办 4   │ │
│ - 知识  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│ - 提示词│  ┌─────────────────────────┐ ┌─────────────────────┐ │
│ - Agent │  │  7 日能量曲线           │ │  记忆 / Dream 日志  │ │
│         │  │  (Chart.js / ECharts)   │ │                     │ │
│ ⚙ 设置  │  └─────────────────────────┘ └─────────────────────┘ │
└─────────┴───────────────────────────────────────────────────────┘
                                       │ Copilot sheet 拉起 │
                                       └─────────────────────┘
                                        ↳ 在聊天框旁加 quick chip：
                                          /今日能量 /今日任务 /本周统计 /提醒队列
```

要点：
- 侧栏宽 256px（与 OpenClaw 一致，便于用户无感切换）`[J — artofstyleframe.com 推荐]`
- 卡片用 `repeat(auto-fit, minmax(280px, 1fr))` 布局；4 个核心卡片（任务/知识/未读/OpenClaw 待办）+ 2 个辅助卡片（能量曲线/记忆）
- Copilot sheet = 右侧 360px 抽屉，与聊天界面共栈，按 ⌘. 唤起
- 所有数字（8/12/3/5/4）均来自 OpenClaw Gateway WebSocket + `/api/state/weekly-energy` 等既有 API `[F — README.md 181-183]`

---

# 方向二 · HTML 前端设计开发方案

## 2.1 技术选型

### 2.1.1 五种方案对比 `[F]`

来源：
- https://www.slant.co/versus/15409/45584/~preact_vs_alpine-js
- https://www.alphabold.com/preact-vs-react/
- https://www.pkgpulse.com/guides/preact-vs-react-2026
- https://www.pagespeedmatters.com/resources/data-studies/core-web-vitals-by-javascript-framework
- https://www.pkgpulse.com/guides/react-vs-vue-2026
- https://dev.to/_7fb6011b57d383122b5a/vanilla-javascript-with-zero-build-tools-in-2026-shipping-es-modules-via--1mg8
- https://hadezuka.dev/your-build-tool-just-cost-you-3-hours-today-heres-the-no-bundler-fix/
- https://docs.bswen.com/blog/2026-02-21-single-file-javascript-apps/
- https://gist.github.com/kristoferjoseph/a838c0fd183b2ed3246b140d1d511d8c
- https://johal.in/opinion-frontend-frameworks-are-overkill-vanilla-js-2026-opinion

| 方案 | 体积（min+gzip） | 学习曲线 | 工具链 | 嵌入 iframe 友好度 | 适配本项目 |
|---|---|---|---|---|---|
| **原生 ES modules + import map** | 0（自写代码） | 低 | 无 | 极好（无第三方依赖） | **★★★ 最合适** |
| **Alpine.js v8** | ~10KB | 极低（15 属性 6 属性 2 方法）`[F]` | 无 | 好 | ★★（事件多时心累） |
| **Preact 10 + Signals** | ~3KB core | 中（需懂 React） | Vite | 极好（10× 比 React 小）`[F]` | ★★（需要构建） |
| **Vue 3 runtime-only** | ~23KB | 中 | Vite | 好 | ★（生态绑架） |
| **React 19 + react-dom** | ~47KB | 中-高 | Vite/Next | 一般 | ✘（过大、SSR 复杂） |

**Alpine.js 量化数据**：`56.3% mobile origins pass CWV`（Alpine）vs `37.1%`（React）vs `33.7%`（Vue），**Alpine 在 Core Web Vitals 上远胜** `[F — pagespeedmatters.com]`。

**核心 web vitals 排名（mobile pass rate）`[F — pagespeedmatters.com]`**：

| 框架 | Mobile CWV pass |
|---|---|
| Alpine.js | 56.3% |
| Astro | 48.0% |
| Svelte | 43.5% |
| React | 37.1% |
| Vue | 33.7% |
| Angular | 33.6% |

**Vite 6 + Vanilla JS vs CRA + React 量化** `[F — johal.in]`：
- CRA 4.1s cold / 1.2s watch
- Angular CLI 6.2s cold
- Vite 6.0 + Vanilla JS 1.2s cold / 0.3s watch（**70% 削减**）
- Vite 用 esbuild 跑 TS 比 CRA 的 tsc 快 10-20×

### 2.1.2 我的判断 `[J]`

**首选：原生 ES modules + import map**，理由：

1. **零构建链 = 零迁移成本**：现有 `static/app.js` 已经是一个 2711 行的全局脚本，迁移到 ES modules 只需要改顶部 `import` 引用，不用装 npm 不用配 webpack。`[J]`
2. **MIME / CORS 必须满足**：浏览器对 ESM 强校验 `Content-Type: text/javascript`；Flask 已经静态托管，只要确认 `.js` 后缀正确即可，**Python `mimetypes` 模块默认识别正确**。`[J]`
3. **iframe 嵌入最友好**：原生 = 0 KB 第三方，OpenClaw Control UI 的 chat pane 把我们的应用嵌入时不会有 React/Vue 加载延迟。`[F — slant.co, pkgpulse.com]`
4. **TypeScript 可选**：不编译，写 `.js` + JSDoc 类型标注足够；esbuild 在 Vite 6 之外也能 standalone 转译 `[F — johal.in]`。

**第二选择：Preact 10 + Signals**（如果后面状态机复杂到 ES modules 也压不住）：

- 体积 3KB，但需要构建步骤 → 引入 Vite/esbuild
- Signals 提供 fine-grained reactivity，绕过 Virtual DOM 的全量重渲染，对双计时器状态机友好

**第三选择：Alpine.js**（如果团队偏好声明式）：

- 10KB 极小，但双向绑定多时心累；与本项目 ~2711 行命令式代码风格差异大

**不选 React / Vue / Angular**：体积、生态绑架、双计时器状态机迁移成本高。

### 2.1.3 嵌入友好的关键设计点 `[J]`

1. **import map 必须存在**（即使没用 bare specifiers 也写上，方便后续加 marked / chart.js）：
   ```html
   <script type="importmap">
   {
     "imports": {
       "marked": "/static/vendor/marked.esm.js",
       "chart.js": "/static/vendor/chart.esm.js"
     }
   }
   </script>
   ```
2. **所有 CDN 依赖本地化**——OpenClaw 内网部署默认无外网（"Local-first"），不能依赖 `unpkg.com / jsdelivr`。 `[F — docs/web/dashboard.md 31-32]`
3. **postMessage 协议 v1**：所有跨 iframe 通信走 `window.parent.postMessage({ source: 'super-auto-learn', version: 1, type, payload }, origin)`；监听端校验 `event.source === iframe.contentWindow && event.data.source === 'super-auto-learn'`。`[J]`（依据 §2.5）

---

## 2.2 信息架构与布局

### 2.2.1 网格断点 / 卡片布局 `[F]`

来源：https://artofstyleframe.com/blog/dashboard-design-patterns-web-apps/

- 卡片网格：`grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;` `[F]`
- metric strip 最多 6 个数字（KPI），每个带 1 个对比 + 1 个可视化 `[F]`
- `auto-rows: minmax(200px, auto)` `[F]`
- 三态设计：loading / empty / error，每个组件都得有 `[F]`

### 2.2.2 响应式断点 `[F]`

来源：https://kostra.io/features/responsive-design

| 断点 | 范围 | 布局 |
|---|---|---|
| 默认（mobile-first） | < 640px | 1 列、卡片堆叠、侧栏抽屉 |
| `sm` | 640px+ | 同上 |
| `md` | 768px+ | 2 列卡片、侧栏图标栏 |
| `lg` | 1024px+ | 3 列卡片、侧栏完整、顶导可显 |
| `xl` | 1280px+ | 4 列卡片 |
| `2xl` | 1536px+ | 大屏宽布局 |

### 2.2.3 我的判断 / 推荐布局骨架 `[J]`

```html
<body data-theme="auto">
  <div class="app-shell">
    <button class="sidebar-toggle" aria-label="切换侧栏">≡</button>
    <nav class="sidebar" data-collapsed="false">
      <ul class="nav-list">...</ul>
    </nav>
    <main class="content">
      <header class="topbar">
        <h1>我的世界 · 学习助手</h1>
        <div class="topbar-actions">
          <button id="notif-bell" aria-label="通知">🔔 <span class="badge">3</span></button>
          <button id="copilot-toggle" aria-label="Copilot">💬 <span class="badge">2</span></button>
          <button id="theme-toggle">🌗</button>
        </div>
      </header>
      <section class="hero">今日能量环 + 下一个建议任务</section>
      <section class="card-grid">
        <article class="card" data-card="tasks">...</article>
        <article class="card" data-card="knowledge">...</article>
        <article class="card" data-card="inbox">...</article>
        <article class="card" data-card="openclaw-todo">...</article>
        <article class="card card--wide" data-card="energy-chart">...</article>
        <article class="card card--wide" data-card="memory">...</article>
      </section>
    </main>
    <aside class="copilot-sheet" aria-hidden="true">
      <iframe id="copilot-iframe" src="http://127.0.0.1:18789/?embed=1" sandbox="allow-scripts allow-forms allow-popups"></iframe>
    </aside>
  </div>
</body>
```

CSS Grid：

```css
.app-shell {
  display: grid;
  grid-template-columns: 256px 1fr;
  grid-template-rows: 56px 1fr;
  grid-template-areas:
    "sidebar topbar"
    "sidebar content";
  height: 100vh;
}
@media (max-width: 1024px) {
  .app-shell {
    grid-template-columns: 64px 1fr;
  }
  .sidebar .nav-label { display: none; }
}
@media (max-width: 768px) {
  .app-shell {
    grid-template-columns: 1fr;
    grid-template-areas: "topbar" "content";
  }
  .sidebar {
    position: fixed; inset: 0 auto 0 0;
    transform: translateX(-100%);
    transition: transform 200ms;
    z-index: 50;
    background: var(--surface);
  }
  .sidebar[data-open="true"] { transform: translateX(0); }
}
```

---

## 2.3 设计系统 / CSS / 主题 / 图标

### 2.3.1 CSS 变量 + data-theme 主题切换（事实为业界 2026 默认范式）`[F]`

来源：
- https://blog.openreplay.com/theme-switcher-css-variables/
- https://dev.to/hasansarwer/a-practical-css-variable-setup-for-lightdark-mode-without-theme-flash-22c2
- https://devtoolbox.dedyn.io/blog/css-custom-properties-complete-guide
- https://www.css-architecture.com/advanced-theming-dark-mode-implementation/prefers-color-scheme-integration/implementing-prefers-color-scheme-without-fouc/
- https://danholloran.me/posts/css-light-dark-stop-duplicating-your-dark-mode-colors

**最佳实践（综合三份以上资料）`[F]`**：

1. **CSS 变量定义在 `:root`**，用 `data-theme` 属性切换
2. **`color-scheme: light dark` 在 `:root`** —— 让原生 UI（滚动条、表单输入、focus ring）跟着主题走
3. **`@media (prefers-color-scheme: dark) :root:not([data-theme="light"])`** —— 没手动选时跟随系统；选了 light 时强制 light
4. **`localStorage` 持久化 + 内联同步脚本（head 内 blocking）** —— 避免 FOUC（Flash of Unstyled Content）
5. **`data-theme` 比 class 更干净** —— 主题是单一值，不是组合状态

```html
<head>
  <script>
    try {
      const t = localStorage.getItem('theme')
        || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      document.documentElement.setAttribute('data-theme', t);
    } catch (_) {}
  </script>
  <style>
    :root { color-scheme: light dark;
      --bg: #ffffff; --surface: #f8fafc; --text: #0f172a; --muted: #64748b;
      --border: #e2e8f0; --primary: #2563eb; --primary-fg: #ffffff;
      --accent: #f59e0b;
    }
    [data-theme="dark"] {
      --bg: #0f172a; --surface: #1e293b; --text: #f1f5f9; --muted: #94a3b8;
      --border: #334155; --primary: #60a5fa; --primary-fg: #0f172a;
      --accent: #fbbf24;
    }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) { /* 重复 dark 变量 */ }
    }
  </style>
</head>
```

**`light-dark()` 函数的取舍**：

- 95% 浏览器支持（Chrome 123+ / Safari 17.5+ / Firefox 120+）`[F — danholloran.me]`
- 好处：一份声明搞定 light/dark，不用 `:root[data-theme="dark"]` 重复块
- 缺点：不能直接支持 3+ 主题（多 brand / solarized 等）；老浏览器需要 fallback `[F — danholloran.me]`
- **本项目建议**：用 `data-theme` + `:root[data-theme]` 范式，留出第三主题（如 "OpenClaw Dash"）的扩展空间 `[J]`

### 2.3.2 图标 / 字体方案 `[F]`

- **图标**：建议 `lucide`（CC0/MIT，~1KB/图标，树摇友好）或 `tabler-icons`（MIT，~300+ 图标）。OpenClaw Control UI 用的是 `@tabler/icons-react` `[F — npmjs.com/package/@lethxrgy/dash-ui]`
- **字体**：默认用系统字体栈（`system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`），避免引入外网字体（local-first）
- **图标 + 字体的本地化目录**：`static/vendor/lucide/` 全部 svg + `static/vendor/fonts/` 系统 fallback `[J]`

### 2.3.3 Tailwind vs 自写 CSS `[F]`

来源：https://kostra.io/features/responsive-design

- Tailwind CSS v4 + JIT：编译快，标准断点（sm/md/lg/xl/2xl），dark mode 默认 `prefers-color-scheme` + 手动 toggle，WCAG 2.1 AA，Framer Motion 动画 + reduced-motion 支持
- 但 Tailwind 引入构建链（PostCSS / Vite / Webpack）+ 体积（runtime zero，但 source 30+ KB）
- **本项目建议**：不引 Tailwind。自写 CSS + 变量 + Grid/Flexbox 已经能覆盖，断点用 `@media`。理由：纯零构建、无 PostCSS 依赖、与现有 app.js 的内联 CSS 风格一致。`[J]`

---

## 2.4 Markdown / 全文搜索 / 图表

### 2.4.1 Markdown 渲染（Obsidian vault 兼容）`[F]`

来源：
- https://www.pkgpulse.com/guides/marked-vs-remark-vs-markdown-it-parsers-2026
- https://markdown-it.github.io/markdown-it/
- https://www.measurethat.net/Benchmarks/Show/35540/1/markdown-performance-comparison-2026
- https://kolavistudio.com/markdown-tools/obsidian

**Markdown 三大库对比（2026）`[F — measurethat.net 基准, PkgPulse 评测]`**：

| 库 | 周下载 | 速度 | 扩展性 | 适合 |
|---|---|---|---|---|
| marked v17 | ~12M | **最快**（~5,445 ops/s on this benchmark vs markdown-it 7,675 ops/s） | 一般 | 直接渲染 |
| markdown-it v14 | ~21M（含 VS Code 间接依赖） | 中 | **最强插件生态** | 需要扩展（Obsidian 风格） |
| remark (unified) | ~8M | 慢 | AST + MDX 化 | Next.js/Astro 文档链 |

**Obsidian Markdown = CommonMark + GFM + 自家扩展** `[F — kolavistudio.com]`：
- `[[wiki-links]]` + `[[Page#Section]]` + `[[Page|Label]]` 双链
- `![[embed]]` 嵌入（含图片）
- `> [!note]` / `> [!warning]` callouts（可折叠）
- `==highlight==` 高亮
- `^block-id` 块引用
- `[[Note#^block-id]]` 块链接
- LaTeX via MathJax

**本项目推荐 markdown-it + 插件** `[J]`：

- 理由：vault 有 1485 篇双链笔记，必须正确渲染 `[[wiki-links]]`；marked 没有原生支持
- 插件组合（事实参考 markdown-it-wikilinks-plus / markdown-it-obsidian-images / markdown-it-shiki 等开源插件）：

```js
import MarkdownIt from 'markdown-it';
import wikiLinks from 'markdown-it-wikilinks-plus';
import obsidianImages from 'markdown-it-obsidian-images';
import shiki from '@shikijs/markdown-it';

const md = new MarkdownIt({ html: true, linkify: true, typographer: true })
  .use(wikiLinks, { uriSuffix: '.md', htmlAttributes: { class: 'wiki-link' } })
  .use(obsidianImages)
  .use(await shiki({ themes: { light: 'github-light', dark: 'github-dark' } }));
```

- **代码高亮 Shiki**：双主题（light/dark），与现有 vault 的代码片段体验最贴近 VS Code 风格；包略大但首次加载后缓存 `[F — pkgpulse.com]`
- **MathJax**：可后置（vault 中 LaTeX 公式少）

### 2.4.2 全文搜索（Fuse.js / Lunr.js / SQLite FTS5）`[F]`

来源：
- https://github.com/formation-res/querylight-ts/blob/main/docs/overview/browser-search-library-comparison.md
- https://mattermost.com/blog/best-search-packages-for-javascript/
- https://www.fusejs.io/
- https://github.com/krisk/Fuse/blob/main/README.md

| 方案 | 模糊匹配 | 全文/BM25 | 索引构建 | 大数据量 | 适合 |
|---|---|---|---|---|---|
| **Fuse.js v7** | ★★★（Bitap 算法，原生支持）`[F]` | 中（token 模式支持 BM25-like IDF）`[F]` | 无（直接 in-memory） | 小-中 | < 10K 文档 / 字段少 |
| **Lunr.js** | ✓（基本） | ★★（stemming + ranking） | 需预构建 | 中 | 静态站点文档搜索 |
| **SQLite FTS5** | △（默认 unicode61 不支持 CJK） | ★★★ | 自动 | 大 | 已有 SQLite 项目 |
| **MiniSearch** | ✓ | ★★ | 动态 | 中-大 | 浏览器 + Node.js |
| **Orama** | ✓ | ✓ | 动态 | 中-大 | 支持 vector + geo |

**Fuse.js 实测体积** `[F — fusejs.io README]`：
- Full build: ~8.6 kB gzip
- Basic build: ~6.8 kB gzip

**vault 1485 个 .md 的搜索建议** `[J]`：

1. **首选 Fuse.js + 延迟加载**（仅在搜索框 focus 时 import 模块 + 倒排索引）
2. **后台构建索引**：后端 Python 服务定期扫 `src/notes/vault/`，生成 `{path, title, headings, tags, snippet}` JSON 列表 → 前端首次加载即用
3. **CJK 友好**：Fuse.js 用 `Intl.Segmenter` 默认 Unicode-aware，可自定义 tokenizer 处理中文 `[F — krisk/Fuse README]`
4. **如未来 vault > 10K 篇**：再迁移到 SQLite FTS5（已经支持中文 trigram 兜底，详见 §3.6）

### 2.4.3 图表库选择（学习统计 / 能量曲线 / 知识图谱）`[F]`

来源：
- https://dataviewer.cloud/chartjs-vs-echarts-vs-recharts-which-library-fits-your-dashboard
- https://devpick.co/chart.js-vs-echarts
- https://www.usedatabrain.com/blog/javascript-chart-libraries
- https://www.pkgpulse.com/guides/best-javascript-charting-libraries-2026

| 库 | 体积 | 渲染 | 大数据 | 树摇 | 学习曲线 | 适合 |
|---|---|---|---|---|---|---|
| **Chart.js v4.5** | ~71 KB gzip (full) / ~92 KB core | Canvas | 10K+（需 decimation） | △（full bundle） | 简单 | 通用仪表盘 |
| **Apache ECharts v6** | ~520 KB full / **~100 KB 树摇后** | Canvas / SVG / WebGL（echarts-gl） | 100K+（LTTB 降采样）+ WebGL | ★★★ | 中 | 数据密集、移动端交互 |
| **Recharts** | ~300 KB | SVG | 小-中 | △ | 简单 | React 项目 |
| **D3.js v7** | ~500 KB | SVG/Canvas | 任意 | ★ | 陡 | 完全自定义 |
| **Visx** | ~50 KB（模块化） | SVG | 小-中 | ★★ | 陡 | React 自定义 |

**本项目建议** `[J]`：

- **学习统计 / 能量曲线**：**Chart.js**——包小、API 简单、足够覆盖"7 日能量线 + 任务完成率柱状 + 抽卡分布饼图"三种典型
- **如果未来要做"知识图谱"**：**Sigma.js + graphology**（详见 §3.5）——这是 Obsidian 同款技术栈
- **不要选 ECharts**——除非确实要画 100K 点以上（学习场景数据量远不到）

### 2.4.4 知识图谱（vault 双链可视化）`[F]`

来源：
- https://www.pkgpulse.com/guides/cytoscape-vs-vis-network-vs-sigma-graph-visualization-2026
- https://weber-stephen.medium.com/the-best-libraries-and-methods-to-render-large-network-graphs-on-the-web-d122ece2f4dc
- https://github.com/cybaea/obsidian-vault-intelligence/commit/78706c5a228a55556617351053e49deae2b85ba8（Semantic Galaxy View 用 Sigma.js + graphology + ForceAtlas2 in Worker + IntersectionObserver + ResizeObserver 防 0×0 WebGL crash）
- https://github.com/multimail-dev/cartographer-obsidian-viz（Float32Array ForceAtlas3 自实现，8500 节点 < 2s）

**对比** `[F — pkgpulse.com]`：

| 库 | 渲染 | 适合 |
|---|---|---|
| **Sigma.js + graphology** | WebGL | 大规模（>1K 节点）知识图谱 |
| **vis-network** | Canvas | 交互式网络图（拖拽、编辑） |
| **Cytoscape.js** | Canvas | 算法 / 路径 / 中心性 |

**本项目 vault 1485 篇**，处于 vis-network 与 Sigma.js 的边界：

- **MVP 建议：Sigma.js + graphology + graphology-layout-forceatlas2（GOTOLITH/Worker 模式）**——为未来 10K+ 预留；Obsidian 自身也用 Sigma.js + graphology
- 性能细节：ForceAtlas2 标准 JS 实现 ~18.2s 跑 8500 节点；ForceAtlas3 自实现（Float32Array 矩阵）可降到 1.9s `[F — cartographer-obsidian-viz README]`——本项目不需要到这个量级

---

## 2.5 嵌入 OpenClaw 的 iframe 工程模式

> 这是与 OpenClaw Control UI 共存的核心技术点。

### 2.5.1 OpenClaw Control UI 自身的嵌入模型 `[F]`

来源：`docs/web/control-ui.md` 326-340（Hosted embeds）、`docs/web/dashboard.md`

**OpenClaw 自己支持嵌入其他内容**：

```json5
{
  gateway: {
    controlUi: {
      embedSandbox: "scripts"  // "strict" | "scripts"（默认） | "trusted"
    }
  }
}
```

- **strict**：禁止所有 script
- **scripts**（默认）：允许 scripts + origin 隔离（self-contained 小工具可跑）
- **trusted**：在 scripts 基础上加 `allow-same-origin`（**仅同站文档需要强权限时**用——如本项目的"嵌入到自己 OpenClaw 实例"场景）

`[F — docs/web/control-ui.md 330-340]`

### 2.5.2 iframe 沙箱 + postMessage 通信规范 `[F]`

来源：
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe
- https://www.performanceisolation.com/third-party-isolation-sandboxing-strategies/building-secure-iframes-for-third-party-widgets/
- https://didit.me/blog/embedded-iframe-security-best-practices/
- https://browseemall.com/iframe-sandbox-attribute-cross-browser-security-guide/
- https://html.spec.whatwg.org/dev/iframe-embed-object.html
- https://usero.io/blog/how-to-embed-a-form-on-website
- https://developer.inlinex.com.sg/blog/iframe-cross-origin-communication-postmessage
- https://bindbee.dev/blog/secure-cross-window-communication
- https://medium.com/aveva-tech/building-secure-widget-systems-with-javascript-iframes-4efd1e7963cc
- https://github.com/davidjbradshaw/iframe-resizer/issues/621

**关键铁律** `[F — MDN, performanceisolation.com]`：

1. **`allow-scripts + allow-same-origin` 绝不能同时给同源内容**——sandbox 形同虚设（iframe 内 JS 可移除 sandbox 属性）
2. **跨域嵌入用 `postMessage`**，且必须 `targetOrigin` 显式指定（不能用 `"*"` 在生产）
3. **父端必须验证 `event.source === iframe.contentWindow`**——多个 iframe 时区分
4. **响应式高度**：iframe 用 `ResizeObserver` 自己测量 `document.body.scrollHeight` 并 postMessage，父端用 listener 更新高度（浏览器跨域看不到 iframe 内部尺寸）
5. **Referrer 策略**：`referrerpolicy="strict-origin-when-cross-origin"`（HTML 标准默认）

### 2.5.3 双向 iframe 通信协议（建议）`[J]`

```
[Super Auto Learn Frontend]                   [OpenClaw Control UI]
       (iframe child in user's browser)        (parent or sibling iframe)
                   │                                  │
   postMessage ──► {                                  │
   { source: 'sal',                                   │
     version: 1,                                       │
     type: 'task.completed',                            │
     payload: { id: 't_42', minutes: 25 } }            │
                   │                                  │
                   │           ◄──── postMessage      │
                   │           { source: 'openclaw',    │
                   │             version: 1,            │
                   │             type: 'chat.message', │
                   │             payload: { ... } }    │
```

**双方协议规范**（最小可行）：

```js
// 父端 OpenClaw Control UI（或我们的页面）
window.addEventListener('message', (event) => {
  if (event.source !== iframe.contentWindow) return;
  const { source, version, type, payload } = event.data || {};
  if (source !== 'sal' || version !== 1) return;
  switch (type) {
    case 'ready': console.log('SAL ready', payload.version); break;
    case 'task.completed':
      // 调用 openclaw chat.inject 把结果贴回聊天
      gatewayRPC('chat.inject', { sessionKey: '...', note: `Task ${payload.id} 完成 ${payload.minutes}min` });
      break;
    case 'resize':
      iframe.style.height = payload.height + 'px';
      break;
  }
});

// 子端（我们的应用）
window.parent.postMessage({
  source: 'sal', version: 1,
  type: 'ready', payload: { version: '0.2.0' }
}, openclawOrigin);

new ResizeObserver(() => {
  window.parent.postMessage({
    source: 'sal', version: 1,
    type: 'resize',
    payload: { height: document.documentElement.scrollHeight }
  }, openclawOrigin);
}).observe(document.documentElement);
```

**两种嵌入方向**：

| 方向 | 谁是父 | 谁是子 | 用途 |
|---|---|---|---|
| **A. SAL 嵌入 OpenClaw** | 我们 | OpenClaw Control UI (`/`) | 用户在 SAL 主界面里点 "💬 Chat" 时，右抽屉拉起 OpenClaw Chat Tab |
| **B. OpenClaw 嵌入 SAL** | OpenClaw Control UI | 我们 | 用户在 OpenClaw Chat 里让 Agent 调 SAL 工具（`config.patch` 或 `tools.effective` 暴露 SAL 工具），或者在 Chat 历史里通过 `[embed ...]` shortcode 显示 SAL 卡片 |

**两种都用 `sandbox="allow-scripts allow-forms allow-popups"`**（不要 `allow-same-origin`）；postMessage + `event.source` 验证是安全基石。`[J — 依据 F iframe-resizer issue 621 与 MDN]`

### 2.5.4 独立访问 vs 嵌入两种形态共存 `[J]`

- **独立访问**（`http://127.0.0.1:5000/`）：完整布局（侧栏 + 顶栏 + Copilot sheet 默认折叠）
- **嵌入态**（被 OpenClaw iframed）：自动隐藏自身侧栏，把顶栏改成更紧凑的 mini 顶栏；通过 postMessage 把用户操作上报给父
- **检测**：`<script>` 内 `window.parent !== window` → 嵌入态；监听 `postMessage('sal:set-mode', { mode: 'compact' | 'full' })`

---

## 2.6 可维护性：原生大单页的拆分策略

### 2.6.1 现有 2711 行 app.js 的问题 `[J]`

从 README 与文件结构推断（具体行号没读全文件）：
- 全局变量多、双计时器状态机紧耦合、各页面 init 散落
- E2E 测试靠 playwright-core，依赖全局 ID（`tests/e2e-manual.js` 26 用例）

### 2.6.2 推荐的拆分策略 `[J]`

**架构：ES modules + 命名空间 + 事件总线 + 状态机**

```
static/
├── index.html                          ← 入口（已存在 src/index.html，复制 + 改为引用 app.js module）
├── app.js                              ← ES module 入口（200 行，启动 + 路由）
├── core/
│   ├── event-bus.js                    ← 极简发布订阅（50 行）
│   ├── state.js                        ← 全局状态 + 订阅（100 行）
│   ├── api.js                          ← fetch 包装（100 行）
│   └── router.js                       ← hash 路由（80 行）
├── modules/
│   ├── gacha/
│   │   ├── index.js                    ← 模块入口（导出 mount/unmount）
│   │   ├── card.js                     ← 卡片组件
│   │   ├── pool.js                     ← 牌池
│   │   └── timer.js                    ← 第一计时器状态机
│   ├── tasks/
│   ├── schedule/
│   ├── state/
│   │   └── energy-chart.js             ← Chart.js 集成
│   ├── knowledge/
│   │   ├── vault.js                    ← vault 浏览
│   │   ├── markdown-render.js          ← markdown-it 集成
│   │   └── graph.js                    ← Sigma.js 集成（可选）
│   ├── inbox/                          ← 未读聚合（OpenClaw bridge）
│   ├── copilot/                        ← OpenClaw Chat 嵌入 + 协议
│   └── settings/
└── vendor/                             ← 本地化的 ESM 依赖
    ├── marked.esm.js
    ├── markdown-it.esm.js
    ├── chart.esm.js
    └── sigma.esm.js
```

**关键规则**：

1. **每个模块导出 `mount(rootEl)` 与 `unmount(rootEl)`**——挂载时初始化 DOM + 绑定事件，卸载时清理
2. **跨模块通信走 event-bus**，不直接调用函数
3. **状态机抽到独立文件**——双计时器拆 `modules/gacha/timer.js` + `modules/tasks/timer2.js`，每个 ~200 行
4. **API 调用统一走 `core/api.js`**——错误处理 / 重试 / 鉴权头注入一处
5. **每页一个 `index.js`，主入口 `app.js` 只做路由 + 懒加载**

### 2.6.3 状态管理建议 `[J]`

- **极简情况**：`core/state.js` 用 Proxy + EventTarget，提供 `state.subscription` API
- **复杂情况**：等真到状态机爆炸再说，不要一开始引 Redux/Zustand/Jotai
- **计时器等长生命周期状态**用 WeakMap 绑 DOM 节点，模块 unmount 时自动 GC

### 2.6.4 测试保留 `[F — AGENTS.md 5/6]`

按 AGENTS.md 第 5/6 条规则：
- **Bug 修复**：先写 RED 测试 → 修 → GREEN → 测试永久保留
- **重构**：先固定行为测试 → 通过 → 再重构
- **现有 `tests/e2e-manual.js` 26 用例是基线**，新结构必须让这些 E2E 全绿，否则不算完成

---

# 方向三 · 外部工程经验方向（12 项逐一调研）

## 3.1 邮件集成

### 3.1.1 协议 / 鉴权事实 `[F]`

来源：
- https://www.unipile.com/imap-api-python/
- https://github.com/mjs/imapclient
- https://imapclient.readthedocs.io/en/master/index.html
- https://pypi.org/project/IMAPClient/
- https://imaplib2.readthedocs.io/en/latest/

- **Gmail 自 2022-05 起阻断标准密码 IMAP 认证**；Microsoft 365 自 2024-09 弃用 IMAP Basic Auth —— **生产环境必须 XOAUTH2（OAuth 2.0 SASL 机制）** `[F — Unipile]`
- 标准库 `imaplib`：零依赖但极 low-level，返回值要手动 parse，UID/flags/timezone 都要自己管 `[F — Unipile / IMAPClient 文档]`
- **IMAPClient**（推荐）：Pythonic 包装 imaplib，UID/flags/国际邮箱名/timezone 自动处理，**测试过 Dovecot / Gmail / Fastmail / Office365 / Yahoo** `[F — IMAPClient 文档]`
- **imaplib2**：imaplib 的 drop-in 替代，支持**并行执行 + IMAP IDLE 扩展**（push 新邮件）`[F — imaplib2 文档]`
- **aioimaplib**：async 库，asyncio 场景用
- **Unipile API**：商业 SaaS，统一 REST/SDK，自动 OAuth token 刷新

### 3.1.2 SMTP 发邮件 `[F]`

- Python 标准库 `smtplib` + `email.message.EmailMessage`——零依赖，够用
- 高级需求（如模板 / 附件 / DKIM 签名）：`yagmail`、`pretty-mail`、`emails`
- Gmail 发信也要 XOAUTH2（与 IMAP 同）

### 3.1.3 OpenClaw 自身 Gmail 集成 `[F]`

来源：`docs/automation/cron-jobs.md` 463-525；`docs/automation/gmail-pubsub.md`

- OpenClaw 用 **Gmail PubSub + Google Cloud Pub/Sub** 接 Gmail 推送
- 一键配置：`openclaw webhooks gmail setup --account openclaw@gmail.com` —— 写 `hooks.gmail` 配置、启用预设、默认走 Tailscale Funnel
- Gateway 启动时自动 `gog gmail watch serve` + 自动续期
- 需要 `gcloud` + `gog`（gogcli）+ Tailscale

### 3.1.4 我的判断 / 推荐方案 `[J]`

**MVP 路径（个人 Gmail / Outlook 接入）**：

1. **后端**：`IMAPClient` + `smtplib`（Python stdlib）
2. **OAuth 流程**：用 `google-auth` + `google-auth-oauthlib`（Gmail）或 `msal`（Outlook）；refresh token 加密存 `config/secrets.json`
3. **新邮件触发**：`imaplib2` 的 IDLE（保持长连接，收到推送后 poll）或轮询（每 60s）
4. **前端**：在"未读聚合"卡片里展示 `[{ from, subject, snippet, time }]`；点击进入详情（独立页面或抽屉）

**进阶（多账号 / 富文本）**：考虑 Unipile API（商业）或自建 `inbox-zero` 风格的多 provider 适配层。

**对接 OpenClaw 路径**：直接复用 OpenClaw 的 `hooks.gmail`——它已经是 PubSub + webhook 闭环，不重复造轮子。我们前端只暴露 `openclaw webhooks gmail setup` 的 UI 即可。

### 3.1.5 本机落地要点 `[J]`

1. **OAuth client_id / client_secret 不能进 git**——用 `config/secrets.json`（已 `.gitignore`）或 OS keychain（参考 FRIDAY 的 `KeyringVault` 模式）
2. **轮询间隔**：邮箱 IDLE 节省资源但需要长连接稳定性；轮询每 60s 是 OpenClaw 默认 cron 触发间隔的友好倍数
3. **大邮箱**：IMAP fetch 用 `SEARCH` + `FETCH` 分页（UID 范围），不要一次 `FETCH 1:*`

---

## 3.2 未读消息聚合（多通道）

### 3.2.1 OpenClaw 自身能力盘点 `[F]`

来源：`docs/channels/`（42 个文件），`docs/web/control-ui.md` 137-142

OpenClaw 已支持 42 个 channels：
- **IM** 类：discord / slack / telegram / whatsapp / imessage / matrix / msteams / googlechat / signal / line / irc / twitch / nextcloud-talk / mattermost / synology-chat / sms / clickclack / tlon / raft / nostr
- **亚洲 IM**：feishu（飞书） / lark / zalo / zaloclawbot / zalouser / qqbot / yuanbao
- **辅助**：location / broadcast-groups / group-messages / channel-routing / bot-loop-protection / pairing / access-groups / groups

OpenClaw 内置 `channels.status` 给前端拉每个 channel 的健康度 + 未读统计 `[F — docs/web/control-ui.md 137]`。

### 3.2.2 轮询 vs Webhook（业界共识）`[F]`

| 通道 | 推荐 | 原因 |
|---|---|---|
| Gmail | **Webhook（PubSub）** | Gmail 自带 watch 机制 |
| Slack | **Webhook（Events API）** | 官方支持 |
| Telegram | **Webhook**（或 long polling fallback） | 官方支持 |
| Discord | **Webhook（Gateway Intents）** | 官方支持 |
| WhatsApp / WeChat | **Webhook（官方）** | 强制 |
| 微信个人号 | **轮询 / hook 客户端**（违规，但开源方案如 wechaty 存在） | 官方不开放 |
| 邮件 IMAP | **IDLE（push）或 60s 轮询** | IDLE 需稳定长连接 |

### 3.2.3 聚合前端模式（业界）

- **Froggo Mission Control**：[Gmail Inbox](https://github.com/ProfFroggo/froggo-mission-control) 卡片：未读列表 + AI triage
- **Arahi AI**：1,500+ apps，统一 inbox
- **Sentient-OS**：Mission Control 主屏显示所有 channel 的 vitals

### 3.2.4 我的判断 `[J]`

**MVP 只做 Gmail + OpenClaw channels 聚合**：

1. **后端**：薄 wrapper `core/api.py` 加 `/api/inbox/unread` 端点
2. **数据源**：
   - Gmail → IMAPClient（或 OpenClaw `hooks.gmail` 事件回调入我们的 DB）
   - OpenClaw channels → 调用 `openclaw channels.status`（CLI）或对应的 WebSocket 事件
3. **前端**：一张"未读聚合"卡片，分组显示 `[Gmail 3] [Slack 5] [Telegram 1]`，每组点击展开 5 条标题/来源/时间

**微信 / QQ 个人号不在 MVP**——官方不开放，会被风控，且会触犯用户规则（合规风险）。

---

## 3.3 日程/日历（ICS / Google Calendar / 与现有 schedule 整合）

### 3.3.1 Python iCal 库对比 `[F]`

来源：
- https://github.com/allenporter/ical/
- https://allenporter.github.io/ical/ical.html
- https://pypi.org/project/ical/14.1.0/
- https://github.com/collective/icalendar/
- https://icalendar.readthedocs.io/en/6.x/index.html

| 库 | 内置 RFC 7986/6868/8536 | 循环展开 | 类型注解 | Python 版本 | 维护状态 |
|---|---|---|---|---|---|
| **ical v14** | ✓ | ✓（无需 recurring-ical-events） | ✓ strict ty | 3.11+ | 活跃 |
| icalendar v7 | 部分 | ✗（需 recurring-ical-events） | ✓ v7+ | 3.8-3.13 | 活跃 |
| ics.py v0.7.2 | ✗ | ✗ | ✗ | 3.8+ | **停滞**（2021-08 后无 release） |
| **caldav**（异步客户端） | — | — | ✓ | 3.8+ | 活跃 |

### 3.3.2 Google Calendar API `[F]`

- 官方：Google Calendar API v3（REST），Python 客户端 `google-api-python-client`
- OAuth 流程同 Gmail（可共用 token）
- 支持 list / insert / update / delete events；支持 watch（webhook）
- Freebusy / ACL 等高级能力

### 3.3.3 现有 schedule 模块（项目内）`[F]`

来源：README.md 181 行 + backend_api.py（具体未读）

- 现有端点：`GET/POST /api/schedule/{weekly,daily,activities}` + `DELETE /api/schedule/activities/<id>` + `GET /api/schedule/slots`
- 表：`weekly_schedule / daily_schedule / activities / slots`
- 已记录睡眠、近 7 日能量、状态评估、日日程格、活动管理

### 3.3.4 我的判断 / 推荐方案 `[J]`

**MVP 路径**：

1. **保留现有 SQLite schedule 表**——它已经是用户的"权威日程"
2. **可选 ICS 导出**：用 `ical` v14 库生成 `.ics` 文件 → `/api/schedule/export.ics` → 用户可导入到 Apple Calendar / Outlook
3. **可选 Google Calendar 双向同步**：用 `google-api-python-client`，每天 1 次 cron 拉取增量 + 推送本地变更；冲突时本地优先（个人助理逻辑）
4. **不做 CalDAV server**——复杂度过高；用户如需自托管日历，可导 `.ics` 后用其他工具同步

**前端**：日历视图用 FullCalendar.io（vanilla JS，~100KB gzip）或自写 CSS Grid；MVP 用简化的"日格 + 周列"即可。

---

## 3.4 通知推送（Web Push + OpenClaw 能力）

### 3.4.1 OpenClaw 自身 Web Push（重要发现）`[F]`

来源：`docs/web/control-ui.md` 296-324

**OpenClaw Control UI 已经实现完整 PWA + Web Push 闭环**：

- 内置 `manifest.webmanifest` + `sw.js`（service worker 处理 push 事件 + notification click）
- 自动生成 VAPID keypair 存在 `push/vapid-keys.json`
- 持久化 browser subscriptions 在 `push/web-push-subscriptions.json`
- 4 个 Gateway RPC 方法：
  - `push.web.vapidPublicKey` —— 取 VAPID 公钥
  - `push.web.subscribe` —— 注册 endpoint + p256dh + auth keys
  - `push.web.unsubscribe` —— 注销
  - `push.web.test` —— 测试通知
- VAPID 私钥可由 `OPENCLAW_VAPID_PUBLIC_KEY` / `OPENCLAW_VAPID_PRIVATE_KEY` / `OPENCLAW_VAPID_SUBJECT` 环境变量覆盖

**结论**：如果我们的应用和 Control UI 在同一域名或同一实例，**直接复用 OpenClaw 的推送**；不要重复实现。

### 3.4.2 业界 Web Push 实施规范 `[F]`

来源：
- https://generalistprogrammer.com/tutorials/web-push-notifications-complete-guide
- https://blog.codercops.com/blog/web-push-notifications-implementation-guide-2026
- https://johal.in/implement-2026-pwa-push-notifications-workbox-70
- https://137foundry.com/articles/how-to-add-web-push-notifications-to-a-progressive-web-app

**三件套**：

1. **VAPID keypair**：服务端生成 P-256 key，公钥给前端订阅用，私钥签名
   - 工具：`npx web-push generate-vapid-keys`（Node）或 `py_vapid`（Python）
2. **Service Worker**：注册 `/sw.js`，监听 `push` 事件 + `notificationclick` 事件
   - 必须 HTTPS（localhost 除外）
3. **后端库**：
   - Node：`web-push` npm 包
   - Python：`pywebpush` pypi 包

### 3.4.3 我的判断 `[J]`

**MVP 推荐：复用 OpenClaw Web Push**，因为：
1. OpenClaw 已经做好了完整链路
2. 我们的应用若也跑 `127.0.0.1`，可以直接 `POST` 到 OpenClaw Gateway 触发推送
3. 避免两套 VAPID key 维护

**自建路径（仅当我们独立域名 / 不依赖 OpenClaw 时）**：

```python
# Python 后端
from py_vapid import Vapid
from pywebpush import webpush

vapid = Vapid.from_file('config/vapid_keys.json')
webpush(
    subscription_info=subscription,  # 来自前端 subscribe() 返回
    data=json.dumps({"title": "任务完成", "body": "..."}).encode('utf-8'),
    vapid_private_key=vapid.private_pem(),
    vapid_claims={"sub": "mailto:admin@example.com"}
)
```

```js
// 前端 sw.js
self.addEventListener('push', event => {
  const data = event.data?.json() ?? {};
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/badge-72.png',
      data: { url: data.url || '/' }
    })
  );
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
```

### 3.4.4 iOS Safari 坑 `[F]`

- iOS Safari 自 2023 起支持 Web Push，**但必须 PWA 安装到 Home Screen 后**才能用 `[F — johal.in]`
- 桌面 Chrome / Edge / Firefox / Safari 全支持

---

## 3.5 数据可视化（学习统计 / 能量曲线 / 知识图谱）

> 图表库选择已在 §2.4.3 给出（**Chart.js** 为主），知识图谱见 §3.6.3。

### 3.5.1 学习统计典型图表 `[J]`

| 图表 | 类型 | 库 | 数据源（项目内） |
|---|---|---|---|
| 7 日能量曲线 | 折线 | Chart.js line | `/api/state/weekly-energy` `[F — README.md 182]` |
| 任务完成率 | 柱状 | Chart.js bar | `/api/gacha/statistics` 或自建聚合 |
| 抽卡分布 | 饼图 | Chart.js doughnut | `/api/gacha/pools/detail` |
| 睡眠 × 能量相关 | 散点 | Chart.js scatter | `/api/state/assessment/{history,correlate}` `[F — README.md 182]` |
| 月度热力 | 热力图 | Chart.js matrix (v4 新) | 自聚合 |
| 任务依赖图 | 网络图 | vis-network | `/api/dependencies` `[F — README.md 180]` |
| 知识图谱 | 网络图 | Sigma.js + graphology | `/api/knowledge/graph` `[F — README.md 185]` |

### 3.5.2 设计原则 `[F — artofstyleframe.com]`

- 图表颜色从 CSS 变量取（`var(--primary)`、`var(--accent)`），跟主题
- WCAG AA 对比度在两种模式下都验证
- 三态（loading / empty / error）必须有

### 3.5.3 我的判断 `[J]`

1. **MVP：Chart.js + vis-network（任务依赖图）**——足够覆盖所有现有数据
2. **不引 ECharts**——本项目数据量小，Chart.js 体积与 API 优势明显
3. **不引 D3**——学习曲线过陡，除非后面要画完全自定义的可视化（如知识图谱的非典型布局）

---

## 3.6 知识库渲染（Obsidian vault / 双链图 / 全文搜索）

### 3.6.1 Markdown 渲染（详见 §2.4.1）

**结论**：**markdown-it + wikiLinks + obsidianImages + shiki** 组合。

### 3.6.2 全文搜索

> §2.4.2 已对比：**MVP 用 Fuse.js**；未来 > 10K 篇迁移 SQLite FTS5。

#### 3.6.2.1 SQLite FTS5 + CJK 实战 `[F]`

来源：
- https://www.sqlite.org/fts5.html
- https://github.com/groue/GRDB.swift/issues/413
- https://sqlite-users.sqlite.narkive.com/N5MOmskp/sqlite-why-sqlite-fts5-unicode61-tokenizer-does-not-support-cjk-chinese-japanese-krean
- https://stackoverflow.com/questions/52422437/why-sqlite-fts5-unicode61-tokenizer-does-not-support-cjkchinese-japanese-krean
- https://zenn.dev/kanseilink/articles/kanseilink-fts5-trigram-cjk-20260507?locale=en
- https://github.com/OpenClaw/.../concepts/memory-builtin.md（OpenClaw 已用 FTS5 + trigram）

**事实**：

1. **FTS5 默认 unicode61 tokenizer 不支持 CJK**——它按 Unicode L/N/Co 类别判断 token，把 `为什么不支持中文` 当成一个 token，无法 BM25 检索 `[F — SQLite FTS5 文档 + 多份 Issue]`
2. **trigram tokenizer**（SQLite 3.34.0+，2020 年）按 3 字符序列索引——**支持 CJK 子串匹配** `[F]`
3. **混合策略（业界实战）`[F — zenn.dev 2026 实战指南]`**：
   - 同时建两张 FTS 表：`fts_unicode61(content, tokenize='unicode61 remove_diacritics 2')` + `fts_trigram(content, tokenize='trigram')`
   - INSERT/UPDATE/DELETE 触发器同步两张
   - 查询路由：`hasCJK(query)` 函数判断，Latin 走 unicode61，3+ 字符 CJK 走 trigram，1-2 字符 CJK 用 `LIKE '%xxx%'` 兜底
   - trigram 不需要 `*`（自带 substring）

**OpenClaw 自身的实现** `[F — docs/concepts/memory-builtin.md 18]`：

> "**CJK support** via trigram tokenization for Chinese, Japanese, and Korean"

—— OpenClaw 已经把 CJK FTS5 跑通，我们如果用 SQLite FTS5 完全可以抄它的实现。

### 3.6.3 知识图谱（双链图）

> 已在 §2.4.4 给出：**Sigma.js + graphology**。

补充事实：
- Obsidian 官方 graph view 用 Canvas 自渲染（不是 Sigma.js）`[F]`
- 但**插件生态大量用 Sigma.js + graphology**（如 Obsidian Vault Intelligence `[F — cybaea/obsidian-vault-intelligence]`）
- Cartographer 的 ForceAtlas3 自实现 8500 节点 < 2s `[F — cartographer-obsidian-viz README]`——本项目 1485 篇用 FA2 已绰绰有余

### 3.6.4 我的判断 / 推荐方案 `[J]`

**MVP**：

1. **Markdown 渲染**：markdown-it + wikiLinks + shiki（语言：中文优先，用 github-light / github-dark 双主题）
2. **全文搜索**：Fuse.js（1485 篇够用），后台索引脚本定期扫 vault
3. **图谱**：v1 不做；v2 加 Sigma.js + graphology（FA2）

**进阶（v2+）**：
- SQLite FTS5 + trigram 双表（迁移到 10K 篇以上时）
- 块引用 / callout 完整支持（markdown-it 插件链）

---

## 3.7 安全与隐私（SQLCipher / Token 管理 / iframe 沙箱 / 局域网鉴权）

### 3.7.1 SQLCipher（SQLite 加密）`[F]`

来源：
- https://charlesleifer.com/blog/encrypted-sqlite-databases-with-python-and-sqlcipher/
- https://github.com/sqlcipher/sqlcipher
- https://github.com/rigglemania/pysqlcipher3/
- https://www.pythonlore.com/securing-sqlite3-databases-with-encryption-techniques/
- https://oneuptime.com/blog/post/2026-02-02-sqlcipher-encryption/view

**事实**：

1. SQLCipher = SQLite 加密 fork，256-bit AES 透明加密，**性能开销 5-15%** `[F]`
2. Python 绑定：`pysqlcipher3` 或 `sqlcipher3-binary`（推荐后者，免编译）
3. **使用方式**（必须先 PRAGMA key）：
   ```python
   import sqlcipher3
   conn = sqlcipher3.connect('data/db.sqlcipher')
   c = conn.cursor()
   c.execute("PRAGMA key='your-password'")           # 或 "PRAGMA key=\"x'64-char-hex'\""
   c.execute("PRAGMA kdf_iter = 256000")              # 提高 PBKDF2 迭代（OWASP 推荐 600000 for 2024）
   ```
4. **轮换 key**：`PRAGMA rekey = 'new-password';`（先 key 后 rekey）
5. **现有 SQLite → SQLCipher 迁移**：
   ```sql
   -- 在 sqlcipher shell 里
   ATTACH DATABASE 'encrypted.db' AS enc KEY 'my password';
   SELECT sqlcipher_export('enc');
   DETACH DATABASE enc;
   ```

### 3.7.2 Token / 密钥管理 `[F]`

- 业界模式（FRIDAY `[F — github.com/LakshyaBadjatya/Friday]`）：
  - **KeyringVault**（OS keychain / Windows Credential Manager / macOS Keychain / Secret Service）
  - **EnvVault**（环境变量）
  - **FileVault 0600**（仅所有者可读的文件）
  - **MemoryVault**（运行时内存，进程结束清空）
- OpenClaw 自身用 `SecretRef` 机制管理敏感配置（`docs/web/control-ui.md` 158-162）：
  - "Writes (`config.set`/`config.apply`/`config.patch`) preflight active SecretRef resolution for refs in the submitted config payload; unresolved active submitted refs are rejected before write"
  - 结构化 SecretRef 对象在表单里只读（防对象被错误序列化为字符串）
  - "Form saves discard stale redacted placeholders that cannot be restored from the saved config"

### 3.7.3 iframe 沙箱（详见 §2.5）

> 关键铁律再重复：`allow-scripts + allow-same-origin` 永不同时给同源内容。

### 3.7.4 局域网暴露时的鉴权 `[F]`

来源：`docs/web/dashboard.md`

- **Localhost**：`http://127.0.0.1:<port>/` 无需鉴权（或 `gateway.auth.token` 即可）
- **非 loopback**：必须四选一：
  - Tailscale Serve（`gateway.auth.allowTailscale: true`）—— 浏览器带 Tailscale 身份头
  - Tailscale Funnel —— 公网 HTTPS
  - 非 loopback bind + `gateway.auth.token`（共享密钥）
  - 非 loopback identity-aware 反代 + `gateway.auth.mode: "trusted-proxy"`
- **绝不**：`bind 0.0.0.0` 且无鉴权 → 任何同网段的人可访问 chat / config / exec approvals（admin surface）

### 3.7.5 我的判断 / 推荐方案 `[J]`

**MVP 路径**：

1. **不要立即上 SQLCipher**——性能开销 + 备份复杂度 + key 管理负担。MVP 用明文 SQLite，但**配置 + vault 目录不进 git**（已是项目红线）。
2. **Token 管理**：跟 OpenClaw 走 SecretRef 模式；我们自己的 API Key（IMAP OAuth 等）存 `config/secrets.json`（`.gitignore`），权限 0600
3. **局域网暴露**：默认 `127.0.0.1:5000`；要跨设备访问走 Tailscale Serve 或 SSH 反代；不要 `bind 0.0.0.0`
4. **iframe 嵌入**：严格 `sandbox="allow-scripts allow-forms allow-popups"` + postMessage + event.source 验证；显式 targetOrigin

**v2 路径**（加密）：
- 数据库 SQLCipher（`sqlcipher3-binary`），启动时从系统 keychain 取 passphrase
- 全盘加密用 LUKS（Linux）/ BitLocker（Windows）/ FileVault（macOS）——比 SQLCipher 更省事

---

## 3.8 PWA / 离线（manifest + service worker + IndexedDB）

### 3.8.1 业界架构事实 `[F]`

来源：
- https://blog.openreplay.com/local-first-pwa-architecture/
- https://techpulsesite.com/how-to-build-an-offline-first-pwa-in-2026-service-workers-and-indexedd/
- https://caasify.com/blog/master-vue-and-vite-build-a-pwa-with-service-worker-and-indexeddb
- https://devblogs.co/posts/build-a-nextjs-16-pwa-with-true-offline-support
- https://mittal-tech.hashnode.dev/progressive-web-apps-with-react-complete-setup-guide-for-developers

**三件套（2026 共识）`[F — blog.openreplay.com]`**：

1. **Service Worker**（应用壳 + 离线）
2. **本地数据库**（IndexedDB 或 OPFS 持久的 SQLite-WASM）
3. **同步引擎**（事件一致性 / 后台同步 / outbox pattern）

**工具**：

- `vite-plugin-pwa`（Vite 项目首选）—— 自动生成 manifest + SW
- `Serwist`（Workbox 7 后继）—— Service Worker 库
- `idb` npm —— IndexedDB Promise 包装（消除 raw API 啰嗦）
- **OPFS-backed SQLite-WASM**——浏览器里的"完整 SQLite"，最快但增加 ~1.5 MB WASM

**local-first vs offline-first 区别** `[F — blog.openreplay.com]`：

> "local-first is a data architecture in which the device holds the primary copy of the data and the server, when present, acts as a sync peer rather than a gatekeeper"

—— 我们默认就是 local-first（SQLite + vault 在本地）；PWA 加的是"离线访问" + "桌面安装" + "OS 级通知"。

### 3.8.2 OpenClaw 自身的 PWA `[F]`

来源：`docs/web/control-ui.md` 296-324

- Control UI 已经 shipped PWA：内置 `manifest.webmanifest` + `sw.js`
- 安装后支持 Web Push
- **结论**：如果 Control UI 与 SAL 在同一域名或通过 reverse proxy 在同一 origin，**直接复用 OpenClaw 的 PWA**——不要重复实现

### 3.8.3 我的判断 `[J]`

**MVP**：

1. **不实现完整 PWA**——OpenClaw Control UI 已经做了
2. **SAL 自身作为 Web App 跑**（浏览器访问），缓存策略：`NetworkFirst` for `/api/*`，`CacheFirst` for `static/vendor/*`，`StaleWhileRevalidate` for `static/*`
3. **若 SAL 是独立域名 / 离线场景**（如出差笔记本），加最小 PWA：
   - `manifest.webmanifest`（name / short_name / icons 192+512 / theme_color / start_url）
   - `sw.js`（cache shell + push 事件）
   - IndexedDB 缓存最近 7 日数据

**进阶**：用 `idb` 把"任务池 / 知识库 / 状态评估"快照缓存到 IndexedDB，离线可读不可写

---

## 3.9 跨设备 / 移动适配（响应式 + OpenClaw iOS/Android canvas 配合）

### 3.9.1 响应式（已在 §2.2.2）

> 移动优先 + 5 个断点 + 侧栏变 drawer + 卡片堆叠 → 1 列

### 3.9.2 OpenClaw 移动端能力 `[F]`

来源：`docs/nodes/index.md`、`docs/nodes/voicewake.md`、`docs/web/control-ui.md` 67-83（Pair mobile device）

- **iOS/Android 节点**：OpenClaw 官方应用（"official iOS/Android app"）
- 配对流程：Control UI → Nodes → Pair mobile device → 显示 QR → iOS/Android 应用扫描
- **iOS**：Voice Wake enable/disable toggle 在 Settings
- **Android**：Voice Wake force-disabled（runtime 强制 Off）；Voice tab 用手动 mic capture
- Web Push 在 iOS 仅在 PWA 安装到 Home Screen 后可用

### 3.9.3 canvas 模式 `[F]`

- OpenClaw 的 iOS/Android 节点是独立的本地应用，**不是 SAL 的移动版**
- 它们共享 Gateway 的 session / chat history
- 移动端访问 SAL = 浏览器打开 `http://<lan-ip>:5000/` 或 Tailscale IP

### 3.9.4 我的判断 `[J]`

1. **SAL 自身的移动端**：用响应式 layout（§2.2）就够了；不做 React Native / Flutter 包壳
2. **SAL 用户在手机上也想聊 OpenClaw**：用 OpenClaw 官方 iOS/Android 应用（共享 Gateway session）
3. **iOS Safari PWA**：如果需要离线访问，把 SAL 也加 manifest + sw，但 MVP 不做
4. **测试覆盖**：playwright-core 加 `--device "iPhone 13"` viewport 测试（现有 E2E 基础设施扩展）

---

## 3.10 语音 / 朗读（Web Speech + 后续 OpenClaw voice/talk 整合）

### 3.10.1 Web Speech API 事实 `[F]`

来源：
- https://www.moreonlinetools.com/en/blog/text-to-speech-web-api-guide/
- https://blog.csdn.net/jugtba/article/details/161308185
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- https://github.com/matthewwoo/cantonese-learner/blob/main/TTS_TROUBLESHOOTING.md
- https://developer.baidu.com/article/detail.html?id=3900609

**TTS 跨平台实测表现** `[F — moreonlinetools.com]`：

| 平台 | 浏览器 | 声音数 | 质量 |
|---|---|---|---|
| Windows 10/11 | Chrome / Edge | 20-30+ | Good（Microsoft voices） |
| macOS | Safari / Chrome | 60-80+ | Excellent（Apple voices） |
| Android | Chrome | 10-30+ | Good（Google voices） |
| iOS | Safari | 50-70+ | Excellent（Apple voices） |
| Linux | Chrome / Firefox | 5-10 | Basic（eSpeak/festival） |

**Firefox 支持有限**，中文发音质量看 OS 装的语言包

**最小示例**：

```js
const u = new SpeechSynthesisUtterance('你好，这是测试');
u.lang = 'zh-CN';
u.rate = 1.0;
u.pitch = 1.0;
u.volume = 1.0;
speechSynthesis.speak(u);

// 必须等 voices 异步加载完才能选声音
speechSynthesis.onvoiceschanged = () => {
  const voices = speechSynthesis.getVoices();
  const zh = voices.find(v => v.lang.startsWith('zh'));
  if (zh) u.voice = zh;
};
```

**autoplay 限制**：必须在用户交互（点击/按键）后才能 speak；Chrome / Edge 最佳支持，Firefox 不可靠 `[F]`

### 3.10.2 OpenClaw 自身 Talk 模式 `[F]`

来源：`docs/nodes/talk.md`

- 5 种 runtime：
  1. Native macOS/iOS/Android Talk（local STT + Gateway chat + `talk.speak` TTS）
  2. iOS Talk realtime（client-owned WebRTC for OpenAI）
  3. Browser Talk（`talk.client.create` / `talk.session.create`）
  4. Android Talk realtime（opt-in `talk.realtime.mode: "realtime"`）
  5. Transcription-only（`talk.session.create({ mode: "transcription" })`）
- TTS provider 配置在 `~/.openclaw/openclaw.json` 的 `talk.providers`：
  - `elevenlabs`（ElevenLabs 云端）
  - `mlx`（本地 MLX）
  - 其他
- **Voice directive in replies**：assistant 回复第一行 JSON `{ "voice": "...", "once": true }` 可控制当前 reply 的声音

### 3.10.3 我的判断 `[J]`

**MVP**：

1. **SAL 自带的 TTS**：用 Web Speech API（零成本，零依赖）—— 在"知识库详情"加 🔊 朗读按钮；MVP 够用
2. **SAL 不做 STT**——那是 OpenClaw 节点的事
3. **如果 OpenClaw 已有 Talk**：SAL 直接调用 `talk.speak` RPC（详见 §3.12），由 Gateway 路由到对应 provider；SAL 不直接调 ElevenLabs

**v2**：

- 接入 ElevenLabs 高质量声音（OpenClaw 已经能配）
- SAL 内置"短消息朗读" chip——读完自动关

---

## 3.11 备份 / 同步（SQLite 备份 + Syncthing + 配置导出）

### 3.11.1 业界同步方案对比 `[F]`

（已在 §1.3.2 列出完整表）

**本项目推荐 Syncthing**：

- 零中心服务器（peer-to-peer）
- BEP 协议 over TLS
- LAN 自发现（mDNS）
- 单二进制 / Docker
- 适合个人多设备
- 缺点：管理多个 device + folder 关系需手动

**多 device 拓扑最佳实践** `[F — knightli.com]`：

1. **星形拓扑**（一个 always-on 设备作 hub，如 NAS / 主力台式机）
2. **手机用 Send Only**，NAS 用 Receive Only（照片单向流）
3. **工作文档用 Send & Receive**（双向）
4. **分发资料用 NAS Send Only + 其他 Receive Only**
5. 在 hub 启用 versioning（错改可回滚）
6. ignore 临时文件（`*.tmp`, `node_modules/`, etc.）

### 3.11.2 SQLite 在线备份 `[F]`

- Python 标准：`sqlite3.connect('file:data/db.sqlite?mode=ro', uri=True)` + `conn.execute("VACUUM INTO 'backup.sqlite'")`（需 SQLite 3.27+，2019）
- 或直接 `shutil.copy2('data/db.sqlite', 'backup/db-YYYY-MM-DD.sqlite')`（需先停服务避免 WAL 写冲突；或用 `.backup` API）
- **冷备份**：`sqlite3 data/db.sqlite ".backup data/backup/db.sqlite"`（在线热备份）

### 3.11.3 配置导出

- `config/config.json` + `config/secrets.json`（**0o600**）—— 直接 `shutil.copy` 到备份目录
- **绝不**进 git（已是事实）

### 3.11.4 我的判断 `[J]`

**MVP（已经在用 + 微调）**：

1. **手动备份脚本**（`scripts/backup_user_data.bat` 已存在 `[F — README.md 130-133]`）：覆盖 `data/task_publisher.db` + `config/` + `src/notes/vault/` + `prompts/` —— 已经够个人用
2. **加 SQLite 热备份**：在备份脚本里用 `sqlite3 .backup` API 而不是 `copy`，避免 WAL 期间复制不完整
3. **不加自动云同步**——按"红线：vault 不出本机"原则

**进阶**：

1. **跨设备同步**：装 Syncthing，把 `data/` + `src/notes/vault/` + `config/` 三目录同步到备用机（手机用 Receive Only 或不参与）
2. **加密备份**：用 `age` 或 `gpg -c` 加密 `.zip` 后丢云盘
3. **OpenClaw 数据**：默认在 `~/.openclaw/`，加入 Syncthing 时注意 SQLite WAL 在多机并发写可能冲突——**单向备份**更稳

---

## 3.12 自动化对接（cron / webhook / OpenClaw memory / Hooks）

### 3.12.1 OpenClaw cron `[F]`

来源：`docs/automation/cron-jobs.md`

**4 种 schedule 类型**：

| 类型 | CLI flag | 描述 |
|---|---|---|
| `at` | `--at` | 一次性（ISO 8601 或相对如 `20m`） |
| `every` | `--every` | 固定间隔（`10m`, `1h`, `1d`） |
| `cron` | `--cron` | 5/6 字段 cron 表达式 + 可选 `--tz` |
| `on-exit` | `--on-exit` | 监视命令退出触发（事件触发） |

**特性**：

- 跑在 Gateway 进程内（Gateway 必须运行才能 fire）
- 作业持久化在 OpenClaw SQLite state
- 每个执行创建 background task
- 一次性作业默认成功后自动删；`--keep-after-run` 保留
- **Webhook delivery mode**：`delivery.mode = "webhook"` + `delivery.to` 设为 HTTP(S) URL；可选 `cron.webhookToken` 作 Bearer 鉴权
- **Event trigger**：作业附 trigger 脚本，cron 到点跑脚本判断 `fire: true / false`，state 在 16KB cap 内持续化
- **top-of-hour 自动 stagger**（5 分钟内）防尖峰；`--exact` 或 `--stagger 30s` 显式覆盖
- **day-of-month + day-of-week 用 OR 逻辑**（Vixie cron 标准）；要用 AND 用 croner 的 `+` 修饰符

### 3.12.2 OpenClaw Webhooks（inbound）`[F]`

来源：`docs/automation/cron-jobs.md` 393-461；`docs/automation/webhook.md`（redirect）

- Gateway 暴露 HTTP webhook endpoints（外部触发）
- 启用：`hooks.enabled: true` + `hooks.path`（**非 `/`**）+ `hooks.token`
- 安全：loopback / tailnet / trusted reverse proxy only；`hooks.allowedAgentIds` 限制目标 agent；`hooks.allowRequestSessionKey` 默认 false
- 重试：默认 3 次（30s / 60s / 5m 退避）
- Bearer token via `cron.webhookToken`

### 3.12.3 OpenClaw Hooks（event-driven）`[F]`

来源：`docs/automation/hooks.md`

**13 个事件类型**（5 大类）：

| 类别 | 事件 |
|---|---|
| **command** | `command:new` / `command:reset` / `command:stop` / `command` |
| **session** | `session:compact:before` / `session:compact:after` / `session:patch` |
| **agent** | `agent:bootstrap` |
| **gateway** | `gateway:startup` / `gateway:shutdown` / `gateway:pre-restart` |
| **message** | `message:received` / `message:transcribed` / `message:preprocessed` / `message:sent` |

**两种 hook**：

- **Internal hooks**（文件目录，Gateway 内执行）—— `HOOK.md` 定义，包名订阅事件
- **Webhooks**（外部 HTTP）—— 上面 3.12.2

还有 **typed plugin hooks**（`api.on(...)`）—— 更结构化，priority / merge / block-cancel 语义

### 3.12.4 OpenClaw Memory 机制 `[F]`

来源：`docs/concepts/memory.md`、`docs/concepts/memory-builtin.md`、`docs/concepts/active-memory.md`

**默认三件套**：

- **`MEMORY.md`** —— 长期记忆，session 启动时加载，受 bootstrap 文件预算限制（超限会截断）
- **`memory/YYYY-MM-DD.md`**（或 `memory/YYYY-MM-DD-<slug>.md`）—— 每日笔记，被 `memory_search` + `memory_get` 索引，但不在 bootstrap 里全量注入
- **`DREAMS.md`**（可选）—— Dream 日志 + sweep 总结

**默认存储**：`~/.openclaw/agents/<agentId>/agent/openclaw.sqlite`，FTS5 + 向量索引；可选 `sqlite-vec` 加速向量查询

**Action-sensitive memory**：包含审批要求 / 时效 / 来源权威时，需要 capture 时机（不是事实本身）

**Active-memory 插件**（bundled）：

- 在每次主回复前跑 blocking memory recall sub-agent
- 命中"相关记忆"才注入到 hidden system context
- 默认开启 + scoped 到 `main` agent + direct-message sessions
- modelFallback 配置
- 持久化 transcript 可选

### 3.12.5 我的判断 `[J]`

**SAL 与 OpenClaw 自动化对接的三层**：

1. **SAL 自己 cron**：本地简单任务（每日提醒 / 自动备份）用 Windows 任务计划程序 或 Python `apscheduler`，不依赖 OpenClaw
2. **SAL → OpenClaw webhook**：当 SAL 内部触发（如"任务超时 1 小时"），POST 到 OpenClaw Gateway `/hooks/...` 端点，让 OpenClaw 决定怎么响应（如发邮件 / 推 push / 启动 agent turn）
3. **OpenClaw → SAL callback**：OpenClaw cron 跑完把结果 webhook 回 SAL（`POST /api/openclaw/callback`），SAL 写 DB + 更新 UI

**memory 集成**：

1. **SAL vault 可作为 OpenClaw memory 的附加源**：`memorySearch.sources` 加 `[{ type: 'file', path: '/path/to/src/notes/vault' }]`（OpenClaw 已支持 `index Markdown files outside the workspace` `[F — docs/concepts/memory-builtin.md 99-103]`）
2. **SAL 读 OpenClaw memory**：直接读 `~/.openclaw/agents/<agentId>/agent/openclaw.sqlite`（只读）；或通过 Gateway 的 `memory_search` / `memory_get` RPC

**Hooks 集成**：

1. SAL 不实现 OpenClaw hooks
2. SAL 用 OpenClaw hooks 订阅 13 个事件来自动化 SAL 行为（如 `message:sent` 后 SAL 更新仪表盘；`session:compact:after` 后 SAL 备份 vault）

### 3.12.6 本机落地要点 `[J]`

1. **Webhook URL 永远用绝对路径** + `https` + dedicated token
2. **避免无限循环**：SAL 触发 OpenClaw webhook，OpenClaw 响应后再调 SAL，SAL 又触发 OpenClaw……必须做 circuit breaker 或 idempotency key
3. **OpenClaw state dir 默认在用户目录**：跨用户 / 跨机部署要 `OPENCLAW_STATE_DIR` override

---

# 4. 落地优先级排序（对 MVP 而言）

> **MVP 定义**：MVP = "在 SAL 现有 Flask 后端 + 原生 HTML/JS 单页基础上，把 OpenClaw 的能力以桥接方式接到 SAL 仪表盘 + 可嵌入 OpenClaw Chat"。**不重写后端，不重写 OpenClaw**。

## P0（必须做，否则不算 MVP）

| # | 任务 | 工作量 | 出处 |
|---|---|---|---|
| 0 | **app.js ES modules 拆分**（§2.6）—— 把 2711 行拆 `core/ + modules/`，跑通现有 26 个 E2E | 3-5 天 | §2.6.2 |
| 1 | **侧栏 + 顶栏 + 卡片网格 layout**（§2.2）—— CSS Grid + 响应式 | 1-2 天 | §2.2 |
| 2 | **dark mode + light-dark() + localStorage 持久化**（§2.3）—— 无 FOUC | 0.5 天 | §2.3.1 |
| 3 | **Copilot sheet 拉起 OpenClaw Chat iframe**（§2.5）—— 双向 postMessage 协议 v1 | 1-2 天 | §2.5.3 |
| 4 | **现有 5 个核心页（gacha / tasks / schedule / knowledge / config）全部迁移到新 layout** | 2-3 天 | §2.6 |
| 5 | **OpenClaw Web Push 接入**（§3.4）—— 复用 Control UI 的 VAPID + RPC | 0.5 天 | §3.4.3 |

## P1（强烈推荐，MVP 后立刻做）

| # | 任务 | 工作量 | 出处 |
|---|---|---|---|
| 6 | **未读聚合卡片**（§3.2）—— Gmail + OpenClaw channels.status | 2 天 | §3.2.4 |
| 7 | **能量曲线 Chart.js 集成**（§3.5）—— 现有 weekly-energy API | 0.5 天 | §2.4.3 + §3.5 |
| 8 | **vault Markdown 渲染升级**（§3.6）—— markdown-it + wikiLinks + shiki | 1-2 天 | §2.4.1 |
| 9 | **Fuse.js 全文搜索**（§3.6）—— 后台索引 + 前端 fuzzy search | 1 天 | §2.4.2 |
| 10 | **memory bridge**（§3.12）—— SAL vault 加入 OpenClaw memorySearch.sources | 1 天 | §3.12.5 |

## P2（半年内做）

| # | 任务 | 工作量 | 出处 |
|---|---|---|---|
| 11 | **Gmail IMAP 收发**（§3.1）—— IMAPClient + smtplib + OAuth | 3-5 天 | §3.1.4 |
| 12 | **本地日历 ICS 导出**（§3.3）—— ical v14 库 | 1 天 | §3.3.4 |
| 13 | **Google Calendar 双向同步**（§3.3）—— google-api-python-client | 3-5 天 | §3.3.4 |
| 14 | **PWA 离线支持**（§3.8）—— manifest + sw + IndexedDB idb 缓存 | 2-3 天 | §3.8.3 |
| 15 | **Syncthing 跨设备同步配置**（§3.11）—— 自动同步 data + vault + config | 0.5 天配置 | §3.11.4 |
| 16 | **OpenClaw cron callback**（§3.12）—— cron 跑完 webhook 回 SAL | 2 天 | §3.12.5 |
| 17 | **Web Speech API 朗读按钮**（§3.10）—— vault 详情页 🔊 | 0.5 天 | §3.10.3 |
| 18 | **信任分层 + 审批队列 UI**（§1.4.4）—— 暴露 OpenClaw exec.approvals | 2-3 天 | §1.4 |

## P3（探索性 / 长期）

| # | 任务 | 工作量 | 出处 |
|---|---|---|---|
| 19 | **知识图谱 Sigma.js + graphology**（§3.6） | 3-5 天 | §2.4.4 + §3.6.3 |
| 20 | **SQLCipher 数据库加密**（§3.7） | 1-2 天 | §3.7.1 |
| 21 | **CalDAV server 自托管**（§3.3） | 1 周+ | §3.3.4（不推荐） |
| 22 | **ElevenLabs 高质量 TTS 接入**（§3.10） | 1 天 | §3.10.3 |
| 23 | **多 device 自管群组**（§3.12） | 1 周+ | §3.12 |
| 24 | **OpenClaw hook 订阅 13 事件**（§3.12） | 1 周+ | §3.12.3 |

## 总估算

- **P0**: ~10-13 天单人 = **MVP 2 周内可上**
- **P0+P1**: ~17-22 天单人 = **MVP + 桥接核心 = 1 个月内**
- **全部 P2**: + 3 周 = **3 个月内成熟**
- **P3**: 1 个季度起

---

# 5. 风险与未知点

## 5.1 已识别风险（按严重度）

| 风险 | 等级 | 描述 | 缓解 |
|---|---|---|---|
| **OpenClaw 文档版本与本机安装版本不一致** | 中 | 调研基于 `node_modules\openclaw\docs`，但运行的是哪个版本？`gateway.version` / `docs.json` 版本字段 | 在 SAL 启动时调用 `openclaw status` 验证；记到 `WORK_LOG.md` |
| **app.js 2711 行拆分时回归** | 高 | 现有 26 个 E2E 用例是基线，拆分时极易引入 bug | AGENTS.md 规则 5：先写回归测试（已存在 E2E），再拆分；拆分后 E2E 全绿才算 |
| **iframe sandbox + postMessage 与 OpenClaw 默认 `embedSandbox: "scripts"` 兼容** | 中 | OpenClaw 默认 sandbox = "scripts"，我们嵌入到 OpenClaw 时 OpenClaw 给的权限可能不够；反过来 OpenClaw 嵌入我们时我们也只给 "allow-scripts" | 提前定义好协议 + 真实两端对接测试 |
| **vault 不进 git 但 Syncthing 多机同步冲突** | 中 | 多机同时编辑同一篇笔记时 SQLite / Markdown 都会冲突 | Syncthing 用 Send & Receive + Staggered File Versioning；SQLite 用 single-writer 模型（hub 写，其他 Receive Only） |
| **OpenClaw Web Push 与 SAL 自身 Web Push 重复** | 低 | OpenClaw 已实现 VAPID + SW；SAL 再做一份会冲突 | 直接复用（§3.4.3）；SAL 只暴露订阅 UI |
| **OAuth refresh token 过期 / 撤销** | 中 | Gmail / Outlook refresh token 可能被用户撤销或失效 | 后端 401 → 触发 OAuth 重新授权流程；UI 弹"重新连接"提示 |
| **SQLite + Syncthing 跨机并发写** | 高 | SQLite 是文件锁，多机同时写必冲突 | 不跨机写——单设备写，其他 Receive Only 备份 |
| **OpenClaw Gateway 进程退出 / 重启时 SAL 桥接失败** | 中 | 所有桥接依赖 Gateway WS；重启时 SAL 需优雅降级 | 前端检测 WS 断开 → 显示 "OpenClaw 离线" chip，但本地功能继续 |
| **iOS Safari Web Push 限制** | 低 | 必须 PWA 安装到 Home Screen | README 文档说明；不强求 |
| **CJK FTS5 性能** | 中 | vault 1485 篇用 Fuse.js 没问题，但 10K+ 篇时 trigram + like 兜底可能慢 | 切到 SQLite FTS5 双表策略（§3.6.2） |

## 5.2 未知点（需要进一步调研或问用户）

| 未知点 | 需要确认的内容 |
|---|---|
| **OpenClaw 当前安装版本** | `openclaw status` / `openclaw --version`；可能影响 Web Push 行为、`embedSandbox` 配置项可用性 |
| **OpenClaw 是否在 docker / bare metal / VPS 跑** | 影响网络访问模型（loopback vs tailnet vs 反代） |
| **目标部署形态** | 单机 / 多机 / VPS？本地优先还是有外网访问需求？决定 PWA / Web Push / Syncthing 优先级 |
| **是否计划接 iOS / Android 节点** | OpenClaw 的 iOS/Android 应用是另一个 app，不是 SAL 的移动版；用户预期是？ |
| **微信 / QQ 个人号集成需求** | 官方不开放；走 wechaty 等第三方有合规风险；用户必须知情同意 |
| **是否需要多用户** | SAL 现在是单用户；如果未来多用户，OAuth / RBAC / vault 隔离方案完全不同 |
| **是否需要 OpenClaw voice/talk 高质量 TTS** | Edge TTS 免费的，ElevenLabs 付费；用户预算？ |
| **vault 规模预期** | 1485 篇 → 5K → 10K；选 Fuse.js vs SQLite FTS5 阈值 |
| **OpenClaw memory 是否要纳入 SAL 检索** | 默认 OpenClaw memory 不含 vault；要明确告诉用户"我把 vault 加进 OpenClaw memory 检索范围" |
| **是否启用 PWA / 离线模式** | 出差 / 移动场景是否核心？决定 §3.8 投入 |

## 5.3 合规与隐私红线（继承项目）

1. **vault 不进 git**——已成立（AGENTS.md / README.md 红线）
2. **OAuth token 不进 git**——`config/secrets.json` 已 `.gitignore`
3. **局域网暴露要鉴权**——OpenClaw 自身强烈警告，本项目必须遵守
4. **iframe 不允许 `allow-same-origin + allow-scripts`** 同源组合
5. **跨设备同步 vault 默认单向备份**——多机写必冲突

---

# 6. 一句话决策建议

> **MVP 走"原生 ES modules 拆分 + OpenClaw 桥接 + 双向 iframe 嵌入"路径**：把 2711 行 app.js 用 ES modules 拆分为 `core/` + `modules/*`（侧栏 256px + 卡片网格 + dark mode 范式照抄 artofstyleframe.com），Gmail IMAP / 全文搜索 / Web Push / 未读聚合 / Markdown 渲染全部桥接 OpenClaw 已实现的能力（VAPID / channels.status / `memorySearch.sources` / hooks.gmail），SAL 与 OpenClaw 通过 `postMessage` 协议 v1（`source + version + type + payload` + `event.source` 校验）双向嵌入，技术栈零构建、零 npm、所有 vendor 库本地化；PWA / Sigma 知识图谱 / SQLCipher 加密暂缓。

---

# 附录 A · 全部来源清单（去重、按方向分组）

## A.1 联网（Web Search / Perplexity 系列）

### 方向一 · 产品形态
- https://open-techstack.com/blog/open-webui-vs-librechat-vs-anythingllm-2026/
- https://dreaming.press/posts/open-webui-vs-librechat-vs-anythingllm.html
- https://toolhalla.ai/blog/open-webui-vs-anythingllm-vs-librechat-2026
- https://onyx.app/insights/openwebui-vs-librechat-vs-onyx
- https://www.local-llm.net/compare/open-webui-vs-librechat-vs-anythingllm/
- https://github.com/ProfFroggo/froggo-mission-control
- https://github.com/kevinreber/aura
- https://arah.ai/personal-assistant
- https://www.vellum.ai/blog/best-ai-assistants-to-automate-your-work
- https://github.com/gestas666/Sentient-OS
- https://github.com/skygkruger/semblance-core
- https://github.com/LakshyaBadjatya/Friday
- https://github.com/PeopleWonder/wylde
- https://github.com/The-Geek-Freaks/NEOTH
- https://github.com/HarshkumarG007/PROMETHEUS

### 方向二 · 前端设计
- https://www.slant.co/versus/15409/45584/~preact_vs_alpine-js
- https://www.alphabold.com/preact-vs-react/
- https://www.pkgpulse.com/guides/preact-vs-react-2026
- https://www.pagespeedmatters.com/resources/data-studies/core-web-vitals-by-javascript-framework
- https://www.pkgpulse.com/guides/react-vs-vue-2026
- https://dev.to/_7fb6011b57d383122b5a/vanilla-javascript-with-zero-build-tools-in-2026-shipping-es-modules-via--1mg8
- https://hadezuka.dev/your-build-tool-just-cost-you-3-hours-today-heres-the-no-bundler-fix/
- https://docs.bswen.com/blog/2026-02-21-single-file-javascript-apps/
- https://gist.github.com/kristoferjoseph/a838c0fd183b2ed3246b140d1d511d8c
- https://johal.in/opinion-frontend-frameworks-are-overkill-vanilla-js-2026-opinion
- https://artofstyleframe.com/blog/dashboard-design-patterns-web-apps/
- https://registry.npmjs.org/@lethxrgy/dash-ui
- https://getcraftly.dev/blog/build-admin-dashboard-nextjs
- https://thefrontkit.com/blogs/react-dashboard-template-guide
- https://kostra.io/features/responsive-design
- https://blog.openreplay.com/theme-switcher-css-variables/
- https://dev.to/hasansarwer/a-practical-css-variable-setup-for-lightdark-mode-without-theme-flash-22c2
- https://devtoolbox.dedyn.io/blog/css-custom-properties-complete-guide
- https://www.css-architecture.com/advanced-theming-dark-mode-implementation/prefers-color-scheme-integration/implementing-prefers-color-scheme-without-fouc/
- https://danholloran.me/posts/css-light-dark-stop-duplicating-your-dark-mode-colors
- https://www.pkgpulse.com/guides/marked-vs-remark-vs-markdown-it-parsers-2026
- https://markdown-it.github.io/markdown-it/
- https://www.measurethat.net/Benchmarks/Show/35540/1/markdown-performance-comparison-2026
- https://kolavistudio.com/markdown-tools/obsidian
- https://dataviewer.cloud/chartjs-vs-echarts-vs-recharts-which-library-fits-your-dashboard
- https://devpick.co/chart.js-vs-echarts
- https://lalatenduswain.medium.com/the-complete-guide-to-javascript-charting-libraries-in-2026-choosing-the-right-visualization-tool-dac9aeb15f60
- https://www.usedatabrain.com/blog/javascript-chart-libraries
- https://www.pkgpulse.com/guides/best-javascript-charting-libraries-2026
- https://github.com/formation-res/querylight-ts/blob/main/docs/overview/browser-search-library-comparison.md
- https://mattermost.com/blog/best-search-packages-for-javascript/
- https://www.fusejs.io/
- https://robbiepalmer.me/projects/personal-site/adrs/022-fuse-js
- https://github.com/krisk/Fuse/blob/main/README.md
- https://www.pkgpulse.com/guides/cytoscape-vs-vis-network-vs-sigma-graph-visualization-2026
- https://weber-stephen.medium.com/the-best-libraries-and-methods-to-render-large-network-graphs-on-the-web-d122ece2f4dc
- https://github.com/cybaea/obsidian-vault-intelligence/commit/78706c5a228a55556617351053e49deae2b85ba8
- https://github.com/multimail-dev/cartographer-obsidian-viz
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe
- https://www.performanceisolation.com/third-party-isolation-sandboxing-strategies/building-secure-iframes-for-third-party-embed-content/
- https://didit.me/blog/embedded-iframe-security-best-practices/
- https://browseemall.com/iframe-sandbox-attribute-cross-browser-security-guide/
- https://html.spec.whatwg.org/dev/iframe-embed-object.html
- https://usero.io/blog/how-to-embed-a-form-on-website
- https://developer.inlinex.com.sg/blog/iframe-cross-origin-communication-postmessage
- https://bindbee.dev/blog/secure-cross-window-communication
- https://medium.com/aveva-tech/building-secure-widget-systems-with-javascript-iframes-4efd1e7963cc
- https://github.com/davidjbradshaw/iframe-resizer/issues/621

### 方向三 · 12 项工程经验
- 3.1 邮件：`https://www.unipile.com/imap-api-python/` / `https://github.com/mjs/imapclient` / `https://imapclient.readthedocs.io/en/master/index.html` / `https://pypi.org/project/IMAPClient/` / `https://imaplib2.readthedocs.io/en/latest/`
- 3.3 日历：`https://github.com/allenporter/ical/` / `https://allenporter.github.io/ical/ical.html` / `https://pypi.org/project/ical/14.1.0/` / `https://github.com/collective/icalendar/` / `https://icalendar.readthedocs.io/en/6.x/index.html`
- 3.4 Web Push：`https://generalistprogrammer.com/tutorials/web-push-notifications-complete-guide` / `https://blog.codercops.com/blog/web-push-notifications-implementation-guide-2026` / `https://johal.in/implement-2026-pwa-push-notifications-workbox-70` / `https://137foundry.com/articles/how-to-add-web-push-notifications-to-a-progressive-web-app`
- 3.6 FTS5 CJK：`https://www.sqlite.org/fts5.html` / `https://github.com/groue/GRDB.swift/issues/413` / `https://sqlite-users.sqlite.narkive.com/N5MOmskp/sqlite-why-sqlite-fts5-unicode61-tokenizer-does-not-support-cjk-chinese-japanese-krean` / `https://stackoverflow.com/questions/52422437/why-sqlite-fts5-unicode61-tokenizer-does-not-support-cjkchinese-japanese-korean` / `https://zenn.dev/kanseilink/articles/kanseilink-fts5-trigram-cjk-20260507?locale=en`
- 3.7 SQLCipher：`https://charlesleifer.com/blog/encrypted-sqlite-databases-with-python-and-sqlcipher/` / `https://github.com/sqlcipher/sqlcipher` / `https://github.com/rigglemania/pysqlcipher3/` / `https://www.pythonlore.com/securing-sqlite3-databases-with-encryption-techniques/` / `https://oneuptime.com/blog/post/2026-02-02-sqlcipher-encryption/view`
- 3.8 PWA / IndexedDB：`https://blog.openreplay.com/local-first-pwa-architecture/` / `https://techpulsesite.com/how-to-build-an-offline-first-pwa-in-2026-service-workers-and-indexedd/` / `https://caasify.com/blog/master-vue-and-vite-build-a-pwa-with-service-worker-and-indexeddb` / `https://devblogs.co/posts/build-a-nextjs-16-pwa-with-true-offline-support` / `https://mittal-tech.hashnode.dev/progressive-web-apps-with-react-complete-setup-guide-for-developers`
- 3.10 Web Speech / TTS：`https://www.moreonlinetools.com/en/blog/text-to-speech-web-api-guide/` / `https://blog.csdn.net/jugtba/article/details/161308185` / `https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API` / `https://github.com/matthewwoo/cantonese-learner/blob/main/TTS_TROUBLESHOOTING.md` / `https://developer.baidu.com/article/detail.html?id=3900609`
- 3.11 备份 / Syncthing：`https://dev.to/selfhostingsh/nextcloud-vs-syncthing-which-file-sync-to-use-5bk2` / `https://appmus.com/vs/syncthing-vs-freefilesync` / `https://zipdo.co/best/folder-sync-software/` / `https://cloudbasedbackup.com/en/blog/nextcloud-vs-syncthing-which-self-hosted-solution-is-right-for-you` / `https://knightli.com/en/2026/05/31/syncthing-multi-device-folder-management/`

## A.2 本地 OpenClaw 文档（`D:\Axelit\工作软件\node_modules\openclaw\docs`）

> 相对路径均相对项目根；绝对路径为 `D:\Axelit\工作软件\node_modules\openclaw\docs\...`

### web/（浏览器侧）
- `web/control-ui.md`（主仪表盘，包含 What-it-can-do 列表、PWA + Web Push、Hosted embeds、Sidebars 章节）
- `web/webchat.md`（macOS/iOS SwiftUI 客户端 + Control UI Chat Tab）
- `web/dashboard.md`（Gateway 仪表盘 + auth 矩阵）
- `web/tui.md`
- `web/index.md`

### automation/（调度与触发）
- `automation/index.md`
- `automation/cron-jobs.md`（at/every/cron/on-exit；Webhooks + Gmail PubSub 集成；Trigger scripts）
- `automation/webhook.md`（redirect 到 cron-jobs#webhooks）
- `automation/gmail-pubsub.md`（redirect）
- `automation/hooks.md`（13 事件类型 + 两种 hook）
- `automation/tasks.md` / `automation/taskflow.md` / `automation/clawflow.md`
- `automation/standing-orders.md`
- `automation/poll.md`
- `automation/auth-monitoring.md`
- `automation/cron-vs-heartbeat.md`
- `automation/troubleshooting.md`

### channels/（42 个 channel 配置）
- 完整文件列表见本报告 §1.2 表格（discord / slack / telegram / whatsapp / imessage / matrix / msteams / googlechat / signal / line / irc / twitch / nextcloud-talk / mattermost / synology-chat / sms / clickclack / tlon / raft / nostr / feishu / zalo / zaloclawbot / zalouser / qqbot / yuanbao / location / broadcast-groups / group-messages / channel-routing / bot-loop-protection / pairing / access-groups / groups / imessage-from-bluebubbles / matrix-push-rules / matrix-presentation / matrix-migration / troubleshooting / index）
- `channels/index.md` 概览

### concepts/（概念与机制，50 个文件）
- `concepts/memory.md`（MEMORY.md / memory/YYYY-MM-DD.md / DREAMS.md；action-sensitive memory）
- `concepts/memory-builtin.md`（SQLite FTS5 + trigram CJK + sqlite-vec；10 个 embedding provider）
- `concepts/memory-search.md` / `concepts/memory-qmd.md` / `concepts/memory-honcho.md`
- `concepts/active-memory.md`（blocking memory recall sub-agent 插件）
- `concepts/agent.md` / `concepts/agent-workspace.md` / `concepts/agent-runtimes.md` / `concepts/agent-loop.md`
- `concepts/multi-agent.md`
- `concepts/oauth.md`（OAuth 机制）
- `concepts/architecture.md`
- `concepts/session.md` / `concepts/session-tool.md` / `concepts/session-pruning.md`
- `concepts/messages.md` / `concepts/message-lifecycle-refactor.md`
- `concepts/compaction.md`
- `concepts/context.md` / `concepts/context-engine.md`
- `concepts/markdown-formatting.md`
- `concepts/streaming.md` / `concepts/typing-indicators.md` / `concepts/typebox.md` / `concepts/system-prompt.md`
- `concepts/soul.md`
- `concepts/timezone.md`
- `concepts/models.md` / `concepts/model-providers.md` / `concepts/model-failover.md`
- `concepts/queue.md` / `concepts/queue-steering.md`
- `concepts/presence.md` / `concepts/commitments.md`
- `concepts/progress-drafts.md`
- `concepts/usage-tracking.md` / `concepts/qa-matrix.md` / `concepts/qa-e2e-automation.md`
- `concepts/parallel-specialist-lanes.md`
- `concepts/dreaming.md`
- `concepts/features.md` / `concepts/experimental-features.md`
- `concepts/personal-agent-benchmark-pack.md`
- `concepts/managed-worktrees.md`
- `concepts/delegate-architecture.md`
- `concepts/mantis.md` / `concepts/mantis-slack-desktop-runbook.md`
- `concepts/channel-docking.md`

### nodes/（iOS/Android/macOS 节点 + 音频）
- `nodes/index.md`
- `nodes/voicewake.md`（全局 wake word 列表；Gateway-owned 同步协议；Trigger list / Routing / Events）
- `nodes/talk.md`（5 种 runtime + 14 voice directive 字段 + providers 配置）
- `nodes/audio.md` / `nodes/images.md` / `nodes/camera.md` / `nodes/media-understanding.md` / `nodes/location-command.md`
- `nodes/troubleshooting.md`

### 其他顶层文档
- `index.md`
- `AGENTS.md`（OpenClaw 自身 AGENTS 规则，与本项目 `AGENTS.md` 区分）
- `docs.json`（58KB 索引）
- `docs_map.md`（225KB 全文档地图）
- `auth-credential-semantics.md`
- `agent-runtime-architecture.md` / `openclaw-agent-runtime.md`
- `date-time.md` / `network.md` / `logging.md` / `vps.md`
- `style.css` / `prose.md` / `nav-tabs-underline.js`
- `brave-search.md` / `perplexity.md`（搜索 provider 配置）

### 已识别但本次未深读的目录
- `install/`, `start/`, `gateway/`, `reference/`, `security/`, `release-notes/`, `snippets/`, `specs/`, `plan/`, `tools/`, `providers/`, `platforms/`, `plugins/`, `maturity/`, `clawhub/`, `cli/`, `refactor/`, `diagnostics/`, `debug/`, `help/`, `announcements/`, `i18n/`

> 本次调研仅深入读了与"前端形态 + 嵌入 + memory + cron/hooks + gmail + nodes talk/voicewake"最相关的子集；其余目录（如 `gateway/`, `install/`, `security/`, `reference/`）建议在 P1+ 阶段按需深读。

---

*报告结束。本报告只调研、未写实现；任何代码修改需要后续单独任务执行。*