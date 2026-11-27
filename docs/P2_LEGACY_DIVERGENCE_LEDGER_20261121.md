# P2 Legacy 行为差异台账（AR03-P2 / Stage 1）

> **性质**：本台账是 AR03-P2 **功能保全** 的主证据之一。
>
> **为什么需要它**：Stage 1 之前，P2 只有一个 parity oracle ——"迁移前 Factory
> 的黄金 HTTP 快照"。但 **21 条兼容桥路由**（`/`、`/api/config`、
> `/api/export`、`/api/dependencies`、discard×3、`/api/agent/*`×9、
> `/api/prompts/*`×5）在迁移前 **只由 legacy 提供**，黄金快照 **根本没有
> 覆盖它们**。只用单一 oracle 会留下保全真空区。
>
> 本台账用 **实测** 数据（`scripts/legacy_divergence_probe.py`）填补
> 真空区。
>
> **Stage 7 变更（2026-11-21）**：legacy 单体已被收口成薄别名
> （不再持有任何 Flask 路由），"现场跑 legacy" 的取数方式随之失效。
> 因此 legacy 侧改为读取 **一次性冻结的基线**
> `tests/fixtures/legacy_baseline.json`（由
> `scripts/_freeze_legacy_baseline.py` 从 **迁移前的 legacy 单体**
> —— Git HEAD 版本 —— 在合成根内实测采集），Factory 侧仍为
> **实时采集**。探针因此在 legacy 收口后 **仍然具备鉴别力**：
> 任何迁移回归都会让实时 Factory 与冻结基线产生新的差异。
>
> **日期**：2026-11-21
> **机读产物**：`tests/fixtures/legacy_divergence.json`
> **冻结基线**：`tests/fixtures/legacy_baseline.json`
> **台账契约测试**：`tests/characterize/test_legacy_divergence_ledger.py`

---

## 1. 权威侧判定规则（不得逐条临时决定）

| # | 规则 | 依据 |
|---|---|---|
| **R1** | **两侧都实现** 的路由 → **Factory 现有行为为权威**，legacy 侧视为历史残留 | 生产默认运行时是 Factory（`scripts/launch_server.py` 强制 `factory`；legacy 后端被 `SystemExit` 拒绝） |
| **R2** | **legacy 独有** 的路由（Stage 5 后剩 ``/api/agent/*`` 9 条 + ``/api/prompts/*`` 5 条） → **legacy 现有行为即为权威**（唯一实现） | 迁移后不得改变可观察语义 |
| **R3** | 两侧都不存在的能力 → **不新增** | 本里程碑不新增产品需求 |
| **R4** | 差异若为 **历史缺陷** → 以权威侧为准，显式记为"按权威侧修正"，并补回归断言；**不静默继承缺陷** | 避免把 bug 搬进新架构 |
| **R5** | 差异若为 **有意差异** → 保留权威侧形状，注明另一侧形状及其历史来源，供 P5 决定是否统一 | 不在 P2 擅自统一 |

---

## 2. 实测结果总览

探针覆盖 **40 条** legacy 路由（覆盖全部 21 条兼容桥路由 + 全部重名路由
的代表样本）。legacy 侧取 **冻结基线**（迁移前单体实测），Factory 侧
**实时采集**，逐条比对状态码 / 响应体 / 副作用：

| 指标 | 数值 |
|---|---|
| 总用例 | 40 |
| **行为一致** | 32 |
| **存在差异** | 8 |

> 探针固定 `random.seed(20260121)`，确保抽卡这类随机路径抽到同一张卡，
> 否则比对结果会被随机性污染。
>
> **Stage 7 复采说明**：Stage 1 的初版计数是 33 一致 / 7 差异。复采后
> 变为 32 / 8，原因有二：
>
> 1. **冻结基线现在包含副作用摘要**（初版冻结件只保存了响应体，
>    无法比对副作用）—— 因此 `discard_pile` 的副作用差异被 **真实检出**
>    （旧口径漏检）。
> 2. **`agent_policy_status` 被检出** —— 迁移前单体（Git HEAD 版本）
>    **没有**这条路由（404），它是 P1 期间新建的 `agent_policy_bp`
>    提供的新能力，按 **R3 之外** 的既有授权保留（见 L-08）。
>
> 这两项都是 **更准确** 的测量，不是回归。

---

## 3. 差异条目（逐条裁决）

### L-01 `GET /api/health`

| 项 | 值 |
|---|---|
| 归属 | **两侧都有**（legacy 独有路由 `backend_api.py` + Factory app 级路由） |
| 实测差异 | 状态码 **相同**（200）；**响应体不同** |
| legacy | `{"status": "healthy"}` |
| Factory | `{"phase": 1, "status": "ok"}` |
| 副作用 | 无差异 |
| **裁决** | **R1** —— Factory 为权威（生产实际可观察形状） |
| 处置 | **保留 Factory 形状**。迁移后 `/api/health` 继续返回 `{"phase": 1, "status": "ok"}`。legacy 的 `{"status": "healthy"}` 是历史形状，在 `docs/P1_ADDENDUM_20261121.md` 与本台账中留档，供 P5 决定是否统一。 |
| 保全证据 | 黄金快照用例 `health`（`tests/fixtures/golden_http_snapshot.json`）；E2E 7.2 API 状态指示器 |
| 状态 | ✅ 已裁决 |

---

### L-02 `POST /api/gacha/replace` —— 缺 `reason` 时的错误语义

| 项 | 值 |
|---|---|
| 归属 | **两侧都有**（重名路由） |
| 实测差异 | 状态码 **404 → 400**；响应体不同 |
| legacy | 404 `{"error": "No replacement available"}` |
| Factory | 400 `{"error": "reason required"}` |
| 副作用 | 无差异（legacy 在此路径下已写入拒绝台账，见 L-04） |
| **裁决** | **R1** + **R4** |
| 处置 | **保留 Factory 的 400 语义**。理由：legacy 静默把缺失的 `reason` 回落成 `"other"`，并 **先写拒绝台账再校验候选** —— 这既是**历史缺陷**（用户没给理由却被记成拒绝），也让错误信息误导（"没有可替换的卡" 而不是 "你必须给理由"）。Factory 的 M02-S03-G01 合同明确要求：理由必须显式给出，缺失一律 400 且 **零副作用**。 |
| 保全证据 | 黄金快照用例 `gacha_replace_missing` / `gacha_replace_no_reason`；差异探针用例 `gacha_replace_missing` / `gacha_replace_no_reason` |
| 状态 | ✅ 已裁决（按权威侧修正，**不**继承 legacy 缺陷） |

---

### L-03 `POST /api/gacha/replace` —— 候选解析失败时的副作用

| 项 | 值 |
|---|---|
| 归属 | **两侧都有**（重名路由） |
| 实测差异 | 状态码 **相同**（404）；响应体 **相同**；**副作用不同** |
| legacy | 404 `{"error": "No replacement available"}`，但 **已写入** `task_rejection_log` 一行、`gacha_records` 一行 refusal 行，并把 `tasks.refusal_count` +1 |
| Factory | 404 `{"error": "No replacement available"}`，**零副作用** |
| **裁决** | **R1** + **R4** |
| 处置 | **保留 Factory 的零副作用语义**。legacy 把"换牌失败"记成"用户成功拒绝"，会虚增 `refusal_count` 并污染拒绝台账 —— 这是**历史缺陷**。Factory 的 M02-S03-G01 合同明确：失败的换牌请求 **绝不** 被记成"用户成功拒绝"或"成功发牌"。 |
| 保全证据 | 差异探针用例 `gacha_replace_with_reason`（比对 `gacha_records` / `task_rejection_log` 副作用摘要）；黄金快照副作用比对 |
| 状态 | ✅ 已裁决（按权威侧修正） |

---

### L-04 `GET /api/export` —— 导出内容的副作用可见性

| 项 | 值 |
|---|---|
| 归属 | **legacy 独有**（兼容桥路由 `/api/export`） |
| 实测差异 | 状态码相同（200）；响应体 **结构相同**，`gacha_records` / `task_rejection_log` **内容不同** |
| legacy | 导出含 `gacha_records` 1 行（`task_id=999999`, `refusal_reason="other"`）+ `task_rejection_log` 1 行 |
| Factory | 同样 2 张表，但为空数组 |
| 根因 | **不是** export 本身行为不同，而是 **L-03 的副作用差异** 传导：legacy 在前面的 replace 请求里写了拒绝台账，Factory 没有。导出只是把既有 DB 状态原样呈现。 |
| **裁决** | **R1**（导出表的清单与结构以 Factory 为准）+ L-03 的连带裁决 |
| 处置 | **保留 Factory 行为**。`/api/export` 的导出表清单（`tasks` / `tags` / `task_tags` / `task_dependencies` / `gacha_records` / `task_rejection_log` / `daily_user_state` / `daily_schedules` / `task_completion_feedback`）与响应结构 **完全一致**；差异仅来自上游副作用。迁移后 `/api/export` 必须保持 Factory 的表清单与结构。 |
| 保全证据 | 黄金快照用例 `export`（结构比对）；差异探针用例 `export` |
| 状态 | ✅ 已裁决（连带 L-03） |

---

### L-05 `POST /api/agent/save-note` —— AI 写 Obsidian 笔记

| 项 | 值 |
|---|---|
| 归属 | **legacy 独有**（兼容桥路由 `/api/agent/save-note`） |
| 实测差异 | 状态码 **200 → 403**；响应体不同 |
| legacy | 200 `{"path": "<vault>/note.md", "relative": "note.md", "saved": true}` —— **真的写了**笔记文件 |
| Factory | 403 `{"error": "AI knowledge-base writes are disabled"}` |
| 根因 | 迁移前的 `server/app/legacy_compat.py` **显式**替换了该路由的 view function：AI 不得写 Obsidian 笔记。这是 **用户策略**（见 P1 交接文档：*"User policy: AI may modify regular tasks, not Obsidian notes."*），由兼容桥注入。**Stage 6 起** 该 403 已 **原生实现在** `server/blueprints/agent_bp.py`（+ `server/services/agent.py::save_note_blocked`），**不再** 依赖兼容桥。 |
| **裁决** | **R1 + R5**（这是 **有意差异**，不是缺陷） |
| 处置 | **保留 Factory 的 403 行为**。Stage 6 迁移 Agent 域时，该 403 **必须** 在真正的 `agent_bp` 内 **显式实现**，**不再依赖兼容桥注入**。这是 **明确的产品边界**，不得因"功能保全"而把"允许 AI 写笔记"恢复回来。 |
| 保全证据 | 差异探针用例 `agent_save_note`（断言 403 + 零文件写入）；`tests/characterize/test_stage6_prompts_agent.py::Stage6BehaviorTests`（403 + 零写入断言） |
| 状态 | ✅ 已裁决（有意差异，保留 403） |

---

### L-06 `GET /api/discard-pile` —— 副作用摘要差异

| 项 | 值 |
|---|---|
| 归属 | **legacy 独有**（兼容桥路由 `/api/discard-pile`） |
| 实测差异 | 状态码相同（200）；响应体 **相同**（都是 `[]`）；**副作用摘要不同** |
| 根因 | 弃牌表在两条路径下都为空，但 legacy 的弃牌恢复路径会 **先写 `task_rejection_log`** 再判断能否恢复（与 L-03 同源），Factory 不写。差异 **不来自** `/api/discard-pile` 自身的读取逻辑。 |
| **裁决** | **R2**（legacy 独有路由 → legacy 读取语义即权威）+ L-03 的连带裁决 |
| 处置 | **保留 Factory 行为**。`/api/discard-pile` 的响应结构（弃牌任务数组 + 字段形状）以 **实测一致** 为准 —— 两侧响应体相同，无结构差异；迁移后必须保持该结构。 |
| 保全证据 | 差异探针用例 `discard_pile`（响应体一致断言 + 副作用摘要比对）；黄金快照用例 `discard_pile` |
| 状态 | ✅ 已裁决（连带 L-03） |

> **Stage 7 复采备注**：初版冻结基线只保存了响应体，**没有**保存副作用
> 摘要，因此本条差异在初版口径下被 **漏检**（误列为"一致"）。Stage 7
> 的冻结基线补齐副作用摘要后，本条被真实检出。

---

### L-07 `POST /api/gacha/replace` —— `reason` 类型/取值校验

| 项 | 值 |
|---|---|
| 归属 | **两侧都有**（重名路由） |
| 实测差异 | legacy **不做校验**（任何 reason 都接受，含缺失）；Factory 严格校验（缺失/空串/非字符串/未知值 → 400） |
| legacy | 缺失 reason → 静默用 `"other"`；未知 reason（如 `"whatever"`）→ 也接受 |
| Factory | 缺失 → 400 `reason required`；非字符串 → 400 `reason must be a string`；空串 → 400；未知值 → 400 `reason must be one of low_energy/no_time/similar_done/other` |
| **裁决** | **R1** + **R4** |
| 处置 | **保留 Factory 的严格校验**。理由白名单（`low_energy` / `no_time` / `similar_done` / `other`）与前端 `static/app.js` 的换牌理由单选框、以及 `docs/design-spec.txt` 记录的合同一致；legacy 的"任何值都接受"是历史宽松行为。 |
| 保全证据 | 差异探针用例 `gacha_replace_no_reason`；Stage 3 将补 gacha 域契约测试锁定白名单 |
| 状态 | ✅ 已裁决（按权威侧修正） |

---

### L-08 `GET /api/agent-policy/status` —— legacy 侧 **不存在** 该路由

| 项 | 值 |
|---|---|
| 归属 | **Factory 独有**（legacy 单体在 Git HEAD 版本里没有这条路由） |
| 实测差异 | 状态码 **404 → 200**；响应体不同 |
| legacy | 404（Flask 默认 HTML 404 页面）—— 该路由在迁移前的单体里 **根本不存在** |
| Factory | 200 `{"initialized": false, "reason": "latest_json_absent", "status": "missing", "version": null}` |
| 副作用 | 无差异（该端点 **纯只读**，从不创建 / 写入 / 修复 `data/agent-policy/` 与 `latest.json`） |
| 根因 | 该路由由 **P1 期间** 新建的 `server/blueprints/agent_policy_bp.py` 提供，契约见 `LT_BOOTSTRAP_FIRST_CARD_20261021_A`（引导卡需要查询策略初始化状态）。P2 迁移期 **没有** 引入任何新端点 —— 这是 P1 既有成果的显影。 |
| **裁决** | **R1 + R5**（**有意差异**：P1 授权的新能力，且属"安全只读"端点） |
| 处置 | **保留 Factory 的 200 只读响应**。不得因"功能保全"而把它退回 404 —— 那会破坏 P1 引导卡流程。台账在 Stage 1 初版把这条路由误标为"两侧都有 / 一致"，Stage 7 复采后按实测纠正。 |
| 保全证据 | 差异探针用例 `agent_policy_status`（404 → 200）；`tests/characterize/test_agent_policy_*.py` 只读契约断言 |
| 状态 | ✅ 已裁决（P1 授权的新能力，保留） |

---

## 4. 行为一致的条目（32 条）

以下路由在 legacy 与 Factory 之间 **实测完全一致**（状态码 + 响应体 + 副作用
三项全同），迁移后必须保持一致：

| 域 | 路由 |
|---|---|
| 任务 | `GET /api/tasks`、`GET /api/tasks/{p}`、`POST /api/tasks`、`PUT /api/tasks/{p}`、`DELETE /api/tasks/{p}`、`GET /api/tasks/{p}/dependents`、`POST /api/tasks/{p}/complete`、`POST /api/tasks/{p}/skip`、`POST /api/tasks/{p}/refuse` |
| 标签 | `GET /api/tags`、`POST /api/tags`、`DELETE /api/tags/{p}`、`POST /api/tags/batch` |
| 抽卡 | `GET /api/gacha/pools`、`GET /api/gacha/pools/detail`、`GET /api/gacha/statistics`、`POST /api/gacha/draw`、`POST /api/gacha/care-draw` |
| 弃牌 | `POST /api/discard-pile/{p}/restore`、`POST /api/tasks/{p}/move-to-discard` |
| 依赖图 | `GET /api/dependencies` |
| 配置 | `GET /api/config` |
| 索引 | `GET /` |
| Agent | `GET /api/agent/agents`、`GET /api/agent/files/raw`、`GET /api/agent/files/vault` |
| Prompts | `GET /api/prompts`、`GET /api/prompts/{p}` |

> 占位符说明：`{p}` 代表路径参数段（`<int:task_id>` / `<path:name>` /
> `<agent_id>`）。
>
> **口径修正（Stage 7）**：初版把 `GET /api/discard-pile` 与
> `GET /api/agent-policy/status` 也列入本清单。复采后：
> 前者的 **副作用摘要** 实测有差异（见 L-06），后者的 legacy 侧
> **根本不存在**该路由（见 L-08）—— 两条均已移出本清单。

---

## 4.1 Legacy 活跃路由 **全覆盖** 清单（43 条）

下表是 legacy 全部活跃路由的 **逐条** 裁决结果。
`{p}` = 路径参数段。

> **兼容桥白名单的演进**（AR03-P2 各阶段逐步收口）：
>
> | 阶段 | 兼容桥 `EXACT_ROUTES` | 剩余 `PREFIX_ROUTES` |
> |---|---|---|
> | Stage 0（P1 收口时） | `/`、`/api/config`、`/api/config/save`、`/api/export`、`/api/dependencies`、discard ×3 | `/api/agent/`、`/api/prompts` |
> | Stage 2 后 | `/`、`/api/config`、`/api/config/save`、`/api/export` | 同上 |
> | **Stage 5 后（当前）** | **（空集）** | 同上 |

| # | 方法 | 路由 | 归属 | 裁决 | 结论 |
|---|---|---|---|---|---|
| 1 | GET | `/api/agent-policy/status` | Factory 独有（P1 新增） | R1+R5 | **差异 L-08**（保留 200 只读） |
| 2 | GET | `/api/tasks` | 两侧都有 | R1 | 一致 |
| 3 | GET | `/api/tasks/{p}` | 两侧都有 | R1 | 一致 |
| 4 | POST | `/api/tasks` | 两侧都有 | R1 | 一致 |
| 5 | PUT | `/api/tasks/{p}` | 两侧都有 | R1 | 一致 |
| 6 | DELETE | `/api/tasks/{p}` | 两侧都有 | R1 | 一致 |
| 7 | GET | `/api/tasks/{p}/dependents` | 两侧都有 | R1 | 一致 |
| 8 | POST | `/api/tasks/{p}/complete` | 两侧都有 | R1 | 一致 |
| 9 | POST | `/api/tasks/{p}/skip` | 两侧都有 | R1 | 一致 |
| 10 | POST | `/api/tasks/{p}/refuse` | 两侧都有 | R1 | 一致 |
| 11 | GET | `/api/gacha/pools` | 两侧都有 | R1 | 一致 |
| 12 | POST | `/api/gacha/draw` | 两侧都有 | R1 | 一致 |
| 13 | POST | `/api/gacha/care-draw` | 两侧都有 | R1 | 一致 |
| 14 | GET | `/api/discard-pile` | 两侧都有 | R2 | **差异 L-06**（副作用摘要差异） |
| 15 | POST | `/api/discard-pile/{p}/restore` | 两侧都有 | R2 | 一致 |
| 16 | POST | `/api/tasks/{p}/move-to-discard` | 两侧都有 | R2 | 一致 |
| 17 | GET | `/api/health` | 两侧都有 | R1 | **差异 L-01** |
| 18 | GET | `/api/config` | 两侧都有 | R2 | 一致 |
| 19 | POST | `/api/config/save` | legacy 独有 | R2 | 一致 |
| 20 | GET | `/api/tags` | 两侧都有 | R1 | 一致 |
| 21 | POST | `/api/tags` | 两侧都有 | R1 | 一致 |
| 22 | DELETE | `/api/tags/{p}` | 两侧都有 | R1 | 一致 |
| 23 | POST | `/api/tags/batch` | 两侧都有 | R1 | 一致 |
| 24 | GET | `/api/gacha/pools/detail` | 两侧都有 | R1 | 一致 |
| 25 | GET | `/api/gacha/statistics` | 两侧都有 | R1 | 一致 |
| 26 | POST | `/api/gacha/replace` | 两侧都有 | R1 | **差异 L-02 / L-03 / L-07** |
| 27 | GET | `/api/dependencies` | 两侧都有 | R2 | 一致 |
| 28 | GET | `/api/export` | 两侧都有 | R2 | **差异 L-04** |
| 29 | GET | `/` | 两侧都有 | R2 | 一致 |
| 30 | GET | `/api/agent/agents` | legacy 独有 | R2 | 一致 |
| 31 | GET | `/api/agent/files/raw` | legacy 独有 | R2 | 一致 |
| 32 | GET | `/api/agent/files/vault` | legacy 独有 | R2 | 一致 |
| 33 | GET | `/api/agent/agents/{p}/prompt` | legacy 独有 | R2 | 一致 |
| 34 | GET | `/api/agent/files/raw/content` | legacy 独有 | R2 | 一致 |
| 35 | GET | `/api/agent/files/vault/content` | legacy 独有 | R2 | 一致 |
| 36 | POST | `/api/agent/process` | legacy 独有 | R2 | 一致 |
| 37 | POST | `/api/agent/save-note` | legacy 独有 | R1+R5 | **差异 L-05**（保留 403） |
| 38 | POST | `/api/agent/import-tasks` | legacy 独有 | R2 | 一致 |
| 39 | GET | `/api/prompts` | legacy 独有 | R2 | 一致 |
| 40 | GET | `/api/prompts/{p}/backup/latest` | legacy 独有 | R2 | 一致 |
| 41 | POST | `/api/prompts/{p}/restore-latest` | legacy 独有 | R2 | 一致 |
| 42 | GET | `/api/prompts/{p}` | legacy 独有 | R2 | 一致 |
| 43 | PUT | `/api/prompts/{p}` | legacy 独有 | R2 | 一致 |

> **覆盖保证**：本表 43 条 = `tests/fixtures/route_inventory.json` 中
> `legacy_active_routes` 的全部条目（静态清单，非运行时采样）。
> `tests/characterize/test_legacy_divergence_ledger.py` 机械校验这一点。
>
> **归属列说明**：Stage 2 / Stage 5 之后，原先"legacy 独有"的
> ``/api/dependencies``、discard ×3、``/api/config``、``/api/config/save``、
> ``/api/export``、``/`` 已迁到 **真 Blueprint**，两侧都能提供 ——
> 表中"归属"反映的是 **当前**（Stage 5 后）的状态。



---

## 5. 保全证据的机械保障

`tests/characterize/test_legacy_divergence_ledger.py` 提供以下断言：

1. **覆盖完整性** —— legacy 的 **每一条** 活跃路由都在台账里有条目
   （要么在"差异条目"，要么在"行为一致"清单）；
2. **条目与实测一致** —— 台账里的每个差异判定与
   `tests/fixtures/legacy_divergence.json` 的实测结果 **不矛盾**；
3. **测试引用非空** —— 每条差异条目都必须引用至少一个
   黄金快照用例名或差异探针用例名；
4. **探针可复现** —— 重新运行 `scripts/legacy_divergence_probe.py` 得到的
   计数与冻结产物一致（防止实现漂移而台账未更新）。

### 5.1 冻结基线的采集与可审计性

`tests/fixtures/legacy_baseline.json` 由 `scripts/_freeze_legacy_baseline.py`
从 **Git HEAD**（Stage 7 之前的 legacy 单体）取出源码、放进合成根、
逐条执行与实时探针 **完全相同** 的 40 条用例后冻结而成。基线含
**响应体 + 状态码 + 副作用摘要** 三项。

由于 legacy 单体在 Stage 7 之后已不存在于工作区，该基线是
**一次性冻结**的审计证据；重复运行冻结脚本会重新从 Git HEAD 采集，
结果必须一致（若不一致，说明 Git HEAD 变了，需重新裁决台账）。

### 5.2 静态路由清单的口径变更（Stage 7）

`scripts/route_inventory.py` 原先从 `server/backend_api.py` **AST 扫描**
活跃路由。Stage 7 之后 legacy 不再持有任何路由，扫描结果恒为空，
失去鉴别力。因此清单的 legacy 侧改为 **从冻结基线的用例路径反推**，
并新增 **工厂侧** 的真实路由覆盖断言：

* `legacy_active_routes` —— 冻结基线覆盖的 legacy 路由（40 条用例对应的
  路由去重集合）；
* `factory_route_count` —— Factory 真实 `url_map` 的路由数；
* `missing_in_factory` —— legacy 路由在 Factory 中缺失的集合（必须为空）。

---

## 6. 未决项

| 项 | 说明 | 归属 |
|---|---|---|
| `GET /api/health` 的响应形状是否与 legacy 统一 | legacy `{"status":"healthy"}` vs Factory `{"phase":1,"status":"ok"}` | P5（不属 P2） |
| legacy 换牌路径的历史缺陷是否需要 **数据修复** | legacy 曾把失败的换牌记成拒绝（`task_rejection_log` / `refusal_count` 虚增） | **需要单独评估**：是否对生产历史数据做一次性校正 —— **不属 P2**（P2 不触碰生产数据） |
