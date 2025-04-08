from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database.database import get_db
from langchainchat.services.unified_chat_service import UnifiedChatService
from database.models import Chat
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/chats", tags=["chats"])

class ChatCreate(BaseModel):
    flow_id: int
    title: Optional[str] = None

class MessageCreate(BaseModel):
    content: str
    role: str = "user"

class ChatResponse(BaseModel):
    id: int
    flow_id: int
    user_id: int
    title: str
    chat_data: dict
    created_at: datetime
    updated_at: datetime
    metadata: dict

    class Config:
        orm_mode = True

@router.post("", response_model=ChatResponse)
def create_chat(chat_data: ChatCreate, db: Session = Depends(get_db)):
    """创建新的聊天会话"""
    service = UnifiedChatService(db)
    try:
        chat = service.create_chat(
            flow_id=chat_data.flow_id,
            user_id=1,  # TODO: 从认证中获取用户ID
            title=chat_data.title
        )
        return chat
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    """获取特定聊天记录"""
    service = UnifiedChatService(db)
    chat = service.get_chat(chat_id, 1)  # TODO: 从认证中获取用户ID
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@router.get("/flow/{flow_id}", response_model=List[ChatResponse])
def get_flow_chats(
    flow_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取流程图相关的所有聊天记录"""
    service = UnifiedChatService(db)
    return service.get_flow_chats(flow_id, 1, skip, limit)  # TODO: 从认证中获取用户ID

@router.post("/{chat_id}/messages", response_model=ChatResponse)
def add_message(
    chat_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """添加消息到聊天记录"""
    service = UnifiedChatService(db)
    try:
        chat = service.add_message(
            chat_id=chat_id,
            user_id=1,  # TODO: 从认证中获取用户ID
            content=message.content,
            role=message.role
        )
        return chat
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """删除聊天记录"""
    service = UnifiedChatService(db)
    if not service.delete_chat(chat_id, 1):  # TODO: 从认证中获取用户ID
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"message": "Chat deleted successfully"} 