import os
import logging
import xml.etree.ElementTree as ET
from typing import Type as TypingType, List, Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class WriteFileInput(BaseModel):
    directory_path: str = Field(description="The directory where the XML file should be saved.")
    file_name: str = Field(description="The name of the XML file (e.g., 'node1.xml', 'relation.xml').")
    xml_content: str = Field(description="The string content of the XML file.")
    ensure_directory_exists: bool = Field(default=True, description="Ensure the directory exists before writing.")

class WriteXmlFileTool(BaseTool):
    name: str = "write_xml_file"
    description: str = (
        "Writes the given XML content to a specified file in a specified directory. "
        "Use this to save generated XML for robot flow nodes, relations, or final flows."
    )
    args_schema: TypingType[BaseModel] = WriteFileInput

    def _run(self, directory_path: str, file_name: str, xml_content: str, ensure_directory_exists: bool = True) -> str:
        if ensure_directory_exists:
            try:
                os.makedirs(directory_path, exist_ok=True)
            except OSError as e:
                logger.error(f"Error creating directory {directory_path}: {e}")
                return f"Error: Could not create directory {directory_path}. Details: {e}"
        
        file_path = os.path.join(directory_path, file_name)
        try:
            # Basic XML validation before writing
            ET.fromstring(xml_content) # This ensures it's well-formed
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            logger.info(f"Successfully wrote XML to {file_path}")
            return f"Success: XML content successfully written to {file_path}"
        except ET.ParseError as e:
            logger.error(f"Invalid XML content for {file_path}: {e}")
            return f"Error: Invalid XML content. Details: {e}"
        except IOError as e:
            logger.error(f"Error writing XML to {file_path}: {e}")
            return f"Error: Could not write to file {file_path}. Details: {e}"
        except Exception as e:
            logger.error(f"An unexpected error occurred while writing {file_path}: {e}")
            return f"Error: An unexpected error occurred. Details: {e}"

    async def _arun(self, directory_path: str, file_name: str, xml_content: str, ensure_directory_exists: bool = True) -> str:
        return self._run(directory_path, file_name, xml_content, ensure_directory_exists)

def merge_xml_files(
    relation_xml_content: str, 
    node_xmls_data: List[Dict[str, str]], 
    final_flow_file_path: str,
    output_dir_path: str,
    data_block_no_reset_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    logger.info(f"Starting XML merge for: {final_flow_file_path}")
    if data_block_no_reset_types is None:
        data_block_no_reset_types = ['loop', 'select_robot', 'main_task']

    try:
        os.makedirs(output_dir_path, exist_ok=True)
        node_content_map = {
            node['id']: ET.fromstring(node['content']).find(".//block") 
            for node in node_xmls_data if node.get('content') and node.get('id')
        }
        if not node_content_map:
            logger.error("No valid node XML content with IDs provided for merging.")
            return {"status": "error", "message": "No valid node XML content with IDs provided."}

        relation_root_element = ET.fromstring(relation_xml_content)
        
        # Determine the actual root for iteration. If relation_xml_content is a full <xml> doc,
        # final_root will be the <xml> element. If it's just one <block>, final_root will contain that block.
        if relation_root_element.tag.lower() == "xml":
            final_xml_tree = ET.ElementTree(ET.Element(relation_root_element.tag, relation_root_element.attrib))
            # The elements to iterate for build_node are children of relation_root_element
            processing_root_for_iteration = relation_root_element 
        else: 
            # Assuming relation_xml_content might be just the top-level block or a fragment
            # Create a standard <xml ...> wrapper
            logger.info(f"Relation XML root is <{relation_root_element.tag}>. Wrapping it in <xml> for final structure.")
            final_xml_wrapper_element = ET.Element("xml", xmlns="https://developers.google.com/blockly/xml")
            final_xml_wrapper_element.append(relation_root_element) # Add the original root as a child
            final_xml_tree = ET.ElementTree(final_xml_wrapper_element)
            # The element to iterate for build_node is the relation_root_element itself
            processing_root_for_iteration = final_xml_wrapper_element

        final_root_to_build_into = final_xml_tree.getroot()
        
        data_block_counters = {}

        def get_next_data_block_no(block_type: str, context_path: str) -> int:
            is_reset_context = any(ctx_type in context_path for ctx_type in data_block_no_reset_types if ctx_type)
            
            counter_key = block_type
            if is_reset_context and context_path:
                 path_parts = [p for p in context_path.split('/') if p]
                 if path_parts:
                    parent_marker = path_parts[-1] 
                    counter_key = f"{parent_marker}_{block_type}"
            
            current_no = data_block_counters.get(counter_key, 0) + 1
            data_block_counters[counter_key] = current_no
            return current_no

        def build_node(relation_element: ET.Element, final_parent_element: ET.Element, current_context_path: str):
            if relation_element.tag != 'block':
                logger.debug(f"Skipping non-block element in relation tree: <{relation_element.tag}> during build_node")
                # If this non-block element (e.g. <next>, <statement>) contains children, process them.
                for child_element in relation_element:
                    build_node(child_element, final_parent_element, current_context_path) # final_parent_element might need to be adjusted
                return

            block_id = relation_element.get('id')
            block_type = relation_element.get('type')

            if not block_id or not block_type:
                logger.warning(f"Skipping relation element due to missing id or type: {ET.tostring(relation_element, encoding='unicode')}")
                return

            source_block_element_from_map = node_content_map.get(block_id)
            
            # Create the new element in the final_parent_element
            # If source_block_element_from_map exists, copy its tag, attributes, and children (fields)
            # Otherwise, create from relation_element (structure only)
            if source_block_element_from_map is not None:
                new_block_element = ET.SubElement(final_parent_element, source_block_element_from_map.tag, source_block_element_from_map.attrib)
                for child_field_or_value in source_block_element_from_map:
                    new_block_element.append(child_field_or_value)
            else:
                logger.warning(f"Node with ID '{block_id}' (type: {block_type}) not in node_xmls_data. Creating from relation structure.")
                new_block_element = ET.SubElement(final_parent_element, relation_element.tag, relation_element.attrib) # Use relation's tag and attribs
            
            # Ensure ID and Type from relation_element are set, as they are authoritative for structure
            new_block_element.set('id', block_id) 
            new_block_element.set('type', block_type)

            new_data_block_no = get_next_data_block_no(block_type, current_context_path)
            new_block_element.set('data-blockNo', str(new_data_block_no))

            # Process <statement> children from relation_element
            for rel_statement_element in relation_element.findall('statement'):
                statement_name = rel_statement_element.get('name')
                if not statement_name: continue

                # Find or create corresponding statement in new_block_element
                # Blockly expects <statement> to be direct child of <block>
                final_statement_element = new_block_element.find(f"statement[@name='{statement_name}']")
                if final_statement_element is None: 
                    final_statement_element = ET.SubElement(new_block_element, 'statement', rel_statement_element.attrib)
                
                inner_context_path = f"{current_context_path}{block_type}:{block_id}/DO:{statement_name}/"
                for child_rel_block in rel_statement_element.findall('block'):
                    build_node(child_rel_block, final_statement_element, inner_context_path)
            
            # Process <next> child from relation_element
            rel_next_element = relation_element.find('next')
            if rel_next_element is not None:
                # Blockly expects <next> to be direct child of <block>
                final_next_element = new_block_element.find('next')
                if final_next_element is None: 
                    final_next_element = ET.SubElement(new_block_element, 'next')
                for child_rel_block in rel_next_element.findall('block'):
                    build_node(child_rel_block, final_next_element, current_context_path) 

        # Iterate over the children of the processing_root_for_iteration (which could be <xml> or a wrapper we made)
        # These children should be the top-level <block> elements.
        for top_level_relation_block in processing_root_for_iteration.findall('block'):
            build_node(top_level_relation_block, final_root_to_build_into, f"{top_level_relation_block.get('type', 'root')}:{top_level_relation_block.get('id', 'unknown')}/")
        
        # Special case: if processing_root_for_iteration was the single block itself (not wrapped)
        if processing_root_for_iteration.tag == 'block' and not list(final_root_to_build_into.findall('block')):
             build_node(processing_root_for_iteration, final_root_to_build_into, f"{processing_root_for_iteration.get('type', 'single_root')}:{processing_root_for_iteration.get('id', 'unknown')}/")


        final_xml_tree.write(final_flow_file_path, encoding='utf-8', xml_declaration=True)
        logger.info(f"Successfully merged XMLs into {final_flow_file_path}")
        return {"status": "success", "file_path": final_flow_file_path}

    except ET.ParseError as e:
        logger.error(f"XML Parsing error during merge: {e}")
        return {"status": "error", "message": f"XML Parsing error: {e}"}
    except IOError as e:
        logger.error(f"File I/O error during merge: {e}")
        return {"status": "error", "message": f"File I/O error: {e}"}
    except Exception as e:
        logger.exception(f"Unexpected error during XML merge for {final_flow_file_path}")
        return {"status": "error", "message": f"Unexpected error: {e}"} 