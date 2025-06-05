import logging
from typing import Dict, Any
import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage

from ..state import RobotFlowAgentState # Adjusted import
from ..prompt_loader import get_sas_step1_formatted_prompt # Adjusted import
from ..llm_utils import invoke_llm_for_text_output # Adjusted import
from ..input_precess_parser import parse_process_plan_to_json # Added parser import

logger = logging.getLogger(__name__)

async def user_input_to_process_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    logger.info(f"--- Entering SAS Step 1: User Input to Process Description (dialog_state: {state.dialog_state}) ---")
    state.current_step_description = "SAS Step 1: Transforming user input to detailed process description."
    state.is_error = False
    state.error_message = None

    user_input = state.user_input
    if not user_input:
        logger.error("User input is missing for SAS Step 1.")
        state.is_error = True
        state.error_message = "User input is required for SAS Step 1 but was not found."
        state.dialog_state = "awaiting_user_input"
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    state.user_input = None 

    if not state.messages or not (isinstance(state.messages[-1], HumanMessage) and state.messages[-1].content == user_input):
        state.messages = (state.messages or []) + [HumanMessage(content=user_input)]

    formatted_prompt = get_sas_step1_formatted_prompt(user_task_description=user_input)

    if not formatted_prompt:
        logger.error("Failed to load or format SAS Step 1 prompt.")
        state.is_error = True
        state.error_message = "Internal error: Failed to prepare SAS Step 1 prompt."
        state.dialog_state = "error" 
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    logger.info("Invoking LLM for SAS Step 1: Process Description Generation.")
    
    llm_response = await invoke_llm_for_text_output(
        llm=llm,
        system_prompt_content="""You are an AI assistant tasked with generating a detailed process plan based on a robot task description provided by the user. 

CRITICAL REQUIREMENTS:
1. Follow the instructions in the user message carefully to produce the plan
2. EVERY step in your process description MUST correspond to available robot control blocks
3. DO NOT create any steps that exceed the capabilities of the available blocks
4. Include specific block type references in your descriptions (e.g., "Block Type: `moveP`")
5. Respect all precautions and limitations mentioned for each block type
6. Ensure proper sequence and dependencies between blocks

Your generated process plan will be used to create executable robot programs, so accuracy and adherence to block capabilities is essential.""",
        user_message_content=formatted_prompt,
        message_history=None
    )

    if "error" in llm_response or not llm_response.get("text_output"):
        logger.error(f"LLM call for SAS Step 1 failed. Error: {llm_response.get('error')}, Details: {llm_response.get('details')}")
        state.is_error = True
        state.error_message = f"LLM failed to generate process description: {llm_response.get('error', 'Unknown LLM error')}. Details: {llm_response.get('details', 'N/A')}"
        state.dialog_state = "error"
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=state.error_message)]
        state.subgraph_completion_status = "error"
    else:
        generated_plan = llm_response["text_output"].strip()
        state.sas_step1_process_description_plan = generated_plan
        logger.info(f"SAS Step 1 completed successfully. Generated plan: {generated_plan[:500]}...")
        state.dialog_state = "sas_step1_completed"
        state.current_step_description = "SAS Step 1: Detailed process description generated successfully."
        if not any(msg.content == generated_plan for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=generated_plan)]
        state.subgraph_completion_status = "completed_partial"

        if state.run_output_directory:
            try:
                logger.info(f"Attempting to parse plan and save to directory: {state.run_output_directory}")
                parsed_plan_json = parse_process_plan_to_json(generated_plan)
                output_file_name = "sas_step1_parsed_plan.json"
                output_file_path = Path(state.run_output_directory) / output_file_name
                
                output_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(parsed_plan_json, f, indent=4, ensure_ascii=False)
                logger.info(f"Successfully parsed and saved SAS Step 1 plan to: {output_file_path}")
            except Exception as e:
                logger.error(f"Failed to parse or save SAS Step 1 plan JSON to {state.run_output_directory}. Error: {e}", exc_info=True)
        else:
            logger.warning("state.run_output_directory is not set. Skipping saving of parsed SAS Step 1 plan.")

    return state.dict(exclude_none=True) 