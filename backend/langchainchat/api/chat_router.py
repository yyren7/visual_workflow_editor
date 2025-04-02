from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from database.connection import get_db
from app.utils import optional_current_user, get_current_user
from app.schemas import User

# 聊天服务将在后续实现
from langchainchat.services.chat_service import ChatService

router = APIRouter(
    prefix="/langchainchat",
    tags=["langchainchat"],
    responses={404: {"description": "Not found"}}
)

# 请求模型
class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str = Field(..., description="用户消息内容")
    conversation_id: Optional[str] = Field(default=None, description="会话ID，如果不提供则创建新会话")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="附加元数据")
    language: Optional[str] = Field(default="en", description="期望的响应语言 (en, zh, ja)")

# 响应模型
class ChatResponse(BaseModel):
    """聊天响应模型"""
    conversation_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="AI响应消息")
    created_at: str = Field(..., description="创建时间")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="附加元数据")
    context_used: Optional[str] = Field(default=None, description="使用的上下文信息")

# 聊天服务实例
chat_service = ChatService()

@router.post("/message", response_model=ChatResponse)
async def process_chat_message(
    request: ChatRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(optional_current_user)
) -> ChatResponse:
    """
    处理聊天消息
    
    Args:
        request: 包含用户消息的请求
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        AI响应
    """
    try:
        # 获取用户ID（如果有）
        user_id = current_user.id if current_user else None
        
        # 处理用户消息
        result = await chat_service.process_message(
            user_input=request.message,
            conversation_id=request.conversation_id,
            user_id=user_id,
            metadata=request.metadata,
            db=db,
            language=request.language  # 传递语言参数
        )
        
        # 返回结果
        return ChatResponse(
            conversation_id=result["conversation_id"],
            message=result["message"],
            created_at=result["created_at"],
            metadata=result.get("metadata"),
            context_used=result.get("context_used")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理消息时出错: {str(e)}")

@router.get("/conversations", response_model=List[Dict[str, Any]])
async def list_conversations(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(optional_current_user)
) -> List[Dict[str, Any]]:
    """
    获取用户的会话列表
    
    Args:
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        会话列表
    """
    try:
        # 获取用户ID（如果有）
        user_id = current_user.id if current_user else None
        
        # 获取会话列表
        conversations = chat_service.list_conversations(user_id)
        
        return conversations
    except Exception as e:
        if isinstance(e, HTTPException) and e.status_code == 401:
            # 如果是认证错误，返回空列表而不是错误
            return []
        raise HTTPException(status_code=500, detail=f"获取会话列表时出错: {str(e)}")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    删除指定会话
    
    Args:
        conversation_id: 要删除的会话ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        # 获取用户ID（如果有）
        user_id = current_user.id if current_user else None
        
        # 删除会话
        success = chat_service.delete_conversation(conversation_id, user_id)
        
        if success:
            return {"success": True, "message": f"已删除会话: {conversation_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"未找到会话: {conversation_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话时出错: {str(e)}") 