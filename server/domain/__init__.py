"""server.domain — 领域模型包（纯数据，不依赖 Flask / 数据库）。

AR03-P2 / Stage 7
-----------------
Stage 7 把 legacy 单体 ``server/backend_api.py`` 收成薄别名之前，先把
**领域模型** 抽到这里，让任务域、抽卡域与脚本共用 **同一份** 定义。

* :mod:`server.domain.models` —— ``Task`` / 各类枚举 / ``GachaSessionContext``。
"""

__all__: list = []
