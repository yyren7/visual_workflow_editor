"""
数据库配置模块

提供数据库连接和设置的配置。
"""

import os
from .base import get_env_bool, get_env_int

# 数据库配置
DB_CONFIG = {
    "DATABASE_URL": os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/flow_editor_db"),
    "DB_POOL_SIZE": get_env_int("DB_POOL_SIZE", "5"),
    "DB_MAX_OVERFLOW": get_env_int("DB_MAX_OVERFLOW", "10"),
    "AUTO_MIGRATE": get_env_bool("AUTO_MIGRATE", "1")
} 