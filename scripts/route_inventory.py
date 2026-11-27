"""scripts/route_inventory.py — **静态** 路由清单 oracle（AR03-P2 / Stage 1 → Stage 7）。

为什么需要静态清单
------------------
P1 的 ``tests/characterize/test_route_inventory.py`` 与
``test_legacy_route_full_parity.py`` 依赖 **现场运行** legacy
``backend_api.py`` 的 ``__main__`` 来取路由清单。那意味着：

* legacy 收口为薄别名（Stage 7）之后，``backend_api`` **不再** 有 Flask
  路由，"现场跑 legacy" 的取数方式彻底失效；
* 该方式在测试期 **启动** 了真实模块，耦合运行时行为。

因此 P2 把路由清单改成 **静态 oracle**：用 AST 解析源码得到路由声明，
与 Factory 运行时 ``url_map`` 对比。

Stage 7 的口径变更
------------------
Stage 7 之后 ``server/backend_api.py`` 已无任何 ``@app.route``
（它是薄别名），AST 扫描恒返回空集 —— 失去鉴别力。因此：

* **legacy 侧** → 从 **冻结基线** ``tests/fixtures/legacy_baseline.json``
  的用例路径反推 legacy 覆盖过的路由集合（基线由迁移前的 legacy 单体
  实测采集，见 :mod:`scripts.legacy_baseline`）；
* **Factory 侧** → 由测试在合成根里 **实时** 采集 ``url_map``；
* 断言：legacy 路由集合在 Factory 中 **零缺失**。

用法
----
::

    python scripts/route_inventory.py            # 打印 JSON
    python scripts/route_inventory.py --check    # 与已冻结的清单比对
    python scripts/route_inventory.py --write    # 写冻结清单

产物
----
``tests/fixtures/route_inventory.json`` —— 冻结的清单（静态 oracle 的真源）。
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE = PROJECT_ROOT / "server" / "backend_api.py"
LEGACY_COMPAT = PROJECT_ROOT / "server" / "app" / "legacy_compat.py"
LEGACY_BASELINE = PROJECT_ROOT / "tests" / "fixtures" / "legacy_baseline.json"
LEGACY_ROUTE_SURFACE = (
    PROJECT_ROOT / "tests" / "fixtures" / "legacy_route_surface.json"
)
INVENTORY_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "route_inventory.json"
)

#: legacy ``backend_api.py`` 中被 **注释掉** 的路由标记。
#: 这些是 P1 之前的历史实现，**不属于**活跃路由集。
_COMMENTED_PREFIXES = ("#@app.route", "# @app.route")


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def _methods_from_decorator(node: ast.AST) -> List[str]:
    """从 ``@app.route(...)`` 装饰器提取方法列表。"""
    if not isinstance(node, ast.Call):
        return []
    methods: List[str] = []
    for keyword in node.keywords:
        if keyword.arg == "methods":
            value = _literal(keyword.value)
            if isinstance(value, (list, tuple)):
                methods = [str(item) for item in value]
    if not methods:
        methods = ["GET"]
    return methods


def scan_source_routes(source_path: Path) -> Dict[str, Any]:
    """AST 扫描一个 Python 文件的 ``@app.route`` 声明。

    返回::

        {
          "active":    [(rule, method), ...],
          "commented": [(rule, method), ...],
        }
    """
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, str(source_path))
    active: Set[Tuple[str, str]] = set()
    commented: Set[Tuple[str, str]] = set()

    # -- 活跃路由：AST 节点上的 @app.route -------------------------------
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            # 只认 ``@app.route(...)``（属性链末段为 route）
            attr = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if attr != "route":
                continue
            rule = _literal(decorator.args[0]) if decorator.args else None
            if not isinstance(rule, str):
                continue
            for method in _methods_from_decorator(decorator):
                active.add((rule, method))

    # -- 被注释掉的路由：逐行扫描（AST 看不到注释） ----------------------
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        prefix = None
        for candidate in _COMMENTED_PREFIXES:
            if stripped.startswith(candidate):
                prefix = candidate
                break
        if prefix is None:
            continue
        call = stripped[len(prefix):].strip()
        # 形如 ``'/api/xxx', methods=['GET']``
        try:
            rule = ast.literal_eval(call.split(",")[0].strip())
        except (ValueError, SyntaxError):
            continue
        if not isinstance(rule, str):
            continue
        methods: List[str] = ["GET"]
        if "methods=" in call:
            try:
                value = ast.literal_eval(call.split("methods=")[1].strip())
                if isinstance(value, (list, tuple)):
                    methods = [str(item) for item in value]
            except (ValueError, SyntaxError):
                pass
        for method in methods:
            commented.add((rule, method))

    return {
        "active": sorted(active),
        "commented": sorted(commented),
    }


def scan_legacy_compat() -> Dict[str, Any]:
    """解析 ``legacy_compat.py`` 的兼容桥白名单。

    这里 **不** import 该模块（它会 import backend_api 并改写全局），只做
    AST 静态读取。

    Stage 7 起该文件已被删除（兼容桥清空 → 退役），此时返回空集合。
    """
    if not LEGACY_COMPAT.is_file():
        return {
            "exact_routes": [],
            "prefix_routes": [],
            "module_present": False,
            "bridged_routes": [],
        }

    source = LEGACY_COMPAT.read_text(encoding="utf-8")
    tree = ast.parse(source, str(LEGACY_COMPAT))

    exact: List[str] = []
    prefix: List[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "EXACT_ROUTES" in targets:
            value = _literal(node.value)
            if isinstance(value, (set, list, tuple)):
                exact = sorted(str(item) for item in value)
        elif "PREFIX_ROUTES" in targets:
            value = _literal(node.value)
            if isinstance(value, (set, list, tuple)):
                prefix = sorted(str(item) for item in value)

    # 兼容桥挂载的路由 = EXACT_ROUTES ∪ PREFIX_ROUTES 覆盖的前缀
    bridged: Set[str] = set(exact)
    for rule in exact:
        bridged.add(rule)
    return {
        "exact_routes": exact,
        "prefix_routes": prefix,
        "module_present": True,
        "bridged_routes": sorted(bridged),
    }


def scan_legacy_baseline() -> Dict[str, Any]:
    """从冻结基线反推 legacy **实际响应过** 的路由集合。

    Stage 7 之后 legacy 单体不再持有 Flask 路由，AST 扫描恒为空。
    冻结基线记录了 legacy 在迁移前 **实际响应过** 的请求路径，
    因此它能证明"legacy 覆盖过哪些路由"。
    """
    if not LEGACY_BASELINE.is_file():
        return {"active": [], "case_count": 0}

    data = json.loads(LEGACY_BASELINE.read_text(encoding="utf-8"))
    active: Set[Tuple[str, str]] = set()
    for entry in data.get("entries", []):
        path = entry.get("path")
        method = entry.get("method")
        if isinstance(path, str) and isinstance(method, str):
            active.add((path, method))
    return {
        "active": sorted(active),
        "case_count": int(data.get("total_cases", len(data.get("entries", [])))),
    }


def scan_legacy_route_surface() -> Dict[str, Any]:
    """读取 **冻结的** 迁移前 legacy 路由面（43 条）。

    这是 legacy 覆盖范围的 **权威** 清单：Stage 7 之前由 AST 扫描
    ``server/backend_api.py`` 得到，Stage 7 之后 legacy 不再持有路由，
    因此冻结为 ``tests/fixtures/legacy_route_surface.json``。
    """
    if not LEGACY_ROUTE_SURFACE.is_file():
        return {"active": []}
    data = json.loads(LEGACY_ROUTE_SURFACE.read_text(encoding="utf-8"))
    active = {
        (str(rule), str(method))
        for rule, method in data.get("legacy_active_routes", [])
    }
    return {"active": sorted(active)}


def build_inventory() -> Dict[str, Any]:
    """构造完整清单（不含 Factory 运行时部分 —— 那部分由测试动态比对）。"""
    legacy = scan_source_routes(LEGACY_SOURCE)
    compat = scan_legacy_compat()
    baseline = scan_legacy_baseline()
    surface = scan_legacy_route_surface()

    # Stage 7：legacy 单体已无路由声明。权威清单 = 冻结的迁移前路由面；
    # 冻结基线覆盖的路由是它的 **实测子集**（探针不可能覆盖全部 43 条）。
    legacy_active = set(surface["active"]) or set(baseline["active"])
    legacy_commented = set(legacy["commented"])

    # 冻结基线实测覆盖到的 legacy 路由（探针证据）
    baseline_active = set(baseline["active"])
    # 探针未覆盖的 legacy 路由（只有静态清单证据）
    baseline_uncovered = sorted(legacy_active - baseline_active)

    compat_exact = set(compat["exact_routes"])
    compat_prefix = tuple(compat["prefix_routes"])

    def _via_bridge(rule: str) -> bool:
        if rule in compat_exact:
            return True
        return any(rule.startswith(p) for p in compat_prefix)

    bridged = {r for r in legacy_active if _via_bridge(r[0])}
    shadowed = legacy_active - bridged

    return {
        "schema_version": 3,
        "generated_by": "scripts/route_inventory.py",
        "legacy_source": str(LEGACY_SOURCE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "legacy_route_source": "tests/fixtures/legacy_route_surface.json",
        "legacy_active_routes": sorted([list(r) for r in legacy_active]),
        "legacy_commented_routes": sorted([list(r) for r in legacy_commented]),
        "legacy_active_count": len(legacy_active),
        "legacy_commented_count": len(legacy_commented),
        "legacy_baseline_case_count": baseline["case_count"],
        "legacy_baseline_covered_routes": sorted(
            [list(r) for r in baseline_active]
        ),
        "legacy_baseline_uncovered_routes": sorted(
            [list(r) for r in baseline_uncovered]
        ),
        "compat_bridge": {
            "exact_routes": compat["exact_routes"],
            "prefix_routes": compat["prefix_routes"],
            "module_present": compat["module_present"],
            "bridged_route_count": len(bridged),
            "bridged_routes": sorted([list(r) for r in bridged]),
            "shadowed_route_count": len(shadowed),
            "shadowed_routes": sorted([list(r) for r in shadowed]),
        },
        "counts": {
            "legacy_active": len(legacy_active),
            "legacy_commented": len(legacy_commented),
            "bridged": len(bridged),
            "shadowed": len(shadowed),
        },
    }


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="静态路由清单 oracle")
    parser.add_argument("--check", action="store_true", help="与冻结清单比对")
    parser.add_argument("--write", action="store_true", help="写入冻结清单")
    args = parser.parse_args(argv[1:])

    inventory = build_inventory()

    if args.write:
        INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        INVENTORY_PATH.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("WROTE " + str(INVENTORY_PATH))
        print(json.dumps(inventory["counts"], ensure_ascii=False))
        return 0

    if args.check:
        if not INVENTORY_PATH.is_file():
            print("MISSING " + str(INVENTORY_PATH), file=sys.stderr)
            return 1
        frozen = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        if frozen.get("counts") != inventory.get("counts"):
            print("DRIFT " + str(INVENTORY_PATH), file=sys.stderr)
            print("frozen=" + json.dumps(frozen.get("counts"), ensure_ascii=False))
            print("live  =" + json.dumps(inventory.get("counts"), ensure_ascii=False))
            return 1
        print("OK " + str(INVENTORY_PATH))
        print(json.dumps(inventory["counts"], ensure_ascii=False))
        return 0

    print(json.dumps(inventory, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
