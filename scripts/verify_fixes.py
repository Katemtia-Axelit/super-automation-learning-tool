"""验证修复后的 API 端点

测试:
1. PUT /api/tasks/{id} - 应返回 200
2. POST /api/tags - 应返回 200/201
3. /api/knowledge/graph - 性能测试
4. /api/task-feedback POST - event_type 验证
"""

import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:5000"


def api_get(path):
    """GET 请求"""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return None, str(e)


def api_post(path, data):
    """POST 请求"""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Content-Length': str(len(body))
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        if hasattr(e, 'read'):
            error_body = e.read().decode('utf-8')
            return None, f"{e.reason}: {error_body}"
        return None, str(e)


def api_put(path, data):
    """PUT 请求"""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Content-Length': str(len(body)),
        'X-HTTP-Method-Override': 'PUT'
    })
    req.get_method = lambda: 'PUT'
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        if hasattr(e, 'read'):
            error_body = e.read().decode('utf-8')
            return None, f"{e.reason}: {error_body}"
        return None, str(e)


def test_put_task():
    """测试 Bug #2: PUT /api/tasks/{id}"""
    print("\n[测试] PUT /api/tasks/{id}")

    # 先获取一个任务
    status, tasks = api_get('/api/tasks')
    if not status or not tasks or len(tasks) == 0:
        print("  无法获取任务列表")
        return False

    task = tasks[0]
    task_id = task['id']

    # 更新任务
    update_data = {
        'name': task['name'] + ' (测试更新)',
        'priority': min(10, task.get('priority', 5) + 1),
        'task_profile': task.get('task_profile', 'deadline_flexible')
    }

    status, resp = api_put(f'/api/tasks/{task_id}', update_data)
    if status == 200:
        print(f"  [PASS] PUT /api/tasks/{task_id} 返回 200")
        return True
    else:
        print(f"  [FAIL] PUT /api/tasks/{task_id} 返回 {status}: {resp}")
        return False


def test_create_tag():
    """测试 Bug #3: POST /api/tags"""
    print("\n[测试] POST /api/tags")

    test_tag = f"测试标签_{int(time.time())}"
    status, resp = api_post('/api/tags', {'name': test_tag})

    if status in [200, 201]:
        print(f"  [PASS] POST /api/tags 返回 {status}")
        print(f"        响应: {resp}")
        return True
    else:
        print(f"  [FAIL] POST /api/tags 返回 {status}: {resp}")
        return False


def test_knowledge_graph_performance():
    """测试 Bug #4: /api/knowledge/graph 性能"""
    print("\n[测试] /api/knowledge/graph 性能")

    start = time.time()
    status, resp = api_get('/api/knowledge/graph')
    elapsed = time.time() - start

    if status == 200:
        nodes = len(resp.get('nodes', []))
        links = len(resp.get('links', []))
        print(f"  [PASS] 响应时间: {elapsed:.2f}s")
        print(f"        节点数: {nodes}, 链接数: {links}")
        if elapsed < 2.0:
            print(f"  [PASS] 性能达标 (<2s)")
            return True
        else:
            print(f"  [WARN] 性能未达标 (>{elapsed:.2f}s)")
            return False
    else:
        print(f"  [FAIL] /api/knowledge/graph 返回 {status}: {resp}")
        return False


def test_task_feedback_event_type():
    """测试 Bug #5: /api/task-feedback event_type"""
    print("\n[测试] /api/task-feedback POST event_type")

    # 先获取一个任务
    status, tasks = api_get('/api/tasks')
    if not status or not tasks or len(tasks) == 0:
        print("  无法获取任务列表")
        return False

    task = tasks[0]
    task_id = task['id']

    # 测试合法的 event_type
    valid_types = [
        'skip_task', 'finish_early', 'finish_on_time',
        'timer_timeout_unfinished', 'abandon_task'
    ]

    for event_type in valid_types:
        status, resp = api_post('/api/task-feedback', {
            'task_id': task_id,
            'event_type': event_type,
            'reason_category': 'other',
            'reason_detail': '测试'
        })

        if status == 201:
            print(f"  [PASS] event_type='{event_type}' 合法，返回 201")
            return True
        else:
            print(f"  [FAIL] event_type='{event_type}' 返回 {status}: {resp}")
            return False


def main():
    print("=" * 60)
    print("API 修复验证测试")
    print("=" * 60)

    results = {}

    # 测试 1: PUT task
    results['PUT /api/tasks'] = test_put_task()

    # 测试 2: POST tag
    results['POST /api/tags'] = test_create_tag()

    # 测试 3: knowledge graph
    results['/api/knowledge/graph'] = test_knowledge_graph_performance()

    # 测试 4: task-feedback
    results['/api/task-feedback'] = test_task_feedback_event_type()

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n通过: {passed}/{total}")


if __name__ == '__main__':
    main()
