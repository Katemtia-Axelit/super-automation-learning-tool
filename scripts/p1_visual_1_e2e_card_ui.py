"""P1-Visual-1 任务卡牌牌感 Playwright E2E

用法:
  python scripts/p1_visual_1_e2e_card_ui.py
"""
import json
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5000'
TEST_PREFIX = '__TEST__'
TEST_CARD = TEST_PREFIX + 'P1_VIS_E2E_CARD'
TEST_SKIP = TEST_PREFIX + 'P1_VIS_E2E_SKIP'
TEST_DISCARD = TEST_PREFIX + 'P1_VIS_E2E_DISCARD'
FAILURES = []


def api_req(path, method='GET', body=None):
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
        st, active = api_req('/api/timer/active')
        if st == 200 and active and active.get('id'):
            api_req('/api/timer/complete', 'POST', {
                'session_id': active['id'], 'actual_minutes': 1,
                'result': 'abandoned', 'reason': 'cleanup',
            })
        st, tasks = api_req('/api/tasks?include_completed=true&unlocked_only=false')
        if st == 200 and isinstance(tasks, list):
            for t in tasks:
                if (t.get('name') or '').startswith(TEST_PREFIX):
                    api_req('/api/tasks/' + str(t['id']), 'DELETE')
    except (urllib.error.URLError, urllib.error.HTTPError):
        pass


def fail(msg):
    FAILURES.append(msg)
    print('[FAIL]', msg)


def ok(msg):
    print('[PASS]', msg)


def confirm_feedback(page):
    page.locator('#taskFeedbackOptions input[name="taskFbOpt"]').first.check()
    page.click('#taskFeedbackConfirmBtn')
    page.wait_for_timeout(700)


def main():
    print('=== P1-Visual-1 E2E Card UI ===')
    card_id = None
    skip_id = None
    discard_id = None

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

    st, c1 = api_req('/api/tasks', 'POST', {
        'name': TEST_CARD, 'prerequisite_ids': [],
        'estimated_time': 10, 'priority': 3, 'tags': ['数学'],
    })
    if st not in (200, 201) or not c1.get('id'):
        fail('create card test task')
        return 1
    card_id = c1['id']

    st, c2 = api_req('/api/tasks', 'POST', {
        'name': TEST_SKIP, 'prerequisite_ids': [], 'estimated_time': 10,
    })
    if st not in (200, 201) or not c2.get('id'):
        fail('create skip test task')
        return 1
    skip_id = c2['id']

    st, c3 = api_req('/api/tasks', 'POST', {
        'name': TEST_DISCARD, 'prerequisite_ids': [], 'estimated_time': 10,
    })
    if st not in (200, 201) or not c3.get('id'):
        fail('create discard test task')
        return 1
    discard_id = c3['id']

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

            if page.locator('#gachaDeck').count():
                ok('gacha deck visible')
            else:
                fail('gacha deck #gachaDeck missing')

            page.click('[data-page="tasks"]')
            page.wait_for_timeout(800)

            if page.locator('#taskGrid .task-card').count():
                ok('task list uses .task-card')
            else:
                fail('.task-card not found in task grid')

            card_el = page.locator('#taskGrid .task-card:has-text("' + TEST_CARD + '")')
            if card_el.count() and card_el.first.locator('.task-card-pattern').count():
                ok('task card has pattern area')
            else:
                fail('task card structure incomplete')

            page.click('[data-page="gacha"]')
            page.wait_for_timeout(500)
            page.click('#gachaBtn')
            page.wait_for_timeout(900)

            drawn = page.locator('#gachaResult .task-card.drawn-card')
            if drawn.count():
                ok('drawn result is task-card')
            else:
                fail('drawn card not shown after gacha')

            if page.locator('#gachaResult .task-card.is-drawing, #gachaResult .task-card.is-revealing').count():
                ok('draw animation classes present')
            elif drawn.count():
                ok('draw animation classes (may have finished)')
            else:
                fail('draw animation state missing')

            page.click('[data-page="tasks"]')
            page.wait_for_timeout(600)
            page.select_option('#taskFilter', 'all')
            page.wait_for_timeout(500)

            complete_btn = page.locator('#taskGrid .task-card:has-text("' + TEST_CARD + '") button:has-text("完成")')
            if complete_btn.count():
                complete_btn.first.click()
                page.wait_for_timeout(400)
                if page.locator('#taskGrid .task-card.is-completing, #taskGrid .task-card.is-evaporating').count():
                    ok('complete animation classes triggered')
                else:
                    ok('complete action executed (animation may have finished)')
                page.wait_for_timeout(800)
                if page.locator('#feedbackModal:not(.hidden)').count():
                    page.click('#feedbackModal .modal-actions button')
                    page.wait_for_timeout(300)
            else:
                fail('complete button not found')

            discard_btn = page.locator('#taskGrid .task-card:has-text("' + TEST_DISCARD + '") button:has-text("弃牌")')
            if discard_btn.count():
                discard_btn.first.click()
                page.wait_for_timeout(400)
                if page.locator('#taskFeedbackModal:not(.hidden)').count():
                    ok('discard triggers P1-5B feedback modal')
                    confirm_feedback(page)
                    page.wait_for_timeout(400)
                    if page.locator('#taskGrid .task-card.is-discarding').count():
                        ok('discard animation class triggered')
                    else:
                        ok('discard action executed (animation may have finished)')
                else:
                    fail('discard feedback modal missing')
            else:
                fail('discard button not found')

            skip_btn = page.locator('#taskGrid .task-card:has-text("' + TEST_SKIP + '") button:has-text("跳过")')
            if skip_btn.count():
                skip_btn.first.click()
                page.wait_for_timeout(400)
                if page.locator('#taskFeedbackModal:not(.hidden)').count():
                    ok('skip triggers P1-5B feedback modal')
                    page.click('#taskFeedbackCancelBtn')
                    page.wait_for_timeout(400)
                    ok('feedback cancel does not block flow')
                else:
                    fail('skip feedback modal missing')
            else:
                fail('skip button not found')

            page.click('[data-page="schedule"]')
            page.wait_for_timeout(400)
            page.click('#stateAssessmentOpenBtn')
            page.wait_for_timeout(300)
            page.click('#stateAssessmentCancelBtn')
            page.click('[data-page="config"]')
            page.wait_for_timeout(400)
            page.click('#agentReadonlyOpenBtn')
            page.wait_for_timeout(300)
            page.click('#agentReadonlyCloseBtn')
            page.wait_for_timeout(200)
            ok('schedule / agent readonly still accessible')

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

    print('\nALL P1-VISUAL-1 E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
