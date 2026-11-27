# AR03-P2 功能迁移映射（2026-11-21）

> **用途**：把 P2 迁移前的 **legacy 路由 / 兼容桥路由** 与 P2 迁移后的
> **Blueprint → Service → Repository** 承接位置逐条对应，给出
> **公开调用方式** 与 **测试证据**，并索引 Legacy 差异台账。
>
> **机读产物**：`tests/fixtures/p2_migration_map.json`
> （由 `scripts/_build_p2_migration_map.py` 从 **实时 Factory** 生成）
> **相关文档**：
> * 差异台账全文 → `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md`
> * 交付说明 → `docs/P2_BACKEND_MODULARIZATION_DELIVERY_20261121.md`
> * P3 交接 → `docs/deliverables/P2_HANDOFF.md`

---

## 0. 口径说明

| 口径 | 值 |
|---|---|
| legacy 活跃路由总数 | **43**（`tests/fixtures/legacy_route_surface.json`，从 Git HEAD 提取） |
| 迁移前 **兼容桥转发** 的路由 | **21** 条（`/`、`/api/config`×2、`/api/export`、`/api/dependencies`、discard×3、`/api/agent/*`×9、`/api/prompts/*`×5） |
| 迁移后 Factory 路由总数 | **81**（14 BP 的 80 条 + 1 条 app 级 `/api/health`） |
| 兼容桥挂载路由数 | **0** |
| legacy 路由在 Factory 中缺失数 | **0** |
| 差异探针用例 | **40**（32 一致 / 8 差异，全部已裁决） |

---

## 1. legacy 43 条活跃路由 → 新三层承接（逐条）

> 「公开调用方式」列给出 **前端/脚本应调用的 HTTP 契约** —— 迁移后
> **路径、方法、状态码、响应结构全部不变**，前端无需改动。

| # | 方法 | 路由 | Blueprint | Service | Repository | 公开调用方式 | 测试证据 | 台账 |
|---|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/tasks` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `GET /api/tasks?include_completed=&unlocked_only=` | `test_stage2_tasks_domain.py`、`test_http_characterization.py` | 一致 |
| 2 | GET | `/api/tasks/{id}` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `GET /api/tasks/{id}` → 200/404 | `test_stage2_tasks_domain.py` | 一致 |
| 3 | POST | `/api/tasks` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `POST /api/tasks` → 201/400 | `test_stage2_tasks_domain.py` | 一致 |
| 4 | PUT | `/api/tasks/{id}` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `PUT /api/tasks/{id}` → 200/404 | `test_stage2_tasks_domain.py` | 一致 |
| 5 | DELETE | `/api/tasks/{id}` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `DELETE /api/tasks/{id}` → 200/404 | `test_task_lifecycle_owner.py` | 一致 |
| 6 | GET | `/api/tasks/{id}/dependents` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `GET /api/tasks/{id}/dependents` | `test_stage2_tasks_domain.py` | 一致 |
| 7 | POST | `/api/tasks/{id}/complete` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `POST /api/tasks/{id}/complete` | `test_task_lifecycle_owner.py` | 一致 |
| 8 | POST | `/api/tasks/{id}/skip` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `POST /api/tasks/{id}/skip` | `test_task_skip_refuse_owner.py` | 一致 |
| 9 | POST | `/api/tasks/{id}/refuse` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `POST /api/tasks/{id}/refuse` | `test_task_skip_refuse_owner.py` | 一致 |
| 10 | GET | `/api/dependencies` | `tasks_bp` | `services.tasks` | `repositories.task_repo` | `GET /api/dependencies` | `test_stage2_tasks_domain.py` | 一致 |
| 11 | GET | `/api/tags` | `tags_bp` | `services.tags` | `repositories.tags_repo` | `GET /api/tags` | `test_stage2_tasks_domain.py` | 一致 |
| 12 | POST | `/api/tags` | `tags_bp` | `services.tags` | `repositories.tags_repo` | `POST /api/tags` → 201（新）/ 200（重名） | `test_stage2_tasks_domain.py` | 一致 |
| 13 | DELETE | `/api/tags/{id}` | `tags_bp` | `services.tags` | `repositories.tags_repo` | `DELETE /api/tags/{id}` → 200 | `test_stage2_tasks_domain.py` | 一致 |
| 14 | POST | `/api/tags/batch` | `tags_bp` | `services.tags` | `repositories.tags_repo` | `POST /api/tags/batch` → 400（缺参） | `test_stage2_tasks_domain.py` | 一致 |
| 15 | GET | `/api/gacha/pools` | `gacha_bp` | `services.gacha` | `repositories.gacha_repo` | `GET /api/gacha/pools` | `test_stage3_gacha_domain.py` | 一致 |
| 16 | GET | `/api/gacha/pools/detail` | `gacha_bp` | `services.gacha` | `repositories.gacha_repo` | `GET /api/gacha/pools/detail` | `test_stage3_gacha_domain.py` | 一致 |
| 17 | GET | `/api/gacha/statistics` | `gacha_bp` | `services.gacha` | `repositories.gacha_repo` | `GET /api/gacha/statistics` | `test_gacha_statistics_ledger.py` | 一致 |
| 18 | POST | `/api/gacha/draw` | `gacha_bp` | `services.gacha` | `repositories.gacha_repo` | `POST /api/gacha/draw` | `test_stage3_gacha_domain.py`、Golden 100250 | 一致 |
| 19 | POST | `/api/gacha/care-draw` | `gacha_bp` | `services.gacha` | `repositories.gacha_repo` | `POST /api/gacha/care-draw` | `test_free_card_gacha_contract.py` | 一致 |
| 20 | POST | `/api/gacha/replace` | `gacha_bp` | `services.gacha` | `repositories.gacha_repo` | `POST /api/gacha/replace`（**必须带 reason**） | `test_gacha_replace_no_repeat.py`、`test_gacha_policy_weights.py` | **L-02 / L-03 / L-07** |
| 21 | GET | `/api/discard-pile` | `discard_bp` | `services.discard` | `repositories.discard_repo` | `GET /api/discard-pile` | `test_discard_cycle_recovery.py` | **L-06** |
| 22 | POST | `/api/discard-pile/{id}/restore` | `discard_bp` | `services.discard` | `repositories.discard_repo` | `POST /api/discard-pile/{id}/restore` | `test_task_discard_restore_owner.py` | 一致 |
| 23 | POST | `/api/tasks/{id}/move-to-discard` | `discard_bp` | `services.discard` | `repositories.discard_repo` | `POST /api/tasks/{id}/move-to-discard` | `test_task_discard_restore_owner.py` | 一致 |
| 24 | GET | `/api/health` | **app 级**（`app_factory`） | — | — | `GET /api/health` → 200 `{"phase":1,"status":"ok"}` | `test_golden_http_snapshot.py` | **L-01** |
| 25 | GET | `/api/config` | `config_bp` | `services.config` | （文件路径来自 app 配置） | `GET /api/config` | `test_stage5_config_export.py` | 一致 |
| 26 | POST | `/api/config/save` | `config_bp` | `services.config` | （文件路径来自 app 配置） | `POST /api/config/save` | `test_stage5_config_export.py` | 一致 |
| 27 | GET | `/api/export` | `config_bp` | `services.export` | `repositories.export_repo` | `GET /api/export` | `test_stage5_config_export.py` | **L-04** |
| 28 | GET | `/` | `index_bp` | — | — | `GET /` → 200（静态页） | `test_legacy_route_full_parity.py` | 一致 |
| 29 | GET | `/api/agent/agents` | `agent_bp` | `services.agent` | — | `GET /api/agent/agents` | `test_stage6_prompts_agent.py` | 一致 |
| 30 | GET | `/api/agent/agents/{agent_id}/prompt` | `agent_bp` | `services.agent` | `repositories.vault_repo` | `GET /api/agent/agents/{agent_id}/prompt` | `test_stage6_prompts_agent.py` | 一致 |
| 31 | GET | `/api/agent/files/raw` | `agent_bp` | `services.agent` | `repositories.vault_repo` | `GET /api/agent/files/raw` | `test_stage6_prompts_agent.py` | 一致 |
| 32 | GET | `/api/agent/files/raw/content` | `agent_bp` | `services.agent` | `repositories.vault_repo` | `GET /api/agent/files/raw/content` | `test_stage6_prompts_agent.py` | 一致 |
| 33 | GET | `/api/agent/files/vault` | `agent_bp` | `services.agent` | `repositories.vault_repo` | `GET /api/agent/files/vault` | `test_stage6_prompts_agent.py` | 一致 |
| 34 | GET | `/api/agent/files/vault/content` | `agent_bp` | `services.agent` | `repositories.vault_repo` | `GET /api/agent/files/vault/content` | `test_stage6_prompts_agent.py` | 一致 |
| 35 | POST | `/api/agent/process` | `agent_bp` | `services.agent` + `services.ai` | `repositories.vault_repo` | `POST /api/agent/process` | `test_stage6_prompts_agent.py` | 一致 |
| 36 | POST | `/api/agent/save-note` | `agent_bp` | `services.agent::save_note_blocked` | — | `POST /api/agent/save-note` → **403**（AI 不得写 Obsidian） | `test_stage6_prompts_agent.py`、`test_http_characterization.py` | **L-05** |
| 37 | POST | `/api/agent/import-tasks` | `agent_bp` | `services.agent` | `repositories.task_repo` | `POST /api/agent/import-tasks` | `test_stage6_prompts_agent.py` | 一致 |
| 38 | GET | `/api/prompts` | `prompts_bp` | `services.prompts` | `repositories.prompt_repo` | `GET /api/prompts` | `test_stage6_prompts_agent.py` | 一致 |
| 39 | GET | `/api/prompts/{name}` | `prompts_bp` | `services.prompts` | `repositories.prompt_repo` | `GET /api/prompts/{name}` → 404（不存在） | `test_stage6_prompts_agent.py` | 一致 |
| 40 | PUT | `/api/prompts/{name}` | `prompts_bp` | `services.prompts` | `repositories.prompt_repo` | `PUT /api/prompts/{name}` | `test_stage6_prompts_agent.py` | 一致 |
| 41 | GET | `/api/prompts/{name}/backup/latest` | `prompts_bp` | `services.prompts` | `repositories.prompt_repo` | `GET /api/prompts/{name}/backup/latest` | `test_stage6_prompts_agent.py` | 一致 |
| 42 | POST | `/api/prompts/{name}/restore-latest` | `prompts_bp` | `services.prompts` | `repositories.prompt_repo` | `POST /api/prompts/{name}/restore-latest` | `test_stage6_prompts_agent.py` | 一致 |
| 43 | GET | `/api/agent-policy/status` | `agent_policy_bp` | `services.agent_policy` | — | `GET /api/agent-policy/status` → 200（纯只读） | `test_agent_policy_status.py` | **L-08** |

---

## 2. 兼容桥 21 条转发路由的收口对照

| 迁移前（兼容桥转发） | 迁移后承接 | 状态 |
|---|---|---|
| `GET /` | `index_bp`（app 级路由） | ✅ 原生 |
| `GET /api/config` | `config_bp` | ✅ 原生 |
| `POST /api/config/save` | `config_bp` | ✅ 原生 |
| `GET /api/export` | `config_bp` + `services.export` | ✅ 原生 |
| `GET /api/dependencies` | `tasks_bp`（依赖图归入任务域） | ✅ 原生 |
| `GET /api/discard-pile` | `discard_bp` | ✅ 原生 |
| `POST /api/discard-pile/{id}/restore` | `discard_bp` | ✅ 原生 |
| `POST /api/tasks/{id}/move-to-discard` | `discard_bp` | ✅ 原生 |
| `GET /api/agent/agents` | `agent_bp` | ✅ 原生 |
| `GET /api/agent/agents/{agent_id}/prompt` | `agent_bp` | ✅ 原生 |
| `GET /api/agent/files/raw` | `agent_bp` | ✅ 原生 |
| `GET /api/agent/files/raw/content` | `agent_bp` | ✅ 原生 |
| `GET /api/agent/files/vault` | `agent_bp` | ✅ 原生 |
| `GET /api/agent/files/vault/content` | `agent_bp` | ✅ 原生 |
| `POST /api/agent/process` | `agent_bp` | ✅ 原生 |
| `POST /api/agent/save-note` | `agent_bp`（403 **原生实现**，不再靠桥注入） | ✅ 原生 |
| `POST /api/agent/import-tasks` | `agent_bp` | ✅ 原生 |
| `GET /api/prompts` | `prompts_bp` | ✅ 原生 |
| `GET /api/prompts/{name}` | `prompts_bp` | ✅ 原生 |
| `PUT /api/prompts/{name}` | `prompts_bp` | ✅ 原生 |
| `GET /api/prompts/{name}/backup/latest` | `prompts_bp` | ✅ 原生 |
| `POST /api/prompts/{name}/restore-latest` | `prompts_bp` | ✅ 原生 |

> **注**：表中 22 行（`/api/agent/*` 实际 9 条 + `/api/prompts/*` 5 条 + 其余 8 条
> = 22）以 **兼容桥白名单** 的历史口径列出；权威路由总数以
> `tests/fixtures/legacy_route_surface.json` 的 **43** 条为准
> （其中 `/api/tasks/{id}/move-to-discard` 与 discard 路由同属弃牌域）。

---

## 3. 迁移后 **新增/继承** 的 Factory 专属路由（不属 legacy 43 条）

| 方法 | 路由 | Blueprint | Service | 说明 |
|---|---|---|---|---|
| GET | `/api/state/daily-tone` | `state_bp` | `services.state` | P1 继承 |
| POST | `/api/state/daily-tone` | `state_bp` | `services.state` | P1 继承 |
| POST | `/api/state/energy` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/state/sleep` | `state_bp` | `services.state` | P1 继承 |
| POST | `/api/state/sleep` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/state/weekly-energy` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/state/questions` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/state/assessment` | `state_bp` | `services.state` | P1 继承 |
| POST | `/api/state/assessment` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/state/assessment/history` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/state/assessment/correlate` | `state_bp` | `services.state` | P1 继承 |
| GET | `/api/timer/active` | `timer_bp` | `services.timer` | P1 继承 |
| POST | `/api/timer/start` | `timer_bp` | `services.timer` | P1 继承 |
| POST | `/api/timer/pause` | `timer_bp` | `services.timer` | P1 继承 |
| POST | `/api/timer/resume` | `timer_bp` | `services.timer` | P1 继承 |
| POST | `/api/timer/complete` | `timer_bp` | `services.timer` | P1 继承 |
| GET | `/api/schedule/daily` | `schedule_bp` | `services.schedule` | P1 继承 |
| POST | `/api/schedule/daily` | `schedule_bp` | `services.schedule` | P1 继承 |
| GET | `/api/schedule/weekly` | `schedule_bp` | `services.schedule` | P1 继承 |
| POST | `/api/schedule/weekly` | `schedule_bp` | `services.schedule` | P1 继承 |
| GET | `/api/schedule/slots` | `schedule_bp` | `services.schedule` | P1 继承 |
| GET | `/api/schedule/activities` | `schedule_bp` | `services.schedule` | P1 继承 |
| POST | `/api/schedule/activities` | `schedule_bp` | `services.schedule` | P1 继承 |
| DELETE | `/api/schedule/activities/{id}` | `schedule_bp` | `services.schedule` | P1 继承 |
| GET | `/api/knowledge/notes` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/categories` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/points` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/point-detail/{subject}/{point_name}` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/note/{note_path}` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/note-content/{note_path}` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/graph` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/knowledge/recent` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| POST | `/api/knowledge/open-in-obsidian` | `knowledge_bp` | `services.knowledge` | P1 继承 |
| GET | `/api/task-feedback` | `feedback_bp` | `services.feedback` | P1 继承 |
| POST | `/api/task-feedback` | `feedback_bp` | `services.feedback` | P1 继承 |
| POST | `/api/tasks/{id}/feedback` | `feedback_bp` | `services.feedback` | P1 继承 |
| POST | `/api/gacha/multi-draw` | `gacha_bp` | `services.gacha` | P1 继承（连抽） |
| GET | `/api/gacha/free-card/suggestion` | `gacha_bp` | `services.free_card_policy` | P1 继承 |
| GET | `/api/agent-policy/status` | `agent_policy_bp` | `services.agent_policy` | P1 新增（见 **L-08**） |
| （opt-in）| `free_task_bp` 路由集 | `free_task_bp` | `services.free_task_adapter` | **受保护预览**，需显式 opt-in，默认不注册 |

---

## 4. Legacy 差异台账索引

台账全文 → `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md`
机读产物 → `tests/fixtures/legacy_divergence.json`

| 台账号 | 路由 | 权威侧判定 | 迁移后保留形状 | 保全证据 |
|---|---|---|---|---|
| **L-01** | `GET /api/health` | R1 | Factory `{"phase":1,"status":"ok"}` | 黄金快照 `health` + 探针 `health` |
| **L-02** | `POST /api/gacha/replace`（缺 reason） | R1+R4 | Factory 400 `reason required` | 探针 `gacha_replace_missing` / `gacha_replace_no_reason` |
| **L-03** | `POST /api/gacha/replace`（副作用） | R1+R4 | Factory **零副作用** | 探针 `gacha_replace_with_reason`（比对 `gacha_records` / `task_rejection_log`） |
| **L-04** | `GET /api/export` | R1 | 表清单与结构与 Factory 一致 | 黄金快照 `export` + 探针 `export` |
| **L-05** | `POST /api/agent/save-note` | R1+R5 | Factory **403**（原生实现） | 探针 `agent_save_note`（403 + 零写入） |
| **L-06** | `GET /api/discard-pile` | R2 | 响应体一致 | 黄金快照 `discard_pile` + 探针 `discard_pile` |
| **L-07** | `POST /api/gacha/replace`（reason 校验） | R1+R4 | Factory 严格白名单 | 探针 `gacha_replace_no_reason` |
| **L-08** | `GET /api/agent-policy/status` | R1+R5 | Factory **200 只读** | 探针 `agent_policy_status` |

**32 条** 实测完全一致的路由见台账 §4。

---

## 5. 三层归属总览

| Blueprint | Service | Repository | 路由数 |
|---|---|---|---|
| `tasks_bp` | `services.tasks` | `repositories.task_repo` | 10 |
| `tags_bp` | `services.tags` | `repositories.tags_repo` | 4 |
| `discard_bp` | `services.discard` | `repositories.discard_repo` | 3 |
| `gacha_bp` | `services.gacha`、`services.tasks`、`services.free_card_policy`、`services.agent_policy` | `repositories.gacha_repo`、`repositories.db` | 8 |
| `state_bp` | `services.state` | `repositories.state_repo`、`repositories.db` | 11 |
| `timer_bp` | `services.timer` | `repositories.timer_repo`、`repositories.db` | 5 |
| `schedule_bp` | `services.schedule` | `repositories.schedule_repo`、`repositories.db` | 8 |
| `knowledge_bp` | `services.knowledge` | `repositories.note_index_repo` | 9 |
| `feedback_bp` | `services.feedback` | `repositories.feedback_repo`、`repositories.state_repo`、`repositories.task_repo`、`repositories.db` | 3 |
| `config_bp` | `services.config`、`services.export` | `repositories.export_repo`、`repositories.db` | 3 |
| `prompts_bp` | `services.prompts` | `repositories.prompt_repo` | 5 |
| `agent_bp` | `services.agent`、`services.ai` | `repositories.vault_repo`、`repositories.db` | 9 |
| `agent_policy_bp` | `services.agent_policy` | — | 1 |
| `index_bp` | — | — | 1 |
| （app 级） | — | — | 1（`/api/health`） |
| `free_task_bp`（opt-in） | `services.free_task_adapter`、`services.free_task_events` | `services.free_task*`（自管 `FreeTaskEventStore`） | 受保护预览 |

> **说明**：`state_bp` 与 `feedback_bp` 存在 **跨域读**（`state_assessments` JOIN
> `tasks` + `task_completion_feedback`），由 `state_repo.list_correlation_samples`
> 承担，属于 **只读跨域聚合**，不构成第二业务事实源。

---

## 6. 遗留兼容层（供 P3 / P5 参考）

| 项 | 现状 | 建议 |
|---|---|---|
| `server/backend_api.py` | 290 行薄别名，零路由零 SQL；保留公共符号再导出 | P5 归档 |
| `server/app/legacy_compat.py` | 退役墓碑（0 路由 / 0 import） | 带外物理删除 |
| `server/utils/energy_calc.py` / `task_blocked.py` / `wiki_link.py` | 转发壳 → 指向新 owner | P3/P5 逐步收敛 |
| `server/app/extensions.py` 的 `configure_sqlite` | 仍被 `backend_api.configure_sqlite` 再导出 | P5 清理 |
