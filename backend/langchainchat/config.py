from pydantic_settings import BaseSettings
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 添加调试功能
def print_env_info():
    """打印环境变量信息，用于调试"""
    import sys
    from datetime import datetime
    
    # 确保环境变量已加载 - 显式加载项目根目录的.env文件
    workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
    load_dotenv(dotenv_path=workspace_env_path)
    
    print("\n===== 环境变量调试信息 =====")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"Python版本: {sys.version}")
    
    # 打印与API相关的环境变量
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    api_base = os.environ.get("DEEPSEEK_BASE_URL", "")
    
    # 安全打印密钥（仅显示部分）
    if api_key:
        key_prefix = api_key[:8] if len(api_key) > 10 else ""
        key_suffix = api_key[-4:] if len(api_key) > 10 else ""
        key_length = len(api_key)
        print(f"DEEPSEEK_API_KEY: {key_prefix}...{key_suffix} (长度: {key_length}字符)")
    else:
        print("DEEPSEEK_API_KEY: 未设置")
    
    print(f"DEEPSEEK_BASE_URL: {api_base}")
    
    # 打印所有环境变量名称（不打印值）
    print(f"所有环境变量: {sorted(list(os.environ.keys()))}")
    print("=======================\n")

# 调用调试函数
# print_env_info()  # 注释掉，避免与run_backend.py重复输出环境变量信息

class LangChainSettings(BaseSettings):
    """LangChain聊天模块的配置设置"""
    
    # 项目设置
    PROJECT_NAME: str = "Flow Editor - LangChain Module"
    
    # DeepSeek API设置
    USE_DEEPSEEK: bool = True
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # API格式选项
    API_KEY_ADD_PREFIX: bool = os.getenv("API_KEY_ADD_PREFIX", "0") == "1"
    ALTERNATIVE_BASE_URL: str = os.getenv("ALTERNATIVE_BASE_URL", "")  # 替代API端点
    
    # 向量存储设置
    VECTOR_STORE_TYPE: str = os.getenv("VECTOR_STORE_TYPE", "chroma")
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", "backend/langchainchat/vector_store")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
    
    # 记忆设置
    MAX_HISTORY_LENGTH: int = int(os.getenv("MAX_HISTORY_LENGTH", "10"))
    DEFAULT_CONTEXT_WINDOW: int = int(os.getenv("DEFAULT_CONTEXT_WINDOW", "1000"))
    
    # 全局变量路径
    GLOBAL_VARIABLES_PATH: str = os.getenv("GLOBAL_VARIABLES_PATH", "global_variables.json")
    
    # 调试模式
    DEBUG: bool = os.getenv("DEBUG", "1") == "1"
    
    # LLM模型参数默认值
    DEFAULT_TEMPERATURE: float = 0.3
    DEFAULT_MAX_TOKENS: int = 1500
    
    # LangChain对话模型名称
    CHAT_MODEL_NAME: str = "deepseek-chat"
    
    # 日志设置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "backend/app/logs")
    
    # 日志文件路径
    @property
    def langchain_log_file(self) -> str:
        """获取LangChain日志文件路径"""
        log_dir = Path(self.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir / "langchain.log")
    
    # 是否记录LLM调用
    LOG_LLM_CALLS: bool = True
    
    # 工具设置
    ENABLE_TOOLS: bool = True
    
    # 会话持久化
    PERSIST_SESSIONS: bool = True
    SESSIONS_DB_PATH: str = os.getenv("SESSIONS_DB_PATH", "backend/langchainchat/sessions")
    
    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'),
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # 忽略额外的环境变量，如DATABASE_URL
    }

# 创建单例设置实例
settings = LangChainSettings() 