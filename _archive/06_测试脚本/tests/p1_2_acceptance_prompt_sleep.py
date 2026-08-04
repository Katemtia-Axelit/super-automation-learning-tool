"""P1-2 提示词只读 + 睡眠追踪 HTTP 验收（需服务器已运行）

用法:
  python scripts/p1_2_acceptance_prompt_sleep.py
  python scripts/p1_2_acceptance_prompt_sleep.py --base http://127.0.0.1:5000
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

FAILURES = []


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
        with urllib.request.urlopen(r, timeout=20) as resp:
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

    print('=== P1-2 Prompt + Sleep Acceptance ===')

    st, h = req(base, '/api/health')
    if st != 200 or h.get('status') != 'healthy':
        fail('health', f'status={st}')
        return 1
    ok('/api/health')

    st, files = req(base, '/api/prompts')
    if st != 200 or not isinstance(files, list) or not files:
        fail('prompts list', f'status={st} count={len(files) if isinstance(files, list) else files}')
    else:
        ok(f'GET /api/prompts (count={len(files)})')
        name = files[0]['name']
        st2, body = req(base, '/api/prompts/' + urllib.parse.quote(name, safe=''))
        content_len = len(body.get('content', '')) if st2 == 200 else 0
        if st2 != 200 or 'content' not in body:
            fail('prompts GET', f'status={st2} file={name}')
        else:
            ok(f'GET /api/prompts/{name} (len={content_len}, no PUT)')

    st, sleep_rows = req(base, '/api/state/sleep')
    if st != 200 or not isinstance(sleep_rows, list):
        fail('sleep GET', f'status={st} {sleep_rows}')
    else:
        ok(f'GET /api/state/sleep (rows={len(sleep_rows)})')

    test_time = '22:30'
    st, saved = req(base, '/api/state/sleep', 'POST', {'bed_time': test_time, 'status': 'on_time'})
    if st != 200 or saved.get('bed_time') != test_time:
        fail('sleep POST', f'status={st} {saved}')
    else:
        ok(f'POST /api/state/sleep bed_time={test_time} streak={saved.get("sleep_early_streak")}')

    st, sleep_rows2 = req(base, '/api/state/sleep')
    today = datetime.now().strftime('%Y-%m-%d')
    row = next((r for r in sleep_rows2 if r.get('date') == today), None) if isinstance(sleep_rows2, list) else None
    if not row or row.get('bed_time') != test_time:
        fail('sleep GET after POST', f'today row={row}')
    else:
        ok('GET /api/state/sleep confirms today bed_time')

    st, energy = req(base, '/api/state/weekly-energy')
    if st != 200 or not isinstance(energy, list):
        fail('weekly-energy', f'status={st} {energy}')
    else:
        ok(f'GET /api/state/weekly-energy (rows={len(energy)})')

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for name, detail in FAILURES:
            print(f'  - {name}: {detail}')
        return 1

    print('\nALL P1-2 PROMPT + SLEEP TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
