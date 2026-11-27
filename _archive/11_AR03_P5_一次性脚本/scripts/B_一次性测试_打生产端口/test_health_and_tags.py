"""直接测试健康检查端点"""
import urllib.request
import json

url = 'http://127.0.0.1:5000/api/health'
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(f'Status: {resp.status}')
        print(f'Response: {resp.read().decode("utf-8")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')

# 测试 tags
print("\n--- Testing POST /api/tags ---")
url2 = 'http://127.0.0.1:5000/api/tags'
body = json.dumps({'name': '新测试标签_final'}).encode('utf-8')
req2 = urllib.request.Request(url2, data=body, headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req2, timeout=5) as resp:
        print(f'Status: {resp.status}')
        print(f'Response: {resp.read().decode("utf-8")}')
except urllib.error.HTTPError as e:
    print(f'HTTPError: {e.code}')
    print(f'Response: {e.read().decode("utf-8")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
