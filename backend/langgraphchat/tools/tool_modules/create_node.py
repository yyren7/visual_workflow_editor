from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
import os
import json
import xml.etree.ElementTree as ET
from database.connection import get_db_context
from backend.app.services.flow_service import FlowService
from backend.langgraphchat.context import current_flow_id_var
from backend.langgraphchat.utils.logging import logger
import uuid
from backend.langgraphchat.adapters.xml_processing_adapter import process_node_data_and_save_to_db

XML_NODE_DEFINITIONS_PATH = "database/node_database/quick-fcpr/"
XML_SAVE_PATH = "/workspace/database/flow_database/result/"

# 仅注册带前缀的 Blockly 命名空间，以期望 ElementTree 在输出时使用它
ET.register_namespace("blockly", "https://developers.google.com/blockly/xml")
# ET.register_namespace("", "https://developers.google.com/blockly/xml") # 移除这个，因为它主要配合 default_namespace

class ExecuteCreateNodeSchema(BaseModel):
    node_id: str = Field(description="The pre-generated ID for the node.")
    node_type: str = Field(description="The type of the node (must match an XML definition file name).")
    label: str = Field(description="The display label for the node.")
    properties: Dict[str, Any] = Field(description="A dictionary of all properties for the node, pre-processed by the agent.")
    position: Optional[Dict[str, float]] = Field(None, description="Position (x, y) for the node on the canvas.")
    # Removed use_llm_for_properties, llm_client
    # Removed node_label, type_alias as these should be resolved by the agent into 'label' and 'node_type'

def execute_create_node_func(
    node_id: str,
    node_type: str,
    label: str,
    properties: Dict[str, Any],
    position: Optional[Dict[str, float]] = None,
    # **kwargs # Removing kwargs for now, agent should provide all in 'properties'
) -> Dict[str, Any]:
    """
    Executes the creation of a node using pre-processed data:
    1. Loads an XML template based on node_type.
    2. Modifies and fills the XML template with the provided properties.
    3. Saves the generated XML to a file named <flow_id>.xml.
    4. Calls an adapter to process this node data and save it to the database using the provided node_id, label, properties, and position.
    """
    try:
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("Execute create node failed: Cannot get current flow_id from context.")
            return {"success": False, "message": "Cannot get current flow ID.", "error": "Context error: Missing flow_id"}

        logger.info("=" * 40)
        logger.info(f"Execute Create Node Tool called (Flow ID: {target_flow_id})")
        logger.info(f"Attempting to create node: ID='{node_id}', Type='{node_type}', Label='{label}'")
        logger.debug(f"Received properties: {properties}")
        logger.debug(f"Received position: {position}")

        xml_defined_properties = {} # To store defaults from XML

        xml_template_file_path = os.path.join(XML_NODE_DEFINITIONS_PATH, f"{node_type}.xml")
        logger.info(f"Looking for node definition XML: {xml_template_file_path}")

        if not os.path.exists(xml_template_file_path):
            logger.error(f"Node type '{node_type}' definition file not found: {xml_template_file_path}")
            available_xml_files = [f.replace('.xml', '') for f in os.listdir(XML_NODE_DEFINITIONS_PATH) if f.endswith('.xml')]
            error_message = f"Node type '{node_type}' is invalid. XML definition file '{xml_template_file_path}' not found."
            if available_xml_files: error_message += f" Available node types: {', '.join(available_xml_files)}."
            else: error_message += f" No XML definition files found in '{XML_NODE_DEFINITIONS_PATH}'."
            return {"success": False, "message": error_message, "error": "Node definition XML not found"}

        try:
            tree = ET.parse(xml_template_file_path)
            root = tree.getroot()
            namespaces = {'blockly': 'https://developers.google.com/blockly/xml'}
            block_element = root.find(".//blockly:block", namespaces)
            if block_element is not None:
                for field in block_element.findall("blockly:field", namespaces):
                    param_name = field.get("name")
                    if param_name:
                        xml_defined_properties[param_name] = field.text if field.text is not None else ""
                logger.info(f"Loaded default properties from '{xml_template_file_path}': {xml_defined_properties}")
            else:
                logger.warning(f"No <block> element found in XML template '{xml_template_file_path}'. No default properties loaded.")
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML template file '{xml_template_file_path}': {e}")
            return {"success": False, "message": f"Failed to parse node definition file '{xml_template_file_path}'.", "error": f"XML ParseError: {e}"}

        # Start with XML defaults, then update with provided properties from agent/caller
        final_node_specific_properties = xml_defined_properties.copy()
        if properties: # Properties from agent/caller
            final_node_specific_properties.update(properties)
        
        logger.info(f"Final merged node-specific properties for XML: {final_node_specific_properties}")

        if block_element is not None:
            namespaces = {'blockly': 'https://developers.google.com/blockly/xml'}
            for field in block_element.findall("blockly:field", namespaces):
                param_name = field.get("name")
                if param_name in final_node_specific_properties:
                    field.text = str(final_node_specific_properties[param_name])
            logger.info("XML template populated with final properties.")
        else: 
            logger.warning("No <block> element in XML to populate; if properties were expected here, they weren't written to XML fields.")

        os.makedirs(XML_SAVE_PATH, exist_ok=True)
        output_xml_filename = f"{target_flow_id}.xml" # Consider if filename needs to be more unique if multiple nodes are created for one flow
        output_xml_full_path = os.path.join(XML_SAVE_PATH, output_xml_filename)
        
        try:
            tree.write(output_xml_full_path, 
                       encoding='utf-8', 
                       xml_declaration=True)
            logger.info(f"Modified XML saved to: {output_xml_full_path}")
        except Exception as e:
            logger.error(f"Failed to save modified XML to '{output_xml_full_path}': {e}")
            return {"success": False, "message": f"Failed to save generated XML file.", "error": str(e)}

        # Use the provided node_id from agent
        logger.info(f"Using provided Node ID: {node_id}")

        if not position:
            import random
            position = {"x": random.randint(100, 800), "y": random.randint(100, 600)}
            logger.info(f"Generated random position as none was provided: {position}")

        # The properties sent to the adapter should be the complete set used for the node,
        # which might be more than what's in the XML fields (e.g. custom data not in XML schema).
        # 'final_node_specific_properties' here is what was used to populate XML.
        # If the agent is intended to provide a richer set of properties beyond XML,
        # the 'properties' input to this function should be that richer set.
        # For now, assuming final_node_specific_properties is what we want to save.
        adapter_result = process_node_data_and_save_to_db(
            flow_id=target_flow_id,
            node_id=node_id, # Use the ID from agent
            node_type_from_tool=node_type,
            node_label=label, # Use label from agent
            position=position,
            all_node_properties=final_node_specific_properties # These are merged XML defaults + agent/caller provided
        )

        if adapter_result.get("success"):
            logger.info(f"Node '{label}' (ID: {node_id}) creation executed successfully. XML saved, DB updated by adapter.")
            logger.info("=" * 40)
            return {
                "success": True,
                "message": f"Successfully executed creation of node '{label}' (Type: {node_type}). XML saved, data sent to DB.",
                "xml_file_path": output_xml_full_path,
                "node_data_db_response": adapter_result 
            }
        else:
            logger.error(f"Adapter failed to process/save node data for node {node_id}. Message: {adapter_result.get('message')}")
            return {
                "success": False,
                "message": f"Node '{label}' XML saved, but failed to save data to DB via adapter. Adapter msg: {adapter_result.get('message')}",
                "xml_file_path": output_xml_full_path, 
                "error": f"Adapter Error: {adapter_result.get('message')}"
            }

    except Exception as e:
        logger.error(f"Unhandled exception in execute_create_node_func: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"success": False, "message": f"An unexpected error occurred: {str(e)}", "error": "Internal tool error"}

# Renamed from create_node_structured_tool to reflect its role
create_node_execution_tool = StructuredTool.from_function(
    func=execute_create_node_func,
    name="execute_create_node", # Changed name to reflect execution
    description="Executes the creation of a new node in the workflow diagram using pre-processed data (ID, type, label, properties, position) and saves it.",
    args_schema=ExecuteCreateNodeSchema
) 