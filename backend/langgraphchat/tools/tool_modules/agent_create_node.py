import uuid
from typing import Dict, Any, Tuple
from backend.langgraphchat.utils.logging import logger
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM
from ..definitions import NodeParams, ToolResult # Relative import

async def generate_node_properties(
    node_type: str, 
    node_label: str,
    llm_client: DeepSeekLLM
) -> Tuple[Dict[str, Any], bool]:
    """
    根据节点类型和标签生成推荐的节点属性
    """
    try:
        prompt = f"""请为以下流程图节点生成合适的属性JSON对象：
        
节点类型: {node_type}
节点标签: {node_label}

请生成一个属性对象，属性名应该反映该类型节点的常见特性，属性值应为占位符或示例值。
请只返回 JSON 对象本身，不要包含其他文本。例如：{{"property_name": "value"}}
"""
        
        properties_schema = {
            "type": "object",
            "properties": {},
            "description": "节点的属性键值对"
        }
        
        result, success = await llm_client.structured_output(
            prompt=prompt,
            system_prompt="你是一个流程图节点属性专家，擅长为不同类型的节点推荐合适的属性。请输出 JSON 对象格式的属性。",
            schema=properties_schema
        )
        
        if not success or not isinstance(result, dict):
            logger.error(f"生成节点属性失败或返回格式错误 for {node_type} - {node_label}")
            return {}, True 
            
        return result, True
        
    except Exception as e:
        logger.error(f"生成节点属性时出错: {str(e)}")
        return {}, False

async def create_node_func(
    params: NodeParams,
    llm_client: DeepSeekLLM
) -> ToolResult:
    """创建节点工具实现"""
    try:
        node_type = params.node_type
        node_label = params.node_label
        properties = params.properties
        position = params.position
        
        logger.info(f"请求创建节点: type={node_type}, label={node_label}")
        
        if not node_type:
            logger.warning("缺少节点类型")
            return ToolResult(
                success=False,
                message="创建节点失败: 缺少节点类型"
            )
        
        if not node_label:
             node_label = f"{node_type.capitalize()}_{str(uuid.uuid4())[:4]}"
             logger.info(f"未提供标签，使用生成的默认标签: {node_label}")
        
        if properties is None:
            logger.info("未提供属性，尝试生成默认属性")
            properties, prop_success = await generate_node_properties(node_type, node_label, llm_client)
            if not prop_success:
                 logger.warning("生成默认属性失败，将使用空属性")
                 properties = {}
            else:
                 logger.info(f"生成默认属性: {properties}")
        
        node_id = f"node_{str(uuid.uuid4())[:8]}"
        
        result_data = {
            "id": node_id,
            "type": node_type,
            "label": node_label,
            "properties": properties,
            "position": position if position else {"x": 100, "y": 100}
        }
        
        logger.info(f"成功准备节点创建数据: {node_label} (ID: {node_id})")
        return ToolResult(
            success=True,
            message=f"成功准备创建节点: {node_label}",
            data=result_data
        )
    except Exception as e:
        logger.error(f"创建节点时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return ToolResult(
            success=False,
            message=f"创建节点失败: {str(e)}"
        ) 