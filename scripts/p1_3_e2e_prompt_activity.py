"""P1-3 提示词可写 + 活动管理 Playwright E2E

用法:
  python scripts/p1_3_e2e_prompt_activity.py

隔离说明: 使用专用测试文件 __TEST__P1_3_E2E.md，避免与
p1_3_acceptance_prompt_activity.py 串跑时争用同一提示词备份链。
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:5000'
TEST_PROMPT = '__TEST__P1_3_E2E.md'
MARKER = '\n<!-- P1_3_E2E_TEST -->\n'
TEST_ACTIVITY = 'P1_3_E2E_ACTIVITY'
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


def qname(name):
    return urllib.parse.quote(name, safe='')


def restore_test_prompt():
    """将 E2E 测试提示词恢复为无 MARKER 的初始状态。"""
    try:
        st, body = api_req_status('/api/prompts/' + qname(TEST_PROMPT))
        if st != 200:
            return
        content = body.get('content', '')
        if MARKER.strip() not in content:
            return
        st, bak = api_req_status('/api/prompts/' + qname(TEST_PROMPT) + '/backup/latest')
        if st == 200 and bak.get('exists'):
            api_req_status('/api/prompts/' + qname(TEST_PROMPT) + '/restore-latest', 'POST', {})
            return
        cleaned = content.replace(MARKER, '').replace(MARKER.strip(), '')
        api_req_status('/api/prompts/' + qname(TEST_PROMPT), 'PUT', {'content': cleaned})
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        pass


def fail(msg):
    FAILURES.append(msg)
    print('[FAIL]', msg)


def ok(msg):
    print('[PASS]', msg)


def main():
    print('=== P1-3 E2E Prompt Write + Activity ===')
    try:
        with urllib.request.urlopen(BASE + '/api/health', timeout=5) as r:
            if r.status != 200:
                fail('health')
                return 1
    except Exception as e:
        fail(f'server: {e}')
        return 1
    ok('server health')

    restore_test_prompt()

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
            page.click('[data-page="config"]')
            page.wait_for_timeout(700)

            page.click('#promptRefreshBtn')
            page.wait_for_timeout(600)

            test_item = page.locator('.prompt-file-item:has-text("' + TEST_PROMPT + '")')
            if not test_item.count():
                fail('isolated test prompt not in list: ' + TEST_PROMPT)
                browser.close()
                return 1
            test_item.first.click()
            page.wait_for_timeout(500)
            ok('using isolated test prompt: ' + TEST_PROMPT)

            before = page.locator('#promptContentView').input_value()

            page.click('#promptEditBtn')
            page.wait_for_timeout(200)
            edited = before + MARKER
            page.fill('#promptContentView', edited)

            page.click('#promptPreviewBtn')
            page.wait_for_timeout(400)
            if not page.locator('#promptDiffModal:not(.hidden)').count():
                fail('diff modal not shown')
            else:
                ok('diff modal shown')

            page.click('#promptDiffCancelBtn')
            page.wait_for_timeout(300)
            ok('diff cancel clicked')

            page.click('#promptPreviewBtn')
            page.wait_for_timeout(400)
            page.click('#promptDiffConfirmBtn')
            page.wait_for_timeout(800)

            page.reload(wait_until='networkidle')
            page.wait_for_timeout(500)
            page.click('[data-page="config"]')
            page.wait_for_timeout(400)
            page.locator('.prompt-file-item:has-text("' + TEST_PROMPT + '")').first.click()
            page.wait_for_timeout(500)
            after_save = page.locator('#promptContentView').input_value()
            if MARKER in after_save:
                ok('saved content persists after reload')
            else:
                fail('marker missing after save reload')

            try:
                page.locator('#promptRestoreBtn').wait_for(state='visible', timeout=5000)
            except Exception:
                fail('restore button not visible after save')

            page.once('dialog', lambda d: d.accept())
            page.click('#promptRestoreBtn')
            page.wait_for_timeout(1200)
            restored = page.locator('#promptContentView').input_value()
            if MARKER not in restored:
                ok('restore latest reverted content')
            else:
                fail('restore did not revert')

            page.click('[data-page="schedule"]')
            page.wait_for_timeout(500)
            page.click('button:has-text("活动管理")')
            page.wait_for_timeout(500)
            if page.locator('#activityMgrModal:not(.hidden)').count():
                ok('activity modal opened')
            else:
                fail('activity modal missing')

            page.fill('#activityNewName', TEST_ACTIVITY)
            page.click('#activityAddBtn')
            page.wait_for_timeout(600)
            if page.locator('#activityList:has-text("' + TEST_ACTIVITY + '")').count():
                ok('activity added to list')
            else:
                fail('activity not in list')

            page.once('dialog', lambda d: d.accept())
            page.locator('#activityList .activity-row:has-text("' + TEST_ACTIVITY + '") .activity-del-btn').click()
            page.wait_for_timeout(800)
            if not page.locator('#activityList:has-text("' + TEST_ACTIVITY + '")').count():
                ok('activity deleted from list')
            else:
                fail('activity still in list')

            page.click('#activityMgrCloseBtn')
            page.wait_for_timeout(300)
            ok('activity modal closed')

            if console_fatal:
                fail('console: ' + console_fatal[0])
            else:
                ok('no fatal console errors')

            browser.close()
    finally:
        restore_test_prompt()

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for f in FAILURES:
            print(' ', f)
        return 1

    print('\nALL P1-3 E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
