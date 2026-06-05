"""P1-5B 任务事件反馈 Playwright E2E

用法:
  python scripts/p1_5b_e2e_task_feedback.py
"""
import json
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5000'
TEST_PREFIX = '__TEST__'
TEST_SKIP = TEST_PREFIX + 'P1_5B_E2E_SKIP'
TEST_TIMER = TEST_PREFIX + 'P1_5B_E2E_TIMER'
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
                'session_id': active['id'], 'actual_minutes': 1,
                'result': 'abandoned', 'reason': 'cleanup',
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


def confirm_feedback(page, pick_first=True):
    if pick_first:
        page.locator('#taskFeedbackOptions input[name="taskFbOpt"]').first.check()
    page.click('#taskFeedbackConfirmBtn')
    page.wait_for_timeout(500)


def main():
    print('=== P1-5B E2E Task Feedback ===')
    skip_id = None
    timer_id = None

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

    st, c1 = api_req_status('/api/tasks', 'POST', {
        'name': TEST_SKIP, 'prerequisite_ids': [], 'estimated_time': 15,
    })
    if st not in (200, 201) or not c1.get('id'):
        fail('create skip test task')
        return 1
    skip_id = c1['id']

    st, c2 = api_req_status('/api/tasks', 'POST', {
        'name': TEST_TIMER, 'prerequisite_ids': [], 'estimated_time': 30,
    })
    if st not in (200, 201) or not c2.get('id'):
        fail('create timer test task')
        return 1
    timer_id = c2['id']

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

            page.click('[data-page="tasks"]')
            page.wait_for_timeout(800)

            skip_btn = page.locator('.task-grid .card:has-text("' + TEST_SKIP + '") button:has-text("跳过")')
            if not skip_btn.count():
                fail('skip button not found')
            else:
                skip_btn.first.click()
                page.wait_for_timeout(400)
                if page.locator('#taskFeedbackModal:not(.hidden)').count():
                    ok('skip feedback modal shown')
                    confirm_feedback(page)
                    page.wait_for_timeout(600)
                else:
                    fail('skip feedback modal missing')

            page.select_option('#timerTaskSelect', str(timer_id))
            page.click('#timerStartBtn')
            page.wait_for_timeout(700)
            page.click('#timerStopBtn')
            page.wait_for_timeout(400)
            if page.locator('#timerOutcomeModal:not(.hidden)').count():
                ok('timer outcome modal shown')
            else:
                fail('timer outcome modal missing')

            page.click('[data-timer-outcome="completed"]')
            page.wait_for_timeout(500)
            if page.locator('#taskFeedbackModal:not(.hidden)').count():
                ok('early finish feedback modal shown')
                confirm_feedback(page)
            page.wait_for_timeout(400)

            page.select_option('#timerTaskSelect', str(timer_id))
            page.click('#timerStartBtn')
            page.wait_for_timeout(700)
            page.click('#timerStopBtn')
            page.wait_for_timeout(300)
            page.click('#timerOutcomeCancelBtn')
            page.wait_for_timeout(300)
            if page.locator('#timerStopBtn:not(.hidden)').count():
                ok('timer outcome cancel keeps session')
            else:
                fail('timer outcome cancel failed')

            page.click('#timerStopBtn')
            page.wait_for_timeout(300)
            page.click('[data-timer-outcome="unfinished"]')
            page.wait_for_timeout(400)
            if page.locator('#taskFeedbackModal:not(.hidden)').count():
                ok('unfinished feedback modal shown')
                page.click('#taskFeedbackCancelBtn')
                page.wait_for_timeout(400)
                ok('feedback cancel does not block flow')
            else:
                fail('unfinished feedback modal missing')

            page.click('[data-page="gacha"]')
            page.wait_for_timeout(400)
            page.click('[data-page="schedule"]')
            page.wait_for_timeout(400)
            page.click('#stateAssessmentOpenBtn')
            page.wait_for_timeout(300)
            page.click('#stateAssessmentCancelBtn')
            page.wait_for_timeout(200)
            page.click('[data-page="tasks"]')
            page.wait_for_timeout(400)
            page.click('#discardPileOpenBtn')
            page.wait_for_timeout(300)
            page.click('#discardPileCloseBtn')
            page.wait_for_timeout(200)
            ok('other modules still accessible')

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

    print('\nALL P1-5B E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
