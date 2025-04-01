"""
语义搜索功能
提供基于嵌入向量的语义搜索
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

# 从database/embedding导入嵌入向量创建API
from database.embedding import create_embedding
from database.embedding.utils import calculate_similarity
from database.embedding.models import JsonEmbedding

# 导入本地配置和工具
from .config import search_config
from .utils import normalize_json, format_search_result

# 设置logger
logger = logging.getLogger(__name__)

async def search_by_text(
    db: Session,
    query_text: str,
    threshold: float = search_config.DEFAULT_SIMILARITY_THRESHOLD,
    limit: int = search_config.DEFAULT_SEARCH_LIMIT
) -> List[Dict[str, Any]]:
    """
    使用文本进行语义搜索
    
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
        
        # 为查询文本创建嵌入向量
        query_embedding = await create_embedding(query_text)
        
        # 使用向量进行搜索
        results = await search_by_vector(db, query_embedding, threshold, limit)
        
        return results
    except Exception as e:
        logger.error(f"文本语义搜索失败: {str(e)}")
        return []

async def search_by_vector(
    db: Session,
    query_vector: List[float],
    threshold: float = search_config.DEFAULT_SIMILARITY_THRESHOLD,
    limit: int = search_config.DEFAULT_SEARCH_LIMIT
) -> List[Dict[str, Any]]:
    """
    使用向量进行语义搜索
    
    Args:
        db: 数据库会话
        query_vector: 查询向量
        threshold: 相似度阈值
        limit: 返回结果数量限制
        
    Returns:
        搜索结果列表
    """
    try:
        logger.info(f"执行向量语义搜索")
        
        # 从数据库获取所有嵌入记录
        db_embeddings = db.query(JsonEmbedding).all()
        
        # 计算相似度并排序
        results_with_scores = []
        for emb in db_embeddings:
            # 确保嵌入向量不是占位符
            if all(v == 0 for v in emb.embedding_vector):
                continue
                
            # 计算余弦相似度
            similarity = calculate_similarity(query_vector, emb.embedding_vector)
            
            # 如果超过阈值，添加到结果
            if similarity >= threshold:
                # 添加分数属性
                emb.score = similarity
                results_with_scores.append((emb, similarity))
        
        # 按相似度排序并截取top结果
        results_with_scores.sort(key=lambda x: x[1], reverse=True)
        top_results = [item[0] for item in results_with_scores[:limit]]
        
        logger.info(f"语义搜索找到 {len(top_results)} 个结果")
        
        # 格式化搜索结果
        return format_search_result(top_results, with_score=True)
    except Exception as e:
        logger.error(f"向量语义搜索失败: {str(e)}")
        return [] 