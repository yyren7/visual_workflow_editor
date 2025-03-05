## backend/app/routers/flow.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from visual_workflow_editor.backend.app import models, database, schemas
from visual_workflow_editor.backend.app.config import Config
from visual_workflow_editor.backend.app.utils import get_current_user

router = APIRouter(
    prefix="/flows",
    tags=["flows"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Flow)
async def create_flow(flow: schemas.FlowCreate, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Creates a new flow. 必须登录才能创建流程。
    """
    db_flow = models.Flow(flow_data=flow.flow_data, owner_id=current_user.id, name=flow.name)
    db.add(db_flow)
    db.commit()
    db.refresh(db_flow)
    return db_flow


@router.get("/{flow_id}", response_model=schemas.Flow)
async def get_flow(flow_id: int, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Gets a flow by ID. 必须登录并且只能访问自己的流程。
    """
    db_flow = db.query(models.Flow).filter(models.Flow.id == flow_id, models.Flow.owner_id == current_user.id).first()
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return db_flow


@router.put("/{flow_id}", response_model=schemas.Flow)
async def update_flow(flow_id: int, flow: schemas.FlowUpdate, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Updates a flow by ID. 必须登录并且只能更新自己的流程。
    """
    db_flow = db.query(models.Flow).filter(models.Flow.id == flow_id, models.Flow.owner_id == current_user.id).first()
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    flow_data = flow.flow_data
    name = flow.name

    if flow_data is not None:
        db_flow.flow_data = flow_data
    if name is not None:
        db_flow.name = name

    db.commit()
    db.refresh(db_flow)
    return db_flow


@router.delete("/{flow_id}")
async def delete_flow(flow_id: int, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Deletes a flow by ID. 必须登录并且只能删除自己的流程。
    """
    db_flow = db.query(models.Flow).filter(models.Flow.id == flow_id, models.Flow.owner_id == current_user.id).first()
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    db.delete(db_flow)
    db.commit()
    return {"message": "Flow deleted successfully"}

@router.get("/", response_model=List[schemas.Flow])
async def get_flows_for_user(db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user), skip: int = Query(default=0, ge=0), limit: int = Query(default=10, le=100)):
    """
    Get all flows for the current user with pagination. 必须登录才能获取流程列表，且只能获取自己的流程。
    """
    flows = db.query(models.Flow).filter(models.Flow.owner_id == current_user.id).offset(skip).limit(limit).all()
    return flows
