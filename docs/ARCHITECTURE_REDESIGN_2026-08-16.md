# 架构重设计文档（2026-08-16）

> 适用项目：`超级自动化学习工具`
> 提出原因：`server/backend_api.py`（3219 行）+ `static/app.js`（2674 行）+ `src/index.html`（947 行，含 ~495 行内联 CSS）三文件单点维护成本已超阈值。
> 用户最高原则：**所有项目都要打造成高内聚、低耦合的模块化工程**——便于维护/更新、便于找 bug、便于借鉴他人高明架构。大文件必拆。

---

## 1. 现状

### 1.1 实测规模（2026-08-16 复核）

| 文件 | 行数 | 性质 | 风险 |
|---|---|---|---|
| `server/backend_api.py` | **3219** | Flask 单文件，21 个 `@app.route` 直接挂全局 `app` | 无 Blueprint、无工厂、全局 CONFIG/DB_PATH |
| `static/app.js` | **2674** | 前端全部业务逻辑，单文件 | 零 ES modules、~80 个 let/var、双计时器独立 |
| `src/index.html` | **947** | 单页 + ~495 行内联 CSS | 翻牌块 2 次重复样式 |
| `src/tasks/` | 218KB / 多文件 | PySide6 桌面端遗留层 | 与 Web 后端 90% schema 重复、抽卡算法也双份 |
| `static/test.js` | 5 行 | 死脚本 | 失效可清理 |

### 1.2 关键症状

1. **后端无 Blueprint**：21 个路由散落，无工厂无 DI，测试无法替换 CONFIG/DB
2. **后端 schema 双源**：`backend_api.py` 内嵌 12 个 `ensure_*` 与 `src/tasks/models/database.py` 完整声明**实际入 DB 的表**不一致
3. **抽卡算法裸奔**：行 1019-1240 整段内联无接口隔离，红线算法
4. **AI Agent 路由裸奔**：行 2852-2999 `/api/agent/*` 前端未接，安全审计盲点
5. **前端单文件**：零模块化，跨域函数直接调，IIFE-free 共享全局
6. **双计时器独立**：`timerDockSession` vs `timerActiveSession` 状态机分裂，god state
7. **桌面端死代码 + 业务双份**：gacha/task/state 三服务与 Web 完全平行实现
8. **index.html 内联 CSS ~500 行**：无法按需加载、首屏阻塞

---

## 2. 目标架构

### 2.1 三套候选方案对比

| 维度 | A. 六边形 + DI 库 | B. Plugin-sdk + 插件式 | **C. Blueprint + Factory + Service/Repository + Feature ESM（选定）** |
|---|---|---|---|
| 精简性 | 低（适配层 + import-linter + 装饰器） | 中（PluginEntry 样板） | **高（仅 Flask 原生 + 浏览器原生 ESM）** |
| 可维护性 | 高（理论） | 中（需中央注册表） | **高（每文件 < 300 行，单一职责）** |
| 拓展性 | 极高（任意换 DB / 框架） | 高（热插拔） | 中（注册式扩展足够） |
| 技术栈匹配 | 偏离纯 sqlite3 | 偏 OpenClaw 内部范式 | **直接贴合现状：Flask + 原生 JS + 无构建** |
| 学习/迁移成本 | 极高（3-4 周） | 中（1 周） | **最低（半周验收点可推进）** |
| 与 OpenClaw 嵌入兼容性 | 中（需适配层） | **高**（范式同源） | 高（前后端双解耦后接入更顺） |
| 调研报告 Top5 推荐 | fast-api-reference-project | OpenClaw plugin-sdk | **本项目专属推荐** |

**调研共识**（4 份资料）：
- 范本 A (OpenClaw plugin-sdk) 与范本 F (cburmeister/flask-bones) 的 hybrid
- 后端 = Blueprint + Application Factory + Service/Repository 分层
- 前端 = Feature-based + micro-kernel 轻量版
- 不引入：六边形 + DI 库 / 插件架构 / React+Redux / 微前端 / SQLAlchemy / Pydantic

### 2.2 选定理由（C 方案）

1. **与现状差距最小**：Phase 1 落 1 个 Blueprint 后端就能跑，降低首阶段翻车面
2. **不引入额外依赖**：保持 "零构建" 硬约束（已与用户确认）
3. **解锁真正的并行临界点** = 文件锁解除：Phase 1 完成 → 两条独立工作线天然不打架
4. **5 份资料一致方向**：OpenClaw 哲学 + Flask Blueprint 范本 + Blank Board 微内核

---

## 3. 后端目标结构

```
server/
├── __init__.py            # 暴露 create_app(config=None) 工厂
├── app_factory.py         # create_app() 主体；注册 11 个 BP（按业务域）
├── config.py              # load_config()；覆盖路径 / 测试 override
├── extensions.py          # 单例：db connection、CORS、logger（不绑 app）
├── schema/
│   ├── __init__.py        # ensure_all(conn) 编排
│   ├── tasks.py           # tasks / tags / task_tags / task_dependencies
│   ├── gacha.py           # gacha_records / task_publishes
│   ├── state.py           # daily_user_state / user_schedule / daily_schedules / activities
│   ├── feedback.py        # task_completion_feedback / ai_analysis_imports
│   └── notes.py           # notes_categories / notes_files 索引元数据
├── models/                # @dataclass 域模型
├── repositories/          # 数据访问层（与 DB 唯一交界面）
│   ├── task_repo.py / gacha_repo.py / state_repo.py
│   └── feedback_repo.py / note_index_repo.py
├── services/              # 业务逻辑（纯函数 + 依赖注入 repo）
│   ├── gacha.py           # 抽卡权重算法（含接口隔离）
│   ├── timer.py / ai.py / knowledge.py / schedule.py
├── blueprints/            # 路由层（thin handler）
│   ├── tasks_bp.py / gacha_bp.py / discard_bp.py / tags_bp.py
│   ├── schedule_bp.py / state_bp.py / feedback_bp.py / timer_bp.py
│   ├── knowledge_bp.py / config_bp.py / prompts_bp.py / agent_bp.py
├── ai/
│   ├── llm_client.py      # 唯一与外部 LLM 通信；带超时/重试
│   └── prompts/
├── utils/
│   ├── task_blocked.py / wiki_link.py / energy_calc.py
└── legacy.py              # 旧 app = Flask(__name__) 兼容层
```

### 3.1 服务层边界规则

- `blueprints/` 只做：参数解析 → 调 service → 返回 JSON（不直连 sqlite）
- `services/` 只做：业务编排（不绑 Flask request/response）
- `repositories/` 只做：SQL 执行与行→字典映射（无业务）
- 单向依赖：`blueprints → services → repositories → sqlite`

---

## 4. 前端目标结构

```
static/
├── app.js                 # 唯一入口（~150 行：bootstrap + router + 注册表）
├── core/
│   ├── api.js             # fetch 包装（鉴权 / 重试 / 错误归一化）
│   ├── event-bus.js       # EventTarget 跨模块通信
│   ├── state.js           # Proxy + EventTarget 状态管理（单一来源）
│   ├── router.js          # 简单 hash router
│   ├── ui/
│   │   ├── modal.js / toast.js / theme.js / sandbox.js
│   └── constants.js
├── modules/                       # Feature-based，每模块自包含
│   ├── gacha/{index,pool,card,draw,animation,feedback}.js
│   ├── tasks/{index,list,editor,tag-batch,dep-graph,timer-panel,discard}.js
│   ├── timer-dock/index.js
│   ├── schedule/{index,render,slot-edit,activities}.js
│   ├── sleep-state/{index,sleep,assessment,weekly-energy}.js
│   ├── knowledge/{index,categories,notes,markdown}.js
│   └── config/{index,form,prompts,agent-panel}.js
├── shared/
│   ├── timer.js           # 单一 store，dock + tasks + 全局共一实例
│   ├── xss.js             # escHtml / setText
│   └── formatters.js
└── css/
    ├── theme.css / layout.css
    └── modules/
```

### 4.1 模块契约（强制）

```javascript
// modules/<name>/index.js
export const meta = { name: 'gacha', version: '1.0.0', deps: ['timer'] };
export async function mount(rootEl, ctx) { /* 初始化 */ }
export async function unmount(rootEl) { /* 清理 listener + interval */ }
```

### 4.2 跨模块通信铁律

- **禁止**直接 import `modules/<other>/<file>` 内部文件
- 跨模块通信**只通过** `core/event-bus.js` 事件 或 `core/state.js` 状态
- 文件边界 `scripts/check_module_imports.js` 强制校验

---

## 5. 双份 Schema 统一方案

- 桌面端整体归档到 `_archive/src_tasks_legacy/`（已与用户确认）
- 单源 schema 落 `server/app/schema/`，由 `ensure_all(conn)` 在 `create_app()` 启动时统一执行
- 删 `backend_api.py` 内嵌 12 个 `ensure_*`
- DB 迁移：对比 `data/task_publisher.db` 实表，仅增量补齐缺失表

---

## 6. OpenClaw 嵌入适配

- `core/ui/sandbox.js`：`window.parent !== window` 检测，独立 vs 嵌入两态
- 双向 `postMessage` 协议 v1：`{source:'sal', version:1, type, payload}`
- iframe sandbox：**禁用** `allow-same-origin + allow-scripts` 同源组合
- `targetOrigin` 显式传入（不用 `"*"`）
- iframe 内容 `ResizeObserver` + `postMessage type:'resize'`

---

## 7. 三性自检

| 性 | 检验点 | 现状 | 目标 |
|---|---|---|---|
| 精简 | 不引入 npm 包 / vite / tsc | 是 | 是 |
| 可维护 | 每文件 < 300 行，单一职责 | 否（3219 / 2674） | 是（<300）|
| 可拓展 | 注册式扩展：加 1 个 domain 加 1 个 BP + 1 个 module | 否（全局 fn 注册）| 是 |

---

## 8. 阶段路线

详见根目录 plan 文件 (`c:\Users\wn\.cursor\plans\全盘模块化重构（双文件锁_+_多路线并行）_8b4393f9.plan.md`)

| Phase | 范围 | 硬门槛 |
|---|---|---|
| P1 | 后端骨架 + 前端 kernel + 桌面归档 + 抽卡接口隔离 + schema 集中 | 36/36 E2E |
| P2 | 后端按域拆 8 个 Blueprint + 6 repo + 5 service | 36/36 E2E |
| P3 | 前端 5 模块拆分 + 双计时器合并 + 模块边界脚本 | 36/36 E2E |
| P4 | CSS 拆分 + OpenClaw sandbox + theme dark mode | 36/36 E2E |
| P5 | legacy 化 + scripts 归档 + schema 一致性脚本 + delivery 报告 | 36/36 E2E + 新补回归 |

---

## 9. 红线（不可妥协）

1. **src/notes/** 永不写入、永不 commit
2. **data/task_publisher.db** 不破坏；schema 迁移要测
3. **零构建**：不引入 npm 包 / vite / tsc / 任何打包
4. **36/36 E2E 全绿** = 每个 Phase 验收门槛
5. **桌面端 src/tasks/ 整体归档**（已与你 2026-08-16 确认）
6. **生成/验证分离**：开发会话不自跑全量 E2E 自报全绿

---

## 10. 风险与缓解

详见 plan §4。摘要：

| 风险 | 缓解 |
|---|---|
| 拆分回归 E2E 挂 | Phase 1 全量通后再开 Phase 2；失败 3 次即停分析 |
| 双计时器合并状态丢失 | 先 characterization test 冻行为再合并 |
| 并行路线文件交叉污染 | 文件白名单；串行合并低→高风险 |
| DB schema 迁移漏表 | `ensure_all` 一处编排 + `check_schema_coverage.py` |
| OpenClaw sandbox 误配 | 文档铁律 + 手动嵌入测试 |
| vault 误提交（红线） | 永不授权 src/notes/ 写；git pre-commit hook 已存在 |
