"""详细测试 HTTP 请求"""
import urllib.request
import json

url = 'http://127.0.0.1:5000/api/tags'

# 测试新标签
test_name = 'HTTP测试标签_' + str(int(__import__('time').time()))
body = json.dumps({'name': test_name}).encode('utf-8')

req = urllib.request.Request(url, data=body, headers={
    'Content-Type': 'application/json',
    'Content-Length': str(len(body))
}, method='POST')

print(f"Testing URL: {url}")
print(f"Request body: {body.decode('utf-8')}")
print()

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"SUCCESS!")
        print(f"Status: {resp.status}")
        print(f"Response headers: {dict(resp.headers)}")
        print(f"Response body: {resp.read().decode('utf-8')}")
except urllib.error.HTTPError as e:
    print(f"HTTPError!")
    print(f"Code: {e.code}")
    print(f"Reason: {e.reason}")
    print(f"Response headers: {dict(e.headers)}")
    print(f"Response body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
