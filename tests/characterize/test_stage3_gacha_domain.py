"""AR03-P2 / Stage 3 — 抽卡域的 **分层契约** 与 **行为不回归** 测试。

Stage 3 把抽卡域的 SQL 从三处（蓝图 / service / 转发壳 repo）收敛到
:mod:`server.repositories.gacha_repo`，编排收敛到
:mod:`server.services.gacha`。

本文件锁定：

1. **分层方向** —— repo 不依赖 service / blueprint / Flask；蓝图不写裸 SQL；
2. **台账口径** —— 发行行与拒绝行 **严格分离**（``/api/gacha/statistics``
   的核心口径）；
3. **事务原子性** —— 发牌 + 计数 + 台账要么全成、要么全不成；
4. **卡池边界** —— 15 / 45 分钟边界任务归 **上** 一个卡池；
5. **换牌顺序** —— 理由校验 → 候选解析 → 记账；候选失败 **零副作用**；
6. **算法不变** —— Gacha Golden 100,250 组 ``max_diff = 0``（由
   ``scripts/phase2_gacha_golden.py`` 独立复验）。

全程 **不** 触碰生产数据库：全部在 ``tests/characterize/sandbox_env.py``
的合成根内。
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tokenize
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GACHA_BP = PROJECT_ROOT / "server" / "blueprints" / "gacha_bp.py"
GACHA_SERVICE = PROJECT_ROOT / "server" / "services" / "gacha.py"
GACHA_REPO = PROJECT_ROOT / "server" / "repositories" / "gacha_repo.py"

_SQL_MARKERS = ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM")


def _code_only(path: Path) -> str:
    """只保留可执行代码（去掉注释与字符串字面量）。"""
    out = []
    try:
        tokens = tokenize.generate_tokens(
            io.StringIO(path.read_text(encoding="utf-8")).readline
        )
        for token in tokens:
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(token.string)
    except (tokenize.TokenError, IndentationError):
        return path.read_text(encoding="utf-8")
    return " ".join(out)


class GachaLayeringTests(unittest.TestCase):
    def test_repo_has_no_flask_service_or_blueprint_dependency(self):
        code = _code_only(GACHA_REPO)
        for forbidden in (
            "server.services",
            "server.blueprints",
            "from flask",
            "import flask",
            "server.backend_api",
        ):
            self.assertNotIn(forbidden, code, "gacha_repo 依赖越界: " + forbidden)

    def test_service_has_no_flask_dependency(self):
        code = _code_only(GACHA_SERVICE)
        self.assertNotIn("from flask", code)
        self.assertNotIn("import flask", code)

    def test_blueprint_has_no_raw_sql(self):
        code = _code_only(GACHA_BP)
        for marker in _SQL_MARKERS:
            self.assertNotIn(marker, code, "gacha_bp 仍含裸 SQL: " + marker)
        self.assertNotIn(".execute(", code, "gacha_bp 直接执行 SQL")

    def test_blueprint_delegates_to_service_and_repo(self):
        text = GACHA_BP.read_text(encoding="utf-8")
        self.assertIn("from server.services import gacha as gacha_service", text)
        self.assertIn("from server.repositories import gacha_repo", text)

    def test_service_delegates_sql_to_repo(self):
        text = GACHA_SERVICE.read_text(encoding="utf-8")
        self.assertIn("from server.repositories import gacha_repo", text)
        # record_* 系列必须经由 repo
        for name in ("record_draw", "record_issuance", "record_rejection"):
            self.assertIn(f"gacha_repo.", text.split(f"def {name}")[1][:900])


_RUNNER = r'''
import json, sqlite3, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app
from server.repositories.db import write_connection
from server.services import gacha as gacha_service

db = root / "data" / "stage3.sqlite3"
if db.exists():
    db.unlink()

def make_cfg():
    return {
        "server": {"host": "127.0.0.1", "port": 0, "debug": False},
        "obsidian": {"vault_path": "vault", "notes_directory": "vault"},
        "api": {"openai_api_key": "", "claude_api_key": ""},
        "database": {"task_db_path": str(Path(db).relative_to(root))},
        "_project_root": str(root),
        "_static_dir": str(root / "static"),
        "_db_path": str(db),
        "_notes_dir": str(root / "vault"),
        "_config_path": str(root / "config" / "config.json"),
    }

app = create_app(make_cfg())
client = app.test_client()
out = {}

# ---- 1. 建三张时长分属三个卡池的任务 --------------------------------------
for name, minutes in (("SHORT", 10), ("MID", 30), ("LONG", 60)):
    client.post("/api/tasks", json={
        "name": name, "category": "study", "estimated_time": minutes,
    })

# ---- 2. 卡池边界：15 与 45 归 上 一个池 ----------------------------------
client.post("/api/tasks", json={
    "name": "EDGE15", "category": "study", "estimated_time": 15})
client.post("/api/tasks", json={
    "name": "EDGE45", "category": "study", "estimated_time": 45})

detail = client.get("/api/gacha/pools/detail").get_json(force=True)
out["pool_keys"] = sorted(detail.keys())
out["pool_names"] = {k: v["name"] for k, v in detail.items()}
out["pool_ranges"] = {k: (v["min"], v["max"]) for k, v in detail.items()}

def pool_of(task_name):
    for pid, pool in detail.items():
        for t in pool["tasks"]:
            if t["name"] == task_name:
                return pid
    return None

out["SHORT_pool"] = pool_of("SHORT")
out["MID_pool"] = pool_of("MID")
out["LONG_pool"] = pool_of("LONG")
out["EDGE15_pool"] = pool_of("EDGE15")
out["EDGE45_pool"] = pool_of("EDGE45")

# ---- 3. 发行行与拒绝行严格分离 --------------------------------------------
client.post("/api/gacha/draw", json={})
stats = client.get("/api/gacha/statistics").get_json(force=True)
out["stats_after_draw"] = stats

with write_connection() as conn:
    conn.execute(
        "INSERT INTO gacha_records "
        "(timestamp,pool_name,available_time,task_id,accepted,refusal_reason) "
        "VALUES ('2026-01-01T00:00:00','fragment',30,1,0,'other')"
    )
stats2 = client.get("/api/gacha/statistics").get_json(force=True)
out["stats_after_rejection_row"] = stats2

# ---- 4. 换牌：理由缺失 → 400 且零副作用 ----------------------------------
before = client.get("/api/gacha/statistics").get_json(force=True)
r = client.post("/api/gacha/replace", json={"task_id": 1})
out["replace_no_reason_status"] = r.status_code
after = client.get("/api/gacha/statistics").get_json(force=True)
out["replace_no_reason_zero_effect"] = (
    before["total_draws"] == after["total_draws"]
    and before["rejections"] == after["rejections"]
)

# ---- 5. 非法 reason → 400 且零副作用 --------------------------------------
r = client.post("/api/gacha/replace", json={"task_id": 1, "reason": "whatever"})
out["replace_bad_reason_status"] = r.status_code
after3 = client.get("/api/gacha/statistics").get_json(force=True)
out["replace_bad_reason_zero_effect"] = (
    before["total_draws"] == after3["total_draws"]
    and before["rejections"] == after3["rejections"]
)

# ---- 6. 候选解析失败 → 404 且零副作用 -------------------------------------
# 造一个"只剩自己"的场景：把其它任务全部完成/弃牌，只留 task 1 可选；
# 换牌时当前 task_id **始终** 被排除 → 无候选 → 404。
with write_connection() as conn:
    conn.execute(
        "UPDATE tasks SET completed=1, in_discard_pile=1 WHERE id != 1"
    )
before_fail = client.get("/api/gacha/statistics").get_json(force=True)
r = client.post("/api/gacha/replace", json={"task_id": 1, "reason": "other"})
out["replace_fail_status"] = r.status_code
out["replace_fail_body"] = r.get_json(force=True)
after_fail = client.get("/api/gacha/statistics").get_json(force=True)
out["replace_fail_zero_effect"] = (
    before_fail["total_draws"] == after_fail["total_draws"]
    and before_fail["rejections"] == after_fail["rejections"]
)

# ---- 7. 成功换牌：台账三处一致 --------------------------------------------
# 恢复候选：把 task 2 放回可抽状态。
with write_connection() as conn:
    conn.execute(
        "UPDATE tasks SET completed=0, in_discard_pile=0, "
        "is_unlocked=1 WHERE id != 1"
    )
r = client.post("/api/gacha/replace", json={"task_id": 1, "reason": "other"})
out["replace_ok_status"] = r.status_code
stats4 = client.get("/api/gacha/statistics").get_json(force=True)
out["rejections_after_ok"] = stats4["rejections"]
out["rejections_before_ok"] = before_fail["rejections"]
with write_connection() as conn:
    row = conn.execute(
        "SELECT refusal_count FROM tasks WHERE id=?", (1,)
    ).fetchone()
    out["refusal_count_after_ok"] = row["refusal_count"]
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM task_rejection_log"
    ).fetchone()["n"]
    out["rejection_log_rows"] = n

# ---- 8. 换牌链字段：replaced_task_ids 类型非法 → 400 ----------------------
r = client.post("/api/gacha/replace", json={
    "task_id": 1, "reason": "other", "replaced_task_ids": "not-a-list"})
out["replace_bad_chain_status"] = r.status_code

# ---- 9. 事务原子性：服务层的 record_* 共享同一连接 ------------------------
# 用一个 **全新的** task（从未抽过牌）来验证，避免被前序换牌的副作用污染。
with write_connection() as conn:
    cursor = conn.execute(
        "INSERT INTO tasks (name, category, priority, estimated_time, "
        "is_unlocked, completed) VALUES ('TX_PROBE','study',5,25,1,0)"
    )
    tx_task_id = cursor.lastrowid
with write_connection() as conn:
    gacha_service.record_issuance(conn, tx_task_id, "fragment", 25)
    gacha_service.record_rejection(conn, tx_task_id, "no_time", "fragment", 25)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM gacha_records WHERE task_id=?", (tx_task_id,)
    ).fetchone()
    out["ledger_rows_same_tx"] = row["n"]
    out["draw_count_not_yet"] = conn.execute(
        "SELECT COALESCE(draw_count_today,0) AS c FROM tasks WHERE id=?",
        (tx_task_id,),
    ).fetchone()["c"]

print("PROBE_JSON=" + json.dumps(out))
'''


def _run_probe() -> dict:
    import json

    with TemporaryDirectory(prefix="lt_stage3_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_stage3_probe.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        env = {
            k: v
            for k, v in os.environ.items()
            if (
                "API_KEY" not in k.upper()
                and "TOKEN" not in k.upper()
                and "SECRET" not in k.upper()
                and k.upper() not in ("PYTHONPATH", "PYTHONHOME")
            )
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-I", str(runner)],
            cwd=root,
            env=env,
            capture_output=True,
            timeout=120,
        )
        stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
        stderr = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
        if proc.returncode != 0:
            raise AssertionError(f"probe 退出码非0: {stderr[-3000:]}")
        lines = [
            ln for ln in stdout.splitlines() if ln.startswith("PROBE_JSON=")
        ]
        if len(lines) != 1:
            raise AssertionError(f"未捕获 PROBE_JSON: {stdout[-3000:]}")
        return json.loads(lines[0][len("PROBE_JSON=") :])


class GachaBehaviorTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    def test_pool_boundaries(self):
        """15 分钟归番茄池、45 分钟归深度池（边界任务归 **上** 一个池）。"""
        p = self.PROBE
        self.assertEqual(p["SHORT_pool"], "fragment", p)
        self.assertEqual(p["MID_pool"], "tomato", p)
        self.assertEqual(p["LONG_pool"], "deep", p)
        self.assertEqual(p["EDGE15_pool"], "tomato", p)
        self.assertEqual(p["EDGE45_pool"], "deep", p)

    def test_pool_structure_unchanged(self):
        p = self.PROBE
        self.assertEqual(
            p["pool_keys"], ["deep", "fragment", "tomato"], p
        )
        self.assertEqual(p["pool_names"]["fragment"], "碎片卡池", p)
        self.assertEqual(list(p["pool_ranges"]["tomato"]), [15, 45], p)

    def test_issuance_and_rejection_rows_are_separated(self):
        """拒绝行（``refusal_reason NOT NULL``）绝不计入抽卡次数。

        往 ``gacha_records`` 手工插一行拒绝行后：

        * ``total_draws`` **不变**（拒绝行不是发行行）；
        * ``by_pool`` **不变**（拒绝行不计入卡池分布）；
        * ``rejections`` **不变**（它统计的是 ``task_rejection_log``，
          不是 ``gacha_records``）。
        """
        p = self.PROBE
        before = p["stats_after_draw"]
        after = p["stats_after_rejection_row"]
        self.assertEqual(before["total_draws"], after["total_draws"], p)
        self.assertEqual(before["by_pool"], after["by_pool"], p)
        self.assertEqual(before["rejections"], after["rejections"], p)

    def test_replace_requires_explicit_reason(self):
        p = self.PROBE
        self.assertEqual(p["replace_no_reason_status"], 400, p)
        self.assertTrue(p["replace_no_reason_zero_effect"], p)

    def test_replace_failure_has_zero_side_effects(self):
        """候选解析失败 → 404 且 **零副作用**（不写台账、不改计数）。"""
        p = self.PROBE
        self.assertEqual(p["replace_fail_status"], 404, p)
        self.assertEqual(
            p["replace_fail_body"].get("error"),
            "No replacement available",
            p,
        )
        self.assertTrue(p["replace_fail_zero_effect"], p)

    def test_replace_rejects_unknown_reason(self):
        p = self.PROBE
        self.assertEqual(p["replace_bad_reason_status"], 400, p)
        self.assertTrue(p["replace_bad_reason_zero_effect"], p)

    def test_successful_replace_records_consistent_ledger(self):
        """成功换牌 → 拒绝台账 +1、``refusal_count`` +1、台账行一致。"""
        p = self.PROBE
        self.assertEqual(p["replace_ok_status"], 200, p)
        self.assertEqual(
            p["rejections_after_ok"], p["rejections_before_ok"] + 1, p
        )
        self.assertEqual(p["refusal_count_after_ok"], 1, p)
        self.assertEqual(p["rejection_log_rows"], 1, p)

    def test_replace_chain_field_type_is_validated(self):
        p = self.PROBE
        self.assertEqual(p["replace_bad_chain_status"], 400, p)

    def test_ledger_writes_share_one_transaction(self):
        """``record_issuance`` / ``record_rejection`` 共享同一连接事务。"""
        p = self.PROBE
        self.assertEqual(p["ledger_rows_same_tx"], 2, p)
        self.assertEqual(p["draw_count_not_yet"], 0, p)


class GachaGoldenTests(unittest.TestCase):
    """6. 算法不变：100,250 组 Golden ``max_diff = 0``。"""

    def test_gacha_golden_equivalence(self):
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "phase2_gacha_golden.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:] + proc.stderr[-2000:])
        self.assertIn("RESULT: OK", proc.stdout)
        self.assertIn("fail=0", proc.stdout)
        self.assertIn("max_diff=0.000e+00", proc.stdout)


if __name__ == "__main__":
    unittest.main()
