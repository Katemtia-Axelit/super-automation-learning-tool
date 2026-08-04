"""P1-5 状态评估 + 计时器 HTTP 验收

用法:
  python scripts/p1_5_acceptance_state_timer.py
"""
import argparse
import json
import urllib.error
import urllib.request

FAILURES = []
TEST_PREFIX = '__TEST__'
TEST_TASK = TEST_PREFIX + 'P1_5_TIMER'


def fail(name, detail):
    FAILURES.append((name, detail))
    print(f'[FAIL] {name}: {detail}')


def ok(name):
    print(f'[PASS] {name}')


def req(base, path, method='GET', body=None):
    url = base.rstrip('/') + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='ignore')
        try:
            j = json.loads(raw)
        except json.JSONDecodeError:
            j = {'raw': raw[:200]}
        return e.code, j


def cleanup_test_tasks(base):
    st, tasks = req(base, '/api/tasks?include_completed=true&unlocked_only=false')
    if st != 200 or not isinstance(tasks, list):
        return
    for t in tasks:
        if (t.get('name') or '').startswith(TEST_PREFIX):
            req(base, f'/api/tasks/{t["id"]}', 'DELETE')


def cleanup_active_timer(base):
    st, active = req(base, '/api/timer/active')
    if st == 200 and active and active.get('id'):
        req(base, '/api/timer/complete', 'POST', {
            'session_id': active['id'],
            'actual_minutes': 1,
            'result': 'completed',
            'reason': 'p1_5_cleanup',
        })


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base
    task_id = None
    session_id = None

    print('=== P1-5 State Assessment + Timer Acceptance ===')

    try:
        st, h = req(base, '/api/health')
        if st != 200 or h.get('status') != 'healthy':
            fail('health', str(st))
            return 1
        ok('/api/health')

        cleanup_active_timer(base)
        cleanup_test_tasks(base)

        st, q = req(base, '/api/state/questions')
        if st != 200 or not q.get('questions'):
            fail('state/questions', str(q))
        else:
            ok('GET /api/state/questions')

        answers1 = {
            'cognitive': 4, 'focus': 3, 'physical': 4,
            'alertness': 3, 'efficiency': 4, 'motivation': 3,
        }
        st, saved = req(base, '/api/state/assessment', 'POST', {'answers': answers1})
        if st != 200 or not saved.get('completed'):
            fail('assessment POST first', str(saved))
        else:
            ok('POST /api/state/assessment (first save)')

        st, today = req(base, '/api/state/assessment')
        if st != 200 or not today.get('completed'):
            fail('assessment GET after save', str(today))
        elif today.get('energy_score') is None:
            fail('assessment scores missing', str(today))
        else:
            ok(f'GET /api/state/assessment (energy={today.get("energy_score")})')

        answers2 = dict(answers1)
        answers2['cognitive'] = 5
        answers2['efficiency'] = 5
        st, updated = req(base, '/api/state/assessment', 'POST', {'answers': answers2})
        if st != 200:
            fail('assessment POST update', str(updated))
        else:
            ok('POST /api/state/assessment (update)')

        st, today2 = req(base, '/api/state/assessment')
        if st != 200 or today2.get('energy_score') != updated.get('energy_score'):
            fail('assessment GET after update', f'{today2.get("energy_score")} vs {updated.get("energy_score")}')
        else:
            ok('GET confirms updated scores')

        st, hist = req(base, '/api/state/assessment/history?days=7')
        if st != 200 or not isinstance(hist, list):
            fail('assessment/history', str(hist))
        else:
            ok(f'GET /api/state/assessment/history (rows={len(hist)})')

        st, active0 = req(base, '/api/timer/active')
        if st != 200:
            fail('timer/active initial', str(active0))
        elif active0 and active0.get('id'):
            fail('timer/active should be idle', str(active0))
        else:
            ok('GET /api/timer/active (idle)')

        st, created = req(base, '/api/tasks', 'POST', {
            'name': TEST_TASK, 'prerequisite_ids': [], 'repeat_type': 'none',
        })
        if st not in (200, 201) or not created.get('id'):
            fail('create timer task', str(created))
            return 1
        task_id = created['id']
        ok(f'POST test task id={task_id}')

        st, started = req(base, '/api/timer/start', 'POST', {
            'task_id': task_id, 'planned_minutes': 15,
        })
        if st != 200 or not started.get('session_id'):
            fail('timer/start', str(started))
            return 1
        session_id = started['session_id']
        ok(f'POST /api/timer/start session={session_id}')

        st, active = req(base, '/api/timer/active')
        if st != 200 or not active or active.get('id') != session_id:
            fail('timer/active running', str(active))
        else:
            ok('GET /api/timer/active (running)')

        st, done = req(base, '/api/timer/complete', 'POST', {
            'session_id': session_id,
            'actual_minutes': 2,
            'result': 'completed',
            'reason': 'p1_5_test',
        })
        if st != 200 or not done.get('ended'):
            fail('timer/complete', str(done))
        else:
            ok('POST /api/timer/complete')

        st, active2 = req(base, '/api/timer/active')
        if st != 200:
            fail('timer/active after complete', str(st))
        elif active2 and active2.get('id'):
            fail('timer should be idle after complete', str(active2))
        else:
            ok('GET /api/timer/active (idle after stop)')

    finally:
        if session_id:
            req(base, '/api/timer/complete', 'POST', {
                'session_id': session_id,
                'actual_minutes': 1,
                'result': 'completed',
                'reason': 'cleanup',
            })
        cleanup_active_timer(base)
        if task_id:
            req(base, f'/api/tasks/{task_id}', 'DELETE')
        cleanup_test_tasks(base)

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for n, d in FAILURES:
            print(f'  - {n}: {d}')
        return 1

    print('\nALL P1-5 STATE + TIMER TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
