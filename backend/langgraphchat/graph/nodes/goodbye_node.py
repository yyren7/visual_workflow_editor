import logging
from langchain_core.messages import AIMessage
from ..agent_state import AgentState

logger = logging.getLogger(__name__)

async def handle_goodbye_node(state: AgentState) -> dict:
    """
    Handles the end_session routing by generating a goodbye message.
    """
    logger.info("--- Handling Goodbye ---")
    
    goodbye_message = AIMessage(content="再见，期待下次为您服务！")
    
    # Add the goodbye message to the list of messages
    # The state's 'messages' field should be configured to append new messages.
    updated_messages = state.get("messages", []) + [goodbye_message]
    
    logger.info(f"Added goodbye message: {goodbye_message.content}")
    
    return {
        "messages": updated_messages,
        "input": None, # Clear any remaining input
        "user_request_for_router": None, # Clear router request
        "task_route_decision": None # Clear decision
    } 