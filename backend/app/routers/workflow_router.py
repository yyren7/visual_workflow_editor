from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from backend.app.database import get_db
from backend.app.services.workflow_prompt_service import WorkflowPromptService, WorkflowProcessResponse
from backend.app.utils import get_current_user
from backend.app import schemas
import os
import json
from backend.app.config import Config

router = APIRouter(
    prefix="/workflow",
    tags=["workflow"],
    responses={404: {"description": "Not found"}}
)

# 请求模型
class WorkflowRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None  # 会话ID，用于关联多次交互

# 全局变量模型
class GlobalVariable(BaseModel):
    key: str
    value: Any

class GlobalVariablesRequest(BaseModel):
    variables: Dict[str, Any]

# 创建工作流服务实例
def get_workflow_service():
    return WorkflowPromptService()

# 获取全局变量文件路径
def get_global_variables_path():
    path = Config.GLOBAL_VARIABLES_PATH
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    return path

@router.get("/global-variables", response_model=Dict[str, Any])
async def get_global_variables(
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取全局变量
    
    Args:
        current_user: 当前用户
        
    Returns:
        全局变量字典
    """
    try:
        path = get_global_variables_path()
        
        # 如果文件不存在，则创建空的全局变量文件
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}
            
        # 读取全局变量文件
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {}
                
            try:
                variables = json.loads(content)
                return variables
            except json.JSONDecodeError:
                # 如果JSON无效，重置为空对象
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取全局变量失败: {str(e)}")

@router.post("/global-variables")
async def update_global_variables(
    request: GlobalVariablesRequest = Body(...),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    更新全局变量
    
    Args:
        request: 包含全局变量的请求
        current_user: 当前用户
        
    Returns:
        更新结果
    """
    try:
        path = get_global_variables_path()
        
        # 写入全局变量文件
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(request.variables, f, ensure_ascii=False, indent=2)
            
        return {"message": "全局变量已更新", "count": len(request.variables)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新全局变量失败: {str(e)}")

@router.delete("/global-variables")
async def reset_global_variables(
    current_user: schemas.User = Depends(get_current_user)
):
    """
    重置全局变量（清空所有变量）
    
    Args:
        current_user: 当前用户
        
    Returns:
        重置结果
    """
    try:
        path = get_global_variables_path()
        
        # 重置为空对象
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f)
            
        return {"message": "全局变量已重置"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置全局变量失败: {str(e)}")

@router.post("/process")
async def process_workflow_input(
    request: WorkflowRequest = Body(...),
    db: Session = Depends(get_db),
    workflow_service: WorkflowPromptService = Depends(get_workflow_service),
    current_user: schemas.User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    处理用户输入，创建或修改工作流（旧版API）
    
    Args:
        request: 包含用户输入的请求
        db: 数据库会话
        workflow_service: 工作流服务
        current_user: 当前用户
        
    Returns:
        处理结果
    """
    try:
        result = await workflow_service.process_user_input(request.prompt, db)
        
        # 添加会话ID和用户信息
        if request.session_id:
            result["session_id"] = request.session_id
        result["user_id"] = current_user.id
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理工作流失败: {str(e)}")

@router.post("/process_v2", response_model=WorkflowProcessResponse)
async def process_workflow_v2(
    request: WorkflowRequest = Body(...),
    db: Session = Depends(get_db),
    workflow_service: WorkflowPromptService = Depends(get_workflow_service),
    current_user: schemas.User = Depends(get_current_user)
) -> WorkflowProcessResponse:
    """
    处理用户输入，创建或修改工作流（使用DeepSeek的新版API）
    
    Args:
        request: 包含用户输入的请求
        db: 数据库会话
        workflow_service: 工作流服务
        current_user: 当前用户
        
    Returns:
        工作流处理响应，包含创建的节点和连接
    """
    try:
        # 调用新的工作流处理方法
        result = await workflow_service.process_workflow(request.prompt, db)
        
        # 生成聊天机器人响应摘要
        if not result.error:
            # 格式化成功结果为聊天摘要
            node_count = len(result.nodes)
            connection_count = len(result.connections)
            
            node_types = {}
            for node in result.nodes:
                node_type = node.get("type", "unknown")
                if node_type in node_types:
                    node_types[node_type] += 1
                else:
                    node_types[node_type] = 1
            
            # 构建节点类型摘要
            node_type_summary = ", ".join([f"{count}个{type_name}节点" for type_name, count in node_types.items()])
            
            # 添加摘要到响应
            result.summary = f"已成功创建流程图，包含{node_count}个节点（{node_type_summary}）和{connection_count}个连接。请在界面上查看生成的流程图。"
        else:
            # 错误情况
            result.summary = f"生成流程图失败: {result.error}"
        
        # 返回处理结果
        return result
    except Exception as e:
        # 记录详细错误
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"处理工作流V2失败: {str(e)}", exc_info=True)
        
        # 返回错误响应
        return WorkflowProcessResponse(
            error=f"处理工作流失败: {str(e)}",
            summary=f"处理流程图时出错: {str(e)}"
        ) 