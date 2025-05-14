from typing import List
from langchain_core.tools import BaseTool

# Import Pydantic models and ToolResult that might still be referenced or re-exported
# (though most specific Pydantic models for tools are now within their respective modules or in .definitions)
from .definitions import (
    NodeParams, ConnectionParams, PropertyParams, 
    QuestionsParams, TextGenerationParams, ToolResult
)

# Import StructuredTool instances from their new modules
from .tool_modules.create_node import create_node_structured_tool
from .tool_modules.connect_nodes import connect_nodes_tool
from .tool_modules.get_flow_info import get_flow_info_tool
from .tool_modules.retrieve_context import retrieve_context_tool

# Import async tool functions from their new modules
from .tool_modules.agent_ask_more_info import ask_more_info_func
from .tool_modules.agent_connect_nodes import connect_nodes_func
from .tool_modules.agent_set_properties import set_properties_func
from .tool_modules.agent_generate_text import generate_text_func

# --- 4. 导出工具列表 (保持不变) --- 
flow_tools: List[BaseTool] = [create_node_structured_tool, connect_nodes_tool, get_flow_info_tool, retrieve_context_tool] 