import logging
import functools # Added functools
from typing import Dict, Any, Optional, Callable

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .state import RobotFlowAgentState
from .llm_nodes import preprocess_and_enrich_input_node, understand_input_node
# Import other node functions as they are created
# from .llm_nodes import generate_individual_xmls_node, generate_relation_xml_node
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
    current_config = state.get("config", {})
    merged_config = DEFAULT_CONFIG.copy()
    merged_config.update(current_config)
    state["config"] = merged_config

    # Initialize new dialog-related fields, ensuring not to overwrite if graph is re-invoked with existing state
    state.setdefault("messages", [])
    state.setdefault("robot_model", None)
    state.setdefault("raw_user_request", None)
    state.setdefault("clarification_question", None)
    state.setdefault("enriched_structured_text", None)
    # Always set dialog_state to initial on first entry to this node if not resuming a dialog.
    # If resuming, user_input and dialog_state would be set by the calling script.
    if state.get("dialog_state") is None:
        state["dialog_state"] = "initial"

    # Standard fields
    state.setdefault("parsed_flow_steps", None)
    state.setdefault("parsed_robot_name", None)
    state.setdefault("is_error", False)
    state.setdefault("error_message", None)
    state["current_step_description"] = "Initialized"
    
    logger.info(f"Agent state initialized/updated. Output directory: {state['config'].get('OUTPUT_DIR_PATH')}, Dialog state: {state['dialog_state']}")
    return state

def error_handling_node(state: RobotFlowAgentState) -> RobotFlowAgentState:
    """Node to handle errors. It can log the error and prepare for termination."""
    logger.error("--- Error Detected in Flow ---")
    logger.error(f"Current Step: {state.get('current_step_description')}, Dialog State: {state.get('dialog_state')}")
    logger.error(f"Error Message: {state.get('error_message')}")
    return state

# Conditional routing function
def should_continue(state: RobotFlowAgentState) -> str:
    """Determines the next step based on the current state, especially error flags."""
    if state.get("is_error", False):
        logger.warning("Error flag is set. Routing to error handler.")
        return "error_handler"
    
    dialog_state = state.get("dialog_state")
    # current_step_desc is the description of the node THAT JUST FINISHED.
    last_completed_node_desc = state.get("current_step_description") 

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
            logger.info("Input understood. For now, routing to END. TODO: Route to Step 2 (XML generation).")
            return END
    
    logger.info(f"should_continue: No specific route for dialog_state '{dialog_state}' and last_node '{last_completed_node_desc}'. Defaulting to END.")
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
    
    # TODO: Add other nodes here as they are developed
    # Example for a future async node needing tools:
    # write_tool = WriteXmlFileTool()
    # generate_xmls_node_with_deps = functools.partial(generate_individual_xmls_node, llm=llm, file_tool=write_tool)
    # workflow.add_node("generate_individual_xmls", generate_xmls_node_with_deps)
    
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
            # "generate_individual_xmls": "generate_individual_xmls", # TODO: Uncomment when step 2 node exists
            "error_handler": "error_handler",
            END: END # For now, step 1 completion goes to END
        }
    )
    
    workflow.add_edge("error_handler", END)

    # TODO: Add edges for step 2 -> step 3 -> step 4

    # Compile the graph
    app = workflow.compile()
    logger.info("Robot flow generation graph compiled successfully with refined preprocessing, clarification, and re-enrichment loop.")
    return app

# Example of how to run (for testing, typically in a main script)
# if __name__ == '__main__':
#     from langchain_openai import ChatOpenAI # Or your preferred LLM

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
#         # "config": {"OUTPUT_DIR_PATH": "/workspace/test_robot_flow_output"} # Example of overriding default config
#     }

#     logger.info(f"Invoking graph with initial input: {initial_input_state}")

#     # Stream events from the graph
#     for event in robot_flow_app.stream(initial_input_state, {"recursion_limit": 10}):
#         for key, value in event.items():
#             logger.info(f"Event: {key} - Value: {value}")
#         print("---")
    
#     final_state = robot_flow_app.invoke(initial_input_state, {"recursion_limit": 10})
#     logger.info(f"\nFinal State: {json.dumps(final_state, indent=2)}")

#     if final_state.get('is_error'):
#         logger.error(f"Flow completed with an error: {final_state.get('error_message')}")
#     elif final_state.get('final_flow_xml_path'):
#         logger.info(f"Flow completed successfully. Final XML at: {final_state.get('final_flow_xml_path')}")
#     elif final_state.get('parsed_flow_steps'):
#         logger.info("Flow completed up to understanding input. Further steps need implementation.")
#     else:
#         logger.info("Flow completed, but no specific output path found. Check logs for details.") 