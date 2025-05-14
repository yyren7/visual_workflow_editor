from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from database.connection import get_db_context
from backend.app.services.flow_service import FlowService
from backend.langgraphchat.context import current_flow_id_var
from backend.langgraphchat.utils.logging import logger

def connect_nodes_tool_func(
    source_id: str,
    target_id: str,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Connects two nodes in the current workflow diagram."""
    try:
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("连接节点失败：无法从上下文中获取当前的 flow_id")
            return {"success": False, "message": "无法获取当前流程ID", "error": "Context error: Missing flow_id"}
        
        logger.info(f"连接节点: {source_id} -> {target_id} (Flow ID: {target_flow_id})")
        
        connection_id = f"reactflow__edge-{source_id}output-{target_id}input"
        
        edge_data = {
            "id": connection_id,
            "source": source_id,
            "target": target_id,
            "label": label or "",
            "type": "smoothstep",
            "animated": False,
            "style": {"stroke": "#888", "strokeWidth": 2},
            "markerEnd": {"type": "arrowclosed", "color": "#888", "width": 20, "height": 20}
        }
        
        try:
            logger.info(f"使用流程图ID: {target_flow_id}")
            with get_db_context() as db:
                flow_service = FlowService(db)
                flow_data = flow_service.get_flow(target_flow_id)
                if not flow_data:
                    return {
                        "success": False,
                        "message": f"无法获取流程图(ID={target_flow_id})数据",
                        "error": f"无法获取流程图(ID={target_flow_id})数据"
                    }
                
                if "edges" not in flow_data:
                    flow_data["edges"] = []
                    
                flow_data["edges"].append(edge_data)
                
                success = flow_service.update_flow(
                    flow_id=target_flow_id,
                    data=flow_data,
                    name=flow_data.get("name")
                )
            
                if not success:
                    logger.error(f"更新流程图失败")
                    return {
                        "success": False,
                        "message": "更新流程图失败",
                        "error": "更新流程图失败"
                    }
            
                logger.info(f"连接创建成功: {connection_id}")
                return {
                    "success": True,
                    "message": f"成功连接节点: {source_id} -> {target_id}",
                    "connection_data": edge_data
                }
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"API调用失败: {str(e)}",
                "error": str(e)
            }
        
    except Exception as e:
        logger.error(f"连接节点时出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"连接节点失败: {str(e)}",
            "error": str(e)
        }

class ConnectNodesSchema(BaseModel):
    source_id: str = Field(description="The ID of the source node.")
    target_id: str = Field(description="The ID of the target node.")
    label: Optional[str] = Field(None, description="Label for the connection.")

connect_nodes_tool = StructuredTool.from_function(
    func=connect_nodes_tool_func,
    name="connect_nodes",
    description="Connects two nodes in the current workflow diagram using their source_id and target_id.",
    args_schema=ConnectNodesSchema
) 