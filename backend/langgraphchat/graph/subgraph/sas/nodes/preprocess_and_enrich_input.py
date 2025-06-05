import logging
import os
from typing import Dict, Any, List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from ..state import RobotFlowAgentState # Adjusted import
from ..prompt_loader import get_filled_prompt # Adjusted import
from .....prompts.shared_constants import USER_INTERACTION_TEXTS # Adjusted import
from ..llm_utils import invoke_llm_for_text_output # Import from llm_utils

logger = logging.getLogger(__name__)

async def preprocess_and_enrich_input_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]: # Ensure return type is Dict
    logger.info(f"--- Entering Preprocess & Enrich (dialog_state: {state.dialog_state}, user_input: '{state.user_input}', language: '{state.language}') ---")

    current_user_input_for_this_cycle = state.user_input
    state.user_input = None # Consume user_input at the beginning

    # Select language for interaction texts
    active_texts = USER_INTERACTION_TEXTS

    # Helper to add AIMessage if not already the last message or similar
    def add_ai_message_if_needed(content: str):
        if not state.messages or not (isinstance(state.messages[-1], AIMessage) and state.messages[-1].content == content):
            state.messages = state.messages + [AIMessage(content=content)] # Use .messages for direct list modification

    # 1. Handle specific AWAITING states first if there's user input for them
    if state.dialog_state == "awaiting_enrichment_confirmation":
        if not current_user_input_for_this_cycle:
            logger.info("Still awaiting enrichment confirmation from user. Clarification question should be in messages.")
            if not state.clarification_question and not state.proposed_enriched_text:
                 add_ai_message_if_needed(active_texts.get("ERROR_INTERNAL_NO_PLAN_TO_CONFIRM", "An internal error occurred: Awaiting enrichment confirmation, but no plan found to confirm. Please describe your flow again."))
                 state.dialog_state = "awaiting_user_input"
            elif not state.clarification_question and state.proposed_enriched_text: # Make sure question is there
                confirm_prompt = active_texts["PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE"].format(
                    current_raw_user_request=state.raw_user_request, # or active_plan_basis if multi-turn revision
                    enriched_text_proposal=state.proposed_enriched_text,
                    robot_model=state.robot_model # Added robot_model back for this specific prompt
                )
                add_ai_message_if_needed(confirm_prompt)
                state.clarification_question = confirm_prompt
            state.subgraph_completion_status = "needs_clarification"
            return state.dict(exclude_none=True)

        logger.info(f"Processing user response for enrichment confirmation: '{current_user_input_for_this_cycle}'")
        state.messages = state.messages + [HumanMessage(content=current_user_input_for_this_cycle)]
        
        user_feedback_lower = current_user_input_for_this_cycle.lower()
        if "yes" in user_feedback_lower or "agree" in user_feedback_lower or "confirm" in user_feedback_lower or "ok" in user_feedback_lower or "y" == user_feedback_lower:
            logger.info("User affirmed the enriched plan.")
            state.enriched_structured_text = state.proposed_enriched_text
            state.active_plan_basis = state.proposed_enriched_text 
            state.proposed_enriched_text = None
            state.clarification_question = None
            state.dialog_state = "input_understood_ready_for_xml"
            add_ai_message_if_needed(active_texts["INFO_AFFIRM_PLAN_CONFIRMED"])
        elif "no" in user_feedback_lower or "modify" in user_feedback_lower or "change" in user_feedback_lower or "n" == user_feedback_lower:
            logger.info("User wants to modify the enriched plan. Treating feedback as new plan basis.")
            add_ai_message_if_needed(active_texts.get("PROMPT_ASK_FOR_MODIFICATION_OR_NEW_PLAN", "Okay, please tell me how you\'d like to modify it, or provide a completely new flow description."))
            state.active_plan_basis = current_user_input_for_this_cycle 
            state.raw_user_request = current_user_input_for_this_cycle 
            state.enriched_structured_text = None
            state.proposed_enriched_text = None
            state.clarification_question = None
            state.dialog_state = "processing_user_input" 
            state.subgraph_completion_status = "needs_clarification"
        else: 
            logger.info("User feedback on enriched plan is unclear.")
            add_ai_message_if_needed(active_texts["GENERAL_FEEDBACK_GUIDANCE"])
            state.dialog_state = "awaiting_enrichment_confirmation" 
            state.subgraph_completion_status = "needs_clarification"
        return state.dict(exclude_none=True)

    if state.dialog_state == "generation_failed":
        if not current_user_input_for_this_cycle:
            logger.info("Still awaiting user input after previous generation failure. Error message should be in messages.")
            if not any("problem generating XML" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
                add_ai_message_if_needed( (active_texts.get("PROMPT_RETRY_AFTER_GENERATION_FAILURE_TEMPLATE", "Sorry, there was a problem generating the XML last time: {error_message}. Please modify your instructions or provide a new flow description.")).format(error_message=state.error_message or 'Unknown error') )
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

    if state.dialog_state in ["initial", "awaiting_user_input"]:
        if not current_user_input_for_this_cycle:
            logger.info(f"Dialog state is '{state.dialog_state}' but no user_input. Awaiting next cycle with input.")
            if state.dialog_state == "initial" and not state.messages: 
                 welcome_msg = active_texts.get("PROMPT_WELCOME_MESSAGE", "Hello! I am your robot flow design assistant. Please enter your flow description.")
                 add_ai_message_if_needed(welcome_msg)
                 state.clarification_question = welcome_msg 
            
            if state.dialog_state == "awaiting_user_input" and not state.clarification_question:
                logger.warning("In 'awaiting_user_input' with no current_user_input and no existing clarification_question. Setting a generic one.")
                generic_prompt_msg = active_texts.get("PROMPT_GENERAL_ASK_FOR_INPUT", "Please provide your robot flow description or the next action you\'d like to take.")
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

    if state.dialog_state == "processing_user_input":
        logger.info(f"Processing user input. Active plan basis: '{state.active_plan_basis[:200]}...'")
        
        if not state.active_plan_basis: 
            logger.warning("Reached 'processing_user_input' but active_plan_basis is empty. Reverting to awaiting_user_input.")
            add_ai_message_if_needed(active_texts.get("ERROR_EMPTY_PLAN_BASIS", "Please enter a valid flow description."))
            state.dialog_state = "awaiting_user_input"
            state.subgraph_completion_status = "needs_clarification"
            return state.dict(exclude_none=True)

        logger.info(f"Proceeding to enrich plan based on: '{state.active_plan_basis}'.")
        
        available_node_types_with_descriptions_str = "No node type information available."
        node_template_dir = state.config.get("NODE_TEMPLATE_DIR_PATH")
        if node_template_dir and os.path.isdir(node_template_dir):
            try:
                # Assuming load_node_descriptions is available from ..prompt_loader
                from ..prompt_loader import load_node_descriptions 
                from pathlib import Path

                all_block_files = sorted([
                    f for f in os.listdir(node_template_dir)
                    if os.path.isfile(os.path.join(node_template_dir, f)) and f.endswith((".xml")) 
                ])
                if all_block_files:
                    logger.info(f"Found {len(all_block_files)} block template files: {all_block_files}")
                    existing_descriptions = load_node_descriptions()
                    descriptions_for_prompt = ["Available node types, their functions, and XML templates:"]
                    
                    for block_file in all_block_files:
                        block_type = os.path.splitext(block_file)[0]
                        description_to_use = existing_descriptions.get(block_type)
                        if description_to_use is None:
                            logger.info(f"Description for block type '{block_type}' not found in existing descriptions. Using default.")
                            description_to_use = "Description for this node type is currently unavailable."
                        
                        xml_template_content = "XML template could not be loaded."
                        try:
                            template_file_path = Path(node_template_dir) / block_file
                            with open(template_file_path, 'r', encoding='utf-8') as f:
                                xml_template_content = f.read().strip()
                        except Exception as e_xml:
                            logger.error(f"Error loading XML template for {block_type} from {template_file_path}: {e_xml}")

                        descriptions_for_prompt.append(f"- Type: {block_type}")
                        descriptions_for_prompt.append(f"  Description: {description_to_use}")
                        descriptions_for_prompt.append(f"  Template:\n```xml\n{xml_template_content}\n```")
                    
                    if len(descriptions_for_prompt) > 1: 
                        available_node_types_with_descriptions_str = "\n\n".join(descriptions_for_prompt)
                    else:
                        available_node_types_with_descriptions_str = "Failed to load any node types, descriptions, or their XML templates."
                else:
                    logger.warning(f"No .xml block type files found in {node_template_dir}")
                    available_node_types_with_descriptions_str = "No XML node template files found in the configured path."
            except Exception as e:
                logger.error(f"Error loading block types or descriptions: {e}", exc_info=True)
                available_node_types_with_descriptions_str = f"Error loading node type information: {e}"
        else:
            logger.warning(f"NODE_TEMPLATE_DIR_PATH '{node_template_dir}' is not configured or not a directory.")
            available_node_types_with_descriptions_str = "Node template directory is not correctly configured."

        enrich_prompt_name = "flow_step0_enrich_input.md"
        enrich_placeholders = {
            "user_core_request": state.active_plan_basis,
            "AVAILABLE_NODE_TYPES_WITH_DESCRIPTIONS": available_node_types_with_descriptions_str,
            "robot_model": state.robot_model or "not specified" # Ensure robot_model is present
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
                add_ai_message_if_needed(active_texts.get("INFO_ENRICHMENT_FAILED_USING_RAW", "Sorry, I encountered an initial issue understanding and optimizing your flow description. We will proceed with confirmation based on your original input."))
                state.proposed_enriched_text = state.active_plan_basis
            else:
                logger.info("Successfully enriched the plan with LLM.")
                state.proposed_enriched_text = enriched_result["text_output"].strip()
        
        logger.info(f"Proposing enriched plan for confirmation: {state.proposed_enriched_text}")
        current_raw_request_for_prompt = state.raw_user_request if state.raw_user_request else state.active_plan_basis
        
        prompt_template = active_texts["PROMPT_CONFIRM_INITIAL_ENRICHED_PLAN_TEMPLATE"]
        
        # Check if robot_model placeholder is in the template before formatting
        # This specific prompt expects {robot_model}
        if "{robot_model}" in prompt_template:
             state.clarification_question = prompt_template.format(
                robot_model=str(state.robot_model or "unknown"), # Ensure robot_model is available
                current_raw_user_request=str(current_raw_request_for_prompt), 
                enriched_text_proposal=str(state.proposed_enriched_text)
            )
        else: # Fallback if the template was changed and no longer includes {robot_model}
            state.clarification_question = prompt_template.replace("{current_raw_user_request}", str(current_raw_request_for_prompt)).replace("{enriched_text_proposal}", str(state.proposed_enriched_text))


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