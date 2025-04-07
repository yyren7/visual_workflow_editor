"""
Flow Editor配置模块

此模块提供应用程序所需的所有配置设置。
采用分布式文件组织，保持配置清晰和模块化。
"""

# 导出所有配置，使其可以从backend.config直接导入
from .app_config import APP_CONFIG
from .db_config import DB_CONFIG
from .ai_config import AI_CONFIG, get_llm_api_url, get_llm_api_key, get_llm_model
from .langchain_config import LANGCHAIN_CONFIG
from .base import get_env_bool, get_env_int, get_env_float, get_log_file_path, LOG_DIR 