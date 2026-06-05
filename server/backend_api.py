from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime, timedelta
from enum import Enum
import random
import math
import os
import re

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'server': {'port': 5000, 'host': '0.0.0.0', 'debug': True},
        'obsidian': {'vault_path': 'src/notes/vault', 'notes_directory': 'src/notes/vault'},
        'api': {'openai_api_key': '', 'claude_api_key': ''},
        'database': {'task_db_path': 'data/task_publisher.db'}
    }

CONFIG = load_config()

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
app = Flask(__name__, static_folder=_STATIC_DIR, static_url_path='/static')
CORS(app)

DATA_DIR = "data"
DB_PATH = CONFIG['database']['task_db_path']
NOTES_DIR = CONFIG['obsidian']['notes_directory']

class TaskCategory(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    FLEXIBLE_DDL = "flexible_ddl"
    ACCUMULATION = "accumulation"

class RepeatType(Enum):
    NONE = "none"
    SINGLE = "single"
    DAILY = "daily"
    WEEKLY = "weekly"
    ACCUMULATION = "accumulation"

class TaskProfile(Enum):
    DAILY_HABIT = "daily_habit"
    WEEKLY_ROUTINE = "weekly_routine"
    DEADLINE_FLEXIBLE = "deadline_flexible"
    DEADLINE_PROGRESSIVE = "deadline_progressive"

class Resistance(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class EnergyRequired(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task:
    def __init__(self, id=None, name="", category="daily", description=None,
                 estimated_time=30, preferred_time=None, deadline=None,
                 resistance="medium", energy_required="medium", rarity="common",
                 priority=5, success_rate=0.0, refusal_count=0, is_daily=False,
                 task_type="other", repeat_type="none", task_profile="deadline_flexible",
                 parent_task_id=None, group_id=None, last_completed_at=None,
                 next_available_at=None, last_drawn_at=None, draw_count_today=0,
                 min_push_time="20:00", in_discard_pile=False, completed_count=0,
                 tags=None, completed=False, difficulty=None, created_at=None,
                 updated_at=None, prerequisite_ids=None, is_unlocked=True):
        self.id = id
        self.name = name
        self.category = category
        self.description = description
        self.estimated_time = estimated_time
        self.preferred_time = preferred_time
        self.deadline = deadline
        self.resistance = resistance
        self.energy_required = energy_required
        self.rarity = rarity
        self.priority = priority
        self.success_rate = success_rate
        self.refusal_count = refusal_count
        self.is_daily = is_daily
        self.task_type = task_type
        self.repeat_type = repeat_type
        self.task_profile = task_profile
        self.parent_task_id = parent_task_id
        self.group_id = group_id
        self.last_completed_at = last_completed_at
        self.next_available_at = next_available_at
        self.last_drawn_at = last_drawn_at
        self.draw_count_today = draw_count_today
        self.min_push_time = min_push_time
        self.in_discard_pile = in_discard_pile
        self.completed_count = completed_count
        self.tags = tags or []
        self.completed = completed
        self.difficulty = difficulty
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
        self.prerequisite_ids = prerequisite_ids or []
        self.is_unlocked = is_unlocked

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "estimated_time": self.estimated_time,
            "preferred_time": self.preferred_time,
            "deadline": self.deadline,
            "resistance": self.resistance,
            "energy_required": self.energy_required,
            "rarity": self.rarity,
            "priority": self.priority,
            "success_rate": self.success_rate,
            "refusal_count": self.refusal_count,
            "is_daily": self.is_daily,
            "task_type": self.task_type,
            "repeat_type": self.repeat_type,
            "task_profile": self.task_profile,
            "parent_task_id": self.parent_task_id,
            "group_id": self.group_id,
            "last_completed_at": self.last_completed_at,
            "next_available_at": self.next_available_at,
            "last_drawn_at": self.last_drawn_at,
            "draw_count_today": self.draw_count_today,
            "min_push_time": self.min_push_time,
            "in_discard_pile": self.in_discard_pile,
            "completed_count": self.completed_count,
            "tags": self.tags,
            "completed": self.completed,
            "difficulty": self.difficulty,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "prerequisite_ids": self.prerequisite_ids,
            "is_unlocked": self.is_unlocked
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            category=data.get("category", "daily"),
            description=data.get("description"),
            estimated_time=data.get("estimated_time", 30),
            preferred_time=data.get("preferred_time"),
            deadline=data.get("deadline"),
            resistance=data.get("resistance", "medium"),
            energy_required=data.get("energy_required", "medium"),
            rarity=data.get("rarity", "common"),
            priority=data.get("priority", 5),
            success_rate=data.get("success_rate", 0.0),
            refusal_count=data.get("refusal_count", 0),
            is_daily=data.get("is_daily", False),
            task_type=data.get("task_type", "other"),
            repeat_type=data.get("repeat_type", "none"),
            task_profile=data.get("task_profile", "deadline_flexible"),
            parent_task_id=data.get("parent_task_id"),
            group_id=data.get("group_id"),
            last_completed_at=data.get("last_completed_at"),
            next_available_at=data.get("next_available_at"),
            last_drawn_at=data.get("last_drawn_at"),
            draw_count_today=data.get("draw_count_today", 0),
            min_push_time=data.get("min_push_time", "20:00"),
            in_discard_pile=data.get("in_discard_pile", False),
            completed_count=data.get("completed_count", 0),
            tags=data.get("tags", []),
            completed=data.get("completed", False),
            difficulty=data.get("difficulty"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            prerequisite_ids=data.get("prerequisite_ids", []),
            is_unlocked=data.get("is_unlocked", True)
        )

    @classmethod
    def from_row(cls, row):
        def safe_get(row, key, default=None):
            try:
                value = row[key]
                return value if value is not None else default
            except (KeyError, IndexError):
                return default

        prereq_raw = safe_get(row, "prerequisite_ids")
        prereq_ids = []
        if prereq_raw:
            try:
                prereq_ids = json.loads(prereq_raw)
            except:
                pass

        return cls(
            id=safe_get(row, "id"),
            name=safe_get(row, "name", ""),
            category=safe_get(row, "category", "other"),
            description=safe_get(row, "description", ""),
            estimated_time=safe_get(row, "estimated_time", 30),
            preferred_time=safe_get(row, "preferred_time"),
            deadline=safe_get(row, "deadline"),
            resistance=safe_get(row, "resistance", "medium"),
            energy_required=safe_get(row, "energy_required", "medium"),
            rarity=safe_get(row, "rarity", "common"),
            priority=safe_get(row, "priority", 5),
            success_rate=safe_get(row, "success_rate", 0.0),
            refusal_count=safe_get(row, "refusal_count", 0),
            is_daily=bool(safe_get(row, "is_daily", False)),
            task_type=safe_get(row, "task_type", "other"),
            repeat_type=safe_get(row, "repeat_type", "none"),
            task_profile=safe_get(row, "task_profile", "deadline_flexible"),
            parent_task_id=safe_get(row, "parent_task_id"),
            group_id=safe_get(row, "group_id"),
            last_completed_at=safe_get(row, "last_completed_at"),
            next_available_at=safe_get(row, "next_available_at"),
            last_drawn_at=safe_get(row, "last_drawn_at"),
            draw_count_today=safe_get(row, "draw_count_today", 0),
            min_push_time=safe_get(row, "min_push_time", "20:00"),
            in_discard_pile=bool(safe_get(row, "in_discard_pile", False)),
            completed_count=safe_get(row, "completed_count", 0),
            tags=safe_get(row, "tags", []),
            completed=bool(safe_get(row, "completed", False)),
            difficulty=safe_get(row, "difficulty"),
            created_at=safe_get(row, "created_at"),
            updated_at=safe_get(row, "updated_at"),
            prerequisite_ids=prereq_ids,
            is_unlocked=bool(safe_get(row, "is_unlocked", True))
        )

class GachaPool(Enum):
    FRAGMENT = "fragment"
    TOMATO = "tomato"
    DEEP = "deep"

class GachaSessionContext:
    def __init__(self):
        self.last_drawn_task_id = None
        self.last_drawn_category = None
        self.category_history = []
        self.replace_count = 0
        self.max_replace_count = 1
        self.replace_used = False
        self.replaced_task_id = None
        self.replace_timestamp = None

    def record_draw(self, task):
        self.last_drawn_task_id = task.id
        self.last_drawn_category = task.category
        self.category_history.append(task.category)
        if len(self.category_history) > 3:
            self.category_history.pop(0)

    def can_replace(self):
        return not self.replace_used

    def use_replace(self, task_id):
        self.replace_used = True
        self.replaced_task_id = task_id
        self.replace_timestamp = datetime.now()

    @property
    def category_count_in_last_3(self):
        counts = {}
        for cat in self.category_history:
            counts[cat] = counts.get(cat, 0) + 1
        return counts

class DrawResult:
    def __init__(self, task=None, pool=None, can_replace=False, is_replacement=False):
        self.task = task
        self.pool = pool
        self.can_replace = can_replace
        self.is_replacement = is_replacement

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ========== 标签查询（批处理） ==========

def get_task_tags(conn, task_id):
    cursor = conn.cursor()
    cursor.execute('''SELECT t.name FROM tags t JOIN task_tags tt ON t.id=tt.tag_id WHERE tt.task_id=?''', (task_id,))
    return [row['name'] for row in cursor.fetchall()]

def get_all_tags_for_tasks(conn, task_ids):
    """批量获取标签：一次查询替代 N 次单独查询"""
    if not task_ids:
        return {}
    placeholders = ','.join('?' * len(task_ids))
    cursor = conn.cursor()
    cursor.execute(f'''SELECT tt.task_id, t.name FROM task_tags tt JOIN tags t ON t.id=tt.tag_id WHERE tt.task_id IN ({placeholders})''', task_ids)
    result = {tid: [] for tid in task_ids}
    for row in cursor.fetchall():
        result[row['task_id']].append(row['name'])
    return result

def _attach_tags(conn, tasks):
    """为任务列表批量附加标签（单次查询）"""
    if not tasks:
        return
    ids = [t.id if hasattr(t, 'id') else t['id'] for t in tasks]
    tag_map = get_all_tags_for_tasks(conn, ids)
    for t in tasks:
        tid = t.id if hasattr(t, 'id') else t['id']
        if hasattr(t, 'tags'):
            t.tags = tag_map.get(tid, [])
        else:
            t['tags'] = tag_map.get(tid, [])

# ========== 数据库索引 ==========

def ensure_indexes(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_auto_%'")
    existing = {r['name'] for r in cur.fetchall()}
    indexes = {
        'idx_auto_tasks_category': 'CREATE INDEX idx_auto_tasks_category ON tasks(category)',
        'idx_auto_tasks_completed': 'CREATE INDEX idx_auto_tasks_completed ON tasks(completed)',
        'idx_auto_tasks_unlocked': 'CREATE INDEX idx_auto_tasks_unlocked ON tasks(is_unlocked)',
        'idx_auto_tasks_discard': 'CREATE INDEX idx_auto_tasks_discard ON tasks(in_discard_pile)',
        'idx_auto_tasks_deadline': 'CREATE INDEX idx_auto_tasks_deadline ON tasks(deadline)',
        'idx_auto_td_task': 'CREATE INDEX idx_auto_td_task ON task_dependencies(task_id)',
        'idx_auto_td_depends': 'CREATE INDEX idx_auto_td_depends ON task_dependencies(depends_on_task_id)',
        'idx_auto_tt_tag': 'CREATE INDEX idx_auto_tt_tag ON task_tags(tag_id)',
    }
    for name, sql in indexes.items():
        if name not in existing:
            cur.execute(sql)
    if set(indexes) - existing:
        conn.commit()
        print(f"[INDEX] Created {len(set(indexes)-existing)} new indexes")

def get_all_tasks(include_completed=False, unlocked_only=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conditions = []
        if not include_completed:
            conditions.append('completed = 0')
        if unlocked_only:
            conditions.append('(is_unlocked = 1 OR is_unlocked IS NULL)')
        where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        cursor.execute(f'SELECT * FROM tasks {where} ORDER BY created_at DESC')
        rows = cursor.fetchall()
        tasks = [Task.from_row(row) for row in rows]
        _attach_tags(conn, tasks)
        return tasks
    finally:
        conn.close()

def get_task_by_id(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        if row:
            task = Task.from_row(row)
            task.tags = get_task_tags(conn, task_id)
            return task
        return None
    finally:
        conn.close()

def add_task(task):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        prereq_ids = normalize_prereq_ids(task.prerequisite_ids)
        task.prerequisite_ids = prereq_ids
        prereq_json = json.dumps(prereq_ids)
        is_unlocked = compute_is_unlocked(conn, prereq_ids)

        cursor.execute('''
            INSERT INTO tasks (
                name, category, task_type, description, 
                estimated_time, preferred_time, deadline, 
                resistance, energy_required, rarity, priority,
                is_daily, repeat_type, created_at, updated_at,
                prerequisite_ids, is_unlocked
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.name, task.category, "normal", task.description,
            task.estimated_time, task.preferred_time, task.deadline,
            task.resistance, task.energy_required, task.rarity, task.priority,
            int(task.is_daily), task.repeat_type, now, now,
            prereq_json, is_unlocked
        ))
        conn.commit()
        task_id = cursor.lastrowid

        if task.tags:
            set_task_tags(conn, task_id, task.tags)

        sync_prerequisite_deps(conn, task_id, prereq_ids)
        conn.commit()
        return task_id
    finally:
        conn.close()

def update_task(task):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        prereq_ids = normalize_prereq_ids(task.prerequisite_ids)
        task.prerequisite_ids = prereq_ids
        is_unlocked = compute_is_unlocked(conn, prereq_ids)
        cursor.execute('''
            UPDATE tasks
            SET name=?, category=?, task_type=?, description=?, estimated_time=?,
                preferred_time=?, deadline=?, resistance=?, energy_required=?,
                rarity=?, priority=?, success_rate=?, refusal_count=?,
                is_daily=?, completed=?, repeat_type=?, task_profile=?,
                parent_task_id=?, group_id=?, min_push_time=?, difficulty=?,
                prerequisite_ids=?, is_unlocked=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            task.name,
            task.category,
            task.task_type,
            task.description,
            task.estimated_time,
            task.preferred_time,
            task.deadline,
            task.resistance,
            task.energy_required,
            task.rarity,
            task.priority,
            task.success_rate,
            task.refusal_count,
            task.is_daily,
            task.completed,
            task.repeat_type,
            task.task_profile,
            task.parent_task_id,
            task.group_id,
            task.min_push_time,
            task.difficulty,
            json.dumps(prereq_ids),
            int(is_unlocked),
            task.id
        ))
        conn.commit()

        if task.tags:
            set_task_tags(conn, task.id, task.tags)

        sync_prerequisite_deps(conn, task.id, prereq_ids)
        conn.commit()
    finally:
        conn.close()

def set_task_tags(conn, task_id, tag_names):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM task_tags WHERE task_id = ?', (task_id,))

    for tag_name in tag_names:
        tag_name = tag_name.strip()
        if not tag_name:
            continue

        cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
        tag_row = cursor.fetchone()
        if tag_row:
            cursor.execute(
                'INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)',
                (task_id, tag_row['id'])
            )
    conn.commit()

# ========== 依赖机制核心 ==========

def normalize_prereq_ids(prereq_ids):
    """将前置依赖规范化为去重后的整数列表"""
    if not prereq_ids:
        return []
    result = []
    seen = set()
    for raw in prereq_ids:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        result.append(pid)
    return result

def get_task_prereq_ids(conn, task_id, override_prereqs=None):
    """读取任务的前置依赖 ID 列表（优先 override）"""
    if override_prereqs is not None:
        return normalize_prereq_ids(override_prereqs)
    cursor = conn.cursor()
    cursor.execute('SELECT prerequisite_ids FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    if not row:
        return []
    try:
        return normalize_prereq_ids(json.loads(row['prerequisite_ids'] or '[]'))
    except (json.JSONDecodeError, TypeError):
        return []

def compute_is_unlocked(conn, prereq_ids):
    """所有前置任务均已完成时返回 1，否则 0"""
    prereq_ids = normalize_prereq_ids(prereq_ids)
    if not prereq_ids:
        return 1
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(prereq_ids))
    cursor.execute(
        f'SELECT id, completed FROM tasks WHERE id IN ({placeholders})',
        prereq_ids
    )
    status = {r['id']: bool(r['completed']) for r in cursor.fetchall()}
    if len(status) != len(prereq_ids):
        return 0
    return 1 if all(status.get(pid) for pid in prereq_ids) else 0

def sync_prerequisite_deps(conn, task_id, prereq_ids):
    """同步 task_dependencies 表（规范存储）和 tasks.prerequisite_ids（展示缓存）"""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM task_dependencies WHERE task_id = ?', (task_id,))
    for pid in normalize_prereq_ids(prereq_ids):
        cursor.execute(
            'INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?,?)',
            (task_id, pid)
        )

def detect_cycle(conn, task_id, new_prereq_ids):
    """检测循环依赖：更新时若从前置任务可到达当前任务，则形成环"""
    new_prereq_ids = normalize_prereq_ids(new_prereq_ids)
    if not new_prereq_ids:
        return None
    if task_id is not None and task_id in new_prereq_ids:
        return [task_id, task_id]
    if task_id is None:
        return None

    def can_reach(start_id, target_id):
        stack = [start_id]
        visited = set()
        while stack:
            node = stack.pop()
            if node == target_id:
                return True
            if node in visited:
                continue
            visited.add(node)
            prereqs = get_task_prereq_ids(
                conn, node,
                override_prereqs=new_prereq_ids if node == task_id else None
            )
            for pid in prereqs:
                if pid not in visited:
                    stack.append(pid)
        return False

    for pid in new_prereq_ids:
        if can_reach(pid, task_id):
            return [task_id, pid]
    return None

def validate_prerequisites(conn, prereq_ids, task_id=None):
    """验证前置任务 ID 合法（存在、非自依赖）"""
    prereq_ids = normalize_prereq_ids(prereq_ids)
    if not prereq_ids:
        return None
    if task_id is not None and task_id in prereq_ids:
        return '任务不能依赖自身'
    cursor = conn.cursor()
    for pid in prereq_ids:
        cursor.execute('SELECT id, name FROM tasks WHERE id = ?', (pid,))
        row = cursor.fetchone()
        if not row:
            return f'前置任务 ID={pid} 不存在'
    return None

def recompute_task_unlock(conn, task_id):
    """根据前置完成状态重算单任务 is_unlocked"""
    prereqs = get_task_prereq_ids(conn, task_id)
    unlocked = compute_is_unlocked(conn, prereqs)
    conn.execute(
        'UPDATE tasks SET is_unlocked = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (unlocked, task_id)
    )

def sync_all_unlock_states(conn):
    """启动时幂等同步所有未完成任务解锁状态"""
    cur = conn.cursor()
    cur.execute('SELECT id FROM tasks WHERE completed = 0')
    for row in cur.fetchall():
        recompute_task_unlock(conn, row['id'])
    conn.commit()

def get_task_dependents(conn, task_id):
    """返回依赖此任务的其他任务（未删除）"""
    cursor = conn.cursor()
    cursor.execute(
        'SELECT DISTINCT t.id, t.name FROM task_dependencies td '
        'JOIN tasks t ON td.task_id = t.id '
        'WHERE td.depends_on_task_id = ?',
        (task_id,)
    )
    deps = [dict(r) for r in cursor.fetchall()]
    cursor.execute('SELECT id, name, prerequisite_ids FROM tasks WHERE prerequisite_ids IS NOT NULL')
    seen = {d['id'] for d in deps}
    for row in cursor.fetchall():
        try:
            prereqs = json.loads(row['prerequisite_ids'] or '[]')
        except (json.JSONDecodeError, TypeError):
            prereqs = []
        if task_id in prereqs and row['id'] not in seen:
            deps.append({'id': row['id'], 'name': row['name']})
            seen.add(row['id'])
    return deps

def ensure_task_dependency_schema(conn):
    """幂等确保任务依赖相关表/字段存在"""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            depends_on_task_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
        )
    ''')
    legacy_cols = [
        ("prerequisite_ids", "TEXT", "'[]'"),
        ("is_unlocked", "INTEGER", "1"),
        ("difficulty", "TEXT", "NULL"),
    ]
    for col, col_type, default in legacy_cols:
        try:
            cur.execute(f'ALTER TABLE tasks ADD COLUMN {col} {col_type} DEFAULT {default}')
        except sqlite3.OperationalError:
            pass
    conn.commit()

def ensure_schedule_schema(conn):
    """幂等确保日程表（与桌面端 user_schedule / daily_schedules 对齐）"""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER,
            time_slot TEXT,
            activity TEXT,
            is_regular BOOLEAN DEFAULT 1
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS daily_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            activity TEXT NOT NULL,
            notes TEXT,
            UNIQUE(date, time_slot)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    conn.commit()
    migrate_legacy_schedule_tables(conn)

def _ensure_table_columns(cur, table, columns):
    """幂等补列：columns = [(name, type, default_or_none), ...]"""
    cur.execute(f'PRAGMA table_info({table})')
    existing = {row[1] for row in cur.fetchall()}
    for name, col_type, default in columns:
        if name in existing:
            continue
        try:
            if default is not None:
                cur.execute(f'ALTER TABLE {table} ADD COLUMN {name} {col_type} DEFAULT {default}')
            else:
                cur.execute(f'ALTER TABLE {table} ADD COLUMN {name} {col_type}')
        except sqlite3.OperationalError:
            pass

def ensure_timer_schema(conn):
    """幂等确保计时器表（与 /api/timer/* 读写一致）"""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS timer_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            planned_minutes INTEGER,
            actual_minutes INTEGER,
            status TEXT DEFAULT 'running',
            result TEXT,
            reason TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    _ensure_table_columns(cur, 'timer_sessions', [
        ('task_id', 'INTEGER', None),
        ('started_at', 'TEXT', None),
        ('ended_at', 'TEXT', None),
        ('planned_minutes', 'INTEGER', None),
        ('actual_minutes', 'INTEGER', None),
        ('status', 'TEXT', "'running'"),
        ('result', 'TEXT', None),
        ('reason', 'TEXT', None),
        ('notes', 'TEXT', None),
        ('created_at', 'TEXT', 'CURRENT_TIMESTAMP'),
    ])
    conn.commit()

TASK_FEEDBACK_EVENT_TYPES = frozenset({
    'skip_task', 'finish_early', 'finish_on_time', 'timer_timeout_unfinished', 'abandon_task',
})
TASK_FEEDBACK_REASON_CATEGORIES = frozenset({
    'state_issue', 'task_definition_issue', 'time_estimation_issue', 'ability_issue',
    'external_interrupt', 'priority_issue', 'other',
})

def ensure_task_feedback_events_schema(conn):
    """幂等确保任务事件反馈表（与 /api/task-feedback 读写一致）"""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_feedback_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            planned_minutes INTEGER,
            actual_minutes INTEGER,
            completion_status TEXT,
            reason_category TEXT NOT NULL,
            reason_detail TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    _ensure_table_columns(cur, 'task_feedback_events', [
        ('task_id', 'INTEGER', None),
        ('event_type', 'TEXT', None),
        ('planned_minutes', 'INTEGER', None),
        ('actual_minutes', 'INTEGER', None),
        ('completion_status', 'TEXT', None),
        ('reason_category', 'TEXT', None),
        ('reason_detail', 'TEXT', None),
        ('note', 'TEXT', None),
        ('created_at', 'TEXT', 'CURRENT_TIMESTAMP'),
    ])
    cur.execute('CREATE INDEX IF NOT EXISTS idx_task_feedback_task ON task_feedback_events(task_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_task_feedback_created ON task_feedback_events(created_at)')
    conn.commit()

def insert_task_feedback_event(data):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute('''
            INSERT INTO task_feedback_events
            (task_id, event_type, planned_minutes, actual_minutes, completion_status,
             reason_category, reason_detail, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['task_id'],
            data['event_type'],
            data.get('planned_minutes'),
            data.get('actual_minutes'),
            data.get('completion_status'),
            data['reason_category'],
            data.get('reason_detail'),
            data.get('note'),
            now,
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def ensure_assessment_schema(conn):
    """幂等确保状态评估表（与 /api/state/assessment* 读写一致）"""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS state_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            answers TEXT NOT NULL,
            daily_tone TEXT,
            energy_score REAL,
            focus_score REAL,
            mood_score REAL,
            formula_version INTEGER DEFAULT 1,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    _ensure_table_columns(cur, 'state_assessments', [
        ('date', 'TEXT', None),
        ('answers', 'TEXT', None),
        ('daily_tone', 'TEXT', None),
        ('energy_score', 'REAL', None),
        ('focus_score', 'REAL', None),
        ('mood_score', 'REAL', None),
        ('formula_version', 'INTEGER', '1'),
        ('timestamp', 'TEXT', 'CURRENT_TIMESTAMP'),
    ])
    conn.commit()

def ensure_daily_state_schema(conn):
    """幂等确保 daily_user_state（睡眠/精力/基调）"""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS daily_user_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            daily_tone TEXT DEFAULT 'normal',
            energy_morning INTEGER,
            energy_afternoon INTEGER,
            energy_evening INTEGER,
            bed_time TEXT,
            sleep_early_streak INTEGER DEFAULT 0
        )
    ''')
    _ensure_table_columns(cur, 'daily_user_state', [
        ('date', 'TEXT', None),
        ('daily_tone', 'TEXT', "'normal'"),
        ('energy_morning', 'INTEGER', None),
        ('energy_afternoon', 'INTEGER', None),
        ('energy_evening', 'INTEGER', None),
        ('bed_time', 'TEXT', None),
        ('sleep_early_streak', 'INTEGER', '0'),
    ])
    conn.commit()

def migrate_legacy_schedule_tables(conn):
    """将旧 Web 表 weekly_schedule / daily_schedule 数据同步到桌面端表（幂等）"""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_schedule'")
    if cur.fetchone():
        try:
            cur.execute('SELECT COUNT(*) AS c FROM user_schedule')
            if cur.fetchone()['c'] == 0:
                cur.execute('SELECT day_of_week, slot_id, activity FROM weekly_schedule')
                for row in cur.fetchall():
                    cur.execute(
                        'INSERT OR IGNORE INTO user_schedule (day_of_week, time_slot, activity, is_regular) VALUES (?,?,?,1)',
                        (row['day_of_week'], row['slot_id'], row['activity'] or '')
                    )
        except sqlite3.OperationalError:
            pass
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_schedule'")
    if cur.fetchone():
        try:
            cur.execute('''
                INSERT OR IGNORE INTO daily_schedules (date, time_slot, activity, notes)
                SELECT date, slot_id, COALESCE(activity, ''), COALESCE(notes, '')
                FROM daily_schedule
            ''')
        except sqlite3.OperationalError:
            pass
    conn.commit()

def delete_task(task_id):
    """删除任务并清理所有依赖引用"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. 用 task_dependencies 索引查找所有依赖此任务的下游（避免全表扫描JSON）
        cursor.execute('SELECT task_id FROM task_dependencies WHERE depends_on_task_id = ?', (task_id,))
        dependent_ids = [r['task_id'] for r in cursor.fetchall()]

        for dep_id in dependent_ids:
            cursor.execute('SELECT prerequisite_ids FROM tasks WHERE id = ?', (dep_id,))
            row = cursor.fetchone()
            if not row:
                continue
            try:
                prereqs = normalize_prereq_ids(json.loads(row['prerequisite_ids'] or '[]'))
                if task_id in prereqs:
                    prereqs = [p for p in prereqs if p != task_id]
                cursor.execute(
                    'UPDATE tasks SET prerequisite_ids=? WHERE id=?',
                    (json.dumps(prereqs), dep_id)
                )
                cursor.execute(
                    'DELETE FROM task_dependencies WHERE task_id=? AND depends_on_task_id=?',
                    (dep_id, task_id)
                )
                recompute_task_unlock(conn, dep_id)
            except (json.JSONDecodeError, TypeError):
                pass

        # 补充：扫描 JSON 字段中引用此任务的下游
        cursor.execute('SELECT id, prerequisite_ids FROM tasks WHERE prerequisite_ids IS NOT NULL')
        for row in cursor.fetchall():
            try:
                prereqs = normalize_prereq_ids(json.loads(row['prerequisite_ids'] or '[]'))
            except (json.JSONDecodeError, TypeError):
                continue
            if task_id in prereqs and row['id'] not in dependent_ids:
                prereqs = [p for p in prereqs if p != task_id]
                cursor.execute(
                    'UPDATE tasks SET prerequisite_ids=? WHERE id=?',
                    (json.dumps(prereqs), row['id'])
                )
                cursor.execute(
                    'DELETE FROM task_dependencies WHERE task_id=? AND depends_on_task_id=?',
                    (row['id'], task_id)
                )
                recompute_task_unlock(conn, row['id'])

        # 2. 删除任务本身的依赖记录
        cursor.execute('DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?', (task_id, task_id))

        # 3. 删除任务
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
    finally:
        conn.close()

def _complete_task(task_id, update_rate=True):
    """统一完成/跳过逻辑"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE tasks SET completed = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (task_id,))
        if update_rate:
            cursor.execute('SELECT success_rate FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            if row:
                cursor.execute('UPDATE tasks SET success_rate = ? WHERE id = ?',
                               (min(1.0, row['success_rate'] + 0.1), task_id))
        conn.commit()
        return chain_unlock(conn, task_id)
    finally:
        conn.close()

def chain_unlock(conn, task_id):
    """级联解锁: 完成task_id后, 递归解锁所有依赖已全满足的下游任务"""
    unlocked_names = []
    cursor = conn.cursor()
    cursor.execute('''SELECT td.task_id as dependent_id, t.name as dependent_name, t.prerequisite_ids
                       FROM task_dependencies td
                       JOIN tasks t ON td.task_id = t.id
                       WHERE td.depends_on_task_id = ? AND t.completed = 0 AND t.is_unlocked = 0
                    ''', (task_id,))
    dependent_rows = cursor.fetchall()

    # 批量预取所有前置任务的完成状态
    all_prereq_ids = set()
    for dep in dependent_rows:
        try:
            for pid in json.loads(dep['prerequisite_ids'] or '[]'):
                all_prereq_ids.add(pid)
        except:
            pass

    prereq_status = {}
    if all_prereq_ids:
        placeholders = ','.join('?' * len(all_prereq_ids))
        cursor.execute(f'SELECT id, completed FROM tasks WHERE id IN ({placeholders})', list(all_prereq_ids))
        for r in cursor.fetchall():
            prereq_status[r['id']] = bool(r['completed'])

    for dep in dependent_rows:
        dep_id = dep['dependent_id']
        try:
            prereqs = json.loads(dep['prerequisite_ids'] or '[]')
        except:
            prereqs = []
        if all(prereq_status.get(pid, False) for pid in prereqs):
            cursor.execute('UPDATE tasks SET is_unlocked = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (dep_id,))
            conn.commit()
            unlocked_names.append(dep['dependent_name'])
            unlocked_names.extend(chain_unlock(conn, dep_id))

    return unlocked_names

def record_refusal(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE tasks SET refusal_count = refusal_count + 1 WHERE id = ?', (task_id,))
        conn.commit()
    finally:
        conn.close()

def _calculate_full_weight(task, current_energy, session_context=None):
    weight = 1.0
    weight *= task.priority / 5.0
    weight *= _calculate_deadline_urgency(task)
    weight *= _calculate_energy_match(task, current_energy)
    weight *= _calculate_resistance_factor(task)
    weight *= 0.5 + task.success_rate * 0.5
    weight *= max(0.3, 1.0 - task.refusal_count * 0.1)
    weight *= _calculate_profile_strategy_weight(task)

    if session_context:
        weight *= _calculate_cooldown_factor(task, session_context)

    return max(0.01, float(weight))

def _calculate_deadline_urgency(task):
    if not task.deadline:
        return 1.0
    try:
        deadline_dt = datetime.fromisoformat(task.deadline)
        now = datetime.now()
        if deadline_dt <= now:
            return 3.0
        days_left = (deadline_dt - now).days
        if days_left <= 1:
            return 2.5
        elif days_left <= 3:
            return 1.5
        elif days_left <= 7:
            return 1.0 + (7.0 - days_left) * 0.1
        else:
            return 0.5
    except:
        return 1.0

def _calculate_energy_match(task, current_energy):
    energy_score = {"low": 0, "medium": 1, "high": 2}
    task_energy = energy_score.get(task.energy_required, 1)
    current_energy_score = energy_score.get(current_energy, 1)
    energy_diff = abs(task_energy - current_energy_score)
    return max(0.5, 1.5 - energy_diff * 0.3)

def _calculate_resistance_factor(task):
    resistance_penalty = {"low": 1.0, "medium": 0.8, "high": 0.6}
    return resistance_penalty.get(task.resistance, 1.0)

def _calculate_profile_strategy_weight(task):
    profile = task.task_profile
    now = datetime.now()

    if profile == TaskProfile.DAILY_HABIT.value:
        return 0.0
    elif profile == TaskProfile.WEEKLY_ROUTINE.value:
        weekday = now.weekday()
        if weekday <= 3:
            return 0.3
        elif weekday <= 5:
            return 1.5
        else:
            return 3.0
    elif profile == TaskProfile.DEADLINE_FLEXIBLE.value:
        if not task.deadline:
            return 1.0
        try:
            deadline_dt = datetime.fromisoformat(task.deadline)
            days_left = (deadline_dt - now).days
            if days_left > 7:
                return 0.5
            elif days_left > 3:
                return 1.0
            elif days_left > 1:
                return 1.5
            else:
                return 2.5
        except:
            return 1.0
    elif profile == TaskProfile.DEADLINE_PROGRESSIVE.value:
        return 1.0
    return 1.0

def _calculate_cooldown_factor(task, session_context):
    if session_context is None:
        return 1.0
    factor = 1.0
    if session_context.last_drawn_task_id is not None and task.id == session_context.last_drawn_task_id:
        return 0.0
    if session_context.last_drawn_category is not None and task.category == session_context.last_drawn_category:
        factor *= 0.3
    cat_count = session_context.category_count_in_last_3
    if cat_count.get(task.category, 0) >= 2:
        factor *= 0.5

    if task.draw_count_today >= 3:
        factor *= 0.2

    return factor

def select_weighted_random_task(current_energy="medium", session_context=None):
    tasks = get_all_tasks(include_completed=False)
    tasks = [t for t in tasks if t.task_profile != TaskProfile.DAILY_HABIT.value]

    if not tasks:
        return None

    weights = []
    for task in tasks:
        weight = _calculate_full_weight(task, current_energy, session_context)
        weights.append(weight)

    total_weight = sum(weights)
    if total_weight <= 0:
        return random.choice(tasks)

    random_val = random.random() * total_weight
    cumulative = 0.0
    for task, weight in zip(tasks, weights):
        cumulative += weight
        if cumulative >= random_val:
            return task
    return tasks[-1]

def get_available_tasks_for_gacha():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute('''
            SELECT * FROM tasks 
            WHERE completed = 0 
            AND (next_available_at IS NULL OR next_available_at <= ?)
            AND (in_discard_pile = 0 OR in_discard_pile IS NULL)
            AND is_unlocked = 1
            ORDER BY priority DESC, id ASC
        ''', (now,))
        rows = cursor.fetchall()
        tasks = [dict(r) for r in rows]
        _attach_tags(conn, tasks)
        return tasks
    finally:
        conn.close()

def draw_single(tasks, pool, energy="medium", session_context=None):
    if session_context is None:
        session_context = GachaSessionContext()

    time_ranges = {GachaPool.FRAGMENT: (0, 15), GachaPool.TOMATO: (15, 45), GachaPool.DEEP: (45, 999)}
    lo, hi = time_ranges.get(pool, (0, 999))

    matching = [t for t in tasks if lo <= (t.get('estimated_time', 0) or 0) < hi]
    if not matching:
        matching = tasks  # fallback: allow all

    if not matching:
        return None

    task_objects = [Task.from_dict(t) if isinstance(t, dict) else t for t in matching]

    selected = _weighted_pick(task_objects, energy, session_context)
    if not selected:
        return None

    session_context.record_draw(selected)
    update_draw_count(selected.id)

    return DrawResult(
        task=selected,
        pool=pool,
        can_replace=session_context.can_replace() and not session_context.replace_used,
        is_replacement=session_context.replace_used
    )

def _weighted_pick(tasks, energy, session):
    """加权随机选择（内联，避免额外 DB 查询）"""
    if not tasks:
        return None
    weights = [_calculate_full_weight(t, energy, session) for t in tasks]
    total = sum(weights)
    if total <= 0:
        return random.choice(tasks)
    r = random.uniform(0, total)
    cum = 0
    for i, w in enumerate(weights):
        cum += w
        if r <= cum:
            return tasks[i]
    return tasks[-1]

def update_draw_count(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE tasks
            SET draw_count_today = draw_count_today + 1,
                last_drawn_at = ?,
                updated_at = ?
            WHERE id = ?
        ''', (now, now, task_id))
        conn.commit()
    finally:
        conn.close()

def get_discard_pile_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT * FROM tasks 
            WHERE in_discard_pile = 1 AND completed = 0
            ORDER BY updated_at DESC, id DESC
        ''')
        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            task = Task.from_row(row)
            task.tags = get_task_tags(conn, task.id)
            tasks.append(task.to_dict())
        return tasks
    finally:
        conn.close()

def move_task_to_discard_pile(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE tasks 
            SET in_discard_pile = 1, 
                last_completed_at = ?,
                completed_count = completed_count + 1,
                updated_at = ?
            WHERE id = ?
        ''', (now, now, task_id))
        conn.commit()
    finally:
        conn.close()

def move_task_to_gacha_pile(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE tasks 
            SET in_discard_pile = 0, updated_at = ?
            WHERE id = ?
        ''', (now, task_id))
        conn.commit()
    finally:
        conn.close()

@app.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'
    unlocked_only = request.args.get('unlocked_only', 'true').lower() == 'true'
    tasks = get_all_tasks(include_completed, unlocked_only)
    return jsonify([task.to_dict() for task in tasks])

@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def api_get_task(task_id):
    task = get_task_by_id(task_id)
    if task:
        return jsonify(task.to_dict())
    return jsonify({'error': 'Task not found'}), 404

def _task_blocked_message(task):
    """返回任务被阻塞时的说明"""
    if task.is_unlocked or task.completed:
        return None
    prereqs = task.prerequisite_ids or []
    if not prereqs:
        return '任务当前不可执行'
    names = []
    for pid in prereqs:
        t = get_task_by_id(pid)
        names.append(t.name if t else f'ID={pid}')
    return '前置任务未完成：' + '、'.join(names)

@app.route('/api/tasks', methods=['POST'])
def api_create_task():
    data = request.json
    prereq_ids = normalize_prereq_ids(data.get('prerequisite_ids', []))

    # 验证 + 环检测
    conn = get_db_connection()
    try:
        err = validate_prerequisites(conn, prereq_ids)
        if err:
            return jsonify({'error': err}), 400
    finally:
        conn.close()

    task = Task(
        name=data.get('name', ''),
        category=data.get('category', 'daily'),
        description=data.get('description'),
        estimated_time=data.get('estimated_time', 30),
        preferred_time=data.get('preferred_time'),
        deadline=data.get('deadline'),
        resistance=data.get('resistance', 'medium'),
        energy_required=data.get('energy_required', 'medium'),
        rarity=data.get('rarity', 'common'),
        priority=data.get('priority', 5),
        is_daily=data.get('is_daily', False),
        repeat_type=data.get('repeat_type', 'none'),
        tags=data.get('tags', []),
        prerequisite_ids=prereq_ids
    )
    task_id = add_task(task)
    return jsonify({'id': task_id, 'message': 'Task created successfully'}), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    data = request.json
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    new_prereqs = normalize_prereq_ids(data.get('prerequisite_ids', task.prerequisite_ids))

    # 验证 + 环检测
    conn = get_db_connection()
    try:
        err = validate_prerequisites(conn, new_prereqs, task_id=task_id)
        if err:
            return jsonify({'error': err}), 400
        cycle = detect_cycle(conn, task_id, new_prereqs)
        if cycle:
            return jsonify({'error': f'检测到循环依赖: {" -> ".join(map(str, cycle))}'}), 400
    finally:
        conn.close()

    if 'name' in data:
        task.name = data['name']
    if 'category' in data:
        task.category = data['category']
    if 'description' in data:
        task.description = data['description']
    if 'estimated_time' in data:
        task.estimated_time = data['estimated_time']
    if 'preferred_time' in data:
        task.preferred_time = data['preferred_time']
    if 'deadline' in data:
        task.deadline = data['deadline']
    if 'resistance' in data:
        task.resistance = data['resistance']
    if 'energy_required' in data:
        task.energy_required = data['energy_required']
    if 'rarity' in data:
        task.rarity = data['rarity']
    if 'priority' in data:
        task.priority = data['priority']
    if 'is_daily' in data:
        task.is_daily = data['is_daily']
    if 'repeat_type' in data:
        task.repeat_type = data['repeat_type']
    if 'tags' in data:
        task.tags = data['tags']
    if 'prerequisite_ids' in data:
        task.prerequisite_ids = new_prereqs

    update_task(task)
    return jsonify({'message': 'Task updated successfully'})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    conn = get_db_connection()
    try:
        dependents = get_task_dependents(conn, task_id)
    finally:
        conn.close()
    delete_task(task_id)
    return jsonify({
        'message': 'Task deleted successfully',
        'dependents_cleaned': [{'id': d['id'], 'name': d['name']} for d in dependents]
    })

@app.route('/api/tasks/<int:task_id>/dependents', methods=['GET'])
def api_get_task_dependents(task_id):
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    conn = get_db_connection()
    try:
        dependents = get_task_dependents(conn, task_id)
        return jsonify({'task_id': task_id, 'dependents': dependents, 'count': len(dependents)})
    finally:
        conn.close()

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def api_complete_task(task_id):
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    blocked = _task_blocked_message(task)
    if blocked:
        return jsonify({'error': blocked}), 400
    unlocked = _complete_task(task_id, update_rate=True)
    return jsonify({
        'message': 'Task completed successfully',
        'unlocked_tasks': unlocked
    })

@app.route('/api/tasks/<int:task_id>/skip', methods=['POST'])
def api_skip_task(task_id):
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    blocked = _task_blocked_message(task)
    if blocked:
        return jsonify({'error': blocked}), 400
    unlocked = _complete_task(task_id, update_rate=False)
    return jsonify({
        'message': 'Task skipped',
        'unlocked_tasks': unlocked
    })

@app.route('/api/tasks/<int:task_id>/refuse', methods=['POST'])
def api_refuse_task(task_id):
    record_refusal(task_id)
    return jsonify({'message': 'Refusal recorded'})

@app.route('/api/gacha/pools', methods=['GET'])
def api_get_gacha_pools():
    pools = [
        {"id": "fragment", "name": "碎片卡池", "description": "0-15分钟"},
        {"id": "tomato", "name": "番茄卡池", "description": "15-45分钟"},
        {"id": "deep", "name": "深度卡池", "description": "45分钟以上"}
    ]
    return jsonify(pools)

@app.route('/api/gacha/draw', methods=['POST'])
def api_draw_task():
    data = request.json
    pool_id = data.get('pool', 'fragment')
    energy = data.get('energy', 'medium')

    try:
        pool = GachaPool(pool_id)
    except ValueError:
        return jsonify({'error': 'Invalid pool'}), 400

    tasks = get_available_tasks_for_gacha()
    session_context = GachaSessionContext()
    result = draw_single(tasks, pool, energy, session_context)

    if result and result.task:
        return jsonify({
            'task': result.task.to_dict(),
            'pool': pool.value,
            'can_replace': result.can_replace,
            'is_replacement': result.is_replacement
        })
    return jsonify({'error': 'No tasks available'}), 404

@app.route('/api/discard-pile', methods=['GET'])
def api_get_discard_pile():
    tasks = get_discard_pile_tasks()
    return jsonify(tasks)

@app.route('/api/discard-pile/<int:task_id>/restore', methods=['POST'])
def api_restore_from_discard(task_id):
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if not task.in_discard_pile:
        return jsonify({'error': 'Task is not in discard pile'}), 400
    move_task_to_gacha_pile(task_id)
    return jsonify({'restored': True, 'task_id': task_id, 'message': 'Task restored from discard pile'})

@app.route('/api/tasks/<int:task_id>/move-to-discard', methods=['POST'])
def api_move_to_discard(task_id):
    move_task_to_discard_pile(task_id)
    return jsonify({'message': 'Task moved to discard pile'})

@app.route('/api/health', methods=['GET'])
def api_health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/knowledge/categories', methods=['GET'])
def api_get_knowledge_categories():
    categories = []
    
    math_path = os.path.join(NOTES_DIR, '知识点', '高等数学')
    if os.path.exists(math_path):
        count = len([f for f in os.listdir(math_path) if f.endswith('.md')])
        categories.append({'id': 'math', 'name': '高等数学', 'count': count})
    
    physics_path = os.path.join(NOTES_DIR, '知识点', '大学物理')
    if os.path.exists(physics_path):
        count = len([f for f in os.listdir(physics_path) if f.endswith('.md')])
        categories.append({'id': 'physics', 'name': '大学物理', 'count': count})
    
    linear_path = os.path.join(NOTES_DIR, '知识点', '线性代数')
    if os.path.exists(linear_path):
        count = len([f for f in os.listdir(linear_path) if f.endswith('.md')])
        categories.append({'id': 'linear', 'name': '线性代数', 'count': count})
    else:
        categories.append({'id': 'linear', 'name': '线性代数', 'count': 8})
    
    elec_path = os.path.join(NOTES_DIR, '知识点', '电子技术')
    if os.path.exists(elec_path):
        count = len([f for f in os.listdir(elec_path) if f.endswith('.md')])
        categories.append({'id': 'electronics', 'name': '电子技术', 'count': count})
    
    cs_path = os.path.join(NOTES_DIR, '知识点', '计算机')
    if os.path.exists(cs_path):
        count = len([f for f in os.listdir(cs_path) if f.endswith('.md')])
        categories.append({'id': 'computer', 'name': '计算机', 'count': count})
    else:
        categories.append({'id': 'computer', 'name': '计算机', 'count': 6})
    
    return jsonify(categories)

@app.route('/api/knowledge/points', methods=['GET'])
def api_get_knowledge_points():
    category = request.args.get('category', 'all')
    
    points = []
    base_path = os.path.join(NOTES_DIR, '知识点')
    
    if category == 'all':
        for subject in os.listdir(base_path):
            subject_path = os.path.join(base_path, subject)
            if os.path.isdir(subject_path):
                for filename in os.listdir(subject_path):
                    if filename.endswith('.md'):
                        name = filename[:-3]
                        points.append({
                            'id': name,
                            'name': name,
                            'category': subject,
                            'category_id': get_category_id(subject)
                        })
    else:
        category_name = get_category_name(category)
        category_path = os.path.join(base_path, category_name)
        if os.path.exists(category_path):
            for filename in os.listdir(category_path):
                if filename.endswith('.md'):
                    name = filename[:-3]
                    points.append({
                        'id': name,
                        'name': name,
                        'category': category_name,
                        'category_id': category
                    })
    
    return jsonify(points)

def get_category_id(subject):
    mapping = {
        '高等数学': 'math',
        '大学物理': 'physics',
        '线性代数': 'linear',
        '电子技术': 'electronics',
        '计算机': 'computer'
    }
    return mapping.get(subject, subject.lower())

def get_category_name(category_id):
    mapping = {
        'math': '高等数学',
        'physics': '大学物理',
        'linear': '线性代数',
        'electronics': '电子技术',
        'computer': '计算机'
    }
    return mapping.get(category_id, category_id)

_WIKI_LINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
_MD_LINK_RE = re.compile(r'(?<!!)\[([^\]]*)\]\(([^)]+)\)')
_TAG_RE = re.compile(r'(?:^|\s)#([^\s#/,]+)')
_FRONTMATTER_TAGS_RE = re.compile(r'^tags:\s*\[(.*?)\]', re.MULTILINE)

def _wiki_link_target(raw):
    t = raw.strip()
    if '|' in t:
        t = t.split('|', 1)[0]
    if '#' in t:
        t = t.split('#', 1)[0]
    return t.strip()

def _vault_rel_path(root, full_path):
    rel = os.path.relpath(full_path, root).replace('\\', '/')
    return rel

def _note_category(rel_path):
    parts = rel_path.replace('\\', '/').split('/')
    if len(parts) >= 2 and parts[0] == '知识点':
        return parts[1]
    if len(parts) >= 2:
        return parts[0]
    return '未分类'

def _parse_note_tags(content):
    tags = []
    fm = _FRONTMATTER_TAGS_RE.search(content[:800])
    if fm:
        tags.extend(t.strip().strip('"\'') for t in fm.group(1).split(',') if t.strip())
    for m in _TAG_RE.finditer(content[:4000]):
        t = m.group(1).strip()
        if t and t not in tags:
            tags.append(t)
        if len(tags) >= 20:
            break
    return tags

def _resolve_wiki_target(target, current_rel, stem_index, path_index):
    target = target.strip().replace('\\', '/')
    if not target:
        return None
    if target.lower().endswith('.md'):
        target = target[:-3]
    if '/' in target:
        rel = target if target.endswith('.md') else target + '.md'
        return path_index.get(rel)
    cur_dir = os.path.dirname(current_rel).replace('\\', '/')
    if cur_dir:
        rel_try = f'{cur_dir}/{target}.md'
        if rel_try in path_index:
            return path_index[rel_try]
    stem = os.path.basename(target).lower()
    for rel in stem_index.get(stem, []):
        if rel in path_index:
            return path_index[rel]
    return None

def _resolve_md_link(href, current_rel, path_index):
    href = href.strip().split('#')[0].strip()
    if not href or href.startswith(('http://', 'https://', 'mailto:')):
        return None
    if href.startswith('/'):
        rel = href.lstrip('/')
    else:
        cur_dir = os.path.dirname(current_rel).replace('\\', '/')
        rel = os.path.normpath(os.path.join(cur_dir, href)).replace('\\', '/')
    if not rel.lower().endswith('.md'):
        rel += '.md'
    return path_index.get(rel)

def _extract_links_from_content(content, source_id, current_rel, stem_index, path_index):
    links = []
    seen = set()
    for m in _WIKI_LINK_RE.finditer(content):
        tid = _resolve_wiki_target(_wiki_link_target(m.group(1)), current_rel, stem_index, path_index)
        if tid is None or tid == source_id:
            continue
        key = (source_id, tid, 'wiki_link')
        if key not in seen:
            seen.add(key)
            links.append({'source': source_id, 'target': tid, 'type': 'wiki_link'})
    for m in _MD_LINK_RE.finditer(content):
        tid = _resolve_md_link(m.group(2), current_rel, path_index)
        if tid is None or tid == source_id:
            continue
        key = (source_id, tid, 'markdown_link')
        if key not in seen:
            seen.add(key)
            links.append({'source': source_id, 'target': tid, 'type': 'markdown_link'})
    return links

def build_vault_knowledge_graph():
    """扫描 vault Markdown，基于真实双链/相对链接构建图谱。"""
    nodes = []
    links = []
    categories = []
    category_set = set()
    if not os.path.isdir(NOTES_DIR):
        return {'nodes': nodes, 'links': links, 'categories': categories}

    md_files = []
    for dirpath, dirnames, filenames in os.walk(NOTES_DIR):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for fn in filenames:
            if fn.endswith('.md') and not fn.startswith('.'):
                md_files.append(os.path.join(dirpath, fn))

    path_index = {}
    stem_index = {}
    file_meta = []

    for idx, full in enumerate(sorted(md_files)):
        rel = _vault_rel_path(NOTES_DIR, full)
        rel_md = rel if rel.endswith('.md') else rel + '.md'
        path_index[rel_md] = idx
        stem = os.path.splitext(os.path.basename(rel_md))[0].lower()
        stem_index.setdefault(stem, []).append(rel_md)
        title = os.path.splitext(os.path.basename(rel_md))[0]
        category = _note_category(rel_md)
        if category not in category_set:
            category_set.add(category)
            categories.append(category)
        try:
            with open(full, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            content = ''
        tags = _parse_note_tags(content)
        file_meta.append({
            'id': idx,
            'title': title,
            'name': title,
            'path': rel_md,
            'category': category,
            'tags': tags,
            'content': content,
            'rel': rel_md,
        })

    link_seen = set()
    for meta in file_meta:
        nodes.append({
            'id': meta['id'],
            'title': meta['title'],
            'name': meta['title'],
            'path': meta['path'],
            'category': meta['category'],
            'tags': meta['tags'],
        })
        for link in _extract_links_from_content(
            meta['content'], meta['id'], meta['rel'], stem_index, path_index
        ):
            key = (link['source'], link['target'], link['type'])
            if key not in link_seen:
                link_seen.add(key)
                links.append(link)

    return {'nodes': nodes, 'links': links, 'categories': categories}

@app.route('/api/knowledge/graph', methods=['GET'])
def api_get_knowledge_graph():
    return jsonify(build_vault_knowledge_graph())

@app.route('/api/knowledge/note/<path:note_path>', methods=['GET'])
def api_get_note_content(note_path):
    full_path = os.path.join(NOTES_DIR, note_path)
    if not full_path.endswith('.md'):
        full_path += '.md'
    
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    
    return jsonify({'error': 'Note not found'}), 404

@app.route('/api/knowledge/recent', methods=['GET'])
def api_get_recent_knowledge():
    recent = [
        {'name': '高斯定理', 'category': '大学物理'},
        {'name': '矩阵运算', 'category': '线性代数'},
        {'name': '导数', 'category': '高等数学'},
        {'name': '布尔代数', 'category': '电子技术'}
    ]
    return jsonify(recent)

@app.route('/api/knowledge/notes', methods=['GET'])
def api_get_notes():
    notes = []
    
    for subject in os.listdir(NOTES_DIR):
        subject_path = os.path.join(NOTES_DIR, subject)
        if os.path.isdir(subject_path) and not subject.startswith('.'):
            for filename in os.listdir(subject_path):
                if filename.endswith('.md'):
                    name = filename[:-3]
                    notes.append({
                        'id': f'{subject}/{name}',
                        'name': name,
                        'category': subject,
                        'path': f'{subject}/{filename}'
                    })
    
    return jsonify(notes)

@app.route('/api/knowledge/note-content/<path:note_path>', methods=['GET'])
def api_get_note_content_full(note_path):
    full_path = os.path.join(NOTES_DIR, note_path)
    if not full_path.endswith('.md'):
        full_path += '.md'
    
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content, 'path': note_path})
    
    return jsonify({'error': 'Note not found'}), 404

@app.route('/api/knowledge/point-detail/<subject>/<point_name>', methods=['GET'])
def api_get_knowledge_point_detail(subject, point_name):
    point_path = os.path.join(NOTES_DIR, '知识点', subject, f'{point_name}.md')
    
    if os.path.exists(point_path):
        with open(point_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({
            'name': point_name,
            'category': subject,
            'content': content
        })
    
    return jsonify({'error': 'Knowledge point not found'}), 404

@app.route('/api/knowledge/open-in-obsidian', methods=['POST'])
def api_open_in_obsidian():
    data = request.json
    file_path = data.get('file_path')
    
    if not file_path:
        return jsonify({'error': 'file_path is required'}), 400
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    full_path = os.path.join(project_root, NOTES_DIR, file_path)
    if not full_path.endswith('.md'):
        full_path += '.md'
    full_path = os.path.abspath(full_path)
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    import subprocess
    import urllib.parse
    try:
        encoded_path = urllib.parse.quote(full_path)
        obsidian_uri = f"obsidian://open?path={encoded_path}"
        subprocess.Popen(['start', '', obsidian_uri], shell=True)
        return jsonify({'success': True, 'message': 'Opening in Obsidian', 'path': full_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/config', methods=['GET'])
def api_get_config():
    return jsonify({
        'port': CONFIG['server']['port'],
        'notes_directory': CONFIG['obsidian']['notes_directory'],
        'vault_path': CONFIG['obsidian']['vault_path'],
        'has_openai_key': bool(CONFIG['api'].get('openai_api_key')),
        'has_claude_key': bool(CONFIG['api'].get('claude_api_key')),
        'api_base': CONFIG['api'].get('api_base', 'https://api.openai.com/v1'),
        'model': CONFIG['api'].get('model', 'gpt-4o-mini'),
    })

@app.route('/api/config/save', methods=['POST'])
def api_save_config():
    try:
        data = request.json
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        
        existing_config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)

        # 处理扁平化的 API 相关字段，合并到 api 子对象
        api_fields = {'openai_api_key', 'claude_api_key', 'api_base', 'model', 'bed_time'}
        for key in list(data.keys()):
            if key in api_fields:
                existing_config.setdefault('api', {})[key] = data.pop(key)
            if key == 'bed_time':
                existing_config.setdefault('obsidian', {})['bed_time'] = data.pop(key)

        # 深度合并
        for key in data:
            if key in existing_config and isinstance(data[key], dict) and isinstance(existing_config[key], dict):
                existing_config[key].update(data[key])
            else:
                existing_config[key] = data[key]
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, ensure_ascii=False, indent=4)

        # 重新加载配置
        global CONFIG
        CONFIG = load_config()
        
        return jsonify({'success': True, 'message': 'Config saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== API: 标签管理 ==========
@app.route('/api/tags', methods=['GET'])
def api_get_tags():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT t.id, t.name, COUNT(tt.task_id) as task_count FROM tags t LEFT JOIN task_tags tt ON t.id = tt.tag_id GROUP BY t.id ORDER BY t.name')
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()

@app.route('/api/tags', methods=['POST'])
def api_create_tag():
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Tag name required'}), 400
    conn = get_db_connection()
    try:
        conn.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (name,))
        conn.commit()
        cur = conn.cursor()
        cur.execute('SELECT id, name FROM tags WHERE name = ?', (name,))
        row = cur.fetchone()
        return jsonify(dict(row)) if row else jsonify({'error': 'Failed to create'}), 500
    finally:
        conn.close()

@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
def api_delete_tag(tag_id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM task_tags WHERE tag_id = ?', (tag_id,))
        conn.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
        conn.commit()
        return jsonify({'deleted': tag_id})
    finally:
        conn.close()

@app.route('/api/tags/batch', methods=['POST'])
def api_batch_assign_tags():
    data = request.json
    task_ids = data.get('task_ids', [])
    tag_names = data.get('tags', [])
    if not task_ids or not tag_names:
        return jsonify({'error': 'task_ids and tags required'}), 400
    conn = get_db_connection()
    try:
        for tid in task_ids:
            set_task_tags(conn, tid, tag_names)
        conn.commit()
        return jsonify({'assigned': len(task_ids)})
    finally:
        conn.close()

# ========== API: 日程管理 ==========
SCHEDULE_SLOTS = [
    {"slot_id": "am1", "name": "上午第一节", "start_time": "08:00", "end_time": "08:50"},
    {"slot_id": "am2", "name": "上午第二节", "start_time": "09:00", "end_time": "09:50"},
    {"slot_id": "am3", "name": "上午第三节", "start_time": "10:10", "end_time": "11:00"},
    {"slot_id": "am4", "name": "上午第四节", "start_time": "11:10", "end_time": "12:00"},
    {"slot_id": "noon", "name": "午休", "start_time": "12:00", "end_time": "14:00"},
    {"slot_id": "pm1", "name": "下午第一节", "start_time": "14:00", "end_time": "14:50"},
    {"slot_id": "pm2", "name": "下午第二节", "start_time": "15:00", "end_time": "15:50"},
    {"slot_id": "pm3", "name": "下午第三节", "start_time": "16:10", "end_time": "17:00"},
    {"slot_id": "pm4", "name": "下午第四节", "start_time": "17:10", "end_time": "18:00"},
    {"slot_id": "night", "name": "晚自习", "start_time": "19:00", "end_time": "21:30"},
]

@app.route('/api/schedule/slots', methods=['GET'])
def api_get_schedule_slots():
    return jsonify(SCHEDULE_SLOTS)

@app.route('/api/schedule/weekly', methods=['GET'])
def api_get_weekly_schedule():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, day_of_week, time_slot, activity FROM user_schedule ORDER BY day_of_week, time_slot')
        rows = [dict(r) for r in cur.fetchall()]
        result = {str(d): {} for d in range(7)}
        for r in rows:
            day = str(r['day_of_week'])
            slot = r['time_slot']
            if day not in result:
                result[day] = {}
            result[day][slot] = {
                'id': r['id'],
                'activity': r['activity'] or '',
                'notes': ''
            }
        return jsonify(result)
    except sqlite3.OperationalError as e:
        return jsonify({'error': '日程表未就绪: ' + str(e)}), 500
    finally:
        conn.close()

@app.route('/api/schedule/weekly', methods=['POST'])
def api_save_weekly_schedule():
    data = request.json
    day = data.get('day_of_week')
    slot_id = data.get('slot_id')
    activity = (data.get('activity') or '').strip()
    if day is None or not slot_id:
        return jsonify({'error': 'day_of_week and slot_id required'}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM user_schedule WHERE day_of_week=? AND time_slot=?', (day, slot_id))
        if activity:
            cur.execute(
                'INSERT INTO user_schedule (day_of_week, time_slot, activity, is_regular) VALUES (?,?,?,1)',
                (day, slot_id, activity)
            )
            cur.execute('INSERT OR IGNORE INTO activities (name) VALUES (?)', (activity,))
        conn.commit()
        return jsonify({'saved': True})
    except sqlite3.OperationalError as e:
        return jsonify({'error': '保存失败: ' + str(e)}), 500
    finally:
        conn.close()

@app.route('/api/schedule/daily', methods=['GET'])
def api_get_daily_schedule():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT id, date, time_slot, activity, notes FROM daily_schedules WHERE date=? ORDER BY time_slot',
            (date_str,)
        )
        rows = [{
            'id': r['id'],
            'date': r['date'],
            'slot_id': r['time_slot'],
            'activity': r['activity'] or '',
            'notes': r['notes'] or ''
        } for r in cur.fetchall()]
        return jsonify(rows)
    except sqlite3.OperationalError as e:
        return jsonify({'error': '日程表未就绪: ' + str(e)}), 500
    finally:
        conn.close()

@app.route('/api/schedule/daily', methods=['POST'])
def api_save_daily_schedule():
    data = request.json
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    slot_id = data.get('slot_id')
    activity = (data.get('activity') or '').strip()
    notes = (data.get('notes') or '').strip()
    if not slot_id:
        return jsonify({'error': 'slot_id required'}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM daily_schedules WHERE date=? AND time_slot=?', (date_str, slot_id))
        existing = cur.fetchone()
        if not activity:
            if existing:
                cur.execute('DELETE FROM daily_schedules WHERE id=?', (existing['id'],))
        elif existing:
            cur.execute(
                'UPDATE daily_schedules SET activity=?, notes=? WHERE id=?',
                (activity, notes, existing['id'])
            )
        else:
            cur.execute(
                'INSERT INTO daily_schedules (date, time_slot, activity, notes) VALUES (?,?,?,?)',
                (date_str, slot_id, activity, notes)
            )
            cur.execute('INSERT OR IGNORE INTO activities (name) VALUES (?)', (activity,))
        conn.commit()
        return jsonify({'saved': True})
    except sqlite3.OperationalError as e:
        return jsonify({'error': '保存失败: ' + str(e)}), 500
    finally:
        conn.close()

@app.route('/api/schedule/activities', methods=['GET'])
def api_get_activities():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM activities ORDER BY name')
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()

@app.route('/api/schedule/activities', methods=['POST'])
def api_add_activity():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Activity name required'}), 400
    activity_type = (data.get('type') or 'custom').strip() or 'custom'
    try:
        duration = int(data.get('duration_minutes', 30) or 30)
    except (TypeError, ValueError):
        duration = 30
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, name FROM activities WHERE name=?', (name,))
        existing = cur.fetchone()
        if existing:
            return jsonify({
                'id': existing['id'],
                'name': existing['name'],
                'type': activity_type,
                'duration_minutes': duration,
                'added': False,
            })
        cur.execute('INSERT INTO activities (name) VALUES (?)', (name,))
        conn.commit()
        return jsonify({
            'id': cur.lastrowid,
            'name': name,
            'type': activity_type,
            'duration_minutes': duration,
            'added': True,
        })
    finally:
        conn.close()

@app.route('/api/schedule/activities/<int:act_id>', methods=['DELETE'])
def api_delete_activity(act_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM activities WHERE id=?', (act_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': '活动不存在'}), 404
        return jsonify({'deleted': act_id})
    finally:
        conn.close()

# ========== API: 状态管理 ==========
@app.route('/api/state/daily-tone', methods=['GET'])
def api_get_daily_tone():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM daily_user_state WHERE date=?', (today,))
        row = cur.fetchone()
        return jsonify(dict(row)) if row else jsonify({'date': today, 'daily_tone': 'normal', 'energy_morning': None, 'energy_afternoon': None, 'energy_evening': None, 'bed_time': None, 'sleep_early_streak': 0})
    finally:
        conn.close()

@app.route('/api/state/daily-tone', methods=['POST'])
def api_set_daily_tone():
    data = request.json
    today = datetime.now().strftime('%Y-%m-%d')
    tone = data.get('daily_tone', 'normal')
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM daily_user_state WHERE date=?', (today,))
        existing = cur.fetchone()
        if existing:
            cur.execute('UPDATE daily_user_state SET daily_tone=? WHERE id=?', (tone, existing['id']))
        else:
            cur.execute('INSERT INTO daily_user_state (date, daily_tone) VALUES (?,?)', (today, tone))
        conn.commit()
        return jsonify({'daily_tone': tone, 'date': today})
    finally:
        conn.close()

@app.route('/api/state/energy', methods=['POST'])
def api_record_energy():
    data = request.json
    today = datetime.now().strftime('%Y-%m-%d')
    period = data.get('period', 'morning')
    value = data.get('value', 5)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM daily_user_state WHERE date=?', (today,))
        existing = cur.fetchone()
        col = f'energy_{period}'
        if existing:
            cur.execute(f'UPDATE daily_user_state SET {col}=? WHERE id=?', (value, existing['id']))
        else:
            cur.execute(f'INSERT INTO daily_user_state (date, {col}) VALUES (?,?)', (today, value))
        conn.commit()
        return jsonify({'recorded': True, 'period': period, 'value': value})
    finally:
        conn.close()

@app.route('/api/state/sleep', methods=['GET'])
def api_get_sleep():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT date, bed_time, sleep_early_streak FROM daily_user_state ORDER BY date DESC LIMIT 14')
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()

@app.route('/api/state/sleep', methods=['POST'])
def api_record_sleep():
    data = request.json
    today = datetime.now().strftime('%Y-%m-%d')
    bed_time = (data.get('bed_time') or '').strip()
    sleep_status = data.get('status', 'on_time')
    if not bed_time:
        return jsonify({'error': '请输入入睡时间'}), 400
    if not re.match(r'^\d{2}:\d{2}$', bed_time):
        return jsonify({'error': '入睡时间格式应为 HH:MM'}), 400
    try:
        h, m = bed_time.split(':')
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            return jsonify({'error': '入睡时间无效'}), 400
    except ValueError:
        return jsonify({'error': '入睡时间无效'}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, sleep_early_streak FROM daily_user_state WHERE date=?', (today,))
        row = cur.fetchone()
        streak = (row['sleep_early_streak'] or 0) if row else 0
        if sleep_status == 'on_time':
            streak += 1
        else:
            streak = 0
        if row:
            cur.execute('UPDATE daily_user_state SET bed_time=?, sleep_early_streak=? WHERE id=?',
                       (bed_time, streak, row['id']))
        else:
            cur.execute('INSERT INTO daily_user_state (date, bed_time, sleep_early_streak) VALUES (?,?,?)',
                       (today, bed_time, streak))
        conn.commit()
        return jsonify({'bed_time': bed_time, 'sleep_early_streak': streak})
    finally:
        conn.close()

@app.route('/api/state/weekly-energy', methods=['GET'])
def api_get_weekly_energy():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT date, energy_morning, energy_afternoon, energy_evening, daily_tone 
                       FROM daily_user_state WHERE date >= date('now','-14 days') ORDER BY date''')
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()

# ========== API: 任务完成反馈 ==========
@app.route('/api/tasks/<int:task_id>/feedback', methods=['POST'])
def api_task_feedback(task_id):
    data = request.json
    energy = data.get('energy_after')
    mood = data.get('mood_after')
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO task_completion_feedback (task_id, energy_after, mood_after, timestamp) VALUES (?,?,?,?)',
                   (task_id, energy, mood, datetime.now().isoformat()))
        # Also update daily_user_state
        today = datetime.now().strftime('%Y-%m-%d')
        hour = datetime.now().hour
        period = 'morning' if hour < 12 else ('afternoon' if hour < 18 else 'evening')
        cur.execute('SELECT id FROM daily_user_state WHERE date=?', (today,))
        row = cur.fetchone()
        col = f'energy_{period}'
        if row and energy is not None:
            cur.execute(f'UPDATE daily_user_state SET {col}=? WHERE id=?', (energy, row['id']))
        elif energy is not None:
            cur.execute(f'INSERT INTO daily_user_state (date, {col}) VALUES (?,?)', (today, energy))
        conn.commit()
        return jsonify({'feedback_recorded': True})
    finally:
        conn.close()

@app.route('/api/task-feedback', methods=['POST'])
def api_create_task_feedback():
    data = request.json or {}
    task_id = data.get('task_id')
    event_type = data.get('event_type')
    reason_category = data.get('reason_category')
    if not task_id:
        return jsonify({'error': 'task_id required'}), 400
    if event_type not in TASK_FEEDBACK_EVENT_TYPES:
        return jsonify({'error': '非法 event_type'}), 400
    if reason_category not in TASK_FEEDBACK_REASON_CATEGORIES:
        return jsonify({'error': '非法 reason_category'}), 400
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    try:
        fid = insert_task_feedback_event({
            'task_id': int(task_id),
            'event_type': event_type,
            'planned_minutes': data.get('planned_minutes'),
            'actual_minutes': data.get('actual_minutes'),
            'completion_status': data.get('completion_status'),
            'reason_category': reason_category,
            'reason_detail': data.get('reason_detail'),
            'note': data.get('note'),
        })
        return jsonify({'saved': True, 'id': fid}), 201
    except (TypeError, ValueError, sqlite3.Error) as e:
        return jsonify({'error': '保存反馈失败: ' + str(e)}), 500

@app.route('/api/task-feedback', methods=['GET'])
def api_list_task_feedback():
    task_id = request.args.get('task_id')
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if task_id:
            try:
                tid = int(task_id)
            except ValueError:
                return jsonify({'error': '非法 task_id'}), 400
            cur.execute(
                'SELECT * FROM task_feedback_events WHERE task_id=? ORDER BY created_at DESC',
                (tid,),
            )
        else:
            cur.execute('SELECT * FROM task_feedback_events ORDER BY created_at DESC LIMIT 100')
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()

# ========== API: 增强抽卡 ==========
@app.route('/api/gacha/pools/detail', methods=['GET'])
def api_get_pool_detail():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        pools = {
            "fragment": {"name": "碎片卡池", "time_range": "0-15分钟", "min": 0, "max": 15, "tasks": []},
            "tomato": {"name": "番茄卡池", "time_range": "15-45分钟", "min": 15, "max": 45, "tasks": []},
            "deep": {"name": "深度卡池", "time_range": "45分钟以上", "min": 45, "max": 999, "tasks": []}
        }
        cur.execute("SELECT * FROM tasks WHERE completed=0 AND in_discard_pile=0 AND is_unlocked=1")
        for row in cur.fetchall():
            task = dict(row)
            task['tags'] = get_task_tags(conn, task['id'])
            et = task.get('estimated_time') or 0
            if et <= 15:
                pools["fragment"]["tasks"].append(task)
            elif et <= 45:
                pools["tomato"]["tasks"].append(task)
            else:
                pools["deep"]["tasks"].append(task)
        return jsonify(pools)
    finally:
        conn.close()

@app.route('/api/gacha/statistics', methods=['GET'])
def api_get_gacha_statistics():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM gacha_records")
        total = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as accepted FROM gacha_records WHERE accepted=1")
        accepted = cur.fetchone()['accepted']
        cur.execute("SELECT pool_name, COUNT(*) as cnt FROM gacha_records GROUP BY pool_name ORDER BY cnt DESC")
        by_pool = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as cnt FROM task_rejection_log")
        rejections = cur.fetchone()['cnt']
        cur.execute('''SELECT reason, COUNT(*) as cnt FROM task_rejection_log 
                       WHERE timestamp >= date('now','-30 days') GROUP BY reason ORDER BY cnt DESC''')
        reject_reasons = [dict(r) for r in cur.fetchall()]
        return jsonify({
            'total_draws': total, 'accepted': accepted, 'rejections': rejections,
            'acceptance_rate': round(accepted / total * 100, 1) if total > 0 else 0,
            'by_pool': by_pool, 'reject_reasons': reject_reasons
        })
    finally:
        conn.close()

@app.route('/api/gacha/replace', methods=['POST'])
def api_gacha_replace():
    data = request.json
    task_id = data.get('task_id')
    reason = data.get('reason', 'other')
    pool_id = data.get('pool', 'fragment')
    energy = data.get('energy', 'medium')

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO task_rejection_log (task_id, reason, timestamp) VALUES (?,?,?)',
                   (task_id, reason, datetime.now().isoformat()))
        cur.execute('UPDATE tasks SET refusal_count = refusal_count + 1 WHERE id = ?', (task_id,))
        cur.execute('INSERT INTO gacha_records (timestamp, pool_name, available_time, task_id, accepted, refusal_reason) VALUES (?,?,?,?,?,?)',
                   (datetime.now().isoformat(), pool_id, 30, task_id, False, reason))
        conn.commit()
    finally:
        conn.close()

    # Redraw
    tasks = get_available_tasks_for_gacha()
    try:
        pool = GachaPool(pool_id)
    except ValueError:
        return jsonify({'error': 'Invalid pool'}), 400
    session_context = GachaSessionContext()
    session_context.use_replace(task_id)
    result = draw_single(tasks, pool, energy, session_context)
    if result and result.task:
        return jsonify({'task': result.task.to_dict(), 'replaced': task_id, 'reason': reason})
    return jsonify({'error': 'No replacement available'}), 404

# ========== API: 依赖图数据 ==========
@app.route('/api/dependencies', methods=['GET'])
def api_get_dependencies():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # 从 prerequisite_ids JSON列读取节点和边
        cur.execute("SELECT id, name, prerequisite_ids, is_unlocked, completed FROM tasks")
        nodes, edges = [], []
        for r in cur.fetchall():
            task = dict(r)
            nodes.append({'id': task['id'], 'name': task['name'], 'is_unlocked': task['is_unlocked'], 'completed': task['completed']})
            try:
                prereqs = json.loads(task['prerequisite_ids'] or '[]')
                for pid in prereqs:
                    edges.append({'from': pid, 'to': task['id']})
            except:
                pass
        return jsonify({'nodes': nodes, 'edges': edges})
    finally:
        conn.close()

# ========== API: 系统导出 ==========
@app.route('/api/export', methods=['GET'])
def api_export_system_state():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        export = {'exported_at': datetime.now().isoformat()}
        for table in ['tasks', 'tags', 'task_tags', 'task_dependencies', 'user_schedule', 'daily_schedules', 'daily_user_state', 'gacha_records', 'task_rejection_log', 'task_completion_feedback']:
            cur.execute(f'SELECT * FROM {table}')
            export[table] = [dict(r) for r in cur.fetchall()]
        return jsonify(export)
    finally:
        conn.close()

def migrate_dependency_data():
    """启动时同步: 将现有 prerequisite_ids JSON数据迁移到 task_dependencies 表"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM task_dependencies")
        if cur.fetchone()['cnt'] > 0:
            return  # 已迁移

        cur.execute("SELECT id, prerequisite_ids FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]'")
        count = 0
        for row in cur.fetchall():
            try:
                prereqs = json.loads(row['prerequisite_ids'] or '[]')
                for pid in prereqs:
                    cur.execute('INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?,?)',
                               (row['id'], pid))
                count += 1
            except:
                pass
        conn.commit()
        print(f"[MIGRATE] {count} tasks with dependencies synced to task_dependencies table")
    finally:
        conn.close()

@app.route('/')
def serve_index():
    from flask import send_file, make_response
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'index.html')
    response = make_response(send_file(index_path))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

# ========== AI Agent 系统 ==========

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'notes', 'prompts')
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'notes', '未分类')
CLASSIFIED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'notes', '已分类')

# 科目名映射：旧缩写 → vault目录名
SUBJECT_MAP = {'高数': '高等数学', '大物': '大学物理', '线代': '线性代数', '英语': '英语四级', '英语四级': '英语四级', '计算机': '计算机', '电子技术': '电子技术'}

AGENT_CONFIG = {
    'note_organizer': {
        'name': '笔记整理师', 'desc': '读取原始录音转写文件，重构为结构化Markdown笔记',
        'icon': 'fa-file-pen', 'prompt_file': '笔记整理师',
        'input_type': 'raw_file',  # 从未分类/ 目录选文件
        'actions': ['save_note'],
    },
    'knowledge_extractor': {
        'name': '知识点整理师', 'desc': '从已有笔记提取核心知识点，生成标准知识点文件',
        'icon': 'fa-lightbulb', 'prompt_file': '知识点整理师',
        'input_type': 'vault_note',  # 从 vault/ 选笔记
        'actions': ['save_knowledge'],
    },
    'structure_reviewer': {
        'name': '结构审查师', 'desc': '检查笔记格式、链接、Mermaid/Callout语法',
        'icon': 'fa-check-double', 'prompt_file': '结构审查师',
        'input_type': 'vault_note',
        'actions': [],
    },
    'content_reviewer': {
        'name': '内容审查师', 'desc': '检查事实准确性、逻辑一致性、可读性',
        'icon': 'fa-magnifying-glass', 'prompt_file': '内容审查师',
        'input_type': 'vault_note',
        'actions': [],
    },
    'task_publisher': {
        'name': 'AI任务发布', 'desc': '用自然语言批量创建学习任务',
        'icon': 'fa-wand-magic-sparkles', 'prompt_file': 'AI_assistant_prompt.md',
        'input_type': 'text',
        'actions': ['import_tasks'],
    },
}

def load_prompt(agent_id):
    cfg = AGENT_CONFIG.get(agent_id)
    if not cfg:
        return None
    prompt_path = os.path.join(PROMPTS_DIR, cfg['prompt_file'])
    if os.path.exists(prompt_path):
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def call_llm(system_prompt, user_message):
    api_key = CONFIG['api'].get('openai_api_key') or CONFIG['api'].get('claude_api_key', '')
    if not api_key:
        raise ValueError('API密钥未配置，请在设置页面填入OpenAI或Claude密钥')
    api_base = CONFIG['api'].get('api_base', 'https://api.openai.com/v1').rstrip('/')
    model = CONFIG['api'].get('model', 'gpt-4o-mini')
    payload = json.dumps({
        'model': model, 'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ], 'temperature': 0.7, 'max_tokens': 4096,
    }).encode('utf-8')
    req = __import__('urllib').request.Request(
        f'{api_base}/chat/completions', data=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'})
    with __import__('urllib').request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())['choices'][0]['message']['content']

def _build_task_context():
    """构建现有任务上下文，供AI任务发布Agent参考（含名称、ID、依赖关系）"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, prerequisite_ids, is_unlocked, completed, repeat_type FROM tasks WHERE completed=0 ORDER BY id")
        tasks = [dict(r) for r in cur.fetchall()]
        if not tasks:
            return None
        lines = ['=== 现有任务列表（供参考，不要重复创建） ===']
        for t in tasks:
            try:
                prereqs = json.loads(t['prerequisite_ids'] or '[]')
            except:
                prereqs = []
            dep_str = f', 前置依赖: {prereqs}' if prereqs else ''
            status = '已锁定' if not t.get('is_unlocked') else '可用'
            lines.append(f'ID={t["id"]} [{status}] {t["name"]}{dep_str}')
        return '\n'.join(lines)
    finally:
        conn.close()

@app.route('/api/agent/agents', methods=['GET'])
def api_list_agents():
    return jsonify([
        {'id': k, 'name': v['name'], 'desc': v['desc'], 'icon': v['icon'],
         'input_type': v['input_type'], 'input_type_label': INPUT_TYPE_LABELS.get(v['input_type'], v['input_type']),
         'actions': v.get('actions', []),
         'action_labels': [ACTION_LABELS.get(a, a) for a in v.get('actions', [])],
         'prompt_file': v.get('prompt_file', '')}
        for k, v in AGENT_CONFIG.items()
    ])

@app.route('/api/agent/files/raw', methods=['GET'])
def api_list_raw_files():
    """列出 未分类/ 目录中的 txt 文件，以及 已分类/ 子目录"""
    subdir = request.args.get('subdir', '')
    if subdir.startswith('已分类'):
        rel = subdir[3:].lstrip('/')
        base = os.path.join(CLASSIFIED_DIR, rel) if rel else CLASSIFIED_DIR
    elif subdir:
        base = os.path.join(RAW_DIR, subdir)
    else:
        base = RAW_DIR
    
    if not os.path.exists(base):
        return jsonify({'subdirs': [], 'files': []})
    
    items = sorted(os.listdir(base))
    subdirs = []
    files = []
    for item in items:
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path):
            txt_count = len([f for f in os.listdir(item_path) if f.endswith('.txt')])
            if txt_count > 0:
                subdirs.append({'name': item, 'file_count': txt_count})
        elif item.endswith('.txt'):
            stat = os.stat(item_path)
            files.append({
                'name': item, 'path': (subdir + '/' + item) if subdir else item,
                'size': stat.st_size, 'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    
    # 根级别：额外显示 已分类 目录入口
    if not subdir and os.path.exists(CLASSIFIED_DIR):
        classified_count = 0
        for d in os.listdir(CLASSIFIED_DIR):
            dp = os.path.join(CLASSIFIED_DIR, d)
            if os.path.isdir(dp):
                classified_count += len([f for f in os.listdir(dp) if f.endswith('.txt')])
        if classified_count > 0:
            subdirs.append({'name': '已分类', 'file_count': classified_count})
    
    return jsonify({'subdirs': subdirs, 'files': files, 'current': subdir})

@app.route('/api/agent/files/vault', methods=['GET'])
def api_list_vault_files():
    """列出 vault 中可供审查/处理的笔记文件"""
    subject = request.args.get('subject', '')
    base = os.path.join(NOTES_DIR, subject) if subject else NOTES_DIR
    
    if not os.path.exists(base) or not os.path.isdir(base):
        return jsonify({'dirs': [], 'files': []})
    
    items = sorted(os.listdir(base))
    dirs = []
    files = []
    for item in items:
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            md_count = len([f for f in os.listdir(item_path) if f.endswith('.md')])
            if md_count > 0:
                dirs.append({'name': item, 'file_count': md_count})
        elif item.endswith('.md'):
            stat = os.stat(item_path)
            files.append({
                'name': item, 'path': (subject + '/' + item) if subject else item,
                'size': stat.st_size,
            })
    return jsonify({'dirs': dirs, 'files': files, 'current': subject or ''})

INPUT_TYPE_LABELS = {
    'raw_file': '从未分类/已分类目录选择 txt 文件',
    'vault_note': '从 Vault 选择 Markdown 笔记',
    'text': '纯文本输入（自然语言）',
}
ACTION_LABELS = {
    'save_note': '保存笔记到 Vault（写操作，本模式不可用）',
    'save_knowledge': '保存知识点到 Vault（写操作，本模式不可用）',
    'import_tasks': '导入任务（写操作，本模式不可用）',
}

def _resolve_agent_prompt_path(prompt_file):
    if not prompt_file:
        return None
    base = os.path.join(PROMPTS_DIR, prompt_file)
    if os.path.isfile(base):
        return base
    if not prompt_file.endswith('.md'):
        alt = base + '.md'
        if os.path.isfile(alt):
            return alt
    return None

def _safe_agent_raw_path(rel):
    if not rel or not isinstance(rel, str):
        return None
    raw = rel.strip().replace('\\', '/').lstrip('/')
    if '..' in raw or raw.startswith('..'):
        return None
    if raw.startswith('已分类/'):
        base = CLASSIFIED_DIR
        inner = raw[4:]
    elif raw.startswith('已分类'):
        base = CLASSIFIED_DIR
        inner = raw[3:].lstrip('/')
    else:
        base = RAW_DIR
        inner = raw
    fpath = os.path.abspath(os.path.join(base, inner))
    base_abs = os.path.abspath(base)
    if not fpath.startswith(base_abs + os.sep) and fpath != base_abs:
        return None
    if not fpath.endswith('.txt') or not os.path.isfile(fpath):
        return None
    return fpath

def _safe_agent_vault_path(rel):
    if not rel or not isinstance(rel, str):
        return None
    raw = rel.strip().replace('\\', '/').lstrip('/')
    if '..' in raw:
        return None
    fpath = os.path.abspath(os.path.join(NOTES_DIR, raw))
    notes_abs = os.path.abspath(NOTES_DIR)
    if not fpath.startswith(notes_abs + os.sep):
        return None
    if not fpath.endswith('.md'):
        fpath_md = fpath + '.md'
        if os.path.isfile(fpath_md):
            fpath = fpath_md
        elif not os.path.isfile(fpath):
            return None
    elif not os.path.isfile(fpath):
        return None
    return fpath

@app.route('/api/agent/agents/<agent_id>/prompt', methods=['GET'])
def api_get_agent_prompt(agent_id):
    if agent_id not in AGENT_CONFIG:
        return jsonify({'error': '无效的Agent'}), 404
    cfg = AGENT_CONFIG[agent_id]
    prompt_path = _resolve_agent_prompt_path(cfg['prompt_file'])
    if not prompt_path:
        return jsonify({
            'agent_id': agent_id,
            'prompt_file': cfg['prompt_file'],
            'exists': False,
            'content': '',
            'size': 0,
        })
    stat = os.stat(prompt_path)
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({
        'agent_id': agent_id,
        'prompt_file': os.path.basename(prompt_path),
        'exists': True,
        'size': stat.st_size,
        'content': content,
    })

@app.route('/api/agent/files/raw/content', methods=['GET'])
def api_get_raw_file_content():
    rel = request.args.get('path', '')
    fpath = _safe_agent_raw_path(rel)
    if not fpath:
        return jsonify({'error': '非法路径或文件不存在'}), 400
    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return jsonify({'path': rel, 'size': os.path.getsize(fpath), 'content': content})

@app.route('/api/agent/files/vault/content', methods=['GET'])
def api_get_vault_file_content():
    rel = request.args.get('path', '')
    fpath = _safe_agent_vault_path(rel)
    if not fpath:
        return jsonify({'error': '非法路径或文件不存在'}), 400
    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    rel_out = os.path.relpath(fpath, NOTES_DIR).replace('\\', '/')
    return jsonify({'path': rel_out, 'size': os.path.getsize(fpath), 'content': content})

@app.route('/api/agent/process', methods=['POST'])
def api_agent_process():
    """执行Agent: 读取指定文件 + 提示词 → 调用LLM → 返回结果"""
    data = request.json
    agent_id = data.get('agent')
    file_paths = data.get('file_paths') or []  # raw或vault中的文件路径列表
    user_text = data.get('text', '')  # 额外的文本输入（任务发布用）
    
    if not agent_id or agent_id not in AGENT_CONFIG:
        return jsonify({'error': '无效的Agent'}), 400
    
    cfg = AGENT_CONFIG[agent_id]
    
    # 构建用户消息：包含文件内容 + 文件路径上下文
    user_message_parts = []
    
    if cfg['input_type'] == 'raw_file' and file_paths:
        # 笔记整理师：读取 未分类/ 或 已分类/ 中的 txt 文件
        for fp in file_paths:
            full_path = os.path.join(RAW_DIR, fp.replace('\\', '/').strip('/'))
            if not os.path.exists(full_path):
                full_path = os.path.join(CLASSIFIED_DIR, fp.replace('\\', '/').strip('/'))
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 尝试从路径推断科目
                subject = None
                for abbr, full in SUBJECT_MAP.items():
                    if abbr in fp:
                        subject = full
                        break
                subject_str = f'\n科目: {subject}' if subject else ''
                user_message_parts.append(f'=== 文件: {fp} ==={subject_str}\n\n{content}')
            else:
                return jsonify({'error': f'文件不存在: {fp}'}), 404
        if not user_message_parts:
            return jsonify({'error': '未找到有效文件'}), 400
    
    elif cfg['input_type'] == 'vault_note' and file_paths:
        # 知识点整理师/审查师：读取 vault 中的 md 文件
        for fp in file_paths:
            full_path = os.path.join(NOTES_DIR, fp.replace('\\', '/').strip('/'))
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                user_message_parts.append(f'=== 笔记文件: {fp} ===\n\n{content}')
            else:
                return jsonify({'error': f'笔记不存在: {fp}'}), 404
        if not user_message_parts:
            return jsonify({'error': '未找到有效笔记'}), 400
    
    elif cfg['input_type'] == 'text':
        user_message_parts.append(user_text if user_text else '')
        if not user_text:
            return jsonify({'error': '请输入任务描述'}), 400
        # 为任务发布Agent注入现有任务上下文（含依赖关系）
        if agent_id == 'task_publisher':
            ctx = _build_task_context()
            if ctx:
                user_message_parts.append(ctx)
    
    else:
        user_message_parts.append(user_text if user_text else '')
    
    user_input = '\n\n---\n\n'.join(user_message_parts)
    
    # 加载提示词
    prompt = load_prompt(agent_id)
    if not prompt:
        return jsonify({'error': 'Agent提示词未找到'}), 404
    
    # 任务发布追加自然语言模板
    if agent_id == 'task_publisher':
        template_path = os.path.join(PROMPTS_DIR, 'AI_自然语言模板.md')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                prompt += '\n\n' + f.read()
        prompt += '\n\n请严格输出JSON格式，放在```json代码块中。不要输出任何其他文字。'
    
    try:
        response_text = call_llm(prompt, user_input)
        return jsonify({
            'agent': agent_id,
            'output': response_text,
            'files_processed': file_paths,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/save-note', methods=['POST'])
def api_agent_save_note():
    """将Agent输出保存为笔记/知识点文件到vault"""
    data = request.json
    content = data.get('content', '')
    filename = data.get('filename', 'note').strip()
    subdir = data.get('subdir', '')  # e.g. 高等数学 or 知识点
    
    if not content:
        return jsonify({'error': '内容为空'}), 400
    if not filename.endswith('.md'):
        filename += '.md'
    
    target_dir = os.path.join(NOTES_DIR, subdir) if subdir else NOTES_DIR
    os.makedirs(target_dir, exist_ok=True)
    safe_name = filename.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(target_dir, safe_name)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return jsonify({'saved': True, 'path': filepath, 'relative': os.path.join(subdir, safe_name) if subdir else safe_name})

@app.route('/api/agent/import-tasks', methods=['POST'])
def api_agent_import_tasks():
    """从Agent输出解析任务JSON并导入"""
    data = request.json
    raw_output = data.get('output', '')
    import re
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_output, re.DOTALL)
    raw_json = json_match.group(1) if json_match else raw_output
    try:
        task_data = json.loads(raw_json)
    except json.JSONDecodeError:
        return jsonify({'error': '无法解析JSON，请确认输出格式'}), 400
    
    tasks = task_data.get('tasks', []) or ([task_data.get('task')] if task_data.get('task') else [])
    if not tasks:
        return jsonify({'error': '未找到可导入的任务'}), 400
    
    imported, errors = [], []
    for t in tasks:
        if not t.get('name'): continue
        try:
            task = Task(
                name=t.get('name', '未命名'), category=t.get('category', 'study'),
                estimated_time=t.get('estimated_time', 30), deadline=t.get('deadline'),
                resistance={'低': 'low', '中': 'medium', '高': 'high'}.get(str(t.get('difficulty', t.get('resistance', '中'))), 'medium'),
                energy_required={'低': 'low', '中': 'medium', '高': 'high'}.get(str(t.get('energy_required', t.get('energy', '中'))), 'medium'),
                priority=t.get('priority', 5), repeat_type=t.get('repeat_type', 'none'),
                tags=t.get('tags', []), prerequisite_ids=t.get('prerequisite_ids', []),
                task_profile=t.get('task_profile', 'deadline_flexible'),
            )
            tid = add_task(task)
            imported.append({'id': tid, 'name': t.get('name')})
        except Exception as e:
            errors.append({'name': t.get('name', '?'), 'error': str(e)})
    return jsonify({'imported': len(imported), 'tasks': imported, 'errors': errors})

# ========== 计时器系统 ==========
@app.route('/api/timer/start', methods=['POST'])
def api_timer_start():
    data = request.json
    task_id = data.get('task_id')
    minutes = data.get('planned_minutes', 30)
    if not task_id:
        return jsonify({'error': 'task_id required'}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        now = datetime.now().isoformat()
        # 检查是否已有进行中的计时
        cur.execute('SELECT id FROM timer_sessions WHERE task_id=? AND status="running"', (task_id,))
        if cur.fetchone():
            return jsonify({'error': '该任务已有进行中的计时'}), 400
        cur.execute('INSERT INTO timer_sessions (task_id, started_at, planned_minutes, status) VALUES (?,?,?,?)',
                   (task_id, now, minutes, 'running'))
        conn.commit()
        sid = cur.lastrowid
        return jsonify({'session_id': sid, 'task_id': task_id, 'started_at': now, 'planned_minutes': minutes})
    finally:
        conn.close()

@app.route('/api/timer/complete', methods=['POST'])
def api_timer_complete():
    data = request.json
    session_id = data.get('session_id')
    actual_minutes = data.get('actual_minutes')
    result = data.get('result', 'completed')  # completed / early / abandoned
    reason = data.get('reason', '')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute('''UPDATE timer_sessions SET ended_at=?, actual_minutes=?, status="ended", result=?, reason=?
                       WHERE id=? AND status="running"''',
                   (now, actual_minutes, result, reason, session_id))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': '计时会话未找到或已结束'}), 404
        return jsonify({'ended': True, 'session_id': session_id, 'result': result})
    finally:
        conn.close()

@app.route('/api/timer/active', methods=['GET'])
def api_timer_active():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT ts.id, ts.task_id, ts.started_at, ts.planned_minutes, t.name as task_name
                       FROM timer_sessions ts JOIN tasks t ON ts.task_id=t.id
                       WHERE ts.status="running" ORDER BY ts.started_at DESC LIMIT 1''')
        row = cur.fetchone()
        if row:
            return jsonify(dict(row))
        return jsonify(None)
    finally:
        conn.close()

# ========== 提示词编辑器 ==========
PROMPTS_BACKUP_DIR = os.path.join(PROMPTS_DIR, '.backups')

def _safe_prompt_basename(name):
    """仅允许 prompts 根目录下的 .md 文件名，防路径穿越。"""
    if not name or not isinstance(name, str):
        return None
    raw = name.strip().replace('\\', '/')
    if '..' in raw or raw.startswith('/') or ':' in raw:
        return None
    base = os.path.basename(raw)
    if base != raw or base.startswith('.'):
        return None
    if not base.endswith('.md'):
        return None
    if '.backups' in base:
        return None
    return base

def _prompt_file_path(name):
    safe = _safe_prompt_basename(name)
    if not safe:
        return None
    fpath = os.path.abspath(os.path.join(PROMPTS_DIR, safe))
    prompts_abs = os.path.abspath(PROMPTS_DIR)
    if not fpath.startswith(prompts_abs + os.sep) and fpath != prompts_abs:
        return None
    return fpath

def _create_prompt_backup_file(fpath, basename, kind='save'):
    os.makedirs(PROMPTS_BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    bak_name = f'{basename}.{ts}.{kind}.bak.md'
    bak_path = os.path.join(PROMPTS_BACKUP_DIR, bak_name)
    with open(fpath, 'r', encoding='utf-8') as src:
        content = src.read()
    with open(bak_path, 'w', encoding='utf-8') as dst:
        dst.write(content)
    return bak_name

def _latest_prompt_backup_name(basename, kind='save'):
    if not os.path.isdir(PROMPTS_BACKUP_DIR):
        return None
    prefix = f'{basename}.'
    suffix = f'.{kind}.bak.md'
    files = [
        f for f in os.listdir(PROMPTS_BACKUP_DIR)
        if f.startswith(prefix) and f.endswith(suffix)
        and os.path.isfile(os.path.join(PROMPTS_BACKUP_DIR, f))
    ]
    if not files:
        # 兼容旧格式 *.bak.md（无 save/restore 标记）
        legacy = [
            f for f in os.listdir(PROMPTS_BACKUP_DIR)
            if f.startswith(prefix) and f.endswith('.bak.md') and '.save.bak.md' not in f and '.restore.bak.md' not in f
            and os.path.isfile(os.path.join(PROMPTS_BACKUP_DIR, f))
        ]
        if not legacy:
            return None
        return max(legacy, key=lambda f: os.path.getmtime(os.path.join(PROMPTS_BACKUP_DIR, f)))
    return max(files, key=lambda f: os.path.getmtime(os.path.join(PROMPTS_BACKUP_DIR, f)))

@app.route('/api/prompts', methods=['GET'])
def api_list_prompts():
    files = []
    if not os.path.isdir(PROMPTS_DIR):
        return jsonify(files)
    for fname in sorted(os.listdir(PROMPTS_DIR)):
        if fname.startswith('.') or not fname.endswith('.md'):
            continue
        fpath = os.path.join(PROMPTS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        stat = os.stat(fpath)
        files.append({
            'name': fname,
            'size': stat.st_size,
            'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return jsonify(files)

@app.route('/api/prompts/<path:name>/backup/latest', methods=['GET'])
def api_prompt_backup_latest(name):
    safe = _safe_prompt_basename(name)
    if not safe:
        return jsonify({'error': '非法文件名'}), 400
    fpath = _prompt_file_path(safe)
    if not fpath or not os.path.isfile(fpath):
        return jsonify({'error': '文件不存在'}), 404
    latest = _latest_prompt_backup_name(safe, kind='save')
    if not latest:
        return jsonify({'exists': False, 'name': safe})
    bak_path = os.path.join(PROMPTS_BACKUP_DIR, latest)
    stat = os.stat(bak_path)
    return jsonify({
        'exists': True,
        'name': safe,
        'backup_name': latest,
        'size': stat.st_size,
        'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
    })

@app.route('/api/prompts/<path:name>/restore-latest', methods=['POST'])
def api_prompt_restore_latest(name):
    safe = _safe_prompt_basename(name)
    if not safe:
        return jsonify({'error': '非法文件名'}), 400
    fpath = _prompt_file_path(safe)
    if not fpath or not os.path.isfile(fpath):
        return jsonify({'error': '文件不存在'}), 404
    latest = _latest_prompt_backup_name(safe, kind='save')
    if not latest:
        return jsonify({'error': '无可用备份'}), 404
    bak_path = os.path.join(PROMPTS_BACKUP_DIR, latest)
    try:
        with open(bak_path, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        if os.path.isfile(fpath):
            _create_prompt_backup_file(fpath, safe, kind='restore')
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(backup_content)
        return jsonify({'restored': True, 'name': safe, 'backup_used': latest})
    except OSError as e:
        return jsonify({'error': '恢复失败: ' + str(e)}), 500

@app.route('/api/prompts/<path:name>', methods=['GET'])
def api_get_prompt(name):
    safe = _safe_prompt_basename(name)
    if not safe:
        return jsonify({'error': '非法文件名'}), 400
    fpath = _prompt_file_path(safe)
    if not fpath or not os.path.isfile(fpath):
        return jsonify({'error': '文件不存在'}), 404
    with open(fpath, 'r', encoding='utf-8') as f:
        return jsonify({'name': safe, 'content': f.read()})

@app.route('/api/prompts/<path:name>', methods=['PUT'])
def api_save_prompt(name):
    safe = _safe_prompt_basename(name)
    if not safe:
        return jsonify({'error': '非法文件名'}), 400
    fpath = _prompt_file_path(safe)
    if not fpath or not os.path.isfile(fpath):
        return jsonify({'error': '文件不存在'}), 404
    data = request.json or {}
    content = data.get('content', '')
    try:
        backup_name = _create_prompt_backup_file(fpath, safe)
        tmp_path = fpath + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, fpath)
        return jsonify({'saved': True, 'name': safe, 'backup': backup_name})
    except OSError as e:
        tmp_path = fpath + '.tmp'
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return jsonify({'error': '保存失败: ' + str(e)}), 500

# ========== 状态评估系统 ==========

# 评估问题（1-5分）
ASSESSMENT_QUESTIONS = [
    {"id": "cognitive", "q": "今天脑子转得动吗？思路清晰吗？", "reverse": False, "weight": 0.25},
    {"id": "focus", "q": "做题时容易分心走神吗？", "reverse": True, "weight": 0.20},
    {"id": "physical", "q": "有头晕、眼涩或身体不适吗？", "reverse": True, "weight": 0.15},
    {"id": "alertness", "q": "经常走神打哈欠吗？", "reverse": True, "weight": 0.20},
    {"id": "efficiency", "q": "学习效率感觉怎么样？", "reverse": False, "weight": 0.15},
    {"id": "motivation", "q": "面对困难任务想逃避吗？", "reverse": True, "weight": 0.05},
]

def calculate_state_scores(answers, version=1):
    """根据答题计算精力/专注/心情分数。版本号用于迭代优化。"""
    scores = {}
    for q in ASSESSMENT_QUESTIONS:
        raw = int(answers.get(q['id'], 3))
        scores[q['id']] = (6 - raw) if q['reverse'] else raw  # reverse: 5→1, 1→5
    
    if version == 1:
        # V1 公式：加权平均 → 映射到 1-10
        energy = (scores['cognitive'] * 0.30 + scores['physical'] * 0.25 + 
                  scores['alertness'] * 0.25 + scores['efficiency'] * 0.20) * 2
        focus = scores['focus'] * 2
        mood = (scores['efficiency'] * 0.40 + scores['motivation'] * 0.35 + 
                scores['cognitive'] * 0.25) * 2
        
        avg = (energy + focus + mood) / 3
        if avg >= 7.0:
            tone = 'high'
        elif avg >= 5.0:
            tone = 'normal'
        elif avg >= 3.0:
            tone = 'low'
        else:
            tone = 'rest'
    else:
        energy = focus = mood = 5.0
        tone = 'normal'
    
    return {
        'energy_score': round(energy, 1),
        'focus_score': round(focus, 1),
        'mood_score': round(mood, 1),
        'daily_tone': tone,
        'formula_version': version,
    }

@app.route('/api/state/questions', methods=['GET'])
def api_get_assessment_questions():
    return jsonify({'questions': ASSESSMENT_QUESTIONS, 'scale': {'min': 1, 'max': 5, 'label': '1=完全不符, 5=完全符合'}})

@app.route('/api/state/assessment', methods=['GET'])
def api_get_today_assessment():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM state_assessments WHERE date=?', (today,))
        row = cur.fetchone()
        if row:
            return jsonify({
                'date': row['date'],
                'answers': json.loads(row['answers']),
                'daily_tone': row['daily_tone'],
                'energy_score': row['energy_score'],
                'focus_score': row['focus_score'],
                'mood_score': row['mood_score'],
                'formula_version': row['formula_version'],
                'completed': True,
            })
        return jsonify({'date': today, 'completed': False, 'questions': ASSESSMENT_QUESTIONS})
    finally:
        conn.close()

@app.route('/api/state/assessment', methods=['POST'])
def api_submit_assessment():
    data = request.json
    answers = data.get('answers', {})
    if not answers:
        return jsonify({'error': '请回答所有问题'}), 400
    
    today = datetime.now().strftime('%Y-%m-%d')
    scores = calculate_state_scores(answers)
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''INSERT OR REPLACE INTO state_assessments (date, answers, daily_tone, energy_score, focus_score, mood_score, formula_version, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (today, json.dumps(answers), scores['daily_tone'], scores['energy_score'],
                    scores['focus_score'], scores['mood_score'], scores['formula_version'],
                    datetime.now().isoformat()))
        conn.commit()
        return jsonify({**scores, 'date': today, 'completed': True})
    finally:
        conn.close()

@app.route('/api/state/assessment/history', methods=['GET'])
def api_get_assessment_history():
    days = int(request.args.get('days', 14))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT date, daily_tone, energy_score, focus_score, mood_score FROM state_assessments ORDER BY date DESC LIMIT ?', (days,))
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()

@app.route('/api/state/assessment/correlate', methods=['GET'])
def api_get_correlation():
    """分析评估数据与实际任务完成率的相关性，用于优化公式"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''SELECT sa.date, sa.energy_score, sa.focus_score, sa.mood_score, sa.answers, sa.daily_tone,
                       (SELECT COUNT(*) FROM tasks WHERE updated_at LIKE sa.date || '%' AND completed=1) as completed,
                       (SELECT COUNT(*) FROM task_completion_feedback WHERE timestamp LIKE sa.date || '%') as feedback_count
                       FROM state_assessments sa ORDER BY sa.date DESC LIMIT 30''')
        rows = [dict(r) for r in cur.fetchall()]
        
        # 简单的相关性统计
        total = len(rows)
        if total < 3:
            return jsonify({'message': '样本不足，需至少3天数据', 'samples': total})
        
        # 按基调分组统计完成率
        tone_stats = {}
        for r in rows:
            t = r['daily_tone']
            if t not in tone_stats:
                tone_stats[t] = {'days': 0, 'total_completed': 0}
            tone_stats[t]['days'] += 1
            tone_stats[t]['total_completed'] += (r['completed'] or 0)
        
        for t in tone_stats:
            tone_stats[t]['avg_completed'] = round(tone_stats[t]['total_completed'] / max(1, tone_stats[t]['days']), 1)
        
        return jsonify({
            'samples': total,
            'tone_stats': tone_stats,
            'latest': rows[:7],
        })
    finally:
        conn.close()

if __name__ == '__main__':
    port = CONFIG['server']['port']
    host = CONFIG['server']['host']
    debug = CONFIG['server']['debug']
    print(f"[CONFIG] Using port: {port}")
    print(f"[CONFIG] Notes directory: {NOTES_DIR}")
    migrate_dependency_data()
    conn = get_db_connection()
    try:
        ensure_task_dependency_schema(conn)
        ensure_schedule_schema(conn)
        ensure_timer_schema(conn)
        ensure_assessment_schema(conn)
        ensure_daily_state_schema(conn)
        ensure_task_feedback_events_schema(conn)
        ensure_indexes(conn)
        sync_all_unlock_states(conn)
    finally:
        conn.close()
    app.run(host=host, port=port, debug=debug)