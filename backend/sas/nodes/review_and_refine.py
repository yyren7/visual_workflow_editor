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


async def review_and_refine_node(state: RobotFlowAgentState) -> RobotFlowAgentState:
    """
    Processes user feedback to determine the next logical state in the SAS workflow.

    This node acts as a central decision point after user review. It updates the
    dialog_state based on whether the user has accepted tasks/modules, or
    provided revisions. It also implements a "Review Gate" principle to ensure
    that any generated artifacts force the state into a review loop, preventing stalls.

    Args:
        state: The current state of the agent.

    Returns:
        The updated state with a new dialog_state if a transition is warranted.
    """
    logger.info(f"✨ review_and_refine_node called with dialog_state: '{state.dialog_state}'")
    
    initial_dialog_state = state.dialog_state

    # --- User-driven Actions ---
    # These reflect direct input from the user in the current step and take priority.

    # Case 1: User accepts the task list.
    if state.task_list_accepted and initial_dialog_state == "sas_awaiting_task_list_review":
        logger.info("User accepted the task list. Transitioning to 'task_list_to_module_steps'.")
        state.dialog_state = "task_list_to_module_steps"
        return state

    # Case 2: User accepts the module steps.
    if state.module_steps_accepted and initial_dialog_state == "sas_awaiting_module_steps_review":
        logger.info("User accepted module steps. Transitioning to 'sas_generating_individual_xmls'.")
        state.dialog_state = "sas_generating_individual_xmls"
        return state

    # Case 3: User provides revisions for the task list.
    if state.user_input and initial_dialog_state == "sas_awaiting_task_list_review":
        logger.info("User provided revisions for the task list. Transitioning to 'user_input_to_task_list' for re-generation.")
        state.dialog_state = "user_input_to_task_list"
        return state
        
    # Case 4: User provides revisions for the module steps.
    if state.user_input and initial_dialog_state == "sas_awaiting_module_steps_review":
        logger.info("User provided revisions for the module steps. Transitioning to 'task_list_to_module_steps' for re-generation.")
        state.dialog_state = "task_list_to_module_steps"
        return state

    # --- Review Gates (State Correction) ---
    # These gates act as a safety net. If artifacts have been generated but the
    # state isn't a review state, they force it to become one. Order is important.

    # Gate 2: Module Steps Review Gate
    # If task list is approved, and module steps exist but are not yet approved,
    # we MUST be awaiting their review.
    if state.task_list_accepted and state.sas_step2_module_steps and not state.module_steps_accepted:
        logger.info("✅ GATE 2: Module steps exist and are not accepted. Ensuring state is 'sas_awaiting_module_steps_review'.")
        state.dialog_state = "sas_awaiting_module_steps_review"
        return state

    # Gate 1: Task List Review Gate
    # If a task list exists and is not yet approved, we MUST be awaiting its review.
    if state.sas_step1_generated_tasks and not state.task_list_accepted:
        logger.info("✅ GATE 1: Task list exists and is not accepted. Ensuring state is 'sas_awaiting_task_list_review'.")
        state.dialog_state = "sas_awaiting_task_list_review"
        return state

    # Default Case: No action taken, waiting for user feedback.
    logger.info(f"No state transition condition met for '{initial_dialog_state}'. Passing state through to await user action.")
    return state


__all__ = [
    "review_and_refine_node"
] 