from typing import Dict, Any, List, Optional, Union
import asyncio
import json
from datetime import datetime
from sqlalchemy.orm import Session
from langchain.agents import initialize_agent, AgentType
from langchain.chains import ConversationChain, LLMChain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from langchainchat.config import settings
from langchainchat.utils.logging import logger
from langchainchat.models.llm import get_chat_model
from langchainchat.memory.conversation_memory import create_memory, EnhancedConversationMemory
from langchainchat.tools.flow_tools import get_flow_tools
from langchainchat.utils.context_collector import context_collector
from langchainchat.prompts.chat_prompts import (
    ENHANCED_CHAT_PROMPT_TEMPLATE,
    CHAT_PROMPT_TEMPLATE,
    CONTEXT_PROCESSING_TEMPLATE,
    TOOL_CALLING_TEMPLATE,
    ERROR_HANDLING_TEMPLATE
)

class ChatService:
    """
    LangChain聊天服务
    
    集成LangChain的各个组件实现聊天功能
    """
    
    def __init__(self):
        """初始化聊天服务"""
        logger.info("初始化聊天服务")
        
        # 创建基础聊天模型
        self.llm = get_chat_model()
        logger.info(f"创建聊天模型: {settings.CHAT_MODEL_NAME}")
        
        # 创建基础聊天链
        self.chat_chain = CHAT_PROMPT_TEMPLATE | self.llm | StrOutputParser()
        
        # 创建上下文增强聊天链
        self.enhanced_chat_chain = ENHANCED_CHAT_PROMPT_TEMPLATE | self.llm | StrOutputParser()
        
        # 创建上下文处理链
        self.context_processing_chain = CONTEXT_PROCESSING_TEMPLATE | self.llm | StrOutputParser()
        
        # 错误处理链
        self.error_handling_chain = ERROR_HANDLING_TEMPLATE | self.llm | StrOutputParser()
        
        # 存储会话缓存
        self._memory_cache = {}
        
        logger.info("聊天服务初始化完成")
    
    async def process_message(
        self,
        user_input: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None,
        use_tools: bool = True,
        use_context: bool = True
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            user_input: 用户输入消息
            conversation_id: 会话ID，如果不提供则创建新会话
            user_id: 用户ID
            metadata: 附加元数据
            db: 数据库会话
            use_tools: 是否使用工具
            use_context: 是否使用上下文
            
        Returns:
            处理结果
        """
        try:
            logger.info(f"处理聊天消息: 会话={conversation_id}, 使用上下文={use_context}, 使用工具={use_tools}")
            
            # 创建或获取记忆组件
            memory = await self._get_memory(conversation_id, user_id, metadata)
            conversation_id = memory.conversation_id
            
            # 是否为简短响应
            is_short_response = len(user_input.strip()) < 10
            context_text = None
            
            # 如果是简短响应且有上下文，使用上下文处理链
            if is_short_response and memory.chat_memory.messages and len(memory.chat_memory.messages) > 1:
                logger.info("检测到简短响应，使用上下文处理")
                
                # 从内存中收集上下文
                context_messages = memory.chat_memory.messages[-4:]  # 获取最近的4条消息
                context_text = "\n".join([f"{msg.__class__.__name__}: {msg.content}" for msg in context_messages])
                
                try:
                    # 使用上下文处理链处理简短响应
                    response = await self.context_processing_chain.ainvoke({
                        "context": context_text,
                        "input": user_input
                    })
                except Exception as e:
                    logger.error(f"上下文处理链执行失败: {str(e)}")
                    # 失败时回退到普通处理
                    response = await self._process_with_context(user_input, db) if use_context else await self._process_without_context(user_input)
            else:
                # 使用适当的处理方式
                if use_context:
                    response = await self._process_with_context(user_input, db)
                else:
                    response = await self._process_without_context(user_input)
            
            # 将用户消息和响应添加到记忆
            memory.chat_memory.add_user_message(user_input)
            memory.chat_memory.add_ai_message(response)
            
            # 保存记忆
            memory.save()
            
            # 创建结果
            result = {
                "conversation_id": conversation_id,
                "response": response,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # 如果使用了上下文，添加到结果中
            if context_text:
                result["context_used"] = context_text
                
            logger.info(f"成功处理消息: 会话={conversation_id}, 响应长度={len(response)}")
            return result
            
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            
            # 尝试处理错误
            try:
                error_response = await self.error_handling_chain.ainvoke({
                    "input": user_input[:100] + "..." if len(user_input) > 100 else user_input,
                    "error": str(e)
                })
            except:
                error_response = f"处理消息时出错: {str(e)}"
            
            return {
                "conversation_id": conversation_id or "error_session",
                "response": error_response,
                "created_at": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def _process_with_context(self, user_input: str, db: Session = None) -> str:
        """
        使用上下文处理用户输入
        
        Args:
            user_input: 用户输入
            db: 数据库会话
            
        Returns:
            处理结果
        """
        logger.info("使用上下文处理用户输入")
        
        # 收集上下文信息
        context = await context_collector.collect_all(db)
        
        # 使用增强聊天链
        response = await self.enhanced_chat_chain.ainvoke({
            "context": context,
            "input": user_input
        })
        
        return response
    
    async def _process_without_context(self, user_input: str) -> str:
        """
        不使用上下文处理用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            处理结果
        """
        logger.info("不使用上下文处理用户输入")
        
        # 使用基础聊天链
        response = await self.chat_chain.ainvoke({
            "input": user_input
        })
        
        return response
    
    async def _get_memory(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EnhancedConversationMemory:
        """
        获取会话记忆组件
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
            metadata: 附加元数据
            
        Returns:
            记忆组件
        """
        # 如果有会话ID且已缓存，直接返回
        if conversation_id and conversation_id in self._memory_cache:
            logger.debug(f"使用缓存的会话记忆: {conversation_id}")
            return self._memory_cache[conversation_id]
            
        # 创建系统消息
        system_message = """你是一个专业的流程图设计助手，帮助用户设计和创建工作流流程图。

作为流程图助手，你应该:
1. 提供专业、简洁的流程图设计建议
2. 帮助解释不同节点类型的用途
3. 提出合理的流程优化建议
4. 协助用户解决流程图设计中遇到的问题
5. 只回答与流程图和工作流相关的问题"""
        
        # 创建新的记忆组件
        memory = create_memory(
            conversation_id=conversation_id,
            user_id=user_id,
            system_message=system_message,
            metadata=metadata,
            max_token_limit=settings.DEFAULT_CONTEXT_WINDOW
        )
        
        # 缓存记忆组件
        self._memory_cache[memory.conversation_id] = memory
        
        return memory
    
    def list_conversations(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取会话列表
        
        Args:
            user_id: 用户ID，如果提供则只返回该用户的会话
            
        Returns:
            会话列表
        """
        return EnhancedConversationMemory.list_conversations(user_id)
    
    def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> bool:
        """
        删除会话
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
            
        Returns:
            是否成功删除
        """
        # 如果会话存在于缓存中，先清除
        if conversation_id in self._memory_cache:
            del self._memory_cache[conversation_id]
            
        # 构建会话路径
        import os
        from pathlib import Path
        
        sessions_dir = Path(settings.SESSIONS_DB_PATH)
        
        # 用户特定目录
        if user_id:
            file_path = sessions_dir / user_id / f"{conversation_id}.json"
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"删除会话: {conversation_id}, 用户: {user_id}")
                return True
                
        # 公共目录
        file_path = sessions_dir / f"{conversation_id}.json"
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"删除会话: {conversation_id}")
            return True
            
        logger.warning(f"未找到要删除的会话: {conversation_id}")
        return False 