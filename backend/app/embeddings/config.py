from pydantic_settings import BaseSettings
from typing import Optional

class EmbeddingConfig(BaseSettings):
    """Embedding配置"""
    
    # 默认embedding模型配置
    DEFAULT_MODEL_NAME: str = "BAAI/bge-large-zh-v1.5"
    VECTOR_DIMENSION: int = 1024  # BAAI/bge-large-zh-v1.5 输出1024维向量
    
    # 相似度搜索配置
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.8
    DEFAULT_SEARCH_LIMIT: int = 10
    
    # Gemini配置
    GOOGLE_API_KEY: Optional[str] = None
    
    # 向量数据库配置
    VECTOR_DB_TYPE: str = "docarray"  # 使用DocArrayInMemorySearch
    VECTOR_DB_HOST: Optional[str] = None
    VECTOR_DB_PORT: Optional[int] = None
    VECTOR_DB_API_KEY: Optional[str] = None
    
    class Config:
        env_prefix = "EMBEDDING_"  # 环境变量前缀

# 创建配置实例
embedding_config = EmbeddingConfig() 