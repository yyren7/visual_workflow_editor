"""
基础配置模块

提供共享的配置函数和初始化逻辑。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 显式加载项目根目录的.env文件
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path=workspace_env_path)

# 日志目录设置
LOG_DIR = os.getenv("LOG_DIR", "backend/app/logs")

# 确保日志目录存在
log_dir_path = Path(LOG_DIR)
log_dir_path.mkdir(parents=True, exist_ok=True)

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

def get_log_file_path(filename):
    """获取日志文件路径"""
    return str(log_dir_path / filename) 