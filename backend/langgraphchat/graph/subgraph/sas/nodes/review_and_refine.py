import logging
import json
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

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
    logger.info(f"--- SAS: Review and Refine Task List Node (Iteration {state.revision_iteration}) ---")
    logger.info(f"RECEIVED user_input at START of review_and_refine_node: '{state.user_input}'")
    state.current_step_description = f"SAS: Awaiting user review (Iter: {state.revision_iteration}) or processing feedback."
    state.is_error = False
    # state.error_message = None # Keep existing error message if any, until cleared or overwritten
    # config = state.config # Config not explicitly used here, but good to have if future needs arise

    current_task_list_json_str = "[]"
    if state.sas_step1_generated_tasks:
        try:
            current_task_list_json_str = json.dumps([task.model_dump() for task in state.sas_step1_generated_tasks], indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error serializing current task list: {e}")
            current_task_list_json_str = "[Error serializing task list]"

    # This node operates based on state.user_input for new feedback.
    # If state.user_input is None, it means the graph is pausing for user review.
    if state.user_input is None:
        logger.info("No new user input for refinement. Presenting current task list for review.")
        question = f"""This is the task list generated based on the current description (iteration {state.revision_iteration}):

```json
{current_task_list_json_str}
```

Do you accept this task list? If you need to make changes, please let me know your opinion. You can directly say "accept" or "agree", or provide your modification instructions."""
        state.clarification_question = question
        if not state.messages or state.messages[-1].content != question:
            state.messages = (state.messages or []) + [AIMessage(content=question)]
        state.dialog_state = "sas_awaiting_task_list_review"
        state.task_list_accepted = False 
        state.user_advice = None # Ensure no stale advice
    else:
        # User has provided input, which is feedback on the previously presented task list.
        state.user_advice = state.user_input # Move feedback to user_advice
        state.user_input = None # Clear user_input as it's now processed into user_advice
        logger.info(f"Processing user feedback (advice): '{state.user_advice[:200]}...'")

        # Add user's feedback (advice) to message history
        if not state.messages or not (isinstance(state.messages[-1], HumanMessage) and state.messages[-1].content == state.user_advice):
            state.messages = (state.messages or []) + [HumanMessage(content=state.user_advice)]

        feedback_for_processing = state.user_advice.strip()
        
        acceptance_keywords_zh = ["accept", "agree", "can", "good", "no problem", "ok"] # Translated from Chinese
        acceptance_keywords_en = ["accept", "yes", "ok", "agree", "fine", "alright", "proceed"]
        
        is_accepted = False
        feedback_lower = feedback_for_processing.lower()
        if any(feedback_lower == keyword for keyword in acceptance_keywords_zh + acceptance_keywords_en):
            is_accepted = True
        elif any(keyword in feedback_lower for keyword in acceptance_keywords_zh + acceptance_keywords_en) and len(feedback_lower) <= 10: 
            is_accepted = True

        if is_accepted:
            logger.info("User accepted the task list.")
            state.task_list_accepted = True
            state.dialog_state = "sas_step1_tasks_generated" # Or a new state like "sas_task_list_accepted_proceeding"
            state.clarification_question = None
            state.user_advice = None # Clear advice as it has been processed (acceptance)
            if not any("Task list confirmed" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                 state.messages = state.messages + [AIMessage(content="Task list confirmed. Preparing for the next step. ")]
        else:
            logger.info("User provided modifications. Revising current_user_request using LLM.")
            state.task_list_accepted = False
            
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
            state.dialog_state = "sas_description_updated_for_regeneration"
            state.clarification_question = None
            state.user_advice = None # Clear advice as it has been processed into a new current_user_request
            
            update_message = f"Your description has been updated based on your feedback (iteration {state.revision_iteration}). Regenerating task list using the new description..."
            logger.info(update_message)
            if not any(update_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                state.messages = state.messages + [AIMessage(content=update_message)]

    return state.model_dump()

__all__ = [
    "review_and_refine_node"
] 