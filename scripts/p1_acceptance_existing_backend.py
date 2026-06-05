"""P1 已存在后端能力验收（需服务器已运行在 http://localhost:5000）

用法:
  python scripts/p1_acceptance_existing_backend.py
  python scripts/p1_acceptance_existing_backend.py --base http://127.0.0.1:5000
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

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
            j = {'raw': raw[:300]}
        return e.code, j


def check_health(base):
    st, d = req(base, '/api/health')
    if st != 200 or d.get('status') != 'healthy':
        fail('health', f'status={st} body={d}')
        return False
    ok('/api/health')
    return True


def check_timer(base):
    st, d = req(base, '/api/timer/active')
    if st != 200:
        fail('timer/active', f'status={st} {d}')
        return
    ok('GET /api/timer/active')

    st, task = req(base, '/api/tasks', 'POST', {'name': '__TEST__P1_TIMER', 'prerequisite_ids': []})
    if st not in (200, 201) or not task.get('id'):
        fail('timer/setup task', f'status={st} {task}')
        return
    tid = task['id']

    st, d = req(base, '/api/timer/start', 'POST', {'task_id': tid, 'planned_minutes': 25})
    if st != 200 or not d.get('session_id'):
        fail('timer/start', f'status={st} {d}')
    else:
        ok('POST /api/timer/start')
        sid = d['session_id']

        st2, d2 = req(base, '/api/timer/start', 'POST', {'task_id': tid, 'planned_minutes': 25})
        if st2 != 400:
            fail('timer/start duplicate', f'expected 400 got {st2} {d2}')
        else:
            ok('POST /api/timer/start duplicate -> 400')

        st3, d3 = req(base, '/api/timer/complete', 'POST', {
            'session_id': sid, 'actual_minutes': 20, 'result': 'completed', 'reason': 'p1_test'
        })
        if st3 != 200:
            fail('timer/complete', f'status={st3} {d3}')
        else:
            ok('POST /api/timer/complete')

    req(base, f'/api/tasks/{tid}', 'DELETE')


def check_assessment(base):
    st, d = req(base, '/api/state/questions')
    if st != 200 or not d.get('questions'):
        fail('state/questions', f'status={st} {d}')
    else:
        ok('GET /api/state/questions')

    answers = {
        'cognitive': 4, 'focus': 3, 'physical': 4,
        'alertness': 3, 'efficiency': 4, 'motivation': 3,
    }
    st, d = req(base, '/api/state/assessment', 'POST', {'answers': answers})
    if st != 200 or not d.get('completed'):
        fail('state/assessment POST', f'status={st} {d}')
    else:
        ok('POST /api/state/assessment')

    st, d = req(base, '/api/state/assessment')
    if st != 200:
        fail('state/assessment GET', f'status={st} {d}')
    else:
        ok('GET /api/state/assessment')

    st, d = req(base, '/api/state/assessment/history?days=7')
    if st != 200 or not isinstance(d, list):
        fail('state/assessment/history', f'status={st} {d}')
    else:
        ok('GET /api/state/assessment/history')


def check_sleep(base):
    st, d = req(base, '/api/state/sleep')
    if st != 200 or not isinstance(d, list):
        fail('state/sleep GET', f'status={st} {d}')
    else:
        ok('GET /api/state/sleep')

    st, d = req(base, '/api/state/sleep', 'POST', {'bed_time': '23:00', 'status': 'on_time'})
    if st != 200 or 'sleep_early_streak' not in d:
        fail('state/sleep POST', f'status={st} {d}')
    else:
        ok('POST /api/state/sleep')

    st, d = req(base, '/api/state/weekly-energy')
    if st != 200 or not isinstance(d, list):
        fail('state/weekly-energy', f'status={st} {d}')
    else:
        ok('GET /api/state/weekly-energy')


def check_prompts(base):
    st, files = req(base, '/api/prompts')
    if st != 200 or not isinstance(files, list) or not files:
        fail('prompts list', f'status={st} {files}')
        return
    ok('GET /api/prompts')

    name = files[0]['name']
    qname = urllib.parse.quote(name, safe='')
    st, orig = req(base, f'/api/prompts/{qname}')
    if st != 200 or 'content' not in orig:
        fail('prompts GET', f'status={st} {orig}')
        return
    ok(f'GET /api/prompts/{name}')

    marker = '\n<!-- P1_ROUNDTRIP_TEST -->\n'
    test_content = orig['content'] + marker
    st, saved = req(base, f'/api/prompts/{qname}', 'PUT', {'content': test_content})
    if st != 200:
        fail('prompts PUT', f'status={st} {saved}')
        return

    st, restored = req(base, f'/api/prompts/{qname}', 'PUT', {'content': orig['content']})
    if st != 200:
        fail('prompts PUT restore', f'status={st} {restored}')
        return
    ok('PUT /api/prompts roundtrip (restored)')


def check_knowledge_graph(base):
    st1, g1 = req(base, '/api/knowledge/graph')
    st2, g2 = req(base, '/api/knowledge/graph')
    if st1 != 200 or st2 != 200:
        fail('knowledge/graph', f'status1={st1} status2={st2}')
        return

    for key in ('nodes', 'links', 'categories'):
        if key not in g1:
            fail('knowledge/graph structure', f'missing {key}')
            return

    if g1.get('links') != g2.get('links'):
        fail('knowledge/graph stability', 'links differ between two requests')
        return

    for link in g1.get('links', [])[:5]:
        if 'source' not in link or 'target' not in link:
            fail('knowledge/graph link shape', str(link))
            return
        if link.get('type') not in ('wiki_link', 'markdown_link', None):
            fail('knowledge/graph link type', str(link))
            return

    ok(f'GET /api/knowledge/graph (nodes={len(g1["nodes"])}, links={len(g1["links"])}, stable)')


def check_agent_readonly(base):
    st, agents = req(base, '/api/agent/agents')
    if st != 200 or not isinstance(agents, list) or len(agents) < 1:
        fail('agent/agents', f'status={st} {agents}')
    else:
        ok(f'GET /api/agent/agents (count={len(agents)})')

    st, raw = req(base, '/api/agent/files/raw')
    if st != 200:
        fail('agent/files/raw', f'status={st} {raw}')
    else:
        ok('GET /api/agent/files/raw')

    st, vault = req(base, '/api/agent/files/vault')
    if st != 200:
        fail('agent/files/vault', f'status={st} {vault}')
    else:
        ok('GET /api/agent/files/vault')

    st, proc = req(base, '/api/agent/process', 'POST', {'agent': 'task_publisher', 'text': 'p1 probe'})
    if st == 500 and isinstance(proc, dict) and 'error' in proc:
        ok('POST /api/agent/process graceful fail without API key')
    elif st == 200:
        ok('POST /api/agent/process (API key configured)')
    else:
        fail('agent/process', f'status={st} {proc}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:5000')
    args = p.parse_args()
    base = args.base

    print('=== P1 Existing Backend Acceptance ===')
    if not check_health(base):
        print('\nABORT: server not healthy')
        return 1

    check_timer(base)
    check_assessment(base)
    check_sleep(base)
    check_prompts(base)
    check_knowledge_graph(base)
    check_agent_readonly(base)

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for name, detail in FAILURES:
            print(f'  - {name}: {detail}')
        return 1

    print('\nALL P1 EXISTING BACKEND TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
