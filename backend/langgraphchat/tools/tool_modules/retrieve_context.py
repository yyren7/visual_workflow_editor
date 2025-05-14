from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
import asyncio
from database.connection import get_db_context
from backend.langgraphchat.utils.logging import logger
from database.embedding.service import DatabaseEmbeddingService # Specific import
from backend.langgraphchat.retrievers.embedding_retriever import EmbeddingRetriever # Specific import

def retrieve_context_func(query: str) -> Dict[str, Any]:
    """Searches the knowledge base for context relevant to the user's query."""
    logger.info(f"检索上下文: 查询='{query[:50]}...'") 
    try:
        with get_db_context() as db:
            embedding_service = DatabaseEmbeddingService() 
            retriever = EmbeddingRetriever(db_session=db, embedding_service=embedding_service)
            
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            documents = loop.run_until_complete(retriever._aget_relevant_documents(query, run_manager=None))

            if not documents:
                return {"success": True, "message": "未找到相关信息。", "retrieved_context": "未找到相关信息。"}

            formatted_docs = "\n\n---\n\n".join([
                f"来源: {doc.metadata.get('source', '未知')}\n内容: {doc.page_content}" 
                for doc in documents
            ])
            logger.info(f"成功检索到 {len(documents)} 个文档。")
            return {"success": True, "message": f"成功检索到 {len(documents)} 条相关信息。", "retrieved_context": formatted_docs}

    except Exception as e:
        logger.error(f"检索上下文时出错: {e}", exc_info=True)
        return {"success": False, "message": f"检索信息时出错: {e}", "retrieved_context": "检索信息时出错。"}

class RetrieveContextSchema(BaseModel):
    query: str = Field(description="The user query to search for relevant context.")

retrieve_context_tool = StructuredTool.from_function(
    func=retrieve_context_func,
    name="retrieve_context",
    description="Searches the knowledge base for context relevant to the user's query. Use this before answering questions that require external knowledge.",
    args_schema=RetrieveContextSchema
) 