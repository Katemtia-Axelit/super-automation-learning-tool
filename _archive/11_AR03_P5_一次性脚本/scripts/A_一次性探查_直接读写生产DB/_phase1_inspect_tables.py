import re
path = r'server/backend_api.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Find CREATE TABLE patterns
ct = re.findall(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)', text, re.IGNORECASE)
print('CREATE TABLE count:', len(ct))
for c in ct:
    print(' ', c)

print('---')
# Also find any function defs at top-level
fns = re.findall(r'\ndef\s+(\w+)\(', text)
print('All top-level functions:', len(fns))
for f in fns:
    print(' ', f)