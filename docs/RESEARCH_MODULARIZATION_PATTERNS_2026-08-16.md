# 调研报告：业界高明模块化架构范式（外部视角 · 可直接借鉴）

> **生成时间**：2026-08-16  
> **调研方式**：联网（web search + GitHub raw README + WebFetch）+ 本地项目实测（`server/backend_api.py` 关键行号 + `static/app.js` 模块切分点）+ 已有调研稿交叉  
> **范围**：只调研 + 给方案 + 不写实现；所有推荐带出处；明确区分"事实 [F]"与"判断 [J]"  
> **项目锚点**：
> - 超级自动化学习工具（Flask + SQLite + 原生 HTML/JS 单页；`backend_api.py` 3439 行单文件 + `static/app.js` ~2900 行单文件）
> - soulvilization（Python + Pygame 模拟器；`core/` 逻辑层 + `world_generation` 16 模块）
> - 聊天记录导出（Python 脚本）
> - 调度平台 OpenClaw（已自带的插件/通道/技能体系）

---

## 目录

- [0. 阅读须知 / 缩写表](#0-阅读须知--缩写表)
- [1. 三大经典/现代模块化范式盘点（后端 / 前端 / Python 项目）](#1-三大经典现代模块化范式盘点后端--前端--python-项目)
  - [1.1 后端：6 个主流范式](#11-后端6-个主流范式)
  - [1.2 前端：4 个原生 ES modules 组织范式](#12-前端4-个原生-es-modules-组织范式)
  - [1.3 Python 项目：3 个包结构最佳实践](#13-python-项目3-个包结构最佳实践)
- [2. 「高明架构」候选 Top 5（含真实开源仓库）](#2-高明架构候选-top-5含真实开源仓库)
  - [2.1 🥇 maxkrivich/fast-api-reference-project — 层级约束范本](#21-maxkrivichfast-api-reference-project--层级约束范本)
  - [2.2 🥈 benavlabs/FastAPI-boilerplate — vertical-slice 模块化范本（2K stars）](#22-benavlabsfastapi-boilerplate--vertical-slice-模块化范本2k-stars)
  - [2.3 🥉 openclaw/openclaw — narrow subpath SDK + PluginEntry 注册式范本](#23-openclawopenclaw--narrow-subpath-sdk--pluginentry-注册式范本)
  - [2.4 ⭐ cburmeister/flask-bones — Flask Blueprint 大型化范本（990 stars）](#24-⭐-cburmeisterflask-bones--flask-blueprint-大型化范本990-stars)
  - [2.5 ⭐ productivty-dashboard-js / Blank Board — vanilla JS 微内核范本](#25-productivty-dashboard-js--blank-board--vanilla-js-微内核范本)
- [3. 大文件拆分方法论（核心难点）](#3-大文件拆分方法论核心难点)
  - [3.1 拆分前：行为固定测试（characterization test）](#31-拆分前行为固定测试characterization-test)
  - [3.2 拆分工具链：依赖图 / 圈复杂度 / 重复检测](#32-拆分工具链依赖图--圈复杂度--重复检测)
  - [3.3 拆分顺序：先底层后顶层，先无 IO 后有 IO](#33-拆分顺序先底层后顶层先无-io-后有-io)
  - [3.4 强制层级约束：CI 中跑 import-linter / dependency-cruiser](#34-强制层级约束ci-中跑-import-linter--dependency-cruiser)
  - [3.5 拆分过程中的重构保险](#35-拆分过程中的重构保险)
- [4. 针对我们三个项目的落地建议](#4-针对我们三个项目的落地建议)
  - [4.1 超级自动化学习工具后端（Flask 3439 行）](#41-超级自动化学习工具后端flask-3439-行)
  - [4.2 超级自动化学习工具前端（`app.js` ~2900 行）](#42-超级自动化学习工具前端appjs-2900-行)
  - [4.3 soulvilization 模拟器](#43-soulvilization-模拟器)
  - [4.4 聊天记录导出（脚本工具）](#44-聊天记录导出脚本工具)
  - [4.5 OpenClaw 调度平台（已有 plugin-sdk，直接复用即可）](#45-openclaw-调度平台已有-plugin-sdk直接复用即可)
- [5. Top 3 推荐 + 每项目第一步拆分动作](#5-top-3-推荐--每项目第一步拆分动作)
- [6. 风险与未知点](#6-风险与未知点)
- [附录 A · 全部来源清单（去重、按主题分组）](#附录-a--全部来源清单去重按主题分组)

---

## 0. 阅读须知 / 缩写表

|| 缩写 / 术语 | 全称 / 出处 |
||---|---|
|| **Blueprint** | Flask 的 Blueprint 子应用机制（`flask.palletsprojects.com/blueprints`） |
|| **APIRouter** | FastAPI 的路由分组机制（`fastapi.tiangolo.com/tutorial/bigger-applications`） |
|| **SRC Layout** | Python 包的 `src/` 嵌套布局（`packaging.python.org/discussions/src-layout-vs-flat-layout`） |
|| **DI** | Dependency Injection 依赖注入；手动 vs 库（`dependency-injector` / `injector` / `punq`） |
|| **FSM** | Finite State Machine 有限状态机；本项目双计时器即 FSM |
|| **HMR** | Hot Module Replacement 热替换（开发体验） |
|| **SCC** | Strongly Connected Component 强连通分量（madge/import-linter 检测循环依赖的算法） |
|| **ROR** | Repository 仓储层；service 调用 repo 实现数据访问 |
|| **VI** | View / Controller 视图层；thin handler 只做 HTTP 转换 |
|| **ESM** | ECMAScript Modules；浏览器原生 ES modules（`<script type="module">`） |
|| **ORM** | Object-Relational Mapping 对象-关系映射 |

**文中标记约定**：
- **[F]** = 事实陈述，引自源材料原文或近原文；附 URL/路径
- **[J]** = 我的判断 / 建议；非材料直接给出，由我对项目 + 多份资料综合得出

---

# 1. 三大经典/现代模块化范式盘点（后端 / 前端 / Python 项目）

## 1.1 后端：6 个主流范式

### 1.1.1 范式 A — Flask Blueprint + Application Factory（最小可用）`[F + J]`

**核心思想**（来源：[tomodahinata.com — Flask Large-App Structure](https://tomodahinata.com/en/blog/flask-application-factory-blueprints-large-app-structure-guide)）：

> "Stop generating `app` at the module top, and assemble it inside a function and return it. The caller gains complete control over 'when, with which settings, and which parts loaded' the app is made."

> "The factory is not 'a future extension' but 'a current requirement'."

**范式要点**：
1. **`create_app(config_name)` 工厂函数**——在 `app/__init__.py` 中创建 Flask 实例（不用全局 `app`）
2. **`extensions.py`**——把扩展（db / login / cache）作为 unbound 对象暴露，`create_app` 内调 `init_app(app)` 绑定
3. **Blueprint 按域分组**（不是按 HTTP 方法）——`auth_bp` / `tasks_bp` / `gacha_bp` 等
4. **`url_prefix`** 隔离命名空间；`register_blueprint()` 注册

**适用场景** `[J]`：
- 单仓库单进程
- 团队 < 5 人
- 业务领域清晰（已稳定下来）

**优点** `[F]`：
- 官方推荐范式，文档最齐全（[Flask Mega-Tutorial Part XV](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xv-a-better-application-structure)）
- 零学习成本、零样板
- 测试友好（每个 test 自己 `create_app`）

**代价**：
- 没有强制层级约束（Domain / Application / Infrastructure 容易混在一起）
- 大型项目容易出现"胖 blueprint"（业务逻辑塞到 view）

**业界知名案例**：
- [cburmeister/flask-bones](https://github.com/cburmeister/flask-bones)（990 stars，**本调研亲测可借鉴**）
- [dimmg/flusk](https://github.com/dimmg/flusk)（221 stars）—— 分 `backend / domain / views / models` 四层

---

### 1.1.2 范式 B — FastAPI Router + 分层（APIRoute → Service → Repository）`[F + J]`

**核心思想**（来源：[zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)）：

```
fastapi-project
├── alembic/
├── src/
│   ├── auth/
│   │   ├── router.py          # API endpoints
│   │   ├── schemas.py         # Pydantic
│   │   ├── models.py          # SQLAlchemy
│   │   ├── dependencies.py    # DI 结点
│   │   ├── config.py          # 局部配置
│   │   ├── constants.py       # 错误码
│   │   ├── exceptions.py      # 模块异常
│   │   ├── service.py         # 业务逻辑
│   │   └── utils.py           # 响应归一化
│   ├── tasks/                 # 同上结构
│   ├── config.py              # 全局配置
│   └── main.py
```

**范式要点**：
1. **每个域独立包**（auth/tasks/posts/...）——包内 9 个文件固定模板
2. **Service 只调 Repository，不调 ORM 模型**
3. **Router 仅做 request→response 转换**，业务全在 service
4. **`api/v1/` 统一聚合**所有域的 router

**适用场景** `[J]`：
- FastAPI 项目
- 需要严谨分层、单元测试覆盖率 > 80%

**优点** `[F]`：
- 模板化、可生成（[benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate) 提供 `bp` CLI 自动生成模块）
- 测试层次清晰（route / service / repo 可独立 mock）

**代价**：
- 文件数爆炸（小功能 9 个文件起步）
- "APIRouter vs Blueprint" 类比——FastAPI 范式不适合 Flask 直接搬

---

### 1.1.3 范式 C — 六边形架构（Ports & Adapters / Hexagonal）`[F + J]`

**核心思想**（来源：[maxkrivich/fast-api-reference-project README](https://github.com/maxkrivich/fast-api-reference-project)）：

```
infrastructure          ← composition root, wires everything together
    ↓
adapters
  inbound/http          ← FastAPI routes, request/response mapping
  outbound/             ← repository implementations (SQL, in-memory)
    ↓
application
  ports/                ← Python Protocols (TaskRepository, ObservabilityPort)
  use_cases/            ← business logic, depends only on domain + ports
    ↓
domain                  ← pure Python: Task entity, TaskNotFound exception
```

**范式要点**：
1. **三层同心圆**：Domain（最里）→ Application（中间）→ Infrastructure（最外）
2. **Ports = Python `Protocol`/`ABC`** 接口，定义在 application 或 domain 层
3. **Adapters** 实现接口（FastAPI routes / SQLAlchemy repo / IMAP client）
4. **依赖方向严格向内**（Domain 不知道 Flask / SQLAlchemy 存在）
5. **可插拔 Repository 后端**：`REPO_BACKEND=sql` 走 Postgres，`=memory` 走内存 dict

**适用场景** `[J]`：
- 需要切换存储后端（SQLite / Postgres / MongoDB）
- 业务规则复杂且需离线测试（不依赖 Flask / DB）
- 团队成熟、有架构师把控

**优点** `[F]`：
- **业务规则可 100% 单测**（不依赖任何 I/O）
- 数据库迁移不影响 domain 代码（只换 adapter）
- 模块边界在 CI 强制（详见 §3.4）

**代价**：
- 小项目过度设计（"[F] Domain folders are the wrong choice for a genuinely small service. Under about three features, a layer-first tree or even a single module is easier to read"——[fastapi-patterns.com](https://fastapi-patterns.com/core-architecture-routing-patterns/modular-router-organization/how-to-structure-large-fastapi-projects-for-scale/)）
- 学习曲线陡，新人上手慢
- Flask 无原生 DI，需引入 `dependency-injector` 库（[python-dependency-injector 教程](https://python-dependency-injector.ets-labs.org/tutorials/flask.html)）

**业界知名案例**：
- [maxkrivich/fast-api-reference-project](https://github.com/maxkrivich/fast-api-reference-project) — **本调研重点范本**，带 `import-linter` CI 约束
- [serfer2/flask-hexagonal-architecture-api](https://github.com/serfer2/flask-hexagonal-architecture-api) — Flask + Hexagonal
- [ShahriyarR/hexagonal-flask-blog-tutorial](https://github.com/ShahriyarR/hexagonal-flask-blog-tutorial) — Flask 官方 blog 教程的 Hexagonal 改写版
- [Khaled-Farhat/modular-monolith-practice](https://github.com/Khaled-Farhat/modular-monolith-practice) — 三模块各用一种架构（Layered / Hexagonal / Clean）

---

### 1.1.4 范式 D — 模块化单体（Modular Monolith / Vertical Slice）`[F + J]`

**核心思想**（来源：[benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate)）：

> **垂直切片（vertical-slice）**：每个模块自带 router / schemas / models / service / tests，可独立存在，跨模块通过 `app.<module>.shared` 公开 API 通信。

```
backend/src/
├── interfaces/      # FastAPI main, OpenAPI 生成
├── infrastructure/  # DB, cache, task queue, telemetry
└── modules/
    ├── users/       # router + service + schemas + tests
    ├── billing/
    └── tasks/
```

**范式要点**：
1. **模块 = 垂直功能切片**（不是水平层）
2. **跨模块访问受控**：只通过 `module/shared.py` 暴露的公开 API
3. **DI 在 container 中集中装配**

**适用场景** `[J]`：
- 业务域稳定但模块数量多（5+）
- 后续可能拆微服务（modular monolith 是微服务的"前身"）

**优点**：
- 团队边界对齐（一个团队 = 一个模块）
- 比六边形轻量，比 Blueprint 严谨

**代价**：
- 模块边界靠纪律维护（无 CI 强制）

**业界知名案例**：
- [benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate)（**2K+ stars**，最热）
- [YoraiLevi/modular-monolith-fastapi](https://github.com/YoraiLevi/modular-monolith-fastapi)（uv + ruff + pyright + pytest 全套工具链）

---

### 1.1.5 范式 E — 插件架构（Plugin Architecture / Micro-kernel）`[F + J]`

**核心思想**（来源：[Pluggy docs](https://pluggy.readthedocs.io/en/stable/) + [OpenClaw plugin architecture](https://docs.openclaw.ai/plugins/architecture-internals.md)）：

```
host (核心) ← micro-kernel（100 行）
├── plugin A (Slack)   ← 注册到 PluginManager
├── plugin B (Discord) ← 注册到 PluginManager
└── plugin C (WeChat)  ← 注册到 PluginManager
```

**范式要点**：
1. **核心 = 极简 micro-kernel**（注册表 + 事件总线 + 钩子）
2. **每个插件 = 独立包**，通过 setuptools entry points 或 `definePluginEntry()` 注册
3. **插件之间不直接调用**，走 host 暴露的事件/钩子
4. **典型实现**：
   - **Python**：[Pluggy](https://pluggy.readthedocs.io/en/stable/)（pytest 同款）、[Stevedore](https://docs.openstack.org/stevedore/1.20.1/)（OpenStack 同款）
   - **JS**：[Native Federation](https://native-federation.com/) + import map

**OpenClaw 自家的实现**（来源：[docs.openclaw.ai/plugins/sdk-overview](https://docs.openclaw.ai/plugins/sdk-overview)）：

> "Each subpath is a small, self-contained module. This keeps startup fast and prevents circular dependency issues."

```
src/plugin-sdk/
├── core.ts              # 通用 helper（umbrella）
├── channel-core.ts      # channel entry/build
├── channel-entry-contract.ts
├── plugin-entry.ts
├── channel-outbound.ts
├── channel-inbound.ts
└── ...                  # 13 个 narrow subpath
```

> **核心要点**：每个 subpath 是窄接口，**禁止从 root barrel 导入**——这是 OpenClaw 强制架构纪律的核心机制。

**适用场景** `[J]`：
- 需要第三方扩展（OpenClaw 自身 = 范例）
- 业务领域未稳定、需要插件化探索

**优点**：
- **极致解耦**：插件作者无需了解 host 实现
- 动态加载：可禁用 / 启用 / 热加载
- OpenClaw 自身就是这套架构——**我们已经在用，只是不知道在用**

**代价**：
- 接口设计需要"深思熟虑"（改接口 = 插件全坏）
- 调试链路长（跨插件调用栈）
- 文档要求高（插件作者必须先读 SDK 文档）

**业界知名案例**：
- [openclaw/openclaw](https://github.com/openclaw/openclaw) — **本调研关键范本**
- [pytest-dev/pytest](https://github.com/pytest-dev/pytest) — Pluggy 的"原作者"用家
- [OpenStack 项目群](https://docs.openstack.org/stevedore/) — Stevedore 的母体

---

### 1.1.6 范式 F — 控制器-服务-仓储（Controller-Service-Repository）`[F]`

**核心思想**（来源：[Cosmic Python 第 4 章](https://www.cosmicpython.com/book/chapter_04_service_layer.html)）：

```
Controller (Flask/FastAPI route)
    ↓
Service (use case orchestration, 业务规则)
    ↓
Repository (数据访问抽象)
    ↓
ORM / DB
```

**与六边形的区别**：
- 六边形 = Ports & Adapters，**业务规则完全不知道外面存在**
- CSR = **业务规则知道 Repository 抽象存在，但不知道具体 DB** `[F]`

**适用场景**：
- 业务不复杂、存储后端稳定、不打算换 DB

**业界知名案例**：
- 几乎所有 Flask 教程默认结构
- [arcTikant/fastapi-modular-monolith-starter-kit](https://github.com/arctikant/fastapi-modular-monolith-starter-kit) — CSR + Modular Monolith 混合

---

### 1.1.7 后端范式对比表 `[J]`

|| 维度 | Blueprint+Factory | Router 分层 | 六边形 | 模块化单体 | 插件架构 | CSR |
||------|---|---|---|---|---|---|
|| **学习曲线** | 低 | 低-中 | 高 | 中 | 高 | 低 |
|| **样板代码** | 少 | 中 | 多 | 中 | 多 | 中 |
|| **测试友好度** | 中 | 高 | 极高 | 高 | 中 | 高 |
|| **存储后端可换性** | ✘ | △ | ✓✓ | ✓ | ✓ | ✓ |
|| **CI 强制约束** | ✘ | ✘ | ✓（import-linter） | △ | ✓（subpath 约定） | ✘ |
|| **大项目可扩展** | △ | ✓ | ✓✓ | ✓✓ | ✓✓ | ✓ |
|| **小项目可起步** | ✓✓ | ✓✓ | ✘ | ✓ | △ | ✓✓ |
|| **本项目适配度** | ★★★★★ | ★★★（已用 Flask） | ★★★★ | ★★★★ | ★★（过度设计） | ★★★ |

**我的推荐** `[J]`：

> **首选** Blueprint + Factory（范式 A）打底——成本最低、与 Flask 现状最贴合。
> **次选** Blueprint + Service/Repository 分层（范式 A + F 的轻量变体）——契合现有 3439 行结构。
> **不引入六边形 + DI 库**——项目目前业务域稳定、不换 DB、不做微服务，过度设计。
> **不引入插件架构**——OpenClaw 自身的 plugin-sdk 已经覆盖"扩展"维度，我们做应用层即可。

---

## 1.2 前端：4 个原生 ES modules 组织范式

### 1.2.1 范式 P1 — Feature-based（业界 2026 默认）`[F + J]`

**核心思想**（来源：[jsgurujobs.com — Feature-based architecture 2026](https://www.jsgurujobs.com/blog/how-to-structure-a-javascript-project-in-2026-and-the-folder-architecture-that-scales-from-side-project-to-500-file-production-application)）：

```
src/
├── features/                 ← 业务域
│   ├── gacha/
│   │   ├── components/
│   │   ├── hooks/             ← 命名沿用 React 习惯，vanilla JS 可改为 services/
│   │   ├── api/
│   │   ├── types/
│   │   └── index.ts          ← barrel export
│   ├── tasks/
│   └── knowledge/
└── shared/                   ← 跨 feature 共用
    ├── components/
    ├── utils/
    └── types/
```

**范式要点** `[F]`：
1. **按业务域组织**，不是按技术层（components / hooks / utils）
2. **每个 feature 自包含**：`gacha` 文件夹里包含它需要的所有文件
3. **`shared/` 目录只放 ≥2 个 feature 用到的代码**——"[F] only move code when at least two features depend on it. Otherwise you create fake abstractions that slow down development"
4. **Barrel exports**（`index.js`）——每个 feature 只对外暴露受控 API
5. **边界用 ESLint 强制**：`import/no-restricted-paths`

**优点** `[F]`：
- "Cognitive load drops: Everything related to gacha lives in one place"
- "Changes are contained: Payment features rarely touch user code"
- "Testing becomes natural: Each domain has its own test suite"
- "Microservices evolution: Domains can be extracted as separate services later"

**业界知名案例** `[F]`：
- [huggingface/transformers.js](https://huggingface.co/docs/transformers.js) — feature-based 大型 JS 项目
- 大多数 React 框架（Next.js / Remix）的约定结构

---

### 1.2.2 范式 P2 — 微内核（Micro-kernel / Plugin Loader）`[F + J]`

**核心思想**（来源：[Blank Board docs](https://empty-ad9a3406.mintlify.app/concepts/architecture)）：

```
core/                         ← 100 行 micro-kernel
├── core.js                   # 启动 + plugin loader
├── api.js                    # 注入到每个 plugin 的 API 工厂
└── eventBus.js               # 跨模块通信

plugins/                      ← 每个 widget 一个 plugin
├── gacha/
│   ├── meta.js               # { name, version, setup }
│   └── plugin.js
├── tasks/
└── knowledge/
```

**范式要点**（来源：[Building a Plugin-Based JavaScript Dashboard](https://javascript.plainenglish.io/building-a-plugin-based-javascript-dashboard-that-can-evolve-without-rewrites-ce4ad97b0a03)）：
1. **核心 = 微内核**（启动 + 注册表 + 事件总线）
2. **每个插件导出 `meta` + `setup`**——standalone ES modules，无构建步骤、无框架
3. **动态 `import()`**——按需加载
4. **共享 context**——注入 API（`container` / `mount` / `storage` / `hooks`）
5. **社区插件独立仓库**——通过 URL + CORS 加载

**优点** `[F]`：
- 极端解耦——插件作者不需要 host 实现细节
- 热重载 / 动态安装 / 卸载
- LocalStorage 持久化插件配置

**代价** `[J]`：
- **每个插件要写 boot / unmount 协议**（~50 行模板代码）
- 不适合"功能紧密耦合"的产品（如本项目抽卡 + 任务 + 计时器三件套紧耦合）
- 调试链路长

**业界知名案例** `[F]`：
- [Blank Board](https://github.com/your-org/blank-board) — 微内核范本（社区插件独立仓库）
- [femcodersclub/productivity-dashboard-js](https://github.com/femcodersclub/productivity-dashboard-js) — Pomodoro + Habits + Notes 三个 widget

---

### 1.2.3 范式 P3 — Layer-based（按技术层）`[F + J]`

**核心思想**：
```
src/
├── components/   ← 所有组件
├── hooks/        ← 所有 hook
├── services/     ← 所有服务
├── stores/       ← 所有状态
├── types/
└── utils/
```

**评价**（来源：[LinkedIn — Layer vs Module Pattern](https://www.linkedin.com/pulse/layer-pattern-vs-module-folder-structure-context-ai-machiraju-rdmec)）：

> "The layer pattern organises code by what it does technically — its role in the stack... The problem shows up as the app grows. Adding a new feature means touching controllers/, services/, models/, and utils/ all at once. Your changes are scattered across the entire codebase for a single logical addition."

**结论** `[J]`：**不推荐**——本项目正是要从 layer-based 转出。

---

### 1.2.4 范式 P4 — 微前端（Micro-frontends / Native Federation）`[F + J]`

**核心思想**（来源：[Native Federation 官方](https://native-federation.com/)）：

```
host/                          ← shell app
└── imports `remoteEntry.json` from:
    ├── mfe-gacha/             ← 独立 build 的微前端
    ├── mfe-tasks/
    └── mfe-knowledge/
```

**范式要点** `[F]`：
1. **每个 MFE 独立 build / 独立部署**
2. **共享依赖通过 import map**——避免重复加载
3. **host 通过 `initFederation({ 'mfe-gacha': 'http://...' })`** 加载

**优点** `[F]`：
- 不同团队独立部署
- 独立技术栈（一个 MFE 用 Preact，另一个用 Vue）

**代价** `[F]`：
- **不能 on-the-fly 更新**（import map 初始化即固化）
- 性能开销（每个 MFE 独立运行时）
- 调试链路最长

**业界知名案例** `[F]`：
- [native-federation/native-federation-core](https://github.com/native-federation/native-federation-core)
- [vanilla-native-federation](https://www.npmjs.com/package/vanilla-native-federation)

**结论** `[J]`：**不适合本项目**——单团队、单技术栈、单部署。

---

### 1.2.5 前端范式对比表 `[J]`

|| 维度 | Feature-based | 微内核 | Layer-based | 微前端 |
||------|---|---|---|---|
|| **学习曲线** | 低 | 中 | 极低 | 高 |
|| **样板代码** | 少 | 多 | 极少 | 多 |
|| **可扩展性** | ✓✓ | ✓✓✓ | △ | ✓✓✓ |
|| **调试友好度** | 高 | 中 | 高 | 低 |
|| **零构建支持** | ✓ | ✓✓ | ✓ | ✘ |
|| **本项目适配度** | ★★★★★ | ★★ | ✘ | ✘ |

**我的推荐** `[J]`：

> **首选** Feature-based（范式 P1）——与后端 modular monolith 对称。
> **不引入微内核/微前端**——单团队单部署，过度设计。
> Layer-based 是我们想逃离的旧结构。

---

## 1.3 Python 项目：3 个包结构最佳实践

### 1.3.1 SRC Layout vs Flat Layout `[F + J]`

**核心思想**（来源：[packaging.python.org](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)）：

```
Flat（不推荐）：                    SRC（推荐）：
myproject/                          myproject/
├── myproject/                      ├── src/
│   ├── __init__.py                 │   └── myproject/
│   └── module.py                   │       ├── __init__.py
├── tests/                          │       └── module.py
└── pyproject.toml                  ├── tests/
                                    └── pyproject.toml
```

**关键差异** `[F]`：
> "The src layout helps enforce that an editable installation is only able to import files that were meant to be importable. The flat layout would add the other project files (eg: `README.md`, `tox.ini`) and packaging/tooling configuration files (eg: `setup.py`, `noxfile.py`) on the import path."

**结论**（来源：[realpython.com](https://realpython.com/ref/best-practices/project-layout/)）：
> "**`src/` layout**: The source code is organized within the `src/` directory. This layout is well suited for library code that will be packaged and distributed to others, and for larger projects."
> "Flat layout: The source code package or packages live at the root level alongside other files like `README.md` or `pyproject.toml`. This layout can work well for quick scripts, but it's prone to accidentally importing the wrong files and can become messy as a project grows."

**结论** `[J]`：
- **可分发的库 / CLI 工具** → `src/` layout
- **直接 `python xxx.py` 跑的应用** → flat 也可以接受
- **本项目 `server/backend_api.py` 是应用入口**（直接 `python server/backend_api.py` 启动）→ 当前 flat 合理；**但 Blueprint 拆分后 `app/` 包内部依然可以用 `src/app/` 嵌套**

---

### 1.3.2 依赖注入（DI）：手动 vs 库 `[F + J]`

**核心思想**（来源：[Snyk — Python DI](https://snyk.io/blog/dependency-injection-python/) + [hackanons — Python DI 2026](https://hackanons.com/python-di-libraries-vs-manual-wiring-2026/)）：

| 方式 | 性能偏差 | GitHub Stars | 适合 |
|------|---------|--------------|------|
| **手动装配**（构造函数传参） | 0% | — | 小项目、原型 |
| **Wireup** | ~1% | 1200 | 中-复杂系统 |
| **Dependency Injector** | ~5% | 3000 | 企业级 |
| **injector** | ~15% | 950 | 大团队 |
| **FastAPI Depends()** | 原生 | — | FastAPI 项目 |
| **Flask-Injector** | 中 | — | Flask + DI |

**结论** `[F]`：
> "FastAPI has built-in support via `Depends()`. Flask needs a library like `dependency-injector`."

**结论** `[J]`：
- **本项目 Flask → 手动 DI**（传参 / `current_app` / `g`）——零成本
- **不引入 dependency-injector**——已有 Blueprint 模式足够
- FastAPI 原生 Depends **不要抄到 Flask**——Flask 没原生 DI，硬抄会引入复杂度

---

### 1.3.3 插件加载：Pluggy vs Stevedore `[F + J]`

**Pluggy 范式**（来源：[Pluggy docs](https://pluggy.readthedocs.io/en/stable/) + [Eli Bendersky — Pluggy case study](https://eli.thegreenplace.net/2026/plugins-case-study-pluggy)）：

```python
# host
pm = pluggy.PluginManager("eggsample")
pm.add_hookspecs(hookspecs)
pm.load_setuptools_entrypoints("eggsample")

# plugin
@hookimpl
def cook_meal(ingredients): ...
```

**Stevedore 范式**（来源：[OpenStack stevedore docs](https://docs.openstack.org/stevedore/1.20.1/1.20.1/)）：

```python
mgr = driver.DriverManager(
    namespace='stevedore.example.formatter',
    name='simple',
    invoke_on_load=True,
)
```

**对比** `[F]`：
- **Pluggy** = hook-based（pytest 同款）——多个插件实现同一接口
- **Stevedore** = manager-based（OpenStack 同款）——驱动 / 扩展动态加载

**结论** `[J]`：
- **本项目不引入**——业务域稳定，5+ 域用 Blueprint 已经够
- OpenClaw 自身用这套（plugin-sdk 是它的 JavaScript 版），我们只需要 "use" 它而不是 "rebuild" 它

---

# 2. 「高明架构」候选 Top 5（含真实开源仓库）

> 评估维度：
> 1. **高明程度**——是不是业界认可的范本
> 2. **可借鉴度**——我们能直接抄哪些具体模式
> 3. **零构建兼容性**——不引入 npm 构建链
> 4. **与现有项目技术栈匹配度**

## 2.1 🥇 maxkrivich/fast-api-reference-project — 层级约束范本

**仓库**：[github.com/maxkrivich/fast-api-reference-project](https://github.com/maxkrivich/fast-api-reference-project)

**目录结构** `[F]`：
```
infrastructure          ← composition root, wires everything together
    ↓
adapters
  inbound/http          ← FastAPI routes, request/response mapping
  outbound/             ← repository implementations (SQL, in-memory)
    ↓
application
  ports/                ← Python Protocols (TaskRepository, ObservabilityPort)
  use_cases/            ← business logic, depends only on domain + ports
    ↓
domain                  ← pure Python: Task entity, TaskNotFound exception
```

**为什么高明** `[F + J]`：

1. **CI 强制层级约束**——"`pyproject.toml` 配置 `import-linter`，每次 `git push` 跑架构合规检查。跨层 import 立即 fail"
2. **Repository 后端可热切换**——`REPO_BACKEND=sql|memory` 环境变量切换，只换 wiring，domain/use case/route 完全不动
3. **observability 三件套（logs/traces/metrics）开箱即用**——OpenTelemetry + Prometheus + structlog
4. **"Adding a feature" 流程标准化**——"Work inside-out: Domain → Port → Use case → Adapter → Wire"

**我们能抄的具体模式** `[J]`：

| 模式 | 怎么抄 | 适配度 |
|---|---|---|
| **三层同心圆** | 后端用 Blueprint + Service + Repository 分层（不必严格 Ports & Adapters） | ★★★★ |
| **CI 强制 import-linter** | Python 用 `import-linter` 或 `flake8-import-restrictions` | ★★★★ |
| **Repository 后端可换** | 把 SQL 操作包成 `task_repo.py` / `gacha_repo.py`，内存版作为测试 fallback | ★★★ |
| **OpenTelemetry 三件套** | 学习成本高，**本项目不引入** | ★ |

---

## 2.2 🥈 benavlabs/FastAPI-boilerplate — vertical-slice 模块化范本（2K stars）

**仓库**：[github.com/benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate)（**2,051 stars**）

**目录结构** `[F]`：
```
fastapi-boilerplate/
├── pyproject.toml          # workspace root (uv workspace metadata)
├── backend/                # deployable app
│   ├── src/
│   │   ├── interfaces/     # FastAPI app factory
│   │   ├── infrastructure/ # DB / cache / task queue
│   │   └── modules/        # 垂直切片
│   └── Dockerfile
└── cli/                    # `bp` developer/operator tool
    └── src/cli/
```

**为什么高明** `[F + J]`：

1. **CLI 工具自动生成模块**——`uv run bp deploy generate prod --workers 8`，避免样板代码
2. **`bp env validate`**——`.env` 安全审计（生产 validator 对照开发 `.env`）
3. **Plugin-ready CLI**——第三方 plugin 可以挂载 `bp xxx` 子命令
4. **uv workspace 单 venv**——backend + cli 共享依赖

**我们能抄的具体模式** `[J]`：

| 模式 | 怎么抄 | 适配度 |
|---|---|---|
| **uv workspace** | 我们的项目可拆 `backend/` + `cli/` + `worker/` 三个子包 | ★★★（当前单包够用） |
| **`bp` CLI 工具** | 写一个 `scripts/sal.py` 用 Click/Typer 暴露 `bp` 子命令（如 `bp new-module gacha`） | ★★★ |
| **Plugin-aware CLI** | OpenClaw 已经有同款机制 | ★★★ |
| **垂直切片模板** | 后端用 `app/<domain>/` 套用 | ★★★★ |

---

## 2.3 🥉 openclaw/openclaw — narrow subpath SDK + PluginEntry 注册式范本

**仓库**：[github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)

**目录结构（核心）** `[F]`（来源：[docs.openclaw.ai/plugins/sdk-overview](https://docs.openclaw.ai/plugins/sdk-overview) + [architecture-internals](https://docs.openclaw.ai/plugins/architecture-internals.md)）：

```
src/plugin-sdk/                      ← 13 个 narrow subpath
├── plugin-entry.ts                  # 注册 primitives
├── channel-core.ts                  # channel entry/build
├── channel-entry-contract.ts        # bundled channel setup
├── channel-outbound.ts              # 发消息 adapter
├── channel-inbound.ts               # 收消息 adapter
├── channel-pairing.ts
├── channel-config-schema.ts
├── secret-input.ts
├── webhook-ingress.ts
├── command-auth.ts
├── setup-runtime.ts
├── setup-tools.ts
└── core.ts                          # umbrella（**禁止从 root barrel 导入**）

extensions/                          ← pnpm workspace 内的插件包
├── discord/
├── slack/
├── telegram/
└── ...

# 边界检测脚本（CI 必跑）
scripts/check-src-extension-import-boundary.mts
scripts/check-sdk-package-extension-import-boundary.mts
scripts/check-test-helper-extension-import-boundary.mts
```

**Plugin 入口模板**（来源：[building-plugins](https://docs.openclaw.ai/plugins/building-plugins)）：

```typescript
import { defineChannelPluginEntry } from "openclaw/plugin-sdk/channel-core";

export default defineChannelPluginEntry({
  id: "my-channel",
  name: "My Channel",
  configSchema: Type.Object({ input: Type.String() }),
  register(api) {
    api.registerChannel({ plugin: myChannelPlugin });
  },
});
```

**为什么高明** `[F + J]`：

1. **Narrow subpath 设计**——"Each subpath is a small, self-contained module. This keeps startup fast and prevents circular dependency issues."——这是行业里**最值得抄**的纪律
2. **CI 强制 import 边界**——三个 `check-*import-boundary.mts` 脚本，任何跨包从 `src/*` 直接 import 都 fail
3. **Plugin 入口协议标准化**——`definePluginEntry / defineChannelPluginEntry` 一个函数管所有注册
4. **Setup / Runtime 分离**——`setupEntry` 是轻量引导入口；完整 `entry` 才加载重 SDK
5. **`api.ts / runtime-api.ts` 本地 barrel**——插件内部 API 通过自己的 barrel 暴露，不外泄内部实现

**我们能抄的具体模式** `[J]`：

| 模式 | 怎么抄 | 适配度 |
|---|---|---|
| **Narrow subpath 纪律** | 前端 ES modules 用类似命名：`core/event-bus.js` / `core/state.js` / `core/api.js` / `modules/gacha/index.js` | ★★★★★ |
| **PluginEntry 注册式** | 后端 Blueprint 也可参考：用 `register_blueprint(app)` 集中在 `app/__init__.py` | ★★★★ |
| **CI import 边界脚本** | 我们用 Python `import-linter` 或 Node `dependency-cruiser` 强制（详见 §3.4） | ★★★★ |
| **Setup / Runtime 分离** | 前端：每个模块导出 `mount(rootEl)` + `unmount(rootEl)`；**未挂载的模块不加载** | ★★★★★ |
| **本地 barrel** | `modules/gacha/index.js` 只导出公开 API（gachaState, draw, startTimer 等）；内部 helpers 不暴露 | ★★★★★ |

**核心洞察** `[J]`：

> **OpenClaw 自身就是"我们要找的高明架构"**。我们已经在用它（HTTP API / WebSocket），只是没有把它的 plugin-sdk 设计哲学（narrow subpath + 入口协议 + 边界检测）抄到自己的代码里。

---

## 2.4 ⭐ cburmeister/flask-bones — Flask Blueprint 大型化范本（990 stars）

**仓库**：[github.com/cburmeister/flask-bones](https://github.com/cburmeister/flask-bones)（990 stars，**最古老的 Flask Blueprint 范本**）

**目录结构** `[F]`：
```
project/
├── app/
│   ├── __init__.py            # create_app() factory
│   ├── extensions.py          # unbound extensions
│   ├── blueprints/            # feature modules
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   ├── forms.py
│   │   │   └── models.py
│   │   ├── items/
│   ├── models/                # shared models
│   ├── templates/
│   ├── static/
│   └── utils/
├── tests/
├── config.py
└── wsgi.py
```

**为什么高明** `[F + J]`：
1. **2013 年至今仍可作为 Flask 大型化的标准答案**——证明该范式的寿命
2. **Blueprint 包自包含**（routes / forms / models / templates / tests）
3. **`app/extensions.py` 用 `init_app` 模式绑定**——这就是本项目该抄的

**我们能抄的具体模式** `[J]`：

| 模式 | 怎么抄 | 适配度 |
|---|---|---|
| **`app/__init__.py` 工厂** | 立刻做——`backend/app/__init__.py` + `create_app(config)` | ★★★★★ |
| **`app/extensions.py`** | 把 SQLite 连接 / CORS / 配置对象集中（unbound） | ★★★★★ |
| **`app/blueprints/<domain>/`** | 按 6 个域拆：`tasks` / `gacha` / `schedule` / `state` / `knowledge` / `prompts` | ★★★★★ |
| **`config.py`** | 把 `config.json` 加载提到独立模块 | ★★★★ |

---

## 2.5 ⭐ productivity-dashboard-js / Blank Board — vanilla JS 微内核范本

**仓库**：
- [femcodersclub/productivity-dashboard-js](https://github.com/femcodersclub/productivity-dashboard-js)（Pomodoro + Habits + Notes 三个 widget）
- [Blank Board](https://empty-ad9a3406.mintlify.app/concepts/architecture)（100 行 micro-kernel + 社区插件独立仓库）

**目录结构**（productivity-dashboard-js）`[F]`：
```
productivity-dashboard-js/
├── src/
│   ├── core/
│   │   └── dashboard.js              # 核心 registry
│   ├── plugins/
│   │   └── plugin-manager.js         # 插件管理器
│   └── widgets/
│       ├── habits.js
│       ├── notes.js
│       └── pomodoro.js
├── tests/
└── index.html
```

**Blank Board 的 micro-kernel 100 行实现**（来源：[Blank Board docs](https://empty-ad9a3406.mintlify.app/concepts/architecture)）`[F]`：

> "The core kernel is ~100 lines. Everything else is modular and optional. Plugins are standalone ES modules. No build step, no frameworks, no dependencies. Just a `.js` file with `meta` and `setup`."

**每个 widget 模板** `[F]`：
```js
// 每个 widget 导出 meta + setup
export default {
  meta: { name: 'pomodoro', version: '1.0.0' },
  setup(api) {
    api.registerWidget({ /* ... */ });
  },
  teardown() { /* cleanup */ }
};
```

**为什么高明** `[F + J]`：
1. **100 行 micro-kernel + 独立 widget**——极致简洁
2. **零依赖**——vanilla JS ES modules + dynamic import
3. **LocalStorage 持久化插件配置**——刷新页面后插件状态保留
4. **可借鉴到我们的双计时器**——两个计时器本质就是两个 widget

**我们能抄的具体模式** `[J]`：

| 模式 | 怎么抄 | 适配度 |
|---|---|---|
| **100 行 micro-kernel** | 前端 `app.js` 拆后，`core/bootstrap.js` 仅 100 行：路由 + 注册表 + 全局错误 | ★★★★★ |
| **`meta + setup` 协议** | 每个模块导出 `{ meta, mount, unmount }` | ★★★★★ |
| **LocalStorage 持久化** | 主题 / 用户偏好存 localStorage（已有 §2.3 dark mode） | ★★★★★ |
| **动态 import** | 各模块懒加载：`await import('./modules/gacha/index.js')` | ★★★★ |

---

# 3. 大文件拆分方法论（核心难点）

## 3.1 拆分前：行为固定测试（characterization test）`[F + J]`

**核心思想**（来源：[Michael Feathers — Characterization Testing](https://michaelfeathers.silvrback.com/characterization-testing) + [avestahq — Characterisation Tests](https://avestahq.com/blog/characterisation-tests-safety-net-legacy-code)）：

> "When we write characterization tests we build up our knowledge of what the code actually does... This is particularly useful when we want to refactor or rewrite. We can run our tests and find out immediately whether we've changed behavior."

**操作流程** `[F]`：
1. **找 seam（接缝点）**——找一个能外部调用的公共入口
2. **破依赖**——最小化修改让代码可测（`seam = breaking dependencies`）
3. **捕获当前输出**——调用 + 记录返回值/副作用/DB 写入
4. **写测试断言捕获的输出**——即使包含 bug 也照搬
5. **重构**——任何重构都跑测试确认未改变行为
6. **重构完后再写"意图测试"**——替换表征测试

**对本项目的应用** `[J]`：

| 目标 | 当前测试缺口 | 需要补的 characterization test |
|---|---|---|
| **`backend_api.py` 拆分** | 已有 26 E2E 用例，但未覆盖所有边界 | 加一组"API 行为快照"测试——每个 endpoint 输入固定值、断言返回 JSON 结构 |
| **`app.js` 拆分** | 26 E2E 覆盖 5 个核心页面 | 加一组"模块导出签名快照"——确保拆分前后每个函数签名不变 |
| **抽卡算法** | E2E 不覆盖算法内部 | 抽卡函数入参+出参快照（golden master） |

**工具建议** `[F]`：
- **Python**：`pytest` + `pytest-approvaltest`（或 `pytest-snapshot`）
- **JS**：`jest --ci` + snapshot 测试

---

## 3.2 拆分工具链：依赖图 / 圈复杂度 / 重复检测

### 3.2.1 依赖图工具 `[F + J]`

| 工具 | 语言 | 关键能力 | 推荐命令 |
|---|---|---|---|
| **[madge](https://github.com/pahen/node-madge/)** | JS/TS | 依赖图 + 循环检测 | `npx madge --circular --extensions js static/` |
| **[dependency-cruiser](https://github.com/sverweij/dependency-cruiser/)** | JS/TS | **架构规则强制**（自定义 forbidden rules） | `npx depcruise src --validate .dependency-cruiser.js` |
| **[pydeps](https://github.com/thebjorn/pydeps)** | Python | 依赖图可视化 | `pydeps server/backend_api.py --show-dot` |
| **[import-linter](https://import-linter.readthedocs.io/)** | Python | **层级强制**（[FastAPI Hexagonal 范本用此](https://github.com/maxkrivich/fast-api-reference-project)） | `lint-imports` |
| **[refactory](https://github.com/codedrop-codes/refactory)** | JS/Python | AI 辅助拆分（LLM 决定边界 + 机械提取） | `refactory split app.js` |
| **[jscpd](https://github.com/kucherenko/jscpd)** | 多语言 | 重复代码检测 | `npx jscpd static/` |

**关键命令**（本项目立即可跑）`[J]`：
```bash
# 1. 依赖图（拆分前的全局视图）
npx madge --image dependency-graph.svg static/app.js

# 2. 循环依赖检测（拆分中持续监控）
npx madge --circular --extensions js static/

# 3. 重复代码检测（找复制粘贴的"伪模块化"陷阱）
npx jscpd static/

# 4. Python 层级约束（拆分后必跑）
pip install import-linter
lint-imports
```

---

### 3.2.2 拆分顺序判定 `[J]`

**黄金法则**（综合 Feathers 与多份实操经验）：

```
Phase 0（行为固定）—— 不改一行代码
  ↓ 跑通基线 + 写 characterization tests
Phase 1（识别 seams）—— 用工具看图
  ↓ madge / jscpd / grep 找出无依赖或低依赖区
Phase 2（抽 utility）—— 最底层、最稳、最通用
  ↓ 抽 const、常量、纯函数、API client、event bus
Phase 3（抽 state）—— 全局状态独立
  ↓ 抽 state.js（Proxy + EventTarget）、api.js（fetch 包装）
Phase 4（抽核心模块）—— 按业务域抽
  ↓ 模块 1 → 跑 E2E → 模块 2 → 跑 E2E → ...
Phase 5（顶层路由）—— 主入口只剩路由 + 启动
  ↓ app.js 缩到 ~200 行
```

---

## 3.3 拆分顺序：先底层后顶层，先无 IO 后有 IO

**核心思想**（来源：[avestahq — Characterisation Tests](https://avestahq.com/blog/characterisation-tests-safety-net-legacy-code) + [Dre Dyson — 7 Advanced Techniques](https://dredyson.com/7-advanced-techniques-to-split-massive-html-js-files-like-a-pro-when-ai-fails/)）：

> "Break down this codebase into logical modules. Identify: 1. Standalone components 2. Key dependencies 3. Natural split points."

**「完美模块」三指标**（来源：[dredyson.com](https://dredyson.com/7-advanced-techniques-to-split-massive-html-js-files-like-a-pro-when-ai-fails/)）`[F]`：
- **Cohesion（内聚度）> 80%**——模块内部文件相互引用多
- **External dependencies < 5**——外部依赖少
- **Size ~300 行 sweet spot**——300 行是大多数团队的最佳点

**对本项目 `static/app.js` 的具体拆分顺序** `[J]`：

```
第一步：抽 constants + warm messages + API client（无依赖）
  → static/core/constants.js  (~50 行)
  → static/core/api.js       (~150 行)
  → static/core/toast.js     (~30 行)

第二步：抽 state（核心状态）
  → static/core/state.js     (~200 行, Proxy + EventTarget)
  → static/core/event-bus.js (~80 行)

第三步：抽 UI helpers（modal / toast）
  → static/core/ui.js        (~80 行)

第四步：抽 router（页面切换）
  → static/core/router.js    (~120 行)

第五步：抽 feature modules（按业务域）
  → static/modules/gacha/index.js     (mount/unmount, ~600 行)
  → static/modules/tasks/index.js     (~700 行)
  → static/modules/schedule/index.js  (~150 行)
  → static/modules/knowledge/index.js (~150 行)
  → static/modules/state/index.js     (~200 行)
  → static/modules/config/index.js    (~300 行)

第六步：抽 timer state machines（独立、双计时器）
  → static/modules/gacha/timer.js     (~200 行)
  → static/modules/tasks/timer.js     (~200 行)

第七步：app.js 缩到 ~200 行
  → static/app.js                    (路由 + 启动 + 注册表)
```

**对应 `server/backend_api.py` 的拆分顺序** `[J]`：

```
第一步：建 app 包 + factory
  → server/app/__init__.py  (create_app)
  → server/app/extensions.py  (unbound db, cors, config)
  → server/app/config.py  (load_config)

第二步：按 6 个 API 域拆 Blueprint
  → server/app/blueprints/tasks.py      (CRUD + complete/skip/refuse)
  → server/app/blueprints/gacha.py      (draw/care-draw/replace)
  → server/app/blueprints/discard.py    (discard pile)
  → server/app/blueprints/tags.py       (tags CRUD)
  → server/app/blueprints/schedule.py   (weekly/daily/activities)
  → server/app/blueprints/state.py      (daily-tone/energy/sleep/assessment)
  → server/app/blueprints/timer.py      (timer)
  → server/app/blueprints/feedback.py   (task-feedback)
  → server/app/blueprints/knowledge.py  (categories/points/graph/notes)
  → server/app/blueprints/config.py     (config)
  → server/app/blueprints/prompts.py    (prompts)
  → server/app/blueprints/agent.py      (agent files/process)

第三步：抽 service 层
  → server/app/services/task_service.py
  → server/app/services/gacha_service.py
  → server/app/services/schedule_service.py
  → ...

第四步：抽 repository 层（可选）
  → server/app/repositories/task_repo.py
  → server/app/repositories/gacha_repo.py
  → ...

第五步：backend_api.py 缩到 ~50 行（仅入口 + 调 create_app）
```

---

## 3.4 强制层级约束：CI 中跑 import-linter / dependency-cruiser

### 3.4.1 Python：`import-linter` `[F + J]`

**配置**（来源：[maxkrivich/fast-api-reference-project](https://github.com/maxkrivich/fast-api-reference-project)）：

```toml
# pyproject.toml
[tool.importlinter]
root_package = "app"

[[tool.importlinter.contracts]]
name = "domain must not import application or infrastructure"
type = "forbidden"
source_modules = ["app.domain"]
forbidden_modules = ["app.application", "app.infrastructure"]

[[tool.importlinter.contracts]]
name = "application must not import infrastructure"
type = "forbidden"
source_modules = ["app.application"]
forbidden_modules = ["app.infrastructure"]

[[tool.importlinter.contracts]]
name = "blueprints only import services"
type = "layers"
layers = [
    "app.blueprints",
    "app.services",
    "app.repositories",
    "app.domain"
]
```

### 3.4.2 JavaScript：`dependency-cruiser` `[F + J]`

**配置**（来源：[DEV.to — dependency-cruiser](https://dev.to/jacobandrewsky/avoid-cross-module-dependencies-with-dependency-cruiser-3b0b)）：

```js
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'error',
      from: {},
      to: { circular: true }
    },
    {
      name: 'gacha-cannot-import-tasks-internals',
      from: { path: '^src/modules/gacha/' },
      to: { path: '^src/modules/tasks/(?!index\\.js$)' }  // 只允许从 barrel 导入
    },
    {
      name: 'modules-cannot-import-each-other-private',
      from: { path: '^src/modules/([^/]+)/' },
      to: {
        path: '^src/modules/([^/]+)/',
        pathNot: '^src/modules/$1/index\\.js$'
      }
    }
  ]
};
```

**CI 接入**（任一平台均可）`[J]`：
```bash
# GitHub Actions / GitLab CI / pre-commit
- name: Architecture check
  run: |
    npx depcruise src --validate .dependency-cruiser.cjs
    pip install import-linter && lint-imports
```

---

## 3.5 拆分过程中的重构保险

**操作纪律** `[F + J]`（继承 AGENTS.md 规则 5/6）：

| 阶段 | 行为 | 反例 |
|---|---|---|
| **拆分前** | 跑全量基线 + 写 characterization test | 不写测试直接拆 |
| **拆分中** | 每次拆完一个小块 → 跑 E2E → commit → 再拆下一块 | 一次拆完再测 |
| **拆分后** | 删除原文件 → 跑全量 E2E → commit | 留着旧文件 |
| **拆分后** | 加 `import-linter` / `dependency-cruiser` CI | 拆分后无纪律，半年后再次退化 |

**commit 粒度建议** `[J]`：
```
拆分应该是"连续的小 PR"，每个 PR 一个模块：
- commit 1: 抽 constants + API client（无 E2E 影响）
- commit 2: 抽 state + event bus（部分 state 行为差异 → E2E RED → 修 → GREEN）
- commit 3: 抽 router（页面切换 → E2E RED → 修 → GREEN）
- commit 4: 抽 gacha module
- commit 5: 抽 tasks module
- ...
```

---

# 4. 针对我们三个项目的落地建议

## 4.1 超级自动化学习工具后端（Flask 3439 行）

### 4.1.1 现状盘点 `[F]`（来源：`server/backend_api.py` + `RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md` §1.1）

**路由分布**（按 `backend_api.py` grep 结果）：
- 健康检查：`/api/health`（行 1554）
- 任务 CRUD：`/api/tasks*`（行 1292-1467，约 12 个端点）
- 抽卡系统：`/api/gacha*`（行 1469-1532，约 5 个端点）
- 弃牌堆：`/api/discard-pile*`（行 1534-1552）
- 知识库：`/api/knowledge*`（行 1558-1910，最大域）
- 日程系统：`/api/schedule*`（行 2046-2217）
- 状态追踪：`/api/state*`（行 2217-2420）
- 计时器：`/api/timer*`（行 3001-3192）
- 反馈：`/api/task-feedback`
- 配置：`/api/config*`
- 提示词：`/api/prompts*`（行 2660-3001）
- Agent 只读：`/api/agent/*`（行 2660-3001）

**主要数据库函数**（grep 行号）：
- `get_db_connection`（行 288）
- `get_all_tasks` / `get_task_by_id` / `add_task` / `update_task`（行 349-474）
- `detect_cycle`（行 552）
- `validate_prerequisites`（行 586）
- `chain_unlock`（行 969）
- `_calculate_*` 抽卡算法（行 1019-1140）
- `draw_single` / `_weighted_pick`（行 1160-1210）
- `ensure_*_schema` 多处（行 640-866）

**核心数据模型**：
- `Task`（行 64-187，约 250 行含 `to_dict` / `from_dict` / `from_row`）

---

### 4.1.2 目标架构：`Flask Blueprint + Application Factory + 分层` `[J]`

**目录结构**：
```
server/
├── backend_api.py                    # 仅入口：from app import create_app; app = create_app()
├── app/                              # 真正的 Flask 应用包
│   ├── __init__.py                   # create_app() 工厂
│   ├── extensions.py                 # unbound SQLite / CORS / config
│   ├── config.py                     # 配置加载（json）
│   ├── models/                       # 数据模型
│   │   ├── __init__.py
│   │   ├── task.py                   # Task 类 + to_dict / from_row
│   │   └── ...                       # 其他需要独立的数据类
│   ├── repositories/                 # 数据访问层
│   │   ├── __init__.py
│   │   ├── task_repo.py              # get_all_tasks / get_task_by_id / add_task / update_task / delete_task
│   │   ├── gacha_repo.py             # record_draw / get_discard_pile_tasks / move_to_discard
│   │   ├── schedule_repo.py
│   │   ├── state_repo.py
│   │   ├── knowledge_repo.py
│   │   └── timer_repo.py
│   ├── services/                     # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── task_service.py           # 含 cycle 检测、prerequisite 验证、chain_unlock
│   │   ├── gacha_service.py          # 含 _calculate_* / draw_single / _weighted_pick
│   │   ├── schedule_service.py
│   │   ├── state_service.py
│   │   ├── knowledge_service.py      # Markdown 渲染 + vault 浏览
│   │   └── timer_service.py
│   ├── blueprints/                   # HTTP 路由层（thin handler）
│   │   ├── __init__.py
│   │   ├── tasks.py                  # tasks_bp = Blueprint('tasks', url_prefix='/api/tasks')
│   │   ├── gacha.py
│   │   ├── discard.py
│   │   ├── tags.py
│   │   ├── dependencies.py           # /api/dependencies
│   │   ├── export.py                 # /api/export
│   │   ├── schedule.py
│   │   ├── state.py
│   │   ├── timer.py
│   │   ├── feedback.py
│   │   ├── knowledge.py
│   │   ├── config.py
│   │   ├── prompts.py
│   │   └── agent.py
│   └── utils/                        # 跨 blueprint 工具
│       ├── __init__.py
│       ├── task_blocked.py           # _task_blocked_message
│       ├── wiki_link.py              # _wiki_link_target / _vault_rel_path
│       └── energy_calc.py            # _calculate_full_weight 等共享
└── tests/
    ├── test_task_service.py          # service 层单测（可脱 DB）
    ├── test_gacha_algorithm.py       # 抽卡算法 snapshot
    ├── ...
    └── e2e-manual.js                 # 现有 E2E（保留，跨 blueprint 集成）
```

**关键约束** `[J]`：
- **Blueprint 只做 HTTP 转换**——一个路由 ≤ 10 行
- **Service 层做业务规则**——可被 Blueprint 调用、可被测试调用
- **Repository 层做 SQL**——可在内存版（test）和 SQLite 版（prod）切换
- **依赖单向**：blueprint → service → repository → models（不反向）

---

### 4.1.3 分阶段迁移路径 `[J]`

**Phase 0：行为固定**（0.5 天）
- 跑基线：26 E2E 全绿（已有）
- 加 5-10 个 `pytest` 测试覆盖核心算法：
  - `detect_cycle` / `chain_unlock` / `draw_single` / `_calculate_full_weight`
- 输出：`tests/algorithm_golden.py`（characterization tests）

**Phase 1：建 app 包骨架**（1 天）
- 新建 `server/app/` + `__init__.py`（`create_app`）+ `extensions.py` + `config.py`
- `backend_api.py` 改为：
  ```python
  from app import create_app
  app = create_app()
  if __name__ == '__main__':
      app.run(...)
  ```
- **E2E 必绿**（同一应用对象，仅重构外壳）
- 提交

**Phase 2：抽最稳定的域**（3-5 天）
- 顺序（按独立性从高到低）：
  1. `config.py` + `prompts.py` blueprint（最简单，几乎纯文件 I/O）
  2. `knowledge.py` blueprint（独立知识库操作，无跨域依赖）
  3. `tags.py` blueprint（纯 CRUD）
  4. `timer.py` blueprint（独立计时器逻辑）
  5. `feedback.py` blueprint（事件记录）
- 每个域拆完后跑 E2E → commit

**Phase 3：抽核心域**（5-7 天）
- 顺序：
  1. `tasks.py` blueprint + `task_service.py` + `task_repo.py`（含 cycle 检测）
  2. `gacha.py` blueprint + `gacha_service.py`（含抽卡算法）
  3. `discard.py` blueprint
  4. `state.py` blueprint + `state_service.py` + `state_repo.py`
  5. `schedule.py` blueprint + `schedule_service.py`
  6. `agent.py` blueprint（最末，因含多子路径）

**Phase 4：清理 + 加 CI 约束**（1-2 天）
- 删除 `backend_api.py` 中已迁移函数
- `backend_api.py` 缩到 ≤ 50 行
- 加 `import-linter` 配置 + pre-commit hook
- 加 CI 必跑 `lint-imports`

**总耗时估算**：单人 10-15 天（按 AGENTS.md 规则 5/6/7）

---

### 4.1.4 不做的事 `[J]`

- ❌ **不引入六边形 + DI 库**——业务域稳定、存储后端固定，过度设计
- ❌ **不引入 `dependency-injector`**——Flask Blueprint + `current_app` 已够
- ❌ **不引入微服务/插件架构**——单仓库单进程
- ❌ **不引入 SQLAlchemy**——纯 sqlite3 已稳定，加 ORM 是无意义改造
- ❌ **不引入 Pydantic**——返回 dict 即可

---

## 4.2 超级自动化学习工具前端（`app.js` ~2900 行）

### 4.2.1 现状盘点 `[F]`（来源：`static/app.js` + `RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md` §1.2）

**模块切分点**（按注释分割的 sections，grep 找到的边界）：
- L4-L30：全局错误捕获 + API client
- L31-L43：UI helpers（toast / modal）
- L44-L158：温情文案库 + 任务事件反馈
- L159-L254：页面切换 + 导航 + 健康检查
- L255-L359：卡牌主题 + 动画系统
- L360-L1050：抽卡（约 690 行，最大段）
- L404-L591：计时器 Dock
- L1206-L1646：任务管理（约 440 行，第二大段）
- L1646-L1768：日程（约 120 行）
- L1768-L1895：知识库（约 130 行）
- L1895-L2150：配置 + Agent（约 260 行）
- L2391-L2560：睡眠 / 状态评估（约 170 行）
- L2632-L2820：计时器面板（约 190 行）

---

### 4.2.2 目标架构：**Feature-based + 微内核（轻量版）** `[J]`

**核心设计哲学**（抄自 OpenClaw plugin-sdk + Blank Board micro-kernel）：
- **每个 feature 是 self-contained module**，导出 `meta + mount + unmount`
- **Narrow imports**——模块间只能通过 barrel 导入对方
- **Micro-kernel 仅 100-200 行**——路由 + 注册 + 启动

**目录结构**：
```
static/
├── app.js                            # 主入口（缩到 ~200 行）
├── core/                             # micro-kernel（~300 行总）
│   ├── bootstrap.js                  # 启动 + 注册表 + 全局错误
│   ├── router.js                     # hash 路由 + 页面切换
│   ├── api.js                        # fetch 包装（鉴权 + 重试 + 错误处理）
│   ├── event-bus.js                  # EventTarget 跨模块通信
│   ├── state.js                      # Proxy + EventTarget 响应式 store
│   ├── ui.js                         # toast / modal / loading
│   └── constants.js                  # 温情文案 + 主题常量 + 标签映射
├── modules/                          # 业务域模块
│   ├── gacha/
│   │   ├── index.js                  # 导出 meta + mount + unmount
│   │   ├── pool.js                   # 牌池逻辑
│   │   ├── card.js                   # 卡牌渲染 + 动画
│   │   ├── draw.js                   # 抽卡算法调用
│   │   └── timer.js                  # 第一计时器状态机
│   ├── tasks/
│   │   ├── index.js                  # meta + mount + unmount
│   │   ├── card.js                   # 任务卡片渲染
│   │   ├── filter.js                 # 筛选 + 搜索
│   │   ├── discard.js                # 弃牌堆
│   │   └── timer.js                  # 第二计时器状态机
│   ├── schedule/
│   │   ├── index.js
│   │   ├── sleep.js                  # 睡眠追踪
│   │   ├── energy.js                 # 能量曲线
│   │   ├── assessment.js             # 状态评估问卷
│   │   └── activities.js             # 活动管理
│   ├── knowledge/
│   │   ├── index.js
│   │   ├── vault.js                  # 笔记列表 + 分类
│   │   ├── markdown.js               # 渲染（未来用 markdown-it）
│   │   └── obsidian.js               # 打开外部 Obsidian
│   ├── config/
│   │   ├── index.js
│   │   ├── server.js                 # 服务配置
│   │   ├── prompts.js                # 提示词浏览 + 备份
│   │   └── agent.js                  # Agent 只读浏览
│   └── shared/                       # 跨 feature 共享
│       ├── warm-messages.js
│       ├── card-themes.js
│       └── format.js
└── vendor/                           # 本地化 ESM 依赖
    ├── marked.esm.js                 # 未来引入
    ├── chart.esm.js                  # 未来引入
    └── markdown-it.esm.js            # 未来引入
```

**每个模块的导出协议** `[J]`：
```js
// static/modules/gacha/index.js
export const meta = {
  name: 'gacha',
  version: '1.0.0',
  description: '抽卡 + 计时器'
};

export function mount(rootEl, ctx) {
  // ctx = { api, bus, state, router }
  initGachaPage(rootEl);
  bus.on('task:completed', handleTaskCompleted);
}

export function unmount(rootEl) {
  // 清理 DOM + 事件监听 + 计时器
  teardownGachaPage();
}
```

**核心设计决策** `[J]`：

| 决策 | 选择 | 理由 |
|---|---|---|
| **是否引入框架** | ✘ 否 | 原生 ES modules + import map，零构建链 |
| **状态管理** | Proxy + EventTarget | 与 OpenClaw 设计哲学一致，体积 0KB |
| **跨模块通信** | EventTarget 总线 | 解耦，避免互相 import |
| **路由** | hash 路由（兼容现有 URL） | 0 改动 URL |
| **CSS** | 保持内联 + 拆 `static/styles/*.css` | 现有风格延续 |
| **vendor** | 本地化到 `static/vendor/` | local-first，OpenClaw 默认无外网 |

---

### 4.2.3 分阶段迁移路径 `[J]`

**Phase 0：行为固定**（0.5 天）
- 跑基线：26 E2E 全绿
- 写 `characterization tests`：每个全局函数导出快照（签名 + 调用结果）

**Phase 1：建 core 目录**（1-2 天）
- 抽 `constants.js` + `api.js` + `event-bus.js` + `state.js` + `ui.js` + `router.js`
- `app.js` 缩到 ~300 行（仅启动 + 路由分发）
- E2E 必绿
- 引入 `<script type="importmap">`（即使空也好）

**Phase 2：抽第一个 feature**（1-2 天）
- 选 `gacha`（最大 + 最复杂，作为模式验证）
- 拆 `modules/gacha/index.js` + 子文件
- E2E 必绿（含计时器状态机）
- 提交 + 锁定模式

**Phase 3：抽剩余 features**（5-7 天）
- 顺序：`tasks` → `schedule` → `knowledge` → `config`
- 每个 feature 拆完 → 跑 E2E → commit
- 关键：双计时器状态机独立（`gacha/timer.js` vs `tasks/timer.js`）

**Phase 4：加边界约束**（1 天）
- `dependency-cruiser` 配置（详见 §3.4）
- CI 必跑 `depcruise static --validate .dependency-cruiser.cjs`

**总耗时估算**：单人 8-12 天

---

### 4.2.4 不做的事 `[J]`

- ❌ **不引入 React/Vue/Svelte**——vanilla JS 已够用，零构建链
- ❌ **不引入 Redux/Zustand**——Proxy + EventTarget 足够
- ❌ **不引入打包工具（Vite/webpack）**——保持 Flask 静态托管
- ❌ **不引入 Native Federation / 微前端**——单 SPA
- ❌ **不引入 PWA / Service Worker（除非需要离线，本项目暂不需要）**

---

## 4.3 soulvilization 模拟器

### 4.3.1 现状盘点 `[F]`（基于 README 描述）

> "Python + Pygame 模拟器（core/ 逻辑层 + world_generation 16 模块）"

**当前结构** `[J]`（基于 AGENTS.md 描述 + 业界 Pygame 范式推断）：
```
soulvilization/
├── core/                  ← 逻辑层（已存在 ✓）
│   ├── ...
└── world_generation/      ← 16 模块（已存在 ✓）
    ├── ...
```

**评估** `[J + F]`：

1. ✅ **已按域拆分**（core + world_generation）——基础架构已合格
2. ✅ **`core/` 与 `world_generation/` 分离**——符合六边形"业务与基础设施"分离思想
3. ❓ **是否已做"逻辑不依赖 Pygame"**——若 `core/` 内引用了 `pygame.surface` / `pygame.Rect`，则违反纯逻辑原则
4. ❓ **是否已用 State Pattern**（`SceneManager`）——若用 if/else mode variable 则欠改进

**业界 Pygame 模块化铁律**（来源：[projectrules.ai — Pygame Architectural Separation Rules](https://www.projectrules.ai/rules/pygame-guidelines)）`[F + J]`：

| 铁律 | 状态 | 借鉴方式 |
|---|---|---|
| **Core 与 Pygame 解耦** | ❓ 需验证 | 若 core/ 引用 pygame，需抽 `pygame_adapter/` 层 |
| **抽象渲染接口**（Renderer Protocol） | ❓ 需验证 | 若直接调用 `screen.blit`，需引入 `Renderer` 接口 |
| **抽象输入接口**（InputHandler） | ❓ 需验证 | 若直接读 `pygame.event.get()`，需引入 `InputHandler` |
| **状态机（SceneManager）** | ❓ 需验证 | 若用 if/else mode，引入 Scene 基类 + SceneManager |
| **事件总线 / Observer** | ❓ 需验证 | 若直接耦合，引入 EventBus 解耦 |
| **DI（服务注入）** | ❓ 需验证 | RNG / AssetManager 等通过构造函数传入 |

---

### 4.3.2 推荐改进（轻量）`[J]`

**最小改动方案**（基于 [Pygame Architectural Separation Rules](https://www.projectrules.ai/rules/pygame-guidelines) + [SebZanardo/The-Ultimate-Pygame-Structure](https://github.com/SebZanardo/The-Ultimate-Pygame-Structure) + [tombackert/ninja-game architecture](https://github.com/tombackert/ninja-game/blob/main/docs/architecture.md)）：

```
soulvilization/
├── core/                       ← 纯逻辑（不改）
│   ├── entities/
│   ├── ai/
│   └── ...
├── world_generation/           ← 数据生成（不改）
│   ├── noise.py
│   ├── ...
│   └── ...
├── rendering/                  ← 新增：Pygame 适配层（Renderer / UI）
│   ├── renderer.py             # 实现 core 定义的 Renderer Protocol
│   ├── input_handler.py        # Pygame event → GameAction
│   ├── resource_manager.py     # 资产加载 + 缓存
│   └── ui/                     # 菜单 / HUD / 弹窗
├── scenes/                     ← 新增：Scene / SceneManager（参考 ninja-game）
│   ├── base_scene.py
│   ├── scene_manager.py
│   ├── title_scene.py
│   ├── game_scene.py
│   └── ...
├── events/                     ← 新增：EventBus（解耦模块通信）
│   ├── event_bus.py
│   └── events.py               # TypedEvent 枚举
├── services/                   ← 新增：跨模块服务（DI 注入）
│   ├── rng_service.py          # 种子化随机
│   ├── settings.py             # 配置持久化
│   └── audio_service.py
├── assets/                     ← 资源（不改）
├── tests/
│   ├── test_core_logic.py      # 不需要 Pygame 初始化
│   └── test_scenes.py
└── main.py                     # 入口：组装 + SceneManager.run()
```

**每个 Scene 的模板**（参考 [sqlpey.com — Refactoring Pygame Scene Management](https://sqlpey.com/python/refactoring-pygame-scene-management/)）`[F]`：

```python
class BaseScene(Protocol):
    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def render(self, screen: pygame.Surface) -> None: ...

class GameScene(BaseScene):
    def __init__(self, level_no: int, services: ServiceContainer):
        self.level = build_level(level_no)
        self.services = services  # rng / asset / audio

    def update(self, dt):
        # 模拟更新（可被核心逻辑接管）
        ...
```

---

### 4.3.3 分阶段迁移 `[J]`

**Phase 1（半天）**：画现状依赖图
- `pydeps core/` 看是否依赖 Pygame
- 若是，先抽 `core/interfaces.py`（Renderer / InputHandler Protocols）

**Phase 2（1 天）**：抽 Pygame 适配层
- `rendering/renderer.py` / `input_handler.py` / `resource_manager.py`

**Phase 3（1-2 天）**：引入 SceneManager
- 把 main loop 的 if/else mode 改成 `scene_manager.run()`
- 现有功能保留，UI 流更清晰

**Phase 4（可选）**：加 EventBus + DI
- 跨模块通信走 EventBus
- 服务注入通过构造函数

---

## 4.4 聊天记录导出（脚本工具）

**现状** `[J]`：Python 脚本工具（按 AGENTS.md 描述）

**评估** `[J]`：脚本工具无需过度模块化

**建议** `[J]`：
- 如果是"一次性的导出脚本" → 保持 flat，**不引入 SRC layout**
- 如果是"定期运行的 ETL 工具" → 拆 `src/chat_export/` 包 + `tests/` + `pyproject.toml`

**结构参考** `[J]`：
```
chat-export/
├── src/
│   └── chat_export/
│       ├── __init__.py
│       ├── extractor.py       # 主逻辑
│       ├── formatters.py      # 输出格式（JSON/Markdown/CSV）
│       └── cli.py             # CLI 入口（click / typer）
├── tests/
│   ├── test_extractor.py
│   └── test_formatters.py
├── pyproject.toml
└── README.md
```

---

## 4.5 OpenClaw 调度平台（已有 plugin-sdk，直接复用即可）

**OpenClaw 自身已经是模块化典范**（详见 §2.3）`[F + J]`：

- `extensions/` 目录 + pnpm workspace
- `src/plugin-sdk/` 13 个 narrow subpath
- `definePluginEntry / defineChannelPluginEntry` 注册式 API
- CI 强制 import 边界（三个 `check-*-import-boundary.mts` 脚本）

**对我们的建议** `[J]`：

1. **不"重新发明"插件架构**——OpenClaw 已有完美范本
2. **直接用 OpenClaw**：
   - 后端通过 `/hooks/agent` 调用 OpenClaw（已在 `RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md` §2.4 详细调研）
   - 前端通过 iframe + postMessage 与 Control UI 通信（已在 §2.5）
3. **借鉴 plugin-sdk 设计哲学到 SAL 自有代码**：
   - **Narrow subpath**——`static/core/` 按职责细分
   - **入口协议**——`{ meta, mount, unmount }`
   - **CI 边界检测**——`dependency-cruiser` 强制模块边界

---

# 5. Top 3 推荐 + 每项目第一步拆分动作

## 5.1 Top 3 高明架构范本

### 🥇 OpenClaw plugin-sdk（narrow subpath + PluginEntry 注册式 + CI 边界检测）

> **为什么排第一**：我们已经在用 OpenClaw。它自身就是我们要抄的"高明架构"。narrow subpath 设计 + definePluginEntry + CI 边界检测 = **业界 2026 的最佳实践**。

### 🥈 maxkrivich/fast-api-reference-project（六边形 + import-linter CI 约束）

> **为什么排第二**：纯 Python / Flask 可借鉴，CI 强制层级约束（`import-linter` 配置 + `pyproject.toml`）。本项目 Python 后端可借鉴到 `service / repository / blueprint` 分层 + CI 架构验证。

### 🥉 benavlabs/FastAPI-boilerplate（vertical-slice 模块化 + CLI 代码生成）

> **为什么排第三**：2K stars 业界标杆。`bp` CLI 自动生成模块的思路可借鉴到我们的 `scripts/sal.py`——自动生成 Blueprint 模板。

### ⭐ 副推：cburmeister/flask-bones（Flask Blueprint 经典范本）

> 990 stars 老牌 Flask Blueprint 范本；本项目 Flask 后端可直接照搬 `app/__init__.py + extensions.py + blueprints/` 结构。

### ⭐ 副推：Blank Board（vanilla JS micro-kernel）

> 100 行 micro-kernel + ES modules；本项目前端 `app.js` 拆分后可借鉴。

---

## 5.2 每个项目的第一步拆分动作

| 项目 | 第一步 | 耗时 | 立即产出 |
|---|---|---|---|
| **学习工具后端** | 建 `server/app/` 包骨架 + `create_app()` + `extensions.py` + `config.py`；`backend_api.py` 改为入口壳 | 1 天 | E2E 必绿，架构外壳就绪 |
| **学习工具前端** | 抽 `static/core/` 六个文件（constants / api / event-bus / state / ui / router）；`app.js` 缩到 ~300 行 | 1-2 天 | E2E 必绿，micro-kernel 就绪 |
| **soulvilization** | 画依赖图（`pydeps core/`），验证 `core/` 是否引用 Pygame | 半天 | 决策：要不要抽 Pygame 适配层 |
| **聊天记录导出** | 不动（脚本工具无需拆分） | 0 | 保持现状 |
| **OpenClaw** | 不动（已是范本） | 0 | 直接复用其 API |

---

# 6. 风险与未知点

## 6.1 已识别风险（按严重度）

| 风险 | 等级 | 描述 | 缓解 |
|---|---|---|---|
| **3439 行单文件拆分破坏现有 E2E** | 高 | 现有 26 E2E 是基线，拆分极易引入回归 | AGENTS.md 规则 5：先写 RED 测试再拆；Phase 0 写 characterization test；逐域拆分 |
| **`app.js` 拆 ES modules 改动 MIME/CORS** | 中 | Flask 默认 `text/javascript` 正确，但需确认静态托管无 `application/octet-stream` 异常 | 测试时浏览器 Network 面板确认；CORS 仅跨域需要，本项目同源 OK |
| **双计时器状态机拆分时回归** | 高 | `gacha/timer.js` 和 `tasks/timer.js` 共享 dock + 内联面板 | 两个 timer 都 ES module 化后，必须写专门 E2E 覆盖；或合并为一个 timer state machine |
| **SQLite 并发写** | 高 | worktree 拆分时多进程写同一 DB 会损坏 | 已有 `RESEARCH_MULTITASK` 报告 §3.1.3：worktree 用 DB 副本；写只能在 main |
| **拆分后反而更糟（意大利面依赖）** | 中 | 拆分时若没有 CI 边界约束，半年后退化 | 立即加 `import-linter` + `dependency-cruiser` CI |
| **没引入测试覆盖核心算法** | 中 | `detect_cycle` / `_calculate_full_weight` / `draw_single` 几乎没单测 | Phase 0 加 5-10 个 characterization test |
| **OpenClaw API 演进风险** | 低 | OpenClaw 自身会演化，narrow subpath 可能改名 | 固定 `package.json` 锁定版本；订阅 OpenClaw 变更通知 |
| **vanilla ES modules 在老浏览器不兼容** | 低 | ES modules 需 Chrome 61+ / Safari 11+ / Firefox 60+ | 本项目 self-hosted，目标用户都是现代浏览器 |

## 6.2 未知点（需进一步验证）

| 未知点 | 验证方式 |
|---|---|
| **soulvilization 当前 `core/` 是否真不依赖 Pygame** | 跑 `pydeps soulvilization/core/` 看 import 列表 |
| **OpenClaw 当前本机版本是否已实现所有 §2.3 提到的机制** | 读 `C:\Users\wn\.openclaw\workspace` 实际目录 |
| **`server/backend_api.py` 全局状态（`app` / `conn` 变量）有哪些需保留** | 实读 + grep `global ` 关键字 |
| **现有 26 E2E 用例覆盖完整度** | 已读 `tests/e2e-manual.js` 头部用例清单；建议补 5-10 个核心算法用例 |
| **`static/app.js` 全局变量数量** | grep `^var ` / `^let ` 数量，决定 state 抽离工作量 |
| **`backend_api.py` 数据库连接是否全局单例** | grep `get_db_connection` 调用上下文 |
| **`src/index.html` 与 app.js 的耦合度** | 检查 `<script src>` 顺序、CSS class 名共享 |

## 6.3 过度设计警示

| 陷阱 | 描述 | 何时应避免 |
|---|---|---|
| **六边形 + DI 库** | 业务域稳定、不换 DB、不做微服务 | 本项目 Flask 后端不需要 |
| **微前端（Native Federation）** | 单团队单部署 | 本项目不需要 |
| **插件架构** | 业务边界清晰、外部扩展需求 | OpenClaw 已有；SAL 自有代码不需要 |
| **微内核（micro-kernel 100 行）** | 需要真正的插件生态 | 本项目用"轻量 micro-kernel 协议"已够，不必走极端 |
| **Pydantic / SQLAlchemy / Dependency Injector** | 简单场景下是负担 | Flask + sqlite3 + dict 返回已够 |
| **Vite/webpack/esbuild** | 引入构建链 | 现有 Flask 静态托管已够 |

## 6.4 与现有技术栈冲突点

| 冲突 | 描述 | 解决方案 |
|---|---|---|
| **`backend_api.py` 全局 `app` 对象** | Blueprint + factory 要求 `app` 在工厂内创建 | 改 `backend_api.py` 为 `from app import create_app; app = create_app()`（10 行变更） |
| **`static/app.js` 全局变量** | ES modules 不允许顶层 `var` 全局可见 | 用 `state.js` 集中管理全局状态；非状态全局用 `window.SAL = {...}` |
| **现有 `index.html` 内联 CSS** | 与拆出的 `static/styles/*.css` 重复 | 一次性迁出；CSS 变量集中到 `:root` |
| **`tests/e2e-manual.js` 强耦合 `app.js` 内部实现** | 通过全局 ID 选择元素 | E2E 不改；新增的 characterization test 用更稳定的语义选择 |

---

# 附录 A · 全部来源清单（去重、按主题分组）

## A.1 后端模块化

- [Flask Large-App Structure - Tomoda Hinata](https://tomodahinata.com/en/blog/flask-application-factory-blueprints-large-app-structure-guide)
- [Flask Best Practices - Simi Studio](https://simi.studio/en/posts/flask-best-practices/)
- [How to Structure Large Flask Applications - oneuptime](https://oneuptime.com/blog/post/2026-01-26-flask-large-applications/view)
- [Application Factory Architecture - Bruno Rocha (YouTube)](https://www.youtube.com/watch?v=xNo-eOfZH5Q)
- [Flask Mega-Tutorial Part XV - miguelgrinberg.com](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xv-a-better-application-structure)
- [How to Use Flask Blueprints - oneuptime](https://oneuptime.com/blog/post/2026-01-27-flask-blueprints-modular/view)
- [tutorial-flask flask-project-structure - app-generator](https://github.com/app-generator/tutorial-flask/blob/main/flask-project-structure.md)
- [cburmeister/flask-bones](https://github.com/cburmeister/flask-bones/)（990 stars）
- [dimmg/flusk](https://github.com/dimmg/flusk)（221 stars）
- [Flask dependency-injector tutorial](https://python-dependency-injector.ets-labs.org/tutorials/flask.html)

## A.2 FastAPI 模块化

- [How to Structure Large FastAPI Projects - fastapi-patterns.com](https://fastapi-patterns.com/core-architecture-routing-patterns/modular-router-organization/how-to-structure-large-fastapi-projects-for-scale/)
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices/blob/master/README.md)
- [FastAPI Large-App Design - Tomoda Hinata](https://tomodahinata.com/en/blog/fastapi-project-structure-apirouter-dependencies-large-app-guide)
- [Production-Ready FastAPI 2026 - DEV.to](https://dev.to/datanestdigital/production-ready-fastapi-project-structure-2026-guide-b1g)
- [Best Practices in FastAPI Architecture - zyneto](https://zyneto.com/blog/best-practices-in-fastapi-architecture)
- [FastAPI Bigger Applications - 官方](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Modular Project Structure With FastAPI Routers - YouTube](https://www.youtube.com/watch?v=_kNyYIFSOFU)
- [Anatomy of a Scalable Python Project (FastAPI) - YouTube](https://www.youtube.com/watch?v=Af6Zr0tNNdE)
- [benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate)（2,051 stars）
- [23bg/racerapi](https://github.com/23bg/racerapi)
- [YoraiLevi/modular-monolith-fastapi](https://github.com/YoraiLevi/modular-monolith-fastapi)
- [Khaled-Farhat/modular-monolith-practice](https://github.com/Khaled-Farhat/modular-monolith-practice)
- [arctikant/fastapi-modular-monolith-starter-kit](https://github.com/arctikant/fastapi-modular-monolith-starter-kit)

## A.3 六边形架构 / Ports & Adapters

- [serfer2/flask-hexagonal-architecture-api](https://github.com/serfer2/flask-hexagonal-architecture-api)
- [MatthiasEg/python-hexagonal-architecture-template](https://github.com/MatthiasEg/python-hexagonal-architecture-template)
- [ShahriyarR/hexagonal-calculator](https://github.com/ShahriyarR/hexagonal-calculator)
- [ShahriyarR/hexagonal-flask-blog-tutorial](https://github.com/ShahriyarR/hexagonal-flask-blog-tutorial)
- [maxkrivich/fast-api-reference-project](https://github.com/maxkrivich/fast-api-reference-project)（**本调研关键范本**）
- [Stop Mixing FastAPI with Business Logic - YouTube](https://www.youtube.com/watch?v=FXwBWS4qDAA)
- [Tutorial: Building a Flask Application with Hexagonal Architecture - İlyas](https://medium.com/@ilyas_genel/tutorial-building-a-flask-application-with-hexagonal-software-architecture-6a396cc6f20d)
- [Isolate Core Logic From Flask Dependencies - codingeasypeasy](https://codingeasypeasy.com/blog/isolate-core-logic-from-flask-dependencies-a-ports-and-adapters-approach/)
- [Cosmic Python - Service Layer Chapter 4](https://www.cosmicpython.com/book/chapter_04_service_layer.html)

## A.4 前端 ES modules 组织

- [How to Structure a JavaScript Project in 2026 - JavaScript Jobs Hub](https://www.jsgurujobs.com/blog/how-to-structure-a-javascript-project-in-2026-and-the-folder-architecture-that-scales-from-side-project-to-500-file-production-application)
- [6 JavaScript Project Structure Patterns - DEV.to](https://dev.to/jsgurujobs/6-javascript-project-structure-patterns-that-eliminate-import-chaos-in-large-codebases-3fcd)
- [Layer pattern vs Module pattern - LinkedIn](https://www.linkedin.com/pulse/layer-pattern-vs-module-folder-structure-context-ai-machiraju-rdmec)
- [Why Your JavaScript Module Architecture Matters - chyshkala.com](https://chyshkala.com/blog/why-your-javascript-module-architecture-matters-more-than-your-framework-choice)
- [Organize your repository with features - kamiljozwik.com](https://www.kamiljozwik.com/posts/features-folder)

## A.5 前端状态管理（vanilla）

- [Reactivity Without a Framework - openreplay](https://blog.openreplay.com/reactivity-without-framework-native-js/)
- [Rethinking Reactivity in JavaScript - acuevas.dev](https://acuevas.dev/articles/reactivity-with-proxies/)
- [JavaScript Proxy for Reactive State - BSWEN](https://docs.bswen.com/blog/2026-04-30-javascript-proxy-reactivity/)
- [State Management in Vanilla JS: 2026 - LinkedIn](https://www.linkedin.com/pulse/state-management-vanilla-js-2026-trends-vibidsoft-1uvpf)
- [Manage State in Vanilla JS - BSWEN](https://docs.bswen.com/blog/2026-04-30-vanilla-js-state-management/)

## A.6 前端插件架构 / 微内核

- [Building a Plugin-Based JavaScript Dashboard - JavaScript in Plain English](https://javascript.plainenglish.io/building-a-plugin-based-javascript-dashboard-that-can-evolve-without-rewrites-ce4ad97b0a03)
- [femcodersclub/productivity-dashboard-js](https://github.com/femcodersclub/productivity-dashboard-js)
- [Blank Board architecture docs](https://empty-ad9a3406.mintlify.app/concepts/architecture)
- [Blank Board introduction](https://empty-ad9a3406.mintlify.app/introduction)

## A.7 微前端 / Native Federation

- [Native Federation 官网](https://native-federation.com/)
- [native-federation/native-federation-core](https://github.com/native-federation/native-federation-core)
- [Micro Frontends with Native Federation - DEV.to](https://dev.to/florianrappl/micro-frontends-with-native-federation-56j4)
- [Micro Frontends: iframes vs Module Federation - Medium](https://viniciusmarson.medium.com/micro-frontend-architecture-iframes-x-module-federation-1782026d95c6)
- [native-federation/orchestrator](https://github.com/native-federation/orchestrator)

## A.8 Python 包结构 + DI

- [Python Package Structure & Layout - pyOpenSci](https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html)
- [src layout vs flat layout - Real Python](https://realpython.com/ref/best-practices/project-layout/)
- [src layout vs flat - pydevtools](https://pydevtools.com/handbook/explanation/src-layout-vs-flat-layout/)
- [Python src layout vs flat - Narcis Miclaus](https://narcismiclaus.com/programming/python/16-project-layout/)
- [packaging.python.org src-layout-vs-flat-layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Python DI Tutorial - datacamp](https://www.datacamp.com/tutorial/python-dependency-injection)
- [Python DI Libraries vs Manual Wiring - hackanons](https://hackanons.com/python-di-libraries-vs-manual-wiring-2026/)
- [Dependency Injector Wiring](https://nikuma0.github.io/python-dependency-injector/wiring.html)
- [Dependency Injector Flask tutorial](https://python-dependency-injector.ets-labs.org/tutorials/flask.html)
- [Dependency injection in Python - Snyk](https://snyk.io/blog/dependency-injection-python/)

## A.9 Python 插件架构

- [stevedore - OpenStack](https://docs.openstack.org/stevedore/1.20.1/1.20.1/)
- [Plugins - Abilian Innovation Lab](https://lab.abilian.com/Tech/Programming%20Techniques/Plugins/)
- [Plugins case study: Pluggy - Eli Bendersky](https://eli.thegreenplace.net/2026/plugins-case-study-pluggy)
- [Master Python Plugin Architecture with Pluggy and Stevedore - besthub](https://www.besthub.dev/articles/master-python-plugin-architecture-with-pluggy-and-stevedore-a-hands-on-guide-04ed4354ce7f)
- [Pluggy 官方文档](https://pluggy.readthedocs.io/en/stable/)

## A.10 Pygame 架构范式

- [Pygame Architectural Separation Rules - projectrules.ai](https://www.projectrules.ai/rules/pygame-guidelines)
- [tombackert/ninja-game architecture.md](https://github.com/tombackert/ninja-game/blob/main/docs/architecture.md)
- [Pygame Development Best Practices - projectrules.ai](https://www.projectrules.ai/rules/pygame)
- [SebZanardo/The-Ultimate-Pygame-Structure](https://github.com/SebZanardo/The-Ultimate-Pygame-Structure)
- [Refactoring Pygame Scene Management - sqlpey](https://sqlpey.com/python/refactoring-pygame-scene-management/)
- [FNAD-World](https://github.com/griffinhampton/FNAD-World)
- [Real-Time Procedural Level Design In Pygame - codewithc](https://www.codewithc.com/real-time-procedural-level-design-in-pygame/)
- [pfaustino/simple_rpg](https://github.com/pfaustino/simple_rpg)

## A.11 大文件拆分方法论

- [madge - node-madge](https://github.com/pahen/node-madge/)
- [Detect TypeScript Import Cycles - markaicode](https://markaicode.com/typescript-import-cycles-graph-analysis/)
- [A Hidden Circular Dependency - Sanyam Aggarwal](https://sanyamaggarwal.medium.com/automate-circular-dependency-detection-in-your-node-js-project-394ed08f64bf)
- [7 Advanced Techniques to Split Massive HTML/JS Files - Dre Dyson](https://dredyson.com/7-advanced-techniques-to-split-massive-html-js-files-like-a-pro-when-ai-fails/)
- [codedrop-codes/refactory](https://github.com/codedrop-codes/refactory)
- [Michael Feathers - Characterization Testing](https://michaelfeathers.silvrback.com/characterization-testing)
- [Characterisation Tests - Avesta HQ](https://avestahq.com/blog/characterisation-tests-safety-net-legacy-code)
- [Characterization Tests - Eden Technologies](https://eden-technologies.eu/blog/characterization-tests-legacy-code/)
- [Characterization testing - Mario Cervera](https://mariocervera.com/characterization-testing-adding-tests-to-legacy-code)
- [Working Effectively with Legacy Code - bssw.io](https://bssw.io/items/working-effectively-with-legacy-code)

## A.12 强制模块边界工具

- [sverweij/dependency-cruiser](https://github.com/sverweij/dependency-cruiser/)
- [dependency-cruiser npm](https://www.npmjs.com/package/dependency-cruiser)
- [Avoid Cross Module Dependencies with Dependency Cruiser - DEV.to](https://dev.to/jacobandrewsky/avoid-cross-module-dependencies-with-dependency-cruiser-3b0b)
- [Validate Dependencies According to Clean Architecture - Better Programming](https://betterprogramming.pub/validate-dependencies-according-to-clean-architecture-743077ea084c)
- [dependency-cruiser options-reference](https://github.com/sverweij/dependency-cruiser/blob/main/doc/options-reference.md)

## A.13 OpenClaw 架构（关键范本）

- [openclaw/openclaw README](https://github.com/openclaw/openclaw)
- [OpenClaw Plugins Architecture Internals](https://docs.openclaw.ai/plugins/architecture-internals.md)
- [OpenClaw Plugin SDK Overview](https://docs.openclaw.ai/plugins/sdk-overview)
- [OpenClaw SDK Setup](https://docs.openclaw.ai/plugins/sdk-setup.md)
- [OpenClaw Building Plugins](https://docs.openclaw.ai/plugins/building-plugins)
- [OpenClaw Channel Plugins](https://docs.openclaw.ai/plugins/sdk-channel-plugins)
- [OpenClaw Architecture (Gateway)](https://docs.openclaw.ai/concepts/architecture)

## A.14 本项目已有调研稿（项目内资料）

- `D:\Axelit\.工作\trae\超级自动化学习工具\README.md`
- `D:\Axelit\.工作\trae\超级自动化学习工具\AGENTS.md`
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md`（前端摸底）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\RESEARCH_ASSISTANT_FRONTEND_DESIGN_2026-08-16.md`（前端设计）
- `D:\Axelit\.工作\trae\超级自动化学习工具\docs\RESEARCH_MULTITASK_SINGLE_PROJECT_2026-08-16.md`（多路线并行）

---

*报告结束。本报告只调研 + 给方案；任何代码改动需要后续单独任务执行。*  
*建议的下一步：派"路线 0 后端 Blueprint 拆分" + "路线 0 前端 ES modules 拆分"两个会话，按 §4.1.3 + §4.2.3 路径推进；每阶段跑全量 E2E 验证。*