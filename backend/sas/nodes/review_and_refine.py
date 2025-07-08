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
    A node that orchestrates the review and refinement loop for both task lists and module steps.
    It can pause execution to await user feedback and then resume based on that feedback.
    """
    logger.info(f"--- SAS: Review and Refine Node (Iteration {state.revision_iteration}) ---")
    logger.info(f"    Initial dialog_state: '{state.dialog_state}'")
    logger.info(f"    task_list_accepted: {state.task_list_accepted}")
    logger.info(f"    module_steps_accepted: {state.module_steps_accepted}")
    
    user_input = state.user_input
    logger.info(f"    RECEIVED user_input at START: '{user_input}'")

    # This node has two main modes:
    # 1. If user_input exists: Process the user's feedback (accept, revise, etc.).
    # 2. If user_input is None: Prepare a question for the user and pause the graph.

    # Mode 1: Process user feedback
    if user_input:
        feedback_lower = user_input.strip().lower()
        is_accepted = any(phrase in feedback_lower for phrase in ["accept", "agree", "yes", "ok", "yep", "approve", "ok."])

        # Determine which review we are in based on the state when the graph was paused
        is_task_list_review = state.dialog_state == 'sas_awaiting_task_list_review'
        is_module_steps_review = state.dialog_state == 'sas_awaiting_module_steps_review'

        if is_accepted:
            if is_task_list_review:
                logger.info("User accepted the TASK LIST.")
                state.task_list_accepted = True
                # This state tells the router to proceed to the next step (module generation)
                state.dialog_state = "sas_step1_tasks_generated" 
            elif is_module_steps_review:
                logger.info("User accepted the MODULE STEPS.")
                state.module_steps_accepted = True
                # This state tells the router that all reviews are done and we can generate XML
                state.dialog_state = "sas_xml_generation_approved"
            else:
                logger.warning(f"Acceptance received in an unexpected state: {state.dialog_state}. No action taken.")

            state.completion_status = "completed_partial" # Mark this part as done
        else:
            # User provided feedback for revision
            logger.info("User provided revision feedback.")
            state.user_advice = user_input
            state.revision_iteration += 1
            if is_task_list_review:
                # This state tells the router to go back to the task generation node
                state.dialog_state = "initial" 
                state.task_list_accepted = False # <<< THE FIX IS HERE
            elif is_module_steps_review:
                 # This state tells the router to go back to the module step generation node
                state.dialog_state = "sas_step2_module_steps_generated_for_review"
                state.module_steps_accepted = False # <<< AND HERE
            
            state.completion_status = "processing"

        # CRITICAL: Clear user_input after processing and return immediately
        state.user_input = None
        state.clarification_question = None # Clear question after processing feedback
        logger.info(f"User feedback processed. New dialog_state: '{state.dialog_state}'. Returning to router.")
        return state

    # Mode 2: No user_input, so prepare a question and pause
    else:
        # Determine which item needs review
        is_task_list_review_needed = state.dialog_state == 'sas_step1_tasks_generated' and not state.task_list_accepted
        is_module_steps_review_needed = state.dialog_state == 'sas_step2_module_steps_generated_for_review' and not state.module_steps_accepted

        if is_task_list_review_needed:
            if state.sas_step1_generated_tasks:
                tasks_json = json.dumps([task.model_dump() for task in state.sas_step1_generated_tasks], indent=2, ensure_ascii=False)
                state.clarification_question = (
                    f"这是根据您的描述生成的任务列表 (第 {state.revision_iteration + 1} 次审核):\n\n"
                    f"```json\n{tasks_json}\n```\n\n"
                    '您是否接受这份任务列表？您可以回答"接受"、"同意"，或者直接提供您的修改意见。'
                )
                state.dialog_state = "sas_awaiting_task_list_review" # PAUSE state
                state.completion_status = "needs_clarification"
            else:
                logger.error("[Review Node] No tasks were generated for review.")
                state.error_message = "No tasks were generated for review."
                state.dialog_state = "error"
                state.completion_status = "error"

        elif is_module_steps_review_needed:
            if state.sas_step2_module_steps:
                 state.clarification_question = (
                    f"这是为任务生成的模块步骤 (第 {state.revision_iteration + 1} 次审核):\n\n"
                    f"```\n{state.sas_step2_module_steps}\n```\n\n"
                    '您是否接受这些模块步骤？您可以回答"接受"、"同意"，或者提供修改意见。'
                )
                 state.dialog_state = "sas_awaiting_module_steps_review" # PAUSE state
                 state.completion_status = "needs_clarification"
            else:
                logger.error("[Review Node] No module steps were generated for review.")
                state.error_message = "No module steps were generated for review."
                state.dialog_state = "error"
                state.completion_status = "error"
        else:
            # If no review is needed, it might be an issue or just passing through.
            logger.warning(f"Review node entered, but no review is currently needed. Dialog state: '{state.dialog_state}'. Passing through.")
            # We don't change the state here, just let it pass to the next node via the router.
            # This case might happen if, for example, the flow is designed to skip a review step.
            # The router should handle the current dialog_state correctly.
            pass

        logger.info(f"Prepared to pause for user input. New dialog_state: '{state.dialog_state}'.")
        return state

__all__ = [
    "review_and_refine_node"
] 