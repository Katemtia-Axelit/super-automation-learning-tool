"""P1-0 API probe for removed/legacy features (read-only except roundtrip tests)."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:5000'


def req(path, method='GET', body=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='ignore')
        try:
            j = json.loads(raw)
        except json.JSONDecodeError:
            j = {'raw': raw[:200]}
        return e.code, j


def main():
    print('=== P1-0 API Probe ===')

    st, d = req('/api/timer/active')
    print(f'timer/active: {st} -> {d}')

    st, task = req('/api/tasks', 'POST', {'name': 'P1_TIMER_PROBE', 'prerequisite_ids': []})
    tid = task.get('id') if st in (200, 201) else None
    if tid:
        st, d = req('/api/timer/start', 'POST', {'task_id': tid, 'planned_minutes': 25})
        print(f'timer/start: {st} -> {d}')
        sid = d.get('session_id') if st == 200 else None
        if sid:
            st, d = req('/api/timer/complete', 'POST', {
                'session_id': sid, 'actual_minutes': 20, 'result': 'completed', 'reason': 'test'
            })
            print(f'timer/complete: {st} -> {d}')
        req(f'/api/tasks/{tid}', 'DELETE')

    st, d = req('/api/state/questions')
    nq = len(d.get('questions', [])) if st == 200 else 0
    print(f'state/questions: {st} questions={nq}')

    st, d = req('/api/state/assessment')
    print(f'state/assessment GET: {st} completed={d.get("completed") if st == 200 else d}')

    st, d = req('/api/state/assessment', 'POST', {
        'answers': {'cognitive': 4, 'focus': 3, 'physical': 4, 'alertness': 3, 'efficiency': 4, 'motivation': 3}
    })
    print(f'state/assessment POST: {st} tone={d.get("daily_tone") if st == 200 else d}')

    st, d = req('/api/state/assessment/history?days=7')
    print(f'state/assessment/history: {st} rows={len(d) if isinstance(d, list) else d}')

    st, d = req('/api/state/sleep')
    print(f'state/sleep GET: {st} rows={len(d) if isinstance(d, list) else d}')

    st, d = req('/api/state/sleep', 'POST', {'bed_time': '23:00', 'status': 'on_time'})
    print(f'state/sleep POST: {st} -> {d}')

    st, d = req('/api/state/weekly-energy')
    print(f'state/weekly-energy: {st} rows={len(d) if isinstance(d, list) else d}')

    st, d = req('/api/prompts')
    print(f'prompts list: {st} files={len(d) if isinstance(d, list) else d}')
    if isinstance(d, list) and d:
        name = d[0]['name']
        st2, d2 = req('/api/prompts/' + urllib.parse.quote(name))
        print(f'prompts GET {name}: {st2} len={len(d2.get("content", ""))}')
        st3, d3 = req('/api/prompts/' + urllib.parse.quote(name), 'PUT', {'content': d2.get('content', '')})
        print(f'prompts PUT roundtrip: {st3} -> {d3}')

    st, d = req('/api/knowledge/graph')
    if st == 200:
        links = d.get('links', [])
        print(f'knowledge/graph: nodes={len(d.get("nodes", []))} links={len(links)} sample_links={links[:2]}')
    else:
        print(f'knowledge/graph: {st} -> {d}')

    st, d = req('/api/agent/agents')
    print(f'agent/agents: {st} count={len(d) if isinstance(d, list) else d}')

    st, d = req('/api/agent/files/raw')
    if st == 200:
        print(f'agent/files/raw: subdirs={len(d.get("subdirs", []))} files={len(d.get("files", []))}')
    else:
        print(f'agent/files/raw: {st} -> {d}')

    st, d = req('/api/agent/files/vault')
    if st == 200:
        print(f'agent/files/vault: dirs={len(d.get("dirs", []))} files={len(d.get("files", []))}')
    else:
        print(f'agent/files/vault: {st} -> {d}')

    st, d = req('/api/agent/process', 'POST', {'agent': 'task_publisher', 'text': 'probe test'})
    print(f'agent/process (no key expected fail): {st} -> {d}')

    st, d = req('/api/gacha/statistics')
    print(f'gacha/statistics: {st} keys={list(d.keys()) if st == 200 else d}')

    st, d = req('/api/schedule/slots')
    print(f'schedule/slots: {st} count={len(d) if isinstance(d, list) else d}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
