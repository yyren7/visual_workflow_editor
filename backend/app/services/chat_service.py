from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import logging
import uuid
import json
import os # 导入 os 模块

from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status

from database.models import Chat, Flow

# 导入 RAG 链/Agent (假设路径和名称)
# from backend.langchainchat.chains.rag_chain import RAGChain # 或者 Agent
# 导入 WorkflowChain (如果 chat service 需要直接触发工作流修改)
# from backend.langchainchat.chains.workflow_chain import WorkflowChain, WorkflowChainOutput
# 导入构建 RAG/Workflow 链所需的依赖 (这些通常在应用启动时初始化并注入)
# 移除 ToolExecutor 导入
# from backend.langchainchat.tools.executor import ToolExecutor
# from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
# from database.embedding.service import DatabaseEmbeddingService

# --- RAG 相关导入 ---
# from backend.langchainchat.chains.rag_chain import create_rag_chain, RAGInput
from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
from database.embedding.service import DatabaseEmbeddingService

# --- 新增：导入 DbChatMemory 和 BaseMessage --- 
from backend.langchainchat.memory.db_chat_memory import DbChatMemory
from langchain_core.messages import BaseMessage
# --- 新增：导入新的 Agent Runnable 创建函数 ---
from backend.langchainchat.agents.workflow_agent import create_workflow_agent_runnable
from langchain_core.runnables import Runnable # 导入 Runnable 类型提示
# 根据官方文档，直接从 langchain_deepseek 导入 ChatDeepSeek
from langchain_deepseek import ChatDeepSeek 
from langchain_google_genai import ChatGoogleGenerativeAI # 导入 Gemini
from langchain_core.language_models import BaseChatModel # 导入 BaseChatModel

logger = logging.getLogger(__name__)

class ChatService:
    """聊天服务，管理聊天记录并与 Agent 系统交互"""
    
    def __init__(self, db: Session):
        self.db = db
        # 将 Agent Executor 的初始化推迟到第一次需要时
        self._agent_executor = None # 初始化为 None
        # 移除 RAG Chain 相关属性
        # self.rag_chain = None 
    
    def _get_active_llm(self) -> BaseChatModel:
        """根据环境变量选择并实例化活动 LLM。"""
        provider = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower()
        logger.info(f"Active LLM provider selected: {provider}")

        if provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY environment variable not set.")
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            try:
                # 'gemini-pro' 是一个常见的模型，你可能需要根据可用性调整
                # convert_system_message_to_human=True 对于某些Agent类型使用Gemini时是必要的
                llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=api_key, convert_system_message_to_human=True)
                logger.info("Instantiated ChatGoogleGenerativeAI (Gemini).")
                return llm
            except Exception as e:
                logger.error(f"Failed to instantiate ChatGoogleGenerativeAI: {e}", exc_info=True)
                raise ValueError(f"Failed to instantiate Gemini LLM: {e}")

        elif provider == "deepseek":
            # ChatDeepSeek 构造函数通常会自动从环境变量读取 DEEPSEEK_API_KEY
            # 无需手动传递 api_key 参数，除非你想覆盖环境变量
            # api_key = os.getenv("DEEPSEEK_API_KEY")
            # if not api_key:
            #     logger.error("DEEPSEEK_API_KEY environment variable not set.")
            #     raise ValueError("DEEPSEEK_API_KEY environment variable not set.")
            try:
                llm = ChatDeepSeek(model="deepseek-chat") # 假设 'deepseek-chat' 是支持工具调用的模型
                logger.info("Instantiated ChatDeepSeek.")
                return llm
            except Exception as e:
                logger.error(f"Failed to instantiate ChatDeepSeek: {e}", exc_info=True)
                raise ValueError(f"Failed to instantiate DeepSeek LLM: {e}")
        else:
            logger.error(f"Unsupported LLM provider specified: {provider}")
            raise ValueError(f"Unsupported LLM provider: {provider}. Choose 'deepseek' or 'gemini'.")

    @property
    def workflow_agent_executor(self):
        """获取或创建 Agent Executor 实例。"""
        if self._agent_executor is None:
            logger.info("Workflow Agent Executor not initialized. Creating now...")
            try:
                # 1. 获取活动的 LLM 实例
                active_llm = self._get_active_llm()
                
                # 2. 移除 Tool Executor 初始化
                # if self._tool_executor is None:
                #      # 使用获取到的 active_llm 初始化 ToolExecutor
                #      self._tool_executor = ToolExecutor(llm_client=active_llm) 
                #      logger.info("Initialized ToolExecutor in workflow_agent_executor property.")

                # 3. 创建 Agent Runnable (不再需要传递 tool_executor)
                self._agent_executor = create_workflow_agent_runnable(llm=active_llm)
                logger.info("Successfully created Workflow Agent Executor.")
            except Exception as e:
                logger.error(f"Failed to create workflow agent executor: {e}", exc_info=True)
                # 根据需要决定是否抛出异常或返回 None
                raise RuntimeError(f"Could not create agent executor: {e}")
        return self._agent_executor

    def create_chat(self, flow_id: str, name: str = "新聊天", chat_data: Dict[str, Any] = None) -> Optional[Chat]:
        """
        创建新的聊天记录
        
        Args:
            flow_id: 关联的流程图ID
            name: 聊天名称
            chat_data: 聊天数据，默认为空字典
            
        Returns:
            创建的Chat对象，如果失败则返回None
        """
        try:
            # 验证流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.error(f"流程图 {flow_id} 不存在，无法创建聊天")
                return None
                
            # 创建聊天记录
            chat = Chat(
                id=str(uuid.uuid4()),
                flow_id=flow_id,
                name=name,
                chat_data=chat_data or { "messages": [] } # 确保有 messages
            )
            
            self.db.add(chat)
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"已为流程图 {flow_id} 创建聊天 {chat.id}")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建聊天失败: {str(e)}")
            return None
    
    def get_chat(self, chat_id: str) -> Optional[Chat]:
        """
        获取聊天记录
        
        Args:
            chat_id: 聊天ID
            
        Returns:
            Chat对象，如果不存在则返回None
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            return chat
        except Exception as e:
            logger.error(f"获取聊天 {chat_id} 失败: {str(e)}")
            return None
    
    def get_chats_for_flow(self, flow_id: str, skip: int = 0, limit: int = 100) -> List[Chat]:
        """
        获取流程图的所有聊天记录
        
        Args:
            flow_id: 流程图ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            Chat对象列表
        """
        try:
            chats = self.db.query(Chat)\
                .filter(Chat.flow_id == flow_id)\
                .order_by(desc(Chat.updated_at))\
                .offset(skip)\
                .limit(limit)\
                .all()
            
            return chats
        except Exception as e:
            logger.error(f"获取流程图 {flow_id} 的聊天记录失败: {str(e)}")
            return []
    
    def update_chat(self, chat_id: str, name: str = None, chat_data: Dict[str, Any] = None) -> Optional[Chat]:
        """
        更新聊天记录
        
        Args:
            chat_id: 聊天ID
            name: 新的聊天名称（可选）
            chat_data: 新的聊天数据（可选）
            
        Returns:
            更新后的Chat对象，如果失败则返回None
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"聊天 {chat_id} 不存在，无法更新")
                return None
                
            # 更新字段
            if name is not None:
                chat.name = name
                
            if chat_data is not None:
                # 安全更新 chat_data，保留其他可能存在的字段
                existing_data = chat.chat_data or {}
                existing_data.update(chat_data)
                chat.chat_data = existing_data
            
            # 更新时间戳
            chat.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"已更新聊天 {chat_id}")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新聊天 {chat_id} 失败: {str(e)}")
            return None
    
    def add_message_to_chat(self, chat_id: str, role: str, content: str) -> Optional[Chat]:
        """
        向聊天添加一条消息
        
        Args:
            chat_id: 聊天ID
            role: 消息发送者角色 (user/assistant/system)
            content: 消息内容
            
        Returns:
            更新后的Chat对象，如果失败则返回None
        """
        try:
            # 1. 查询聊天对象
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"聊天 {chat_id} 不存在，无法添加消息")
                return None
            
            # 2. 使用 MutableDict 安全地修改 chat_data
            from sqlalchemy.dialects.postgresql import JSONB
            from sqlalchemy.ext.mutable import MutableDict
            chat_data = MutableDict.as_mutable(chat.chat_data) if chat.chat_data else MutableDict()
            
            # 确保有messages数组
            if "messages" not in chat_data:
                chat_data["messages"] = []
            elif not isinstance(chat_data["messages"], list):
                 logger.warning(f"Chat {chat_id} messages is not a list, resetting.")
                 chat_data["messages"] = [] # 如果不是列表，重置
                 
            # 3. 准备新消息
            new_message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            # --- 添加详细日志 --- 
            logger.debug(f"ChatService: Preparing to add message to chat {chat_id}: role='{role}', content='{content[:100]}...'" ) 
                 
            # 4. 添加新消息到列表
            chat_data["messages"].append(new_message)
            
            # 5. 更新聊天对象的属性
            chat.chat_data = chat_data 
            chat.updated_at = datetime.utcnow()
            
            # 6. 提交到数据库
            self.db.add(chat) # 将更改添加到 session
            # --- 添加详细日志 --- 
            logger.info(f"ChatService: Attempting commit for chat {chat_id}...") 
            self.db.commit()  # <--- 提交事务
            logger.info(f"ChatService: Commit successful for chat {chat_id}.") # 修改日志
            logger.info(f"ChatService: Attempting refresh for chat {chat_id}...") # 添加日志
            self.db.refresh(chat) # 刷新对象状态
            logger.info(f"ChatService: Refresh successful for chat {chat_id}.") # 添加日志
            
            # 7. 记录成功日志 (在 commit 之后)
            logger.info(f"已向聊天 {chat_id} 添加一条 {role} 消息 (verified after commit/refresh)") # 修改日志文本
            return chat
            
        except Exception as e:
            # --- 添加更详细的回滚日志 --- 
            logger.error(f"向聊天 {chat_id} 添加消息失败: {str(e)}", exc_info=True)
            logger.info(f"ChatService: Attempting rollback for chat {chat_id} due to error in add_message...") 
            try:
                self.db.rollback()
                logger.info(f"ChatService: Rollback successful for chat {chat_id} in add_message.") 
            except Exception as rb_err:
                logger.error(f"ChatService: Rollback failed for chat {chat_id} in add_message: {rb_err}", exc_info=True) 
            return None

    def delete_chat(self, chat_id: str) -> bool:
        """
        删除聊天记录及其关联数据

        Args:
            chat_id: 聊天ID
            
        Returns:
            是否成功删除
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.warning(f"聊天 {chat_id} 不存在，无需删除")
                return False
                
            self.db.delete(chat)
            self.db.commit()
            
            logger.info(f"已删除聊天 {chat_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除聊天 {chat_id} 失败: {str(e)}")
            return False 