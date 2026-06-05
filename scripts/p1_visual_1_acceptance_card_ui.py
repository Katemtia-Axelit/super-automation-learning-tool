"""P1-Visual-1 任务卡牌牌感 HTTP 验收（主链路无回归）

用法:
  python scripts/p1_visual_1_acceptance_card_ui.py
"""
import argparse
import json
import urllib.error
import urllib.request

FAILURES = []
TEST_PREFIX = '__TEST__'
TEST_DRAW = TEST_PREFIX + 'P1_VIS_DRAW'
TEST_LIST = TEST_PREFIX + 'P1_VIS_LIST'


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
    st, active = req(base, '/api/timer/active')
    if st == 200 and active and active.get('id'):
        req(base, '/api/timer/complete', 'POST', {
            'session_id': active['id'], 'actual_minutes': 1,
            'result': 'abandoned', 'reason': 'cleanup',
        })
    st, tasks = req(base, '/api/tasks?include_completed=true&unlocked_only=false')
    if st == 200 and isinstance(tasks, list):
        for t in tasks:
            if (t.get('name') or '').startswith(TEST_PREFIX):
                req(base, f'/api/tasks/{t["id"]}', 'DELETE')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base
    draw_id = None
    list_id = None

    print('=== P1-Visual-1 Card UI HTTP Acceptance ===')

    try:
        st, h = req(base, '/api/health')
        if st != 200 or h.get('status') != 'healthy':
            fail('health', str(st))
            return 1
        ok('/api/health')

        cleanup(base)

        st, c1 = req(base, '/api/tasks', 'POST', {
            'name': TEST_DRAW, 'prerequisite_ids': [],
            'estimated_time': 10, 'priority': 3, 'tags': ['数学'],
        })
        if st not in (200, 201) or not c1.get('id'):
            fail('create draw task', str(c1))
            return 1
        draw_id = c1['id']
        ok(f'POST draw task id={draw_id}')

        st, c2 = req(base, '/api/tasks', 'POST', {
            'name': TEST_LIST, 'prerequisite_ids': [],
            'estimated_time': 15, 'priority': 2, 'tags': ['复习'],
        })
        if st not in (200, 201) or not c2.get('id'):
            fail('create list task', str(c2))
            return 1
        list_id = c2['id']
        ok(f'POST list task id={list_id}')

        st, drawn = req(base, '/api/gacha/draw', 'POST', {
            'pool': 'fragment', 'energy': 'medium', 'available_time': 30,
        })
        if st != 200 or not drawn.get('task'):
            fail('gacha/draw', str(drawn))
        else:
            ok('POST gacha/draw')

        st, done = req(base, f'/api/tasks/{list_id}/complete', 'POST', {})
        if st != 200:
            fail('complete task', str(done))
        else:
            ok('POST complete')

        st, fb = req(base, '/api/task-feedback', 'POST', {
            'task_id': draw_id,
            'event_type': 'skip_task',
            'planned_minutes': 10,
            'completion_status': 'skipped',
            'reason_category': 'state_issue',
            'reason_detail': '测试跳过',
        })
        if st not in (200, 201) or not fb.get('saved'):
            fail('task-feedback skip_task', str(fb))
        else:
            ok('POST task-feedback skip_task (P1-5B intact)')

        st, skipped = req(base, f'/api/tasks/{draw_id}/skip', 'POST', {})
        if st != 200:
            fail('skip task', str(skipped))
        else:
            ok('POST skip')

        st, c3 = req(base, '/api/tasks', 'POST', {
            'name': TEST_PREFIX + 'P1_VIS_REFUSE', 'prerequisite_ids': [],
            'estimated_time': 10,
        })
        refuse_id = c3.get('id') if st in (200, 201) else None
        if refuse_id:
            st, refused = req(base, f'/api/tasks/{refuse_id}/refuse', 'POST', {})
            if st != 200:
                fail('refuse task', str(refused))
            else:
                ok('POST refuse')
            req(base, f'/api/tasks/{refuse_id}', 'DELETE')

        st, c4 = req(base, '/api/tasks', 'POST', {
            'name': TEST_PREFIX + 'P1_VIS_DISCARD', 'prerequisite_ids': [],
            'estimated_time': 10,
        })
        discard_id = c4.get('id') if st in (200, 201) else None
        if discard_id:
            st, disc = req(base, f'/api/tasks/{discard_id}/move-to-discard', 'POST', {})
            if st != 200:
                fail('move-to-discard', str(disc))
            else:
                ok('POST move-to-discard')
            req(base, f'/api/discard-pile/{discard_id}/restore', 'POST', {})
            req(base, f'/api/tasks/{discard_id}', 'DELETE')

        st, events = req(base, f'/api/task-feedback?task_id={draw_id}')
        if st != 200 or not isinstance(events, list):
            fail('GET task-feedback', str(events))
        else:
            ok('GET task-feedback list')

    finally:
        cleanup(base)

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for name, detail in FAILURES:
            print(f'  {name}: {detail}')
        return 1

    print('\nALL P1-VISUAL-1 HTTP TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
