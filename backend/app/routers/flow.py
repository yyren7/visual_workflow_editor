## backend/app/routers/flow.py
from typing import List, Dict, Any, Optional
# 不再需要UUID类型
# from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.orm import Session
from backend.app import schemas, utils
from database.models import Flow, FlowVariable
from database.connection import get_db
from backend.config import APP_CONFIG
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.user_flow_service import UserFlowService

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
