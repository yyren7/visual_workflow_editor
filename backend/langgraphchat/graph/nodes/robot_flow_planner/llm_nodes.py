import logging
import json
from typing import List, Optional, Dict, Any, cast, Type, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, BaseMessage
from pydantic import BaseModel, Field
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

from .state import RobotFlowAgentState
from .prompt_loader import get_filled_prompt

logger = logging.getLogger(__name__)

# Define known robot models for normalization
KNOWN_ROBOT_MODELS = ["dobot_mg400", "dobot_cr5", "ur5e", "aubo_i5", "cool_robot_v1"]


async def invoke_llm_for_text_output( # Renamed for clarity, as it's now primarily for text
    llm: BaseChatModel,
    system_prompt_content: str, # Now takes content directly for simple prompts
    user_message_content: str,
    message_history: Optional[List[BaseMessage]] = None,
) -> Dict[str, Any]:
    messages: List[BaseMessage] = [SystemMessage(content=system_prompt_content)]
    if message_history:
        messages.extend(message_history)
    messages.append(HumanMessage(content=user_message_content))

    logger.info(f"Invoking LLM for raw text output.")
    chain = llm | StrOutputParser()
    try:
        ai_response_content = await chain.ainvoke(messages)
        return {"text_output": ai_response_content}
    except Exception as e:
        logger.error(f"LLM call for string output failed. Error: {e}", exc_info=True)
        return {"error": "LLM call for string output failed.", "details": str(e)}

async def invoke_llm_for_json_output(
    llm: BaseChatModel,
    system_prompt_template_name: str,
    placeholder_values: Dict[str, str],
    user_message_content: str,
    message_history: Optional[List[BaseMessage]] = None,
    json_schema: Optional[Type[BaseModel]] = None, # Must be provided for this function
) -> Dict[str, Any]:
    if not json_schema:
        return {"error": "json_schema must be provided to invoke_llm_for_json_output."}

    filled_system_prompt = get_filled_prompt(system_prompt_template_name, placeholder_values)
    if not filled_system_prompt:
        return {"error": f"Failed to load or fill system prompt: {system_prompt_template_name}"}

    messages: List[BaseMessage] = [SystemMessage(content=filled_system_prompt)]
    if message_history:
        messages.extend(message_history)
    messages.append(HumanMessage(content=user_message_content))

    logger.info(f"Invoking LLM. System prompt template: {system_prompt_template_name}, Expecting JSON for schema: {json_schema.__name__}")
    structured_llm = llm.with_structured_output(json_schema)
    try:
        ai_response = await structured_llm.ainvoke(messages)
        if isinstance(ai_response, BaseModel):
            return ai_response.dict(exclude_none=True)
        else:
            logger.error(f"LLM with_structured_output did not return a Pydantic model instance. Got: {type(ai_response)}")
            return {"error": "LLM structured output did not return a Pydantic model."}
    except Exception as e:
        logger.error(f"LLM call with_structured_output failed for schema {json_schema.__name__}. Error: {e}", exc_info=True)
        raw_output = ""
        try:
            raw_output_msg = await llm.ainvoke(messages)
            raw_output = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
        except Exception as e_raw:
            logger.error(f"Failed to get raw output from LLM after structured output error: {e_raw}", exc_info=True)
        return {"error": f"LLM call with_structured_output failed for schema {json_schema.__name__}.", "details": str(e), "raw_output": raw_output}


# --- Node 0: Preprocess and Enrich Input ---
async def preprocess_and_enrich_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 0: Preprocess and Enrich Input ---")
    state["current_step_description"] = "Preprocessing and enriching input"

    user_input = state.get("user_input", "").strip()
    robot_model = state.get("robot_model")
    dialog_state = state.get("dialog_state", "initial")
    raw_user_request = state.get("raw_user_request", user_input) # Default raw_user_request to current user_input if not set
    config = state.get("config", {})
    current_messages = state.get("messages", [])
    
    # Ensure raw_user_request is set if we are in initial state with a new input
    if dialog_state == "initial" and not state.get("raw_user_request"):
        state["raw_user_request"] = user_input
        raw_user_request = user_input


    # A. Handle user's response to robot model clarification
    if dialog_state == "awaiting_robot_model":
        logger.info(f"Received user response for robot model query: '{user_input}'")
        current_messages = current_messages + [HumanMessage(content=user_input)]
        
        # Normalize robot model
        normalize_prompt = (
            f"User provided robot model: '{user_input}'. "
            f"Known official models are: {', '.join(KNOWN_ROBOT_MODELS)}. "
            "Respond with the closest matching official model name from the list. "
            "If no close match (e.g., input is nonsensical or completely unrelated), respond with 'unknown_model'. "
            "Only output the official model name or 'unknown_model'."
        )
        norm_response = await invoke_llm_for_text_output(
            llm,
            system_prompt_content="You are a robot model normalization assistant.",
            user_message_content=normalize_prompt
        )

        if "error" in norm_response or not norm_response.get("text_output"):
            logger.error(f"Robot model normalization LLM call failed: {norm_response.get('error')}")
            state["error_message"] = "Failed to normalize robot model name."
            state["is_error"] = True
            state["dialog_state"] = "initial" # Reset to try again or stop
            return state

        normalized_model = norm_response["text_output"].strip()
        logger.info(f"LLM normalized '{user_input}' to '{normalized_model}'")
        current_messages.append(AIMessage(content=f"Normalized robot model from '{user_input}' to '{normalized_model}'."))


        if normalized_model.lower() == "unknown_model" or normalized_model not in KNOWN_ROBOT_MODELS:
            clarification_msg_content = f"Sorry, I couldn't recognize '{user_input}' or normalize it to a known model. Known models: {', '.join(KNOWN_ROBOT_MODELS)}. Please provide a valid robot model name."
            state["clarification_question"] = clarification_msg_content
            state["dialog_state"] = "awaiting_robot_model" # Ask again
            state["messages"] = current_messages + [AIMessage(content=clarification_msg_content)]
            return state
        
        state["robot_model"] = normalized_model
        robot_model = normalized_model # Update for current scope
        
        # Restore original request after getting model
        user_input = state["raw_user_request"] if state["raw_user_request"] else ""
        logger.info(f"Robot model confirmed/normalized to: {robot_model}. Original request was: '{user_input}'")
        dialog_state = "initial" # Transition to 'initial' to proceed with enrichment
        state["dialog_state"] = dialog_state


    # B. Handle user's response to enrichment confirmation
    elif dialog_state == "awaiting_enrichment_confirmation":
        logger.info(f"Received user response for enrichment confirmation: '{user_input}'")
        current_messages = current_messages + [HumanMessage(content=user_input)]
        
        if user_input.lower() == "yes":
            logger.info("User confirmed the enriched plan.")
            state["enriched_structured_text"] = state["proposed_enriched_text"]
            state["proposed_enriched_text"] = None
            state["clarification_question"] = None
            state["dialog_state"] = "processing_enriched_input"
            state["messages"] = current_messages + [AIMessage(content="User approved the enriched plan.")]
            # Fall through to C: (Check if ready for next step) or return, graph will re-evaluate
            return state
        else: # "no" or other feedback
            logger.info("User rejected or wants to modify the enriched plan.")
            # Simple reset: treat feedback as new raw input, keep robot model
            state["raw_user_request"] = user_input # The feedback becomes the new request
            state["user_input"] = user_input       # Also update user_input for the next cycle
            state["dialog_state"] = "initial"      # Restart enrichment with new input
            state["proposed_enriched_text"] = None
            state["enriched_structured_text"] = None
            state["clarification_question"] = None
            state["messages"] = current_messages + [AIMessage(content=f"User provided feedback on the plan: '{user_input}'. Restarting enrichment.")]
            # This will loop back to robot model check (which should pass) and then re-enrich.
            # Need to ensure that user_input for enrichment is now the feedback.
            # The 'user_input = state["raw_user_request"]' line in section A would re-fetch this.
            return state


    # C. Initial entry, or after robot model is known/confirmed, or after enrichment rejection (now re-evaluating)
    if not robot_model: # If still no robot model (e.g. initial entry and no model provided)
        logger.info("Robot model is unknown. Requesting clarification.")
        if not state.get("raw_user_request"): state["raw_user_request"] = user_input

        clarification_msg_content = f"请问您使用的是什么型号的机器人？例如：{', '.join(KNOWN_ROBOT_MODELS)}"
        state["clarification_question"] = clarification_msg_content
        state["dialog_state"] = "awaiting_robot_model"
        state["messages"] = current_messages + [AIMessage(content=clarification_msg_content)]
        return state

    # If we have robot_model and dialog_state is "initial" (meaning ready to enrich)
    if robot_model and dialog_state == "initial":
        # === Re-fetch the potentially updated raw_user_request from state ===
        # This ensures that if we looped back from a "no" to enrichment confirmation,
        # we use the user's feedback (which was stored in state["raw_user_request"]) 
        # instead of the raw_user_request variable from the top of the function scope.
        current_raw_user_request = state.get("raw_user_request", user_input) # Fallback to current user_input if somehow not set
        # ========================================================================

        logger.info(f"Robot model is '{robot_model}'. Proceeding to enrich user request: '{current_raw_user_request}'")
        
        if not current_messages or not (isinstance(current_messages[-1], HumanMessage) and current_messages[-1].content == current_raw_user_request):
             current_messages = current_messages + [HumanMessage(content=current_raw_user_request)]
             state["messages"] = current_messages

        placeholder_values = {**config, "robot_model": robot_model, "user_core_request": current_raw_user_request}
        
        # Correction: Call the text output function
        llm_enrich_response = await invoke_llm_for_text_output(
            llm,
            system_prompt_content=get_filled_prompt("flow_step0_enrich_input.md", placeholder_values),
            user_message_content=f"Robot Model: {robot_model}\nUser's Core Task: {current_raw_user_request}",
            message_history=current_messages
        )

        if "error" in llm_enrich_response or not llm_enrich_response.get("text_output"):
            error_msg = f"Step 0 Failed: Could not enrich input. LLM Error: {llm_enrich_response.get('error', 'No output')}"
            logger.error(error_msg)
            state["is_error"] = True
            state["error_message"] = error_msg
            state["dialog_state"] = "initial"
            state["messages"] = current_messages + [AIMessage(content=f"Error during enrichment: {error_msg}")]
            return state

        enriched_text_proposal = llm_enrich_response["text_output"].strip()

        if not enriched_text_proposal or enriched_text_proposal == "NEEDS_CLARIFICATION":
            logger.warning(f"LLM indicated input needs clarification or enrichment failed for: {current_raw_user_request}")
            clarification_msg_content = "I couldn't fully understand your request or it needs more details for enrichment. Could you please rephrase or add more information?"
            state["clarification_question"] = clarification_msg_content
            state["raw_user_request"] = "" 
            state["dialog_state"] = "initial"
            state["messages"] = current_messages + [AIMessage(content=clarification_msg_content)]
            return state
        else:
            logger.info(f"Step 0 Succeeded. Proposed enriched input text:\n{enriched_text_proposal}")
            state["proposed_enriched_text"] = enriched_text_proposal
            confirmation_question = (
                f"根据您的机器人型号 '{robot_model}' 和请求 '{current_raw_user_request}', 我生成的初步流程如下:\n\n"
                f"```text\n{enriched_text_proposal}\n```\n\n"
                f"您是否同意按此流程继续？ (请输入 'yes' 或 'no'，或者提供修改意见)"
            )
            state["clarification_question"] = confirmation_question
            state["dialog_state"] = "awaiting_enrichment_confirmation"
            state["messages"] = current_messages + [AIMessage(content=confirmation_question)]
            return state

    # Fallback if state is unexpected
    # Fetch the latest dialog_state for the warning message
    current_dialog_state_for_warning = state.get("dialog_state", "unknown")
    logger.warning(f"preprocess_and_enrich_input_node reached an unexpected state: {current_dialog_state_for_warning} with robot_model: {robot_model}. Resetting.")
    state["dialog_state"] = "initial"
    state["robot_model"] = None 
    state["raw_user_request"] = user_input 
    return state


# --- Node 1: Understand Input ---
class ParsedStep(BaseModel):
    id_suggestion: str = Field(description="A suggested unique ID for this operation block, e.g., 'movel_P1_Z_on'.")
    type: str = Field(description="The type of operation, e.g., 'select_robot', 'set_motor', 'moveL', 'loop', 'return'.")
    description: str = Field(description="A brief natural language description of this specific step.")
    parameters: Dict[str, Any] = Field(description="A dictionary of parameters for this operation, e.g., {'robotName': 'dobot_mg400'} or {'point_name_list': 'P1', 'control_z': 'enable'.}")
    sub_steps: Optional[List["ParsedStep"]] = Field(None, description="For control flow blocks like 'loop', this contains the nested sequence of operations.")

ParsedStep.update_forward_refs()

class UnderstandInputSchema(BaseModel):
    robot_name: Optional[str] = Field(None, description="The name or model of the robot as explicitly stated in the parsed text, e.g., 'dobot_mg400'. This should match the robot name from the input text.")
    flow_operations: List[ParsedStep] = Field(description="An ordered list of operations identified from the user input text.")

async def understand_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 1: Understand Input (from potentially enriched text) ---")
    state["current_step_description"] = "Understanding user input"

    enriched_input_text = state.get("enriched_structured_text")
    if not enriched_input_text:
        logger.error("Enriched input text is missing in state for understand_input_node.")
        state["is_error"] = True
        state["error_message"] = "Enriched input text is missing for parsing."
        return state

    if not state.get("config"):
        logger.error("Config (placeholder values) is missing in state.")
        state["is_error"] = True
        state["error_message"] = "Configuration (placeholders) is missing."
        return state
    
    current_messages = state.get("messages", [])

    user_message_for_llm = (
        f"Parse the following robot workflow description into a structured format. "
        f"Identify the robot name (it must be explicitly stated in the text to be parsed, typically at the beginning like '机器人: model_name') and each distinct operation with its parameters. "
        f"Pay close attention to control flow structures like loops and their nested operations.\\n\\n"
        f"Workflow Description to Parse:\\n```text\\n{enriched_input_text}\\n```"
    )

    parsed_output = await invoke_llm_for_json_output(
        llm,
        system_prompt_template_name="flow_step1_understand_input.md",
        placeholder_values=state["config"],
        user_message_content=user_message_for_llm,
        json_schema=UnderstandInputSchema,
        message_history=current_messages
    )

    if "error" in parsed_output:
        error_msg_detail = f"Step 1 Failed: {parsed_output.get('error')}. Details: {parsed_output.get('details')}"
        logger.error(error_msg_detail)
        raw_out = parsed_output.get('raw_output', '')
        state["is_error"] = True
        state["error_message"] = f"Step 1: Failed to understand input. LLM Error: {error_msg_detail}. Raw: {str(raw_out)[:500]}"
        return state

    try:
        validated_data = UnderstandInputSchema(**parsed_output)
        logger.info(f"Step 1 Succeeded. Parsed robot from text: {validated_data.robot_name}, Operations: {len(validated_data.flow_operations)}")
        
        state["parsed_flow_steps"] = [op.dict(exclude_none=True) for op in validated_data.flow_operations]
        state["parsed_robot_name"] = validated_data.robot_name 
        state["dialog_state"] = "input_understood" 
        state["clarification_question"] = None 
        state["error_message"] = None
        state["is_error"] = False
        state["messages"] = current_messages + [AIMessage(content=f"Successfully parsed input. Robot: {validated_data.robot_name}. Steps: {len(validated_data.flow_operations)}")]
        return state
    except Exception as e: 
        logger.error(f"Step 1 Failed: Output validation error. Error: {e}. Raw Output: {parsed_output}", exc_info=True)
        state["is_error"] = True
        state["error_message"] = f"Step 1: Output validation error. Details: {e}. Parsed: {str(parsed_output)[:500]}"
        return state

# TODO: Implement other node functions for Step 2, 3, 4
# - generate_individual_xmls_node
# - generate_relation_xml_node
# - generate_final_flow_xml_node (this one might not be an LLM node, but a Python function node) 