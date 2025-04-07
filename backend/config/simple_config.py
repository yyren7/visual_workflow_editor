"""
简化的配置模块

避免使用复杂类型，简化设计，确保能正常工作。
"""

import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# 显式加载项目根目录的.env文件
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path=workspace_env_path)

# 日志目录设置
LOG_DIR = os.getenv("LOG_DIR", "backend/app/logs")

# 确保日志目录存在
log_dir_path = Path(LOG_DIR)
log_dir_path.mkdir(parents=True, exist_ok=True)

# 应用配置
APP_CONFIG = {
    "PROJECT_NAME": "Flow Editor",
    "BASE_URL": "http://localhost:8000", 
    "DEBUG": os.getenv("DEBUG", "0") == "1",
    "CORS_ORIGINS": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://172.18.0.3:3000",
        "http://workflow-editor-frontend:3000",
        "*"
    ]
}

# 数据库配置
DB_CONFIG = {
    "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///database/flow_editor.db")
}

# AI提供商配置
AI_CONFIG = {
    "USE_DEEPSEEK": os.getenv("USE_DEEPSEEK", "1") == "1",
    "USE_GOOGLE_AI": os.getenv("USE_GOOGLE_AI", "0") == "1",
    "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
    "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", "")
}

# LangChain配置
LANGCHAIN_CONFIG = {
    "VECTOR_STORE_TYPE": os.getenv("VECTOR_STORE_TYPE", "chroma"),
    "VECTOR_STORE_PATH": os.getenv("VECTOR_STORE_PATH", "backend/langchainchat/vector_store"),
    "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
    "MAX_HISTORY_LENGTH": int(os.getenv("MAX_HISTORY_LENGTH", "10")),
    "DEFAULT_CONTEXT_WINDOW": int(os.getenv("DEFAULT_CONTEXT_WINDOW", "1000")),
    "DEFAULT_TEMPERATURE": 0.3,
    "DEFAULT_MAX_TOKENS": 1500
}

# 计算LLM API设置
def get_llm_api_url():
    if AI_CONFIG["USE_DEEPSEEK"]:
        return AI_CONFIG["DEEPSEEK_BASE_URL"]
    return os.getenv("LLM_API_URL", "http://localhost:8001")

def get_llm_api_key():
    if AI_CONFIG["USE_DEEPSEEK"]:
        return AI_CONFIG["DEEPSEEK_API_KEY"]
    if AI_CONFIG["USE_GOOGLE_AI"]:
        return AI_CONFIG["GOOGLE_API_KEY"]
    return os.getenv("LLM_API_KEY", "your_llm_api_key")

def get_llm_model():
    if AI_CONFIG["USE_DEEPSEEK"]:
        return AI_CONFIG["DEEPSEEK_MODEL"]
    return os.getenv("LLM_MODEL", "")

# 兼容旧代码的API
AI_CONFIG["LLM_API_URL"] = get_llm_api_url()
AI_CONFIG["LLM_API_KEY"] = get_llm_api_key()
AI_CONFIG["LLM_MODEL"] = get_llm_model()

# 日志文件路径
LANGCHAIN_CONFIG["LANGCHAIN_LOG_FILE"] = str(log_dir_path / "langchain.log")
LANGCHAIN_CONFIG["LANGCHAIN_DEBUG_LOG_FILE"] = str(log_dir_path / "langchain_debug.log")
LANGCHAIN_CONFIG["DEEPSEEK_LOG_FILE"] = str(log_dir_path / "deepseek_api.log")

# 测试配置系统
def test_config():
    """测试简化的配置系统"""
    print("===== 简化配置系统测试 =====")
    
    # 测试应用配置
    print(f"应用名称: {APP_CONFIG['PROJECT_NAME']}")
    print(f"调试模式: {APP_CONFIG['DEBUG']}")
    print(f"CORS源: {APP_CONFIG['CORS_ORIGINS']}")
    
    # 测试数据库配置
    print(f"数据库URL: {DB_CONFIG['DATABASE_URL']}")
    
    # 测试AI提供商配置
    print(f"使用DeepSeek: {AI_CONFIG['USE_DEEPSEEK']}")
    print(f"DeepSeek模型: {AI_CONFIG['DEEPSEEK_MODEL']}")
    print(f"当前LLM API URL: {AI_CONFIG['LLM_API_URL']}")
    
    # 测试LangChain配置
    print(f"向量存储类型: {LANGCHAIN_CONFIG['VECTOR_STORE_TYPE']}")
    print(f"向量存储路径: {LANGCHAIN_CONFIG['VECTOR_STORE_PATH']}")
    print(f"LangChain日志文件: {LANGCHAIN_CONFIG['LANGCHAIN_LOG_FILE']}")
    
    print("===== 测试完成 =====")

if __name__ == "__main__":
    test_config() 