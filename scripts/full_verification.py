"""全面 API 端点验证测试

验证所有关键端点，确保修复后没有回归
"""

import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:5000"


def api_request(method, path, data=None):
    """发送 API 请求"""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode('utf-8') if data else None
    headers = {'Content-Type': 'application/json'}
    if body:
        headers['Content-Length'] = str(len(body))

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except:
            return e.code, e.reason
    except Exception as e:
        return None, str(e)


def test_endpoint(method, path, data=None, expected_status=None, description=""):
    """测试单个端点"""
    status, resp = api_request(method, path, data)

    passed = expected_status is None or status == expected_status

    result = "[PASS]" if passed else "[FAIL]"
    status_str = f" {status}" if status else "N/A"
    expected_str = f" (期望 {expected_status})" if expected_status else ""

    print(f"  {result} {method} {path}{status_str}{expected_str}")
    if not passed:
        print(f"       实际响应: {resp}")

    return passed, status, resp


def main():
    print("=" * 70)
    print("全面 API 端点验证")
    print("=" * 70)

    results = {}

    # 1. 健康检查
    print("\n[1] 健康检查")
    passed, _, _ = test_endpoint("GET", "/api/health", expected_status=200)
    results['健康检查'] = passed

    # 2. 任务管理
    print("\n[2] 任务管理")

    # GET /api/tasks
    passed, _, resp = test_endpoint("GET", "/api/tasks", expected_status=200)
    results['GET /api/tasks'] = passed

    # POST /api/tasks
    passed, create_status, create_resp = test_endpoint("POST", "/api/tasks", {
        'name': '验证测试任务',
        'category': 'daily',
        'priority': 5
    }, expected_status=201)
    results['POST /api/tasks'] = passed

    # 获取有效任务 ID
    test_task_id = None
    if isinstance(resp, list) and len(resp) > 0:
        test_task_id = resp[0]['id']
    elif isinstance(create_resp, dict) and 'id' in create_resp:
        test_task_id = create_resp['id']

    # GET /api/tasks/{id}
    if test_task_id:
        passed, _, _ = test_endpoint(f"GET", f"/api/tasks/{test_task_id}", expected_status=200)
        results['GET /api/tasks/{id}'] = passed

        # PUT /api/tasks/{id} - 关键修复
        passed, _, _ = test_endpoint("PUT", f"/api/tasks/{test_task_id}", {
            'name': '验证更新',
            'priority': 6
        }, expected_status=200)
        results['PUT /api/tasks/{id}'] = passed

        # DELETE /api/tasks/{id}
        passed, _, _ = test_endpoint("DELETE", f"/api/tasks/{test_task_id}", expected_status=200)
        results['DELETE /api/tasks/{id}'] = passed
    else:
        print("  [SKIP] 无法获取有效任务 ID")
        results['GET /api/tasks/{id}'] = False
        results['PUT /api/tasks/{id}'] = False
        results['DELETE /api/tasks/{id}'] = False

    # 3. 标签管理 - 关键修复
    print("\n[3] 标签管理")

    # GET /api/tags
    passed, _, _ = test_endpoint("GET", "/api/tags", expected_status=200)
    results['GET /api/tags'] = passed

    # POST /api/tags - 关键修复
    test_name = f"验证标签_{int(time.time())}"
    passed, status, resp = test_endpoint("POST", "/api/tags", {
        'name': test_name
    }, expected_status=201)
    results['POST /api/tags'] = passed

    # POST /api/tags (已存在)
    passed, status, _ = test_endpoint("POST", "/api/tags", {
        'name': test_name
    }, expected_status=200)
    results['POST /api/tags (已存在)'] = passed

    # 4. 知识图谱 - 性能修复
    print("\n[4] 知识图谱")

    start = time.time()
    result = api_request("GET", "/api/knowledge/graph")
    elapsed = time.time() - start

    if isinstance(result, tuple) and len(result) == 2:
        status, resp = result
        passed = status == 200 and elapsed < 2.0
    else:
        passed = False
        status = "N/A"

    passed = status == 200 and elapsed < 2.0
    result_str = "[PASS]" if passed else "[FAIL]"
    print(f"  {result_str} GET /api/knowledge/graph {status} (耗时 {elapsed:.2f}s)")
    results['/api/knowledge/graph'] = passed

    # 5. 任务反馈 - event_type 修复
    print("\n[5] 任务反馈")

    # 获取有效任务 ID 用于反馈测试
    feedback_task_id = test_task_id if test_task_id else 1

    # POST /api/task-feedback - event_type 验证
    passed, status, _ = test_endpoint("POST", "/api/task-feedback", {
        'task_id': feedback_task_id,
        'event_type': 'skip_task',
        'reason_category': 'other',
        'reason_detail': '验证测试'
    }, expected_status=201)
    results['POST /api/task-feedback'] = passed

    # GET /api/task-feedback
    passed, _, _ = test_endpoint("GET", "/api/task-feedback", expected_status=200)
    results['GET /api/task-feedback'] = passed

    # 6. 抽卡系统
    print("\n[6] 抽卡系统")

    passed, _, _ = test_endpoint("GET", "/api/gacha/pools", expected_status=200)
    results['GET /api/gacha/pools'] = passed

    passed, _, _ = test_endpoint("GET", "/api/gacha/statistics", expected_status=200)
    results['GET /api/gacha/statistics'] = passed

    # 7. 计时器
    print("\n[7] 计时器")

    passed, _, _ = test_endpoint("POST", "/api/timer/start", {
        'task_id': 1,
        'planned_minutes': 30
    }, expected_status=200)
    results['POST /api/timer/start'] = passed

    passed, _, _ = test_endpoint("GET", "/api/timer/active", expected_status=200)
    results['GET /api/timer/active'] = passed

    # 8. 其他重要端点
    print("\n[8] 其他重要端点")

    passed, _, _ = test_endpoint("GET", "/api/schedule/slots", expected_status=200)
    results['GET /api/schedule/slots'] = passed

    passed, _, _ = test_endpoint("GET", "/api/state/daily-tone", expected_status=200)
    results['GET /api/state/daily-tone'] = passed

    passed, _, _ = test_endpoint("GET", "/api/prompts", expected_status=200)
    results['GET /api/prompts'] = passed

    passed, _, _ = test_endpoint("GET", "/api/dependencies", expected_status=200)
    results['GET /api/dependencies'] = passed

    passed, _, _ = test_endpoint("GET", "/api/export", expected_status=200)
    results['GET /api/export'] = passed

    # 汇总
    print("\n" + "=" * 70)
    print("验证结果汇总")
    print("=" * 70)

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    print("\n" + "=" * 70)
    print(f"通过: {passed_count}/{total_count}")
    print("=" * 70)

    return passed_count == total_count


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
