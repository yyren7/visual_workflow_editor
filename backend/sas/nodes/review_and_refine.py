import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from ..state import RobotFlowAgentState, TaskDefinition

logger = logging.getLogger(__name__)

# Helper to load task type descriptions
def _load_all_task_type_descriptions(base_path: str) -> str:
    logger.info(f"Loading all task type descriptions from: {base_path}")
    descriptions = []
    try:
        task_list_path = Path(base_path)
        if task_list_path.is_dir():
            for md_file in task_list_path.glob("*.md"):
                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        descriptions.append(f.read())
                    logger.debug(f"Loaded task type description: {md_file.name}")
                except Exception as e:
                    logger.error(f"Error reading task type description file {md_file}: {e}")
        else:
            logger.warning(f"Task type descriptions path is not a directory: {base_path}")
    except Exception as e:
        logger.error(f"Error accessing task type descriptions path {base_path}: {e}")
        return "Error: Could not load task type descriptions."
    
    if not descriptions:
        logger.warning(f"No task type descriptions found in {base_path}. Prompt will be incomplete.")
        return "Warning: Task type descriptions are missing."
        
    return "\n\n---\n\n".join(descriptions)


async def review_and_refine_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    """
    Handles the review and refinement process for both task lists and module steps.
    This node transitions the state to await user feedback and prepares the necessary messages.
    """
    logger.info(f"✨ review_and_refine_node called with dialog_state: {state.dialog_state}")
    
    # Check if we are entering review for the first time after task list generation.
    # The previous node (user_input_to_task_list) has successfully run.
    if state.sas_step1_generated_tasks and not state.task_list_accepted:
        logger.info("📋 Entering task list review for the first time.")
        state.dialog_state = 'sas_awaiting_task_list_review'
        state.completion_status = 'needs_clarification'
        
        task_count = len(state.sas_step1_generated_tasks)
        review_message = f"已生成 {task_count} 个任务，请审核任务列表。您可以批准或提供修改建议。"
        if state.messages and not any(review_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=review_message)]
        return state
    
    # Check if we are entering review for the first time after module steps generation.
    # The previous node (task_list_to_module_steps) has successfully run.
    elif state.sas_step2_module_steps and not state.module_steps_accepted:
        logger.info("📋 Entering module steps review for the first time.")
        state.dialog_state = 'sas_awaiting_module_steps_review'
        state.completion_status = 'needs_clarification'
        
        review_message = "模块步骤已生成，请审核。您可以批准或提供修改建议。"
        if state.messages and not any(review_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=review_message)]
        return state

    # If the user provides input during a review phase, the routing logic in graph_builder.py
    # will handle directing it back to the appropriate generation node. This node's primary
    # role here is to initiate the review state. The external interaction (e.g., via API)
    # is responsible for setting `task_list_accepted` or `module_steps_accepted` to True upon approval.
    
    # Fallback/default behavior
    logger.info(f"review_and_refine_node: No specific action taken for dialog_state '{state.dialog_state}'. Passing state through.")
    return state

__all__ = [
    "review_and_refine_node"
] 