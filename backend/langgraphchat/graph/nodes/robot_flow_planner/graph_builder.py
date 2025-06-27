import logging
import functools
from typing import Dict, Any, Optional, Callable, List
import asyncio
import os
import xml.etree.ElementTree as ET
import copy
from pathlib import Path
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage

from .state import RobotFlowAgentState, GeneratedXmlFile
from .llm_nodes import (
    preprocess_and_enrich_input_node,
    understand_input_node,
    generate_individual_xmls_node,
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

def initialize_state_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    logger.info("--- Initializing Agent State (Robot Flow Subgraph) ---")
    merged_config = DEFAULT_CONFIG.copy()
    if state.config is None: state.config = {}
    merged_config.update(state.config) # Apply other overrides from input config
    state.config = merged_config
    
    if state.dialog_state is None: state.dialog_state = "initial"
    state.current_step_description = "Initialized Robot Flow Subgraph"
    # Ensure user_input from invoker is preserved if dialog_state is initial
    # preprocess_and_enrich_input_node will consume it.
    logger.info(f"Agent state initialized. Dialog state: {state.dialog_state}, Initial User Input: '{state.user_input}', Using NODE_TEMPLATE_DIR_PATH: {state.config.get('NODE_TEMPLATE_DIR_PATH')}")
    return state.dict(exclude_none=True)

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

    return state.dict(exclude_none=True)

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
        return state.dict(exclude_none=True)

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
                    return state.dict(exclude_none=True)
            elif gf.block_id:
                logger.warning(f"Skipping block_id {gf.block_id} for merge due to status '{gf.status}' or no content.")

    try:
        relation_structure_root = ET.fromstring(relation_xml_str)
    except ET.ParseError as e:
        logger.error(f"Failed to parse relation.xml: {e}. XML: {relation_xml_str[:200]}", exc_info=True)
        state.is_error = True
        state.error_message = f"Internal error: Failed to parse relation XML: {e}"
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

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
        return state.dict(exclude_none=True)
    except Exception as e:
        logger.error(f"Unexpected error during final XML construction: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Internal error: Unexpected error while constructing final XML: {e}"; 
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    ET.register_namespace("", BLOCKLY_NS) # Ensure default namespace for output
    try:
        if hasattr(ET, 'indent'): ET.indent(final_flow_xml_root, space="  ") # Python 3.9+
        merged_xml_content_string = ET.tostring(final_flow_xml_root, encoding='unicode', xml_declaration=False)
        final_xml_string_output = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n{merged_xml_content_string}"
    except Exception as e:
        logger.error(f"Error serializing final merged XML: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Internal error: Error serializing final XML: {e}"; 
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

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

    return state.dict(exclude_none=True)

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

# Simple error handler node logic (optional, could be merged into routing)
# async def error_handler_node(state: RobotFlowAgentState) -> Dict[str, Any]:
#     logger.error(f"--- Error Handler Node Entered. Error: {state.error_message} ---")
#     # This node primarily logs. The routing logic will take it back to core_interaction_node.
#     # It might add a generic error message to state.messages if not already specific enough.
#     if state.error_message and not any("通用错误提示" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
#          state.messages = state.messages + [AIMessage(content=f"发生错误: {state.error_message}. 请尝试修改您的请求.")]
#     state.dialog_state = "generation_failed"
#     return state.dict(exclude_none=True)

# create_robot_flow_graph function (original was L344, this is a rewrite for the new flow)
def create_robot_flow_graph(
    llm: BaseChatModel,
) -> Callable[[Dict[str, Any]], Any]: 
    
    workflow = StateGraph(RobotFlowAgentState)

    # Node Binding (using functools.partial for llm where needed)
    workflow.add_node(INITIALIZE_STATE, initialize_state_node)
    workflow.add_node(CORE_INTERACTION_NODE, functools.partial(preprocess_and_enrich_input_node, llm=llm))
    workflow.add_node(UNDERSTAND_INPUT, functools.partial(understand_input_node, llm=llm))
    workflow.add_node(GENERATE_INDIVIDUAL_XMLS, functools.partial(generate_individual_xmls_node, llm=llm))
    workflow.add_node(GENERATE_RELATION_XML, generate_relation_xml_node_py)
    workflow.add_node(GENERATE_FINAL_XML, functools.partial(generate_final_flow_xml_node, llm=llm))
    # workflow.add_node(ERROR_HANDLER, error_handler_node) # Optional: if a separate error logging node is desired.

    # --- Define Graph Edges ---
    workflow.set_entry_point(INITIALIZE_STATE)
    workflow.add_edge(INITIALIZE_STATE, CORE_INTERACTION_NODE)

    workflow.add_conditional_edges(
        CORE_INTERACTION_NODE,
        route_after_core_interaction,
        {
            UNDERSTAND_INPUT: UNDERSTAND_INPUT,
            CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, # For loops waiting for user reply to clarification_question
            END_FOR_CLARIFICATION: END, # New edge to END node
            # ERROR_HANDLER: ERROR_HANDLER # If preprocess itself has an unrecoverable error
        }
    )

    # XML Generation Chain with error handling routing back to Core Interaction
    workflow.add_conditional_edges(
        UNDERSTAND_INPUT, 
        functools.partial(route_xml_generation_or_python_step, next_step_if_ok=GENERATE_INDIVIDUAL_XMLS, current_step_name_for_log="Understand Input"),
        {CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, GENERATE_INDIVIDUAL_XMLS: GENERATE_INDIVIDUAL_XMLS}
    )
    workflow.add_conditional_edges(
        GENERATE_INDIVIDUAL_XMLS, 
        functools.partial(route_xml_generation_or_python_step, next_step_if_ok=GENERATE_RELATION_XML, current_step_name_for_log="Generate Individual XMLs"),
        {CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, GENERATE_RELATION_XML: GENERATE_RELATION_XML}
    )
    workflow.add_conditional_edges(
        GENERATE_RELATION_XML, 
        functools.partial(route_xml_generation_or_python_step, next_step_if_ok=GENERATE_FINAL_XML, current_step_name_for_log="Generate Relation XML (Python)"),
        {CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, GENERATE_FINAL_XML: GENERATE_FINAL_XML}
    )
    workflow.add_conditional_edges(
        GENERATE_FINAL_XML,
        decide_after_final_xml_generation, # This handles final success (END) or failure (CORE_INTERACTION_NODE)
        {END: END, CORE_INTERACTION_NODE: CORE_INTERACTION_NODE}
    )
    
    # If using a separate ERROR_HANDLER node that gets routed to from various error points:
    # workflow.add_edge(ERROR_HANDLER, CORE_INTERACTION_NODE) 

    logger.info("Robot Flow Subgraph (Python relation.xml version) compiled.")
    app = workflow.compile()
    logger.info("Robot flow subgraph compilation complete.")
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

async def main_test_run():
    from langchain_openai import ChatOpenAI
    import json

    # REMOVE THIS LINE: logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Ensure OPENAI_API_KEY is set in your environment or .env file
    # For DeepSeek, ensure appropriate API key and base URL are set if not using OpenAI models
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0) 
    # Or for Deepseek:
    # llm = ChatOpenAI(
    #     model_name="deepseek-chat", 
    #     openai_api_key="YOUR_DEEPSEEK_API_KEY", # Replace with your actual key
    #     openai_api_base="https://api.deepseek.com/v1", # Or your specific endpoint
    #     temperature=0
    # )

    robot_flow_app = create_robot_flow_graph(llm=llm)

    initial_input_state = {
        "messages": [], 
        "user_input": "Robot: dobot_mg400\nWorkflow:\n1. Set motor state to on.\n2. Linear move to point P1. Z-axis enabled, others disabled.\n3. Linear move to point P2. X-axis enabled, others disabled.",
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
    
    # final_state = {}
    # async for event in robot_flow_app.astream(initial_input_state, {"recursion_limit": 15}):
    #     logger.info(f"Event keys: {event.keys()}")
    #     for key, value in event.items():
    #         logger.info(f"  Node: {key}")
    #         # logger.info(f"    Value: {json.dumps(value, indent=2, ensure_ascii=False)}")
    #         if isinstance(value, dict) and "messages" in value:
    #             logger.info(f"    Last Message: {value['messages'][-1] if value['messages'] else 'No messages'}")
    #         final_state = value # Keep the last state
    #     print("---")

    final_state = await robot_flow_app.ainvoke(initial_input_state, {"recursion_limit": 15}) # Increased recursion limit

    logger.info(f"\nFinal State: {json.dumps(final_state, indent=2, ensure_ascii=False)}")

    if final_state.get('is_error'):
        logger.error(f"Flow completed with an error: {final_state.get('error_message')}")
    elif final_state.get('final_flow_xml_path'):
        logger.info(f"Flow completed successfully. Final XML at: {final_state.get('final_flow_xml_path')}")
        logger.info("Content of relation.xml:")
        try:
            with open(final_state.get('relation_xml_path', ''), 'r') as f:
                print(f.read())
        except Exception as e:
            logger.error(f"Could not read relation.xml: {e}")
    else:
        logger.info("Flow completed, but no specific output path found. Check logs for details.")

if __name__ == '__main__':
    asyncio.run(main_test_run()) 