from typing import Dict, Any, List
import logging
from sqlalchemy.orm import Session
from backend.app.services.prompt_service import BasePromptService
# 修改为延迟导入
# from backend.app.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

# 存储全局PromptEmbeddingService实例
_prompt_embedding_service_instance = None
# 存储全局EmbeddingService实例
_embedding_service_instance = None

class PromptEmbeddingService(BasePromptService):
    """
    Prompt嵌入搜索服务
    搜索相关上下文并添加到prompt中
    """
    
    def __init__(self, embedding_service=None):
        """
        初始化PromptEmbeddingService
        
        Args:
            embedding_service: 可选的EmbeddingService实例，如果不提供则获取单例实例
        """
        super().__init__()
        self.embedding_service = embedding_service
        
        # 上下文增强模板
        self.context_template = """
以下是与您的需求相关的背景信息:

{context}

基于上述背景信息，请处理以下需求:
{original_prompt}
"""
        # 延迟初始化embedding_service，只在首次使用时初始化
        if self.embedding_service is None:
            logger.debug("PromptEmbeddingService将在首次使用时初始化EmbeddingService")
            # 预初始化嵌入服务以加载缓存
            self._ensure_embedding_service()

    def _ensure_embedding_service(self):
        """确保embedding_service已初始化"""
        global _embedding_service_instance
        if self.embedding_service is None:
            # 如果全局实例存在，直接使用
            if _embedding_service_instance is not None:
                logger.debug("使用现有的全局EmbeddingService实例")
                self.embedding_service = _embedding_service_instance
            else:
                # 延迟导入，避免循环引用
                from embeddings.service import EmbeddingService
                logger.debug("初始化全局EmbeddingService实例")
                self.embedding_service = EmbeddingService.get_instance()
                _embedding_service_instance = self.embedding_service
                logger.info("EmbeddingService单例实例已初始化并缓存")

    @classmethod
    def get_instance(cls):
        """获取PromptEmbeddingService的单例实例"""
        global _prompt_embedding_service_instance
        if _prompt_embedding_service_instance is None:
            logger.info("创建PromptEmbeddingService单例实例")
            _prompt_embedding_service_instance = cls()
        return _prompt_embedding_service_instance
    
    async def enrich_with_context(self, input_prompt: str, db: Session, max_results: int = 3) -> str:
        """
        搜索相关上下文并添加到prompt
        
        Args:
            input_prompt: 原始prompt
            db: 数据库会话
            max_results: 最大结果数量
            
        Returns:
            增强后的prompt
        """
        try:
            # 确保embedding_service已初始化
            self._ensure_embedding_service()
            
            # 日志记录，但不实际查询嵌入
            logger.info(f"搜索与以下输入相关的上下文: {input_prompt[:50]}...")
            
            # 将输入转换为可搜索的查询格式
            query_json = {"query": input_prompt}
            
            # 搜索相关文档
            similar_docs = await self.embedding_service.find_similar(
                db, 
                query_json,
                threshold=0.5,  # 相似度阈值
                limit=max_results
            )
            
            # 如果没有找到相关文档，返回原始prompt
            if not similar_docs:
                logger.debug("没有找到相关上下文")
                return input_prompt
            
            # 提取并格式化上下文
            context_texts = []
            for doc in similar_docs:
                # 格式化JSON数据为字符串
                if hasattr(doc, 'json_data') and doc.json_data:
                    # 格式化节点信息，使其更可读
                    node_data = doc.json_data
                    node_text = f"节点: {node_data.get('id', 'unknown')}, 类型: {node_data.get('type', 'unknown')}"
                    
                    # 添加字段信息
                    fields = node_data.get("fields", {})
                    if fields:
                        field_info = ", ".join([f"{key}: {value}" for key, value in fields.items()])
                        node_text += f", 属性: {field_info}"
                        
                    context_texts.append(node_text)
            
            # 如果没有有效上下文，返回原始prompt
            if not context_texts:
                return input_prompt
                
            # 合并上下文文本
            context = "\n\n---\n\n".join(context_texts)
            
            # 使用模板增强prompt
            enhanced_prompt = self.process_template(
                self.context_template,
                {"context": context, "original_prompt": input_prompt}
            )
            
            logger.debug(f"增强后的prompt: {enhanced_prompt[:100]}...")
            return enhanced_prompt
        except Exception as e:
            logger.error(f"增强prompt时出错: {str(e)}")
            # 出错时返回原始prompt
            return input_prompt 