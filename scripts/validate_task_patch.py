"""校验外部 AI 生成的任务修改草稿 JSON（只校验，不写入）。

用法:
  python scripts/validate_task_patch.py
  python scripts/validate_task_patch.py --file ai_workspace/03_task_drafts/task_patch.json
  python scripts/validate_task_patch.py --file ai_workspace/03_task_drafts/task_patch.example.json
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATCH = ROOT / 'ai_workspace' / '03_task_drafts' / 'task_patch.json'
EXAMPLE_PATCH = ROOT / 'ai_workspace' / '03_task_drafts' / 'task_patch.example.json'

ALLOWED_OPS = {'add', 'update', 'split', 'merge', 'archive'}
ALLOWED_RISK = {'low', 'medium', 'high'}
FORBIDDEN_KEYS = {
    'sql', 'auto_import', 'delete_directly', 'change_weight',
    'modify_feedback_events', 'direct_db_write',
}
FORBIDDEN_PATTERNS = [
    re.compile(r'\bDELETE\s+FROM\b', re.I),
    re.compile(r'\bUPDATE\s+tasks\b', re.I),
    re.compile(r'\bINSERT\s+INTO\s+tasks\b', re.I),
    re.compile(r'auto_import', re.I),
    re.compile(r'direct_db_write', re.I),
]


def fail(msg):
    print(f'[FAIL] {msg}')
    return False


def scan_forbidden(obj, path='root'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in FORBIDDEN_KEYS:
                return fail(f'forbidden key at {path}.{k}')
            bad = scan_forbidden(v, f'{path}.{k}')
            if bad is False:
                return False
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            bad = scan_forbidden(item, f'{path}[{i}]')
            if bad is False:
                return False
    elif isinstance(obj, str):
        for pat in FORBIDDEN_PATTERNS:
            if pat.search(obj):
                return fail(f'forbidden pattern in {path}: {obj[:80]}')
    return True


def validate_change(change, idx):
    prefix = f'changes[{idx}]'
    if not isinstance(change, dict):
        return fail(f'{prefix} must be object')
    for field in ('operation', 'reason', 'risk_level', 'manual_action'):
        if field not in change or change[field] in (None, ''):
            return fail(f'{prefix}.{field} is required')
    op = str(change['operation']).lower()
    if op not in ALLOWED_OPS:
        return fail(f'{prefix}.operation invalid: {op}')
    risk = str(change['risk_level']).lower()
    if risk not in ALLOWED_RISK:
        return fail(f'{prefix}.risk_level invalid: {risk}')
    return True


def validate_patch(data):
    if not isinstance(data, dict):
        return fail('root must be JSON object')
    if data.get('version') != 'task_patch_v1':
        return fail('version must be task_patch_v1')
    if data.get('mode') != 'manual_review_only':
        return fail('mode must be manual_review_only')
    changes = data.get('changes')
    if not isinstance(changes, list):
        return fail('changes must be array')
    if not scan_forbidden(data):
        return False
    for i, ch in enumerate(changes):
        if not validate_change(ch, i):
            return False
    return True


def main():
    p = argparse.ArgumentParser(description='Validate task patch JSON (no DB write)')
    p.add_argument('--file', default=None, help='Patch JSON path')
    p.add_argument('--allow-missing', action='store_true', help='Exit 0 if default file missing')
    args = p.parse_args()

    path = Path(args.file) if args.file else DEFAULT_PATCH
    if not path.is_absolute():
        path = ROOT / path

    if not path.is_file():
        if not args.file and EXAMPLE_PATCH.is_file():
            print('[INFO] task_patch.json not found; validating task_patch.example.json')
            path = EXAMPLE_PATCH
        elif args.allow_missing:
            print('[INFO] patch file not found (no write performed)')
            print(f'  expected: {DEFAULT_PATCH}')
            print(f'  template: {EXAMPLE_PATCH}')
            return 0
        else:
            print('[INFO] patch file not found (no write performed)')
            print(f'  create from: {EXAMPLE_PATCH}')
            return 2

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        return 1 if fail(f'cannot parse JSON: {e}') else 1

    if not validate_patch(data):
        return 1

    print('[PASS] task patch validation OK')
    print(f'  file: {path}')
    print(f'  changes: {len(data.get("changes", []))}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
