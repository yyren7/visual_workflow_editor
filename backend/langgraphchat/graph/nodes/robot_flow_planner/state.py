from typing import TypedDict, List, Dict, Any, Optional, Literal

from langchain_core.messages import BaseMessage


class RobotFlowAgentState(TypedDict):
    """
    Represents the state of the robot flow generation agent.
    It accumulates information as the agent progresses through the defined flow.
    """
    # Core conversation and input
    messages: List[BaseMessage]  # History of messages
    user_input: str  # Original user natural language input

    # New fields for clarification and enrichment
    raw_user_request: Optional[str] # Stores the initial core request if clarification is needed
    robot_model: Optional[str]
    dialog_state: Literal["initial", "awaiting_robot_model", "awaiting_enrichment_confirmation", "processing_enriched_input", "input_understood"]
    clarification_question: Optional[str] # If agent needs to ask something
    proposed_enriched_text: Optional[str] # Stores the LLM-enriched text before user confirmation
    enriched_structured_text: Optional[str] # The output of the new preprocessing step

    # Configuration from placeholders.md, loaded at the beginning
    config: Dict[str, str] # Stores values like output_dir_path, node_template_dir_path etc.
    
    # Step 1: Understand Input - Output
    # List of dictionaries, each representing a parsed operation/step from user input
    # Example: [{"type": "moveL", "params": {"point": "P1", "axis_control": "Z enable"}, "id_suggestion": "moveL_P1_Z_on"}, ...]
    parsed_flow_steps: Optional[List[Dict[str, Any]]] 

    # Step 2: Generate Independent Node XMLs - Output
    # List of dictionaries, each representing a generated individual XML node file
    # Example: [{"id": "block_uuid_1", "file_path": "/path/to/block_uuid_1.xml", "content": "<xml>...</xml>"}, ...]
    generated_node_xmls: Optional[List[Dict[str, str]]]

    # Step 3: Generate Node Relation Structure File - Output
    relation_xml_content: Optional[str]  # Content of the relation.xml file
    relation_xml_path: Optional[str] # Path to the generated relation.xml file

    # Step 4: Generate Final Flow File - Output
    final_flow_xml_path: Optional[str]  # Path to the final generated flow.xml

    # Utility fields
    current_step_description: Optional[str] # For logging and debugging, describes current high-level step
    error_message: Optional[str]  # To store any error messages during the flow
    is_error: bool # Flag to indicate if an error occurred 