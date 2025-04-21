from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from backend.database.connection import get_db
from backend.app.services.workflow_prompt_service import WorkflowPromptService, WorkflowProcessResponse
from backend.app.utils_auth import get_current_user
from backend.app.schemas import User
import os
import json
from backend.config import APP_CONFIG
from backend.langchainchat.utils.translator import translator

router = APIRouter(
    prefix="/workflow",
    tags=["workflow"],
    responses={404: {"description": "Not found"}}
)

# 请求模型
class WorkflowRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None  # 会话ID，用于关联多次交互
    language: Optional[str] = "en"    # 期望的响应语言 (en, zh, ja)

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
    path = APP_CONFIG['GLOBAL_VARIABLES_PATH']
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    return path

@router.get("/global-variables", response_model=Dict[str, Any])
async def get_global_variables(
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
        
        # 翻译结果
        if hasattr(request, 'language') and request.language:
            if result.get("summary"):
                result["summary"] = translator.translate(result["summary"], target_language=request.language)
            if result.get("error"):
                result["error"] = translator.translate(result["error"], target_language=request.language)
            if result.get("expanded_prompt"):
                result["expanded_prompt"] = translator.translate(result["expanded_prompt"], target_language=request.language)
            
        return result
    except Exception as e:
        error_message = f"处理工作流失败: {str(e)}"
        # 翻译错误信息
        if hasattr(request, 'language') and request.language:
            error_message = translator.translate(error_message, target_language=request.language)
        raise HTTPException(status_code=500, detail=error_message)

@router.post("/process_v2", response_model=WorkflowProcessResponse)
async def process_workflow_v2(
    request: WorkflowRequest = Body(...),
    db: Session = Depends(get_db),
    workflow_service: WorkflowPromptService = Depends(get_workflow_service),
    current_user: User = Depends(get_current_user)
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
        
        # 翻译结果
        if hasattr(request, 'language') and request.language:
            if result.summary:
                result.summary = translator.translate(result.summary, target_language=request.language)
            if result.error:
                result.error = translator.translate(result.error, target_language=request.language)
            if result.expanded_prompt:
                result.expanded_prompt = translator.translate(result.expanded_prompt, target_language=request.language)
            if result.missing_info:
                if isinstance(result.missing_info, list):
                    result.missing_info = [translator.translate(item, target_language=request.language) for item in result.missing_info]
                elif isinstance(result.missing_info, str):
                    result.missing_info = translator.translate(result.missing_info, target_language=request.language)
        
        return result
    except Exception as e:
        error_message = f"处理工作流失败: {str(e)}"
        # 翻译错误信息
        if hasattr(request, 'language') and request.language:
            error_message = translator.translate(error_message, target_language=request.language)
        
        # 创建带有错误信息的响应对象
        return WorkflowProcessResponse(error=error_message) 