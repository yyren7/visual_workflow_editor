"""
嵌入向量服务
提供嵌入向量的创建和管理功能
"""

import time
import logging
from typing import Any, Dict, List
from sqlalchemy.orm import Session

# 导入工具和配置
from .utils import normalize_json
from .config import embedding_config
from .models import JsonEmbedding
from .lmstudio_client import LMStudioClient

# 设置logger
logger = logging.getLogger(__name__)

# 添加全局缓存变量
_lmstudio_client = None

class EmbeddingService:
    """嵌入向量服务，提供嵌入向量的创建功能"""
    
    def __init__(self, model_name: str = embedding_config.DEFAULT_MODEL_NAME):
        """
        初始化嵌入向量服务
        
        Args:
            model_name: 要使用的嵌入模型名称
        """
        self.model_name = model_name
        
        # 检查是否使用LMStudio
        if embedding_config.USE_LMSTUDIO:
            logger.info(f"初始化EmbeddingService，使用LMStudio API: {embedding_config.LMSTUDIO_API_BASE_URL}")
            # 初始化LMStudio客户端
            global _lmstudio_client
            if _lmstudio_client is None:
                _lmstudio_client = LMStudioClient(
                    api_base_url=embedding_config.LMSTUDIO_API_BASE_URL,
                    api_key=embedding_config.LMSTUDIO_API_KEY
                )
            self.lmstudio_client = _lmstudio_client
        else:
            logger.info(f"初始化EmbeddingService，使用占位符向量而非嵌入模型")
    
    @classmethod
    def get_instance(cls, model_name: str = embedding_config.DEFAULT_MODEL_NAME):
        """
        获取EmbeddingService的单例实例
        
        Args:
            model_name: 要使用的嵌入模型名称
            
        Returns:
            EmbeddingService实例
        """
        global _embedding_service_instance
        if '_embedding_service_instance' not in globals() or _embedding_service_instance is None:
            logger.info(f"创建EmbeddingService单例实例")
            _embedding_service_instance = cls(model_name)
        return _embedding_service_instance

    async def create_embedding_vector(self, text: str) -> List[float]:
        """
        为文本创建嵌入向量
        
        Args:
            text: 要嵌入的文本
            
        Returns:
            嵌入向量
        """
        try:
            # 使用LMStudio API或占位符
            if embedding_config.USE_LMSTUDIO:
                try:
                    # 使用LMStudio API生成嵌入向量
                    embedding_vector = self.lmstudio_client.create_embedding(text)
                    logger.info(f"成功使用LMStudio API生成嵌入向量，维度: {len(embedding_vector)}")
                    return embedding_vector
                except Exception as e:
                    logger.error(f"使用LMStudio生成嵌入向量失败: {str(e)}，将使用占位符")
                    # 如果LMStudio调用失败，使用占位符向量
                    return [0.0] * embedding_config.VECTOR_DIMENSION
            else:
                # 使用占位符向量（全0）
                return [0.0] * embedding_config.VECTOR_DIMENSION
        except Exception as e:
            logger.error(f"创建嵌入向量时出错: {str(e)}")
            return [0.0] * embedding_config.VECTOR_DIMENSION

    async def create_embedding(self, db: Session, json_data: Dict[str, Any]):
        """
        为JSON数据创建嵌入并存储到数据库
        
        Args:
            db: 数据库会话
            json_data: 要嵌入的JSON数据
            
        Returns:
            创建的嵌入记录
        """
        try:
            # 标准化JSON数据
            normalized_data = normalize_json(json_data)
            
            # 创建嵌入向量
            embedding_vector = await self.create_embedding_vector(normalized_data)
            
            # 记录当前时间
            current_time = time.time()
            
            # 创建嵌入记录
            embedding = JsonEmbedding(
                json_data=json_data,
                embedding_vector=embedding_vector,
                model_name=self.model_name,
                created_at=current_time,
                updated_at=current_time
            )
            
            # 保存到数据库
            db.add(embedding)
            db.commit()
            db.refresh(embedding)
            
            return embedding
        except Exception as e:
            logger.error(f"创建嵌入时出错: {str(e)}")
            db.rollback()
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取嵌入模型信息
        
        Returns:
            模型信息字典
        """
        return {
            "model_name": self.model_name,
            "vector_dimension": embedding_config.VECTOR_DIMENSION,
            "using_lmstudio": embedding_config.USE_LMSTUDIO,
            "api_base_url": embedding_config.LMSTUDIO_API_BASE_URL if embedding_config.USE_LMSTUDIO else None
        } 