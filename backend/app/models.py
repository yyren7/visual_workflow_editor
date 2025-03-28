"""
已弃用: 请使用 database.models 模块
此模块仅用于向后兼容，重定向到新的模型模块
"""

import warnings

# 导入所有模型
from database.models import (
    User,
    Flow,
    FlowVariable,
    VersionInfo,
    UserFlowPreference,
    Base
)

warnings.warn(
    "从 backend.app.models 导入已弃用。请直接从 database.models 导入。",
    DeprecationWarning,
    stacklevel=2
) 