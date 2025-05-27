import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, BaseMessage
from ..agent_state import AgentState # Adjusted relative import for AgentState

logger = logging.getLogger(__name__)

async def input_handler_node(state: AgentState, **kwargs) -> Dict[str, Any]:
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

    # This will be the dictionary returned to update the state.
    # Start by ensuring user_request_for_router is part of what we might update.
    updated_state_dict: Dict[str, Any] = {}

    current_user_request: str | None = None
    subgraph_clarification_mode = state.get("subgraph_completion_status") == "needs_clarification"

    if subgraph_clarification_mode:
        current_user_request = state.get("user_request_for_router") # Presumed to be set by user's clarification input mechanism
        logger.info(
            f"Input Handler: In subgraph clarification mode. "
            f"Using user_request_for_router from state: '{current_user_request[:100] if current_user_request else 'None'}'"
        )
    elif current_messages_from_state and isinstance(current_messages_from_state[-1], HumanMessage):
        current_user_request = current_messages_from_state[-1].content.strip()
        logger.info(
            f"Input Handler: New turn or HumanMessage. Determined user_request_for_router: '{current_user_request[:100]}...'"
        )
    else:
        current_user_request = state.get("user_request_for_router") # Fallback, could be None
        logger.warning(
            f"Input Handler: No new HumanMessage and not in subgraph clarification. Fallback user_request_for_router: '{current_user_request[:100] if current_user_request else 'None'}'"
        )
    
    # Always update the user_request_for_router in the state based on the determination above.
    updated_state_dict["user_request_for_router"] = current_user_request

    # Process state["input"] to add it as a HumanMessage to state.messages if it's new.
    if input_str and not input_already_processed:
        logger.info(f"Input handler: Processing new state['input']: '{input_str}'")
        new_human_message = HumanMessage(content=input_str)

        should_add_new_message = False
        if (not current_messages_from_state or
            not (isinstance(current_messages_from_state[-1], HumanMessage) and
                 current_messages_from_state[-1].content == input_str)):
            should_add_new_message = True

        if should_add_new_message:
            # If new_human_message is to be added, include it in the messages update.
            # Note: The graph typically uses operator.add for messages, so we return a list with the new message.
            updated_state_dict["messages"] = [new_human_message]
            logger.info(f"Input handler: Adding new HumanMessage to state.messages: '{input_str}'")
        else:
            logger.info("Input handler: state['input'] matches last HumanMessage; not adding to state.messages again.")

        updated_state_dict["input_processed"] = True
        updated_state_dict["input"] = None # Clear state["input"] after processing
        logger.info("Input handler: state['input'] processed, flag set, field cleared.")

    elif input_str and input_already_processed:
        logger.info(f"Input handler: state['input'] '{input_str}' found but already marked processed. Clearing input field.")
        updated_state_dict["input"] = None # Still ensure input is cleared
    
    return updated_state_dict 