"""测试 Flask 测试客户端 with make_response"""
import sys
sys.path.insert(0, '.')

from server.backend_api import app

# 创建测试客户端
with app.test_client() as client:
    # 测试1: 创建新标签
    print("=== 测试1: 创建新标签 ===")
    response = client.post('/api/tags',
                          json={'name': 'TestTag_MakeResponse'},
                          content_type='application/json')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.get_json()}")
    print(f"Headers: {dict(response.headers)}")

    # 测试2: 创建已存在的标签
    print("\n=== 测试2: 创建已存在的标签 ===")
    response2 = client.post('/api/tags',
                           json={'name': 'TestTag_MakeResponse'},
                           content_type='application/json')
    print(f"Status: {response2.status_code}")
    print(f"Response: {response2.get_json()}")
