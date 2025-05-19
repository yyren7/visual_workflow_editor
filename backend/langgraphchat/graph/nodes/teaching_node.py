import logging
from typing import Dict, Any

from ..agent_state import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

async def teaching_node(state: AgentState, **kwargs) -> Dict[str, Any]:
    """
    处理与示教点相关的任务。
    目前是一个占位符，后续可以添加保存、查询、修改、删除坐标点的逻辑。
    """
    user_input_message = state.get("messages", [])[-1] # 获取最新的用户消息
    user_input = user_input_message.content if user_input_message else ""

    logger.info(f"Teaching Node: Received input '{user_input[:100]}...'")

    # TODO: 实现示教点操作逻辑
    # 1. 解析用户输入，识别操作类型（保存、查询、删除等）和坐标信息。
    # 2. 与数据库或状态管理器交互来存储/检索坐标点。
    # 3. 构建响应消息。

    response_message = AIMessage(
        content=f"Teaching Node: 您希望进行示教点操作：'{user_input}'。此功能正在开发中。",
        additional_kwargs={"node": "teaching"}
    )

    logger.info("Teaching Node: Processing complete.")
    return {"messages": [response_message]} 