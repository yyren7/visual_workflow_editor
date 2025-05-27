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

from backend.langgraphchat.retrievers.embedding_retriever import EmbeddingRetriever
from database.embedding.service import DatabaseEmbeddingService

# --- 导入 DbChatMemory 和 BaseMessage --- 
from backend.langgraphchat.memory.db_chat_memory import DbChatMemory
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable # 导入 Runnable 类型提示
# 根据官方文档，直接从 langchain_deepseek 导入 ChatDeepSeek
from langchain_deepseek import ChatDeepSeek 
from langchain_google_genai import ChatGoogleGenerativeAI # 导入 Gemini
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph

# --- 从工作流图模块导入编译函数 ---
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
# --- 工具 ---
from backend.langgraphchat.tools import flow_tools

# --- 新增导入 ---
from sqlalchemy.dialects.postgresql import JSONB # 如果您确实在用PostgreSQL并希望用JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.attributes import flag_modified
# --- 结束新增导入 ---

logger = logging.getLogger(__name__)

class ChatService:
    """聊天服务，管理聊天记录并与 Agent 系统交互"""
    
    def __init__(self, db: Session):
        self.db = db
        self._compiled_workflow_graph = None # 用于缓存编译后的 LangGraph
    
    def _get_active_llm(self) -> BaseChatModel:
        """根据环境变量选择并实例化活动 LLM。"""
        provider = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower()
        provider = "gemini"
        logger.info(f"Active LLM provider selected: {provider}")

        if provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY environment variable not set.")
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            try:
                # convert_system_message_to_human=True 对于某些Agent类型使用Gemini时是必要的
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20", google_api_key=api_key, convert_system_message_to_human=True)
                logger.info("Instantiated ChatGoogleGenerativeAI (Gemini).")
                return llm
            except Exception as e:
                logger.error(f"Failed to instantiate ChatGoogleGenerativeAI: {e}", exc_info=True)
                raise ValueError(f"Failed to instantiate Gemini LLM: {e}")

        elif provider == "deepseek":
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
    def compiled_workflow_graph(self) -> StateGraph:
        """获取或创建编译后的 LangGraph 工作流实例。"""
        if self._compiled_workflow_graph is None:
            logger.info("Compiled LangGraph not initialized. Creating now...")
            try:
                active_llm = self._get_active_llm()
                # flow_tools 是直接从 backend.langgraphchat.tools 导入的列表
                self._compiled_workflow_graph = compile_workflow_graph(llm=active_llm, custom_tools=flow_tools)
                logger.info("Successfully compiled LangGraph workflow.")
            except Exception as e:
                logger.error(f"Failed to compile LangGraph workflow: {e}", exc_info=True)
                raise RuntimeError(f"Could not compile LangGraph workflow: {e}")
        return self._compiled_workflow_graph

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
        logger.info(f"ChatService: Attempting to add message to chat_id: {chat_id}, role: {role}") # 修改日志前缀以清晰
        try:
            # 1. 查询聊天对象
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"ChatService: Chat {chat_id} not found. Cannot add message.")
                return None
            
            logger.debug(f"ChatService: Chat {chat_id} found. Current chat_data before modification: {chat.chat_data}") # 记录修改前的数据

            # 2. 使用 MutableDict 安全地修改 chat_data
            # from sqlalchemy.dialects.postgresql import JSONB # 已移到顶部
            # from sqlalchemy.ext.mutable import MutableDict # 已移到顶部
            chat_data_variable = MutableDict.as_mutable(chat.chat_data) if chat.chat_data else MutableDict()
            
            # 确保有messages数组
            if "messages" not in chat_data_variable:
                chat_data_variable["messages"] = []
            elif not isinstance(chat_data_variable["messages"], list):
                 logger.warning(f"ChatService: Chat {chat_id} messages was not a list, resetting to empty list.")
                 chat_data_variable["messages"] = [] # 如果不是列表，重置
                 
            # 3. 准备新消息
            new_message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat() # 使用 UTC 时间
            }
            logger.debug(f"ChatService: Prepared new message for chat {chat_id}: {{'role': '{role}', 'content': '{content[:50]}...', 'timestamp': '{new_message['timestamp']}'}}") # 记录准备好的消息（内容截断）
                 
            # 4. 添加新消息到列表
            chat_data_variable["messages"].append(new_message)
            logger.debug(f"ChatService: Appended new message to chat_data_variable for chat {chat_id}. New messages count: {len(chat_data_variable['messages'])}")
            
            # 5. 更新聊天对象的属性
            chat.chat_data = chat_data_variable 
            # ---- 显式标记 chat_data 已修改 ----
            flag_modified(chat, "chat_data") # <--- 添加此行
            logger.debug(f"ChatService: chat.chat_data assigned and explicitly flagged as modified for chat {chat_id}.")
            
            chat.updated_at = datetime.utcnow()
            
            # 6. 提交到数据库
            self.db.add(chat) # 通常在对象已从会话加载后，修改会自动跟踪，但 add() 无害
            logger.info(f"ChatService: Attempting commit for chat {chat_id} after adding/modifying message...")
            self.db.commit()
            logger.info(f"ChatService: Commit successful for chat {chat_id}.")
            
            # --- 调试：提交后立即用同一会话查询并记录 ---
            # 首先刷新当前 chat 实例以获取数据库的最新状态
            logger.info(f"ChatService: Attempting to refresh chat object {chat_id} in current session...")
            self.db.refresh(chat)
            logger.info(f"ChatService: Chat {chat_id} refreshed. Verifying data in current session: chat.chat_data.messages count = {len(chat.chat_data.get('messages', []))}")
            if chat.chat_data.get('messages'):
                # 记录最后一条消息的部分内容以供验证
                last_msg_preview = chat.chat_data['messages'][-1].get('content', '')[:50]
                last_msg_role = chat.chat_data['messages'][-1].get('role')
                logger.debug(f"ChatService: Last message in current session after refresh for {chat_id}: {{'role': '{last_msg_role}', 'content': '{last_msg_preview}...'}}")
            # --- 结束调试 ---

            logger.info(f"ChatService: Successfully added and committed '{role}' message to chat {chat_id}.") # 修改日志
            return chat
            
        except Exception as e:
            logger.error(f"ChatService: Error adding message to chat {chat_id}: {e}", exc_info=True)
            try:
                logger.info(f"ChatService: Attempting rollback for chat {chat_id} due to error in add_message_to_chat.") # 增强日志
                self.db.rollback()
                logger.info(f"ChatService: Rollback successful for chat {chat_id} in add_message_to_chat.") # 增强日志
            except Exception as rb_err:
                logger.error(f"ChatService: Rollback FAILED for chat {chat_id} in add_message_to_chat: {rb_err}", exc_info=True) # 增强日志
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

    def edit_user_message_and_truncate(self, chat_id: str, message_timestamp: str, new_content: str) -> Optional[Chat]:
        """
        编辑用户消息，删除此消息之后的所有消息，并以新内容重新生成用户消息。

        Args:
            chat_id: 聊天ID
            message_timestamp: 要编辑的用户消息的时间戳
            new_content: 用户消息的新内容

        Returns:
            更新后的Chat对象，如果失败则返回None
        """
        logger.info(f"ChatService: Attempting to edit message in chat_id: {chat_id} at timestamp: {message_timestamp}")
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"ChatService: Chat {chat_id} not found. Cannot edit message.")
                return None

            chat_data_variable = MutableDict.as_mutable(chat.chat_data) if chat.chat_data else MutableDict()
            if "messages" not in chat_data_variable or not isinstance(chat_data_variable["messages"], list):
                logger.error(f"ChatService: Chat {chat_id} has no messages or messages are not a list. Cannot edit.")
                return None

            messages: List[Dict[str, Any]] = chat_data_variable["messages"]
            target_message_index = -1
            for i, msg in enumerate(messages):
                if msg.get("timestamp") == message_timestamp and msg.get("role") == "user":
                    target_message_index = i
                    break
            
            if target_message_index == -1:
                logger.error(f"ChatService: User message with timestamp {message_timestamp} not found in chat {chat_id}.")
                return None

            logger.debug(f"ChatService: Found user message at index {target_message_index} for editing.")

            # 删除目标消息及之后的所有消息
            truncated_messages = messages[:target_message_index]
            logger.debug(f"ChatService: Messages truncated. Kept {len(truncated_messages)} messages.")

            # 添加编辑后的用户消息
            edited_message = {
                "role": "user",
                "content": new_content,
                "timestamp": datetime.utcnow().isoformat() # 使用新的时间戳
            }
            truncated_messages.append(edited_message)
            logger.debug(f"ChatService: Added edited user message. Total messages now: {len(truncated_messages)}")
            
            chat_data_variable["messages"] = truncated_messages
            chat.chat_data = chat_data_variable
            flag_modified(chat, "chat_data")
            chat.updated_at = datetime.utcnow()

            self.db.add(chat)
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"ChatService: Successfully edited message in chat {chat_id} at timestamp {message_timestamp}.")
            return chat

        except Exception as e:
            logger.error(f"ChatService: Error editing message in chat {chat_id}: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception as rb_err:
                logger.error(f"ChatService: Rollback FAILED while editing message in chat {chat_id}: {rb_err}", exc_info=True)
            return None 