"""P1-5 状态评估 + 计时器 Playwright E2E

用法:
  python scripts/p1_5_e2e_state_timer.py
"""
import json
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5000'
TEST_PREFIX = '__TEST__'
TEST_TASK = TEST_PREFIX + 'P1_5_E2E_TIMER'
FAILURES = []


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


def cleanup():
    try:
        st, active = api_req_status('/api/timer/active')
        if st == 200 and active and active.get('id'):
            api_req_status('/api/timer/complete', 'POST', {
                'session_id': active['id'],
                'actual_minutes': 1,
                'result': 'completed',
                'reason': 'e2e_cleanup',
            })
        st, tasks = api_req_status('/api/tasks?include_completed=true&unlocked_only=false')
        if st == 200 and isinstance(tasks, list):
            for t in tasks:
                if (t.get('name') or '').startswith(TEST_PREFIX):
                    api_req_status('/api/tasks/' + str(t['id']), 'DELETE')
    except (urllib.error.URLError, urllib.error.HTTPError):
        pass


def fail(msg):
    FAILURES.append(msg)
    print('[FAIL]', msg)


def ok(msg):
    print('[PASS]', msg)


def main():
    print('=== P1-5 E2E State Assessment + Timer ===')
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

    cleanup()

    st, created = api_req_status('/api/tasks', 'POST', {
        'name': TEST_TASK, 'prerequisite_ids': [], 'repeat_type': 'none',
    })
    if st not in (200, 201) or not created.get('id'):
        fail('create test task for timer')
        return 1
    task_id = created['id']

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        fail('Playwright not installed')
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
            ok('page loaded')

            page.click('[data-page="schedule"]')
            page.wait_for_timeout(800)

            page.click('#stateAssessmentOpenBtn')
            page.wait_for_timeout(500)
            if not page.locator('#stateAssessmentModal:not(.hidden)').count():
                fail('assessment modal not opened')
            else:
                ok('assessment modal opened')

            page.locator('#stateAssessmentForm .assess-range').first.fill('4')
            page.click('#stateAssessmentSaveBtn')
            page.wait_for_timeout(800)

            if page.locator('#stateAssessmentSummary .state-scores').count():
                ok('assessment summary updated after save')
            elif page.locator('#stateAssessmentSummary:has-text("今日还没有评估")').count():
                fail('assessment summary not updated')
            else:
                ok('assessment saved (summary visible)')

            page.click('[data-page="tasks"]')
            page.wait_for_timeout(700)

            if page.locator('#timerPanel').count():
                ok('timer panel visible')
            else:
                fail('timer panel missing')

            page.select_option('#timerTaskSelect', str(task_id))
            page.click('#timerStartBtn')
            page.wait_for_timeout(800)

            if page.locator('#timerStopBtn:not(.hidden)').count():
                ok('timer started')
            else:
                fail('timer start UI not updated')

            page.click('#timerStopBtn')
            page.wait_for_timeout(400)
            page.click('[data-timer-outcome="completed"]')
            page.wait_for_timeout(500)
            if page.locator('#taskFeedbackModal:not(.hidden)').count():
                page.locator('#taskFeedbackOptions input[name="taskFbOpt"]').first.check()
                page.click('#taskFeedbackConfirmBtn')
                page.wait_for_timeout(400)

            if page.locator('#timerStartBtn:not(.hidden)').count():
                ok('timer stopped')
            else:
                fail('timer stop UI not updated')

            page.reload(wait_until='networkidle')
            page.wait_for_timeout(500)
            page.click('[data-page="gacha"]')
            page.wait_for_timeout(300)
            page.click('[data-page="tasks"]')
            page.wait_for_timeout(300)
            page.click('[data-page="schedule"]')
            page.wait_for_timeout(300)
            ok('navigation after reload ok')

            if console_fatal:
                fail('console: ' + console_fatal[0])
            else:
                ok('no fatal console errors')

            browser.close()
    finally:
        cleanup()

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for f in FAILURES:
            print(' ', f)
        return 1

    print('\nALL P1-5 E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
