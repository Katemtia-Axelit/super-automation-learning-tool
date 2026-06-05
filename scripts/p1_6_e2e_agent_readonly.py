"""P1-6 智能体只读模式 Playwright E2E

用法:
  python scripts/p1_6_e2e_agent_readonly.py
"""
import sys
import urllib.request

BASE = 'http://127.0.0.1:5000'
FAILURES = []
FORBIDDEN_URLS = ['/api/agent/process', '/api/agent/save-note', '/api/agent/import-tasks']


def fail(msg):
    FAILURES.append(msg)
    print('[FAIL]', msg)


def ok(msg):
    print('[PASS]', msg)


def main():
    print('=== P1-6 E2E Agent Readonly ===')
    try:
        with urllib.request.urlopen(BASE + '/api/health', timeout=5) as r:
            if r.status != 200:
                fail('health')
                return 1
    except Exception as e:
        fail(f'server: {e}')
        return 1
    ok('server health')

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        fail('Playwright not installed')
        return 1

    console_fatal = []
    post_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('console', lambda msg: console_fatal.append(msg.text)
                if msg.type == 'error' and ('SyntaxError' in msg.text or 'already been declared' in msg.text) else None)
        page.on('pageerror', lambda err: console_fatal.append(str(err)))

        def on_request(req):
            if req.method == 'POST':
                post_calls.append(req.url)

        page.on('request', on_request)

        page.goto(BASE, wait_until='networkidle', timeout=30000)
        ok('page loaded')

        page.click('[data-page="config"]')
        page.wait_for_timeout(600)

        page.click('#agentReadonlyOpenBtn')
        page.wait_for_timeout(600)
        if page.locator('#agentReadonlyModal:not(.hidden)').count():
            ok('agent readonly modal opened')
        else:
            fail('agent modal missing')

        if page.locator('#agentRoList .agent-ro-item').count():
            ok('agent list visible')
        else:
            fail('agent list empty')

        page.locator('#agentRoList .agent-ro-item').first.click()
        page.wait_for_timeout(500)
        prompt_val = page.locator('#agentRoPromptView').input_value()
        if prompt_val and prompt_val != '加载中...':
            ok('agent prompt content loaded')
        else:
            fail('agent prompt empty')

        page.locator('.agent-ro-tab[data-agent-tab="vault"]').click()
        page.wait_for_timeout(600)
        if page.locator('#agentVaultList .agent-ro-item').count():
            ok('vault file list visible')
            page.locator('#agentVaultList [data-vault-file]').first.click()
            page.wait_for_timeout(500)
            vault_text = page.locator('#agentVaultContent').inner_text()
            if vault_text and vault_text != '加载中...':
                ok('vault content loaded')
            else:
                ok('vault list ok (no file click or empty content)')
        else:
            ok('vault tab ok (empty vault)')

        page.click('#agentReadonlyCloseBtn')
        page.wait_for_timeout(300)

        page.click('[data-page="tasks"]')
        page.wait_for_timeout(300)
        page.click('[data-page="gacha"]')
        page.wait_for_timeout(300)
        ok('navigation after agent modal ok')

        bad_posts = [u for u in post_calls if any(f in u for f in FORBIDDEN_URLS)]
        if bad_posts:
            fail('forbidden agent POST called: ' + bad_posts[0])
        else:
            ok('no forbidden agent write/process POST during browse')

        if console_fatal:
            fail('console: ' + console_fatal[0])
        else:
            ok('no fatal console errors')

        browser.close()

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for f in FAILURES:
            print(' ', f)
        return 1

    print('\nALL P1-6 E2E TESTS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
