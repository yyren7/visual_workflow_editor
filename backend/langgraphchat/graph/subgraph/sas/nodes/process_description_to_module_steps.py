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
    node_index: int # For logging
) -> Tuple[str, List[str], Optional[str]]: # Returns (task_name, list_of_details, error_message_or_none)
    task_name = getattr(task_def, 'name', f"Unnamed Task {node_index+1}")
    task_type = getattr(task_def, 'type', 'UnknownType')

    prompt_file_name = f"step2_{task_type.lower()}_prompt_en.md"
    prompt_file_path = STEP2_PROMPT_DIR / prompt_file_name
    
    base_prompt_template: str
    if prompt_file_path.exists():
        base_prompt_template = load_raw_prompt_file(str(prompt_file_path))
        if not base_prompt_template:
            logger.error(f"Failed to load SAS Step 2 prompt file: {prompt_file_path} for task type '{task_type}'. Using fallback.")
            base_prompt_template = DEFAULT_FALLBACK_PROMPT_TEXT
    else:
        logger.warning(f"Prompt file not found: {prompt_file_path} for task type '{task_type}'. Using fallback.")
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
        async for chunk in invoke_llm_for_text_output(
            llm=llm,
            system_prompt_content=system_prompt_content,
            user_message_content=user_prompt_content,
            message_history=None
        ):
            if isinstance(chunk, str):
                llm_response_content += chunk
            elif isinstance(chunk, dict) and "error" in chunk: # Handle potential error dicts from stream
                raise Exception(f"LLM stream error for {task_name}: {chunk.get('error')} - Details: {chunk.get('details')}")
        
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
            return task_name, parsed_details, None
        else:
            raise ValueError("Parsed JSON is not a list of strings.")

    except Exception as e:
        error_msg = f"Error processing task '{task_name}': {e}. Raw LLM output hint: {llm_response_content[:200]}..."
        logger.error(error_msg, exc_info=True)
        return task_name, [f"Error: Could not generate module steps. Details: {str(e)[:100]}"], error_msg

async def process_description_to_module_steps_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    SAS Step 2: Convert detailed process description for each task from Step 1 
    into specific, executable module steps using task-type-specific prompts.
    """
    logger.info(f"--- Entering SAS Step 2: Process Description to Module Steps (dialog_state: {state.dialog_state}) ---")
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
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    node_descriptions = load_node_descriptions()
    available_blocks_markdown = _generate_available_blocks_markdown(node_descriptions)

    # Create a list of coroutines for processing each task
    coroutines = []
    for i, task_def in enumerate(state.sas_step1_generated_tasks):
        # Initialize/clear details for the current task before starting async processing
        task_def.details = [] 
        coroutines.append(
            _generate_steps_for_single_task_async(
                task_def=task_def,
                llm=llm,
                available_blocks_markdown=available_blocks_markdown,
                node_index=i
            )
        )

    # Run all task processing coroutines concurrently
    logger.info(f"Starting parallel generation of module steps for {len(coroutines)} tasks.")
    # return_exceptions=True allows us to gather all results, even if some tasks fail
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    logger.info(f"Finished parallel generation. Received {len(results)} results.")

    # Process results
    for i, result_or_exception in enumerate(results):
        task_def_to_update = state.sas_step1_generated_tasks[i] # Get the original task object
        task_name_for_log = getattr(task_def_to_update, 'name', f"Unnamed Task {i+1}")
        task_type_for_log = getattr(task_def_to_update, 'type', 'UnknownType')

        if isinstance(result_or_exception, Exception):
            # Handle exceptions raised by _generate_steps_for_single_task_async explicitly
            error_msg = f"Exception during module step generation for task '{task_name_for_log}': {str(result_or_exception)}"
            logger.error(error_msg, exc_info=result_or_exception) # Log with exc_info
            task_def_to_update.details = [f"Error: Exception occurred - {str(result_or_exception)[:150]}"]
            aggregate_error_messages.append(f"Error for {task_name_for_log}: {str(result_or_exception)}")
            state.is_error = True
        else:
            # Result is a tuple: (task_name, list_of_details, error_message_or_none)
            _processed_task_name, processed_details, individual_task_error_msg = result_or_exception
            
            task_def_to_update.details = processed_details # Update the original task_def's details
            
            if individual_task_error_msg:
                # This means the LLM call itself or parsing within the helper function had an issue, but didn't raise an unhandled exception to gather
                aggregate_error_messages.append(f"Error for {_processed_task_name} (reported by helper): {individual_task_error_msg}")
                state.is_error = True # Mark overall error
                logger.warning(f"Task '{_processed_task_name}' completed with reported error: {individual_task_error_msg}")
            else:
                all_generated_module_steps_for_logging.append(f"### Module Steps for Task: {task_name_for_log} (Type: {task_type_for_log})\\n{json.dumps(processed_details, indent=2)}")
                logger.info(f"Successfully processed and updated details for task '{task_name_for_log}'.")

    if state.is_error:
        final_error_detail = "; ".join(aggregate_error_messages) if aggregate_error_messages else "Unknown error during parallel module step generation."
        state.error_message = f"SAS Step 2 encountered errors: {final_error_detail}"
        logger.error(state.error_message)
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "completed_partial" 
        
    logger.info(f"    Final state.task_list_accepted in SAS_PROCESS_TO_MODULE_STEPS: {state.task_list_accepted}")
    return state.dict(exclude_none=True) 

__all__ = [
    "process_description_to_module_steps_node"
] 