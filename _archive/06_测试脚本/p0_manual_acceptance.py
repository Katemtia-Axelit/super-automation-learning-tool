"""P0-3 完整人工流程 HTTP + 静态前端 + 可选 Playwright 控制台验收"""
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = 'http://127.0.0.1:5000'
ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__file__))


def req(path, method='GET', body=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))


def req_raw(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as resp:
        return resp.read().decode('utf-8')


def fail(msg):
    print('[FAIL]', msg)
    sys.exit(1)


def ok(msg):
    print('[PASS]', msg)


def check_static_frontend():
    html = req_raw('/')
    js = req_raw('/static/app.js')

    if html.count('const API') > 0:
        fail('index.html 内联重复 const API')
    if html.count('/static/app.js') != 1:
        fail('index.html 应仅引用一次 app.js')
    if js.count('const API') != 1:
        fail('app.js 中 const API 应只出现一次')
    ok('无重复声明（index + app.js 静态检查）')

    nav_pages = ['gacha', 'tasks', 'schedule', 'knowledge', 'config']
    for p in nav_pages:
        if f'data-page="{p}"' not in html:
            fail(f'导航缺少 {p}')
    ok('导航五页 DOM 存在')

    handlers = [
        'drawGacha', 'completeWithFeedback', 'handleSkip', 'handleRefuse', 'doReplace',
        'cancelFeedback', 'submitFeedback', 'openTaskEdit', 'saveTask', 'deleteTask',
        'openDepGraph', 'moveToDiscard', 'taskSkip', 'taskRefuse', 'loadCategories',
        'openCurrentInObsidian', 'saveConfigForm', 'editSlot', 'openActivityMgr',
    ]
    for h in handlers:
        if f'function {h}' not in js and f'async function {h}' not in js:
            fail(f'app.js 缺少函数 {h}')
    ok('主要按钮处理函数均存在')


def check_task_dependency_manual():
    # 使用唯一名称避免与历史数据冲突
    suffix = datetime.now().strftime('%H%M%S')
    name_a = f'P0_A_{suffix}'
    name_b = f'P0_B_{suffix}'

    _, a = req('/api/tasks', 'POST', {'name': name_a, 'prerequisite_ids': []})
    id_a = a['id']
    _, b = req('/api/tasks', 'POST', {'name': name_b, 'prerequisite_ids': [id_a]})
    id_b = b['id']

    _, tasks = req('/api/tasks?unlocked_only=false')
    tb = next(t for t in tasks if t['id'] == id_b)
    if tb.get('is_unlocked'):
        fail('B 应在 A 未完成时阻塞')
    ok('A 未完成时 B 显示阻塞（is_unlocked=0）')

    drawn_b = False
    for _ in range(8):
        try:
            _, dr = req('/api/gacha/draw', 'POST', {'pool': 'fragment', 'energy': 'medium'})
            if dr.get('task', {}).get('id') == id_b:
                drawn_b = True
                break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
    if drawn_b:
        fail('抽卡不应抽到被阻塞的 B')
    ok('抽卡时 B 不会被抽中（8 次抽样）')

    try:
        req(f'/api/tasks/{id_a}', 'PUT', {'prerequisite_ids': [id_b]})
        fail('A 依赖 B 应被阻止')
    except urllib.error.HTTPError as e:
        if e.code != 400:
            fail(f'循环依赖应返回 400，实际 {e.code}')
    ok('A 依赖 B 被阻止（循环依赖）')

    req(f'/api/tasks/{id_a}/complete', 'POST', {})
    _, tasks2 = req('/api/tasks?unlocked_only=false')
    tb2 = next(t for t in tasks2 if t['id'] == id_b)
    if not tb2.get('is_unlocked'):
        fail('完成 A 后 B 应解锁')
    ok('完成 A 后 B 解除阻塞')

    found_in_pool = False
    for _ in range(15):
        try:
            _, dr = req('/api/gacha/draw', 'POST', {'pool': 'deep', 'energy': 'high'})
            tid = dr.get('task', {}).get('id')
            if tid == id_b:
                found_in_pool = True
                break
        except urllib.error.HTTPError:
            pass
    # B 可能在池中但加权未抽到；检查 pools/detail 是否包含 B
    _, detail = req('/api/gacha/pools/detail', 'GET')
    in_detail = any(t['id'] == id_b for p in detail.values() for t in p.get('tasks', []))
    if not in_detail and not found_in_pool:
        fail('B 解锁后应进入抽卡候选池')
    ok('B 解锁后可进入抽卡候选池')

    req(f'/api/tasks/{id_a}', 'DELETE')
    _, tasks3 = req('/api/tasks?unlocked_only=false')
    tb3 = next(t for t in tasks3 if t['id'] == id_b)
    if tb3.get('prerequisite_ids'):
        fail('删除 A 后 B 的依赖应被清理')
    _, deps = req('/api/dependencies', 'GET')
    if not isinstance(deps.get('nodes'), list):
        fail('依赖图接口报错')
    ok('删除 A 后 B/任务列表/依赖图正常')

    req(f'/api/tasks/{id_b}', 'DELETE')
    ok('任务依赖人工验收全流程')


def check_schedule_manual():
    today = datetime.now().strftime('%Y-%m-%d')
    _, slots = req('/api/schedule/slots', 'GET')
    slot_id = slots[0]['slot_id']

    req('/api/schedule/daily', 'POST', {'date': today, 'slot_id': slot_id, 'activity': '测试日程 P0-3'})
    _, daily = req(f'/api/schedule/daily?date={today}', 'GET')
    row = next((d for d in daily if d.get('slot_id') == slot_id), None)
    if not row or row.get('activity') != '测试日程 P0-3':
        fail('保存后刷新应仍存在「测试日程 P0-3」')
    ok('日程保存并刷新后内容存在')

    req('/api/schedule/daily', 'POST', {'date': today, 'slot_id': slot_id, 'activity': '测试日程 P0-3 修改'})
    _, daily2 = req(f'/api/schedule/daily?date={today}', 'GET')
    row2 = next((d for d in daily2 if d.get('slot_id') == slot_id), None)
    if not row2 or row2.get('activity') != '测试日程 P0-3 修改':
        fail('修改后刷新应存在新内容')
    ok('日程修改后刷新内容正确')

    req('/api/schedule/daily', 'POST', {'date': today, 'slot_id': slot_id, 'activity': ''})
    _, daily3 = req(f'/api/schedule/daily?date={today}', 'GET')
    row3 = next((d for d in daily3 if d.get('slot_id') == slot_id), None)
    if row3 and row3.get('activity'):
        fail('清空后刷新应为空')
    ok('日程清空后刷新为空')

    req('/api/schedule/weekly', 'GET')
    ok('日程 weekly 接口正常')


def check_knowledge_and_config():
    _, cats = req('/api/knowledge/categories', 'GET')
    if not cats:
        fail('知识库分类为空')
    ok('知识库分类接口正常')

    _, notes = req('/api/knowledge/notes', 'GET')
    if notes:
        path = notes[0].get('path') or notes[0].get('id')
        req('/api/knowledge/note-content/' + urllib.request.quote(path, safe=''), 'GET')
        ok('知识库笔记内容可读')

    try:
        req('/api/knowledge/open-in-obsidian', 'POST', {'file_path': 'nonexistent/test.md'})
        fail('Obsidian 打开不存在文件应失败')
    except urllib.error.HTTPError as e:
        if e.code not in (404, 500):
            fail(f'Obsidian 错误码异常: {e.code}')
    ok('Obsidian 打开失败有明确 HTTP 错误（非静默）')

    _, cfg = req('/api/config', 'GET')
    _, saved = req('/api/config/save', 'POST', {'port': cfg.get('port', 5000)})
    if not saved.get('success'):
        fail('保存配置失败')
    ok('设置保存配置接口正常')


def check_server_log():
    log_path = __import__('os').path.join(ROOT, '.run', 'server.log')
    if not __import__('os').path.exists(log_path):
        fail('server.log 不存在')
    text = open(log_path, encoding='utf-8', errors='ignore').read()
    for err in ['no such table: weekly_schedule', 'no such table: daily_schedule',
                'no such table: user_schedule', 'no such table: daily_schedules']:
        if err in text.lower():
            fail(f'日志含 SQL 错误: {err}')
    ok('server.log 无日程表 SQL 错误')


def try_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('[SKIP] Playwright 未安装，跳过真实浏览器 Console 采集')
        return

    console_errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
        page.on('pageerror', lambda err: console_errors.append(str(err)))
        page.goto(BASE, wait_until='networkidle', timeout=30000)

        for sel in ['[data-page="tasks"]', '[data-page="schedule"]', '[data-page="knowledge"]', '[data-page="config"]', '[data-page="gacha"]']:
            page.click(sel)
            page.wait_for_timeout(300)

        page.click('#gachaBtn')
        page.wait_for_timeout(500)

        errs = [e for e in console_errors if 'Identifier' in e and 'already been declared' in e]
        if errs:
            fail('浏览器 Console 重复声明: ' + errs[0])
        fatal = [e for e in console_errors if 'SyntaxError' in e or 'already been declared' in e]
        if fatal:
            fail('浏览器 Console 致命错误: ' + fatal[0])
        browser.close()
    ok('Playwright 浏览器 Console 无重复声明/语法错误')


def main():
    print('=== P0-3 Manual + Static Browser Acceptance ===')
    check_static_frontend()
    check_task_dependency_manual()
    check_schedule_manual()
    check_knowledge_and_config()
    check_server_log()
    try_playwright()
    print('\nALL P0-3 MANUAL ACCEPTANCE PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
