"""
嵌入向量API接口
提供简单的对外接口函数
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from .service import EmbeddingService
from .utils import normalize_json

# 设置logger
logger = logging.getLogger(__name__)

async def create_embedding(text: str) -> List[float]:
    """
    为文本创建嵌入向量
    
    Args:
        text: 要嵌入的文本
        
    Returns:
        嵌入向量
    """
    try:
        logger.info(f"创建文本嵌入向量")
        service = EmbeddingService.get_instance()
        return await service.create_embedding_vector(text)
    except Exception as e:
        logger.error(f"创建文本嵌入向量失败: {str(e)}")
        raise

async def create_json_embedding(db: Session, json_data: Dict[str, Any]):
    """
    为JSON数据创建嵌入并保存到数据库
    
    Args:
        db: 数据库会话
        json_data: 要嵌入的JSON数据
        
    Returns:
        创建的嵌入记录
    """
    try:
        logger.info(f"创建JSON嵌入向量并保存到数据库")
        service = EmbeddingService.get_instance()
        return await service.create_embedding(db, json_data)
    except Exception as e:
        logger.error(f"创建JSON嵌入向量失败: {str(e)}")
        raise

def get_embedding_model_info() -> Dict[str, Any]:
    """
    获取当前嵌入模型信息
    
    Returns:
        模型信息字典
    """
    try:
        logger.info(f"获取嵌入模型信息")
        service = EmbeddingService.get_instance()
        return service.get_model_info()
    except Exception as e:
        logger.error(f"获取嵌入模型信息失败: {str(e)}")
        return {
            "error": str(e),
            "model_name": "unknown",
            "vector_dimension": 0,
            "using_lmstudio": False
        } 