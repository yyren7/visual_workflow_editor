from typing import List, Any, Dict
import logging

from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from sqlalchemy.orm import Session

# 导入新的 DatabaseEmbeddingService
from database.embedding.service import DatabaseEmbeddingService

logger = logging.getLogger(__name__)

class EmbeddingRetriever(BaseRetriever):
    """
    使用数据库嵌入服务进行相似性搜索的检索器。
    """
    db_session: Session
    embedding_service: DatabaseEmbeddingService
    search_k: int = 3
    search_threshold: float = 0.5

    # 实现异步方法 _aget_relevant_documents
    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        根据查询文本异步检索相关文档。
        
        Args:
            query: 查询字符串。
            run_manager: LangChain 回调管理器。
            
        Returns:
            相关文档列表。
        """
        logger.info(f"Retriever received async query: {query[:50]}...")
        try:
            # 调用异步的 similarity_search 方法
            similar_docs_data = await self.embedding_service.similarity_search(
                db=self.db_session,
                query=query,
                k=self.search_k,
                threshold=self.search_threshold
            )
            
            # 将返回的数据转换为 LangChain Document 对象
            documents = []
            for doc_data in similar_docs_data:
                metadata = doc_data.get('metadata', {})
                score = metadata.pop('score', None) 
                documents.append(Document(
                    page_content=doc_data.get('text', ''),
                    metadata=metadata
                ))
            
            logger.info(f"Retrieved {len(documents)} documents asynchronously.")
            return documents

        except Exception as e:
            logger.error(f"Error during async retrieval: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    # 同步方法可以保留，但通常会调用异步方法（需要事件循环管理）
    # 或者如果不需要同步接口，可以移除。
    # 为了简单起见，暂时不实现同步调用异步的逻辑。
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """同步接口（占位符/未完全实现）。"""
        logger.warning("Synchronous _get_relevant_documents called, but core logic is async. Returning empty list.")
        # 在实际应用中，这里需要运行异步方法，例如:
        # import asyncio
        # try:
        #     loop = asyncio.get_event_loop()
        # except RuntimeError:
        #     loop = asyncio.new_event_loop()
        #     asyncio.set_event_loop(loop)
        # return loop.run_until_complete(self._aget_relevant_documents(query, run_manager=run_manager))
        # 但这在某些环境（如 FastAPI 内部）可能不安全或低效
        return []

# 数据库会话管理注意事项同上。

# 注意：此类是同步实现 LangChain 的 BaseRetriever。
# 如果 DatabaseEmbeddingService.similarity_search 是异步的 (async def)，
# 则 EmbeddingRetriever 需要实现 aget_relevant_documents 而不是 _get_relevant_documents
# 或者在同步方法中使用 asyncio.run() 或类似方式调用异步方法。
# 这里假设可以在同步方法中调用异步方法（可能需要调整事件循环管理）。

# 还需要考虑 db_session 的传递和管理。
# 通常，db_session 不会直接存储在 Retriever 实例中，
# 而是通过调用时的上下文或其他依赖注入方式提供。 