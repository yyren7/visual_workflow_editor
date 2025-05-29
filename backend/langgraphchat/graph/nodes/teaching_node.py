import logging
import yaml
import json
import re
from typing import Dict, Any, List, Optional, Union, Tuple

from ..agent_state import AgentState
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

TEACHING_POINTS_FILE = "backend/langgraphchat/synced_files/teaching.yaml"

# --- Helper Data Structures ---
POINT_FIELD_SCHEMA: Dict[str, Dict[str, Any]] = {
    "name": {"type": str, "default": None},
    "x_pos": {"type": float, "default": 0.0},
    "y_pos": {"type": float, "default": 0.0},
    "z_pos": {"type": float, "default": 0.0},
    "rx_pos": {"type": float, "default": 0.0},
    "ry_pos": {"type": float, "default": 0.0},
    "rz_pos": {"type": float, "default": 0.0},
    "vel": {"type": float, "default": 100.0},
    "acc": {"type": float, "default": 100.0},
    "dec": {"type": float, "default": 100.0},
    "dist": {"type": float, "default": 0.1},
    "stime": {"type": float, "default": 0.0},
    "tool": {"type": (float, int, type(None)), "default": 0.0}
}

# --- Helper Functions (File I/O and Data Manipulation) ---
def _load_teaching_points() -> Dict[str, Dict[str, Any]]:
    """Loads teaching points from the YAML file."""
    try:
        with open(TEACHING_POINTS_FILE, 'r', encoding='utf-8') as f:
            points = yaml.safe_load(f)
            if points is None: return {}
            valid_points = {}
            for key, value in points.items():
                if isinstance(value, dict):
                    valid_points[key] = value
                else:
                    logger.warning(f"Invalid data for point '{key}' in {TEACHING_POINTS_FILE}, expected dict, got {type(value)}. Skipping.")
            return valid_points
    except FileNotFoundError:
        logger.info(f"Teaching points file not found: {TEACHING_POINTS_FILE}. Returning empty dict.")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {TEACHING_POINTS_FILE}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading teaching points: {e}")
        return {}

def _save_teaching_points(points: Dict[str, Dict[str, Any]]) -> bool:
    """Saves teaching points to the YAML file."""
    try:
        with open(TEACHING_POINTS_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(points, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        logger.info(f"Teaching points saved to {TEACHING_POINTS_FILE}")
        return True
    except IOError as e:
        logger.error(f"Error writing to YAML file {TEACHING_POINTS_FILE}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving teaching points: {e}")
        return False

def _find_points_by_identifiers(points_data: Dict[str, Dict[str, Any]], identifiers_from_llm: List[str]) -> List[Dict[str, Any]]:
    """Finds multiple points by P_N slot key, exact logical name, or fuzzy logical name match.
       Returns a list of dictionaries, each containing point data and match info.
    """
    found_points_results = []
    added_p_keys = set()

    for original_id in identifiers_from_llm:
        match_info = {"original_identifier": original_id, "matched_by": None, "matched_identifier": None, "data": None}
        found_this_id = False

        if original_id in points_data and original_id not in added_p_keys:
            match_info["data"] = points_data[original_id].copy()
            match_info["data"]["_id"] = original_id
            match_info["matched_by"] = "exact_pkey"
            match_info["matched_identifier"] = original_id
            found_points_results.append(match_info)
            added_p_keys.add(original_id)
            found_this_id = True
            continue

        for p_key, p_data in points_data.items():
            if p_key in added_p_keys: continue
            if p_data.get("name") == original_id:
                match_info["data"] = p_data.copy()
                match_info["data"]["_id"] = p_key
                match_info["matched_by"] = "exact_logical_name"
                match_info["matched_identifier"] = original_id
                found_points_results.append(match_info)
                added_p_keys.add(p_key)
                found_this_id = True
                break
        if found_this_id: continue

        if not found_this_id:
            found_points_results.append(match_info)
            
    return found_points_results

def _find_slot_by_identifier(points_data: Dict[str, Dict[str, Any]], identifier_from_llm: str) -> Tuple[Optional[str], str, str]:
    """Finds a P_N slot key by P_N id, exact logical name, or fuzzy logical name.
       Returns (p_key_found, type_of_match, identifier_actually_used_for_match).
       Match types: 'exact_pkey', 'exact_logical_name', 'fuzzy_logical_name', 'none'.
    """
    if identifier_from_llm in points_data:
        return identifier_from_llm, "exact_pkey", identifier_from_llm
    
    for p_key, p_data in points_data.items():
        if p_data.get("name") == identifier_from_llm:
            return p_key, "exact_logical_name", identifier_from_llm
            
    return None, "none", identifier_from_llm

def _find_empty_slot_key(points: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Finds the key of the first empty teaching point slot."""
    for i in range(1, 101):
        key = f"P{i}"
        if key not in points:
            return key
        point_data = points[key]
        if not point_data.get("name"):
            is_truly_empty = True
            for field, spec in POINT_FIELD_SCHEMA.items():
                if field == "name": continue
                if point_data.get(field) != spec["default"] and point_data.get(field) is not None:
                    is_truly_empty = False
                    break
            if is_truly_empty:
                return key
    return None

def _apply_schema_and_defaults_to_llm_params(
    llm_params: Dict[str, Any], 
    existing_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    validated_data = existing_data.copy() if existing_data else {}
    if not existing_data:
        for field_key, spec in POINT_FIELD_SCHEMA.items():
            validated_data[field_key] = spec["default"]

    for field_key, spec in POINT_FIELD_SCHEMA.items():
        raw_value = llm_params.get(field_key)
        if raw_value is not None:
            expected_type = spec["type"]
            try:
                if field_key == "tool" and isinstance(raw_value, str) and raw_value.lower() == "null":
                    validated_data[field_key] = None
                elif expected_type is str:
                    validated_data[field_key] = str(raw_value)
                elif expected_type is float:
                    validated_data[field_key] = float(raw_value)
                elif expected_type is int:
                    validated_data[field_key] = int(raw_value)
                elif isinstance(expected_type, tuple):
                    if isinstance(raw_value, str) and raw_value.lower() == "null" and type(None) in expected_type:
                        validated_data[field_key] = None
                    else: 
                        converted = False
                        type_checks = []
                        if float in expected_type: type_checks.append((float, float))
                        if int in expected_type: type_checks.append((int, int))
                        
                        for type_to_check, type_constructor in type_checks:
                            try: validated_data[field_key] = type_constructor(raw_value); converted = True; break
                            except (ValueError, TypeError): pass   
                                             
                        if not converted and type(None) in expected_type and raw_value is None: 
                            validated_data[field_key] = None; converted = True
                        if not converted:
                            if any(isinstance(raw_value, t) for t in expected_type if t is not type(None)):
                                validated_data[field_key] = raw_value
                            else:
                                raise ValueError(f"Cannot convert LLM value '{raw_value}' of type {type(raw_value)} to any of types {expected_type}")
                else:
                    validated_data[field_key] = raw_value 
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not convert LLM value '{raw_value}' for field '{field_key}' to {expected_type}: {e}. Using default: {spec['default']}.")
                validated_data[field_key] = spec["default"]
        elif existing_data and field_key in existing_data:
            validated_data[field_key] = existing_data[field_key]
        elif field_key not in validated_data :
             validated_data[field_key] = spec["default"]

    logger.info(f"Data after applying schema to LLM params: {validated_data}")
    return validated_data

# --- LLM Prompting ---
def _get_llm_prompt_for_teaching(user_input: str, points_data: Dict[str, Dict[str, Any]], messages: List[BaseMessage]) -> List[BaseMessage]:
    schema_description_parts = ["Point fields and their expected types/defaults:"]
    for name, details in POINT_FIELD_SCHEMA.items():
        type_str = getattr(details['type'], '__name__', str(details['type']))
        default_val = details['default']
        schema_description_parts.append(f"  - {name}: type is {type_str}, default is '{default_val}' (use null for 'tool' if it's truly null/none).")
    schema_str = "\n".join(schema_description_parts)

    existing_points_summary = ["Current defined teaching points:"]
    if points_data:
        sorted_p_keys = sorted(points_data.keys(), key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf'))
        for p_key in sorted_p_keys:
            p_data = points_data[p_key]
            name = p_data.get("name")
            is_defined = False
            if name: 
                is_defined = True
            else:
                for field, spec in POINT_FIELD_SCHEMA.items():
                    if field != "name" and p_data.get(field) != spec["default"] and p_data.get(field) is not None:
                        is_defined = True; break
            if is_defined:
                 existing_points_summary.append(f"  - {p_key} (Logical Name: {name if name else '(No logical name, but has data)'})")

    else:
        existing_points_summary.append("  (No teaching points defined yet)")
    existing_points_str = "\n".join(existing_points_summary)

    VALID_INTENTS_LIST = [
        "save_update_point", 
        "delete_point", 
        "query_points",
        "list_points", 
        "clarify_ambiguous_instruction"
    ]
    valid_intents_str = ", ".join([f'"{i}"' for i in VALID_INTENTS_LIST])

    ai_response_history_str = "(No recent AI responses)"
    user_request_history_str = "(No recent user requests)"
    
    if messages:
        recent_ai_messages = []
        recent_user_messages = []
        recent_messages = messages[-6:]
        
        for msg in reversed(recent_messages):
            if isinstance(msg, AIMessage) and len(recent_ai_messages) < 2:
                recent_ai_messages.append(msg.content.strip())
            elif isinstance(msg, HumanMessage) and len(recent_user_messages) < 2:
                recent_user_messages.append(msg.content.strip())
        
        if recent_ai_messages:
            ai_response_history_str = "\n".join([
                f"AI Response {i+1}: {msg[:200]}..." if len(msg) > 200 else f"AI Response {i+1}: {msg}"
                for i, msg in enumerate(recent_ai_messages)
            ])
        if recent_user_messages:
            user_request_history_str = "\n".join([
                f"User Request {i+1}: {msg[:200]}..." if len(msg) > 200 else f"User Request {i+1}: {msg}"
                for i, msg in enumerate(recent_user_messages)
            ])

    new_system_prompt_template = f"""
You are a professional robot teaching point management assistant.
Your task is to analyze the [User's Latest Input], combine it with [Recent Conversation History] to understand the user's intent, and then output a structured JSON object. You must reply in English.

[JSON Output Structure]
You must output a JSON object that conforms to the following description:
- intent: (String) The user's core intent. Must be chosen from the following list: [{valid_intents_str}].
- user_provided_target_identifier: (String or Null) The point identifier (P_Key or logical name) explicitly specified in the user's input. Null if not explicitly specified.
- resolved_target_p_key: (String or Null) If `user_provided_target_identifier` or context can clearly resolve to a P_Key of a defined point, this is the P_Key (e.g., "P1"); otherwise null.
- resolution_details: (String) Detailed explanation of how you resolved (or why you couldn't resolve) `user_provided_target_identifier` to `resolved_target_p_key`. Include context information you considered.
- parameters: (Object or Null) Contains parameters required for the operation.
    - For `save_update_point`, it may contain fields like `name`, `x_pos`, etc., and their values.
    - For `query_points`, it can contain a `query_scope` field, whose value can be:
        - "specific": When the user queries one or more [specific] points. In this case, `user_provided_target_identifier` (single) or `target_identifiers_for_multi_point_ops` (multiple) should be filled.
        - "all_named": When the user wants to query [all teaching points with logical names].
        - "all": When the user wants to query [all defined teaching points] (with or without names).
    - For `list_points`, it can contain a `list_options` object, e.g., {{"scope": "all_named", "include_details": true}}.
        - `scope` can be "all", "all_named".
        - `include_details` (boolean, optional): Whether to include detailed coordinates in the reply.
- target_identifiers_for_multi_point_ops: (List of Strings or Null) Only for `query_points` (when `query_scope` is "specific" and multiple specific points need to be queried) or `delete_point` (when batch deletion is needed), a list of multiple point identifiers specified by the user.

[Intent Selection Rules and Guidance]
1.  **`save_update_point`**: Create or modify a point.
    *   **Creating a new point**: A logical name (`name` parameter) is required for the point being created.
        *   If the user explicitly provides a `name` in their instruction, use that name.
        *   If the user does *not* explicitly provide a `name` when their instruction implies creating a new point (e.g., "copy point X to the first empty slot", "save point with data X,Y,Z at P_N", or even "copy point X to P_N with a new name" but they forget to specify the actual name), you MUST automatically generate a descriptive and unique logical name for this new point. For example, if copying 'Point_A', a good auto-generated name could be 'Point_A_copy' or 'New_Point_From_A'.
        *   Ensure any user-provided or auto-generated name for a new point is unique. If it clashes with an existing point's name, and the user provided the name, change intent to `clarify_ambiguous_instruction` to report the conflict. If your auto-generated name clashes (which should be avoided by checking existing names), try generating a different unique name.
    *   **Updating an existing, unnamed point by assigning coordinates**: If the user's instruction is to update a point that currently has no logical name (e.g., P5 is unnamed) by setting or changing its coordinate data (x_pos, y_pos, etc.), the user MUST provide a logical name for this point as part of the update. If they don't, you should set the `intent` to `clarify_ambiguous_instruction` and ask the user to provide a name.
    *   **Updating an existing, named point**:
        *   If the user provides a `name` parameter that is different from the point's current name, this implies a rename.
        *   If no `name` parameter is provided by the user for an existing named point, its current name is retained.
    *   **General Uniqueness for Names**: If a user-provided `name` for any save/update operation (new point, renaming an existing point) would result in a duplicate logical name (i.e., another *different* existing point already has that name), you must set `intent` to `clarify_ambiguous_instruction` to report the conflict and ask for a different name. Your auto-generated names must also be unique.
2.  **`delete_point`**: Delete a point.
3.  **`query_points`**: Query [detailed information] of specific points, all points, or all named points. The LLM should decide `query_scope`.
4.  **`list_points`**: List [summary information] of points (usually P_Key and logical name). The LLM should set `scope` (e.g., "all", "all_named") and optional `include_details` in `parameters.list_options`.
5.  **`clarify_ambiguous_instruction`**: When the instruction is unclear or the target point cannot be safely resolved.

[Important: Coreference Resolution, Fuzzy Matching, and Ambiguity Handling]
(Content same as before, emphasizing that for save_update (update) and delete, if an exact match cannot be found, it must be converted to clarify_ambiguous_instruction)
- **For intents `save_update_point` (when updating an existing robot teaching point, not creating a new one with a new name) and `delete_point`, a non-null `resolved_target_p_key` must be provided in the JSON. If you cannot resolve the target point for these intents (i.e., cannot find an exact match), you must set `intent` to `clarify_ambiguous_instruction`.**

**Reliance on Provided Point Data**: When you need to know the current state of teaching points (e.g., for resolving identifiers, checking for empty slots, checking for name conflicts, listing points), you MUST rely *exclusively* on the data provided in the `[Existing Teaching Points Reference]:` section below. Do not attempt to infer, recall, or derive the state of teaching points from any other source, including previous conversational turns or other parts of this prompt, if the `[Existing Teaching Points Reference]:` section is populated.
[Existing Teaching Points Reference]:
Note on empty/available slots: For your understanding and when determining where to save a new point if the user doesn't specify a P_N key, consider any slot with a missing or empty 'name' field as 'available' or 'empty'. If such a slot already contains some coordinate data, saving a new point to it will overwrite that data. The system prioritizes truly empty slots (all default values) when automatically assigning a slot, but your primary guide for availability based on 'name' is as stated.
{existing_points_str}

[Point Data Field Definitions (for `parameters` object)]:
{schema_str}

[Recent Conversation History]:
AI: {ai_response_history_str}
User: {user_request_history_str}

[User's Latest Input]:
{user_input}

Please generate your JSON output based on all the above information. Ensure your final user-facing response is in English.
"""
    llm_messages: List[BaseMessage] = [SystemMessage(content=new_system_prompt_template)]
    if messages:
        history_to_include = messages[-4:]
        llm_messages.extend(history_to_include)
    llm_messages.append(HumanMessage(content=user_input))
    return llm_messages

async def _invoke_llm_for_intent(llm: BaseChatModel, user_input: str, points_data: Dict[str, Dict[str, Any]], messages: List[BaseMessage]) -> Dict[str, Any]:
    prompt_messages = _get_llm_prompt_for_teaching(user_input, points_data, messages)
    json_str_to_parse = ""
    original_llm_content = ""
    try:
        response = await llm.ainvoke(prompt_messages)
        original_llm_content = response.content
        logger.info(f"LLM raw response content for teaching intent: {original_llm_content}")

        json_markdown_match = re.search(r"```json\s*(\{.*?\})\s*```", original_llm_content, re.DOTALL | re.IGNORECASE)
        if json_markdown_match:
            json_str_to_parse = json_markdown_match.group(1).strip()
        else:
            first_brace = original_llm_content.find('{')
            last_brace = original_llm_content.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                potential_json = original_llm_content[first_brace : last_brace + 1]
                if potential_json.startswith('{') and potential_json.endswith('}'):
                    json_str_to_parse = potential_json.strip()
                else:
                    json_str_to_parse = original_llm_content 
            else:
                json_str_to_parse = original_llm_content
        
        if not json_str_to_parse:
            logger.error(f"Could not extract any parsable JSON string from LLM output. Raw content: {original_llm_content}")
            return {"intent": "unclear_intent", "reason": f"LLM output did not contain a recognizable JSON structure. Raw output: {original_llm_content}"}

        parsed_json = json.loads(json_str_to_parse)
        return parsed_json
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extracted JSON string. Error: {e}. String attempted to parse: '{json_str_to_parse}'. Original LLM content: '{original_llm_content}'")
        return {"intent": "unclear_intent", "reason": f"LLM output was not valid JSON despite extraction attempts. Extracted part: '{json_str_to_parse}'. Raw output: '{original_llm_content}'"}
    except Exception as e:
        logger.error(f"Error invoking LLM for teaching intent or parsing JSON: {e}. Raw content: '{original_llm_content}'")
        return {"error": str(e), "intent": "error_parsing_llm_response", "raw_content": original_llm_content}

async def _invoke_llm_for_polishing(
    llm: BaseChatModel,
    original_user_query: str,
    step_a_analysis: str,
    intermediate_results_text: str,
    generated_json_data_for_potential_inclusion: str,
    intent: str,
    logger_object: logging.Logger
) -> str:
    """
    Invokes an LLM to polish the raw intermediate results into a natural, user-facing response.
    The LLM also decides whether to include the provided JSON data based on the context and intent.
    """
    is_json_available = bool(
        generated_json_data_for_potential_inclusion and
        generated_json_data_for_potential_inclusion.strip() and
        generated_json_data_for_potential_inclusion.strip() != '""'
    )
    logger_object.info(
        f"Polishing: Intent='{intent}', Original Query='{original_user_query[:100]}...', "
        f"JSON available for potential inclusion: {is_json_available}"
    )

    prompt_parts = [
        f"Original user query:\n{original_user_query}\n",
        f"Your initial analysis and decision (from first-stage LLM output - JSON format):\n{step_a_analysis}\n",
        f"Based on the above analysis and your internal processing, the preliminary text result is as follows:\n{intermediate_results_text}\n"
    ]

    json_data_to_consider_str = ""
    json_was_valid_and_available = False

    if is_json_available:
        try:
            # Validate that it's proper JSON before presenting to LLM as such
            json.loads(generated_json_data_for_potential_inclusion)
            json_data_to_consider_str = generated_json_data_for_potential_inclusion
            json_was_valid_and_available = True
            prompt_parts.append(
                f"The following is detailed JSON data generated by your internal processing. You will decide whether to include it in the final user-facing response:\n"
                f"```json\n{json_data_to_consider_str}\n```\n"
            )
        except json.JSONDecodeError:
            logger_object.warning(
                f"Polishing - provided generated_json_data was not valid JSON. "
                f"Not including in prompt for LLM decision. Data: {generated_json_data_for_potential_inclusion[:100]}..."
            )
            prompt_parts.append("Note: Some data was generated during initial processing, but its format is not standard JSON, so its detailed content for your consideration of inclusion is not provided here.\n")
    else:
        prompt_parts.append("Note: No additional detailed JSON data was generated during initial processing for you to consider including.\n")

    instruction_clauses = [
        "1. Your primary response should be in natural language, friendly, concise, and directly answer the original user query. Respond in English."
    ]
    if json_was_valid_and_available:
        instruction_clauses.extend([
            "2. Regarding whether to append the detailed JSON data mentioned above after your natural language response:",
            f"    *   The intent of the current operation is '{intent}'.",
            f"    *   **If the intent is to list multiple items (e.g., intent is `list_points`, or `query_points` and the query scope is `all` or `all_named`), and you judge that this detailed JSON data might be too verbose for a typical user, or your natural language summary is already clear enough, then please DO NOT include that detailed JSON data in your response.**",
            f"    *   In other cases (e.g., querying a single specific item where JSON data is concise, or the user might need to copy-paste this data, or the intent is not bulk listing), you may include the detailed JSON data after the natural language response, using standard markdown JSON code blocks (```json ... ```).",
            f"    *   If you decide to include the JSON, ensure it is accurately copied from the JSON data provided to you above and correctly wrapped in ```json ... ```."
        ])
    else:
        instruction_clauses.append("2. Since no valid or relevant detailed JSON data was provided, your response should only contain the natural language part. Respond in English.")
    
    instruction_clauses.append("\nPlease directly output the complete final response for the user. Do not add any extra explanations or conversational markers unless they are part of your final response. Ensure the final response is in English.")

    instruction_text = "\nTask:\n" + "\n".join(instruction_clauses) # Ensure newlines are correctly formatted for the final prompt string
    prompt_parts.append(instruction_text)
    
    final_prompt_for_llm = "\n".join(prompt_parts)
    logger_object.debug(f"Polishing - Final prompt for LLM:\n{final_prompt_for_llm}") # Changed to debug level for potentially long prompts

    try:
        messages_for_llm = [HumanMessage(content=final_prompt_for_llm)]
        llm_response = await llm.ainvoke(messages_for_llm)
        polished_response = llm_response.content.strip()
        logger_object.info(f"Polishing - LLM generated response: {polished_response[:300]}...")
        return polished_response
    except Exception as e:
        logger_object.error(f"Error invoking LLM for polishing: {e}")
        # Fallback to a simpler response if polishing LLM fails
        return f"There was a problem processing your request. The preliminary result is:\n{intermediate_results_text}"


# --- Main Node Logic ---
async def teaching_node(state: AgentState, llm: BaseChatModel, **kwargs) -> Dict[str, Any]:
    messages: List[BaseMessage] = state.get("messages", [])
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {"messages": [AIMessage(content="Cannot process teaching point operation: No valid user instruction.", additional_kwargs={"node": "teaching"})]}

    user_input_content = messages[-1].content.strip()
    logger.info(f"Teaching Node: Received input '{user_input_content[:200]}...'")

    all_points_data = _load_teaching_points()
    response_parts = [] 
    final_data_for_json_output = []
    operation_succeeded_for_json_check = False 

    llm_analysis = await _invoke_llm_for_intent(llm, user_input_content, all_points_data, messages)
    intent = llm_analysis.get("intent")
    resolution_details = llm_analysis.get("resolution_details", "No details provided by LLM.")
    logger.info(f"LLM intent: {intent}, analysis: {llm_analysis}")

    current_turn_aimessage_kwargs = {"node": "teaching"}

    if intent == "clarify_ambiguous_instruction":
        logger.info(f"Teaching Node: LLM requested clarification. Details: {resolution_details}")
        clarification_message = resolution_details if resolution_details and len(resolution_details) > 10 else f"Sorry, I didn't quite understand that. {resolution_details} Could you be more specific?"
        return {"messages": [AIMessage(content=clarification_message, additional_kwargs=current_turn_aimessage_kwargs)]}

    if intent == "query_points":
        queried_points_info = []
        any_point_found_successfully = False
        llm_params = llm_analysis.get("parameters", {})
        query_scope = llm_params.get("query_scope")
        multi_point_ids_llm = llm_analysis.get("target_identifiers_for_multi_point_ops")
        user_provided_id = llm_analysis.get("user_provided_target_identifier")
        
        if query_scope == "all_named":
            logger.info("Processing 'query_points' with scope 'all_named'.")
            named_points = []
            for p_key_iter in sorted(all_points_data.keys(), key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')):
                p_data_item = all_points_data[p_key_iter]
                if p_data_item.get('name'):
                    point_with_id = p_data_item.copy(); point_with_id["_id"] = p_key_iter
                    named_points.append(point_with_id)
                    any_point_found_successfully = True
            if named_points:
                response_parts.append(f"Found {len(named_points)} teaching points with logical names:")
                for point in named_points:
                    response_parts.append(f"  - {point['_id']}: {point.get('name', '')}")
                final_data_for_json_output.extend(named_points)
                response_parts.append(f"\nDetails of the queried points:\n{json.dumps(final_data_for_json_output, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("No teaching points with logical names found.")

        elif query_scope == "all":
            logger.info("Processing 'query_points' with scope 'all'.")
            all_defined_points_list = []
            for p_key_iter in sorted(all_points_data.keys(), key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')):
                p_data_item = all_points_data[p_key_iter]
                is_defined = False
                if p_data_item.get("name"): is_defined = True
                else:
                    for field, spec in POINT_FIELD_SCHEMA.items():
                        if field != "name" and p_data_item.get(field) != spec["default"] and p_data_item.get(field) is not None:
                            is_defined = True; break
                if is_defined:
                    point_with_id = p_data_item.copy(); point_with_id["_id"] = p_key_iter
                    all_defined_points_list.append(point_with_id)
                    any_point_found_successfully = True
            if all_defined_points_list:
                response_parts.append(f"Found {len(all_defined_points_list)} defined teaching points:")
                for point in all_defined_points_list:
                    response_parts.append(f"  - {point['_id']}: {point.get('name', '(No logical name)')}")
                final_data_for_json_output.extend(all_defined_points_list)
                response_parts.append(f"\nDetails of the queried points:\n{json.dumps(final_data_for_json_output, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("No defined teaching points found.")

        elif query_scope == "specific" or (not query_scope and (isinstance(multi_point_ids_llm, list) and multi_point_ids_llm or user_provided_id)):
            logger.info(f"Processing 'query_points' with scope 'specific' (or inferred). IDs: {multi_point_ids_llm or user_provided_id}")
            identifiers_to_query = []
            if isinstance(multi_point_ids_llm, list) and multi_point_ids_llm: identifiers_to_query.extend(multi_point_ids_llm)
            elif user_provided_id: identifiers_to_query.append(user_provided_id)
            
            current_query_results = []
            if identifiers_to_query:
                found_points_results_list = _find_points_by_identifiers(all_points_data, identifiers_to_query)
                for found_item in found_points_results_list:
                    uid = found_item["original_identifier"]
                    point_data = found_item["data"]
                    if point_data:
                        queried_points_info.append(f"Query for '{uid}': Successful. Matched by: {found_item.get('matched_by')} ('{found_item.get('matched_identifier')}'), Slot: {point_data.get('_id')}")
                        current_query_results.append(point_data) 
                        any_point_found_successfully = True
                    else:
                        queried_points_info.append(f"Query for '{uid}': Failed. No matching point found. (Resolution details: {found_item.get('resolution_details', resolution_details)})")
                
                if queried_points_info:
                    response_parts.extend(queried_points_info)
                if current_query_results:
                    final_data_for_json_output.extend(current_query_results)
                    response_parts.append(f"\nDetails of the queried points:\n{json.dumps(final_data_for_json_output, ensure_ascii=False, indent=2)}")
                elif not response_parts:
                    response_parts.append("Could not find any points based on the provided identifiers.")
            else:
                response_parts.append("LLM failed to identify the point(s) to query. Please specify clearly.")

        else:
            response_parts.append(f"Received query request, but the query scope '{query_scope}' is unclear or parameters are insufficient.")
            logger.warning(f"query_points intent with unclear scope: '{query_scope}' or missing identifiers. LLM analysis: {llm_analysis}")

        if any_point_found_successfully and len(final_data_for_json_output) == 1:
            single_result_data = final_data_for_json_output[0]
            ctx_resolved_pk = single_result_data.get("_id")
            user_provided_id_for_ctx = user_provided_id
            if query_scope == "specific" and isinstance(multi_point_ids_llm, list) and len(multi_point_ids_llm) == 1: user_provided_id_for_ctx = multi_point_ids_llm[0]
            elif query_scope in ["all_named", "all"] or (isinstance(multi_point_ids_llm, list) and len(multi_point_ids_llm) > 1): user_provided_id_for_ctx = single_result_data.get("name") or ctx_resolved_pk
            if ctx_resolved_pk:
                current_turn_aimessage_kwargs["last_successful_point_context"] = {"user_provided": user_provided_id_for_ctx or ctx_resolved_pk, "resolved_p_key": ctx_resolved_pk, "intent_of_last_op": "query_points"}
                logger.info(f"Set last_successful_point_context for query: {current_turn_aimessage_kwargs['last_successful_point_context']}")
        if not response_parts: response_parts.append("No results found or your query request could not be identified.")
    
    elif intent == "list_points":
        if all_points_data:
            summary_list = []
            points_for_display_and_json = []
            sorted_p_keys = sorted(all_points_data.keys(), key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf'))
            
            llm_params_for_list = llm_analysis.get("parameters", {})
            list_options = llm_params_for_list.get("list_options", {}) if isinstance(llm_params_for_list, dict) else {}
            if not isinstance(list_options, dict): list_options = {}

            list_scope = list_options.get("scope", "all")
            wants_detailed_coords = list_options.get("include_details", False)
            
            if list_options.get("only_named", False) or list_options.get("named_only", False):
                list_scope = "all_named"

            logger.info(f"List points processing: scope='{list_scope}', wants_detailed_coords={wants_detailed_coords}, LLM params: {llm_params_for_list}")

            for p_key in sorted_p_keys:
                p_data = all_points_data[p_key]
                p_name = p_data.get('name')
                
                is_defined_for_all_scope = False
                if p_name: is_defined_for_all_scope = True
                else:
                    for field, spec in POINT_FIELD_SCHEMA.items():
                        if field != "name" and p_data.get(field) != spec["default"] and p_data.get(field) is not None:
                            is_defined_for_all_scope = True; break
                
                should_include = False
                if list_scope == "all_named":
                    if p_name: should_include = True
                elif list_scope == "all":
                    if is_defined_for_all_scope : should_include = True
                
                if should_include:
                    point_with_id = p_data.copy(); point_with_id["_id"] = p_key
                    points_for_display_and_json.append(point_with_id)
            
            if points_for_display_and_json:
                count_display_prefix = f"{len(points_for_display_and_json)}"
                if list_scope == "all_named": count_display_prefix += " teaching points with logical names"
                elif list_scope == "all": count_display_prefix += " defined teaching points"
                response_parts.append(f"Found {count_display_prefix}:")

                for point in points_for_display_and_json:
                    summary_list.append(f"  - {point['_id']}: {point.get('name', '(No logical name)')}")
                response_parts.append("\n".join(summary_list))
                
                final_data_for_json_output.extend(points_for_display_and_json)

                if wants_detailed_coords:
                    response_parts.append(f"\nDetails:\n{json.dumps(points_for_display_and_json, ensure_ascii=False, indent=2)}")
            else:
                if list_scope == "all_named": response_parts.append("No teaching points with logical names found.")
                else: response_parts.append("No defined teaching points found.")
        else:
            response_parts.append("No teaching point information is currently saved.")

    elif intent == "save_update_point":
        user_provided_target_id = llm_analysis.get("user_provided_target_identifier")
        resolved_target_p_key = llm_analysis.get("resolved_target_p_key")
        llm_params = llm_analysis.get("parameters")

        if not user_provided_target_id or not isinstance(llm_params, dict):
            response_parts.append(f"Cannot save/update point: LLM failed to extract target identifier or valid parameters. Details: {resolution_details}")
        else:
            action = "save" # Default action
            existing_data_for_slot = None
            slot_to_use_or_error = resolved_target_p_key # Initial candidate from LLM

            # Determine initial action and existing_data based on resolved_target_p_key
            if resolved_target_p_key and resolved_target_p_key in all_points_data:
                action = "update"
                existing_data_for_slot = all_points_data[resolved_target_p_key]
                logger.info(f"Intent: {action} existing teaching point '{resolved_target_p_key}'. User provided: '{user_provided_target_id}'.")
            elif resolved_target_p_key: # P_Key provided by LLM but not in all_points_data
                action = "save" # Treat as saving to a new, specific P_Key if valid
                logger.info(f"Intent: {action} to LLM suggested new slot '{resolved_target_p_key}'. User provided: '{user_provided_target_id}'.")
            else: # No P_Key from LLM, must be a new point needing an empty slot
                action = "save"
                slot_to_use_or_error = None # Explicitly set to None, needs slot finding
                logger.info(f"Intent: {action} new point. User provided: '{user_provided_target_id}'.")

            # Determine final logical name to be saved/updated
            final_logical_name = llm_params.get("name")
            if not final_logical_name: # If LLM didn't extract a name directly
                if action == "update" and existing_data_for_slot and existing_data_for_slot.get("name"):
                    final_logical_name = existing_data_for_slot.get("name") # Keep existing if not changing
                # If saving a new point, and user_id is not P-like, and resolved_p_key was not a name either:
                elif action == "save" and not (slot_to_use_or_error and re.fullmatch(r"P\d+", slot_to_use_or_error, re.IGNORECASE)) and not re.fullmatch(r"P\d+", user_provided_target_id, re.IGNORECASE):
                    final_logical_name = user_provided_target_id # Use user_id as name
            
            if final_logical_name: # Ensure llm_params reflects the name to be used for schema validation
                llm_params["name"] = final_logical_name
            
            point_data_to_save = _apply_schema_and_defaults_to_llm_params(llm_params, existing_data_for_slot)

            # --- Logic for 'action == "save"' ---
            if action == "save":
                if not point_data_to_save.get("name"):
                    response_parts.append(f"Cannot save new point: A new point must have a logical name. User input '{user_provided_target_id}' failed to provide a valid name.")
                    slot_to_use_or_error = "ERROR_SAVE_NO_NAME"
                else:
                    # Check for duplicate logical name if we are assigning a name
                    for p_key_iter, p_data_iter in all_points_data.items():
                        # If we are trying to use a specific P_Key (slot_to_use_or_error is set from resolved_target_p_key)
                        # and that P_Key is the one we are checking, skip (no self-conflict on name for this slot)
                        if slot_to_use_or_error and p_key_iter == slot_to_use_or_error:
                            continue 
                        if p_data_iter.get("name") == point_data_to_save.get("name"):
                            response_parts.append(f"Error: Logical name '{point_data_to_save.get('name')}' is already used by slot {p_key_iter}.")
                            slot_to_use_or_error = "ERROR_SAVE_DUPLICATE_NAME"; break
                    
                    if not (slot_to_use_or_error and slot_to_use_or_error.startswith("ERROR_")): # If no duplicate name error
                        if slot_to_use_or_error: # This means resolved_target_p_key was set and was not in all_points_data
                            # We are trying to save to a specific P_Key suggested by LLM.
                            # We need to ensure this P_Key isn't somehow already "taken" by an unnamed point with data
                            # (though _find_empty_slot_key should handle truly empty ones).
                            # For now, assume if it's not in all_points_data, it's available or will overwrite if it was an empty dict placeholder.
                            logger.info(f"Saving to LLM specified, currently non-existent slot '{slot_to_use_or_error}' (Name: '{point_data_to_save.get('name')}').")
                        else: # No specific P_Key from LLM, find an empty slot
                            slot_to_use_or_error = _find_empty_slot_key(all_points_data)
                            if slot_to_use_or_error:
                                logger.info(f"Assigning empty slot '{slot_to_use_or_error}' to new teaching point '{point_data_to_save.get('name')}'.")
                            else:
                                response_parts.append(f"Cannot save new point '{point_data_to_save.get('name')}': No empty slots available.")
                                slot_to_use_or_error = "ERROR_SAVE_NO_EMPTY_SLOT"
            
            # --- Logic for 'action == "update"' ---
            elif action == "update":
                if not slot_to_use_or_error or slot_to_use_or_error.startswith("ERROR_"): # Should not happen if action is update
                    logger.error(f"Logic error: Action is update, but slot_to_use_or_error ('{slot_to_use_or_error}') is invalid.")
                    response_parts.append(f"Internal logic error occurred while updating point.")
                elif point_data_to_save.get("name") is not None: # If name is part of the update parameters
                    new_name = point_data_to_save.get("name")
                    current_name_of_slot = existing_data_for_slot.get("name") if existing_data_for_slot else None
                    if new_name != current_name_of_slot: # Only check for duplicates if name is actually changing
                        for p_key_iter, p_data_iter in all_points_data.items():
                            if p_key_iter != slot_to_use_or_error and p_data_iter.get("name") == new_name:
                                response_parts.append(f"Error: Attempting to rename point '{slot_to_use_or_error}' to '{new_name}', but that name is already used by slot {p_key_iter}.")
                                slot_to_use_or_error = "ERROR_UPDATE_DUPLICATE_NAME"; break
            
            # --- Perform actual save/update if no errors detected ---
            if slot_to_use_or_error and not slot_to_use_or_error.startswith("ERROR_"):
                all_points_data[slot_to_use_or_error] = point_data_to_save
                if _save_teaching_points(all_points_data):
                    saved_name_display = point_data_to_save.get('name', slot_to_use_or_error)
                    response_parts.append(f"Teaching point '{saved_name_display}' (Slot: {slot_to_use_or_error}) has been successfully {action}d.")
                    point_display_data = {slot_to_use_or_error: point_data_to_save}
                    response_parts.append(f"Data for {slot_to_use_or_error} after {action}:\n{json.dumps(point_display_data, ensure_ascii=False, indent=2)}")
                    operation_succeeded_for_json_check = True
                    final_data_for_json_output.append({slot_to_use_or_error: point_data_to_save})
                    current_turn_aimessage_kwargs["last_successful_point_context"] = {
                        "user_provided": user_provided_target_id,
                        "resolved_p_key": slot_to_use_or_error,
                        "intent_of_last_op": "save_update_point"
                    }
                else:
                    response_parts.append(f"{action.capitalize()} teaching point '{point_data_to_save.get('name', slot_to_use_or_error)}' failed: Could not write to file.")
            elif not response_parts : # If no specific error message has been added by the logic above
                 error_code = slot_to_use_or_error if (slot_to_use_or_error and slot_to_use_or_error.startswith("ERROR_")) else "Unknown error"
                 response_parts.append(f"Cannot {action} point '{user_provided_target_id}'. Error code: {error_code}. LLM details: {resolution_details}")

    elif intent == "delete_point":
        user_provided_id = llm_analysis.get("user_provided_target_identifier")
        resolved_p_key_to_delete = llm_analysis.get("resolved_target_p_key")

        if not resolved_p_key_to_delete: 
            logger.warning(f"delete_point intent without resolved_target_p_key. User ID: '{user_provided_id}', Details: {resolution_details}")
            response_parts.append(f"Cannot find the point '{user_provided_id}' you specified for deletion. Please ensure the point exists or your phrasing is clear. LLM resolution: {resolution_details}")
        elif resolved_p_key_to_delete in all_points_data:
            deleted_point_name_display = all_points_data[resolved_p_key_to_delete].get("name", resolved_p_key_to_delete)
            
            empty_point_template = {key: spec["default"] for key, spec in POINT_FIELD_SCHEMA.items()}
            all_points_data[resolved_p_key_to_delete] = empty_point_template
            
            if _save_teaching_points(all_points_data):
                response_parts.append(f"The content of teaching point '{deleted_point_name_display}' (Slot {resolved_p_key_to_delete}) has been cleared. The slot is now reusable.")
                operation_succeeded_for_json_check = True
                final_data_for_json_output.append({"deleted_p_key": resolved_p_key_to_delete, "status": "cleared"})
                current_turn_aimessage_kwargs["last_successful_point_context"] = {"user_provided": user_provided_id, "resolved_p_key": resolved_p_key_to_delete, "intent_of_last_op": "delete_point"}
            else:
                response_parts.append(f"Clearing point '{deleted_point_name_display}' (from user identifier '{user_provided_id}') failed: Could not write to file.")
        else:
            response_parts.append(f"Point {resolved_p_key_to_delete} (from user identifier '{user_provided_id}') not found, cannot delete. LLM resolution: {resolution_details}")
    
    elif intent == "unclear_intent" or intent == "error_parsing_llm_response":
        reason = llm_analysis.get("reason", resolution_details if intent == "unclear_intent" else "Operation not supported or could not be understood.")
        response_parts.append(f"Cannot process your request: {reason}")
        raw_content_for_debug = llm_analysis.get("raw_content")
        if raw_content_for_debug:
            response_parts.append(f"LLM raw output (for debugging): {raw_content_for_debug[:200]}...")

    if not response_parts:
        response_parts.append(f"I'm not sure how to handle your teaching point request. LLM analyzed intent as: {intent if intent else 'Unknown'}. Details: {resolution_details}")
        logger.warning(f"Fallback: Unhandled intent '{intent}' or empty response_parts. LLM analysis was {llm_analysis}")

    final_response_content = "\n".join(filter(None, response_parts))
    
    # Determine if JSON output is appropriate for the intent and if data exists
    generated_json_str_for_polishing = ""
    if intent == "query_points" and final_data_for_json_output:
        # For query_points, the JSON should be a list of point details or a single point detail object
        if len(final_data_for_json_output) == 1:
            generated_json_str_for_polishing = json.dumps({"point_details": final_data_for_json_output[0]}, ensure_ascii=False, indent=2)
        else:
            generated_json_str_for_polishing = json.dumps({"points_details": final_data_for_json_output}, ensure_ascii=False, indent=2)
        logger.info(f"Prepared JSON for query_points: {generated_json_str_for_polishing[:200]}...")

    elif intent == "list_points" and final_data_for_json_output:
        # For list_points, the JSON should be a list of point summaries (name and p_key)
        # or full details if wants_detailed_coords was true (already handled in final_data_for_json_output structure for this intent)
        # We can directly use final_data_for_json_output if it contains the correct structure for the polishing prompt guide.
        # Based on `json_output_prompt_template` guide for list_points:
        # `{{ "named_points": [{{ "name": "入口点", "p_key": "P1" }}, ...] }}` or `{{ "point_names": ["入口点", ...] }}`
        # Current `final_data_for_json_output` for list_points is a list of dicts with full data or just name/_id
        # We should adapt it here to match one of the example structures.
        # Let's go with a structure similar to `named_points` but more general.
        points_for_json_list = []
        for point_data in final_data_for_json_output:
            p_key = point_data.get("_id", "Unknown_PKey")
            p_name = point_data.get("name")
            if p_name:
                points_for_json_list.append({"name": p_name, "p_key": p_key})
            # Optionally, if no name, one might choose to include just p_key or skip.
            # For now, let's focus on named points for this JSON structure.
        if points_for_json_list:
            generated_json_str_for_polishing = json.dumps({"listed_points": points_for_json_list}, ensure_ascii=False, indent=2)
        else: # If no points qualify (e.g. all were unnamed in a list_points call)
            generated_json_str_for_polishing = json.dumps({"listed_points": []}, ensure_ascii=False, indent=2) # Empty list
        logger.info(f"Prepared JSON for list_points: {generated_json_str_for_polishing[:200]}...")

    elif intent == "save_update_point" and operation_succeeded_for_json_check and final_data_for_json_output:
        # For save_update_point, JSON can be status or details of the saved point
        # `final_data_for_json_output` is `[{slot_to_use_or_error: point_data_to_save}]`
        # We can present this as { "status": "success", "operation": action, "point_saved": {P_Key: data} }
        # `action` variable is not directly available here. We can infer it or get it from llm_analysis or simplify.
        # Let's simplify to just the saved point data for now.
        if final_data_for_json_output: # Should be a list with one element
            saved_point_dict = final_data_for_json_output[0] # This is {P_Key: data}
            generated_json_str_for_polishing = json.dumps({"saved_point_details": saved_point_dict}, ensure_ascii=False, indent=2)
        logger.info(f"Prepared JSON for save_update_point: {generated_json_str_for_polishing[:200]}...")

    elif intent == "delete_point" and operation_succeeded_for_json_check and final_data_for_json_output:
        # `final_data_for_json_output` is `[{"deleted_p_key": resolved_p_key_to_delete, "status": "cleared"}]`
        if final_data_for_json_output:
            generated_json_str_for_polishing = json.dumps(final_data_for_json_output[0], ensure_ascii=False, indent=2)
        logger.info(f"Prepared JSON for delete_point: {generated_json_str_for_polishing[:200]}...")
    
    # If no specific JSON was generated, it remains an empty string.
    # The polishing function will handle appending it only if it's non-empty.

    step_a_analysis_str = json.dumps(llm_analysis, ensure_ascii=False, indent=2)

    logger.info(f"Teaching Node: Invoking LLM for polishing. Original query: '{user_input_content[:100]}...'")

    polished_response_content = await _invoke_llm_for_polishing(
        llm=llm,
        original_user_query=user_input_content,
        step_a_analysis=step_a_analysis_str,
        intermediate_results_text=final_response_content,
        generated_json_data_for_potential_inclusion=generated_json_str_for_polishing,
        intent=intent,
        logger_object=logger
    )

    logger.info(f"Teaching Node: Final polished response: '{polished_response_content[:300]}...' AIMessage kwargs: {current_turn_aimessage_kwargs}")
    return {"messages": [AIMessage(content=polished_response_content, additional_kwargs=current_turn_aimessage_kwargs)]} 