import xml.etree.ElementTree as ET
import json
from typing import Dict, Any
from backend.app.services.flow_service import FlowService
from database.connection import get_db_context
from backend.langgraphchat.utils.logging import logger

def convert_xml_to_json(xml_string: str) -> Dict[str, Any]:
    try:
        root = ET.fromstring(xml_string)
        
        def _etree_to_dict_inner(t):
            key = t.tag
            value = {}
            # Attributes
            if t.attrib:
                value.update(t.attrib)
            
            # Children
            children = list(t)
            if children:
                child_dict = {}
                for child in children:
                    child_key, child_value = _etree_to_dict_inner(child)
                    if child_key in child_dict:
                        if not isinstance(child_dict[child_key], list):
                            child_dict[child_key] = [child_dict[child_key]]
                        child_dict[child_key].append(child_value)
                    else:
                        child_dict[child_key] = child_value
                value.update(child_dict)
            
            # Text
            if t.text and t.text.strip():
                text = t.text.strip()
                if not value: # If no attributes or children, tag value is just text
                    value = text
                else: # Otherwise, add text as a special key, e.g., '#text' or 'value'
                    value['_text'] = text # Using '_text' to avoid collision
            elif not value and not children: # Element has no attributes, no children, and no text
                 value = None # Or an empty string '' depending on preference

            return key, value

        # The top-level element
        top_key, top_value = _etree_to_dict_inner(root)
        return {top_key: top_value}

    except ET.ParseError as e:
        logger.error(f"Error parsing XML: {e}")
        raise ValueError(f"Cannot parse XML: {e}") from e
    except Exception as e:
        logger.error(f"Unknown error converting XML to JSON: {e}")
        raise

def save_node_data_to_db(
    flow_id: str,
    node_data: Dict[str, Any],
    flow_service: FlowService
) -> bool:
    """Saves node data to the database via FlowService."""
    try:
        logger.info(f"Adapter: Preparing to save node data to flow_id: {flow_id}")
        flow_data_obj = flow_service.get_flow(flow_id)
        if not flow_data_obj:
            logger.error(f"Adapter: Cannot retrieve flow data for ID={flow_id}")
            return False
        
        flow_data = {} # Initialize as an empty dict
        if hasattr(flow_data_obj, 'model_dump'):
            flow_data = flow_data_obj.model_dump()
        elif isinstance(flow_data_obj, dict):
            flow_data = flow_data_obj.copy() # Use copy to avoid modifying the original if it's mutable
        else:
            try:
                flow_data = dict(flow_data_obj)
            except TypeError as e:
                logger.error(f"Adapter: Cannot convert flow_data of type {type(flow_data_obj)} to dict: {e}")
                return False

        if "nodes" not in flow_data or not isinstance(flow_data.get("nodes"), list):
            flow_data["nodes"] = []
            
        node_exists = False
        if "id" in node_data:
            for i, existing_node in enumerate(flow_data["nodes"]):
                if isinstance(existing_node, dict) and existing_node.get("id") == node_data["id"]:
                    flow_data["nodes"][i] = node_data
                    node_exists = True
                    logger.info(f"Adapter: Updated existing node ID: {node_data['id']}")
                    break
        
        if not node_exists:
            flow_data["nodes"] .append(node_data)
            logger.info(f"Adapter: Added new node to flow: {node_data.get('id', 'Unknown ID')}")
        
        current_name = flow_data.get("name")
        success_db = flow_service.update_flow(
            flow_id=flow_id,
            data=flow_data, 
            name=current_name 
        )
        
        if not success_db:
            logger.error(f"Adapter: Database update failed for flow {flow_id}")
            return False
        
        logger.info(f"Adapter: Node data successfully saved to database for flow {flow_id}")
        return True
        
    except Exception as e:
        logger.error(f"Adapter: Database operation failed: {str(e)}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return False

def process_node_data_and_save_to_db(
    flow_id: str,
    node_id: str,
    node_type_from_tool: str, # Renamed to avoid confusion with react flow 'type'
    node_label: str,
    position: Dict[str, float],
    all_node_properties: Dict[str, Any] 
) -> Dict[str, Any]:
    """
    Constructs the node_data dictionary for database storage and saves it.
    The actual XML file is managed by the caller.
    """
    try:
        logger.info(f"Adapter: Processing node data for node_id: {node_id} in flow_id: {flow_id}")

        # This is the structure React Flow typically expects for a node.
        # 'type' here is the React Flow node type (e.g., 'custom', 'input', 'output', or your generic type)
        # 'data.nodeType' can be your application-specific node type from the tool.
        node_data_for_db = {
            "id": node_id,
            "type": "generic", # This should be a valid React Flow node type string.
            "position": position,
            "data": {
                "label": node_label,
                "nodeType": node_type_from_tool, # Application-specific type
                # **all_node_properties # Spread all properties directly into data
            }
        }
        # Merge all_node_properties into data, but ensure not to overwrite core fields like label, nodeType
        for key, value in all_node_properties.items():
            if key not in ["label", "nodeType"]:
                 node_data_for_db["data"][key] = value
        
        # If you have a specific structure like 'nodeProperties' that front-end expects:
        node_data_for_db["data"]["nodeProperties"] = {
            "nodeId": node_id,
            "nodeType": node_type_from_tool,
            **all_node_properties # Or a filtered/structured version of properties
        }

        logger.debug(f"Adapter: Constructed node data for DB: {json.dumps(node_data_for_db, indent=2)}")

        with get_db_context() as db:
            flow_service = FlowService(db)
            save_success = save_node_data_to_db(flow_id, node_data_for_db, flow_service)

        if save_success:
            logger.info(f"Adapter: Node {node_id} data successfully processed and saved to DB.")
            return {"success": True, "message": "Node data successfully processed and saved to DB", "node_data": node_data_for_db}
        else:
            logger.error(f"Adapter: Node {node_id} data failed to save to DB.")
            return {"success": False, "message": "Node data failed to save to DB"}

    except Exception as e:
        logger.error(f"Adapter: Error in process_node_data_and_save_to_db: {str(e)}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return {"success": False, "message": f"Error processing and saving node data: {str(e)}"} 