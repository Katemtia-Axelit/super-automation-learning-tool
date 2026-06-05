"""P0 HTTP 验收（需服务器已启动）

用法:
  python scripts/p0_acceptance_http.py
  python scripts/p0_acceptance_http.py --base http://127.0.0.1:5000
"""
import argparse
import json
import urllib.error
import urllib.request

TEST_PREFIX = '__TEST__'


def req(base, path, method='GET', body=None):
    url = base.rstrip('/') + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


def req_status(base, path, method='GET', body=None):
    url = base.rstrip('/') + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='ignore')
        try:
            j = json.loads(raw)
        except json.JSONDecodeError:
            j = {}
        return e.code, j


def cleanup_test_tasks(base):
    st, tasks = req_status(base, '/api/tasks?include_completed=true&unlocked_only=false')
    if st != 200 or not isinstance(tasks, list):
        return
    legacy_names = {TEST_PREFIX + 'P0_HTTP_A', TEST_PREFIX + 'P0_HTTP_B', 'P0_HTTP_A', 'P0_HTTP_B'}
    for t in tasks:
        name = t.get('name') or ''
        if name.startswith(TEST_PREFIX) or name in legacy_names:
            try:
                req_status(base, f'/api/tasks/{t["id"]}', 'DELETE')
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base
    created_ids = []

    try:
        cleanup_test_tasks(base)

        health = req(base, '/api/health')
        assert health.get('status') == 'healthy', health
        print('[PASS] /api/health')

        slots = req(base, '/api/schedule/slots')
        assert len(slots) > 0
        print('[PASS] /api/schedule/slots')

        weekly = req(base, '/api/schedule/weekly')
        assert isinstance(weekly, dict)
        print('[PASS] /api/schedule/weekly')

        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        slot_id = slots[0]['slot_id']
        req(base, '/api/schedule/daily', 'POST', {
            'date': today, 'slot_id': slot_id, 'activity': 'HTTP_TEST'
        })
        daily = req(base, '/api/schedule/daily?date=' + today)
        assert any(d.get('slot_id') == slot_id and d.get('activity') == 'HTTP_TEST' for d in daily)
        req(base, '/api/schedule/daily', 'POST', {'date': today, 'slot_id': slot_id, 'activity': ''})
        daily2 = req(base, '/api/schedule/daily?date=' + today)
        assert not any(d.get('slot_id') == slot_id and d.get('activity') for d in daily2)
        print('[PASS] schedule daily CRUD')

        a = req(base, '/api/tasks', 'POST', {'name': TEST_PREFIX + 'P0_HTTP_A', 'prerequisite_ids': []})
        id_a = a['id']
        created_ids.append(id_a)
        b = req(base, '/api/tasks', 'POST', {'name': TEST_PREFIX + 'P0_HTTP_B', 'prerequisite_ids': [id_a]})
        id_b = b['id']
        created_ids.append(id_b)
        tasks = req(base, '/api/tasks?unlocked_only=false')
        tb = next(t for t in tasks if t['id'] == id_b)
        assert not tb['is_unlocked']
        print('[PASS] B blocked when A incomplete')

        try:
            req(base, f'/api/tasks/{id_a}', 'PUT', {'prerequisite_ids': [id_b]})
            raise AssertionError('cycle should fail')
        except urllib.error.HTTPError as e:
            assert e.code == 400, e.code
        print('[PASS] cycle blocked')

        req(base, '/api/tasks/' + str(id_a) + '/complete', 'POST', {})
        tasks2 = req(base, '/api/tasks?unlocked_only=false')
        tb2 = next(t for t in tasks2 if t['id'] == id_b)
        assert tb2['is_unlocked']
        print('[PASS] B unlocked after A complete')

        draw = req(base, '/api/gacha/draw', 'POST', {'pool': 'fragment', 'energy': 'medium'})
        assert draw.get('task')
        print('[PASS] gacha draw')

        req(base, '/api/tasks/' + str(id_a), 'DELETE')
        created_ids.remove(id_a)
        deps = req(base, '/api/dependencies')
        assert isinstance(deps.get('nodes'), list)
        print('[PASS] delete + dependencies')

        html = urllib.request.urlopen(base + '/', timeout=10).read().decode('utf-8')
        assert html.count("const API") == 0, 'index should not inline const API'
        assert '/static/app.js' in html
        print('[PASS] index.html single script')

        print('\nALL HTTP ACCEPTANCE PASSED')
        return 0
    finally:
        for tid in reversed(created_ids):
            try:
                req_status(base, f'/api/tasks/{tid}', 'DELETE')
            except Exception:
                pass
        cleanup_test_tasks(base)


if __name__ == '__main__':
    raise SystemExit(main())