import logging
from typing import Dict, Any, List
import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import ValidationError

from ..state import RobotFlowAgentState, TaskDefinition
from ..prompt_loader import get_sas_step1_task_list_generation_prompt
from ..llm_utils import invoke_llm_for_text_output

logger = logging.getLogger(__name__)

async def user_input_to_task_list_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    logger.info(f"--- Entering SAS Step 1: User Input to Task List Generation (dialog_state: {state.dialog_state}) ---")
    state.current_step_description = "SAS Step 1: Transforming user input to a structured task list."
    state.is_error = False
    state.error_message = None
    state.sas_step1_generated_tasks = None # Clear previous tasks at the beginning

    # This node now uses state.current_user_request as the source for task generation.
    # state.user_input should have been cleared by initialize_state_node or review_and_refine_node.
    # if state.user_input is not None: # MODIFIED: Commented out this block
    #     logger.warning(f"state.user_input was expected to be None but found: '{state.user_input[:100]}...'. This node uses current_user_request. Clearing user_input.")
    #     state.user_input = None

    current_description_for_tasks = state.current_user_request
    if not current_description_for_tasks:
        logger.error("state.current_user_request is missing for SAS Step 1 (Task List Generation). This is required.")
        state.is_error = True
        state.error_message = "Critical: current_user_request is required for SAS Step 1 but was not found."
        state.dialog_state = "error" # A more critical error state
        state.subgraph_completion_status = "error"
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return state.model_dump()

    # Add the current_description_for_tasks (which is current_user_request) to messages
    # if it's not already the last HumanMessage or if messages are empty.
    # This ensures the LLM sees what description is being processed.
    # However, we should be cautious: if initialize_state also adds the first HumanMessage,
    # and then review_and_refine revises current_user_request, this could lead to redundant messages
    # if not handled carefully. The prompt for review_and_refine should manage its own HumanMessage from user feedback.
    # For this node, ensure the *basis* of its generation (current_user_request) is in history.
    # Let's assume for now that message history is managed correctly by upstream nodes (init, review_and_refine)
    # and current_user_request reflects the text this node should process.
    # A simple check: if the last message is not this current_user_request, add it.
    # This might be redundant if current_user_request was JUST set from user_input which also went into messages.
    # This logic is tricky. For now, let's assume the prompt context is sufficient and avoid altering message history here
    # unless a clear need is established. The system_prompt + user_message_content to the LLM should encapsulate the task.

    formatted_prompt = get_sas_step1_task_list_generation_prompt(user_task_description=current_description_for_tasks, language=state.language)
    logger.debug(f"FULL formatted_prompt for task list generation:\n{formatted_prompt}")

    if not formatted_prompt:
        logger.error("Failed to load or format SAS Step 1 prompt for task list generation.")
        state.is_error = True
        state.error_message = "Internal error: Failed to prepare SAS Step 1 prompt (task list generation)."
        state.dialog_state = "error" 
        state.subgraph_completion_status = "error"
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return state.model_dump()

    logger.info(f"Invoking LLM for SAS Step 1: Task List Generation based on current_user_request (iteration {state.revision_iteration}).")
    
    system_prompt = (
        "You are an AI assistant specialized in robotic process automation. "
        "Your task is to analyze the user's robot task description and the provided contextual information (Task Type Descriptions, Allowed Block Types). "
        "Based on this, you must generate a structured Task List in JSON format. "
        "The JSON output should be a list of task objects, adhering strictly to the format and guidelines specified in the user message. "
        "Ensure the JSON is well-formed and complete."
    )

    llm_response_text = await invoke_llm_for_text_output(
        llm=llm,
        system_prompt_content=system_prompt,
        user_message_content=formatted_prompt,
        message_history=None # Assuming messages in state are for overall history, not direct LLM context for this specific call
    )

    if "error" in llm_response_text or not llm_response_text.get("text_output"):
        error_detail = llm_response_text.get('error', 'Unknown LLM error')
        error_msg_detail = llm_response_text.get('details', 'N/A')
        logger.error(f"LLM call for SAS Step 1 (Task List) failed. Error: {error_detail}, Details: {error_msg_detail}")
        state.is_error = True
        state.error_message = f"LLM failed to generate task list: {error_detail}. Details: {error_msg_detail}"
        state.dialog_state = "generation_failed"
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        state.subgraph_completion_status = "error"
    else:
        raw_json_output = llm_response_text["text_output"].strip()
        logger.debug(f"Raw LLM output for task list: {raw_json_output}")
        
        try:
            if raw_json_output.startswith("```json"):
                raw_json_output = raw_json_output[len("```json"):].strip()
                if raw_json_output.endswith("```"):
                    raw_json_output = raw_json_output[:-len("```")]
            
            parsed_tasks_json = json.loads(raw_json_output)
            
            if not isinstance(parsed_tasks_json, list):
                raise ValueError("LLM output is not a JSON list.")

            generated_tasks: List[TaskDefinition] = []
            for task_data in parsed_tasks_json:
                generated_tasks.append(TaskDefinition(**task_data))
            
            state.sas_step1_generated_tasks = generated_tasks
            logger.info(f"SAS Step 1 (Task List Generation) completed successfully. {len(generated_tasks)} tasks generated for request iteration {state.revision_iteration}.")
            task_names = [task.name for task in generated_tasks]
            logger.info(f"Generated task names: {task_names}")

            state.dialog_state = "sas_step1_tasks_generated"
            state.current_step_description = f"SAS Step 1: Structured task list generated successfully (Iteration {state.revision_iteration})."
            
            success_message_content = f"成功为请求 (迭代 {state.revision_iteration}) 生成了包含 {len(generated_tasks)} 个任务的任务列表: {', '.join(task_names[:3])}{'...' if len(task_names) > 3 else ''}."
            if not any(msg.content == success_message_content for msg in state.messages if isinstance(msg, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=success_message_content)]
            state.subgraph_completion_status = "completed_partial" # Or "processing" if more steps are guaranteed

            if state.run_output_directory:
                # Create a specific filename for this iteration's task list
                iteration_tasks_filename = f"sas_step1_tasks_iter{state.revision_iteration}.json"
                iteration_tasks_file_path = Path(state.run_output_directory) / iteration_tasks_filename
                
                try:
                    # The content will just be the list of tasks for this iteration
                    tasks_to_save = [task.model_dump() for task in generated_tasks]
                    
                    with open(iteration_tasks_file_path, "w", encoding="utf-8") as f_write:
                        json.dump(tasks_to_save, f_write, indent=2, ensure_ascii=False)
                    logger.info(f"Successfully saved generated task list (Iteration {state.revision_iteration}) to: {iteration_tasks_file_path}")
                except Exception as e:
                    logger.error(f"Failed to save task list for Iteration {state.revision_iteration} to {iteration_tasks_file_path}. Error: {e}", exc_info=True)
            else:
                logger.warning("state.run_output_directory is not set. Skipping saving of iteration-specific task list.")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM JSON output for task list: {e}. Output: {raw_json_output}", exc_info=True)
            state.is_error = True
            state.error_message = f"从LLM收到的任务列表JSON格式无效: {e}"
            state.dialog_state = "generation_failed"
            if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
            state.subgraph_completion_status = "error"
        except ValidationError as e:
            logger.error(f"Validation error for generated task list: {e}. Parsed JSON: {parsed_tasks_json if 'parsed_tasks_json' in locals() else 'Error before parsing'}", exc_info=True)
            state.is_error = True
            state.error_message = f"生成的任务列表不符合预期结构: {e}"
            state.dialog_state = "generation_failed"
            if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
            state.subgraph_completion_status = "error"
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing the LLM output for task list: {e}. Output: {raw_json_output}", exc_info=True)
            state.is_error = True
            state.error_message = f"处理任务列表时发生意外错误: {e}"
            state.dialog_state = "generation_failed"
            if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
            state.subgraph_completion_status = "error"
            
    # Ensure user_input is cleared before exiting, as its content (if any) should have been processed
    # or is irrelevant to the next step (review_and_refine, which expects new feedback).
    # state.user_input = None # MODIFIED: Commented out
    return state.model_dump() 