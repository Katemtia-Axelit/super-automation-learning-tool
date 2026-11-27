#!/usr/bin/env python3
"""scripts/_p5_report_scripts.py —— 把 .p5_script_refs.json 渲染成可读分级表。

一次性工具（AR03-P5）。只读。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / ".p5_script_refs.json").read_text(encoding="utf-8"))

rows = []
for s in data["scripts"]:
    rows.append((s["refs_total"], s["name"], s["bytes"], s["refs_by_area"]))

rows.sort(key=lambda r: (-r[0], r[1]))
print(f"{'refs':>5}  {'bytes':>7}  name")
print("-" * 78)
for refs, name, size, areas in rows:
    top = ", ".join(f"{k}:{v}" for k, v in list(areas.items())[:3])
    print(f"{refs:>5}  {size:>7}  {name}   [{top}]")
print()
print("总脚本数:", len(rows))
print("零引用:", sum(1 for r in rows if r[0] == 0))
print("被 scripts/ 内部引用:", sum(1 for r in rows if "scripts" in r[3]))
