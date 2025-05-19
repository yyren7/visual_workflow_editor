from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class ToolType(str, Enum):
    """工具类型"""
    NODE_CREATION = "node_creation"
    CONNECTION_CREATION = "connection_creation"
    PROPERTY_SETTING = "property_setting"
    ASK_MORE_INFO = "ask_more_info"
    TEXT_GENERATION = "text_generation"

class NodeParams(BaseModel):
    """节点创建参数"""
    node_type: str
    node_label: str
    position: Optional[Dict[str, float]] = None
    properties: Optional[Dict[str, Any]] = None

class ConnectionParams(BaseModel):
    """节点连接参数"""
    source_id: str
    target_id: str
    label: Optional[str] = None
    
class PropertyParams(BaseModel):
    """属性设置参数"""
    element_id: str # 可以是节点ID或连接ID
    properties: Dict[str, Any]

class QuestionsParams(BaseModel):
    """追加问题参数"""
    questions: List[str]
    context: Optional[str] = None

class TextGenerationParams(BaseModel):
    """文本生成参数"""
    prompt: str
    max_length: int = 500

class ToolCallRequest(BaseModel):
    """(旧) 工具调用请求 - 可能会被 LangChain Agent 调用格式取代"""
    tool_type: ToolType
    params: Dict[str, Any]
    description: Optional[str] = None

class ToolResult(BaseModel):
    """工具调用结果"""
    success: bool
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)

# ==========================
# LangChain 工具定义 (示例)
# ==========================
# 这些是给 LangChain Agent 使用的工具定义，
# 它们会引用 backend/langgraphchat/tools/flow_tools.py 中的具体实现函数。

# 示例：创建节点的工具定义 (需要与 flow_tools.py 中的函数关联)
# from langchain.tools import StructuredTool
# from .flow_tools import create_node_tool_func # 假设函数存在

# create_node_tool = StructuredTool.from_function(
#     func=create_node_tool_func,
#     name="create_node",
#     description="创建一个流程图节点",
#     args_schema=NodeParams
# )

# connect_nodes_tool = StructuredTool.from_function(...)
# set_properties_tool = StructuredTool.from_function(...)
# ask_more_info_tool = StructuredTool.from_function(...)
# generate_text_tool = StructuredTool.from_function(...)

# 工具列表，供 Agent 使用
# available_tools = [create_node_tool, connect_nodes_tool, ...]

# ==================================
# DeepSeek 函数调用定义 (示例)
# ==================================
# 这些是直接传递给 DeepSeek API 的函数调用 JSON 定义。

NODE_CREATION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "create_node",
        "description": "创建一个流程图节点",
        "parameters": NodeParams.model_json_schema()
    }
}

CONNECTION_CREATION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "connect_nodes",
        "description": "连接两个流程图节点",
        "parameters": ConnectionParams.model_json_schema()
    }
}

PROPERTY_SETTING_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "set_properties",
        "description": "设置节点或连接的属性",
        "parameters": PropertyParams.model_json_schema()
    }
}

ASK_MORE_INFO_TOOL_DEFINITION = {
     "type": "function",
     "function": {
         "name": "ask_more_info",
         "description": "当信息不足时，向用户询问更多问题",
         "parameters": QuestionsParams.model_json_schema()
     }
}

TEXT_GENERATION_TOOL_DEFINITION = {
     "type": "function",
     "function": {
         "name": "generate_text",
         "description": "根据提示生成文本内容",
         "parameters": TextGenerationParams.model_json_schema()
     }
}

# DeepSeek API 可用的工具列表
deepseek_tools_definition = [
    NODE_CREATION_TOOL_DEFINITION,
    CONNECTION_CREATION_TOOL_DEFINITION,
    PROPERTY_SETTING_TOOL_DEFINITION,
    ASK_MORE_INFO_TOOL_DEFINITION,
    TEXT_GENERATION_TOOL_DEFINITION
] 