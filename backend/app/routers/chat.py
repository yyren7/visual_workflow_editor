from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
import logging

from backend.app import schemas
from database.connection import get_db
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from database.models import Flow

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chats",
    tags=["chats"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Chat)
async def create_chat(
    chat: schemas.ChatCreate, 
    request: Request,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    创建新的聊天记录，必须登录并且只能为自己的流程图创建聊天
    """
    print(f"成功进入 create_chat 函数: {request.method} {request.url.path}")
    logger.info(f"成功进入 create_chat 函数: {request.method} {request.url.path}")

    try:
        # 验证流程图存在且属于当前用户
        logger.info(f"验证 flow ownership: {chat.flow_id}")
        verified_flow = verify_flow_ownership(chat.flow_id, current_user, db)
        logger.info(f"Flow ownership 验证通过 for flow: {verified_flow.id}")

        # 创建聊天
        logger.info(f"调用 chat_service.create_chat")
        chat_service = ChatService(db)
        db_chat = chat_service.create_chat(
            flow_id=chat.flow_id,
            name=chat.name,
            chat_data=chat.chat_data
        )
        logger.info(f"chat_service.create_chat 返回: {db_chat}")

        if not db_chat:
            logger.error("chat_service.create_chat 未成功创建聊天，引发 400")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法创建聊天"
            )

        # --- Update Flow's last_interacted_chat_id ---
        if verified_flow: # Ensure we have the flow object
            try:
                verified_flow.last_interacted_chat_id = db_chat.id
                db.commit()
                logger.info(f"更新 Flow {verified_flow.id} 的 last_interacted_chat_id 为 {db_chat.id}")
            except Exception as update_err:
                logger.error(f"更新 Flow last_interacted_chat_id 失败 (Flow: {verified_flow.id}, Chat: {db_chat.id}): {update_err}", exc_info=True)
                db.rollback() # Rollback only the failed update
        else:
             logger.warning(f"无法更新 Flow 的 last_interacted_chat_id，因为在创建聊天后未能获取 Flow 对象 (Flow ID: {chat.flow_id})")
        # --- End Update ---

        logger.info(f"成功创建聊天，返回 chat 对象 ID: {db_chat.id}")
        return db_chat
    except HTTPException as http_exc:
        logger.error(f"处理 create_chat 时发生 HTTPException: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"处理 create_chat 时发生意外错误", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建聊天时发生内部错误: {str(e)}"
        )


@router.get("/{chat_id}", response_model=schemas.Chat)
async def get_chat(
    chat_id: str, 
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取聊天记录，必须登录并且只能访问自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verify_flow_ownership(chat.flow_id, current_user, db)
    
    return chat


@router.get("/flow/{flow_id}", response_model=List[schemas.Chat])
async def get_flow_chats(
    flow_id: str, 
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取流程图的所有聊天记录，必须登录并且只能访问自己流程图的聊天
    """
    # 验证流程图属于当前用户
    verify_flow_ownership(flow_id, current_user, db)
    
    # 获取聊天列表
    chat_service = ChatService(db)
    chats = chat_service.get_chats_for_flow(flow_id, skip, limit)
    
    return chats


@router.put("/{chat_id}", response_model=schemas.Chat)
async def update_chat(
    chat_id: str,
    chat_update: schemas.ChatUpdate,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    更新聊天记录，必须登录并且只能更新自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verify_flow_ownership(chat.flow_id, current_user, db)
    
    # 更新聊天
    updated_chat = chat_service.update_chat(
        chat_id=chat_id,
        name=chat_update.name,
        chat_data=chat_update.chat_data
    )
    
    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="更新聊天失败"
        )
    
    return updated_chat


@router.post("/{chat_id}/messages", response_model=schemas.Chat)
async def add_message(
    chat_id: str,
    message: schemas.ChatAddMessage,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    向聊天添加消息，必须登录并且只能操作自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verified_flow = verify_flow_ownership(chat.flow_id, current_user, db)
    logger.info(f"Flow ownership 验证通过 for flow: {verified_flow.id} linked to chat: {chat_id}")

    # 添加消息
    updated_chat = chat_service.add_message_to_chat(
        chat_id=chat_id,
        role=message.role,
        content=message.content
    )
    
    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="添加消息失败"
        )

    # --- Update Flow's last_interacted_chat_id ---
    if verified_flow: # Ensure we have the flow object
        try:
            verified_flow.last_interacted_chat_id = updated_chat.id # Use the current chat_id
            db.commit()
            logger.info(f"更新 Flow {verified_flow.id} 的 last_interacted_chat_id 为 {updated_chat.id}")
        except Exception as update_err:
            logger.error(f"更新 Flow last_interacted_chat_id 失败 (Flow: {verified_flow.id}, Chat: {updated_chat.id}): {update_err}", exc_info=True)
            db.rollback() # Rollback only the failed update
    else:
        logger.warning(f"无法更新 Flow 的 last_interacted_chat_id，因为在添加消息后未能获取 Flow 对象 (Flow ID: chat.flow_id if available else 'unknown')") # Improved logging
    # --- End Update ---

    return updated_chat


@router.delete("/{chat_id}", response_model=bool)
async def delete_chat(
    chat_id: str,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    删除聊天记录，必须登录并且只能删除自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verify_flow_ownership(chat.flow_id, current_user, db)
    
    # 删除聊天
    success = chat_service.delete_chat(chat_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="删除聊天失败"
        )
    
    return True 