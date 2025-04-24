import os
from dotenv import load_dotenv
from pathlib import Path

# 加载 .env 文件
load_dotenv()

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")

# JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# AI 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# REMOVED: USE_GOOGLE_AI: bool = False  # 禁用Google AI
ACTIVE_LLM_PROVIDER = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower()

# LangSmith Tracing (Optional)
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

# 检查必要的 AI 配置 (根据 ACTIVE_LLM_PROVIDER)
if ACTIVE_LLM_PROVIDER == "deepseek" and not DEEPSEEK_API_KEY:
    print("警告: ACTIVE_LLM_PROVIDER 设置为 deepseek, 但 DEEPSEEK_API_KEY 未设置.")
elif ACTIVE_LLM_PROVIDER == "gemini" and not GOOGLE_API_KEY:
    print("警告: ACTIVE_LLM_PROVIDER 设置为 gemini, 但 GOOGLE_API_KEY 未设置.")

# 可以在这里添加其他应用配置，例如 CORS 设置等
# ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"] # 前端地址示例

class Config:
    """
    Configuration settings for the backend application.
    """
    PROJECT_NAME: str = "Flow Editor"
    BASE_URL: str = "http://localhost:8000"  # Default base URL
    API_PREFIX: str = "/api"
    SECRET_KEY: str = SECRET_KEY
    ALGORITHM: str = ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = ACCESS_TOKEN_EXPIRE_MINUTES

    # Database settings
    DATABASE_URL: str = DATABASE_URL

    # LLM API settings
    USE_DEEPSEEK: bool = True  # 启用DeepSeek
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # 兼容旧代码的配置
    LLM_API_URL: str = os.getenv("LLM_API_URL", "http://localhost:8001")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", DEEPSEEK_API_KEY if USE_DEEPSEEK else "your_llm_api_key") 
    LLM_MODEL: str = os.getenv("LLM_MODEL", DEEPSEEK_MODEL)
    
    # Debug mode
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"

    # CORS settings
    CORS_ORIGINS: list = [
        "http://localhost:3000",      # 本地开发环境
        "http://172.18.0.3:3000",     # Docker网络中的前端容器
        "http://workflow-editor-frontend:3000",  # 容器名称访问
        "*"                          # 允许所有源（生产环境应该更严格）
    ]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]

    # Global Variables File Path
    GLOBAL_VARIABLES_PATH: str = os.getenv("GLOBAL_VARIABLES_PATH", "global_variables.json") # Default path for global variables

    # Email settings
    MAIL_HOST: str = os.getenv("MAIL_HOST", "smtp.example.com")  # Default SMTP server
    MAIL_USER: str = os.getenv("MAIL_USER", "your_email@example.com")  # Default email username
    MAIL_PASS: str = os.getenv("MAIL_PASS", "your_email_password")  # Default email password

    @staticmethod
    def configure():
        """
        Load environment variables and configure the application.
        """
        # This method can be extended to perform more complex configuration tasks
        pass
