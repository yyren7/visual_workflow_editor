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
from .nodes.robot_flow_planner import planner_node # Will be used
from .nodes.tool_executor import tool_node # Already configured to be used
from .nodes.task_router import task_router_node # Import RouteDecision if needed here, or ensure AgentState handles it
from .nodes.teaching_node import teaching_node
from .nodes.ask_info_node import ask_info_node
from .conditions import should_continue, route_after_task_router # RouteDecision is now in types
from .types import RouteDecision # Import RouteDecision from types


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

# --- 新增：处理重新输入的节点（如果需要明确提示用户）---
# 这个节点可以用来向用户明确地发送"请重新输入"的消息
# 或者，这个逻辑可以合并到 task_router_node 内部
async def rephrase_request_node(state: AgentState) -> dict:
    """
    如果 task_router 决定需要用户重新澄清，这个节点可以添加一个提示消息。
    然后流程会回到 task_router。
    """
    # 从 state 中获取 task_router 的原始意图总结（如果存在）
    decision = state.get("task_route_decision")
    llm_summary = decision.user_intent if decision else "我不确定您的意思。"

    # 创建提示用户重新输入的消息
    # TODO: 思考这个消息应该由谁发出，以及如何更好地融入对话历史
    # 一种可能是，task_router 在判断为 rephrase 时，自己就返回一个包含引导的 AIMessage
    # 这样就不需要一个单独的 rephrase_request_node，直接在 task_router 条件路由回 task_router 即可
    # 目前的设计是 task_router 返回 next_node="rephrase"，然后条件路由回 task_router
    # task_router 节点在再次被调用时，会处理最新的用户输入。
    # 如果需要明确的系统提示，可以在 task_router 内部检查是否是 "rephrase" 后的再次调用。

    # 为了简化，我们先不在 state 中添加额外的消息，
    # 而是依赖 task_router 在下一次调用时处理新的用户输入。
    # 如果需要更明确的提示，可以在 task_router_node 的开头检查
    # state 中是否有之前的 "rephrase" 信号，并相应调整其初始行为或提示。

    # 此处，我们仅打印日志，因为 task_router 自身会重新处理输入。
    # 如果要在此节点添加消息到 state['messages']，需要确保消息的来源和类型是合适的。
    logger.info("Rephrase request: Prompting user to rephrase or provide more details.")
    # 返回空字典，因为我们不直接修改主要的状态（如 messages）
    # 路由将通过条件边完成
    return {}


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
    # 新节点绑定
    bound_task_router_node = partial(task_router_node, llm=llm) # task_router 也需要 llm
    bound_teaching_node = partial(teaching_node) # 假设 teaching_node 不需要额外参数
    bound_ask_info_node = partial(ask_info_node) # 假设 ask_info_node 不需要额外参数
    # bound_rephrase_request_node = partial(rephrase_request_node)


    # 添加节点到图
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("task_router", bound_task_router_node) # 新增 task_router 节点
    workflow.add_node("planner", bound_planner_node)
    workflow.add_node("tools", bound_tool_node)
    workflow.add_node("teaching", bound_teaching_node) # 新增 teaching 节点
    workflow.add_node("ask_info", bound_ask_info_node) # 新增 ask_info 节点
    # workflow.add_node("rephrase_requester", bound_rephrase_request_node) # 新增 rephrase 节点


    # 设置图的入口点
    workflow.set_entry_point("input_handler")

    # 定义节点间的边
    workflow.add_edge("input_handler", "task_router") # 输入处理后到 task_router

    # 从 task_router 出发的条件边
    workflow.add_conditional_edges(
        "task_router",
        route_after_task_router, # 使用新的条件函数
        {
            "planner": "planner",
            "teaching": "teaching",
            "ask_info": "ask_info",
            "task_router": "task_router", # 如果 route_after_task_router 返回 "task_router" (用于rephrase)
            END: END # 新增：如果 route_after_task_router 返回 END (用于end_session)
        }
    )
    
    # 如果使用了 rephrase_requester 节点，它处理完后应该回到 task_router
    # workflow.add_edge("rephrase_requester", "task_router")


    # 从规划器出发的条件边
    workflow.add_conditional_edges(
        "planner",          # 源节点
        should_continue,    # 判断函数
        {                   # 目标映射
            "tools": "tools", # 如果 should_continue 返回 "tools"
            END: END         # 新增：如果 should_continue 返回 END (langgraph.graph.END)
        }
    )

    # 从工具节点回到规划器节点
    workflow.add_edge("tools", "planner") # 工具执行完毕后，回到规划器处理结果

    # teaching 节点执行完毕后也导向 END
    workflow.add_edge("teaching", END)
    # ask_info 节点执行完毕后导向 END (根据之前的修改)
    workflow.add_edge("ask_info", END)

    # 编译图
    logger.info("Workflow graph compilation complete.")
    return workflow.compile()
