import logging
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, BaseMessage
from ..agent_state import AgentState # Adjusted relative import for AgentState

logger = logging.getLogger(__name__)

async def input_handler_node(state: AgentState, **kwargs) -> Dict[str, Any]:
    """
    处理 state['input'] 字段，将其转换为 HumanMessage 并有条件地添加到 messages 列表中。
    同时，确定用于任务路由的 user_request_for_router。

    此节点确保：
    1. 用户输入（state['input']）在合适的时机被用作路由决策依据。
    2. 用户输入在需要时被转换为 HumanMessage 并添加到消息历史，避免重复。
    3. 'input' 和 'input_processed' 状态字段得到正确更新。
    """
    logger.debug(
        f"Input Handler START. Input='{state.get('input')}', "
        f"InputProcessed='{state.get('input_processed')}', "
        f"SubgraphStatus='{state.get('subgraph_completion_status')}', "
        f"NumMessages={len(state.get('messages', []))}"
    )

    current_messages = list(state.get("messages", []))
    input_str: Optional[str] = state.get("input")
    # This flag indicates if the *same* input_str content was processed in a *previous* graph invocation.
    input_processed_in_prior_cycles: bool = state.get("input_processed", False)
    
    updated_state_dict: Dict[str, Any] = {}
    new_human_message: Optional[HumanMessage] = None
    
    # --- 1. Determine user_request_for_router with clear precedence ---
    determined_user_request: Optional[str] = None
    # This flag is True if input_str is the primary source for determined_user_request in *this* cycle.
    input_str_is_the_active_request_source = False

    subgraph_clarification_mode = state.get("subgraph_completion_status") == "needs_clarification"

    if subgraph_clarification_mode:
        if input_str:
            # In clarification mode, the new input_str IS the user's clarification for routing.
            determined_user_request = input_str
            input_str_is_the_active_request_source = True
            logger.info(f"Input Handler: Clarification Mode. Using new input '{input_str}' as user_request_for_router.")
        else:
            # No new input during clarification, fall back to the existing request that led to clarification.
            determined_user_request = state.get("user_request_for_router")
            logger.info(f"Input Handler: Clarification Mode. No new input. Using existing user_request_for_router: '{determined_user_request}'.")
    elif input_str and not input_processed_in_prior_cycles:
        # Standard case: New input string received, not in clarification, and this specific input content
        # has not been processed in a previous cycle. This is the primary request.
        determined_user_request = input_str
        input_str_is_the_active_request_source = True
        logger.info(f"Input Handler: New Input. Using '{input_str}' as user_request_for_router.")
    elif current_messages and isinstance(current_messages[-1], HumanMessage):
        # No new active input_str (either it's None, or it was already processed in a prior cycle).
        # Rely on the last human message in history for routing.
        last_hm_content = current_messages[-1].content
        if isinstance(last_hm_content, str): # Should usually be str
            determined_user_request = last_hm_content.strip()
            logger.info(f"Input Handler: Using last HumanMessage's content for user_request_for_router: '{determined_user_request[:100]}'.")
        # else: last message content is not a simple string (e.g. list for multimodal), router might not handle this.
    else:
        # Ultimate fallback: No clarification, no new/active input_str, no last HumanMessage.
        # This could be an initial call with no input, or an empty/unexpected state.
        # Preserve existing user_request_for_router if any.
        determined_user_request = state.get("user_request_for_router") 
        logger.warning(
            f"Input Handler: Fallback. No new input or last HM to guide routing. "
            f"User_request_for_router will be: '{determined_user_request[:100] if determined_user_request else 'None'}'."
        )
    
    updated_state_dict["user_request_for_router"] = determined_user_request

    # --- 2. Determine if a new HumanMessage needs to be added from input_str ---
    # A new HumanMessage is added if input_str was the active source for the request (or a new clarification)
    # AND its content is genuinely new compared to the last message in history.
    if input_str and input_str_is_the_active_request_source:
        if not current_messages or \
           not (isinstance(current_messages[-1], HumanMessage) and current_messages[-1].content == input_str):
            new_human_message = HumanMessage(content=input_str)
            updated_state_dict["messages"] = [new_human_message] # operator.add will handle appending
            logger.info(f"Input Handler: Adding new HumanMessage to state.messages: '{input_str}'.")
        else:
            logger.info(f"Input Handler: Input string '{input_str}' matches the last HumanMessage; not adding as a new message again.")
    
    # --- 3. Manage 'input' and 'input_processed' state fields ---
    if input_str_is_the_active_request_source:
        # If input_str was actively used in this cycle (for routing and potentially a new message),
        # mark it as processed for this cycle and clear it from the state.
        updated_state_dict["input_processed"] = True
        updated_state_dict["input"] = None 
        logger.info(f"Input Handler: Input string '{input_str}' was actively processed this cycle. Setting 'input_processed'=True, 'input'=None.")
    elif input_str and input_processed_in_prior_cycles:
        # If input_str exists, was marked as processed in a *prior* cycle,
        # AND was *not* actively used as the request source in *this* cycle (e.g., clarification got no new input, or new turn used last HM).
        # This implies input_str is stale from a previous turn and wasn't cleared. Clear it now.
        updated_state_dict["input"] = None
        logger.info(f"Input Handler: Clearing stale 'input' field ('{input_str}') as it was processed in a prior cycle and not actively used now.")
    
    logger.debug(f"Input Handler END. Returning updates: {updated_state_dict}")
    return updated_state_dict 