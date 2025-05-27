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
# from .nodes.planner import planner_node # 旧的 planner，将被移除或替换
from .nodes.tool_executor import tool_node # Already configured to be used
from .nodes.task_router import task_router_node # Import RouteDecision if needed here, or ensure AgentState handles it
from .nodes.teaching_node import teaching_node
from .nodes.other_assistant_node import other_assistant_node # Changed from ask_info_node
from .nodes.robot_flow_invoker_node import robot_flow_invoker_node # 新的调用节点
from .nodes.rephrase_prompt_node import rephrase_prompt_node # <-- 新增导入
from .conditions import should_continue, route_after_task_router # RouteDecision is now in types
from .graph_types import RouteDecision # Import RouteDecision from types


# Conditional edge for the old planner (will be removed or re-purposed if needed)
# def should_continue(state: AgentState) -> str:
# \"\"\"
# 条件边：决定 Planner 节点之后的下一个状态。
# \"\"\"
# messages = state.get("messages", [])
# if not messages:
# logger.warning("should_continue: No messages found in state, ending.")
# return END
# last_message = messages[-1]
# if isinstance(last_message, AIMessage):
# if last_message.tool_calls:
# logger.info("should_continue: AIMessage has tool_calls, routing to 'tools'.")
# return "tools"
# else:
# logger.info("should_continue: AIMessage has no tool_calls, ending.")
# return END
# else:
# logger.info(f"should_continue: Last message is not AIMessage (type: {type(last_message)}), ending.")
# return END
# The should_continue logic might not be needed if robot_flow_invoker_node always goes to END or handles its own loop.

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

def route_after_functional_node(state: AgentState) -> str:
    """
    在功能节点（如 robot_flow_planner, teaching, other_assistant）执行完毕后进行路由。
    检查子图是否需要澄清，或者任务是否完成/出错。
    """
    logger.info(f"--- Routing after Functional Node. Subgraph status: {state.get('subgraph_completion_status')}, Current Task Route: {state.get('task_route_decision')}")
    
    subgraph_status = state.get("subgraph_completion_status")

    if subgraph_status == "needs_clarification":
        logger.info("Functional node/subgraph needs clarification. Routing to input_handler to await user input.")
        # task_route_decision 和 user_request_for_router 应该已被 invoker_node 保留
        # subgraph_completion_status 也保留，以便 input_handler 或后续节点知道上下文
        return "input_handler"
    elif subgraph_status in ["completed_success", "error"]:
        logger.info(f"Subgraph completed with status: {subgraph_status}. Resetting task context and routing to input_handler for new cycle.")
        state["task_route_decision"] = None
        state["user_request_for_router"] = None
        state["subgraph_completion_status"] = None # 清除状态
        return "input_handler"
    else: # subgraph_status is None (it was a simple functional node like teaching/other_assistant)
        logger.info(f"Simple functional node completed (status: {subgraph_status}). Resetting task context and routing to END to signify turn completion.")
        state["task_route_decision"] = None # Task is done for this turn.
        state["user_request_for_router"] = None # Request was processed.
        state["subgraph_completion_status"] = None # Ensure it's cleared.
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
    tools_to_use = custom_tools if custom_tools is not None else flow_tools # tools_to_use is for the old planner's tool_node
    # The new robot_flow_invoker_node and its subgraph will manage their own tools.
    # So, `tools_to_use` and related system prompt parts might be less relevant for the main graph's planner path.
    # However, if other parts of the main graph use tools, this remains necessary.
    # For now, we keep it as is, as the `tool_node` is still part of the graph, though not directly after the new planner.

    # --- 准备 Planner 的系统提示模板 (这部分是为旧 planner 准备的) ---
    # 如果新的 robot_flow_invoker_node 不需要特定的系统提示模板注入，
    # 或者它内部处理自己的提示，这部分可能不再直接用于 "planner" 路径。
    # 暂时保留，以防其他节点可能间接使用。
    if not (STRUCTURED_CHAT_AGENT_PROMPT.messages and
            isinstance(STRUCTURED_CHAT_AGENT_PROMPT.messages[0], SystemMessagePromptTemplate) and
            hasattr(STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt, 'template')):
        logger.error("System prompt template structure is not as expected. Using a fallback.")
        raw_system_template = "You are a helpful assistant. Use the available tools if necessary. Context: {flow_context}"
    else:
        raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template

    rendered_tools_desc = render_text_description(tools_to_use if tools_to_use else []) # Handle empty tools_to_use
    tool_names_list_str = ", ".join([t.name for t in tools_to_use] if tools_to_use else [])

    try:
        node_types_description = get_dynamic_node_types_info()
    except Exception as e:
        logger.error(f"Error getting dynamic node types info: {e}")
        node_types_description = "(获取节点类型信息时出错)\\n"

    system_prompt_template_for_planner = raw_system_template # This might not be used by new invoker node
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

    bound_input_handler_node = partial(input_handler_node)
    
    # 绑定新的 robot_flow_invoker_node，它也需要 llm
    bound_robot_flow_invoker_node = partial(robot_flow_invoker_node, llm=llm)
    
    # 旧的 planner_node 和 tool_node 暂时保留，以防万一，但它们不再是主要的规划路径
    # from .nodes.planner import planner_node # Make sure this is not accidentally re-imported if deleted above
    # bound_planner_node = partial(
    # planner_node, # This would cause NameError if planner_node import is removed
    # llm=llm,
    # tools=tools_to_use,
    # system_message_template=system_prompt_template_for_planner
    # )
    # bound_tool_node = partial(
    # tool_node, 
    # tools=tools_to_use
    # )
    
    # 新节点绑定
    bound_task_router_node = partial(task_router_node, llm=llm) 
    bound_teaching_node = partial(teaching_node, llm=llm)
    bound_other_assistant_node = partial(other_assistant_node) # Changed from bound_ask_info_node and ask_info_node
    bound_rephrase_prompt_node = partial(rephrase_prompt_node) # <-- 新增绑定


    # 添加节点到图
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("task_router", bound_task_router_node) 
    workflow.add_node("robot_flow_planner", bound_robot_flow_invoker_node) # 新的规划器节点
    # workflow.add_node("planner", bound_planner_node) # 旧的 planner 节点，移除
    # workflow.add_node("tools", bound_tool_node) # 旧的 tools 节点，如果不再需要，也可以移除
    workflow.add_node("teaching", bound_teaching_node) 
    workflow.add_node("other_assistant", bound_other_assistant_node) # Changed from ask_info
    workflow.add_node("rephrase_prompt", bound_rephrase_prompt_node) # <-- 添加新节点


    # 设置图的入口点
    workflow.set_entry_point("input_handler")

    # 定义节点间的边
    workflow.add_edge("input_handler", "task_router")

    # 从 task_router 出发的条件边
    workflow.add_conditional_edges(
        "task_router",
        route_after_task_router,
        {
            "planner": "robot_flow_planner", # 路由到新的机器人流程规划器
            "teaching": "teaching",
            "other_assistant": "other_assistant", # Changed from ask_info
            "rephrase": "rephrase_prompt",  # <-- 修改 rephrase 路由
            END: END 
        }
    )
    
    # 从功能节点出来后，进行统一路由处理
    workflow.add_conditional_edges(
        "robot_flow_planner",
        route_after_functional_node,
        {
            "input_handler": "input_handler",
            END: END # Handle case where it might end
        }
    )
    workflow.add_conditional_edges(
        "teaching",
        route_after_functional_node,
        {
            "input_handler": "input_handler", # Should not happen for simple nodes unless they can ask for clarification
            END: END # Normal completion routes to END
        }
    )
    workflow.add_conditional_edges(
        "other_assistant",
        route_after_functional_node,
        {
            "input_handler": "input_handler", # Should not happen for simple nodes
            END: END # Normal completion routes to END
        }
    )

    # 新增：从 rephrase_prompt 节点出来的边，固定到 END
    workflow.add_edge("rephrase_prompt", END)

    # 旧的 planner 和 tools 相关的边被移除
    # workflow.add_conditional_edges(
    # "planner",
    # should_continue,
    # {
    # "tools": "tools",
    #         END: END
    #     }
    # )
    # workflow.add_edge("tools", "planner")

    # teaching 节点执行完毕后也导向 END # 旧逻辑，已通过上面条件边处理
    # workflow.add_edge("teaching", END)
    # other_assistant 节点执行完毕后导向 END (Changed from ask_info) # 旧逻辑，已通过上面条件边处理
    # workflow.add_edge("other_assistant", END)

    # 编译图
    logger.info("Workflow graph compilation complete.")
    return workflow.compile()
