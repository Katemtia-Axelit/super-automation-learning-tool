"""M02-S03-G02 W02: 统一抽卡行为事件写入（后端入口）刻画测试。

范围（LT_M02_S03_G02_BEHAVIOR-EVENT-INGEST-RECOVERY）：

  A. 事件类型合同
     - 10 个稳定事件类型全部注册；
     - 既有 5 个事件类型 + ``accept_task`` **逐字不变**。

  B. 正常追加与读取
     - 合法行为事件 → 201，写入 **既有** ``task_feedback_events`` 账本；
     - note 原文（``context`` 等）可读回；
     - GET ``/api/task-feedback`` 能读到新事件。

  C. 幂等
     - 同一 ``event_id`` + **相同** 内容 → 返回旧 id，**不新增行**；
     - 同一 ``event_id`` + **冲突** 内容 → 409，**不写入**。

  D. 非法输入
     - 缺 ``event_id`` / ``session_id`` / ``schema_version`` / ``source``，
       或 ``note`` 不是 JSON 对象 → 400 且 **零写入**；
     - ``task_id`` 非正整数 → 400 且零写入；
     - ``reason_category`` 不是 ``other`` → 400 且零写入。

  E. 旧反馈兼容
     - ``accept_task`` 严格合同不回退；
     - 旧类型反馈仍可正常写入。

  F. Factory / Legacy 真实启动路径
     - 用 ``tests/characterize/sandbox_env.py`` 的合成沙箱分别跑
       ``factory``（``run_app.py``）与 ``legacy``（``server/backend_api.py``），
       真实 HTTP 验证同一套行为。

本文件是 **纯合成** 测试：所有 SQLite 都建在 ``tempfile`` 临时目录内；
绝不触碰真实 ``data/task_publisher.db``(±wal/shm)、``config/config.json``、
``src/notes/**``；不启动真实 Web 服务（除 F 组用合成沙箱自起进程）。
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
for _extra in (str(_PROJECT_ROOT), str(_HERE)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from flask import Flask  # noqa: E402

from server.blueprints.feedback_bp import feedback_bp  # noqa: E402
from server.services import feedback as feedback_service  # noqa: E402

from sandbox_env import available_port, materialize, seed, server  # noqa: E402


#: 合同规定的 10 个统一抽卡行为事件类型。
EXPECTED_BEHAVIOR_EVENT_TYPES = (
    'card_drawn',
    'card_shown',
    'help_me_choose',
    'card_replaced',
    'task_started',
    'timer_started',
    'timer_ended',
    'task_ended',
    'card_discarded',
    'card_restored',
)

#: 既有事件类型（必须 **逐字不变**）。
LEGACY_EVENT_TYPES = (
    'skip_task',
    'finish_early',
    'finish_on_time',
    'timer_timeout_unfinished',
    'abandon_task',
    'accept_task',
)

#: 与真实 ``server/schema/feedback.py`` 逐字一致的合成 schema（只建本文件
#: 用到的表）。**不** 引入任何生产 DB。
_SYNTH_SCHEMA = """
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, category TEXT DEFAULT 'daily',
  task_type TEXT DEFAULT 'normal', description TEXT,
  estimated_time INTEGER DEFAULT 25, repeat_type TEXT DEFAULT 'none',
  priority INTEGER DEFAULT 5, tags TEXT, is_unlocked INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE task_feedback_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  planned_minutes INTEGER,
  actual_minutes INTEGER,
  completion_status TEXT,
  reason_category TEXT NOT NULL,
  reason_detail TEXT,
  note TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);
CREATE TABLE task_completion_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  energy_after INTEGER,
  mood_after TEXT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _note(
    event_id: str = "evt-1",
    session_id: str = "sess-1",
    source: str = "unified_gacha",
    schema_version: int = 1,
    **context,
) -> str:
    """构造一个合法的行为事件 note（JSON 对象字符串）。"""
    payload = {
        "schema_version": schema_version,
        "event_id": event_id,
        "session_id": session_id,
        "source": source,
    }
    if context:
        payload["context"] = context
    return json.dumps(payload, ensure_ascii=False)


def _behavior_payload(event_type: str = "card_drawn", **overrides):
    """一个合法的统一抽卡行为事件请求体。"""
    payload = {
        "task_id": 1,
        "event_type": event_type,
        "reason_category": "other",
        "note": _note(),
    }
    payload.update(overrides)
    return payload


def _accept_payload(**overrides):
    """一个合法的 ``accept_task`` 请求体（既有严格合同）。"""
    payload = {
        "task_id": 1,
        "event_type": "accept_task",
        "planned_minutes": 25,
        "completion_status": "accepted",
        "reason_category": "other",
        "reason_detail": "没有什么理由，我就是想。",
        "note": json.dumps(
            {"schema_version": 1, "session_id": 7, "activity": "看纪录片"},
            ensure_ascii=False,
        ),
    }
    payload.update(overrides)
    return payload


class _BehaviorHarness:
    """一次性的合成 app + 合成 DB（全部在临时目录内）。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.db_path = root / "synthetic.sqlite3"
        with closing(sqlite3.connect(self.db_path)) as db:
            db.executescript(_SYNTH_SCHEMA)
            db.execute(
                "INSERT INTO tasks (id, name, category, task_type, estimated_time) "
                "VALUES (1, 'synthetic-card', 'study', 'normal', 25)"
            )
            db.commit()
        self.app = Flask(__name__)
        self.app.config["_db_path"] = str(self.db_path)
        self.app.register_blueprint(feedback_bp)
        self.client = self.app.test_client()

    def post(self, payload):
        return self.client.post("/api/task-feedback", json=payload)

    def get(self, query: str = ""):
        return self.client.get("/api/task-feedback" + query)

    def events(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM task_feedback_events ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def event_count(self) -> int:
        return len(self.events())


# ===========================================================================
# A. 事件类型合同
# ===========================================================================


class BehaviorEventTypeContractTests(unittest.TestCase):
    """10 个新事件类型全部注册；既有类型逐字不变。"""

    def test_all_ten_behavior_event_types_are_registered(self):
        registered = feedback_service.UNIFIED_GACHA_BEHAVIOR_EVENT_TYPES
        for event_type in EXPECTED_BEHAVIOR_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                self.assertIn(event_type, registered)

    def test_behavior_event_types_are_exactly_the_ten_contract_types(self):
        self.assertEqual(
            set(feedback_service.UNIFIED_GACHA_BEHAVIOR_EVENT_TYPES),
            set(EXPECTED_BEHAVIOR_EVENT_TYPES),
        )

    def test_legacy_event_types_are_unchanged(self):
        for event_type in LEGACY_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                self.assertIn(
                    event_type, feedback_service.TASK_FEEDBACK_EVENT_TYPES
                )

    def test_behavior_event_types_do_not_shadow_legacy_types(self):
        self.assertEqual(
            set(feedback_service.UNIFIED_GACHA_BEHAVIOR_EVENT_TYPES)
            & set(LEGACY_EVENT_TYPES),
            set(),
        )

    def test_reason_category_other_is_reused_not_invented(self):
        """统一行为事件复用既有 'other' 类别，绝不新增类别。"""
        self.assertIn("other", feedback_service.TASK_FEEDBACK_REASON_CATEGORIES)
        self.assertEqual(
            feedback_service.UNIFIED_GACHA_REASON_CATEGORY, "other"
        )


# ===========================================================================
# B/C/D. 后端行为（合成 Flask app + 合成 SQLite）
# ===========================================================================


class BehaviorEventIngestTests(unittest.TestCase):
    """合法追加 / 幂等 / 冲突 / 非法输入 / 旧反馈兼容。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(
            prefix="lt_m02_behavior_", ignore_cleanup_errors=True
        )
        self.addCleanup(self._tmp.cleanup)
        self.harness = _BehaviorHarness(Path(self._tmp.name))

    # -- B. 正常追加与读取 --------------------------------------------
    def test_valid_behavior_event_is_appended_and_readable(self):
        response = self.harness.post(_behavior_payload("card_drawn"))
        self.assertEqual(response.status_code, 201, response.get_json())
        body = response.get_json()
        self.assertTrue(body["saved"])
        self.assertIsInstance(body["id"], int)

        rows = self.harness.events()
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual(row["event_type"], "card_drawn")
        self.assertEqual(row["task_id"], 1)
        self.assertEqual(row["reason_category"], "other")
        # note 原文可读回（服务端不得改写用户文本）
        self.assertEqual(
            json.loads(row["note"])["event_id"], "evt-1", row["note"]
        )

    def test_every_behavior_event_type_is_accepted(self):
        for index, event_type in enumerate(EXPECTED_BEHAVIOR_EVENT_TYPES):
            with self.subTest(event_type=event_type):
                payload = _behavior_payload(
                    event_type, note=_note(event_id=f"evt-{index}")
                )
                response = self.harness.post(payload)
                self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(self.harness.event_count(), 10)

    def test_note_context_is_preserved_verbatim(self):
        note = _note(event_id="ctx-1", source="unified_gacha",
                     card_pool="tomato", reason="用户自述", minutes=25)
        response = self.harness.post(_behavior_payload("card_shown", note=note))
        self.assertEqual(response.status_code, 201, response.get_json())
        stored = json.loads(self.harness.events()[0]["note"])
        self.assertEqual(stored["context"]["card_pool"], "tomato")
        self.assertEqual(stored["context"]["reason"], "用户自述")
        self.assertEqual(stored["context"]["minutes"], 25)
        self.assertEqual(stored["source"], "unified_gacha")

    def test_get_endpoint_returns_the_new_behavior_event(self):
        self.harness.post(_behavior_payload("timer_started"))
        response = self.harness.get("?task_id=1")
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["event_type"], "timer_started")
        # GET 结果里的 note 原文仍可解析
        self.assertEqual(
            json.loads(rows[0]["note"])["source"], "unified_gacha"
        )

    def test_get_without_task_id_filter_lists_behavior_events(self):
        self.harness.post(_behavior_payload("task_started"))
        response = self.harness.get()
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["event_type"], "task_started")

    # -- C. 幂等 --------------------------------------------------------
    def test_same_event_id_same_content_is_idempotent(self):
        payload = _behavior_payload("card_drawn")
        first = self.harness.post(payload)
        self.assertEqual(first.status_code, 201, first.get_json())

        second = self.harness.post(payload)
        self.assertEqual(second.status_code, 200, second.get_json())
        body = second.get_json()
        self.assertTrue(body["duplicate"])
        self.assertEqual(body["id"], first.get_json()["id"])

        self.assertEqual(self.harness.event_count(), 1)

    def test_idempotent_replay_survives_key_order_and_whitespace(self):
        """同一内容但 JSON 键序 / 空白不同 → 仍然幂等（比较的是解析后的内容）。"""
        note_a = json.dumps(
            {"schema_version": 1, "event_id": "ord-1", "session_id": "s",
             "source": "unified_gacha"},
            ensure_ascii=False,
        )
        note_b = json.dumps(
            {"source": "unified_gacha", "session_id": "s", "event_id": "ord-1",
             "schema_version": 1},
            ensure_ascii=False,
        )
        first = self.harness.post(
            _behavior_payload("card_drawn", note=note_a)
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        second = self.harness.post(
            _behavior_payload("card_drawn", note=note_b)
        )
        self.assertEqual(second.status_code, 200, second.get_json())
        self.assertTrue(second.get_json()["duplicate"])
        self.assertEqual(self.harness.event_count(), 1)

    def test_same_event_id_with_conflicting_content_is_409(self):
        first = self.harness.post(
            _behavior_payload("card_drawn", note=_note(event_id="conf-1"))
        )
        self.assertEqual(first.status_code, 201, first.get_json())

        conflicting = self.harness.post(
            _behavior_payload(
                "card_drawn",
                note=_note(event_id="conf-1", minutes=99),
            )
        )
        self.assertEqual(conflicting.status_code, 409, conflicting.get_json())
        self.assertIn("error", conflicting.get_json())
        # 冲突绝不写入新行
        self.assertEqual(self.harness.event_count(), 1)
        stored = json.loads(self.harness.events()[0]["note"])
        self.assertNotIn("context", stored)

    def test_same_event_id_with_different_event_type_is_409(self):
        first = self.harness.post(
            _behavior_payload("card_drawn", note=_note(event_id="cross-1"))
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        conflicting = self.harness.post(
            _behavior_payload("card_discarded", note=_note(event_id="cross-1"))
        )
        self.assertEqual(conflicting.status_code, 409, conflicting.get_json())
        self.assertEqual(self.harness.event_count(), 1)

    def test_same_event_id_with_different_minutes_is_409(self):
        """同 event_id 但分钟数不同 → 409（内容冲突，不是幂等）。"""
        first = self.harness.post(
            _behavior_payload("timer_ended", actual_minutes=25)
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        conflicting = self.harness.post(
            _behavior_payload("timer_ended", actual_minutes=30)
        )
        self.assertEqual(conflicting.status_code, 409, conflicting.get_json())
        self.assertEqual(self.harness.event_count(), 1)
        self.assertEqual(self.harness.events()[0]["actual_minutes"], 25)

    # -- D. 非法输入（400 + 零写入）-------------------------------------
    def _assert_rejected(self, payload, label):
        response = self.harness.post(payload)
        self.assertEqual(response.status_code, 400, f"{label}: {response.get_json()}")
        self.assertIn("error", response.get_json())
        self.assertEqual(self.harness.event_count(), 0, f"{label}: 不允许写入")

    def test_missing_event_id_is_rejected(self):
        note = json.dumps(
            {"schema_version": 1, "session_id": "s", "source": "unified_gacha"},
            ensure_ascii=False,
        )
        self._assert_rejected(
            _behavior_payload("card_drawn", note=note), "missing event_id"
        )

    def test_missing_session_id_is_rejected(self):
        note = json.dumps(
            {"schema_version": 1, "event_id": "e", "source": "unified_gacha"},
            ensure_ascii=False,
        )
        self._assert_rejected(
            _behavior_payload("card_drawn", note=note), "missing session_id"
        )

    def test_missing_schema_version_is_rejected(self):
        note = json.dumps(
            {"event_id": "e", "session_id": "s", "source": "unified_gacha"},
            ensure_ascii=False,
        )
        self._assert_rejected(
            _behavior_payload("card_drawn", note=note), "missing schema_version"
        )

    def test_wrong_schema_version_is_rejected(self):
        self._assert_rejected(
            _behavior_payload(
                "card_drawn", note=_note(schema_version=2)
            ),
            "schema_version=2",
        )

    def test_boolean_schema_version_is_rejected(self):
        note = json.dumps(
            {"schema_version": True, "event_id": "e", "session_id": "s",
             "source": "unified_gacha"},
            ensure_ascii=False,
        )
        self._assert_rejected(
            _behavior_payload("card_drawn", note=note), "schema_version=True"
        )

    def test_missing_or_wrong_source_is_rejected(self):
        note = json.dumps(
            {"schema_version": 1, "event_id": "e", "session_id": "s"},
            ensure_ascii=False,
        )
        self._assert_rejected(
            _behavior_payload("card_drawn", note=note), "missing source"
        )
        self._assert_rejected(
            _behavior_payload("card_drawn", note=_note(source="other_source")),
            "wrong source",
        )

    def test_blank_event_id_is_rejected(self):
        self._assert_rejected(
            _behavior_payload("card_drawn", note=_note(event_id="   ")),
            "blank event_id",
        )

    def test_non_object_note_is_rejected(self):
        for bad in ("[]", '"text"', "123", "null", "{not json", ""):
            with self.subTest(note=bad):
                self._assert_rejected(
                    _behavior_payload("card_drawn", note=bad), f"note={bad!r}"
                )

    def test_missing_note_is_rejected(self):
        payload = _behavior_payload("card_drawn")
        payload.pop("note")
        self._assert_rejected(payload, "missing note")

    def test_non_positive_task_id_is_rejected(self):
        for bad_task_id in (0, -1, "1", 1.5, True, None):
            with self.subTest(task_id=bad_task_id):
                self._assert_rejected(
                    _behavior_payload("card_drawn", task_id=bad_task_id),
                    f"task_id={bad_task_id!r}",
                )

    def test_missing_task_id_is_rejected(self):
        payload = _behavior_payload("card_drawn")
        payload.pop("task_id")
        self._assert_rejected(payload, "missing task_id")

    def test_non_other_reason_category_is_rejected(self):
        for category in ("state_issue", "external_interrupt", "not_a_category"):
            with self.subTest(reason_category=category):
                self._assert_rejected(
                    _behavior_payload("card_drawn", reason_category=category),
                    f"reason_category={category}",
                )

    def test_unknown_event_type_is_still_rejected(self):
        self._assert_rejected(
            _behavior_payload("totally_unknown_event"), "unknown event_type"
        )

    # -- E. 旧反馈兼容 --------------------------------------------------
    def test_accept_task_contract_did_not_regress(self):
        response = self.harness.post(_accept_payload())
        self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["event_type"], "accept_task")
        self.assertEqual(rows[0]["reason_category"], "other")
        self.assertEqual(rows[0]["planned_minutes"], 25)
        self.assertEqual(rows[0]["completion_status"], "accepted")

    def test_accept_task_still_rejects_bad_payload(self):
        response = self.harness.post(_accept_payload(planned_minutes=30))
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(self.harness.event_count(), 0)

    def test_legacy_event_types_still_write(self):
        for event_type in LEGACY_EVENT_TYPES:
            if event_type == "accept_task":
                continue
            with self.subTest(event_type=event_type):
                response = self.harness.post(
                    {
                        "task_id": 1,
                        "event_type": event_type,
                        "planned_minutes": 30,
                        "actual_minutes": 25,
                        "completion_status": "completed",
                        "reason_category": "state_issue",
                        "reason_detail": "随便",
                        "note": "原有 note 语义保持不变",
                    }
                )
                self.assertEqual(response.status_code, 201, response.get_json())
        rows = self.harness.events()
        self.assertEqual(len(rows), 5, rows)
        for row in rows:
            self.assertEqual(row["reason_category"], "state_issue", row)
            self.assertEqual(row["note"], "原有 note 语义保持不变", row)
            self.assertEqual(row["planned_minutes"], 30, row)

    def test_behavior_event_and_legacy_event_coexist(self):
        """行为事件与旧反馈写进 **同一个** 账本，互不干扰。"""
        self.harness.post(_behavior_payload("card_drawn"))
        self.harness.post(
            {
                "task_id": 1,
                "event_type": "skip_task",
                "reason_category": "other",
                "note": "legacy",
            }
        )
        rows = self.harness.events()
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual(
            [r["event_type"] for r in rows], ["card_drawn", "skip_task"]
        )

    # -- 隔离性 ---------------------------------------------------------
    def test_nothing_was_written_outside_the_temp_root(self):
        self.harness.post(_behavior_payload("card_drawn"))
        db_files = sorted(p.name for p in Path(self._tmp.name).iterdir())
        self.assertEqual(db_files, ["synthetic.sqlite3"], db_files)


# ===========================================================================
# F. Factory / Legacy 真实启动路径
# ===========================================================================


def _http_json(base, path, data=None):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = Request(
        base + path, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw}


class BehaviorEventRealServerTests(unittest.TestCase):
    """Factory（run_app.py）与 legacy（server/backend_api.py）两条真实路径。"""

    MODES = ("factory", "legacy")

    def _seed_task(self, root: Path) -> Path:
        db_path = root / "data" / "synthetic.sqlite3"
        with closing(sqlite3.connect(db_path)) as db:
            db.execute("DELETE FROM tasks")
            db.execute("DELETE FROM task_dependencies")
            db.execute("DELETE FROM task_tags")
            db.execute(
                "INSERT INTO tasks (id, name, category, priority, completed, "
                "prerequisite_ids, is_unlocked, in_discard_pile) "
                "VALUES (1, 'synthetic-behavior-card', 'daily', 5, 0, '[]', 1, 0)"
            )
            db.commit()
        return db_path

    def test_behavior_event_flow_on_real_servers(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory(
                    prefix=f"lt_m02_behavior_{mode}_"
                ) as temp:
                    port = available_port()
                    root = materialize(Path(temp) / "runtime", port)
                    seed(root)
                    db_path = self._seed_task(root)
                    with server(root, mode, port) as base:
                        # 1) 正常追加
                        status, body = _http_json(
                            base,
                            "/api/task-feedback",
                            _behavior_payload("card_drawn"),
                        )
                        self.assertEqual(status, 201, body)
                        first_id = body["id"]

                        # 2) 重复幂等
                        status, body = _http_json(
                            base,
                            "/api/task-feedback",
                            _behavior_payload("card_drawn"),
                        )
                        self.assertEqual(status, 200, body)
                        self.assertTrue(body["duplicate"])
                        self.assertEqual(body["id"], first_id)

                        # 3) 冲突 409
                        status, body = _http_json(
                            base,
                            "/api/task-feedback",
                            _behavior_payload(
                                "card_drawn", note=_note(event_id="evt-1", minutes=99)
                            ),
                        )
                        self.assertEqual(status, 409, body)

                        # 4) 非法输入 400
                        status, body = _http_json(
                            base,
                            "/api/task-feedback",
                            _behavior_payload("card_drawn", task_id=0),
                        )
                        self.assertEqual(status, 400, body)

                        # 5) 旧反馈仍然可用
                        status, body = _http_json(
                            base, "/api/task-feedback", _accept_payload()
                        )
                        self.assertEqual(status, 201, body)

                    # 账本里：1 行行为事件 + 1 行 accept_task
                    with closing(sqlite3.connect(db_path)) as db:
                        db.row_factory = sqlite3.Row
                        rows = db.execute(
                            "SELECT * FROM task_feedback_events ORDER BY id"
                        ).fetchall()
                    self.assertEqual(len(rows), 2, [dict(r) for r in rows])
                    self.assertEqual(rows[0]["event_type"], "card_drawn")
                    self.assertEqual(rows[1]["event_type"], "accept_task")
                    self.assertEqual(
                        json.loads(rows[0]["note"])["source"], "unified_gacha"
                    )

    def test_get_endpoint_on_real_servers(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory(
                    prefix=f"lt_m02_behavior_get_{mode}_"
                ) as temp:
                    port = available_port()
                    root = materialize(Path(temp) / "runtime", port)
                    seed(root)
                    self._seed_task(root)
                    with server(root, mode, port) as base:
                        status, body = _http_json(
                            base,
                            "/api/task-feedback",
                            _behavior_payload("timer_ended"),
                        )
                        self.assertEqual(status, 201, body)

                        status, rows = _http_json(
                            base, "/api/task-feedback?task_id=1"
                        )
                        self.assertEqual(status, 200, rows)
                        self.assertEqual(len(rows), 1, rows)
                        self.assertEqual(rows[0]["event_type"], "timer_ended")
                        self.assertEqual(
                            json.loads(rows[0]["note"])["event_id"], "evt-1"
                        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
