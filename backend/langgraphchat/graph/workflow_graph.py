"""
定义和编译 LangGraph 工作流图。

该模块负责构建用于处理聊天交互、管理状态以及调用工具（特别是与流程图操作相关的工具）的 LangGraph 状态图。

它定义了图的结构（节点、边、入口点、条件路由），并将具体的节点实现逻辑委托给其他模块。

提供了一个编译函数 `compile_workflow_graph` 来创建可执行的图实例。

"""

# Input-》advisor-》planner-》parameter-》
# exhibitor-》code generator-》code combination

from typing import List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from langchain_core.prompts import SystemMessagePromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, render_text_description
from langchain_core.runnables import RunnableConfig

from .agent_state import AgentState
from ..prompts.chat_prompts import STRUCTURED_CHAT_AGENT_PROMPT # For system prompt content
from ..prompts.dynamic_prompt_utils import get_dynamic_node_types_info
from ..tools import flow_tools # This should be the List[BaseTool]
from ..context import current_flow_id_var # Context variable for flow_id
import logging # Ensure logging is imported
import os # Make sure os is imported for listing files
import xml.etree.ElementTree as ET
import json
from functools import partial

# 导入工具，LLM, ChatService 等将在此处添加
# from ...app.services.chat_service import ChatService # 路径可能需要调整
# from ..tools.flow_tools import ... # 具体的工具或工具列表

# 获取日志记录器
logger = logging.getLogger(__name__)

# --- 导入节点和条件逻辑实现 --- (这部分应该在 logger 定义之后)
from .nodes.input_handler import input_handler_node # Will be used
from .nodes.planner import planner_node # Will be used
from .nodes.tool_executor import tool_node # Already configured to be used
from .conditions import should_continue

# REMOVING LOCAL DEFINITION of input_handler_node. 
# The version from .nodes.input_handler will be used via the import above.

# REMOVING LOCAL DEFINITION of planner_node.
# The version from .nodes.planner will be used via the import above.

# REMOVING THE LOCAL DEFINITION of tool_node that was here. 
# The version from .nodes.tool_executor will be used via the import above.

# Conditional edge: determines whether to continue with tools or end
def should_continue(state: AgentState) -> str:
    """
    条件边：决定 Planner 节点之后的下一个状态。

    检查状态中最后一条消息是否是包含工具调用 (tool_calls) 的 AIMessage。
    如果是，则路由到 "tools" 节点执行工具。
    否则，流程结束 (END)。
    """
    messages = state.get("messages", [])
    if not messages:
        # 如果没有任何消息，通常不应该发生，但为了安全起见结束
        logger.warning("should_continue: No messages found in state, ending.")
        return END

    last_message = messages[-1]
    if isinstance(last_message, AIMessage):
        if last_message.tool_calls:
            logger.info("should_continue: AIMessage has tool_calls, routing to 'tools'.")
            return "tools"
        else:
            logger.info("should_continue: AIMessage has no tool_calls, ending.")
            return END
    else:
        # 如果最后一条消息不是 AIMessage（例如是 HumanMessage 或 ToolMessage），
        # 这通常意味着流程应该结束或出现了意外状态
        logger.info(f"should_continue: Last message is not AIMessage (type: {type(last_message)}), ending.")
        return END

# Graph compilation
def compile_workflow_graph(llm: BaseChatModel, custom_tools: List[BaseTool] = None) -> StateGraph:
    """
    编译并返回 LangGraph 工作流图实例。

    Args:
        llm: 用于 Planner 节点的 BaseChatModel 实例。
        custom_tools: 可选的工具列表。如果提供，则使用这些工具；否则使用默认的 `flow_tools`。

    Returns:
        一个已编译的 LangGraph StateGraph 实例。
    """
    logger.info("Compiling workflow graph...")

    # 确定要使用的工具集
    tools_to_use = custom_tools if custom_tools is not None else flow_tools
    if not tools_to_use:
         logger.warning("Compiling workflow with an empty tool list.")
    else:
         logger.info(f"Compiling workflow with tools: {[t.name for t in tools_to_use]}")


    # --- 准备 Planner 的系统提示模板 ---
    # 1. 获取基础模板字符串
    # 假设 STRUCTURED_CHAT_AGENT_PROMPT 的第一个消息是系统提示模板
    if not (STRUCTURED_CHAT_AGENT_PROMPT.messages and
            isinstance(STRUCTURED_CHAT_AGENT_PROMPT.messages[0], SystemMessagePromptTemplate) and
            hasattr(STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt, 'template')):
        logger.error("System prompt template structure is not as expected. Using a fallback.")
        raw_system_template = "You are a helpful assistant. Use the available tools if necessary. Context: {flow_context}"
    else:
        raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template

    # 2. 渲染工具描述和名称（静态部分）
    rendered_tools_desc = render_text_description(tools_to_use)
    tool_names_list_str = ", ".join([t.name for t in tools_to_use])

    # 3. 获取动态节点类型信息
    try:
        node_types_description = get_dynamic_node_types_info()
    except Exception as e:
        logger.error(f"Error getting dynamic node types info: {e}")
        node_types_description = "(获取节点类型信息时出错)\n"

    # 4. 部分格式化系统提示模板，填入静态信息
    #    动态的 {flow_context} 将在 planner_node 中根据每次调用的状态填入
    #    确保模板中确实包含这些占位符
    system_prompt_template_for_planner = raw_system_template
    placeholders_to_fill = {
        "{tools}": rendered_tools_desc,
        "{tool_names}": tool_names_list_str,
        "{NODE_TYPES_INFO}": node_types_description
    }
    for placeholder, value in placeholders_to_fill.items():
        if placeholder in system_prompt_template_for_planner:
            system_prompt_template_for_planner = system_prompt_template_for_planner.replace(placeholder, value)
        else:
            logger.warning(f"Placeholder '{placeholder}' not found in the system prompt template provided by STRUCTURED_CHAT_AGENT_PROMPT.")

    # --- 创建和配置 StateGraph ---
    workflow = StateGraph(AgentState)

    # 使用 functools.partial 绑定参数到节点函数
    # 这使得节点函数只需要接收 state 参数，其他依赖（如 llm, tools）在编译时注入
    bound_input_handler_node = partial(input_handler_node)
    bound_planner_node = partial(
        planner_node,
        llm=llm,
        tools=tools_to_use,
        system_message_template=system_prompt_template_for_planner # 传递部分格式化的模板
    )
    bound_tool_node = partial(
        tool_node, 
        tools=tools_to_use
    )

    # 添加节点到图
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("planner", bound_planner_node)
    workflow.add_node("tools", bound_tool_node)

    # 设置图的入口点
    workflow.set_entry_point("input_handler")

    # 定义节点间的边
    workflow.add_edge("input_handler", "planner") # 输入处理后总是到规划器

    # 从规划器出发的条件边
    workflow.add_conditional_edges(
        "planner",          # 源节点
        should_continue,    # 判断函数
        {                   # 目标映射
            "tools": "tools", # 如果 should_continue 返回 "tools"
            END: END,         # 如果 should_continue 返回 END
        }
    )

    # 从工具节点回到规划器节点
    workflow.add_edge("tools", "planner") # 工具执行完毕后，回到规划器处理结果

    # 编译图
    logger.info("Workflow graph compilation complete.")
    return workflow.compile()
