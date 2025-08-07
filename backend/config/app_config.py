"""
应用配置模块

提供应用程序核心功能所需的配置设置。
"""

from .base import get_env_bool
import os

def get_cors_origins() -> list[str]:
    """
    从环境变量 CORS_ORIGINS（逗号分隔）中获取允许的源列表。
    如果环境变量未设置，则返回一个包含常见本地开发源的默认列表。
    如果环境变量设置为 "*"，则返回 ["*"] 以允许所有源。
    """
    origins_str = os.getenv("CORS_ORIGINS")
    if origins_str:
        if origins_str == "*":
            return ["*"]
        return [origin.strip() for origin in origins_str.split(',') if origin.strip()]
    else:
        # 默认允许的源列表（如果环境变量未设置）
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001", # 确保开发时常用的端口也被包含
            "http://127.0.0.1:3001", # 新增：允许来自127.0.0.1:3001的请求
            "http://workflow-editor-frontend:3000", # Docker Compose 服务名
            "http://localhost:8000", # 后端自己
            "http://127.0.0.1:8000"  # 后端自己
        ]

def is_cors_origin_allowed(origin: str) -> bool:
    """
    动态验证CORS origin是否被允许
    支持：
    1. 静态配置的origins列表
    2. 192.168.16.*网段的所有地址
    """
    import re
    
    # 获取静态配置的origins
    allowed_origins = get_cors_origins()
    
    # 如果配置了 "*"，允许所有源
    if "*" in allowed_origins:
        return True
    
    # 检查是否在静态列表中
    if origin in allowed_origins:
        return True
    
    # 检查是否是192.168.16.*网段（支持常用端口）
    pattern = r'^http://192\.168\.16\.\d{1,3}:(3000|3001|8000|8080)$'
    if re.match(pattern, origin):
        return True
    
    # 检查环境变量中是否明确配置了192.168.16.*模式
    origins_str = os.getenv("CORS_ORIGINS", "")
    if "192.168.16.*" in origins_str:
        subnet_pattern = r'^http://192\.168\.16\.\d{1,3}:\d+$'
        if re.match(subnet_pattern, origin):
            return True
    
    return False

# 应用配置
APP_CONFIG = {
    "PROJECT_NAME": "Flow Editor",
    "BASE_URL": "http://localhost:8000", 
    "DEBUG": get_env_bool("DEBUG"),
    "API_PREFIX": "/api",
    "SECRET_KEY": os.getenv("SECRET_KEY", "your_secret_key"),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": 300,
    "CORS_ORIGINS": get_cors_origins(),
    "CORS_CREDENTIALS": True,
    "CORS_METHODS": ["*"],
    "CORS_HEADERS": ["*"],
    "GLOBAL_VARIABLES_PATH": os.getenv("GLOBAL_VARIABLES_PATH", "global_variables.json"),
    # 邮件设置
    "MAIL_HOST": os.getenv("MAIL_HOST", "smtp.example.com"),
    "MAIL_USER": os.getenv("MAIL_USER", "your_email@example.com"),
    "MAIL_PASS": os.getenv("MAIL_PASS", "your_email_password")
} 