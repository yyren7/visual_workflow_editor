# ---- START PATCH FOR DIRECT EXECUTION ----
if __name__ == '__main__' and (__package__ is None or __package__ == ''):
    import sys
    from pathlib import Path
    # Calculate the path to the project root ('/workspace')
    # This file is backend/langgraphchat/graph/subgraph/sas/graph_builder.py
    # Relative path from this file to /workspace is ../../../../..
    project_root = Path(__file__).resolve().parents[5]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Set __package__ to the expected package name for relative imports to work
    # The package is 'backend.langgraphchat.graph.subgraph.sas'
    __package__ = "backend.langgraphchat.graph.subgraph.sas"
# ---- END PATCH FOR DIRECT EXECUTION ----

import logging
import functools
from typing import Dict, Any, Optional, Callable, List
import asyncio
import os
import xml.etree.ElementTree as ET
import copy
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
import json

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import Client as LangSmithClient
from langsmith.utils import tracing_is_enabled as langsmith_tracing_is_enabled
from langchain_core.callbacks import BaseCallbackHandler

from .state import RobotFlowAgentState, GeneratedXmlFile
from .llm_nodes import (
    preprocess_and_enrich_input_node,
    understand_input_node,
    generate_individual_xmls_node,
    user_input_to_process_node
)
from .nodes import (
    process_description_to_module_steps_node,
    parameter_mapping_node
)
from .xml_tools import WriteXmlFileTool
from ....tools.file_share_tool import upload_file
from .prompt_loader import DEFAULT_CONFIG

logger = logging.getLogger(__name__)

load_dotenv() # Load environment variables from .env file

# Node name constants for clarity in graph definition
INITIALIZE_STATE = "initialize_state"
CORE_INTERACTION_NODE = "core_interaction_node"
UNDERSTAND_INPUT = "understand_input"
GENERATE_INDIVIDUAL_XMLS = "generate_individual_xmls"
GENERATE_RELATION_XML = "generate_relation_xml"
GENERATE_FINAL_XML = "generate_final_xml"
ERROR_HANDLER = "error_handler" # General error logging node, if needed beyond is_error flag
UPLOAD_FINAL_XML_NODE = "upload_final_xml_node" # If you have this node for uploading

# Define a new end state for clarification
END_FOR_CLARIFICATION = "end_for_clarification"
BLOCKLY_NS = "https://developers.google.com/blockly/xml" # Define globally for this module

# New node names for SAS refactoring
SAS_USER_INPUT_TO_PROCESS = "sas_user_input_to_process"
SAS_PROCESS_TO_MODULE_STEPS = "sas_process_to_module_steps"
SAS_PARAMETER_MAPPING = "sas_parameter_mapping"

def initialize_state_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    logger.info("--- Initializing Agent State (Robot Flow Subgraph) ---")
    merged_config = DEFAULT_CONFIG.copy()
    if state.config is None: state.config = {}
    merged_config.update(state.config)
    state.config = merged_config
    
    # Create a run-specific output directory
    base_output_dir_str = merged_config.get("RUN_BASE_OUTPUT_DIR", "backend/tests/llm_sas_test")
    base_output_dir = Path(base_output_dir_str)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_specific_dir_name = f"run_{timestamp}"
    run_output_dir = base_output_dir / run_specific_dir_name
    try:
        run_output_dir.mkdir(parents=True, exist_ok=True)
        state.run_output_directory = str(run_output_dir.resolve())
        logger.info(f"Created run-specific output directory: {state.run_output_directory}")

        # Create a JSON file for caching step outputs within the run-specific directory
        json_cache_filename = "step_outputs.json"
        # run_output_dir is already a Path object here
        json_cache_file_path = run_output_dir / json_cache_filename
        try:
            with open(json_cache_file_path, "w", encoding="utf-8") as f:
                json.dump({}, f) # Initialize with an empty JSON object
            logger.info(f"Successfully created step output cache file: {json_cache_file_path}")
        except IOError as e_json: # More specific exception for file I/O
            logger.error(f"Failed to create step output cache file '{json_cache_filename}' in '{state.run_output_directory}': {e_json}", exc_info=True)
            # This failure is logged but doesn't make the overall initialization fail for now.

    except Exception as e_dir: # This catches errors from mkdir or path resolution for run_output_dir
        logger.error(f"Failed to create run-specific output directory at {run_output_dir}: {e_dir}", exc_info=True)
        # Decide if this error should prevent further execution
        # For now, log and continue; the parser node will handle missing dir
        state.run_output_directory = None # Explicitly set to None on failure

    if state.dialog_state is None: state.dialog_state = "initial"
    state.current_step_description = "Initialized Robot Flow Subgraph"
    # Ensure user_input from invoker is preserved if dialog_state is initial
    # preprocess_and_enrich_input_node will consume it.
    logger.info(f"Agent state initialized. Dialog state: {state.dialog_state}, Initial User Input: '{state.user_input}', Using NODE_TEMPLATE_DIR_PATH: {state.config.get('NODE_TEMPLATE_DIR_PATH')}")
    return state.model_dump(exclude_none=True)

def _generate_relation_xml_content_from_steps_py(
    parsed_steps: Optional[List[Dict[str, Any]]],
    generated_xmls: Optional[List[GeneratedXmlFile]],
    config: Dict[str, Any] # For logging and potential future use
) -> str:
    logger.info("--- Generating Relation XML (Python Logic) ---")

    if not parsed_steps or not generated_xmls:
        logger.warning("Parsed steps or generated XMLs are empty. Generating empty relation XML.")
        return f'<?xml version="1.0" encoding="UTF-8"?>\\n<xml xmlns="{BLOCKLY_NS}"></xml>'

    relation_root = ET.Element(f"{{{BLOCKLY_NS}}}xml")

    valid_block_data: List[Dict[str, str]] = [] # Store dicts with "id" and "type"

    for i, step_info in enumerate(parsed_steps):
        if i < len(generated_xmls):
            xml_file_info = generated_xmls[i]
            if xml_file_info.status == "success" and xml_file_info.block_id and xml_file_info.type:
                valid_block_data.append({"id": xml_file_info.block_id, "type": xml_file_info.type})
            else:
                desc = step_info.get('description', f'step_{i}')
                logger.warning(f"Skipping step '{desc}' for relation.xml as its individual XML generation failed or block_id/type is missing.")
        else:
            logger.error(f"Mismatch: parsed_step {i} has no corresponding entry in generated_xmls.")

    if not valid_block_data:
        logger.warning("No successfully generated blocks with IDs and types found. Generating empty relation XML.")
        return f'<?xml version="1.0" encoding="UTF-8"?>\\n<xml xmlns="{BLOCKLY_NS}"></xml>'

    current_xml_element_in_relation: Optional[ET.Element] = None
    for block_info in valid_block_data:
        block_id = block_info["id"]
        block_type = block_info["type"]

        new_block_relation_element = ET.Element("block")
        new_block_relation_element.set("type", block_type)
        new_block_relation_element.set("id", block_id)

        if current_xml_element_in_relation is None:
            relation_root.append(new_block_relation_element)
        else:
            next_element = ET.SubElement(current_xml_element_in_relation, "next")
            next_element.append(new_block_relation_element)
        
        current_xml_element_in_relation = new_block_relation_element
        
        # Basic loop handling: If a block type ends with '_start' or is known as a loop type,
        # and the next block type is its corresponding '_end', then nest subsequent blocks.
        # This is a placeholder for more robust loop/statement handling.
        # For now, we primarily support linear flows. More complex nesting requires
        # analyzing parsed_steps' has_sub_steps and sub_step_descriptions,
        # or a dedicated recursive structure builder.

    try:
        if hasattr(ET, 'indent'): ET.indent(relation_root, space="  ")
        xml_string = ET.tostring(relation_root, encoding="unicode", xml_declaration=False)
        final_xml_string = f'<?xml version="1.0" encoding="UTF-8"?>\\n{xml_string}'
        logger.info(f"Successfully generated relation.xml content (Python Logic). Preview: {final_xml_string[:250]}...")
        return final_xml_string
    except Exception as e:
        logger.error(f"Error serializing relation XML (Python Logic): {e}", exc_info=True)
        # Fallback to empty XML on serialization error
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>'

def generate_relation_xml_node_py(state: RobotFlowAgentState) -> Dict[str, Any]:
    logger.info("--- Running Step 3: Generate Node Relation XML (Python Implementation) ---")
    state.current_step_description = "Generating node relation XML file (Python)"
    state.is_error = False 

    config = state.config
    parsed_steps = state.parsed_flow_steps
    generated_node_xmls_list = state.generated_node_xmls if state.generated_node_xmls is not None else []

    if not parsed_steps:
        logger.warning("Parsed flow steps are missing for relation XML generation. Generating empty relation.xml.")
        state.relation_xml_content = f'<?xml version="1.0" encoding="UTF-8"?>\\n<xml xmlns="{BLOCKLY_NS}"></xml>'
        # Attempt to save this empty relation.xml
    else:
        try:
            state.relation_xml_content = _generate_relation_xml_content_from_steps_py(
                parsed_steps,
                generated_node_xmls_list,
                config
            )
        except Exception as e:
            logger.error(f"Internal error: Unexpected error while generating relation XML: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Internal error: Unexpected error while generating relation XML: {e}"
            state.relation_xml_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>' # Fallback
            state.subgraph_completion_status = "error"

    output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
    relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
    relation_file_path = output_dir / relation_file_name
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(relation_file_path, "w", encoding="utf-8") as f:
            f.write(state.relation_xml_content)
        state.relation_xml_path = str(relation_file_path)
        logger.info(f"Successfully wrote relation XML to {relation_file_path}.")
    except IOError as e:
        logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
        state.is_error = True # Mark as error if file write fails
        state.error_message = (state.error_message or "") + f" Failed to save relation file: {e}"
        state.subgraph_completion_status = "error"
        # relation_xml_content remains in state for potential debugging

    if not state.is_error:
        state.dialog_state = "generating_xml_final"
        state.subgraph_completion_status = None 
    else: # if an error occurred either during generation or saving
        state.dialog_state = "error" # Or route back to core for retry/clarification
        if not any( state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
             state.messages = state.messages + [AIMessage(content=f"Error generating relation XML: {state.error_message}")]

    return state.model_dump(exclude_none=True)

async def generate_final_flow_xml_node(state: RobotFlowAgentState, llm: Optional[BaseChatModel] = None) -> Dict[str, Any]:
    logger.info("--- Running Step 4: Merge Individual XMLs into Final Flow XML ---")
    state.current_step_description = "Merging XMLs into final flow file"
    state.is_error = False # Reset error flag at the beginning of the node execution
    state.dialog_state = "generating_xml_final" # Update dialog state

    relation_xml_str = state.relation_xml_content
    individual_xmls_info = state.generated_node_xmls
    config = state.config
    state.is_error = False # Reset error before attempting

    if not relation_xml_str:
        logger.error("Relation XML content is missing from state.")
        state.is_error = True
        state.error_message = "Internal error: Relation XML content is missing, cannot merge final flow."
        state.subgraph_completion_status = "error"
        # state.messages = state.messages + [AIMessage(content=state.error_message)] # Message will be added by routing logic
        return state.model_dump(exclude_none=True)

    if not individual_xmls_info:
        logger.warning("List of generated individual XMLs is empty. Final flow may be minimal.")

    # ... (rest of the existing XML merging logic from the original file) ...
    # Ensure BLOCKLY_NS is defined or imported
    block_element_map: Dict[str, ET.Element] = {}
    if individual_xmls_info: 
        for gf in individual_xmls_info:
            if gf.status == "success" and gf.xml_content and gf.block_id:
                try:
                    individual_xml_file_root = ET.fromstring(gf.xml_content)
                    block_node = None
                    # Blockly XMLs might or might not have the namespace directly on <block>
                    # but often have it on the root <xml> tag.
                    # We search for any block tag, with or without namespace explicitly here for robustness.
                    block_node_ns = individual_xml_file_root.find(f"{{{BLOCKLY_NS}}}block")
                    block_node_no_ns = individual_xml_file_root.find("block")
                    block_node = block_node_ns if block_node_ns is not None else block_node_no_ns
                    
                    if block_node is None: # If still not found, check children of the root if root is <xml>
                        if individual_xml_file_root.tag == f"{{{BLOCKLY_NS}}}xml" or individual_xml_file_root.tag == "xml":
                            for child in individual_xml_file_root:
                                if child.tag == f"{{{BLOCKLY_NS}}}block" or child.tag == "block":
                                    block_node = child
                                    break
                    
                    if block_node is not None:
                        block_element_map[gf.block_id] = block_node
                    else:
                        logger.warning(f"Could not find main <block> in individual XML for block_id: {gf.block_id} (content: {gf.xml_content[:100]}...).")
                except ET.ParseError as e:
                    logger.error(f"Failed to parse XML for block_id {gf.block_id}: {e}. XML: {gf.xml_content[:200]}", exc_info=True)
                    state.is_error = True
                    state.error_message = f"Internal error: Failed to parse XML for node {gf.block_id}: {e}"
                    state.subgraph_completion_status = "error"
                    return state.model_dump(exclude_none=True)
            elif gf.block_id:
                logger.warning(f"Skipping block_id {gf.block_id} for merge due to status '{gf.status}' or no content.")

    try:
        relation_structure_root = ET.fromstring(relation_xml_str)
    except ET.ParseError as e:
        logger.error(f"Failed to parse relation.xml: {e}. XML: {relation_xml_str[:200]}", exc_info=True)
        state.is_error = True
        state.error_message = f"Internal error: Failed to parse relation XML: {e}"
        state.subgraph_completion_status = "error"
        return state.model_dump(exclude_none=True)

    final_flow_xml_root = ET.Element(f"{{{BLOCKLY_NS}}}xml")
    for name, value in relation_structure_root.attrib.items(): # Copy attributes from relation <xml> root
         final_flow_xml_root.set(name, value)
    
    memo_processed_relation_blocks: Dict[str, ET.Element] = {}

    def _build_final_block_tree(relation_block_element: ET.Element) -> ET.Element:
        block_id = relation_block_element.get("id")
        if not block_id:
            err_msg = f"Block in relation.xml missing 'id': {ET.tostring(relation_block_element, encoding='unicode')}"
            logger.error(err_msg)
            raise LookupError(err_msg)
        
        if block_id in memo_processed_relation_blocks:
            return copy.deepcopy(memo_processed_relation_blocks[block_id])

        full_block_template_from_map = block_element_map.get(block_id)
        if full_block_template_from_map is None:
            block_type_from_relation = relation_block_element.get("type", "N/A")
            err_msg = f"Content for block_id '{block_id}' (type: {block_type_from_relation}) not found in provided individual XMLs."
            logger.error(err_msg)
            raise LookupError(err_msg)

        final_merged_block = copy.deepcopy(full_block_template_from_map)
        for child_tag_to_clear in ["next", "statement"]:
            # Check with and without namespace for broader compatibility
            for ns_prefix in [f"{{{BLOCKLY_NS}}}", ""]:
                for element_to_remove in final_merged_block.findall(f"{ns_prefix}{child_tag_to_clear}"):
                    final_merged_block.remove(element_to_remove)
        
        for rel_statement_element in relation_block_element.findall(f"{{{BLOCKLY_NS}}}statement") + relation_block_element.findall("statement"):
            statement_name = rel_statement_element.get("name")
            final_stmt_element_for_merge = ET.SubElement(final_merged_block, f"{{{BLOCKLY_NS}}}statement", name=statement_name)
            rel_inner_block = rel_statement_element.find(f"{{{BLOCKLY_NS}}}block") or rel_statement_element.find("block")
            if rel_inner_block is not None:
                constructed_inner_block = _build_final_block_tree(rel_inner_block)
                final_stmt_element_for_merge.append(constructed_inner_block)
        
        rel_next_element = relation_block_element.find(f"{{{BLOCKLY_NS}}}next") or relation_block_element.find("next")
        if rel_next_element is not None:
            rel_next_inner_block = rel_next_element.find(f"{{{BLOCKLY_NS}}}block") or rel_next_element.find("block")
            if rel_next_inner_block is not None:
                final_next_element_for_merge = ET.SubElement(final_merged_block, f"{{{BLOCKLY_NS}}}next")
                constructed_next_inner_block = _build_final_block_tree(rel_next_inner_block)
                final_next_element_for_merge.append(constructed_next_inner_block)
        
        memo_processed_relation_blocks[block_id] = final_merged_block
        return copy.deepcopy(final_merged_block)

    try:
        # Find the first block, might be namespaced or not
        first_block_in_relation = relation_structure_root.find(f"{{{BLOCKLY_NS}}}block") or relation_structure_root.find("block")
        if first_block_in_relation is not None:
            root_block_for_final_flow = _build_final_block_tree(first_block_in_relation)
            final_flow_xml_root.append(root_block_for_final_flow)
        elif block_element_map:
             logger.warning("Relation.xml is empty but individual XMLs exist. Final flow.xml will be empty.")
        else: 
            logger.info("Relation.xml and individual_node_xmls are empty. Final flow.xml will be empty.")
    except LookupError as e:
        logger.error(f"Merge process failed due to missing block data or structure: {e}", exc_info=True)
        state.is_error = True; state.error_message = str(e); 
        state.subgraph_completion_status = "error"
        return state.model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Unexpected error during final XML construction: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Internal error: Unexpected error while constructing final XML: {e}"; 
        state.subgraph_completion_status = "error"
        return state.model_dump(exclude_none=True)

    ET.register_namespace("", BLOCKLY_NS) # Ensure default namespace for output
    try:
        if hasattr(ET, 'indent'): ET.indent(final_flow_xml_root, space="  ") # Python 3.9+
        merged_xml_content_string = ET.tostring(final_flow_xml_root, encoding='unicode', xml_declaration=False)
        final_xml_string_output = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n{merged_xml_content_string}"
    except Exception as e:
        logger.error(f"Error serializing final merged XML: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Internal error: Error serializing final XML: {e}"; 
        state.subgraph_completion_status = "error"
        return state.model_dump(exclude_none=True)

    state.final_flow_xml_content = final_xml_string_output
    output_dir_path_str = config.get("OUTPUT_DIR_PATH", "/tmp") # Ensure config is available
    final_flow_file_name = config.get("FINAL_FLOW_FILE_NAME_ACTUAL", "flow.xml")
    final_file_path = Path(output_dir_path_str) / final_flow_file_name
    try:
        os.makedirs(output_dir_path_str, exist_ok=True)
        with open(final_file_path, "w", encoding="utf-8") as f:
            f.write(state.final_flow_xml_content)
        state.final_flow_xml_path = str(final_file_path)
        logger.info(f"Successfully merged and saved final flow XML to: {state.final_flow_xml_path}")
    except Exception as e:
        logger.error(f"Error saving final_flow.xml to {final_file_path}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to save final flow file {final_file_path}: {e}"
        state.subgraph_completion_status = "error"
        # Keep final_flow_xml_content in state even if save fails

    if not state.is_error:
        state.subgraph_completion_status = "completed_success"
        state.dialog_state = "final_xml_generated_success"
        state.clarification_question = None

    return state.model_dump(exclude_none=True)

# --- Conditional Edge Functions ---
def route_after_core_interaction(state: RobotFlowAgentState) -> str:
    logger.info(
        f"Entering routing after Core Interaction. dialog_state: {state.dialog_state}, "
        f"raw_user_request: '{state.raw_user_request}', "
        f"active_plan_basis: '{state.active_plan_basis}', "
        f"enriched_structured_text: '{state.enriched_structured_text}', "
        f"is_error: {state.is_error}"
    )
    logger.info(f"--- Routing after Core Interaction (dialog_state: '{state.dialog_state}', is_error: {state.is_error}) ---")
    
    # Check if preprocess_and_enrich_input_node (CORE_INTERACTION_NODE) itself set an error during its execution
    if state.is_error: # This implies preprocess_and_enrich_input_node failed its own task
        logger.warning(f"Error flag is set by CORE_INTERACTION_NODE. Dialog state: {state.dialog_state}. Routing back to core for user correction.")
        # Ensure error message is in messages for the user to see
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=f"Error preprocessing input: {state.error_message}")]
        state.dialog_state = 'awaiting_user_input' # Prepare for new user input
        state.user_input = None # Crucial: Clear stale user_input to prevent re-processing old data if core node failed.
        state.clarification_question = None # Clear any pending questions from core node
        return CORE_INTERACTION_NODE

    current_dialog_state = state.dialog_state

    # If a clarification question has been set by CORE_INTERACTION_NODE, 
    # and it's waiting for input, it should end the current graph run.
    if state.clarification_question and current_dialog_state in [
        "awaiting_enrichment_confirmation", 
        "awaiting_user_input", # If CORE_INTERACTION_NODE decided to ask a question and transitioned to this state
        "initial" # If it asked a question right from the initial state
    ]:
        logger.info(f"Clarification question is pending ('{state.clarification_question}'). Dialog state: {current_dialog_state}. Ending graph invocation to get user input.")
        state.subgraph_completion_status = "needs_clarification" # Indicate why it's ending
        return END_FOR_CLARIFICATION

    if current_dialog_state == "input_understood_ready_for_xml":
        if state.enriched_structured_text:
            logger.info("Core interaction successful (input_understood_ready_for_xml). Routing to: UNDERSTAND_INPUT")
            return UNDERSTAND_INPUT
        else: 
            logger.warning("State is 'input_understood_ready_for_xml' but enriched_structured_text is missing. Awaiting user input.")
            if not any("Flow description is incomplete" in msg.content for msg in state.messages if isinstance(msg, AIMessage)): # Check for English version
                 state.messages = state.messages + [AIMessage(content="Flow description is incomplete or could not be processed correctly, please re-enter." )]
            state.dialog_state = "awaiting_user_input"
            state.user_input = None # Clear stale input
            return CORE_INTERACTION_NODE
    elif current_dialog_state in ["awaiting_enrichment_confirmation", "awaiting_user_input", "processing_user_input", "generation_failed"]:
        # If CORE_INTERACTION_NODE (preprocess_and_enrich_input_node) has set one of these states, 
        # it means it's either waiting for a specific user reply (e.g. to a clarification_question),
        # actively processing, or has just handled a generation failure by setting state to await input.
        # In all these cases, the graph should loop back to CORE_INTERACTION_NODE.
        logger.info(f"Staying in CORE_INTERACTION_NODE. Dialog_state: {current_dialog_state}. This node will await next invocation or process further.")
        return CORE_INTERACTION_NODE
    
    # Fallback: If no conditions above are met (which should be rare if preprocess_and_enrich_input_node behaves as expected)
    # this indicates an unexpected state produced by CORE_INTERACTION_NODE itself.
    logger.error(f"CRITICAL: route_after_core_interaction encountered an unhandled dialog_state '{current_dialog_state}' originating from CORE_INTERACTION_NODE. This suggests an issue in preprocess_and_enrich_input_node's state setting. Resetting to await user input.")
    if not any(f"Robot flow subgraph encountered an unhandled core state ({current_dialog_state})" in msg.content for msg in state.messages if isinstance(msg, AIMessage)): # Check for English version
        state.messages = state.messages + [AIMessage(content=f"Robot flow subgraph encountered an unhandled core state ({current_dialog_state}). Please retry or contact support." )]
    state.dialog_state = "awaiting_user_input"
    state.user_input = None
    state.is_error = True
    state.error_message = f"Robot flow subgraph encountered an unhandled core state ({current_dialog_state})."
    state.clarification_question = None
    return CORE_INTERACTION_NODE

def route_xml_generation_or_python_step(state: RobotFlowAgentState, next_step_if_ok: str, current_step_name_for_log: str) -> str:
    """Generic router for steps that can set state.is_error."""
    logger.info(f"--- Routing after Step: '{current_step_name_for_log}' (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "error": # Check dialog_state as well, as some python nodes might set it
        logger.warning(f"Error during '{current_step_name_for_log}'. Routing to core_interaction_node.")
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            # Ensure the error_message from the state is added to AIMessages if not already present by the node itself
            state.messages = state.messages + [AIMessage(content=f"Error in step '{current_step_name_for_log}': {state.error_message}")]
        
        # Reset relevant state fields before going back to core interaction
        state.dialog_state = 'generation_failed' # A specific state to indicate failure and need for new input/correction
        state.user_input = None 
        # state.is_error should remain True as set by the failing node
        state.subgraph_completion_status = "error" # Mark subgraph as errored
        return CORE_INTERACTION_NODE
    else:
        logger.info(f"'{current_step_name_for_log}' successful. Routing to {next_step_if_ok}.")
        return next_step_if_ok

def decide_after_final_xml_generation(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Deciding after Final XML Generation (is_error: {state.is_error}, final_xml_content exists: {bool(state.final_flow_xml_content)}) ---")
    if not state.is_error and state.final_flow_xml_content:
        logger.info("Final XML generated successfully. Routing to END.")
        if not any("Flow XML generated successfully" in msg.content for msg in state.messages if isinstance(msg, AIMessage)): # Check for English version
             state.messages = state.messages + [AIMessage(content=f"Flow XML generated successfully. You can view it at path {state.final_flow_xml_path or 'not saved to file'}, or see the content in the chat history.")]
        state.dialog_state = 'final_xml_generated_success'
        state.subgraph_completion_status = "completed_success" # Mark as fully successful
        return END
    else:
        logger.warning("Final XML generation failed or produced no content. Routing back to core_interaction_node.")
        if not state.is_error: # If is_error wasn't set but content is missing
            state.is_error = True
            state.error_message = state.error_message or "Final XML content is empty or generation failed."
        
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=f"Problem encountered while generating final XML: {state.error_message}. Please modify your instructions." )]
        
        state.dialog_state = 'generation_failed'
        state.user_input = None
        state.subgraph_completion_status = "error"
        return CORE_INTERACTION_NODE

# New routing function for SAS Step 1
def route_after_sas_step1(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 1: User Input to Process Description (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "error":
        logger.warning(f"Error during SAS Step 1. Error message: {state.error_message}")
        # state.subgraph_completion_status is likely already set to "error" by the node
        if not state.error_message:
             state.error_message = "Unknown error after SAS Step 1."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"SAS Step 1 Failed: {state.error_message}")]
        return END # End the graph on error for now
    elif state.dialog_state == "sas_step1_completed":
        logger.info("SAS Step 1 (User Input to Process Description) completed successfully. Routing to Step 2.")
        # state.subgraph_completion_status is likely "completed_partial" by the node
        return SAS_PROCESS_TO_MODULE_STEPS
    else:
        logger.warning(f"Unexpected state after SAS Step 1: {state.dialog_state}. Routing to END.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected state ({state.dialog_state}) after SAS Step 1."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return END

# New routing function for SAS Step 2
def route_after_sas_step2(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 2: Process Description to Module Steps (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "error":
        logger.warning(f"Error during SAS Step 2. Error message: {state.error_message}")
        if not state.error_message:
             state.error_message = "Unknown error after SAS Step 2."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"SAS Step 2 Failed: {state.error_message}")]
        return END
    elif state.dialog_state == "sas_step2_completed":
        logger.info("SAS Step 2 (Process Description to Module Steps) completed successfully. Routing to Step 3.")
        return SAS_PARAMETER_MAPPING
    else:
        logger.warning(f"Unexpected state after SAS Step 2: {state.dialog_state}. Routing to END.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected state ({state.dialog_state}) after SAS Step 2."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return END

# New routing function for SAS Step 3
def route_after_sas_step3(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 3: Parameter Mapping (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "error":
        logger.warning(f"Error during SAS Step 3. Error message: {state.error_message}")
        if not state.error_message:
             state.error_message = "Unknown error after SAS Step 3."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"SAS Step 3 Failed: {state.error_message}")]
        return END
    elif state.dialog_state == "sas_step3_completed":
        logger.info("SAS Step 3 (Parameter Mapping) completed successfully. All SAS steps complete.")
        # Mark as fully completed
        state.subgraph_completion_status = "completed_success"
        return END
    else:
        logger.warning(f"Unexpected state after SAS Step 3: {state.dialog_state}. Routing to END.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected state ({state.dialog_state}) after SAS Step 3."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return END

# create_robot_flow_graph function (original was L344, this is a rewrite for the new flow)
def create_robot_flow_graph(
    llm: BaseChatModel,
) -> Callable[[Dict[str, Any]], Any]: 
    
    workflow = StateGraph(RobotFlowAgentState)

    # Node Binding (using functools.partial for llm where needed)
    workflow.add_node(INITIALIZE_STATE, initialize_state_node)
    workflow.add_node(SAS_USER_INPUT_TO_PROCESS, functools.partial(user_input_to_process_node, llm=llm))
    workflow.add_node(SAS_PROCESS_TO_MODULE_STEPS, functools.partial(process_description_to_module_steps_node, llm=llm))
    workflow.add_node(SAS_PARAMETER_MAPPING, parameter_mapping_node)

    # --- Original Nodes (Commented out for SAS refactoring) ---
    # workflow.add_node(CORE_INTERACTION_NODE, functools.partial(preprocess_and_enrich_input_node, llm=llm))
    # workflow.add_node(UNDERSTAND_INPUT, functools.partial(understand_input_node, llm=llm))
    # workflow.add_node(GENERATE_INDIVIDUAL_XMLS, functools.partial(generate_individual_xmls_node, llm=llm))
    # workflow.add_node(GENERATE_RELATION_XML, generate_relation_xml_node_py) # generate_relation_xml_node_py is python only
    # workflow.add_node(GENERATE_FINAL_XML, functools.partial(generate_final_flow_xml_node, llm=llm))
    # workflow.add_node(ERROR_HANDLER, error_handler_node) # Optional: if a separate error logging node is desired.

    # --- Define Graph Edges ---
    workflow.set_entry_point(INITIALIZE_STATE)
    # New flow for SAS refactoring: INITIALIZE_STATE -> SAS_USER_INPUT_TO_PROCESS -> SAS_PROCESS_TO_MODULE_STEPS -> SAS_PARAMETER_MAPPING -> END
    workflow.add_edge(INITIALIZE_STATE, SAS_USER_INPUT_TO_PROCESS)

    workflow.add_conditional_edges(
        SAS_USER_INPUT_TO_PROCESS,
        route_after_sas_step1,
        {
            SAS_PROCESS_TO_MODULE_STEPS: SAS_PROCESS_TO_MODULE_STEPS,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_PROCESS_TO_MODULE_STEPS,
        route_after_sas_step2,
        {
            SAS_PARAMETER_MAPPING: SAS_PARAMETER_MAPPING,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_PARAMETER_MAPPING,
        route_after_sas_step3,
        {
            END: END
        }
    )

    app = workflow.compile()
    return app

# Removed old should_continue and other unused/placeholder nodes/edges from original file if they existed.
# Ensure all node functions (initialize_state_node, generate_final_flow_xml_node, etc.)
# return state.dict(exclude_none=True) if RobotFlowAgentState is Pydantic model.

# Example of how to run (for testing, typically in a main script)
# if __name__ == '__main__':
#     from langchain_openai import ChatOpenAI # Or your preferred LLM
#     import json # Make sure json is imported for dump

#     # Configure logging
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#     # Initialize LLM (ensure API key is set in environment)
#     # llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
#     llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0) # Cheaper for testing
    
#     # Create the graph
#     robot_flow_app = create_robot_flow_graph(llm=llm)

#     # Example initial state (input for the graph)
#     initial_input_state = {
#         "messages": [], 
#         "user_input": "机器人: dobot_mg400\n工作流程：\n1. 将电机状态设置为 on。\n2. 线性移动到点 P1。Z 轴启用,其余禁用。\n3. 线性移动到点 P2。X 轴启用,其余禁用。",
#         "config": {"OUTPUT_DIR_PATH": "/workspace/test_robot_flow_output_deepseek_interactive"} # Example of overriding default config
#     }

#     logger.info(f"Invoking graph with initial input: {initial_input_state}")

#     # # Stream events from the graph
#     # async def stream_events():
#     #     async for event in robot_flow_app.astream(initial_input_state, {"recursion_limit": 5}):
#     #         for key, value in event.items():
#     #             logger.info(f"Event: {key} - Value: {value}")
#     #         print("---")
#     # asyncio.run(stream_events())
    
#     final_state = asyncio.run(robot_flow_app.ainvoke(initial_input_state, {"recursion_limit": 5}))
#     logger.info(f"\nFinal State: {json.dumps(final_state, indent=2, ensure_ascii=False)}")

#     if final_state.get('is_error'):
#         logger.error(f"Flow completed with an error: {final_state.get('error_message')}")
#     elif final_state.get('final_flow_xml_path'):
#         logger.info(f"Flow completed successfully. Final XML at: {final_state.get('final_flow_xml_path')}")
#     elif final_state.get('generated_node_xmls') and any(xml.status == 'success' for xml in final_state.get('generated_node_xmls')):
#         logger.info("Flow completed up to generating individual XMLs. Relation and Final XML steps might be placeholders or incomplete.")
#     elif final_state.get('parsed_flow_steps'):
#         logger.info("Flow completed up to understanding input. Further steps need implementation or are placeholders.")
#     else:
#         logger.info("Flow completed, but no specific output path found. Check logs for details.") 

class RootRunIDCollector(BaseCallbackHandler):
    """Callback handler to collect the root run ID of a trace."""
    def __init__(self):
        super().__init__()
        self.root_run_id = None
        self.run_map = {} # To store run objects by id

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], *, run_id, parent_run_id: Optional[str] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        if parent_run_id is None: # This is a root run
            self.root_run_id = run_id
        # Store basic info, could be expanded if needed during streaming
        self.run_map[run_id] = {"id": run_id, "name": serialized.get("name", "Unknown"), "inputs": inputs}


    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], *, run_id, parent_run_id: Optional[str] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        if parent_run_id is None and self.root_run_id is None : # This is a root run (if an LLM is a root)
             self.root_run_id = run_id
        self.run_map[run_id] = {"id": run_id, "name": serialized.get("name", prompts[0][:30] if prompts else "Unknown LLM"), "inputs": {"prompts": prompts}}


    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, *, run_id, parent_run_id: Optional[str] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        if parent_run_id is None and self.root_run_id is None:
            self.root_run_id = run_id
        self.run_map[run_id] = {"id": run_id, "name": serialized.get("name", "Unknown Tool"), "inputs": {"input_str": input_str}}


async def main_test_run():
    # from langchain_openai import ChatOpenAI # Commented out OpenAI import
    import json
    import os # Ensure os is imported for getenv

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Load environment variables (already done globally by load_dotenv())

    # Get Gemini configuration from environment variables
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-pro") # Default to gemini-pro if not set

    if not gemini_api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")
        return

    logger.info(f"Using Gemini model: {gemini_model_name}")
    llm = ChatGoogleGenerativeAI(
        model=gemini_model_name, 
        google_api_key=gemini_api_key,
        temperature=0, # Consistent with previous OpenAI setup
    )

    robot_flow_app = create_robot_flow_graph(llm=llm)

    initial_input_state = {
        "messages": [], 
        "user_input":  """この自動化プロセスは、ベアリング（BRG）、ベアリングハウジング（BH）、およびパレット（PLT）が関与する組み立ておよび取り扱いタスクを共同で完了することを目的としています。ロボットはまず、初期位置からベアリングとベアリングハウジングを取得します。その後、これら 2 つの部品を右側のマシニングセンター（RMC）に順次配置し、ここで圧入または組み立て操作を行うと予定です。組み立て後、ロボットは RMC から組み立てられた部品を取り出し、左側のマシニングセンター（LMC）に転送して一時保管または後続処理を行います。次に、ロボットは空のパレットを取得し、このパレットをコンベア（CNV）の指定されたステーションに配置します。最後に、ロボットは LMC から以前に保管されていた組み立て済み部品を取得し、コンベア上のパレットに正確に配置して、サイクル全体を完了します。"""
,
        "config": {
            "OUTPUT_DIR_PATH": "/workspace/test_robot_flow_output_py_relation",
            "NODE_TEMPLATE_DIR_PATH": "/workspace/database/node_database/quick-fcpr-new/" # Ensure this path is correct
            } 
    }
    
    # More complex input for testing loops (if supported by templates and prompts)
    # initial_input_state_loop = {
    #     "messages": [],
    #     "user_input": "Robot: dobot_mg400\nWorkflow:\n1. Motor on\n2. Loop 3 times:\n   a. Move to P1\n   b. Move to P2\n3. Motor off",
    #     "config": {"OUTPUT_DIR_PATH": "/workspace/test_robot_flow_output_loop_py_relation"}
    # }

    logger.info(f"Invoking graph with initial input: {initial_input_state}")
    
    final_state = {} # Initialize to store the last state from the stream
    root_run_id_collector = RootRunIDCollector()
    langsmith_client = None
    if langsmith_tracing_is_enabled():
        try:
            langsmith_client = LangSmithClient() # Initialize client to fetch run details later
            logger.info("LangSmith tracing is enabled. Metrics will be collected.")
        except Exception as e:
            logger.warning(f"Failed to initialize LangSmith client. Metrics might not be fully collected: {e}")
            langsmith_client = None # Ensure it's None if init fails
    else:
        logger.info("LangSmith tracing is not enabled (LANGCHAIN_TRACING_V2 != 'true'). Metrics will not be collected.")

    graph_config = {"recursion_limit": 15, "callbacks": [root_run_id_collector]}

    async for event in robot_flow_app.astream(initial_input_state, config=graph_config):
        logger.info(f"Streaming Event Keys: {list(event.keys())}") # Log which node's event this is
        for key, value in event.items():
            # logger.info(f"  Node '{key}' output: {json.dumps(value, indent=2, ensure_ascii=False)}") # This can be very verbose
            logger.info(f"  State from Node '{key}':")
            if isinstance(value, dict):
                # Print a summary or specific parts of the state
                if "messages" in value and value["messages"]:
                    logger.info(f"    Last Message: {value['messages'][-1]}")
                if "current_step_description" in value:
                    logger.info(f"    Current Step: {value['current_step_description']}")
                if "dialog_state" in value:
                    logger.info(f"    Dialog State: {value['dialog_state']}")
            else:
                 logger.info(f"    Value: {str(value)[:500]}...") # Print a snippet if not a dict
            final_state = value # Capture the entire state from the last processed part of the event
        logger.info("--- Next Streaming Event ---")

    # final_state = await robot_flow_app.ainvoke(initial_input_state, {"recursion_limit": 15}) # Increased recursion limit
    # The line below was causing TypeError: Object of type async_generator is not JSON serializable OR TypeError: object async_generator can't be used in 'await' expression
    # final_state = robot_flow_app.astream(initial_input_state, {"recursion_limit": 15}) # Increased recursion limit

    logger.info(f"\nFinal Accumulated State after Stream: {json.dumps(final_state, indent=2, ensure_ascii=False)}")

    run_output_directory = final_state.get('run_output_directory')
    if not run_output_directory:
        # Fallback if not in state, though initialize_state_node should set it
        base_output_dir_str = initial_input_state.get("config", {}).get("RUN_BASE_OUTPUT_DIR", "backend/tests/llm_sas_test")
        base_output_dir = Path(base_output_dir_str)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_output_directory = str(base_output_dir / f"run_{timestamp}_fallback")
        try:
            Path(run_output_directory).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Fallback directory creation failed: {run_output_directory}, error: {e}")
            run_output_directory = None # Cannot save metrics
        logger.warning(f"run_output_directory not found in final_state, using fallback: {run_output_directory}")


    if langsmith_client and root_run_id_collector.root_run_id and run_output_directory:
        root_run_id = root_run_id_collector.root_run_id
        logger.info(f"Attempting to fetch metrics for root run ID: {root_run_id}")
        try:
            root_run = langsmith_client.read_run(root_run_id)
            
            # Fetch all types of runs associated with the trace for comprehensive node data
            runs_in_trace_iterator = langsmith_client.list_runs(trace_id=root_run.trace_id) # Use trace_id from root_run
            all_runs_in_trace = list(runs_in_trace_iterator)
            
            metrics_report = {
                "run_id": str(root_run.id),
                "name": root_run.name,
                "status": "failure" if root_run.error else "success",
                "error_message": root_run.error,
                "start_time": root_run.start_time.isoformat() if root_run.start_time else None,
                "end_time": root_run.end_time.isoformat() if root_run.end_time else None,
                "total_duration_seconds": (root_run.end_time - root_run.start_time).total_seconds() if root_run.start_time and root_run.end_time else None,
                "inputs": root_run.inputs,
                "nodes": []
            }

            # Filter for actual graph nodes (children of the root_run or part of the same trace)
            # Nodes are runs that are not the root_run itself.
            node_runs = [r for r in all_runs_in_trace if r.id != root_run.id]
            
            # Sort nodes by start time for chronological order in the report
            node_runs.sort(key=lambda r: r.start_time if r.start_time else datetime.min.replace(tzinfo=timezone))

            for node_run in node_runs:
                node_info = {
                    "node_id": str(node_run.id),
                    "name": node_run.name,
                    "status": "failure" if node_run.error else "success",
                    "error_message": node_run.error,
                    "start_time": node_run.start_time.isoformat() if node_run.start_time else None,
                    "end_time": node_run.end_time.isoformat() if node_run.end_time else None,
                    "duration_seconds": (node_run.end_time - node_run.start_time).total_seconds() if node_run.start_time and node_run.end_time else None,
                    "run_type": node_run.run_type,
                }

                if node_run.run_type == "llm":
                    llm_metrics = {}
                    ttfb_seconds = None
                    
                    if node_run.extra and 'metadata' in node_run.extra and isinstance(node_run.extra['metadata'], dict):
                        ttfb_ms = node_run.extra['metadata'].get('time_to_first_token_ms')
                        if ttfb_ms is not None: # Check for None explicitly
                            try:
                                ttfb_seconds = float(ttfb_ms) / 1000.0
                                llm_metrics["time_to_first_token_seconds"] = ttfb_seconds
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not parse TTFB from metadata ('{ttfb_ms}') for node {node_run.name}: {e}")
                    
                    completion_tokens = node_run.outputs.get("llm_output", {}).get("token_usage", {}).get("completion_tokens") if node_run.outputs else None
                    prompt_tokens = node_run.outputs.get("llm_output", {}).get("token_usage", {}).get("prompt_tokens") if node_run.outputs else None
                    # total_tokens = node_run.outputs.get("llm_output", {}).get("token_usage", {}).get("total_tokens") if node_run.outputs else None
                    # Use tokens from run object directly if available, often more reliable
                    if hasattr(node_run, 'completion_tokens') and node_run.completion_tokens is not None:
                         completion_tokens = node_run.completion_tokens
                    if hasattr(node_run, 'prompt_tokens') and node_run.prompt_tokens is not None:
                         prompt_tokens = node_run.prompt_tokens
                    
                    if completion_tokens is not None: llm_metrics["completion_tokens"] = completion_tokens
                    if prompt_tokens is not None: llm_metrics["prompt_tokens"] = prompt_tokens
                    if completion_tokens is not None and prompt_tokens is not None:
                        llm_metrics["total_tokens"] = completion_tokens + prompt_tokens
                    
                    if completion_tokens and node_run.start_time and node_run.end_time:
                        effective_latency_seconds = (node_run.end_time - node_run.start_time).total_seconds()
                        if effective_latency_seconds > 0: # Avoid division by zero
                            if ttfb_seconds is not None and effective_latency_seconds > ttfb_seconds:
                                generation_time = effective_latency_seconds - ttfb_seconds
                                if generation_time > 0: # Avoid division by zero
                                    llm_metrics["tokens_per_second"] = completion_tokens / generation_time
                            else: # If no TTFB or TTFB is not applicable
                                 llm_metrics["tokens_per_second"] = completion_tokens / effective_latency_seconds
                    
                    if llm_metrics:
                        node_info["llm_metrics"] = llm_metrics
                
                metrics_report["nodes"].append(node_info)
            
            metrics_file_path = Path(run_output_directory) / "langsmith_run_metrics.json"
            with open(metrics_file_path, "w", encoding="utf-8") as f:
                json.dump(metrics_report, f, indent=2, ensure_ascii=False)
            logger.info(f"LangSmith metrics report saved to: {metrics_file_path}")

        except Exception as e:
            logger.error(f"Failed to fetch or process LangSmith run data for run_id {root_run_id}: {e}", exc_info=True)
    elif not run_output_directory:
        logger.warning("run_output_directory is not set. LangSmith metrics report cannot be saved to a file.")
    elif not (langsmith_client and root_run_id_collector.root_run_id):
        logger.info("LangSmith client not available or root run ID not captured. Skipping metrics report generation.")


    if final_state.get('is_error'):
        logger.error(f"Flow completed with an error: {final_state.get('error_message')}")
    else:
        # Check for SAS specific completion states if applicable
        sas_status = final_state.get('subgraph_completion_status')
        if sas_status == "completed_success":
            logger.info("SAS Flow completed successfully.")
            # Add any specific output paths for SAS if available in final_state
        elif sas_status == "error":
             logger.error(f"SAS Flow completed with an error: {final_state.get('error_message')}")
        else:
            logger.info(f"Flow completed. Status: {sas_status if sas_status else 'Unknown'}. Check logs for details and output paths.")


if __name__ == '__main__':
    # The patch for direct execution is already at the top of the file.
    # Ensure load_dotenv() is called if it wasn't implicitly by the patch or top-level script execution.
    # However, load_dotenv() is already called at the global scope (line 22 in the provided full file).
    # So, environment variables from .env should be loaded by the time main_test_run is called.
    asyncio.run(main_test_run()) 