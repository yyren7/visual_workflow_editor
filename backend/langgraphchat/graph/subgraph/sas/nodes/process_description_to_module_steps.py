import logging
from typing import Dict, Any
import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage

from ..state import RobotFlowAgentState
from ..prompt_loader import load_raw_prompt_file, load_node_descriptions
from ..llm_utils import invoke_llm_for_text_output

logger = logging.getLogger(__name__)

# Step2 prompt file path
STEP2_PROMPT_FILE_PATH = "/workspace/database/prompt_database/sas_input_prompt/step2_process_description_to_module_steps_prompt_en.md"

def get_sas_step2_formatted_prompt(process_description: str) -> str:
    """
    Loads the SAS step 2 prompt and formats it with the process description from step 1.
    Dynamically injects available node descriptions into the prompt.
    """
    base_prompt_content = load_raw_prompt_file(STEP2_PROMPT_FILE_PATH)
    if not base_prompt_content:
        logger.error("Failed to load SAS Step 2 prompt file")
        return None

    # Load available block descriptions and format them for injection
    node_descriptions = load_node_descriptions()
    available_blocks_section = ""

    if not node_descriptions:
        logger.warning(
            "No node descriptions loaded for Step 2. LLM will rely on its general knowledge "
            "and examples in the prompt. A placeholder warning will be added to the prompt."
        )
        available_blocks_section = (
            "\\n\\n## Available Robot Control Blocks\\n\\n"
            "**Warning**: No specific block descriptions were dynamically loaded from the central "
            "repository. Please ensure all generated steps can be implemented with standard robot "
            "control blocks and refer to any examples provided in this prompt for guidance on block types.\\n"
        )
    else:
        logger.info(f"Successfully loaded {len(node_descriptions)} node description(s) for Step 2.")
        available_blocks_section = "\\n\\n## Available Robot Control Blocks (Dynamically Loaded)\\n\\n"
        available_blocks_section += (
            "**CRITICAL REQUIREMENT**: All generated module steps MUST strictly correspond to the "
            "following available blocks provided from the central repository. Do NOT create steps that "
            "exceed these block capabilities or invent new block types not listed here.\\n\\n"
        )
        available_blocks_section += "### Block Types and Their Capabilities:\\n\\n"
        for block_type, description in sorted(node_descriptions.items()): # Sorting for consistent output
            available_blocks_section += f"- **{block_type.strip()}**: {description.strip()}\\n"
        
        available_blocks_section += (
            "\\n### Adherence to these explicitly listed blocks is mandatory for successful robot "
            "program generation. These definitions supersede any examples if conflicts arise.\\n\\n"
        )

    # Insert the available blocks section into the base prompt content
    # Attempt to insert before "## Example Fewshot" marker, similar to Step 1's prompt formatting.
    insertion_marker = "## Example Fewshot"
    marker_pos = base_prompt_content.find(insertion_marker)
    modified_base_prompt: str 

    if marker_pos != -1:
        modified_base_prompt = (
            base_prompt_content[:marker_pos] + 
            available_blocks_section + 
            base_prompt_content[marker_pos:]
        )
        logger.info(f"Injected dynamically loaded node descriptions before '{insertion_marker}' in SAS Step 2 prompt.")
    else:
        # Fallback: if marker not found, append to the main content before the user-specific part.
        logger.warning(
            f"Marker '{insertion_marker}' not found in SAS Step 2 prompt. "
            "Appending dynamically loaded node descriptions to the end of the base prompt content, "
            "before the user-specific process description input."
        )
        modified_base_prompt = base_prompt_content + available_blocks_section
    
    # Append the process description from step1 as input
    formatted_user_input = f"""

## Process Description Input (From Stage 1)

{process_description}

## Your Module Steps Output (Convert the above process description to specific module steps)

**IMPORTANT REMINDER**: 
- Every step you generate MUST correspond to the **Available Robot Control Blocks** (listed above if dynamically loaded from the central repository; otherwise, refer to examples in the prompt).
- Use the Block Type references from the input and the provided list (if available and dynamically loaded) to guide your implementation.
- Assign specific point codes (P1, P21, P22, etc.) and parameters.
- Respect all precautions and limitations for each block type.

Please generate the specific module steps now:
"""
    
    return modified_base_prompt + formatted_user_input

async def process_description_to_module_steps_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    SAS Step 2: Convert detailed process description from Step 1 into specific, executable module steps.
    
    This node takes the process description generated by step 1 and converts it into 
    parameterized, executable robot program steps with specific points, I/O configurations, etc.
    """
    logger.info(f"--- Entering SAS Step 2: Process Description to Module Steps (dialog_state: {state.dialog_state}) ---")
    state.current_step_description = "SAS Step 2: Converting process description to specific module steps."
    state.is_error = False
    state.error_message = None

    # Check if we have the process description from step 1
    process_description = state.sas_step1_process_description_plan
    if not process_description:
        logger.warning("Process description from SAS Step 1 (sas_step1_process_description_plan) is missing. Attempting to build from sas_step1_generated_tasks.")
        if state.sas_step1_generated_tasks:
            task_descriptions = []
            for i, task in enumerate(state.sas_step1_generated_tasks):
                # Assuming task is a Pydantic model or dict with 'name' and 'description'
                task_name = getattr(task, 'name', f"Task {i+1}")
                task_desc = getattr(task, 'description', "No description provided.")
                task_type = getattr(task, 'type', "UnknownType")
                task_descriptions.append(f"Task {i+1}: {task_name} (Type: {task_type})\nDescription: {task_desc}")
            
            if task_descriptions:
                process_description = "\n\n".join(task_descriptions)
                logger.info(f"Successfully built process description from {len(state.sas_step1_generated_tasks)} tasks.")
            else:
                logger.error("sas_step1_generated_tasks was found, but it was empty or tasks lacked descriptions. Cannot build process description.")
        else:
            logger.error("sas_step1_generated_tasks is also missing. Cannot build process description.")

    if not process_description:
        logger.error("Process description from SAS Step 1 is missing and could not be built from tasks.")
        state.is_error = True
        state.error_message = "Process description from SAS Step 1 is required but was not found."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    # Add the process description to messages if not already present
    if not state.messages or not any(process_description in msg.content for msg in state.messages if isinstance(msg, HumanMessage)):
        state.messages = (state.messages or []) + [HumanMessage(content=f"Process Description from Step 1: {process_description}")]

    # Generate the formatted prompt for step 2
    formatted_prompt = get_sas_step2_formatted_prompt(process_description)
    if not formatted_prompt:
        logger.error("Failed to load or format SAS Step 2 prompt.")
        state.is_error = True
        state.error_message = "Internal error: Failed to prepare SAS Step 2 prompt."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    logger.info("Invoking LLM for SAS Step 2: Module Steps Generation.")
    
    # Call LLM to generate module steps
    llm_response = await invoke_llm_for_text_output(
        llm=llm,
        system_prompt_content="""You are an AI assistant specialized in converting detailed robot process descriptions into specific, executable module steps. 

CRITICAL REQUIREMENTS:
1. Convert each logical step from the process description into specific robot control blocks
2. Assign concrete parameters (point codes like P1, P21, etc., I/O pin numbers, variable names)
3. EVERY generated step MUST correspond to available robot control blocks
4. Use the Block Type references from the input to ensure correct mapping
5. Respect all precautions and block limitations
6. Generate parameterized, immediately executable steps

Your output will be used to create actual robot programs, so precision and block compliance is essential.""",
        user_message_content=formatted_prompt,
        message_history=None
    )

    if "error" in llm_response or not llm_response.get("text_output"):
        logger.error(f"LLM call for SAS Step 2 failed. Error: {llm_response.get('error')}, Details: {llm_response.get('details')}")
        state.is_error = True
        state.error_message = f"LLM failed to generate module steps: {llm_response.get('error', 'Unknown LLM error')}. Details: {llm_response.get('details', 'N/A')}"
        state.dialog_state = "error"
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=state.error_message)]
        state.subgraph_completion_status = "error"
    else:
        generated_module_steps = llm_response["text_output"].strip()
        state.sas_step2_module_steps = generated_module_steps
        logger.info(f"SAS Step 2 completed successfully. Generated module steps: {generated_module_steps[:500]}...")
        state.dialog_state = "sas_step2_completed"
        state.current_step_description = "SAS Step 2: Specific module steps generated successfully."
        if not any(msg.content == generated_module_steps for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=generated_module_steps)]
        state.subgraph_completion_status = "completed_partial"

        # Save module steps to output directory if available
        if state.run_output_directory:
            try:
                logger.info(f"Saving module steps to directory: {state.run_output_directory}")
                output_file_name = "sas_step2_module_steps.txt"
                output_file_path = Path(state.run_output_directory) / output_file_name
                
                output_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file_path, "w", encoding="utf-8") as f:
                    f.write(generated_module_steps)
                logger.info(f"Successfully saved SAS Step 2 module steps to: {output_file_path}")
            except Exception as e:
                logger.error(f"Failed to save SAS Step 2 module steps to {state.run_output_directory}. Error: {e}", exc_info=True)
        else:
            logger.warning("state.run_output_directory is not set. Skipping saving of SAS Step 2 module steps.")

    return state.dict(exclude_none=True) 