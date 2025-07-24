import asyncio
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
    sse_event_queue: Optional[asyncio.Queue] = Field(default=None, exclude=True, description="SSE event queue for real-time updates from graph nodes.")
    
    # --- 新增: 用于进度事件通信的字段 ---
    current_chat_id: Optional[str] = Field(None, description="Current chat/thread ID for sending progress events via SSE.")
    thread_id: Optional[str] = Field(None, description="Thread ID for LangGraph state management.")
    
    user_input: Optional[str] = Field(None, description="The latest input from the user, consumed after processing by a node.")
    current_user_request: Optional[str] = Field(None, description="The active user request (initialized from first user_input, then revised by feedback) that serves as the basis for the current flow or sub-flow.")
    user_advice: Optional[str] = Field(None, description="User's feedback/advice for revising the current task description.")
    active_plan_basis: Optional[str] = Field(None, description="The current text basis for planning (can be current_user_request or a revised plan after user feedback).")

    dialog_state: Optional[Literal[
        # --- Generic States ---
        "initial",                                 # Initial state upon entering the subgraph.
        "error",                                   # A non-recoverable error occurred in a node.
        "generation_failed",                       # A failure happened during an LLM generation step, might be recoverable.
        
        # --- SAS Specific States ---
        "sas_step1_tasks_generated",               # Step 1 (user_input_to_task_list) completed successfully.
        "sas_step2_module_steps_generated_for_review", # Step 2 (process_to_module_steps) completed, awaiting review.
        "sas_step3_completed",                     # Step 3 (parameter_mapping) completed successfully.

        # --- Review & Refine States ---
        "sas_awaiting_task_list_review",           # System has presented the task list and is awaiting user acceptance or feedback.
        "sas_awaiting_module_steps_review",        # System has presented the module steps and is awaiting user acceptance or feedback.
        "sas_awaiting_task_list_revision_input",   # System received feedback on tasks, awaiting full revised description.
        "sas_awaiting_module_steps_revision_input",# System received feedback on module steps, awaiting full revised description.

        # --- Routing States (internal signals for graph transitions) ---
        "sas_module_steps_accepted_proceeding",    # User accepted module steps, proceeding to the next phase (e.g., parameter mapping).
        "sas_all_steps_accepted_proceed_to_xml",   # User accepted all reviewable steps, proceeding to XML generation.
        "sas_step3_to_merge_xml",                  # Internal state indicating transition from step 3 to XML merging.
        "sas_merging_completed",                   # State after sas_merge_xml_node completes successfully.
        "sas_merging_completed_no_files",          # State after sas_merge_xml_node completes but finds no files to merge.
        "sas_merging_done_ready_for_concat",       # State indicating merging is done and ready for concatenation.
        
        # --- XML Generation States ---
        "generating_xml_relation",                 # Process is currently generating the relation XML.
        "generating_xml_final",                    # Process is currently generating the final merged XML.
        "final_xml_generated_success",             # Final XML has been generated and saved successfully.
        "sas_generating_individual_xmls",          # State indicating the process is generating individual XML files.
        "sas_individual_xmls_generated_ready_for_mapping", # State after individual XMLs are generated, ready for parameter mapping.
        "sas_xml_generation_approved",             # User has approved to proceed with XML generation.
        "sas_awaiting_xml_generation_approval",    # Waiting for user approval to start XML generation.

        # --- Error/Fallback States ---
        "sas_processing_error"                     # A specific error state for XML processing nodes.

    ]] = Field("initial", description="The current detailed state of the dialog within the robot flow subgraph.")
    
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

    completion_status: Optional[Literal["completed_success", "completed_partial", "needs_clarification", "error", "processing"]] = Field(None, description="Indicates how the graph concluded its execution for the current call.")

    merged_xml_file_paths: Optional[List[str]] = Field(default_factory=list, description="Paths to XML files after merging individual task XMLs.")

    class Config:
        arbitrary_types_allowed = True 