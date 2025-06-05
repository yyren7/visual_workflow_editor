import logging
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

from langchain_core.language_models import BaseChatModel

from ..state import RobotFlowAgentState, GeneratedXmlFile # Adjusted import
from ..prompt_loader import get_filled_prompt # Adjusted import
from ..llm_utils import invoke_llm_for_text_output # Adjusted import

logger = logging.getLogger(__name__)

def _prepare_data_for_relation_prompt(
    parsed_steps: List[Dict[str, Any]], 
    generated_xmls: List[GeneratedXmlFile] # Type hint from state.py
) -> List[Dict[str, Any]]:
    if not parsed_steps:
        return []
    if not generated_xmls:
        logger.warning("_prepare_data_for_relation_prompt: No generated_xmls provided for mapping.")
        return []

    if len(parsed_steps) != len(generated_xmls):
        logger.error(
            f"Mismatch in parsed operations ({len(parsed_steps)}) "
            f"and number of generated XML files ({len(generated_xmls)}). "
            "Block IDs in relation.xml might be incorrect."
        )

    tree_for_prompt = []
    for i, step in enumerate(parsed_steps):
        if i < len(generated_xmls):
            corresponding_xml_info = generated_xmls[i]
            relation_node_data = {
                "type": step["type"],
                "id": corresponding_xml_info.block_id,
            }
            if step.get("has_sub_steps", False) and step.get("sub_step_descriptions"):
                relation_node_data["has_sub_steps"] = True
                relation_node_data["sub_step_descriptions"] = step["sub_step_descriptions"]
            
            tree_for_prompt.append(relation_node_data)
        else:
            logger.warning(f"No corresponding XML found for parsed step {i}: {step.get('description', 'N/A')}")

    return tree_for_prompt

async def generate_relation_xml_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 3: Generate Node Relation XML ---")
    state.current_step_description = "Generating node relation XML file"
    state.is_error = False

    config = state.config
    parsed_steps = state.parsed_flow_steps
    generated_node_xmls_list = state.generated_node_xmls if state.generated_node_xmls is not None else []

    if not parsed_steps:
        logger.error("Parsed flow steps are missing for relation XML generation.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for relation XML."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    if not generated_node_xmls_list:
        logger.warning("Generated node XMLs list is empty. Generating empty relation XML.")
        state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
        state.dialog_state = "generating_xml_final"
        
        output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
        relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
        relation_file_path = output_dir / relation_file_name
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(relation_file_path, "w", encoding="utf-8") as f:
                f.write(state.relation_xml_content)
            state.relation_xml_path = str(relation_file_path)
            logger.info(f"Wrote empty relation XML to {relation_file_path}")
        except IOError as e:
            logger.error(f"Failed to write empty relation XML to {relation_file_path}: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Failed to write empty relation XML: {e}"
            state.dialog_state = "error"
            state.subgraph_completion_status = "error"
        return state

    try:
        simplified_flow_structure_with_ids = _prepare_data_for_relation_prompt(
            parsed_steps, 
            generated_node_xmls_list
        )
    except Exception as e:
        logger.error(f"Error preparing data for relation prompt: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to prepare data for relation XML: {e}"
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    if not simplified_flow_structure_with_ids:
         logger.warning("Simplified flow structure for relation prompt is empty after prep. Generating empty relation XML.")
         state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
         state.dialog_state = "generating_xml_final"
         output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
         relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
         relation_file_path = output_dir / relation_file_name
         try:
            os.makedirs(output_dir, exist_ok=True)
            with open(relation_file_path, "w", encoding="utf-8") as f:
                f.write(state.relation_xml_content)
            state.relation_xml_path = str(relation_file_path)
            logger.info(f"Successfully wrote relation XML to {relation_file_path}. Content head: {state.relation_xml_content[:100]}")
         except IOError as e:
            logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Failed to write relation XML: {e}"
            state.dialog_state = "error"
            state.subgraph_completion_status = "error"
         return state

    flow_structure_json_for_prompt = json.dumps(simplified_flow_structure_with_ids, indent=2)
    
    example_relation_xml_content = "<!-- Default example relation XML structure -->"
    # Ensure this path is correct or made configurable if it varies.
    static_example_relation_xml_path = config.get("EXAMPLE_RELATION_XML_PATH", "/workspace/database/flow_database/result/5.15_test/relation.xml") 
    try:
        with open(static_example_relation_xml_path, 'r', encoding='utf-8') as f:
            example_relation_xml_content = f.read()
    except Exception as e:
        logger.warning(f"Could not load example relation XML from {static_example_relation_xml_path}: {e}. Prompt will use its internal example.")

    placeholder_values = {
        **config,
        "PARSED_FLOW_STRUCTURE_WITH_IDS_JSON": flow_structure_json_for_prompt,
        "EXAMPLE_RELATION_XML_CONTENT": example_relation_xml_content
    }

    system_prompt_content = get_filled_prompt("flow_step3_generate_relation_xml.md", placeholder_values)
    if not system_prompt_content:
        logger.error("Failed to load or fill system prompt: flow_step3_generate_relation_xml.md")
        state.is_error = True
        state.error_message = "Failed to load relation XML generation prompt."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    user_message_for_llm = (
        f"Please generate the relation.xml content based on the `PARSED_FLOW_STRUCTURE_WITH_IDS_JSON` provided in the system prompt. "
        f"Ensure the output is only the XML content, adhering to the structural rules (no <field> or data-blockNo) outlined in the system prompt."
    )

    llm_response = await invoke_llm_for_text_output(
        llm,
        system_prompt_content=system_prompt_content,
        user_message_content=user_message_for_llm,
        message_history=None
    )

    if "error" in llm_response or not llm_response.get("text_output"):
        error_msg = f"Relation XML generation LLM call failed. Error: {llm_response.get('error', 'No output')}"
        logger.error(error_msg)
        state.is_error = True
        state.error_message = error_msg
        state.relation_xml_content = llm_response.get("text_output") 
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state
    
    generated_relation_xml_string = llm_response["text_output"].strip()

    match = re.search(r"```xml\n(.*?)\n```", generated_relation_xml_string, re.DOTALL)
    if match:
        extracted_xml = match.group(1).strip()
        logger.info("Extracted relation XML from markdown code block.")
        generated_relation_xml_string = extracted_xml
    else:
        first_angle = generated_relation_xml_string.find('<')
        last_angle = generated_relation_xml_string.rfind('>')
        if first_angle != -1 and last_angle != -1 and last_angle > first_angle:
            potential_xml = generated_relation_xml_string[first_angle : last_angle+1]
            if potential_xml.strip().startswith("<") and potential_xml.strip().endswith(">"):
                if generated_relation_xml_string.strip() != potential_xml.strip():
                    logger.info("Attempting to extract relation XML by finding first '<' and last '>'.")
                    generated_relation_xml_string = potential_xml.strip()

    if not (generated_relation_xml_string.startswith("<") and generated_relation_xml_string.endswith(">")):
        error_msg = f"LLM output for relation.xml does not look like valid XML: {generated_relation_xml_string[:200]}..."
        logger.error(error_msg)
        state.is_error = True
        state.error_message = error_msg
        state.relation_xml_content = generated_relation_xml_string
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    try:
        ET.fromstring(generated_relation_xml_string)
        logger.info("Successfully validated relation XML string with ElementTree.")
    except ET.ParseError as e:
        error_msg = f"Generated relation.xml is not well-formed XML. ParseError: {e}. Content: {generated_relation_xml_string[:500]}"
        logger.error(error_msg)
        state.is_error = True
        state.error_message = error_msg
        state.relation_xml_content = generated_relation_xml_string
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    state.relation_xml_content = generated_relation_xml_string
    
    output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
    relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
    relation_file_path = output_dir / relation_file_name
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(relation_file_path, "w", encoding="utf-8") as f:
            f.write(state.relation_xml_content)
        state.relation_xml_path = str(relation_file_path)
        logger.info(f"Successfully wrote relation XML to {relation_file_path}. Content head: {state.relation_xml_content[:100]}")
    except IOError as e:
        logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to write relation XML: {e}"
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    state.dialog_state = "generating_xml_final"
    state.subgraph_completion_status = None
    return state 