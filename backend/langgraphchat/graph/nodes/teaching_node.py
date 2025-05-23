import logging
import yaml
import json
import re
import difflib
from typing import Dict, Any, List, Optional, Union, Tuple

from ..agent_state import AgentState
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

TEACHING_POINTS_FILE = "/workspace/test_robot_flow_output_deepseek_interactive/teaching.yaml"
FUZZY_MATCH_CUTOFF = 0.7

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
    # Use a set to track P_N keys that have already been added to avoid duplicates if an identifier matches multiple ways
    added_p_keys = set()

    all_logical_names = [p_data.get("name") for p_data in points_data.values() if p_data.get("name")]

    for original_id in identifiers_from_llm:
        match_info = {"original_identifier": original_id, "matched_by": None, "matched_identifier": None, "data": None}
        found_this_id = False

        # 1. Exact P_N slot key match
        if original_id in points_data and original_id not in added_p_keys:
            match_info["data"] = points_data[original_id].copy()
            match_info["data"]["_id"] = original_id
            match_info["matched_by"] = "exact_pkey"
            match_info["matched_identifier"] = original_id
            found_points_results.append(match_info)
            added_p_keys.add(original_id)
            found_this_id = True
            continue # Found by P_N key, move to next identifier

        # 2. Exact logical name match
        for p_key, p_data in points_data.items():
            if p_key in added_p_keys: continue # Already added this slot
            if p_data.get("name") == original_id:
                match_info["data"] = p_data.copy()
                match_info["data"]["_id"] = p_key
                match_info["matched_by"] = "exact_logical_name"
                match_info["matched_identifier"] = original_id
                found_points_results.append(match_info)
                added_p_keys.add(p_key)
                found_this_id = True
                break # Found by logical name, assume logical names are unique enough for one entry per original_id
        if found_this_id: continue

        # 3. Fuzzy logical name match (if not a P_N pattern and no exact match found yet)
        if not re.fullmatch(r"P\d+", original_id, re.IGNORECASE):
            close_matches = difflib.get_close_matches(original_id, all_logical_names, n=1, cutoff=FUZZY_MATCH_CUTOFF)
            if close_matches:
                matched_logical_name = close_matches[0]
                for p_key, p_data in points_data.items():
                    if p_key in added_p_keys: continue
                    if p_data.get("name") == matched_logical_name:
                        match_info["data"] = p_data.copy()
                        match_info["data"]["_id"] = p_key
                        match_info["matched_by"] = "fuzzy_logical_name"
                        match_info["matched_identifier"] = matched_logical_name
                        found_points_results.append(match_info)
                        added_p_keys.add(p_key)
                        found_this_id = True
                        break # Found by fuzzy match
        
        if not found_this_id: # If no match at all for this identifier
            found_points_results.append(match_info) # Add with data=None
            
    return found_points_results

def _find_slot_by_identifier(points_data: Dict[str, Dict[str, Any]], identifier_from_llm: str) -> Tuple[Optional[str], str, str]:
    """Finds a P_N slot key by P_N id, exact logical name, or fuzzy logical name.
       Returns (p_key_found, type_of_match, identifier_actually_used_for_match).
       Match types: 'exact_pkey', 'exact_logical_name', 'fuzzy_logical_name', 'none'.
    """
    # 1. Exact P_N slot key match
    if identifier_from_llm in points_data:
        return identifier_from_llm, "exact_pkey", identifier_from_llm
    
    # 2. Exact logical name match
    for p_key, p_data in points_data.items():
        if p_data.get("name") == identifier_from_llm:
            return p_key, "exact_logical_name", identifier_from_llm
            
    # 3. Fuzzy logical name match (if not a P_N pattern)
    if not re.fullmatch(r"P\d+", identifier_from_llm, re.IGNORECASE):
        all_logical_names = [p.get("name") for p in points_data.values() if p.get("name")]
        close_matches = difflib.get_close_matches(identifier_from_llm, all_logical_names, n=1, cutoff=FUZZY_MATCH_CUTOFF)
        if close_matches:
            matched_logical_name = close_matches[0]
            for p_key, p_data in points_data.items():
                if p_data.get("name") == matched_logical_name:
                    return p_key, "fuzzy_logical_name", matched_logical_name
                    
    return None, "none", identifier_from_llm

def _find_empty_slot_key(points: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Finds the key of the first empty teaching point slot."""
    for i in range(1, 101):
        key = f"P{i}"
        if key not in points or not points[key].get("name"):
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
                        type_checks = [(float, float), (int, int)] # Order matters if overlaps
                        for type_to_check, type_constructor in type_checks:
                             if type_to_check in expected_type:
                                try: validated_data[field_key] = type_constructor(raw_value); converted = True; break
                                except (ValueError, TypeError): pass                        
                        if not converted and type(None) in expected_type and raw_value is None: 
                            validated_data[field_key] = None; converted = True
                        if not converted:
                             raise ValueError(f"Cannot convert LLM value '{raw_value}' to any of types {expected_type}")
                else:
                    validated_data[field_key] = raw_value 
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not convert LLM value '{raw_value}' for field '{field_key}' to {expected_type}: {e}. Using default: {spec['default']}.")
                validated_data[field_key] = spec["default"]
        elif existing_data and field_key in existing_data:
            validated_data[field_key] = existing_data[field_key]
        elif field_key not in validated_data:
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
            if name:
                existing_points_summary.append(f"  - {p_key} (Logical Name: {name})")
            elif p_data and any(v is not None for k, v in p_data.items() if k != 'name'): # Check if other fields are set
                 existing_points_summary.append(f"  - {p_key} (No logical name, but has data)")
    else:
        existing_points_summary.append("  (No teaching points defined yet)")
    existing_points_str = "\n".join(existing_points_summary)

    # --- Try to get context from the last AI message from this node ---
    previous_context_str = "No specific point context from the immediately preceding turn."
    ctx_p_key_for_prompt_example = "[P_Key from context]"

    if len(messages) >= 2:
        last_ai_message = messages[-2]
        logger.info(f"Attempting to extract context from messages[-2]: {last_ai_message}")
        if isinstance(last_ai_message, AIMessage) and last_ai_message.additional_kwargs.get("node") == "teaching":
            last_point_ctx = last_ai_message.additional_kwargs.get("last_successful_point_context")
            logger.info(f"Extracted last_successful_point_context: {last_point_ctx}")
            if last_point_ctx and isinstance(last_point_ctx, dict):
                ctx_user_id = last_point_ctx.get("user_provided")
                actual_ctx_p_key = last_point_ctx.get("resolved_p_key")
                ctx_op = last_point_ctx.get("intent_of_last_op")
                if actual_ctx_p_key:
                    ctx_p_key_for_prompt_example = actual_ctx_p_key
                    previous_context_str = (
                        f"RECENTLY PROCESSED POINT: The point '{actual_ctx_p_key}' (user referred to it as '{ctx_user_id}') "
                        f"was successfully processed with operation '{ctx_op}' in the previous turn. "
                        f"This point ('{actual_ctx_p_key}') is the primary candidate if the user says \"it\", \"that one\", etc."
                    )
                    logger.info(f"Populated previous_context_str: {previous_context_str}")
                else:
                    logger.info("No actual_ctx_p_key found in last_point_ctx.")
            else:
                logger.info("last_point_ctx is None or not a dict.")
        else:
            logger.info("messages[-2] is not an AIMessage or not from teaching_node.")
    else:
        logger.info("Not enough messages to extract previous context (len(messages) < 2).")
    # --- End context retrieval ---

    system_prompt = f"""You are an expert assistant for managing robot teaching points.
Your task is to understand the user's request and extract relevant information, including resolving point identifiers against a provided list and using conversational context.
Teaching points are stored with primary keys like P1, P2, ..., P100. Each point can have a 'name' field (a user-defined logical name).

SCHEMA:
{schema_str}

CURRENT DEFINED TEACHING POINTS:
{existing_points_str}

PREVIOUS TURN CONTEXT:
{previous_context_str}

Based on the user's input, the current defined points, and the previous turn context, determine the intent and extract parameters. Respond in JSON format.

General instructions for resolving identifiers:
1. Extract the identifier(s) the user provided in their input.
2. For each identifier (or for `it` if referential based on PREVIOUS TURN CONTEXT):
    a. If the user input is a referential term (e.g., "it", "that", "that one") AND the PREVIOUS TURN CONTEXT section indicates a RECENTLY PROCESSED POINT (e.g., "...'P_N' is the primary candidate..."), then you MUST resolve the user's term to that specific P_N. Set resolution_details clearly, e.g., "Resolved from 'it' based on previous context: '{ctx_p_key_for_prompt_example}'."
    b. If not a referential term resolved from context, and it's an exact P-number (e.g., "P1") listed in the defined points, that's your resolved key.
    c. If not resolved by above, and it's a logical name, try to match it against the logical names in the defined points list (exact first, then close fuzzy).
    d. If an identifier is not resolved by any of the above means:
        - For 'save_update_point', this usually means a new point is being created with this identifier as its proposed name.
        - For 'query_points' or 'delete_point', it means the point was not found.

JSON Response Format:

1.  Intent: "query_points"
    - "identifiers_to_query": [
        {{
            "user_provided": "<original_id_as_stated_by_user_or_referential_like_it>",
            "resolved_p_key": "<P_N_or_null>",
            "resolution_details": "<E.g., 'Exact P-Key match.', 'Matched logical name: [name].', 'Resolved from \'it\' based on previous context targeting P2.', 'No match found.'>"
        }},
        ...
      ]

2.  Intent: "list_all_points" (No specific parameters needed beyond intent)

3.  Intent: "save_update_point"
    - "user_provided_target_identifier": "<original_id_for_target_as_stated_by_user_or_referential_like_it>"
    - "resolved_target_p_key": "<P_N_or_null_if_new_or_unresolved>"
    - "resolution_details": "<E.g., 'Exact P-Key match to [P_Key].', 'Resolved from \'it\' based on previous context targeting P1, will update P1.', 'Identifier does not match existing points, will create new point.'>"
    - "parameters": {{ <dict of parameters to set/update. If creating a new point with a logical name, 'name' MUST be in parameters.> }}

4.  Intent: "delete_point"
    - "user_provided_identifier": "<original_id_for_delete_as_stated_by_user_or_referential_like_it>"
    - "resolved_p_key_to_delete": "<P_N_or_null_if_unresolved>"
    - "resolution_details": "<E.g., 'Exact P-Key match to [P_Key].', 'Resolved from \'it\' based on previous context targeting P5, will delete P5.', 'No match found.'>"

5.  Intent: "unclear_intent"
    - "reason": "<explanation>"

Examples:
(Assuming P1 (Name: home_A), P2 (Name: station_B) were defined. Previous turn context: User queried "P2" which resolved to P2 successfully.)

User: "delete it"
JSON: {{
  "intent": "delete_point",
  "user_provided_identifier": "it",
  "resolved_p_key_to_delete": "P2",
  "resolution_details": "Resolved from 'it' based on previous context targeting P2."
}}

User: "查询点位 P1 和 station_C"
JSON: {{
  "intent": "query_points",
  "identifiers_to_query": [
    {{"user_provided": "P1", "resolved_p_key": "P1", "resolution_details": "Exact P-Key match."}},
    {{"user_provided": "station_C", "resolved_p_key": null, "resolution_details": "No match found for 'station_C'."}}
  ]
}}

Now, analyze the following user input:
"""
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]

async def _invoke_llm_for_intent(llm: BaseChatModel, user_input: str, points_data: Dict[str, Dict[str, Any]], messages: List[BaseMessage]) -> Dict[str, Any]:
    prompt_messages = _get_llm_prompt_for_teaching(user_input, points_data, messages)
    json_str_to_parse = ""
    original_llm_content = ""
    try:
        response = await llm.ainvoke(prompt_messages)
        original_llm_content = response.content
        logger.info(f"LLM raw response content for teaching intent: {original_llm_content}")

        # Enhanced JSON extraction
        # Try to find ```json ... ``` block first
        json_markdown_match = re.search(r"```json\s*(\{.*?\})\s*```", original_llm_content, re.DOTALL | re.IGNORECASE)
        if json_markdown_match:
            json_str_to_parse = json_markdown_match.group(1).strip()
            logger.info(f"Extracted JSON from markdown block: {json_str_to_parse}")
        else:
            # If no markdown block, try to find the first '{' and last '}' that form a plausible JSON object.
            # This is a fallback and might be brittle if LLM includes other braces in explanations.
            first_brace = original_llm_content.find('{')
            last_brace = original_llm_content.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                potential_json = original_llm_content[first_brace : last_brace + 1]
                # Basic validation: does it look like a JSON object?
                if potential_json.startswith('{') and potential_json.endswith('}'):
                    json_str_to_parse = potential_json.strip()
                    logger.info(f"Extracted potential JSON using first/last brace: {json_str_to_parse}")
                else:
                    # This case means we found braces but they didn't form a simple block. 
                    # Could be an error or complex output not parsable this way.
                    json_str_to_parse = original_llm_content # Fallback to full content, likely to fail parsing
                    logger.warning(f"Found braces, but not a simple JSON block. Attempting to parse full content, which will likely fail: {json_str_to_parse}")
            else:
                # No markdown, no braces found, likely not JSON.
                json_str_to_parse = original_llm_content # Fallback to full content, likely to fail parsing
                logger.warning(f"No JSON markdown block or clear JSON object braces found. Attempting to parse full content, which will likely fail: {json_str_to_parse}")
        
        if not json_str_to_parse: # If after all attempts, json_str_to_parse is empty
            logger.error(f"Could not extract any parsable JSON string from LLM output. Raw content: {original_llm_content}")
            return {"intent": "unclear_intent", "reason": f"LLM output did not contain a recognizable JSON structure. Raw output: {original_llm_content}"}

        parsed_json = json.loads(json_str_to_parse)
        return parsed_json
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extracted JSON string. Error: {e}. String attempted to parse: '{json_str_to_parse}'. Original LLM content: '{original_llm_content}'")
        return {"intent": "unclear_intent", "reason": f"LLM output was not valid JSON despite extraction attempts. Extracted part: '{json_str_to_parse}'. Raw output: '{original_llm_content}'"}
    except Exception as e:
        logger.error(f"Error invoking LLM or processing response: {e}. Original LLM content (if available): '{original_llm_content}'")
        return {"intent": "unclear_intent", "reason": "Error processing LLM response."}


# --- Main Node Logic ---
async def teaching_node(state: AgentState, llm: BaseChatModel, **kwargs) -> Dict[str, Any]:
    messages: List[BaseMessage] = state.get("messages", [])
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {"messages": [AIMessage(content="Cannot process teaching point operation: No valid user instruction.", additional_kwargs={"node": "teaching"})]}

    user_input_content = messages[-1].content.strip()
    logger.info(f"Teaching Node: Received input '{user_input_content[:200]}...'")

    all_points_data = _load_teaching_points()
    response_parts = [] # For constructing response message

    # Pass the full messages list to _invoke_llm_for_intent
    llm_analysis = await _invoke_llm_for_intent(llm, user_input_content, all_points_data, messages)
    intent = llm_analysis.get("intent")
    logger.info(f"LLM intent: {intent}, analysis: {llm_analysis}")

    # Initialize last_successful_point_context for this turn's AIMessage
    current_turn_aimessage_kwargs = {"node": "teaching"}

    if intent == "query_points":
        identifiers_to_query = llm_analysis.get("identifiers_to_query", [])
        if not isinstance(identifiers_to_query, list) or not identifiers_to_query:
            response_parts.append("LLM did not return any identifiers to query. Please specify point identifiers (P-number or logical name).")
        else:
            found_data_for_json = []
            any_point_found = False

            for item in identifiers_to_query:
                user_provided = item.get("user_provided")
                resolved_p_key = item.get("resolved_p_key")
                details = item.get("resolution_details", "No details provided by LLM.")

                if resolved_p_key and resolved_p_key in all_points_data:
                    point_data = all_points_data[resolved_p_key].copy()
                    point_data["_id"] = resolved_p_key # Ensure the P-key is part of the output data
                    found_data_for_json.append(point_data)
                    response_parts.append(f"Found point for '{user_provided}' (resolved to {resolved_p_key}): {details}")
                    any_point_found = True
                else:
                    response_parts.append(f"Could not find point for '{user_provided}'. LLM resolution: {details}")
            
            if found_data_for_json:
                response_parts.append(f"Queried point information:\\n{json.dumps(found_data_for_json, ensure_ascii=False, indent=2)}")
                if len(found_data_for_json) == 1:
                    the_found_point_data = found_data_for_json[0]
                    resolved_p_key_for_context = the_found_point_data.get("_id")
                    user_provided_for_context = None

                    if resolved_p_key_for_context:
                        # Try to find the original user_provided term that led to this resolved_p_key
                        for queried_item in identifiers_to_query: 
                            if queried_item.get("resolved_p_key") == resolved_p_key_for_context:
                                user_provided_for_context = queried_item.get("user_provided")
                                break
                        
                        # Fallback if direct match not found but only one thing was initially queried by LLM
                        if user_provided_for_context is None and len(identifiers_to_query) == 1:
                            user_provided_for_context = identifiers_to_query[0].get("user_provided")
                        
                        # If still None, use a generic placeholder
                        user_provided_for_context = user_provided_for_context if user_provided_for_context else resolved_p_key_for_context # Fallback to P_Key if user_provided is elusive

                        current_turn_aimessage_kwargs["last_successful_point_context"] = {
                            "user_provided": user_provided_for_context,
                            "resolved_p_key": resolved_p_key_for_context,
                            "intent_of_last_op": "query_points"
                        }
                        logger.info(f"Set last_successful_point_context for query: {current_turn_aimessage_kwargs['last_successful_point_context']}")
                    else:
                        logger.warning("Single found point in found_data_for_json is missing '_id'. Cannot set context.")
            elif not any_point_found:
                 response_parts.append("No matching points found based on the provided identifiers and LLM resolution.")

    elif intent == "list_all_points":
        if all_points_data:
            summary_list = []
            sorted_p_keys = sorted(all_points_data.keys(), key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf'))
            for p_key in sorted_p_keys:
                p_data = all_points_data[p_key]
                p_name = p_data.get('name', '')
                status = f"Logical Name: {p_name}" if p_name else "(Logical name not set)"
                summary_list.append(f"  - {p_key}: {status}")
            response_parts.append("Current status of all teaching point slots:\n" + "\n".join(summary_list))
            defined_points_details = {k:v for k,v in sorted(all_points_data.items()) if v.get("name")}
            if defined_points_details:
                 response_parts.append(f"\n\nDetailed defined point information (P-key: data):\n{json.dumps(defined_points_details, ensure_ascii=False, indent=2)}")
        else:
            response_parts.append("There is currently no saved teaching point information.")

    elif intent == "save_update_point":
        user_provided_target_id = llm_analysis.get("user_provided_target_identifier")
        resolved_target_p_key = llm_analysis.get("resolved_target_p_key")
        resolution_details = llm_analysis.get("resolution_details", "No resolution details from LLM.")
        llm_params = llm_analysis.get("parameters")

        if not user_provided_target_id or not isinstance(llm_params, dict):
            response_parts.append(f"Cannot save/update point: LLM failed to extract target identifier or valid parameters. Details: {resolution_details}")
        else:
            action = "save"
            existing_data_for_slot = None
            slot_to_use = resolved_target_p_key

            if resolved_target_p_key and resolved_target_p_key in all_points_data:
                action = "update"
                existing_data_for_slot = all_points_data.get(resolved_target_p_key)
                logger.info(f"{action.capitalize()} existing teaching point. User ID: '{user_provided_target_id}', Resolved P-Key: '{resolved_target_p_key}'. LLM Details: {resolution_details}. Params: {llm_params}")
            elif resolved_target_p_key: # LLM resolved a P-Key but it's not in current data (e.g. P101)
                logger.warning(f"LLM resolved to P-Key '{resolved_target_p_key}' for '{user_provided_target_id}', but this P-Key is not in current data. Treating as new if possible. Details: {resolution_details}")
                # This might be a case where LLM hallucinates a P-key not in current data. We will try to find an empty slot or reject if name isn't in params.
                slot_to_use = None # Force finding an empty slot if we proceed with save.

            final_logical_name = llm_params.get("name")
            if not final_logical_name:
                if action == "update" and existing_data_for_slot and existing_data_for_slot.get("name"):
                    final_logical_name = existing_data_for_slot.get("name")
                elif action == "save" and not re.fullmatch(r"P\\d+", user_provided_target_id, re.IGNORECASE): # If saving new and user_provided wasn't a P-key
                    final_logical_name = user_provided_target_id
            
            llm_params["name"] = final_logical_name # Ensure name is consistently set in params

            point_data_to_save = _apply_schema_and_defaults_to_llm_params(llm_params, existing_data_for_slot)

            if not slot_to_use: # If slot_to_use is None (new point or LLM resolved P-key was invalid)
                if not point_data_to_save.get("name"): # Cannot save a new point without a logical name
                    response_parts.append(f"Cannot {action} point: New point requires a logical name, but none was provided or derived. User ID: '{user_provided_target_id}'. LLM Resolution: {resolution_details}")
                    slot_to_use = None # Explicitly ensure it stays None
                else:
                    # Check if a point with this logical name already exists in a DIFFERENT P_N slot
                    for p_key_iter, p_data_iter in all_points_data.items():
                        if p_data_iter.get("name") == point_data_to_save.get("name"):
                            response_parts.append(f"Error: Logical name '{point_data_to_save.get('name')}' already exists at slot {p_key_iter}. Cannot create a new point with a duplicate logical name.")
                            slot_to_use = "DUPLICATE_LOGICAL_NAME" # Special value to prevent saving
                            break
                    if slot_to_use != "DUPLICATE_LOGICAL_NAME":
                        slot_to_use = _find_empty_slot_key(all_points_data)
                        if slot_to_use:
                            action = "save" # Explicitly set to save for new slot
                            logger.info(f"Assigned empty slot '{slot_to_use}' for new teaching point '{final_logical_name}'. Original user ID: '{user_provided_target_id}'. LLM Resolution: {resolution_details}")
                        else:
                            response_parts.append(f"Cannot {action} teaching point '{final_logical_name}': All slots are full. User ID: '{user_provided_target_id}'.")
            
            if slot_to_use and slot_to_use != "DUPLICATE_LOGICAL_NAME":
                all_points_data[slot_to_use] = point_data_to_save
                if _save_teaching_points(all_points_data):
                    saved_name = point_data_to_save.get('name', slot_to_use)
                    response_parts.append(f"Teaching point '{saved_name}' (slot: {slot_to_use}) successfully {action}d. User ID: '{user_provided_target_id}'. LLM Resolution: {resolution_details}")
                    point_display_data = {slot_to_use: point_data_to_save}
                    response_parts.append(f"Data for {slot_to_use}:\\n{json.dumps(point_display_data, ensure_ascii=False, indent=2)}")
                    current_turn_aimessage_kwargs["last_successful_point_context"] = {
                        "user_provided": user_provided_target_id, # or saved_name if more appropriate as antecedent
                        "resolved_p_key": slot_to_use,
                        "intent_of_last_op": "save_update_point"
                    }
                else:
                    response_parts.append(f"{action.capitalize()} teaching point '{point_data_to_save.get('name', slot_to_use)}' failed: Cannot write to file. User ID: '{user_provided_target_id}'.")
            elif slot_to_use != "DUPLICATE_LOGICAL_NAME": # Only if not already handled by duplicate name message
                 response_parts.append(f"Could not {action} point for '{user_provided_target_id}'. Check logs. LLM details: {resolution_details}")

    elif intent == "delete_point":
        user_provided_id = llm_analysis.get("user_provided_identifier")
        resolved_p_key_to_delete = llm_analysis.get("resolved_p_key_to_delete")
        resolution_details = llm_analysis.get("resolution_details", "No resolution details from LLM.")

        if not user_provided_id:
            response_parts.append("Please specify the point identifier to delete. LLM did not provide one.")
        elif resolved_p_key_to_delete and resolved_p_key_to_delete in all_points_data:
            deleted_point_name_display = all_points_data[resolved_p_key_to_delete].get("name", resolved_p_key_to_delete)
            # Store details before deleting from all_points_data for context
            context_user_provided_id = user_provided_id
            context_resolved_p_key = resolved_p_key_to_delete
            
            empty_point_template = {key: spec["default"] for key, spec in POINT_FIELD_SCHEMA.items()}
            empty_point_template["name"] = None 
            all_points_data[resolved_p_key_to_delete] = empty_point_template
            
            if _save_teaching_points(all_points_data):
                response_parts.append(f"Contents of teaching point '{deleted_point_name_display}' (slot {resolved_p_key_to_delete}) have been cleared. The slot is reusable. User ID: '{user_provided_id}'. LLM Resolution: {resolution_details}")
                current_turn_aimessage_kwargs["last_successful_point_context"] = {
                    "user_provided": context_user_provided_id,
                    "resolved_p_key": context_resolved_p_key, # The key that was deleted
                    "intent_of_last_op": "delete_point"
                }
            else:
                response_parts.append(f"Clearing point '{deleted_point_name_display}' (from user ID '{user_provided_id}') failed: Cannot write to file. LLM Resolution: {resolution_details}")
        else:
            response_parts.append(f"Teaching point specified by user as '{user_provided_id}' not found for deletion. LLM Resolution: {resolution_details}")
    
    elif intent == "unclear_intent":
        reason = llm_analysis.get("reason", "Could not parse your request.")
        response_parts.append(f"Cannot process your request: {reason}")
        response_parts.append("Please refer to the following format:\n" +
                           "  - Query: 'Query point P1', 'Query point home', 'Query all points'\n" +
                           "  - Save/Modify: 'Save point home x_pos 10 ...', 'Modify P2 x_pos 15 name P2_new'\n" +
                           "  - Delete: 'Delete point P1', 'Delete point home'")
    else: 
        response_parts.append("Cannot recognize your instruction. Please specify if you want to query, save/modify, or delete a teaching point.")
        logger.warning(f"Fallback: LLM analysis was {llm_analysis}")
        # Fallback help info
        if all_points_data:
            saved_points_summary = [] ; empty_slot_keys = []
            sorted_p_keys = sorted(all_points_data.keys(), key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf'))
            for p_key in sorted_p_keys:
                p_data = all_points_data[p_key]
                p_name = p_data.get('name', '')
                if p_name: saved_points_summary.append(f"  - {p_key} (Logical Name: {p_name})")
                else: empty_slot_keys.append(p_key)
            for i in range(1, 101): 
                k = f"P{i}"
                if k not in all_points_data and k not in empty_slot_keys: empty_slot_keys.append(k)
            empty_slot_keys.sort(key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf'))
            response_parts.append("\nDefined/Used Point Slots:\n" + ('\n'.join(saved_points_summary) if saved_points_summary else "  (None)"))
            response_parts.append("Available Empty Slots (Example):\n  " + (', '.join(empty_slot_keys[:10]) + ("..." if len(empty_slot_keys) > 10 else "") if empty_slot_keys else " (None)"))
        else: response_parts.append("\nCurrently, there is no teaching point file in the workspace or the file is empty.")

    final_response_content = "\n".join(filter(None, response_parts))
    logger.info(f"Teaching Node: Final response: '{final_response_content[:300]}...' AIMessage kwargs: {current_turn_aimessage_kwargs}")
    return {"messages": [AIMessage(content=final_response_content, additional_kwargs=current_turn_aimessage_kwargs)]} 