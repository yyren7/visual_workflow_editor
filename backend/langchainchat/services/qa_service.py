"""
LLM问答服务
提供基于LLM的问答功能
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from openai import OpenAI

# 导入必要的配置和工具
from backend.config import LANGCHAIN_CONFIG, AI_CONFIG
from backend.langchainchat.embeddings.semantic_search import search_by_text
from backend.langchainchat.embeddings.node_search import search_nodes

# 设置logger
logger = logging.getLogger(__name__)

# 全局客户端缓存
_llm_client = None

class QAService:
    """LLM问答服务"""
    
    def __init__(self):
        """初始化问答服务"""
        self.init_llm_client()
    
    def init_llm_client(self):
        """初始化LLM客户端"""
        global _llm_client
        
        # 如果已初始化，直接返回
        if _llm_client is not None:
            return
            
        # 检查是否使用DeepSeek
        if AI_CONFIG['USE_DEEPSEEK']:
            logger.info("初始化DeepSeek客户端")
            _llm_client = OpenAI(
                api_key=AI_CONFIG['DEEPSEEK_API_KEY'], 
                base_url=AI_CONFIG['DEEPSEEK_BASE_URL']
            )
        else:
            # 使用OpenAI
            logger.info("初始化OpenAI客户端")
            _llm_client = OpenAI(
                api_key=AI_CONFIG.get('OPENAI_API_KEY', '')
            )
    
    async def query_with_context(
        self,
        db: Session,
        question: str,
        context_limit: int = 3,
        model: Optional[str] = None
    ) -> str:
        """
        使用上下文回答问题
        
        Args:
            db: 数据库会话
            question: 用户问题
            context_limit: 上下文数量限制
            model: 模型名称
            
        Returns:
            LLM回答
        """
        try:
            logger.info(f"处理问题: {question}")
            
            # 获取问题相关的语义搜索结果
            semantic_results = await search_by_text(db, question, limit=context_limit)
            
            # 获取问题相关的节点搜索结果
            node_results = await search_nodes(question, limit=context_limit)
            
            # 如果都没有找到相关内容，返回默认回答
            if not semantic_results and not node_results:
                return "我找不到相关的信息来回答您的问题。您可以尝试更具体的描述。"
            
            # 构建上下文
            context_items = []
            
            # 添加语义搜索结果到上下文
            if semantic_results:
                context_items.append("相关数据库内容:")
                for i, item in enumerate(semantic_results, 1):
                    context_text = f"{i}. " + str(item.get('data', {}))
                    context_items.append(context_text)
            
            # 添加节点搜索结果到上下文
            if node_results:
                context_items.append("\n相关节点:")
                for i, item in enumerate(node_results, 1):
                    node_data = item.get('data', {})
                    node_id = node_data.get('id', 'unknown')
                    node_type = node_data.get('type', 'unknown')
                    fields = node_data.get('fields', {})
                    
                    context_text = f"{i}. 节点ID: {node_id}, 类型: {node_type}"
                    if fields:
                        context_text += ", 字段: " + str(fields)
                    
                    context_items.append(context_text)
            
            # 合并上下文
            context = "\n".join(context_items)
            
            # 使用LLM回答问题
            return await self._query_llm(question, context, model)
        except Exception as e:
            logger.error(f"问答处理失败: {str(e)}")
            return f"处理您的问题时发生错误: {str(e)}"
    
    async def _query_llm(
        self,
        question: str,
        context: str = "",
        model: Optional[str] = None
    ) -> str:
        """
        调用LLM回答问题
        
        Args:
            question: 用户问题
            context: 上下文内容
            model: 模型名称
            
        Returns:
            LLM回答
        """
        try:
            # 确保客户端已初始化
            self.init_llm_client()
            
            # 使用全局客户端
            client = _llm_client
            
            # 确定使用的模型
            model_name = model or LANGCHAIN_CONFIG['CHAT_MODEL_NAME']
            
            # 构建提示
            system_message = "你是一个有帮助的AI助手。"
            
            prompt = f"请根据以下提供的上下文回答问题。如果上下文中没有相关信息，请坦诚说不知道。\n\n"
            prompt += f"上下文:\n{context}\n\n"
            prompt += f"问题: {question}"
            
            # 调用LLM
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            
            # 提取回答
            answer = response.choices[0].message.content
            
            logger.info(f"已生成回答，长度: {len(answer)}")
            
            return answer
        except Exception as e:
            logger.error(f"调用LLM失败: {str(e)}")
            return f"无法获取回答: {str(e)}"

# 创建单例实例
_qa_service_instance = None

def get_qa_service() -> QAService:
    """
    获取QA服务实例
    
    Returns:
        QAService实例
    """
    global _qa_service_instance
    if _qa_service_instance is None:
        _qa_service_instance = QAService()
    return _qa_service_instance 