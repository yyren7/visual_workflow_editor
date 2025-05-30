import logging
from typing import Dict, Any, Optional
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

    updated_state_dict: Dict[str, Any] = {}
    new_human_message_to_add: Optional[HumanMessage] = None

    current_user_request_for_router: str | None = None
    subgraph_clarification_mode = state.get("subgraph_completion_status") == "needs_clarification"

    if subgraph_clarification_mode:
        # If in clarification mode, the new input_str IS the user's clarification.
        # This should become the user_request_for_router for the task_router.
        if input_str:
            logger.info(f"Input Handler: In subgraph clarification mode. Using new input '{input_str}' as user_request_for_router.")
            current_user_request_for_router = input_str
            # Also, this new input should be added as a HumanMessage if it's not already the last one.
            if (not current_messages_from_state or 
                not (isinstance(current_messages_from_state[-1], HumanMessage) and 
                     current_messages_from_state[-1].content == input_str)):
                new_human_message_to_add = HumanMessage(content=input_str)
            # Mark input as processed for this cycle.
            updated_state_dict["input_processed"] = True 
            updated_state_dict["input"] = None # Clear state["input"] as it's now captured
        else:
            # No new input provided in this cycle, but still in clarification mode.
            # Fallback to existing user_request_for_router if any (e.g. original intent summary).
            # This case might lead to re-prompting if task_router finds this insufficient.
            current_user_request_for_router = state.get("user_request_for_router")
            logger.info(
                f"Input Handler: In subgraph clarification mode but no new input string. "
                f"Using existing user_request_for_router: '{current_user_request_for_router[:100] if current_user_request_for_router else 'None'}'"
            )
    elif current_messages_from_state and isinstance(current_messages_from_state[-1], HumanMessage):
        # This typically means a new turn, not a clarification response within a sub-graph loop.
        # The last human message content is taken as the basis for routing.
        if isinstance(current_messages_from_state[-1].content, str):
            current_user_request_for_router = current_messages_from_state[-1].content.strip()
        # else: handle list content if necessary, though task_router likely expects string.
        logger.info(
            f"Input Handler: New turn or HumanMessage. Determined user_request_for_router: '{current_user_request_for_router[:100] if current_user_request_for_router else '...'}'"
        )
        # If input_str also exists and is DIFFERENT from the last human message, it needs to be added.
        if input_str and input_str != current_user_request_for_router and not input_already_processed:
            if (not current_messages_from_state or # Redundant check if we are in this elif block
                not (isinstance(current_messages_from_state[-1], HumanMessage) and 
                     current_messages_from_state[-1].content == input_str)):
                 new_human_message_to_add = HumanMessage(content=input_str) 
            updated_state_dict["input_processed"] = True
            updated_state_dict["input"] = None
    else:
        # Fallback if no HumanMessage is last and not in clarification (e.g. initial call with input_str)
        if input_str and not input_already_processed:
            current_user_request_for_router = input_str
            new_human_message_to_add = HumanMessage(content=input_str)
            updated_state_dict["input_processed"] = True
            updated_state_dict["input"] = None
            logger.info(f"Input Handler: Fallback - using input_str for user_request_for_router: '{input_str[:100]}...'")
        else:
            current_user_request_for_router = state.get("user_request_for_router") # Last resort
            logger.warning(
                f"Input Handler: No new HumanMessage, not in clarification, and no new input_str. Fallback user_request_for_router: '{current_user_request_for_router[:100] if current_user_request_for_router else 'None'}'"
            )
    
    updated_state_dict["user_request_for_router"] = current_user_request_for_router

    # Add the new human message if one was determined necessary
    if new_human_message_to_add:
        updated_state_dict["messages"] = [new_human_message_to_add] # operator.add will handle appending
        logger.info(f"Input handler: Adding new HumanMessage to state.messages: '{new_human_message_to_add.content}'")

    # This part handles input_str if it wasn't handled by the clarification logic or new turn logic above
    # Typically, if clarification mode used input_str, input_processed is already true.
    if input_str and not updated_state_dict.get("input_processed"):
        logger.info(f"Input handler: Processing state['input']: '{input_str}' (was not handled by clarification/new turn logic)")
        # This path should be less common if the logic above is comprehensive.
        if not new_human_message_to_add: # Avoid double-adding if already decided
            if (not current_messages_from_state or
                not (isinstance(current_messages_from_state[-1], HumanMessage) and
                     current_messages_from_state[-1].content == input_str)):
                # Add as message if truly new and not captured yet
                new_human_message_to_add_fallback = HumanMessage(content=input_str)
                if "messages" in updated_state_dict:
                    # This implies a message was already staged, which is unlikely here.
                    # Handle carefully if this case is possible.
                    logger.warning("Input Handler: 'messages' already in updated_state_dict in fallback input processing. This is unexpected.")
                else:
                    updated_state_dict["messages"] = [new_human_message_to_add_fallback]
                logger.info(f"Input handler: Adding new HumanMessage (fallback) to state.messages: '{input_str}'")
            else:
                logger.info("Input handler: state['input'] (fallback) matches last HumanMessage; not adding to state.messages again.")
        
        updated_state_dict["input_processed"] = True
        updated_state_dict["input"] = None # Clear state["input"] after processing
        logger.info("Input handler: state['input'] (fallback) processed, flag set, field cleared.")
    elif input_str and updated_state_dict.get("input_processed") and updated_state_dict.get("input") is None:
        # This means input_str was processed (e.g. by clarification path), and input field was cleared.
        # No further action on input_str needed.
        pass 
    elif input_str and not updated_state_dict.get("input_processed") and input_already_processed:
        # input_str exists, was not processed in this cycle by earlier logic, but state says it was processed in a *previous* cycle.
        # This implies stale input_str that wasn't cleared. Clear it now.
        logger.info(f"Input handler: state['input'] '{input_str}' found, not processed this cycle, but state.input_already_processed is True. Clearing stale input field.")
        updated_state_dict["input"] = None
    
    return updated_state_dict 