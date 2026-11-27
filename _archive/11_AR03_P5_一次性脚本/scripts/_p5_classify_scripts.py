#!/usr/bin/env python3
"""scripts/_p5_classify_scripts.py —— AR03-P5 脚本分级器（一次性工具）

用途
----
扫描 `scripts/` 下的每个文件，统计它在**仓库其它位置**被引用的情况，
据此输出分级清单（production / gatekeeper / one-time / diagnostic）。

只读脚本：不修改任何文件。
输出：JSON 到 stdout。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# 扫描范围：排除 scripts/ 自身、_archive/、prototypes/、node_modules、.git
EXCLUDE_TOP = {"_archive", "prototypes", "node_modules", ".git", ".run",
               "art-p0", "__pycache__", ".venv", "venv"}

# 这些目录的引用算「内部引用」（同目录内互相引用）
INTERNAL_DIRS = {"scripts"}

TEXT_EXT = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".json", ".md", ".html", ".css",
    ".bat", ".ps1", ".sh", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini",
}


def iter_source_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = Path(dirpath).relative_to(ROOT)
        top = rel.parts[0] if rel.parts else ""
        if top in EXCLUDE_TOP:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in {"node_modules", "__pycache__", ".git"}]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in TEXT_EXT:
                yield p


def main() -> int:
    targets = {}
    for p in sorted(SCRIPTS.iterdir()):
        if p.is_file():
            targets[p.name] = p

    ref_counts = {name: {"total": 0, "by_area": {}} for name in targets}
    patterns = {
        name: re.compile(re.escape(name), re.IGNORECASE) for name in targets
    }

    for src in iter_source_files():
        rel = src.relative_to(ROOT)
        try:
            text = src.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        top = rel.parts[0] if rel.parts else ""
        area = top if top in INTERNAL_DIRS else (
            "/".join(rel.parts[:2]) if len(rel.parts) > 1 else top
        )
        for name, rx in patterns.items():
            if rel.name == name and top == "scripts":
                # 同名文件自身不计
                continue
            n = len(rx.findall(text))
            if n:
                ref_counts[name]["total"] += n
                ref_counts[name]["by_area"][area] = (
                    ref_counts[name]["by_area"].get(area, 0) + n
                )

    out = {
        "root": str(ROOT),
        "scripts": [
            {
                "name": name,
                "bytes": targets[name].stat().st_size,
                "refs_total": ref_counts[name]["total"],
                "refs_by_area": dict(
                    sorted(ref_counts[name]["by_area"].items(),
                           key=lambda kv: -kv[1])
                ),
            }
            for name in sorted(targets)
        ],
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
