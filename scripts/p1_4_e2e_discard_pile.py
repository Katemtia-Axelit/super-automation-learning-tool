"""P1-4 弃牌堆浏览/恢复 Playwright E2E

用法:
  python scripts/p1_4_e2e_discard_pile.py
"""
import json
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5000'
TEST_PREFIX = '__TEST__'
TEST_NAME = TEST_PREFIX + 'P1_4_E2E_DISCARD'
FAILURES = []


def api_req(path, method='GET', body=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def api_req_status(path, method='GET', body=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='ignore')
        try:
            j = json.loads(raw)
        except json.JSONDecodeError:
            j = {}
        return e.code, j


def cleanup_test_tasks():
    try:
        tasks = api_req('/api/tasks?include_completed=true&unlocked_only=false')
        if not isinstance(tasks, list):
            return
        for t in tasks:
            if (t.get('name') or '').startswith(TEST_PREFIX):
                api_req_status('/api/tasks/' + str(t['id']), 'DELETE')
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        pass


def fail(msg):
    FAILURES.append(msg)
    print('[FAIL]', msg)


def ok(msg):
    print('[PASS]', msg)


def main():
    print('=== P1-4 E2E Discard Pile ===')
    task_id = None

    try:
        with urllib.request.urlopen(BASE + '/api/health', timeout=5) as r:
            if r.status != 200:
                fail('health')
                return 1
    except Exception as e:
        fail(f'server: {e}')
        return 1
    ok('server health')

    cleanup_test_tasks()

    try:
        st, created = api_req_status('/api/tasks', 'POST', {
            'name': TEST_NAME,
            'prerequisite_ids': [],
            'repeat_type': 'daily',
        })
        if st not in (200, 201) or not created.get('id'):
            fail('create test task')
            return 1
        task_id = created['id']
        st, _ = api_req_status('/api/tasks/' + str(task_id) + '/move-to-discard', 'POST', {})
        if st != 200:
            fail('move test task to discard')
            return 1
        ok('test task prepared in discard pile')

        from playwright.sync_api import sync_playwright
    except ImportError:
        fail('Playwright not installed')
        return 1
    except Exception as e:
        fail(f'setup: {e}')
        return 1

    console_fatal = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on('console', lambda msg: console_fatal.append(msg.text)
                    if msg.type == 'error' and ('SyntaxError' in msg.text or 'already been declared' in msg.text) else None)
            page.on('pageerror', lambda err: console_fatal.append(str(err)))

            page.goto(BASE, wait_until='networkidle', timeout=30000)
            page.click('[data-page="tasks"]')
            page.wait_for_timeout(500)

            page.click('#discardPileOpenBtn')
            page.wait_for_timeout(600)
            if not page.locator('#discardPileModal:not(.hidden)').count():
                fail('discard modal not opened')
            else:
                ok('discard modal opened')

            if not page.locator('#discardPileList:has-text("' + TEST_NAME + '")').count():
                fail('test task not in discard list')
            else:
                ok('test task visible in discard list')

            page.once('dialog', lambda d: d.accept())
            page.locator('#discardPileList .discard-restore-btn[data-id="' + str(task_id) + '"]').click()
            page.wait_for_timeout(900)

            if page.locator('#discardPileList:has-text("' + TEST_NAME + '")').count():
                fail('task still in list after restore')
            else:
                ok('task removed from list after restore')

            page.click('#discardPileCloseBtn')
            page.wait_for_timeout(300)
            if page.locator('#discardPileModal:not(.hidden)').count():
                fail('discard modal not closed')
            else:
                ok('discard modal closed')

            page.click('[data-page="gacha"]')
            page.wait_for_timeout(400)
            page.click('[data-page="schedule"]')
            page.wait_for_timeout(400)
            ok('navigation after discard modal ok')

            if console_fatal:
                fail('console: ' + console_fatal[0])
            else:
                ok('no fatal console errors')

            browser.close()
    finally:
        if task_id:
            try:
                api_req_status('/api/tasks/' + str(task_id), 'DELETE')
            except Exception:
                pass
        cleanup_test_tasks()

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for f in FAILURES:
            print(' ', f)
        return 1

    print('\nALL P1-4 E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
