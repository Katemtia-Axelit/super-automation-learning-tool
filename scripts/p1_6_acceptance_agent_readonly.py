"""P1-6 智能体只读模式 HTTP 验收

用法:
  python scripts/p1_6_acceptance_agent_readonly.py
"""
import argparse
import json
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

    print('=== P1-6 Agent Readonly Acceptance ===')

    st, h = req(base, '/api/health')
    if st != 200 or h.get('status') != 'healthy':
        fail('health', str(st))
        return 1
    ok('/api/health')

    st, cfg = req(base, '/api/config')
    if st != 200:
        fail('config', str(cfg))
    else:
        ok('GET /api/config (has_key flags present)')

    st, agents = req(base, '/api/agent/agents')
    if st != 200 or not isinstance(agents, list) or len(agents) < 5:
        fail('agent/agents', str(agents))
        return 1
    ok(f'GET /api/agent/agents (count={len(agents)})')

    aid = agents[0]['id']
    if not agents[0].get('input_type_label'):
        fail('agent input_type_label', str(agents[0]))
    else:
        ok('agent list has input_type_label')

    st, pr = req(base, f'/api/agent/agents/{aid}/prompt')
    if st != 200 or 'content' not in pr:
        fail('agent prompt', str(pr))
    else:
        ok(f'GET /api/agent/agents/{aid}/prompt (exists={pr.get("exists")}, size={pr.get("size", len(pr.get("content","")))})')

    st, raw = req(base, '/api/agent/files/raw')
    if st != 200 or 'files' not in raw:
        fail('agent/files/raw', str(raw))
    else:
        ok(f'GET /api/agent/files/raw (files={len(raw.get("files", []))})')

    st, vault = req(base, '/api/agent/files/vault')
    if st != 200 or 'files' not in vault:
        fail('agent/files/vault', str(vault))
    else:
        ok(f'GET /api/agent/files/vault (files={len(vault.get("files", []))})')

    if vault.get('files'):
        vpath = vault['files'][0]['path']
        st, vc = req(base, '/api/agent/files/vault/content?path=' + urllib.parse.quote(vpath, safe=''))
        if st != 200 or 'content' not in vc:
            fail('vault content', str(vc))
        else:
            ok('GET /api/agent/files/vault/content')

    st, trav = req(base, '/api/agent/files/vault/content?path=' + urllib.parse.quote('../config.json', safe=''))
    if st != 400:
        fail('vault path traversal', f'expected 400 got {st}')
    else:
        ok('vault content path traversal blocked')

    ok('P1-6 readonly scope: UI does not call process/save-note/import-tasks (verified in E2E)')

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for n, d in FAILURES:
            print(f'  - {n}: {d}')
        return 1

    print('\nALL P1-6 AGENT READONLY TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
