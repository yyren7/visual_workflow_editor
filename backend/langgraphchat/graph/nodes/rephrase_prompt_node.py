import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage
from ..agent_state import AgentState

logger = logging.getLogger(__name__)

async def rephrase_prompt_node(state: AgentState, **kwargs) -> Dict[str, Any]:
    """
    当 task_router 无法清晰理解用户意图并决定需要用户 rephrase 时，
    此节点负责向用户发送一条请求澄清的消息。
    """
    logger.info("Rephrase Prompt Node: Requesting user to rephrase their input.")

    # 从 state 中获取 task_router 对模糊输入的原始意图总结（如果存在且有用）
    # route_decision = state.get("task_route_decision")
    # llm_summary = route_decision.user_intent if route_decision and route_decision.user_intent else "您的指令不够清晰。"
    # clarification_message_content = f"抱歉，我不太理解您的意思 ({llm_summary})。您能换个方式描述您的需求吗？"
    
    # 使用一个更通用的澄清消息
    clarification_message_content = "抱歉，我不太理解您的意思。您能说得更具体一些，或者换个方式描述您的需求吗？"

    # 返回包含 AIMessage 的字典，以便将其添加到对话历史中
    # operator.add 通常用于 messages 列表
    return {"messages": [AIMessage(content=clarification_message_content, additional_kwargs={"node": "rephrase_prompt"})]} 