import uuid
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import asyncio
import logging

logger = logging.getLogger(__name__)
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM # For consistent interface
from ..definitions import ToolResult # Relative import assuming definitions.py is in the parent tools directory

# XML_NODE_DEFINITIONS_PATH will be needed here if the agent needs to validate node_type against available XMLs
# However, for now, let's assume the execution part handles XML loading and validation.
# If the agent needs to know about available node types, this might need to be refactored.

class CreateNodeAgentParams(BaseModel):
    node_type: str = Field(description="The type of the node to create (should correspond to an available node definition).")
    node_label: Optional[str] = Field(None, description="Label for the node.")
    properties: Optional[Dict[str, Any]] = Field(None, description="User-provided properties for the node.")
    position: Optional[Dict[str, float]] = Field(None, description="Optional position (x, y) for the node.")
    use_llm_for_properties: bool = Field(False, description="Whether to use LLM to suggest/enhance properties.")
    # Add any other parameters that the agent logic might need to decide on node creation.
    # For example, if the agent needs to decide *which* type of node, or *if* a node should be created.


async def generate_node_properties_llm_agent( # Renamed to avoid conflict if original is kept temporarily
    node_type: str, 
    node_label: str,
    llm_client: DeepSeekLLM
) -> Tuple[Dict[str, Any], bool]:
    """
    Generates recommended node properties based on node type and label using LLM.
    (Moved from create_node.py)
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
            return {}, False
            
        logger.info(f"LLM generated properties for {node_type} - {node_label}: {result}")
        return result, True
        
    except Exception as e:
        logger.error(f"Error during LLM property generation for {node_type} - {node_label}: {str(e)}")
        return {}, False

async def create_node_agent_func(
    params: CreateNodeAgentParams,
    llm_client: DeepSeekLLM 
) -> ToolResult:
    """
    Prepares data for creating a new node, potentially using an LLM for property suggestions.
    This function DOES NOT save anything to the database or file system.
    """
    logger.info(f"Agent preparing to create node: Type='{params.node_type}', Label='{params.node_label}'")

    final_properties = params.properties.copy() if params.properties else {}
    node_id = f"node_{str(uuid.uuid4())[:8]}" # Agent can propose an ID
    
    effective_label = params.node_label or params.node_type # Simplified label logic for agent

    if params.use_llm_for_properties:
        logger.info(f"Agent attempting to use LLM for properties: Type='{params.node_type}', Label='{effective_label}'")
        # Ensure llm_client is provided if use_llm_for_properties is True
        if not llm_client:
            logger.warning("use_llm_for_properties is True, but no llm_client was provided to the agent.")
            return ToolResult(
                success=False,
                message="LLM property generation requested, but LLM client not available to agent."
            )
        
        llm_props, llm_success = await generate_node_properties_llm_agent(
            params.node_type, 
            effective_label, 
            llm_client
        )
        if llm_success:
            logger.info(f"Agent received LLM properties: {llm_props}")
            # Merge LLM properties: LLM suggestions can be overridden by user-provided properties
            # Or, decide on a merging strategy (e.g., user properties take precedence)
            merged_props = llm_props.copy()
            if params.properties:
                merged_props.update(params.properties) # User properties override LLM
            final_properties = merged_props
        else:
            logger.warning("Agent's LLM property generation failed. Proceeding with user-provided properties if any.")
            # If LLM fails, we fall back to user-provided properties (already in final_properties or empty)

    # Prepare the data packet that the execution tool would need
    node_data_to_create = {
        "node_id": node_id, # Proposed ID
        "node_type": params.node_type,
        "label": effective_label,
        "properties": final_properties,
        "position": params.position # Pass through position if provided
    }

    logger.info(f"Agent successfully prepared data for node creation: ID='{node_id}', Data: {node_data_to_create}")
    return ToolResult(
        success=True,
        message=f"Successfully prepared data to create node '{effective_label}' (Type: {params.node_type}).",
        data=node_data_to_create
    )

# Example usage (for testing purposes, would not be in final agent tool usually)
# async def main():
#     # Mock LLM client
#     class MockLLM:
#         async def structured_output(self, prompt, system_prompt, schema):
#             print("MockLLM structured_output called")
#             return {"mock_prop_llm": "llm_value"}, True

#     llm = MockLLM()
    
#     # Test case 1: No LLM, just basic properties
#     params1 = CreateNodeAgentParams(
#         node_type="Action", 
#         node_label="Perform Action", 
#         properties={"user_prop": "user_value"},
#         position={"x": 10, "y": 20}
#     )
#     result1 = await create_node_agent_func(params1, llm)
#     print(f"Result 1: {result1}")

#     # Test case 2: With LLM
#     params2 = CreateNodeAgentParams(
#         node_type="Decision", 
#         node_label="Make Decision", 
#         properties={"user_prop_decision": "user_value_decision"},
#         use_llm_for_properties=True,
#         position={"x": 100, "y": 200}
#     )
#     result2 = await create_node_agent_func(params2, llm)
#     print(f"Result 2: {result2}")
    
#     # Test case 3: With LLM, no user properties
#     params3 = CreateNodeAgentParams(
#         node_type="Input", 
#         node_label="Get Input",
#         use_llm_for_properties=True
#     )
#     result3 = await create_node_agent_func(params3, llm)
#     print(f"Result 3: {result3}")

# if __name__ == "__main__":
#     asyncio.run(main()) 