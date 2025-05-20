import logging
import functools # Added functools
from typing import Dict, Any, Optional, Callable, List # Ensure List is imported
import asyncio
import os
import xml.etree.ElementTree as ET # Ensure ET is imported
import copy # Ensure copy is imported
from pathlib import Path # Ensure Path is imported

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel # For type hint
from langchain_core.tools import BaseTool

from .state import RobotFlowAgentState, GeneratedXmlFile
from .llm_nodes import preprocess_and_enrich_input_node, understand_input_node, generate_individual_xmls_node, generate_relation_xml_node
# Import other node functions as they are created
# from .xml_tools import merge_xml_files # Assuming step 4 might be a direct Python function node

from .xml_tools import WriteXmlFileTool # Example tool

logger = logging.getLogger(__name__)

# Placeholder for loading initial config (placeholder values from flow_placeholders.md)
# This could come from a file, environment variables, or direct input.
DEFAULT_CONFIG = {
    "GENERAL_INSTRUCTION_INTRO": "作为机器人流程文件创建智能体，根据上下文和用户的最新自然语言输入，你需要执行以下多步骤流程来生成机器人控制的 XML 文件：",
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

def initialize_state_node(state: RobotFlowAgentState) -> RobotFlowAgentState:
    """Node to initialize the agent state with default config if not already present."""
    logger.info("--- Initializing Agent State ---")
    
    # Initialize config
    # state.config is initialized as {} by Pydantic's default_factory=dict
    merged_config = DEFAULT_CONFIG.copy()
    # Ensure state.config is not None before attempting update, though default_factory should prevent it.
    if state.config is None:
        state.config = {} # Should not be necessary with default_factory
    merged_config.update(state.config)
    state.config = merged_config

    # Pydantic models handle default initialization for fields.
    # For example, 'messages' has default_factory=list.
    # 'dialog_state' has a default "initial".
    # Optional fields default to None.

    # If 'dialog_state' somehow became None and we want to enforce 'initial'
    # (though its default in RobotFlowAgentState is "initial")
    if state.dialog_state is None: 
        state.dialog_state = "initial"

    # Fields like robot_model, raw_user_request are Optional and will be None by default.
    # No need for setdefault for them if None is the desired initial state.

    state.current_step_description = "Initialized"
    
    output_dir_path = state.config.get('OUTPUT_DIR_PATH') # Use .get() on the dict state.config
    logger.info(f"Agent state initialized/updated. Output directory: {output_dir_path}, Dialog state: {state.dialog_state}")
    return state

def error_handling_node(state: RobotFlowAgentState) -> RobotFlowAgentState:
    """Node to handle errors. It can log the error and prepare for termination."""
    logger.error("--- Error Detected in Flow ---")
    logger.error(f"Current Step: {state.current_step_description}, Dialog State: {state.dialog_state}") # Direct access
    logger.error(f"Error Message: {state.error_message}") # Direct access
    return state

# Placeholder Node for Step 2: Generate Independent Node XMLs
# def generate_individual_xmls_node(state: RobotFlowAgentState, llm: Optional[BaseChatModel] = None) -> RobotFlowAgentState:
#     logger.info("--- Running Step 2: Generate Independent Node XMLs (Placeholder) ---")
#     state.current_step_description = "Generating individual XML nodes"
#     # Actual logic for XML generation will go here.
#     # For now, simulate success and prepare for the next step.
#     state.generated_node_xmls = [
#         GeneratedXmlFile(
#             block_id="example_node_1", 
#             type="placeholder_type", # Added placeholder type
#             source_description="Placeholder step description", # Added placeholder source_description
#             status="success", # Added status
#             file_path="/path/to/example_node_1.xml", 
#             xml_content="<example_node />"
#         )
#     ]
#     logger.info("Placeholder: Individual XML nodes generated.")
#     state.dialog_state = "generating_relations"
#     return state

# Placeholder for Step 3: Generate Node Relation XML (Placeholder - to be implemented)
# async def generate_relation_xml_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
#     logger.info("--- Step 3: Generate Node Relation XML (Placeholder) ---")
#     state.current_step_description = "Generating node relation XML (Placeholder)"
#     # TODO: Implement logic to create relation.xml based on state.parsed_flow_steps and generated_node_xmls IDs
#     # This will likely involve taking the parsed_flow_steps, mapping to the generated block_ids,
#     # and then constructing an XML string that defines <next> and <statement name=\"DO\"> relationships.
#     # It should NOT include <field> values or data-blockNo attributes in relation.xml.
#     # The output should be saved to a file and its path stored in state.relation_xml_path
#     # state.relation_xml_content = "<?xml version=\"1.0\"?><xml><block type=\"start\" id=\"start_block\"><next><block type=\"end\" id=\"end_block\" /></next></block></xml>" # Dummy content
#     # state.relation_xml_path = "/tmp/relation_placeholder.xml"
#     # with open(state.relation_xml_path, "w") as f:
#     #     f.write(state.relation_xml_content)
    
#     state.dialog_state = "relation_xml_generated" # Placeholder success state
#     logger.info("Relation XML generation (Placeholder) complete.")
#     return state

# --- Step 4: Merge Individual XMLs into Final Flow XML ---
# This node takes the relation.xml structure and the content of individual block XMLs
# and merges them into a single, final flow.xml file.
# This is a pure Python XML manipulation node, does not require LLM.

BLOCKLY_NS = "https://developers.google.com/blockly/xml" # Namespace used in Blockly XMLs

async def generate_final_flow_xml_node(state: RobotFlowAgentState, llm: Optional[BaseChatModel] = None) -> RobotFlowAgentState:
    logger.info("--- Running Step 4: Merge Individual XMLs into Final Flow XML ---")
    state.current_step_description = "Merging XMLs into final flow file"

    relation_xml_str = state.relation_xml_content
    individual_xmls_info = state.generated_node_xmls
    config = state.config

    if not relation_xml_str:
        logger.error("Relation XML content is missing from state.")
        state.is_error = True
        state.error_message = "Relation XML content missing for final merge."
        state.dialog_state = "error"
        return state

    if not individual_xmls_info:
        logger.warning("List of generated individual XMLs is empty. Final flow may be minimal.")

    block_element_map: Dict[str, ET.Element] = {}
    if individual_xmls_info: 
        for gf in individual_xmls_info:
            if gf.status == "success" and gf.xml_content and gf.block_id:
                try:
                    individual_xml_file_root = ET.fromstring(gf.xml_content)
                    block_node = None
                    for child in individual_xml_file_root:
                        if child.tag == f"{{{BLOCKLY_NS}}}block":
                            block_node = child
                            break
                    if block_node is not None:
                        block_element_map[gf.block_id] = block_node
                    else:
                        logger.warning(f"Could not find main <block> in individual XML for block_id: {gf.block_id}.")
                except ET.ParseError as e:
                    logger.error(f"Failed to parse XML for block_id {gf.block_id}: {e}.", exc_info=True)
                    state.is_error = True
                    state.error_message = f"Malformed XML for block_id {gf.block_id}: {e}"
                    state.dialog_state = "error"
                    return state
            elif gf.block_id:
                logger.warning(f"Skipping block_id {gf.block_id} for merge due to status '{gf.status}' or no content.")

    try:
        relation_structure_root = ET.fromstring(relation_xml_str)
    except ET.ParseError as e:
        logger.error(f"Failed to parse relation.xml: {e}.", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to parse relation.xml: {e}"
        state.dialog_state = "error"
        return state

    final_flow_xml_root = ET.Element(f"{{{BLOCKLY_NS}}}xml")
    for name, value in relation_structure_root.attrib.items():
         final_flow_xml_root.set(name, value)
    
    memo_processed_relation_blocks = {} # Memoization for _build_final_block_tree

    def _build_final_block_tree(relation_block_element: ET.Element) -> ET.Element:
        block_id = relation_block_element.get("id")
        if not block_id:
            err_msg = f"Block in relation.xml missing 'id': {ET.tostring(relation_block_element, encoding='unicode')}"
            logger.error(err_msg)
            raise LookupError(err_msg)
        
        # Check memoization table before re-processing
        if block_id in memo_processed_relation_blocks:
            return copy.deepcopy(memo_processed_relation_blocks[block_id]) # Return a copy

        full_block_template_from_map = block_element_map.get(block_id)
        if full_block_template_from_map is None:
            block_type_from_relation = relation_block_element.get("type", "N/A")
            err_msg = f"Content for block_id '{block_id}' (type: {block_type_from_relation}) not found."
            logger.error(err_msg)
            raise LookupError(err_msg)

        final_merged_block = copy.deepcopy(full_block_template_from_map)
        for child_tag_to_clear in ["next", "statement"]:
            for element_to_remove in final_merged_block.findall(f"{{{BLOCKLY_NS}}}{child_tag_to_clear}"):
                final_merged_block.remove(element_to_remove)

        for rel_statement_element in relation_block_element.findall(f"{{{BLOCKLY_NS}}}statement"):
            statement_name = rel_statement_element.get("name")
            final_stmt_element_for_merge = ET.SubElement(final_merged_block, f"{{{BLOCKLY_NS}}}statement", name=statement_name)
            rel_inner_block = rel_statement_element.find(f"{{{BLOCKLY_NS}}}block")
            if rel_inner_block is not None:
                constructed_inner_block = _build_final_block_tree(rel_inner_block)
                final_stmt_element_for_merge.append(constructed_inner_block)
        
        rel_next_element = relation_block_element.find(f"{{{BLOCKLY_NS}}}next")
        if rel_next_element is not None:
            rel_next_inner_block = rel_next_element.find(f"{{{BLOCKLY_NS}}}block")
            if rel_next_inner_block is not None:
                final_next_element_for_merge = ET.SubElement(final_merged_block, f"{{{BLOCKLY_NS}}}next")
                constructed_next_inner_block = _build_final_block_tree(rel_next_inner_block)
                final_next_element_for_merge.append(constructed_next_inner_block)
        
        memo_processed_relation_blocks[block_id] = final_merged_block # Store the original constructed block
        return copy.deepcopy(final_merged_block) # Return a copy for the current caller

    try:
        first_block_in_relation = relation_structure_root.find(f"{{{BLOCKLY_NS}}}block")
        if first_block_in_relation is not None:
            root_block_for_final_flow = _build_final_block_tree(first_block_in_relation)
            final_flow_xml_root.append(root_block_for_final_flow)
        elif block_element_map: # individual XMLs exist but relation.xml is empty
             logger.warning("Relation.xml is empty but individual XMLs exist. Final flow.xml will be empty.")
        else: # Both are empty
            logger.info("Relation.xml and individual_node_xmls are empty. Final flow.xml will be empty.")
    except LookupError as e:
        logger.error(f"Merge process failed due to missing block data or structure: {e}", exc_info=True)
        state.is_error = True; state.error_message = str(e); state.dialog_state = "error"; return state
    except Exception as e:
        logger.error(f"Unexpected error during final XML construction: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Unexpected merge error: {e}"; state.dialog_state = "error"; return state

    ET.register_namespace("", BLOCKLY_NS)
    try:
        if hasattr(ET, 'indent'): ET.indent(final_flow_xml_root, space="  ")
        merged_xml_content_string = ET.tostring(final_flow_xml_root, encoding='unicode', xml_declaration=False)
        final_xml_string_output = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n{merged_xml_content_string}"
    except Exception as e:
        logger.error(f"Error serializing final merged XML: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Error serializing final XML: {e}"; state.dialog_state = "error"; return state

    state.final_flow_xml_content = final_xml_string_output
    output_dir_path_str = config.get("OUTPUT_DIR_PATH", "/tmp")
    final_flow_file_name = config.get("FINAL_FLOW_FILE_NAME_ACTUAL", "flow.xml")
    final_flow_file_path = Path(output_dir_path_str) / final_flow_file_name

    try:
        os.makedirs(output_dir_path_str, exist_ok=True)
        with open(final_flow_file_path, "w", encoding="utf-8") as f: f.write(final_xml_string_output)
        state.final_flow_xml_path = str(final_flow_file_path)
        logger.info(f"Successfully merged and wrote final flow XML to {final_flow_file_path}")
    except IOError as e:
        logger.error(f"Failed to write final flow XML to {final_flow_file_path}: {e}", exc_info=True)
        state.is_error = True; state.error_message = f"Failed to write final XML file: {e}"; state.dialog_state = "error"; return state
    
    state.dialog_state = "flow_completed"
    return state

# Conditional routing function
def should_continue(state: RobotFlowAgentState) -> str:
    """Determines the next step based on the current state, especially error flags."""
    if state.is_error: # Direct access for boolean
        logger.warning("Error flag is set. Routing to error handler.")
        return "error_handler"
    
    dialog_state = state.dialog_state # Direct access
    # current_step_desc is the description of the node THAT JUST FINISHED.
    last_completed_node_desc = state.current_step_description # Direct access

    # From initialize_state
    if last_completed_node_desc == "Initialized":
        logger.info("State initialized. Routing to preprocess_and_enrich_input.")
        return "preprocess_and_enrich_input"

    # From preprocess_and_enrich_input
    if last_completed_node_desc == "Preprocessing and enriching input":
        if dialog_state == "awaiting_robot_model":
            logger.info("Dialog state is 'awaiting_robot_model'. Ending turn.")
            return END
        if dialog_state == "awaiting_enrichment_confirmation":
            logger.info("Dialog state is 'awaiting_enrichment_confirmation'. Ending turn.")
            return END
        if dialog_state == "initial": # This means user provided feedback, and we want to re-enrich
            logger.info("User provided feedback or model normalized, dialog_state is 'initial'. Re-routing to preprocess_and_enrich_input.")
            return "preprocess_and_enrich_input" # Loop back to itself with updated state
        if dialog_state == "processing_enriched_input":
            logger.info("Input enriched and confirmed. Routing to understand_input.")
            return "understand_input"
        
    # From understand_input
    if last_completed_node_desc == "Understanding user input":
        if dialog_state == "input_understood": # This is set by understand_input_node on success
            logger.info("Input understood. Routing to Step 2 (generate_individual_xmls).")
            return "generate_individual_xmls" # Route to Step 2
    
    # Routing from the actual generate_individual_xmls_node (from llm_nodes.py)
    if last_completed_node_desc == "Generating individual XML files for each flow operation":
        if dialog_state == "individual_xmls_generated":
            logger.info("Individual XMLs generated (from llm_nodes). Routing to Step 3 (generate_relation_xml).")
            return "generate_relation_xml"
    
    # Routing from generate_relation_xml_node (from llm_nodes.py)
    if last_completed_node_desc == "Generating node relation XML file":
        if dialog_state == "relation_xml_generated":
            logger.info("Relation XML generated. Routing to Step 4 (merge_xmls).")
            return "merge_xmls"
    
    # Routing for a potential future generate_relation_xml_node from llm_nodes.py
    # if last_completed_node_desc == "Generating node relation XML file": # Future description from llm_nodes
    #     if dialog_state == "relation_xml_generated": # State it might set
    #         logger.info("Relation XML generated (from llm_nodes). Routing to Step 4 (generate_final_flow_xml).")
    #         return "generate_final_flow_xml"

    if last_completed_node_desc == "Merging XMLs into final flow file": # Updated description
        if dialog_state == "flow_completed":
            logger.info("Final flow XML generated. Flow completed. Routing to END.")
            return END
            
    logger.info(f"should_continue: No route for dialog '{dialog_state}', last_node '{last_completed_node_desc}'. Default END.")
    return END


def create_robot_flow_graph(
    llm: BaseChatModel, 
    # tools: Optional[List[BaseTool]] = None # Tools might be specific to nodes
) -> Callable[[Dict[str, Any]], Any]:
    """
    Creates and compiles the Langgraph StatefulGraph for the robot flow generation agent.
    """
    workflow = StateGraph(RobotFlowAgentState)

    # Add Nodes
    workflow.add_node("initialize_state", initialize_state_node)
    
    preprocess_node_with_llm = functools.partial(preprocess_and_enrich_input_node, llm=llm)
    workflow.add_node("preprocess_and_enrich_input", preprocess_node_with_llm)
    
    understand_input_node_with_llm = functools.partial(understand_input_node, llm=llm)
    workflow.add_node("understand_input", understand_input_node_with_llm)
    
    # Add new placeholder nodes (Step 2, 3, 4)
    # Note: These placeholders currently don't use the LLM, but it's passed for future consistency.
    generate_xmls_node_with_deps = functools.partial(generate_individual_xmls_node, llm=llm) # This will now use the imported one
    workflow.add_node("generate_individual_xmls", generate_xmls_node_with_deps)

    generate_relations_node_with_deps = functools.partial(generate_relation_xml_node, llm=llm) 
    workflow.add_node("generate_relation_xml", generate_relations_node_with_deps)

    # Step 4 is conceptually "merge_xmls" which then produces the final flow. 
    # We'll name the node "merge_xmls" but it will call the generate_final_flow_xml_node placeholder for now.
    merge_xmls_node_placeholder = functools.partial(generate_final_flow_xml_node, llm=llm)
    workflow.add_node("merge_xmls", merge_xmls_node_placeholder)
    
    workflow.add_node("error_handler", error_handling_node)

    # Set Entry Point
    workflow.set_entry_point("initialize_state")

    # Add Edges and Conditional Edges
    workflow.add_conditional_edges(
        "initialize_state",
        should_continue,
        {
            "preprocess_and_enrich_input": "preprocess_and_enrich_input",
            "error_handler": "error_handler", 
            END: END
        }
    )

    workflow.add_conditional_edges(
        "preprocess_and_enrich_input",
        should_continue,
        {
            "understand_input": "understand_input",
            "preprocess_and_enrich_input": "preprocess_and_enrich_input", # Added self-loop for re-enrichment
            "error_handler": "error_handler",
            END: END  # This occurs if awaiting_robot_model or awaiting_enrichment_confirmation
        }
    )
    
    workflow.add_conditional_edges(
        "understand_input",
        should_continue, 
        {
            "generate_individual_xmls": "generate_individual_xmls", # Enabled route to Step 2
            "error_handler": "error_handler",
            END: END 
        }
    )
    
    # Add edges for Step 2 -> Step 3 -> Step 4 -> END
    workflow.add_conditional_edges(
        "generate_individual_xmls",
        should_continue,
        {
            "generate_relation_xml": "generate_relation_xml",
            "error_handler": "error_handler",
            END: END # In case of unexpected state
        }
    )

    workflow.add_conditional_edges(
        "generate_relation_xml",
        should_continue,
        {
            "merge_xmls": "merge_xmls", # Route to the merge_xmls node
            "error_handler": "error_handler",
            END: END 
        }
    )

    # Edges from merge_xmls (which runs the generate_final_flow_xml_node placeholder)
    workflow.add_conditional_edges(
        "merge_xmls", # This is the new name for the node that was previously generate_final_flow_xml
        should_continue,
        {
            END: END, 
            "error_handler": "error_handler"
        }
    )
    
    workflow.add_edge("error_handler", END)

    # Compile the graph
    app = workflow.compile()
    # Updated log message to reflect current state of nodes
    logger.info("Robot flow generation graph compiled. generate_individual_xmls and generate_relation_xml are from llm_nodes. merge_xmls is local placeholder (generate_final_flow_xml_node).")
    return app

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
#     #     async for event in robot_flow_app.astream(initial_input_state, {"recursion_limit": 25}):
#     #         for key, value in event.items():
#     #             logger.info(f"Event: {key} - Value: {value}")
#     #         print("---")
#     # asyncio.run(stream_events())
    
#     final_state = asyncio.run(robot_flow_app.ainvoke(initial_input_state, {"recursion_limit": 25}))
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