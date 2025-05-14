from typing import Dict, Any, Optional, Tuple
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
import asyncio
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM
from backend.langgraphchat.adapters.xml_processing_adapter import process_node_data_and_save_to_db

XML_NODE_DEFINITIONS_PATH = "database/node_database/quick-fcpr/"
XML_SAVE_PATH = "/workspace/database/flow_database/result/"

async def generate_node_properties_llm(
    node_type: str, 
    node_label: str,
    llm_client: DeepSeekLLM
) -> Tuple[Dict[str, Any], bool]:
    """
    Generates recommended node properties based on node type and label using LLM.
    """
    try:
        prompt = f"""Please generate a suitable JSON object of properties for the following flowchart node:
        
Node Type: {node_type}
Node Label: {node_label}

Please generate a properties object. Property names should reflect common characteristics of this type of node, and property values should be placeholders or example values.
Return only the JSON object itself, without any other text. For example: {{"property_name": "value"}}
"""
        
        properties_schema = {
            "type": "object",
            "properties": {}, # Allow any properties
            "additionalProperties": True,
            "description": "Key-value pairs for node properties"
        }
        
        result, success = await llm_client.structured_output(
            prompt=prompt,
            system_prompt="You are an expert in flowchart node properties, adept at recommending suitable attributes for various node types. Please output properties in JSON object format.",
            schema=properties_schema
        )
        
        if not success or not isinstance(result, dict):
            logger.error(f"LLM failed to generate node properties or returned incorrect format for {node_type} - {node_label}. Result: {result}")
            return {}, False # Return False for success to indicate LLM failure
            
        logger.info(f"LLM generated properties for {node_type} - {node_label}: {result}")
        return result, True
        
    except Exception as e:
        logger.error(f"Error during LLM property generation for {node_type} - {node_label}: {str(e)}")
        return {}, False

def create_node_tool_func(
    node_type: str,
    node_label: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    position: Optional[Dict[str, float]] = None,
    use_llm_for_properties: bool = False,
    llm_client: Optional[DeepSeekLLM] = None,
    node_name: Optional[str] = None,
    label: Optional[str] = None,
    type_alias: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Creates a node: 
    1. Determines properties (user-provided, LLM-generated, or XML defaults).
    2. Loads an XML template based on node_type.
    3. Modifies and fills the XML template with the determined properties.
    4. Saves the generated XML to a file named <flow_id>.xml.
    5. Calls an adapter to process this node data and save it to the database.
    """
    try:
        target_flow_id = current_flow_id_var.get()
        if not target_flow_id:
            logger.error("Create node failed: Cannot get current flow_id from context.")
            return {"success": False, "message": "Cannot get current flow ID.", "error": "Context error: Missing flow_id"}

        logger.info("=" * 40)
        logger.info(f"Create Node Tool called (Flow ID: {target_flow_id})")

        actual_node_type = node_type or type_alias
        if not actual_node_type:
            logger.error(f"Missing required node_type parameter. Provided: node_type={node_type}, type_alias={type_alias}")
            return {"success": False, "message": "Create node failed: Missing node_type parameter.", "error": "Missing node_type"}

        effective_label = node_label or node_name or label or actual_node_type
        logger.info(f"Attempting to create node: Type='{actual_node_type}', Label='{effective_label}'")

        xml_defined_properties = {}
        user_provided_properties = {}
        llm_generated_properties = {}

        xml_template_file_path = os.path.join(XML_NODE_DEFINITIONS_PATH, f"{actual_node_type}.xml")
        logger.info(f"Looking for node definition XML: {xml_template_file_path}")

        if not os.path.exists(xml_template_file_path):
            logger.error(f"Node type '{actual_node_type}' definition file not found: {xml_template_file_path}")
            available_xml_files = [f.replace('.xml', '') for f in os.listdir(XML_NODE_DEFINITIONS_PATH) if f.endswith('.xml')]
            error_message = f"Node type '{actual_node_type}' is invalid. XML definition file '{xml_template_file_path}' not found."
            if available_xml_files: error_message += f" Available node types: {', '.join(available_xml_files)}."
            else: error_message += f" No XML definition files found in '{XML_NODE_DEFINITIONS_PATH}'."
            return {"success": False, "message": error_message, "error": "Node definition XML not found"}

        try:
            tree = ET.parse(xml_template_file_path)
            root = tree.getroot()
            block_element = root.find(".//block")
            if block_element is not None:
                for field in block_element.findall("field"):
                    param_name = field.get("name")
                    if param_name:
                        xml_defined_properties[param_name] = field.text if field.text is not None else ""
                logger.info(f"Loaded default properties from '{xml_template_file_path}': {xml_defined_properties}")
            else:
                logger.warning(f"No <block> element found in XML template '{xml_template_file_path}'. No default properties loaded.")
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML template file '{xml_template_file_path}': {e}")
            return {"success": False, "message": f"Failed to parse node definition file '{xml_template_file_path}'.", "error": f"XML ParseError: {e}"}

        if properties:
            user_provided_properties.update(properties)
        
        known_params = {'node_type', 'node_label', 'properties', 'position', 'use_llm_for_properties', 'llm_client', 'node_name', 'label', 'type_alias'}
        for key, value in kwargs.items():
            if key not in known_params:
                user_provided_properties[key] = value
        logger.info(f"User-provided properties (incl. kwargs): {user_provided_properties}")

        final_node_specific_properties = xml_defined_properties.copy()

        if use_llm_for_properties and llm_client:
            logger.info(f"Attempting to generate properties using LLM for node type '{actual_node_type}'.")
            try:
                llm_props, llm_success = asyncio.run(generate_node_properties_llm(actual_node_type, effective_label, llm_client))
                if llm_success:
                    llm_generated_properties = llm_props
                    logger.info(f"LLM generated properties: {llm_generated_properties}")
                    final_node_specific_properties.update(llm_generated_properties)
                else:
                    logger.warning("LLM property generation failed or returned no data. Using XML defaults and user-provided properties.")
            except Exception as e: 
                logger.error(f"Exception during LLM property generation: {e}")
                logger.warning("Proceeding without LLM-generated properties due to error.")
        
        if user_provided_properties:
            final_node_specific_properties.update(user_provided_properties)
        
        logger.info(f"Final merged node-specific properties: {final_node_specific_properties}")

        if block_element is not None:
            for field in block_element.findall("field"):
                param_name = field.get("name")
                if param_name in final_node_specific_properties:
                    field.text = str(final_node_specific_properties[param_name])
            logger.info("XML template populated with final properties.")
        else: 
            logger.warning("No <block> element in XML to populate; if properties were expected here, they weren't written to XML fields.")

        os.makedirs(XML_SAVE_PATH, exist_ok=True)
        output_xml_filename = f"{target_flow_id}.xml"
        output_xml_full_path = os.path.join(XML_SAVE_PATH, output_xml_filename)
        
        try:
            tree.write(output_xml_full_path, encoding='utf-8', xml_declaration=True)
            logger.info(f"Modified XML saved to: {output_xml_full_path}")
        except Exception as e:
            logger.error(f"Failed to save modified XML to '{output_xml_full_path}': {e}")
            return {"success": False, "message": f"Failed to save generated XML file.", "error": str(e)}

        node_id = f"node_{str(uuid.uuid4())[:8]}" 
        logger.info(f"Generated Node ID: {node_id}")

        if not position:
            import random
            position = {"x": random.randint(100, 800), "y": random.randint(100, 600)}
            logger.info(f"Generated random position: {position}")

        adapter_result = process_node_data_and_save_to_db(
            flow_id=target_flow_id,
            node_id=node_id,
            node_type_from_tool=actual_node_type,
            node_label=effective_label,
            position=position,
            all_node_properties=final_node_specific_properties
        )

        if adapter_result.get("success"):
            logger.info(f"Node '{effective_label}' (ID: {node_id}) creation process successful. XML saved, DB updated by adapter.")
            logger.info("=" * 40)
            return {
                "success": True,
                "message": f"Successfully created node '{effective_label}' (Type: {actual_node_type}). XML saved, data sent to DB.",
                "xml_file_path": output_xml_full_path,
                "node_data_db_response": adapter_result 
            }
        else:
            logger.error(f"Adapter failed to process/save node data for node {node_id}. Message: {adapter_result.get('message')}")
            return {
                "success": False,
                "message": f"Node '{effective_label}' XML saved, but failed to save data to DB via adapter. Adapter msg: {adapter_result.get('message')}",
                "xml_file_path": output_xml_full_path, 
                "error": f"Adapter Error: {adapter_result.get('message')}"
            }

    except Exception as e:
        logger.error(f"Unhandled exception in create_node_tool_func: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"success": False, "message": f"An unexpected error occurred: {str(e)}", "error": "Internal tool error"}

class CreateNodeSchema(BaseModel):
    node_type: str = Field(description="The type of the node to create (must match an XML definition file name).")
    node_label: Optional[str] = Field(None, description="Label for the node. Uses node_type or a generated name if not provided.")
    properties: Optional[Dict[str, Any]] = Field(None, description="Specific properties for the node, overriding XML defaults and LLM suggestions.")
    position: Optional[Dict[str, float]] = Field(None, description="Position (x, y) for the node on the canvas.")
    use_llm_for_properties: bool = Field(False, description="Set to true to use LLM to suggest properties if 'properties' field is not provided.")
    type_alias: Optional[str] = Field(None, alias="type", description="Alias for node_type.")

create_node_structured_tool = StructuredTool.from_function(
    func=create_node_tool_func,
    name="create_node",
    description="Creates a new node in the workflow diagram. Specify node_type. Optionally provide label, properties, position, and whether to use LLM for property suggestions.",
    args_schema=CreateNodeSchema
) 