import logging
import yaml
import json
import re
from typing import Dict, Any, List, Optional, Union, Tuple

from ..agent_state import AgentState
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

TEACHING_POINTS_FILE = "/workspace/test_robot_flow_output_deepseek_interactive/teaching.yaml"

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

    ai_response_history_str = "(无最近AI回复)"
    user_request_history_str = "(无最近用户请求)"
    
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
                f"AI回复{i+1}: {msg[:200]}..." if len(msg) > 200 else f"AI回复{i+1}: {msg}"
                for i, msg in enumerate(recent_ai_messages)
            ])
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
    - 对于 `list_points`，可以包含 `list_options` 对象，例如 `{{"scope": "all_named", "include_details": true}}`。
        - `scope` 可以是 "all", "all_named"。
        - `include_details` (boolean, optional): 是否在回复中包含详细坐标。
- target_identifiers_for_multi_point_ops: (List of Strings or Null) 仅用于 `query_points` (当 `query_scope` 为 "specific" 且需要查询多个特定点时) 或 `delete_point` (当需要批量删除时)，用户指定的多个点标识符列表。

【意图选择规则与指导】
1.  **`save_update_point`**: 创建或修改点。
2.  **`delete_point`**: 删除点。
3.  **`query_points`**: 查询特定点、所有点、所有命名点的【详细信息】。LLM应决定`query_scope`。
4.  **`list_points`**: 列出点的【概览信息】（通常是P_Key和逻辑名称）。LLM应在`parameters.list_options`中设置`scope` (e.g., "all", "all_named") 和可选的`include_details`。
5.  **`clarify_ambiguous_instruction`**: 当指令不明确或无法安全解析目标点时。

【重要：指代消解、模糊匹配与歧义处理】
(内容同前，强调无法确切匹配时，对于save_update (更新) 和 delete，必须转为clarify_ambiguous_instruction)
- **对于意图 `save_update_point` (当更新一个现有机器人示教点时，而不是用新名称创建一个新点) 和 `delete_point`，必须在JSON中提供一个非空的 `resolved_target_p_key`。如果你无法为这些意图解析出目标点（即无法找到确切匹配），则必须将 `intent` 设置为 `clarify_ambiguous_instruction`。**

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
    intermediate_results: str,
    generated_json_data_str: str,
    logger_object: logging.Logger
) -> str:
    """
    Invokes an LLM to polish the raw intermediate results into a natural, user-facing response,
    and appends a pre-generated JSON string if provided.
    """
    natural_language_prompt_template = f"""原始用户问题:
{original_user_query}

已进行的分析和决策 (JSON格式):
{step_a_analysis}

根据上述分析和决策，以及执行工具/查询后得到的初步结果如下:
{intermediate_results}

请根据以上所有信息，生成一个友好、简洁且直接回答原始用户问题的【自然语言回复】。
不要包含JSON代码块，除非用户明确要求纯JSON。专注于对话式的回复。
例如："答案如下：..."， "好的，已经为您处理完成。"， "查询结果是：..."
"""

    natural_language_response = ""

    try:
        # 1. Generate Natural Language Response
        nl_messages = [HumanMessage(content=natural_language_prompt_template)]
        nl_llm_response = await llm.ainvoke(nl_messages)
        natural_language_response = nl_llm_response.content.strip()
        logger_object.info(f"Polishing - Natural Language LLM response: {natural_language_response}")

    except Exception as e:
        logger_object.error(f"Error invoking LLM for polishing natural language: {e}")
        if not natural_language_response:
             return f"处理自然语言回复时出现错误。原始信息：\\n{intermediate_results}"

    # 3. Combine the responses
    if generated_json_data_str and generated_json_data_str.strip() and generated_json_data_str.strip() != '""':
        try:
            final_polished_content = f"{natural_language_response}\\n\\n```json\\n{generated_json_data_str.strip()}\\n```"
            logger_object.info(f"Polishing - Appended provided JSON string: {generated_json_data_str.strip()[:100]}...")
        except json.JSONDecodeError as e:
            logger_object.warning(f"Polishing - provided generated_json_data_str ('{generated_json_data_str.strip()[:100]}...') was not valid JSON: {e}. Not appending.")
            final_polished_content = natural_language_response
    else:
        final_polished_content = natural_language_response
        logger_object.info("Polishing - No valid provided JSON string to append or it was explicitly empty.")
        
    logger_object.info(f"Polishing - Combined final response: {final_polished_content[:300]}...")
    return final_polished_content


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
        clarification_message = resolution_details if resolution_details and len(resolution_details) > 10 else f"抱歉，我不太理解您的意思。{resolution_details} 您能说得更具体一些吗？"
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
                response_parts.append(f"查询到 {len(named_points)} 个具有逻辑名称的示教点:")
                for point in named_points:
                    response_parts.append(f"  - {point['_id']}: {point.get('name', '')}")
                final_data_for_json_output.extend(named_points)
                response_parts.append(f"\n查询到的点位详细信息:\n{json.dumps(final_data_for_json_output, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("没有找到具有逻辑名称的示教点。")

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
                response_parts.append(f"查询到 {len(all_defined_points_list)} 个已定义的示教点:")
                for point in all_defined_points_list:
                    response_parts.append(f"  - {point['_id']}: {point.get('name', '(无逻辑名称)')}")
                final_data_for_json_output.extend(all_defined_points_list)
                response_parts.append(f"\n查询到的点位详细信息:\n{json.dumps(final_data_for_json_output, ensure_ascii=False, indent=2)}")
            else:
                response_parts.append("没有找到任何已定义的示教点。")

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
                        queried_points_info.append(f"查询 '{uid}': 成功。匹配方式: {found_item.get('matched_by')} ('{found_item.get('matched_identifier')}'), 槽位: {point_data.get('_id')}")
                        current_query_results.append(point_data) 
                        any_point_found_successfully = True
                    else:
                        queried_points_info.append(f"查询 '{uid}': 失败。未找到匹配的点。 (解析详情: {found_item.get('resolution_details', resolution_details)})")
                
                if queried_points_info:
                    response_parts.extend(queried_points_info)
                if current_query_results:
                    final_data_for_json_output.extend(current_query_results)
                    response_parts.append(f"\n查询到的点位详细信息:\n{json.dumps(final_data_for_json_output, ensure_ascii=False, indent=2)}")
                elif not response_parts:
                    response_parts.append("未能根据提供的标识符找到任何点。")
            else:
                response_parts.append("LLM 未能识别要查询的点。请明确指定。")

        else:
            response_parts.append(f"收到查询请求，但查询范围 '{query_scope}' 不明确或参数不足。")
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
        if not response_parts: response_parts.append("没有查询到任何结果或无法识别您的查询请求。")
    
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
                count_display_prefix = f"{len(points_for_display_and_json)} 个"
                if list_scope == "all_named": count_display_prefix += "具有逻辑名称的"
                elif list_scope == "all": count_display_prefix += "已定义的"
                response_parts.append(f"找到 {count_display_prefix}示教点:")

                for point in points_for_display_and_json:
                    summary_list.append(f"  - {point['_id']}: {point.get('name', '(无逻辑名称)')}")
                response_parts.append("\n".join(summary_list))
                
                final_data_for_json_output.extend(points_for_display_and_json)

                if wants_detailed_coords:
                    response_parts.append(f"\n详细信息:\n{json.dumps(points_for_display_and_json, ensure_ascii=False, indent=2)}")
            else:
                if list_scope == "all_named": response_parts.append("没有找到具有逻辑名称的示教点。")
                else: response_parts.append("没有找到任何已定义的示教点。")
        else:
            response_parts.append("当前没有保存任何示教点信息。")

    elif intent == "save_update_point":
        user_provided_target_id = llm_analysis.get("user_provided_target_identifier")
        resolved_target_p_key = llm_analysis.get("resolved_target_p_key")
        llm_params = llm_analysis.get("parameters")

        if not user_provided_target_id or not isinstance(llm_params, dict):
            response_parts.append(f"无法保存/更新点: LLM 未能提取目标标识符或有效参数。详情: {resolution_details}")
        else:
            action = "保存" # Default action
            existing_data_for_slot = None
            slot_to_use_or_error = resolved_target_p_key # Initial candidate from LLM

            # Determine initial action and existing_data based on resolved_target_p_key
            if resolved_target_p_key and resolved_target_p_key in all_points_data:
                action = "更新"
                existing_data_for_slot = all_points_data[resolved_target_p_key]
                logger.info(f"意图: {action}现有示教点 '{resolved_target_p_key}'. 用户提供: '{user_provided_target_id}'.")
            elif resolved_target_p_key: # P_Key provided by LLM but not in all_points_data
                action = "保存" # Treat as saving to a new, specific P_Key if valid
                logger.info(f"意图: {action}到LLM建议的新槽位 '{resolved_target_p_key}'. 用户提供: '{user_provided_target_id}'.")
            else: # No P_Key from LLM, must be a new point needing an empty slot
                action = "保存"
                slot_to_use_or_error = None # Explicitly set to None, needs slot finding
                logger.info(f"意图: {action}新点. 用户提供: '{user_provided_target_id}'.")

            # Determine final logical name to be saved/updated
            final_logical_name = llm_params.get("name")
            if not final_logical_name: # If LLM didn't extract a name directly
                if action == "更新" and existing_data_for_slot and existing_data_for_slot.get("name"):
                    final_logical_name = existing_data_for_slot.get("name") # Keep existing if not changing
                # If saving a new point, and user_id is not P-like, and resolved_p_key was not a name either:
                elif action == "保存" and not (slot_to_use_or_error and re.fullmatch(r"P\d+", slot_to_use_or_error, re.IGNORECASE)) and not re.fullmatch(r"P\d+", user_provided_target_id, re.IGNORECASE):
                    final_logical_name = user_provided_target_id # Use user_id as name
            
            if final_logical_name: # Ensure llm_params reflects the name to be used for schema validation
                llm_params["name"] = final_logical_name
            
            point_data_to_save = _apply_schema_and_defaults_to_llm_params(llm_params, existing_data_for_slot)

            # --- Logic for 'action == "保存"' ---
            if action == "保存":
                if not point_data_to_save.get("name"):
                    response_parts.append(f"无法保存新点: 新点必须有一个逻辑名称。用户输入 '{user_provided_target_id}' 未能提供有效名称。")
                    slot_to_use_or_error = "ERROR_SAVE_NO_NAME"
                else:
                    # Check for duplicate logical name if we are assigning a name
                    for p_key_iter, p_data_iter in all_points_data.items():
                        # If we are trying to use a specific P_Key (slot_to_use_or_error is set from resolved_target_p_key)
                        # and that P_Key is the one we are checking, skip (no self-conflict on name for this slot)
                        if slot_to_use_or_error and p_key_iter == slot_to_use_or_error:
                            continue 
                        if p_data_iter.get("name") == point_data_to_save.get("name"):
                            response_parts.append(f"错误: 逻辑名称 '{point_data_to_save.get('name')}' 已被槽位 {p_key_iter} 使用。")
                            slot_to_use_or_error = "ERROR_SAVE_DUPLICATE_NAME"; break
                    
                    if not (slot_to_use_or_error and slot_to_use_or_error.startswith("ERROR_")): # If no duplicate name error
                        if slot_to_use_or_error: # This means resolved_target_p_key was set and was not in all_points_data
                            # We are trying to save to a specific P_Key suggested by LLM.
                            # We need to ensure this P_Key isn't somehow already "taken" by an unnamed point with data
                            # (though _find_empty_slot_key should handle truly empty ones).
                            # For now, assume if it's not in all_points_data, it's available or will overwrite if it was an empty dict placeholder.
                            logger.info(f"将保存到LLM指定的、当前不存在的槽位 '{slot_to_use_or_error}' (名称: '{point_data_to_save.get('name')}').")
                        else: # No specific P_Key from LLM, find an empty slot
                            slot_to_use_or_error = _find_empty_slot_key(all_points_data)
                            if slot_to_use_or_error:
                                logger.info(f"分配空槽位 '{slot_to_use_or_error}' 给新示教点 '{point_data_to_save.get('name')}'.")
                            else:
                                response_parts.append(f"无法保存新点 '{point_data_to_save.get('name')}': 没有可用的空槽位。")
                                slot_to_use_or_error = "ERROR_SAVE_NO_EMPTY_SLOT"
            
            # --- Logic for 'action == "更新"' ---
            elif action == "更新":
                if not slot_to_use_or_error or slot_to_use_or_error.startswith("ERROR_"): # Should not happen if action is update
                    logger.error(f"逻辑错误: action为更新，但slot_to_use_or_error ('{slot_to_use_or_error}') 无效。")
                    response_parts.append(f"更新点时发生内部逻辑错误。")
                elif point_data_to_save.get("name") is not None: # If name is part of the update parameters
                    new_name = point_data_to_save.get("name")
                    current_name_of_slot = existing_data_for_slot.get("name") if existing_data_for_slot else None
                    if new_name != current_name_of_slot: # Only check for duplicates if name is actually changing
                        for p_key_iter, p_data_iter in all_points_data.items():
                            if p_key_iter != slot_to_use_or_error and p_data_iter.get("name") == new_name:
                                response_parts.append(f"错误: 试图将点 '{slot_to_use_or_error}' 重命名为 '{new_name}', 但该名称已被槽位 {p_key_iter} 使用。")
                                slot_to_use_or_error = "ERROR_UPDATE_DUPLICATE_NAME"; break
            
            # --- Perform actual save/update if no errors detected ---
            if slot_to_use_or_error and not slot_to_use_or_error.startswith("ERROR_"):
                all_points_data[slot_to_use_or_error] = point_data_to_save
                if _save_teaching_points(all_points_data):
                    saved_name_display = point_data_to_save.get('name', slot_to_use_or_error)
                    response_parts.append(f"示教点 '{saved_name_display}' (槽位: {slot_to_use_or_error}) 已成功{action}。")
                    point_display_data = {slot_to_use_or_error: point_data_to_save}
                    response_parts.append(f"{action}后 {slot_to_use_or_error} 的数据:\n{json.dumps(point_display_data, ensure_ascii=False, indent=2)}")
                    operation_succeeded_for_json_check = True
                    final_data_for_json_output.append({slot_to_use_or_error: point_data_to_save})
                    current_turn_aimessage_kwargs["last_successful_point_context"] = {
                        "user_provided": user_provided_target_id,
                        "resolved_p_key": slot_to_use_or_error,
                        "intent_of_last_op": "save_update_point"
                    }
                else:
                    response_parts.append(f"{action.capitalize()}示教点 '{point_data_to_save.get('name', slot_to_use_or_error)}' 失败: 无法写入文件。")
            elif not response_parts : # If no specific error message has been added by the logic above
                 error_code = slot_to_use_or_error if (slot_to_use_or_error and slot_to_use_or_error.startswith("ERROR_")) else "未知错误"
                 response_parts.append(f"无法{action}点 '{user_provided_target_id}'. 错误代码: {error_code}. LLM详情: {resolution_details}")

    elif intent == "delete_point":
        user_provided_id = llm_analysis.get("user_provided_target_identifier")
        resolved_p_key_to_delete = llm_analysis.get("resolved_target_p_key")

        if not resolved_p_key_to_delete: 
            logger.warning(f"delete_point intent without resolved_target_p_key. User ID: '{user_provided_id}', Details: {resolution_details}")
            response_parts.append(f"无法找到您指定要删除的点 '{user_provided_id}'。请确保点存在或您的表述清晰。LLM解析: {resolution_details}")
        elif resolved_p_key_to_delete in all_points_data:
            deleted_point_name_display = all_points_data[resolved_p_key_to_delete].get("name", resolved_p_key_to_delete)
            
            empty_point_template = {key: spec["default"] for key, spec in POINT_FIELD_SCHEMA.items()}
            all_points_data[resolved_p_key_to_delete] = empty_point_template
            
            if _save_teaching_points(all_points_data):
                response_parts.append(f"示教点 '{deleted_point_name_display}' (槽位 {resolved_p_key_to_delete}) 的内容已被清除。该槽位可复用。")
                operation_succeeded_for_json_check = True
                final_data_for_json_output.append({"deleted_p_key": resolved_p_key_to_delete, "status": "cleared"})
                current_turn_aimessage_kwargs["last_successful_point_context"] = {"user_provided": user_provided_id, "resolved_p_key": resolved_p_key_to_delete, "intent_of_last_op": "delete_point"}
            else:
                response_parts.append(f"清除点 '{deleted_point_name_display}' (来自用户标识 '{user_provided_id}') 失败: 无法写入文件。")
        else:
            response_parts.append(f"点 {resolved_p_key_to_delete} (来自用户标识 '{user_provided_id}') 未找到，无法删除。LLM解析: {resolution_details}")
    
    elif intent == "unclear_intent" or intent == "error_parsing_llm_response":
        reason = llm_analysis.get("reason", resolution_details if intent == "unclear_intent" else "操作不被支持或无法理解。")
        response_parts.append(f"无法处理您的请求: {reason}")
        raw_content_for_debug = llm_analysis.get("raw_content")
        if raw_content_for_debug:
            response_parts.append(f"LLM原始输出 (供调试): {raw_content_for_debug[:200]}...")

    if not response_parts:
        response_parts.append(f"我不太确定如何处理您的示教点请求。LLM分析意图为：{intent if intent else '未知'}。细节：{resolution_details}")
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
        intermediate_results=final_response_content,
        generated_json_data_str=generated_json_str_for_polishing, # MODIFIED: Pass the generated string
        logger_object=logger
    )

    logger.info(f"Teaching Node: Final polished response: '{polished_response_content[:300]}...' AIMessage kwargs: {current_turn_aimessage_kwargs}")
    return {"messages": [AIMessage(content=polished_response_content, additional_kwargs=current_turn_aimessage_kwargs)]} 