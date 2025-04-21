from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Chat
from langchain_core.chat_history import BaseChatMessageHistory
from backend.langchainchat.memory.conversation_memory import EnhancedConversationMemory
from datetime import datetime
from langchain_core.messages import (
    AIMessage, 
    BaseMessage, 
)

class DatabaseMemoryAdapter:
    """数据库与LangChain记忆组件的适配器"""
    
    @staticmethod
    def sync_to_database(memory: EnhancedConversationMemory, db: Session) -> bool:
        """将LangChain记忆同步到数据库"""
        
        # 获取会话ID和用户ID
        conversation_id = memory.conversation_id
        user_id = memory.user_id
        
        # 查找对应的聊天记录
        chat = db.query(Chat).filter(Chat.metadata.contains({"langchain_session_id": conversation_id})).first()
        if not chat:
            return False
            
        # 转换消息格式
        messages = []
        for msg in memory.chat_memory.messages:
            message = {
                "role": "user" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                "content": msg.content,
                "timestamp": datetime.now().isoformat()
            }
            messages.append(message)
            
        # 更新数据库记录
        chat.chat_data = {"messages": messages}
        chat.updated_at = datetime.now()
        db.commit()
        
        return True
        
    @staticmethod
    def sync_from_database(chat: Chat, memory: EnhancedConversationMemory) -> bool:
        """从数据库同步到LangChain记忆"""
        
        # 清除现有记忆
        memory.clear()
        
        # 如果没有消息，直接返回
        if not chat.chat_data or "messages" not in chat.chat_data:
            return True
            
        # 添加消息到记忆
        for msg in chat.chat_data["messages"]:
            if msg["role"] == "user":
                memory.chat_memory.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                memory.chat_memory.add_ai_message(msg["content"])
                
        # 保存记忆
        memory.save()
        
        return True 