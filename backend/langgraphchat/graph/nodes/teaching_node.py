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
            elif p_data and any(v is not None for k, v in p_data.items() if k != 'name'):
                 existing_points_summary.append(f"  - {p_key} (No logical name, but has data)")
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

    # Parse recent conversation history from messages
    ai_response_history_str = "(无最近AI回复)"
    user_request_history_str = "(无最近用户请求)"
    
    if messages:
        # Find the most recent AI response and user request from the messages list
        recent_ai_messages = []
        recent_user_messages = []
        
        # Look at the last few messages to get recent context
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        
        for msg in reversed(recent_messages):
            if isinstance(msg, AIMessage) and len(recent_ai_messages) < 2:
                recent_ai_messages.append(msg.content.strip())
            elif isinstance(msg, HumanMessage) and len(recent_user_messages) < 2:
                recent_user_messages.append(msg.content.strip())
        
        # Format AI response history (most recent first)
        if recent_ai_messages:
            ai_response_history_str = "\n".join([
                f"AI回复{i+1}: {msg[:200]}..." if len(msg) > 200 else f"AI回复{i+1}: {msg}"
                for i, msg in enumerate(recent_ai_messages)
            ])
        
        # Format user request history (most recent first)
        if recent_user_messages:
            user_request_history_str = "\n".join([
                f"用户请求{i+1}: {msg[:200]}..." if len(msg) > 200 else f"用户请求{i+1}: {msg}"
                for i, msg in enumerate(recent_user_messages)
            ])

    new_system_prompt_template = f"""
你是一个专业的机器人示教点管理助手。
你的任务是分析【用户最新的输入】，并结合【最近的对话历史】来理解用户的意图，然后输出一个结构化的JSON对象。

【JSON输出结构】
你必须输出一个符合以下描述的JSON对象：
- intent: (String) 用户的核心意图。必须从以下列表中选择：[{valid_intents_str}]。
- user_provided_target_identifier: (String or Null) 用户输入中明确指定的点标识符（P_Key或逻辑名称）。如果用户没有明确指定，则为null。
- resolved_target_p_key: (String or Null) 如果 `user_provided_target_identifier` 或上下文能够明确解析到某个已定义点的P_Key，则为该P_Key (例如 "P1")；否则为null。
- resolution_details: (String) 详细说明你是如何解析（或为何无法解析） `user_provided_target_identifier` 到 `resolved_target_p_key` 的。包括你考虑的上下文信息。
- parameters: (Object or Null) 包含操作所需的参数。
    - 对于 `save_update_point`，它可能包含 `name`, `x_pos` 等字段及其值。
    - 对于 `query_points`，可以包含 `query_scope` 字段，其值可以是:
        - "specific": 当用户查询一个或多个【特定】点时。此时应填充 `user_provided_target_identifier` (单个) 或 `target_identifiers_for_multi_point_ops` (多个)。
        - "all_named": 当用户想要查询【所有带逻辑名称的示教点】时。
        - "all": 当用户想要查询【所有已定义的示教点】时（无论有无名称）。
    - 对于查询或删除，如果无其他参数（例如 `query_scope`），则为null。
- target_identifiers_for_multi_point_ops: (List of Strings or Null) 仅用于 `query_points` (当 `query_scope` 为 "specific" 且需要查询多个特定点时) 或 `delete_point` (当需要批量删除时)，用户指定的多个点标识符列表。

【意图选择规则与指导】
1.  **`save_update_point`**: 
    *   当用户想要【创建】一个新的示教点并赋予其属性（名称、坐标等）。
    *   当用户想要【修改/更新】一个【已存在】的示教点的任何属性（包括其逻辑名称、坐标、工具号等）。
    *   **重命名点**: 如果用户想【重命名】一个点，这属于更新点的逻辑名称，因此应使用此意图。在 `parameters` 中提供新的 `name`。
2.  **`delete_point`**: 当用户想要【删除】一个或多个已定义的示教点。
3.  **`query_points`**: 
    *   当用户想要查询【单个特定点】的详细信息。在 `parameters` 中设置 `query_scope: "specific"`，并将该点的标识符放入 `user_provided_target_identifier`。
    *   当用户想要查询【多个特定点】的详细信息。在 `parameters` 中设置 `query_scope: "specific"`，并将这些点的标识符列表放入 `target_identifiers_for_multi_point_ops`。
    *   当用户想要查询【所有示教点】。在 `parameters` 中设置 `query_scope: "all"`。
    *   当用户想要查询【所有带逻辑名称的示教点】。在 `parameters` 中设置 `query_scope: "all_named"`。
4.  **`list_points`**: 
    *   当用户想要【列出多个特定点】的概览信息（通常是P_Key和逻辑名称）。
    *   当用户想要列出【所有点】或【所有有名称的点】等概览信息。此时 `target_identifiers_for_multi_point_ops` 可能为null或包含特殊指令（如 "all_named"），由后续代码处理。LLM需要根据用户描述在 `parameters` 中设置 `list_options` (例如: "all", "named_only", "details_for_identified")。
5.  **`clarify_ambiguous_instruction`**: 
    *   当用户的指令不明确，或者你无法安全地解析出用户想要操作的目标点时（特别是对于 `save_update_point` 更新操作 和 `delete_point` 操作）。
    *   当你根据【重要：指代消解与歧义处理】部分的规则判断需要澄清时。

【重要：指代消解与歧义处理】
当用户使用代词（如\"它\"、\"他的\"、\"那个点\"）或模糊引用时，你必须仔细查看【最近的对话历史】，特别是【上一个用户输入】和【上一个AI的回复】，来确定这些指代具体指向哪个已定义的示教点（P_Key，如P1，或逻辑名称，如\"入口点\"）。
- 如果你能成功解析指代，请在输出的JSON中将 \"resolved_target_p_key\" 设置为解析到的 P_Key。
- 如果指代不明或无法从上下文中解析，请将 \"resolved_target_p_key\" 设置为 null，并在 \"resolution_details\" 中详细说明原因。
- **关键：如果 `user_provided_target_identifier` 是一个代词 (例如, '他', '它', '那个') 或任何根据你的 `resolution_details` 分析表明具有高度歧义的标识符，并且你因此将 `resolved_target_p_key` 设置为 `null`，那么你必须将 `intent` 设置为 `clarify_ambiguous_instruction`。**
- **对于意图 `save_update_point` (当更新一个现有机器人示教点时，而不是用新名称创建一个新点) 和 `delete_point`，必须在JSON中提供一个非空的 `resolved_target_p_key`。如果你无法为这些意图解析出目标点，则必须将 `intent` 设置为 `clarify_ambiguous_instruction`。**

【现有示教点参考】：
{existing_points_str}

【点位数据字段定义 (用于 `parameters` 对象)】:
{schema_str}

【最近的对话历史】:
AI: {ai_response_history_str}
User: {user_request_history_str}

【用户最新的输入】:
{user_input}

请根据以上所有信息，生成你的JSON输出。
"""
    # Prepare message history for the prompt
    llm_messages: List[BaseMessage] = []
    llm_messages.append(SystemMessage(content=new_system_prompt_template))

    # Add recent history from 'messages'.
    # 'messages' contains the history *before* the current user_input.
    # We want to give the LLM the most relevant recent turns.
    # Let's take up to the last 4 messages (2 user, 2 AI turns typically) as context.
    # Adjust N as needed for optimal performance.
    if messages:
        history_to_include = messages[-4:] # Take last 4 messages
        llm_messages.extend(history_to_include)
        logger.debug(f"Including last {len(history_to_include)} messages from history for LLM context in teaching_node.")

    llm_messages.append(HumanMessage(content=user_input))
    
    # Log the messages being sent to LLM for teaching intent analysis (optional, can be verbose)
    # for i, msg in enumerate(llm_messages):
    #     logger.debug(f"LLM Teaching Prompt - Message {i} ({type(msg).__name__}):\\n{msg.content[:500]}...") # Log first 500 chars

    return llm_messages

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

    # Pass the full messages list (which includes history *before* current user_input) 
    # to _invoke_llm_for_intent. _get_llm_prompt_for_teaching (called by _invoke_llm_for_intent)
    # will select the relevant recent history.
    llm_analysis = await _invoke_llm_for_intent(llm, user_input_content, all_points_data, messages)
    intent = llm_analysis.get("intent")
    resolution_details = llm_analysis.get("resolution_details", "No details provided by LLM.") # Get this early for clarification messages
    logger.info(f"LLM intent: {intent}, analysis: {llm_analysis}")

    current_turn_aimessage_kwargs = {"node": "teaching"}

    # 1. Handle explicit clarification request from LLM
    if intent == "clarify_ambiguous_instruction":
        logger.info(f"Teaching Node: LLM requested clarification. Details: {resolution_details}")
        # Prefer resolution_details if it's well-formed for the user, otherwise a generic message.
        clarification_message = resolution_details if resolution_details and len(resolution_details) > 10 else f"抱歉，我不太理解您的意思。{resolution_details} 您能说得更具体一些吗？"
        return {"messages": [AIMessage(content=clarification_message, additional_kwargs=current_turn_aimessage_kwargs)]}

    # --- Main intent processing starts here ---
    if intent == "query_points":
        queried_points_info = []
        final_query_results_data = []
        any_point_found_successfully = False

        llm_params = llm_analysis.get("parameters", {})
        query_scope = llm_params.get("query_scope")

        multi_point_ids_llm = llm_analysis.get("target_identifiers_for_multi_point_ops")
        user_provided_id = llm_analysis.get("user_provided_target_identifier")
        resolved_p_key = llm_analysis.get("resolved_target_p_key")
        
        if query_scope == "all_named":
            logger.info(f"Processing 'query_points' with scope 'all_named'.")
            named_points = []
            for p_key_iter in sorted(all_points_data.keys(), 
                              key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')):
                p_data_item = all_points_data[p_key_iter]
                if p_data_item.get('name'):
                    point_with_id = p_data_item.copy()
                    point_with_id["_id"] = p_key_iter
                    named_points.append(point_with_id)
                    any_point_found_successfully = True # Found at least one named point
            
            if named_points:
                response_parts.append(f"查询到 {len(named_points)} 个具有逻辑名称的示教点:")
                for point in named_points:
                    p_key_display = point["_id"]
                    p_name_display = point.get("name", "")
                    response_parts.append(f"  - {p_key_display}: {p_name_display}")
                # For context setting, even if we only show summary, all results are relevant
                final_query_results_data.extend(named_points)
                # Optionally, to show full details in message:
                # response_parts.append(f"\n详细坐标信息:\n{json.dumps(named_points, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("没有找到具有逻辑名称的示教点。")

        elif query_scope == "all":
            logger.info(f"Processing 'query_points' with scope 'all'.")
            all_defined_points_list = []
            for p_key_iter in sorted(all_points_data.keys(), 
                              key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')):
                p_data_item = all_points_data[p_key_iter]
                is_defined = False
                if p_data_item.get("name"):
                    is_defined = True
                else:
                    for field, spec in POINT_FIELD_SCHEMA.items():
                        if field != "name" and p_data_item.get(field) != spec["default"] and p_data_item.get(field) is not None:
                            is_defined = True
                            break
                if is_defined:
                    point_with_id = p_data_item.copy()
                    point_with_id["_id"] = p_key_iter
                    all_defined_points_list.append(point_with_id)
                    any_point_found_successfully = True # Found at least one defined point
            
            if all_defined_points_list:
                response_parts.append(f"查询到 {len(all_defined_points_list)} 个已定义的示教点:")
                for point in all_defined_points_list:
                    p_key_display = point["_id"]
                    p_name_display = point.get("name", "(无逻辑名称)")
                    response_parts.append(f"  - {p_key_display}: {p_name_display}")
                final_query_results_data.extend(all_defined_points_list)
                # Optionally, to show full details in message:
                # response_parts.append(f"\n详细坐标信息:\n{json.dumps(all_defined_points_list, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("没有找到任何已定义的示教点。")

        elif query_scope == "specific" or (not query_scope and (isinstance(multi_point_ids_llm, list) and multi_point_ids_llm or user_provided_id)):
            logger.info(f"Processing 'query_points' with scope 'specific' (or inferred). IDs: {multi_point_ids_llm or user_provided_id}")
            
            identifiers_to_query = []
            if isinstance(multi_point_ids_llm, list) and multi_point_ids_llm:
                identifiers_to_query.extend(multi_point_ids_llm)
            elif user_provided_id:
                identifiers_to_query.append(user_provided_id)

            if identifiers_to_query:
                found_points_results_list = _find_points_by_identifiers(all_points_data, identifiers_to_query)
                for found_item in found_points_results_list:
                    uid = found_item["original_identifier"]
                    point_data = found_item["data"]
                    if point_data:
                        rpk_display = point_data.get("_id") # _find_points_by_identifiers adds _id
                        match_type_display = found_item.get("matched_by")
                        matched_id_display = found_item.get("matched_identifier")
                        queried_points_info.append(f"查询 '{uid}': 成功。匹配方式: {match_type_display} ('{matched_id_display}'), 槽位: {rpk_display}")
                        final_query_results_data.append(point_data) 
                        any_point_found_successfully = True
                    else:
                        queried_points_info.append(f"查询 '{uid}': 失败。未找到匹配的点。 (解析详情: {found_item.get('resolution_details', resolution_details)})")
            else: # Should not be reached if the outer condition was met, but as a safe guard.
                response_parts.append("LLM 未能识别要查询的点。请明确指定。")

            if queried_points_info:
                response_parts.extend(queried_points_info)
            
            if final_query_results_data: # If any points were actually found and data retrieved
                response_parts.append(f"\n查询到的点位详细信息:\n{json.dumps(final_query_results_data, ensure_ascii=False, indent=2)}")
            elif not response_parts: # Only if no specific messages were added above.
                response_parts.append("未能根据提供的标识符找到任何点。")

        else: 
            response_parts.append(f"收到查询请求，但查询范围 '{query_scope}' 不明确或参数不足。请指明是查询特定点、全部命名点还是所有点。")
            logger.warning(f"Teaching Node: query_points intent with unclear scope: '{query_scope}' or missing identifiers. LLM analysis: {llm_analysis}")

        # Set context for successful single point queries or if only one point resulted from any query type
        if any_point_found_successfully and len(final_query_results_data) == 1:
            single_result_data = final_query_results_data[0]
            ctx_resolved_pk = single_result_data.get("_id") # Should exist
            
            user_provided_id_for_ctx = user_provided_id # Default from single specific query
            if query_scope == "specific" and isinstance(multi_point_ids_llm, list) and len(multi_point_ids_llm) == 1:
                user_provided_id_for_ctx = multi_point_ids_llm[0]
            elif query_scope in ["all_named", "all"] or (isinstance(multi_point_ids_llm, list) and len(multi_point_ids_llm) > 1):
                # If it was a list all/all_named that resulted in one, or a multi-specific that resolved to one
                # Use its P_key or name for the context's "user_provided" field as a best guess.
                user_provided_id_for_ctx = single_result_data.get("name") or ctx_resolved_pk
            
            if ctx_resolved_pk:
                current_turn_aimessage_kwargs["last_successful_point_context"] = {
                    "user_provided": user_provided_id_for_ctx or ctx_resolved_pk, 
                    "resolved_p_key": ctx_resolved_pk,
                    "intent_of_last_op": "query_points"
                }
                logger.info(f"Set last_successful_point_context for query: {current_turn_aimessage_kwargs['last_successful_point_context']}")

        if not response_parts:
            response_parts.append("没有查询到任何结果或无法识别您的查询请求。")

    elif intent == "list_all_points" or intent == "list_points":
        if all_points_data:
            summary_list = []
            detailed_points_to_show = []
            sorted_p_keys = sorted(
                all_points_data.keys(),
                key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')
            )
            
            list_options = llm_analysis.get("list_options", {})
            wants_named_only = list_options.get("only_named", False)
            wants_detailed_coords = list_options.get("include_details", False)
            is_conditional_list = wants_named_only or wants_detailed_coords

            logger.info(f"List points processing: wants_named_only={wants_named_only}, wants_detailed_coords={wants_detailed_coords}, intent={intent}")

            if intent == "list_points" and is_conditional_list:
                for p_key in sorted_p_keys:
                    p_data = all_points_data[p_key]
                    p_name = p_data.get('name', '')
                    if wants_named_only and not p_name:
                        continue # Skip if only named points are requested and this one has no name
                    
                    status = f"逻辑名称: {p_name}" if p_name else "(未设置逻辑名称)"
                    summary_list.append(f"  - {p_key}: {status}")
                    point_with_id = p_data.copy()
                    point_with_id["_id"] = p_key
                    detailed_points_to_show.append(point_with_id)
                
                if detailed_points_to_show:
                    count_display = f"{len(detailed_points_to_show)} 个"
                    if wants_named_only:
                        count_display += "具有逻辑名称的"
                    response_parts.append(f"找到 {count_display}示教点:")
                    response_parts.append("\n".join(summary_list))
                    if wants_detailed_coords:
                        response_parts.append(f"\n详细信息:\n{json.dumps(detailed_points_to_show, ensure_ascii=False, indent=2)}")
                else:
                    if wants_named_only:
                        response_parts.append("没有找到具有逻辑名称的示教点。")
                    else:
                        response_parts.append("没有找到符合条件的示教点。") # Generic if not specifically only_named
            else: # Handles list_all_points or list_points without specific conditions from LLM
                for p_key in sorted_p_keys:
                    p_data = all_points_data[p_key]
                    p_name = p_data.get('name', '')
                    status = f"逻辑名称: {p_name}" if p_name else "(未设置逻辑名称)"
                    summary_list.append(f"  - {p_key}: {status}")
                
                response_parts.append("当前所有示教点槽位状态:\n" + "\n".join(summary_list))
                defined_points_details = {
                    k:v for k,v in sorted(all_points_data.items())
                    if v.get("name") or any(
                        val is not None and val != POINT_FIELD_SCHEMA[field]["default"]
                        for field, val in v.items() if field != "name"
                    )
                }
            if defined_points_details:
                    response_parts.append(
                        f"\n\n已定义点位详细信息 (P-Key: 数据):\n{json.dumps(defined_points_details, ensure_ascii=False, indent=2)}"
                    )
        else:
            response_parts.append("当前没有保存任何示教点信息。")

    elif intent == "save_update_point":
        user_provided_target_id = llm_analysis.get("user_provided_target_identifier")
        resolved_target_p_key = llm_analysis.get("resolved_target_p_key")
        llm_params = llm_analysis.get("parameters")

        if not user_provided_target_id or not isinstance(llm_params, dict):
            response_parts.append(f"无法保存/更新点: LLM 未能提取目标标识符或有效参数。详情: {resolution_details}")
        else:
            action = "保存"
            existing_data_for_slot = None
            slot_to_use = resolved_target_p_key

            if resolved_target_p_key and resolved_target_p_key in all_points_data:
                action = "更新"
                existing_data_for_slot = all_points_data.get(resolved_target_p_key)
                logger.info(
                    f"{action}现有示教点。用户标识: '{user_provided_target_id}', "
                    f"解析后P-Key: '{resolved_target_p_key}'. LLM详情: {resolution_details}. 参数: {llm_params}"
                )
            elif resolved_target_p_key:
                logger.warning(
                    f"LLM 解析到 P-Key '{resolved_target_p_key}' (用户标识: '{user_provided_target_id}'), "
                    f"但此 P-Key 不在当前数据中。将尝试作为新点处理。详情: {resolution_details}"
                )
                slot_to_use = None

            final_logical_name = llm_params.get("name")
            if not final_logical_name:
                if action == "更新" and existing_data_for_slot and existing_data_for_slot.get("name"):
                    final_logical_name = existing_data_for_slot.get("name")
                elif action == "保存" and not re.fullmatch(r"P\d+", user_provided_target_id, re.IGNORECASE):
                    final_logical_name = user_provided_target_id
            
            if final_logical_name:
                llm_params["name"] = final_logical_name

            point_data_to_save = _apply_schema_and_defaults_to_llm_params(llm_params, existing_data_for_slot)

            if not slot_to_use: # Implies a new point or a point LLM resolved to a P_Key not in data
                if not point_data_to_save.get("name"):
                    response_parts.append(
                        f"无法保存新点: 新点需要一个逻辑名称，但未提供或无法从用户输入 '{user_provided_target_id}' 派生。"
                        f"LLM解析详情: {resolution_details}"
                    )
                    slot_to_use = "NO_NAME_FOR_NEW_POINT" # Error condition
                else:
                    # Check for duplicate logical name IF IT'S A NEW POINT
                    for p_key_iter, p_data_iter in all_points_data.items():
                        if p_data_iter.get("name") == point_data_to_save.get("name"):
                            response_parts.append(
                                f"错误: 逻辑名称 '{point_data_to_save.get('name')}' 已存在于槽位 {p_key_iter}。"
                                f"无法用重复的逻辑名称创建新点。"
                            )
                            slot_to_use = "DUPLICATE_LOGICAL_NAME" # Error condition
                            break
                    if slot_to_use not in ["DUPLICATE_LOGICAL_NAME", "NO_NAME_FOR_NEW_POINT"]:
                        slot_to_use = _find_empty_slot_key(all_points_data)
                        if slot_to_use:
                            action = "保存" # Confirm action is save for new slot
                            logger.info(
                                f"分配空槽位 '{slot_to_use}' 给新示教点 '{point_data_to_save.get('name')}'."
                                f"原用户标识: '{user_provided_target_id}'. LLM解析: {resolution_details}"
                            )
                        else:
                            response_parts.append(
                                f"无法保存新示教点 '{point_data_to_save.get('name')}'."
                                f"用户标识: '{user_provided_target_id}'."
                            )
                            slot_to_use = "NO_EMPTY_SLOT" # Error condition
            elif llm_params.get("name") is not None: # Existing point, but name is being changed in parameters
                new_name_to_check = llm_params.get("name")
                for p_key_iter, p_data_iter in all_points_data.items():
                    if p_key_iter != slot_to_use and p_data_iter.get("name") == new_name_to_check:
                        response_parts.append(
                            f"错误: 逻辑名称 '{new_name_to_check}' 已被槽位 {p_key_iter} 使用."
                            f"无法更新点 '{slot_to_use}' 为已存在的逻辑名称."
                        )
                        slot_to_use = "DUPLICATE_LOGICAL_NAME_ON_UPDATE" # Error condition
                        break
            
            if slot_to_use and slot_to_use not in ["DUPLICATE_LOGICAL_NAME", "NO_NAME_FOR_NEW_POINT", "NO_EMPTY_SLOT", "DUPLICATE_LOGICAL_NAME_ON_UPDATE"]:
                all_points_data[slot_to_use] = point_data_to_save
                if _save_teaching_points(all_points_data):
                    saved_name_display = point_data_to_save.get('name', slot_to_use)
                    response_parts.append(
                        f"示教点 '{saved_name_display}' (槽位: {slot_to_use}) 已成功{action}。"
                        f"用户标识: '{user_provided_target_id}'. LLM解析: {resolution_details}"
                    )
                    point_display_data = {slot_to_use: point_data_to_save}
                    response_parts.append(
                        f"{action}后 {slot_to_use} 的数据:\\n"
                        f"{json.dumps(point_display_data, ensure_ascii=False, indent=2)}"
                    )
                    current_turn_aimessage_kwargs["last_successful_point_context"] = {
                        "user_provided": user_provided_target_id,
                        "resolved_p_key": slot_to_use,
                        "intent_of_last_op": "save_update_point"
                    }
                else:
                    response_parts.append(
                        f"{action.capitalize()}示教点 '{point_data_to_save.get('name', slot_to_use)}' 失败: "
                        f"无法写入文件。用户标识: '{user_provided_target_id}'."
                    )
            elif not response_parts:
                 response_parts.append(
                     f"无法{action}点 '{user_provided_target_id}'。请检查日志。LLM详情: {resolution_details}"
                 )

    elif intent == "delete_point":
        user_provided_id = llm_analysis.get("user_provided_target_identifier")
        resolved_p_key_to_delete = llm_analysis.get("resolved_target_p_key")

        if not resolved_p_key_to_delete: # If LLM still didn't resolve, despite prompt instructions.
            # This implies LLM provided `delete_point` intent but no `resolved_target_p_key`.
            # And it was not caught as `clarify_ambiguous_instruction`.
            logger.warning(f"delete_point intent without resolved_target_p_key. User ID: '{user_provided_id}', Details: {resolution_details}")
            response_parts.append(f"无法找到您指定要删除的点 '{user_provided_id}'。请确保点存在或您的表述清晰。LLM解析: {resolution_details}")
        elif resolved_p_key_to_delete in all_points_data:
            deleted_point_name_display = all_points_data[resolved_p_key_to_delete].get("name", resolved_p_key_to_delete)
            context_user_provided_id = user_provided_id
            context_resolved_p_key = resolved_p_key_to_delete
            
            empty_point_template = {key: spec["default"] for key, spec in POINT_FIELD_SCHEMA.items()}
            empty_point_template["name"] = None 
            all_points_data[resolved_p_key_to_delete] = empty_point_template
            
            if _save_teaching_points(all_points_data):
                response_parts.append(
                    f"示教点 '{deleted_point_name_display}' (槽位 {resolved_p_key_to_delete}) 的内容已被清除。"
                    f"该槽位可复用。用户标识: '{user_provided_id}'. LLM解析: {resolution_details}"
                )
                current_turn_aimessage_kwargs["last_successful_point_context"] = {
                    "user_provided": context_user_provided_id,
                    "resolved_p_key": context_resolved_p_key,
                    "intent_of_last_op": "delete_point"
                }
            else:
                response_parts.append(
                    f"清除点 '{deleted_point_name_display}' (来自用户标识 '{user_provided_id}') 失败: "
                    f"无法写入文件。LLM解析: {resolution_details}"
                )
        else:
            response_parts.append(
                f"点 {resolved_p_key_to_delete} (来自用户标识 '{user_provided_id}') 未找到，无法删除。"
                f"LLM解析: {resolution_details}"
            )
    
    elif intent == "unclear_intent" or intent == "unsupported_operation":
        reason = llm_analysis.get("reason", resolution_details if intent == "unclear_intent" else "操作不被支持或无法理解。")
        response_parts.append(f"无法处理您的请求: {reason}")

    if not response_parts:
        response_parts.append(
            f"我不太确定如何处理您的示教点请求。LLM分析意图为：{intent if intent else '未知'}。细节：{resolution_details}"
        )
        logger.warning(f"Fallback: Unhandled intent '{intent}' or empty response_parts. LLM analysis was {llm_analysis}")
        if all_points_data:
            saved_points_summary = []
            empty_slot_keys = []
            sorted_p_keys = sorted(
                all_points_data.keys(),
                key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')
            )
            for p_key in sorted_p_keys:
                p_data = all_points_data[p_key]
                p_name = p_data.get('name', '')
                # Check if point has a name OR any field is different from its default
                if p_name or any(
                    val is not None and val != POINT_FIELD_SCHEMA[field]["default"]
                    for field, val in p_data.items() if field != "name"
                ):
                    saved_points_summary.append(f"  - {p_key} (逻辑名称: {p_name if p_name else '(未设置)'})")
                else:
                    empty_slot_keys.append(p_key)
            
            # Add P_N keys that are not in all_points_data at all
            for i in range(1, 101): 
                k = f"P{i}"
                if k not in all_points_data and k not in empty_slot_keys:
                    empty_slot_keys.append(k)
            
            empty_slot_keys.sort(key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf'))
            
            response_parts.append("\n已定义/使用中的点槽位:\n" + ("\n".join(saved_points_summary) if saved_points_summary else "  (无)"))
            response_parts.append(
                "可用的空槽位 (示例):\\n  " + 
                (', '.join(empty_slot_keys[:10]) + ("..." if len(empty_slot_keys) > 10 else "") if empty_slot_keys else " (无)")
            )
        else:
            response_parts.append("\n当前，工作区中没有示教点文件或文件为空。")

    final_response_content = "\n".join(filter(None, response_parts))
    logger.info(f"Teaching Node: Final response: '{final_response_content[:300]}...' AIMessage kwargs: {current_turn_aimessage_kwargs}")
    return {"messages": [AIMessage(content=final_response_content, additional_kwargs=current_turn_aimessage_kwargs)]} 