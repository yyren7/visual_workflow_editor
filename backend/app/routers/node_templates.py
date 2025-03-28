from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import os

from backend.app.dependencies import get_node_template_service
from backend.app.services.node_template_service import NodeTemplateService

router = APIRouter(
    prefix="/node-templates",
    tags=["node templates"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=Dict[str, Any])
async def get_node_templates(
    template_service: NodeTemplateService = Depends(get_node_template_service)
):
    """
    获取所有可用的节点模板
    
    从节点模板服务获取所有已加载的节点模板定义
    
    返回:
        Dict[str, Any]: 节点模板数据字典，键为模板类型
    """
    templates = template_service.get_templates()
    
    # 检查模板目录是否存在
    template_dir = template_service.template_dir
    dir_exists = os.path.exists(template_dir)
    
    # 获取数据库目录相关信息用于诊断
    response = {
        "templates": templates,
        "metadata": {
            "template_count": len(templates),
            "template_dir": template_dir,
            "template_dir_exists": dir_exists
        }
    }
    
    if not templates:
        if not dir_exists:
            response["error"] = f"模板目录不存在: {template_dir}"
        else:
            files = os.listdir(template_dir)
            xml_files = [f for f in files if f.endswith('.xml')]
            response["metadata"]["total_files"] = len(files)
            response["metadata"]["xml_files"] = len(xml_files)
            if len(xml_files) == 0:
                response["error"] = f"模板目录中没有XML文件: {template_dir}"
    
    return response 