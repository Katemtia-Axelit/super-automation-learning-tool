"""
补全数据库表的初始化脚本 + 追加任务

修复问题：
1. Flask 的 migrate_dependency_data() 在 task_dependencies 表创建前执行
2. 缺少 gacha_records, task_rejection_log 等表
3. 没有 CET4 任务
"""

import sqlite3, json, re, datetime, shutil
from pathlib import Path
from typing import List, Dict

DB_PATH = Path(__file__).parent.parent / "data" / "task_publisher.db"


# ========== 完整建表语句（来自 Flask backend） ==========
def init_all_tables(conn):
    """创建所有需要的表和缺失的列"""
    cur = conn.cursor()

    # 1. tasks 表（含完整字段）
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT 'normal',
            task_type TEXT DEFAULT 'other',
            description TEXT,
            estimated_time INTEGER,
            preferred_time TEXT,
            deadline TEXT,
            resistance TEXT,
            energy_required TEXT,
            rarity TEXT DEFAULT 'common',
            priority INTEGER DEFAULT 5,
            success_rate REAL DEFAULT 0.0,
            refusal_count INTEGER DEFAULT 0,
            is_daily BOOLEAN DEFAULT 0,
            completed BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            prerequisite_ids TEXT DEFAULT '[]',
            is_unlocked INTEGER DEFAULT 1,
            difficulty TEXT,
            draw_count_today INTEGER DEFAULT 0,
            last_drawn_at TEXT,
            min_push_time TEXT DEFAULT '20:00',
            in_discard_pile BOOLEAN DEFAULT 0,
            completed_count INTEGER DEFAULT 0,
            repeat_type TEXT DEFAULT 'none',
            last_completed_at TEXT,
            next_available_at TEXT
        )
    ''')

    # 2. tags 表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # 3. task_tags 表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_tags (
            task_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (task_id, tag_id)
        )
    ''')

    # 4. task_dependencies 表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            depends_on_task_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
        )
    ''')

    # 5. user_schedule 表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER,
            time_slot TEXT,
            activity TEXT,
            is_regular BOOLEAN DEFAULT 1
        )
    ''')

    # 6. daily_schedules 表
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

    # 7. activities 表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # 8. timer_sessions 表
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

    # 9. task_feedback_events 表
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

    # 10. state_assessments 表
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

    # 11. daily_user_state 表
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

    # 12. task_completion_feedback 表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_completion_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            energy_after INTEGER,
            mood_after INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')

    # 13. gacha_records 表（缺失！）
    cur.execute('''
        CREATE TABLE IF NOT EXISTS gacha_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pool_name TEXT NOT NULL,
            available_time INTEGER,
            task_id INTEGER,
            accepted BOOLEAN,
            refusal_reason TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')

    # 14. task_rejection_log 表（缺失！）
    cur.execute('''
        CREATE TABLE IF NOT EXISTS task_rejection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')

    # 幂等补列（安全添加缺失列）
    def add_col(table, col, col_type, default=None):
        try:
            if default is not None:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {default}")
            else:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass

    for table in ['tasks', 'tags', 'task_tags']:
        add_col(table, 'x_task_id', 'INTEGER')
        add_col(table, 'x_depends_on', 'INTEGER')

    conn.commit()
    print(f"  tables initialized")


# ========== 迁移现有任务的依赖关系到 task_dependencies ==========
def migrate_dependencies(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]'")
        count = cur.fetchone()['cnt']
        if count == 0:
            print("  no dependencies to migrate")
            return
        cur.execute("SELECT id, prerequisite_ids FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]'")
        migrated = 0
        for row in cur.fetchall():
            try:
                prereqs = json.loads(row['prerequisite_ids'] or '[]')
                for pid in prereqs:
                    cur.execute(
                        'INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?,?)',
                        (row['id'], pid)
                    )
                migrated += 1
            except:
                pass
        conn.commit()
        print(f"  migrated {migrated} tasks with dependencies")
    except Exception as e:
        print(f"  migrate_dependencies: {e}")


# ========== 任务写入（复用 v4 逻辑） ==========
VAULT_DIR = Path(__file__).parent.parent / "src" / "notes" / "vault"

SUBJECT_CONFIG = {
    "高等数学": {
        "display": "高数",
        "notes_pattern": r"^(\d{2}-\d{2})_",
        "modules": [
            ("第6章", "06-01", "06-06"),
            ("第7章", "07-01", "07-06"),
            ("第8章", "08-01", "08-02"),
            ("第9章", "09-01", "09-02"),
            ("第10章", "10-01", "10-06"),
            ("第11章", "11-01", "11-07"),
        ],
        "exam_logic": 1,
        "num_exams": 3,
    },
    "线性代数": {
        "display": "线代",
        "notes_pattern": r"^(\d{2})_",
        "modules": [
            ("向量与空间", "01", "05"),
            ("矩阵与特征值", "06", "09"),
            ("初等变换与行列式", "10", "13"),
        ],
        "exam_logic": 1,
        "num_exams": 2,
    },
    "大学物理": {
        "display": "大物",
        "notes_pattern": r"^(\d{2})_",
        "modules": [
            ("力学", "01", "06"),
            ("刚体与振动", "07", "11"),
            ("波动", "12", "13"),
            ("热学", "14", "17"),
            ("光学", "18", "21"),
            ("电磁学", "22", "24"),
        ],
        "exam_logic": 2,
        "num_exams": 3,
    },
    "计算机": {
        "display": "计算机",
        "notes_pattern": r"^(\d{2})_",
        "modules": [
            ("系统与硬件", "01", "04"),
            ("数据编码", "05", "08"),
            ("指令与程序", "09", "12"),
        ],
        "exam_logic": 1,
        "num_exams": 1,
    },
    "电子技术": {
        "display": "电子技术",
        "notes_pattern": r"^(\d{2})_",
        "modules": [
            ("半导体器件", "01", "03"),
            ("电路分析", "04", "07"),
            ("数字电路", "08", "12"),
        ],
        "exam_logic": 1,
        "num_exams": 1,
    },
    # CET4: 单独处理，无编号格式
    "英语四级": {
        "display": "CET4",
        "notes_pattern": None,  # 不用编号格式
        "modules": [
            ("写作", "写作", "写作"),
            ("听力", "听力", "听力"),
            ("阅读", "阅读", "阅读"),
            ("语法", "语法", "语法"),
        ],
        "exam_logic": None,
        "num_exams": 0,
    },
}


def scan_notes(vault_dir, subject, pattern):
    dir_path = vault_dir / subject
    results = []
    for f in sorted(dir_path.glob("*.md")):
        m = re.match(pattern, f.stem) if pattern else None
        if m:
            num = m.group(1)
            title = f.stem[len(m.group(0)):]
            results.append((num, title))
    return results


def note_in_range(num, start, end):
    return start <= num <= end


class Writer:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
        self.name_to_id = {}
        self.stats = {"created": 0, "updated": 0}

    def load(self):
        self.cur.execute("SELECT id, name FROM tasks")
        for r in self.cur.fetchall():
            self.name_to_id[r["name"]] = r["id"]

    def upsert(self, name, prereqs=None, task_type="note", priority=50,
               tags=None, subject=""):
        prereq_json = json.dumps(prereqs or [])
        unlocked = 1 if not prereqs else 0
        now = datetime.datetime.now().isoformat()

        if name in self.name_to_id:
            self.cur.execute(
                "UPDATE tasks SET prerequisite_ids=?, is_unlocked=?, task_type=?, updated_at=? WHERE id=?",
                (prereq_json, unlocked, task_type, now, self.name_to_id[name])
            )
            self.stats["updated"] += 1
            tid = self.name_to_id[name]
        else:
            self.cur.execute(
                "INSERT INTO tasks (name,priority,prerequisite_ids,is_unlocked,task_type,category,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (name, priority, prereq_json, unlocked, task_type, "normal", now, now)
            )
            tid = self.cur.lastrowid
            self.name_to_id[name] = tid
            self.stats["created"] += 1

        if tags:
            self._set_tags(tid, [subject] + tags)
        return tid

    def _set_tags(self, tid, tags):
        for tag in tags:
            self.cur.execute("SELECT id FROM tags WHERE name=?", (tag,))
            row = self.cur.fetchone()
            tag_id = row["id"] if row else None
            if not tag_id:
                self.cur.execute("INSERT INTO tags (name) VALUES (?)", (tag,))
                tag_id = self.cur.lastrowid
            self.cur.execute("INSERT OR IGNORE INTO task_tags (task_id,tag_id) VALUES (?,?)", (tid, tag_id))

    def commit(self):
        self.conn.commit()


def scan_cet4_notes(vault_dir):
    """CET4 没有编号，直接扫描模块文件中的 wiki 链接"""
    cet4_dir = vault_dir / "英语四级"
    modules = {
        "写作": [],
        "听力": [],
        "阅读": [],
        "语法": [],
    }
    module_files = {
        "写作": cet4_dir / "英语四级-写作.md",
        "听力": cet4_dir / "英语四级-听力.md",
        "阅读": cet4_dir / "英语四级-阅读.md",
        "语法": cet4_dir / "英语四级-语法.md",
    }
    for mod_name, fpath in module_files.items():
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            # 匹配 [[CET4-xxx-yyy]]
            links = re.findall(r'\[\[CET4[^\]]+\]\]', content)
            for link in links:
                # 提取文件名: [[CET4-写作-句子扩写与句型改写]] -> CET4-写作-句子扩写与句型改写
                fname = link[2:-2]
                modules[mod_name].append(fname)
    return modules


def build_subject(w: Writer, subject, cfg):
    display = cfg["display"]
    pattern = cfg.get("notes_pattern")
    modules = cfg["modules"]

    print(f"\n=== {subject} ({display}) ===")

    if pattern:
        all_notes = scan_notes(VAULT_DIR, subject, pattern)
        print(f"  scan {len(all_notes)} notes")
        module_note_lists = []
        for mod_name, start, end in modules:
            mod_notes = [(n, t) for n, t in all_notes if note_in_range(n, start, end)]
            module_note_lists.append((mod_name, mod_notes))
    else:
        # CET4: 直接扫描模块文件
        cet4_notes = scan_cet4_notes(VAULT_DIR)
        module_note_lists = []
        for mod_name, _, _ in modules:
            notes = cet4_notes.get(mod_name, [])
            module_note_lists.append((mod_name, notes))
        print(f"  CET4 modules: {[(m, len(n)) for m, n in module_note_lists]}")

    for mn, notes in module_note_lists:
        print(f"  - {mn}: {len(notes)} notes")

    module_review_ids = []
    module_exam_ids = []

    for mod_idx, (mod_name, notes) in enumerate(module_note_lists):
        prev_id = None
        exercise_ids = []

        for n_idx, note_item in enumerate(notes):
            if pattern:
                note_num, title = note_item
            else:
                # CET4: note_item 就是文件名
                title = note_item
                note_num = str(n_idx + 1).zfill(2)

            if pattern:
                nname = f"{display}-{mod_name}-{note_num}_{title}-复习"
                ename = f"{display}-{mod_name}-{note_num}_{title}-习题"
            else:
                # CET4 格式
                nname = f"{display}-{mod_name}-{title}-复习"
                ename = f"{display}-{mod_name}-{title}-习题"

            nid = w.upsert(nname, prereqs=[prev_id] if prev_id else [],
                          task_type="note", priority=90 - mod_idx * 5 - n_idx,
                          tags=["复习"], subject=display)
            prev_id = nid

            eid = w.upsert(ename, prereqs=[nid],
                          task_type="exercise", priority=80 - mod_idx * 5 - n_idx,
                          tags=["习题"], subject=display)
            exercise_ids.append(eid)

        if pattern:
            mrname = f"{display}-{mod_name}-章节复习"
        else:
            mrname = f"{display}-{mod_name}-章节复习"
        mrnid = w.upsert(mrname, prereqs=[prev_id] if prev_id else [],
                         task_type="chapter_review", priority=60 - mod_idx * 5,
                         tags=["章节复习"], subject=display)
        module_review_ids.append(mrnid)

        if pattern:
            mename = f"{display}-{mod_name}-章节总习题"
        else:
            mename = f"{display}-{mod_name}-章节总习题"
        meid = w.upsert(mename, prereqs=exercise_ids,
                        task_type="chapter_exam", priority=50 - mod_idx * 5,
                        tags=["章节总习题"], subject=display)
        module_exam_ids.append(meid)

    w.commit()

    # 跨模块衔接
    print(f"\n  [cross-module links]")
    for mod_idx in range(1, len(module_note_lists)):
        prev_rev_id = module_review_ids[mod_idx - 1]
        this_mod_name = module_note_lists[mod_idx][0]
        this_notes = module_note_lists[mod_idx][1]

        if not this_notes:
            continue

        if pattern:
            first_note_num = this_notes[0][0]
            first_note_title = this_notes[0][1]
            first_name = f"{display}-{this_mod_name}-{first_note_num}_{first_note_title}-复习"
        else:
            first_title = this_notes[0]
            first_name = f"{display}-{this_mod_name}-{first_title}-复习"

        if first_name in w.name_to_id:
            first_id = w.name_to_id[first_name]
            w.cur.execute(
                "UPDATE tasks SET prerequisite_ids=?, is_unlocked=0, updated_at=? WHERE id=?",
                (json.dumps([prev_rev_id]), datetime.datetime.now().isoformat(), first_id)
            )
            print(f"  [{mod_idx}] {first_name} <- locked by prev chapter review")

    w.commit()

    # 真题链
    logic = cfg.get("exam_logic")
    n_exams = cfg.get("num_exams", 0)
    if logic and n_exams > 0 and module_exam_ids:
        print(f"\n  [exam logic={logic}, {n_exams} papers]")
        build_exam_chain(w, display, module_exam_ids, logic, n_exams)

    w.commit()


def build_exam_chain(w, display, module_exam_ids, logic, n_exams):
    qtypes = ["选择题", "填空题", "计算题"]
    if logic == 1:
        prev = None
        for ei in range(1, n_exams + 1):
            qids = []
            for qt in qtypes:
                qname = f"{display}-真题卷{ei}-{qt}"
                qid = w.upsert(qname, prereqs=module_exam_ids,
                               task_type="exam_question", priority=30,
                               tags=["真题", f"卷{ei}", qt], subject=display)
                qids.append(qid)
            prereqs = qids if prev is None else qids + [prev]
            rname = f"{display}-真题卷{ei}-批改并复盘"
            rid = w.upsert(rname, prereqs=prereqs,
                          task_type="exam_review", priority=25,
                          tags=["真题", f"卷{ei}", "批改"], subject=display)
            print(f"  [exam] {rname}")
            prev = rid
    elif logic == 2:
        for ei in range(1, n_exams + 1):
            all_qids = []
            for ci, me_id in enumerate(module_exam_ids):
                for qt in qtypes:
                    qname = f"{display}-真题卷{ei}-{qt}(第{ci+1}模块)"
                    qid = w.upsert(qname, prereqs=[me_id],
                                   task_type="exam_question", priority=30,
                                   tags=["真题", f"卷{ei}", f"第{ci+1}模块", qt], subject=display)
                    all_qids.append(qid)
            rname = f"{display}-真题卷{ei}-批改并复盘"
            rid = w.upsert(rname, prereqs=all_qids,
                          task_type="exam_review", priority=25,
                          tags=["真题", f"卷{ei}", "批改"], subject=display)
            print(f"  [exam] {rname} ({len(all_qids)} q)")


# ========== 主程序 ==========
if __name__ == "__main__":
    print("=" * 50)
    print("Task Rebuild Script v5 (complete tables + CET4)")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. 建所有表
    print("\n[1] Initializing all tables...")
    init_all_tables(conn)

    # 2. 迁移依赖关系
    print("\n[2] Migrating dependencies...")
    migrate_dependencies(conn)

    # 3. 写入任务
    print("\n[3] Writing tasks...")
    w = Writer(conn)
    w.load()
    print(f"  existing: {len(w.name_to_id)}")

    for subj, cfg in SUBJECT_CONFIG.items():
        build_subject(w, subj, cfg)

    print(f"\n{'='*50}")
    print(f"Result: created={w.stats['created']}, updated={w.stats['updated']}")

    # 验证解锁状态
    w.cur.execute("SELECT id, name FROM tasks WHERE is_unlocked=1 AND (prerequisite_ids='[]' OR prerequisite_ids IS NULL)")
    print(f"\nUnlocked (no prereq):")
    for r in w.cur.fetchall():
        print(f"  [{r['id']}] {r['name']}")

    conn.commit()
    conn.close()
    print("\nDone!")
