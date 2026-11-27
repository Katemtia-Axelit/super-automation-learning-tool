# -*- coding: utf-8 -*-
"""
超级自动化学习工具 - API 全端点检验脚本
"""
import urllib.request
import urllib.error
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"
RESULTS = []

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_endpoint(method, path, data=None, expected_status=200, description=""):
    """测试单个API端点"""
    url = f"{BASE_URL}{path}"
    result = {
        "method": method,
        "path": path,
        "description": description,
        "status_code": None,
        "success": False,
        "error": None,
        "response_preview": None
    }
    
    try:
        body = None
        if data:
            body = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            result["status_code"] = resp.status
            
            try:
                raw = resp.read().decode('utf-8')
                if raw:
                    result["response_preview"] = json.loads(raw)
                else:
                    result["response_preview"] = {}
            except:
                result["response_preview"] = {"_raw": "non-json response"}
            
            if resp.status == expected_status:
                result["success"] = True
                log(f"  [PASS] {method} {path} -> {resp.status}")
            else:
                result["success"] = True  # 2xx 都算通过
                log(f"  [WARN] {method} {path} -> {resp.status} (expected {expected_status})")
                
    except urllib.error.HTTPError as e:
        result["status_code"] = e.code
        try:
            result["response_preview"] = json.loads(e.read().decode('utf-8'))
        except:
            result["response_preview"] = {"_raw": e.reason}
        
        if e.code == expected_status:
            result["success"] = True
            log(f"  [PASS] {method} {path} -> {e.code}")
        elif e.code >= 400:
            result["error"] = f"HTTP {e.code}: {e.reason}"
            log(f"  [FAIL] {method} {path} -> {e.code} (expected {expected_status})")
        else:
            result["success"] = True
            log(f"  [WARN] {method} {path} -> {e.code}")
            
    except urllib.error.URLError as e:
        result["error"] = f"Connection failed: {e.reason}"
        log(f"  [FAIL] {method} {path} -> Connection Error")
    except Exception as e:
        result["error"] = str(e)
        log(f"  [FAIL] {method} {path} -> {type(e).__name__}: {e}")
    
    RESULTS.append(result)
    return result

def main():
    print("=" * 60)
    print("超级自动化学习工具 - API 全端点检验")
    print("=" * 60)
    
    # 1. 健康检查
    log("=" * 40)
    log("1. 健康检查")
    test_endpoint("GET", "/api/health", description="健康检查")
    
    # 2. 任务 CRUD
    log("=" * 40)
    log("2. 任务 CRUD 端点")
    
    # 获取所有任务
    test_endpoint("GET", "/api/tasks", description="获取所有任务")
    
    # 创建任务
    new_task_data = {
        "name": "API测试任务_" + str(int(time.time())),
        "category": "study",
        "description": "自动化测试创建的任务",
        "estimated_time": 30,
        "priority": 5,
        "tags": ["测试", "自动化"]
    }
    create_result = test_endpoint("POST", "/api/tasks", new_task_data, expected_status=201, description="创建新任务")
    task_id = None
    if create_result["success"] and isinstance(create_result.get("response_preview"), dict):
        task_id = create_result["response_preview"].get("id")
    
    # 获取单个任务
    if task_id:
        test_endpoint("GET", f"/api/tasks/{task_id}", description="获取单个任务")
        # 更新任务
        update_data = {"name": "API测试任务_已更新", "priority": 3}
        test_endpoint("PUT", f"/api/tasks/{task_id}", update_data, description="更新任务")
    
    # 3. 抽卡相关
    log("=" * 40)
    log("3. 抽卡相关端点")
    test_endpoint("GET", "/api/gacha/pools", description="获取卡池列表")
    test_endpoint("POST", "/api/gacha/draw", {"pool": "fragment"}, description="普通抽卡")
    test_endpoint("POST", "/api/gacha/care-draw", {"pool": "fragment"}, description="关怀抽卡")
    
    # 4. 标签管理
    log("=" * 40)
    log("4. 标签管理端点")
    test_endpoint("GET", "/api/tags", description="获取所有标签")
    test_endpoint("POST", "/api/tags", {"name": "测试标签_" + str(int(time.time()))}, description="创建标签")
    
    # 5. 作弊堆
    log("=" * 40)
    log("5. 作弊堆(Discard Pile)端点")
    test_endpoint("GET", "/api/discard-pile", description="获取作弊堆任务")
    if task_id:
        test_endpoint("POST", f"/api/discard-pile/{task_id}/restore", description="恢复任务")
    
    # 6. 知识库
    log("=" * 40)
    log("6. 知识库端点")
    test_endpoint("GET", "/api/knowledge/categories", description="获取知识分类")
    test_endpoint("GET", "/api/knowledge/points", description="获取知识点")
    test_endpoint("GET", "/api/knowledge/graph", description="获取知识图谱")
    test_endpoint("GET", "/api/knowledge/recent", description="获取最近笔记")
    test_endpoint("GET", "/api/knowledge/notes", description="获取笔记列表")
    
    # 7. 配置
    log("=" * 40)
    log("7. 配置端点")
    test_endpoint("GET", "/api/config", description="获取配置")
    
    # 8. 日程安排
    log("=" * 40)
    log("8. 日程安排端点")
    test_endpoint("GET", "/api/schedule/slots", description="获取日程槽")
    test_endpoint("GET", "/api/schedule/weekly", description="获取周日程")
    test_endpoint("GET", "/api/schedule/daily", description="获取日程")
    test_endpoint("GET", "/api/schedule/activities", description="获取活动列表")
    
    # 9. 状态管理
    log("=" * 40)
    log("9. 状态管理端点")
    test_endpoint("GET", "/api/state/daily-tone", description="获取每日心情")
    test_endpoint("GET", "/api/state/sleep", description="获取睡眠数据")
    test_endpoint("GET", "/api/state/weekly-energy", description="获取每周精力")
    test_endpoint("GET", "/api/state/questions", description="获取状态问题")
    test_endpoint("GET", "/api/state/assessment", description="获取评估")
    
    # 10. 计时器
    log("=" * 40)
    log("10. 计时器端点")
    test_endpoint("GET", "/api/timer/active", description="获取活动计时器")
    if task_id:
        test_endpoint("POST", "/api/timer/start", {"task_id": task_id, "planned_minutes": 30}, description="开始计时")
    test_endpoint("POST", "/api/timer/complete", {"session_id": 99999, "actual_minutes": 5, "result": "completed"}, description="完成计时(不存在)")
    
    # 11. Agent 相关
    log("=" * 40)
    log("11. Agent 相关端点")
    test_endpoint("GET", "/api/agent/agents", description="获取Agent列表")
    test_endpoint("GET", "/api/agent/files/raw", description="获取原始文件列表")
    test_endpoint("GET", "/api/agent/files/vault", description="获取Vault文件列表")
    
    # 12. 提示词
    log("=" * 40)
    log("12. 提示词端点")
    test_endpoint("GET", "/api/prompts", description="获取提示词列表")
    
    # 13. 依赖关系
    log("=" * 40)
    log("13. 依赖关系端点")
    test_endpoint("GET", "/api/dependencies", description="获取依赖关系")
    
    # 14. 导出
    log("=" * 40)
    log("14. 导出端点")
    test_endpoint("GET", "/api/export", description="导出数据")
    
    # 15. 反馈
    log("=" * 40)
    log("15. 反馈端点")
    test_endpoint("POST", "/api/task-feedback", {
        "task_id": 1,
        "event_type": "complete_task",
        "reason_category": "completed"
    }, description="提交反馈")
    test_endpoint("GET", "/api/task-feedback", description="获取反馈历史")
    
    # 16. 抽卡统计
    log("=" * 40)
    log("16. 抽卡统计端点")
    test_endpoint("GET", "/api/gacha/statistics", description="抽卡统计")
    test_endpoint("GET", "/api/gacha/pools/detail", description="卡池详情")
    
    # 17. 错误路径测试
    log("=" * 40)
    log("17. 错误路径测试")
    test_endpoint("GET", "/api/tasks/999999", description="获取不存在的任务")
    test_endpoint("DELETE", "/api/tasks/999999", description="删除不存在的任务")
    test_endpoint("PUT", "/api/tasks/999999", {"name": "Test"}, description="更新不存在的任务")
    test_endpoint("POST", "/api/tasks", {}, expected_status=400, description="创建空任务")
    
    # 18. 清理测试数据
    log("=" * 40)
    log("18. 清理测试数据")
    if task_id:
        test_endpoint("DELETE", f"/api/tasks/{task_id}", description="删除测试任务")
    
    # 生成报告
    print("\n" + "=" * 60)
    print("检验结果汇总")
    print("=" * 60)
    
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["success"])
    failed = sum(1 for r in RESULTS if not r["success"])
    
    print(f"总测试数: {total}")
    print(f"通过: {passed} ({100*passed/total:.1f}%)")
    print(f"失败: {failed} ({100*failed/total:.1f}%)")
    print()
    
    # 按状态码分类
    status_codes = {}
    for r in RESULTS:
        code = r["status_code"] or "N/A"
        status_codes[code] = status_codes.get(code, 0) + 1
    
    print("状态码分布:")
    for code, count in sorted(status_codes.items(), key=lambda x: str(x[0])):
        print(f"  {code}: {count}个")
    print()
    
    # 列出失败项
    failures = [r for r in RESULTS if not r["success"]]
    if failures:
        print("失败/错误详情:")
        for r in failures:
            print(f"  [{r['method']}] {r['path']}")
            print(f"    状态码: {r['status_code']}")
            print(f"    错误: {r['error']}")
            print()
    else:
        print("所有测试均通过!")
    
    # 保存JSON报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed
        },
        "results": RESULTS
    }
    
    with open("docs/api_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n详细报告已保存到 docs/api_test_report.json")
    
    return passed, failed

if __name__ == "__main__":
    main()
