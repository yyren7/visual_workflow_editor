"""
搜索配置
"""

from pydantic_settings import BaseSettings

class SearchConfig(BaseSettings):
    """搜索配置"""
    
    # 相似度搜索配置
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.5
    DEFAULT_SEARCH_LIMIT: int = 10
    
    # 节点搜索配置
    NODE_KEYWORD_MIN_LENGTH: int = 3
    
    class Config:
        env_prefix = "SEARCH_"  # 环境变量前缀

# 创建全局配置实例
search_config = SearchConfig() 