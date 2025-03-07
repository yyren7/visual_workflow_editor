import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    Configuration settings for the backend application.
    """
    PROJECT_NAME: str = "Flow Editor"
    BASE_URL: str = "http://localhost:8000"  # Default base URL
    API_PREFIX: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your_secret_key")  # Use environment variable, default to "your_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/flow_editor")  # Default PostgreSQL URL

    # LLM API settings
    LLM_API_URL: str = os.getenv("LLM_API_URL", "http://localhost:8001")  # Default LLM API URL
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "your_llm_api_key") # Use environment variable, default to "your_llm_api_key"

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
