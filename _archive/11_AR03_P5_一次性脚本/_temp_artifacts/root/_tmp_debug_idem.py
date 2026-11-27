import sys, sqlite3
sys.path.insert(0, r'.')
from server.schema import ensure_all

conn = sqlite3.connect(':memory:')
ensure_all(conn)


def snap(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    cols = {t: {r[1] for r in conn.execute('PRAGMA table_info(%s)' % t)}
            for t in sorted(tables)}
    idx = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")}
    return tables, cols, idx


a = snap(conn)
ensure_all(conn)
b = snap(conn)
print('tables diff:', a[0] ^ b[0])
for t in sorted(set(a[1]) | set(b[1])):
    if a[1].get(t) != b[1].get(t):
        print('COL DIFF', t)
        print('   before:', a[1].get(t))
        print('   after :', b[1].get(t))
print('idx diff:', a[2] ^ b[2])
