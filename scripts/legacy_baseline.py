"""scripts/legacy_baseline.py — **冻结** 的 legacy 行为基线（AR03-P2 / Stage 7）。

背景
----
Stage 7 把 ``server/backend_api.py`` 收口成 **薄别名**（委托
``create_app()``），legacy 单体因此 **不再持有任何 Flask 路由**。
这让 ``scripts/legacy_divergence_probe.py`` 原先的"现场跑 legacy 单体"
取数方式彻底失效 —— 而且它本来就不该在 P2 后期继续跑一个已被
判定为"历史残留"的实现。

因此本模块把 **Stage 1 采集到的 legacy 实测结果** 冻结成一份
**只读基线**（``tests/fixtures/legacy_baseline.json``），并提供：

* :func:`load_baseline` —— 读取冻结基线；
* :func:`baseline_index` —— 按用例名索引。

冻结基线由 ``scripts/legacy_divergence_probe.py --freeze-baseline``
在 **legacy 单体仍然存在** 时采集过一次；Stage 7 之后该命令不再
可用（legacy 已收口），基线因此是 **一次性冻结**的审计证据。

**它不是**"重新算一遍 legacy"：legacy 的实现已被判定为历史残留，
差异台账的权威判定见 ``docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md``。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "legacy_baseline.json"


def load_baseline() -> Dict[str, Any]:
    """读取冻结的 legacy 行为基线。"""
    if not BASELINE_PATH.is_file():
        raise FileNotFoundError(
            "冻结的 legacy 基线缺失: " + str(BASELINE_PATH)
        )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def baseline_index() -> Dict[str, Dict[str, Any]]:
    """按用例名索引冻结基线。"""
    data = load_baseline()
    return {entry["name"]: entry for entry in data["entries"]}


def baseline_names() -> List[str]:
    """冻结基线覆盖的用例名（有序）。"""
    data = load_baseline()
    return [entry["name"] for entry in data["entries"]]


__all__ = [
    "BASELINE_PATH",
    "baseline_index",
    "baseline_names",
    "load_baseline",
]
