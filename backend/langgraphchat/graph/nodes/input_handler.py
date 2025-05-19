import logging
from typing import List
from langchain_core.messages import HumanMessage, BaseMessage
from ..agent_state import AgentState # Adjusted relative import for AgentState

logger = logging.getLogger(__name__)

async def input_handler_node(state: AgentState) -> dict:
    """
    处理 state['input'] 字段，将其转换为 HumanMessage 并有条件地添加到 messages 列表中。

    此节点确保每个用户输入只被转换为 HumanMessage 并添加到状态一次，
    避免因图的循环执行导致重复添加相同的用户消息。
    它通过检查 'input_processed' 标志位和比较最后一条消息来实现。
    返回的字典仅包含需要通过 operator.add 更新到状态的字段（通常是 'messages' 和 'input_processed'）。
    """
    current_messages_from_state = list(state.get("messages", []))
    input_str = state.get("input")
    input_already_processed = state.get("input_processed", False)

    updated_state_dict = {}
    newly_added_message_for_operator_add = None

    if input_str and not input_already_processed:
        logger.info(f"Input handler: Processing new input: '{input_str}'")
        new_human_message = HumanMessage(content=input_str)

        should_add_new_message = False
        if (not current_messages_from_state or
            not (isinstance(current_messages_from_state[-1], HumanMessage) and
                 current_messages_from_state[-1].content == input_str)):
            should_add_new_message = True

        if should_add_new_message:
            newly_added_message_for_operator_add = new_human_message
            updated_state_dict["user_request_for_router"] = new_human_message.content
            logger.info(f"Input handler: Prepared new HumanMessage for appending and set user_request_for_router: {new_human_message.content}")
        else:
            logger.info("Input handler: Input string matches last HumanMessage; not preparing for append.")

        updated_state_dict["input_processed"] = True
        updated_state_dict["input"] = None
        logger.info("Input handler: Input processed flag set, input field cleared.")

    elif input_str and input_already_processed:
        logger.info(f"Input handler: Input '{input_str}' found but already marked processed. Clearing input field.")
        updated_state_dict["input"] = None
    
    if newly_added_message_for_operator_add:
        updated_state_dict["messages"] = [newly_added_message_for_operator_add]

    return updated_state_dict 