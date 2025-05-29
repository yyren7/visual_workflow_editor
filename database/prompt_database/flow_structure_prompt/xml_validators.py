import re
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
import argparse # Added argparse
import sys # Added sys for file reading in main

# --- Namespace Definition ---
BLOCKLY_NS_URI = "https://developers.google.com/blockly/xml"
NS_MAP = {"b": BLOCKLY_NS_URI} # For ET.find functions if needed, though direct tag comparison is used more here

def _tag(tag_name):
    """Helper to create a namespaced tag name in Clark notation."""
    return f"{{{BLOCKLY_NS_URI}}}{tag_name}"

# --- Helper Function ---
def _parse_xml_string(xml_content_string: str):
    """Helper to parse XML content string, raising ValueError on failure."""
    try:
        # Attempt to remove XML declaration if present, as it can sometimes interfere
        # with ElementTree if not handled perfectly by all underlying XML parsers.
        # However, ET.fromstring should generally handle it.
        # For robustness, we can strip it if it's causing issues, but let's first assume ET handles it.
        content_to_parse = xml_content_string.strip()
        return ET.fromstring(content_to_parse)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}") from e

# --- Node Definitions (based on /workspace/database/node_database/quick-fcpr-new/) ---
# Ideally, these definitions would be dynamically loaded and parsed from the XML template files
# in {{NODE_TEMPLATE_DIR_PATH}}. For this script, they are hardcoded based on known templates.
NODE_DEFINITIONS = {
    "moveL": {
        "fields": {
            "point_name_list": {"type": "string", "description": "Target point name, e.g., P1, P2."},
            "control_x": {"allowed_values": ["enable", "disable"], "description": "X-axis control state."},
            "control_y": {"allowed_values": ["enable", "disable"], "description": "Y-axis control state."},
            "control_z": {"allowed_values": ["enable", "disable"], "description": "Z-axis control state."},
            "control_rz": {"allowed_values": ["enable", "disable"], "description": "Rz-axis control state."},
            "control_ry": {"allowed_values": ["enable", "disable"], "description": "Ry-axis control state."},
            "control_rx": {"allowed_values": ["enable", "disable"], "description": "Rx-axis control state."},
            "pallet_list": {"type": "string", "description": "Pallet number, e.g., none, pallet_1."},
            "camera_list": {"type": "string", "description": "Camera number, e.g., none, camera_1."}
        },
        "required_fields": ["point_name_list", "control_x", "control_y", "control_z", "control_rz", "control_ry", "control_rx", "pallet_list", "camera_list"]
    },
    "select_robot": {
        "fields": {"robotName": {"type": "string", "description": "Name of the robot, e.g., dobot_mg400."}},
        "required_fields": ["robotName"]
    },
    "set_motor": {
        "fields": {"state_list": {"allowed_values": ["on", "off"], "description": "Motor state."}},
        "required_fields": ["state_list"]
    },
    "loop": { # Loop block structure is mainly about its <statement name="DO"> child.
        "fields": {},
        "required_fields": []
    },
    "return": { # Return block has no fields.
        "fields": {},
        "required_fields": []
    }
}

# --- Validation Functions ---

def validate_relation_xml(xml_content_string: str) -> tuple[bool, list[str]]:
    """
    Validates relation.xml content.
    Ensures it only contains allowed structural elements (block, next, statement)
    and their 'type' and 'id' attributes.
    It must NOT contain <field>, <value> tags, or 'data-blockNo' attributes.
    The general structure should follow Blockly's XML format.
    """
    errors = []
    try:
        root = _parse_xml_string(xml_content_string)
        if root.tag != _tag("xml"):
            errors.append(f"Root element of relation.xml must be <xml> with namespace. Found: {root.tag}")
            return not errors, errors # Critical error

        for element in root.iter():
            tag_local_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            if 'data-blockNo' in element.attrib:
                errors.append(f"Element <{tag_local_name} id='{element.get('id')}'> must not have 'data-blockNo' attribute in relation.xml.")
            
            if tag_local_name in ["field", "value"]:
                errors.append(f"Disallowed tag <{tag_local_name}> found in relation.xml. Full tag: {element.tag}")

            if tag_local_name == "block":
                if 'id' not in element.attrib:
                    errors.append(f"Block element is missing 'id' attribute. Full tag: {element.tag}")
                if 'type' not in element.attrib:
                    errors.append(f"Block element is missing 'type' attribute. Full tag: {element.tag}")
            elif tag_local_name == "statement":
                if 'name' not in element.attrib:
                    errors.append(f"Statement element is missing 'name' attribute. Full tag: {element.tag}")
            elif tag_local_name not in ["xml", "next", "block", "statement"]:
                errors.append(f"Unexpected tag <{tag_local_name}> found in relation.xml. Full tag: {element.tag}")
                
    except ValueError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"An unexpected error occurred during relation.xml validation: {e}")
    
    return not errors, errors


def validate_single_block_xml(xml_content_string: str) -> tuple[bool, list[str]]:
    """
    Validates a single block's XML content against NODE_DEFINITIONS.
    Checks for presence of <xml><block>...</block></xml> structure.
    Ensures required attributes (id, data-blockNo, type) for the <block> exist.
    Validates <field> names and their values according to NODE_DEFINITIONS.
    """
    errors = []
    try:
        root = _parse_xml_string(xml_content_string)
        if root.tag != _tag("xml"):
             errors.append(f"Single block XML root must be <xml> with namespace. Found: {root.tag}")
             return not errors, errors
        if len(root) == 0 or root[0].tag != _tag("block"):
            errors.append(f"Single block XML must have one <block> child under <xml>. Found child: {root[0].tag if len(root)>0 else 'None'}")
            return not errors, errors
        
        block_element = root[0]
        block_type = block_element.get("type")

        if not block_type:
            errors.append("<block> element is missing 'type' attribute.")
            return not errors, errors

        if 'id' not in block_element.attrib:
            errors.append(f"Block type '{block_type}' is missing 'id' attribute.")
        if 'data-blockNo' not in block_element.attrib:
            errors.append(f"Block type '{block_type}' is missing 'data-blockNo' attribute.")
        else:
            if not re.fullmatch(r"\d+", block_element.get("data-blockNo", "")):
                 errors.append(f"Block type '{block_type}' has invalid 'data-blockNo' format: '{block_element.get('data-blockNo')}'. Expected digits.")

        if block_type not in NODE_DEFINITIONS:
            errors.append(f"Unknown block type '{block_type}'.")
        else:
            definition = NODE_DEFINITIONS[block_type]
            defined_fields_spec = definition.get("fields", {})
            required_field_names = definition.get("required_fields", [])
            present_field_names = []

            for field_element in block_element.findall(_tag("field")):
                field_name = field_element.get("name")
                if not field_name:
                    errors.append(f"Field in block '{block_type}' is missing 'name' attribute.")
                    continue
                present_field_names.append(field_name)
                field_value = field_element.text if field_element.text is not None else ""

                if field_name not in defined_fields_spec:
                    errors.append(f"Block type '{block_type}' has an unexpected field: '{field_name}'.")
                    continue

                field_spec = defined_fields_spec[field_name]
                if "allowed_values" in field_spec and field_value not in field_spec["allowed_values"]:
                    errors.append(f"Field '{field_name}' in block '{block_type}' has value '{field_value}', allowed: {field_spec['allowed_values']}.")

            for req_field_name in required_field_names:
                if req_field_name not in present_field_names:
                    errors.append(f"Block type '{block_type}' is missing required field: '{req_field_name}'.")
        
        allowed_block_children_local_names = {"field", "mutation"}
        if block_type == "loop":
            allowed_block_children_local_names.add("statement")

        for child in block_element:
            child_local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_local_name not in allowed_block_children_local_names:
                 errors.append(f"Block type '{block_type}' has unexpected child <{child_local_name}>. Full tag: {child.tag}")
            elif block_type == "loop" and child_local_name == "statement":
                if child.get("name") != "DO":
                    errors.append(f"Loop block's <statement> child must have name='DO'. Found name='{child.get('name')}'. Full tag: {child.tag}")
                # Check if the statement has any children other than a 'next' element or other 'block' elements.
                # This part might be too specific if we don't know the exact allowed structure within a loop's statement.
                # For now, we just validate the name attribute.

    except ValueError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"An unexpected error occurred: {e}")
        
    return not errors, errors


def validate_flow_xml_data_block_no(xml_content_string: str) -> tuple[bool, list[str]]:
    """
    Validates flow.xml for 'data-blockNo' attributes.
    Ensures 'data-blockNo' is present on all blocks, is a positive integer,
    and for each block type, the set of 'data-blockNo' values is unique and,
    when sorted, forms a continuous sequence starting from 1 (e.g., 1, 2, 3, ...).
    """
    errors = []
    try:
        root = _parse_xml_string(xml_content_string)
        if root.tag != _tag("xml"):
            errors.append(f"Root element of flow.xml must be <xml> with namespace. Found: {root.tag}")
            return not errors, errors

        block_nos_by_type = defaultdict(list)
        for element in root.iter(_tag("block")):
            block_type = element.get("type")
            block_id = element.get("id", "N/A")
            data_block_no_str = element.get("data-blockNo")

            if not block_type:
                errors.append(f"Block (id: {block_id}) is missing 'type' attribute.")
                continue 

            if data_block_no_str:
                if not re.fullmatch(r"\d+", data_block_no_str):
                    errors.append(f"Invalid 'data-blockNo' '{data_block_no_str}' for '{block_type}' (id: {block_id}). Expected digits.")
                    continue
                try:
                    data_block_no = int(data_block_no_str)
                    if data_block_no <= 0:
                         errors.append(f"'data-blockNo' '{data_block_no_str}' for '{block_type}' (id: {block_id}) must be positive.")
                         continue
                    block_nos_by_type[block_type].append(data_block_no)
                except ValueError:
                    errors.append(f"Cannot parse 'data-blockNo' '{data_block_no_str}' for '{block_type}' (id: {block_id}).")
            else:
                errors.append(f"Block '{block_type}' (id: {block_id}) is missing 'data-blockNo'.")
        
        for block_type, nos_list in block_nos_by_type.items():
            if not nos_list: continue
            counts = Counter(nos_list)
            duplicates = [item for item, count in counts.items() if count > 1]
            if duplicates:
                errors.append(f"Duplicate 'data-blockNo' for '{block_type}': {duplicates}. All: {nos_list}.")

            sorted_unique_nos = sorted(list(set(nos_list)))
            expected_sequence = list(range(1, len(sorted_unique_nos) + 1))
            if sorted_unique_nos != expected_sequence:
                errors.append(f"For '{block_type}', 'data-blockNo' {sorted_unique_nos} not continuous from 1. Expected: {expected_sequence}.")

    except ValueError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"An unexpected error: {e}")
        
    return not errors, errors

# Main execution block for CLI
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Validate XML flow files.")
    parser.add_argument("function_name", choices=["validate_relation_xml", "validate_single_block_xml", "validate_flow_xml_data_block_no"], help="Validation function name.")
    parser.add_argument("file_path", help="Path to XML file.")
    args = parser.parse_args()
    try:
        with open(args.file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        # print(f"DEBUG: XML Content (first 70 chars): {xml_content[:70]}", file=sys.stderr) # Keep for debugging if needed
    except FileNotFoundError:
        print(f"(False, [\"Error: File not found: {args.file_path}\"])")
        sys.exit(1)
    except Exception as e:
        print(f"(False, [\"Error reading file {args.file_path}: {e}\"])")
        sys.exit(1)

    validation_function = globals().get(args.function_name)
    if validation_function:
        is_valid, errors = validation_function(xml_content)
        print(f"({is_valid}, {errors})")
    else:
        print(f"(False, [\"Error: Validation function '{args.function_name}' not found.\"])")
        sys.exit(1) 