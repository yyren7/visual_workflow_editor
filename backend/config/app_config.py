"""
应用配置模块

提供应用程序核心功能所需的配置设置。
"""

from .base import get_env_bool
import os

# 应用配置
APP_CONFIG = {
    "PROJECT_NAME": "Flow Editor",
    "BASE_URL": "http://localhost:8000", 
    "DEBUG": get_env_bool("DEBUG"),
    "API_PREFIX": "/api",
    "SECRET_KEY": os.getenv("SECRET_KEY", "your_secret_key"),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": 300,
    "CORS_ORIGINS": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://172.18.0.3:3000",
        "http://workflow-editor-frontend:3000",
        "*"
    ],
    "CORS_CREDENTIALS": True,
    "CORS_METHODS": ["*"],
    "CORS_HEADERS": ["*"],
    "GLOBAL_VARIABLES_PATH": os.getenv("GLOBAL_VARIABLES_PATH", "global_variables.json"),
    # 邮件设置
    "MAIL_HOST": os.getenv("MAIL_HOST", "smtp.example.com"),
    "MAIL_USER": os.getenv("MAIL_USER", "your_email@example.com"),
    "MAIL_PASS": os.getenv("MAIL_PASS", "your_email_password")
} 