from typing import Dict, Any
from pydantic import BaseModel
from langchain_core.tools import StructuredTool
import logging
from database.connection import get_db_context
from backend.app.services.flow_service import FlowService
from backend.app.services.flow_variable_service import FlowVariableService
from backend.langgraphchat.context import current_flow_id_var
logger = logging.getLogger(__name__)

def get_flow_info_tool_func() -> Dict[str, Any]:
    """Retrieves information about the current workflow (nodes, connections, variables)."""
    try:
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("获取流程图信息失败：无法从上下文中获取当前的 flow_id")
            return {"success": False, "message": "无法获取当前流程ID", "error": "Context error: Missing flow_id"}
        
        logger.info(f"获取流程图信息 (Flow ID: {target_flow_id})")
        
        with get_db_context() as db:
            flow_service = FlowService(db)
            variable_service = FlowVariableService(db)
            logger.info(f"使用流程图ID: {target_flow_id}")
            flow_data = flow_service.get_flow(target_flow_id)
            if not flow_data:
                return {"success": False, "message": f"未找到流程图 {target_flow_id}", "error": "Flow not found"}
            variables = variable_service.get_variables(target_flow_id)
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", []) 
            return {
                "success": True, "message": "成功获取流程图信息",
                "flow_info": {
                    "flow_id": target_flow_id,
                    "name": flow_data.get("name", "未命名流程图"),
                    "created_at": flow_data.get("created_at", "未知"),
                    "updated_at": flow_data.get("updated_at", "未知"),
                    "nodes": nodes, "edges": edges, "variables": variables
                }
            }
            
    except Exception as e:
        logger.error(f"获取流程图信息时出错: {str(e)}", exc_info=True)
        return {"success": False, "message": f"获取流程图信息失败: {str(e)}"}

class GetFlowInfoSchema(BaseModel):
    pass

get_flow_info_tool = StructuredTool.from_function(
    func=get_flow_info_tool_func,
    name="get_flow_info",
    description="Retrieves information about the current workflow, such as nodes, connections, and variables.",
    args_schema=GetFlowInfoSchema
) 