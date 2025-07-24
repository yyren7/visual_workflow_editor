import logging
import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, HumanMessage
from pydantic import ValidationError

from ..state import RobotFlowAgentState, TaskDefinition
from ..llm_utils import invoke_llm_for_text_output
from ..prompt_loader import get_sas_step1_task_list_generation_prompt

logger = logging.getLogger(__name__)

async def user_input_to_task_list_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    logger.info(f"--- Entering SAS Step 1: User Input to Task List Generation (dialog_state: {state.dialog_state}) ---")
    state.current_step_description = "SAS Step 1: Transforming user input to a structured task list."
    state.is_error = False
    state.error_message = None
    state.sas_step1_generated_tasks = None # Clear previous tasks at the beginning

    # Boolean flag to control saving of iteration data
    save_debug_data = False

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
        state.completion_status = "error"
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return state.model_dump()

    # Add the current_description_for_tasks (which is current_user_request) to messages
    # if it's not already the last HumanMessage or if messages are empty.
    # This ensures the LLM sees what description is being processed.
    # However, we should be cautious: if initialize_state also adds the first HumanMessage,
    # and then review_and_refine revises current_user_request, this could lead to redundant messages
    # if not handled carefully. The system_prompt + user_message_content to the LLM should encapsulate the task.

    formatted_prompt = get_sas_step1_task_list_generation_prompt(user_task_description=current_description_for_tasks, language=state.language)
    logger.debug(f"FULL formatted_prompt for task list generation:\n{formatted_prompt}")

    if not formatted_prompt:
        logger.error("Failed to load or format SAS Step 1 prompt for task list generation.")
        state.is_error = True
        state.error_message = "Internal error: Failed to prepare SAS Step 1 prompt (task list generation)."
        state.dialog_state = "error" 
        state.completion_status = "error"
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

    full_response_content = ""
    stream_id = f"sas_step1_llm_stream_{uuid.uuid4()}"

    try:
        # 使用标准的LangChain调用方式，让LangGraph事件系统能够捕获流式输出
        # 将system_prompt作为HumanMessage发送（符合Gemini的要求）
        messages = [
            HumanMessage(content=system_prompt),
            HumanMessage(content=formatted_prompt)
        ]
        
        # 使用标准的LangChain流式调用
        async for chunk in llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                chunk_text = str(chunk.content)
                if chunk_text:
                    full_response_content += chunk_text

        logger.info(f"LLM streaming finished for stream {stream_id}. Accumulated {len(full_response_content)} characters.")

    except Exception as e:
        logger.error(f"Error streaming LLM output in user_input_to_task_list_node for stream {stream_id}: {e}", exc_info=True)
        error_message_content = f"LLM streaming failed: {e}. "
        if full_response_content:
            error_message_content += f"Partial content: \'{full_response_content[:100]}...\'"
        else:
            error_message_content += "No content received before error."
        
        state.is_error = True
        state.error_message = error_message_content 
        state.dialog_state = "generation_failed"
        state.completion_status = "error"
        full_response_content = "" # Reset content on stream error
    
    # 流式处理完成后，如果有完整响应，将其作为AI消息添加到状态中
    if full_response_content and not state.is_error:
        ai_message = AIMessage(content=full_response_content, id=stream_id)
        state.messages = (state.messages or []) + [ai_message]
        logger.info(f"Added complete AI response to messages (stream {stream_id})")
    
    # After streaming loop (successful or with error)

    final_message_content_for_this_node: Optional[str] = None
    final_message_is_error = False

    if state.is_error: # If stream failed
        final_message_content_for_this_node = state.error_message
        final_message_is_error = True

    elif not full_response_content: # Stream finished with no error, but no content
        logger.error(f"LLM returned no content after streaming successfully for stream {stream_id}.")
        state.is_error = True
        state.error_message = "LLM returned no content."
        final_message_content_for_this_node = state.error_message
        final_message_is_error = True
        state.dialog_state = "generation_failed"
        state.completion_status = "error"

    if final_message_content_for_this_node is None: # Means no prior critical error, or stream error with partial content
        raw_json_output = full_response_content.strip()
        logger.debug(f"Aggregated raw LLM output for task list (stream {stream_id}): {raw_json_output}")
        
        try:
            if raw_json_output.startswith("```json"):
                raw_json_output = raw_json_output[len("```json"):].strip()
                if raw_json_output.endswith("```"):
                    raw_json_output = raw_json_output[:-len("```")]
            
            parsed_tasks_json = json.loads(raw_json_output)
            
            if not isinstance(parsed_tasks_json, list):
                # Use a more specific error that will be user-facing
                raise ValueError("LLM output should be a JSON list of tasks, but it was not.")

            # Check for empty task list
            if not parsed_tasks_json:
                logger.warning(f"LLM generated an empty task list for stream {stream_id}. This might indicate the input was unclear or too complex.")
                state.is_error = True
                state.error_message = "抱歉，我无法从您的描述中识别出具体的任务。请提供更清晰、更具体的机器人任务描述，包括具体的操作步骤。"
                state.dialog_state = "generation_failed"
                state.completion_status = "error"
                final_message_content_for_this_node = state.error_message
                final_message_is_error = True
            else:
                generated_tasks: List[TaskDefinition] = []
                for task_data in parsed_tasks_json:
                    generated_tasks.append(TaskDefinition(**task_data))
                
                state.sas_step1_generated_tasks = generated_tasks
                logger.info(f"SAS Step 1 (Task List Generation) completed successfully for stream {stream_id}. {len(generated_tasks)} tasks generated for request iteration {state.revision_iteration}.")
                task_names = [task.name for task in generated_tasks]
                logger.info(f"Generated task names: {task_names}")

                # The dialog_state is now managed by the graph's routing logic.
                # This node's responsibility is to set the output and error flags.
                state.current_step_description = f"SAS Step 1: Structured task list generated successfully (Iteration {state.revision_iteration})."
                
                final_message_content_for_this_node = f"成功为请求 (迭代 {state.revision_iteration}) 生成了包含 {len(generated_tasks)} 个任务的任务列表: {', '.join(task_names[:3])}{'...' if len(task_names) > 3 else ''}."
                state.completion_status = "processing" # Use "processing" to indicate the graph should continue
                state.is_error = False
                state.error_message = None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM JSON output for task list (stream {stream_id}): {e}. Output: {raw_json_output}", exc_info=True)
            state.is_error = True
            state.error_message = f"从LLM收到的任务列表JSON格式无效: {e}"
            final_message_content_for_this_node = state.error_message
            final_message_is_error = True
            state.dialog_state = "generation_failed"
            state.completion_status = "error"
        except ValidationError as e:
            logger.error(f"Validation error for generated task list (stream {stream_id}): {e}. Parsed JSON: {parsed_tasks_json if 'parsed_tasks_json' in locals() else 'Error before parsing'}", exc_info=True)
            state.is_error = True
            error_detail_str = str(e)
            simplified_error_msg = f"生成的任务列表结构校验失败。错误数量: {len(e.errors())}。首个错误细节: {e.errors()[0]['type'] if e.errors() else 'N/A'} at path \'{'.'.join(map(str,e.errors()[0]['loc'])) if e.errors() else 'N/A'}\'."
            state.error_message = simplified_error_msg
            final_message_content_for_this_node = state.error_message
            final_message_is_error = True
            state.dialog_state = "generation_failed"
            state.completion_status = "error"
        except Exception as e: # Catch any other exception during parsing/validation
            logger.error(f"An unexpected error occurred while processing the LLM output for task list (stream {stream_id}): {e}. Output: {raw_json_output}", exc_info=True)
            state.is_error = True
            state.error_message = f"处理任务列表时发生意外错误: {e}"
            final_message_content_for_this_node = state.error_message
            final_message_is_error = True
            state.dialog_state = "generation_failed"
            state.completion_status = "error"

    if final_message_content_for_this_node:
        state.messages = (state.messages or []) + [AIMessage(content=final_message_content_for_this_node, id=stream_id)]
        log_msg_type = "Error" if final_message_is_error else "Success"
        logger.info(f"Final {log_msg_type} AIMessage (ID: {stream_id}) set: \"{final_message_content_for_this_node[:100]}...\"")

    # Ensure state.error_message correctly reflects the final message if it was an error
    if final_message_is_error and final_message_content_for_this_node:
        state.error_message = final_message_content_for_this_node
            
    return state.model_dump() 