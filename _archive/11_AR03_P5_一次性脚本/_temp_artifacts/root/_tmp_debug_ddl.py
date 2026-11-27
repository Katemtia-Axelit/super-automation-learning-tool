import ast
import re
import sys

sys.path.insert(0, r'.')
import importlib.util

spec = importlib.util.spec_from_file_location(
    "gate", r"scripts/check_schema_consistency.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

for rel in ("server/services/free_task_events.py",
            "server/services/free_task_session_ownership.py"):
    src = open(rel, encoding="utf-8").read()
    print("===", rel)
    print("consts:", gate._resolve_table_names(src))
    texts = gate._collect_sql_strings(src)
    for t in texts:
        if "CREATE TABLE" in t.upper():
            print("TEXT:", repr(t[:120]))
            print("matches:", [(m.group(0), m.group("name"), m.group("ph"))
                               for m in gate._CREATE_TABLE_RE.finditer(t)])
    print("found:", gate._find_created_tables(src))
