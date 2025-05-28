import logging
from langgraph.graph import END
from langchain_core.messages import AIMessage
from .agent_state import AgentState # Adjusted relative import for AgentState
# from typing import Literal # No longer needed here
# from pydantic import BaseModel, Field # No longer needed here

logger = logging.getLogger(__name__)

# RouteDecision definition moved to types.py

# 新的条件函数，用于 task_router 之后的路由
def route_after_task_router(state: AgentState) -> str:
    """
    根据 task_router_node 的决策进行路由。
    """
    decision = state.get("task_route_decision")
    if not decision:
        logger.warning("route_after_task_router: No task_route_decision found in state. Defaulting to rephrase (back to task_router).")
        return "rephrase" # 或者一个专门的错误处理节点

    next_node = decision.next_node
    logger.info(f"route_after_task_router: Routing to '{next_node}' based on LLM decision.")

    if next_node == "planner":
        return "planner"
    elif next_node == "teaching":
        return "teaching"
    elif next_node == "other_assistant":
        return "other_assistant"
    elif next_node == "rephrase":
        logger.info("route_after_task_router: LLM requested rephrase. Routing to rephrase_prompt node.")
        return "rephrase_prompt"
    elif next_node == "end_session":
        logger.info("route_after_task_router: LLM detected end_session. Routing to handle_goodbye_node.")
        return "handle_goodbye_node"
    else:
        logger.warning(f"route_after_task_router: Unknown next_node '{next_node}'. Defaulting to rephrase_prompt.")
        return "rephrase_prompt" # 安全回退，也应指向 rephrase_prompt

def should_continue(state: AgentState) -> str:
    """
    条件边：决定 Planner 节点之后的下一个状态。

    检查状态中最后一条消息是否是包含工具调用 (tool_calls) 的 AIMessage。
    如果是，则路由到 "tools" 节点执行工具。
    否则，流程应返回到 task_router 节点。
    """
    messages = state.get("messages", [])
    if not messages:
        logger.warning("should_continue: No messages found in state, routing to task_router as a fallback.")
        return "task_router" # 修改：无消息则返回 task_router

    last_message = messages[-1]
    if isinstance(last_message, AIMessage):
        if last_message.tool_calls:
            logger.info("should_continue: AIMessage has tool_calls, routing to 'tools'.")
            return "tools"
        else:
            logger.info("should_continue: AIMessage has no tool_calls, routing to 'task_router'.")
            return "task_router" # 修改：无工具调用则返回 task_router
    else:
        # 如果最后一条消息不是 AIMessage（例如是 HumanMessage 或 ToolMessage after tools run）,
        # 通常意味着工具执行完毕或者规划器直接回复，之后应该由 task_router 决定下一步
        logger.info(f"should_continue: Last message is not AIMessage (type: {type(last_message)}), routing to 'task_router'.")
        return "task_router" # 修改：其他情况也返回 task_router 