"""P1-Stable-1 项目可迁移性检查

用法:
  python scripts/check_portability.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES = []
WARNINGS = []

SKIP_DIRS = {'.venv', '.git', 'backups', '.run', '__pycache__', 'node_modules'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.db-journal', '.log'}
SCAN_EXTENSIONS = {'.py', '.bat', '.js', '.json', '.html', '.md', '.txt', '.toml', '.cfg', '.ini', '.yaml', '.yml'}

ABS_PATTERNS = [
    re.compile(r'[A-Za-z]:\\Users\\', re.I),
    re.compile(r'/Users/'),
    re.compile(r'/home/'),
]


def fail(msg):
    FAILURES.append(msg)
    text = f'[FAIL] {msg}'
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('gbk', errors='replace').decode('gbk'))


def warn(msg):
    WARNINGS.append(msg)
    print(f'[WARN] {msg}')


def ok(msg):
    print(f'[PASS] {msg}')


def is_portable_path(value):
    if not isinstance(value, str) or not value.strip():
        return True
    v = value.strip().replace('\\', '/')
    for pat in ABS_PATTERNS:
        if pat.search(value):
            return False
    if re.match(r'^[A-Za-z]:/', v) and not v.startswith('//'):
        return False
    return True


def scan_absolute_paths():
    hits = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('backups/') or rel.startswith('docs/') or rel.startswith('ai_workspace/'):
            continue
        if rel == 'README.md':
            continue
        if rel == 'scripts/check_portability.py':
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if '.venv' in line and ('VIRTUAL_ENV' in line or 'Scripts\\activate' in line):
                continue
            for pat in ABS_PATTERNS:
                if pat.search(line):
                    hits.append(f'{rel}:{i}: {line.strip()[:120]}')
                    break
    if hits:
        for h in hits[:20]:
            fail(f'absolute path: {h}')
        if len(hits) > 20:
            fail(f'absolute path: ... and {len(hits) - 20} more')
    else:
        ok('no hardcoded absolute paths in project source')


def check_required_paths():
    required = [
        ('data/task_publisher.db', True),
        ('src/notes/vault', False),
        ('src/notes/prompts', False),
        ('static/app.js', True),
        ('index.html', True),
        ('config/config.json', True),
        ('scripts/start_web_safe.bat', True),
        ('scripts/stop_web_safe.bat', True),
        ('ai_workspace/README.md', True),
    ]
    for rel, is_file in required:
        p = ROOT / rel.replace('/', '\\') if sys.platform == 'win32' else ROOT / rel
        if is_file:
            if p.is_file():
                ok(f'exists file: {rel}')
            else:
                fail(f'missing file: {rel}')
        else:
            if p.is_dir():
                ok(f'exists dir: {rel}')
            else:
                fail(f'missing dir: {rel}')


def check_config():
    cfg_path = ROOT / 'config' / 'config.json'
    try:
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        fail(f'config.json unreadable: {e}')
        return
    notes = cfg.get('notes_directory') or cfg.get('obsidian', {}).get('notes_directory', '')
    vault = cfg.get('vault_path') or cfg.get('obsidian', {}).get('vault_path', '')
    db = cfg.get('database', {}).get('task_db_path', '')
    for label, val in [('notes_directory', notes), ('vault_path', vault), ('task_db_path', db)]:
        if is_portable_path(val):
            ok(f'config {label} is portable: {val}')
        else:
            fail(f'config {label} is absolute: {val}')


def check_index_app_js():
    html = (ROOT / 'index.html').read_text(encoding='utf-8', errors='ignore')
    m = re.search(r'src="/static/app\.js(\?v=\d+)?"', html)
    if not m:
        fail('index.html missing /static/app.js reference')
        return
    ok('index.html references static/app.js')
    if not (ROOT / 'static' / 'app.js').is_file():
        fail('static/app.js missing on disk')


def check_bat_relative():
    bats = list((ROOT / 'scripts').glob('*.bat')) + [ROOT / '启动学习工具.bat']
    for bat in bats:
        if not bat.is_file():
            continue
        text = bat.read_text(encoding='utf-8', errors='ignore')
        rel = bat.relative_to(ROOT).as_posix()
        if '%~dp0' in text or 'cd /d "%~dp0' in text:
            ok(f'bat uses script dir: {rel}')
        else:
            warn(f'bat may not anchor to script dir: {rel}')


def main():
    print('=== P1-Stable-1 Portability Check ===')
    check_required_paths()
    check_config()
    check_index_app_js()
    check_bat_relative()
    scan_absolute_paths()

    if WARNINGS:
        print(f'\nWarnings ({len(WARNINGS)}):')
        for w in WARNINGS:
            print(' ', w)

    if FAILURES:
        print(f'\nFAILED ({len(FAILURES)}):')
        for f in FAILURES:
            try:
                print(' ', f)
            except UnicodeEncodeError:
                print(' ', str(f).encode('gbk', errors='replace').decode('gbk'))
        return 1

    print('\nALL PORTABILITY CHECKS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
