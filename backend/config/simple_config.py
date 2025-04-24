"""
简化的配置模块

避免使用复杂类型，简化设计，确保能正常工作。
"""

import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class SimpleConfig:
    # Application settings
    APP_NAME = os.getenv("APP_NAME", "MyFastAPIApp")
    DEBUG = os.getenv("DEBUG", "False") == "True"

    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", "logs") # Default log directory
    LOG_FILENAME_GENERAL = os.getenv("LOG_FILENAME_GENERAL", "app.log")
    LOG_FILENAME_ERROR = os.getenv("LOG_FILENAME_ERROR", "error.log")
    LOG_FILENAME_ACCESS = os.getenv("LOG_FILENAME_ACCESS", "access.log")
    LOG_FILENAME_LANGCHAIN = os.getenv("LOG_FILENAME_LANGCHAIN", "langchain.log")

    # 应用配置
    APP_CONFIG = {
        "PROJECT_NAME": "Flow Editor",
        "BASE_URL": "http://localhost:8000", 
        "DEBUG": DEBUG,
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
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        "ACTIVE_LLM_PROVIDER": os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower()
    }

    # LangChain配置
    LANGCHAIN_CONFIG = {
        "VECTOR_STORE_TYPE": os.getenv("VECTOR_STORE_TYPE", "chroma"),
        "VECTOR_STORE_PATH": os.getenv("VECTOR_STORE_PATH", "backend/langchainchat/vector_store"),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
        "MAX_HISTORY_LENGTH": int(os.getenv("MAX_HISTORY_LENGTH", "10")),
        "DEFAULT_CONTEXT_WINDOW": int(os.getenv("DEFAULT_CONTEXT_WINDOW", "1000")),
        "DEFAULT_TEMPERATURE": 0.3,
        "DEFAULT_MAX_TOKENS": 1500,
        "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        "LANGCHAIN_API_KEY": os.getenv("LANGCHAIN_API_KEY")
    }

    # 计算LLM API设置
    def get_llm_api_url(self):
        if self.AI_CONFIG["USE_DEEPSEEK"]:
            return self.AI_CONFIG["DEEPSEEK_BASE_URL"]
        return os.getenv("LLM_API_URL", "http://localhost:8001")

    def get_llm_api_key(self):
        if self.AI_CONFIG["USE_DEEPSEEK"]:
            return self.AI_CONFIG["DEEPSEEK_API_KEY"]
        if self.AI_CONFIG["USE_GOOGLE_AI"]:
            return self.AI_CONFIG["GOOGLE_API_KEY"]
        return os.getenv("LLM_API_KEY", "your_llm_api_key")

    def get_llm_model(self):
        if self.AI_CONFIG["USE_DEEPSEEK"]:
            return self.AI_CONFIG["DEEPSEEK_MODEL"]
        return os.getenv("LLM_MODEL", "")

    # 兼容旧代码的API
    def set_ai_config(self):
        self.AI_CONFIG["LLM_API_URL"] = self.get_llm_api_url()
        self.AI_CONFIG["LLM_API_KEY"] = self.get_llm_api_key()
        self.AI_CONFIG["LLM_MODEL"] = self.get_llm_model()

    # 日志文件路径
    def set_langchain_config(self, log_dir_path):
        self.LANGCHAIN_CONFIG["LANGCHAIN_LOG_FILE"] = str(log_dir_path / "langchain.log")
        self.LANGCHAIN_CONFIG["LANGCHAIN_DEBUG_LOG_FILE"] = str(log_dir_path / "langchain_debug.log")
        self.LANGCHAIN_CONFIG["DEEPSEEK_LOG_FILE"] = str(log_dir_path / "deepseek_api.log")

    def _validate_config(self):
        """验证必要的配置项是否已设置。"""
        # 验证数据库 URL
        if not self.DB_CONFIG["DATABASE_URL"]:
            raise ValueError("错误：数据库连接 URL (DATABASE_URL) 未在 .env 文件中设置。")

        # 根据 ACTIVE_LLM_PROVIDER 验证 AI Key
        provider = self.AI_CONFIG["ACTIVE_LLM_PROVIDER"]
        if provider == 'deepseek' and not self.AI_CONFIG["DEEPSEEK_API_KEY"]:
            print("警告：LLM 提供商设置为 'deepseek'，但 DEEPSEEK_API_KEY 未设置。")
        elif provider == 'gemini' and not self.AI_CONFIG["GOOGLE_API_KEY"]:
            print("警告：LLM 提供商设置为 'gemini'，但 GOOGLE_API_KEY 未设置。")
        elif provider not in ['deepseek', 'gemini']:
            print(f"警告：不支持的 LLM 提供商 '{provider}'。请设置为 'deepseek' 或 'gemini'。")
        
        # 验证 LangSmith 配置 (如果启用)
        if self.LANGCHAIN_CONFIG["LANGCHAIN_TRACING_V2"] and not self.LANGCHAIN_CONFIG["LANGCHAIN_API_KEY"]:
            print("警告：LangSmith 追踪已启用 (LANGCHAIN_TRACING_V2=true)，但 LANGCHAIN_API_KEY 未设置。")

# Instantiate the configuration
config = SimpleConfig()

# Example usage:
if __name__ == "__main__":
    print(f"App Name: {config.APP_NAME}")
    print(f"Debug Mode: {config.DEBUG}")
    print(f"Log Level: {config.LOG_LEVEL}")
    print(f"Log Directory: {config.LOG_DIR}")
    print(f"General Log Filename: {config.LOG_FILENAME_GENERAL}")
    print(f"Error Log Filename: {config.LOG_FILENAME_ERROR}")
    print(f"Access Log Filename: {config.LOG_FILENAME_ACCESS}")
    print(f"Langchain Log Filename: {config.LOG_FILENAME_LANGCHAIN}")

    # 测试配置系统
    def test_config():
        """测试简化的配置系统"""
        print("===== 简化配置系统测试 =====")
        
        # 测试应用配置
        print(f"应用名称: {config.APP_CONFIG['PROJECT_NAME']}")
        print(f"调试模式: {config.APP_CONFIG['DEBUG']}")
        print(f"CORS源: {config.APP_CONFIG['CORS_ORIGINS']}")
        
        # 测试数据库配置
        print(f"数据库URL: {config.DB_CONFIG['DATABASE_URL']}")
        
        # 测试AI提供商配置
        print(f"使用DeepSeek: {config.AI_CONFIG['USE_DEEPSEEK']}")
        print(f"DeepSeek模型: {config.AI_CONFIG['DEEPSEEK_MODEL']}")
        print(f"当前LLM API URL: {config.AI_CONFIG['LLM_API_URL']}")
        
        # 测试LangChain配置
        print(f"向量存储类型: {config.LANGCHAIN_CONFIG['VECTOR_STORE_TYPE']}")
        print(f"向量存储路径: {config.LANGCHAIN_CONFIG['VECTOR_STORE_PATH']}")
        print(f"LangChain日志文件: {config.LANGCHAIN_CONFIG['LANGCHAIN_LOG_FILE']}")
        
        print("===== 测试完成 =====")

    test_config() 