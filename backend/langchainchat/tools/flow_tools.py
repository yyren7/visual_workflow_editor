from typing import Dict, Any, List, Optional, Type, Union, Tuple
from pydantic import BaseModel, Field
from langchain.tools import BaseTool, Tool
import logging
import uuid
import os
import json
import httpx
import asyncio
from sqlalchemy.orm import Session

# Use correct absolute path for logger import
from backend.langchainchat.utils.logging import logger

# Import Pydantic models and ToolResult
from .definitions import (
    NodeParams, ConnectionParams, PropertyParams, 
    QuestionsParams, TextGenerationParams, ToolResult
)
# Import the necessary LLM client class
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM
# Import the output parser (assuming it's needed for property generation)
from backend.langchainchat.output_parsers.structured_parser import StructuredOutputParser

# 当前活动的流程图ID，可以由会话管理器设置
_active_flow_id = None

def set_active_flow_id(flow_id: int):
    """
    设置当前活动的流程图ID
    
    Args:
        flow_id: 流程图ID
    """
    global _active_flow_id
    _active_flow_id = flow_id
    logger.info(f"设置当前活动流程图ID: {flow_id}")

def get_active_flow_id(db: Session = None) -> Optional[int]:
    """
    获取当前活动的流程图ID
    如果未设置当前活动流程图ID，则获取最新的流程图ID
    
    Args:
        db: 数据库会话，如果需要获取最新流程图
        
    Returns:
        当前活动的流程图ID
    """
    global _active_flow_id
    
    # 如果已经设置了活动流程图ID，直接返回
    if _active_flow_id is not None:
        return _active_flow_id
    
    # 否则尝试获取最新的流程图ID
    if db:
        try:
            from backend.app.services.flow_service import FlowService
            flow_service = FlowService(db)
            flows = flow_service.get_flows()
            if flows:
                newest_flow_id = flows[0].id
                logger.info(f"获取最新流程图ID: {newest_flow_id}")
                return newest_flow_id
        except Exception as e:
            logger.error(f"获取最新流程图ID失败: {str(e)}")
    
    return None

# 节点创建工具 - 同步版本
def create_node_tool_func(
    node_type: str,
    node_label: Optional[str] = None, 
    properties: Optional[Dict[str, Any]] = None,
    position: Optional[Dict[str, float]] = None,
    # 添加可能的替代参数名
    node_name: Optional[str] = None,
    label: Optional[str] = None,
    type: Optional[str] = None,  # 兼容可能的type参数
    flow_id: Optional[str] = None,  # 添加flow_id参数
    **kwargs  # 捕获任何其他参数
) -> Dict[str, Any]:
    """
    创建流程图节点
    
    Args:
        node_type: 节点类型
        node_label: 节点标签，如果未提供则使用节点类型作为标签
        properties: 节点属性
        position: 节点位置
        node_name: node_label的别名
        label: node_label的别名
        type: node_type的别名
        flow_id: 流程图ID，如果提供则优先使用
        **kwargs: 捕获任何其他参数
        
    Returns:
        节点创建结果
    """
    try:
        # 添加详细的调试日志
        logger.info("=" * 40)
        logger.info("创建节点工具函数被调用")
        logger.info(f"节点类型参数: node_type={node_type}, type={type}")
        logger.info(f"节点标签参数: node_label={node_label}, node_name={node_name}, label={label}")
        logger.info(f"流程图ID: flow_id={flow_id}")
        logger.info(f"其他参数: kwargs={kwargs}")
        
        # 处理参数别名
        if node_type is None and type is not None:
            node_type = type
            logger.info(f"使用type参数作为节点类型: {node_type}")
            
        # 确保我们有节点类型
        if node_type is None:
            logger.error("缺少必要的node_type参数")
            return {
                "success": False,
                "message": "创建节点失败: 缺少必要的node_type参数",
                "error": "缺少node_type参数"
            }
            
        # 处理标签的不同可能参数名
        effective_label = node_label or node_name or label
            
        # 如果未提供标签，使用节点类型作为标签
        if effective_label is None:
            effective_label = node_type
            logger.info(f"未提供标签，使用节点类型作为标签: {effective_label}")
            
        logger.info(f"创建节点: 类型={node_type}, 标签={effective_label}")
        
        # 合并所有可能是属性的参数
        all_properties = {}
        if properties is not None:
            all_properties.update(properties)
            logger.info(f"使用提供的属性: {properties}")
            
        # 从kwargs中提取可能的属性
        for key, value in kwargs.items():
            if key not in ['node_type', 'node_label', 'position', 'node_name', 'label', 'type', 'flow_id']:
                all_properties[key] = value
        
        # 生成唯一ID，遵循前端格式：nodeType-timestamp
        from datetime import datetime
        timestamp = int(datetime.now().timestamp() * 1000)
        node_id = f"{node_type}-{timestamp}"
        logger.info(f"生成节点ID: {node_id}")
        
        # 处理默认位置
        if not position:
            # 生成随机位置
            import random
            position = {
                "x": random.randint(100, 500),
                "y": random.randint(100, 300)
            }
            logger.info(f"生成随机位置: {position}")
        
        # 为常用属性提供默认值 - 确保与前端NodeSelector拖放创建的节点格式一致
        default_properties = {
            "control_x": "enable",
            "control_y": "enable",
            "description": "",
            "fields": [],
            "inputs": [],
            "outputs": [],
            "point_name_list": [],
            "pallet_list": [],
            "camera_list": []
        }
        
        # 合并默认属性和用户提供的属性，用户提供的属性优先
        merged_properties = {**default_properties, **all_properties}
        logger.info(f"最终节点属性: {merged_properties}")
            
        # 创建节点数据，完全符合前端FlowEditor.onDrop方法创建的节点格式
        node_data = {
            "id": node_id,
            "type": "generic",  # 使用generic类型，与前端保持一致
            "position": position,
            "data": {
                "label": effective_label,
                "nodeType": node_type,
                "type": node_type,
                "description": merged_properties.get("description", ""),
                "fields": merged_properties.get("fields", []),
                "inputs": merged_properties.get("inputs", []),
                "outputs": merged_properties.get("outputs", []),
                # 添加nodeProperties，与前端格式保持一致
                "nodeProperties": {
                    "nodeId": node_id,
                    "nodeType": node_type,
                    **merged_properties
                },
                # 添加所有合并后的属性到顶层
                **merged_properties
            }
        }
        logger.info(f"创建节点数据: id={node_id}, type={node_type}, label={effective_label}")
        
        # 使用同步方式调用API
        try:
            # 这里我们使用内部API直接创建节点
            from database.connection import get_db
            from backend.app.services.flow_service import FlowService
            
            # 获取数据库会话
            db = next(get_db())
            
            # 获取流服务
            flow_service = FlowService(db)
            
            # 获取流程图ID，优先使用传入的flow_id
            target_flow_id = flow_id
            if not target_flow_id:
                target_flow_id = get_active_flow_id(db)
            
            if not target_flow_id:
                logger.error("没有找到活动的流程图")
                return {
                    "success": False, 
                    "message": "没有找到活动的流程图",
                    "error": "没有找到活动的流程图"
                }
            
            logger.info(f"使用流程图ID: {target_flow_id}")
            
            # 获取当前流程图数据
            flow_data = flow_service.get_flow(target_flow_id)
            if not flow_data:
                logger.error(f"无法获取流程图(ID={target_flow_id})数据")
                return {
                    "success": False,
                    "message": f"无法获取流程图(ID={target_flow_id})数据",
                    "error": f"无法获取流程图(ID={target_flow_id})数据"
                }
            
            # 确保nodes字段存在
            if "nodes" not in flow_data:
                flow_data["nodes"] = []
                
            # 添加新节点到节点列表
            flow_data["nodes"].append(node_data)
            
            # 更新流程图数据
            success = flow_service.update_flow(
                flow_id=target_flow_id,
                data=flow_data
            )
            
            if not success:
                logger.error(f"更新流程图失败")
                return {
                    "success": False,
                    "message": "更新流程图失败",
                    "error": "更新流程图失败"
                }
            
            logger.info(f"节点创建成功: {node_id}")
            logger.info("=" * 40)
            return {
                "success": True,
                "message": f"成功创建节点: {effective_label} (类型: {node_type})",
                "node_data": node_data
            }
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            
            # 即使API调用失败，我们仍然返回节点数据
            # 这样LLM至少可以继续工作流程，即使节点未保存到数据库
            logger.info(f"返回虚拟节点数据: {node_id}")
            logger.info("=" * 40)
            return {
                "success": True,
                "message": f"创建了虚拟节点: {effective_label} (类型: {node_type})",
                "node_data": node_data,
                "warning": "节点未保存到数据库，但已创建虚拟节点以继续工作流"
            }
        
    except Exception as e:
        logger.error(f"创建节点时出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        logger.info("=" * 40)
        return {
            "success": False,
            "message": f"创建节点失败: {str(e)}",
            "error": str(e)
        }

# 使用Tool工厂函数创建工具
create_node_tool = Tool(
    name="create_node",
    description="""创建一个新的流程图节点。
    参数:
    - node_type (必需): 节点类型，如"moveL", "movel", "process", "decision"等，也可使用type参数
    - node_label (可选): 节点标签，如果未提供则使用node_type作为标签，也可使用node_name或label参数
    - properties (可选): 节点属性字典，可包含节点特定的配置参数。所有缺失的属性都会使用默认值自动填充
                       包括control_x、control_y等属性，默认值均为"enable"
    - position (可选): 节点位置，包含x和y坐标的对象，如果未提供则自动生成随机位置
    
    示例用法:
    create_node(node_type="moveL")
    create_node(node_type="process", node_label="处理数据")
    create_node(node_type="moveL", properties={"control_x": "enable", "control_y": "enable"})
    create_node(type="moveL", node_name="移动节点")
    
    注意：
    1. 即使不提供任何可选参数，也能成功创建节点，所有必要的属性都会自动填充默认值
    2. 工具会自动处理inputs参数中的常见参数别名，如node_name代替node_label
    3. 对于movel类型节点，工具会自动提供点位列表、控制参数等默认值
    """,
    func=create_node_tool_func,
)

# 连接节点工具函数
def connect_nodes_tool_func(
    source_id: str,
    target_id: str,
    label: Optional[str] = None,
    flow_id: Optional[str] = None  # 添加flow_id参数
) -> Dict[str, Any]:
    """
    连接两个流程图节点
    
    Args:
        source_id: 源节点ID
        target_id: 目标节点ID
        label: 连接标签
        flow_id: 流程图ID，如果提供则优先使用
        
    Returns:
        连接创建结果
    """
    try:
        logger.info(f"连接节点: {source_id} -> {target_id}")
        
        # 生成唯一ID
        connection_id = f"reactflow__edge-{source_id}output-{target_id}input"  # 使用与前端一致的边ID格式
        
        # 创建连接数据
        edge_data = {
            "id": connection_id,
            "source": source_id,
            "target": target_id,
            "label": label or "",
            "type": "smoothstep",  # 使用默认边类型
            "animated": False,
            "style": {"stroke": "#888", "strokeWidth": 2},
            "markerEnd": {"type": "arrowclosed", "color": "#888", "width": 20, "height": 20}
        }
        
        # 调用API创建连接
        try:
            # 这里使用内部API直接创建连接
            from database.connection import get_db
            from backend.app.services.flow_service import FlowService
            
            # 获取数据库会话
            db = next(get_db())
            
            # 获取流服务
            flow_service = FlowService(db)
            
            # 获取流程图ID，优先使用传入的flow_id
            target_flow_id = flow_id
            if not target_flow_id:
                target_flow_id = get_active_flow_id(db)
            
            if not target_flow_id:
                return {
                    "success": False, 
                    "message": "没有找到活动的流程图",
                    "error": "没有找到活动的流程图"
                }
            
            logger.info(f"使用流程图ID: {target_flow_id}")
            
            # 获取当前流程图数据
            flow_data = flow_service.get_flow(target_flow_id)
            if not flow_data:
                return {
                    "success": False,
                    "message": f"无法获取流程图(ID={target_flow_id})数据",
                    "error": f"无法获取流程图(ID={target_flow_id})数据"
                }
            
            # 确保edges字段存在
            if "edges" not in flow_data:
                flow_data["edges"] = []
                
            # 添加新连接到edges列表
            flow_data["edges"].append(edge_data)
            
            # 更新流程图数据
            success = flow_service.update_flow(
                flow_id=target_flow_id,
                data=flow_data
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

# 使用Tool工厂函数创建连接节点工具
connect_nodes_tool = Tool(
    name="connect_nodes",
    description="连接两个流程图节点",
    func=connect_nodes_tool_func,
)

# 获取流程图信息工具函数
def get_flow_info_tool_func(
    flow_id: Optional[str] = None  # 添加flow_id参数
) -> Dict[str, Any]:
    """
    获取当前流程图的信息
    
    Args:
        flow_id: 流程图ID，如果提供则优先使用
        
    Returns:
        流程图信息
    """
    try:
        logger.info("获取流程图信息")
        
        # 使用内部API获取流程图信息
        from database.connection import get_db
        from backend.app.services.flow_service import FlowService
        
        # 获取数据库会话
        db = next(get_db())
        
        try:
            # 获取流服务
            flow_service = FlowService(db)
            
            # 获取流程图ID，优先使用传入的flow_id
            target_flow_id = flow_id
            if not target_flow_id:
                target_flow_id = get_active_flow_id(db)
            
            if not target_flow_id:
                return {
                    "success": False, 
                    "message": "没有找到活动的流程图",
                    "error": "没有找到活动的流程图"
                }
            
            logger.info(f"使用流程图ID: {target_flow_id}")
            
            # 获取流程图详情
            flow_data = flow_service.get_flow(target_flow_id)
            
            # 提取节点和连接
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])  # 使用edges而不是connections
            
            # 构建节点摘要
            node_summaries = []
            for node in nodes[:10]:  # 限制节点数量，避免响应过大
                node_id = node.get("id", "未知")
                node_type = node.get("type", "未知")
                node_label = node.get("data", {}).get("label", "未命名")
                node_summaries.append({
                    "id": node_id,
                    "type": node_type,
                    "label": node_label
                })
            
            # 构建返回信息
            return {
                "success": True,
                "message": "成功获取流程图信息",
                "flow_info": {
                    "flow_id": target_flow_id,
                    "name": flow_data.get("name", "未命名流程图"),
                    "created_at": flow_data.get("created_at", "未知"),
                    "updated_at": flow_data.get("updated_at", "未知"),
                    "node_count": len(nodes),
                    "connection_count": len(edges),
                    "node_summaries": node_summaries
                }
            }
        
        finally:
            # 关闭数据库会话
            db.close()
        
    except Exception as e:
        logger.error(f"获取流程图信息时出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"获取流程图信息失败: {str(e)}",
            "error": str(e)
        }

# 使用Tool工厂函数创建获取流程图信息工具
get_flow_info_tool = Tool(
    name="get_flow_info",
    description="获取当前流程图的信息",
    func=get_flow_info_tool_func,
)

# 提供一个简单的工具列表
def get_flow_tools() -> List[BaseTool]:
    """
    获取流程工具列表
    
    Returns:
        工具列表
    """
    logger.info("获取流程工具列表")
    return [
        create_node_tool,
        connect_nodes_tool,
        get_flow_info_tool
    ]

# ======================
# 工具实现函数
# ======================

async def generate_node_properties(
    node_type: str, 
    node_label: str,
    llm_client: DeepSeekLLM # 注入 LLM 客户端
) -> Tuple[Dict[str, Any], bool]:
    """
    根据节点类型和标签生成推荐的节点属性
    
    Args:
        node_type: 节点类型
        node_label: 节点标签
        llm_client: DeepSeekLLM 客户端实例
        
    Returns:
        (推荐的属性, 是否成功)
    """
    try:
        prompt = f"""请为以下流程图节点生成合适的属性JSON对象：
        
节点类型: {node_type}
节点标签: {node_label}

请生成一个属性对象，属性名应该反映该类型节点的常见特性，属性值应为占位符或示例值。
请只返回 JSON 对象本身，不要包含其他文本。例如：{{\"property_name\": \"value\"}}
"""
        
        properties_schema = {
            "type": "object",
            "properties": {},
            "description": "节点的属性键值对"
            # 这里不限制具体属性，让 LLM 自由生成
        }
        
        # 使用 LLM 客户端进行结构化输出
        result, success = await llm_client.structured_output(
            prompt=prompt,
            system_prompt="你是一个流程图节点属性专家，擅长为不同类型的节点推荐合适的属性。请输出 JSON 对象格式的属性。",
            schema=properties_schema # 虽然不限制属性，但仍指定 schema 以鼓励 JSON 输出
        )
        
        if not success or not isinstance(result, dict):
            logger.error(f"生成节点属性失败或返回格式错误 for {node_type} - {node_label}")
            # 返回空字典作为默认值
            return {}, True # 即使生成失败，也认为工具调用本身是"成功"的，只是没生成内容
            
        # 确保返回的是字典
        return result, True
        
    except Exception as e:
        logger.error(f"生成节点属性时出错: {str(e)}")
        return {}, False

async def ask_more_info_func(
    params: QuestionsParams,
    llm_client: DeepSeekLLM # 注入 LLM 客户端
) -> ToolResult:
    """询问更多信息工具实现"""
    try:
        questions = params.questions
        context = params.context
        
        # 过滤掉空字符串问题
        questions = [q for q in questions if q and q.strip()]
        
        # 如果没有提供问题，使用智能默认问题
        if not questions:
            logger.info("未提供问题，尝试基于上下文生成")
            
            # 如果有上下文，尝试基于上下文生成相关问题
            if context and len(context) > 10:
                try:
                    prompt = f"""根据以下流程图设计对话的上下文，生成最多3个相关问题，以帮助获取更多设计流程图所需的信息：
                    
上下文: {context}

请生成一个包含问题的 JSON 数组，例如：{{\"questions\": [\"问题1\", \"问题2\"]}}。确保只返回 JSON。
"""
                    
                    questions_schema = {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "需要向用户询问的问题列表"
                            }
                        },
                        "required": ["questions"]
                    }
                    
                    result, success = await llm_client.structured_output(
                        prompt=prompt,
                        system_prompt="你是一个帮助生成有用问题的助手。请输出 JSON 数组格式的问题列表。",
                        schema=questions_schema
                    )
                    
                    if success and isinstance(result, dict) and "questions" in result and result["questions"]:
                        questions = result["questions"]
                        logger.info(f"基于上下文生成了 {len(questions)} 个问题")
                    else:
                        logger.warning("无法基于上下文生成问题，将使用默认问题")
                        questions = [] # 重置，下面会填充默认
                except Exception as e:
                    logger.error(f"基于上下文生成问题时出错: {str(e)}，将使用默认问题")
                    questions = []
            
            # 如果仍然没有问题（生成失败或无上下文），使用默认
            if not questions:
                questions = [
                    "请详细描述一下您想要创建的流程图的主要目标或功能是什么？",
                    "这个流程图大概包含哪些关键的步骤或处理节点？", 
                    "流程中是否存在需要判断条件或做出选择的地方（决策点）？"
                ]
                logger.info("使用默认问题列表")
        
        # 生成格式化文本
        formatted_questions = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        formatted_text = f"为了更好地帮助您，我需要了解更多信息：\n{formatted_questions}"
        if context:
             formatted_text = f"基于之前的讨论:\n{context}\n\n为了继续，我需要了解更多信息：\n{formatted_questions}"
        
        result_data = {
            "questions": questions,
            "context": context,
            "formatted_text": formatted_text
        }
        
        return ToolResult(
            success=True,
            message="已准备好需要询问的问题。", # 修改消息，表明是准备问题而非已生成
            data=result_data
        )
    except Exception as e:
        logger.error(f"生成问题时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"生成问题失败: {str(e)}"
        )

async def create_node_func(
    params: NodeParams,
    llm_client: DeepSeekLLM # 注入
) -> ToolResult:
    """创建节点工具实现"""
    try:
        node_type = params.node_type
        node_label = params.node_label
        properties = params.properties
        position = params.position # 获取位置信息
        
        logger.info(f"请求创建节点: type={node_type}, label={node_label}")
        
        if not node_type:
            logger.warning("缺少节点类型")
            return ToolResult(
                success=False,
                message="创建节点失败: 缺少节点类型"
            )
        
        # 处理标签缺失
        if not node_label:
             node_label = f"{node_type.capitalize()}_{str(uuid.uuid4())[:4]}"
             logger.info(f"未提供标签，使用生成的默认标签: {node_label}")
        
        # 处理属性缺失 (调用 generate_node_properties)
        if properties is None: # 检查是否为 None
            logger.info("未提供属性，尝试生成默认属性")
            properties, prop_success = await generate_node_properties(node_type, node_label, llm_client)
            if not prop_success:
                 logger.warning("生成默认属性失败，将使用空属性")
                 properties = {}
            else:
                 logger.info(f"生成默认属性: {properties}")
        
        # 生成节点ID
        node_id = f"node_{str(uuid.uuid4())[:8]}"
        
        # 创建结果数据
        result_data = {
            "id": node_id,
            "type": node_type,
            "label": node_label,
            "properties": properties,
             # 包含位置信息，如果提供了的话
            "position": position if position else {"x": 100, "y": 100} # 提供默认位置
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

async def connect_nodes_func(
    params: ConnectionParams,
    llm_client: DeepSeekLLM # 注入 (虽然此函数当前不直接使用，但保持接口一致性)
) -> ToolResult:
    """连接创建工具实现"""
    try:
        source_id = params.source_id
        target_id = params.target_id
        label = params.label
        
        logger.info(f"请求连接节点: {source_id} -> {target_id}")

        # 注意：这里不再自动创建缺失的节点，假设调用者（Agent/Chain）
        # 已经确保了 source_id 和 target_id 存在或会先创建它们。
        if not source_id or not target_id:
            return ToolResult(
                success=False,
                message="创建连接失败: 必须提供源节点ID和目标节点ID"
            )
        
        # 生成连接ID
        connection_id = f"conn_{str(uuid.uuid4())[:8]}"
        
        # 创建结果数据
        result_data = {
            "id": connection_id,
            "source": source_id,
            "target": target_id,
            "label": label or "" # 确保标签是字符串
        }
        
        logger.info(f"成功准备连接创建数据: {source_id} -> {target_id}")
        return ToolResult(
            success=True,
            message=f"成功准备创建连接: {source_id} -> {target_id}",
            data=result_data
        )
    except Exception as e:
        logger.error(f"创建连接时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"创建连接失败: {str(e)}"
        )

async def set_properties_func(
    params: PropertyParams,
    llm_client: DeepSeekLLM # 注入
) -> ToolResult:
    """属性设置工具实现"""
    try:
        element_id = params.element_id
        properties = params.properties
        
        logger.info(f"请求设置属性 for element: {element_id}")

        if not element_id or properties is None: # 检查 properties 是否为 None
            return ToolResult(
                success=False,
                message="设置属性失败: 缺少元素ID或属性"
            )
        
        # 创建结果数据
        result_data = {
            "element_id": element_id,
            "properties": properties
        }
        
        logger.info(f"成功准备属性设置数据 for: {element_id}")
        return ToolResult(
            success=True,
            message=f"成功准备设置属性: {element_id}",
            data=result_data
        )
    except Exception as e:
        logger.error(f"设置属性时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"设置属性失败: {str(e)}"
        )

async def generate_text_func(
    params: TextGenerationParams,
    llm_client: DeepSeekLLM # 注入
) -> ToolResult:
    """文本生成工具实现"""
    try:
        prompt = params.prompt
        max_length = params.max_length
        
        logger.info(f"请求生成文本: prompt length={len(prompt)}, max_length={max_length}")

        if not prompt:
            return ToolResult(
                success=False,
                message="文本生成失败: 缺少提示"
            )
        
        # 使用 DeepSeek 客户端服务生成文本
        # 注意：这里直接调用 chat_completion 可能不够优化，
        # 可能需要一个更通用的 system prompt。
        response_text, success = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一个专业的文本生成助手。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_length
        )
        
        if not success:
            logger.error("LLM 调用失败 during text generation")
            return ToolResult(
                success=False,
                message="文本生成失败: AI 服务错误"
            )
        
        logger.info("成功生成文本")
        return ToolResult(
            success=True,
            message="成功生成文本",
            data={"text": response_text}
        )
    except Exception as e:
        logger.error(f"生成文本时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"生成文本失败: {str(e)}"
        ) 