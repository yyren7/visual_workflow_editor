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
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import Client as LangSmithClient
from langsmith.utils import tracing_is_enabled as langsmith_tracing_is_enabled
from langchain_core.callbacks import BaseCallbackHandler

from .state import RobotFlowAgentState, GeneratedXmlFile
from .nodes import (
    process_description_to_module_steps_node,
    parameter_mapping_node,
    user_input_to_task_list_node,
    review_and_refine_node
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
# END_FOR_CLARIFICATION = "end_for_clarification" # Removed if not a node
BLOCKLY_NS = "https://developers.google.com/blockly/xml" # Define globally for this module

# New node names for SAS refactoring
SAS_USER_INPUT_TO_TASK_LIST = "sas_user_input_to_task_list"
SAS_PROCESS_TO_MODULE_STEPS = "sas_process_to_module_steps"
SAS_PARAMETER_MAPPING = "sas_parameter_mapping"
SAS_REVIEW_AND_REFINE = "sas_review_and_refine"

def initialize_state_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    logger.info("--- Initializing Agent State (Robot Flow Subgraph) ---")
    
    # Log the initial state of relevant config values
    logger.info(f"Initial state.config before merge: {state.config}")
    initial_output_dir_from_config = state.config.get("OUTPUT_DIR_PATH") if state.config else None
    logger.info(f"Initial OUTPUT_DIR_PATH from state.config: {initial_output_dir_from_config}")
    
    merged_config = DEFAULT_CONFIG.copy()
    if state.config is None: state.config = {}
    merged_config.update(state.config)
    state.config = merged_config # state.config is now merged_config
    
    logger.info(f"state.config after merge with DEFAULT_CONFIG: {state.config}")
    
    # Try to use the existing OUTPUT_DIR_PATH from the main graph's config
    provided_output_dir_str = merged_config.get("OUTPUT_DIR_PATH")
    logger.info(f"Value of 'OUTPUT_DIR_PATH' from merged_config: '{provided_output_dir_str}'")
    
    run_output_directory_set = False
    if provided_output_dir_str:
        provided_path_obj = Path(provided_output_dir_str)
        logger.info(f"Checking provided_output_dir_str: '{provided_output_dir_str}'")
        logger.info(f"Path('{provided_output_dir_str}').exists(): {provided_path_obj.exists()}")
        logger.info(f"Path('{provided_output_dir_str}').is_dir(): {provided_path_obj.is_dir()}")
        
        if provided_path_obj.is_dir():
            run_output_dir = provided_path_obj
            try:
                run_output_dir.mkdir(parents=True, exist_ok=True) # Ensure it still exists and we have perms
                state.run_output_directory = str(run_output_dir.resolve())
                logger.info(f"SUCCESS: Using provided output directory: {state.run_output_directory}")
                run_output_directory_set = True
            except Exception as e_dir:
                logger.error(f"Error trying to mkdir on already existing provided_output_dir_str '{run_output_dir}': {e_dir}", exc_info=True)
                # Fallback to creating a new one if ensuring fails
        elif provided_path_obj.exists() and not provided_path_obj.is_dir():
            logger.warning(f"Provided OUTPUT_DIR_PATH '{provided_output_dir_str}' exists but is NOT a directory. Will fallback.")
        else: # Path does not exist
            logger.info(f"Provided OUTPUT_DIR_PATH '{provided_output_dir_str}' does NOT exist. Attempting to create it.")
            try:
                provided_path_obj.mkdir(parents=True, exist_ok=True)
                state.run_output_directory = str(provided_path_obj.resolve())
                logger.info(f"SUCCESS: Created and using provided output directory: {state.run_output_directory}")
                run_output_directory_set = True
            except Exception as e_create:
                logger.error(f"Failed to CREATE directory from provided_output_dir_str '{provided_output_dir_str}': {e_create}", exc_info=True)
    else:
        logger.info("'OUTPUT_DIR_PATH' was not found in merged_config or was empty. Will fallback.")

    if not run_output_directory_set:
        base_output_dir_str = merged_config.get("RUN_BASE_OUTPUT_DIR", "backend/tests/llm_sas_test") # Original fallback base
        effective_base_output_dir = Path(base_output_dir_str)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_specific_dir_name = f"run_sas_subgraph_{timestamp}"
        run_output_dir = effective_base_output_dir / run_specific_dir_name
        
        logger.warning(f"FALLBACK: 'OUTPUT_DIR_PATH' ('{provided_output_dir_str}') was not valid or usable. Creating new run-specific directory in fallback location: {run_output_dir}")
        try:
            run_output_dir.mkdir(parents=True, exist_ok=True)
            state.run_output_directory = str(run_output_dir.resolve())
            logger.info(f"FALLBACK: Created new run-specific output directory: {state.run_output_directory}")
        except Exception as e_dir: 
            logger.error(f"FALLBACK: Failed to create run-specific output directory at {run_output_dir}: {e_dir}", exc_info=True)
            state.run_output_directory = None # Critical failure
    
    # Ensure other necessary paths from DEFAULT_CONFIG are also correctly set up in state.config
    # For example, NODE_TEMPLATE_DIR_PATH, etc.
    # The current merged_config should already be in state.config
    
    # Initialize other SAS-specific state variables
    if state.current_user_request is None and state.user_input:
        logger.info(f"Initializing current_user_request from initial user_input: '{state.user_input[:100]}...'")
        state.current_user_request = state.user_input
        state.active_plan_basis = state.user_input  # Set active plan basis from the first input
        state.revision_iteration = 0 # Initialize revision counter

        # Add current_user_request as the first HumanMessage if messages list is empty
        # This helps ensure the very first request is part of the message history from the start.
        # user_input_to_task_list_node will also add the input it processes to messages,
        # so we need to be careful about duplicates if it also uses current_user_request.
        # If initialize_state_node clears state.user_input, then user_input_to_task_list_node
        # should explicitly use state.current_user_request and add that to history if needed.
        if not state.messages:
            state.messages = [HumanMessage(content=state.current_user_request)]
            logger.info("Added current_user_request as the first HumanMessage because messages list was empty.")
        
        logger.info(f"Initial user_input '{state.user_input[:100]}...' moved to current_user_request. Clearing user_input for subsequent nodes.")
        state.user_input = None # Clear user_input as it has been processed into current_user_request

    elif state.user_input is not None and state.user_input == state.current_user_request:
        logger.info(f"state.user_input ('{state.user_input[:50]}...') matches state.current_user_request and was not initial. Clearing state.user_input.")
        state.user_input = None

    if state.dialog_state is None: state.dialog_state = "initial"
    state.current_step_description = "Initialized Robot Flow Subgraph"
    
    logger.info(
        f"Agent state initialized. Dialog state: {state.dialog_state}, "
        f"User Input (transient, should be None if processed by this node): '{state.user_input[:100] if state.user_input else 'None'}', "
        f"Current User Request (active base for generation): '{state.current_user_request[:100] if state.current_user_request else 'None'}', "
        f"NODE_TEMPLATE_DIR_PATH: {state.config.get('NODE_TEMPLATE_DIR_PATH')}"
    )
    logger.info(f"FINAL user_input in initialize_state_node before return: '{state.user_input}'")
    return state.model_dump()

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
        return END

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
    logger.info(f"--- Routing after SAS Step 1: User Input to Task List Generation (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "error":
        logger.warning(f"Error during SAS Step 1 (Task List Generation). Error message: {state.error_message}")
        if not state.error_message:
             state.error_message = "Unknown error after SAS Step 1 (Task List Generation)."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"SAS Step 1 (Task List Generation) Failed: {state.error_message}")]
        state.subgraph_completion_status = "error" 
        return END 
    elif state.dialog_state == "sas_step1_tasks_generated":
        logger.info("SAS Step 1 (User Input to Task List Generation) completed successfully. Routing to SAS_REVIEW_AND_REFINE.")
        state.task_list_accepted = False 
        return SAS_REVIEW_AND_REFINE 
    elif state.dialog_state == "sas_step1_completed": 
        logger.warning(f"Unexpected old state 'sas_step1_completed' after SAS Step 1. Expected 'sas_step1_tasks_generated'. Routing to END as an error.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected legacy state ('sas_step1_completed') after SAS Step 1. Task list generation might have failed to set the correct new state."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return END
    else:
        logger.warning(f"Unexpected dialog state after SAS Step 1 (Task List Generation): {state.dialog_state}. Routing to END.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected state ('{state.dialog_state}') after SAS Step 1 (Task List Generation)."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return END

# New routing function for SAS Review and Refine Task List
def route_after_sas_review_and_refine(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Review/Refine Node ---")
    logger.info(f"    is_error: {state.is_error}")
    logger.info(f"    dialog_state: '{state.dialog_state}'")
    logger.info(f"    task_list_accepted: {state.task_list_accepted}")
    logger.info(f"    module_steps_accepted: {state.module_steps_accepted}")

    if state.is_error: 
        logger.warning(f"Error flag is set after Review/Refine node. Error message: {state.error_message}")
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"Error during review/refinement: {state.error_message}")]
        state.subgraph_completion_status = "error"
        return END # Or a dedicated error handling node if desired

    # Priority 1: Handling states indicating the node is waiting for external user input
    if state.dialog_state == "sas_awaiting_task_list_review":
        logger.info("Awaiting user feedback on the TASK LIST. Ending graph run for clarification.")
        state.subgraph_completion_status = "needs_clarification"
        return END
    elif state.dialog_state == "sas_awaiting_module_steps_review":
        logger.info("Awaiting user feedback on the MODULE STEPS. Ending graph run for clarification.")
        state.subgraph_completion_status = "needs_clarification"
        return END

    # Priority 2: Handling successful acceptance of module steps
    if state.module_steps_accepted and state.dialog_state == "sas_module_steps_accepted_proceeding":
        logger.info("Module steps accepted by user. Routing to GENERATE_INDIVIDUAL_XMLS.")
        state.current_step_description = "Module steps accepted, preparing to generate individual XMLs."
        state.dialog_state = "sas_generating_individual_xmls" # New dialog state
        state.subgraph_completion_status = "processing" 
        return GENERATE_INDIVIDUAL_XMLS # Changed target

    # Priority 3: Handling successful acceptance of task list (and module steps not yet reviewed/accepted)
    if state.task_list_accepted and not state.module_steps_accepted:
        # This implies task list was accepted, and we are now either proceeding to generate module steps
        # or have just generated them and are going to review them.
        # The review_and_refine_node itself would set sas_step1_tasks_generated if only task list accepted.
        if state.dialog_state == "sas_step1_tasks_generated": # Set by review_and_refine if task list accepted
            logger.info("Task list accepted by user. Routing to SAS_PROCESS_TO_MODULE_STEPS.")
            state.subgraph_completion_status = "completed_partial"
            return SAS_PROCESS_TO_MODULE_STEPS
    
    # Priority 4: Handling regeneration/re-review loops initiated by review_and_refine_node
    if state.dialog_state == "sas_description_updated_for_regeneration": # For task list regen
        logger.info("User description revised for task list. Routing back to SAS_USER_INPUT_TO_TASK_LIST for regeneration.")
        state.subgraph_completion_status = "processing"
        return SAS_USER_INPUT_TO_TASK_LIST
    
    if state.dialog_state == "sas_step2_module_steps_generated_for_review": # For module steps re-review after modification
        logger.info("Module steps were modified. Routing back to SAS_REVIEW_AND_REFINE for re-review.")
        state.subgraph_completion_status = "processing"
        return SAS_REVIEW_AND_REFINE

    # Fallback / Unexpected states
    logger.warning(f"Unexpected state combination after SAS Review/Refine: dialog_state='{state.dialog_state}', task_list_accepted={state.task_list_accepted}, module_steps_accepted={state.module_steps_accepted}. Defaulting to END graph run for clarification or error.")
    state.subgraph_completion_status = "needs_clarification" # Or "error"
    if not state.clarification_question and not any("An unexpected state was reached" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
         state.messages = (state.messages or []) + [AIMessage(content="An unexpected state was reached during the review process. Please try providing your feedback again or restart.")]
    return END

# New routing function for SAS Step 2
def route_after_sas_step2(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 2: Module Steps Generation (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "error":
        logger.warning(f"Error during SAS Step 2. Error message: {state.error_message}")
        if not state.error_message:
             state.error_message = "Unknown error after SAS Step 2 (Module Steps Generation)."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"SAS Step 2 (Module Steps Generation) Failed: {state.error_message}")]
        state.subgraph_completion_status = "error"
        return END
    elif state.dialog_state == "sas_step2_module_steps_generated_for_review":
        logger.info("SAS Step 2 (Module Steps Generation) completed. Routing to SAS_REVIEW_AND_REFINE for module steps review.")
        state.subgraph_completion_status = "completed_partial" # Still partial, awaiting review
        # Reset task_list_accepted as we are entering a new review phase for different content
        # However, module_steps_accepted will be a new flag for this phase.
        # For clarity, let's ensure we don't mix up acceptance flags.
        # The review_and_refine_node will handle its own logic based on the incoming dialog_state.
        return SAS_REVIEW_AND_REFINE
    elif state.dialog_state == "sas_step2_completed": # Keep old state for now as a fallback during transition, but should be deprecated.
        logger.warning(f"DEPRECATED ROUTE: SAS Step 2 reached 'sas_step2_completed'. Consider transitioning fully to 'sas_step2_module_steps_generated_for_review'. Routing to SAS_PARAMETER_MAPPING for now.")
        state.subgraph_completion_status = "completed_partial"
        return SAS_PARAMETER_MAPPING # This path should ideally be removed once review cycle for step 2 is robust.
    else:
        logger.warning(f"Unexpected state after SAS Step 2 (Module Steps Generation): {state.dialog_state}. Routing to END as error.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected state ('{state.dialog_state}') after SAS Step 2 (Module Steps Generation)."
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
        state.subgraph_completion_status = "error"
        return END
    elif state.dialog_state == "sas_step3_completed":
        logger.info("SAS Step 3 (Parameter Mapping) completed successfully. All SAS steps complete.")
        state.subgraph_completion_status = "completed_success"
        return END
    else:
        logger.warning(f"Unexpected state after SAS Step 3: {state.dialog_state}. Routing to END.")
        state.subgraph_completion_status = "error"
        state.error_message = f"Unexpected state ({state.dialog_state}) after SAS Step 3."
        if not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        return END

# New routing function after INITIALIZE_STATE
def route_after_initialize_state(state: RobotFlowAgentState) -> str:
    logger.info(
        f"--- Routing after Initialize State. "
        f"Dialog state: {state.dialog_state}, "
        f"Subgraph status: {state.subgraph_completion_status}, "
        f"User input available: {bool(state.user_input)}, "
        f"Clarification question: {state.clarification_question}, "
        f"Task list accepted: {state.task_list_accepted}, "
        f"Generated tasks exist: {bool(state.sas_step1_generated_tasks)}"
    )

    # If dialog_state is "sas_awaiting_task_list_review", it means the graph previously exited
    # from review_and_refine_node to get user feedback. Now that the graph is re-entered,
    # (and user's feedback should be in state.user_input, preserved by initialize_state_node),
    # we should go directly to SAS_REVIEW_AND_REFINE_TASK_LIST to process that feedback.
    if state.dialog_state == "sas_awaiting_task_list_review":
        logger.info("Dialog state is 'sas_awaiting_task_list_review'. Routing to SAS_REVIEW_AND_REFINE.")
        return SAS_REVIEW_AND_REFINE
    else:
        # For all other cases:
        # - Initial run (dialog_state will be 'initial' or None, then set to 'initial' by initialize_state_node)
        # - After an error that routes back to start for a fresh attempt
        # - If the flow logic somehow leads back to the start without being in a review cycle
        logger.info(f"Dialog state is '{state.dialog_state}'. Routing to SAS_USER_INPUT_TO_TASK_LIST for new task generation.")
        return SAS_USER_INPUT_TO_TASK_LIST

# create_robot_flow_graph function (original was L344, this is a rewrite for the new flow)
def create_robot_flow_graph(
    llm: BaseChatModel,
) -> Callable[[Dict[str, Any]], Any]: 
    
    workflow = StateGraph(RobotFlowAgentState)

    # Node Binding (using functools.partial for llm where needed)
    workflow.add_node(INITIALIZE_STATE, initialize_state_node)
    workflow.add_node(SAS_USER_INPUT_TO_TASK_LIST, functools.partial(user_input_to_task_list_node, llm=llm))
    workflow.add_node(SAS_REVIEW_AND_REFINE, functools.partial(review_and_refine_node, llm=llm))
    workflow.add_node(SAS_PROCESS_TO_MODULE_STEPS, functools.partial(process_description_to_module_steps_node, llm=llm))
    workflow.add_node(SAS_PARAMETER_MAPPING, parameter_mapping_node)

    # --- Add the GENERATE_INDIVIDUAL_XMLS node ---
    workflow.add_node(GENERATE_INDIVIDUAL_XMLS, functools.partial(generate_individual_xmls_node, llm=llm))

    # --- Original Nodes (Commented out for SAS refactoring) ---
    # workflow.add_node(CORE_INTERACTION_NODE, functools.partial(preprocess_and_enrich_input_node, llm=llm))
    # workflow.add_node(UNDERSTAND_INPUT, functools.partial(understand_input_node, llm=llm))
    # workflow.add_node(GENERATE_RELATION_XML, generate_relation_xml_node_py) # generate_relation_xml_node_py is python only
    # workflow.add_node(GENERATE_FINAL_XML, functools.partial(generate_final_flow_xml_node, llm=llm))
    # workflow.add_node(ERROR_HANDLER, error_handler_node) # Optional: if a separate error logging node is desired.

    # --- Define Graph Edges ---
    workflow.set_entry_point(INITIALIZE_STATE)
    # New flow for SAS refactoring: INITIALIZE_STATE -> SAS_USER_INPUT_TO_TASK_LIST -> SAS_PROCESS_TO_MODULE_STEPS -> SAS_PARAMETER_MAPPING -> END
    workflow.add_conditional_edges(
        INITIALIZE_STATE,
        route_after_initialize_state,
        {
            SAS_USER_INPUT_TO_TASK_LIST: SAS_USER_INPUT_TO_TASK_LIST,
            SAS_REVIEW_AND_REFINE: SAS_REVIEW_AND_REFINE,
        }
    )

    workflow.add_conditional_edges(
        SAS_USER_INPUT_TO_TASK_LIST,
        route_after_sas_step1,
        {
            SAS_REVIEW_AND_REFINE: SAS_REVIEW_AND_REFINE,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_REVIEW_AND_REFINE,
        route_after_sas_review_and_refine,
        {
            SAS_PROCESS_TO_MODULE_STEPS: SAS_PROCESS_TO_MODULE_STEPS,
            SAS_USER_INPUT_TO_TASK_LIST: SAS_USER_INPUT_TO_TASK_LIST,
            GENERATE_INDIVIDUAL_XMLS: GENERATE_INDIVIDUAL_XMLS, # Added new route from review
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_PROCESS_TO_MODULE_STEPS,
        route_after_sas_step2,
        {
            SAS_PARAMETER_MAPPING: SAS_PARAMETER_MAPPING,
            SAS_REVIEW_AND_REFINE: SAS_REVIEW_AND_REFINE,
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

    # Add edge from GENERATE_INDIVIDUAL_XMLS
    workflow.add_conditional_edges(
        GENERATE_INDIVIDUAL_XMLS,
        route_after_generate_individual_xmls,
        {
            SAS_PARAMETER_MAPPING: SAS_PARAMETER_MAPPING,
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
        
        node_name = "Unknown Chain"
        if serialized: # Added check for None
            node_name = serialized.get("name", "Unknown Chain")
        
        self.run_map[run_id] = {"id": run_id, "name": node_name, "inputs": inputs}


    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], *, run_id, parent_run_id: Optional[str] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        if parent_run_id is None and self.root_run_id is None : # This is a root run (if an LLM is a root)
             self.root_run_id = run_id
        
        node_name = prompts[0][:30] if prompts else "Unknown LLM Call"
        if serialized: # Added check for None
            node_name = serialized.get("name", node_name) # Use prompt-derived name as fallback
            
        self.run_map[run_id] = {"id": run_id, "name": node_name, "inputs": {"prompts": prompts}}


    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, *, run_id, parent_run_id: Optional[str] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        if parent_run_id is None and self.root_run_id is None:
            self.root_run_id = run_id
            
        node_name = "Unknown Tool"
        if serialized: # Added check for None
            node_name = serialized.get("name", "Unknown Tool")
            
        self.run_map[run_id] = {"id": run_id, "name": node_name, "inputs": {"input_str": input_str}}


async def main_test_run():
    # from langchain_openai import ChatOpenAI # Commented out OpenAI import
    import json
    import os # Ensure os is imported for getenv
    from pathlib import Path # Ensure Path is imported
    from datetime import datetime # Ensure datetime is imported

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

    # Define the base directory for test runs
    base_dir_for_runs_str = "backend/tests/llm_sas_test"
    base_dir_for_runs = Path(base_dir_for_runs_str)
    
    # Create a unique sub-directory for this specific run using a timestamp
    current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    current_run_specific_dir_name = f"run_{current_timestamp}"
    current_run_output_dir = base_dir_for_runs / current_run_specific_dir_name

    try:
        current_run_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Successfully created run-specific output directory for this test: {current_run_output_dir}")
    except Exception as e:
        logger.error(f"Failed to create run-specific output directory {current_run_output_dir}: {e}. Check permissions.", exc_info=True)
        # Fallback to a temporary directory or handle error as appropriate
        # For this example, we'll set it to a default that might exist or fail later in a more visible way.
        current_run_output_dir = Path("/tmp/sas_test_fallback_output") 
        current_run_output_dir.mkdir(parents=True, exist_ok=True) # Try to make a fallback
        logger.warning(f"Using fallback output directory: {current_run_output_dir}")

    initial_input_state = {
        "messages": [], 
        "user_input":  """この自動化プロセスは、ベアリング（BRG）、ベアリングハウジング（BH）、およびパレット（PLT）が関与する組み立ておよび取り扱いタスクを共同で完了することを目的としています。
ロボットはまず、初期位置からベアリング（BRG）とベアリングハウジング（BH）を同時に取得します。
このとき、ベアリングとパレット（PLT）で共用するクランプと、ベアリングハウジングと組み立て後の部品で共用するクランプをそれぞれ使用します。
その後、ロボットはまずベアリングハウジング（BH）を右側のマシニングセンター（RMC）に配置します。
続いて、そのベアリングハウジング（BH）にベアリング（BRG）をはめ込む形で配置し、圧入組み立て操作を行います。
組み立て後、ロボットはRMCから組み立てられた部品を取り出し、左側のマシニングセンター（LMC）に転送して一時保管します。
次に、ロボットはベアリングと共用するクランプを用いて空のパレットを取得し、このパレットをコンベア（CNV）の指定されたステーションに配置します。
最後に、ロボットはLMCから以前に保管されていた組み立て済み部品を取得し、コンベア上のパレットに正確に配置して、サイクル全体を完了します。""",
        "config": {
            "OUTPUT_DIR_PATH": str(current_run_output_dir), # Pass the path to the unique run-specific directory
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

    logger.info("--- Starting Interactive Robot Flow Test ---")
    
    # Use a copy of the initial state for the first run
    current_state = initial_input_state.copy()
    # Ensure 'messages' is part of the state if graph expects it
    if "messages" not in current_state or current_state["messages"] is None:
        current_state["messages"] = []

    loop_count = 0
    max_loops = 20 # Safety break for very long unintended loops

    while loop_count < max_loops:
        loop_count += 1
        logger.info(f"--- Interaction Loop: {loop_count} ---")

        # Invoke the graph with the current state
        # The first invocation will use the initial_user_input from initial_input_state
        # Subsequent invocations will use user_input collected in the loop
        returned_state = await robot_flow_app.ainvoke(current_state, config=graph_config)
        
        logger.info(f"\nState after invocation: {json.dumps(returned_state, indent=2, ensure_ascii=False)}")

        # Update current_state with the returned state for the next iteration
        current_state = returned_state.copy() # Important to copy

        # Check for clarification question
        clarification_question = current_state.get("clarification_question")
        dialog_state = current_state.get("dialog_state")
        subgraph_status = current_state.get("subgraph_completion_status")

        if clarification_question:
            print("\n----------------------------------------------------")
            print(f"AI: {clarification_question}")
            print("----------------------------------------------------")
            try:
                user_response = input("Your response: ")
            except EOFError: # Happens if input stream is closed (e.g. piping from a file)
                logger.warning("EOFError received, exiting loop.")
                break
            current_state["user_input"] = user_response
            # Add user message to history for the graph to see
            current_state["messages"] = (current_state.get("messages") or []) + [HumanMessage(content=user_response)]
        elif subgraph_status == "completed_success":
            logger.info("--- Flow COMPLETED SUCCESSFULLY ---")
            break
        elif subgraph_status == "error":
            logger.error(f"--- Flow FAILED with error: {current_state.get('error_message')} ---")
            break
        elif dialog_state in ["final_xml_generated_success", "sas_step3_completed"]: # other potential success states
            logger.info(f"--- Flow appears to have reached a successful end state ({dialog_state}) ---")
            break
        else:
            logger.info("No clarification question, and not a recognized completion/error state. Ending loop.")
            logger.info(f"Final Dialog State: {dialog_state}, Subgraph Status: {subgraph_status}")
            break # Fallback to prevent infinite loop if state is unclear

    if loop_count >= max_loops:
        logger.warning(f"Reached maximum loop iteration ({max_loops}). Exiting.")

    final_state = current_state # The state after the last interaction
    logger.info(f"\nFinal Accumulated State from Interactive Loop: {json.dumps(final_state, indent=2, ensure_ascii=False)}")

    run_output_directory = final_state.get('run_output_directory')
    if not run_output_directory:
        # Fallback if not in state, though initialize_state_node should set it
        # This fallback logic might not be strictly necessary anymore if current_run_output_dir is robustly set above
        # and passed via config, as initialize_state_node will use it.
        # However, keeping it for safety or if the graph somehow loses run_output_directory from state.
        logger.warning("run_output_directory was not found in final_state. Attempting to use the one created by main_test_run.")
        run_output_directory = str(current_run_output_dir) # Use the one created at the start of main_test_run
        # Ensure it is an absolute path if it wasn't already
        if not Path(run_output_directory).is_absolute():
             run_output_directory = str(Path(run_output_directory).resolve())
        
        # Re-check if this fallback directory exists, though it should have been created.
        if not Path(run_output_directory).exists():
            logger.error(f"Critical: Fallback run_output_directory '{run_output_directory}' does not exist. Metrics cannot be saved.")
            run_output_directory = None # Prevent trying to save metrics to a non-existent dir


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
                "inputs_summary": f"Input type: {type(root_run.inputs)}, Keys: {list(root_run.inputs.keys()) if isinstance(root_run.inputs, dict) else 'N/A'}", # Add a brief summary instead
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
                    logger.info(f"LLM Node found: {node_run.name}, ID: {node_run.id}") # DEBUG LOG
                    logger.info(f"Raw node_run.extra: {node_run.extra}") # DEBUG LOG
                    llm_metrics = {}
                    ttfb_seconds = None
                    
                    if node_run.extra and 'metadata' in node_run.extra and isinstance(node_run.extra['metadata'], dict):
                        logger.info(f"Metadata found: {node_run.extra['metadata']}") # DEBUG LOG
                        ttfb_ms = node_run.extra['metadata'].get('time_to_first_token_ms')
                        logger.info(f"Extracted ttfb_ms: {ttfb_ms}") # DEBUG LOG
                        if ttfb_ms is not None: # Check for None explicitly
                            try:
                                ttfb_seconds = float(ttfb_ms) / 1000.0
                                llm_metrics["time_to_first_token_seconds"] = ttfb_seconds
                                logger.info(f"Calculated ttfb_seconds: {ttfb_seconds}") # DEBUG LOG
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not parse TTFB from metadata (\\'{ttfb_ms}\\') for node {node_run.name}: {e}")
                    else: # DEBUG LOG
                        logger.warning(f"No metadata or metadata not a dict for LLM node {node_run.name}. node_run.extra: {node_run.extra}") # DEBUG LOG
                    
                    completion_tokens = node_run.outputs.get("llm_output", {}).get("token_usage", {}).get("completion_tokens") if node_run.outputs else None
                    prompt_tokens = node_run.outputs.get("llm_output", {}).get("token_usage", {}).get("prompt_tokens") if node_run.outputs else None
                    # total_tokens = node_run.outputs.get("llm_output", {}).get("token_usage", {}).get("total_tokens") if node_run.outputs else None
                    # Use tokens from run object directly if available, often more reliable
                    if hasattr(node_run, 'completion_tokens') and node_run.completion_tokens is not None:
                         completion_tokens = node_run.completion_tokens
                    if hasattr(node_run, 'prompt_tokens') and node_run.prompt_tokens is not None:
                         prompt_tokens = node_run.prompt_tokens
                    
                    # Make sure we only add integers or serializable values
                    if isinstance(completion_tokens, int): llm_metrics["completion_tokens"] = completion_tokens
                    if isinstance(prompt_tokens, int): llm_metrics["prompt_tokens"] = prompt_tokens
                    if isinstance(completion_tokens, int) and isinstance(prompt_tokens, int):
                        llm_metrics["total_tokens"] = completion_tokens + prompt_tokens
                    
                    if isinstance(completion_tokens, int) and node_run.start_time and node_run.end_time:
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