import logging
from typing import Dict, Any, List, Tuple, Optional
import json
from pathlib import Path
import re
import asyncio

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage

from ..state import RobotFlowAgentState, TaskDefinition
from ..prompt_loader import load_raw_prompt_file, load_node_descriptions
from ..llm_utils import invoke_llm_for_text_output

logger = logging.getLogger(__name__)

# 引入事件广播器（如果存在的话）
try:
    from backend.app.routers.sas_chat import event_broadcaster
    EVENT_BROADCASTER_AVAILABLE = True
    logger.info("SAS Step 2 Node: Event broadcaster imported successfully")
except ImportError:
    EVENT_BROADCASTER_AVAILABLE = False
    logger.warning("SAS Step 2 Node: Event broadcaster not available, progress events will not be sent")

# Directory for task-specific Step 2 prompts
STEP2_PROMPT_DIR = Path("/workspace/database/prompt_database/task_based_prompt/step2_task_type_prompts")
DEFAULT_FALLBACK_PROMPT_TEXT = """\
You are an AI assistant. Your task is to generate a list of detailed steps for a robot task.
The user will provide a task definition. Based on this, provide a JSON array of strings, where each string is a detailed step.
Example Input:
{
  "name": "Example_Task",
  "type": "ExampleType",
  "sub_tasks": [],
  "description": "This is an example task."
}
Expected Output:
["Step 1 for Example_Task", "Step 2 for Example_Task"]
"""

async def _send_task_progress_event(chat_id: str, task_index: int, task_name: str, status: str, details: Optional[str] = None):
    """发送任务进度事件到前端，匹配前端TaskNode期望的事件格式"""
    if EVENT_BROADCASTER_AVAILABLE and chat_id:
        try:
            if status == "processing":
                # 发送开始事件
                event_data = {
                    "type": "task_detail_generation_start",
                    "data": {
                        "taskIndex": task_index,
                        "task_name": task_name,
                        "details": details,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                }
                await event_broadcaster.broadcast_event(chat_id, event_data)
                logger.debug(f"[TASK_PROGRESS] 发送开始事件: 任务{task_index} ({task_name})")
            elif status in ["completed", "error"]:
                # 发送结束事件
                event_data = {
                    "type": "task_detail_generation_end", 
                    "data": {
                        "taskIndex": task_index,
                        "task_name": task_name,
                        "status": "success" if status == "completed" else "failure",
                        "error_message": details if status == "error" else None,
                        "details": details if status == "completed" else None,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                }
                await event_broadcaster.broadcast_event(chat_id, event_data)
                logger.debug(f"[TASK_PROGRESS] 发送结束事件: 任务{task_index} ({task_name}) - {status}")
        except Exception as e:
            logger.warning(f"[TASK_PROGRESS] 发送进度事件失败: {e}")

async def _send_step_overall_event(chat_id: str, status: str, details: Optional[str] = None):
    """发送SAS Step 2整体进度事件"""
    if EVENT_BROADCASTER_AVAILABLE and chat_id:
        try:
            event_data = {
                "type": "sas_step2_progress",
                "data": {
                    "status": status,
                    "details": details,
                    "timestamp": asyncio.get_event_loop().time()
                }
            }
            await event_broadcaster.broadcast_event(chat_id, event_data)
            logger.debug(f"[SAS_STEP2] 发送整体进度事件: {status}")
        except Exception as e:
            logger.warning(f"[SAS_STEP2] 发送整体进度事件失败: {e}")

def _generate_available_blocks_markdown(node_descriptions: Dict[str, str]) -> str:
    """
    Formats the available node descriptions into a markdown string for prompt injection.
    """
    if not node_descriptions:
        logger.warning(
            "No node descriptions loaded. LLM will rely on its general knowledge. "
            "A placeholder warning will be added to the prompt."
        )
        return (
            "\\n\\n## Available Robot Control Blocks\\n\\n"
            "**Warning**: No specific block descriptions were dynamically loaded. "
            "Please ensure all generated steps can be implemented with standard robot "
            "control blocks and refer to any examples provided in the task-specific prompt for guidance.\\n"
        )

    logger.info(f"Successfully formatted {len(node_descriptions)} node description(s).")
    available_blocks_section = "\\n\\n## Available Robot Control Blocks (Dynamically Loaded from Central Repository)\\n\\n"
    available_blocks_section += (
        "**CRITICAL REQUIREMENT**: All generated module steps MUST strictly correspond to the "
        "following available blocks. Do NOT create steps that "
        "exceed these block capabilities or invent new block types not listed here.\\n\\n"
    )
    available_blocks_section += "### Block Types and Their Capabilities:\\n\\n"
    for block_type, description in sorted(node_descriptions.items()): # Sorting for consistent output
        available_blocks_section += f"- **{block_type.strip()}**: {description.strip()}\\n"
    
    available_blocks_section += (
        "\\n### Adherence to these explicitly listed blocks is mandatory for successful robot "
        "program generation. These definitions supersede any examples in the task-specific prompt if conflicts arise.\\n"
    )
    return available_blocks_section

def _get_formatted_sas_step2_user_prompt(
    task_definition: TaskDefinition, 
    available_blocks_markdown: str,
    base_prompt_template: str
) -> str:
    """
    Formats the final user message for the LLM for SAS Step 2,
    injecting task definition and available blocks into the base prompt template.
    """
    # Inject available blocks markdown into the base prompt template
    # The new prompts use: (System will inject "Available Robot Control Blocks" here)
    block_injection_marker = '(System will inject "Available Robot Control Blocks" here)'
    prompt_with_blocks = base_prompt_template.replace(block_injection_marker, available_blocks_markdown)

    # Prepare the current task's definition as a JSON string for injection
    # Ensure sub_tasks is a list of strings, not objects, if that's the case.
    # This depends on how TaskDefinition stores sub_tasks. Assuming it's List[str].
    task_input_dict = {
        "name": getattr(task_definition, 'name', 'Unnamed Task'),
        "type": getattr(task_definition, 'type', 'UnknownType'),
        "sub_tasks": getattr(task_definition, 'sub_tasks', []),
        "description": getattr(task_definition, 'description', '')
    }
    task_input_json_str = json.dumps(task_input_dict, indent=2)

    # Append the task-specific input section to the prompt
    # The task-specific prompts expect this structure.
    formatted_user_input_section = f"""

## Input Task Definition (Current Task Being Processed)

```json
{task_input_json_str}
```

## Your Detailed Steps Output (JSON Array of Strings)

**IMPORTANT REMINDERS** (Review instructions in the prompt above for task type: **{task_input_dict['type']}**):
- Generate **ONLY a JSON array of strings** as your output. Each string is a detailed step.
- Ensure every step strictly corresponds to an **Available Robot Control Block** listed above.

Please generate the detailed steps for the task defined above:
"""
    
    return prompt_with_blocks + formatted_user_input_section

async def _generate_steps_for_single_task_async(
    task_def: TaskDefinition,
    llm: BaseChatModel,
    available_blocks_markdown: str,
    node_index: int, # For logging
    chat_id: Optional[str] = None  # 新增: 用于发送进度事件
) -> Tuple[str, List[str], Optional[str]]: # Returns (task_name, list_of_details, error_message_or_none)
    task_name = getattr(task_def, 'name', f"Unnamed Task {node_index+1}")
    task_type = getattr(task_def, 'type', 'UnknownType')

    # 发送开始处理事件
    if chat_id:
        await _send_task_progress_event(chat_id, node_index, task_name, "processing", f"开始为任务 '{task_name}' (类型: {task_type}) 生成模块步骤")

    prompt_file_name = f"step2_{task_type.lower()}_prompt_en.md"
    prompt_file_path = STEP2_PROMPT_DIR / prompt_file_name
    
    base_prompt_template: Optional[str] = None
    if prompt_file_path.exists():
        base_prompt_template = load_raw_prompt_file(str(prompt_file_path))

    if not base_prompt_template:
        logger.warning(f"Prompt file not found or empty: {prompt_file_path} for task type '{task_type}'. Using fallback.")
        base_prompt_template = DEFAULT_FALLBACK_PROMPT_TEXT

    if not getattr(task_def, 'description', None):
        task_def.description = f"Task: {task_name}, Type: {task_type}. Generate appropriate steps."
        logger.warning(f"Task '{task_name}' had an empty description. Using a generated one.")

    user_prompt_content = _get_formatted_sas_step2_user_prompt(
        task_definition=task_def,
        available_blocks_markdown=available_blocks_markdown,
        base_prompt_template=base_prompt_template
    )

    logger.info(f"Invoking LLM for SAS Step 2 for task: '{task_name}' (Type: '{task_type}').")
    
    system_prompt_content = """\\
You are an AI assistant specialized in converting robot task definitions into specific, executable module steps.

CRITICAL REQUIREMENTS:
1.  Analyze the provided **Input Task Definition** (name, type, sub_tasks, description).
2.  Follow the detailed instructions and examples within the user message, which are specific to the task\'s `type`.
3.  Generate a sequence of detailed steps for the robot.
4.  **Every generated step MUST strictly correspond to an "Available Robot Control Block"** detailed in the user message. Do not invent blocks or functionalities.
5.  Assign concrete parameters as exemplified (point codes like P1, P21, I/O pin numbers, variable names, etc.).
6.  Respect all precautions and limitations for each block type mentioned.
7.  Your output MUST be **ONLY a valid JSON array of strings**. Each string in the array is a single, detailed step description, including its (Block Type: `block_name`) annotation.
    Example: `["1. Select robot (Block Type: select_robot)", "2. Move to P1 (Block Type: moveP)"]`
8.  Do NOT include any extra headers, explanations, or markdown formatting outside the JSON array itself."""

    llm_response_content = ""
    try:
        # 使用标准的LangChain调用方式，让LangGraph事件系统能够捕获流式输出
        messages = [
            HumanMessage(content=system_prompt_content),
            HumanMessage(content=user_prompt_content)
        ]
        
        async for chunk in llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                chunk_text = str(chunk.content)
                if chunk_text:
                    llm_response_content += chunk_text
        
        if not llm_response_content.strip():
             raise ValueError("LLM returned empty content.")

        generated_steps_str = llm_response_content.strip()
        if generated_steps_str.startswith("```json"):
            generated_steps_str = generated_steps_str[len("```json"):]
        if generated_steps_str.endswith("```"):
            generated_steps_str = generated_steps_str.rsplit("```", 1)[0].strip()

        parsed_details = json.loads(generated_steps_str)
            
        if isinstance(parsed_details, list) and all(isinstance(s, str) for s in parsed_details):
            logger.info(f"SAS Step 2 LLM call successful for task '{task_name}'. {len(parsed_details)} module steps generated.")
            # 发送成功完成事件
            if chat_id:
                await _send_task_progress_event(chat_id, node_index, task_name, "completed", f"成功生成 {len(parsed_details)} 个模块步骤")
            return task_name, parsed_details, None
        else:
            raise ValueError("Parsed JSON is not a list of strings.")

    except Exception as e:
        error_msg = f"Error processing task '{task_name}': {e}. Raw LLM output hint: {llm_response_content[:200]}..."
        logger.error(error_msg, exc_info=True)
        # 发送错误事件
        if chat_id:
            await _send_task_progress_event(chat_id, node_index, task_name, "error", f"处理失败: {str(e)[:100]}")
        return task_name, [f"Error: Could not generate module steps. Details: {str(e)[:100]}"], error_msg

async def process_description_to_module_steps_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    SAS Step 2: Convert detailed process description for each task from Step 1 
    into specific, executable module steps using task-type-specific prompts.
    """
    logger.info(f"--- Entering SAS Step 2: Process Description to Module Steps (dialog_state: {state.dialog_state}) ---")
    
    # 尝试从状态中获取chat_id，如果没有则为None
    chat_id = getattr(state, 'current_chat_id', None) or getattr(state, 'thread_id', None)
    
    # SSE事件队列已移除，不再进行队列检查
    logger.info("[SSE] SSE事件队列功能已在新架构中通过其他方式处理")
    
    logger.info(f"    Initial state.task_list_accepted in SAS_PROCESS_TO_MODULE_STEPS: {state.task_list_accepted}")
    state.current_step_description = "SAS Step 2: Converting individual task descriptions to specific module steps (parallel execution)."
    state.is_error = False
    state.error_message = None
    aggregate_error_messages = []
    all_generated_module_steps_for_logging = []

    if not state.sas_step1_generated_tasks:
        logger.error("state.sas_step1_generated_tasks is missing. Cannot perform SAS Step 2.")
        state.is_error = True
        state.error_message = "Task list from SAS Step 1 is missing."
        state.dialog_state = "error"
        state.completion_status = "error"
        return state.dict(exclude_none=True)

    # 发送Step 2开始事件
    if chat_id:
        await _send_step_overall_event(chat_id, "processing", f"开始并行处理 {len(state.sas_step1_generated_tasks)} 个任务的模块步骤生成")

    node_descriptions = load_node_descriptions()
    available_blocks_markdown = _generate_available_blocks_markdown(node_descriptions)

    coroutines = []
    for i, task_def in enumerate(state.sas_step1_generated_tasks):
        task_def.details = [] 
        
        # SSE事件现在通过外部SSE处理器发送，不再通过状态队列
        logger.info(f"[SAS Step 2] 开始为任务 {i}: {getattr(task_def, 'name', f'Task {i+1}')} 生成模块步骤")

        coroutines.append(
            _generate_steps_for_single_task_async(
                task_def=task_def,
                llm=llm,
                available_blocks_markdown=available_blocks_markdown,
                node_index=i,
                chat_id=chat_id
            )
        )

    logger.info(f"Starting parallel generation of module steps for {len(coroutines)} tasks.")
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    logger.info(f"Finished parallel generation. Received {len(results)} results.")

    successful_tasks = 0
    failed_tasks = 0

    for i, result_or_exception in enumerate(results):
        task_def_to_update = state.sas_step1_generated_tasks[i]
        task_name_for_log = getattr(task_def_to_update, 'name', f"Unnamed Task {i+1}")
        task_type_for_log = getattr(task_def_to_update, 'type', 'UnknownType')

        task_status = "success"
        task_error_message = None

        if isinstance(result_or_exception, Exception):
            error_msg = f"Exception during module step generation for task '{task_name_for_log}': {str(result_or_exception)}"
            logger.error(error_msg, exc_info=result_or_exception)
            task_def_to_update.details = [f"Error: Exception occurred - {str(result_or_exception)[:150]}"]
            aggregate_error_messages.append(f"Error for {task_name_for_log}: {str(result_or_exception)}")
            state.is_error = True
            task_status = "failure"
            task_error_message = str(result_or_exception)
            failed_tasks += 1
        elif isinstance(result_or_exception, tuple):
            _processed_task_name, processed_details, individual_task_error_msg = result_or_exception
            task_def_to_update.details = processed_details
            if individual_task_error_msg:
                aggregate_error_messages.append(f"Error for {_processed_task_name} (reported by helper): {individual_task_error_msg}")
                state.is_error = True
                logger.warning(f"Task '{_processed_task_name}' completed with reported error: {individual_task_error_msg}")
                task_status = "failure"
                task_error_message = individual_task_error_msg
                failed_tasks += 1
            else:
                all_generated_module_steps_for_logging.append(f"### Module Steps for Task: {task_name_for_log} (Type: {task_type_for_log})\\n{json.dumps(processed_details, indent=2)}")
                logger.info(f"Successfully processed and updated details for task '{task_name_for_log}'.")
                successful_tasks += 1
        else:
            # Handle cases where the result is not an exception or the expected tuple
            error_msg = f"Unexpected result type for task '{task_name_for_log}': {type(result_or_exception)}"
            logger.error(error_msg)
            task_def_to_update.details = [f"Error: Unexpected result type during processing."]
            aggregate_error_messages.append(f"Error for {task_name_for_log}: Unexpected result type.")
            state.is_error = True
            task_status = "failure"
            task_error_message = "Unexpected result type."
            failed_tasks += 1
        
        # SSE事件现在通过外部SSE处理器发送，不再通过状态队列
        logger.info(f"[SAS Step 2] 任务 {i} ({task_name_for_log}) 处理完成，状态: {task_status}")

    # 发送Step 2完成汇总事件
    completion_status_event = "completed" if not state.is_error else "error"
    completion_details = f"并行处理完成: {successful_tasks} 个任务成功, {failed_tasks} 个任务失败"
    if chat_id:
        await _send_step_overall_event(chat_id, completion_status_event, completion_details)

    if state.is_error:
        final_error_detail = "; ".join(aggregate_error_messages) if aggregate_error_messages else "Unknown error during parallel module step generation."
        state.error_message = f"SAS Step 2 encountered errors: {final_error_detail}"
        logger.error(state.error_message)
        state.dialog_state = "error"
        state.completion_status = "error"
        if not any(state.error_message in str(msg.content) for msg in (state.messages or []) if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
    else:
        state.sas_step2_module_steps = "\\n\\n".join(all_generated_module_steps_for_logging) 
        state.dialog_state = "sas_step2_module_steps_generated_for_review"
        state.current_step_description = f"SAS Step 2: Module steps generated in parallel for all {len(state.sas_step1_generated_tasks)} tasks, awaiting review."
        
        logger.info("Populating state.parsed_flow_steps from successfully processed tasks after parallel execution.")
        parsed_steps_list = []
        for task_def_obj in state.sas_step1_generated_tasks:
            # Check if task_def_obj.details has error messages; if so, perhaps exclude or mark them?
            # For now, assume details are either good steps or an error string from the helper.
            # The generate_individual_xmls_node will need to handle potentially error-filled details.
            parsed_steps_list.append({
                "name": getattr(task_def_obj, 'name', 'UnknownTaskName'),
                "type": getattr(task_def_obj, 'type', 'UnknownTaskType'),
                "description": getattr(task_def_obj, 'description', ''),
                "details": getattr(task_def_obj, 'details', []), # These are the crucial module steps
                "sub_tasks": getattr(task_def_obj, 'sub_tasks', [])
            })
        state.parsed_flow_steps = parsed_steps_list
        logger.info(f"Successfully populated state.parsed_flow_steps with {len(state.parsed_flow_steps)} entries after parallel processing.")
        
        review_message = (
            f"Module steps have been generated in parallel for all {len(state.sas_step1_generated_tasks)} tasks "
            f"and assigned to their respective 'details' fields. They are now ready for your review."
        )
        if not any(review_message in str(msg.content) for msg in (state.messages or []) if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=review_message)]
        state.completion_status = "completed_partial"
        
    logger.info(f"    Final state.task_list_accepted in SAS_PROCESS_TO_MODULE_STEPS: {state.task_list_accepted}")
    return state.dict(exclude_none=True) 

__all__ = [
    "process_description_to_module_steps_node"
] 