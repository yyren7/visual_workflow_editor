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
    ),
    "ERROR_INTERNAL_NO_PLAN_TO_CONFIRM": "An internal error occurred: Awaiting enrichment confirmation, but no plan found to confirm. Please describe your flow again.",
    "PROMPT_ASK_FOR_MODIFICATION_OR_NEW_PLAN": "Okay, please tell me how you'd like to modify it, or provide a completely new flow description.",
    "PROMPT_RETRY_AFTER_GENERATION_FAILURE_TEMPLATE": "Sorry, there was a problem generating the XML last time: {error_message}. Please modify your instructions or provide a new flow description.",
    "PROMPT_WELCOME_MESSAGE": "Hello! I am your robot flow design assistant. Please enter your flow description.",
    "PROMPT_GENERAL_ASK_FOR_INPUT": "Please provide your robot flow description or the next action you'd like to take.",
    "ERROR_EMPTY_PLAN_BASIS": "Please enter a valid flow description.",
    "INFO_ENRICHMENT_FAILED_USING_RAW": "Sorry, I encountered an initial issue understanding and optimizing your flow description. We will proceed with confirmation based on your original input."
}

KNOWN_ROBOT_MODELS = ["dobot_mg400", "fairino_FR", "hitbot_Z_ARM", "iai_3axis_tabletop", "robodk"] 