"""
已弃用: 请使用 database.connection 模块
此模块仅用于向后兼容，重定向到新的数据库模块
"""

import warnings

# 导入新路径中的数据库组件
from database.connection import (
    engine,
    Base,
    SessionLocal,
    get_db,
    get_db_context,
    verify_connection
)

warnings.warn(
    "从 backend.app.database 导入已弃用。请直接从 database.connection 导入。",
    DeprecationWarning,
    stacklevel=2
) 