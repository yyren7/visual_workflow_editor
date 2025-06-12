import os
import xml.etree.ElementTree as ET
from pathlib import Path

# Parent directory containing subdirectories with XML part files
PARENT_INPUT_DIR = Path("backend/tests/llm_sas_test/1_sample_sas_generate_xml_output")
# Base output directory for the assembled XML files
OUTPUT_BASE_DIR = Path("backend/tests/llm_sas_test/specific_clamp_output/")
# Blockly XML namespace
BLOCKLY_XMLNS = "https://developers.google.com/blockly/xml"

def get_block_from_file(file_path: Path):
    """
    Parses an XML file, extracts the root <block> element and its data-blockNo.
    Returns (block_no, block_element) or (None, None) on error.
    """
    try:
        tree = ET.parse(file_path)
        root_element = tree.getroot()
        
        namespaced_block_tag = f"{{{BLOCKLY_XMLNS}}}block"
        namespaced_xml_tag = f"{{{BLOCKLY_XMLNS}}}xml"
        block_element = None

        if root_element.tag == namespaced_block_tag or root_element.tag == "block":
            block_element = root_element
        elif root_element.tag == namespaced_xml_tag or root_element.tag == "xml":
            block_element = root_element.find(namespaced_block_tag)
            if block_element is None: 
                block_element = root_element.find("block")
            if block_element is None:
                print(f"Warning: Root tag is '{root_element.tag}' but no '{namespaced_block_tag}' or 'block' child found in {file_path}. Skipping.")
                return None, None
        else:
            print(f"Warning: Unexpected root tag '{root_element.tag}' in {file_path}. Expected '{namespaced_block_tag}', 'block', '{namespaced_xml_tag}', or 'xml'. Skipping.")
            return None, None
        
        current_block_tag = block_element.tag
        if '}' in current_block_tag: 
            block_local_name = current_block_tag.split('}', 1)[1]
        else:
            block_local_name = current_block_tag
            
        if block_local_name != "block":
            print(f"Internal Warning: Isolated element is not a 'block' (actual local name: '{block_local_name}', full tag: '{current_block_tag}') in {file_path}. Skipping.")
            return None, None
            
        block_no_str = block_element.get("data-blockNo")
        if block_no_str is None:
            print(f"Warning: Missing 'data-blockNo' attribute in block from file {file_path}. Skipping.")
            return None, None
        
        try:
            block_no = int(block_no_str)
        except ValueError:
            print(f"Warning: Invalid 'data-blockNo' value '{block_no_str}' in {file_path}. Skipping.")
            return None, None
            
        return block_no, block_element
    except ET.ParseError as e:
        print(f"Error parsing XML file {file_path}: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred while processing file {file_path}: {e}")
        return None, None

def process_single_directory(input_dir: Path, output_dir_base: Path):
    """
    Processes XML files in a single directory, assembles them, and writes the output.
    """
    print(f"Processing directory: {input_dir.name}")
    all_blocks_with_order = []

    xml_files_in_dir = list(input_dir.glob("*.xml"))
    if not xml_files_in_dir:
        print(f"No XML files found in {input_dir.name}.")
        return

    for xml_file in xml_files_in_dir:
        block_no, block_element = get_block_from_file(xml_file)
        if block_element is not None and block_no is not None:
            all_blocks_with_order.append((block_no, block_element, xml_file.name))
    
    if not all_blocks_with_order:
        print(f"No valid blocks found in {input_dir.name} after parsing.")
        return
        
    all_blocks_with_order.sort(key=lambda item: item[0])
    sorted_block_elements = [item[1] for item in all_blocks_with_order]

    root_xml_element = ET.Element(f"{{{BLOCKLY_XMLNS}}}xml")

    if not sorted_block_elements:
        print(f"No valid blocks to assemble for {input_dir.name}. Output XML will be empty (except for the root tag).")
    else:
        first_block_element = sorted_block_elements[0]
        root_xml_element.append(first_block_element)

        current_parent_for_chaining = first_block_element
        # Modified DEBUG print to include directory context
        print(f"DEBUG [{input_dir.name}]: Initial parent data-blockNo='{current_parent_for_chaining.get('data-blockNo')}', type='{current_parent_for_chaining.get('type')}'")

        for i in range(1, len(sorted_block_elements)):
            block_to_attach = sorted_block_elements[i]
            parent_type = current_parent_for_chaining.get("type")
            
            # Modified DEBUG prints to include directory context
            print(f"DEBUG [{input_dir.name}]: Iteration for i={i}")
            print(f"DEBUG [{input_dir.name}]: Current Parent: data-blockNo='{current_parent_for_chaining.get('data-blockNo')}', type='{parent_type}'")
            print(f"DEBUG [{input_dir.name}]: Block to Attach: data-blockNo='{block_to_attach.get('data-blockNo')}', type='{block_to_attach.get('type')}'")

            target_statement_name = None

            if parent_type == "procedures_defnoreturn":
                target_statement_name = "STACK"
            elif parent_type == "loop": # Simplified this, assuming "loop" is a generic type for various loops
                target_statement_name = "DO"
            elif parent_type in ["controls_repeat_ext", "controls_whileuntil", "controls_for"]:
                target_statement_name = "DO"
            elif parent_type == "controls_if":
                target_statement_name = "DO0"
            
            # Modified DEBUG print to include directory context
            if target_statement_name:
                print(f"DEBUG [{input_dir.name}]: Determined target_statement_name='{target_statement_name}'")
            else:
                print(f"DEBUG [{input_dir.name}]: target_statement_name is None. Will use direct <next> connection.")

            namespaced_statement_tag = f"{{{BLOCKLY_XMLNS}}}statement"
            namespaced_next_tag = f"{{{BLOCKLY_XMLNS}}}next"
            namespaced_block_tag_for_find = f"{{{BLOCKLY_XMLNS}}}block" 

            if target_statement_name:
                statement_element = current_parent_for_chaining.find(f"./{namespaced_statement_tag}[@name='{target_statement_name}']")
                if statement_element is None:
                    statement_element = ET.SubElement(current_parent_for_chaining, namespaced_statement_tag, {"name": target_statement_name})
                
                # Logic to find the last block in a statement chain (DO, STACK, etc.)
                last_block_in_statement_chain = None
                # Check for an existing block directly under the statement tag
                first_block_in_statement = None
                for child_node in list(statement_element):
                    if child_node.tag == namespaced_block_tag_for_find or child_node.tag == "block": 
                        first_block_in_statement = child_node
                        break
                
                if first_block_in_statement is not None:
                    # If a block exists, traverse its <next> chain to find the end
                    current_end_of_internal_chain = first_block_in_statement
                    while True:
                        next_tag_node = current_end_of_internal_chain.find(namespaced_next_tag)
                        if next_tag_node is None or not len(list(next_tag_node)):
                            break # No <next> tag or <next> tag is empty
                        # Find the <block> inside <next>
                        found_block_in_next_tag = False
                        for block_candidate_in_next in list(next_tag_node):
                            if block_candidate_in_next.tag == namespaced_block_tag_for_find or block_candidate_in_next.tag == "block":
                                current_end_of_internal_chain = block_candidate_in_next
                                found_block_in_next_tag = True
                                break
                        if not found_block_in_next_tag:
                            break # No <block> found inside <next>
                    last_block_in_statement_chain = current_end_of_internal_chain

                if last_block_in_statement_chain is None: # No blocks yet in this statement, append directly
                    statement_element.append(block_to_attach)
                else: # Append to the <next> of the last block in the statement chain
                    next_tag_for_block = ET.SubElement(last_block_in_statement_chain, namespaced_next_tag)
                    next_tag_for_block.append(block_to_attach)
                
                current_parent_for_chaining = block_to_attach # The newly attached block becomes parent for subsequent blocks *in the main sequence*
            else: # No specific statement target, attach via <next> to the current parent
                next_tag_for_block = ET.SubElement(current_parent_for_chaining, namespaced_next_tag)
                next_tag_for_block.append(block_to_attach)
                current_parent_for_chaining = block_to_attach

    try:
        ET.indent(root_xml_element) 
    except AttributeError:
        print(f"Warning: ET.indent not available (requires Python 3.9+). XML for {input_dir.name} will not be pretty-printed by ElementTree's indent method.")
        pass

    tree = ET.ElementTree(root_xml_element)
    
    output_file_path = output_dir_base / f"{input_dir.name}_flow.xml"
    
    try:
        output_dir_base.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory {output_dir_base}: {e}")
        return

    try:
        tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Successfully assembled XML for {input_dir.name} to {output_file_path}")
    except IOError as e:
        print(f"Error writing output XML for {input_dir.name} to {output_file_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while writing XML for {input_dir.name} to {output_file_path}: {e}")

def main():
    """
    Main function to discover subdirectories in PARENT_INPUT_DIR, 
    and process each one to assemble XML files.
    """
    ET.register_namespace("", BLOCKLY_XMLNS) # Register namespace once globally

    if not PARENT_INPUT_DIR.exists() or not PARENT_INPUT_DIR.is_dir():
        print(f"Error: Parent input directory {PARENT_INPUT_DIR} does not exist or is not a directory.")
        return

    # Get all items in the parent directory and filter for directories only
    subdirectories = [d for d in PARENT_INPUT_DIR.iterdir() if d.is_dir()]

    if not subdirectories:
        print(f"No subdirectories found in {PARENT_INPUT_DIR}.")
        return

    print(f"Found {len(subdirectories)} subdirectories to process in {PARENT_INPUT_DIR.resolve()}.")
    for subdir in subdirectories:
        print(f"\\n--- Processing Subdirectory: {subdir.resolve()} ---")
        process_single_directory(subdir, OUTPUT_BASE_DIR)
        print(f"--- Finished processing {subdir.name} ---")

if __name__ == "__main__":
    main()