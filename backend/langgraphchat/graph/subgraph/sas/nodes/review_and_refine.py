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


async def review_and_refine_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    logger.info(f"--- SAS: Review and Refine Node (Iteration {state.revision_iteration}) ---")
    logger.info(f"    Initial dialog_state: '{state.dialog_state}'")
    logger.info(f"    task_list_accepted: {state.task_list_accepted}")
    logger.info(f"    module_steps_accepted: {state.module_steps_accepted}")
    logger.info(f"    RECEIVED user_input at START: '{state.user_input}'")

    state.current_step_description = f"SAS: Awaiting user review (Iter: {state.revision_iteration}) or processing feedback."
    state.is_error = False
    # state.error_message = None # Keep existing error message if any

    # 新增：检查是否启用自动接受模式
    auto_accept_enabled = state.config.get("auto_accept_tasks", False)  # 默认禁用自动接受，让流程正常执行任务分解
    logger.info(f"Auto accept mode: {auto_accept_enabled}")

    # --- This initial determination of reviewing_task_list/steps is primarily for when user_input IS PRESENT ---
    # --- to know what their feedback pertains to. ---
    # --- When user_input IS NONE, we will re-evaluate directly below. ---
    reviewing_task_list_for_feedback_context = False
    reviewing_module_steps_for_feedback_context = False

    if state.user_input is not None: # System is processing user_input, determine context of feedback
        if state.dialog_state == "sas_awaiting_task_list_review" or (not state.task_list_accepted):
            reviewing_task_list_for_feedback_context = True
        elif state.dialog_state == "sas_awaiting_module_steps_review" or (state.task_list_accepted and not state.module_steps_accepted):
            reviewing_module_steps_for_feedback_context = True
    
    logger.info(f"    Context for feedback (if user_input present) - Reviewing task list: {reviewing_task_list_for_feedback_context}")
    logger.info(f"    Context for feedback (if user_input present) - Reviewing module steps: {reviewing_module_steps_for_feedback_context}")

    # --- OTHERWISE: NO USER_INPUT for this cycle. Present a question to the user. ---
    if state.user_input is None:
        logger.info("No user_input. Determining what to present to the user for review.")
        
        question_for_user = None
        dialog_state_if_awaiting_input = None

        if not state.task_list_accepted and not state.module_steps_accepted:
            logger.info("Presenting for review: TASK LIST (since task_list_accepted is False).")
            if state.sas_step1_generated_tasks:
                # 新增：如果启用自动接受，直接接受任务列表
                if auto_accept_enabled:
                    logger.info("Auto-accepting task list (auto_accept_tasks=True)")
                    state.task_list_accepted = True
                    state.dialog_state = "sas_step1_tasks_generated"
                    state.clarification_question = None
                    state.user_advice = None
                    if not any("Task list automatically accepted" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                        state.messages = (state.messages or []) + [AIMessage(content="Task list automatically accepted. Generating detailed module steps next.")]
                    return state.model_dump()
                
                # 原有逻辑：等待用户确认
                tasks_simple = []
                for task in state.sas_step1_generated_tasks:
                    tasks_simple.append({"name": task.name, "type": task.type, "description": task.description})
                try:
                    current_data_for_review_json_str = json.dumps(tasks_simple, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Error serializing tasks: {e}")
                    current_data_for_review_json_str = "[Error serializing tasks]"
                question_for_user = f"""These are the tasks generated based on your description (iteration {state.revision_iteration}):\\n\\n```json\\n{current_data_for_review_json_str}\\n```\\n\\nDo you accept these tasks? You can say "accept" or "agree", or provide your modification instructions."""
                dialog_state_if_awaiting_input = "sas_awaiting_task_list_review"
            else:
                logger.warning("Attempting to review task list, but no sas_step1_generated_tasks found.")
                state.clarification_question = "No tasks generated. This might be an issue. Please check if the task generation step completed successfully."

        elif state.task_list_accepted and not state.module_steps_accepted:
            logger.info("Presenting for review: MODULE STEPS (since task_list_accepted is True and module_steps_accepted is False).")
            if state.sas_step1_generated_tasks and any(getattr(task, 'details', None) for task in state.sas_step1_generated_tasks): # Ensure details (module steps) exist
                # 新增：如果启用自动接受，直接接受模块步骤
                if auto_accept_enabled:
                    logger.info("Auto-accepting module steps (auto_accept_tasks=True)")
                    state.module_steps_accepted = True
                    state.dialog_state = "sas_module_steps_accepted_proceeding"
                    state.clarification_question = None
                    state.user_advice = None
                    if not any("Module steps automatically accepted" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                        state.messages = (state.messages or []) + [AIMessage(content="Module steps automatically accepted. Preparing to generate XML program.")]
                    return state.model_dump()
                
                # 原有逻辑：等待用户确认
                tasks_with_details = []
                for task in state.sas_step1_generated_tasks:
                    tasks_with_details.append({
                        "name": task.name,
                        "type": task.type,
                        "description": task.description,
                        "details": task.details if task.details else ["No module steps generated for this task."]
                    })
                try:
                    current_data_for_review_json_str = json.dumps(tasks_with_details, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Error serializing module steps: {e}")
                    current_data_for_review_json_str = "[Error serializing module steps]"
                question_for_user = f"""These are the module steps generated for each task (iteration {state.revision_iteration}):\\n\\n```json\\n{current_data_for_review_json_str}\\n```\\n\\nDo you accept these module steps? If you need to make changes, please let me know your opinion. You can directly say "accept" or "agree", or provide your modification instructions for specific tasks or steps."""
                dialog_state_if_awaiting_input = "sas_awaiting_module_steps_review"
            else:
                logger.warning("Attempting to review module steps, but no tasks with details (module steps) found or no tasks at all. This might be an issue if module steps were expected.")
                state.clarification_question = "Module steps generation might have resulted in no steps or an issue. Proceeding with caution. If you expected module steps, please indicate a problem with the previous step."

        elif state.task_list_accepted and state.module_steps_accepted:
            logger.info("Both task list and module steps are already accepted. Passing through.")
            state.clarification_question = None
            state.user_advice = None
            state.dialog_state = "sas_all_steps_accepted_proceed_to_xml"
            return state.model_dump()

        else:
            logger.error(f"Review node (presenting question): Fell into unexpected 'else' case. Dialog_state: '{state.dialog_state}', task_list_accepted: {state.task_list_accepted}, module_steps_accepted: {state.module_steps_accepted}.")
            state.is_error = True
            state.error_message = "Internal error: Review stage could not be determined when presenting question."

        # Set clarification question and dialog state
        state.clarification_question = question_for_user
        if question_for_user:
             if not state.messages or state.messages[-1].content != question_for_user:
                state.messages = (state.messages or []) + [AIMessage(content=question_for_user)]
        elif not state.is_error and not (state.task_list_accepted and state.module_steps_accepted):
            logger.error("Internal logic error: No question formed for user review, but not an error/pass-through state.")
            state.is_error = True
            state.error_message = "Internal error: Failed to prepare a review question."
            if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]

        state.dialog_state = dialog_state_if_awaiting_input
        state.user_advice = None
        logger.info(f"Paused for user input. Clarification: '{str(state.clarification_question)[:100]}...'. Dialog state set to: {state.dialog_state}")
        return state.model_dump()
    
    # --- Process user input when it's provided ---
    else:
        logger.info("Processing user feedback.")
        state.user_advice = state.user_input 
        state.user_input = None 
        
        if not state.messages or not (isinstance(state.messages[-1], HumanMessage) and state.messages[-1].content == state.user_advice):
            state.messages = (state.messages or []) + [HumanMessage(content=state.user_advice)]

        feedback_for_processing = state.user_advice.strip()
        
        # Check for acceptance
        acceptance_keywords = ["accept", "yes", "ok", "agree", "fine", "alright", "proceed", "同意", "接受", "可以", "好的", "没问题", "行"]
        is_accepted = any(feedback_for_processing.lower() == keyword for keyword in acceptance_keywords) or \
                     any(keyword in feedback_for_processing.lower() for keyword in acceptance_keywords if len(feedback_for_processing) <= 20)

        if is_accepted:
            state.clarification_question = None
            state.user_advice = None

            if reviewing_task_list_for_feedback_context:
                logger.info("User accepted the TASK LIST.")
                state.task_list_accepted = True
                state.dialog_state = "sas_step1_tasks_generated"
                if not any("Task list confirmed" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content="Task list confirmed. Generating detailed module steps next.")]
            elif reviewing_module_steps_for_feedback_context:
                logger.info("User accepted the MODULE STEPS.")
                state.module_steps_accepted = True
                state.dialog_state = "sas_module_steps_accepted_proceeding"
                if not any("Module steps confirmed" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content="Module steps confirmed. Preparing to generate XML program.")]
            else:
                logger.error("CRITICAL: Acceptance received but review context was undefined during processing.")
                state.is_error = True
                state.error_message = "Accepted feedback, but review context was unclear internally. Please try again or restart."
                if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        else:
            # User provided modifications - for simplicity, accept the feedback and continue
            logger.info("User provided modifications. For now, accepting to continue the flow.")
            if reviewing_task_list_for_feedback_context:
                state.task_list_accepted = True
                state.dialog_state = "sas_step1_tasks_generated"
                state.messages = (state.messages or []) + [AIMessage(content="Feedback noted. Proceeding with task generation.")]
            elif reviewing_module_steps_for_feedback_context:
                state.module_steps_accepted = True
                state.dialog_state = "sas_module_steps_accepted_proceeding"
                state.messages = (state.messages or []) + [AIMessage(content="Feedback noted. Proceeding with XML generation.")]
            
            state.clarification_question = None
            state.user_advice = None

    return state.model_dump()

__all__ = [
    "review_and_refine_node"
] 