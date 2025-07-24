import logging
import json
import os
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable
import xml.etree.ElementTree as ET
import xml.dom.minidom
import uuid # Added for UUID generation
import sys # Added for sys.path modification

# LLM-related imports are removed as LLM is no longer used.

# Helper function to clean namespace URI from element tags recursively
def _clean_namespace_from_tags(element, namespace_uri_to_clean):
    if element is None:
        return
    # Clean the current element's tag
    if '}' in element.tag and element.tag.startswith(f'{{{namespace_uri_to_clean}}}'):
        element.tag = element.tag.split('}', 1)[1]
    
    # Recursively clean children's tags
    for child in element:
        _clean_namespace_from_tags(child, namespace_uri_to_clean)

# Conditional import for direct script execution vs. package import
if __name__ == "__main__" and __package__ is None:
    # This allows the script to be run directly for testing,
    # by adding the project root to sys.path and setting __package__.
    file_path_for_preamble = Path(__file__).resolve()
    print(f"[Preamble] Attempting to set up for direct execution. Script path: {file_path_for_preamble}") 

    # Assuming the script is in: backend/sas/nodes/generate_individual_xmls.py
    # The project root /workspace is 4 levels up.
    project_root_for_preamble = file_path_for_preamble.parents[4] 
    print(f"[Preamble] Calculated project root: {project_root_for_preamble}")

    if str(project_root_for_preamble) not in sys.path:
        sys.path.insert(0, str(project_root_for_preamble))
        print(f"[Preamble] Added to sys.path: {project_root_for_preamble}")
    else:
        print(f"[Preamble] Already in sys.path: {project_root_for_preamble}")

    # Set __package__ to allow relative imports like ..state to work correctly.
    # The package is the dot-separated path from the project root to the current file's parent directory.
    try:
        relative_script_parent_dir = file_path_for_preamble.parent.relative_to(project_root_for_preamble)
        # Convert path to package string (e.g., backend/langgraphchat/.../nodes -> backend.langgraphchat....nodes)
        calculated_package = str(relative_script_parent_dir).replace(os.sep, '.')
        __package__ = calculated_package
        print(f"[Preamble] __package__ set to: '{__package__}'") 
    except ValueError as e_pkg:
        print(f"[Preamble] Error setting __package__: {e_pkg}. This might happen if project_root calculation is incorrect.")
        # If __package__ cannot be set, relative imports might still fail.

from ..state import RobotFlowAgentState, GeneratedXmlFile, TaskDefinition 
# prompt_loader and llm_utils imports are removed.

logger = logging.getLogger(__name__)

def _extract_block_type_from_detail(detail_string: str) -> Optional[str]:
    """
    Extracts block type from detail string.
    Attempts to find explicit (Block Type: `...`) pattern first.
    Falls back to keyword-based matching for common block types.
    """
    # Regex for explicit block type: (Block Type: `block_type_value`)
    # The first capturing group (index 1) will be the block_type_value.
    type_match = re.search(r"\(Block Type: `([^`]+)`\)", detail_string) 
    if type_match:
        return type_match.group(1) 
    
    # Fallback to keyword-based extraction if explicit pattern is not found
    detail_lower = detail_string.lower()
    # Order more specific checks before general ones to avoid incorrect matching
    if "select robot" in detail_lower: return "select_robot"
    if "set motor" in detail_lower: return "set_motor"
    if "movep" in detail_lower or "move p" in detail_lower : return "moveP"
    # Make loop detection more specific to avoid conflict with "loop until" or "loop while"
    if "loop" in detail_lower and not any(kw in detail_lower for kw in ["until", "while", "condition"]) : return "loop"
    if "if" in detail_lower : return "controls_if" # Basic if
    if "call sub-program" in detail_lower or "call procedure" in detail_lower: return "procedures_callnoreturn"
    if "set output" in detail_lower: return "set_output"
    if "wait input" in detail_lower: return "wait_input"
    if "wait timer" in detail_lower: return "wait_timer"
    if "return" in detail_lower and not any(kw in detail_lower for kw in ["select", "set", "move", "loop", "if", "call", "wait"]):
        # Ensure 'return' is likely the primary action and not part of another block's description
        return "return"

    logger.warning(f"Could not reliably extract block type from detail string: {detail_string}")
    return None

def _extract_parameters_from_detail(detail_string: str, block_type: str) -> Dict[str, Any]:
    """
    Returns a dictionary of DEFAULT parameters based on the block_type.
    The detail_string is largely ignored for value extraction, focusing on defaults.
    An exception is made for procedure names (defnoreturn, callnoreturn) which will
    still attempt to be extracted from detail_string or given a unique placeholder.
    """
    params = {'fields': {}, 'mutations': {}}
    detail_lower = detail_string.lower() # Keep for procedure name extraction
    logger.debug(f"Generating mostly default parameters for block_type: {block_type} (detail: '{detail_string}' used sparingly)")

    if block_type == "moveP":
        params['fields'] = {
            'point_name_list': 'P1',       # Default from template
            'control_x': 'enable',         # Default from template
            'control_y': 'enable',         # Default from template
            'control_z': 'enable',         # Default from template
            'control_rx': 'enable',        # Default from template
            'control_ry': 'enable',        # Default from template
            'control_rz': 'enable',        # Default from template
            'pallet_list': 'none',         # Default from template
            'camera_list': 'none'          # Default from template
        }
        params['mutations'] = {
            'timeout': '60000000'       # Default from template
        }
        logger.info(f"Using default parameters for moveP: {params}")

    elif block_type == "set_speed":
        params['fields'] = {
            'speed': '100'               # Default from template
        }
        params['mutations'] = {
            'timeout': '-1'                # Default from template (as observed in examples)
        }
        logger.info(f"Using default parameters for set_speed: {params}")

    elif block_type == "procedures_callnoreturn":
        logger.info("--- Debug procedures_callnoreturn ---")
        logger.info(f"Processing detail_string: '{detail_string}'")

        proc_name = None
        # Priority 1: Match "Call sub-program \\"PROC_NAME\\"" (case-insensitive for keywords)
        # Target Python re: r"(?:^|\\d+\\.\\s+)Call sub-program \\"([^\\"]+)\\""
        call_match = re.search(r'(?:^|\d+\.\s+)Call sub-program "([^"]+)"', detail_string, re.IGNORECASE)
        if call_match:
            extracted_name_modern = call_match.group(1).strip()
            logger.info(f"Modern pattern matched. Extracted name: '{extracted_name_modern}'")
            proc_name = extracted_name_modern
        else:
            logger.info(f"Modern pattern DID NOT match for: '{detail_string}'")
            # Priority 2: Match "(Mutation Name: `PROC_NAME`)" or "(Calls: `PROC_NAME`)" (case-insensitive)
            # Target Python re: r"\\((?:Mutation Name|Calls)\\s*:\\s*\\`([^\\`]+)\\`\\)"
            legacy_match = re.search(r"\\((?:Mutation Name|Calls)\\s*:\\s*\\`([^\\`]+)\\`\\)", detail_string, re.IGNORECASE)
            if legacy_match:
                extracted_name_legacy1 = legacy_match.group(1).strip()
                logger.info(f"Legacy pattern 1 matched. Extracted name: '{extracted_name_legacy1}'")
                proc_name = extracted_name_legacy1
            else:
                logger.info(f"Legacy pattern 1 DID NOT match for: '{detail_string}'")
                # Simpler legacy pattern check
                # Target Python re: r"\\((?:Mutation Name|Calls): \\`([^\\`]+)\\`\\)"
                legacy_match_simplified = re.search(r"\\((?:Mutation Name|Calls): \\`([^\\`]+)\\`\\)", detail_string, re.IGNORECASE)
                if legacy_match_simplified:
                    extracted_name_legacy2 = legacy_match_simplified.group(1).strip()
                    logger.info(f"Legacy pattern 2 matched. Extracted name: '{extracted_name_legacy2}'")
                    proc_name = extracted_name_legacy2
                else:
                    logger.info(f"Legacy pattern 2 DID NOT match for: '{detail_string}'")

        logger.info(f"Determined proc_name before default assignment: '{proc_name}'")

        if proc_name:
            params['mutations'] = {'name': proc_name.replace('&', '&amp;')}
        else:
            default_name = f"UnnamedProcedure_CALL_{str(uuid.uuid4())[:4]}"
            logger.warning(f"Could not extract procedure call name from: '{detail_string}'. Using default: '{default_name}'")
            params['mutations'] = {'name': default_name}
        
        logger.info(f"Final parameters for procedures_callnoreturn: {params}")
        logger.info("--- End Debug procedures_callnoreturn ---")

    elif block_type == "procedures_defnoreturn":
        # The 'NAME' field for procedures_defnoreturn will be set by the calling function (generate_individual_xmls_node)
        # using task_data.get('name'). This function will only set other potential default parameters if any.
        logger.info(f"Parameters for procedures_defnoreturn (name to be set by caller based on task_name): {params}")
        # Example: If there were other default mutations/fields for defnoreturn, they'd be set here.
        # params['mutations'] = {'some_other_default_mutation': 'value'}

    elif block_type == "return":
        # return 类型的块不需要参数，使用模板的默认结构即可
        logger.info(f"return block type detected - no parameters needed, using template defaults: {params}")

    # Add other block types and their fixed default parameters here as needed.
    # Example:
    # elif block_type == "select_robot":
    #     params['fields'] = {'robotName': 'dobot_mg400'}
    #     params['mutations'] = {'timeout': '-1'}
    #     logger.info(f"Using default parameters for select_robot: {params}")

    else:
        logger.warning(f"No specific default parameter logic in _extract_parameters_from_detail for block_type: '{block_type}'. XML will rely solely on template structure if no params are set.")

    if not params['fields'] and not params['mutations'] and block_type not in ["procedures_defnoreturn", "return"]: # defnoreturn might only have a name field, return uses template defaults
         logger.debug(f"No default parameters explicitly set for block_type: '{block_type}'. Template defaults will be primary.")
    else:
        logger.debug(f"Final default/extracted parameters for '{block_type}': {params}")
        
    return params

async def _generate_xml_from_template(
    block_type: str,
    target_block_id: str, 
    data_block_no_in_task: str,   
    node_template_dir_str: str,
    source_description: str, 
    parameters: Dict[str, Any], 
    get_next_nested_block_data_no_func: Callable[[], str], # NEW: Function to get next data-blockNo for nested blocks
    x_coord: Optional[str] = None, 
    y_coord: Optional[str] = None  
) -> GeneratedXmlFile:
    """
    Loads an XML template based on block_type, sets its id and data-blockNo attributes,
    and returns a GeneratedXmlFile object containing the modified XML string or error info.
    """
    template_file_path = Path(node_template_dir_str) / f"{block_type}.xml"
    
    # Initialize GeneratedXmlFile entry for this block attempt
    generated_xml_file_entry = GeneratedXmlFile(
        block_id=target_block_id,
        type=block_type,
        source_description=source_description,
        status="failure", # Default to failure, update on success
        xml_content=None,
        file_path=None,
        error_message=None
    )

    logger.debug(f"Attempting to generate XML for block_id: {target_block_id}, type: {block_type}")
    logger.debug(f"  Template path: {template_file_path}")
    logger.debug(f"  Received parameters: {json.dumps(parameters, indent=2)}")

    try:
        with open(template_file_path, 'r', encoding='utf-8') as f:
            template_content = f.read().strip() # Read and strip whitespace
            if template_content.startswith('\ufeff'): # Handle potential BOM
                template_content = template_content[1:]
    except FileNotFoundError:
        generated_xml_file_entry.error_message = f"Node template file not found: {template_file_path}"
        logger.error(generated_xml_file_entry.error_message)
        return generated_xml_file_entry
    except Exception as e:
        generated_xml_file_entry.error_message = f"Error reading node template file {template_file_path}: {e}"
        logger.error(generated_xml_file_entry.error_message, exc_info=True)
        return generated_xml_file_entry

    try:
        # Parse the XML template string. Assumes template is a single <block>...</block> element,
        # or <xml><block>...</block></xml>.
        xml_block_element = ET.fromstring(template_content)

        # Check if the root tag is the namespaced <xml> or a simple <xml>
        if xml_block_element.tag == '{https://developers.google.com/blockly/xml}xml' or xml_block_element.tag == 'xml':
            # Try to find a 'block' element, ignoring namespaces for the 'block' tag itself for simplicity.
            # This uses a wildcard for the namespace of 'block': '{*}block'
            # Or a direct find if no namespace is on 'block': 'block'
            found_block = xml_block_element.find('.//{*}block') # General case for namespaced block
            if found_block is None: # Fallback if block has no namespace
                 found_block = xml_block_element.find('.//block')

            if found_block is not None:
                xml_block_element = found_block
            else:
                raise ValueError(f"Template with <xml> root (namespaced or not) does not contain a <block> element. Path: {template_file_path}")
        # Check if the root tag is the namespaced <block> or a simple <block>
        elif xml_block_element.tag != '{https://developers.google.com/blockly/xml}block' and xml_block_element.tag != 'block':
            raise ValueError(f"Template is not a <block> element (namespaced or not) nor an <xml> wrapper containing a <block>. Root tag: '{xml_block_element.tag}'. Path: {template_file_path}")

        # Set the globally unique ID for this block instance
        xml_block_element.set('id', target_block_id)
        
        # Set the data-blockNo attribute for this block instance (its 1-based index within its task)
        xml_block_element.set('data-blockNo', data_block_no_in_task)
        
        # NEW: Add x and y coordinates if provided
        if x_coord is not None:
            xml_block_element.set('x', x_coord)
            logger.info(f"  Applied x_coord='{x_coord}' to block ID {target_block_id}")
        if y_coord is not None:
            xml_block_element.set('y', y_coord)
            logger.info(f"  Applied y_coord='{y_coord}' to block ID {target_block_id}")
        
        # NEW: Apply extracted parameters to fields and mutations
        if parameters:
            # Apply field values
            if 'fields' in parameters and parameters['fields']:
                for field_name, field_value in parameters['fields'].items():
                    # Use namespace wildcard {*} to find the field element
                    field_element = xml_block_element.find(f"./{{*}}field[@name='{field_name}']") 
                    if field_element is not None:
                        logger.debug(f"  Found field '{field_name}' in template for block ID {target_block_id}. Current text: '{field_element.text}'")
                        field_element.text = str(field_value) # Ensure value is string
                        logger.info(f"  Applied field '{field_name}' = '{field_value}' to block ID {target_block_id}. New text: '{field_element.text}'")
                    else:
                        logger.warning(f"Field '{field_name}' not found in template for block ID {target_block_id}, type {block_type}. Path: {template_file_path}")
            
            # Apply mutation attributes
            if 'mutations' in parameters and parameters['mutations']:
                mutation_element = xml_block_element.find("./{*}mutation") # Mutation is usually a direct child
                if mutation_element is not None:
                    for attr_name, attr_value in parameters['mutations'].items():
                        mutation_element.set(attr_name, str(attr_value)) # Ensure value is string
                        logger.debug(f"Applied mutation attribute '{attr_name}' = '{attr_value}' to block ID {target_block_id}")
                elif parameters['mutations']: # Only warn if there were mutations to apply but no <mutation> tag
                    logger.warning(f"<mutation> element not found in template for block ID {target_block_id}, type {block_type}, but mutation parameters were provided: {parameters['mutations']}. Path: {template_file_path}")

        # NEW: Randomize IDs of all nested <block> elements within this main block
        # The main block's ID (target_block_id) is already set and should not be changed here.
        # We find all <block> elements that are descendants of the current xml_block_element.
        if xml_block_element is not None: # Ensure xml_block_element is valid
            nested_blocks = xml_block_element.findall('.//{*}block') # Finds all descendant blocks
            if nested_blocks:
                logger.debug(f"Found {len(nested_blocks)} nested block(s) for block ID {target_block_id}. Randomizing their IDs and setting data-blockNo.")
                for nested_block_element in nested_blocks:
                    new_nested_id = str(uuid.uuid4())
                    nested_block_element.set('id', new_nested_id)
                    
                    # NEW: Set data-blockNo for nested block using the provided function
                    new_nested_data_block_no = get_next_nested_block_data_no_func()
                    nested_block_element.set('data-blockNo', new_nested_data_block_no)
                    logger.info(f"  Nested block (type: {nested_block_element.get('type')}): ID set to '{new_nested_id}', data-blockNo set to '{new_nested_data_block_no}'")
            else:
                logger.debug(f"No nested blocks found for block ID {target_block_id}.")

        blockly_namespace_uri = "https://developers.google.com/blockly/xml"
        
        # Recursively clean the Blockly namespace URI from the tags of xml_block_element and its children
        _clean_namespace_from_tags(xml_block_element, blockly_namespace_uri)

        # Register the Blockly namespace with an empty prefix to make it the default (xmlns="...")
        # This affects how ET.tostring will serialize elements from this namespace.
        ET.register_namespace("", blockly_namespace_uri) 
        
        # Create the <xml> wrapper element *in the Blockly namespace*.
        # Its tag will be '{https://developers.google.com/blockly/xml}xml'.
        # When serialized with the registered namespace, it becomes <xml xmlns="...">.
        root_xml_wrapper = ET.Element(f"{{{blockly_namespace_uri}}}xml")
        
        # Append the prepared <block> element (e.g., xml_block_element.tag is 'block')
        # as a child of the namespaced <xml> wrapper.
        # The <block> and its children will inherit the default namespace.
        root_xml_wrapper.append(xml_block_element)
        
        # Convert the new root_xml_wrapper to an XML string.
        final_xml_block_string = ET.tostring(root_xml_wrapper, encoding='unicode', method="xml")
        
        # Remove the XML declaration (e.g., <?xml version="1.0"?>) if ElementTree added one.
        # This is because the calling function (generate_individual_xmls_node)
        # explicitly adds a specific XML declaration before writing the content to a file.
        final_xml_block_string = re.sub(r"^<\?xml.*?\?>\\s*", "", final_xml_block_string).strip()

        generated_xml_file_entry.xml_content = final_xml_block_string
        generated_xml_file_entry.status = "success"

    except ET.ParseError as pe:
        generated_xml_file_entry.error_message = f"XML ParseError for template {template_file_path}: {pe}. Content hint: {template_content[:200]}..."
        logger.error(generated_xml_file_entry.error_message)
    except ValueError as ve: # From custom validation (e.g., no <block> found)
        generated_xml_file_entry.error_message = str(ve)
        logger.error(generated_xml_file_entry.error_message)
    except Exception as e:
        generated_xml_file_entry.error_message = f"Unexpected error processing template {template_file_path}: {e}"
        logger.error(generated_xml_file_entry.error_message, exc_info=True)
    
    return generated_xml_file_entry

async def generate_individual_xmls_node(state: RobotFlowAgentState, llm: Optional[Any] = None) -> RobotFlowAgentState:
    # llm parameter is no longer used but kept for signature compatibility if other nodes expect it.
    logger.info("--- Running Step 2: Generate Independent Node XMLs (Template-based) ---")    
    state.current_step_description = "Generating individual XML block files from templates for each task detail"
    state.is_error = False
    state.generated_node_xmls = []

    tasks_from_state = state.sas_step1_generated_tasks
    config = state.config

    # Validate essential configurations
    if not tasks_from_state:
        logger.error("sas_step1_generated_tasks is missing or empty in agent state.")
        state.is_error = True
        state.error_message = "Task list (sas_step1_generated_tasks) is missing or empty for XML generation."
        state.dialog_state = "generation_failed"
        state.completion_status = "error"
        return state

    main_output_dir_str = config.get("OUTPUT_DIR_PATH")
    node_template_dir_str = config.get("NODE_TEMPLATE_DIR_PATH")

    if not main_output_dir_str:
        logger.error("OUTPUT_DIR_PATH is not configured in state.config.")
        state.is_error = True
        state.error_message = "Main output directory path (OUTPUT_DIR_PATH) for individual XMLs is not configured."
        state.dialog_state = "error"
        state.completion_status = "error"
        return state

    if not node_template_dir_str:
        logger.error("NODE_TEMPLATE_DIR_PATH is not configured in state.config.")
        state.is_error = True
        state.error_message = "Node template directory path (NODE_TEMPLATE_DIR_PATH) is not configured."
        state.dialog_state = "error"
        state.completion_status = "error"
        return state

    main_output_dir = Path(main_output_dir_str)
    try:
        os.makedirs(main_output_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create main output directory {main_output_dir}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to create main output directory: {e}"
        state.dialog_state = "error"
        state.completion_status = "error"
        return state

    # Counter for main blocks' data-blockNo (starts from 1)
    global_data_block_counter = 1 
    overall_errors_in_processing = False

    # Coordinate generation variables for the first block in each task folder
    current_x_for_first_block_in_next_task = 10 
    fixed_y_for_first_block = "10" 
    x_increment_for_tasks = 200

    # NEW: Counter for nested blocks' data-blockNo (starts from 1000)
    # This counter will be captured by the lambda/inner function.
    _nested_block_data_no_current_val = 1000
    def get_next_nested_block_data_no() -> str:
        nonlocal _nested_block_data_no_current_val
        val_to_return = _nested_block_data_no_current_val
        _nested_block_data_no_current_val += 1
        return str(val_to_return)

    for task_index, task_data in enumerate(tasks_from_state):
        task_name = getattr(task_data, 'name', f'task_{task_index}')
        task_details = getattr(task_data, 'details', [])
        
        sanitized_task_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', task_name)
        task_specific_dir_name = f"{task_index:02d}_{sanitized_task_name}"
        task_output_dir = main_output_dir / task_specific_dir_name

        try:
            os.makedirs(task_output_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create task-specific directory {task_output_dir}: {e}", exc_info=True)
            dir_error_entry = GeneratedXmlFile(
                block_id=f"task_dir_error_{task_index}", 
                type="task_directory_creation_failure", 
                source_description=f"Error creating directory for task: {task_name}",
                status="failure", 
                xml_content=None,
                file_path=None,
                error_message=str(e)
            )
            state.generated_node_xmls.append(dir_error_entry)
            overall_errors_in_processing = True
            continue

        if not task_details:
            logger.warning(f"Task '{task_name}' (index {task_index}) has no details. No XML blocks will be generated for it.")
            continue

        logger.info(f"Processing Task '{task_name}' (index {task_index}): {len(task_details)} details found.")
        
        block_generation_coroutines_for_task = []
        file_save_metadata_for_task = [] 
        
        # This flag ensures only the first *valid* detail in the *current task* gets coordinates.
        assign_coords_to_this_detail = True 
        # This will store the block_id of the block that was assigned coordinates for this task.
        block_id_assigned_coords_this_task: Optional[str] = None

        for detail_idx, detail_str in enumerate(task_details):
            current_target_block_id = str(uuid.uuid4())
            current_data_block_no = str(global_data_block_counter) 
            # Increment counter only if we are actually processing this detail for block generation
            # This is implicitly handled as we only increment after successful type extraction and param setup.
            # Let's move increment after successful processing for this detail.

            block_type = _extract_block_type_from_detail(detail_str)
            if not block_type:
                logger.warning(f"  Skipping detail for task '{task_name}' (detail #{detail_idx}) due to unextracted block type. Detail: '{detail_str}'")
                parse_fail_entry = GeneratedXmlFile(
                    block_id=current_target_block_id,
                    type="unknown_type_extraction_failure",
                    source_description=detail_str,
                    status="failure",
                    xml_content=None,
                    file_path=None,
                    error_message="Could not extract block type from detail string."
                )
                state.generated_node_xmls.append(parse_fail_entry)
                overall_errors_in_processing = True
                continue # Skip to next detail if block type cannot be determined
            
            # If we are here, this detail is valid and will attempt to generate a block.
            # Increment global_data_block_counter now.
            global_data_block_counter += 1

            extracted_params = _extract_parameters_from_detail(detail_str, block_type)
            
            if block_type == "procedures_defnoreturn":
                procedure_name_from_task = getattr(task_data, 'name', None)
                if procedure_name_from_task:
                    if 'fields' not in extracted_params:
                        extracted_params['fields'] = {}
                    extracted_params['fields']['NAME'] = procedure_name_from_task
                else:
                    logger.warning(f"  Task name not found for procedures_defnoreturn: task_index {task_index}, detail_idx {detail_idx}.")
            
            generated_xml_filename = f"{current_data_block_no}_{block_type}.xml"
            file_save_metadata_for_task.append({
                "target_filename": generated_xml_filename,
                "task_output_directory": task_output_dir,
                "block_id_for_result_matching": current_target_block_id # Store ID for later matching
            })

            x_to_pass = None
            y_to_pass = None
            if assign_coords_to_this_detail:
                x_to_pass = str(current_x_for_first_block_in_next_task)
                y_to_pass = fixed_y_for_first_block
                block_id_assigned_coords_this_task = current_target_block_id # Record which block got the attempt
                assign_coords_to_this_detail = False # Ensure subsequent valid details in this task don't get coords

            block_generation_coroutines_for_task.append(
                _generate_xml_from_template(
                    block_type=block_type,
                    target_block_id=current_target_block_id,
                    data_block_no_in_task=current_data_block_no,
                    node_template_dir_str=node_template_dir_str,
                    source_description=detail_str,
                    parameters=extracted_params,
                    get_next_nested_block_data_no_func=get_next_nested_block_data_no, # Pass the function
                    x_coord=x_to_pass, 
                    y_coord=y_to_pass
                )
            )
        
        if not block_generation_coroutines_for_task:
            logger.info(f"No valid block generation tasks created for task '{task_name}' (index {task_index}).")
            continue

        current_task_block_results: List[GeneratedXmlFile] = await asyncio.gather(*block_generation_coroutines_for_task)
        
        # Check if the block that was intended to receive coordinates was successfully generated.
        coords_were_successfully_applied_to_first_block_of_this_task = False
        if block_id_assigned_coords_this_task: # If an attempt was made to assign coords in this task
            for result_info in current_task_block_results:
                if result_info.block_id == block_id_assigned_coords_this_task and result_info.status == "success":
                    coords_were_successfully_applied_to_first_block_of_this_task = True
                    logger.info(f"Coordinates successfully applied to block {block_id_assigned_coords_this_task} for task '{task_name}'.")
                    break
        
        if coords_were_successfully_applied_to_first_block_of_this_task:
            current_x_for_first_block_in_next_task += x_increment_for_tasks
            logger.info(f"Next task's first block will start at X = {current_x_for_first_block_in_next_task}")

        # Process results: save successful XMLs and log errors
        for i, result_info in enumerate(current_task_block_results):
            # Find corresponding metadata using the block_id as there's no direct index if details were skipped.
            # However, block_generation_coroutines_for_task and current_task_block_results are 1:1 if no details were skipped *after* deciding to create a coroutine.
            # The file_save_metadata_for_task was built in sync with coroutines. So direct indexing by 'i' is fine.
            metadata = file_save_metadata_for_task[i]
            
            if result_info.status == "success" and result_info.xml_content:
                file_path_to_save = metadata["task_output_directory"] / metadata["target_filename"]
                try:
                    # Start of new code block for pretty printing
                    parsed_xml = xml.dom.minidom.parseString(result_info.xml_content)

                    # Ensure mutation tags are not self-closing even if they only have attributes
                    mutation_elements = parsed_xml.getElementsByTagName("mutation")
                    for mutation_element in mutation_elements:
                        if not mutation_element.hasChildNodes():
                            mutation_element.appendChild(parsed_xml.createTextNode(""))
                    
                    # Use toprettyxml for indentation. It adds its own XML declaration.
                    # encoding="UTF-8" ensures the output string from toprettyxml can be decoded as UTF-8
                    pretty_xml_string_with_decl = parsed_xml.toprettyxml(indent="\t", encoding="UTF-8").decode('utf-8')
                    
                    # Split into lines to process
                    lines = pretty_xml_string_with_decl.splitlines()
                    
                    # Remove the XML declaration added by toprettyxml (usually the first line)
                    if lines and lines[0].strip().startswith("<?xml"):
                        lines.pop(0)
                    
                    # Filter out any completely blank lines that toprettyxml might have added.
                    compact_pretty_lines = [line for line in lines if line.strip()]
                    pretty_content_no_decl = "\n".join(compact_pretty_lines)
                    
                    # Prepend our standard XML declaration
                    xml_to_write = '<?xml version="1.0" encoding="UTF-8"?>\n' + pretty_content_no_decl
                    
                    # Ensure the entire content ends with a single newline.
                    if not xml_to_write.endswith('\n'):
                        xml_to_write += '\n'
                    # End of new code block

                    with open(file_path_to_save, 'w', encoding='utf-8') as f:
                        f.write(xml_to_write)
                    result_info.file_path = str(file_path_to_save)
                    logger.info(f"  Successfully wrote XML block to: {file_path_to_save}")
                except IOError as e:
                    logger.error(f"  Failed to write XML block file {file_path_to_save}: {e}", exc_info=True)
                    result_info.status = "failure"
                    result_info.error_message = f"IOError on writing file: {e}"
                    result_info.file_path = None
                    overall_errors_in_processing = True
            elif result_info.status == "failure":
                overall_errors_in_processing = True
                logger.error(f"  Failed to generate XML for block_id '{result_info.block_id}' (type: {result_info.type}): {result_info.error_message}")
            
            state.generated_node_xmls.append(result_info)

    # After processing all tasks
    if overall_errors_in_processing:
        logger.error("One or more errors occurred during the generation of individual XML blocks.")
        state.is_error = True 
        
        # 收集具体的错误信息
        failed_blocks = [xml_file for xml_file in state.generated_node_xmls if xml_file.status == "failure"]
        error_details = []
        for failed_block in failed_blocks[:3]:  # 只显示前3个错误，避免信息过多
            error_details.append(f"- {failed_block.type}: {failed_block.error_message}")
        
        if not state.error_message:
            if error_details:
                detailed_errors = "\n".join(error_details)
                if len(failed_blocks) > 3:
                    detailed_errors += f"\n- ...以及其他 {len(failed_blocks) - 3} 个错误"
                state.error_message = f"XML生成过程中发生错误:\n{detailed_errors}"
            else:
                state.error_message = "XML生成过程中发生未知错误，请检查日志以获取更多信息。"
        
        state.completion_status = "error" 
        state.dialog_state = "generation_failed"
    else:
        logger.info("All individual XML blocks for all tasks were generated and saved successfully.")
        state.dialog_state = "sas_individual_xmls_generated_ready_for_mapping" 
        state.completion_status = "processing"
    
    return state

# After the last function definition (generate_individual_xmls_node)
# Add the following test execution block:

if __name__ == "__main__":
    # Mock or minimal RobotFlowAgentState for testing
    class MockRobotFlowAgentState:
        def __init__(self, sas_step1_generated_tasks: List[Dict[str, Any]], config: Dict[str, Any]):
            self.sas_step1_generated_tasks = [TaskDefinition(**task) for task in sas_step1_generated_tasks] # Convert dicts to Pydantic models
            self.config = config
            self.current_step_description: Optional[str] = None
            self.is_error: bool = False
            self.error_message: Optional[str] = None
            self.dialog_state: Optional[str] = None
            self.completion_status: Optional[str] = None
            self.generated_node_xmls: List[GeneratedXmlFile] = []

    async def main_test():
        # Ensure this path is correct for your environment
        test_json_path = Path("/workspace/backend/tests/llm_sas_test/1_sample/step2_output_sample.json") 
        
        if not test_json_path.exists():
            print(f"ERROR: Test JSON file not found at {test_json_path}")
            logger.error(f"Test JSON file not found at: {test_json_path}")
            return

        try:
            with open(test_json_path, 'r', encoding='utf-8') as f:
                test_input_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode JSON from {test_json_path}: {e}")
            logger.error(f"Failed to decode JSON from {test_json_path}: {e}")
            return
        
        tasks_for_state: List[Dict[str, Any]] = []
        if isinstance(test_input_data, list):
            tasks_for_state = test_input_data
            logger.info(f"Loaded {len(tasks_for_state)} tasks directly from JSON list.")
        elif isinstance(test_input_data, dict):
            # Check for common keys that might hold the list of tasks
            possible_task_list_keys = ["sas_step1_generated_tasks", "parsed_flow_steps"] 
            found_list = False
            for key in possible_task_list_keys:
                if key in test_input_data and isinstance(test_input_data[key], list):
                    tasks_for_state = test_input_data[key]
                    logger.info(f"Loaded {len(tasks_for_state)} tasks from key '{key}' in JSON dictionary.")
                    found_list = True
                    break
            if not found_list: # If not found under primary keys
                # Check if the dict itself is a single task object (e.g., has 'name' and 'details')
                if 'name' in test_input_data and 'details' in test_input_data: 
                    tasks_for_state = [test_input_data]
                    logger.info("Loaded 1 task (JSON dictionary itself appears to be a single task object).")
                else:
                    logger.warning(
                        "Could not identify a list of tasks in the loaded JSON dictionary using known keys, "
                        "and it does not appear to be a single task object. 'tasks_for_state' will be empty."
                    )
                    tasks_for_state = [] # Ensure it's an empty list
        else:
            logger.error(
                f"Loaded JSON data is neither a list nor a dictionary (type: {type(test_input_data)}). "
                "Cannot extract tasks. 'tasks_for_state' will be empty."
            )
            tasks_for_state = [] # Ensure it's an empty list

        if not tasks_for_state:
            logger.warning("No tasks found or extracted from the JSON data. The script might not produce output.")

        # Ensure this output path is writable and desired for testing
        test_output_dir = "/workspace/backend/tests/llm_sas_test/1_sample_sas_generate_xml_output"
        # UPDATE THE NODE TEMPLATE PATH HERE
        node_templates_path = "/workspace/database/node_database/quick-fcpr-new-default" 

        mock_config = {
            "OUTPUT_DIR_PATH": test_output_dir, 
            "NODE_TEMPLATE_DIR_PATH": node_templates_path,
            "BLOCK_ID_PREFIX_INDIVIDUAL": "test_block_uuid" # Using a distinct prefix for test
        }
        
        os.makedirs(mock_config["OUTPUT_DIR_PATH"], exist_ok=True)
        if not Path(mock_config["NODE_TEMPLATE_DIR_PATH"]).is_dir():
            print(f"ERROR: NODE_TEMPLATE_DIR_PATH does not exist or is not a directory: {mock_config['NODE_TEMPLATE_DIR_PATH']}")
            logger.error(f"NODE_TEMPLATE_DIR_PATH does not exist or is not a directory: {mock_config['NODE_TEMPLATE_DIR_PATH']}")
            # Decide if you want to return or proceed if templates are missing
            # return 

        print(f"[Test Main] Mock config created. OUTPUT_DIR_PATH: {mock_config['OUTPUT_DIR_PATH']}")
        print(f"[Test Main] NODE_TEMPLATE_DIR_PATH: {mock_config['NODE_TEMPLATE_DIR_PATH']}")
        print(f"[Test Main] Number of tasks to process: {len(tasks_for_state)}")

        initial_state = MockRobotFlowAgentState(
            sas_step1_generated_tasks=tasks_for_state, 
            config=mock_config
        )

        print("[Test Main] Initial state created. Calling generate_individual_xmls_node...")
        final_state = await generate_individual_xmls_node(initial_state) # type: ignore

        if final_state.is_error:
            print(f"[Test Main] Test run failed. Error: {final_state.error_message}")
            logger.error(f"Test run failed. Error: {final_state.error_message}")
        else:
            print("[Test Main] Test run completed successfully (no errors reported by the node).")
            logger.info("Test run completed successfully (no errors reported by the node).")
        
        if final_state.generated_node_xmls:
            print(f"[Test Main] Total GeneratedXmlFile entries: {len(final_state.generated_node_xmls)}")
            success_count = 0
            failure_count = 0
            for entry_idx, entry in enumerate(final_state.generated_node_xmls):
                status_marker = "OK" if entry.status == "success" else "FAIL"
                print(f"  [{status_marker}] Entry {entry_idx+1}: ID={entry.block_id}, Type={entry.type}, Path={entry.file_path}")
                if entry.status == "success":
                    success_count +=1
                else:
                    failure_count +=1
                    print(f"      Error for {entry.block_id}: {entry.error_message}")
            print(f"[Test Main] Summary: {success_count} successful, {failure_count} failed block generations.")
        else:
            print("[Test Main] No GeneratedXmlFile entries were created.")

        print(f"[Test Main] Check output files (if any) in: {mock_config['OUTPUT_DIR_PATH']}")

    # Configure logging to show messages from this script's logger and potentially others
    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s'
    # REMOVE THIS LINE: logging.basicConfig(level=logging.DEBUG, format=log_format)
    # If you want to see DEBUG logs from your script for finer details:
    logger.setLevel(logging.DEBUG) # Sets this script's logger to DEBUG
    # logging.getLogger('__main__').setLevel(logging.DEBUG) # Also useful if logger name isn't caught by basicConfig
       
    print("[Test Main] Starting asyncio main_test...")
    asyncio.run(main_test())
    print("[Test Main] Finished asyncio main_test.")
