"""P1-4 弃牌堆浏览/恢复 HTTP 验收

用法:
  python scripts/p1_4_acceptance_discard_pile.py
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

FAILURES = []
TEST_PREFIX = '__TEST__'
TEST_NAME = TEST_PREFIX + 'P1_4_DISCARD'


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
    """删除所有 __TEST__ 前缀任务。"""
    st, tasks = req(base, '/api/tasks?include_completed=true&unlocked_only=false')
    if st != 200 or not isinstance(tasks, list):
        return
    for t in tasks:
        name = t.get('name') or ''
        if name.startswith(TEST_PREFIX):
            req(base, f'/api/tasks/{t["id"]}', 'DELETE')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base
    task_id = None

    print('=== P1-4 Discard Pile Acceptance ===')

    try:
        st, h = req(base, '/api/health')
        if st != 200 or h.get('status') != 'healthy':
            fail('health', str(st))
            return 1
        ok('/api/health')

        cleanup_test_tasks(base)

        st, created = req(base, '/api/tasks', 'POST', {
            'name': TEST_NAME,
            'prerequisite_ids': [],
            'repeat_type': 'none',
            'tags': ['test-tag'],
        })
        if st not in (200, 201) or not created.get('id'):
            fail('create task', str(created))
            return 1
        task_id = created['id']
        ok(f'POST task id={task_id}')

        st, moved = req(base, f'/api/tasks/{task_id}/move-to-discard', 'POST', {})
        if st != 200:
            fail('move-to-discard', str(moved))
            return 1
        ok('POST move-to-discard')

        st, pile = req(base, '/api/discard-pile')
        if st != 200 or not isinstance(pile, list):
            fail('GET discard-pile', str(pile))
            return 1
        found = next((t for t in pile if t.get('id') == task_id), None)
        if not found:
            fail('discard-pile contains task', f'count={len(pile)}')
        else:
            ok(f'GET discard-pile contains task (count={len(pile)})')
            if found.get('name') != TEST_NAME:
                fail('discard name', found.get('name'))
            else:
                ok('discard task name matches')
            if found.get('in_discard_pile') not in (True, 1):
                fail('discard in_discard_pile flag', str(found.get('in_discard_pile')))
            else:
                ok('discard in_discard_pile=true')

        st, restored = req(base, f'/api/discard-pile/{task_id}/restore', 'POST', {})
        if st != 200 or not restored.get('restored'):
            fail('restore', str(restored))
            return 1
        ok('POST restore')

        st, pile2 = req(base, '/api/discard-pile')
        if any(t.get('id') == task_id for t in (pile2 if isinstance(pile2, list) else [])):
            fail('discard-pile after restore', 'task still in pile')
        else:
            ok('GET discard-pile task removed after restore')

        st, task = req(base, f'/api/tasks/{task_id}')
        if st != 200:
            fail('GET task after restore', str(st))
        elif task.get('in_discard_pile') not in (False, 0, None):
            fail('task in_discard_pile after restore', str(task.get('in_discard_pile')))
        else:
            ok('restored task in_discard_pile=false')

        st, bad = req(base, '/api/discard-pile/999999/restore', 'POST', {})
        if st != 404:
            fail('restore missing task', f'expected 404 got {st}')
        else:
            ok('restore missing task -> 404')

        st, dup = req(base, f'/api/discard-pile/{task_id}/restore', 'POST', {})
        if st != 400:
            fail('restore not in pile', f'expected 400 got {st}')
        else:
            ok('restore not in pile -> 400')

    finally:
        if task_id:
            req(base, f'/api/tasks/{task_id}', 'DELETE')
        cleanup_test_tasks(base)

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for n, d in FAILURES:
            print(f'  - {n}: {d}')
        return 1

    print('\nALL P1-4 DISCARD PILE TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
