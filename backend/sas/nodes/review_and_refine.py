import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from ..state import RobotFlowAgentState, TaskDefinition

logger = logging.getLogger(__name__)

# Helper to load task type descriptions
def _load_all_task_type_descriptions(base_path: str) -> str:
    logger.info(f"Loading all task type descriptions from: {base_path}")
    descriptions = []
    try:
        task_list_path = Path(base_path)
        if task_list_path.is_dir():
            for md_file in task_list_path.glob("*.md"):
                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        descriptions.append(f.read())
                    logger.debug(f"Loaded task type description: {md_file.name}")
                except Exception as e:
                    logger.error(f"Error reading task type description file {md_file}: {e}")
        else:
            logger.warning(f"Task type descriptions path is not a directory: {base_path}")
    except Exception as e:
        logger.error(f"Error accessing task type descriptions path {base_path}: {e}")
        return "Error: Could not load task type descriptions."
    
    if not descriptions:
        logger.warning(f"No task type descriptions found in {base_path}. Prompt will be incomplete.")
        return "Warning: Task type descriptions are missing."
        
    return "\n\n---\n\n".join(descriptions)


async def review_and_refine_node(state: RobotFlowAgentState, llm: BaseChatModel) -> Dict[str, Any]:
    logger.info(f"--- SAS: Review and Refine Node (Iteration {state.revision_iteration}) ---")
    logger.info(f"    Initial dialog_state: '{state.dialog_state}'")
    logger.info(f"    task_list_accepted: {state.task_list_accepted}")
    logger.info(f"    module_steps_accepted: {state.module_steps_accepted}")
    logger.info(f"    RECEIVED user_input at START: '{state.user_input}'")

    state.current_step_description = f"SAS: Awaiting user review (Iter: {state.revision_iteration}) or processing feedback."
    state.is_error = False
    # state.error_message = None # Keep existing error message if any

    # --- This initial determination of reviewing_task_list/steps is primarily for when user_input IS PRESENT ---
    # --- to know what their feedback pertains to. ---
    # --- When user_input IS NONE, we will re-evaluate directly below. ---
    reviewing_task_list_for_feedback_context = False
    reviewing_module_steps_for_feedback_context = False

    if state.user_input is not None: # System is processing user_input, determine context of feedback
        if state.dialog_state == "sas_awaiting_task_list_review" or (not state.task_list_accepted):
            reviewing_task_list_for_feedback_context = True
        elif state.dialog_state == "sas_awaiting_module_steps_review" or (state.task_list_accepted and not state.module_steps_accepted):
            reviewing_module_steps_for_feedback_context = True
        elif state.dialog_state == "sas_awaiting_xml_generation_approval":
            # 用户在XML生成确认阶段提供了输入
            logger.info("User provided input during XML generation approval phase")
    
    logger.info(f"    Context for feedback (if user_input present) - Reviewing task list: {reviewing_task_list_for_feedback_context}")
    logger.info(f"    Context for feedback (if user_input present) - Reviewing module steps: {reviewing_module_steps_for_feedback_context}")

    # --- OTHERWISE: NO USER_INPUT for this cycle. Present a question to the user. ---
    if state.user_input is None:
        logger.info("No user_input. Determining what to present to the user for review.")
        
        question_for_user = None
        dialog_state_if_awaiting_input = None

        if not state.task_list_accepted and not state.module_steps_accepted:
            logger.info("Presenting for review: TASK LIST (since task_list_accepted is False).")
            if state.sas_step1_generated_tasks:
                # 原有逻辑：等待用户确认
                tasks_simple = []
                for task in state.sas_step1_generated_tasks:
                    tasks_simple.append({"name": task.name, "type": task.type, "description": task.description})
                try:
                    current_data_for_review_json_str = json.dumps(tasks_simple, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Error serializing tasks: {e}")
                    current_data_for_review_json_str = "[Error serializing tasks]"
                question_for_user = f"""These are the tasks generated based on your description (iteration {state.revision_iteration}):\\n\\n```json\\n{current_data_for_review_json_str}\\n```\\n\\nDo you accept these tasks? You can say "accept" or "agree", or provide your modification instructions."""
                dialog_state_if_awaiting_input = "sas_awaiting_task_list_review"
            else:
                logger.warning("Attempting to review task list, but no sas_step1_generated_tasks found.")
                state.clarification_question = "No tasks generated. This might be an issue. Please check if the task generation step completed successfully."

        elif state.task_list_accepted and not state.module_steps_accepted:
            logger.info("Presenting for review: MODULE STEPS (since task_list_accepted is True and module_steps_accepted is False).")
            if state.sas_step1_generated_tasks and any(getattr(task, 'details', None) for task in state.sas_step1_generated_tasks): # Ensure details (module steps) exist
                # 原有逻辑：等待用户确认
                tasks_with_details = []
                for task in state.sas_step1_generated_tasks:
                    tasks_with_details.append({
                        "name": task.name,
                        "type": task.type,
                        "description": task.description,
                        "details": task.details if task.details else ["No module steps generated for this task."]
                    })
                try:
                    current_data_for_review_json_str = json.dumps(tasks_with_details, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Error serializing module steps: {e}")
                    current_data_for_review_json_str = "[Error serializing module steps]"
                question_for_user = f"""These are the module steps generated for each task (iteration {state.revision_iteration}):\\n\\n```json\\n{current_data_for_review_json_str}\\n```\\n\\nDo you accept these module steps? If you need to make changes, please let me know your opinion. You can directly say "accept" or "agree", or provide your modification instructions for specific tasks or steps."""
                dialog_state_if_awaiting_input = "sas_awaiting_module_steps_review"
            else:
                logger.warning("Attempting to review module steps, but no tasks with details (module steps) found or no tasks at all. This might be an issue if module steps were expected.")
                state.clarification_question = "Module steps generation might have resulted in no steps or an issue. Proceeding with caution. If you expected module steps, please indicate a problem with the previous step."

        elif state.task_list_accepted and state.module_steps_accepted and state.dialog_state != "sas_awaiting_xml_generation_approval":
            logger.info("Both task list and module steps are already accepted. Proceeding to XML generation approval.")
            state.clarification_question = None
            state.user_advice = None
            state.dialog_state = "sas_awaiting_xml_generation_approval"
            # 设置确认问题
            approval_question = """All tasks and module steps have been confirmed. Ready to generate XML files.

**Summary:**
- Generated Tasks: {} tasks
- Module Steps: Completed and approved
- Next Step: Generate XML program files

**Do you want to proceed with XML generation?**

You can respond with:
- "approve" or "yes" to start XML generation
- "reset" to restart the task configuration
- Provide specific feedback for modifications

Please confirm to proceed with XML generation.""".format(len(state.sas_step1_generated_tasks) if state.sas_step1_generated_tasks else 0)
            
            state.clarification_question = approval_question
            if not state.messages or state.messages[-1].content != approval_question:
                state.messages = (state.messages or []) + [AIMessage(content=approval_question)]
            return state.model_dump()
            
        elif state.dialog_state == "sas_awaiting_xml_generation_approval":
            logger.info("Presenting XML generation approval confirmation.")
            if state.sas_step1_generated_tasks:
                tasks_summary = []
                for i, task in enumerate(state.sas_step1_generated_tasks):
                    tasks_summary.append(f"{i+1}. {task.name} ({task.type})")
                    if task.details:
                        tasks_summary.append(f"   - {len(task.details)} module steps defined")
                tasks_summary_str = "\\n".join(tasks_summary)
                
                approval_question = f"""Ready to generate XML program files based on the confirmed configuration:

**Tasks Overview:**
{tasks_summary_str}

**Next Action:** Generate individual XML files and merge them into a complete robot program

**Please confirm:**
- Say "approve", "yes", or "generate" to start XML generation
- Say "reset" to restart task configuration  
- Provide specific feedback for any modifications needed

Do you approve XML generation?"""
                state.clarification_question = approval_question
                if not state.messages or state.messages[-1].content != approval_question:
                    state.messages = (state.messages or []) + [AIMessage(content=approval_question)]
            else:
                logger.warning("In XML generation approval state but no tasks found.")
                state.clarification_question = "No tasks found for XML generation. Please restart the configuration."
            return state.model_dump()

        else:
            logger.error(f"Review node (presenting question): Fell into unexpected 'else' case. Dialog_state: '{state.dialog_state}', task_list_accepted: {state.task_list_accepted}, module_steps_accepted: {state.module_steps_accepted}.")
            state.is_error = True
            state.error_message = "Internal error: Review stage could not be determined when presenting question."

        # Set clarification question and dialog state
        state.clarification_question = question_for_user
        if question_for_user:
             if not state.messages or state.messages[-1].content != question_for_user:
                state.messages = (state.messages or []) + [AIMessage(content=question_for_user)]
        elif not state.is_error and not (state.task_list_accepted and state.module_steps_accepted):
            logger.error("Internal logic error: No question formed for user review, but not an error/pass-through state.")
            state.is_error = True
            state.error_message = "Internal error: Failed to prepare a review question."
            if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]

        state.dialog_state = dialog_state_if_awaiting_input
        state.user_advice = None
        logger.info(f"Paused for user input. Clarification: '{str(state.clarification_question)[:100]}...'. Dialog state set to: {state.dialog_state}")
        return state.model_dump()
    
    # --- Process user input when it's provided ---
    else:
        logger.info("Processing user feedback.")
        state.user_advice = state.user_input 
        state.user_input = None 
        
        # +++ ADDED DIAGNOSTIC LOGGING START +++
        logger.info(f"[REVIEW_NODE_INPUT] User advice received: \'{state.user_advice}\'")
        # +++ ADDED DIAGNOSTIC LOGGING END +++
        
        if not state.messages or not (isinstance(state.messages[-1], HumanMessage) and state.messages[-1].content == state.user_advice):
            state.messages = (state.messages or []) + [HumanMessage(content=state.user_advice)]

        feedback_for_processing = state.user_advice.strip()
        # +++ ADDED DIAGNOSTIC LOGGING START +++
        logger.info(f"[REVIEW_NODE_INPUT] Feedback for processing (stripped): \'{feedback_for_processing}\'")
        # +++ ADDED DIAGNOSTIC LOGGING END +++
        
        # Check for acceptance
        acceptance_keywords = ["accept", "accept_tasks", "approve", "yes", "ok", "agree", "fine", "alright", "proceed", "generate", "同意", "接受", "可以", "好的", "没问题", "行", "生成"]
        is_accepted = any(feedback_for_processing.lower() == keyword for keyword in acceptance_keywords) or \
                     any(keyword in feedback_for_processing.lower() for keyword in acceptance_keywords if len(feedback_for_processing) <= 20)
        
        # Check for reset request
        reset_keywords = ["reset", "restart", "重新开始", "重置", "重来"]
        is_reset_request = any(feedback_for_processing.lower() == keyword for keyword in reset_keywords) or \
                          any(keyword in feedback_for_processing.lower() for keyword in reset_keywords if len(feedback_for_processing) <= 20)
        
        # +++ ADDED DIAGNOSTIC LOGGING START +++
        logger.info(f"[REVIEW_NODE_ACCEPTANCE] Feedback \'{feedback_for_processing}\' - is_accepted: {is_accepted}, is_reset_request: {is_reset_request}")
        # +++ ADDED DIAGNOSTIC LOGGING END +++

        if is_accepted:
            state.clarification_question = None
            # state.user_advice = None # Keep user_advice as it was the acceptance command

            if reviewing_task_list_for_feedback_context:
                logger.info("User accepted the TASK LIST.")
                state.task_list_accepted = True
                state.dialog_state = "sas_step1_tasks_generated" # This state will route to module step generation
                # +++ ADDED DIAGNOSTIC LOGGING START +++
                logger.info(f"[REVIEW_NODE_ACCEPTANCE] TASK LIST ACCEPTED. New dialog_state: \'{state.dialog_state}\', task_list_accepted: {state.task_list_accepted}")
                # +++ ADDED DIAGNOSTIC LOGGING END +++
                if not any("Task list confirmed" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content="Task list confirmed by user. Generating detailed module steps next.")]
            elif reviewing_module_steps_for_feedback_context:
                logger.info("User accepted the MODULE STEPS.")
                state.module_steps_accepted = True
                # 修改：不直接进入XML生成，而是等待用户确认XML生成
                state.dialog_state = "sas_awaiting_xml_generation_approval" 
                # +++ ADDED DIAGNOSTIC LOGGING START +++
                logger.info(f"[REVIEW_NODE_ACCEPTANCE] MODULE STEPS ACCEPTED. New dialog_state: \'{state.dialog_state}\', module_steps_accepted: {state.module_steps_accepted}")
                # +++ ADDED DIAGNOSTIC LOGGING END +++
                if not any("Module steps confirmed" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content="Module steps confirmed by user. Ready to generate XML program with your approval.")]
            elif state.dialog_state == "sas_awaiting_xml_generation_approval":
                logger.info("User approved XML GENERATION.")
                state.dialog_state = "sas_xml_generation_approved"
                # +++ ADDED DIAGNOSTIC LOGGING START +++
                logger.info(f"[REVIEW_NODE_ACCEPTANCE] XML GENERATION APPROVED. New dialog_state: \'{state.dialog_state}\'")
                # +++ ADDED DIAGNOSTIC LOGGING END +++
                if not any("XML generation approved" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content="XML generation approved by user. Starting XML file generation process...")]
            else:
                logger.error("CRITICAL: Acceptance received but review context was undefined during processing.")
                state.is_error = True
                state.error_message = "Accepted feedback, but review context was unclear internally. Please try again or restart."
                if not any(state.error_message in m.content for m in (state.messages or []) if isinstance(m, AIMessage)):
                    state.messages = (state.messages or []) + [AIMessage(content=state.error_message)]
        elif is_reset_request:
            logger.info("User requested RESET.")
            # 重置所有状态回到初始状态
            state.task_list_accepted = False
            state.module_steps_accepted = False
            state.sas_step1_generated_tasks = None
            state.dialog_state = "initial"
            state.clarification_question = None
            state.revision_iteration = 0
            # +++ ADDED DIAGNOSTIC LOGGING START +++
            logger.info(f"[REVIEW_NODE_RESET] RESET REQUESTED. All states reset to initial.")
            # +++ ADDED DIAGNOSTIC LOGGING END +++
            if not any("Configuration reset" in msg.content for msg in (state.messages or []) if isinstance(msg, AIMessage)):
                state.messages = (state.messages or []) + [AIMessage(content="Configuration reset by user request. Please provide a new task description to start over.")]
        else:
            # User provided modifications.
            # The graph will now hang, waiting for the user to submit a revised full description via the frontend.
            # The frontend will use the original description, the generated tasks, and this feedback to help the user.
            logger.info(f"User provided feedback/modifications: '{feedback_for_processing[:200]}...'. Awaiting revised input from frontend.")
            
            current_data_for_review_json_str = ""
            if reviewing_task_list_for_feedback_context and state.sas_step1_generated_tasks:
                tasks_simple = []
                for task in state.sas_step1_generated_tasks:
                    tasks_simple.append({"name": task.name, "type": task.type, "description": task.description})
                current_data_for_review_json_str = json.dumps(tasks_simple, indent=2, ensure_ascii=False)
                state.dialog_state = "sas_awaiting_task_list_revision_input" # New state to indicate waiting for full revised input
                question_for_user = (
                    f"Original Request:\n```text\n{state.current_user_request}\n```\n\n"
                    f"Generated Tasks (Iteration {state.revision_iteration}):\n```json\n{current_data_for_review_json_str}\n```\n\n"
                    f"Your Feedback:\n```text\n{feedback_for_processing}\n```\n\n"
                    f"Please provide a **complete revised task description** in the input field. You can also choose to 'approve' the generated tasks if they are now satisfactory after considering your feedback."
                )
            elif reviewing_module_steps_for_feedback_context and state.sas_step1_generated_tasks:
                 # Similar logic for module steps if needed, for now focusing on task list
                tasks_with_details = []
                for task in state.sas_step1_generated_tasks:
                    tasks_with_details.append({
                        "name": task.name,
                        "type": task.type,
                        "description": task.description,
                        "details": task.details if task.details else ["No module steps generated for this task."]
                    })
                current_data_for_review_json_str = json.dumps(tasks_with_details, indent=2, ensure_ascii=False)
                state.dialog_state = "sas_awaiting_module_steps_revision_input" # New state
                question_for_user = (
                    f"Original Task List was accepted.\n\n"
                    f"Generated Module Steps (Iteration {state.revision_iteration}):\n```json\n{current_data_for_review_json_str}\n```\n\n"
                    f"Your Feedback:\n```text\n{feedback_for_processing}\n```\n\n"
                    f"Please provide **complete revised module steps or overall task description** as needed. You can also 'approve'."
                )
            else:
                logger.warning("Feedback received, but context for review (task list/module steps) or generated data is missing.")
                # Fallback: Treat as general feedback, ask to clarify or resubmit full description
                state.dialog_state = "sas_awaiting_task_list_review" # Revert to a general waiting state
                question_for_user = (
                    f"I have received your feedback: '{feedback_for_processing}'.\n"
                    f"However, I'm unsure about the context. Please provide a complete new task description, or clarify your previous request."
                )

            state.clarification_question = question_for_user
            state.revision_iteration += 1 # Increment iteration as feedback was given
            state.task_list_accepted = False # Still needs explicit approval later
            state.module_steps_accepted = False # Still needs explicit approval later

            # Add feedback to messages as HumanMessage, and an AI message indicating it's waiting
            if not any(feedback_for_processing in msg.content for msg in (state.messages or []) if isinstance(msg, HumanMessage)): # Avoid duplicate if already added
                 state.messages = (state.messages or []) + [HumanMessage(content=feedback_for_processing)]
            state.messages = (state.messages or []) + [AIMessage(content=f"Received your feedback for iteration {state.revision_iteration}. Please provide the revised input or approve.")]
            
            # The graph will naturally end here because dialog_state (e.g., "sas_awaiting_task_list_revision_input")
            # will be routed to END by route_after_sas_review_and_refine, with subgraph_completion_status = "needs_clarification".
            # Frontend will then get this state and allow user to submit a new full request.
            # That new full request will come in as state.user_input in the *next* invocation of the graph.
            # initialize_state_node will then set state.current_user_request = state.user_input,
            # and the flow will go to user_input_to_task_list_node for fresh generation.
            
    logger.info(f"--- SAS: Review and Refine Node PRE-RETURN ---")
    logger.info(f"    FINAL dialog_state before return: '{state.dialog_state}'")
    if state.sas_step1_generated_tasks:
        logger.info(f"    FINAL sas_step1_generated_tasks count before return: {len(state.sas_step1_generated_tasks)}")
        # Log first task name if exists for quick check
        try:
            logger.info(f"    FINAL first task name: {state.sas_step1_generated_tasks[0].name if state.sas_step1_generated_tasks else 'N/A'}")
        except Exception as e_log:
            logger.error(f"Error logging first task name: {e_log}")
    else:
        logger.info(f"    FINAL sas_step1_generated_tasks before return: IS EMPTY OR NONE")
    logger.info(f"    FINAL clarification_question before return: '{str(state.clarification_question)[:100]}...'")
    logger.info(f"    FINAL subgraph_completion_status before return: '{state.subgraph_completion_status}'") # Check if it's set or passed through

    return state.model_dump()

__all__ = [
    "review_and_refine_node"
] 