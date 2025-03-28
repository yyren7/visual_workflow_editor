from typing import Dict, Any, List, Optional, Tuple
from langchain_core.memory import BaseMemory
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import (
    AIMessage, 
    BaseMessage, 
    HumanMessage,
    SystemMessage
)
import uuid
import os
import json
from datetime import datetime
from pathlib import Path

from langchainchat.config import settings
from langchainchat.utils.logging import logger

class EnhancedConversationMemory(ConversationBufferMemory):
    """
    增强的对话记忆组件，扩展了LangChain的ConversationBufferMemory
    
    添加了对话保存、加载和管理功能
    """
    
    conversation_id: str = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    max_token_limit: int = 2000
    
    def __init__(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_token_limit: Optional[int] = None,
        **kwargs
    ):
        """
        初始化增强对话记忆组件
        
        Args:
            conversation_id: 对话ID，如果不提供则自动生成
            user_id: 用户ID
            metadata: 关联的元数据
            max_token_limit: 最大令牌限制
            **kwargs: 传递给ConversationBufferMemory的参数
        """
        super().__init__(**kwargs)
        
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.user_id = user_id
        self.metadata = metadata or {}
        self.max_token_limit = max_token_limit or 2000
        
        # 添加创建时间戳到元数据
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.now().isoformat()
            
        logger.info(f"初始化增强对话记忆: ID={self.conversation_id}, 用户={self.user_id}")
    
    def add_system_message(self, content: str) -> None:
        """添加系统消息到对话历史"""
        system_message = SystemMessage(content=content)
        # 确保chat_memory已初始化
        if not hasattr(self, "chat_memory"):
            from langchain.memory import ChatMessageHistory
            self.chat_memory = ChatMessageHistory()
        # 使用add_message方法而不是append
        self.chat_memory.add_message(system_message)
        logger.debug(f"添加系统消息到对话 {self.conversation_id}: {content[:50]}...")
    
    def get_session_path(self) -> str:
        """获取会话存储路径"""
        if not settings.PERSIST_SESSIONS:
            return None
            
        # 创建会话目录
        sessions_dir = Path(settings.SESSIONS_DB_PATH)
        sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # 用户特定目录
        if self.user_id:
            user_dir = sessions_dir / self.user_id
            user_dir.mkdir(exist_ok=True)
            return str(user_dir / f"{self.conversation_id}.json")
        
        return str(sessions_dir / f"{self.conversation_id}.json")
    
    def save(self) -> bool:
        """
        保存对话历史到文件
        
        Returns:
            保存是否成功
        """
        if not settings.PERSIST_SESSIONS:
            logger.debug("会话持久化已禁用，跳过保存")
            return False
        
        try:
            # 获取存储路径
            session_path = self.get_session_path()
            if not session_path:
                return False
                
            # 准备保存数据
            chat_history = []
            for message in self.chat_memory.messages:
                message_dict = {
                    "type": message.__class__.__name__,
                    "content": message.content
                }
                # 添加其他属性（如果有）
                if hasattr(message, "additional_kwargs") and message.additional_kwargs:
                    message_dict["additional_kwargs"] = message.additional_kwargs
                    
                chat_history.append(message_dict)
                
            save_data = {
                "conversation_id": self.conversation_id,
                "user_id": self.user_id,
                "metadata": self.metadata,
                "max_token_limit": self.max_token_limit,
                "chat_history": chat_history,
                "saved_at": datetime.now().isoformat()
            }
            
            # 保存到文件
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"对话历史已保存: {session_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存对话历史失败: {str(e)}")
            return False
    
    @classmethod
    def load(cls, conversation_id: str, user_id: Optional[str] = None) -> Optional['EnhancedConversationMemory']:
        """
        从文件加载对话历史
        
        Args:
            conversation_id: 对话ID
            user_id: 用户ID
            
        Returns:
            加载的对话记忆实例，如果加载失败则返回None
        """
        if not settings.PERSIST_SESSIONS:
            logger.debug("会话持久化已禁用，跳过加载")
            return None
            
        try:
            # 构建会话路径
            sessions_dir = Path(settings.SESSIONS_DB_PATH)
            
            # 尝试在用户目录中查找
            session_path = None
            if user_id:
                user_path = sessions_dir / user_id / f"{conversation_id}.json"
                if user_path.exists():
                    session_path = user_path
            
            # 如果在用户目录中未找到，则尝试在根目录中查找
            if not session_path:
                root_path = sessions_dir / f"{conversation_id}.json"
                if root_path.exists():
                    session_path = root_path
            
            if not session_path or not session_path.exists():
                logger.warning(f"未找到对话历史文件: {conversation_id}")
                return None
                
            # 读取文件
            with open(session_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 创建实例
            memory = cls(
                conversation_id=data.get("conversation_id", conversation_id),
                user_id=data.get("user_id", user_id),
                metadata=data.get("metadata", {}),
                max_token_limit=data.get("max_token_limit", 2000),
                memory_key="chat_history",
                return_messages=True,
                output_key="output",
                input_key="input"
            )
            
            # 恢复对话历史
            for msg_data in data.get("chat_history", []):
                msg_type = msg_data.get("type")
                content = msg_data.get("content", "")
                additional_kwargs = msg_data.get("additional_kwargs", {})
                
                if msg_type == "HumanMessage":
                    message = HumanMessage(content=content, additional_kwargs=additional_kwargs)
                elif msg_type == "AIMessage":
                    message = AIMessage(content=content, additional_kwargs=additional_kwargs)
                elif msg_type == "SystemMessage":
                    message = SystemMessage(content=content, additional_kwargs=additional_kwargs)
                else:
                    logger.warning(f"未知的消息类型: {msg_type}")
                    continue
                    
                memory.chat_memory.add_message(message)
                
            logger.info(f"成功加载对话历史: {conversation_id}, 消息数量: {len(memory.chat_memory.messages)}")
            return memory
            
        except Exception as e:
            logger.error(f"加载对话历史失败: {str(e)}")
            return None
    
    @staticmethod
    def list_conversations(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有可用的对话
        
        Args:
            user_id: 如果提供，则仅列出特定用户的对话
            
        Returns:
            对话列表，每个对话包含ID、用户ID和元数据
        """
        if not settings.PERSIST_SESSIONS:
            logger.debug("会话持久化已禁用，跳过列表获取")
            return []
            
        try:
            sessions_dir = Path(settings.SESSIONS_DB_PATH)
            if not sessions_dir.exists():
                return []
                
            conversations = []
            
            # 如果提供了用户ID，则仅检查特定用户目录
            if user_id:
                user_dir = sessions_dir / user_id
                if user_dir.exists():
                    for file_path in user_dir.glob("*.json"):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                conversations.append({
                                    "conversation_id": data.get("conversation_id", file_path.stem),
                                    "user_id": data.get("user_id", user_id),
                                    "metadata": data.get("metadata", {}),
                                    "saved_at": data.get("saved_at", ""),
                                    "messages_count": len(data.get("chat_history", []))
                                })
                        except Exception as e:
                            logger.error(f"读取对话文件失败: {file_path}, 错误: {str(e)}")
            else:
                # 查找所有对话文件
                for file_path in sessions_dir.glob("**/*.json"):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            conversations.append({
                                "conversation_id": data.get("conversation_id", file_path.stem),
                                "user_id": data.get("user_id", ""),
                                "metadata": data.get("metadata", {}),
                                "saved_at": data.get("saved_at", ""),
                                "messages_count": len(data.get("chat_history", []))
                            })
                    except Exception as e:
                        logger.error(f"读取对话文件失败: {file_path}, 错误: {str(e)}")
            
            # 按保存时间排序
            conversations.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
            
            logger.info(f"列出对话历史: 总数={len(conversations)}")
            return conversations
            
        except Exception as e:
            logger.error(f"列出对话历史失败: {str(e)}")
            return []
            
    def clear(self) -> None:
        """清除对话历史"""
        super().clear()
        logger.info(f"清除对话历史: {self.conversation_id}")

def create_memory(
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    system_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    max_token_limit: Optional[int] = None,
    load_if_exists: bool = True
) -> EnhancedConversationMemory:
    """
    创建或加载对话记忆实例
    
    Args:
        conversation_id: 对话ID，如果不提供则自动生成
        user_id: 用户ID
        system_message: 初始系统消息
        metadata: 关联元数据
        max_token_limit: 最大令牌限制
        load_if_exists: 如果对话ID存在，是否加载现有对话
        
    Returns:
        对话记忆实例
    """
    # 如果提供了ID且设置了加载现有对话，则尝试加载
    if conversation_id and load_if_exists and settings.PERSIST_SESSIONS:
        existing_memory = EnhancedConversationMemory.load(conversation_id, user_id)
        if existing_memory:
            logger.info(f"加载现有对话: {conversation_id}")
            return existing_memory
    
    # 创建新的记忆实例
    memory = EnhancedConversationMemory(
        conversation_id=conversation_id,
        user_id=user_id,
        metadata=metadata or {},
        max_token_limit=max_token_limit or settings.DEFAULT_CONTEXT_WINDOW,
        memory_key="chat_history",
        return_messages=True,
        output_key="output",
        input_key="input"
    )
    
    # 添加系统消息（如果提供）
    if system_message:
        memory.add_system_message(system_message)
        
    logger.info(f"创建新对话: {memory.conversation_id}")
    return memory 