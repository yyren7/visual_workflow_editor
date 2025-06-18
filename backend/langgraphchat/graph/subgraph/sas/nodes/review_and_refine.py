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

    # ---- BEGIN REFACTORED SECTION for PRESENTING QUESTIONS ----
    if state.user_input is None: # System is presenting something for review
        logger.info("Mode: Presenting data for review to the user.")
        question_for_user = ""
        dialog_state_if_awaiting_input = state.dialog_state # Default

        if not state.task_list_accepted:
            logger.info("Presenting for review: TASK LIST (since state.task_list_accepted is False).")
            if state.sas_step1_generated_tasks:
                try:
                    current_data_for_review_json_str = json.dumps([task.model_dump(exclude_none=True) for task in state.sas_step1_generated_tasks], indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Error serializing current task list: {e}")
                    current_data_for_review_json_str = "[Error serializing task list]"
                question_for_user = f"""This is the task list generated based on the current description (iteration {state.revision_iteration}):\\n\\n```json\\n{current_data_for_review_json_str}\\n```\\n\\nDo you accept this task list? If you need to make changes, please let me know your opinion. You can directly say "accept" or "agree", or provide your modification instructions."""
                dialog_state_if_awaiting_input = "sas_awaiting_task_list_review"
            else:
                logger.warning("Attempting to review task list, but no tasks found in state.sas_step1_generated_tasks. This might be an issue.")
                state.is_error = True
                state.error_message = "Review node: No tasks available for task list review, though task list is not accepted."
                # No question can be formed.

        elif state.task_list_accepted and not state.module_steps_accepted:
            logger.info("Presenting for review: MODULE STEPS (since task_list_accepted is True and module_steps_accepted is False).")
            if state.sas_step1_generated_tasks and any(getattr(task, 'details', None) for task in state.sas_step1_generated_tasks): # Ensure details (module steps) exist
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
                # This could happen if module step generation failed or produced nothing.
                # The node should ideally not ask for review if there's nothing substantive to review.
                # Consider if an error message or a different path is needed.
                # For now, if no steps, no question. The routing after process_description_to_module_steps_node should handle empty/error states.
                # If we are here, it means process_description_to_module_steps_node probably completed "successfully" but maybe with no actual steps.
                state.clarification_question = "Module steps generation might have resulted in no steps or an issue. Proceeding with caution. If you expected module steps, please indicate a problem with the previous step."
                # No specific dialog_state to await input for this, it's more of a notification.
                # The graph will likely proceed, and if XML generation fails due to no steps, that will be caught.

        elif state.task_list_accepted and state.module_steps_accepted:
            logger.info("Both task list and module steps are already accepted. Passing through.")
            # No clarification question, user_advice should be None.
            state.clarification_question = None
            state.user_advice = None
            state.dialog_state = "sas_all_steps_accepted_proceed_to_xml" # Signal to routing
            return state.model_dump() # Pass through

        else: # Should ideally not be reached if logic above is complete
            logger.error(f"Review node (presenting question): Fell into unexpected 'else' case. Dialog_state: '{state.dialog_state}', task_list_accepted: {state.task_list_accepted}, module_steps_accepted: {state.module_steps_accepted}.")
            state.is_error = True
            state.error_message = "Internal error: Review stage could not be determined when presenting question."
            # No specific question.

        # Set clarification question and dialog state
        state.clarification_question = question_for_user
        if question_for_user: # Only add message if there's a question
             if not state.messages or state.messages[-1].content != question_for_user:
                state.messages = (state.messages or []) + [AIMessage(content=question_for_user)]
        elif not state.is_error and not (state.task_list_accepted and state.module_steps_accepted):
            # If no question was formed, but it's not an error and not a pass-through state, it's problematic.
            logger.error("Internal logic error: No question formed for user review, but not an error/pass-through state.")
            state.is_error = True
            state.error_message = "Internal error: Failed to prepare a review question."
            if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]

        state.dialog_state = dialog_state_if_awaiting_input
        state.user_advice = None # Clear any old advice
        logger.info(f"Paused for user input. Clarification: '{str(state.clarification_question)[:100]}...'. Dialog state set to: {state.dialog_state}")
        return state.model_dump()
    # ---- END REFACTORED SECTION for PRESENTING QUESTIONS ----
    
    else: # User has provided input, process it
        # This section uses reviewing_task_list_for_feedback_context and reviewing_module_steps_for_feedback_context
        # which were determined at the start of the function based on dialog_state and acceptance flags.
        state.user_advice = state.user_input 
        state.user_input = None 
        logger.info(f"Processing user feedback (advice): '{state.user_advice[:200]}...' for context: {'Task List' if reviewing_task_list_for_feedback_context else 'Module Steps' if reviewing_module_steps_for_feedback_context else 'Undefined'}")

        if not state.messages or not (isinstance(state.messages[-1], HumanMessage) and state.messages[-1].content == state.user_advice):
            state.messages = (state.messages or []) + [HumanMessage(content=state.user_advice)]

        feedback_for_processing = state.user_advice.strip()
        
        acceptance_keywords_zh = ["同意", "接受", "可以", "好的", "没问题", "行", "ok"]
        acceptance_keywords_en = ["accept", "yes", "ok", "agree", "fine", "alright", "proceed"]
        
        is_accepted = False
        feedback_lower = feedback_for_processing.lower()

        if any(feedback_lower == keyword for keyword in acceptance_keywords_zh + acceptance_keywords_en):
            is_accepted = True
        elif any(keyword in feedback_lower for keyword in acceptance_keywords_zh + acceptance_keywords_en) and len(feedback_lower) <= 20: 
            is_accepted = True

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
                if not any("Module steps confirmed" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):\
                    state.messages = (state.messages or []) + [AIMessage(content="Module steps confirmed. Preparing to generate XML program.")]
            else: 
                logger.error("CRITICAL: Acceptance received but review context was undefined during processing.")
                state.is_error = True
                state.error_message = "Accepted feedback, but review context was unclear internally. Please try again or restart."
                if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):\
                    state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
                return state.model_dump()
        
        else:
            # User provided modifications.
            logger.info("User provided modifications.")
            
            modification_triggers_description_revision = False

            if reviewing_task_list_for_feedback_context:
                logger.info("Modifications pertain to the TASK LIST or underlying description. Revising current_user_request.")
                state.task_list_accepted = False # Mark as not accepted due to modifications
                modification_triggers_description_revision = True
            
            elif reviewing_module_steps_for_feedback_context:
                # Check if the "modification" was just an empty input
                if not state.user_advice.strip():
                    logger.info("Empty feedback received for module steps. Re-presenting module steps for review.")
                    state.clarification_question = None # Clear any pending modification clarification
                    state.user_advice = None # Clear the empty advice
                    state.dialog_state = "sas_awaiting_module_steps_review" # Set to re-present module steps
                    # The AIMessage for re-presentation will be added on the next entry to the node when user_input is None
                    return state.model_dump()
                else: # Actual, non-empty modification advice provided
                    logger.info("Modifications pertain to the MODULE STEPS.")
                    state.module_steps_accepted = False # Mark as not accepted
                    
                    # Check if user's advice implies revising the overall description
                    advice_lower = state.user_advice.lower()
                    # Keywords for revising description (can be expanded)
                    revise_description_keywords = ["1", "revise description", "修改描述", "更新描述", "modify the overall task description"]
                    
                    if any(keyword in advice_lower for keyword in revise_description_keywords):
                        logger.info("User feedback on module steps implies revising the overall task description.")
                        state.task_list_accepted = False # Critical: task list will be invalidated and regenerated
                        # module_steps_accepted is already False
                        modification_triggers_description_revision = True
                    else:
                        # User feedback is specific to module steps and not a general description revision
                        logger.info("Modifications are specific to MODULE STEPS. This requires further logic for targeted refinement (TODO). Re-prompting for clarification.")
                        state.clarification_question = (
                            f"You've provided feedback on the module steps: '{state.user_advice}'. "
                            "To refine the module steps, please clarify if you want to: \n"
                            "1. Modify the overall task description (this will regenerate all tasks and steps).\n"
                            "2. Specify which task's steps need changes and describe those changes.\n"
                            "Or, you can say 'revise description with this feedback' to update the main description."
                        )
                        if not any(state.clarification_question in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                            state.messages = (state.messages or []) + [AIMessage(content=state.clarification_question)]
                        state.dialog_state = "sas_awaiting_module_steps_review" # Stay in module step review
                        # state.user_advice is kept for user to see their previous feedback
                        return state.model_dump() # End here, wait for more specific user input

            if modification_triggers_description_revision:
                # Original logic for revising current_user_request (primarily for task list / description changes)
                current_description_to_revise = state.current_user_request
                if not current_description_to_revise:
                    logger.error("CRITICAL: state.current_user_request is missing. Cannot revise description without it.")
                    state.is_error = True
                    state.error_message = "Revision cannot be performed because the current user request description is missing (internal system error)."
                    if not any(state.error_message in m.content for m in state.messages if isinstance(m, AIMessage)):
                        state.messages = state.messages + [AIMessage(content=state.error_message)]
                    state.user_advice = None # Clear advice as it can't be processed
                    return state.model_dump()

                logger.info(f"Description to revise (current_user_request): '{current_description_to_revise[:100]}...'")
                logger.info(f"User feedback for revision (user_advice): '{state.user_advice[:100]}...'")

                prompt_for_description_revision = f"""The original user robot task description is as follows:
'''
{current_description_to_revise}
'''

The user provided the following feedback on the above description or the task list generated based on it:
'''
{state.user_advice}
'''

Please carefully analyze the original description and user feedback to generate an updated, unified, and complete robot task description.
Your goal is to modify the original description to incorporate the user's feedback, not to comment on the feedback or directly generate a new task list.
Important: Please only output the full text of the revised robot task description. Your response must begin directly with the revised description text, without any other words, prefixes, explanations, or Markdown markup."""
                
                logger.info("Invoking LLM to revise the natural language description (current_user_request).")
                try:
                    llm_response = await llm.ainvoke([HumanMessage(content=prompt_for_description_revision)])
                    revised_description = llm_response.content
                    if not isinstance(revised_description, str): 
                        revised_description = str(revised_description)
                    
                    revised_description = revised_description.strip()
                    if revised_description.startswith("```") and revised_description.endswith("```"):
                        # Attempt to remove markdown code block fences if present, handling potential empty content
                        temp_desc = revised_description[3:-3].strip()
                        if temp_desc: # Only assign if there's content within the backticks
                            revised_description = temp_desc
                        # If temp_desc is empty, revised_description remains the original with backticks for error logging below
                    
                    logger.info(f"LLM generated revised description (first 200 chars): {revised_description[:200]}")
                    logger.info(f"FULL LLM generated revised_description:\n{revised_description}")

                    if not revised_description.strip(): # Check after potential stripping of markdown
                        logger.error("LLM returned an empty revised description.")
                        state.is_error = True
                        state.error_message = "LLM returned an empty revised description."
                        if not any(state.error_message in m.content for m in state.messages if isinstance(m, AIMessage)):
                            state.messages = state.messages + [AIMessage(content=state.error_message + " Please try again later or adjust your feedback. ")]
                        # Do not clear user_advice here, allow it to be re-evaluated by the graph logic if needed.
                        return state.model_dump()

                except Exception as e:
                    logger.error(f"LLM invocation for description revision failed: {e}", exc_info=True)
                    state.is_error = True
                    state.error_message = f"LLM description revision failed: {e}"
                    if not any(state.error_message in m.content for m in state.messages if isinstance(m, AIMessage)):
                        state.messages = state.messages + [AIMessage(content=f"User description revision failed (LLM call error): {e}")]
                    state.user_advice = None # Clear problematic advice
                    return state.model_dump()

                # Update state with the revised description
                state.current_user_request = revised_description 
                state.active_plan_basis = revised_description 
                state.revision_iteration += 1
                logger.info(f"current_user_request updated. New iteration: {state.revision_iteration}")

                # Update step_outputs.json with the new current_user_request
                if state.run_output_directory:
                    step_outputs_file_path = Path(state.run_output_directory) / "step_outputs.json"
                    try:
                        step_outputs_data = {"user_requests": [], "task_list_generations": []} # Default structure
                        if step_outputs_file_path.exists():
                            with open(step_outputs_file_path, "r", encoding="utf-8") as f_read:
                                step_outputs_data = json.load(f_read)
                        
                        # Ensure 'user_requests' key exists and is a list
                        if not isinstance(step_outputs_data.get("user_requests"), list):
                            step_outputs_data["user_requests"] = [] 
                        step_outputs_data["user_requests"].append(state.current_user_request) 

                        with open(step_outputs_file_path, "w", encoding="utf-8") as f_write:
                            json.dump(step_outputs_data, f_write, indent=2, ensure_ascii=False)
                        logger.info(f"Successfully appended revised current_user_request (Iteration {state.revision_iteration}) to: {step_outputs_file_path}")
                    except Exception as e_json_update:
                        logger.error(f"Failed to update {step_outputs_file_path} with revised request: {e_json_update}", exc_info=True)
                
                state.sas_step1_generated_tasks = [] # Clear previous tasks as description has changed
                state.module_steps_accepted = False # Also reset module step acceptance if description changes
                state.dialog_state = "sas_description_updated_for_regeneration"
                state.clarification_question = None
                state.user_advice = None # Clear advice as it has been processed into a new current_user_request
                
                update_message = f"Your description has been updated based on your feedback (iteration {state.revision_iteration}). Regenerating task list using the new description..."
                logger.info(update_message)
                if not any(update_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                    state.messages = state.messages + [AIMessage(content=update_message)]
            else:
                # This path should ideally not be hit if the logic above is complete.
                # It means user provided modifications, but it wasn't for task_list, 
                # nor was it module_step feedback that triggered description revision or re-prompting.
                logger.error("User provided modifications, but the system could not determine how to process them (e.g. not a task list change, and module step feedback did not lead to description revision or re-prompt). This is an unexpected state.")
                state.is_error = True
                state.error_message = "Internal error: Could not process modification feedback."
                if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
                return state.model_dump()

    return state.model_dump()

__all__ = [
    "review_and_refine_node"
] 