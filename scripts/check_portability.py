"""P1-Stable-1 项目可迁移性检查

用法:
  python scripts/check_portability.py
  python scripts/check_portability.py --json    # JSON 输出给门禁脚本消费

退出码:
  0 = PASS              无问题
  1 = FAIL              存在 BLOCKER
  2 = PASS_WITH_WARNINGS 仅有 WARNING/INFO
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES = []
WARNINGS = []
INFOS = []

SKIP_DIRS = {'.venv', '.git', 'backups', '.run', '__pycache__', 'node_modules'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.db-journal', '.log'}
SCAN_EXTENSIONS = {'.py', '.bat', '.js', '.json', '.html', '.md', '.txt', '.toml', '.cfg', '.ini', '.yaml', '.yml'}

HIT_BLOCKER = 'BLOCKER'
HIT_WARNING = 'WARNING'
HIT_INFO = 'INFO'

BLOCKER_PATTERNS = [
    (re.compile(r'(?:^|[^%A-Za-z])[A-Za-z]:\\\w+', re.I), 'WINDOWS_ABS'),
    (re.compile(r'(?<![%A-Za-z])[A-Za-z]:/[\w/]', re.I), 'WINDOWS_ABS_FWDSLASH'),
    (re.compile(r'(?<![.\w])\\\\[\w.-]+\\', re.I), 'UNC_PATH'),
    (re.compile(r'(?<!\w)/home/\w+', re.I), 'UNIX_HOME'),
    (re.compile(r'(?<!\w)/Users/\w+', re.I), 'UNIX_USERS'),
]

WARNING_PATTERNS = [
    (re.compile(r'\\AppData\\', re.I), 'APPDATA_DIR'),
    (re.compile(r'\\Desktop\\', re.I), 'DESKTOP_DIR'),
    (re.compile(r'\\Documents\\', re.I), 'DOCUMENTS_DIR'),
    (re.compile(r'(?<!\w)/opt/\w+', re.I), 'UNIX_OPT'),
    (re.compile(r'(?<!\w)/etc/\w+', re.I), 'UNIX_ETC'),
]

SUGGESTED_ACTIONS = {
    'WINDOWS_ABS':          '替换为 Path(__file__).resolve() 或 os.path.dirname(__file__) 动态定位',
    'WINDOWS_ABS_FWDSLASH': '替换为 Path(__file__).resolve() 或 os.path.dirname(__file__) 动态定位',
    'UNC_PATH':             '替换为本地相对路径或动态解析',
    'UNIX_HOME':            '替换为 Path(__file__).resolve() 动态定位项目根',
    'UNIX_USERS':           '替换为 Path(__file__).resolve() 动态定位项目根',
    'APPDATA_DIR':          '检查是否使用了用户级 AppData 目录，建议改用项目内路径',
    'DESKTOP_DIR':          '检查是否依赖桌面路径，建议改用项目内 data/ 目录',
    'DOCUMENTS_DIR':        '检查是否依赖文档目录，建议改用项目内路径',
    'UNIX_OPT':             '确认是否为跨平台可用的软件路径',
    'UNIX_ETC':             '确认是否为跨平台可用的配置路径',
}


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
    v = value.strip()
    if re.match(r'^[A-Za-z]:[\\/]', v):
        return False
    if re.match(r'^\\\\', v):
        return False
    if re.match(r'^(?:/home/|/Users/|/opt/)', v.replace('\\', '/')):
        return False
    return True


def _classify_line(line):
    for pat, hit_type in BLOCKER_PATTERNS:
        m = pat.search(line)
        if m:
            return (HIT_BLOCKER, hit_type, m.group(0).strip()[:100])
    for pat, hit_type in WARNING_PATTERNS:
        m = pat.search(line)
        if m:
            return (HIT_WARNING, hit_type, m.group(0).strip()[:100])
    return None


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
        if rel == 'README.md' or rel == 'scripts/check_portability.py':
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if '.venv' in line and ('VIRTUAL_ENV' in line or 'Scripts\\activate' in line):
                continue
            result = _classify_line(line)
            if result:
                severity, hit_type, snippet = result
                action = SUGGESTED_ACTIONS.get(hit_type, '人工检查')
                hits.append({
                    'file': rel,
                    'line': i,
                    'severity': severity,
                    'type': hit_type,
                    'snippet': snippet,
                    'action': action,
                })

    if not hits:
        ok('no hardcoded absolute paths detected in project source')
        return

    blocker_hits = [h for h in hits if h['severity'] == HIT_BLOCKER]
    warning_hits = [h for h in hits if h['severity'] == HIT_WARNING]
    info_hits = [h for h in hits if h['severity'] == HIT_INFO]

    if blocker_hits:
        print(f'\n  [BLOCKER] {len(blocker_hits)} hardcoded absolute path(s):')
        for h in blocker_hits:
            _print_hit(h)
        for h in blocker_hits:
            fail(f'{h["file"]}:{h["line"]} [{h["type"]}] {h["snippet"][:60]}')

    if warning_hits:
        print(f'\n  [WARNING] {len(warning_hits)} suspicious path(s):')
        for h in warning_hits:
            _print_hit(h)
        for h in warning_hits:
            warn(f'{h["file"]}:{h["line"]} [{h["type"]}] {h["snippet"][:60]}')

    if info_hits:
        print(f'\n  [INFO] {len(info_hits)} informational:')
        for h in info_hits:
            _print_hit(h)

    print(f'\n  Scan summary: BLOCKER={len(blocker_hits)} WARNING={len(warning_hits)} INFO={len(info_hits)} total={len(hits)}')


def _print_hit(h):
    text = f'    {h["file"]}:{h["line"]}  [{h["severity"]}/{h["type"]}]  {h["snippet"]}'
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('gbk', errors='replace').decode('gbk'))
    print(f'          -> {h["action"]}')


def check_venv_validity():
    venv_python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if not venv_python.is_file():
        fail('.venv/Scripts/python.exe not found — run: python -m venv .venv')
        return

    cfg_path = ROOT / '.venv' / 'pyvenv.cfg'
    if cfg_path.is_file():
        try:
            cfg = cfg_path.read_text(encoding='utf-8', errors='ignore')
            m = re.search(r'home\s*=\s*(.+)', cfg)
            if m:
                home = m.group(1).strip()
                if not Path(home).exists():
                    fail(f'.venv pyvenv.cfg home path does not exist: {home} — delete .venv and recreate')
                    return
        except OSError:
            pass

    try:
        import subprocess
        r = subprocess.run([str(venv_python), '--version'], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            fail('.venv python.exe does not run — delete .venv and recreate')
        else:
            ok(f'.venv python valid: {r.stdout.strip()}')
    except Exception:
        fail('.venv python.exe cannot execute — delete .venv and recreate')


def check_backend_entry():
    backend_path = ROOT / 'server' / 'backend_api.py'
    if not backend_path.is_file():
        fail(f'server/backend_api.py not found at: {backend_path}')
        return
    ok(f'server/backend_api.py accessible at: {backend_path.relative_to(ROOT).as_posix()}')

    try:
        import py_compile
        py_compile.compile(str(backend_path), doraise=True)
        ok('server/backend_api.py syntax OK')
    except py_compile.PyCompileError as exc:
        fail(f'server/backend_api.py syntax error — {exc}')


def check_python_version():
    min_ver = (3, 8)
    v = sys.version_info[:3]
    if v < min_ver:
        fail(f'Python {v[0]}.{v[1]}.{v[2]} is too old (need 3.8+) — install from https://www.python.org/downloads/')
    else:
        ok(f'Python version {v[0]}.{v[1]}.{v[2]} (>= 3.8)')


def check_python_source():
    embed = ROOT / '.python' / 'python.exe'
    embed_pth = ROOT / '.python' / 'python311._pth'
    if embed.is_file():
        if embed_pth.is_file():
            ok('embedded Python: .python/python.exe + python311._pth')
        else:
            warn('embedded Python present but missing python311._pth — run scripts/download_python.bat or manually patch')
    else:
        ok('no embedded Python — will use system/venv Python')


def check_requirements():
    req_path = ROOT / 'requirements-web.txt'
    if not req_path.is_file():
        warn('requirements-web.txt not found — dependencies cannot be verified')
        return

    try:
        lines = req_path.read_text(encoding='utf-8').strip().splitlines()
    except OSError:
        warn('requirements-web.txt unreadable')
        return

    missing = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z0-9_\-\.]+)', line)
        if not m:
            continue
        pkg = m.group(1)
        import_name = pkg.replace('-', '_')
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        warn(f'missing dependencies: {", ".join(sorted(missing))} — run: pip install -r requirements-web.txt')
    else:
        ok('all requirements-web.txt packages importable')


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
    verdict = 'PASS'
    print('=== P1-Stable-1 Portability Check ===')
    print()

    print('--- Project Structure ---')
    check_required_paths()

    print('\n--- Configuration ---')
    check_config()

    print('\n--- Frontend Reference ---')
    check_index_app_js()

    print('\n--- Batch Script Anchoring ---')
    check_bat_relative()

    print('\n--- Environment Check ---')
    check_venv_validity()
    check_python_version()
    check_python_source()

    print('\n--- Dependencies Check ---')
    check_requirements()

    print('\n--- Backend Entry Check ---')
    check_backend_entry()

    print('\n--- Absolute Path Scan ---')
    scan_absolute_paths()

    print()
    print('========================================')
    if FAILURES:
        verdict = 'FAIL'
        print(f'VERDICT: FAIL  ({len(FAILURES)} BLOCKER(S))')
        print('----------------------------------------')
        print('BLOCKER items found. Do NOT proceed.')
        print('Fix all BLOCKER items before retrying.')
        for f in FAILURES:
            try:
                print(f'  -> {f}')
            except UnicodeEncodeError:
                print(f'  -> {str(f).encode("gbk", errors="replace").decode("gbk")}')
        if WARNINGS:
            print(f'\nAlso {len(WARNINGS)} warning(s) present (will need attention).')
    elif WARNINGS:
        verdict = 'PASS_WITH_WARNINGS'
        print(f'VERDICT: PASS_WITH_WARNINGS  ({len(WARNINGS)} WARNING(S))')
        print('----------------------------------------')
        print('No blockers, but warnings present.')
        print('Review warnings before production use.')
        for w in WARNINGS:
            try:
                print(f'  -> {w}')
            except UnicodeEncodeError:
                print(f'  -> {str(w).encode("gbk", errors="replace").decode("gbk")}')
    else:
        print('VERDICT: PASS')
        print('----------------------------------------')
        print('All checks passed. Project is portable.')
    print('========================================')

    if verdict == 'FAIL':
        return 1
    elif verdict == 'PASS_WITH_WARNINGS':
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
