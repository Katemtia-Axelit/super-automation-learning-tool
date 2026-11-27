"""server.services.free_task_adapter - 自由任务适配层的 **稳定公共入口**。

定位
----
HTTP 层（:mod:`server.blueprints.free_task_bp`）与未来的接线方应当
**只** 从本模块导入适配 API。本模块是 **显式重导出层**，唯一实现体
是已经独立路径安全复验过的 :mod:`server.services.free_task_adapter_ab_opus`
（``LT_MODEL_AB_B_20261022_B``）。本模块 **不复制、不粘贴** 实现体 ——
避免出现第二份会漂移的适配逻辑。

公共 API（显式导出）
--------------------
- :class:`FreeTaskAdapter` —— 注入式适配器；
- :class:`FreeTaskAdapterError` —— 适配层自身的错误（code 前缀 ``adapter_``）；
- :func:`validate_synthetic_db_path` —— 只验证、不创建的合成路径校验。

另外重导出契约常量 :data:`APPEND_ALLOWED_KEYS`、
:data:`SUMMARY_ALLOWED_KEYS`、:data:`SUPPORTED_ACTIONS`、
:data:`FORBIDDEN_DB_BASENAMES`，以及只读引用
:data:`implementation`（需要检查实现细节时使用）。

不变量
------
1. **无默认 DB 路径**：:class:`FreeTaskAdapter` 只接受调用方注入的既有
   :class:`~server.services.free_task_events.FreeTaskEventStore`；本模块
   **绝不** 构造 store、**绝不** 建库、**绝不** 发现数据库。
2. **绝不 import Astra 原型**（``free_task_adapter_ab_astra`` 存在已知
   Windows 内部 junction 绕过缺陷，**不得** 作为规范实现）。本模块
   只依赖 opus 实现体。
3. **无副作用**：本模块不 import Flask、不读 ``config/config.json``、
   不写 ``src/notes/**``、不联网。
4. 领域错误码原样透传：底层
   :class:`~server.services.free_task_events.FreeTaskEventError` 不被捕获、
   不被包装；本模块只对自己的形状校验抛
   :class:`FreeTaskAdapterError`。

进入生产之前仍必须完成的工作（本模块 **不** 声称已具备）
--------------------------------------------------------------
1. **原子化安全打开 / TOCTOU 复审**：当前 ``validate_synthetic_db_path``
   只做 ``lstat`` 元数据校验后再由调用方打开，存在检查与使用之间的
   时间窗；生产接线前必须改为“校验 + 打开”的原子流程（例如
   ``O_NOFOLLOW`` / 以句柄为准的 ``fstat`` 复检 / Windows
   ``FILE_FLAG_OPEN_REPARSE_POINT`` 复核），并重新做一次独立安全复审。
2. **用户授权**：当前接口 **没有** 认证、没有 CSRF、没有速率限制、
   没有调用者身份；任何能访问该端口的主体都能写入事件账本。生产暴露前
   必须由 Controller 决定授权模型。
3. **真实数据留存策略**：本层只面向 synthetic 沙箱；真实用户事件一旦落库，
   需要先有明确的留存期、导出、删除与审计策略，以及与
   ``src/notes/**`` / ``data/task_publisher.db`` 的一致性约定。
4. **并发与规模**：真实流量下的锁竞争（WAL + ``BEGIN IMMEDIATE``）、
   账本体积与归档策略尚未评估。
"""

from __future__ import annotations

from .free_task_adapter_ab_opus import (  # noqa: F401  (稳定公共入口：显式重导出)
    APPEND_ALLOWED_KEYS,
    FORBIDDEN_DB_BASENAMES,
    SUMMARY_ALLOWED_KEYS,
    SUPPORTED_ACTIONS,
    FreeTaskAdapter,
    FreeTaskAdapterError,
    validate_synthetic_db_path,
)
from . import free_task_adapter_ab_opus as _implementation

#: 唯一实现体引用（只读）。公共 API 请直接用本模块的显式导出。
implementation = _implementation

__all__ = [
    "APPEND_ALLOWED_KEYS",
    "FORBIDDEN_DB_BASENAMES",
    "SUMMARY_ALLOWED_KEYS",
    "SUPPORTED_ACTIONS",
    "FreeTaskAdapter",
    "FreeTaskAdapterError",
    "implementation",
    "validate_synthetic_db_path",
]