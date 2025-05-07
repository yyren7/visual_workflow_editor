"""
LangChain配置模块

提供LangChain模块所需的特定配置。
"""

import os
from .base import get_env_bool, get_env_int, get_env_float, get_log_file_path, LOG_DIR

# LangChain配置
LANGCHAIN_CONFIG = {
    "PROJECT_NAME": "Flow Editor - LangChain Module",
    "VECTOR_STORE_TYPE": os.getenv("VECTOR_STORE_TYPE", "chroma"),
    "VECTOR_STORE_PATH": os.getenv("VECTOR_STORE_PATH", "backend/langgraphchat/vector_store"),
    "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
    "MAX_HISTORY_LENGTH": get_env_int("MAX_HISTORY_LENGTH", "10"),
    "DEFAULT_CONTEXT_WINDOW": get_env_int("DEFAULT_CONTEXT_WINDOW", "1000"),
    "DEFAULT_TEMPERATURE": 0.3,
    "DEFAULT_MAX_TOKENS": 1500,
    "CHAT_MODEL_NAME": "deepseek-chat",
    "LOG_LLM_CALLS": True,
    "API_KEY_ADD_PREFIX": get_env_bool("API_KEY_ADD_PREFIX", "0"),
    "ALTERNATIVE_BASE_URL": os.getenv("ALTERNATIVE_BASE_URL", ""),
    "ENABLE_TOOLS": True,
    "PERSIST_SESSIONS": True,
    "SESSIONS_DB_PATH": os.getenv("SESSIONS_DB_PATH", "backend/langgraphchat/sessions"),
    "LOG_LEVEL": os.getenv("LOG_LEVEL", "DEBUG"),
    "LOG_DIR": LOG_DIR
}

# 添加日志文件路径
LANGCHAIN_CONFIG["LANGCHAIN_LOG_FILE"] = get_log_file_path("langchain.log")
LANGCHAIN_CONFIG["LANGCHAIN_DEBUG_LOG_FILE"] = get_log_file_path("langchain_debug.log") 
LANGCHAIN_CONFIG["DEEPSEEK_LOG_FILE"] = get_log_file_path("deepseek_api.log") 