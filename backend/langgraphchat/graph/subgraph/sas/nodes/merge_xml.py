import os
import xml.etree.ElementTree as ET
from pathlib import Path

# Base directory containing XML part files
BASE_DIR = Path("backend/tests/llm_sas_test/1_sample_sas_generate_xml_output/01_Open_BRG_PLT_Clamp")
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
        
        # Expected tags with Blockly namespace
        # BLOCKLY_XMLNS is defined globally as "https://developers.google.com/blockly/xml"
        namespaced_block_tag = f"{{{BLOCKLY_XMLNS}}}block"
        namespaced_xml_tag = f"{{{BLOCKLY_XMLNS}}}xml"

        block_element = None

        # Check for root tag, considering it might be namespaced or not
        if root_element.tag == namespaced_block_tag or root_element.tag == "block":
            block_element = root_element
        elif root_element.tag == namespaced_xml_tag or root_element.tag == "xml":
            # If the root is <xml> (namespaced or not), find the <block> child.
            # The <block> child is expected to be in the BLOCKLY_XMLNS namespace.
            block_element = root_element.find(namespaced_block_tag)
            
            if block_element is None: # Fallback: try finding "block" without namespace
                block_element = root_element.find("block")

            if block_element is None:
                print(f"Warning: Root tag is '{root_element.tag}' but no '{namespaced_block_tag}' or 'block' child found in {file_path}. Skipping.")
                return None, None
        else:
            print(f"Warning: Unexpected root tag '{root_element.tag}' in {file_path}. Expected '{namespaced_block_tag}', 'block', '{namespaced_xml_tag}', or 'xml'. Skipping.")
            return None, None
        
        # Validate that we indeed have a <block> element by checking its local name
        # The block_element.tag could be "block" or "{namespace}block"
        current_block_tag = block_element.tag
        if '}' in current_block_tag: # Check if it's a namespaced tag like {uri}tag
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
        # Catch any other unexpected errors during file processing
        print(f"An unexpected error occurred while processing file {file_path}: {e}")
        return None, None

def main():
    """
    Main function to discover XML parts in a specific directory, sort them, 
    assemble them, and write the output.
    """
    ET.register_namespace("", BLOCKLY_XMLNS)
    
    if not BASE_DIR.exists() or not BASE_DIR.is_dir():
        print(f"Error: Source directory {BASE_DIR} does not exist or is not a directory.")
        return

    print(f"Processing directory: {BASE_DIR.name}")
    all_blocks_with_order = []

    # Iterate through XML files in the current (BASE_DIR) directory
    xml_files_in_dir = list(BASE_DIR.glob("*.xml"))
    if not xml_files_in_dir:
        print(f"No XML files found in {BASE_DIR.name}.")
        return

    for xml_file in xml_files_in_dir:
        block_no, block_element = get_block_from_file(xml_file)
        if block_element is not None and block_no is not None:
            # Store as (order_key, element_object, source_filename_for_debug)
            all_blocks_with_order.append((block_no, block_element, xml_file.name))
    
    if not all_blocks_with_order:
        print(f"No valid blocks found in {BASE_DIR.name} after parsing.")
        return
        
    # Sort collected blocks by data-blockNo
    all_blocks_with_order.sort(key=lambda item: item[0])
    
    # Extract just the Element objects in the correct order
    sorted_block_elements = [item[1] for item in all_blocks_with_order]

    # Create the root <xml> element with the Blockly namespace
    root_xml_element = ET.Element("xml", {"xmlns": BLOCKLY_XMLNS})

    if not sorted_block_elements: 
        print(f"No valid blocks to assemble for {BASE_DIR.name}. Output XML will be empty (except for the root tag).")
    else:
        first_block_element = sorted_block_elements[0]
        root_xml_element.append(first_block_element)

        # Check if the first block is 'procedures_defnoreturn' and there are subsequent blocks for the STACK
        if first_block_element.get("type") == "procedures_defnoreturn" and len(sorted_block_elements) > 1:
            statement_element = ET.SubElement(first_block_element, "statement", {"name": "STACK"})
            
            # The first block in the STACK is sorted_block_elements[1]
            current_block_for_next_tag = sorted_block_elements[1]
            statement_element.append(current_block_for_next_tag)
            
            # Link subsequent blocks (from sorted_block_elements[2] onwards) within the STACK
            for i in range(2, len(sorted_block_elements)):
                next_block_to_append = sorted_block_elements[i]
                next_tag = ET.SubElement(current_block_for_next_tag, "next")
                next_tag.append(next_block_to_append)
                current_block_for_next_tag = next_block_to_append
        elif len(sorted_block_elements) > 1: # Standard linking for other cases with more than one block
            # The first block (already appended) is the starting point for <next>
            current_block_for_next_tag = first_block_element
            # Link subsequent blocks (from sorted_block_elements[1] onwards)
            for i in range(1, len(sorted_block_elements)):
                next_block_to_append = sorted_block_elements[i]
                next_tag = ET.SubElement(current_block_for_next_tag, "next")
                next_tag.append(next_block_to_append)
                current_block_for_next_tag = next_block_to_append
        # If only one block, no further linking is needed as it's already appended and no special structure is required.

    # Pretty-print the XML tree (requires Python 3.9+ for ET.indent)
    try:
        ET.indent(root_xml_element) 
    except AttributeError:
        print(f"Warning: ET.indent not available (requires Python 3.9+). XML for {BASE_DIR.name} will not be pretty-printed by ElementTree\'s indent method.")
        # For production use with older Python, consider using lxml.etree for robust pretty-printing.
        pass

    # Create an ElementTree object for writing
    tree = ET.ElementTree(root_xml_element)
    
    # Define output path for the current directory
    # The OUTPUT_BASE_DIR is the directory where the file will be saved.
    # The file name will be based on the BASE_DIR's name.
    output_file_path = OUTPUT_BASE_DIR / f"{BASE_DIR.name}_flow.xml"
    
    # Ensure the output directory exists
    try:
        OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory {OUTPUT_BASE_DIR}: {e}")
        return # Exit if cannot create output directory

    # Write the assembled XML to the output file
    try:
        tree.write(output_file_path, encoding="utf-8", xml_declaration=True)
        print(f"Successfully assembled XML for {BASE_DIR.name} to {output_file_path}")
    except IOError as e:
        print(f"Error writing output XML for {BASE_DIR.name} to {output_file_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while writing XML for {BASE_DIR.name} to {output_file_path}: {e}")

if __name__ == "__main__":
    main()