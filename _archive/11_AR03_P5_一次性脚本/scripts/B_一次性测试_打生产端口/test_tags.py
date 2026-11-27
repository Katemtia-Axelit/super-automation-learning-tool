"""直接测试 POST /api/tags"""
import urllib.request
import json

url = 'http://127.0.0.1:5000/api/tags'
body = json.dumps({'name': '验证测试标签2'}).encode('utf-8')
req = urllib.request.Request(url, data=body, headers={
    'Content-Type': 'application/json'
}, method='POST')

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f'Status: {resp.status}')
        print(f'Response: {resp.read().decode("utf-8")}')
except urllib.error.HTTPError as e:
    print(f'HTTPError: {e.code}')
    print(f'Response: {e.read().decode("utf-8")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
