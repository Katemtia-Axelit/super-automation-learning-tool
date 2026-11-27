"""AR03-P2 / Stage 1 — 黄金 HTTP 快照 oracle 的契约测试。

黄金快照（``tests/fixtures/golden_http_snapshot.json``）是 P2 各阶段迁移的
**主 parity oracle**：迁移前 Factory 在合成环境下的 HTTP 行为。

本文件锁定：

1. 快照文件存在，且用例数不小于预期基线；
2. 快照 **可复现** —— 重新采集得到与冻结产物 **完全一致** 的结果；
3. 快照覆盖了 P2 迁移要动的 **全部** 业务域的路由；
4. 快照的每个用例都有状态码与结构化响应体。

全程 **不** 触碰生产数据库：采集在 ``tests/characterize/sandbox_env.py``
的合成根内进行。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import golden_snapshot  # type: ignore  # noqa: E402

SNAPSHOT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "golden_http_snapshot.json"

#: P2 迁移要动的业务域 → 必须被快照覆盖的路由前缀。
REQUIRED_DOMAIN_PREFIXES = (
    "/api/tasks",
    "/api/tags",
    "/api/gacha",
    "/api/discard-pile",
    "/api/dependencies",
    "/api/config",
    "/api/export",
    "/api/agent",
    "/api/prompts",
    "/api/timer",
    "/api/schedule",
    "/api/state",
    "/api/knowledge",
    "/api/task-feedback",
)


class GoldenSnapshotTests(unittest.TestCase):
    def test_snapshot_file_exists(self):
        self.assertTrue(
            SNAPSHOT_PATH.is_file(), "黄金快照缺失: " + str(SNAPSHOT_PATH)
        )

    def test_snapshot_has_expected_size(self):
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(
            len(data["cases"]), 40, "黄金快照用例过少，可能采集不完整"
        )

    def test_every_case_has_status_and_body(self):
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        for case in data["cases"]:
            self.assertIn("status", case, case.get("name"))
            self.assertIsInstance(case["status"], int, case.get("name"))
            self.assertIn("json", case, case.get("name"))

    def test_snapshot_covers_all_business_domains(self):
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        paths = {case["path"] for case in data["cases"]}
        for prefix in REQUIRED_DOMAIN_PREFIXES:
            self.assertTrue(
                any(path.startswith(prefix) for path in paths),
                "黄金快照未覆盖业务域: " + prefix,
            )

    def test_snapshot_covers_error_paths(self):
        """必须包含错误路径用例（404 / 400），不能只有成功路径。"""
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        statuses = {case["status"] for case in data["cases"]}
        self.assertIn(404, statuses, "缺少 404 路径用例")
        self.assertIn(400, statuses, "缺少 400 路径用例")

    def test_snapshot_covers_side_effect_verification(self):
        """必须有用例记录副作用（DB 状态），供事务语义比对。"""
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        with_effects = [
            case for case in data["cases"] if case.get("side_effects")
        ]
        self.assertGreaterEqual(
            len(with_effects), 5, "缺少带副作用快照的用例"
        )

    def test_snapshot_is_reproducible(self):
        """重新采集必须得到与冻结产物 **完全一致** 的结果。"""
        frozen = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        live = golden_snapshot._run_collector()
        problems = golden_snapshot.compare(frozen, live)
        self.assertFalse(
            problems,
            "黄金快照不可复现（实现已漂移或快照过期）:\n  "
            + "\n  ".join(problems[:20]),
        )


if __name__ == "__main__":
    unittest.main()
