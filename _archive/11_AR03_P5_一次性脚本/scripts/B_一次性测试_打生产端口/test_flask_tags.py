"""直接测试 Flask 应用中的 tags 端点"""
import sys
sys.path.insert(0, '.')

from server.backend_api import app

# 创建测试客户端
with app.test_client() as client:
    # 测试1: 创建新标签
    print("=== 测试1: 创建新标签 ===")
    response = client.post('/api/tags',
                          json={'name': '直接测试标签_001'},
                          content_type='application/json')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.get_json()}")
    print(f"Headers: {dict(response.headers)}")

    # 测试2: 创建已存在的标签
    print("\n=== 测试2: 创建已存在的标签 ===")
    response2 = client.post('/api/tags',
                           json={'name': '直接测试标签_001'},
                           content_type='application/json')
    print(f"Status: {response2.status_code}")
    print(f"Response: {response2.get_json()}")

    # 测试3: 空名称
    print("\n=== 测试3: 空名称 ===")
    response3 = client.post('/api/tags',
                           json={'name': ''},
                           content_type='application/json')
    print(f"Status: {response3.status_code}")
    print(f"Response: {response3.get_json()}")
