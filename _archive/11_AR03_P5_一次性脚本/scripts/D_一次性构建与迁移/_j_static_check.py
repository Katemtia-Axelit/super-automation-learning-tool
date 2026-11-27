import ast
import pathlib
import sys

root = pathlib.Path(r"D:\Axelit\.工作\trae\超级自动化学习工具")
files = [
    root / "server" / "schema" / "feedback.py",
    root / "tests" / "characterize" / "test_feedback_schema_migration.py",
]
ok = True
for f in files:
    try:
        src = f.read_text(encoding="utf-8")
        ast.parse(src, filename=str(f))
        print(f"OK {f.relative_to(root)}")
    except SyntaxError as exc:
        ok = False
        print(f"FAIL {f}: {exc}")
sys.exit(0 if ok else 1)