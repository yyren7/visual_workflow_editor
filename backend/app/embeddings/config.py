from pydantic_settings import BaseSettings
from typing import Optional

class EmbeddingConfig(BaseSettings):
    """Embedding配置"""
    
    # 默认embedding模型配置
    DEFAULT_MODEL_NAME: str = "node_database"  # 直接使用节点数据库而不是模型
    VECTOR_DIMENSION: int = 768  # 保持向量维度以兼容现有代码
    
    # 相似度搜索配置 - 现在使用关键词匹配而非嵌入相似度
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.5  # 降低阈值使匹配更容易
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