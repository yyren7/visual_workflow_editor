import logging
from typing import Dict, Any

from ..agent_state import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

async def ask_info_node(state: AgentState, **kwargs) -> Dict[str, Any]:
    """
    处理用户关于助手能力、工作范围等信息的询问。
    目前是一个占位符，后续可以添加具体的问答逻辑。
    """
    user_input_message = state.get("messages", [])[-1] # 获取最新的用户消息
    user_input = user_input_message.content if user_input_message else ""

    logger.info(f"Ask Info Node: Received input '{user_input[:100]}...'")

    # TODO: 实现信息咨询逻辑
    # 1. 根据用户输入，提供关于助手功能、使用方法等信息。
    # 2. 可以集成知识库或预设问答对。

    response_message = AIMessage(
        content=f"Ask Info Node: 您询问了关于助手的信息：'{user_input}'。我可以帮助您进行流程图编辑和示教点操作。请告诉我您想做什么。",
        additional_kwargs={"node": "ask_info"}
    )

    logger.info("Ask Info Node: Processing complete.")
    return {"messages": [response_message]} 