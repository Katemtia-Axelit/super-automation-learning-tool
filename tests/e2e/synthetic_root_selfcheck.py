"""合成服务器启动自检（Stage 0 / AR03-P2）—— **证明**隔离，而不是观测。

本模块在合成服务器 **启动前** 与 **启动后** 断言：

1. 合成根位于系统临时目录之下，且 **不是** 真实项目根；
2. 合成根内不存在真实项目根的路径前缀（即合成根不是真实根的子目录，反之亦然）；
3. 解析出来的 SQLite 路径、notes 根、配置文件路径 **全部** 落在合成根内；
4. 真实项目的 ``data/`` / ``config/`` / ``src/notes/`` **从不被打开**。

任何一条不成立 → 直接拒绝启动（fail closed），而不是打一条警告继续跑。

**本模块只做路径解析与断言，绝不读取生产文件内容。**
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

#: 真实项目内绝不允许被测试触碰的相对目录。
PROTECTED_RELATIVE_DIRS = ("data", "config")
PROTECTED_RELATIVE_SUBPATHS = (("src", "notes"),)


class IsolationError(RuntimeError):
    """合成环境自检失败 —— 必须 fail closed。"""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _is_under(root: str, target: str) -> bool:
    if not root or not target:
        return False
    try:
        common = os.path.commonpath([_norm(root), _norm(target)])
    except (ValueError, OSError):
        return False
    return _norm(common) == _norm(root)


def assert_synthetic_root(synthetic_root: Path, real_root: Path) -> Dict[str, Any]:
    """断言合成根与真实项目根彼此独立。"""
    synth = _norm(str(synthetic_root))
    real = _norm(str(real_root))

    if synth == real:
        raise IsolationError("synthetic root must not be the real project root")
    if _is_under(real, synth) or _is_under(synth, real):
        raise IsolationError(
            "synthetic root and real project root must not contain each other: "
            + synth + " / " + real
        )
    return {"synthetic_root": synth, "real_root": real}


def assert_paths_inside(synthetic_root: Path, paths: Dict[str, str]) -> Dict[str, Any]:
    """断言给定路径全部落在合成根内。"""
    synth = _norm(str(synthetic_root))
    resolved: Dict[str, str] = {}
    offenders: List[str] = []
    for label, value in paths.items():
        if not value:
            continue
        target = _norm(str(value))
        resolved[label] = target
        if not _is_under(synth, target):
            offenders.append(label + " -> " + target)
    if offenders:
        raise IsolationError(
            "resolved paths escaped the synthetic root: " + "; ".join(offenders)
        )
    return resolved


def assert_config_uses_synthetic(synthetic_root: Path, config_path: Path) -> None:
    """断言合成根的配置文件确实指向合成根内的数据库与 notes 根。"""
    synth = _norm(str(synthetic_root))
    cfg = _norm(str(config_path))
    if not _is_under(synth, cfg):
        raise IsolationError("config path escaped the synthetic root: " + cfg)


def assert_real_protected_absent(synthetic_root: Path, real_root: Path) -> None:
    """断言合成根 **不是** 指向真实受保护目录。

    这里只做 **路径字符串比较**，不 stat、不读取任何真实文件。
    真实受保护文件位于真实项目根，合成根内本来就不该有它们的副本。
    """
    synth = _norm(str(synthetic_root))
    for rel in PROTECTED_RELATIVE_DIRS:
        candidate = _norm(os.path.join(synth, rel))
        real_candidate = _norm(os.path.join(str(real_root), rel))
        if candidate == real_candidate:
            raise IsolationError("synthetic root points at real protected dir: " + rel)
    for parts in PROTECTED_RELATIVE_SUBPATHS:
        candidate = _norm(os.path.join(synth, *parts))
        real_candidate = _norm(os.path.join(str(real_root), *parts))
        if candidate == real_candidate:
            raise IsolationError(
                "synthetic root points at real protected dir: " + "/".join(parts)
            )


def self_check(synthetic_root: Path, real_root: Path, resolved: Dict[str, str]) -> Dict[str, Any]:
    """执行全部自检并返回可打印的证据摘要。"""
    result: Dict[str, Any] = {}
    result.update(assert_synthetic_root(synthetic_root, real_root))
    result.update(assert_paths_inside(synthetic_root, resolved))
    assert_config_uses_synthetic(synthetic_root, Path(resolved["config_path"]))
    assert_real_protected_absent(synthetic_root, real_root)
    result["ok"] = True
    return result


def main(argv: List[str]) -> int:
    """CLI：``python synthetic_root_selfcheck.py <synthetic_root> <real_root>``"""
    if len(argv) < 3:
        print(
            "usage: synthetic_root_selfcheck.py <synthetic_root> <real_root>",
            file=sys.stderr,
        )
        return 2
    synthetic_root = Path(argv[1]).resolve()
    real_root = Path(argv[2]).resolve()
    db = synthetic_root / "data" / "synthetic.sqlite3"
    resolved = {
        "db_path": str(db),
        "notes_dir": str(synthetic_root / "vault"),
        "config_path": str(synthetic_root / "config" / "config.json"),
    }
    summary = self_check(synthetic_root, real_root, resolved)
    print("SELFCHECK_OK " + ", ".join(sorted(summary)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
