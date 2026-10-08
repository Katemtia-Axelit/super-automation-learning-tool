"""server.app package for the 超级自动化学习工具 backend.

Phase 1 收紧版：
- `create_app` 工厂：组装 Flask 实例 + 扩展 + schema ensure_all + 3 个 Blueprint
- 老入口 `server/backend_api.py` 仍可独立运行（兼容期），避免 36/36 E2E 受影响
"""

from .app_factory import create_app
from .config import load_config

__all__ = ["create_app", "load_config"]
