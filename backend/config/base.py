"""
基础配置模块

提供共享的配置函数和初始化逻辑。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录确定 (假设此文件在 /workspace/backend/config/base.py)
# Path(__file__).resolve() -> /workspace/backend/config/base.py
# .parent -> /workspace/backend/config
# .parent.parent -> /workspace/backend
# .parent.parent.parent -> /workspace
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 显式加载项目根目录的.env文件
workspace_env_path = PROJECT_ROOT / '.env'
if workspace_env_path.exists():
    load_dotenv(dotenv_path=workspace_env_path)
else:
    # This print is fine as it's very early configuration
    print(f"Warning: .env file not found at {workspace_env_path}. Using environment variables or defaults.")

# --- 日志配置 --- 
# LOG_DIR_BASENAME 用于从环境变量读取日志目录的基名，例如 "logs"
LOG_DIR_BASENAME_FROM_ENV = os.getenv("LOG_DIR_BASENAME", "logs") 
LOG_DIR = PROJECT_ROOT / LOG_DIR_BASENAME_FROM_ENV # LOG_DIR 现在是一个 Path 对象
LOG_DIR.mkdir(parents=True, exist_ok=True) # 在此确保日志目录存在

# 默认日志级别字符串，如果 LOG_LEVEL 环境变量未设置，logging_config.py 将使用此值
DEFAULT_LOG_LEVEL = "INFO" 

# 日志文件路径常量 (作为 Path 对象)
BACKEND_LOG_FILE = LOG_DIR / "backend.log"
DEEPSEEK_LOG_FILE = LOG_DIR / "deepseek_api.log"
LANGGRAPHCHAT_DEBUG_LOG_FILE = LOG_DIR / "langgraphchat_debug.log"
# --- 结束日志配置 ---

# 辅助函数
def get_env_bool(env_var, default="0"):
    """获取环境变量布尔值"""
    return os.getenv(env_var, default) == "1"

def get_env_int(env_var, default="0"):
    """获取环境变量整数值"""
    return int(os.getenv(env_var, default))

def get_env_float(env_var, default="0.0"):
    """获取环境变量浮点值"""
    return float(os.getenv(env_var, default))

def get_log_file_path(filename: str) -> str:
    """获取日志文件在LOG_DIR下的绝对路径 (返回字符串)"""
    return str(LOG_DIR / filename) 