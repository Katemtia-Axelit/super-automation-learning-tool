"""全面诊断前端问题 - 模拟浏览器行为"""
import urllib.request, json, re, subprocess, sys, os, time

ROOT = os.path.dirname(os.path.abspath(__file__))

# 启动服务器
print("启动服务器...")
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, 'server', 'backend_api.py')],
                        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(4)

try:
    # 1. 检查页面
    r = urllib.request.urlopen('http://localhost:5000/', timeout=5)
    html = r.read().decode('utf-8')
    print(f'页面: {len(html)} bytes, Content-Type: {r.headers.get("Content-Type", "?")}')

    # 2. 提取并分析 JS
    m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    if not m:
        print("ERROR: 找不到 script 块!")
        sys.exit(1)
    js = m.group(1)
    lines = js.split('\n')
    
    # 3. 检查基础结构
    errors = []
    
    # 检查所有 onclick 函数是否存在
    onclick_funcs = set(re.findall(r'onclick="([^(]+)\(', html))
    defined_funcs = set(re.findall(r'(?:async )?function (\w+)', js))
    
    print(f'\n===== onclick 函数检查 ({len(onclick_funcs)} 个) =====')
    for f in sorted(onclick_funcs):
        if f in defined_funcs:
            print(f'  OK  {f}')
        elif f.startswith('this.') or f.startswith('return') or f in ('if','clearTimeout','setTimeout','alert','confirm','prompt'):
            pass  # 内置函数
        else:
            print(f'  MISSING {f}')
            errors.append(f'onclick函数 {f} 未定义')
    
    # 4. 检查所有 getElementById 引用的 DOM 是否存在于 HTML
    js_ids = set(re.findall(r"getElementById\('([^']+)'\)", js))
    html_ids = set(re.findall(r'id="([^"]+)"', html))
    
    print(f'\n===== DOM ID 检查 =====')
    missing_ids = js_ids - html_ids
    for mid in sorted(missing_ids):
        # 排除动态创建的
        if mid in ('replaceReasonBar',):
            continue
        print(f'  MISSING DOM: {mid}')
        errors.append(f'DOM元素 {mid} 不存在于HTML中')
    
    for mid in sorted(js_ids & html_ids):
        count = html.count(f'id="{mid}"')
        if count == 1:
            pass  # OK
        elif count > 1:
            print(f'  DUPLICATE: {mid} (出现{count}次)')
            errors.append(f'DOM元素 {mid} 重复{count}次')
    
    # 5. 检查 HTML 结构
    print(f'\n===== HTML 结构检查 =====')
    for tag, close in [('<html', '</html>'), ('<head', '</head>'), ('<body', '</body>'), 
                        ('<style', '</style>'), ('<script', '</script>'), ('<div', '</div>')]:
        opens = len(re.findall(f'{tag}[>\s]', html))
        closes = html.count(close)
        status = 'OK' if opens == closes else f'ERR ({opens}/{closes})'
        print(f'  {tag}: {status}')
    
    # 6. JS 语法快速检查
    print(f'\n===== JS 语法检查 =====')
    print(f'  括号: () = {js.count("(")}/{js.count(")")}, {{}} = {js.count("{")}/{js.count("}")}, [] = {js.count("[")}/{js.count("]")}')
    if js.count("(") != js.count(")"): errors.append('圆括号不匹配')
    if js.count("{") != js.count("}"): errors.append('花括号不匹配')
    if js.count("[") != js.count("]"): errors.append('方括号不匹配')
    
    # 7. 检查是否有 CSS pointer-events: none
    pointer_events = re.findall(r'pointer-events\s*:\s*(\w+)', html)
    if pointer_events:
        print(f'\n===== CSS pointer-events 检查 =====')
        for pe in pointer_events:
            if pe == 'none':
                # 找上下文
                idx = html.find(f'pointer-events:{pe}')
                ctx = html[max(0,idx-100):idx+100]
                print(f'  WARNING: pointer-events: none 在: ...{ctx}...')
                errors.append('CSS pointer-events: none 可能阻止点击')
    
    # 8. 检查 z-index 覆盖
    z_indices = re.findall(r'z-index\s*:\s*(\d+)', html)
    print(f'\n===== Z-index 检查 =====')
    for z in z_indices:
        idx = html.find(f'z-index:{z}')
        ctx = html[max(0,idx-30):idx+50].strip()
        print(f'  z-index:{z} -> {ctx[:80]}')
    
    # 9. 测试API
    print(f'\n===== API 测试 =====')
    apis = ['/api/health', '/api/tasks?unlocked_only=false', '/api/gacha/statistics']
    for api_url in apis:
        try:
            urllib.request.urlopen(f'http://localhost:5000{api_url}', timeout=3)
            print(f'  OK {api_url}')
        except Exception as e:
            print(f'  FAIL {api_url}: {e}')
            errors.append(f'API {api_url} 失败')
    
    # 10. 总结
    print(f'\n===== 总结 =====')
    if errors:
        print(f'发现 {len(errors)} 个问题:')
        for e in errors:
            print(f'  - {e}')
    else:
        print('未发现结构性问题')
        print()
        print('如果按钮仍无反应，可能的原因:')
        print('  1. 浏览器扩展阻止了内联事件 (onclick=...)')
        print('  2. 浏览器缓存了旧版本 (尝试无痕模式)')
        print('  3. JavaScript 在特定浏览器上有兼容性问题')
    
except Exception as e:
    print(f'诊断失败: {e}')
    import traceback
    traceback.print_exc()
finally:
    proc.terminate()
    proc.wait()
