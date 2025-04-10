"""
语义搜索功能
提供基于嵌入向量的语义搜索
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import uuid

# Removed imports that are no longer needed here
# from database.embedding import create_embedding
# from database.embedding.utils import calculate_similarity
# from database.models import JsonEmbedding
from database.session import AsyncSessionLocal # Assuming AsyncSessionLocal might still be needed if db session is passed differently
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Import the service that now handles search
from database.embedding.service import DatabaseEmbeddingService

# 导入本地配置和工具
from .config import search_config
# format_search_result is now used within DatabaseEmbeddingService, but utils might be needed for normalize_json
from .utils import normalize_json # Keep if needed, remove otherwise

# 设置logger
logger = logging.getLogger(__name__)

async def search_by_text(
    db: Session,
    query_text: str,
    threshold: float = search_config.DEFAULT_SIMILARITY_THRESHOLD,
    limit: int = search_config.DEFAULT_SEARCH_LIMIT
) -> List[Dict[str, Any]]:
    """
    使用文本进行语义搜索 (调用 DatabaseEmbeddingService)

    Args:
        db: 数据库会话
        query_text: 查询文本
        threshold: 相似度阈值
        limit: 返回结果数量限制

    Returns:
        搜索结果列表
    """
    try:
        logger.info(f"执行文本语义搜索: {query_text}")

        # Get instance of the database embedding service
        # Assuming DatabaseEmbeddingService doesn't require config for __init__ now
        embedding_service = DatabaseEmbeddingService()

        # Call the unified similarity search method
        results = await embedding_service.similarity_search(
            db=db,
            query=query_text,
            threshold=threshold,
            k=limit # Pass limit as k
        )

        return results
    except Exception as e:
        logger.error(f"文本语义搜索失败: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []

# Removed search_by_vector as its logic is now in DatabaseEmbeddingService.similarity_search
# async def search_by_vector(...)
#    ... 