"""AR03-P2 / Stage 1 — **Legacy 差异台账** 与实现的一致性契约测试。

台账（``docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md``）是 P2 功能保全的
主证据之一。它必须与 **实测结果**（``tests/fixtures/legacy_divergence.json``）
保持一致，否则台账就成了"看起来很全但其实是编的"文档。

本文件锁定四件事：

1. **覆盖完整性** —— legacy 的 **每一条** 活跃路由都在台账中有条目；
2. **条目与实测不矛盾** —— 台账里的每个差异判定与实测结果一致；
3. **测试引用非空** —— 每条差异条目都必须引用至少一个测试用例名；
4. **探针可复现** —— 重新运行探针得到相同计数（防止实现漂移）。

全程 **不** 触碰生产数据库：探针跑在 ``tests/characterize/sandbox_env.py``
的合成根内。
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import route_inventory  # type: ignore  # noqa: E402

LEDGER_PATH = PROJECT_ROOT / "docs" / "P2_LEGACY_DIVERGENCE_LEDGER_20261121.md"
DIVERGENCE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legacy_divergence.json"
)
GOLDEN_PATH = PROJECT_ROOT / "tests" / "fixtures" / "golden_http_snapshot.json"


def _ledger_text() -> str:
    return LEDGER_PATH.read_text(encoding="utf-8")


def _divergence() -> dict:
    return json.loads(DIVERGENCE_PATH.read_text(encoding="utf-8"))


class LedgerCoverageTests(unittest.TestCase):
    """1. 覆盖完整性。"""

    def test_ledger_file_exists(self):
        self.assertTrue(LEDGER_PATH.is_file(), "台账缺失: " + str(LEDGER_PATH))

    def test_every_legacy_active_route_is_covered(self):
        """legacy 的每一条活跃路由都必须出现在台账里。

        判定方式：台账中出现了该路由的 **路径**（去掉 ``<...>`` 占位符后
        的规范化形式）。
        """
        ledger = _ledger_text()
        inventory = route_inventory.build_inventory()
        active = inventory["legacy_active_routes"]
        self.assertTrue(active, "静态清单为空")

        uncovered = []
        for rule, _method in active:
            normalized = re.sub(r"<[^>]*>", "{p}", rule)
            if normalized not in ledger:
                uncovered.append(rule)
        self.assertFalse(
            uncovered,
            "台账未覆盖的 legacy 路由: " + ", ".join(sorted(set(uncovered))),
        )

    def test_ledger_covers_all_bridged_routes(self):
        """21 条兼容桥路由必须逐条在台账里有条目。"""
        ledger = _ledger_text()
        inventory = route_inventory.build_inventory()
        bridged = inventory["compat_bridge"]["bridged_routes"]
        uncovered = []
        for rule, _method in bridged:
            normalized = re.sub(r"<[^>]*>", "{p}", rule)
            if normalized not in ledger:
                uncovered.append(rule)
        self.assertFalse(
            uncovered,
            "台账未覆盖的兼容桥路由: " + ", ".join(sorted(set(uncovered))),
        )

    def test_ledger_states_the_authority_rules(self):
        """台账必须写明权威侧判定规则（R1–R5）。"""
        ledger = _ledger_text()
        for rule in ("R1", "R2", "R3", "R4", "R5"):
            self.assertIn(rule, ledger, "台账缺少判定规则 " + rule)


class LedgerMatchesMeasurementTests(unittest.TestCase):
    """2. 条目与实测不矛盾。"""

    def test_divergence_counts_match_ledger(self):
        data = _divergence()
        ledger = _ledger_text()
        self.assertIn(str(data["total_cases"]), ledger)
        self.assertIn(str(data["identical_count"]), ledger)
        self.assertIn(str(data["divergent_count"]), ledger)

    def test_each_divergent_case_has_a_ledger_entry(self):
        """每个实测有差异的用例，台账里必须有对应的 L-xx 条目。"""
        data = _divergence()
        ledger = _ledger_text()
        sections = re.findall(r"### (L-\d+)([^\n]*)", ledger)
        self.assertTrue(sections, "台账没有 L-xx 条目")
        ledger_blob = "\n".join(text for _label, text in sections)

        divergent = [
            entry for entry in data["entries"] if entry["verdict"] != "identical"
        ]
        for entry in divergent:
            probe_name = entry["name"]
            path = entry["path"]
            self.assertTrue(
                probe_name in ledger_blob or path in ledger_blob,
                "实测差异用例未在台账中裁决: " + probe_name + " " + path,
            )

    def test_identical_cases_are_listed(self):
        """行为一致的路由必须在台账的"行为一致"清单里出现。

        探针用 **具体 id**（如 ``/api/tasks/999999``），台账用 **占位符**
        （``/api/tasks/{p}``）。比对时把具体 id 归一化成占位符。
        """
        ledger = _ledger_text()
        data = _divergence()
        identical = [
            entry for entry in data["entries"] if entry["verdict"] == "identical"
        ]
        self.assertGreater(len(identical), 20)
        missing = []
        for entry in identical:
            path = entry["path"]
            if path in ledger:
                continue
            # 路径带参数占位符：检查其归一化形式
            normalized = re.sub(r"/\d+(?=/|$)", "/{p}", path)
            normalized = re.sub(r"/[^/]+\.md$", "/{p}", normalized)
            if normalized in ledger:
                continue
            missing.append(path)
        self.assertFalse(
            missing, "行为一致但未在台账清单中列出的路由: " + ", ".join(missing)
        )


class LedgerEvidenceTests(unittest.TestCase):
    """3. 每条差异条目必须有测试引用。"""

    def test_each_divergent_entry_references_a_test_case(self):
        ledger = _ledger_text()
        data = _divergence()
        divergent = [
            entry for entry in data["entries"] if entry["verdict"] != "identical"
        ]
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        golden_names = {case["name"] for case in golden["cases"]}
        probe_names = {entry["name"] for entry in data["entries"]}

        # 按 "### L-xx <title>" 切分台账条目
        parts = re.split(r"^### (L-\d+)", ledger, flags=re.MULTILINE)
        entries = {}
        for index in range(1, len(parts) - 1, 2):
            entries[parts[index]] = parts[index + 1]

        for label, body in entries.items():
            referenced = set(re.findall(r"`([a-z0-9_]+)`", body))
            has_evidence = bool(referenced & (golden_names | probe_names))
            self.assertTrue(
                has_evidence,
                label + " 没有引用任何黄金快照/探针用例名",
            )

    def test_ledger_documents_unresolved_items(self):
        """台账必须显式列出未决项。"""
        ledger = _ledger_text()
        self.assertIn("未决项", ledger)


class ProbeReproducibilityTests(unittest.TestCase):
    """4. 探针可复现（防止实现漂移而台账未更新）。"""

    def test_probe_reproduces_frozen_counts(self):
        import legacy_divergence_probe  # type: ignore

        live = legacy_divergence_probe.build_divergence()
        frozen = _divergence()
        self.assertEqual(
            live["counts"] if "counts" in live else {
                "total_cases": live["total_cases"],
                "identical_count": live["identical_count"],
                "divergent_count": live["divergent_count"],
            },
            {
                "total_cases": frozen["total_cases"],
                "identical_count": frozen["identical_count"],
                "divergent_count": frozen["divergent_count"],
            },
            "Legacy/Factory 差异探针结果漂移；请重新运行 "
            "`python scripts/legacy_divergence_probe.py --write` 并复核台账",
        )


if __name__ == "__main__":
    unittest.main()
