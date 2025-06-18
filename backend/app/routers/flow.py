## backend/app/routers/flow.py
from typing import List, Dict, Any, Optional
# 不再需要UUID类型
# from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body, Response
from sqlalchemy.orm import Session
from backend.app import schemas, utils
from database.models import Flow, FlowVariable, Chat
from database.connection import get_db
from backend.config import APP_CONFIG
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.user_flow_service import UserFlowService
import logging # Add logging
from sqlalchemy import desc # Import desc for ordering

logger = logging.getLogger(__name__) # Add logger

router = APIRouter(
    prefix="/flows",
    tags=["flows"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Flow)
async def create_flow(flow: schemas.FlowCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Creates a new flow. 必须登录才能创建流程。
    """
    db_flow = Flow(flow_data=flow.flow_data, owner_id=current_user.id, name=flow.name)
    db.add(db_flow)
    db.commit()
    db.refresh(db_flow)
    
    # 设置为用户最后选择的流程图
    flow_service = UserFlowService(db)
    flow_service.set_last_selected_flow_id(current_user.id, db_flow.id)
    
    return db_flow


@router.get("/{flow_id}", response_model=schemas.Flow)
async def get_flow(flow_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Gets a flow by ID. 必须登录并且只能访问自己的流程。
    """
    flow = verify_flow_ownership(flow_id, current_user, db)
    
    # 记录用户最后访问的流程图
    flow_service = UserFlowService(db)
    flow_service.set_last_selected_flow_id(current_user.id, flow_id)
    
    return flow


@router.put("/{flow_id}", response_model=schemas.Flow)
async def update_flow(flow_id: str, flow: schemas.FlowUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Updates a flow. 必须登录并且只能更新自己的流程。
    """
    db_flow = verify_flow_ownership(flow_id, current_user, db)
    
    # Update flow fields
    if flow.name is not None:
        db_flow.name = flow.name
    if flow.flow_data is not None:
        db_flow.flow_data = flow.flow_data
    
    db.commit()
    db.refresh(db_flow)
    return db_flow


@router.delete("/{flow_id}", response_model=bool)
async def delete_flow(flow_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Deletes a flow. 必须登录并且只能删除自己的流程。
    """
    db_flow = verify_flow_ownership(flow_id, current_user, db)
    db.delete(db_flow)
    db.commit()
    return True


@router.get("/", response_model=List[schemas.Flow])
async def get_flows_for_user(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user), skip: int = Query(default=0, ge=0), limit: int = Query(default=10, le=100)):
    """
    Get all flows for the current user with pagination. 必须登录才能获取流程列表，且只能获取自己的流程。
    """
    flows = db.query(Flow).filter(Flow.owner_id == current_user.id).order_by(Flow.updated_at.desc()).offset(skip).limit(limit).all()
    return flows


@router.post("/{flow_id}/set-as-last-selected", response_model=bool)
async def set_as_last_selected(flow_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Sets a flow as the user's last selected flow. 必须登录并且只能选择自己的流程。
    """
    # 验证流程图存在且属于当前用户
    verify_flow_ownership(flow_id, current_user, db)
    
    # 设置为用户最后选择的流程图
    flow_service = UserFlowService(db)
    success = flow_service.set_last_selected_flow_id(current_user.id, flow_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="无法更新用户流程图偏好")
    
    return True


@router.get("/user/last-selected", response_model=schemas.Flow)
async def get_last_selected_flow(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Gets the user's last selected flow. 必须登录才能获取。
    """
    # 获取用户最后选择的流程图ID
    flow_service = UserFlowService(db)
    flow_id = flow_service.get_last_selected_flow_id(current_user.id)
    
    if not flow_id:
        # 如果用户没有选择过流程图，返回最新的一个
        flows = db.query(Flow).filter(Flow.owner_id == current_user.id).order_by(Flow.updated_at.desc()).first()
        if not flows:
            raise HTTPException(status_code=404, detail="用户没有流程图")
        return flows
    
    # 获取流程图详情
    flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not flow:
        # 如果记录的流程图不存在，返回最新的一个
        flows = db.query(Flow).filter(Flow.owner_id == current_user.id).order_by(Flow.updated_at.desc()).first()
        if not flows:
            raise HTTPException(status_code=404, detail="用户没有流程图")
        
        # 更新用户偏好
        flow_service.set_last_selected_flow_id(current_user.id, flows.id)
        return flows
    
    return flow


# --- Modify endpoint to get last interacted chat ID ---
@router.get("/{flow_id}/last_chat", response_model=schemas.LastChatResponse)
async def get_flow_last_chat_id(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取流程图最后交互且仍然存在的聊天 ID。
    如果记录的最后交互聊天已被删除，则尝试查找最新的、仍然存在的聊天。
    """
    try:
        logger.info(f"Attempting to get last valid chat ID for flow: {flow_id} for user: {current_user.id}")
        flow = verify_flow_ownership(flow_id, current_user, db) # Verify ownership and get flow

        last_chat_id = flow.last_interacted_chat_id
        valid_chat_id_to_return = None

        if last_chat_id:
            # 1. Check if the recorded last_chat_id still exists
            chat_exists = db.query(Chat).filter(
                Chat.id == last_chat_id,
                Chat.flow_id == flow_id # Ensure it belongs to the correct flow
            ).first()

            if chat_exists:
                logger.info(f"Recorded last chat ID {last_chat_id} is valid for flow {flow_id}.")
                valid_chat_id_to_return = last_chat_id
            else:
                logger.warning(f"Recorded last chat ID {last_chat_id} for flow {flow_id} not found or deleted. Searching for fallback.")
                # 2. If not exists, find the most recent *existing* chat for this flow
                fallback_chat = db.query(Chat).filter(
                    Chat.flow_id == flow_id
                ).order_by(desc(Chat.updated_at)).first() # Order by updated_at descending

                if fallback_chat:
                    logger.info(f"Found fallback chat ID {fallback_chat.id} for flow {flow_id}.")
                    valid_chat_id_to_return = fallback_chat.id
                    # Optional: Update the flow's last_interacted_chat_id to the new valid one
                    try:
                        flow.last_interacted_chat_id = fallback_chat.id
                        db.add(flow)
                        db.commit()
                        logger.info(f"Updated flow {flow_id}'s last_interacted_chat_id to {fallback_chat.id}.")
                    except Exception as update_err:
                         logger.error(f"Failed to update last_interacted_chat_id for flow {flow_id}", exc_info=True)
                         db.rollback() # Rollback the specific update attempt on error
                else:
                    logger.warning(f"No existing chats found for flow {flow_id} as fallback.")
                    # Optional: Clear the invalid last_interacted_chat_id if no fallback exists
                    if flow.last_interacted_chat_id is not None: # Only update if it was previously set
                        try:
                            flow.last_interacted_chat_id = None
                            db.add(flow)
                            db.commit()
                            logger.info(f"Cleared invalid last_interacted_chat_id for flow {flow_id}.")
                        except Exception as clear_err:
                             logger.error(f"Failed to clear last_interacted_chat_id for flow {flow_id}", exc_info=True)
                             db.rollback() # Rollback the specific clear attempt on error

        else:
             logger.info(f"No last interacted chat ID recorded for flow {flow_id}.")
             # last_chat_id was None initially, so valid_chat_id_to_return remains None

        logger.info(f"Returning last chat ID for flow {flow_id}: {valid_chat_id_to_return}")
        return schemas.LastChatResponse(chatId=valid_chat_id_to_return)

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        logger.warning(f"HTTPException getting last chat ID for flow {flow_id}: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch other potential errors
        logger.error(f"Unexpected error getting last chat ID for flow {flow_id}", exc_info=True)
        db.rollback() # Rollback any potential transaction changes from this function
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取最后聊天ID时出错: {str(e)}"
        )
# --- End modify endpoint ---

# --- 新增: 设置流程的最后交互聊天 ---
@router.post("/{flow_id}/set_last_chat", status_code=status.HTTP_204_NO_CONTENT)
async def set_flow_last_chat(
    flow_id: str,
    payload: schemas.SetLastChatRequest, # 使用定义的请求体模型
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    设置指定流程图的最后交互聊天ID。
    必须登录，并且只能操作自己的流程图。
    """
    logger.info(f"Attempting to set last interacted chat for flow: {flow_id} to chat: {payload.chat_id} for user: {current_user.id}")

    # 1. 验证流程图所有权并获取流程对象
    flow = verify_flow_ownership(flow_id, current_user, db)

    # 2. 验证 chat_id 对应的聊天是否存在且属于该 flow
    chat_to_set = db.query(Chat).filter(
        Chat.id == payload.chat_id,
        Chat.flow_id == flow_id # 确保聊天属于当前流程
    ).first()

    if not chat_to_set:
        logger.warning(f"Chat ID {payload.chat_id} not found or does not belong to flow {flow_id} for user {current_user.id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {payload.chat_id} not found for flow {flow_id}"
        )

    # 3. 更新流程的 last_interacted_chat_id
    try:
        flow.last_interacted_chat_id = payload.chat_id
        db.add(flow) # 添加到会话以进行更新
        db.commit()
        db.refresh(flow) # 刷新以获取更新后的状态 (可选，但良好实践)
        logger.info(f"Successfully set last interacted chat for flow {flow_id} to {payload.chat_id}")
        # 对于 204 No Content，通常不返回任何响应体
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to set last interacted chat for flow {flow_id} to {payload.chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update the last interacted chat for the flow."
        )
# --- 结束新增 ---

@router.post("/{flow_id}/ensure-agent-state", response_model=schemas.Flow)
async def ensure_agent_state(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    确保流程图有完整的 agent_state 结构。
    如果没有或缺少字段，会自动补充默认值。
    """
    from backend.app.services.flow_service import FlowService
    
    # 验证流程图所有权
    flow = verify_flow_ownership(flow_id, current_user, db)
    
    # 确保 agent_state 字段
    flow_service = FlowService(db)
    updated = flow_service.ensure_agent_state_fields(flow_id)
    
    if updated:
        logger.info(f"Updated agent_state for flow {flow_id}")
    
    # 重新获取更新后的流程图
    db.refresh(flow)
    return flow
