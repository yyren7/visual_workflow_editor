import logging
import json
import os
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.language_models import BaseChatModel

from ..state import RobotFlowAgentState, GeneratedXmlFile # Adjusted import
from ..prompt_loader import get_filled_prompt # Adjusted import
from ..llm_utils import invoke_llm_for_text_output # Adjusted import

logger = logging.getLogger(__name__)

def _collect_all_operations_for_xml_generation(
    operations: List[Dict[str, Any]], 
    config: Dict[str, Any],
    _block_counter: int = 1 
    ) -> (List[Dict[str, Any]], int):
    ops_to_generate = []
    block_id_prefix = config.get("BLOCK_ID_PREFIX_EXAMPLE", "block_uuid") 

    for op_data_from_step1 in operations:
        xml_block_id = f"{block_id_prefix}_{_block_counter}"
        xml_data_block_no = str(_block_counter)
        
        generated_xml_filename = f"{xml_block_id}_{op_data_from_step1['type']}.xml"

        full_description = op_data_from_step1['description']
        if op_data_from_step1.get('has_sub_steps', False) and op_data_from_step1.get('sub_step_descriptions'):
            sub_descriptions = op_data_from_step1['sub_step_descriptions']
            if sub_descriptions:
                full_description += f" [Sub-steps: { '; '.join(sub_descriptions)} ]"

        op_info_for_llm = {
            "type": op_data_from_step1['type'],
            "description": full_description,
            "parameters_json": json.dumps(op_data_from_step1.get('parameters', {})),
            "id_suggestion_from_step1": op_data_from_step1.get('id_suggestion', ''),
            
            "target_xml_block_id": xml_block_id, 
            "target_xml_data_block_no": xml_data_block_no,
            "target_xml_filename": generated_xml_filename,
            "node_template_filename_to_load": f"{op_data_from_step1['type']}.xml" 
        }
        ops_to_generate.append(op_info_for_llm)
        _block_counter += 1

    return ops_to_generate, _block_counter

async def _generate_one_xml_for_operation_task(
    op_info_for_llm: Dict[str, Any],
    state: RobotFlowAgentState,
    llm: BaseChatModel
) -> GeneratedXmlFile:
    config = state.config
    node_template_dir = config.get("NODE_TEMPLATE_DIR_PATH")

    if not node_template_dir:
        error_msg = "NODE_TEMPLATE_DIR_PATH is not configured."
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg
        )

    template_file_path = Path(node_template_dir) / op_info_for_llm["node_template_filename_to_load"]
    node_template_xml_content_as_string = ""
    try:
        with open(template_file_path, 'r', encoding='utf-8') as f:
            node_template_xml_content_as_string = f.read()
    except FileNotFoundError:
        error_msg = f"Node template file not found: {template_file_path}"
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg
        )
    except Exception as e:
        error_msg = f"Error reading node template file {template_file_path}: {e}"
        logger.error(error_msg, exc_info=True)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg
        )

    placeholder_values = {
        **config,
        "CURRENT_NODE_TYPE": op_info_for_llm["type"],
        "CURRENT_NODE_DESCRIPTION": op_info_for_llm["description"],
        "CURRENT_NODE_PARAMETERS_JSON": op_info_for_llm["parameters_json"],
        "CURRENT_NODE_ID_SUGGESTION_FROM_STEP1": op_info_for_llm["id_suggestion_from_step1"],
        "TARGET_XML_BLOCK_ID": op_info_for_llm["target_xml_block_id"],
        "TARGET_XML_DATA_BLOCK_NO": op_info_for_llm["target_xml_data_block_no"],
        "NODE_TEMPLATE_XML_CONTENT_AS_STRING": node_template_xml_content_as_string,
    }

    user_message_for_llm = (
        f"Generate the Blockly XML for a '{op_info_for_llm['type']}' node. "
        f"Use the provided template content. "
        f"Target Block ID: {op_info_for_llm['target_xml_block_id']}. "
        f"Description: {op_info_for_llm['description']}."
    )

    logger.info(f"Attempting LLM call for op type: {op_info_for_llm['type']}, block_id: {op_info_for_llm['target_xml_block_id']}")
    logger.info(f"LLM User Message: {user_message_for_llm}")

    llm_response = await invoke_llm_for_text_output(
        llm,
        system_prompt_content=get_filled_prompt("flow_step2_generate_node_xml.md", placeholder_values),
        user_message_content=user_message_for_llm,
        message_history=None
    )

    if "error" in llm_response or not llm_response.get("text_output"):
        error_msg = f"LLM call failed for block {op_info_for_llm['target_xml_block_id']}. Error: {llm_response.get('error', 'No output')}"
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg,
            xml_content=llm_response.get("text_output")
        )
    
    generated_xml_string = llm_response["text_output"].strip()

    match = re.search(r"```xml\n(.*?)\n```", generated_xml_string, re.DOTALL)
    if match:
        extracted_xml = match.group(1).strip()
        logger.info(f"Extracted XML from markdown code block for block {op_info_for_llm['target_xml_block_id']}")
        generated_xml_string = extracted_xml
    else:
        first_angle_bracket = generated_xml_string.find('<')
        last_angle_bracket = generated_xml_string.rfind('>')
        if first_angle_bracket != -1 and last_angle_bracket != -1 and last_angle_bracket > first_angle_bracket:
            potential_xml = generated_xml_string[first_angle_bracket : last_angle_bracket+1]
            if potential_xml.strip().startswith("<") and potential_xml.strip().endswith(">"):
                if generated_xml_string.strip() != potential_xml.strip():
                    logger.info(f"Attempting to extract XML by finding first '<' and last '>' for block {op_info_for_llm['target_xml_block_id']}")
                    generated_xml_string = potential_xml.strip()

    if not (generated_xml_string.startswith("<") and generated_xml_string.endswith(">")):
        error_msg = f"LLM output for block {op_info_for_llm['target_xml_block_id']} does not look like valid XML: {generated_xml_string[:100]}..."
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg,
            xml_content=generated_xml_string
        )

    logger.info(f"Successfully generated XML for block: {op_info_for_llm['target_xml_block_id']}")
    return GeneratedXmlFile(
        block_id=op_info_for_llm["target_xml_block_id"],
        type=op_info_for_llm["type"],
        source_description=op_info_for_llm["description"],
        status="success",
        xml_content=generated_xml_string,
    )

async def generate_individual_xmls_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 2: Generate Independent Node XMLs ---")    
    state.current_step_description = "Generating individual XML files for each flow operation"
    state.is_error = False

    parsed_steps = state.parsed_flow_steps
    config = state.config

    if not parsed_steps:
        logger.error("parsed_flow_steps is missing in state for generate_individual_xmls_node.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for XML generation."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    if not config or not config.get("OUTPUT_DIR_PATH"):
        logger.error("OUTPUT_DIR_PATH is not configured in state.config.")
        state.is_error = True
        state.error_message = "Output directory path (OUTPUT_DIR_PATH) is not configured."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    all_ops_for_llm, _ = _collect_all_operations_for_xml_generation(parsed_steps, config)
    if not all_ops_for_llm:
        logger.warning("No operations collected for XML generation. This might be an empty plan.")
        state.generated_node_xmls = []
        state.dialog_state = "generating_xml_relation"
        state.subgraph_completion_status = "error" # Or None/completed if empty plan is valid
        return state

    logger.info(f"Collected {len(all_ops_for_llm)} operations for XML generation.")

    tasks = [
        _generate_one_xml_for_operation_task(op_info, state, llm) 
        for op_info in all_ops_for_llm
    ]
    
    generation_results: List[GeneratedXmlFile] = await asyncio.gather(*tasks)

    output_dir = Path(config.get("OUTPUT_DIR_PATH"))
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create output directory {output_dir}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to create output directory: {e}"
        state.generated_node_xmls = generation_results 
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    processed_xml_files: List[GeneratedXmlFile] = []
    any_errors = False
    for i, result_info in enumerate(generation_results):
        op_metadata = all_ops_for_llm[i]
        if result_info.status == "success" and result_info.xml_content:
            file_name = op_metadata["target_xml_filename"]
            file_path = output_dir / file_name
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(result_info.xml_content)
                result_info.file_path = str(file_path)
                logger.info(f"Successfully wrote XML to {file_path}")
            except IOError as e:
                logger.error(f"Failed to write XML file {file_path}: {e}", exc_info=True)
                result_info.status = "failure"
                result_info.error_message = f"Failed to write file: {e}"
                result_info.file_path = None
                any_errors = True
        elif result_info.status == "failure":
            any_errors = True
            logger.error(f"Failed to generate XML for block_id {result_info.block_id}: {result_info.error_message}")
        
        processed_xml_files.append(result_info)
    
    state.generated_node_xmls = processed_xml_files

    if any_errors:
        logger.error("One or more errors occurred during individual XML generation.")
        state.subgraph_completion_status = "error" 
        # Retain original logic: pass # For now, just log and proceed to next state

    logger.info(f"Finished Step 2. Generated {len(processed_xml_files) - sum(1 for r in processed_xml_files if r.status=='failure')} XML files successfully.")
    state.dialog_state = "generating_xml_relation" 
    state.subgraph_completion_status = None 
    return state 