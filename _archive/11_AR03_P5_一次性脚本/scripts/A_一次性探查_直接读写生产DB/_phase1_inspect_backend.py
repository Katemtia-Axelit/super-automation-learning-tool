import re
path = r'server/backend_api.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all @app.route
routes = []
for i, line in enumerate(lines, 1):
    if re.search(r'@app\.(route|get|post|put|delete|patch)', line):
        routes.append((i, line.rstrip()))
print('@app.route count:', len(routes))
for ln, t in routes:
    print(f'  L{ln}: {t}')

print('---')
# Find ensure_* function defs
ens = []
for i, line in enumerate(lines, 1):
    m = re.match(r'\s*def\s+(ensure_\w+)', line)
    if m:
        ens.append((i, m.group(1)))
print('ensure_* functions:', len(ens))
for ln, name in ens:
    print(f'  L{ln}: {name}')