"""测试简单的文本响应"""
import sys
sys.path.insert(0, '.')

from server.backend_api import app

# 创建测试客户端
with app.test_client() as client:
    # 测试1: 简单文本响应
    print("=== 测试1: 简单文本响应 ===")
    response = client.post('/api/tags',
                          data='test',
                          content_type='application/json')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.data}")
