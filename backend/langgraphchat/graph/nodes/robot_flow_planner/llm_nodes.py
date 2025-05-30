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
from .prompt_loader import get_filled_prompt, load_node_descriptions, append_node_description

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
    "PROMPT_INPUT_NEEDS_CLARIFICATION_FROM_LLM": "I couldn't fully understand your request or it needs more details for enrichment. Could you please rephrase or add more information?",
    "PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE": (
        "根据您的请求 '{current_raw_user_request}', 我生成的初步流程如下:\\n\\n"
        "```text\\n{enriched_text_proposal}\\n```\\n\\n"
        "您是否同意按此流程继续？ (请输入 'yes' 或 'no'，或者提供修改意见)"
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
    
    # Check if LLM is ChatDeepSeek and streaming is enabled
    is_streaming_deepseek = isinstance(llm, BaseChatModel) and hasattr(llm, 'streaming') and llm.streaming and "deepseek" in llm.model_name.lower()

    if is_streaming_deepseek:
        logger.info("Using streaming for ChatDeepSeek text output.")
        full_response_content = ""
        try:
            # Langchain's stream() method is synchronous, astream() is asynchronous
            # Assuming this function might be called in an async context from other nodes,
            # we should ideally use astream if invoke_llm_for_text_output itself is async.
            # For now, let's use a simple loop that would work with a sync llm.stream()
            # or an async llm.astream() if adapted.
            # Given the function is `async def`, we should use `astream`.
            async for chunk in llm.astream(messages): # Ensure llm.astream is available and correctly used
                if hasattr(chunk, 'content'):
                    print(chunk.content, end="", flush=True)
                    full_response_content += chunk.content
            print() # Add a newline after streaming is complete
            return {"text_output": full_response_content}
        except Exception as e:
            logger.error(f"LLM streaming call for string output failed. Error: {e}", exc_info=True)
            # Fallback or error reporting
            if full_response_content: # If some content was streamed before error
                 print("\\n<Streaming incomplete due to error>", flush=True)
                 return {"text_output": full_response_content, "error": "LLM streaming failed partially.", "details": str(e)}
            return {"error": "LLM streaming call for string output failed.", "details": str(e)}
    else:
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
async def preprocess_and_enrich_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]: # Ensure return type is Dict
    logger.info(f"--- Entering Preprocess & Enrich (dialog_state: {state.dialog_state}, user_input: '{state.user_input}', language: '{state.language}') ---")

    current_user_input_for_this_cycle = state.user_input
    state.user_input = None # Consume user_input at the beginning

    # Select language for interaction texts
    active_texts = USER_INTERACTION_TEXTS_ZH if state.language == "zh" else USER_INTERACTION_TEXTS

    # Helper to add AIMessage if not already the last message or similar
    def add_ai_message_if_needed(content: str):
        if not state.messages or not (isinstance(state.messages[-1], AIMessage) and state.messages[-1].content == content):
            state.messages = state.messages + [AIMessage(content=content)] # Use .messages for direct list modification

    # 1. Handle specific AWAITING states first if there's user input for them
    if state.dialog_state == "awaiting_enrichment_confirmation":
        if not current_user_input_for_this_cycle:
            logger.info("Still awaiting enrichment confirmation from user. Clarification question should be in messages.")
            if not state.clarification_question and not state.proposed_enriched_text:
                 add_ai_message_if_needed(active_texts.get("ERROR_INTERNAL_NO_PLAN_TO_CONFIRM", "发生了一个内部错误：正在等待浓缩确认，但没有找到待确认的计划。请重新描述您的流程。") if state.language == "zh" else active_texts.get("ERROR_INTERNAL_NO_PLAN_TO_CONFIRM", "An internal error occurred: Awaiting enrichment confirmation, but no plan found to confirm. Please describe your flow again."))
                 state.dialog_state = "awaiting_user_input"
            elif not state.clarification_question and state.proposed_enriched_text: # Make sure question is there
                confirm_prompt = active_texts["PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE"].format(
                    current_raw_user_request=state.raw_user_request, # or active_plan_basis if multi-turn revision
                    enriched_text_proposal=state.proposed_enriched_text
                )
                add_ai_message_if_needed(confirm_prompt)
                state.clarification_question = confirm_prompt
            state.subgraph_completion_status = "needs_clarification"
            return state.dict(exclude_none=True)

        logger.info(f"Processing user response for enrichment confirmation: '{current_user_input_for_this_cycle}'")
        state.messages = state.messages + [HumanMessage(content=current_user_input_for_this_cycle)]
        
        # Simple yes/no check for now, can be enhanced with LLM for intent parsing
        user_feedback_lower = current_user_input_for_this_cycle.lower()
        if "yes" in user_feedback_lower or "同意" in user_feedback_lower or "确认" in user_feedback_lower or "可以" in user_feedback_lower:
            logger.info("User affirmed the enriched plan.")
            state.enriched_structured_text = state.proposed_enriched_text
            state.active_plan_basis = state.proposed_enriched_text # The confirmed plan is now the basis
            state.proposed_enriched_text = None
            state.clarification_question = None
            state.dialog_state = "input_understood_ready_for_xml"
            add_ai_message_if_needed(active_texts["INFO_AFFIRM_PLAN_CONFIRMED"])
        elif "no" in user_feedback_lower or "修改" in user_feedback_lower or "不" in user_feedback_lower:
            logger.info("User wants to modify the enriched plan. Treating feedback as new plan basis.")
            add_ai_message_if_needed(active_texts.get("PROMPT_ASK_FOR_MODIFICATION_OR_NEW_PLAN", "好的，请告诉我您希望如何修改，或者提供一个全新的流程描述。") if state.language == "zh" else active_texts.get("PROMPT_ASK_FOR_MODIFICATION_OR_NEW_PLAN", "Okay, please tell me how you'd like to modify it, or provide a completely new flow description."))
            state.active_plan_basis = current_user_input_for_this_cycle 
            state.raw_user_request = current_user_input_for_this_cycle 
            state.enriched_structured_text = None
            state.proposed_enriched_text = None
            state.clarification_question = None
            state.dialog_state = "processing_user_input" 
            state.subgraph_completion_status = "needs_clarification"
        else: # Unclear feedback
            logger.info("User feedback on enriched plan is unclear.")
            add_ai_message_if_needed(active_texts["GENERAL_FEEDBACK_GUIDANCE"])
            state.dialog_state = "awaiting_enrichment_confirmation" # Stay and re-ask
            state.subgraph_completion_status = "needs_clarification"
        return state.dict(exclude_none=True)

    # 2. Handle 'generation_failed' state if user provides new input
    if state.dialog_state == "generation_failed":
        if not current_user_input_for_this_cycle:
            logger.info("Still awaiting user input after previous generation failure. Error message should be in messages.")
            if not any("生成XML时遇到问题" in msg.content or "problem generating XML" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                add_ai_message_if_needed( (active_texts.get("PROMPT_RETRY_AFTER_GENERATION_FAILURE_TEMPLATE", "抱歉，上次生成XML时遇到问题: {error_message}。请修改您的指令或提供新的流程描述。") if state.language == "zh" else active_texts.get("PROMPT_RETRY_AFTER_GENERATION_FAILURE_TEMPLATE", "Sorry, there was a problem generating the XML last time: {error_message}. Please modify your instructions or provide a new flow description.")).format(error_message=state.error_message or ('未知错误' if state.language == "zh" else 'Unknown error')) )
            state.dialog_state = 'awaiting_user_input' 
            state.subgraph_completion_status = "needs_clarification"
            return state.dict(exclude_none=True)
        
        logger.info(f"Received user input after generation failure: '{current_user_input_for_this_cycle}'. Treating as new/revised flow.")
        state.messages = state.messages + [HumanMessage(content=current_user_input_for_this_cycle)]
        state.raw_user_request = current_user_input_for_this_cycle
        state.active_plan_basis = current_user_input_for_this_cycle
        state.enriched_structured_text = None
        state.parsed_flow_steps = None
        state.generated_node_xmls = [] 
        state.relation_xml_content = None
        state.final_flow_xml_content = None
        state.is_error = False 
        state.error_message = None
        state.clarification_question = None
        state.dialog_state = "processing_user_input"

    # 3. Handle 'initial' or 'awaiting_user_input' states when new input is provided
    if state.dialog_state in ["initial", "awaiting_user_input"]:
        if not current_user_input_for_this_cycle:
            logger.info(f"Dialog state is '{state.dialog_state}' but no user_input. Awaiting next cycle with input.")
            if state.dialog_state == "initial" and not state.messages: 
                 welcome_msg = active_texts.get("PROMPT_WELCOME_MESSAGE", "您好！我是机器人流程设计助手。请输入您的流程描述。") if state.language == "zh" else active_texts.get("PROMPT_WELCOME_MESSAGE", "Hello! I am your robot flow design assistant. Please enter your flow description.")
                 add_ai_message_if_needed(welcome_msg)
                 state.clarification_question = welcome_msg 
            
            if state.dialog_state == "awaiting_user_input" and not state.clarification_question:
                logger.warning("In 'awaiting_user_input' with no current_user_input and no existing clarification_question. Setting a generic one.")
                generic_prompt_msg = active_texts.get("PROMPT_GENERAL_ASK_FOR_INPUT", "请提供您的机器人流程描述或您希望进行的下一步操作。") if state.language == "zh" else active_texts.get("PROMPT_GENERAL_ASK_FOR_INPUT", "Please provide your robot flow description or the next action you'd like to take.")
                add_ai_message_if_needed(generic_prompt_msg)
                state.clarification_question = generic_prompt_msg
            
            state.dialog_state = 'awaiting_user_input'
            state.subgraph_completion_status = "needs_clarification" 
            return state.dict(exclude_none=True)

        logger.info(f"Received new user input in '{state.dialog_state}' state: '{current_user_input_for_this_cycle}'")
        state.messages = state.messages + [HumanMessage(content=current_user_input_for_this_cycle)]
        state.raw_user_request = current_user_input_for_this_cycle
        state.active_plan_basis = current_user_input_for_this_cycle
        state.enriched_structured_text = None
        state.proposed_enriched_text = None
        state.parsed_flow_steps = None
        state.generated_node_xmls = []
        state.relation_xml_content = None
        state.final_flow_xml_content = None
        state.is_error = False 
        state.error_message = None
        state.clarification_question = None
        state.dialog_state = "processing_user_input"

    # 4. Core 'processing_user_input' logic (enrichment)
    if state.dialog_state == "processing_user_input":
        logger.info(f"Processing user input. Active plan basis: '{state.active_plan_basis[:200]}...'")
        
        # REMOVED: Attempt to auto-detect robot model 
        # REMOVED: Asking user for robot model

        if not state.active_plan_basis: 
            logger.warning("Reached 'processing_user_input' but active_plan_basis is empty. Reverting to awaiting_user_input.")
            add_ai_message_if_needed(active_texts.get("ERROR_EMPTY_PLAN_BASIS", "请输入有效的流程描述。") if state.language == "zh" else active_texts.get("ERROR_EMPTY_PLAN_BASIS", "Please enter a valid flow description."))
            state.dialog_state = "awaiting_user_input"
            state.subgraph_completion_status = "needs_clarification"
            return state.dict(exclude_none=True)

        # Proceed with plan enrichment
        logger.info(f"Proceeding to enrich plan based on: '{state.active_plan_basis}'.")
        
        available_node_types_with_descriptions_str = "没有可用的节点类型信息。"
        node_template_dir = state.config.get("NODE_TEMPLATE_DIR_PATH")
        if node_template_dir and os.path.isdir(node_template_dir):
            try:
                all_block_files = sorted([
                    f for f in os.listdir(node_template_dir)
                    if os.path.isfile(os.path.join(node_template_dir, f)) and f.endswith((".xml")) # Only process .xml files for templates
                ])
                if all_block_files:
                    logger.info(f"Found {len(all_block_files)} block template files: {all_block_files}")
                    existing_descriptions = load_node_descriptions()
                    descriptions_for_prompt = ["可用节点类型及其功能和XML模板:"]
                    
                    for block_file in all_block_files:
                        block_type = os.path.splitext(block_file)[0]
                        description_to_use = existing_descriptions.get(block_type)
                        if description_to_use is None:
                            logger.info(f"Description for block type '{block_type}' not found in existing descriptions. Using default.")
                            description_to_use = "该节点类型的描述当前不可用。"
                        
                        xml_template_content = "XML模板无法加载。"
                        try:
                            template_file_path = Path(node_template_dir) / block_file
                            with open(template_file_path, 'r', encoding='utf-8') as f:
                                xml_template_content = f.read().strip()
                        except Exception as e_xml:
                            logger.error(f"Error loading XML template for {block_type} from {template_file_path}: {e_xml}")

                        descriptions_for_prompt.append(f"- 类型: {block_type}")
                        descriptions_for_prompt.append(f"  描述: {description_to_use}")
                        descriptions_for_prompt.append(f"  模板:\\n```xml\\n{xml_template_content}\\n```")
                    
                    if len(descriptions_for_prompt) > 1: 
                        available_node_types_with_descriptions_str = "\\n\\n".join(descriptions_for_prompt)
                    else:
                        available_node_types_with_descriptions_str = "未能加载任何节点类型、描述或其XML模板。"
                else:
                    logger.warning(f"No .xml block type files found in {node_template_dir}")
                    available_node_types_with_descriptions_str = "在配置的路径中未找到任何XML节点模板文件。"
            except Exception as e:
                logger.error(f"Error loading block types or descriptions: {e}", exc_info=True)
                available_node_types_with_descriptions_str = f"加载节点类型信息时出错: {e}"
        else:
            logger.warning(f"NODE_TEMPLATE_DIR_PATH '{node_template_dir}' is not configured or not a directory.")
            available_node_types_with_descriptions_str = "节点模板目录未正确配置。"

        enrich_prompt_name = "flow_step0_enrich_input.md"
        enrich_placeholders = {
            "user_core_request": state.active_plan_basis,
            "AVAILABLE_NODE_TYPES_WITH_DESCRIPTIONS": available_node_types_with_descriptions_str
        }
        
        filled_enrich_prompt_content = get_filled_prompt(enrich_prompt_name, enrich_placeholders)

        if not filled_enrich_prompt_content:
            logger.error(f"Failed to load or fill enrichment prompt: {enrich_prompt_name}. Skipping enrichment.")
            state.proposed_enriched_text = state.active_plan_basis 
        else:
            enriched_result = await invoke_llm_for_text_output(
                llm,
                system_prompt_content="You are a helpful assistant that refines user requests into a structured, step-by-step robot plan.", 
                user_message_content=filled_enrich_prompt_content
            )
            if "error" in enriched_result or not enriched_result.get("text_output"):
                logger.error(f"Enrichment LLM call failed: {enriched_result.get('error')}. Using raw plan for confirmation.")
                add_ai_message_if_needed(active_texts.get("INFO_ENRICHMENT_FAILED_USING_RAW", "抱歉，我在理解和优化您的流程描述时遇到初步问题。我们将基于您的原始输入进行确认。") if state.language == "zh" else active_texts.get("INFO_ENRICHMENT_FAILED_USING_RAW", "Sorry, I encountered an initial issue understanding and optimizing your flow description. We will proceed with confirmation based on your original input."))
                state.proposed_enriched_text = state.active_plan_basis
            else:
                logger.info("Successfully enriched the plan with LLM.")
                state.proposed_enriched_text = enriched_result["text_output"].strip()
        
        logger.info(f"Proposing enriched plan for confirmation: {state.proposed_enriched_text}")
        current_raw_request_for_prompt = state.raw_user_request if state.raw_user_request else state.active_plan_basis
        
        state.clarification_question = active_texts["PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE"].format(
            current_raw_user_request=str(current_raw_request_for_prompt), 
            enriched_text_proposal=str(state.proposed_enriched_text) 
        )
        add_ai_message_if_needed(state.clarification_question)
        state.dialog_state = "awaiting_enrichment_confirmation"
        state.subgraph_completion_status = "needs_clarification"
        return state.dict(exclude_none=True)

    logger.info(
        f"Exiting P&E Node. dialog_state: {state.dialog_state}, "
        f"raw_user_request: '{state.raw_user_request}', "
        f"active_plan_basis: '{state.active_plan_basis}', "
        f"enriched_structured_text: '{state.enriched_structured_text}'"
    )
    logger.info(f"--- Exiting Preprocess & Enrich (new dialog_state: {state.dialog_state}) ---")
    return state.dict(exclude_none=True)


# --- Node 1: Understand Input ---
class ParsedStep(BaseModel):
    id_suggestion: str = Field(description="A suggested unique ID for this operation block, e.g., 'movel_P1_Z_on'.")
    type: str = Field(description="The type of operation, e.g., 'select_robot', 'set_motor', 'moveL', 'loop', 'return'.")
    description: str = Field(description="A brief natural language description of this specific step.")
    parameters: Dict[str, Any] = Field(description="A dictionary of parameters for this operation, e.g., {'robotName': 'dobot_mg400'} or {'point_name_list': 'P1', 'control_z': 'enable'.}")
    has_sub_steps: bool = Field(False, description="Whether this step contains nested sub-steps.")
    sub_step_descriptions: List[str] = Field(default_factory=list, description="List of description strings for nested operations, to avoid deep recursion.")

class UnderstandInputSchema(BaseModel):
    operations: List[ParsedStep] = Field(description="An ordered list of operations identified from the user input text.")

async def understand_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 1: Understand Input (from potentially enriched text) ---")
    state.current_step_description = "Understanding user input"
    state.is_error = False # Reset error flag at the beginning of the node execution

    enriched_input_text = state.enriched_structured_text
    if not enriched_input_text:
        logger.error("Enriched input text is missing in state for understand_input_node.")
        state.is_error = True
        state.error_message = "Enriched input text is missing for parsing."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    config = state.config
    if not config:
        logger.error("Config (placeholder values) is missing in state.")
        state.is_error = True
        state.error_message = "Configuration (placeholders) is missing."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
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
    placeholder_values_for_prompt.setdefault("GENERAL_INSTRUCTION_INTRO", "Please analyze the following robot workflow.")

    user_message_for_llm = (
        f"Parse the following robot workflow description into a structured format. "
        f"Identify each distinct operation. " # Removed robot name identification
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
        # ---- START: Added for debugging ----
        print("\nERROR: LLM output for UnderstandInputSchema caused an error.")
        print(f"LLM Raw Output (json.loads might be needed if it is a string):\n{raw_out}\n")
        print(f"Full parsed_output from LLM call before Pydantic validation:\n{json.dumps(parsed_output, indent=2, ensure_ascii=False)}\n")
        # ---- END: Added for debugging ----
        state.is_error = True
        state.error_message = f"Step 1: Failed to understand input. LLM Error: {error_msg_detail}. Raw: {str(raw_out)[:500]}"
        state.dialog_state = "generation_failed" # Corrected: Use a valid Literal state
        state.subgraph_completion_status = "error"
        return state

    # Pre-process parameters to ensure they are dicts
    if isinstance(parsed_output, dict) and "operations" in parsed_output and isinstance(parsed_output["operations"], list):
        for operation in parsed_output["operations"]:
            if isinstance(operation, dict) and "parameters" in operation:
                params = operation["parameters"]
                if isinstance(params, str):
                    try:
                        operation["parameters"] = json.loads(params)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to json.loads parameters string for operation {operation.get('id_suggestion', 'N/A')}: {params}. Error: {e}. Leaving as string, Pydantic validation might fail.")
                elif not isinstance(params, dict):
                    logger.warning(f"Operation {operation.get('id_suggestion', 'N/A')} parameters is not a dict or string: {type(params)}. Pydantic validation might fail.")
    elif isinstance(parsed_output, UnderstandInputSchema): # If it's already a Pydantic model (less likely path if error occurred before)
        for operation_model in parsed_output.operations:
            if isinstance(operation_model.parameters, str): # This check is less likely to be hit if conversion already happened
                try:
                    # Pydantic models are generally immutable after creation without specific config,
                    # so direct assignment might not work as intended here.
                    # This branch indicates a deeper issue if parameters are strings *after* Pydantic parsing.
                    # For now, logging this scenario.
                    logger.warning(f"Operation {operation_model.id_suggestion} parameters is a string *after* initial Pydantic parsing attempt. This is unusual. String: {operation_model.parameters}")
                except Exception as e:
                     logger.warning(f"Could not process parameters for {operation_model.id_suggestion} after noticing it's a string post-Pydantic attempt: {e}")


    # Manual validation of operation types BEFORE Pydantic parsing, if known_node_types_list is available
    if known_node_types_list and parsed_output.get("operations"):
        flow_ops_data = parsed_output.get("operations", [])
        invalid_types_details = []
        # Check types in operations (no longer recursive since we use flat structure)
        for i, op_data in enumerate(flow_ops_data):
            op_type = op_data.get("type")
            current_op_id_for_log = op_data.get('id_suggestion', f"op_{i+1}")
            current_op_desc_for_log = op_data.get('description', 'N/A')
            if op_type not in known_node_types_list and op_type != "unknown_operation": # Allow 'unknown_operation' as per prompt
                invalid_types_details.append(
                    f"Operation {current_op_id_for_log} ('{current_op_desc_for_log}') has an invalid type '{op_type}'. "
                    f"Valid types are: {known_node_types_list} (or 'unknown_operation')."
                )
        
        if invalid_types_details:
            error_message = " ".join(invalid_types_details)
            logger.error(f"Step 1 Failed: Invalid node types found after LLM parsing. {error_message}")
            state.is_error = True
            state.error_message = f"Step 1: Invalid node types found. {error_message} Raw LLM Output: {str(parsed_output)[:500]}"
            state.dialog_state = "error"
            state.subgraph_completion_status = "error"
            return state

    try:
        # If parsed_output is already a Pydantic model instance from invoke_llm_for_json_output,
        # this re-validation might be redundant unless pre-processing was needed.
        # If pre-processing occurred on a dict, this is the main validation.
        if isinstance(parsed_output, UnderstandInputSchema):
            validated_data = parsed_output # Already validated if it's the correct type
        else:
            validated_data = UnderstandInputSchema(**parsed_output)

        logger.info(f"Step 1 Succeeded. Parsed operations: {len(validated_data.operations)}")
        
        # Validate operation types (excluding sub-steps for now)
        # ... (rest of type validation)

        state.parsed_flow_steps = [op.dict(exclude_none=True) for op in validated_data.operations]
        state.parsed_robot_name = validated_data.robot 
        state.error_message = None
        state.messages = current_messages + [AIMessage(content=f"Successfully parsed input. Robot: {state.parsed_robot_name}. Steps: {len(state.parsed_flow_steps)}")]
        state.subgraph_completion_status = None
        return state
    except Exception as e: 
        logger.error(f"Step 1 Failed: Pydantic validation error for UnderstandInputSchema or subsequent validation. Error: {e}. Raw Output from LLM: {json.dumps(parsed_output, indent=2, ensure_ascii=False)}", exc_info=True)
        print("\\nERROR: Pydantic validation failed for UnderstandInputSchema or subsequent validation.")
        print(f"LLM's Parsed Output that failed validation:\\n{json.dumps(parsed_output, indent=2, ensure_ascii=False)}\\n")
        state.is_error = True
        state.error_message = f"Step 1: Output validation error. Details: {e}. Parsed: {str(parsed_output)[:500]}"
        state.dialog_state = "generation_failed"
        state.subgraph_completion_status = "error"
        return state

# --- Helper function to recursively collect all operations for XML generation --- 
def _collect_all_operations_for_xml_generation(
    operations: List[Dict[str, Any]], 
    config: Dict[str, Any],
    _block_counter: int = 1 # Internal counter, starts at 1
    ) -> (List[Dict[str, Any]], int): # Returns: (list of op_infos_for_llm, next_block_counter)
    """
    Flattens the list of operations and assigns 
    unique IDs and block numbers for XML generation.
    Now handles flat structure with sub_step_descriptions instead of recursive sub_steps.
    """
    ops_to_generate = []
    block_id_prefix = config.get("BLOCK_ID_PREFIX_EXAMPLE", "block_uuid") 

    for op_data_from_step1 in operations:
        xml_block_id = f"{block_id_prefix}_{_block_counter}"
        xml_data_block_no = str(_block_counter)
        
        generated_xml_filename = f"{xml_block_id}_{op_data_from_step1['type']}.xml"

        # Include sub-step descriptions in the description if available
        full_description = op_data_from_step1['description']
        if op_data_from_step1.get('has_sub_steps', False) and op_data_from_step1.get('sub_step_descriptions'):
            sub_descriptions = op_data_from_step1['sub_step_descriptions']
            if sub_descriptions:
                full_description += f" [Sub-steps: {'; '.join(sub_descriptions)}]"

        op_info_for_llm = {
            "type": op_data_from_step1['type'],
            "description": full_description,
            "parameters_json": json.dumps(op_data_from_step1.get('parameters', {})), # Ensure parameters exist
            "id_suggestion_from_step1": op_data_from_step1.get('id_suggestion', ''),
            
            "target_xml_block_id": xml_block_id, 
            "target_xml_data_block_no": xml_data_block_no,
            "target_xml_filename": generated_xml_filename,
            "node_template_filename_to_load": f"{op_data_from_step1['type']}.xml" 
        }
        ops_to_generate.append(op_info_for_llm)
        _block_counter += 1

        # No longer process recursive sub_steps since we use flat structure
        # if "sub_steps" in op_data_from_step1 and op_data_from_step1["sub_steps"]:
        #     sub_ops_list, next_block_counter_after_subs = _collect_all_operations_for_xml_generation(
        #         op_data_from_step1["sub_steps"],
        #         config,
        #         _block_counter=_block_counter
        #     )
        #     ops_to_generate.extend(sub_ops_list)
        #     _block_counter = next_block_counter_after_subs

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
    robot_model_from_state = "unknown_robot" # Keep a default value or remove if placeholder not used

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
        "CURRENT_NODE_PARAMETERS_JSON": op_info_for_llm["parameters_json"],
        "CURRENT_NODE_ID_SUGGESTION_FROM_STEP1": op_info_for_llm["id_suggestion_from_step1"],
        "TARGET_XML_BLOCK_ID": op_info_for_llm["target_xml_block_id"],
        "TARGET_XML_DATA_BLOCK_NO": op_info_for_llm["target_xml_data_block_no"],
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

    logger.info(f"Attempting LLM call for op type: {op_info_for_llm['type']}, block_id: {op_info_for_llm['target_xml_block_id']}")
    logger.info(f"LLM User Message: {user_message_for_llm}")
    # For more detailed debugging, you might log the system prompt, but it can be very long.
    # system_prompt_for_debug = get_filled_prompt("flow_step2_generate_node_xml.md", placeholder_values)
    # logger.debug(f"LLM System Prompt (first 500 chars): {system_prompt_for_debug[:500]}...")

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
    state.is_error = False # Reset error flag at the beginning of the node execution

    parsed_steps = state.parsed_flow_steps
    config = state.config

    if not parsed_steps:
        logger.error("parsed_flow_steps is missing in state for generate_individual_xmls_node.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for XML generation."
        state.dialog_state = "error" # Or back to understand_input or initial
        state.subgraph_completion_status = "error"
        return state

    if not config or not config.get("OUTPUT_DIR_PATH"):
        logger.error("OUTPUT_DIR_PATH is not configured in state.config.")
        state.is_error = True
        state.error_message = "Output directory path (OUTPUT_DIR_PATH) is not configured."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    # 1. Flatten all operations
    all_ops_for_llm, _ = _collect_all_operations_for_xml_generation(parsed_steps, config)
    if not all_ops_for_llm:
        logger.warning("No operations collected for XML generation. This might be an empty plan.")
        state.generated_node_xmls = []
        state.dialog_state = "generating_xml_relation" # Mark step as complete even if no XMLs
        state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "error"
        # Decide if this is a full stop error or if we can proceed with partial results
        # For now, let's flag it but allow the graph to potentially continue if some succeeded
        # state["is_error"] = True 
        pass # For now, just log and proceed to next state

    logger.info(f"Finished Step 2. Generated {len(processed_xml_files) - sum(1 for r in processed_xml_files if r.status=='failure')} XML files successfully.")
    state.dialog_state = "generating_xml_relation" # Corrected value to reflect readiness for next step
    state.subgraph_completion_status = None # 修正：成功时不应是 needs_clarification
    return state

# --- Helper function to prepare data for the relation XML prompt ---
def _prepare_data_for_relation_prompt(
    parsed_steps: List[Dict[str, Any]], 
    generated_xmls: List[GeneratedXmlFile]
) -> List[Dict[str, Any]]:
    """
    Prepares a simplified tree structure of operations with their final block_ids
    for the relation XML generation prompt.
    Now works with flat structure without recursive sub_steps.
    """
    
    if not parsed_steps:
        return []
    if not generated_xmls: # If no XMLs were generated (e.g., empty plan), no relations to build
        logger.warning("_prepare_data_for_relation_prompt: No generated_xmls provided for mapping.")
        return []

    # Simple validation: check if number of operations matches number of generated XMLs
    if len(parsed_steps) != len(generated_xmls):
        logger.error(
            f"Mismatch in parsed operations ({len(parsed_steps)}) "
            f"and number of generated XML files ({len(generated_xmls)}). "
            "Block IDs in relation.xml might be incorrect."
        )
        # Depending on severity, could raise an error here or return empty list.
        # For now, will proceed, but this is a sign of upstream issues.

    # Build simple mapping since we no longer have recursive structure
    tree_for_prompt = []
    for i, step in enumerate(parsed_steps):
        if i < len(generated_xmls):
            corresponding_xml_info = generated_xmls[i]
            relation_node_data = {
                "type": step["type"], # Type from parsed_step
                "id": corresponding_xml_info.block_id, # Actual block_id from generated_xmls
            }
            # Add sub-step info if available but as metadata, not as nested structure
            if step.get("has_sub_steps", False) and step.get("sub_step_descriptions"):
                relation_node_data["has_sub_steps"] = True
                relation_node_data["sub_step_descriptions"] = step["sub_step_descriptions"]
            
            tree_for_prompt.append(relation_node_data)
        else:
            logger.warning(f"No corresponding XML found for parsed step {i}: {step.get('description', 'N/A')}")

    return tree_for_prompt


# --- Node 3: Generate Node Relation XML ---
async def generate_relation_xml_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    logger.info("--- Running Step 3: Generate Node Relation XML ---")
    state.current_step_description = "Generating node relation XML file"
    state.is_error = False # Reset error flag at the beginning of the node execution

    config = state.config
    parsed_steps = state.parsed_flow_steps
    # Ensure generated_node_xmls is not None before passing
    generated_node_xmls_list = state.generated_node_xmls if state.generated_node_xmls is not None else []


    if not parsed_steps:
        logger.error("Parsed flow steps are missing for relation XML generation.")
        state.is_error = True
        state.error_message = "Parsed flow steps are missing for relation XML."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    # If there are no parsed steps, or no generated XMLs, generate an empty relation XML.
    if not generated_node_xmls_list: # Also implies parsed_steps might be empty or led to no XMLs
        logger.warning("Generated node XMLs list is empty. Generating empty relation XML.")
        state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
        state.dialog_state = "generating_xml_final"
        
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
            state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "error"
        return state

    if not simplified_flow_structure_with_ids: # Should be caught by earlier check on generated_node_xmls_list
         logger.warning("Simplified flow structure for relation prompt is empty after prep. Generating empty relation XML.")
         state.relation_xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<xml xmlns="https://developers.google.com/blockly/xml"></xml>'
         state.dialog_state = "generating_xml_final"
         # Code to save empty file (similar to above)
         output_dir = Path(config.get("OUTPUT_DIR_PATH", "/tmp"))
         relation_file_name = config.get("RELATION_FILE_NAME_ACTUAL", "relation.xml")
         relation_file_path = output_dir / relation_file_name
         try:
            os.makedirs(output_dir, exist_ok=True)
            with open(relation_file_path, "w", encoding="utf-8") as f:
                f.write(state.relation_xml_content)
            state.relation_xml_path = str(relation_file_path)
            logger.info(f"Successfully wrote relation XML to {relation_file_path}. Content head: {state.relation_xml_content[:100]}")
         except IOError as e: # pragma: no cover
            logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
            state.is_error = True
            state.error_message = f"Failed to write relation XML: {e}"
            state.dialog_state = "error"
            state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "error"
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
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "error"
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
        state.subgraph_completion_status = "error"
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
        logger.info(f"Successfully wrote relation XML to {relation_file_path}. Content head: {state.relation_xml_content[:100]}")
    except IOError as e: # pragma: no cover
        logger.error(f"Failed to write relation XML to {relation_file_path}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to write relation XML: {e}"
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    state.dialog_state = "generating_xml_final" # Corrected value to reflect readiness for the final XML generation step
    state.subgraph_completion_status = None # 修正：成功时不应是 needs_clarification
    return state

# Ensure logger is available at the module level if not already defined
# logger = logging.getLogger(__name__)

# TODO: Implement other node functions for Step 2, 3, 4
# - generate_individual_xmls_node
# - generate_relation_xml_node
# - generate_final_flow_xml_node (this one might not be an LLM node, but a Python function node) 