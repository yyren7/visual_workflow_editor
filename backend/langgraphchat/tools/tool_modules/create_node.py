from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
import os
import json
import xml.etree.ElementTree as ET
from database.connection import get_db_context
from backend.app.services.flow_service import FlowService
from backend.langgraphchat.context import current_flow_id_var
from backend.langgraphchat.utils.logging import logger

XML_NODE_DEFINITIONS_PATH = "database/node_database/quick-fcpr/"

def create_node_tool_func(
    node_type: str,
    node_label: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    position: Optional[Dict[str, float]] = None,
    node_name: Optional[str] = None,
    label: Optional[str] = None,
    type: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Creates a node in the current workflow diagram.
    Node type must correspond to an XML file in the XML_NODE_DEFINITIONS_PATH.
    Node properties will be dynamically loaded from the XML, with user-provided
    properties overriding the defaults.
    """
    try:
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("创建节点失败：无法从上下文中获取当前的 flow_id")
            return {"success": False, "message": "无法获取当前流程ID", "error": "Context error: Missing flow_id"}

        logger.info("=" * 40)
        logger.info(f"创建节点工具函数被调用 (Flow ID: {target_flow_id})")
        
        original_node_type_arg = node_type
        if node_type is None and type is not None:
            node_type = type
            logger.info(f"使用 type 参数作为节点类型: {node_type}")
        
        if node_type is None:
            logger.error(f"缺少必要的 node_type 参数 (传入的 node_type: {original_node_type_arg}, type: {type})")
            return {
                "success": False,
                "message": "创建节点失败: 缺少必要的 node_type 参数",
                "error": "缺少 node_type 参数"
            }

        effective_label = node_label or node_name or label
        if effective_label is None:
            effective_label = node_type
            logger.info(f"未提供标签，使用节点类型 '{node_type}' 作为标签: {effective_label}")
        
        logger.info(f"尝试创建节点: 类型='{node_type}', 标签='{effective_label}'")

        xml_file_path = os.path.join(XML_NODE_DEFINITIONS_PATH, f"{node_type}.xml")
        logger.info(f"查找节点定义XML: {xml_file_path}")

        if not os.path.exists(xml_file_path):
            logger.error(f"节点类型 '{node_type}' 的定义文件未找到: {xml_file_path}")
            available_xml_files = [f.replace('.xml', '') for f in os.listdir(XML_NODE_DEFINITIONS_PATH) if f.endswith('.xml')]
            error_message = f"节点类型 '{node_type}' 无效. XML 定义文件 '{xml_file_path}' 未找到。"
            if available_xml_files:
                error_message += f" 可用的节点类型有: {', '.join(available_xml_files)}."
            else:
                error_message += f" 在 '{XML_NODE_DEFINITIONS_PATH}' 目录下没有找到任何XML定义文件."
            return {
                "success": False,
                "message": error_message,
                "error": "Node definition XML not found"
            }

        xml_defined_properties = {}
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            block_element = root.find(".//block")
            if block_element is not None:
                for field in block_element.findall("field"):
                    param_name = field.get("name")
                    if param_name:
                        default_value = field.text if field.text is not None else "" 
                        xml_defined_properties[param_name] = default_value
                logger.info(f"从 '{xml_file_path}' 加载的默认属性: {xml_defined_properties}")
            else:
                logger.warning(f"XML 文件 '{xml_file_path}' 中未找到 <block> 元素，无法加载默认属性。")

        except ET.ParseError as e:
            logger.error(f"解析XML文件 '{xml_file_path}' 失败: {e}")
            return {
                "success": False,
                "message": f"解析节点定义文件 '{xml_file_path}' 失败.",
                "error": f"XML ParseError: {e}"
            }

        provided_properties = {}
        if properties is not None:
            provided_properties.update(properties)
        
        main_func_params = {'node_type', 'node_label', 'properties', 'position', 'node_name', 'label', 'type'}
        for key, value in kwargs.items():
            if key not in main_func_params:
                provided_properties[key] = value
        
        logger.info(f"用户提供的属性 (合并 'properties' 和 kwargs): {provided_properties}")

        final_node_specific_properties = {**xml_defined_properties, **provided_properties}
        logger.info(f"合并后的节点特定属性 (XML默认 + 用户提供): {final_node_specific_properties}")
        
        from datetime import datetime
        timestamp = int(datetime.now().timestamp() * 1000)
        node_id = f"{node_type}-{timestamp}"
        logger.info(f"生成节点ID: {node_id}")
        
        if not position:
            import random
            position = {"x": random.randint(100, 500), "y": random.randint(100, 300)}
            logger.info(f"生成随机位置: {position}")
        
        generic_default_properties = {
            "description": final_node_specific_properties.get("description", ""),
            "fields": final_node_specific_properties.get("fields", []),
            "inputs": final_node_specific_properties.get("inputs", []),
            "outputs": final_node_specific_properties.get("outputs", []),
            "point_name_list": final_node_specific_properties.get("point_name_list", []),
            "pallet_list": final_node_specific_properties.get("pallet_list", []),
            "camera_list": final_node_specific_properties.get("camera_list", [])
        }

        node_data = {
            "id": node_id,
            "type": "generic",
            "position": position,
            "data": {
                "label": effective_label,
                "nodeType": node_type,
                "type": node_type,
                **generic_default_properties,
                **final_node_specific_properties, 
                "nodeProperties": {
                    "nodeId": node_id,
                    "nodeType": node_type,
                    **final_node_specific_properties
                },
            }
        }
        
        logger.info(f"创建节点数据: id={node_id}, type(data.nodeType)={node_type}, label={effective_label}")
        logger.debug(f"完整节点数据: {json.dumps(node_data, indent=2)}")

        try:
            logger.info(f"使用流程图ID: {target_flow_id}")
            with get_db_context() as db:
                flow_service = FlowService(db)
                flow_data = flow_service.get_flow(target_flow_id)
                if not flow_data:
                    logger.error(f"无法获取流程图(ID={target_flow_id})数据")
                    return {
                        "success": False,
                        "message": f"无法获取流程图(ID={target_flow_id})数据",
                        "error": f"无法获取流程图(ID={target_flow_id})数据"
                    }
                
                if "nodes" not in flow_data or not isinstance(flow_data.get("nodes"), list):
                    flow_data["nodes"] = []
                    
                flow_data["nodes"].append(node_data)
                
                success_db = flow_service.update_flow(
                    flow_id=target_flow_id,
                    data=flow_data,
                    name=flow_data.get("name")
                )
            
                if not success_db:
                    logger.error(f"更新流程图失败 for flow {target_flow_id}")
                    return {
                        "success": False,
                        "message": f"创建节点 '{effective_label}' 成功，但更新数据库失败",
                        "error": "数据库更新失败",
                        "node_data": node_data
                    }
                
                logger.info(f"节点创建并保存成功: {node_id}")
                logger.info("=" * 40)
                return {
                    "success": True,
                    "message": f"成功创建并保存节点: {effective_label} (类型: {node_type})",
                    "node_data": node_data
                }
        except Exception as e:
            logger.error(f"数据库操作失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"创建节点 '{effective_label}' 时数据库操作失败",
                "error": f"数据库错误: {str(e)}",
                "node_data": node_data
            }
        
    except Exception as e:
        logger.error(f"创建节点准备阶段或XML处理出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        logger.info("=" * 40)
        return {
            "success": False,
            "message": f"创建节点失败: {str(e)}",
            "error": str(e)
        }

class CreateNodeSchema(BaseModel):
    node_type: str = Field(description="The type of the node to create.")
    node_label: Optional[str] = Field(None, description="The label for the node. Uses node_type if not provided.")
    properties: Optional[Dict[str, Any]] = Field(None, description="Properties for the node.")
    position: Optional[Dict[str, float]] = Field(None, description="Position (x, y) for the node.")

create_node_tool = StructuredTool.from_function(
    func=create_node_tool_func,
    name="create_node",
    description="Creates a new node in the current workflow diagram. Specify node type, label, position, and properties.",
    args_schema=CreateNodeSchema
) 