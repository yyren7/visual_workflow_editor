from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


class GeneratedXmlFile(BaseModel):
    block_id: str = Field(description="The unique ID used in the generated XML <block id='xxx'>.")
    type: str = Field(description="The type of the operation/block.")
    source_description: str = Field(description="The natural language description of the step from parsing.")
    status: Literal["success", "failure"] = Field(description="Status of the XML generation for this block.")
    file_path: Optional[str] = Field(None, description="Full path to the generated .xml file if successful.")
    xml_content: Optional[str] = Field(None, description="The generated XML content. Primarily for debugging or intermediate use.")
    error_message: Optional[str] = Field(None, description="Error message if generation failed.")

class RobotFlowAgentState(BaseModel):
    """
    Represents the state of the Robot Flow Agent.
    """
    messages: List[BaseMessage] = Field(default_factory=list, description="The history of messages in the conversation.")
    
    user_input: Optional[str] = Field(None, description="The latest input from the user.")
    raw_user_request: Optional[str] = Field(None, description="The initial, un-enriched user request for the current flow.")
    robot_model: Optional[str] = Field(None, description="The confirmed robot model to be used.")
    active_plan_basis: Optional[str] = Field(None, description="The current text basis for planning (can be raw_user_request or a revised plan).")

    dialog_state: str = Field("initial", description="The current state of the dialog with the user, e.g., 'initial', 'awaiting_robot_model', 'awaiting_enrichment_confirmation', 'processing_enriched_input', 'input_understood', 'individual_xmls_generated', 'relation_xml_generated', 'flow_completed', 'error'.")
    
    clarification_question: Optional[str] = Field(None, description="A question posed to the user for clarification.")
    proposed_enriched_text: Optional[str] = Field(None, description="The LLM-enriched version of the user's request, pending user confirmation.")
    enriched_structured_text: Optional[str] = Field(None, description="The confirmed, enriched text that will be parsed.")
    
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration values, potentially loaded from a file or environment, like API keys, paths, etc.")
    
    # Outputs from Step 1 (understand_input_node)
    parsed_flow_steps: Optional[List[Dict[str, Any]]] = Field(None, description="The structured representation of the flow steps, parsed from the enriched input text. Each item is a dict matching ParsedStep.")
    parsed_robot_name: Optional[str] = Field(None, description="Robot name as parsed directly from the enriched text in Step 1.")

    # --- Outputs from Step 2 (generate_individual_xmls_node) ---
    generated_node_xmls: Optional[List[GeneratedXmlFile]] = Field(None, description="Information about each generated individual XML node file.")
    # --- End of Step 2 outputs ---

    # Outputs from Step 3 (generate_relation_xml_node)
    relation_xml_content: Optional[str] = Field(None, description="The content of the generated relation.xml file.")
    relation_xml_path: Optional[str] = Field(None, description="Path to the saved relation.xml file.")

    # Outputs from Step 4 (generate_final_flow_xml_node)
    final_flow_xml_content: Optional[str] = None
    final_flow_xml_path: Optional[str] = None
    
    current_step_description: Optional[str] = Field(None, description="A human-readable description of the current processing step.")
    error_message: Optional[str] = Field(None, description="A message describing an error if one occurred.")
    upload_status: Optional[str] = None # To track file upload status e.g. "success", "remote_address_offline"
    is_error: bool = False

    class Config:
        arbitrary_types_allowed = True 