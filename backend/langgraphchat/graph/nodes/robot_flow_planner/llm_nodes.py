import logging
import json
import os # Ensure os is imported
import asyncio
from pathlib import Path # For path manipulation
from typing import List, Optional, Dict, Any, cast, Type, Literal
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, BaseMessage
from pydantic import BaseModel, Field
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

from .state import RobotFlowAgentState, GeneratedXmlFile
from .prompt_loader import get_filled_prompt

logger = logging.getLogger(__name__)

# English language strings for user interaction and system messages.
# Templates use {variable_name} for placeholders.
USER_INTERACTION_TEXTS = {
    "GENERAL_FEEDBACK_GUIDANCE": "Sorry, I couldn't fully understand your feedback. I can only support 'agree', 'change robot', or 'modify plan'. Please rephrase your request.",
    "ERROR_INTENT_VALIDATION_FAILED": "Sorry, I couldn't accurately parse your feedback intent. I can only support 'agree', 'change robot', or 'modify plan'. Please rephrase your request.",
    "INFO_AFFIRM_PLAN_CONFIRMED": "Based on your feedback, the current plan has been confirmed.",
    "INFO_ROBOT_MODEL_CHANGED_TEMPLATE": "Okay, the robot model has been changed to {suggested_model}. I will replan using the new robot based on the current latest plan (or your original request).",
    "PROMPT_ROBOT_MODEL_UNCLEAR_TEMPLATE": "You suggested changing the robot, but the model '{suggested_model}' is unclear or not in the known list ({known_models_str}). Can you provide an exact model name? Or should we continue revising the plan with the original robot '{robot_model}'?",
    "INFO_TREATING_FEEDBACK_AS_NEW_REQUEST_TEMPLATE": "Since no previous plan was found, I will treat your feedback '{user_feedback_for_revision}' as a new request.",
    "ERROR_REVISE_PLAN_LLM_FAILED_MESSAGE_TEMPLATE": "Encountered an issue when trying to modify the plan based on your feedback '{user_feedback_for_revision}': The LLM failed to generate a valid revision. Error: {error_details}",
    "PROMPT_CLARIFY_REVISION_FEEDBACK_AFTER_ERROR": "Could you clarify your modification suggestions or rephrase your request?",
    "LLM_OUTPUT_FEEDBACK_UNCLEAR_FOR_REVISION": "User feedback is not clear enough to complete the modification. Please provide more specific modification suggestions.",
    "LOG_LLM_SAID_FEEDBACK_UNCLEAR_TEMPLATE": "LLM indicated your feedback is not clear enough for modification: {llm_direct_unclear_feedback}",
    "PROMPT_CONFIRM_REVISED_PLAN_TEMPLATE": (
        "Based on your feedback '{user_feedback_for_revision}', I have revised the plan. The updated plan is as follows:\\n\\n"
        "```text\\n{revised_text_proposal}\\n```\\n\\n"
        "Do you agree to proceed with this updated plan? (Please enter 'yes' or 'no', or provide further modification suggestions)"
    ),
    "PROMPT_ASK_ROBOT_MODEL_TEMPLATE": "What robot model are you using? For example: {known_models_str}",
    "PROMPT_ASK_FOR_TASK_AFTER_MODEL_CONFIRMATION_TEMPLATE": "Robot model confirmed as {robot_model}. Please tell me the specific task or plan you want to execute.",
    "PROMPT_INPUT_NEEDS_CLARIFICATION_FROM_LLM": "I couldn't fully understand your request or it needs more details for enrichment. Could you please rephrase or add more information?",
    "PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE": (
        "Based on your robot model '{robot_model}' and request '{current_raw_user_request}', the initial plan I generated is as follows:\\n\\n"
        "```text\\n{enriched_text_proposal}\\n```\\n\\n"
        "Do you agree to proceed with this plan? (Please enter 'yes' or 'no', or provide modification suggestions)"
    ),
    "PROMPT_ROBOT_MODEL_NOT_RECOGNIZED_TEMPLATE": (
        "Sorry, I couldn't recognize '{user_input}' or normalize it to a known model. "
        "Known models: {known_models_str}. Please provide a valid robot model name."
    )
}

# Chinese language strings (original version of USER_INTERACTION_TEXTS)
# Templates use {variable_name} for placeholders.
USER_INTERACTION_TEXTS_ZH = {
    "GENERAL_FEEDBACK_GUIDANCE": "抱歉，我未能完全理解您的反馈。我只能支持'同意'、'修改机器人'或'修改流程'这三种行为。请您重新表述您的意思。",
    "ERROR_INTENT_VALIDATION_FAILED": "抱歉，我未能准确解析您的反馈意图。我只能支持'同意'、'修改机器人'或'修改流程'这三种行为。请您重新表述您的意思。",
    "INFO_AFFIRM_PLAN_CONFIRMED": "已根据您的反馈确认为同意当前计划。",
    "INFO_ROBOT_MODEL_CHANGED_TEMPLATE": "好的，机器人型号已更改为 {suggested_model}。我将基于当前最新计划（或您的原始请求）使用新机器人重新规划。",
    "PROMPT_ROBOT_MODEL_UNCLEAR_TEMPLATE": "您建议更换机器人，但型号 '{suggested_model}' 不太明确或不在已知列表 ({known_models_str}) 中。您能提供一个准确的型号吗？或者我们继续使用原机器人 '{robot_model}' 进行计划修订？",
    "INFO_TREATING_FEEDBACK_AS_NEW_REQUEST_TEMPLATE": "由于未找到之前的计划，我将您的反馈 '{user_feedback_for_revision}' 作为新的请求来处理。",
    "ERROR_REVISE_PLAN_LLM_FAILED_MESSAGE_TEMPLATE": "尝试根据您的反馈 '{user_feedback_for_revision}' 修改流程时遇到问题：LLM未能生成有效修订。错误: {error_details}",
    "PROMPT_CLARIFY_REVISION_FEEDBACK_AFTER_ERROR": "您能否更清晰地说明您的修改意见，或者重新描述您的请求？",
    "LLM_OUTPUT_FEEDBACK_UNCLEAR_FOR_REVISION": "用户反馈不够清晰，无法完成修改，请提供更具体的修改意见。",
    "LOG_LLM_SAID_FEEDBACK_UNCLEAR_TEMPLATE": "LLM认为您的反馈不够清晰无法修改：{llm_direct_unclear_feedback}",
    "PROMPT_CONFIRM_REVISED_PLAN_TEMPLATE": (
        "根据您的反馈 '{user_feedback_for_revision}'，我对流程进行了修改。更新后的流程如下:\\n\\n"
        "```text\\n{revised_text_proposal}\\n```\\n\\n"
        "您是否同意按此更新后的流程继续？ (请输入 'yes' 或 'no'，或者提供进一步的修改意见)"
    ),
    "PROMPT_ASK_ROBOT_MODEL_TEMPLATE": "请问您使用的是什么型号的机器人？例如：{known_models_str}",
    "PROMPT_ASK_FOR_TASK_AFTER_MODEL_CONFIRMATION_TEMPLATE": "机器人型号已确认为 {robot_model}。请告诉我您想执行的具体任务或流程。",
    "PROMPT_INPUT_NEEDS_CLARIFICATION_FROM_LLM": "I couldn't fully understand your request or it needs more details for enrichment. Could you please rephrase or add more information?",
    "PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE": (
        "根据您的机器人型号 '{robot_model}' 和请求 '{current_raw_user_request}', 我生成的初步流程如下:\\n\\n"
        "```text\\n{enriched_text_proposal}\\n```\\n\\n"
        "您是否同意按此流程继续？ (请输入 'yes' 或 'no'，或者提供修改意见)"
    ),
    "PROMPT_ROBOT_MODEL_NOT_RECOGNIZED_TEMPLATE": (
        "Sorry, I couldn't recognize '{user_input}' or normalize it to a known model. "
        "Known models: {known_models_str}. Please provide a valid robot model name."
    )
}

# Define known robot models for normalization
KNOWN_ROBOT_MODELS = ["dobot_mg400", "fairino_FR", "hitbot_Z_ARM", "iai_3axis_tabletop", "robodk"]

# Pydantic model for intent classification output
class UserFeedbackIntent(BaseModel):
    intent: Literal["affirm", "change_robot", "modify_plan", "unclear"] = Field(description="The classified intent of the user's feedback.")
    robot_model_suggestion: Optional[str] = Field(None, description="If intent is 'change_robot', the suggested new robot model name.")
    revision_feedback: Optional[str] = Field(None, description="If intent is 'modify_plan', the core feedback for revising the plan. If not distinct from original feedback, can be the original feedback itself.")

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
        logger.error("json_schema must be provided to invoke_llm_for_json_output.")
        return {"error": "json_schema must be provided to invoke_llm_for_json_output."}

    filled_system_prompt = get_filled_prompt(system_prompt_template_name, placeholder_values)
    if not filled_system_prompt:
        logger.error(f"Failed to load or fill system prompt: {system_prompt_template_name}")
        return {"error": f"Failed to load or fill system prompt: {system_prompt_template_name}"}

    messages: List[BaseMessage] = [SystemMessage(content=filled_system_prompt)]
    if message_history:
        messages.extend(message_history)
    messages.append(HumanMessage(content=user_message_content))

    logger.info(f"Invoking LLM. System prompt template: {system_prompt_template_name}, Expecting JSON for schema: {json_schema.__name__}")
    structured_llm = llm.with_structured_output(json_schema)
    raw_output_for_debug = "Not available or attempt failed."
    try:
        ai_response = await structured_llm.ainvoke(messages)
        
        if ai_response is None:
            logger.error(f"LLM with_structured_output for schema {json_schema.__name__} returned None. This is unexpected.")
            try:
                logger.info(f"Attempting to get raw output after structured_llm returned None for schema {json_schema.__name__}...")
                raw_output_msg = await llm.ainvoke(messages)
                raw_output_for_debug = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
                logger.info(f"Raw output obtained after None from structured_llm: {raw_output_for_debug[:500]}...")
            except Exception as e_raw_after_none:
                logger.error(f"Failed to get raw output after structured_llm returned None for schema {json_schema.__name__}. Error: {e_raw_after_none}", exc_info=True)
                raw_output_for_debug = f"Failed to fetch raw output after None: {e_raw_after_none}"
            return {"error": f"LLM with_structured_output returned None for schema {json_schema.__name__}.", "raw_output": raw_output_for_debug}

        if isinstance(ai_response, BaseModel):
            return ai_response.dict(exclude_none=True)
        else:
            logger.error(f"LLM with_structured_output did not return a Pydantic model instance for schema {json_schema.__name__}. Got type: {type(ai_response)}. Value: {str(ai_response)[:200]}...")
            try:
                logger.info(f"Attempting to get raw output after receiving non-Pydantic type {type(ai_response)} for schema {json_schema.__name__}...")
                raw_output_msg = await llm.ainvoke(messages)
                raw_output_for_debug = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
                logger.info(f"Raw output obtained after non-Pydantic response: {raw_output_for_debug[:500]}...")
            except Exception as e_raw_non_pydantic:
                logger.error(f"Failed to get raw output after non-Pydantic response for schema {json_schema.__name__}. Error: {e_raw_non_pydantic}", exc_info=True)
                raw_output_for_debug = f"Failed to fetch raw output after non-Pydantic: {e_raw_non_pydantic}"
            return {"error": f"LLM structured output did not return a Pydantic model for schema {json_schema.__name__}. Got type: {type(ai_response)}", "raw_output": raw_output_for_debug}

    except Exception as e:
        logger.error(f"LLM call with_structured_output failed for schema {json_schema.__name__}. Error: {e}", exc_info=True)
        try:
            logger.info(f"Attempting to get raw output after structured_output exception for schema {json_schema.__name__}...")
            raw_output_msg = await llm.ainvoke(messages)
            raw_output_for_debug = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
            logger.info(f"Raw output obtained after exception: {raw_output_for_debug[:500]}...")
        except Exception as e_raw:
            logger.error(f"Failed to get raw output from LLM after structured output error for schema {json_schema.__name__}. Error: {e_raw}", exc_info=True)
            raw_output_for_debug = f"Failed to fetch raw output after exception: {e_raw}"
        return {"error": f"LLM call with_structured_output failed for schema {json_schema.__name__}.", "details": str(e), "raw_output": raw_output_for_debug}


# --- Node 0: Preprocess and Enrich Input ---
async def preprocess_and_enrich_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 0: Preprocess and Enrich Input ---")
    state.current_step_description = "Preprocessing and enriching input"

    user_input = state.user_input.strip() if state.user_input else ""
    robot_model = state.robot_model
    dialog_state = state.dialog_state if state.dialog_state else "initial"
    raw_user_request = state.raw_user_request if state.raw_user_request else user_input
    config = state.config
    current_messages = state.messages
    
    if dialog_state == "initial" and not state.raw_user_request:
        state.raw_user_request = user_input
        raw_user_request = user_input
    if state.active_plan_basis is None and state.raw_user_request:
        state.active_plan_basis = state.raw_user_request


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
            state.error_message = "Failed to normalize robot model name."
            state.is_error = True
            state.dialog_state = "initial" # Reset to try again or stop
            return state

        normalized_model = norm_response["text_output"].strip()
        logger.info(f"LLM normalized '{user_input}' to '{normalized_model}'")
        current_messages.append(AIMessage(content=f"Normalized robot model from '{user_input}' to '{normalized_model}'."))


        if normalized_model.lower() == "unknown_model" or normalized_model not in KNOWN_ROBOT_MODELS:
            clarification_msg_content = USER_INTERACTION_TEXTS["PROMPT_ROBOT_MODEL_NOT_RECOGNIZED_TEMPLATE"].format(
                user_input=user_input,
                known_models_str=", ".join(KNOWN_ROBOT_MODELS)
            )
            state.clarification_question = clarification_msg_content
            state.dialog_state = "awaiting_robot_model" # Ask again
            state.messages = current_messages + [AIMessage(content=clarification_msg_content)]
            return state
        
        state.robot_model = normalized_model
        robot_model = normalized_model # Update for current scope
        
        # Restore original request after getting model
        user_input = state.raw_user_request if state.raw_user_request else ""
        logger.info(f"Robot model confirmed/normalized to: {robot_model}. Original request was: '{user_input}'")
        dialog_state = "initial" # Transition to 'initial' to proceed with enrichment
        state.dialog_state = dialog_state


    # B. Handle user's response to enrichment confirmation
    elif dialog_state == "awaiting_enrichment_confirmation":
        logger.info(f"Received user response for enrichment confirmation: '{user_input}'")
        current_messages = current_messages + [HumanMessage(content=user_input)]
        
        positive_confirmations = ["yes", "y", "是的", "是", "同意", "同意继续", "ok", "okay", "好的"]
        
        if user_input.strip().lower() in positive_confirmations:
            logger.info("User confirmed the enriched plan directly.")
            state.enriched_structured_text = state.proposed_enriched_text
            state.proposed_enriched_text = None
            state.clarification_question = None
            state.dialog_state = "processing_enriched_input"
            state.messages = current_messages + [AIMessage(content="User approved the enriched plan.")]
            return state
        else: 
            logger.info("User feedback is not a direct confirmation. Classifying intent...")
            
            previous_proposal_for_intent = state.proposed_enriched_text if state.proposed_enriched_text else ""
            
            intent_placeholder_values = {
                **config,
                "KNOWN_ROBOT_MODELS": ", ".join(KNOWN_ROBOT_MODELS),
                "previous_proposal": previous_proposal_for_intent,
                "user_feedback": user_input 
            }

            # User message for intent classification can be minimal as prompt is detailed
            intent_user_message = f"User feedback on proposed plan: '{user_input}'"

            intent_classification_response_dict = await invoke_llm_for_json_output(
                llm,
                system_prompt_template_name="flow_step0_classify_feedback_intent.md",
                placeholder_values=intent_placeholder_values,
                user_message_content=intent_user_message, # User message can be simple
                json_schema=UserFeedbackIntent,
                message_history=current_messages # Pass current history for context
            )

            if "error" in intent_classification_response_dict or not intent_classification_response_dict:
                logger.error(f"Intent classification LLM call failed: {intent_classification_response_dict.get('error', 'No response')}")
                # Fallback: treat as unclear and ask user to clarify with specific guidance
                state.clarification_question = USER_INTERACTION_TEXTS["GENERAL_FEEDBACK_GUIDANCE"]
                state.dialog_state = "awaiting_enrichment_confirmation" # Stay to re-confirm
                state.messages = current_messages + [AIMessage(content=state.clarification_question)]
                return state

            try:
                classified_intent = UserFeedbackIntent(**intent_classification_response_dict)
            except Exception as e:
                logger.error(f"Failed to validate intent classification response: {e}. Response was: {intent_classification_response_dict}")
                # Fallback: treat as unclear and ask user to clarify with specific guidance
                state.clarification_question = USER_INTERACTION_TEXTS["ERROR_INTENT_VALIDATION_FAILED"]
                state.dialog_state = "awaiting_enrichment_confirmation" # Stay to re-confirm
                state.messages = current_messages + [AIMessage(content=state.clarification_question)]
                return state

            logger.info(f"Classified user feedback intent: {classified_intent.intent}")

            if classified_intent.intent == "affirm":
                logger.info("User feedback classified as 'affirm'. Processing as confirmation.")
                state.enriched_structured_text = state.proposed_enriched_text
                state.proposed_enriched_text = None
                state.clarification_question = None
                state.dialog_state = "processing_enriched_input"
                state.messages = current_messages + [AIMessage(content=USER_INTERACTION_TEXTS["INFO_AFFIRM_PLAN_CONFIRMED"])]
                return state

            elif classified_intent.intent == "change_robot":
                suggested_model = classified_intent.robot_model_suggestion
                logger.info(f"User feedback classified as 'change_robot'. Suggested model: {suggested_model}")
                if suggested_model and suggested_model in KNOWN_ROBOT_MODELS:
                    state.robot_model = suggested_model
                    state.dialog_state = "initial" # Re-trigger enrichment with new model
                    state.proposed_enriched_text = None # Clear previous proposal text
                    state.enriched_structured_text = None # Clear any confirmed text
                    state.clarification_question = None
                    # active_plan_basis remains, to be used by the 'initial' state logic
                    logger.info(f"Robot model changed to '{suggested_model}'. Restarting enrichment using active plan basis: '{state.active_plan_basis}' or raw request if basis is null.")
                    state.messages = current_messages + [AIMessage(content=USER_INTERACTION_TEXTS["INFO_ROBOT_MODEL_CHANGED_TEMPLATE"].format(suggested_model=suggested_model))]
                    return state
                else:
                    clarification_msg = USER_INTERACTION_TEXTS["PROMPT_ROBOT_MODEL_UNCLEAR_TEMPLATE"].format(
                        suggested_model=suggested_model,
                        known_models_str=", ".join(KNOWN_ROBOT_MODELS),
                        robot_model=robot_model
                    )
                    state.clarification_question = clarification_msg
                    state.dialog_state = "awaiting_enrichment_confirmation" # Ask for model again or confirm revision
                    state.messages = current_messages + [AIMessage(content=clarification_msg)]
                    return state

            elif classified_intent.intent == "modify_plan":
                logger.info("User feedback classified as 'modify_plan'. Proceeding with plan revision.")
                user_feedback_for_revision = classified_intent.revision_feedback if classified_intent.revision_feedback else user_input
                
                previous_proposal = state.proposed_enriched_text
                if not previous_proposal:
                    logger.warning("No previous_proposal (proposed_enriched_text) found for 'modify_plan' intent. This should ideally not happen if a plan was proposed.")
                    # Fallback: try to use active_plan_basis if available, otherwise treat as new initial request
                    previous_proposal = state.active_plan_basis
                    if not previous_proposal:
                        logger.warning("No active_plan_basis found either. Treating feedback as new raw_user_request.")
                        state.raw_user_request = user_feedback_for_revision
                        state.user_input = user_feedback_for_revision
                        state.active_plan_basis = None # Explicitly clear, as we are starting fresh
                        state.dialog_state = "initial" 
                        state.proposed_enriched_text = None
                        state.enriched_structured_text = None
                        state.clarification_question = None
                        state.messages = current_messages + [AIMessage(content=USER_INTERACTION_TEXTS["INFO_TREATING_FEEDBACK_AS_NEW_REQUEST_TEMPLATE"].format(user_feedback_for_revision=user_feedback_for_revision))]
                        return state
                    else:
                        logger.info("Using active_plan_basis as the previous_proposal for revision.")

                revision_placeholder_values = {
                    **config, 
                    "robot_model": robot_model, # robot_model should be in state from before
                    "previous_proposal": previous_proposal,
                    "user_feedback": user_feedback_for_revision # Use the (potentially refined) feedback from intent classification
                }
                
                revision_user_message_content = (
                    f"Robot Model: {robot_model}\\n"
                    f"Previous Proposed Workflow:\\n{previous_proposal}\\n\\n"
                    f"User's Feedback/Modifications for Revision:\\n{user_feedback_for_revision}\\n\\n"
                    "Please generate an updated and complete workflow text based on this feedback."
                )

                llm_revise_response = await invoke_llm_for_text_output(
                    llm,
                    system_prompt_content=get_filled_prompt("flow_step0_revise_enriched_input.md", revision_placeholder_values),
                    user_message_content=revision_user_message_content,
                    message_history=current_messages
                )

                if "error" in llm_revise_response or not llm_revise_response.get("text_output"):
                    error_msg_detail = llm_revise_response.get('error', '无输出') # Assuming '无输出' is "no output"
                    error_msg_formatted = USER_INTERACTION_TEXTS["ERROR_REVISE_PLAN_LLM_FAILED_MESSAGE_TEMPLATE"].format(
                        user_feedback_for_revision=user_feedback_for_revision,
                        error_details=error_msg_detail
                    )
                    logger.error(error_msg_formatted) # Log the formatted error
                    state.clarification_question = (
                        f"{error_msg_formatted} "
                        f"{USER_INTERACTION_TEXTS['PROMPT_CLARIFY_REVISION_FEEDBACK_AFTER_ERROR']}"
                    )
                    state.dialog_state = "awaiting_enrichment_confirmation" 
                    state.messages = current_messages + [AIMessage(content=state.clarification_question)]
                    return state

                revised_text_proposal = llm_revise_response["text_output"].strip()

                if revised_text_proposal == USER_INTERACTION_TEXTS["LLM_OUTPUT_FEEDBACK_UNCLEAR_FOR_REVISION"]: # Check for specific LLM refusal
                    logger.info("LLM indicated user feedback for revision is not clear enough.")
                    state.clarification_question = revised_text_proposal 
                    state.dialog_state = "awaiting_enrichment_confirmation" 
                    state.messages = current_messages + [AIMessage(content=USER_INTERACTION_TEXTS["LOG_LLM_SAID_FEEDBACK_UNCLEAR_TEMPLATE"].format(llm_direct_unclear_feedback=revised_text_proposal))]
                    return state
                else:
                    logger.info(f"Successfully revised enriched input based on feedback '{user_feedback_for_revision}'. New proposed text:\\n{revised_text_proposal}")
                    state.proposed_enriched_text = revised_text_proposal
                    state.active_plan_basis = revised_text_proposal # UPDATE active_plan_basis with the new revision
                    confirmation_question = USER_INTERACTION_TEXTS["PROMPT_CONFIRM_REVISED_PLAN_TEMPLATE"].format(
                        user_feedback_for_revision=user_feedback_for_revision,
                        revised_text_proposal=revised_text_proposal
                    )
                    state.clarification_question = confirmation_question
                    state.dialog_state = "awaiting_enrichment_confirmation"
                    state.messages = current_messages + [AIMessage(content=confirmation_question)]
                    return state
            
            elif classified_intent.intent == "unclear":
                logger.info("User feedback classified as 'unclear'. Asking for clarification with specific guidance.")
                state.clarification_question = USER_INTERACTION_TEXTS["GENERAL_FEEDBACK_GUIDANCE"]
                state.dialog_state = "awaiting_enrichment_confirmation" # Stay to re-confirm
                state.messages = current_messages + [AIMessage(content=state.clarification_question)]
                return state
            
            else: # Should not happen if Pydantic model and prompt are aligned
                logger.error(f"Unknown intent classified: {classified_intent.intent}. Defaulting to unclear.")
                # Treat unknown as unclear and ask for clarification with specific guidance
                state.clarification_question = USER_INTERACTION_TEXTS["GENERAL_FEEDBACK_GUIDANCE"] # Using general one, or can use specific ERROR_UNKNOWN_INTENT_TYPE
                state.dialog_state = "awaiting_enrichment_confirmation"
                state.messages = current_messages + [AIMessage(content=state.clarification_question)]
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
                        state.robot_model = normalized_model
                        robot_model = normalized_model # Update for current scope
                        logger.info(f"Robot model '{robot_model}' identified and normalized from initial input via LLM.")
                        ai_detection_message = AIMessage(content=f"Identified robot model '{robot_model}' from your initial request.")
                        current_messages = current_messages + [ai_detection_message] # Update local current_messages
                        state.messages = current_messages # Update state
                    else:
                        logger.info(f"Could not normalize LLM-identified phrase '{potential_model_mention}' (normalized to '{normalized_model}') to a known model.")
                else:
                    logger.warning(f"Normalization call failed for LLM-identified phrase '{potential_model_mention}'. Error: {norm_response.get('error')}, Output: {norm_response.get('text_output')}")
            # else: # Covered by previous log messages if potential_model_mention is None
            #    logger.info("No robot model mention identified by LLM in initial input, or identification failed.")

        # If robot_model is STILL None after the attempt, then ask the user.
        if not robot_model: # This condition is checked again
            logger.info("Robot model remains unknown after LLM-based initial check. Requesting clarification from user.")
            if not state.raw_user_request: state.raw_user_request = user_input
            # Initialize active_plan_basis from raw_user_request if it's the very first input and model is missing
            if not state.active_plan_basis and state.raw_user_request:
                state.active_plan_basis = state.raw_user_request
                logger.info(f"Initialized active_plan_basis from raw_user_request as model is being queried: {state.active_plan_basis}")

            clarification_msg_content = USER_INTERACTION_TEXTS["PROMPT_ASK_ROBOT_MODEL_TEMPLATE"].format(
                known_models_str=", ".join(KNOWN_ROBOT_MODELS)
            )
            state.clarification_question = clarification_msg_content
            state.dialog_state = "awaiting_robot_model"
            state.messages = current_messages + [AIMessage(content=clarification_msg_content)]
            return state

    # If we have robot_model and dialog_state is "initial" (meaning ready to enrich)
    if robot_model and dialog_state == "initial":
        # === Determine the basis for enrichment ===
        base_text_for_enrichment = state.active_plan_basis 
        # Fallback to raw_user_request ONLY if active_plan_basis is truly empty or None.
        # raw_user_request itself might be empty if user started by just providing a model.
        if not base_text_for_enrichment:
            base_text_for_enrichment = state.raw_user_request if state.raw_user_request else "" # Default to empty string if both are None/empty
            logger.info(f"active_plan_basis is empty. Using raw_user_request as base for enrichment: '{base_text_for_enrichment}'")
            # If raw_user_request was used and it's not empty, it becomes the initial active_plan_basis
            if base_text_for_enrichment and not state.active_plan_basis:
                 state.active_plan_basis = base_text_for_enrichment
        else:
            logger.info(f"Using active_plan_basis as base for enrichment: '{base_text_for_enrichment}'")
        
        # If base_text_for_enrichment is still empty, it means we have no basis to proceed.
        # This could happen if user only provided a robot model and no actual request yet.
        if not base_text_for_enrichment.strip():
            logger.warning("No content in active_plan_basis or raw_user_request to enrich. Asking user for a task.")
            clarification_msg_content = USER_INTERACTION_TEXTS["PROMPT_ASK_FOR_TASK_AFTER_MODEL_CONFIRMATION_TEMPLATE"].format(
                robot_model=robot_model
            )
            state.clarification_question = clarification_msg_content
            state.dialog_state = "awaiting_enrichment_confirmation" # Or a new state like "awaiting_initial_task"
            state.messages = current_messages + [AIMessage(content=clarification_msg_content)]
            return state

        current_raw_user_request = base_text_for_enrichment # This variable is used by the prompt below, ensure it has the right base

        logger.info(f"Robot model is '{robot_model}'. Proceeding to enrich user request: '{current_raw_user_request}'")
        
        if not current_messages or not (isinstance(current_messages[-1], HumanMessage) and current_messages[-1].content == current_raw_user_request):
             current_messages = current_messages + [HumanMessage(content=current_raw_user_request)]
             state.messages = current_messages

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
            state.is_error = True
            state.error_message = error_msg
            state.dialog_state = "initial"
            state.messages = current_messages + [AIMessage(content=f"Error during enrichment: {error_msg}")]
            return state

        enriched_text_proposal = llm_enrich_response["text_output"].strip()

        if not enriched_text_proposal or enriched_text_proposal == "NEEDS_CLARIFICATION":
            logger.warning(f"LLM indicated input needs clarification or enrichment failed for: {current_raw_user_request}")
            clarification_msg_content = USER_INTERACTION_TEXTS["PROMPT_INPUT_NEEDS_CLARIFICATION_FROM_LLM"]
            state.clarification_question = clarification_msg_content
            state.raw_user_request = "" 
            state.dialog_state = "initial"
            state.messages = current_messages + [AIMessage(content=clarification_msg_content)]
            return state
        else:
            logger.info(f"Step 0: Enrichment proposal generated. User confirmation will be requested.") # MODIFIED log message
            state.proposed_enriched_text = enriched_text_proposal
            state.active_plan_basis = enriched_text_proposal # UPDATE active_plan_basis with the newly enriched plan
            confirmation_question = USER_INTERACTION_TEXTS["PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE"].format(
                robot_model=robot_model,
                current_raw_user_request=current_raw_user_request,
                enriched_text_proposal=enriched_text_proposal
            )
            state.clarification_question = confirmation_question
            state.dialog_state = "awaiting_enrichment_confirmation"
            state.messages = current_messages + [AIMessage(content=confirmation_question)]
            return state

    # Fallback if state is unexpected
    # Fetch the latest dialog_state for the warning message
    current_dialog_state_for_warning = state.dialog_state if state.dialog_state else "unknown"
    logger.warning(f"preprocess_and_enrich_input_node reached an unexpected state: {current_dialog_state_for_warning} with robot_model: {robot_model}. Resetting.")
    state.dialog_state = "initial"
    state.robot_model = None 
    state.raw_user_request = user_input 
    return state


# --- Node 1: Understand Input ---
class ParsedStep(BaseModel):
    id_suggestion: str = Field(description="A suggested unique ID for this operation block, e.g., 'movel_P1_Z_on'.")
    type: str = Field(description="The type of operation, e.g., 'select_robot', 'set_motor', 'moveL', 'loop', 'return'.")
    description: str = Field(description="A brief natural language description of this specific step.")
    # parameters: Dict[str, Any] = Field(description="A dictionary of parameters for this operation, e.g., {'robotName': 'dobot_mg400'} or {'point_name_list': 'P1', 'control_z': 'enable'.}")
    sub_steps: Optional[List["ParsedStep"]] = Field(None, description="For control flow blocks like 'loop', this contains the nested sequence of operations.")

ParsedStep.update_forward_refs()

class UnderstandInputSchema(BaseModel):
    robot: Optional[str] = Field(None, description="The name or model of the robot as explicitly stated in the parsed text, e.g., 'dobot_mg400'. This should match the robot name from the input text.")
    operations: List[ParsedStep] = Field(description="An ordered list of operations identified from the user input text.")

async def understand_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 1: Understand Input (from potentially enriched text) ---")
    state.current_step_description = "Understanding user input"

    enriched_input_text = state.enriched_structured_text
    if not enriched_input_text:
        logger.error("Enriched input text is missing in state for understand_input_node.")
        state.is_error = True
        state.error_message = "Enriched input text is missing for parsing."
        return state

    config = state.config
    if not config:
        logger.error("Config (placeholder values) is missing in state.")
        state.is_error = True
        state.error_message = "Configuration (placeholders) is missing."
        return state
    
    current_messages = state.messages

    # Dynamically load known node types from the template directory
    known_node_types_list = []
    node_template_dir = config.get("NODE_TEMPLATE_DIR_PATH")
    if node_template_dir and os.path.isdir(node_template_dir):
        try:
            # Assuming XML files for node templates, adjust extension if necessary (e.g., .json, .py)
            known_node_types_list = sorted([
                os.path.splitext(f)[0] 
                for f in os.listdir(node_template_dir) 
                if os.path.isfile(os.path.join(node_template_dir, f)) and f.endswith( (".xml", ".json", ".py")) # Support multiple extensions
            ])
            if not known_node_types_list:
                logger.warning(f"No node templates found in directory: {node_template_dir} with supported extensions. Type validation will be lenient.")
            else:
                logger.info(f"Dynamically loaded {len(known_node_types_list)} known node types: {known_node_types_list}")
        except Exception as e:
            logger.error(f"Failed to list or parse node templates from {node_template_dir}: {e}. Type validation may be skipped or lenient.")
            # Proceed with an empty list, LLM will not be constrained by KNOWN_NODE_TYPES_LIST_STR if it's empty.
    else:
        logger.warning(f"NODE_TEMPLATE_DIR_PATH '{node_template_dir}' is not configured or not a directory. Type validation will be lenient.")

    # Prepare placeholder values for the prompt, including the known node types list
    # Ensure all expected placeholders by the prompt are present in config or added here.
    placeholder_values_for_prompt = config.copy() # Start with existing config
    placeholder_values_for_prompt["KNOWN_NODE_TYPES_LIST_STR"] = ", ".join(known_node_types_list) if known_node_types_list else "(dynamic list not available)"
    # Add other default/example placeholders if not already in config and are used by this specific prompt
    placeholder_values_for_prompt.setdefault("GENERAL_INSTRUCTION_INTRO", "Please analyze the following robot workflow.")
    placeholder_values_for_prompt.setdefault("ROBOT_NAME_EXAMPLE", "example_robot_CoppeliaSim")
    placeholder_values_for_prompt.setdefault("POINT_NAME_EXAMPLE_1", "P1")
    placeholder_values_for_prompt.setdefault("POINT_NAME_EXAMPLE_2", "P2")
    placeholder_values_for_prompt.setdefault("POINT_NAME_EXAMPLE_3", "P3")

    user_message_for_llm = (
        f"Parse the following robot workflow description into a structured format. "
        f"Identify the robot name (it must be explicitly stated in the text to be parsed, typically at the beginning like '机器人: model_name') and each distinct operation. " # Removed "with its parameters"
        f"Pay close attention to control flow structures like loops and their nested operations.\\n\\n"
        f"Workflow Description to Parse:\\n```text\\n{enriched_input_text}\\n```"
    )

    parsed_output = await invoke_llm_for_json_output(
        llm,
        system_prompt_template_name="flow_step1_understand_input.md",
        placeholder_values=placeholder_values_for_prompt, # Use the enriched placeholders
        user_message_content=user_message_for_llm,
        json_schema=UnderstandInputSchema,
        message_history=None # Do not pass full history for this specific, intensive step
    )

    if "error" in parsed_output:
        error_msg_detail = f"Step 1 Failed: {parsed_output.get('error')}. Details: {parsed_output.get('details')}"
        logger.error(error_msg_detail)
        raw_out = parsed_output.get('raw_output', '')
        state.is_error = True
        state.error_message = f"Step 1: Failed to understand input. LLM Error: {error_msg_detail}. Raw: {str(raw_out)[:500]}"
        return state

    # Manual validation of operation types BEFORE Pydantic parsing, if known_node_types_list is available
    if known_node_types_list and parsed_output.get("operations"):
        flow_ops_data = parsed_output.get("operations", [])
        invalid_types_details = []
        # Helper to recursively check types in sub_steps
        def check_op_types(ops_list, path_prefix=""): # path_prefix for better error reporting in nested steps
            for i, op_data in enumerate(ops_list):
                op_type = op_data.get("type")
                current_op_id_for_log = op_data.get('id_suggestion', f"{(path_prefix + str(i+1))}")
                current_op_desc_for_log = op_data.get('description', 'N/A')
                if op_type not in known_node_types_list and op_type != "unknown_operation": # Allow 'unknown_operation' as per prompt
                    invalid_types_details.append(
                        f"Operation {current_op_id_for_log} ('{current_op_desc_for_log}') has an invalid type '{op_type}'. "
                        f"Valid types are: {known_node_types_list} (or 'unknown_operation')."
                    )
                # Recursively check sub_steps if they exist
                if op_data.get("sub_steps") and isinstance(op_data["sub_steps"], list):
                    check_op_types(op_data["sub_steps"], path_prefix=f"{current_op_id_for_log}.")
        
        check_op_types(flow_ops_data)
        
        if invalid_types_details:
            error_message = " ".join(invalid_types_details)
            logger.error(f"Step 1 Failed: Invalid node types found after LLM parsing. {error_message}")
            state.is_error = True
            state.error_message = f"Step 1: Invalid node types found. {error_message} Raw LLM Output: {str(parsed_output)[:500]}"
            return state

    try:
        validated_data = UnderstandInputSchema(**parsed_output)
        logger.info(f"Step 1 Succeeded. Parsed robot from text: {validated_data.robot}, Operations: {len(validated_data.operations)}")
        
        state.parsed_flow_steps = [op.dict(exclude_none=True) for op in validated_data.operations]
        state.parsed_robot_name = validated_data.robot 
        state.dialog_state = "input_understood" 
        state.clarification_question = None 
        state.error_message = None
        state.is_error = False
        state.messages = current_messages + [AIMessage(content=f"Successfully parsed input. Robot: {validated_data.robot}. Steps: {len(validated_data.operations)}")]
        return state
    except Exception as e: 
        logger.error(f"Step 1 Failed: Output validation error. Error: {e}. Raw Output: {parsed_output}", exc_info=True)
        state.is_error = True
        state.error_message = f"Step 1: Output validation error. Details: {e}. Parsed: {str(parsed_output)[:500]}"
        return state

# --- Helper function to recursively collect all operations for XML generation --- 
def _collect_all_operations_for_xml_generation(
    operations: List[Dict[str, Any]], 
    config: Dict[str, Any],
    _block_counter: int = 1 # Internal counter, starts at 1
    ) -> (List[Dict[str, Any]], int): # Returns: (list of op_infos_for_llm, next_block_counter)
    """
    Flattens the list of operations (including sub-steps) and assigns 
    unique IDs and block numbers for XML generation.
    """
    ops_to_generate = []
    block_id_prefix = config.get("BLOCK_ID_PREFIX_EXAMPLE", "block_uuid") 

    for op_data_from_step1 in operations:
        xml_block_id = f"{block_id_prefix}_{_block_counter}"
        xml_data_block_no = str(_block_counter)
        
        generated_xml_filename = f"{xml_block_id}_{op_data_from_step1['type']}.xml"

        op_info_for_llm = {
            "type": op_data_from_step1['type'],
            "description": op_data_from_step1['description'],
            # "parameters_json": json.dumps(op_data_from_step1.get('parameters', {})), # Ensure parameters exist
            "id_suggestion_from_step1": op_data_from_step1.get('id_suggestion', ''),
            
            "target_xml_block_id": xml_block_id, 
            "target_xml_data_block_no": xml_data_block_no,
            "target_xml_filename": generated_xml_filename,
            "node_template_filename_to_load": f"{op_data_from_step1['type']}.xml" 
        }
        ops_to_generate.append(op_info_for_llm)
        _block_counter += 1

        if "sub_steps" in op_data_from_step1 and op_data_from_step1["sub_steps"]:
            sub_ops_list, next_block_counter_after_subs = _collect_all_operations_for_xml_generation(
                op_data_from_step1["sub_steps"],
                config,
                _block_counter=_block_counter
            )
            ops_to_generate.extend(sub_ops_list)
            _block_counter = next_block_counter_after_subs

    return ops_to_generate, _block_counter

# --- Helper function to generate XML for a single operation --- 
async def _generate_one_xml_for_operation_task(
    op_info_for_llm: Dict[str, Any],
    state: RobotFlowAgentState,
    llm: BaseChatModel
) -> GeneratedXmlFile:
    """
    Generates XML for a single operation by calling the LLM.
    Reads the node template, fills the prompt, and invokes the LLM.
    """
    logger = logging.getLogger(__name__) # Get logger instance
    config = state.config
    node_template_dir = config.get("NODE_TEMPLATE_DIR_PATH")
    robot_model_from_state = state.robot_model if state.robot_model else "unknown_robot"

    if not node_template_dir:
        error_msg = "NODE_TEMPLATE_DIR_PATH is not configured."
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg
        )

    template_file_path = Path(node_template_dir) / op_info_for_llm["node_template_filename_to_load"]
    node_template_xml_content_as_string = ""
    try:
        with open(template_file_path, 'r', encoding='utf-8') as f:
            node_template_xml_content_as_string = f.read()
    except FileNotFoundError:
        error_msg = f"Node template file not found: {template_file_path}"
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg
        )
    except Exception as e:
        error_msg = f"Error reading node template file {template_file_path}: {e}"
        logger.error(error_msg, exc_info=True)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg
        )

    placeholder_values = {
        **config, # General config like OUTPUT_DIR_PATH, BLOCK_ID_PREFIX_EXAMPLE
        "CURRENT_NODE_TYPE": op_info_for_llm["type"],
        "CURRENT_NODE_DESCRIPTION": op_info_for_llm["description"],
        # "CURRENT_NODE_PARAMETERS_JSON": op_info_for_llm["parameters_json"],
        "CURRENT_NODE_ID_SUGGESTION_FROM_STEP1": op_info_for_llm["id_suggestion_from_step1"],
        "TARGET_XML_BLOCK_ID": op_info_for_llm["target_xml_block_id"],
        "TARGET_XML_DATA_BLOCK_NO": op_info_for_llm["target_xml_data_block_no"],
        "ROBOT_MODEL_NAME_FROM_STATE": robot_model_from_state,
        "NODE_TEMPLATE_XML_CONTENT_AS_STRING": node_template_xml_content_as_string,
        # Ensure all placeholders used by flow_step2_generate_node_xml.md are here
        # Example: ROBOT_NAME_EXAMPLE, POINT_NAME_EXAMPLE_1, etc. if still used directly by step2 prompt
    }

    # User message can be simple as the system prompt is detailed
    user_message_for_llm = (
        f"Generate the Blockly XML for a '{op_info_for_llm['type']}' node. "
        f"Use the provided template content. "  # Removed parameters reference
        f"Target Block ID: {op_info_for_llm['target_xml_block_id']}. "
        f"Description: {op_info_for_llm['description']}."
    )

    llm_response = await invoke_llm_for_text_output(
        llm,
        system_prompt_content=get_filled_prompt("flow_step2_generate_node_xml.md", placeholder_values),
        user_message_content=user_message_for_llm,
        message_history=None # Explicitly set to None
    )

    if "error" in llm_response or not llm_response.get("text_output"):
        error_msg = f"LLM call failed for block {op_info_for_llm['target_xml_block_id']}. Error: {llm_response.get('error', 'No output')}"
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg,
            xml_content=llm_response.get("text_output") # Store raw output on failure for debugging
        )
    
    generated_xml_string = llm_response["text_output"].strip()

    # Attempt to extract XML from markdown code block if present
    match = re.search(r"```xml\n(.*?)\n```", generated_xml_string, re.DOTALL)
    if match:
        extracted_xml = match.group(1).strip()
        logger.info(f"Extracted XML from markdown code block for block {op_info_for_llm['target_xml_block_id']}")
        generated_xml_string = extracted_xml
    else:
        # Fallback: try to find the first < and last > and extract content in between,
        # if it still contains non-XML preamble/postamble but no markdown.
        # This is more risky and should be used cautiously.
        # A more robust solution would be a proper XML parser, but for now,
        # this might help with simple cases of LLM adding leading/trailing text.
        first_angle_bracket = generated_xml_string.find('<')
        last_angle_bracket = generated_xml_string.rfind('>')
        if first_angle_bracket != -1 and last_angle_bracket != -1 and last_angle_bracket > first_angle_bracket:
            potential_xml = generated_xml_string[first_angle_bracket : last_angle_bracket+1]
            # Basic check if this substring itself looks like an XML doc or fragment
            if potential_xml.strip().startswith("<") and potential_xml.strip().endswith(">"):
                 # And if the original string has non-XML parts outside this potential XML
                if generated_xml_string.strip() != potential_xml.strip():
                    logger.info(f"Attempting to extract XML by finding first '<' and last '>' for block {op_info_for_llm['target_xml_block_id']}")
                    generated_xml_string = potential_xml.strip()


    # Basic validation: Check if it looks like XML
    if not (generated_xml_string.startswith("<") and generated_xml_string.endswith(">")):
        error_msg = f"LLM output for block {op_info_for_llm['target_xml_block_id']} does not look like valid XML: {generated_xml_string[:100]}..."
        logger.error(error_msg)
        return GeneratedXmlFile(
            block_id=op_info_for_llm["target_xml_block_id"],
            type=op_info_for_llm["type"],
            source_description=op_info_for_llm["description"],
            status="failure",
            error_message=error_msg,
            xml_content=generated_xml_string
        )

    logger.info(f"Successfully generated XML for block: {op_info_for_llm['target_xml_block_id']}")
    return GeneratedXmlFile(
        block_id=op_info_for_llm["target_xml_block_id"],
        type=op_info_for_llm["type"],
        source_description=op_info_for_llm["description"],
        status="success",
        xml_content=generated_xml_string,
        # file_path will be set after writing the file in the main node function
    )


# --- Node 2: Generate Independent Node XMLs ---
async def generate_individual_xmls_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger = logging.getLogger(__name__) # Get logger instance
    logger.info("--- Running Step 2: Generate Independent Node XMLs ---")    
    state.current_step_description = "Generating individual XML files for each flow operation"

    parsed_steps = state.parsed_flow_steps
    config = state.config

    if not parsed_steps:
        logger.error("parsed_flow_steps is missing in state for generate_individual_xmls_node.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for XML generation."
        state.dialog_state = "error" # Or back to understand_input or initial
        return state

    if not config or not config.get("OUTPUT_DIR_PATH"):
        logger.error("OUTPUT_DIR_PATH is not configured in state.config.")
        state.is_error = True
        state.error_message = "Output directory path (OUTPUT_DIR_PATH) is not configured."
        state.dialog_state = "error"
        return state

    # 1. Flatten all operations
    all_ops_for_llm, _ = _collect_all_operations_for_xml_generation(parsed_steps, config)
    if not all_ops_for_llm:
        logger.warning("No operations collected for XML generation. This might be an empty plan.")
        state.generated_node_xmls = []
        state.dialog_state = "individual_xmls_generated" # Mark step as complete even if no XMLs
        return state

    logger.info(f"Collected {len(all_ops_for_llm)} operations for XML generation.")

    # 2. Create asyncio tasks for concurrent LLM calls
    tasks = [
        _generate_one_xml_for_operation_task(op_info, state, llm) 
        for op_info in all_ops_for_llm
    ]
    
    generation_results: List[GeneratedXmlFile] = await asyncio.gather(*tasks)

    # 3. Process results: save files and update state
    output_dir = Path(config.get("OUTPUT_DIR_PATH"))
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create output directory {output_dir}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to create output directory: {e}"
        state.generated_node_xmls = generation_results # Store partial results if any
        state.dialog_state = "error"
        return state

    processed_xml_files: List[GeneratedXmlFile] = []
    any_errors = False
    for i, result_info in enumerate(generation_results):
        op_metadata = all_ops_for_llm[i] # Get corresponding input metadata for filename
        if result_info.status == "success" and result_info.xml_content:
            file_name = op_metadata["target_xml_filename"]
            file_path = output_dir / file_name
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(result_info.xml_content)
                result_info.file_path = str(file_path)
                logger.info(f"Successfully wrote XML to {file_path}")
            except IOError as e:
                logger.error(f"Failed to write XML file {file_path}: {e}", exc_info=True)
                result_info.status = "failure"
                result_info.error_message = f"Failed to write file: {e}"
                result_info.file_path = None # Ensure file_path is None on write error
                any_errors = True
        elif result_info.status == "failure":
            any_errors = True
            logger.error(f"Failed to generate XML for block_id {result_info.block_id}: {result_info.error_message}")
        
        processed_xml_files.append(result_info)
    
    state.generated_node_xmls = processed_xml_files

    if any_errors:
        logger.error("One or more errors occurred during individual XML generation.")
        # Decide if this is a full stop error or if we can proceed with partial results
        # For now, let's flag it but allow the graph to potentially continue if some succeeded
        # state["is_error"] = True 
        # state["error_message"] = "Errors occurred during XML generation for some nodes."
        # state["dialog_state"] = "error" 
        # Let graph builder decide based on number of successes vs failures perhaps
        pass # For now, just log and proceed to next state

    logger.info(f"Finished Step 2. Generated {len(processed_xml_files) - sum(1 for r in processed_xml_files if r.status=='failure')} XML files successfully.")
    state.dialog_state = "individual_xmls_generated"
    return state

# --- Helper function to prepare data for the relation XML prompt ---
def _prepare_data_for_relation_prompt(
    parsed_steps: List[Dict[str, Any]], 
    generated_xmls: List[GeneratedXmlFile]
) -> List[Dict[str, Any]]:
    """
    Prepares a simplified tree structure of operations with their final block_ids
    for the relation XML generation prompt.
    Relies on the order of generated_xmls matching a full traversal of parsed_steps.
    """
    
    generated_xml_iter = iter(generated_xmls) # Create an iterator for generated_xmls

    def _build_relation_tree_with_ids(current_parsed_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tree_for_prompt = []
        for step in current_parsed_steps:
            try:
                corresponding_xml_info = next(generated_xml_iter)
            except StopIteration:
                logger.error("Ran out of generated_xmls while building relation tree. Mismatch likely.")
                # Optionally, raise an error or return a partial tree with an error indicator.
                # For now, we'll just break and the resulting tree might be incomplete.
                break 

            relation_node_data = {
                "type": step["type"], # Type from parsed_step
                "id": corresponding_xml_info.block_id, # Actual block_id from generated_xmls
            }
            if step.get("sub_steps") and isinstance(step["sub_steps"], list):
                relation_node_data["sub_steps"] = _build_relation_tree_with_ids(step["sub_steps"])
            tree_for_prompt.append(relation_node_data)
        return tree_for_prompt

    if not parsed_steps:
        return []
    if not generated_xmls: # If no XMLs were generated (e.g., empty plan), no relations to build
        logger.warning("_prepare_data_for_relation_prompt: No generated_xmls provided for mapping.")
        # Fallback: build tree with original id_suggestions or placeholders if absolutely necessary,
        # but this means the relation XML will not have correct final block IDs.
        # For now, it's better to return an empty tree or signal an issue if IDs are crucial.
        # Let's assume for now that if generated_xmls is empty, parsed_steps should also logically lead to empty relations.
        return []


    # Check for length mismatch as a basic safeguard
    # A more robust check would be to count total nodes in parsed_steps (including sub_steps)
    # and compare with len(generated_xmls).
    
    # Simple count for now:
    def count_total_ops(steps: List[Dict[str, Any]]) -> int:
        count = 0
        for step in steps:
            count += 1
            if step.get("sub_steps"):
                count += count_total_ops(step["sub_steps"])
        return count

    total_parsed_ops = count_total_ops(parsed_steps)
    if total_parsed_ops != len(generated_xmls):
        logger.error(
            f"Mismatch in total parsed operations ({total_parsed_ops}) "
            f"and number of generated XML files ({len(generated_xmls)}). "
            "Block IDs in relation.xml might be incorrect."
        )
        # Depending on severity, could raise an error here or return empty list.
        # For now, will proceed, but this is a sign of upstream issues.

    return _build_relation_tree_with_ids(parsed_steps)


# --- Node 3: Generate Node Relation XML ---
async def generate_relation_xml_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 3: Generate Node Relation XML ---")
    state.current_step_description = "Generating node relation XML file"

    config = state.config
    parsed_steps = state.parsed_flow_steps
    # Ensure generated_node_xmls is not None before passing
    generated_node_xmls_list = state.generated_node_xmls if state.generated_node_xmls is not None else []


    if not parsed_steps:
        logger.error("Parsed flow steps are missing for relation XML generation.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for relation XML."
        state.dialog_state = "error"
        return state

    # If there are no parsed steps, or no generated XMLs, generate an empty relation XML.
    if not generated_node_xmls_list: # Also implies parsed_steps might be empty or led to no XMLs
        logger.warning("Generated node XMLs list is empty. Generating empty relation XML.")
        state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
        state.dialog_state = "relation_xml_generated"
        
        output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
        relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
        relation_file_path = output_dir / relation_file_name
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(relation_file_path, "w", encoding="utf-8") as f:
                f.write(state.relation_xml_content)
            state.relation_xml_path = str(relation_file_path)
            logger.info(f"Wrote empty relation XML to {relation_file_path}")
        except IOError as e:
            logger.error(f"Failed to write empty relation XML to {relation_file_path}: {e}", exc_info=True)
            state.is_error = True # Still an error if file write fails
            state.error_message = f"Failed to write empty relation XML: {e}"
            state.dialog_state = "error"
        return state

    try:
        simplified_flow_structure_with_ids = _prepare_data_for_relation_prompt(
            parsed_steps, 
            generated_node_xmls_list
        )
    except Exception as e:
        logger.error(f"Error preparing data for relation prompt: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to prepare data for relation XML: {e}"
        state.dialog_state = "error"
        return state

    if not simplified_flow_structure_with_ids: # Should be caught by earlier check on generated_node_xmls_list
         logger.warning("Simplified flow structure for relation prompt is empty after prep. Generating empty relation XML.")
         state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
         state.dialog_state = "relation_xml_generated"
         # Code to save empty file (similar to above)
         output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
         relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
         relation_file_path = output_dir / relation_file_name
         try:
            os.makedirs(output_dir, exist_ok=True)
            with open(relation_file_path, "w", encoding="utf-8") as f:
                f.write(state.relation_xml_content)
            state.relation_xml_path = str(relation_file_path)
            logger.info(f"Wrote empty relation XML (after prep) to {relation_file_path}")
         except IOError as e: # pragma: no cover
            logger.error(f"Failed to write empty relation XML (after prep) to {relation_file_path}: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Failed to write empty relation XML (after prep): {e}"
            state.dialog_state = "error"
         return state

    flow_structure_json_for_prompt = json.dumps(simplified_flow_structure_with_ids, indent=2)
    
    example_relation_xml_content = "<!-- Default example relation XML structure -->"
    static_example_relation_xml_path = "/workspace/database/flow_database/result/5.15_test/relation.xml" # Specific example
    try:
        with open(static_example_relation_xml_path, 'r', encoding='utf-8') as f:
            example_relation_xml_content = f.read()
    except Exception as e:
        logger.warning(f"Could not load example relation XML from {static_example_relation_xml_path}: {e}. Prompt will use its internal example.")

    placeholder_values = {
        **config,
        "PARSED_FLOW_STRUCTURE_WITH_IDS_JSON": flow_structure_json_for_prompt,
        "EXAMPLE_RELATION_XML_CONTENT": example_relation_xml_content
    }

    system_prompt_content = get_filled_prompt("flow_step3_generate_relation_xml.md", placeholder_values)
    if not system_prompt_content: # pragma: no cover
        logger.error("Failed to load or fill system prompt: flow_step3_generate_relation_xml.md")
        state.is_error = True
        state.error_message = "Failed to load relation XML generation prompt."
        state.dialog_state = "error"
        return state

    user_message_for_llm = (
        f"Please generate the relation.xml content based on the `PARSED_FLOW_STRUCTURE_WITH_IDS_JSON` provided in the system prompt. "
        f"Ensure the output is only the XML content, adhering to the structural rules (no <field> or data-blockNo) outlined in the system prompt."
    )

    llm_response = await invoke_llm_for_text_output(
        llm,
        system_prompt_content=system_prompt_content,
        user_message_content=user_message_for_llm,
        message_history=None # Explicitly set to None
    )

    if "error" in llm_response or not llm_response.get("text_output"): # pragma: no cover
        error_msg = f"Relation XML generation LLM call failed. Error: {llm_response.get('error', 'No output')}"
        logger.error(error_msg)
        state.is_error = True
        state.error_message = error_msg
        state.relation_xml_content = llm_response.get("text_output") 
        return state
    
    generated_relation_xml_string = llm_response["text_output"].strip()

    match = re.search(r"```xml\n(.*?)\n```", generated_relation_xml_string, re.DOTALL)
    if match:
        extracted_xml = match.group(1).strip()
        logger.info("Extracted relation XML from markdown code block.")
        generated_relation_xml_string = extracted_xml
    else:
        first_angle = generated_relation_xml_string.find('<')
        last_angle = generated_relation_xml_string.rfind('>')
        if first_angle != -1 and last_angle != -1 and last_angle > first_angle:
            potential_xml = generated_relation_xml_string[first_angle : last_angle+1]
            if potential_xml.strip().startswith("<") and potential_xml.strip().endswith(">"):
                if generated_relation_xml_string.strip() != potential_xml.strip(): # pragma: no cover
                    logger.info("Attempting to extract relation XML by finding first '<' and last '>'.")
                    generated_relation_xml_string = potential_xml.strip()

    if not (generated_relation_xml_string.startswith("<") and generated_relation_xml_string.endswith(">")): # pragma: no cover
        error_msg = f"LLM output for relation.xml does not look like valid XML: {generated_relation_xml_string[:200]}..."
        logger.error(error_msg)
        state.is_error = True
        state.error_message = error_msg
        state.relation_xml_content = generated_relation_xml_string
        state.dialog_state = "error"
        return state

    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(generated_relation_xml_string)
        logger.info("Successfully validated relation XML string with ElementTree.")
    except ET.ParseError as e: # pragma: no cover
        error_msg = f"Generated relation.xml is not well-formed XML. ParseError: {e}. Content: {generated_relation_xml_string[:500]}"
        logger.error(error_msg)
        state.is_error = True
        state.error_message = error_msg
        state.relation_xml_content = generated_relation_xml_string
        state.dialog_state = "error"
        return state

    state.relation_xml_content = generated_relation_xml_string
    
    output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
    relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
    relation_file_path = output_dir / relation_file_name
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(relation_file_path, "w", encoding="utf-8") as f:
            f.write(state.relation_xml_content)
        state.relation_xml_path = str(relation_file_path)
        logger.info(f"Successfully generated and wrote relation XML to {relation_file_path}")
    except IOError as e: # pragma: no cover
        logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to write relation XML: {e}"
        state.dialog_state = "error"
        return state

    state.dialog_state = "relation_xml_generated" 
    return state

# Ensure logger is available at the module level if not already defined
# logger = logging.getLogger(__name__)

# TODO: Implement other node functions for Step 2, 3, 4
# - generate_individual_xmls_node
# - generate_relation_xml_node
# - generate_final_flow_xml_node (this one might not be an LLM node, but a Python function node) 