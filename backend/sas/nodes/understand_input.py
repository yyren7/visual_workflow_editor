import logging
import json
import os
from typing import List, Dict, Any, Type

from pydantic import BaseModel, Field, field_validator
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from ..state import RobotFlowAgentState # Adjusted import
from ..llm_utils import invoke_llm_for_json_output # Adjusted import

logger = logging.getLogger(__name__)

class ParsedStep(BaseModel):
    id_suggestion: str = Field(description="A suggested unique ID for this operation block, e.g., 'movel_P1_Z_on'.")
    type: str = Field(description="The type of operation, e.g., 'select_robot', 'set_motor', 'moveL', 'loop', 'return'.")
    description: str = Field(description="A brief natural language description of this specific step.")
    parameters: Dict[str, Any] = Field(description="A dictionary of parameters for this operation, e.g., {'robotName': 'dobot_mg400'} or {'point_name_list': 'P1', 'control_z': 'enable'.}")
    has_sub_steps: bool = Field(False, description="Whether this step contains nested sub-steps.")
    sub_step_descriptions: List[str] = Field(default_factory=list, description="List of description strings for nested operations, to avoid deep recursion.")

    @field_validator('parameters', mode='before')
    @classmethod
    def parse_parameters_from_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                loaded_json = json.loads(v)
                if isinstance(loaded_json, dict):
                    return loaded_json
                else:
                    return loaded_json 
            except json.JSONDecodeError:
                pass
        return v

class UnderstandInputSchema(BaseModel):
    operations: List[ParsedStep] = Field(description="An ordered list of operations identified from the user input text.")
    # robot: str = Field(description="The identified robot model name from the input, normalized if possible. E.g., 'dobot_mg400'. If no specific robot is mentioned or identifiable, default to 'general_robot'.") # Removed as per latest llm_nodes.py

async def understand_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 1: Understand Input (from potentially enriched text) ---")
    state.current_step_description = "Understanding user input"
    state.is_error = False

    enriched_input_text = state.enriched_structured_text
    if not enriched_input_text:
        logger.error("Enriched input text is missing in state for understand_input_node.")
        state.is_error = True
        state.error_message = "Enriched input text is missing for parsing."
        state.dialog_state = "error"
        state.completion_status = "error"
        return state

    config = state.config
    if not config:
        logger.error("Config (placeholder values) is missing in state.")
        state.is_error = True
        state.error_message = "Configuration (placeholders) is missing."
        state.dialog_state = "error"
        state.completion_status = "error"
        return state
    
    current_messages = state.messages

    known_node_types_list = []
    node_template_dir = config.get("NODE_TEMPLATE_DIR_PATH")
    if node_template_dir and os.path.isdir(node_template_dir):
        try:
            known_node_types_list = sorted([
                os.path.splitext(f)[0] 
                for f in os.listdir(node_template_dir) 
                if os.path.isfile(os.path.join(node_template_dir, f)) and f.endswith( (".xml", ".json", ".py"))
            ])
            if not known_node_types_list:
                logger.warning(f"No node templates found in directory: {node_template_dir} with supported extensions. Type validation will be lenient.")
            else:
                logger.info(f"Dynamically loaded {len(known_node_types_list)} known node types: {known_node_types_list}")
        except Exception as e:
            logger.error(f"Failed to list or parse node templates from {node_template_dir}: {e}. Type validation may be skipped or lenient.")
    else:
        logger.warning(f"NODE_TEMPLATE_DIR_PATH '{node_template_dir}' is not configured or not a directory. Type validation will be lenient.")

    placeholder_values_for_prompt = config.copy()
    placeholder_values_for_prompt["KNOWN_NODE_TYPES_LIST_STR"] = ", ".join(known_node_types_list) if known_node_types_list else "(dynamic list not available)"
    placeholder_values_for_prompt.setdefault("GENERAL_INSTRUCTION_INTRO", "Please analyze the following robot workflow.")

    user_message_for_llm = (
        f"Parse the following robot workflow description into a structured format. "
        f"Identify each distinct operation. "
        f"Pay close attention to control flow structures like loops and their nested operations.\n\n"
        f"Workflow Description to Parse:\n```text\n{enriched_input_text}\n```"
    )

    # Assuming invoke_llm_for_json_output and get_filled_prompt are correctly imported or available
    # get_filled_prompt will be needed by invoke_llm_for_json_output if it internally uses it.
    # Based on llm_nodes.py, invoke_llm_for_json_output uses get_filled_prompt from ..prompt_loader.
    # This means prompt_loader needs to be in the correct relative path.
    # from ..prompt_loader import get_filled_prompt # This import might be needed directly or indirectly.

    parsed_output = await invoke_llm_for_json_output(
        llm,
        system_prompt_template_name="flow_step1_understand_input.md",
        placeholder_values=placeholder_values_for_prompt,
        user_message_content=user_message_for_llm,
        json_schema=UnderstandInputSchema,
        message_history=None
    )

    if "error" in parsed_output:
        error_msg_detail = f"Step 1 Failed: {parsed_output.get('error')}. Details: {parsed_output.get('details')}"
        logger.error(error_msg_detail)
        raw_out = parsed_output.get('raw_output', '')
        print("\nERROR: LLM output for UnderstandInputSchema caused an error.")
        print(f"LLM Raw Output (json.loads might be needed if it is a string):\n{raw_out}\n")
        print(f"Full parsed_output from LLM call before Pydantic validation:\n{json.dumps(parsed_output, indent=2, ensure_ascii=False)}\n")
        state.is_error = True
        state.error_message = f"Step 1: Failed to understand input. LLM Error: {error_msg_detail}. Raw: {str(raw_out)[:500]}"
        state.dialog_state = "generation_failed"
        state.completion_status = "error"
        return state

    if known_node_types_list and parsed_output.get("operations"):
        flow_ops_data = parsed_output.get("operations", [])
        invalid_types_details = []
        for i, op_data in enumerate(flow_ops_data):
            op_type = op_data.get("type")
            current_op_id_for_log = op_data.get('id_suggestion', f"op_{i+1}")
            current_op_desc_for_log = op_data.get('description', 'N/A')
            if op_type not in known_node_types_list and op_type != "unknown_operation":
                invalid_types_details.append(
                    f"Operation {current_op_id_for_log} ('{current_op_desc_for_log}') has an invalid type '{op_type}'. "
                    f"Valid types are: {known_node_types_list} (or 'unknown_operation')."
                )
        
        if invalid_types_details:
            error_message = " ".join(invalid_types_details)
            logger.error(f"Step 1 Failed: Invalid node types found after LLM parsing. {error_message}")
            state.is_error = True
            state.error_message = f"Step 1: Invalid node types found. {error_message} Raw LLM Output: {str(parsed_output)[:500]}"
            state.dialog_state = "error" # Corrected from generation_failed to error if it is a direct error not a retryable one.
            state.completion_status = "error"
            return state

    try:
        if isinstance(parsed_output, UnderstandInputSchema):
            validated_data = parsed_output
        else:
            validated_data = UnderstandInputSchema(**parsed_output)

        logger.info(f"Step 1 Succeeded. Parsed operations: {len(validated_data.operations)}")
        
        state.parsed_flow_steps = [op.dict(exclude_none=True) for op in validated_data.operations]
        # state.parsed_robot_name = validated_data.robot # Removed as robot field was removed from UnderstandInputSchema
        state.error_message = None
        # Add message to state.messages (example)
        # For this specific node, it seems messages are handled carefully, so I will retain original logic for adding messages if any.
        # Example: state.messages = current_messages + [AIMessage(content=f"Successfully parsed input. Steps: {len(state.parsed_flow_steps)}")]
        # The original code for this node did not add a generic success message, but rather relied on `preprocess_and_enrich_input_node` for user-facing messages.
        # However, the original llm_nodes.py had: state.messages = current_messages + [AIMessage(content=f"Successfully parsed input. Robot: {state.parsed_robot_name}. Steps: {len(state.parsed_flow_steps)}")]
        # Since parsed_robot_name is removed, I will adjust this.
        if state.parsed_flow_steps is not None:
             state.messages = current_messages + [AIMessage(content=f"Successfully parsed input. Steps: {len(state.parsed_flow_steps)}")]

        state.completion_status = None
        return state
    except Exception as e: 
        logger.error(f"Step 1 Failed: Pydantic validation error for UnderstandInputSchema or subsequent validation. Error: {e}. Raw Output from LLM: {json.dumps(parsed_output, indent=2, ensure_ascii=False)}", exc_info=True)
        print("\nERROR: Pydantic validation failed for UnderstandInputSchema or subsequent validation.")
        print(f"LLM's Parsed Output that failed validation:\n{json.dumps(parsed_output, indent=2, ensure_ascii=False)}\n")
        state.is_error = True
        state.error_message = f"Step 1: Output validation error. Details: {e}. Parsed: {str(parsed_output)[:500]}"
        state.dialog_state = "generation_failed"
        state.completion_status = "error"
        return state 