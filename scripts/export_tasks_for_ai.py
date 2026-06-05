"""只读导出任务快照，供外部网页端 AI 协作使用。

用法:
  python scripts/export_tasks_for_ai.py
  python scripts/export_tasks_for_ai.py --db data/task_publisher.db
"""
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / 'data' / 'task_publisher.db'
OUT_DIR = ROOT / 'ai_workspace' / '00_context'


def load_config_db():
    cfg = ROOT / 'config' / 'config.json'
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding='utf-8'))
            rel = data.get('database', {}).get('task_db_path', 'data/task_publisher.db')
            return ROOT / rel.replace('/', '\\') if '\\' in str(ROOT) else ROOT / rel
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_DB


def row_get(row, key, default=None):
    try:
        val = row[key]
        return default if val is None else val
    except (KeyError, IndexError):
        return default


def task_status(row):
    if row_get(row, 'completed'):
        return 'completed'
    if row_get(row, 'in_discard_pile'):
        return 'in_discard_pile'
    if row_get(row, 'is_unlocked') in (0, False):
        return 'blocked'
    return 'active'


def parse_prereqs(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def fetch_tags(conn):
    tags = {}
    try:
        for tid, name in conn.execute(
            'SELECT tt.task_id, t.name FROM task_tags tt JOIN tags t ON t.id = tt.tag_id'
        ):
            tags.setdefault(tid, []).append(name)
    except sqlite3.Error:
        pass
    return tags


def export_tasks(db_path):
    if not db_path.is_file():
        raise FileNotFoundError(f'database not found: {db_path}')

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    tag_map = fetch_tags(conn)

    try:
        rows = conn.execute('SELECT * FROM tasks ORDER BY id').fetchall()
    except sqlite3.Error as e:
        conn.close()
        raise RuntimeError(f'failed to read tasks: {e}') from e
    conn.close()

    tasks = []
    for row in rows:
        tid = row_get(row, 'id')
        tasks.append({
            'task_id': tid,
            'title': row_get(row, 'name', ''),
            'name': row_get(row, 'name', ''),
            'description': row_get(row, 'description', '') or '',
            'estimated_minutes': row_get(row, 'estimated_time'),
            'category': row_get(row, 'category', ''),
            'task_type': row_get(row, 'task_type', ''),
            'tags': tag_map.get(tid, []),
            'priority': row_get(row, 'priority'),
            'status': task_status(row),
            'completed': bool(row_get(row, 'completed')),
            'in_discard_pile': bool(row_get(row, 'in_discard_pile')),
            'is_unlocked': row_get(row, 'is_unlocked', True) not in (0, False),
            'dependencies': parse_prereqs(row_get(row, 'prerequisite_ids')),
            'repeat_type': row_get(row, 'repeat_type', 'none'),
            'deadline': row_get(row, 'deadline'),
            'difficulty': row_get(row, 'difficulty'),
        })

    ts = datetime.now().strftime('%Y%m%d-%H%M')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f'tasks_snapshot_{ts}.json'
    md_path = OUT_DIR / f'tasks_snapshot_{ts}.md'

    payload = {
        'exported_at': datetime.now().isoformat(timespec='seconds'),
        'source_db': str(db_path.relative_to(ROOT)) if db_path.is_relative_to(ROOT) else str(db_path),
        'task_count': len(tasks),
        'tasks': tasks,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# 任务快照',
        '',
        f'- 导出时间: {payload["exported_at"]}',
        f'- 任务数量: {len(tasks)}',
        f'- 来源: `{payload["source_db"]}`',
        '',
        '> 本文件只读导出，供外部 AI 协作参考。不会自动写回数据库。',
        '',
    ]
    for t in tasks:
        lines.append(f'## [{t["task_id"]}] {t["title"]}')
        lines.append('')
        lines.append(f'- 状态: {t["status"]}')
        lines.append(f'- 分类: {t["category"] or "-"}')
        lines.append(f'- 预计时长: {t["estimated_minutes"] or "?"} 分钟')
        lines.append(f'- 优先级: {t["priority"] or "?"}')
        lines.append(f'- 重复: {t["repeat_type"] or "none"}')
        lines.append(f'- 标签: {", ".join(t["tags"]) if t["tags"] else "-"}')
        lines.append(f'- 依赖 task_id: {t["dependencies"] if t["dependencies"] else "无"}')
        lines.append(f'- 弃牌堆: {"是" if t["in_discard_pile"] else "否"}')
        if t.get('description'):
            lines.append(f'- 描述: {t["description"][:200]}')
        lines.append('')

    md_path.write_text('\n'.join(lines), encoding='utf-8')
    return json_path, md_path, len(tasks)


def main():
    p = argparse.ArgumentParser(description='Export read-only task snapshot for external AI')
    p.add_argument('--db', default=None, help='Path to task_publisher.db')
    args = p.parse_args()
    db_path = Path(args.db) if args.db else load_config_db()
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    try:
        json_path, md_path, count = export_tasks(db_path)
    except (FileNotFoundError, RuntimeError) as e:
        print(f'[FAIL] {e}')
        return 1

    print('[PASS] read-only export completed')
    print(f'  tasks: {count}')
    print(f'  json:  {json_path}')
    print(f'  md:    {md_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
