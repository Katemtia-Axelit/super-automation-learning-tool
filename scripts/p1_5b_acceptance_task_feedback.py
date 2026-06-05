"""P1-5B 任务事件反馈 HTTP 验收

用法:
  python scripts/p1_5b_acceptance_task_feedback.py
"""
import argparse
import json
import urllib.error
import urllib.request

FAILURES = []
TEST_PREFIX = '__TEST__'
TEST_TASK = TEST_PREFIX + 'P1_5B_FEEDBACK'


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


def cleanup(base):
    st, tasks = req(base, '/api/tasks?include_completed=true&unlocked_only=false')
    if st == 200 and isinstance(tasks, list):
        for t in tasks:
            if (t.get('name') or '').startswith(TEST_PREFIX):
                req(base, f'/api/tasks/{t["id"]}', 'DELETE')
    st, active = req(base, '/api/timer/active')
    if st == 200 and active and active.get('id'):
        req(base, '/api/timer/complete', 'POST', {
            'session_id': active['id'], 'actual_minutes': 1,
            'result': 'abandoned', 'reason': 'cleanup',
        })


def post_feedback(base, payload):
    return req(base, '/api/task-feedback', 'POST', payload)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base
    task_id = None
    session_id = None

    print('=== P1-5B Task Feedback Acceptance ===')

    try:
        st, h = req(base, '/api/health')
        if st != 200 or h.get('status') != 'healthy':
            fail('health', str(st))
            return 1
        ok('/api/health')

        cleanup(base)

        st, created = req(base, '/api/tasks', 'POST', {
            'name': TEST_TASK, 'prerequisite_ids': [], 'estimated_time': 30,
        })
        if st not in (200, 201) or not created.get('id'):
            fail('create task', str(created))
            return 1
        task_id = created['id']
        ok(f'POST task id={task_id}')

        st, fb1 = post_feedback(base, {
            'task_id': task_id,
            'event_type': 'skip_task',
            'planned_minutes': 30,
            'completion_status': 'skipped',
            'reason_category': 'state_issue',
            'reason_detail': '现在没精力',
        })
        if st not in (200, 201) or not fb1.get('saved'):
            fail('skip_task feedback', str(fb1))
        else:
            ok('POST skip_task feedback')

        st, started = req(base, '/api/timer/start', 'POST', {
            'task_id': task_id, 'planned_minutes': 30,
        })
        if st != 200 or not started.get('session_id'):
            fail('timer/start', str(started))
            return 1
        session_id = started['session_id']
        ok('POST timer/start')

        st, done = req(base, '/api/timer/complete', 'POST', {
            'session_id': session_id,
            'actual_minutes': 5,
            'result': 'completed',
            'reason': 'completed',
        })
        if st != 200:
            fail('timer/complete', str(done))
            return 1
        session_id = None
        ok('POST timer/complete')

        st, fb2 = post_feedback(base, {
            'task_id': task_id,
            'event_type': 'finish_early',
            'planned_minutes': 30,
            'actual_minutes': 5,
            'completion_status': 'completed',
            'reason_category': 'time_estimation_issue',
            'reason_detail': '任务比预想简单',
        })
        if st not in (200, 201):
            fail('finish_early feedback', str(fb2))
        else:
            ok('POST finish_early feedback')

        st, fb3 = post_feedback(base, {
            'task_id': task_id,
            'event_type': 'timer_timeout_unfinished',
            'planned_minutes': 30,
            'actual_minutes': 25,
            'completion_status': 'unfinished',
            'reason_category': 'external_interrupt',
            'reason_detail': '中途被打断',
        })
        if st not in (200, 201):
            fail('unfinished feedback', str(fb3))
        else:
            ok('POST timer_timeout_unfinished feedback')

        st, fb4 = post_feedback(base, {
            'task_id': task_id,
            'event_type': 'abandon_task',
            'planned_minutes': 30,
            'completion_status': 'abandoned',
            'reason_category': 'priority_issue',
            'reason_detail': '不重要了',
        })
        if st not in (200, 201):
            fail('abandon feedback', str(fb4))
        else:
            ok('POST abandon_task feedback')

        st, rows = req(base, f'/api/task-feedback?task_id={task_id}')
        if st != 200 or not isinstance(rows, list) or len(rows) < 4:
            fail('GET task-feedback', f'count={len(rows) if isinstance(rows, list) else rows}')
        else:
            types = {r.get('event_type') for r in rows}
            needed = {'skip_task', 'finish_early', 'timer_timeout_unfinished', 'abandon_task'}
            if not needed.issubset(types):
                fail('feedback event types', str(types))
            else:
                ok(f'GET task-feedback (count={len(rows)})')

        st, bad = post_feedback(base, {
            'task_id': task_id,
            'event_type': 'invalid_type',
            'reason_category': 'other',
        })
        if st != 400:
            fail('invalid event_type', f'expected 400 got {st}')
        else:
            ok('invalid event_type -> 400')

    finally:
        if session_id:
            req(base, '/api/timer/complete', 'POST', {
                'session_id': session_id, 'actual_minutes': 1,
                'result': 'abandoned', 'reason': 'cleanup',
            })
        if task_id:
            req(base, f'/api/tasks/{task_id}', 'DELETE')
        cleanup(base)

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for n, d in FAILURES:
            print(f'  - {n}: {d}')
        return 1

    print('\nALL P1-5B TASK FEEDBACK TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
