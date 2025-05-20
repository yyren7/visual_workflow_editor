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
KNOWN_ROBOT_MODELS = ["dobot_mg400", "dobot_cr5", "hitbot", "RoboDK"]


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
            return state
        else: # "no" or other feedback - This is where we integrate the new revision logic
            logger.info("User rejected or wants to modify the enriched plan. Attempting revision.")
            
            previous_proposal = state.get("proposed_enriched_text")
            user_feedback = user_input 

            if not previous_proposal:
                # This case should ideally not happen if we always have a proposal before asking for confirmation.
                # But as a fallback, treat it as a new request.
                logger.warning("User provided feedback, but no previous proposal found in state. Treating feedback as new raw_user_request.")
                state["raw_user_request"] = user_feedback
                state["user_input"] = user_feedback
                state["dialog_state"] = "initial" 
                state["proposed_enriched_text"] = None
                state["enriched_structured_text"] = None
                state["clarification_question"] = None
                state["messages"] = current_messages + [AIMessage(content=f"User provided feedback: '{user_feedback}'. No previous plan to revise, restarting enrichment.")]
                return state

            # Use the new prompt for revising the enrichment
            revision_placeholder_values = {
                **config, 
                "robot_model": robot_model, 
                "previous_proposal": previous_proposal,
                "user_feedback": user_feedback
            }
            
            # The user_message_content for the revision prompt might be minimal or just repeat the feedback,
            # as the core information is in the system prompt template.
            # Let's provide a clear context in user_message_content as well.
            revision_user_message_content = (
                f"Robot Model: {robot_model}\n"
                f"Previous Proposed Workflow:\n{previous_proposal}\n\n"
                f"User's Feedback/Modifications:\n{user_feedback}\n\n"
                "Please generate an updated and complete workflow text based on this feedback."
            )

            llm_revise_response = await invoke_llm_for_text_output(
                llm,
                system_prompt_content=get_filled_prompt("flow_step0_revise_enriched_input.md", revision_placeholder_values),
                user_message_content=revision_user_message_content, # Provide context for revision
                message_history=current_messages # Pass current message history
            )

            if "error" in llm_revise_response or not llm_revise_response.get("text_output"):
                error_msg = f"Revision of enriched input failed. LLM Error: {llm_revise_response.get('error', 'No output')}"
                logger.error(error_msg)
                # Fallback: ask user to rephrase or treat as new input?
                # For now, let's inform and ask for re-clarification of the modification.
                state["clarification_question"] = (
                    f"尝试根据您的反馈 '{user_feedback}' 修改流程时遇到问题：{error_msg}. "
                    "您能否更清晰地说明您的修改意见，或者重新描述您的请求？"
                )
                state["dialog_state"] = "awaiting_enrichment_confirmation" # Stay in this state, user needs to respond to this new Q
                state["messages"] = current_messages + [AIMessage(content=f"Error during revision: {error_msg}. Asking for clearer feedback.")]
                return state

            revised_text_proposal = llm_revise_response["text_output"].strip()

            if revised_text_proposal == "用户反馈不够清晰，无法完成修改，请提供更具体的修改意见。":
                logger.info("LLM indicated user feedback for revision is not clear enough.")
                state["clarification_question"] = revised_text_proposal # LLM's message to user
                state["dialog_state"] = "awaiting_enrichment_confirmation" 
                state["messages"] = current_messages + [AIMessage(content=f"LLM needs clearer feedback for revision: {revised_text_proposal}")]
                return state
            else:
                logger.info(f"Successfully revised enriched input based on user feedback. New proposed text:\n{revised_text_proposal}")
                state["proposed_enriched_text"] = revised_text_proposal # Update with the revised proposal
                
                # Ask for confirmation again, this time for the revised plan
                confirmation_question = (
                    f"根据您的反馈 '{user_feedback}'，我对流程进行了修改。更新后的流程如下:\n\n"
                    f"```text\n{revised_text_proposal}\n```\n\n"
                    f"您是否同意按此更新后的流程继续？ (请输入 'yes' 或 'no'，或者提供进一步的修改意见)"
                )
                state["clarification_question"] = confirmation_question
                state["dialog_state"] = "awaiting_enrichment_confirmation" # Stay to confirm the revision
                state["messages"] = current_messages + [AIMessage(content=confirmation_question)]
                return state


    # C. Initial entry, or after robot model is known/confirmed, or after enrichment rejection (now re-evaluating)
    if not robot_model: # If still no robot model (e.g. initial entry and no model provided)
        # Attempt to extract/guess model from initial input if dialog_state is 'initial'
        if dialog_state == "initial":
            logger.info(f"Robot model not in state. Attempting to identify from initial user input via LLM: '{user_input}'")
            
            identification_prompt_system = (
                f"You are an assistant helping to identify robot model mentions in user requests. "
                f"The user might mention a robot model directly or indirectly. "
                f"Here is a list of known official robot model names for context: {', '.join(KNOWN_ROBOT_MODELS)}. "
                f"Your task is to analyze the user\'s request and extract the specific phrase or term that refers to a robot model. "
                f"If no part of the request seems to mention a robot model, respond with the exact string 'NO_MENTION'."
            )
            identification_prompt_user = f"User\'s request: '{user_input}'"

            identification_response = await invoke_llm_for_text_output(
                llm,
                system_prompt_content=identification_prompt_system,
                user_message_content=identification_prompt_user
            )

            potential_model_mention = None
            if "error" not in identification_response and identification_response.get("text_output"):
                extracted_phrase = identification_response["text_output"].strip()
                if extracted_phrase.upper() != "NO_MENTION":
                    potential_model_mention = extracted_phrase
                    logger.info(f"LLM identified potential model phrase: '{potential_model_mention}' from initial input.")
                else:
                    logger.info("LLM indicated no robot model mention in initial input (responded NO_MENTION).")
            else:
                logger.warning(f"LLM call for model identification failed or produced no output. Error: {identification_response.get('error')}, Output: {identification_response.get('text_output')}")

            if potential_model_mention:
                logger.info(f"Attempting normalization for LLM-identified phrase: '{potential_model_mention}'.")
                # Use existing normalization logic
                normalize_prompt = (
                    f"User provided robot model phrase: '{potential_model_mention}'. " # Changed from "User provided robot model" for clarity
                    f"Known official models are: {', '.join(KNOWN_ROBOT_MODELS)}. "
                    "Respond with the closest matching official model name from the list. "
                    "If no close match (e.g., input is nonsensical or completely unrelated to these models), respond with 'unknown_model'. "
                    "Only output the official model name or 'unknown_model'."
                )
                norm_response = await invoke_llm_for_text_output(
                    llm,
                    system_prompt_content="You are a robot model normalization assistant.", # This system prompt remains suitable
                    user_message_content=normalize_prompt
                )

                if "error" not in norm_response and norm_response.get("text_output"):
                    normalized_model = norm_response["text_output"].strip()
                    logger.info(f"LLM normalized '{potential_model_mention}' to '{normalized_model}'")
                    if normalized_model.lower() != "unknown_model" and normalized_model in KNOWN_ROBOT_MODELS:
                        state["robot_model"] = normalized_model
                        robot_model = normalized_model # Update for current scope
                        logger.info(f"Robot model '{robot_model}' identified and normalized from initial input via LLM.")
                        ai_detection_message = AIMessage(content=f"Identified robot model '{robot_model}' from your initial request.")
                        current_messages = current_messages + [ai_detection_message] # Update local current_messages
                        state["messages"] = current_messages # Update state
                    else:
                        logger.info(f"Could not normalize LLM-identified phrase '{potential_model_mention}' (normalized to '{normalized_model}') to a known model.")
                else:
                    logger.warning(f"Normalization call failed for LLM-identified phrase '{potential_model_mention}'. Error: {norm_response.get('error')}, Output: {norm_response.get('text_output')}")
            # else: # Covered by previous log messages if potential_model_mention is None
            #    logger.info("No robot model mention identified by LLM in initial input, or identification failed.")

        # If robot_model is STILL None after the attempt, then ask the user.
        if not robot_model: # This condition is checked again
            logger.info("Robot model remains unknown after LLM-based initial check. Requesting clarification from user.")
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