import sys
from pathlib import Path
_FILE_PATH_FOR_PREAMBLE = Path(__file__).resolve()
if __name__ == "__main__" and __package__ is None:
    # This script is in: backend/langgraphchat/graph/subgraph/sas/nodes/generate_relation_xml.py
    # The project root is /workspace, which is 6 levels up from the script's directory.
    _project_root_for_preamble = _FILE_PATH_FOR_PREAMBLE.parents[6] # Should resolve to /workspace
    sys.path.insert(0, str(_project_root_for_preamble))
    import os # os.sep is used here for platform-independent path component replacement
    # Set __package__ to the expected package string, e.g., backend.langgraphchat.graph.subgraph.sas.nodes
    __package__ = str(_FILE_PATH_FOR_PREAMBLE.parent.relative_to(_project_root_for_preamble)).replace(os.sep, '.')

import logging
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import xml.etree.ElementTree as ET

# Removed BaseChatModel import as LLM is no longer used
# from langchain_core.language_models import BaseChatModel

from ..state import RobotFlowAgentState, GeneratedXmlFile # Adjusted import
# Removed prompt_loader and llm_utils imports
# from ..prompt_loader import get_filled_prompt # Adjusted import
# from ..llm_utils import invoke_llm_for_text_output # Adjusted import

logger = logging.getLogger(__name__)

# Removed _prepare_data_for_relation_prompt as it was for LLM prompting

def _extract_block_type_from_detail(detail_string: str) -> Tuple[Optional[str], bool]:
    """
    Extracts block type from a detail string and checks if it's disabled.
    Example: "1. Select robot (Block Type: `select_robot`)"
    Example disabled: "2. Wait for I/O (Block Type: `wait_io`) (This block is disabled)"
    """
    disabled = "(This block is disabled)" in detail_string
    
    # Corrected regex: removed extra backslash before ( and )
    match = re.search(r"(Block Type: `([^`]+)`)", detail_string)
    if match:
        # The first group is the whole match "(Block Type: `type`)", the second group is the `type` itself
        return match.group(2), disabled 
    return None, disabled

def _format_xml(elem: ET.Element) -> str:
    """Return a pretty-printed XML string for the Element."""
    # This is a basic pretty-print. For more control, a library like xml.dom.minidom might be used.
    # However, ElementTree itself doesn't have a robust pretty-print out of the box.
    # A common workaround is to use minidom, but to avoid new dependencies for this edit,
    # we'll do a simpler indenting if possible, or just tostring.
    # For now, let's rely on ET.indent if available (Python 3.9+) or just tostring.
    if hasattr(ET, "indent"):
        ET.indent(elem)
    xml_string = ET.tostring(elem, encoding="unicode")
    # Add XML declaration
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_string


async def generate_relation_xml_node(state: RobotFlowAgentState, llm: Any = None) -> RobotFlowAgentState: # llm parameter is no longer used
    logger.info("--- Running Step 3: Generate Node Relation XML (Rule-based) ---")
    state.current_step_description = "Generating node relation XML file (Rule-based)"
    state.is_error = False

    config = state.config
    parsed_flow_steps = state.parsed_flow_steps # This is the list of task dicts

    if not parsed_flow_steps:
        logger.error("Parsed flow steps are missing for relation XML generation.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for relation XML."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    # --- Select the main task to process ---
    main_task_to_process = None
    if parsed_flow_steps:
        main_task_to_process = parsed_flow_steps[0] # Default to the first task
        for task_data in parsed_flow_steps:
            if task_data.get("type") == "MainTask":
                main_task_to_process = task_data
                break
    
    if not main_task_to_process:
        logger.warning("No suitable main task found to generate relation XML. Generating empty relation XML.")
        state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
    else:
        logger.info(f"Processing task: {main_task_to_process.get('name', 'Unnamed Task')} for relation XML.")
        task_details = main_task_to_process.get("details", [])

        if not task_details:
            logger.warning(f"Task '{main_task_to_process.get('name', 'Unnamed Task')}' has no details. Generating empty relation XML.")
            state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
        else:
            logger.info(f"Starting XML generation for task: {main_task_to_process.get('name')}. Total details: {len(task_details)}")
            xml_root = ET.Element("xml", xmlns="https://developers.google.com/blockly/xml")
            
            parent_stack: List[ET.Element] = [xml_root] 
            last_block_at_depth: Dict[int, Optional[ET.Element]] = {0: None}
            current_depth = 0
            block_id_counter = 1

            for idx, detail_str in enumerate(task_details):
                logger.debug(f"Processing detail [{idx+1}/{len(task_details)}]: '{detail_str}'")
                block_type, is_disabled = _extract_block_type_from_detail(detail_str)
                logger.debug(f"  Extracted block_type: '{block_type}', is_disabled: {is_disabled}")

                if not block_type:
                    logger.debug(f"  Skipping detail: No block type found.")
                    continue
                if is_disabled:
                    logger.debug(f"  Skipping detail: Block is disabled.")
                    continue

                block_id = f"sas_rel_block_{block_id_counter}"
                block_id_counter += 1
                
                current_xml_element = ET.Element("block", type=block_type, id=block_id)
                logger.debug(f"  Created XML element: <block type='{block_type}' id='{block_id}'>")
                
                attach_to_parent_element = parent_stack[-1]
                logger.debug(f"  Current parent stack element: {attach_to_parent_element.tag} (name: {attach_to_parent_element.get('name', 'N/A')}) at depth {current_depth}")
                
                previous_block_at_this_depth = last_block_at_depth.get(current_depth)

                if previous_block_at_this_depth is not None:
                    logger.debug(f"  Attaching to <next> of previous block: {previous_block_at_this_depth.tag} id '{previous_block_at_this_depth.get('id')}'")
                    next_tag = ET.SubElement(previous_block_at_this_depth, "next")
                    next_tag.append(current_xml_element)
                else:
                    logger.debug(f"  Attaching directly to parent element: {attach_to_parent_element.tag}")
                    attach_to_parent_element.append(current_xml_element)
                
                last_block_at_depth[current_depth] = current_xml_element

                if block_type == "loop":
                    logger.debug(f"  Encountered 'loop' block. Creating <statement name='DO'> and increasing depth.")
                    statement_tag = ET.SubElement(current_xml_element, "statement", name="DO")
                    parent_stack.append(statement_tag)
                    current_depth += 1
                    last_block_at_depth[current_depth] = None 
                    logger.debug(f"  New depth: {current_depth}. Parent stack size: {len(parent_stack)}")
                elif block_type == "controls_if": 
                    logger.debug(f"  Encountered 'controls_if' block. Creating <statement name='DO0'> and increasing depth.")
                    statement_tag = ET.SubElement(current_xml_element, "statement", name="DO0")
                    parent_stack.append(statement_tag)
                    current_depth += 1
                    last_block_at_depth[current_depth] = None
                    logger.debug(f"  New depth: {current_depth}. Parent stack size: {len(parent_stack)}")
                elif block_type == "return":
                    logger.debug(f"  Encountered 'return' block.")
                    if current_depth > 0: 
                        parent_stack.pop()
                        del last_block_at_depth[current_depth]
                        current_depth -= 1
                        logger.debug(f"  Closing scope. New depth: {current_depth}. Parent stack size: {len(parent_stack)}. Last block at new depth: {last_block_at_depth.get(current_depth).get('id') if last_block_at_depth.get(current_depth) is not None else 'None'}")
                    else:
                        logger.debug("  'return' block at root level (depth 0). No scope change.")

            logger.info(f"Finished processing details. Final XML content generation.")
            state.relation_xml_content = _format_xml(xml_root)

    # --- Save the generated XML content to file (reusing existing logic) ---
    output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
    relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
    relation_file_path = output_dir / relation_file_name
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(relation_file_path, "w", encoding="utf-8") as f:
            f.write(state.relation_xml_content)
        state.relation_xml_path = str(relation_file_path)
        logger.info(f"Successfully wrote relation XML to {relation_file_path}. Content head: {state.relation_xml_content[:200]}...")
    except IOError as e:
        logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to write relation XML: {e}"
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    # Final state updates
    if not state.is_error: 
        state.dialog_state = "generating_xml_final"
        state.subgraph_completion_status = None 
    return state 


if __name__ == "__main__":
    import asyncio
    # import tempfile # No longer needed for fixed output path

    # Mock RobotFlowAgentState for direct script execution
    class MockRobotFlowAgentState:
        def __init__(self, parsed_flow_steps: List[Dict[str, Any]], config: Dict[str, Any]):
            self.parsed_flow_steps = parsed_flow_steps
            self.config = config
            self.current_step_description: Optional[str] = None
            self.is_error: bool = False
            self.error_message: Optional[str] = None
            self.dialog_state: Optional[str] = None
            self.subgraph_completion_status: Optional[str] = None
            self.relation_xml_content: Optional[str] = None
            self.relation_xml_path: Optional[str] = None
            # Add any other fields that generate_relation_xml_node might try to set/read
            # For example, if it reads generated_node_xmls, it should be initialized.
            self.generated_node_xmls: Optional[List[Any]] = [] # Assuming it might be checked

    async def main_test():
        # Path to your test JSON file
        # Ensure this path is correct relative to where you run the script from, or use an absolute path.
        # For robustness in different execution contexts, constructing path from __file__ is better.
        script_dir = Path(__file__).parent.resolve()
        # Adjust the relative path to your test JSON file from the script's location
        # The script is in /workspace/backend/langgraphchat/graph/subgraph/sas/nodes/
        # The test file is in /workspace/backend/tests/llm_sas_test/run_20250609_071825_821008/
        test_json_path = script_dir.parent.parent.parent.parent.parent / "tests" / "llm_sas_test" / "run_20250609_071825_821008" / "sas_step2_module_steps_iter2.json"

        if not test_json_path.exists():
            logger.error(f"Test JSON file not found at: {test_json_path}")
            print(f"Error: Test JSON file not found at: {test_json_path}")
            return

        with open(test_json_path, 'r', encoding='utf-8') as f:
            test_data_json = json.load(f)
        
        # Define the fixed output directory
        fixed_output_dir_str = "backend/tests/llm_sas_test/1_sample"
        # Construct the output path relative to the project root determined by the preamble
        # Assuming _project_root_for_preamble is defined as in the preamble for direct execution
        # If _project_root_for_preamble is not available here, we might need to re-calculate it
        # or assume a fixed structure from where the script is run.
        # For this case, let's assume the preamble sets up paths correctly so Path() works from workspace root.
        output_dir = Path(fixed_output_dir_str) # This will be relative to workspace if script is run from workspace

        # Ensure the output directory exists
        try:
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Test output will be saved in: {output_dir.resolve()}")
            print(f"Test output directory: {output_dir.resolve()}")
        except OSError as e:
            logger.error(f"Could not create output directory {output_dir}: {e}")
            print(f"Error: Could not create output directory {output_dir}: {e}")
            return

        # Prepare a mock config
        mock_config = {
            "OUTPUT_DIR_PATH": str(output_dir), # Use the Path object converted to string
            "RELATION_FILE_NAME_ACTUAL": "test_relation.xml",
            # Add other config values if your function expects them
        }

        # Initialize the mock state
        initial_state = MockRobotFlowAgentState(
            parsed_flow_steps=test_data_json, 
            config=mock_config
        )

        # Configure logging for the test run to see output
        logging.basicConfig(level=logging.DEBUG) # Changed to DEBUG to see detailed logs
        # Suppress other loggers if they are too verbose for the test
        # logging.getLogger("some_other_module").setLevel(logging.WARNING)

        logger.info("Starting test run for generate_relation_xml_node...")
        
        # Run the node function
        # The second argument to generate_relation_xml_node (llm) is optional and defaults to None in the modified function
        final_state = await generate_relation_xml_node(initial_state)

        if final_state.is_error:
            logger.error(f"Test run failed. Error: {final_state.error_message}")
            print(f"Test run failed. Error: {final_state.error_message}")
            if final_state.relation_xml_content:
                print("--- Partial/Error XML Content ---")
                print(final_state.relation_xml_content)
                print("---------------------------------")
        else:
            logger.info(f"Test run successful. Relation XML generated at: {final_state.relation_xml_path}")
            print(f"Test run successful. Relation XML generated at: {final_state.relation_xml_path}")
            if final_state.relation_xml_content:
                print("--- Generated XML Content ---")
                print(final_state.relation_xml_content)
                print("-----------------------------")
        
        # print(f"Reminder: Test output (if any) is in {temp_output_dir}. You might want to delete it manually.") # No longer a temp dir
        logger.info(f"Test output saved to {final_state.relation_xml_path if final_state else 'N/A'}")

    # Run the async main_test function
    asyncio.run(main_test()) 