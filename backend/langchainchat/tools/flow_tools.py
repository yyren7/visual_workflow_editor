from typing import Dict, Any, List, Optional, Type, Union, Tuple
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool, BaseTool
import logging
import uuid
import os
import json
import httpx
import asyncio
from sqlalchemy.orm import Session
from database.connection import get_db, get_db_context
from backend.app.services.flow_service import FlowService
from backend.app.services.flow_variable_service import FlowVariableService

# Import context variable
from backend.langchainchat.context import current_flow_id_var

# Use correct absolute path for logger import
from backend.langchainchat.utils.logging import logger

# Import Pydantic models and ToolResult
from .definitions import (
    NodeParams, ConnectionParams, PropertyParams, 
    QuestionsParams, TextGenerationParams, ToolResult
)
# Import the necessary LLM client class
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM

# --- 1. 定义同步工具函数 --- 
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
    
    Args:
        node_type: Type of the node.
        node_label: Label for the node (uses node_type if not provided).
        properties: Properties for the node.
        position: Position (x, y) for the node.
        node_name: Alias for node_label.
        label: Alias for node_label.
        type: Alias for node_type.
        **kwargs: Catch any other arguments.
        
    Returns:
        Node creation result.
    """
    try:
        # --- Get flow_id from context ---
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("创建节点失败：无法从上下文中获取当前的 flow_id")
            return {"success": False, "message": "无法获取当前流程ID", "error": "Context error: Missing flow_id"}
        # --------------------------------

        logger.info("=" * 40)
        logger.info(f"创建节点工具函数被调用 (Flow ID: {target_flow_id})")
        logger.info(f"节点类型参数: node_type={node_type}, type={type}")
        logger.info(f"节点标签参数: node_label={node_label}, node_name={node_name}, label={label}")
        
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
            if key not in ['node_type', 'node_label', 'position', 'node_name', 'label', 'type']:
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

        # 使用上下文管理器进行数据库操作
        try:
            logger.info(f"使用流程图ID: {target_flow_id}")

            # 使用上下文管理器获取db会话
            with get_db_context() as db:
                flow_service = FlowService(db)
                
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
                    data=flow_data,
                    name=flow_data.get("name") # Pass name explicitly if it exists in flow_data
                )
            
                if not success:
                    logger.error(f"更新流程图失败 for flow {target_flow_id}")
                    # Return success: False if DB update fails
                    return {
                        "success": False,
                        "message": f"创建节点 '{effective_label}' 成功，但更新数据库失败",
                        "error": "数据库更新失败",
                        "node_data": node_data # Still return the intended node data for context
                    }
                
                logger.info(f"节点创建并保存成功: {node_id}") # Updated log message
                logger.info("=" * 40)
                return {
                    "success": True,
                    "message": f"成功创建并保存节点: {effective_label} (类型: {node_type})", # Updated message
                    "node_data": node_data
                }
        except Exception as e:
            # This exception is for the API call block (getting flow, updating flow)
            logger.error(f"数据库操作失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"创建节点 '{effective_label}' 时数据库操作失败",
                "error": f"数据库错误: {str(e)}",
                "node_data": node_data # Return intended node data for context
            }
        
    except Exception as e:
        # This is for general errors before DB operations
        logger.error(f"创建节点准备阶段出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        logger.info("=" * 40)
        return {
            "success": False,
            "message": f"创建节点准备阶段失败: {str(e)}",
            "error": str(e)
        }

def connect_nodes_tool_func(
    source_id: str,
    target_id: str,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Connects two nodes in the current workflow diagram."""
    try:
        # --- Get flow_id from context ---
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("连接节点失败：无法从上下文中获取当前的 flow_id")
            return {"success": False, "message": "无法获取当前流程ID", "error": "Context error: Missing flow_id"}
        # --------------------------------
        
        logger.info(f"连接节点: {source_id} -> {target_id} (Flow ID: {target_flow_id})")
        
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
        
        # 使用上下文管理器进行数据库操作
        try:
            logger.info(f"使用流程图ID: {target_flow_id}")

            # 使用上下文管理器获取db会话
            with get_db_context() as db:
                flow_service = FlowService(db)
                
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
                    data=flow_data,
                    name=flow_data.get("name") # 明确传递 name
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

def get_flow_info_tool_func(
    # No parameters needed from LLM anymore
    # flow_id: Optional[str] = None # Removed
) -> Dict[str, Any]:
    """Retrieves information about the current workflow (nodes, connections, variables)."""
    try:
        # --- Get flow_id from context ---
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("获取流程图信息失败：无法从上下文中获取当前的 flow_id")
            return {"success": False, "message": "无法获取当前流程ID", "error": "Context error: Missing flow_id"}
        # --------------------------------
        
        logger.info(f"获取流程图信息 (Flow ID: {target_flow_id})")
        
        # DB operations using target_flow_id (Copied and adapted)
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

def retrieve_context_func(
    # Remove flow_id parameter
    query: str, 
    # flow_id: Optional[str] = None # Removed
) -> Dict[str, Any]:
    """Searches the knowledge base for context relevant to the user's query."""
    # --- Get flow_id from context (but retrieval might not actually use it yet) ---
    # target_flow_id = current_flow_id_var.get() # We get it, but the RAG logic might not use it.
    # logger.info(f"检索上下文: 查询='{query[:50]}...', Flow ID (from context): {target_flow_id}")
    # Let's keep the original logging for now, as RAG might not be flow-specific yet
    logger.info(f"检索上下文: 查询='{query[:50]}...'") 
    # -----------------------------------------------------------------------------
    try:
        with get_db_context() as db:
            from database.embedding.service import DatabaseEmbeddingService
            from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
            embedding_service = DatabaseEmbeddingService() 
            retriever = EmbeddingRetriever(db_session=db, embedding_service=embedding_service)
            
            # Async retrieval logic (Copied)
            try:
                import asyncio
                try: loop = asyncio.get_running_loop()
                except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
                documents = loop.run_until_complete(retriever._aget_relevant_documents(query, run_manager=None))
            except Exception as async_err:
                 logger.error(f"调用异步检索时出错: {async_err}. 尝试同步方法 (可能为空).")
                 documents = retriever._get_relevant_documents(query, run_manager=None)

            if not documents:
                return {"success": True, "message": "未找到相关信息。", "retrieved_context": "未找到相关信息。"}

            formatted_docs = "\n\n---\n\n".join([
                f"来源: {doc.metadata.get('source', '未知')}\n内容: {doc.page_content}" 
                for doc in documents
            ])
            logger.info(f"成功检索到 {len(documents)} 个文档。")
            return {"success": True, "message": f"成功检索到 {len(documents)} 条相关信息。", "retrieved_context": formatted_docs}

    except Exception as e:
        logger.error(f"检索上下文时出错: {e}", exc_info=True)
        return {"success": False, "message": f"检索信息时出错: {e}", "retrieved_context": "检索信息时出错。"}

# --- 2. 定义 Pydantic V2 Schema --- 
class CreateNodeSchema(BaseModel):
    # Remove flow_id field
    node_type: str = Field(description="The type of the node to create.")
    node_label: Optional[str] = Field(None, description="The label for the node. Uses node_type if not provided.")
    properties: Optional[Dict[str, Any]] = Field(None, description="Properties for the node.")
    position: Optional[Dict[str, float]] = Field(None, description="Position (x, y) for the node.")
    # flow_id: Optional[str] = Field(description="The ID of the workflow to add the node to.") # Removed

class ConnectNodesSchema(BaseModel):
    # Remove flow_id field
    source_id: str = Field(description="The ID of the source node.")
    target_id: str = Field(description="The ID of the target node.")
    label: Optional[str] = Field(None, description="Label for the connection.")
    # flow_id: Optional[str] = Field(description="The ID of the workflow where the connection belongs.") # Removed

class GetFlowInfoSchema(BaseModel):
    # Remove flow_id field - No fields needed from LLM
    pass # Tool now takes no arguments from LLM

class RetrieveContextSchema(BaseModel):
    # Remove flow_id field
    query: str = Field(description="The user query to search for relevant context.")
    # flow_id: Optional[str] = Field(None, description="(Optional) The ID of the current workflow to scope the search.") # Removed

# --- 3. 创建 StructuredTool 实例 --- 
create_node_tool = StructuredTool.from_function(
    func=create_node_tool_func,
    name="create_node",
    description="Creates a new node in the current workflow diagram. Specify node type, label, position, and properties.", # Removed flow_id mention
    args_schema=CreateNodeSchema
)

connect_nodes_tool = StructuredTool.from_function(
    func=connect_nodes_tool_func,
    name="connect_nodes",
    description="Connects two nodes in the current workflow diagram using their source_id and target_id.", # Removed flow_id mention
    args_schema=ConnectNodesSchema
)

get_flow_info_tool = StructuredTool.from_function(
    func=get_flow_info_tool_func,
    name="get_flow_info",
    description="Retrieves information about the current workflow, such as nodes, connections, and variables.", # Removed flow_id mention
    args_schema=GetFlowInfoSchema # Schema now has no args
)

retrieve_context_tool = StructuredTool.from_function(
    func=retrieve_context_func,
    name="retrieve_context",
    description="Searches the knowledge base for context relevant to the user's query. Use this before answering questions that require external knowledge.",
    args_schema=RetrieveContextSchema # Removed flow_id mention
)

# --- 4. 导出工具列表 (保持不变) --- 
flow_tools: List[BaseTool] = [create_node_tool, connect_nodes_tool, get_flow_info_tool, retrieve_context_tool]

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