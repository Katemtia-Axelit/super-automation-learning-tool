"""server.utils.energy_calc — 精力/专注/心情评分（公开工具门面）。

AR03-P2 / Stage 7
-----------------
此前本模块是 **转发壳**：函数体 ``from server.backend_api import
calculate_state_scores``。但 legacy 里的那份实现 **早已被注释掉**
（P1 的 Schema 权威层把评分数学搬进了 service），因此该转发在运行期
会直接抛 ``ImportError`` —— 是一条 **死路**。

Stage 7 把它指向 **真正的 owner**：
:mod:`server.services.state.calculate_state_scores`。

:mod:`server.services.state` 是纯 Python（不依赖 Flask），因此本门面
仍然可以在 CLI / 脚本里直接使用。
"""

from __future__ import annotations

from typing import Any, Dict

__all__ = ["calculate_state_scores"]


def calculate_state_scores(
    answers: Dict[str, Any], version: int = 1
) -> Dict[str, Any]:
    """根据答题计算精力/专注/心情分数。

    委托给 :func:`server.services.state.calculate_state_scores`
    （真正的 owner）。
    """
    from server.services.state import calculate_state_scores as _impl

    return _impl(answers, version)
