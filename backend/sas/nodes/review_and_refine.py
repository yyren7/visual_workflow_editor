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
    This version is corrected to always return the full RobotFlowAgentState object.
    """
    logger.info(f"--- SAS: Review and Refine Node (Iteration {state.revision_iteration}) ---")
    logger.info(f"    Initial dialog_state: '{state.dialog_state}'")
    logger.info(f"    task_list_accepted: {state.task_list_accepted}")
    logger.info(f"    module_steps_accepted: {state.module_steps_accepted}")
    
    user_input = state.user_input
    logger.info(f"    RECEIVED user_input at START: '{user_input}'")

    # Default pass-through values
    new_dialog_state = state.dialog_state
    completion_status = state.completion_status
    error_message = state.error_message
    clarification_question = None # Reset clarification unless explicitly set

    # Determine context for feedback
    is_task_list_review = state.dialog_state in ['sas_awaiting_task_list_review', 'sas_step1_tasks_generated']
    is_module_steps_review = state.dialog_state == 'sas_awaiting_module_steps_review'

    # If user_input is present, it means we are responding to feedback.
    if user_input:
        logger.info("Processing user feedback.")
        feedback_lower = user_input.strip().lower()
        
        # Check for acceptance
        is_accepted = any(phrase in feedback_lower for phrase in ["accept", "agree", "yes", "ok", "yep", "approve"])
        is_reset_request = "reset" in feedback_lower

        if is_reset_request:
            logger.info("[REVIEW_NODE_RESET] User requested reset.")
            # Reset logic needs to be handled by a dedicated node or graph state update.
            # For now, we set a state that can be routed to a reset handler.
            new_dialog_state = "error" # Or a specific 'reset_triggered' state
            error_message = "User requested a reset. This feature is under development."
            completion_status = "error"
        
        elif is_accepted:
            if is_task_list_review:
                logger.info("User accepted the TASK LIST.")
                state.task_list_accepted = True
                new_dialog_state = "sas_step1_tasks_generated" # Signal to proceed to step 2
                completion_status = "completed_partial"
            elif is_module_steps_review:
                logger.info("User accepted the MODULE STEPS.")
                state.module_steps_accepted = True
                new_dialog_state = "sas_all_steps_accepted_proceed_to_xml" # Signal to proceed to XML generation
                completion_status = "completed_partial"
            else:
                logger.warning(f"Acceptance received in an unexpected state: {state.dialog_state}")

            # After acceptance, update state and return immediately to allow routing
            state.dialog_state = new_dialog_state
            state.completion_status = completion_status
            state.user_input = None # Clear input
            logger.info(f"Acceptance processed. Returning immediately with state: {new_dialog_state}")
            return state
        else:
            # User provided feedback for revision
            logger.info("User provided revision feedback.")
            state.user_advice = user_input
            state.revision_iteration += 1
            if is_task_list_review:
                new_dialog_state = "sas_awaiting_task_list_revision_input"
            elif is_module_steps_review:
                new_dialog_state = "sas_awaiting_module_steps_revision_input"
            completion_status = "needs_clarification"

            # After setting up for revision, return immediately
            state.dialog_state = new_dialog_state
            state.completion_status = completion_status
            state.user_input = None # Clear input
            logger.info(f"Revision feedback processed. Returning immediately to re-run previous node.")
            return state

    # This block handles the case where there is no user_input.
    # The purpose is to prepare the state for user review and then pause.
    else:
        if is_task_list_review:
            # Generate the clarification question for the task list
            if state.sas_step1_generated_tasks:
                tasks_json = json.dumps([task.model_dump() for task in state.sas_step1_generated_tasks], indent=2)
                clarification_question = (
                    f"These are the tasks generated based on your description (iteration {state.revision_iteration}):\n\n"
                    f"```json\n{tasks_json}\n```\n\n"
                    f"Do you accept these tasks? You can say \"accept\" or \"agree\", or provide your modification instructions."
                )
                new_dialog_state = "sas_awaiting_task_list_review"
            else:
                error_message = "[Review Node] No tasks were generated for review."
                logger.error(error_message)
                new_dialog_state = "error"
                completion_status = "error"

        elif is_module_steps_review:
            # Generate the clarification question for the module steps
            if state.sas_step2_module_steps:
                 clarification_question = (
                    f"These are the module steps generated for the tasks (iteration {state.revision_iteration}):\n\n"
                    f"```\n{state.sas_step2_module_steps}\n```\n\n"
                    f"Do you accept these module steps? You can say \"accept\" or \"agree\", or provide modification instructions."
                )
                 new_dialog_state = "sas_awaiting_module_steps_review"
            else:
                error_message = "[Review Node] No module steps were generated for review."
                logger.error(error_message)
                new_dialog_state = "error"
                completion_status = "error"
        else:
            # No specific review state, likely an issue. For safety, just pass through.
            logger.warning(f"Review node entered with no user_input and an unexpected dialog_state: '{state.dialog_state}'. Passing state through.")
            # No change to state, just return it.
            return state

        # If we are here, we have generated a clarification question and are pausing.
        state.clarification_question = clarification_question
        state.dialog_state = new_dialog_state
        state.completion_status = "needs_clarification"
        
        logger.info(f"Paused for user input. Clarification: '{str(clarification_question)[:100]}...'. Dialog state set to: {new_dialog_state}")
        
        # Directly return the modified state object
        return state
        
    # This final state update is now only for the path where user input was processed
    # but did not result in an immediate return (e.g., a path that might not exist anymore).
    # The main logic paths (acceptance, revision) now return early.
    state.dialog_state = new_dialog_state
    state.completion_status = completion_status
    state.error_message = error_message
    state.clarification_question = clarification_question
            
    logger.info(f"--- SAS: Review and Refine Node PRE-RETURN (Standard Fallback) ---")
    logger.info(f"    FINAL dialog_state before return: '{state.dialog_state}'")
    if state.sas_step1_generated_tasks:
        logger.info(f"    FINAL sas_step1_generated_tasks count before return: {len(state.sas_step1_generated_tasks)}")
        if state.sas_step1_generated_tasks:
             logger.info(f"    FINAL first task name: {state.sas_step1_generated_tasks[0].name}")
    else:
        logger.info(f"    FINAL sas_step1_generated_tasks is empty or None.")
    logger.info(f"    FINAL clarification_question before return: '{str(state.clarification_question)[:50]}...'")
    logger.info(f"    FINAL completion_status before return: '{state.completion_status}'")
    
    # CRITICAL: Clear the user_input after it has been processed to prevent reuse in subsequent steps.
    state.user_input = None
    logger.info("    User input cleared before returning from review_and_refine node.")

    return state

__all__ = [
    "review_and_refine_node"
] 