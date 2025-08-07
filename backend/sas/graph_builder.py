# ---- START PATCH FOR DIRECT EXECUTION ----
if __name__ == '__main__' and (__package__ is None or __package__ == ''):
    import sys
    from pathlib import Path
    # Calculate the path to the project root ('/workspace')
    # This file is backend/sas/graph_builder.py
    # Relative path from this file to /workspace is ../../../
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Set __package__ to the expected package name for relative imports to work
    # The package is 'backend.sas'
    __package__ = "backend.sas"
# ---- END PATCH FOR DIRECT EXECUTION ----

import logging
import functools
from typing import Dict, Any, Optional, Callable, List, Tuple
import asyncio
import os
import xml.etree.ElementTree as ET
import copy
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
import json
import time
from langsmith.utils import LangSmithNotFoundError

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import Client as LangSmithClient
from langsmith.utils import tracing_is_enabled as langsmith_tracing_is_enabled
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver # ADDED THIS IMPORT

from .state import RobotFlowAgentState, GeneratedXmlFile
from .nodes import (
    parameter_mapping_node,
    user_input_to_task_list_node,
    review_and_refine_node,
    generate_individual_xmls_node,
    task_list_to_module_steps_node
)
from .xml_tools import WriteXmlFileTool
from ..langgraphchat.tools.file_share_tool import upload_file
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
SAS_TASK_LIST_TO_MODULE_STEPS = "sas_task_list_to_module_steps"
SAS_PARAMETER_MAPPING = "sas_parameter_mapping"
SAS_REVIEW_AND_REFINE = "sas_review_and_refine"

# New node names for XML processing
SAS_MERGE_XMLS = "sas_merge_xmls"
SAS_CONCATENATE_XMLS = "sas_concatenate_xmls"

# Constants from merge_xml.py (adapt as needed)
MERGE_XML_BLOCKLY_XMLNS = "https://developers.google.com/blockly/xml"
CONCAT_XML_BLOCKLY_XMLNS = "https://developers.google.com/blockly/xml" # Added this line

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
    
    # 新增：获取用户信息和流程图信息，生成动态输出路径
    try:
        # 尝试从配置中获取用户信息和流程图信息
        current_username = merged_config.get("CURRENT_USERNAME")
        current_flow_id = merged_config.get("CURRENT_FLOW_ID")
        
        logger.info(f"从配置中获取用户信息: username={current_username}, flow_id={current_flow_id}")
        
        # 如果配置中没有，尝试从context中获取流程图ID
        if not current_flow_id:
            try:
                from backend.langgraphchat.context import current_flow_id_var
                current_flow_id = current_flow_id_var.get()
                logger.info(f"从上下文中获取流程图ID: {current_flow_id}")
            except Exception as context_e:
                logger.warning(f"从上下文获取流程图ID失败: {context_e}")
        
        # 强制生成动态输出路径，不允许使用examplerun默认路径
        # 为缺失的信息提供默认值
        safe_username = current_username or "unknown_user"
        safe_flow_id = current_flow_id or f"flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        from backend.sas.prompt_loader import get_dynamic_output_path
        dynamic_output_path = get_dynamic_output_path(safe_flow_id, safe_username)
        logger.info(f"强制生成动态输出路径: {dynamic_output_path} (username: {safe_username}, flow_id: {safe_flow_id})")
        
        # 更新配置中的输出路径
        merged_config["OUTPUT_DIR_PATH"] = dynamic_output_path
        state.config = merged_config
        
        # 设置流程图和用户信息到状态中（用于后续节点使用）
        state.config["CURRENT_FLOW_ID"] = safe_flow_id
        state.config["CURRENT_USERNAME"] = safe_username
        
        logger.info(f"已强制设置动态输出路径和用户信息到配置中，禁止使用examplerun路径")
            
    except Exception as e:
        logger.error(f"设置动态输出路径失败，但将强制重试: {e}")
        # 即使异常也要强制使用动态路径，不允许回退到examplerun
        try:
            fallback_username = "fallback_user"
            fallback_flow_id = f"fallback_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            from backend.sas.prompt_loader import get_dynamic_output_path
            fallback_dynamic_path = get_dynamic_output_path(fallback_flow_id, fallback_username)
            merged_config["OUTPUT_DIR_PATH"] = fallback_dynamic_path
            state.config = merged_config
            
            logger.warning(f"强制使用回退动态路径: {fallback_dynamic_path}")
        except Exception as fallback_e:
            logger.error(f"回退动态路径也失败: {fallback_e}，但仍禁止使用examplerun路径")
    
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
        # 强制使用动态路径，不允许回退到默认测试路径
        logger.warning("run_output_directory未设置，强制生成最终回退动态路径")
        final_fallback_username = "emergency_user"
        final_fallback_flow_id = f"emergency_flow_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        try:
            from backend.sas.prompt_loader import get_dynamic_output_path
            final_dynamic_path = get_dynamic_output_path(final_fallback_flow_id, final_fallback_username)
            run_output_dir = Path(final_dynamic_path)
            logger.info(f"使用最终回退动态路径: {run_output_dir}")
        except Exception as final_e:
            logger.error(f"最终回退动态路径生成失败: {final_e}，使用基础动态路径结构")
            # 如果连动态路径生成都失败，至少确保不使用examplerun
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            run_output_dir = Path(f"/workspace/database/flow_database/result/emergency_user/emergency_flow_{timestamp}")
        
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

def _generate_relation_xml_content_from_steps_py_deprecated(
    parsed_steps: Optional[List[Dict[str, Any]]],
    generated_xmls: Optional[List[GeneratedXmlFile]],
    config: Dict[str, Any] # For logging and potential future use
) -> str:
    """
    DEPRECATED: This function was part of the old workflow that generated a separate relation.xml.
    The new workflow merges XMLs directly.
    """
    logger.warning("Executing DEPRECATED function: _generate_relation_xml_content_from_steps_py_deprecated")
    logger.info("--- Generating Relation XML (Python Logic) ---")

    if not parsed_steps or not generated_xmls:
        logger.warning("Parsed steps or generated XMLs are empty. Generating empty relation XML.")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>'

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
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>'

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
        final_xml_string = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'
        logger.info(f"Successfully generated relation.xml content (Python Logic). Preview: {final_xml_string[:250]}...")
        return final_xml_string
    except Exception as e:
        logger.error(f"Error serializing relation XML (Python Logic): {e}", exc_info=True)
        # Fallback to empty XML on serialization error
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>'

def generate_relation_xml_node_py_deprecated(state: RobotFlowAgentState) -> Dict[str, Any]:
    """
    DEPRECATED: This node was part of the old workflow. The new workflow merges XMLs directly.
    """
    logger.warning("Executing DEPRECATED function: generate_relation_xml_node_py_deprecated")
    logger.info("--- Running Step 3: Generate Node Relation XML (Python Implementation) ---")
    state.current_step_description = "Generating node relation XML file (Python)"
    state.is_error = False 

    config = state.config
    parsed_steps = state.parsed_flow_steps
    generated_node_xmls_list = state.generated_node_xmls if state.generated_node_xmls is not None else []

    if not parsed_steps:
        logger.warning("Parsed flow steps are missing for relation XML generation. Generating empty relation.xml.")
        state.relation_xml_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>'
        # Attempt to save this empty relation.xml
    else:
        try:
            state.relation_xml_content = _generate_relation_xml_content_from_steps_py_deprecated(
                parsed_steps,
                generated_node_xmls_list,
                config
            )
        except Exception as e:
            logger.error(f"Internal error: Unexpected error while generating relation XML: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Internal error: Unexpected error while generating relation XML: {e}"
            state.relation_xml_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="{BLOCKLY_NS}"></xml>' # Fallback
            state.completion_status = "error"

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
        state.completion_status = "error"
        # relation_xml_content remains in state for potential debugging

    if not state.is_error:
        state.dialog_state = "generating_xml_final"
        state.completion_status = None 
    else: # if an error occurred either during generation or saving
        state.dialog_state = "error" # Or route back to core for retry/clarification
        if state.error_message and not any( state.error_message in (msg.content if hasattr(msg, 'content') else '') for msg in (state.messages or []) if isinstance(msg, AIMessage)):
             state.messages = (state.messages or []) + [AIMessage(content=f"Error generating relation XML: {state.error_message}")]

    return state.model_dump(exclude_none=True)

async def generate_final_flow_xml_node_deprecated(state: RobotFlowAgentState, llm: Optional[BaseChatModel] = None) -> Dict[str, Any]:
    """
    DEPRECATED: This node was part of the old workflow. The new workflow uses a simplified merge node.
    """
    logger.warning("Executing DEPRECATED function: generate_final_flow_xml_node_deprecated")
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
        state.completion_status = "error"
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
                    state.completion_status = "error"
                    return state.model_dump(exclude_none=True)
            elif gf.block_id:
                logger.warning(f"Skipping block_id {gf.block_id} for merge due to status '{gf.status}' or no content.")

    try:
        relation_structure_root = ET.fromstring(relation_xml_str)
    except ET.ParseError as e:
        logger.error(f"Failed to parse relation.xml: {e}. XML: {relation_xml_str[:200]}", exc_info=True)
        state.is_error = True
        state.error_message = f"Internal error: Failed to parse relation XML: {e}"
        state.completion_status = "error"
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
            if statement_name:
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
        state.completion_status = "error"
        return state.model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Unexpected error during final XML construction: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Internal error: Unexpected error while constructing final XML: {e}"; 
        state.completion_status = "error"
        return state.model_dump(exclude_none=True)

    ET.register_namespace("", BLOCKLY_NS) # Ensure default namespace for output
    try:
        if hasattr(ET, 'indent'): ET.indent(final_flow_xml_root, space="  ") # Python 3.9+
        merged_xml_content_string = ET.tostring(final_flow_xml_root, encoding='unicode', xml_declaration=False)
        final_xml_string_output = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n{merged_xml_content_string}"
    except Exception as e:
        logger.error(f"Error serializing final merged XML: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Internal error: Error serializing final XML: {e}"; 
        state.completion_status = "error"
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
        state.completion_status = "error"
        # Keep final_flow_xml_content in state even if save fails

    if not state.is_error:
        state.completion_status = "completed_success"
        state.dialog_state = "final_xml_generated_success"
        state.clarification_question = None

    return state.model_dump(exclude_none=True)

# --- BEGIN NEW XML PROCESSING NODES ---

def _get_block_from_file_for_merge(file_path: Path) -> Tuple[Optional[int], Optional[ET.Element]]:
    try:
        tree = ET.parse(file_path)
        root_element = tree.getroot()
        namespaced_block_tag = f"{{{MERGE_XML_BLOCKLY_XMLNS}}}block"
        namespaced_xml_tag = f"{{{MERGE_XML_BLOCKLY_XMLNS}}}xml"
        block_element = None

        if root_element.tag == namespaced_block_tag or root_element.tag == "block":
            block_element = root_element
        elif root_element.tag == namespaced_xml_tag or root_element.tag == "xml":
            block_element = root_element.find(namespaced_block_tag)
            if block_element is None: block_element = root_element.find("block")
            if block_element is None:
                logger.warning(f"MergeXML Helper: Root is '{root_element.tag}' but no block child in {file_path}.")
                return None, None
        else:
            logger.warning(f"MergeXML Helper: Unexpected root tag '{root_element.tag}' in {file_path}.")
            return None, None
        
        block_no_str = block_element.get("data-blockNo")
        if block_no_str is None:
            logger.warning(f"MergeXML Helper: Missing 'data-blockNo' in {file_path}.")
            return None, None
        return int(block_no_str), block_element
    except ET.ParseError as e:
        logger.error(f"MergeXML Helper: Error parsing {file_path}: {e}")
        return None, None
    except ValueError:
        logger.error(f"MergeXML Helper: Invalid 'data-blockNo' in {file_path}.")
        return None, None
    except Exception as e:
        logger.error(f"MergeXML Helper: Unexpected error processing {file_path}: {e}", exc_info=True)
        return None, None

def _process_single_directory_for_merge(input_dir: Path, output_dir_base: Path, task_name_for_file: str) -> Optional[str]:
    logger.info(f"MergeXML Helper: Processing directory: {input_dir.name} for task {task_name_for_file}")
    all_blocks_with_order = []
    xml_files_in_dir = list(input_dir.glob("*.xml"))
    if not xml_files_in_dir:
        logger.info(f"MergeXML Helper: No XML files found in {input_dir.name}.")
        return None

    for xml_file in xml_files_in_dir:
        block_no, block_element = _get_block_from_file_for_merge(xml_file)
        if block_element is not None and block_no is not None:
            all_blocks_with_order.append((block_no, block_element, xml_file.name))
    
    if not all_blocks_with_order:
        logger.info(f"MergeXML Helper: No valid blocks found in {input_dir.name} after parsing.")
        return None
        
    all_blocks_with_order.sort(key=lambda item: item[0])
    sorted_block_elements = [item[1] for item in all_blocks_with_order]

    root_xml_element = ET.Element(f"{{{MERGE_XML_BLOCKLY_XMLNS}}}xml")
    if sorted_block_elements:
        first_block_element = sorted_block_elements[0]
        root_xml_element.append(first_block_element)
        current_parent_for_chaining = first_block_element
        for i in range(1, len(sorted_block_elements)):
            block_to_attach = sorted_block_elements[i]
            parent_type = current_parent_for_chaining.get("type")
            target_statement_name = None
            if parent_type == "procedures_defnoreturn": target_statement_name = "STACK"
            elif parent_type == "loop": target_statement_name = "DO"
            elif parent_type in ["controls_repeat_ext", "controls_whileuntil", "controls_for"]: target_statement_name = "DO"
            elif parent_type == "controls_if": target_statement_name = "DO0"

            namespaced_statement_tag = f"{{{MERGE_XML_BLOCKLY_XMLNS}}}statement"
            namespaced_next_tag = f"{{{MERGE_XML_BLOCKLY_XMLNS}}}next"
            
            if target_statement_name:
                statement_element = current_parent_for_chaining.find(f"./{namespaced_statement_tag}[@name='{target_statement_name}']")
                if statement_element is None:
                    statement_element = ET.SubElement(current_parent_for_chaining, namespaced_statement_tag, {"name": target_statement_name})
                
                last_block_in_statement_chain = None
                # Find first actual block in the statement to append to its <next>
                current_block_in_statement = None
                for child_node_in_stmt in list(statement_element):
                    if child_node_in_stmt.tag == f"{{{MERGE_XML_BLOCKLY_XMLNS}}}block" or child_node_in_stmt.tag == "block":
                        current_block_in_statement = child_node_in_stmt
                        break
                
                if current_block_in_statement is not None:
                    last_block_in_statement_chain = current_block_in_statement
                    while True:
                        next_tag_node = last_block_in_statement_chain.find(namespaced_next_tag)
                        if next_tag_node is None or not len(list(next_tag_node)): break
                        found_block_in_next_tag = False
                        for block_candidate_in_next in list(next_tag_node):
                            if block_candidate_in_next.tag == f"{{{MERGE_XML_BLOCKLY_XMLNS}}}block" or block_candidate_in_next.tag == "block":
                                last_block_in_statement_chain = block_candidate_in_next
                                found_block_in_next_tag = True; break
                        if not found_block_in_next_tag: break
                
                if last_block_in_statement_chain is None: # No blocks yet in this statement, append directly to statement
                    statement_element.append(block_to_attach)
                else: # Append to the <next> of the last block in the statement chain
                    ET.SubElement(last_block_in_statement_chain, namespaced_next_tag).append(block_to_attach)
                current_parent_for_chaining = block_to_attach
            else: # No specific statement target, attach via <next> to the current parent in the main flow
                ET.SubElement(current_parent_for_chaining, namespaced_next_tag).append(block_to_attach)
                current_parent_for_chaining = block_to_attach
    
    output_file_path = output_dir_base / f"{task_name_for_file}_merged.xml"
    try:
        output_dir_base.mkdir(parents=True, exist_ok=True)
        tree = ET.ElementTree(root_xml_element)
        if hasattr(ET, 'indent'): ET.indent(root_xml_element, space="  ")
        tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        logger.info(f"MergeXML Helper: Successfully assembled XML for {input_dir.name} to {output_file_path}")
        return str(output_file_path)
    except Exception as e:
        logger.error(f"MergeXML Helper: Error writing output XML {output_file_path}: {e}", exc_info=True)
        return None

def sas_merge_xml_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    logger.info("--- SAS: Merging Individual Task XMLs (Node) ---")
    state.current_step_description = "Merging individual XMLs for each task flow."
    state.is_error = False
    state.error_message = None
    
    if not state.run_output_directory:
        state.is_error = True; state.error_message = "run_output_directory is not set."; logger.error(state.error_message)
        state.dialog_state = "sas_processing_error"; state.completion_status = "error"
        return state.model_dump(exclude_none=True)

    base_input_dir = Path(state.run_output_directory)
    # Individual XMLs are assumed to be in subdirectories directly under base_input_dir,
    # named by generate_individual_xmls_node (e.g., "00_TaskName", "01_AnotherTask").
    
    # Create timestamped directory to avoid file conflicts
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    merged_output_dir = base_input_dir / f"merged_task_flows_{timestamp}"
    state.merged_task_flows_dir = str(merged_output_dir)  # Save for concatenate step
    
    try:
        merged_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"MergeXML Node: Created timestamped directory: {merged_output_dir}")
    except Exception as e:
        state.is_error = True; state.error_message = f"Failed to create dir for merged flows: {e}"; logger.error(state.error_message, exc_info=True)
        state.dialog_state = "sas_processing_error"; state.completion_status = "error"
        return state.model_dump(exclude_none=True)

    merged_file_paths: List[str] = []
    # Filter for directories that seem to be task outputs, avoiding our own output dirs
    subdirs_to_process = []
    if state.generated_node_xmls: # If individual XMLs were generated, their parent dirs were noted
        # This is more robust if generate_individual_xmls_node saves files in task-specific subdirs.
        # We need to derive the subdirectories from state.generated_node_xmls file paths
        processed_parent_dirs = set()
        for xml_info in state.generated_node_xmls:
            if xml_info.file_path:
                parent_dir = Path(xml_info.file_path).parent
                if (parent_dir not in processed_parent_dirs and 
                    not parent_dir.name.startswith("merged_task_flows_") and 
                    not parent_dir.name.startswith("concatenated_flow_output")):
                    subdirs_to_process.append(parent_dir)
                    processed_parent_dirs.add(parent_dir)
    else: # Fallback if generated_node_xmls is not populated as expected, try to scan run_output_directory
        logger.warning("MergeXML Node: state.generated_node_xmls is empty or not populated. Attempting to scan run_output_directory for task subdirectories.")
        subdirs_to_process = [d for d in base_input_dir.iterdir() if d.is_dir() and 
                             not d.name.startswith("merged_task_flows_") and 
                             not d.name.startswith("concatenated_flow_output")]

    if not subdirs_to_process:
        logger.warning(f"MergeXML Node: No task-specific subdirectories found in {base_input_dir} to merge based on scan or generated_node_xmls state.")
        state.merged_xml_file_paths = []
        state.dialog_state = "sas_merging_completed_no_files"
        return state.model_dump(exclude_none=True)

    ET.register_namespace("", MERGE_XML_BLOCKLY_XMLNS)
    for task_dir in sorted(subdirs_to_process):
        # Use task_dir.name as a base for the output filename. It should be like "00_TaskName".
        # The _process_single_directory_for_merge expects a task_name_for_file which becomes part of output.
        merged_file_path = _process_single_directory_for_merge(task_dir, merged_output_dir, task_dir.name)
        if merged_file_path:
            merged_file_paths.append(merged_file_path)
        else:
            logger.warning(f"MergeXML Node: Failed to process/merge XMLs for task directory: {task_dir.name}")
            # Decide if a single failure here should be a graph-level error
            # state.is_error = True; state.error_message = f"Failed to merge for {task_dir.name}" # Example

    state.merged_xml_file_paths = merged_file_paths
    if not merged_file_paths and subdirs_to_process: # If there were dirs but nothing was merged
        state.is_error = True; state.error_message = "No XML files successfully merged."; logger.error(state.error_message)
        state.dialog_state = "sas_processing_error"; state.completion_status = "error"
    elif not subdirs_to_process:
         state.dialog_state = "sas_merging_completed_no_files"
    else:
        logger.info(f"MergeXML Node: Successfully merged XMLs into {len(merged_file_paths)} file(s) in {merged_output_dir}.")
        state.dialog_state = "sas_merging_completed"
    
    return state.model_dump(exclude_none=True)

async def sas_concatenate_xml_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    """
    Concatenates merged task XML files into a single final robot program XML file.
    This step creates the final executable XML that contains all tasks.
    """
    logger.info("Executing sas_concatenate_xml_node")
    logger.info("--- SAS: Concatenating Merged Task XMLs (Node) ---")
    state.current_step_description = "Concatenating merged task XMLs into a final flow."
    state.is_error = False
    state.error_message = None

    if not state.run_output_directory:
        state.is_error = True; state.error_message = "run_output_directory not set."; logger.error(state.error_message)
        state.dialog_state = "sas_processing_error"; state.completion_status = "error"
        return state.model_dump(exclude_none=True)

    # Use the timestamped directory created by sas_merge_xml_node
    if state.merged_task_flows_dir:
        input_dir_for_concat = Path(state.merged_task_flows_dir)
        logger.info(f"ConcatenateXML Node: Using timestamped merge directory: {input_dir_for_concat}")
    else:
        # Fallback to scanning for the most recent merged_task_flows directory
        base_dir = Path(state.run_output_directory)
        merge_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("merged_task_flows_")]
        if merge_dirs:
            input_dir_for_concat = max(merge_dirs, key=lambda d: d.stat().st_mtime)  # Most recent
            logger.info(f"ConcatenateXML Node: Found most recent merge directory: {input_dir_for_concat}")
        else:
            input_dir_for_concat = base_dir / "merged_task_flows"  # Original fallback
            logger.warning(f"ConcatenateXML Node: No timestamped merge directories found, using fallback: {input_dir_for_concat}")
    
    # Create timestamped output directory for concatenated results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir_for_concat = Path(state.run_output_directory) / f"concatenated_flow_output_{timestamp}"
    state.concatenated_flow_output_dir = str(output_dir_for_concat)  # Save for future reference
    final_output_file = output_dir_for_concat / "final_concatenated_sas_flow.xml"

    try:
        output_dir_for_concat.mkdir(parents=True, exist_ok=True)
        logger.info(f"ConcatenateXML Node: Created timestamped output directory: {output_dir_for_concat}")
    except Exception as e:
        state.is_error = True; state.error_message = f"Failed to create dir for concatenated flow: {e}"; logger.error(state.error_message, exc_info=True)
        state.dialog_state = "sas_processing_error"; state.completion_status = "error"
        return state.model_dump(exclude_none=True)

    merged_files_to_concat_paths = state.merged_xml_file_paths
    if not merged_files_to_concat_paths:
        logger.warning(f"ConcatenateXML Node: No merged XML file paths found in state.merged_xml_file_paths (input dir was {input_dir_for_concat}). Generating empty final XML.")
        # 修复：分开字符串连接避免\n字符残留
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
        xml_content = f'<xml xmlns="{CONCAT_XML_BLOCKLY_XMLNS}"></xml>'
        state.final_flow_xml_content = xml_declaration + '\n' + xml_content
        state.final_flow_xml_path = str(final_output_file)
        try:
            with open(state.final_flow_xml_path, "w", encoding="utf-8") as f: f.write(state.final_flow_xml_content)
            logger.info(f"ConcatenateXML Node: Empty final XML saved to {state.final_flow_xml_path}")
        except Exception as e_save:
            state.is_error = True; state.error_message = f"Failed to save empty final XML: {e_save}"; logger.error(state.error_message, exc_info=True)
            state.dialog_state = "sas_processing_error"; state.completion_status = "error"
            return state.model_dump(exclude_none=True)
        
        # 🔧 空XML情况下也延迟1秒，给前端SSE连接准备时间
        logger.info("🔧 空XML生成完成，延迟1秒发送最终状态事件，确保前端SSE准备就绪...")
        await asyncio.sleep(1.0)
        
        state.dialog_state = "final_xml_generated_success"
        state.completion_status = "completed_success"
        logger.info("🎉 最终状态已设置：final_xml_generated_success (空XML情况)")
        return state.model_dump(exclude_none=True)

    ET.register_namespace("", CONCAT_XML_BLOCKLY_XMLNS)
    concatenated_root = ET.Element(f"{{{CONCAT_XML_BLOCKLY_XMLNS}}}xml")
    for xml_file_path_str in sorted(merged_files_to_concat_paths): # Sort by path for deterministic order
        xml_file = Path(xml_file_path_str)
        try:
            if not xml_file.exists():
                logger.warning(f"ConcatenateXML Node: File {xml_file} listed in merged_xml_file_paths does not exist. Skipping.")
                continue
            tree = ET.parse(xml_file)
            root_element = tree.getroot()
            if root_element.tag == f"{{{CONCAT_XML_BLOCKLY_XMLNS}}}xml" or root_element.tag == "xml":
                for child in root_element:
                    concatenated_root.append(child)
            elif root_element.tag == f"{{{CONCAT_XML_BLOCKLY_XMLNS}}}block" or root_element.tag == "block":
                concatenated_root.append(root_element)
            else:
                logger.warning(f"ConcatenateXML Node: File {xml_file} has unexpected root '{root_element.tag}'. Skipping.")
        except ET.ParseError as e:
            logger.error(f"ConcatenateXML Node: Error parsing {xml_file}: {e}")
            state.is_error = True; state.error_message = (state.error_message or "") + f" Parse error in {xml_file.name};"
        except Exception as e:
            logger.error(f"ConcatenateXML: Unexpected error with {xml_file}: {e}")
            state.is_error = True; state.error_message = (state.error_message or "") + f" Unexpected error with {xml_file.name};"

    if state.is_error:
        state.error_message = "Errors occurred during XML concatenation: " + (state.error_message or "Unknown concatenation error.")
        state.dialog_state = "error"; state.completion_status = "error"
        return state.model_dump(exclude_none=True)

    try:
        if hasattr(ET, 'indent'): ET.indent(concatenated_root)
        final_xml_str = ET.tostring(concatenated_root, encoding="unicode", xml_declaration=False)
        # 修复：分开字符串连接避免\n字符残留
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
        final_xml_str_with_decl = xml_declaration + '\n' + final_xml_str
        with open(final_output_file, "w", encoding="utf-8") as f: f.write(final_xml_str_with_decl)
        state.final_flow_xml_path = str(final_output_file)
        state.final_flow_xml_content = final_xml_str_with_decl
        logger.info(f"ConcatenateXML: Successfully concatenated XML files to {final_output_file}")
        
        # 🔧 XML生成完成延迟1秒，给前端SSE连接准备时间
        logger.info("🔧 XML生成完成，延迟1秒发送最终状态事件，确保前端SSE准备就绪...")
        await asyncio.sleep(1.0)
        
        state.dialog_state = "final_xml_generated_success"
        state.completion_status = "completed_success"
        logger.info("🎉 最终状态已设置：final_xml_generated_success")
    except Exception as e:
        logger.error(f"ConcatenateXML: Error writing final concatenated XML to {final_output_file}: {e}")
        state.is_error = True
        state.error_message = f"Error writing final concatenated XML: {e}"
        state.dialog_state = "error"; state.completion_status = "error"
        
    return state.model_dump(exclude_none=True)

# --- END NEW XML PROCESSING NODES ---

# New routing function after SAS_MERGE_XMLS
def route_after_sas_merge_xmls(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Merge XMLs (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "sas_processing_error":
        logger.warning(f"Error during SAS Merge XMLs or error state triggered. Error: {state.error_message}")
        if state.error_message and not any(state.error_message in (msg.content if hasattr(msg, 'content') else '') for msg in (state.messages or []) if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"Error merging XMLs: {state.error_message}")]
        state.completion_status = "error"
        return END
    elif state.dialog_state == "sas_merging_completed" or state.dialog_state == "sas_merging_completed_no_files":
        logger.info(f"SAS Merge XMLs completed (state: {state.dialog_state}). Routing to SAS_CONCATENATE_XMLS.")
        state.completion_status = "processing" # Indicate processing continues
        # Ensure dialog state is neutral or indicative for the next step if needed
        state.dialog_state = "sas_merging_done_ready_for_concat" 
        return SAS_CONCATENATE_XMLS
    else:
        logger.error(f"Unexpected dialog state after SAS Merge XMLs: {state.dialog_state}. Routing to END as error.")
        state.error_message = state.error_message or f"Unexpected state ('{state.dialog_state}') after XML merging."
        if state.error_message and not any(state.error_message in (msg.content if hasattr(msg, 'content') else '') for msg in (state.messages or []) if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        state.completion_status = "error"
        return END

print("DEBUG: Defining route_after_sas_concatenate_xmls") # ADDED DEBUG PRINT
# New routing function after SAS_CONCATENATE_XMLS
def route_after_sas_concatenate_xmls(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Concatenate XMLs (is_error: {state.is_error}, dialog_state: {state.dialog_state}, completion_status: {state.completion_status}) ---")
    if state.is_error or state.completion_status == "error":
        logger.warning(f"Error during SAS Concatenate XMLs or error state encountered. Error: {state.error_message}")
        if state.error_message and not any(state.error_message in (msg.content if hasattr(msg, 'content') else '') for msg in (state.messages or []) if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=f"Error concatenating XMLs: {state.error_message}")]
        return END
    elif state.completion_status == "completed_success" and state.dialog_state == "final_xml_generated_success":
        logger.info("SAS Concatenate XMLs completed successfully. Final XML generated. Routing to END.")
        return END
    else:
        logger.error(f"Unexpected state after SAS Concatenate XMLs: dialog_state='{state.dialog_state}', completion_status='{state.completion_status}'. Routing to END as error.")
        state.error_message = state.error_message or f"Unexpected state ('{state.dialog_state}', status: '{state.completion_status}') after XML concatenation."
        if state.error_message and not any(state.error_message in (msg.content if hasattr(msg, 'content') else '') for msg in (state.messages or []) if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        state.completion_status = "error"
        return END

# --- Conditional Edge Functions ---
def route_after_initialize_state(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after Initialize State (dialog_state: {state.dialog_state}) ---")
    if state.dialog_state in ["sas_awaiting_task_list_review", "sas_awaiting_module_steps_review"]:
        logger.info(f"Resuming at review step: {state.dialog_state}. Routing to SAS_REVIEW_AND_REFINE.")
        return SAS_REVIEW_AND_REFINE
    else:
        logger.info(f"Starting new flow (dialog_state: '{state.dialog_state}'). Routing to SAS_USER_INPUT_TO_TASK_LIST.")
        return SAS_USER_INPUT_TO_TASK_LIST

def route_after_sas_step1(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 1: Task List Generation (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "generation_failed":
        logger.warning(f"Error during Task List Generation. Error: {state.error_message}")
        state.completion_status = "error"
        return END 
    else:
        logger.info("Task List Generation successful. Routing to SAS_REVIEW_AND_REFINE.")
        return SAS_REVIEW_AND_REFINE

# New routing function for SAS Review and Refine Task List
def route_after_sas_review_and_refine(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Review/Refine Node ---")
    logger.info(f"    [ROUTE_REVIEW_REFINE_ENTRY] dialog_state: '{state.dialog_state}'")

    if state.is_error: 
        logger.warning(f"Error flag is set. Error: {state.error_message}")
        state.completion_status = "error"
        return END

    # The review_and_refine_node has already updated the dialog_state.
    # We just need to route based on the result.
    dialog_state = state.dialog_state

    if dialog_state == "task_list_to_module_steps":
        logger.info("Routing to SAS_TASK_LIST_TO_MODULE_STEPS.")
        state.completion_status = "processing"
        return SAS_TASK_LIST_TO_MODULE_STEPS
    
    if dialog_state == "sas_generating_individual_xmls":
        logger.info("Routing to GENERATE_INDIVIDUAL_XMLS.")
        state.completion_status = "processing"
        return GENERATE_INDIVIDUAL_XMLS

    if dialog_state == "user_input_to_task_list":
        logger.info("Routing back to SAS_USER_INPUT_TO_TASK_LIST for re-generation.")
        state.completion_status = "processing"
        return SAS_USER_INPUT_TO_TASK_LIST

    if dialog_state in ["sas_awaiting_task_list_review", "sas_awaiting_module_steps_review"]:
        logger.info(f"Awaiting user feedback on: {dialog_state}. Ending graph run for clarification.")
        state.completion_status = "needs_clarification"
        return END

    # Fallback for any unexpected state
    logger.error(f"Unexpected state after Review/Refine: '{dialog_state}'. Defaulting to END.")
    state.completion_status = "error"
    if not state.error_message:
         state.messages = (state.messages or []) + [AIMessage(content="An unexpected error occurred during the review process.")]
    return END

# New routing function for SAS Step 2
def route_after_sas_step2(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 2: Module Steps Generation (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "generation_failed":
        logger.warning(f"Error during Module Steps Generation. Error: {state.error_message}")
        state.completion_status = "error"
        return END
    else:
        logger.info("Module Steps Generation successful. Routing to SAS_REVIEW_AND_REFINE.")
        return SAS_REVIEW_AND_REFINE

# New routing function for SAS Step 3
def route_after_sas_step3(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after SAS Step 3: Parameter Mapping (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "generation_failed":
        logger.warning(f"Error during Parameter Mapping. Error: {state.error_message}")
        state.completion_status = "error"
        return END
    elif state.dialog_state == "sas_step3_completed":
        logger.info("Parameter Mapping successful. Routing to SAS_MERGE_XMLS.")
        return SAS_MERGE_XMLS
    else:
        logger.error(f"Unexpected state after Parameter Mapping: {state.dialog_state}. Routing to END as error.")
        state.completion_status = "error"
        return END

# New routing function after GENERATE_INDIVIDUAL_XMLS
def route_after_generate_individual_xmls(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after Generate Individual XMLs (is_error: {state.is_error}, dialog_state: {state.dialog_state}) ---")
    if state.is_error or state.dialog_state == "generation_failed":
        logger.warning(f"Error during Individual XML Generation. Error: {state.error_message}")
        state.completion_status = "error"
        return END
    elif state.dialog_state == "sas_individual_xmls_generated_ready_for_mapping":
        logger.info("Individual XMLs generated. Routing to SAS_PARAMETER_MAPPING.")
        return SAS_PARAMETER_MAPPING
    else:
        logger.error(f"Unexpected state after Individual XML Generation: {state.dialog_state}. Routing to END as error.")
        state.completion_status = "error"
        return END

def create_robot_flow_graph(
    llm: BaseChatModel,
    checkpointer: Optional[BaseCheckpointSaver] = None
) -> Any:
    
    workflow = StateGraph(RobotFlowAgentState)

    # Node Binding
    workflow.add_node(INITIALIZE_STATE, initialize_state_node)
    workflow.add_node(SAS_USER_INPUT_TO_TASK_LIST, functools.partial(user_input_to_task_list_node, llm=llm))
    workflow.add_node(SAS_TASK_LIST_TO_MODULE_STEPS, functools.partial(task_list_to_module_steps_node, llm=llm))
    workflow.add_node(SAS_REVIEW_AND_REFINE, review_and_refine_node)
    workflow.add_node(GENERATE_INDIVIDUAL_XMLS, functools.partial(generate_individual_xmls_node, llm=llm))
    workflow.add_node(SAS_MERGE_XMLS, sas_merge_xml_node)
    workflow.add_node(SAS_CONCATENATE_XMLS, sas_concatenate_xml_node)
    workflow.add_node(SAS_PARAMETER_MAPPING, functools.partial(parameter_mapping_node, llm=llm))

    # Define Graph Edges
    workflow.set_entry_point(INITIALIZE_STATE)

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
            SAS_TASK_LIST_TO_MODULE_STEPS: SAS_TASK_LIST_TO_MODULE_STEPS,
            SAS_USER_INPUT_TO_TASK_LIST: SAS_USER_INPUT_TO_TASK_LIST,
            GENERATE_INDIVIDUAL_XMLS: GENERATE_INDIVIDUAL_XMLS,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_TASK_LIST_TO_MODULE_STEPS,
        route_after_sas_step2,
        {
            SAS_REVIEW_AND_REFINE: SAS_REVIEW_AND_REFINE, 
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        GENERATE_INDIVIDUAL_XMLS,
        route_after_generate_individual_xmls,
        {
            SAS_PARAMETER_MAPPING: SAS_PARAMETER_MAPPING,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_PARAMETER_MAPPING,
        route_after_sas_step3,
        {
            SAS_MERGE_XMLS: SAS_MERGE_XMLS,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_MERGE_XMLS,
        route_after_sas_merge_xmls,
        {
            SAS_CONCATENATE_XMLS: SAS_CONCATENATE_XMLS,
            END: END
        }
    )

    workflow.add_conditional_edges(
        SAS_CONCATENATE_XMLS,
        route_after_sas_concatenate_xmls,
        {
            END: END
        }
    )

    app = workflow.compile(checkpointer=checkpointer)
    return app

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


# NOTE: Test code has been moved to backend/tests/test_sas_graph_builder.py
# The test code previously in this file contained hardcoded BRG (bearing) related input
# which was causing issues with task generation. For proper testing, please use the
# dedicated test file instead of running this module directly.

# Example of how to run the graph (for reference):
# from backend.sas.graph_builder import create_robot_flow_graph
# from langchain_google_genai import ChatGoogleGenerativeAI
# llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
# robot_flow_app = create_robot_flow_graph(llm=llm)
# final_state = await robot_flow_app.ainvoke(initial_input_state) 