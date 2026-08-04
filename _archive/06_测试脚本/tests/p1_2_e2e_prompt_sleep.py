"""P1-2 提示词只读 + 睡眠追踪 Playwright E2E（需服务器已运行）

用法:
  python scripts/p1_2_e2e_prompt_sleep.py
"""
import sys
import urllib.request

BASE = 'http://127.0.0.1:5000'
FAILURES = []


def fail(msg):
    FAILURES.append(msg)
    print('[FAIL]', msg)


def ok(msg):
    print('[PASS]', msg)


def ensure_server():
    try:
        with urllib.request.urlopen(BASE + '/api/health', timeout=5) as r:
            if r.status != 200:
                fail('server health')
    except Exception as e:
        fail(f'server not running: {e}')
        return False
    ok('server health')
    return True


def main():
    print('=== P1-2 E2E Prompt + Sleep ===')
    if not ensure_server():
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        fail('Playwright not installed')
        return 1

    console_fatal = []
    test_time = '22:45'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('console', lambda msg: console_fatal.append(msg.text)
                if msg.type == 'error' and ('SyntaxError' in msg.text or 'already been declared' in msg.text) else None)
        page.on('pageerror', lambda err: console_fatal.append(str(err)))

        page.goto(BASE, wait_until='networkidle', timeout=30000)

        page.click('[data-page="config"]')
        page.wait_for_timeout(600)

        if not page.locator('#promptPanel').count():
            fail('prompt panel missing')
        else:
            ok('settings: prompt panel exists')

        page.click('#promptRefreshBtn')
        page.wait_for_timeout(800)

        item = page.locator('.prompt-file-item').first
        if item.count():
            item.click()
            page.wait_for_timeout(500)
            content = page.locator('#promptContentView').input_value()
            if content:
                ok('settings: prompt content loaded (readonly)')
            else:
                fail('settings: prompt content empty')
            page.click('#promptCopyBtn')
            page.wait_for_timeout(300)
            ok('settings: copy button clicked')
        else:
            empty = page.locator('#promptFileList:has-text("暂无")')
            if empty.count():
                ok('settings: empty prompt list state')
            else:
                fail('settings: no prompt files and no empty message')

        readonly = page.locator('#promptContentView')
        if readonly.count() and readonly.get_attribute('readonly') is not None:
            ok('settings: textarea is readonly')

        page.click('[data-page="schedule"]')
        page.wait_for_timeout(600)

        if not page.locator('#sleepPanel').count():
            fail('sleep panel missing')
        else:
            ok('schedule: sleep panel exists')

        page.fill('#sleepBedTimeInput', test_time)
        page.click('#sleepSaveBtn')
        page.wait_for_timeout(800)

        displayed = page.locator('#sleepBedTimeDisplay').inner_text()
        if test_time in displayed or displayed == test_time:
            ok('schedule: sleep time saved and displayed')
        else:
            fail(f'schedule: display={displayed!r} expected {test_time}')

        page.reload(wait_until='networkidle')
        page.wait_for_timeout(800)
        page.click('[data-page="schedule"]')
        page.wait_for_timeout(600)

        inp_val = page.locator('#sleepBedTimeInput').input_value()
        if inp_val == test_time:
            ok('schedule: sleep time persists after reload')
        else:
            fail(f'schedule: after reload input={inp_val!r}')

        if page.locator('#weeklyEnergyTable table').count() or page.locator('#weeklyEnergyTable:has-text("暂无")').count():
            ok('schedule: weekly energy table or empty state')
        else:
            fail('schedule: weekly energy area missing')

        if console_fatal:
            fail('console fatal: ' + console_fatal[0])
        else:
            ok('browser console no fatal errors')

        browser.close()

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for f in FAILURES:
            print(' ', f)
        return 1

    print('\nALL P1-2 E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
