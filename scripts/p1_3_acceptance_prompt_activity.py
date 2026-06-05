"""P1-3 提示词可写 + 活动管理 HTTP 验收

用法:
  python scripts/p1_3_acceptance_prompt_activity.py
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

FAILURES = []
MARKER = '\n<!-- P1_3_ACCEPT_TEST -->\n'
TEST_ACTIVITY = 'P1_3_TEST_ACTIVITY_X'


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base

    print('=== P1-3 Prompt Write + Activity Acceptance ===')

    st, h = req(base, '/api/health')
    if st != 200 or h.get('status') != 'healthy':
        fail('health', str(st))
        return 1
    ok('/api/health')

    st, files = req(base, '/api/prompts')
    if st != 200 or not isinstance(files, list) or not files:
        fail('prompts list', str(st))
        return 1
    bad = [f for f in files if '.bak' in f.get('name', '') or f.get('name', '').startswith('.')]
    if bad:
        fail('prompts list no backup', str(bad))
    else:
        ok(f'GET /api/prompts (count={len(files)}, no backup files)')

    name = files[0]['name']
    qname = urllib.parse.quote(name, safe='')
    st, orig = req(base, f'/api/prompts/{qname}')
    if st != 200:
        fail('prompts GET', str(st))
        return 1
    original = orig.get('content', '')
    ok(f'GET /api/prompts/{name} (len={len(original)})')

    modified = original + MARKER
    st, saved = req(base, f'/api/prompts/{qname}', 'PUT', {'content': modified})
    if st != 200 or not saved.get('saved'):
        fail('prompts PUT', f'status={st} {saved}')
    else:
        ok(f'PUT /api/prompts/{name} (backup={saved.get("backup", "?")})')

    st, after = req(base, f'/api/prompts/{qname}')
    if st != 200 or MARKER.strip() not in after.get('content', ''):
        fail('prompts GET after PUT', 'marker missing')
    else:
        ok('GET after PUT confirms write')

    st, bak = req(base, f'/api/prompts/{qname}/backup/latest')
    if st != 200 or not bak.get('exists'):
        fail('backup/latest', str(bak))
    else:
        ok(f'backup/latest exists ({bak.get("backup_name")})')

    st, restored = req(base, f'/api/prompts/{qname}/restore-latest', 'POST', {})
    if st != 200 or not restored.get('restored'):
        fail('restore-latest', str(restored))
    else:
        ok('POST restore-latest')

    st, final = req(base, f'/api/prompts/{qname}')
    if st != 200 or final.get('content') != original:
        fail('content after restore', f'len={len(final.get("content",""))} vs orig={len(original)}')
    else:
        ok('GET after restore matches original')

    st, trav = req(base, '/api/prompts/' + urllib.parse.quote('../config.json', safe=''))
    if st != 400:
        fail('path traversal', f'expected 400 got {st}')
    else:
        ok('path traversal blocked')

    st, acts = req(base, '/api/schedule/activities')
    if st != 200 or not isinstance(acts, list):
        fail('activities GET', str(st))
    else:
        ok(f'GET /api/schedule/activities (count={len(acts)})')

    st, added = req(base, '/api/schedule/activities', 'POST', {
        'name': TEST_ACTIVITY, 'type': 'custom', 'duration_minutes': 30
    })
    if st != 200 or not added.get('id'):
        fail('activities POST', str(added))
    else:
        act_id = added['id']
        ok(f'POST activity id={act_id}')

    st, acts2 = req(base, '/api/schedule/activities')
    if not any(a.get('name') == TEST_ACTIVITY for a in acts2):
        fail('activities list contains new', str(acts2))
    else:
        ok('GET confirms activity exists')

    st, deleted = req(base, f'/api/schedule/activities/{act_id}', 'DELETE')
    if st != 200:
        fail('activities DELETE', str(deleted))
    else:
        ok('DELETE activity')

    st, acts3 = req(base, '/api/schedule/activities')
    if any(a.get('name') == TEST_ACTIVITY for a in acts3):
        fail('activity still exists', str(acts3))
    else:
        ok('GET confirms activity deleted')

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for n, d in FAILURES:
            print(f'  - {n}: {d}')
        return 1

    print('\nALL P1-3 PROMPT + ACTIVITY TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
