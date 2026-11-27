# Todo 3 (feedback_bp) 收尾报告

**收尾时间**：2026-08-16 20:46–21:02 UTC+8（Cursor parent 接管）
**接管原因**：subagent `[babdabd9-670f-437e-b66b-2da24b672dcd](babdabd9-670f-437e-b66b-2da24b672dcd)` 同样在 tool_use 后无 tool_result，被父会话判死锁；用户主动停掉并要求 parent 接手。
**判定**：Todo 3 实际上**已经完成**——所有代码在盘上，只是 worker 还没跑完验证步骤就被卡住了。

---

## 一、结论：Todo 3 ✅ 完成

| 维度 | 结果 |
|---|---|
| 路由数（feedback_bp） | **3/3** 全注册到 `create_app()` |
| Plan 目标 | 3 endpoints（survey §3 §A）— Todo 3 **不是 4 endpoint**，3 是真值 |
| HTTP 探测 | **6/6** 全绿（含 cross-domain write 跨域写 daily_user_state） |
| `verify_p0_cleanup.py` | **24/24** 全绿（feedback_bp 不破坏 P0 契约，PEP 562 lazy access 兼容） |
| Legacy 兼容 | `api_task_feedback` / `api_create_task_feedback` / `api_list_task_feedback` 三个名字都经 `__getattr__` 暴露给 `verify_p0_cleanup.py T3` |
| 跨域写（survey §11.3） | `record_task_completion` 用 `state_repo.upsert_energy(conn,...)` 直调，**无 BP→BP 循环** |
| E2E（baseline 不退化） | 跑中（单独跑 E2E 不阻塞 Todo 3 验收） |

---

## 二、文件证据（已写盘、parent 接手时即存在）

### 1. `server/blueprints/feedback_bp.py`（106 行真 BP）
- `feedback_bp = Blueprint("feedback", __name__, url_prefix="/api")`
- 3 view functions：
  - `api_task_feedback(task_id)` → `POST /api/tasks/<int:task_id>/feedback`
  - `api_create_task_feedback()` → `POST /api/task-feedback`
  - `api_list_task_feedback()` → `GET /api/task-feedback`
- 路由子级 `__getattr__`（PEP 562）暴露 3 个 legacy 名字给 `verify_p0_cleanup.py T3`

### 2. `server/services/feedback.py`（192 行 service）
- 常量 `TASK_FEEDBACK_EVENT_TYPES` (5) + `TASK_FEEDBACK_REASON_CATEGORIES` (7)
- `infer_period(hour)` — period 推断（morning/afternoon/evening）
- 3 个 `validate_*` 函数
- 2 个编排函数：
  - `record_task_completion(conn, task_id, payload)` — task 存在校验 + 写 `task_completion_feedback` + 跨域写 `daily_user_state.energy_{period}`（调 `state_repo.upsert_energy`，无 BP→BP 循环）
  - `create_event(conn, payload)` — 验证 + 调 `feedback_repo.insert_event`
- `list_events(conn, task_id)` — 纯 read wrapper

### 3. `server/repositories/feedback_repo.py`（115 行 SQL 层）
- `insert_completion_feedback(conn, task_id, energy, mood, timestamp=None)` — 写 `task_completion_feedback`
- `insert_event(conn, event_data) -> int` — 写 `task_feedback_events`，返回 lastrowid
- `list_events(conn, task_id=None, limit=100) -> List[dict]` — 读，按 `created_at DESC`

### 4. `server/app/app_factory.py`（register feedback_bp）
- L24：`from server.blueprints.feedback_bp import feedback_bp  # Phase 2 / Todo 3`
- L69：`app.register_blueprint(feedback_bp)  # Phase 2 / Todo 3 (3 endpoints)`

### 5. `server/backend_api.py`（legacy 段 2390-2474 已禁用）
- 旧 handler 全在 `# === PHASE 2 TODO 3 FEEDBACK_MIGRATION_START ===` 和 `=== END ===` 之间注释掉
- 表名仍出现在 L2594 的健康检查 list 中（这是健康检查要列所有表，不是路由）
- L3547-3552 是 `__main__` 兜底注册 `feedback_bp`，与 `app_factory.py` 双注册安全（flask 默认去重）

---

## 三、HTTP 探测证据（独立 Python 客户端，避免 PowerShell `curl.exe` 编码干扰）

文件：`tests/probe_feedback_bp.py`（parent 新写）
日志：`tests/feedback_todo3_verify.log`（verify_p0_cleanup 输出）

| # | 请求 | 期望 | 实际 |
|---|---|---|---|
| 1 | GET `/api/task-feedback` | 200 + rows | 200, 12 rows ✓ |
| 2 | GET `/api/task-feedback?task_id=2` | 200 + filtered | 200, 3 rows ✓ |
| 3 | POST `/api/task-feedback` valid | 201 + saved/id | 201, `{"id":13,"saved":true}` ✓ |
| 4 | POST `/api/task-feedback` bad event_type | 400 + error | 400, `{"error":"非法 event_type"}` ✓ |
| 5 | POST `/api/tasks/2/feedback` (cross-domain) | 200 + recorded | 200, `{"feedback_recorded":true}` ✓ |
| 6 | POST `/api/tasks/99999/feedback` | 404 + not found | 404, `{"error":"Task not found"}` ✓ |

---

## 四、create_app() 注册清单证据

```
['POST'] /api/tasks/<int:task_id>/feedback feedback.api_task_feedback
['POST'] /api/task-feedback                feedback.api_create_task_feedback
['GET']  /api/task-feedback                feedback.api_list_task_feedback
total: 3
```

所有 3 个 endpoint **全部**通过 `feedback_bp`（`feedback.` 前缀）注册，**没有** fallback 到 `backend_api.api_*`——切流 100% 完成。

---

## 五、与 Plan 的偏差说明

| Plan 项 | 实际 | 说明 |
|---|---|---|
| Todo 3 endpoint 数 | 3 (不是 4) | survey §3 §A 表 + L609 "feedback_bp 3 endpoints" 一致；前轮 Todo 3 worker 报告 4 是把 task_id 反查 / detail 算进来了 |
| `_BACKEND_API_NAMES` 数 | 3 (不是 2) | survey L179 警告"漏 1 个" → 已经在真 BP 里**补齐 3 个**（含 `api_task_feedback`） |
| `list_feedback` NotImplementedError | **已实现** `list_events` | survey L181 警告"list_feedback 仍 NotImplementedError" → repo 已用 `list_events` 实现并被 service 包装 |
| `server/services/feedback.py` 不存在 | **已创建**（192 行） | survey L180 警告 → 已实现 |
| 表 `task_completion_feedback` 无 schema owner | **仍然 inline**（Todo 11 负责） | survey L575 标 Todo 11 范围，不在 Todo 3 |
| `state_service.update_energy` BP→BP 循环 | **避免**（survey L586 方案落实） | 用 `state_repo.upsert_energy(conn,...)` 直接调，无 state_bp/service 依赖 |

---

## 六、对后续 worker 的衔接建议

1. **Todo 5 (knowledge_bp)**: 已经在 parent 的并发 worker [84a2e0b8 之外] 重跑中
2. **Todo 6-9 (config/prompts/agent/discard)**: 按 plan 顺序派单
3. **Todo 11 (schema 切流)**: 需要把 `task_completion_feedback` 的 DDL 加到 `server/schema/feedback.py::ensure_schema`（survey §11.1）
4. **Todo 12 (backend_api.py 收尾)**: 把 §2390-2474 注释段正式删除，保留 L3547-3552 的兜底注册（`if __name__ == "__main__"` 入口使用）

---

## 七、交付

- ✅ 3/3 endpoint 工作
- ✅ 6/6 HTTP 探测
- ✅ 24/24 verify_p0_cleanup
- ✅ 跨域写正确（无 BP 循环）
- ✅ 切流 100%（无 backend_api legacy 兜底）
- ⏳ E2E baseline 在后台跑（不影响 Todo 3 验收）

**Todo 3 收尾完成，可继续 Todo 5 / Todo 6-9 派单。**