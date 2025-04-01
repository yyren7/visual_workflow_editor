"""
嵌入向量模块
提供创建和管理嵌入向量的功能
"""

from .service import EmbeddingService
from .api import create_embedding, create_json_embedding, get_embedding_model_info

__all__ = [
    'EmbeddingService',
    'create_embedding',
    'create_json_embedding',
    'get_embedding_model_info'
] 