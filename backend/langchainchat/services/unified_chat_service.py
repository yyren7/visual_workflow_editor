from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Chat, Flow
from langchainchat.services.chat_service import ChatService as LangChainChatService
from langchainchat.adapters.db_memory_adapter import DatabaseMemoryAdapter
from langchainchat.memory.conversation_memory import EnhancedConversationMemory
from datetime import datetime
import uuid

class UnifiedChatService:
    """统一的聊天服务，整合标准聊天和LangChain聊天功能"""
    
    def __init__(self, db: Session):
        self.db = db
        self.langchain_service = LangChainChatService()
        self.memory_adapter = DatabaseMemoryAdapter()
        
    def create_chat(self, flow_id: int, user_id: int, title: str = None) -> Chat:
        """创建新的聊天会话"""
        
        # 验证流程图是否存在
        flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
        if not flow:
            raise ValueError("Flow not found")
            
        # 创建LangChain会话
        langchain_session_id = str(uuid.uuid4())
        memory = EnhancedConversationMemory(
            conversation_id=langchain_session_id,
            user_id=user_id
        )
        
        # 创建数据库记录
        chat = Chat(
            flow_id=flow_id,
            user_id=user_id,
            title=title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            chat_data={"messages": []},
            metadata={
                "langchain_session_id": langchain_session_id,
                "context_used": False
            }
        )
        
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        
        return chat
        
    def get_chat(self, chat_id: int, user_id: int) -> Optional[Chat]:
        """获取聊天记录"""
        chat = self.db.query(Chat).filter(
            Chat.id == chat_id,
            Chat.user_id == user_id
        ).first()
        
        if not chat:
            return None
            
        return chat
        
    def get_flow_chats(self, flow_id: int, user_id: int, skip: int = 0, limit: int = 10) -> List[Chat]:
        """获取流程图相关的所有聊天记录"""
        return self.db.query(Chat).filter(
            Chat.flow_id == flow_id,
            Chat.user_id == user_id
        ).order_by(Chat.created_at.desc()).offset(skip).limit(limit).all()
        
    def add_message(self, chat_id: int, user_id: int, content: str, role: str = "user") -> Chat:
        """添加消息到聊天记录"""
        
        # 获取聊天记录
        chat = self.get_chat(chat_id, user_id)
        if not chat:
            raise ValueError("Chat not found")
            
        # 创建消息
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        # 更新数据库记录
        if not chat.chat_data:
            chat.chat_data = {"messages": []}
        chat.chat_data["messages"].append(message)
        chat.updated_at = datetime.now()
        
        # 同步到LangChain记忆
        memory = EnhancedConversationMemory(
            conversation_id=chat.metadata["langchain_session_id"],
            user_id=user_id
        )
        self.memory_adapter.sync_from_database(chat, memory)
        
        # 如果是用户消息，使用LangChain处理
        if role == "user":
            response = self.langchain_service.process_message(content, memory)
            
            # 添加AI响应
            ai_message = {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            }
            chat.chat_data["messages"].append(ai_message)
            
            # 同步更新后的记忆到数据库
            self.memory_adapter.sync_to_database(memory, self.db)
            
        self.db.commit()
        return chat
        
    def delete_chat(self, chat_id: int, user_id: int) -> bool:
        """删除聊天记录"""
        chat = self.get_chat(chat_id, user_id)
        if not chat:
            return False
            
        self.db.delete(chat)
        self.db.commit()
        return True 