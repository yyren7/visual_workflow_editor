import logging
import functools
from typing import Dict, Any, Optional, Callable, List
import asyncio
import os
import xml.etree.ElementTree as ET
import copy
from pathlib import Path

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage

from .state import RobotFlowAgentState, GeneratedXmlFile
from .llm_nodes import (
    preprocess_and_enrich_input_node,
    understand_input_node,
    generate_individual_xmls_node,
    generate_relation_xml_node
)
from .xml_tools import WriteXmlFileTool
from .file_share_tool import upload_file

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "GENERAL_INSTRUCTION_INTRO": "As an intelligent agent for creating robot process files, you need to perform the following multi-step process to generate robot control XML files based on the context and the user's latest natural language input:",
    "ROBOT_NAME_EXAMPLE": "dobot_mg400",
    "POINT_NAME_EXAMPLE_1": "P3",
    "POINT_NAME_EXAMPLE_2": "P1",
    "POINT_NAME_EXAMPLE_3": "P2",
    "NODE_TEMPLATE_DIR_PATH": "/workspace/database/node_database/quick-fcpr",
    "OUTPUT_DIR_PATH": "/workspace/database/flow_database/result/example_run/",
    "EXAMPLE_FLOW_STRUCTURE_DOC_PATH": "/workspace/database/document_database/flow.xml",
    "BLOCK_ID_PREFIX_EXAMPLE": "block_uuid",
    "RELATION_FILE_NAME_ACTUAL": "relation.xml",
    "FINAL_FLOW_FILE_NAME_ACTUAL": "flow.xml"
}

# Node name constants for clarity in graph definition
INITIALIZE_STATE = "initialize_state"
CORE_INTERACTION_NODE = "core_interaction_node"
UNDERSTAND_INPUT = "understand_input"
GENERATE_INDIVIDUAL_XMLS = "generate_individual_xmls"
GENERATE_RELATION_XML = "generate_relation_xml"
GENERATE_FINAL_XML = "generate_final_xml"
ERROR_HANDLER = "error_handler" # General error logging node, if needed beyond is_error flag
UPLOAD_FINAL_XML_NODE = "upload_final_xml_node" # If you have this node for uploading

def initialize_state_node(state: RobotFlowAgentState) -> Dict[str, Any]:
    logger.info("--- Initializing Agent State (Robot Flow Subgraph) ---")
    merged_config = DEFAULT_CONFIG.copy()
    if state.config is None: state.config = {}
    merged_config.update(state.config)
    state.config = merged_config
    if state.dialog_state is None: state.dialog_state = "initial"
    state.current_step_description = "Initialized Robot Flow Subgraph"
    # Ensure user_input from invoker is preserved if dialog_state is initial
    # preprocess_and_enrich_input_node will consume it.
    logger.info(f"Agent state initialized. Dialog state: {state.dialog_state}, Initial User Input: '{state.user_input}'")
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
        state.error_message = "内部错误：关系XML内容缺失，无法合并最终流程。"
        state.subgraph_completion_status = "error"
        # state.messages = state.messages + [AIMessage(content=state.error_message)] # Message will be added by routing logic
        return state.dict(exclude_none=True)

    if not individual_xmls_info:
        logger.warning("List of generated individual XMLs is empty. Final flow may be minimal.")

    # ... (rest of the existing XML merging logic from the original file) ...
    # Ensure BLOCKLY_NS is defined or imported
    BLOCKLY_NS = "https://developers.google.com/blockly/xml"
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
                    state.error_message = f"内部错误：解析节点 {gf.block_id} 的XML时失败: {e}"
                    state.subgraph_completion_status = "error"
                    return state.dict(exclude_none=True)
            elif gf.block_id:
                logger.warning(f"Skipping block_id {gf.block_id} for merge due to status '{gf.status}' or no content.")

    try:
        relation_structure_root = ET.fromstring(relation_xml_str)
    except ET.ParseError as e:
        logger.error(f"Failed to parse relation.xml: {e}. XML: {relation_xml_str[:200]}", exc_info=True)
        state.is_error = True
        state.error_message = f"内部错误：解析关系XML时失败: {e}"
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
        state.is_error = True; state.error_message = f"内部错误：构建最终XML时发生意外: {e}"; 
        state.subgraph_completion_status = "error"
        return state.dict(exclude_none=True)

    ET.register_namespace("", BLOCKLY_NS) # Ensure default namespace for output
    try:
        if hasattr(ET, 'indent'): ET.indent(final_flow_xml_root, space="  ") # Python 3.9+
        merged_xml_content_string = ET.tostring(final_flow_xml_root, encoding='unicode', xml_declaration=False)
        final_xml_string_output = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n{merged_xml_content_string}"
    except Exception as e:
        logger.error(f"Error serializing final merged XML: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"内部错误：序列化最终XML时出错: {e}"; 
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
        state.error_message = f"保存最终流程文件 {final_file_path} 失败: {e}"
        state.subgraph_completion_status = "error"
        # Keep final_flow_xml_content in state even if save fails

    if not state.is_error:
        state.subgraph_completion_status = "completed_success"
        state.dialog_state = "final_xml_generated_success"
        state.clarification_question = None

    return state.dict(exclude_none=True)

# --- Conditional Edge Functions ---
def route_after_core_interaction(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Routing after Core Interaction (dialog_state: '{state.dialog_state}', is_error: {state.is_error}) ---")
    
    # Check if preprocess_and_enrich_input_node (CORE_INTERACTION_NODE) itself set an error during its execution
    if state.is_error: # This implies preprocess_and_enrich_input_node failed its own task
        logger.warning(f"Error flag is set by CORE_INTERACTION_NODE. Dialog state: {state.dialog_state}. Routing back to core for user correction.")
        # Ensure error message is in messages for the user to see
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=f"预处理输入时出错: {state.error_message}")]
        state.dialog_state = 'awaiting_user_input' # Prepare for new user input
        state.user_input = None # Crucial: Clear stale user_input to prevent re-processing old data if core node failed.
        state.clarification_question = None # Clear any pending questions from core node
        return CORE_INTERACTION_NODE

    current_dialog_state = state.dialog_state
    if current_dialog_state == "input_understood_ready_for_xml":
        if state.enriched_structured_text:
            logger.info("Core interaction successful (input_understood_ready_for_xml). Routing to: UNDERSTAND_INPUT")
            return UNDERSTAND_INPUT
        else: 
            logger.warning("State is 'input_understood_ready_for_xml' but enriched_structured_text is missing. Awaiting user input.")
            if not any("流程描述不完整" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                 state.messages = state.messages + [AIMessage(content="流程描述不完整或未能正确处理，请重新输入。" )]
            state.dialog_state = "awaiting_user_input"
            state.user_input = None # Clear stale input
            return CORE_INTERACTION_NODE
    elif current_dialog_state in ["awaiting_robot_model_input", "awaiting_enrichment_confirmation", "awaiting_user_input", "processing_user_input", "generation_failed"]:
        # If CORE_INTERACTION_NODE (preprocess_and_enrich_input_node) has set one of these states, 
        # it means it's either waiting for a specific user reply (e.g. to a clarification_question),
        # actively processing, or has just handled a generation failure by setting state to await input.
        # In all these cases, the graph should loop back to CORE_INTERACTION_NODE.
        # If it's awaiting specific input (e.g. robot model), state.user_input should ideally be None 
        # (consumed by preprocess_and_enrich_input_node in the current cycle if it was a response to a question, 
        # or will be None if it just set a question and is waiting for the *next* graph invocation).
        # The invoker node is responsible for providing new user_input in the next cycle if required.
        logger.info(f"Staying in CORE_INTERACTION_NODE. Dialog_state: {current_dialog_state}. This node will await next invocation or process further.")
        return CORE_INTERACTION_NODE
    # else:
        # This 'else' block is removed because this function should ONLY route based on the outcome of CORE_INTERACTION_NODE.
        # Other states like 'generating_xml_individual' are outcomes of *other* nodes, and routing from those
        # is handled by route_xml_generation_step or decide_after_final_xml_generation.
        # If CORE_INTERACTION_NODE produces an unexpected dialog_state not covered above, 
        # it's an internal logic error in preprocess_and_enrich_input_node.
        # logger.error(f"Unexpected dialog_state '{current_dialog_state}' set by CORE_INTERACTION_NODE. Defaulting to CORE_INTERACTION_NODE to reset.")
        # if not any(f"系统遇到意外的内部状态 ({current_dialog_state})" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
        #     state.messages = state.messages + [AIMessage(content=f"系统遇到意外的内部状态 ({current_dialog_state})，请尝试重新描述您的请求。" )]
        # state.dialog_state = "awaiting_user_input"
        # state.user_input = None 
        # state.is_error = True 
        # state.error_message = f"系统遇到由核心交互节点设置的意外内部状态 ({current_dialog_state})，已重置到等待用户输入。"
        # return CORE_INTERACTION_NODE
    
    # Fallback: If no conditions above are met (which should be rare if preprocess_and_enrich_input_node behaves as expected)
    # this indicates an unexpected state produced by CORE_INTERACTION_NODE itself.
    logger.error(f"CRITICAL: route_after_core_interaction encountered an unhandled dialog_state '{current_dialog_state}' originating from CORE_INTERACTION_NODE. This suggests an issue in preprocess_and_enrich_input_node's state setting. Resetting to await user input.")
    if not any(f"系统遇到意外的内部状态 ({current_dialog_state})" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
        state.messages = state.messages + [AIMessage(content=f"机器人流程子图遇到未处理的核心状态 ({current_dialog_state})。请重试或联系支持。" )]
    state.dialog_state = "awaiting_user_input"
    state.user_input = None
    state.is_error = True
    state.error_message = f"机器人流程子图遇到未处理的核心状态 ({current_dialog_state})。"
    state.clarification_question = None
    return CORE_INTERACTION_NODE

def route_xml_generation_step(state: RobotFlowAgentState, next_step_if_ok: str, current_step_name_for_log: str) -> str:
    logger.info(f"--- Routing after XML Gen Step: '{current_step_name_for_log}' (is_error: {state.is_error}) ---")
    if state.is_error:
        logger.warning(f"Error during '{current_step_name_for_log}'. Routing to core_interaction_node.")
        # Ensure error message is in messages for the user
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=f"在 '{current_step_name_for_log}' 步骤中发生错误: {state.error_message}")]
        state.dialog_state = 'generation_failed'
        state.user_input = None # Clear to signify waiting for new input
        return CORE_INTERACTION_NODE
    else:
        logger.info(f"'{current_step_name_for_log}' successful. Routing to {next_step_if_ok}.")
        return next_step_if_ok

def decide_after_final_xml_generation(state: RobotFlowAgentState) -> str:
    logger.info(f"--- Deciding after Final XML Generation (is_error: {state.is_error}, final_xml_content exists: {bool(state.final_flow_xml_content)}) ---")
    if not state.is_error and state.final_flow_xml_content:
        logger.info("Final XML generated successfully. Routing to END.")
        if not any("流程XML已成功生成" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
             state.messages = state.messages + [AIMessage(content=f"流程XML已成功生成。您可以在路径 {state.final_flow_xml_path or '未保存到文件'} 查看，或在聊天记录中查看内容.")]
        state.dialog_state = 'final_xml_generated_success'
        return END
    else:
        logger.warning("Final XML generation failed or produced no content. Routing back to core_interaction_node.")
        if not state.is_error:
            state.is_error = True
            state.error_message = state.error_message or "最终XML内容为空或生成失败。"
        if state.error_message and not any(state.error_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = state.messages + [AIMessage(content=f"生成最终XML时遇到问题: {state.error_message}。请修改您的指令。" )]
        state.dialog_state = 'generation_failed'
        state.user_input = None
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
    workflow.add_node(GENERATE_RELATION_XML, functools.partial(generate_relation_xml_node, llm=llm))
    # generate_final_flow_xml_node is in this file, needs llm passed if its signature requires, currently Optional
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
            # ERROR_HANDLER: ERROR_HANDLER # If preprocess itself has an unrecoverable error
        }
    )

    # XML Generation Chain with error handling routing back to Core Interaction
    workflow.add_conditional_edges(
        UNDERSTAND_INPUT, 
        functools.partial(route_xml_generation_step, next_step_if_ok=GENERATE_INDIVIDUAL_XMLS, current_step_name_for_log="Understand Input"),
        {CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, GENERATE_INDIVIDUAL_XMLS: GENERATE_INDIVIDUAL_XMLS}
    )
    workflow.add_conditional_edges(
        GENERATE_INDIVIDUAL_XMLS, 
        functools.partial(route_xml_generation_step, next_step_if_ok=GENERATE_RELATION_XML, current_step_name_for_log="Generate Individual XMLs"),
        {CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, GENERATE_RELATION_XML: GENERATE_RELATION_XML}
    )
    workflow.add_conditional_edges(
        GENERATE_RELATION_XML, 
        functools.partial(route_xml_generation_step, next_step_if_ok=GENERATE_FINAL_XML, current_step_name_for_log="Generate Relation XML"),
        {CORE_INTERACTION_NODE: CORE_INTERACTION_NODE, GENERATE_FINAL_XML: GENERATE_FINAL_XML}
    )
    workflow.add_conditional_edges(
        GENERATE_FINAL_XML,
        decide_after_final_xml_generation, # This handles final success (END) or failure (CORE_INTERACTION_NODE)
        {END: END, CORE_INTERACTION_NODE: CORE_INTERACTION_NODE}
    )
    
    # If using a separate ERROR_HANDLER node that gets routed to from various error points:
    # workflow.add_edge(ERROR_HANDLER, CORE_INTERACTION_NODE) 

    logger.info("Robot Flow Subgraph (循环版) compiled.")
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