"""P0 任务依赖 + 日程表逻辑自测（使用临时 DB 副本）"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'server'))

SRC_DB = os.path.join(ROOT, 'data', 'task_publisher.db')
TMP = tempfile.mkdtemp(prefix='p0test_')
TEST_DB = os.path.join(TMP, 'test.db')
shutil.copy2(SRC_DB, TEST_DB)

import backend_api as api  # noqa: E402

api.DB_PATH = TEST_DB


def conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


def reset_tasks():
    c = conn()
    c.execute('DELETE FROM task_dependencies')
    c.execute('DELETE FROM task_tags')
    c.execute('DELETE FROM tasks')
    c.commit()
    c.close()


def make_task(**kwargs):
    defaults = dict(
        category='study', estimated_time=30, resistance='medium',
        energy_required='medium', priority=5, is_daily=False,
        repeat_type='none', task_profile='deadline_flexible',
        tags=[], prerequisite_ids=[]
    )
    defaults.update(kwargs)
    return api.Task(**defaults)


def test_dependencies():
    reset_tasks()
    c = conn()
    api.ensure_task_dependency_schema(c)
    c.close()

    id_a = api.add_task(make_task(name='TaskA'))
    id_b = api.add_task(make_task(name='TaskB', prerequisite_ids=[id_a]))
    b = api.get_task_by_id(id_b)
    assert not b.is_unlocked, 'B blocked when A incomplete'

    err = api.validate_prerequisites(conn(), [id_a], task_id=id_a)
    assert err, 'self dependency blocked'

    api.update_task(make_task(id=id_a, name='TaskA', prerequisite_ids=[id_b]))
    assert api.detect_cycle(conn(), id_a, [id_b]), 'cycle detected'

    api.update_task(make_task(id=id_a, name='TaskA', prerequisite_ids=[]))
    api._complete_task(id_a)
    assert api.get_task_by_id(id_b).is_unlocked, 'B unlocked after A complete'

    pool_ids = [t['id'] for t in api.get_available_tasks_for_gacha()]
    assert id_b in pool_ids, 'B in gacha when unlocked'

    reset_tasks()
    id_a2 = api.add_task(make_task(name='TaskA2'))
    id_b2 = api.add_task(make_task(name='TaskB2', prerequisite_ids=[id_a2]))
    pool_blocked = [t['id'] for t in api.get_available_tasks_for_gacha()]
    assert id_b2 not in pool_blocked, 'blocked task not in gacha pool'

    api.delete_task(id_a2)
    b3 = api.get_task_by_id(id_b2)
    assert b3 and (not b3.prerequisite_ids), 'deps cleaned after delete'
    print('[PASS] task dependency tests')


def test_schedule():
    c = conn()
    api.ensure_schedule_schema(c)
    c.close()

    today = datetime.now().strftime('%Y-%m-%d')
    slot = 'am1'
    activity = 'P0_TEST_MATH'

    c = conn()
    cur = c.cursor()
    cur.execute(
        'INSERT INTO daily_schedules (date, time_slot, activity, notes) VALUES (?,?,?,?)',
        (today, slot, activity, '')
    )
    c.commit()
    cur.execute('SELECT activity FROM daily_schedules WHERE date=? AND time_slot=?', (today, slot))
    assert cur.fetchone()['activity'] == activity
    cur.execute('UPDATE daily_schedules SET activity=? WHERE date=? AND time_slot=?', ('', today, slot))
    cur.execute('DELETE FROM daily_schedules WHERE date=? AND time_slot=? AND activity=""', (today, slot))
    c.commit()
    cur.execute('SELECT COUNT(*) AS c FROM daily_schedules WHERE date=? AND time_slot=?', (today, slot))
    assert cur.fetchone()['c'] == 0
    c.close()

    c = conn()
    cur = c.cursor()
    cur.execute(
        'INSERT INTO user_schedule (day_of_week, time_slot, activity, is_regular) VALUES (?,?,?,1)',
        (1, slot, 'WeeklyTest')
    )
    c.commit()
    cur.execute('SELECT activity FROM user_schedule WHERE day_of_week=1 AND time_slot=?', (slot,))
    assert cur.fetchone()['activity'] == 'WeeklyTest'
    c.close()
    print('[PASS] schedule table tests')


def main():
    if not os.path.exists(SRC_DB):
        print('ERROR: source DB not found:', SRC_DB)
        return 1
    test_dependencies()
    test_schedule()
    print('\nALL P0 TESTS PASSED')
    shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
