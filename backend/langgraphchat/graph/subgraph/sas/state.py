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

class TaskDefinition(BaseModel):
    name: str = Field(description="A concise and descriptive name for the task.")
    type: str = Field(description="The category of the task (e.g., MainTask, GraspTask).")
    details: List[str] = Field(default_factory=list, description="Detailed module steps generated for this task by SAS Step 2, as a list of strings, or other relevant details.")
    sub_tasks: List[str] = Field(default_factory=list, description="A list of names of other tasks that are nested within or executed as part of this task.")
    description: Optional[str] = Field(None, description="A brief natural language description of the task's purpose.")

class RobotFlowAgentState(BaseModel):
    """
    Represents the state of the Robot Flow Agent.
    """
    messages: List[BaseMessage] = Field(default_factory=list, description="The history of messages in the conversation.")
    
    user_input: Optional[str] = Field(None, description="The latest input from the user, consumed after processing by a node.")
    current_user_request: Optional[str] = Field(None, description="The active user request (initialized from first user_input, then revised by feedback) that serves as the basis for the current flow or sub-flow.")
    user_advice: Optional[str] = Field(None, description="User's feedback/advice for revising the current task description.")
    active_plan_basis: Optional[str] = Field(None, description="The current text basis for planning (can be current_user_request or a revised plan after user feedback).")

    dialog_state: Literal[
        "initial",                             #Initial state upon entering the subgraph
        "awaiting_robot_model_input",          #Robot model has been queried, awaiting user reply
        "awaiting_enrichment_confirmation",    #Enriched plan has been proposed, awaiting user confirmation
        "awaiting_user_input",                 #General state of waiting for user to provide new flow description or corrections
        "processing_user_input",               #Actively processing the latest user input (e.g., calling LLM for enrichment or parsing)
        "input_understood_ready_for_xml",      #User input processed, ready to start generating specific XML steps
        "generating_xml_individual",           #Generating individual XML nodes (detailed state)
        "generating_xml_relation",             #Generating relation XML (detailed state)
        "generating_xml_final",                #Generating final flow XML (detailed state)
        "generation_failed",                   #Any XML generation step failed, awaiting user correction
        "final_xml_generated_success",         #Final XML successfully generated, ready to exit subgraph
        "sub_flow_cancelled_by_user",           #User has indicated to cancel current flow editing (can be added in the future)
        "sas_step1_tasks_generated",           # SAS step 1 (user_input_to_task_list) completed successfully
        "sas_step1_completed",                 # SAS step 1 (user_input_to_process) completed successfully - to be deprecated or renamed
        "sas_step2_module_steps_generated_for_review", # SAS step 2 generated module steps, awaiting review
        "sas_step2_completed",                 # SAS step 2 (process_description_to_module_steps) completed successfully
        "sas_module_steps_accepted_proceeding", # SAS: Module steps reviewed and accepted, ready for next step (e.g. param mapping)
        "sas_step3_completed",                  # SAS step 3 (parameter_mapping) completed successfully
        "sas_awaiting_task_list_review",        # SAS: System has presented the task list and is awaiting user acceptance or feedback.
        "sas_awaiting_module_steps_review",     # SAS: System has presented the module steps and is awaiting user acceptance or feedback.
        "sas_description_updated_for_regeneration" # SAS: User description has been updated and is ready for regeneration of tasks.
    ] = Field("initial", description="The current detailed state of the dialog within the robot flow subgraph.")
    
    clarification_question: Optional[str] = Field(None, description="A question posed to the user for clarification (e.g. about robot model, or ambiguous request).")
    proposed_enriched_text: Optional[str] = Field(None, description="The LLM-enriched version of the user's request, pending user confirmation.")
    enriched_structured_text: Optional[str] = Field(None, description="The confirmed, enriched text that will be parsed by understand_input_node.")
    
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration values, potentially loaded from a file or environment, like API keys, paths, etc.")
    
    # Outputs from Step 1 (understand_input_node)
    parsed_flow_steps: Optional[List[Dict[str, Any]]] = Field(None, description="The structured representation of the flow steps, parsed from the enriched input text. Each item is a dict matching ParsedStep.")

    # --- Outputs from Step 2 (generate_individual_xmls_node) ---
    generated_node_xmls: Optional[List[GeneratedXmlFile]] = Field(default_factory=list, description="Information about each generated individual XML node file.")
    # --- End of Step 2 outputs ---

    # Outputs from Step 3 (generate_relation_xml_node)
    relation_xml_content: str = Field(default="", description="The content of the generated relation.xml file.")
    relation_xml_path: str = Field(default="", description="Path to the saved relation.xml file.")

    # Outputs from Step 4 (generate_final_flow_xml_node)
    final_flow_xml_content: Optional[str] = None
    final_flow_xml_path: Optional[str] = None
    
    # SAS Step 1 outputs
    sas_step1_generated_tasks: Optional[List[TaskDefinition]] = Field(None, description="The structured list of tasks generated from user input by SAS step 1.")
    
    # SAS Step 2 outputs  
    sas_step2_module_steps: Optional[str] = Field(None, description="The specific, executable module steps generated from the process description by SAS step 2.")
    
    # SAS Step 3 outputs
    sas_step3_parameter_mapping: Optional[Dict[str, Dict[str, str]]] = Field(None, description="The mapping from logical parameters to actual parameter file slots, generated by SAS step 3.")
    sas_step3_mapping_report: Optional[str] = Field(None, description="Human-readable report of the parameter mapping process and results from SAS step 3.")

    run_output_directory: Optional[str] = Field(None, description="The directory path for saving outputs for the current run.")

    task_list_accepted: bool = Field(False, description="Flag indicating if the user has accepted the current task list.")
    module_steps_accepted: bool = Field(False, description="Flag indicating if the user has accepted the module steps generated in Step 2.")
    revision_iteration: int = Field(default=0, description="Counter for revision cycles.")

    current_step_description: Optional[str] = Field(None, description="A human-readable description of the current processing step.")
    error_message: Optional[str] = Field(None, description="A message describing an error if one occurred.")
    upload_status: Optional[str] = None # To track file upload status e.g. "success", "remote_address_offline"
    is_error: bool = False

    language: str = Field("zh", description="The language setting for user interactions, e.g., 'zh' or 'en'.")

    subgraph_completion_status: Optional[Literal["completed_success", "completed_partial", "needs_clarification", "error"]] = Field(None, description="Indicates how the robot_flow_subgraph concluded its execution for the current call.")

    class Config:
        arbitrary_types_allowed = True 