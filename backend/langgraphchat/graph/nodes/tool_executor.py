import logging
from typing import List

from langgraph.prebuilt import ToolNode
from langchain_core.tools import BaseTool

from ..agent_state import AgentState # Adjusted relative import for AgentState

logger = logging.getLogger(__name__)

async def tool_node(state: AgentState, tools: List[BaseTool]) -> dict:
    """
    工具执行节点：使用 LangGraph 的 ToolNode 来执行 Agent 请求的工具。

    它接收包含工具调用请求的 AIMessage (通常是 messages 列表中的最后一条)，
    调用相应的工具，并将结果作为 ToolMessage 返回。
    """
    logger.info("Tool node: Executing tools...")
    
    tool_executor = ToolNode(tools)
    result = await tool_executor.ainvoke({"messages": state["messages"]})

    if "messages" in result and isinstance(result["messages"], list):
         logger.info(f"Tool node: Finished execution, returning {len(result['messages'])} ToolMessage(s).")
    else:
         logger.warning(f"Tool node: Execution finished but result format might be unexpected: {result}")

    return result 