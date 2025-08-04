import sys
from pathlib import Path
_FILE_PATH_FOR_PREAMBLE = Path(__file__).resolve()
if __name__ == "__main__" and __package__ is None:
    # This script is in: backend/sas/nodes/generate_relation_xml.py
    # The project root is /workspace, which is 4 levels up from the script's directory.
    _project_root_for_preamble = _FILE_PATH_FOR_PREAMBLE.parents[4] # Should resolve to /workspace
    sys.path.insert(0, str(_project_root_for_preamble))
    import os # os.sep is used here for platform-independent path component replacement
    # Set __package__ to the expected package string, e.g., backend.sas.nodes
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

def _extract_block_info_from_detail(detail_string: str) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    Extracts block type, disabled status, and mutation name if applicable for procedures_callnoreturn.
    Example: "1. Select robot (Block Type: `select_robot`)"
    Example disabled: "2. Wait for I/O (Block Type: `wait_io`) (This block is disabled)"
    Example call: "3. Call Procedure XYZ (Block Type: `procedures_callnoreturn`, Mutation Name: `XYZ`)"
    """
    disabled = "(This block is disabled)" in detail_string
    block_type = None
    mutation_name = None # For procedures_callnoreturn

    # Regex for block type
    type_match = re.search(r"(Block Type: `([^`]+)`)", detail_string) # Group 2 is the type
    if type_match:
        block_type = type_match.group(2)
    
    if block_type == "procedures_callnoreturn":
        # Priority 1: Match "Call sub-program \"PROC_NAME\""
        call_sub_program_match = re.search(r"Call sub-program \"([^\"]+)\"", detail_string)
        if call_sub_program_match:
            mutation_name = call_sub_program_match.group(1)
            # XML escaping for characters like '&' to '&amp;' is handled by ET.SubElement for attribute values
            logger.debug(f"Extracted mutation name (from Call sub-program): {mutation_name} for call block.")
        else:
            # Priority 2: Match "(Mutation Name: `PROC_NAME`)" or "(Calls: `PROC_NAME`)"
            legacy_mutation_match = re.search(r"\((?:Mutation Name|Calls): `([^`]+)`\)", detail_string)
            if legacy_mutation_match:
                mutation_name = legacy_mutation_match.group(1)
                logger.debug(f"Extracted mutation name (from legacy pattern): {mutation_name} for call block.")
            else:
                logger.warning(f"Could not extract mutation name for procedures_callnoreturn from detail: {detail_string}")
    
    return block_type, disabled, mutation_name

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
    state.current_step_description = "Generating node relation XML file(s) (Rule-based)"
    state.is_error = False
    # The line 'state.generated_relation_files: List[GeneratedXmlFile] = []' is intentionally removed here.

    config = state.config
    parsed_flow_steps = state.parsed_flow_steps

    if not parsed_flow_steps:
        logger.warning("Parsed flow steps are missing. Generating a single empty relation XML.")
        empty_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
        state.relation_xml_content = empty_xml_content
        state.relation_xml_path = "" # Path will be set if file is successfully written

        output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
        # This will be the name for the single empty XML if parsed_flow_steps is empty.
        relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml") 
        relation_file_path = output_dir / relation_file_name
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(relation_file_path, "w", encoding="utf-8") as f:
                f.write(empty_xml_content)
            
            state.relation_xml_path = str(relation_file_path) 
            logger.info(f"Successfully wrote empty relation XML to {relation_file_path}")

        except IOError as e:
            logger.error(f"Failed to write empty relation XML to {relation_file_path}: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Failed to write empty relation XML: {e}"
            state.dialog_state = "error"
            state.completion_status = "error"
            # Error state will be returned at the end of the function
    else:
        num_tasks = len(parsed_flow_steps)
        processed_at_least_one_file_successfully = False
        for task_index, current_task_data in enumerate(parsed_flow_steps):
            task_name = current_task_data.get('name', f'Task_{task_index + 1}')
            logger.info(f"Processing task [{task_index + 1}/{num_tasks}]: '{task_name}' for relation XML.")
            task_details = current_task_data.get("details", [])
            
            current_task_xml_content: str
            xml_doc_root = ET.Element("xml", xmlns="https://developers.google.com/blockly/xml")
            block_id_counter = 1 # IDs for blocks start from 1 for each task file.

            parent_for_block_sequence: ET.Element # Will be set differently based on task type and logic
            is_main_task_type = current_task_data.get("type") == "MainTask"

            # For sub-tasks, this will store the identified definition block once found in details
            proc_def_block_identified_for_sub_task: Optional[ET.Element] = None
            
            # Initialize parent_stack. For sub-tasks, it's initially empty until definition is found.
            parent_stack: List[ET.Element]
            if is_main_task_type:
                logger.info(f"Task '{task_name}' is MAIN TASK type. Blocks will be children of <xml>.")
                parent_stack = [xml_doc_root]
            else: # Sub-procedure
                logger.info(f"Task '{task_name}' is SUB-PROCEDURE type. Definition expected from details.")
                parent_stack = [] # Will be populated once proc_def_block_identified_for_sub_task is set
            
            if not task_details:
                if is_main_task_type:
                    logger.warning(f"Main task '{task_name}' has no details. XML will be <xml />.")
                else: # sub-procedure - without details, it won't have a definition from details
                    logger.warning(f"Sub-procedure '{task_name}' has no details. It will likely result in an empty <xml /> or an error if definition is mandatory.")
                    # If a sub-procedure has no details, it effectively cannot be defined by this new logic.
                    # We might need a default empty proc_def here, or ensure details are never empty for sub-procs that need definition.
                    # For now, it will result in an empty xml_doc_root if not handled later.
                current_task_xml_content = _format_xml(xml_doc_root)
            else:
                # parent_stack is initialized above.
                # last_block_at_depth keys are 0-based depth relative to the start of parent_stack[-1].
                last_block_at_depth: Dict[int, Optional[ET.Element]] = {0: None} 
                current_processing_relative_depth = 0 # Depth relative to the initial parent_for_block_sequence

                for idx, detail_str in enumerate(task_details):
                    block_type, is_disabled, mutation_name = _extract_block_info_from_detail(detail_str)
                    if not block_type or is_disabled:
                        logger.debug(f"  Skipping detail for task '{task_name}': No block type ('{block_type}') or disabled ({is_disabled}).")
                        continue

                    current_block_id = f"sas_rel_block_{block_id_counter}"
                    # block_id_counter will be incremented after this block is potentially created.

                    # New logic for handling procedures_defnoreturn from details for SUB-TASKS
                    if not is_main_task_type and block_type == "procedures_defnoreturn":
                        if proc_def_block_identified_for_sub_task is None:
                            logger.info(f"  Task '{task_name}': Found defining 'procedures_defnoreturn' detail: \"{detail_str}\"")
                            # This detail IS the definition block
                            current_xml_element = ET.Element("block", type="procedures_defnoreturn", id=current_block_id)
                            ET.SubElement(current_xml_element, "field", name="NAME").text = task_name
                            xml_doc_root.append(current_xml_element) # Definition is child of <xml>
                            proc_def_block_identified_for_sub_task = current_xml_element
                            
                            # Create its STACK and set up parent_stack for its contents
                            statement_for_def = ET.SubElement(proc_def_block_identified_for_sub_task, "statement", name="STACK")
                            parent_stack = [statement_for_def]
                            current_processing_relative_depth = 0
                            last_block_at_depth = {0: None} # Reset for the new STACK
                            block_id_counter += 1 # ID consumed by the definition block
                            continue # Move to the next detail, which should be the first step IN this STACK
                        else:
                            logger.warning(
                                f"  Task '{task_name}': Encountered a subsequent 'procedures_defnoreturn' detail: \"{detail_str}\". "
                                f"Skipping as a definition is already identified."
                            )
                            continue
                    
                    # Check if parent_stack is valid for adding blocks, especially for sub-tasks
                    if not parent_stack: # Handles sub-tasks before their definition is found
                        if not is_main_task_type:
                            logger.error(
                                f"  Task '{task_name}' (Sub-procedure): Trying to process step \"{detail_str}\" "
                                f"but its 'procedures_defnoreturn' definition has not been identified from details yet. Skipping this step."
                            )
                            continue
                        else: # Should not happen for MainTask as parent_stack is initialized
                            logger.error(f"  Task '{task_name}' (MainTask): parent_stack is unexpectedly empty. Skipping step \"{detail_str}\".")
                            continue
                            
                    # Create the current block if it's not a definitional procedures_defnoreturn handled above
                    current_xml_element = ET.Element("block", type=block_type, id=current_block_id)
                    block_id_counter += 1

                    if block_type == "procedures_callnoreturn" and mutation_name:
                        ET.SubElement(current_xml_element, "mutation", name=mutation_name)
                    
                    # Determine where to attach current_xml_element
                    active_parent_statement_or_root = parent_stack[-1] 
                    
                    previous_block_this_level = last_block_at_depth.get(current_processing_relative_depth)

                    if previous_block_this_level is not None:
                        next_tag = ET.SubElement(previous_block_this_level, "next")
                        next_tag.append(current_xml_element)
                    else:
                        # First block in active_parent_statement_or_root or first block in a new (e.g. loop's) statement
                        active_parent_statement_or_root.append(current_xml_element)
                    
                    last_block_at_depth[current_processing_relative_depth] = current_xml_element

                    # Handle blocks that introduce new scopes and thus new <statement> tags
                    if block_type == "loop":
                        statement_tag = ET.SubElement(current_xml_element, "statement", name="DO")
                        parent_stack.append(statement_tag)
                        current_processing_relative_depth += 1
                        last_block_at_depth[current_processing_relative_depth] = None # Reset for the new scope
                    elif block_type == "controls_if": 
                        # Assuming only DO0, no ELSE/ELSEIF from current details
                        statement_tag = ET.SubElement(current_xml_element, "statement", name="DO0")
                        parent_stack.append(statement_tag)
                        current_processing_relative_depth += 1
                        last_block_at_depth[current_processing_relative_depth] = None # Reset for the new scope
                    # Removed the specific stack pop logic for block_type == "return"
                
                current_task_xml_content = _format_xml(xml_doc_root)

            output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
            base_relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
            
            name_part, ext_part = os.path.splitext(base_relation_file_name)
            sanitized_task_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', task_name) 
            task_specific_file_name = f"{name_part}_{sanitized_task_name}_taskidx{task_index}{ext_part if ext_part else '.xml'}"
            
            relation_file_path_for_task = output_dir / task_specific_file_name
            
            try:
                os.makedirs(output_dir, exist_ok=True)
                with open(relation_file_path_for_task, "w", encoding="utf-8") as f:
                    f.write(current_task_xml_content)
                
                logger.info(f"Successfully wrote relation XML for task '{task_name}' to {relation_file_path_for_task}.")
                
                # Update state to reflect the latest successfully written file
                state.relation_xml_content = current_task_xml_content
                state.relation_xml_path = str(relation_file_path_for_task)
                processed_at_least_one_file_successfully = True

            except IOError as e:
                logger.error(f"Failed to write relation XML for task '{task_name}' to {relation_file_path_for_task}: {e}", exc_info=True)
                state.is_error = True
                state.error_message = f"Failed to write relation XML for task '{task_name}': {e}"
                state.dialog_state = "error"
                state.completion_status = "error"
                return state # Exit immediately if a file write fails in the loop
        
        if not processed_at_least_one_file_successfully and parsed_flow_steps:
             logger.warning("Loop over tasks completed, but no files were successfully processed/written.")
             # Set to default empty if no file was processed, even if there were tasks
             state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
             state.relation_xml_path = ""

    # Final state updates based on whether an error occurred anywhere
    if not state.is_error: 
        state.dialog_state = "generating_xml_final"
        state.completion_status = None # Explicitly None if no error
    else:
        # Ensure dialog_state and completion_status reflect error if not already set by specific error points
        if state.dialog_state != "error": # Avoid overwriting more specific error states if already set
             state.dialog_state = "error"
        if state.completion_status != "error":
             state.completion_status = "error"
             
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
            self.completion_status: Optional[str] = None
            self.relation_xml_content: Optional[str] = None 
            self.relation_xml_path: Optional[str] = None    
            # The field 'self.generated_relation_files' is intentionally removed here.
            self.generated_node_xmls: Optional[List[Any]] = [] 
            # Add pydantic BaseModel for proper model_dump if tasks are TaskDefinition instances
            # from pydantic import BaseModel # Already imported globally for RobotFlowAgentState

    async def main_test():
        from pydantic import BaseModel # Required if TaskDefinition objects are used and need model_dump

        script_dir = Path(__file__).parent.resolve()
        # Path to the test JSON file that contains a dictionary, where tasks are in "parsed_flow_steps"
        # test_json_path = script_dir.parent.parent.parent.parent.parent / "tests" / "llm_sas_test" / "run_20250609_071825_821008" / "sas_step2_module_steps_iter2.json"
        # Updated test path as per user request
        project_root_dir = script_dir.parents[3] # backend/sas/nodes -> /workspace
        test_json_path = project_root_dir / "backend" / "tests" / "llm_sas_test" / "1_sample" / "step2_output_sample.json"


        if not test_json_path.exists():
            logger.error(f"Test JSON file not found at: {test_json_path}")
            print(f"Error: Test JSON file not found at: {test_json_path}")
            return

        try:
            with open(test_json_path, 'r', encoding='utf-8') as f:
                test_data_from_file = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from {test_json_path}: {e}")
            print(f"Error: Failed to decode JSON from {test_json_path}: {e}")
            return
        
        test_data_json_list: List[Dict[str, Any]] = []
        if isinstance(test_data_from_file, list):
            logger.info("Test JSON is a direct list of tasks.")
            test_data_json_list = test_data_from_file
        elif isinstance(test_data_from_file, dict):
            logger.info("Test JSON is a dictionary. Looking for task list under known keys.")
            if "parsed_flow_steps" in test_data_from_file and isinstance(test_data_from_file["parsed_flow_steps"], list):
                test_data_json_list = test_data_from_file["parsed_flow_steps"]
                logger.info(f"Found {len(test_data_json_list)} tasks under 'parsed_flow_steps'.")
            elif "sas_step1_generated_tasks" in test_data_from_file and isinstance(test_data_from_file["sas_step1_generated_tasks"], list):
                logger.info("Found tasks under 'sas_step1_generated_tasks'. Converting to dicts if they are Pydantic models.")
                # Assuming TaskDefinition is a Pydantic model, use model_dump()
                # If it's already a dict, this will handle it.
                processed_tasks = []
                for task_item in test_data_from_file["sas_step1_generated_tasks"]:
                    if hasattr(task_item, 'model_dump') and callable(getattr(task_item, 'model_dump')): # Check if it's a Pydantic model
                        processed_tasks.append(task_item.model_dump())
                    elif isinstance(task_item, dict):
                        processed_tasks.append(task_item)
                    else:
                        logger.warning(f"Skipping an item in 'sas_step1_generated_tasks' as it is not a Pydantic model or dict: {type(task_item)}")
                test_data_json_list = processed_tasks
                logger.info(f"Processed {len(test_data_json_list)} tasks from 'sas_step1_generated_tasks'.")
            elif "name" in test_data_from_file and "details" in test_data_from_file: # Heuristic for single task dict not in a list
                 logger.info("Test JSON seems to be a single task object (not in a list); wrapping it.")
                 test_data_json_list = [test_data_from_file]
            else:
                logger.error(f"Test JSON (dict) at {test_json_path} does not have a known task list key (e.g., 'parsed_flow_steps', 'sas_step1_generated_tasks'). Found keys: {list(test_data_from_file.keys())}")
                print(f"Error: Test JSON (dict) at {test_json_path} is not in a recognized list-of-tasks format.")
                return 
        else:
            logger.error(f"Test JSON data at {test_json_path} is not a list or a recognized dict structure. Type: {type(test_data_from_file)}")
            print(f"Error: Test JSON data at {test_json_path} is not a list or recognized dict.")
            return
        
        if not test_data_json_list: # Check after all processing
            logger.warning(f"After processing, test_data_json_list from {test_json_path} is empty. Test might not produce new files if it relies on these tasks.")

        # Using a new directory for this test iteration
        fixed_output_dir_str = "backend/tests/llm_sas_test/1_sample_multi_relation_v2"
        output_dir = Path(fixed_output_dir_str) 

        try:
            os.makedirs(output_dir, exist_ok=True)
            # Optional: Clean up old files in the directory for a fresh test run
            # for item in output_dir.iterdir():
            #     if item.is_file() and item.name.startswith(os.path.splitext(mock_config["RELATION_FILE_NAME_ACTUAL"])[0]):
            #         item.unlink()
            logger.info(f"Test output will be saved in: {output_dir.resolve()} (relative to script: {output_dir})") # Added relative path for clarity
            print(f"Test output directory: {output_dir.resolve()}")
        except OSError as e:
            logger.error(f"Could not create output directory {output_dir}: {e}")
            print(f"Error: Could not create output directory {output_dir}: {e}")
            return

        mock_config = {
            "OUTPUT_DIR_PATH": str(output_dir), 
            "RELATION_FILE_NAME_ACTUAL": "relation_base.xml", # Base name for generated files
        }

        initial_state = MockRobotFlowAgentState(
            parsed_flow_steps=test_data_json_list, 
            config=mock_config
        )

        logger.info(f"Starting test run for generate_relation_xml_node (multi-task file output) with {len(initial_state.parsed_flow_steps)} task(s) queued...")
        
        final_state = await generate_relation_xml_node(initial_state) # type: ignore

        if final_state.is_error:
            logger.error(f"Test run failed. Error: {final_state.error_message}")
            print(f"Test run failed. Error: {final_state.error_message}")
            if final_state.relation_xml_content: 
                print("--- XML Content (Last Attempted or Error Placeholder) ---")
                print(final_state.relation_xml_content)
                print("------------------------------------------------------")
        else:
            logger.info(f"Test run completed. Output files should be in: {mock_config['OUTPUT_DIR_PATH']}")
            print(f"Test run completed. Output files should be in: {mock_config['OUTPUT_DIR_PATH']}")
            if final_state.relation_xml_path:
                logger.info(f"  Last generated relation XML path: {final_state.relation_xml_path}")
                print(f"  Last generated relation XML path: {final_state.relation_xml_path}")
                # Optionally print content of the last file
                # print("  --- Content of Last Generated XML ---")
                # print(final_state.relation_xml_content)
                # print("  -----------------------------------")
            else:
                logger.warning("  No specific relation_xml_path was set in the final state. This is expected if parsed_flow_steps was empty, or if all tasks resulted in empty/no XML output and no files were written.")
            
            print(f"Please check the directory '{output_dir.resolve()}' for generated files.")
            try:
                base_name_for_check = os.path.splitext(mock_config["RELATION_FILE_NAME_ACTUAL"])[0]
                created_files = [name for name in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, name)) and name.startswith(base_name_for_check)]
                num_files_created = len(created_files)
                logger.info(f"Found {num_files_created} file(s) matching base name '{base_name_for_check}' in output directory: {created_files}")
                print(f"Found {num_files_created} file(s) matching base name '{base_name_for_check}' in output directory.")
            except Exception as e:
                logger.error(f"Could not list or count files in output directory: {e}")

        logger.info(f"Test output (if any) saved to directory: {mock_config['OUTPUT_DIR_PATH']}")

    asyncio.run(main_test()) 