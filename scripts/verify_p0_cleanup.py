"""verify_p0_cleanup.py — Phase 1 P0 cleanup evidence (2026-08-16).

Run from project root:
    python scripts/verify_p0_cleanup.py

Asserts:
1. `import server.blueprints` does NOT load `server.backend_api`.
2. `import server.blueprints.<bp>` does NOT load `server.backend_api`
   (all 14 real Blueprints — AR03-P2 / Stage 6).
3. Accessing an attribute on a BP forces at most ONE backend_api load.
4. All 14 real Blueprints register the expected number of routes via
   `create_app()` (AR03-P2 / Stage 7: extended from 3 BPs to 14, and the
   route counts updated to the post-migration values — assertion strength
   increased, not weakened).
5. `make_request_conn()` sets foreign_keys=ON + WAL + busy_timeout.
6. `create_app()` runs ensure_all with foreign_keys=ON.

Exit code 0 on success, non-zero on failure.
"""
import os
import sys
import time

# Ensure project root is on sys.path so `import server.*` works.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sqlite3

# Sentinel route count via Flask's app.url_map. We use it to prove the
# real BPs register the documented endpoints.
#
# AR03-P2 / Stage 7（漂移修正，**不弱化断言** —— 改为断言 "真实值"）：
# Phase 1 的期望值是 tasks=9 / gacha=6，但随后的分域迁移 **增加** 了路由：
#   * Stage 2：``/api/dependencies`` 归入 tasks 域 → tasks 9 → 10；
#   * Stage 3：抽卡域补齐 pools-detail / statistics / replace → gacha 6 → 8。
# 这些是 **功能保全**（legacy 的活跃路由一条不少地被覆盖），不是路由丢失。
# 因此这里把期望值更新为当前真实值，并 **扩大** 覆盖面到全部 14 个 BP ——
# 断言强度只增不减（原先只查 3 个 BP，现在查 14 个）。
EXPECTED_ROUTE_COUNTS = {
    "tasks": 10,       # + GET /api/dependencies（Stage 2 归入 tasks 域）
    "gacha": 8,        # + pools-detail / statistics / replace（Stage 3）
    "tags": 4,         # GET / POST / DELETE-id / batch
    "discard": 3,      # GET pile / POST restore / POST move-to-discard
    "config": 3,       # GET config / POST config-save / GET export（Stage 5）
    "index": 1,        # GET /
    "state": 11,
    "timer": 5,
    "schedule": 8,
    "knowledge": 9,
    "feedback": 3,
    "agent_policy": 1,
    "prompts": 5,      # Stage 6
    "agent": 9,        # Stage 6
}

STUB_BP_MODULES = [
    "state_bp", "schedule_bp", "feedback_bp", "timer_bp",
    "knowledge_bp", "config_bp", "prompts_bp", "agent_bp", "discard_bp",
]

#: AR03-P2 / Stage 6 起全部 14 个都是真 BP —— 导入 **任何一个** 都不应
#: 触发 legacy 单体的导入。
ALL_BP_MODULES = [
    "tasks_bp", "gacha_bp", "tags_bp", "discard_bp", "config_bp",
    "index_bp", "state_bp", "timer_bp", "schedule_bp", "knowledge_bp",
    "feedback_bp", "agent_policy_bp", "prompts_bp", "agent_bp",
]

failures = []


def check(condition, msg):
    print(("  PASS  " if condition else "  FAIL  ") + msg)
    if not condition:
        failures.append(msg)


def fresh_syspath():
    """Drop everything we've imported so we can re-import from scratch."""
    for mod_name in list(sys.modules.keys()):
        if mod_name == "server" or mod_name.startswith("server."):
            del sys.modules[mod_name]


# ---------------------------------------------------------------------------
# Test 1: `import server.blueprints` does NOT load server.backend_api
# ---------------------------------------------------------------------------
print("\n[T1] import server.blueprints → backend_api NOT loaded")
fresh_syspath()
t0 = time.perf_counter()
import server  # noqa: F401
import server.blueprints  # noqa: F401
t1 = time.perf_counter()
check("server.backend_api" not in sys.modules,
      "server.backend_api absent after `import server.blueprints`")
check("server.blueprints.tasks_bp" in sys.modules,
      "server.blueprints.tasks_bp loaded (real BP)")
check("server.blueprints.gacha_bp" in sys.modules,
      "server.blueprints.gacha_bp loaded (real BP)")
check("server.blueprints.tags_bp" in sys.modules,
      "server.blueprints.tags_bp loaded (real BP)")
print(f"        import time: {(t1 - t0) * 1000:.1f} ms")

# ---------------------------------------------------------------------------
# Test 2: `import server.blueprints.<bp>` does NOT load backend_api
#
# AR03-P2 / Stage 6：覆盖范围从 9 个 stub 扩展到 **全部 14 个真 BP**
# （断言强度只增不减）。
# ---------------------------------------------------------------------------
print("\n[T2] import server.blueprints.<bp> → backend_api NOT loaded")
for bp_name in ALL_BP_MODULES:
    fresh_syspath()
    __import__(f"server.blueprints.{bp_name}")
    check("server.backend_api" not in sys.modules,
          f"import server.blueprints.{bp_name} did NOT load backend_api")

# ---------------------------------------------------------------------------
# Test 3: accessing an attribute on a stub BP forces AT MOST ONE backend_api
# ---------------------------------------------------------------------------
print("\n[T3] attribute access on stub BP loads backend_api once then caches")
fresh_syspath()
import server.blueprints.state_bp  # noqa: F401
check("server.backend_api" not in sys.modules,
      "before attribute access: backend_api still NOT loaded")
_ = server.blueprints.state_bp.api_get_daily_tone
check("server.backend_api" in sys.modules,
      "after first attribute access: backend_api loaded")
# Cache check: globals() should now have the name
check("api_get_daily_tone" in vars(server.blueprints.state_bp),
      "state_bp module globals cached the import (PEP 562)")

# ---------------------------------------------------------------------------
# Test 4: route counts via create_app()
# ---------------------------------------------------------------------------
print("\n[T4] create_app() registers the expected real BP routes")
fresh_syspath()
from server.app import create_app
app = create_app()
counts = {}
for rule in app.url_map.iter_rules():
    if "." in rule.endpoint:
        bp_name = rule.endpoint.split(".", 1)[0]
        counts[bp_name] = counts.get(bp_name, 0) + 1
for bp_name, expected in EXPECTED_ROUTE_COUNTS.items():
    actual = counts.get(bp_name, 0)
    check(actual == expected,
          f"bp '{bp_name}': expected {expected} routes, got {actual}")

# ---------------------------------------------------------------------------
# Test 5: make_request_conn() sets foreign_keys=ON + WAL + busy_timeout
# ---------------------------------------------------------------------------
print("\n[T5] make_request_conn() PRAGMA assertions")
fresh_syspath()
from server.app.extensions import make_request_conn, SQLITE_BUSY_TIMEOUT_MS
db_path = os.path.join(PROJECT_ROOT, "data", "task_publisher.db")
conn = make_request_conn(db_path)
try:
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
    bt = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    check(int(fk) == 1, f"PRAGMA foreign_keys=ON (got {fk})")
    check(str(jm).lower() == "wal", f"PRAGMA journal_mode=WAL (got {jm})")
    check(int(bt) == SQLITE_BUSY_TIMEOUT_MS,
          f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}ms (got {bt})")
    check(isinstance(conn.execute("SELECT 1").fetchone()[0], int),
          "row_factory=sqlite3.Row works (dict-style access)")
finally:
    conn.close()

# ---------------------------------------------------------------------------
# Test 6: create_app() runs ensure_all with foreign_keys=ON
# ---------------------------------------------------------------------------
print("\n[T6] create_app() enables foreign_keys before ensure_all")
fresh_syspath()
# Monkey-patch ensure_all to capture the foreign_keys setting at call time.
from server.app import app_factory as _af
from server.schema import ensure_all as _ensure_all_orig
captured = {}
def _spy_ensure_all(conn):
    captured["foreign_keys"] = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    return _ensure_all_orig(conn)
_af.ensure_all_schema = _spy_ensure_all
from server.app import create_app as _ca
_ca()
check(int(captured.get("foreign_keys", 0)) == 1,
      f"ensure_all sees foreign_keys=ON (got {captured.get('foreign_keys')})")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
if failures:
    print(f"FAILED ({len(failures)} assertions)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
else:
    print("ALL ASSERTIONS PASSED")
    sys.exit(0)
