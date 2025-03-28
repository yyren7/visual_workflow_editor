from pydantic_settings import BaseSettings
from typing import Optional

class EmbeddingConfig(BaseSettings):
    """Embedding配置"""
    
    # 默认配置
    DEFAULT_MODEL_NAME: str = "keyword_matching"  # 改为更准确的名称，表示使用关键词匹配
    VECTOR_DIMENSION: int = 768  # 保持向量维度以兼容现有代码
    
    # 相似度搜索配置
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.5
    DEFAULT_SEARCH_LIMIT: int = 10
    
    # LMStudio API配置
    USE_LMSTUDIO: bool = False  # 是否使用LMStudio API
    LMSTUDIO_API_BASE_URL: str = "http://localhost:1234/v1"  # LMStudio API基础URL
    LMSTUDIO_API_KEY: Optional[str] = None  # LMStudio API密钥(如需)
    
    class Config:
        env_prefix = "EMBEDDING_"  # 环境变量前缀

# 创建配置实例
embedding_config = EmbeddingConfig() 