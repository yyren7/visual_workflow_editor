"""
嵌入向量服务
提供嵌入向量的创建和管理功能
"""

import time
import logging
from typing import Any, Dict, List
from sqlalchemy.orm import Session
import json
import uuid

# 导入工具和配置
from .utils import normalize_json, calculate_similarity
from .config import embedding_config
# from .embedding_result import EmbeddingResult # Removed unused import
from .lmstudio_client import LMStudioClient
# Removed import causing circular dependency
# from backend.langchainchat.embeddings.semantic_search import search_by_vector

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
        # Moved import inside method to break circular dependency
        from database.models import JsonEmbedding
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
                meta_data=json_data.get('metadata'),
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

class DatabaseEmbeddingService:
    """
    负责文本嵌入生成和向量相似性搜索
    与底层的 Embedding 模型和向量存储交互
    """
    
    def __init__(self):
        """
        初始化服务，获取 EmbeddingService 实例
        """
        logger.info("Initializing DatabaseEmbeddingService...")
        # 获取 EmbeddingService 的单例实例用于创建向量
        self._embedding_creator = EmbeddingService.get_instance()
        logger.info("DatabaseEmbeddingService initialized.")

    async def embed_text(self, text: str) -> List[float]:
        """
        生成单个文本的嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量
        """
        logger.debug(f"Embedding text: {text[:50]}...")
        try:
            vector = await self._embedding_creator.create_embedding_vector(text)
            logger.debug(f"Text embedded successfully, vector dimension: {len(vector)}")
            return vector
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            # 返回零向量或根据策略抛出异常
            return [0.0] * embedding_config.VECTOR_DIMENSION

    async def embed_documents(self, documents: List[Dict[str, Any]]) -> List[List[float]]:
        """
        生成多个文档的嵌入向量
        
        Args:
            documents: 文档列表 (每个文档是包含 'text' 键的字典)
            
        Returns:
            嵌入向量列表
        """
        logger.debug(f"Embedding {len(documents)} documents...")
        embeddings = []
        for doc in documents:
            text_to_embed = doc.get("text")
            if isinstance(text_to_embed, dict): # Handle case where 'text' might be JSON itself
                text_to_embed = normalize_json(text_to_embed)
            elif not isinstance(text_to_embed, str):
                text_to_embed = str(text_to_embed) # Fallback to string conversion

            if text_to_embed:
                vector = await self.embed_text(text_to_embed)
                embeddings.append(vector)
            else:
                logger.warning("Document missing 'text' field or text is empty, creating zero vector.")
                embeddings.append([0.0] * embedding_config.VECTOR_DIMENSION)
        logger.debug(f"Finished embedding {len(documents)} documents.")
        return embeddings

    async def add_documents(self, db: Session, documents: List[Dict[str, Any]]):
        """
        将文档及其嵌入添加到数据库
        
        Args:
            db: 数据库会话
            documents: 文档列表 (包含文本和可能的元数据)
        """
        # Moved import inside method to break circular dependency
        from database.models import JsonEmbedding
        logger.info(f"Adding {len(documents)} documents to the database...")
        added_count = 0
        try:
            for doc in documents:
                json_data = doc.get("data") # Assuming data is under 'data' key
                if not json_data:
                    logger.warning(f"Document missing 'data' field, skipping: {doc.get('id', 'N/A')}")
                    continue

                # Prepare text for embedding (e.g., from specific fields or normalized JSON)
                text_to_embed = normalize_json(json_data) # Embed the normalized JSON data

                # Create embedding vector
                embedding_vector = await self.embed_text(text_to_embed)

                if not embedding_vector or all(v == 0 for v in embedding_vector):
                     logger.warning(f"Failed to create embedding for document {doc.get('id', 'N/A')}, skipping.")
                     continue

                # Record current time
                current_time = time.time()

                # Create JsonEmbedding object
                embedding_record = JsonEmbedding(
                    id=doc.get("id", uuid.uuid4()), # Use provided ID or generate new one
                    json_data=json_data,
                    embedding_vector=embedding_vector,
                    model_name=self._embedding_creator.model_name,
                    meta_data=doc.get('metadata'), # Use provided metadata
                    created_at=current_time,
                    updated_at=current_time
                )
                db.add(embedding_record)
                added_count += 1

            if added_count > 0:
                db.commit()
                logger.info(f"Successfully added {added_count} documents to the database.")
            else:
                 logger.info("No valid documents were added.")
            # Refresh might not be needed/possible in bulk async operations easily
            # Consider returning IDs or status

        except Exception as e:
            logger.error(f"Error adding documents to database: {e}")
            db.rollback()
            raise # Re-raise the exception after rollback

    async def similarity_search(self, db: Session, query: str, k: int = 3, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        根据查询文本在数据库中执行相似性搜索
        
        Args:
            db: 数据库会话
            query: 查询文本
            k: 返回的最相似结果数量
            threshold: 相似度阈值
            
        Returns:
            相似文档列表 (格式化后的结果)
        """
        # Moved import inside method to potentially break circular dependency if JsonEmbedding is needed here
        # Although it seems it's only needed for the query() call, let's keep it simple for now.
        from database.models import JsonEmbedding
        from backend.langchainchat.embeddings.utils import format_search_result # Use the existing formatter

        logger.info(f"Performing similarity search for: {query[:50]}... K={k}, Threshold={threshold}")
        try:
            # 1. 生成查询嵌入
            query_embedding = await self.embed_text(query)
            if not query_embedding or all(v == 0 for v in query_embedding):
                logger.error("Failed to generate query embedding for the search.")
                return []

            # 2. Core search logic moved here from semantic_search.py's search_by_vector
            logger.debug(f"Executing vector similarity search in database.")

            # 从数据库获取所有嵌入记录 (Consider optimization for large datasets)
            # TODO: Explore direct vector search capabilities of the DB (e.g., using pgvector operators) for efficiency
            # For now, fetch all and calculate in Python:
            db_embeddings = db.query(JsonEmbedding).all()

            # 计算相似度并排序
            results_with_scores = []
            for emb in db_embeddings:
                # Ensure embedding vector is valid
                if not emb.embedding_vector or all(v == 0 for v in emb.embedding_vector):
                    continue

                # Calculate cosine similarity
                similarity = calculate_similarity(query_embedding, emb.embedding_vector)

                # If above threshold, add to results
                if similarity >= threshold:
                    # Add score attribute dynamically for sorting/formatting
                    emb.score = similarity
                    results_with_scores.append((emb, similarity))

            # Sort by similarity score (descending) and take top K
            results_with_scores.sort(key=lambda x: x[1], reverse=True)
            top_results_objects = [item[0] for item in results_with_scores[:k]]

            logger.info(f"Database search found {len(top_results_objects)} potential matches above threshold.")

            # 3. Format the results using the utility from langchainchat.embeddings
            formatted_results = format_search_result(top_results_objects, with_score=True)

            logger.info(f"Formatted {len(formatted_results)} results for output.")
            return formatted_results

        except Exception as e:
            logger.error(f"Error during similarity search execution: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [] 