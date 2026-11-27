"""M02-S03-G01-W05 合成测试：弃牌/自然周期恢复与手动恢复语义。

只使用 ``sandbox_env`` 的临时合成 SQLite，绝不触碰真实项目数据库。
分别验证 legacy（``server/backend_api.py``）与 factory（``run_app.py``）两条
真实启动路径，通过真实 HTTP 路由与真实启动时的周期恢复函数验证语义。
不做浏览器 E2E。
"""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sandbox_env import available_port, materialize, seed, server

MODES = ("legacy", "factory")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _db_path(root: Path) -> Path:
    return root / "data" / "synthetic.sqlite3"


def _iso(dt: datetime) -> str:
    """本地 naive datetime → ISO 字符串（与 backend_api 使用同一格式）。"""
    return dt.isoformat()


def _tomorrow_midnight() -> datetime:
    return (datetime.now() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _next_monday_after(date) -> datetime:
    days_ahead = 7 - date.weekday()  # Monday==0 ... Sunday==6
    boundary = date + timedelta(days=days_ahead)
    return datetime(boundary.year, boundary.month, boundary.day)


def _insert_task(db: Path, *, name: str, repeat_type: str, completed: int,
                 in_discard_pile: int, last_completed_at=None,
                 next_available_at=None, completed_count: int = 0) -> int:
    with closing(sqlite3.connect(db)) as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (name, repeat_type, completed, in_discard_pile,
                               last_completed_at, next_available_at,
                               completed_count, is_unlocked)
            VALUES (?,?,?,?,?,?,?,1)
            """,
            (name, repeat_type, completed, in_discard_pile,
             last_completed_at, next_available_at, completed_count),
        )
        conn.commit()
        return cur.lastrowid


def _fetch(db: Path, task_id: int):
    with closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None


def _post(base: str, path: str, data=None):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = Request(base + path, data=payload,
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=4) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"raw": body}


def _get(base: str, path: str):
    try:
        with urlopen(base + path, timeout=4) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _make_root(work: Path, port: int) -> Path:
    root = materialize(work / "runtime", port)
    seed(root)
    return root


# --------------------------------------------------------------------------- #
# 启动时周期恢复
# --------------------------------------------------------------------------- #
class StartupRecoveryTests(unittest.TestCase):
    def test_recurring_and_shield_recovery_on_startup(self):
        for mode in MODES:
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_dcr_rec_") as temp:
                port = available_port()
                root = _make_root(Path(temp), port)
                db = _db_path(root)
                now = datetime.now()
                today = now.date()

                # 昨天完成的 daily → 应该恢复（自然周期 = 今天 00:00 <= now）。
                daily_yesterday = _insert_task(
                    db, name="daily-yesterday", repeat_type="daily", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today - timedelta(days=1), datetime.min.time().replace(hour=12))),
                )
                # 今天完成的 daily → 不应恢复（自然周期 = 明天 00:00 > now）。
                daily_today = _insert_task(
                    db, name="daily-today", repeat_type="daily", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today, datetime.min.time().replace(hour=12))),
                    completed_count=3,
                )
                # 上一自然周完成、本周到期的 weekly → 应恢复。
                weekly_due = _insert_task(
                    db, name="weekly-due", repeat_type="weekly", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today - timedelta(days=8), datetime.min.time().replace(hour=9))),
                )
                # 本周刚完成的 weekly → 不应恢复。
                weekly_fresh = _insert_task(
                    db, name="weekly-fresh", repeat_type="weekly", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today, datetime.min.time().replace(hour=9))),
                )
                # daily 已完成但 next_available_at 在未来 → 不应提前恢复。
                daily_future_shield = _insert_task(
                    db, name="daily-future-shield", repeat_type="daily", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today - timedelta(days=1), datetime.min.time().replace(hour=12))),
                    next_available_at=_iso(datetime.now() + timedelta(days=3)),
                )
                # 已完成的单次任务 → 不恢复。
                one_off = _insert_task(
                    db, name="one-off", repeat_type="none", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today - timedelta(days=30), datetime.min.time().replace(hour=12))),
                )
                # 没有到期时间的手动弃牌（completed=0，无 next_available_at）→ 不自动恢复。
                manual_no_due = _insert_task(
                    db, name="manual-no-due", repeat_type="none", completed=0,
                    in_discard_pile=1,
                )
                # 临时屏蔽已过期 → 清除。
                shield_expired = _insert_task(
                    db, name="shield-expired", repeat_type="none", completed=0,
                    in_discard_pile=1,
                    next_available_at=_iso(datetime.now() - timedelta(hours=2)),
                )
                # 临时屏蔽未到期 → 保留。
                shield_future = _insert_task(
                    db, name="shield-future", repeat_type="none", completed=0,
                    in_discard_pile=1,
                    next_available_at=_iso(datetime.now() + timedelta(hours=6)),
                )

                with server(root, mode, port):
                    pass  # 启动即触发恢复；进程退出后读取最终 DB 状态

                r = _fetch(db, daily_yesterday)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (0, 0), mode)
                self.assertIsNone(r["next_available_at"], mode)

                r = _fetch(db, weekly_due)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (0, 0), mode)
                self.assertIsNone(r["next_available_at"], mode)

                # 今天完成的 daily 保持完成/弃牌，且完成计数与时间不变。
                r = _fetch(db, daily_today)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (1, 1), mode)
                self.assertEqual(r["completed_count"], 3, mode)

                r = _fetch(db, weekly_fresh)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (1, 1), mode)

                r = _fetch(db, daily_future_shield)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (1, 1), mode)
                self.assertIsNotNone(r["next_available_at"], mode)

                r = _fetch(db, one_off)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (1, 1), mode)

                r = _fetch(db, manual_no_due)
                self.assertEqual(r["in_discard_pile"], 1, mode)

                r = _fetch(db, shield_expired)
                self.assertEqual(r["in_discard_pile"], 0, mode)
                self.assertIsNone(r["next_available_at"], mode)

                r = _fetch(db, shield_future)
                self.assertEqual(r["in_discard_pile"], 1, mode)
                self.assertIsNotNone(r["next_available_at"], mode)

    def test_repeated_startup_is_idempotent(self):
        for mode in MODES:
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_dcr_idem_") as temp:
                port = available_port()
                root = _make_root(Path(temp), port)
                db = _db_path(root)
                now = datetime.now()
                today = now.date()

                daily_due = _insert_task(
                    db, name="idem-daily-due", repeat_type="daily", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today - timedelta(days=1), datetime.min.time().replace(hour=12))),
                    completed_count=4,
                )
                daily_today = _insert_task(
                    db, name="idem-daily-today", repeat_type="daily", completed=1,
                    in_discard_pile=1,
                    last_completed_at=_iso(datetime.combine(
                        today, datetime.min.time().replace(hour=12))),
                    completed_count=2,
                )

                for _ in range(2):
                    # 同一合成数据库重复启动必须幂等。sandbox 的 config.json
                    # 固化了 materialize 时分配的端口，故复用同一端口。
                    with server(root, mode, port):
                        pass

                r = _fetch(db, daily_due)
                self.assertEqual((r["completed"], r["in_discard_pile"]), (0, 0), mode)
                # 恢复流程绝不改写完成计数或完成时间。
                self.assertEqual(r["completed_count"], 4, mode)
                original = _iso(datetime.combine(
                    today - timedelta(days=1), datetime.min.time().replace(hour=12)))
                self.assertEqual(r["last_completed_at"], original, mode)

                r = _fetch(db, daily_today)
                self.assertEqual(r["completed_count"], 2, mode)
                self.assertEqual(r["completed"], 1, mode)


# --------------------------------------------------------------------------- #
# 手动恢复路由
# --------------------------------------------------------------------------- #
class ManualRestoreTests(unittest.TestCase):
    def test_restore_future_blocked_then_due_restores(self):
        for mode in MODES:
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_dcr_restore_") as temp:
                port = available_port()
                root = _make_root(Path(temp), port)
                db = _db_path(root)
                with server(root, mode, port) as base:
                    # 未来 next_available_at 的临时屏蔽 → 409 且零副作用。
                    shielded = _insert_task(
                        db, name="shield-future-restore", repeat_type="none",
                        completed=0, in_discard_pile=1,
                        next_available_at=_iso(datetime.now() + timedelta(hours=5)),
                    )
                    status, body = _post(base, f"/api/discard-pile/{shielded}/restore")
                    self.assertEqual(status, 409, (mode, body))
                    r = _fetch(db, shielded)
                    self.assertEqual(r["in_discard_pile"], 1, mode)
                    self.assertIsNotNone(r["next_available_at"], mode)

                    # 已完成 daily，今天完成（周期未到期）→ 409 且零副作用。
                    daily_today = _insert_task(
                        db, name="daily-today-restore", repeat_type="daily",
                        completed=1, in_discard_pile=1,
                        last_completed_at=datetime.now().isoformat(),
                        completed_count=1,
                    )
                    status, body = _post(base, f"/api/discard-pile/{daily_today}/restore")
                    self.assertEqual(status, 409, (mode, body))
                    r = _fetch(db, daily_today)
                    self.assertEqual(r["completed"], 1, mode)
                    self.assertEqual(r["in_discard_pile"], 1, mode)
                    self.assertEqual(r["completed_count"], 1, mode)

                    # 已完成 daily，昨天完成（周期已到期）→ 可恢复。
                    daily_due = _insert_task(
                        db, name="daily-due-restore", repeat_type="daily",
                        completed=1, in_discard_pile=1,
                        last_completed_at=_iso(datetime.combine(
                            datetime.now().date() - timedelta(days=1),
                            datetime.min.time().replace(hour=12))),
                        completed_count=7,
                    )
                    status, body = _post(base, f"/api/discard-pile/{daily_due}/restore")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, daily_due)
                    self.assertEqual((r["completed"], r["in_discard_pile"]), (0, 0), mode)
                    self.assertIsNone(r["next_available_at"], mode)
                    # 手动恢复绝不改完成计数或完成时间。
                    self.assertEqual(r["completed_count"], 7, mode)

                    # 已完成单次任务 → 不得通过手动恢复绕过完成状态。
                    one_off = _insert_task(
                        db, name="one-off-restore", repeat_type="none",
                        completed=1, in_discard_pile=1,
                        last_completed_at=_iso(datetime.now() - timedelta(days=40)),
                    )
                    status, body = _post(base, f"/api/discard-pile/{one_off}/restore")
                    self.assertEqual(status, 409, (mode, body))
                    r = _fetch(db, one_off)
                    self.assertEqual((r["completed"], r["in_discard_pile"]), (1, 1), mode)

                    # 未完成手动弃牌、next_available_at 已过期 → 恢复并清除过期值。
                    stale_shield = _insert_task(
                        db, name="stale-shield-restore", repeat_type="none",
                        completed=0, in_discard_pile=1,
                        next_available_at=_iso(datetime.now() - timedelta(hours=3)),
                    )
                    status, body = _post(base, f"/api/discard-pile/{stale_shield}/restore")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, stale_shield)
                    self.assertEqual(r["in_discard_pile"], 0, mode)
                    self.assertIsNone(r["next_available_at"], mode)

                    # 未完成手动弃牌、没有到期时间 → 可恢复且不影响完成指标。
                    plain_manual = _insert_task(
                        db, name="plain-manual-restore", repeat_type="none",
                        completed=0, in_discard_pile=1,
                        last_completed_at=None, completed_count=0,
                    )
                    status, body = _post(base, f"/api/discard-pile/{plain_manual}/restore")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, plain_manual)
                    self.assertEqual(r["in_discard_pile"], 0, mode)


# --------------------------------------------------------------------------- #
# move-to-discard 语义
# --------------------------------------------------------------------------- #
class MoveToDiscardTests(unittest.TestCase):
    def test_manual_discard_preserves_completion_fields(self):
        for mode in MODES:
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_dcr_manual_") as temp:
                port = available_port()
                root = _make_root(Path(temp), port)
                db = _db_path(root)
                with server(root, mode, port) as base:
                    preserved_ts = _iso(datetime.now() - timedelta(days=2))
                    task_id = _insert_task(
                        db, name="manual-preserve", repeat_type="daily",
                        completed=0, in_discard_pile=0,
                        last_completed_at=preserved_ts,
                        next_available_at=None,
                        completed_count=5,
                    )
                    status, body = _post(base, f"/api/tasks/{task_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, task_id)
                    self.assertEqual(r["in_discard_pile"], 1, mode)
                    # 手动弃牌绝不改动完成指标。
                    self.assertEqual(r["completed_count"], 5, mode)
                    self.assertEqual(r["last_completed_at"], preserved_ts, mode)
                    self.assertIsNone(r["next_available_at"], mode)

    def test_completion_accounting_is_single_and_natural_boundary(self):
        for mode in MODES:
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_dcr_complete_") as temp:
                port = available_port()
                root = _make_root(Path(temp), port)
                db = _db_path(root)
                with server(root, mode, port) as base:
                    daily_id = _insert_task(
                        db, name="complete-daily", repeat_type="daily",
                        completed=1, in_discard_pile=0,
                        last_completed_at=None, completed_count=0,
                    )
                    status, body = _post(base, f"/api/tasks/{daily_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, daily_id)
                    self.assertEqual(r["completed_count"], 1, mode)
                    self.assertEqual(r["in_discard_pile"], 1, mode)
                    self.assertIsNotNone(r["last_completed_at"], mode)
                    # daily 的自然 next_available_at == 本地明天 00:00。
                    expected_next = _tomorrow_midnight()
                    got_next = datetime.fromisoformat(r["next_available_at"])
                    self.assertEqual(got_next, expected_next, mode)

                    # 重复调用必须幂等：不重复计数/推周期。
                    status, body = _post(base, f"/api/tasks/{daily_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, daily_id)
                    self.assertEqual(r["completed_count"], 1, mode)
                    self.assertEqual(
                        datetime.fromisoformat(r["next_available_at"]), expected_next, mode
                    )

                    # weekly 任务：自然 next_available_at == 完成日之后的周一 00:00。
                    weekly_id = _insert_task(
                        db, name="complete-weekly", repeat_type="weekly",
                        completed=1, in_discard_pile=0,
                        last_completed_at=None, completed_count=2,
                    )
                    status, body = _post(base, f"/api/tasks/{weekly_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, weekly_id)
                    self.assertEqual(r["completed_count"], 3, mode)
                    expected_weekly = _next_monday_after(datetime.now().date())
                    self.assertEqual(
                        datetime.fromisoformat(r["next_available_at"]),
                        expected_weekly, mode,
                    )

                    # 非周期任务完成后不设置 next_available_at（不可自动恢复）。
                    one_off_id = _insert_task(
                        db, name="complete-one-off", repeat_type="none",
                        completed=1, in_discard_pile=0,
                        last_completed_at=None, completed_count=0,
                    )
                    status, body = _post(base, f"/api/tasks/{one_off_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, one_off_id)
                    self.assertEqual(r["completed_count"], 1, mode)
                    self.assertIsNone(r["next_available_at"], mode)

    def test_completion_preserves_later_existing_shield(self):
        """完成入弃牌堆不得提前缩短既有且晚于自然边界的临时屏蔽。"""
        for mode in MODES:
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_dcr_shield_") as temp:
                port = available_port()
                root = _make_root(Path(temp), port)
                db = _db_path(root)
                with server(root, mode, port) as base:
                    later_iso = _iso(datetime.now() + timedelta(days=3))
                    daily_id = _insert_task(
                        db, name="complete-daily-shielded", repeat_type="daily",
                        completed=1, in_discard_pile=0,
                        last_completed_at=None, next_available_at=later_iso,
                        completed_count=4,
                    )
                    status, body = _post(base, f"/api/tasks/{daily_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, daily_id)
                    self.assertEqual(r["completed_count"], 5, mode)
                    self.assertEqual(r["in_discard_pile"], 1, mode)
                    self.assertIsNotNone(r["last_completed_at"], mode)
                    # 更晚的既有屏蔽必须保留，绝不被自然日边界提前。
                    self.assertEqual(
                        datetime.fromisoformat(r["next_available_at"]),
                        datetime.fromisoformat(later_iso), mode,
                    )
                    self.assertGreater(
                        datetime.fromisoformat(r["next_available_at"]),
                        _tomorrow_midnight(), mode,
                    )

                    # 重复调用：未来时间不变，完成计数不再增加。
                    status, body = _post(base, f"/api/tasks/{daily_id}/move-to-discard")
                    self.assertEqual(status, 200, (mode, body))
                    r = _fetch(db, daily_id)
                    self.assertEqual(r["completed_count"], 5, mode)
                    self.assertEqual(
                        datetime.fromisoformat(r["next_available_at"]),
                        datetime.fromisoformat(later_iso), mode,
                    )


if __name__ == "__main__":
    unittest.main()
