import logging
import json
import os # Ensure os is imported
import asyncio # Keep asyncio if other async functions remain or are used by imported nodes
from pathlib import Path # Keep Path if used by remaining utility functions (Removed for now)
from typing import List, Optional, Dict, Any, cast, Type, Literal
# import re # Keep re if used by remaining utility functions or for invoke_llm_for_text_output (Removed for now)

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, BaseMessage
from pydantic import BaseModel, Field, field_validator # Keep BaseModel and Field for UserFeedbackIntent
from langchain_core.output_parsers import JsonOutputParser # For parsing new task list
# Removed: import json # For serializing/deserializing task lists (already imported above)

# Import state and prompt_loader which might be used by shared functions or are essential
from .state import RobotFlowAgentState, GeneratedXmlFile, TaskDefinition # GeneratedXmlFile might be used if helper functions constructing it remain
from .prompt_loader import get_filled_prompt, load_node_descriptions, append_node_description, get_sas_step1_formatted_prompt
from ....prompts.shared_constants import USER_INTERACTION_TEXTS, KNOWN_ROBOT_MODELS # Import from shared constants

# Import nodes from the new submodule
from .nodes import (
    preprocess_and_enrich_input_node,
    understand_input_node,
    ParsedStep, # This should be imported if UserFeedbackIntent or other models here need it, otherwise it's in nodes.understand_input
    UnderstandInputSchema, # Same as ParsedStep, likely belongs with its node
    generate_individual_xmls_node,
    generate_relation_xml_node,
    user_input_to_task_list_node
    # Removed: sas_review_and_refine_task_list_node (it's now in .nodes.review_and_refine)
)

logger = logging.getLogger(__name__)

# Pydantic model for intent classification output
class UserFeedbackIntent(BaseModel):
    intent: Literal["affirm", "change_robot", "modify_plan", "unclear"] = Field(description="The classified intent of the user's feedback.")
    robot_model_suggestion: Optional[str] = Field(None, description="If intent is 'change_robot', the suggested new robot model name.")
    revision_feedback: Optional[str] = Field(None, description="If intent is 'modify_plan', the core feedback for revising the plan. If not distinct from original feedback, can be the original feedback itself.")

# --- All node functions have been moved to the .nodes submodule ---
# They are imported above and re-exported via nodes/__init__.py if needed elsewhere directly from this path, 
# but typically consumers should import from .nodes directly.

# Removed _load_all_task_type_descriptions helper function
# Removed sas_review_and_refine_task_list_node async function

# It's good practice to define __all__ if this module is intended to be a public API for some of these utilities
__all__ = [
    "USER_INTERACTION_TEXTS",
    "KNOWN_ROBOT_MODELS",
    "UserFeedbackIntent",
    # "invoke_llm_for_text_output", # Moved to llm_utils.py
    # "invoke_llm_for_json_output", # Moved to llm_utils.py
    # Re-exporting nodes - these should ideally be imported from .nodes by consumers
    "preprocess_and_enrich_input_node",
    "understand_input_node",
    "ParsedStep", # Re-exporting from nodes for now, but ideally should be in nodes.__init__ only
    "UnderstandInputSchema", # Re-exporting from nodes for now
    "generate_individual_xmls_node",
    "generate_relation_xml_node",
    "user_input_to_task_list_node",
    # Removed: "sas_review_and_refine_task_list_node", 
    # Re-exporting from state and prompt_loader if they are part of this module's public API
    "RobotFlowAgentState",
    "GeneratedXmlFile",
    "get_filled_prompt",
    "load_node_descriptions",
    "append_node_description",
    "get_sas_step1_formatted_prompt"
] 