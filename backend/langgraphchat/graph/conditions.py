import logging
from langgraph.graph import END
from langchain_core.messages import AIMessage
from .agent_state import AgentState # Adjusted relative import for AgentState

logger = logging.getLogger(__name__)

def should_continue(state: AgentState) -> str:
    """
    条件边：决定 Planner 节点之后的下一个状态。

    检查状态中最后一条消息是否是包含工具调用 (tool_calls) 的 AIMessage。
    如果是，则路由到 "tools" 节点执行工具。
    否则，流程结束 (END)。
    """
    messages = state.get("messages", [])
    if not messages:
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
        logger.info(f"should_continue: Last message is not AIMessage (type: {type(last_message)}), ending.")
        return END 