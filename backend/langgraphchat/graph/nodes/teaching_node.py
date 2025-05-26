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

    # New System Prompt
    new_system_prompt_template = f"""你是一个专业的机器人示教点管理助手。
你的任务是分析【用户最新的输入】，并结合【最近的对话历史】来理解用户的意图，然后输出一个结构化的JSON对象。

【重要：指代消解】
当用户使用代词（如"它"、"他的"、"那个点"）或模糊引用时，你必须仔细查看【最近的对话历史】，特别是【上一个用户输入】和【上一个AI的回复】，来确定这些指代具体指向哪个已定义的示教点（P_Key，如P1，或逻辑名称，如"入口点"）。
- 如果你能成功解析指代，请在输出的JSON中将 "resolved_target_p_key" 设置为解析到的 P_Key。
- 如果指代不明或无法从上下文中解析，请将 "resolved_target_p_key" 设置为 null，并在 "resolution_details" 中详细说明原因。

【现有示教点参考】：
{existing_points_str}

【示教点参数规范】：
{schema_str}

【你的JSON输出格式要求】：
请严格按照以下字段输出JSON对象：
- "intent": (字符串) 用户意图，例如："save_update_point", "query_point", "delete_point", "list_points", "rename_point", "clarify_ambiguous_instruction", "unsupported_operation"。
- "user_provided_target_identifier": (字符串或null) 用户输入的原始点标识符（名称、P_Key或代词）。
- "resolved_target_p_key": (字符串或null) 解析后的目标点P_Key。如果是新点或是无法解析的指代，则为null。
- "resolution_details": (字符串) 你是如何解析（或未能解析）指代的思考过程和详细解释。
- "parameters": (对象或null) 用户要求修改或保存的点参数，例如 {{"name": "新名称", "z_pos": 100.0}}。只包含用户明确提及的字段。
- "target_identifiers_for_multi_point_ops": (字符串列表或null) 适用于多点操作（如批量删除）的目标标识符列表。

【处理流程】：
1. 分析【用户最新的输入】。
2. 参考【最近的对话历史】进行指代消解。
3. 根据分析结果填充上述JSON字段。

示例1：成功解析指代
  对话历史:
    用户: "查询P1"
    AI: "P1点的数据是 X:10, Y:20, Z:30，名称是'初始点'。"
  用户最新的输入: "把它Z轴改为50，并重命名为'新起点'"
  你的JSON输出:
  {{
    "intent": "save_update_point",
    "user_provided_target_identifier": "它",
    "resolved_target_p_key": "P1",
    "resolution_details": "代词"它"根据上一轮对话上下文明确指向P1。",
    "parameters": {{ "z_pos": 50.0, "name": "新起点" }}
  }}

示例2：指代不明
  对话历史:
    用户: "列出所有点"
    AI: "当前有点位P1 (入口), P2 (出口)。"
  用户最新的输入: "删除它"
  你的JSON输出:
  {{
    "intent": "clarify_ambiguous_instruction", 
    "user_provided_target_identifier": "它",
    "resolved_target_p_key": null,
    "resolution_details": "代词"它"指代不明，因为上一轮对话提及了多个点 (P1, P2)，无法确定用户意图删除哪一个。",
    "parameters": null
  }}
"""

    # Construct the list of messages for the LLM
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
    if intent == "query_points" or intent == "query_point":
        # Unified query processing for both single and multi-point queries
        queried_points_info = [] # Collects info about each queried point
        final_query_results_data = []
        any_point_found_successfully = False

        # Check for multi-point query first
        multi_point_ids_llm = llm_analysis.get("target_identifiers_for_multi_point_ops")
        user_provided_id = llm_analysis.get("user_provided_target_identifier")
        resolved_p_key = llm_analysis.get("resolved_target_p_key")
        
        # Enhanced logic: If user_provided_id suggests "all named points" but no specific resolution
        is_all_named_points_query = (
            user_provided_id and 
            any(phrase in user_provided_id.lower() for phrase in [
                "all", "these points", "points all", "所有", "全部", 
                "all which have names", "all that have names", "有名字的点"
            ]) and
            not resolved_p_key and 
            not multi_point_ids_llm
        )
        
        if is_all_named_points_query:
            logger.info(f"Detected 'all named points' query from user_provided_id: '{user_provided_id}'")
            # Convert to list all named points with coordinates
            named_points = []
            for p_key in sorted(all_points_data.keys(), 
                              key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')):
                p_data = all_points_data[p_key]
                if p_data.get('name'):  # Only points with logical names
                    point_with_id = p_data.copy()
                    point_with_id["_id"] = p_key
                    named_points.append(point_with_id)
                    final_query_results_data.append(point_with_id)
                    any_point_found_successfully = True
            
            if named_points:
                response_parts.append(f"查询到 {len(named_points)} 个具有逻辑名称的示教点:")
                for point in named_points:
                    p_key = point["_id"]
                    p_name = point.get("name", "")
                    response_parts.append(f"  - {p_key}: {p_name}")
                response_parts.append(f"\n详细坐标信息:\n{json.dumps(final_query_results_data, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("没有找到具有逻辑名称的示教点。")
                
        elif isinstance(multi_point_ids_llm, list) and multi_point_ids_llm:
            logger.info(f"Processing multi-point query for: {multi_point_ids_llm}")
            found_points_list = _find_points_by_identifiers(all_points_data, multi_point_ids_llm)
            for found_item in found_points_list:
                uid = found_item["original_identifier"]
                rpk = found_item["data"].get("_id") if found_item["data"] else None
                r_details = f"Matched by: {found_item['matched_by']}" if rpk else "No match found."
                queried_points_info.append(f"查询 '{uid}': {r_details}")
                if rpk and rpk in all_points_data:
                    final_query_results_data.append(all_points_data[rpk])
                    any_point_found_successfully = True
            
            response_parts.extend(queried_points_info)
            if final_query_results_data:
                response_parts.append(f"查询到的点位信息:\n{json.dumps(final_query_results_data, ensure_ascii=False, indent=2)}")
                
        elif user_provided_id: # Single point query
            if resolved_p_key and resolved_p_key in all_points_data:
                queried_points_info.append(f"查询 '{user_provided_id}' (解析为 {resolved_p_key}): {resolution_details}")
                final_query_results_data.append(all_points_data[resolved_p_key])
                any_point_found_successfully = True
            else:
                queried_points_info.append(f"查询 '{user_provided_id}' 失败: {resolution_details}")
            
            response_parts.extend(queried_points_info)
            if final_query_results_data:
                response_parts.append(f"查询到的点位信息:\n{json.dumps(final_query_results_data, ensure_ascii=False, indent=2)}")
        else:
            response_parts.append("LLM 未能识别要查询的点。请明确指定。")

        # Set context for successful single point queries
        if len(final_query_results_data) == 1 and any_point_found_successfully:
            single_result_data = final_query_results_data[0]
            ctx_resolved_pk = single_result_data.get("_id")
            user_provided_id_for_ctx = user_provided_id or ctx_resolved_pk
            
            if ctx_resolved_pk:
                current_turn_aimessage_kwargs["last_successful_point_context"] = {
                    "user_provided": user_provided_id_for_ctx,
                    "resolved_p_key": ctx_resolved_pk,
                    "intent_of_last_op": "query_points"
                }
                logger.info(f"Set last_successful_point_context for query: {current_turn_aimessage_kwargs['last_successful_point_context']}")
        
        if not response_parts:
            response_parts.append("没有指定要查询的点，或无法识别您的查询请求。")

    elif intent == "list_all_points" or intent == "list_points":
        if all_points_data:
            summary_list = []
            detailed_points_to_show = []
            sorted_p_keys = sorted(
                all_points_data.keys(),
                key=lambda x: int(x[1:]) if x.startswith('P') and x[1:].isdigit() else float('inf')
            )
            
            # Check if this is a conditional query (list_points) vs complete listing (list_all_points)
            if intent == "list_points":
                # Enhanced logic for conditional listing based on user criteria
                user_request = llm_analysis.get("user_provided_target_identifier", "").lower()
                resolution_details = llm_analysis.get("resolution_details", "")
                
                # Determine what kind of filtering the user wants
                wants_named_points = any(keyword in user_request for keyword in ["name", "named", "有名字", "逻辑名称"])
                wants_detailed_coords = any(keyword in resolution_details for keyword in ["坐标信息", "coordinate", "详细", "detail"])
                
                logger.info(f"Enhanced list_points processing: wants_named_points={wants_named_points}, wants_detailed_coords={wants_detailed_coords}")
                
                if wants_named_points or wants_detailed_coords:
                    # Filter points that have logical names and collect their detailed data
                    for p_key in sorted_p_keys:
                        p_data = all_points_data[p_key]
                        p_name = p_data.get('name', '')
                        if p_name:  # Only include points with logical names
                            status = f"逻辑名称: {p_name}"
                            summary_list.append(f"  - {p_key}: {status}")
                            # Add full point data for detailed display
                            point_with_id = p_data.copy()
                            point_with_id["_id"] = p_key
                            detailed_points_to_show.append(point_with_id)
                    
                    if detailed_points_to_show:
                        response_parts.append(f"找到 {len(detailed_points_to_show)} 个具有逻辑名称的示教点:")
                        response_parts.append("\n".join(summary_list))
                        if wants_detailed_coords:
                            response_parts.append(f"\n详细坐标信息:\n{json.dumps(detailed_points_to_show, ensure_ascii=False, indent=2)}")
                    else:
                        response_parts.append("没有找到具有逻辑名称的示教点。")
                else:
                    # Fallback to basic listing for other types of list_points requests
                    for p_key in sorted_p_keys:
                        p_data = all_points_data[p_key]
                        p_name = p_data.get('name', '')
                        status = f"逻辑名称: {p_name}" if p_name else "(未设置逻辑名称)"
                        summary_list.append(f"  - {p_key}: {status}")
                        if p_name or any(val is not None and val != POINT_FIELD_SCHEMA[field]["default"] for field, val in p_data.items() if field != "name"):
                            point_with_id = p_data.copy()
                            point_with_id["_id"] = p_key
                            detailed_points_to_show.append(point_with_id)
                    
                    response_parts.append("已定义的示教点:")
                    response_parts.append("\n".join(summary_list))
                    if detailed_points_to_show:
                        response_parts.append(f"\n详细信息:\n{json.dumps(detailed_points_to_show, ensure_ascii=False, indent=2)}")
            else:
                # Original list_all_points logic
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
            is_potentially_ambiguous_ref = user_provided_target_id.lower() in ["他", "它", "他的", "她的", "它的", "那个", "这个"] or (
                "ambiguous" in resolution_details.lower() or
                "no specific point context" in resolution_details.lower() or
                "could not resolve" in resolution_details.lower() or
                "unclear which point" in resolution_details.lower()
            )
            
            if not resolved_target_p_key and is_potentially_ambiguous_ref:
                clarification_message = (
                    f"""您想对"{user_provided_target_id}"进行操作，但我未能明确它具体指向哪个已定义的点。
{resolution_details} 请提供一个已存在的点位名称或编号，
或者如果您想创建一个新点，请使用一个唯一的名称。"""
                )
                logger.info(
                    f"Teaching Node: Ambiguous reference for '{user_provided_target_id}' in save_update_point intent. "
                    f"Asking for clarification. LLM details: {resolution_details}"
                )
                return {"messages": [AIMessage(content=clarification_message, additional_kwargs=current_turn_aimessage_kwargs)]}
            
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
                elif action == "保存" and not re.fullmatch(r"P\d+", user_provided_target_id, re.IGNORECASE) and \
                     not is_potentially_ambiguous_ref:
                    final_logical_name = user_provided_target_id
            
            if final_logical_name:
                llm_params["name"] = final_logical_name
            else:
                # Condition: new point (slot_to_use is None or resolved_target_p_key was not in all_points_data)
                # and no final_logical_name could be derived.
                if not slot_to_use or (resolved_target_p_key and resolved_target_p_key not in all_points_data):
                    response_parts.append(
                        f"""无法{action}点: 新点需要逻辑名称，但未提供或无法从"{user_provided_target_id}"派生。
{resolution_details}"""
                    )
                    slot_to_use = "NO_NAME_FOR_NEW_POINT"

            point_data_to_save = _apply_schema_and_defaults_to_llm_params(llm_params, existing_data_for_slot)

            if not slot_to_use: # If slot_to_use is still None (it's a new point needing a slot)
                if not point_data_to_save.get("name"):
                    response_parts.append(
                        f"无法保存点: 新点需要一个逻辑名称。用户标识: '{user_provided_target_id}'. "
                        f"LLM解析: {resolution_details}"
                    )
                    slot_to_use = "NO_NAME_FOR_NEW_POINT"
                else:
                    for p_key_iter, p_data_iter in all_points_data.items():
                        if p_data_iter.get("name") == point_data_to_save.get("name"):
                            response_parts.append(
                                f"错误: 逻辑名称 '{point_data_to_save.get('name')}' 已存在于槽位 {p_key_iter}。"
                                f"无法用重复的逻辑名称创建新点。"
                            )
                            slot_to_use = "DUPLICATE_LOGICAL_NAME"
                            break
                    if slot_to_use not in ["DUPLICATE_LOGICAL_NAME", "NO_NAME_FOR_NEW_POINT"]:
                        slot_to_use = _find_empty_slot_key(all_points_data)
                        if slot_to_use:
                            action = "保存"
                            logger.info(
                                f"分配空槽位 '{slot_to_use}' 给新示教点 '{point_data_to_save.get('name')}'. "
                                f"原用户标识: '{user_provided_target_id}'. LLM解析: {resolution_details}"
                            )
                        else:
                            response_parts.append(
                                f"无法{action}示教点 '{point_data_to_save.get('name')}': 所有槽位已满。"
                                f"用户标识: '{user_provided_target_id}'."
                            )
                            slot_to_use = "NO_EMPTY_SLOT"
            
            if slot_to_use and slot_to_use not in ["DUPLICATE_LOGICAL_NAME", "NO_NAME_FOR_NEW_POINT", "NO_EMPTY_SLOT"]:
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

        if not user_provided_id:
            response_parts.append("请指定要删除的点标识符。LLM未能提供。")
        else:
            is_potentially_ambiguous_ref_delete = user_provided_id.lower() in ["他", "它", "他的", "她的", "它的", "那个", "这个"] or (
                "ambiguous" in resolution_details.lower() or
                "no specific point context" in resolution_details.lower() or
                "could not resolve" in resolution_details.lower() or
                "unclear which point" in resolution_details.lower()
            )
            if not resolved_p_key_to_delete and is_potentially_ambiguous_ref_delete:
                clarification_message = (
                    f"""您想删除"{user_provided_id}"，但我未能明确它具体指向哪个已定义的点。
{resolution_details} 请提供一个已存在的点位名称或编号。"""
                )
                logger.info(
                    f"Teaching Node: Ambiguous reference for deletion '{user_provided_id}'. "
                    f"Asking for clarification. LLM details: {resolution_details}"
                )
                return {"messages": [AIMessage(content=clarification_message, additional_kwargs=current_turn_aimessage_kwargs)]}
            elif not resolved_p_key_to_delete:
                response_parts.append(f"无法找到您指定要删除的点'{user_provided_id}'。LLM解析: {resolution_details}")
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