from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.utils import get_current_user
from backend.app import schemas
from backend.app.services.flow_variable_service import FlowVariableService

router = APIRouter(
    prefix="/flow-variables",
    tags=["flow-variables"],
    responses={404: {"description": "Not found"}}
)

# 请求模型
class VariableUpdateRequest(BaseModel):
    variables: Dict[str, str]

class SingleVariableRequest(BaseModel):
    key: str
    value: str

# 获取变量服务实例
def get_variable_service(db: Session = Depends(get_db)):
    return FlowVariableService(db)

@router.get("/{flow_id}", response_model=Dict[str, str])
async def get_flow_variables(
    flow_id: str,
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取流程图的所有变量
    
    Args:
        flow_id: 流程图ID
        
    Returns:
        变量字典
    """
    # 这里可以添加权限检查，确保当前用户有权访问该流程图
    
    variables = variable_service.get_variables(flow_id)
    return variables

@router.post("/{flow_id}")
async def update_flow_variables(
    flow_id: str,
    request: VariableUpdateRequest,
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    更新流程图的变量（替换所有现有变量）
    
    Args:
        flow_id: 流程图ID
        request: 包含所有变量的请求
        
    Returns:
        更新结果
    """
    # 这里可以添加权限检查，确保当前用户有权修改该流程图
    
    success = variable_service.update_variables(flow_id, request.variables)
    if not success:
        raise HTTPException(status_code=500, detail="更新变量失败")
    
    return {"message": "变量更新成功", "count": len(request.variables)}

@router.post("/{flow_id}/variable")
async def add_flow_variable(
    flow_id: str,
    request: SingleVariableRequest,
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    添加或更新单个变量
    
    Args:
        flow_id: 流程图ID
        request: 包含变量名和值的请求
        
    Returns:
        添加/更新结果
    """
    # 这里可以添加权限检查，确保当前用户有权修改该流程图
    
    success = variable_service.add_variable(flow_id, request.key, request.value)
    if not success:
        raise HTTPException(status_code=500, detail=f"添加/更新变量 {request.key} 失败")
    
    return {"message": f"变量 {request.key} 添加/更新成功"}

@router.delete("/{flow_id}/variable/{key}")
async def delete_flow_variable(
    flow_id: str,
    key: str,
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    删除单个变量
    
    Args:
        flow_id: 流程图ID
        key: 变量名
        
    Returns:
        删除结果
    """
    # 这里可以添加权限检查，确保当前用户有权修改该流程图
    
    success = variable_service.delete_variable(flow_id, key)
    if not success:
        raise HTTPException(status_code=404, detail=f"变量 {key} 不存在")
    
    return {"message": f"变量 {key} 删除成功"}

@router.delete("/{flow_id}")
async def reset_flow_variables(
    flow_id: str,
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    重置流程图的所有变量（删除所有变量）
    
    Args:
        flow_id: 流程图ID
        
    Returns:
        重置结果
    """
    # 这里可以添加权限检查，确保当前用户有权修改该流程图
    
    success = variable_service.reset_variables(flow_id)
    if not success:
        raise HTTPException(status_code=500, detail="重置变量失败")
    
    return {"message": "所有变量已重置"}

@router.post("/{flow_id}/import")
async def import_flow_variables(
    flow_id: str,
    file: UploadFile = File(...),
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    从JSON文件导入变量
    
    Args:
        flow_id: 流程图ID
        file: JSON文件
        
    Returns:
        导入结果
    """
    # 这里可以添加权限检查，确保当前用户有权修改该流程图
    
    try:
        content = await file.read()
        json_data = content.decode('utf-8')
        
        success = variable_service.import_variables_from_json(flow_id, json_data)
        if not success:
            raise HTTPException(status_code=400, detail="导入变量失败，可能是无效的JSON格式")
        
        return {"message": "变量导入成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入变量时出错: {str(e)}")

@router.get("/{flow_id}/export")
async def export_flow_variables(
    flow_id: str,
    variable_service: FlowVariableService = Depends(get_variable_service),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    导出变量为JSON
    
    Args:
        flow_id: 流程图ID
        
    Returns:
        JSON字符串
    """
    # 这里可以添加权限检查，确保当前用户有权访问该流程图
    
    json_data = variable_service.export_variables_to_json(flow_id)
    return {"data": json_data} 