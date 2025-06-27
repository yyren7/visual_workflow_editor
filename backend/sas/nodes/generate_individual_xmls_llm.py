import logging
import json
import os
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import xml.etree.ElementTree as ET
import uuid
import sys
from dotenv import load_dotenv
from xml.dom import minidom

# Conditional import for direct script execution vs. package import
if __name__ == "__main__" and __package__ is None: # pragma: no cover
    file_path_for_preamble = Path(__file__).resolve()
    # Assuming the script is in: backend/sas/nodes/
    # The project root /workspace is 4 levels up.
    project_root_for_preamble = file_path_for_preamble.parents[4] 
    if str(project_root_for_preamble) not in sys.path:
        sys.path.insert(0, str(project_root_for_preamble))
    try:
        # The package is the dot-separated path from the project root to the current file's parent directory.
        relative_script_parent_dir = file_path_for_preamble.parent.relative_to(project_root_for_preamble)
        calculated_package = str(relative_script_parent_dir).replace(os.sep, '.')
        __package__ = calculated_package
    except ValueError: 
        # This can happen if the script is not under the project root as expected,
        # or if project_root_for_preamble calculation is incorrect.
        # Silently pass if __package__ cannot be set, hoping other imports work.
        pass


from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from ..state import RobotFlowAgentState, GeneratedXmlFile

logger = logging.getLogger(__name__)

BLOCKLY_NS = "https://developers.google.com/blockly/xml"

# Define _PROJECT_ROOT at the module level for use in template path resolution
try:
    _PROJECT_ROOT = Path(__file__).resolve().parents[4]
except IndexError: # pragma: no cover
    _PROJECT_ROOT = Path.cwd()
    logger.warning(
        f"Could not determine project root via relative pathing from script location. "
        f"Assuming CWD ('{_PROJECT_ROOT}') is project root. Template loading might be affected if this assumption is incorrect."
    )

# Helper function to clean namespace URI from element tags recursively
def _clean_namespace_from_tags(element, namespace_uri_to_clean): # pragma: no cover
    if element is None:
        return
    if '}' in element.tag and element.tag.startswith(f'{{{namespace_uri_to_clean}}}'):
        element.tag = element.tag.split('}', 1)[1]
    for child in element:
        _clean_namespace_from_tags(child, namespace_uri_to_clean)

def _extract_explicit_block_type(detail_string: str) -> Optional[str]:
    """
    Extracts explicit block type (Block Type: `...`) from detail string.
    """
    type_match = re.search(r"Block Type: `([^`]+)`", detail_string)
    if type_match:
        return type_match.group(1)
    logger.warning(f"Could not extract explicit block type from detail string: {detail_string}")
    return None

async def _process_single_detail_with_llm(
    llm: BaseChatModel,
    task_name_context: str, 
    task_data_for_detail: Dict[str, Any],
    detail_str: str,
    target_block_id: str,
    data_block_no: str,
    task_output_dir: Path
) -> GeneratedXmlFile:
    """
    Processes a single detail string using LLM to generate XML, then saves it.
    """
    block_type = _extract_explicit_block_type(detail_str)
    
    generated_xml_file_entry = GeneratedXmlFile(
        block_id=target_block_id,
        type=block_type or "unknown_type_extraction_failure", # Store actual or error type
        source_description=detail_str,
        status="failure", # Default to failure
        xml_content=None,
        file_path=None,
        error_message=None
    )

    if not block_type:
        generated_xml_file_entry.error_message = "Could not extract explicit block type from detail string."
        logger.warning(f"Skipping detail for task '{task_name_context}' (block_id: {target_block_id}) due to unextracted block type. Detail: '{detail_str}'")
        return generated_xml_file_entry
    
    # --- Begin: Dynamically load and process block template ---
    # At this point, block_type is guaranteed to be non-None.
    # template_xml_str_for_prompt will be set if successful, otherwise we return with an error.
    template_xml_str_for_prompt = None 
    
    # According to memory ID: 2407533088222190099, templates are in database/node_database/quick-fcpr-new/
    template_dir = _PROJECT_ROOT / "database" / "node_database" / "quick-fcpr-new"
    template_path = template_dir / f"{block_type}.xml"
    
    if not template_path.exists():
        error_msg = f"Template file not found for block type '{block_type}' at {template_path}. Cannot proceed without template."
        logger.error(error_msg)
        generated_xml_file_entry.error_message = error_msg
        return generated_xml_file_entry # Status is already 'failure'
    
    # Template file exists, now try to read and parse it.
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            raw_template_content = f.read()
        
        template_root = ET.fromstring(raw_template_content)
        block_in_template_el = None

        # --- Modified Template Parsing Logic ---
        root_tag_cleaned = template_root.tag
        if '}' in root_tag_cleaned:
            root_tag_cleaned = root_tag_cleaned.split('}', 1)[1]

        if root_tag_cleaned == 'block':
            block_in_template_el = template_root
            logger.info(f"Template root is <block> for {template_path}.")
        elif root_tag_cleaned == 'xml':
            logger.info(f"Template root is <xml> for {template_path}. Searching for <block> inside.")
            # Prioritize direct children, then descendants, considering namespace
            search_queries = [
                f'{{{BLOCKLY_NS}}}block',  # Direct child with namespace
                'block',                     # Direct child without namespace
                f'.//{{{BLOCKLY_NS}}}block', # Any descendant with namespace
                './/block'                   # Any descendant without namespace
            ]
            for query in search_queries:
                found_block = template_root.find(query)
                if found_block is not None:
                    block_in_template_el = found_block
                    logger.info(f"Found <block> element inside <xml> using query '{query}' for {template_path}.")
                    break
        else:
            logger.warning(f"Template root for {template_path} is neither <xml> nor <block> (actual: {template_root.tag}). Will attempt to find <block> as a fallback.")
            # Fallback: try to find a block element anywhere if root is not recognized (e.g. some other wrapper)
            # This is less ideal but might catch some edge cases.
            block_in_template_el = template_root.find(f".//{{{BLOCKLY_NS}}}block") or template_root.find(".//block")


        if block_in_template_el is None:
            error_msg = f"Could not find <block> element within template file: {template_path} (root: {template_root.tag}) for block_type '{block_type}'. Searched in <xml> if present, or directly if root was <block>. Cannot proceed."
            logger.error(error_msg)
            generated_xml_file_entry.error_message = error_msg
            return generated_xml_file_entry # Status is already 'failure'
        # --- End Modified Template Parsing Logic ---
        
        # Successfully found block element, process it for the prompt
        _clean_namespace_from_tags(block_in_template_el, BLOCKLY_NS)
        
        # Convert the <block> element to a pretty string for the prompt
        temp_block_str = ET.tostring(block_in_template_el, encoding='unicode', method='xml')
        parsed_template_block_dom = minidom.parseString(temp_block_str)
        template_xml_str_for_prompt = parsed_template_block_dom.documentElement.toprettyxml(indent="  ")
        
        # Remove XML declaration if minidom added one
        template_xml_str_for_prompt = re.sub(r'<\?xml version="1.0" \?(encoding=".*?"\s*)?\?>\n?', '', template_xml_str_for_prompt).strip()
        # Remove xmlns attribute from the root <block> tag in the string, if present from ET processing
        template_xml_str_for_prompt = template_xml_str_for_prompt.replace(f' xmlns="{BLOCKLY_NS}"', '', 1)
        template_xml_str_for_prompt = template_xml_str_for_prompt.replace(' xmlns=""', '', 1) # Handle empty xmlns
    
    except ET.ParseError as e_parse:
        error_msg = f"Failed to parse template XML {template_path}: {e_parse}. Cannot proceed."
        logger.error(error_msg)
        generated_xml_file_entry.error_message = error_msg
        return generated_xml_file_entry
    except IOError as e_io:
        error_msg = f"Failed to read template XML {template_path}: {e_io}. Cannot proceed."
        logger.error(error_msg)
        generated_xml_file_entry.error_message = error_msg
        return generated_xml_file_entry
    except Exception as e_generic_template: # Catch-all for other unexpected errors during template processing
        error_msg = f"An unexpected error occurred while loading/processing template {template_path}: {e_generic_template}. Cannot proceed."
        logger.error(error_msg, exc_info=True) # Add exc_info for better debugging
        generated_xml_file_entry.error_message = error_msg
        return generated_xml_file_entry
    # --- End: Dynamically load and process block template ---
    
    # Simplified prompt construction
    # If we reach here, block_type is valid and template_xml_str_for_prompt is successfully populated.
    prompt_lines = [
        "You are an expert in generating Blockly XML for robot programming.",
        "Your task is to generate a single, complete Blockly XML `<block>` element.",
        f"The block's `type` attribute MUST be: `{block_type}`.",
        f"The block's `id` attribute MUST be: `{target_block_id}`.",
        f"The block's `data-blockNo` attribute MUST be: `{data_block_no}`.",
    ]

    # Since template loading is now mandatory for a valid block_type,
    # template_xml_str_for_prompt must be populated if we've reached this point.
    prompt_lines.append(
        f"Use the following XML template as a strict guide for the block\\'s structure, fields, and mutations. "
        f"Pay attention to comments in the template for field purposes, valid values, and default values (\\'初期値\\'). "
        f"Populate field values based on the \\'descriptive context\\' provided below. "
        f"If context is insufficient for a field, use the default value from the template comments if available."
    )
    prompt_lines.extend("""[
              "请根据模板和上下文严格生成XML。必须遵守以下规则：",
              "1. **XML结构精确匹配 (模板绝对优先)**: 生成的XML块中所有标签（如 `<field>`, `<value>`, `<statement>`, `<mutation>` 等）及其属性，必须与模板中定义的结构完全一致。所有XML标签必须正确闭合。 "
              "   **核心原则**: 模板是决定块内部结构（即是否包含 `<field>`, `<value>`, `<mutation>`, `<statement>` 等子元素）的**唯一且最终依据**。 "
              "   **严禁**为那些在模板中明确定义为内部无子元素的块（例如，模板中 `<block ...></block>` 内部只有注释）添加任何如 `<mutation>`, `<value>` 等子元素。",
              "2. **字段值填充**: ",
              "   - **上下文优先**: 如果描述性上下文为字段提供了具体值，请使用该值。",
              "   - **强制使用默认值 (初期値)**: 如果上下文信息不足以确定某个字段的值，并且模板注释中为此字段提供了明确的默认值（\\'初期値\\'），则**必须**使用该默认值。如果默认值是一个字符串（例如 \\"none\\"），则生成的字段**必须**包含该确切的字符串作为其文本内容（例如 `<field name=\\"some_field\\">none</field>`），而**不是**生成一个自闭合的空标签（如 `<field name=\\"some_field\\"/>`）或完全省略。",
              "   - **严格遵循有效范围 (有效范围)**: 如果模板注释为某个字段指定了\\"有效范围\\"（例如，一组特定的可选值如 `enable`, `disable`），那么LLM生成的该字段值**必须**从这个指定的有效范围中选择。如果上下文中没有明确指示，且\\"初期値\\"也在有效范围内，则优先使用\\"初期値\\"。**严禁**使用未在\\"有效范围\\"中列出的值，或在有默认值和有效范围的情况下留空字段。",
              "3. **示例说明**: ",
              "   - **示例1 (使用初期値)**: 若模板字段存在 `<field name=\\"SPEED\\">...</field> <!-- 初期値: 50 -->`，且上下文中无相关速度信息，则输出必须为 `<field name=\\"SPEED\\">50</field>`。",
              "   - **示例2 (使用初期値和有效范围)**: 若模板字段为 `<field name=\\"FLAG_NAME\\">...</field> <!-- 初期値: F0, 有效范围: F0-F499 -->`，且上下文中无相关标志位信息，则输出必须为 `<field name=\\"FLAG_NAME\\">F0</field>`。",
              "   - **示例3 (严格遵循有效范围和使用初期値)**: 若模板字段如 `moveP.xml` 中的 `<field name=\\"control_x\\">...</field> <!-- control_x (X方向補正): X轴方向是否启用修正。 有效范围: enable (有效), disable (无效) 初期値: enable -->`，如果上下文没有明确指定 `control_x` 的值，则输出**必须**是 `<field name=\\"control_x\\">enable</field>`。如果上下文指示禁用，则输出应为 `<field name=\\"control_x\\">disable</field>`。**绝不能**输出像 `<field name=\\"control_x\\">0</field>` 或将此字段留空。",
              "   - **示例4 (处理特定字符串默认值，如 \\'none\\')**: 若模板字段为 `<field name=\\"camera_list\\">none</field> <!-- 初期値: none -->`，并且上下文中没有明确的相机列表信息，则输出**必须**是 `<field name=\\"camera_list\\">none</field>`。**严禁**输出 `<field name=\\"camera_list\\"/>`、`<field name=\\"camera_list\\">C0</field>`（除非上下文明确指示了C0）或任何其他不符合模板和默认值的形式。此规则同样适用于 `pallet_list` 等具有类似字符串默认值的字段。",
              "你的输出必须是单一、完整且格式正确的Blockly XML `<block>` 元素。不要包含任何额外的解释或标记。"
         ]""")
    prompt_lines.append("XML Template to strictly follow:")
    prompt_lines.append(template_xml_str_for_prompt) # This is now guaranteed to be non-None and populated.
    
    # These lines are common and should come after template instructions
    escaped_detail_str = detail_str.replace('"', '\\"') # Perform replacement outside f-string
    prompt_lines.append(f"Descriptive context for this block: \"{escaped_detail_str}\".") # Use the pre-escaped string
    
    # Handle special block types more naturally
    if block_type == "procedures_defnoreturn":
        procedure_definition_name = task_data_for_detail.get('name')
        if procedure_definition_name:
            safe_proc_name = procedure_definition_name.replace('&', '&amp;')
            prompt_lines.append(f"This block defines a procedure. The procedure's name (within the <mutation> tag, attribute 'name') MUST be exactly \"{safe_proc_name}\".")
        else: # pragma: no cover
            prompt_lines.append("This block defines a procedure. If the context implies a name for the procedure, use it for the mutation's 'name' attribute. Otherwise, use a sensible placeholder like 'UnnamedProcedure'.")
            logger.warning(f"Task '{task_name_context}' is procedures_defnoreturn but task_data has no 'name'. LLM will infer or use placeholder for procedure name.")

    elif block_type == "procedures_callnoreturn":
        call_match = re.search(r'Call sub-program "([^"]+)"', detail_str, re.IGNORECASE)
        if call_match:
            proc_name_to_call = call_match.group(1).strip().replace('&', '&amp;')
            prompt_lines.append(f"This block calls a procedure. The called procedure's name (within the <mutation> tag, attribute 'name') MUST be exactly \"{proc_name_to_call}\".")
        else: # pragma: no cover
            prompt_lines.append("This block calls a procedure. Attempt to infer the called procedure name from the context for the mutation's 'name' attribute. If unclear, use a sensible placeholder like 'CalledProcedure'.")
            logger.warning(f"Could not extract procedure call name from '{detail_str}' for procedures_callnoreturn. LLM will infer or use placeholder.")
    
    prompt_lines.append(
        "IMPORTANT: Your output MUST be ONLY the XML for the single `<block>` element, starting with `<block ...>` and ending with `</block>`. "
        "Do NOT include any surrounding ```xml ... ``` markers, explanations, comments outside the XML, or XML declarations (like <?xml ...?>)."
    )
    
    prompt_text = "\n".join(prompt_lines)
    logger.debug(f"LLM Prompt for block_id {target_block_id} (type: {block_type}):\n{prompt_text}")

    raw_llm_xml = None
    try:
        llm_response = await llm.ainvoke([HumanMessage(content=prompt_text)])
        raw_llm_xml = llm_response.content.strip() if hasattr(llm_response, 'content') else str(llm_response).strip()
        logger.debug(f"Raw LLM output for block_id {target_block_id}: {raw_llm_xml}")

        # Clean common LLM output issues (markdown, etc.)
        if raw_llm_xml.startswith("```xml"):
            raw_llm_xml = raw_llm_xml[len("```xml"):].strip()
        if raw_llm_xml.startswith("```"): # General ``` if xml was missed
            raw_llm_xml = raw_llm_xml[len("```"):].strip()
        if raw_llm_xml.endswith("```"):
            raw_llm_xml = raw_llm_xml[:-len("```")].strip()
        
        # Attempt to parse the XML. LLM should return just a <block>...</block> string.
        # If it returns <xml><block>...</block></xml>, we try to extract block.
        parsed_root = None
        try:
            # It's possible the LLM still includes an XML declaration despite instructions
            # We can try to remove it before parsing if it's a common failure point.
            # For now, let's assume ET.fromstring handles it or it's not the primary issue.
            if raw_llm_xml.startswith("<?xml"): # Remove XML declaration if present
                raw_llm_xml = re.sub(r'^<\?xml.*?\?>\s*', '', raw_llm_xml, flags=re.IGNORECASE)
            parsed_root = ET.fromstring(raw_llm_xml)
        except ET.ParseError as e_parse_direct: # pragma: no cover
            raise ValueError(f"LLM output is not valid XML or could not be parsed. ParseError: {e_parse_direct}. Output: {raw_llm_xml[:300]}") from e_parse_direct

        xml_block_element = None
        # Check if the root is <block> or if <block> is a child (e.g., under <xml>)
        # Normalize tag check (e.g. {namespace}block vs block)
        current_tag = parsed_root.tag
        if '}' in current_tag:
            current_tag = current_tag.split('}', 1)[1]

        if current_tag.lower() == 'block':
            xml_block_element = parsed_root
        else:
            # Try to find a 'block' element, accommodating potential Blockly namespace or no namespace
            # Search more flexibly: direct child or any descendant
            block_el_search_queries = [f'{{{BLOCKLY_NS}}}block', 'block', f'.//{{{BLOCKLY_NS}}}block', './/block']
            for query in block_el_search_queries:
                found = parsed_root.find(query)
                if found is not None:
                    xml_block_element = found
                    logger.info(f"Extracted <block> element from LLM output (possibly from a wrapper like <xml>) for block_id {target_block_id} using query '{query}'")
                    break
        
        if xml_block_element is None: # pragma: no cover
            raise ValueError(f"Could not find a <block> element in the LLM's XML output. Parsed root tag: '{parsed_root.tag}'. Output: {raw_llm_xml[:300]}")

        # Final check on the identified element's tag
        final_element_tag = xml_block_element.tag
        if '}' in final_element_tag:
            final_element_tag = final_element_tag.split('}', 1)[1]
        if final_element_tag.lower() != 'block': # pragma: no cover
             raise ValueError(f"The identified XML element is not a <block> after extraction. Effective tag: '{final_element_tag}'. Original was '{xml_block_element.tag}'.")

        xml_block_element.set('id', target_block_id)
        xml_block_element.set('data-blockNo', data_block_no)

        _clean_namespace_from_tags(xml_block_element, BLOCKLY_NS)
        
        # 使用pretty_print添加格式化换行
        xml_str = ET.tostring(xml_block_element, encoding='utf-8')
        parsed = minidom.parseString(xml_str)
        final_xml_block_string = parsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

        # 移除多余的XML声明和空行
        final_xml_block_string = re.sub(r'<\?xml version="1.0" \?>\n', '', final_xml_block_string)
        final_xml_block_string = re.sub(r'\n\s*\n', '\n', final_xml_block_string).strip()
        
        # Smart removal of xmlns attribute only from the main 'block' tag, if it's there
        if xml_block_element.tag == "block": # Check if the tag we serialized is indeed 'block'
            # Regex to match xmlns="BLOCKLY_NS" only if it's at the root <block ...>
            # This is a bit tricky; ET.tostring might add it if ET.register_namespace was used.
            # A simpler way is to replace it if known to be added.
            # Example: <block type="foo" id="123" xmlns="https://developers.google.com/blockly/xml">...</block>
            # becomes <block type="foo" id="123">...</block>
            # The .replace is safer than regex if the exact string is known.
            final_xml_block_string = final_xml_block_string.replace(f' xmlns="{BLOCKLY_NS}"', '', 1)

        # General cleanup for ns0: prefixes and empty xmlns attributes on children
        final_xml_block_string = re.sub(r'<(/?)ns\\d+:', r'<\\1', final_xml_block_string)
        final_xml_block_string = re.sub(r'\\s*xmlns:ns\\d+=[\\\'\"]' + re.escape(BLOCKLY_NS) + '[\\\'\"]', '', final_xml_block_string)
        final_xml_block_string = final_xml_block_string.replace(' xmlns=""', "")

        generated_xml_file_entry.xml_content = final_xml_block_string
        generated_xml_file_entry.status = "success"
        
    except ET.ParseError as pe: # pragma: no cover
        generated_xml_file_entry.error_message = f"XML ParseError from LLM output for block_id {target_block_id}: {pe}. LLM Raw: {raw_llm_xml[:300] if raw_llm_xml else 'None'}"
    except ValueError as ve: # pragma: no cover
        generated_xml_file_entry.error_message = f"Validation error for block_id {target_block_id}: {ve}. LLM Raw: {raw_llm_xml[:300] if raw_llm_xml else 'None'}"
    except Exception as e: # pragma: no cover
        generated_xml_file_entry.error_message = f"Error processing LLM response or generating XML for block_id {target_block_id}: {e}. LLM Raw: {raw_llm_xml[:300] if raw_llm_xml else 'None'}"
    
    # File saving logic (outside try-except for LLM processing, but inside the function)
    if generated_xml_file_entry.status == "success" and generated_xml_file_entry.xml_content:
        generated_xml_filename = f"{block_type}_{data_block_no}.xml" # Use the validated block_type and data_block_no
        file_path_to_save = task_output_dir / generated_xml_filename
        try:
            xml_to_write = generated_xml_file_entry.xml_content
            # 添加XML声明并确保换行
            if not xml_to_write.strip().startswith('<?xml'):
                xml_to_write = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_to_write
            
            with open(file_path_to_save, 'w', encoding='utf-8') as f:
                f.write(xml_to_write)
            generated_xml_file_entry.file_path = str(file_path_to_save)
            logger.info(f"Successfully wrote LLM-generated XML block to: {file_path_to_save}")
        except IOError as e: # pragma: no cover
            logger.error(f"Failed to write LLM-generated XML block file {file_path_to_save}: {e}", exc_info=True)
            generated_xml_file_entry.status = "failure" 
            generated_xml_file_entry.error_message = (generated_xml_file_entry.error_message or "") + f"; IOError on writing file: {e}"
            generated_xml_file_entry.file_path = None # Clear path on write failure
    
    if generated_xml_file_entry.status == "failure": # pragma: no cover
         logger.error(f"Failed to generate/save XML for block_id '{generated_xml_file_entry.block_id}' (type: {generated_xml_file_entry.type}): {generated_xml_file_entry.error_message}")

    return generated_xml_file_entry

MAX_RETRIES = 2 # Total attempts = MAX_RETRIES + 1 (e.g., 1 initial + 2 retries = 3 total)

async def generate_individual_xmls_node(state: RobotFlowAgentState, llm: Optional[BaseChatModel] = None) -> RobotFlowAgentState:
    logger.info("--- Running Step 2: Generate Independent Node XMLs (LLM-based) with Retries ---")    
    state.current_step_description = "Generating individual XML block files via LLM for each task detail, with retries"
    state.is_error = False 
    state.generated_node_xmls = [] # Initialize here, will be populated with all final results

    if not llm: # pragma: no cover
        logger.error("LLM instance is not provided to generate_individual_xmls_node.")
        state.is_error = True
        state.error_message = "LLM instance is required for XML generation but was not provided."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    parsed_tasks_from_state = state.parsed_flow_steps 
    config = state.config

    if not parsed_tasks_from_state: # pragma: no cover
        logger.error("parsed_flow_steps is missing or empty in agent state.")
        state.is_error = True
        state.error_message = "Parsed flow steps (tasks) are missing or empty for XML generation."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    main_output_dir_str = config.get("OUTPUT_DIR_PATH")
    if not main_output_dir_str: # pragma: no cover
        logger.error("OUTPUT_DIR_PATH is not configured in state.config.")
        state.is_error = True
        state.error_message = "Main output directory path (OUTPUT_DIR_PATH) for individual XMLs is not configured."
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    main_output_dir = Path(main_output_dir_str)
    try:
        os.makedirs(main_output_dir, exist_ok=True)
    except OSError as e: # pragma: no cover
        logger.error(f"Failed to create main output directory {main_output_dir}: {e}", exc_info=True)
        state.is_error = True
        state.error_message = f"Failed to create main output directory: {e}"
        state.dialog_state = "error"
        state.subgraph_completion_status = "error"
        return state

    # --- Prepare initial list of all task detail arguments for LLM processing ---
    all_task_detail_args: List[Dict[str, Any]] = []
    global_data_block_counter = 1 

    for task_index, task_data in enumerate(parsed_tasks_from_state):
        task_name = task_data.get('name', f'task_{task_index}')
        task_details = task_data.get('details', [])
        
        sanitized_task_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', task_name)
        task_specific_dir_name = f"{task_index:02d}_{sanitized_task_name}"
        task_output_dir = main_output_dir / task_specific_dir_name

        try:
            os.makedirs(task_output_dir, exist_ok=True)
        except OSError as e: # pragma: no cover
            logger.error(f"Failed to create task-specific directory {task_output_dir}: {e}", exc_info=True)
            dir_error_entry = GeneratedXmlFile(
                block_id=f"task_dir_error_{task_index}", 
                type="task_directory_creation_failure", 
                source_description=f"Error creating directory for task: {task_name}",
                status="failure", 
                error_message=str(e)
            )
            state.generated_node_xmls.append(dir_error_entry) # Add directory errors immediately
            continue # Skip adding details from this task if its directory cannot be made

        if not task_details: # pragma: no cover
            logger.warning(f"Task '{task_name}' (index {task_index}) has no details. No XML blocks will be generated for it.")
            continue

        for detail_idx, detail_str in enumerate(task_details):
            current_target_block_id = str(uuid.uuid4()) 
            current_data_block_no = str(global_data_block_counter)
            global_data_block_counter += 1
            
            all_task_detail_args.append({
                "llm": llm,
                "task_name_context": task_name, 
                "task_data_for_detail": task_data,
                "detail_str": detail_str,
                "target_block_id": current_target_block_id,
                "data_block_no": current_data_block_no,
                "task_output_dir": task_output_dir
            })

    # --- Retry logic for LLM processing ---
    llm_processed_results: List[GeneratedXmlFile] = [] 
    tasks_to_attempt_args = all_task_detail_args # Start with all prepared tasks

    for attempt_num in range(MAX_RETRIES + 1):
        if not tasks_to_attempt_args:
            if attempt_num == 0: # No tasks were prepared for LLM at all
                 logger.info("No task details found that require LLM processing.")
            else: # All tasks completed in previous attempts
                 logger.info("All LLM tasks successfully processed or retries exhausted in previous attempts.")
            break

        logger.info(f"--- LLM XML Generation Attempt {attempt_num + 1}/{MAX_RETRIES + 1} for {len(tasks_to_attempt_args)} details ---")
        
        generation_coroutines = [
            _process_single_detail_with_llm(**task_args) for task_args in tasks_to_attempt_args
        ]
        
        current_attempt_outcomes: List[Union[GeneratedXmlFile, Exception]] = await asyncio.gather(*generation_coroutines, return_exceptions=True)
        
        failed_tasks_for_next_retry_args: List[Dict[str, Any]] = []

        for i, outcome in enumerate(current_attempt_outcomes):
            original_task_args = tasks_to_attempt_args[i] 
            processed_entry: Optional[GeneratedXmlFile] = None

            if isinstance(outcome, Exception):
                logger.error(f"Unhandled exception during LLM processing for block_id {original_task_args['target_block_id']}: {outcome}", exc_info=True)
                processed_entry = GeneratedXmlFile(
                    block_id=original_task_args['target_block_id'],
                    type=_extract_explicit_block_type(original_task_args['detail_str']) or "unknown_type_unhandled_exception",
                    source_description=original_task_args['detail_str'],
                    status="failure",
                    error_message=f"Unhandled processing exception: {str(outcome)}"
                )
            else:
                processed_entry = outcome 
            
            if processed_entry.status == "success":
                llm_processed_results.append(processed_entry)
            else: # status is "failure"
                if attempt_num < MAX_RETRIES:
                    logger.warning(f"LLM generation for block_id {processed_entry.block_id} (type: {processed_entry.type}) failed on attempt {attempt_num + 1}. Will retry. Error: {processed_entry.error_message}")
                    failed_tasks_for_next_retry_args.append(original_task_args) 
                else:
                    logger.error(f"LLM generation for block_id {processed_entry.block_id} (type: {processed_entry.type}) failed after {MAX_RETRIES + 1} attempts. Error: {processed_entry.error_message}")
                    llm_processed_results.append(processed_entry) 

        tasks_to_attempt_args = failed_tasks_for_next_retry_args 
        
        if not tasks_to_attempt_args: 
            logger.info(f"All pending LLM tasks for attempt {attempt_num + 1} have been resolved.")
            break
            
    state.generated_node_xmls.extend(llm_processed_results)

    # --- Determine overall error status based on all collected results ---
    overall_errors_in_processing = any(r.status == "failure" for r in state.generated_node_xmls)
    
    if overall_errors_in_processing: # pragma: no cover
        logger.error("One or more errors occurred during the LLM-based generation of individual XML blocks (including retries or directory issues). Details should be in preceding logs.")
        state.is_error = True 
        if not state.error_message: 
            state.error_message = "Errors occurred during LLM-based individual XML block generation or directory creation."
        state.subgraph_completion_status = "error" 
        state.dialog_state = "generating_xml_relation" 
    else:
        if not state.generated_node_xmls and not all_task_detail_args and parsed_tasks_from_state : # check if there were tasks but no details that led to xml generation
            logger.warning("XML generation step completed, but no actual XMLs were generated (e.g. tasks had no details or only directory errors occurred).")
        elif not parsed_tasks_from_state:
             logger.info("XML generation step completed. No tasks were provided in parsed_flow_steps.")
        else:
            logger.info("All individual XML blocks for all tasks were processed successfully (including retries if any, and no directory issues)." )
        
        state.dialog_state = "generating_xml_relation" 
        state.subgraph_completion_status = None 
    
    return state

# Test execution block
if __name__ == "__main__": # pragma: no cover
    
    class MockRobotFlowAgentState:
        def __init__(self, parsed_flow_steps: List[Dict[str, Any]], config: Dict[str, Any]):
            self.parsed_flow_steps = parsed_flow_steps
            self.config = config
            self.current_step_description: Optional[str] = None
            self.is_error: bool = False
            self.error_message: Optional[str] = None
            self.dialog_state: Optional[str] = None
            self.subgraph_completion_status: Optional[str] = None
            self.generated_node_xmls: List[GeneratedXmlFile] = []

    async def main_test():
        # 加载环境变量
        load_dotenv()
        
        # 从环境变量获取LLM配置
        llm_provider = os.getenv("ACTIVE_LLM_PROVIDER", "gemini")
        google_api_key = os.getenv("GOOGLE_API_KEY")
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        
        # 根据配置创建LLM实例
        if llm_provider == "gemini" and google_api_key:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm_for_test = ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                temperature=0.1,
                api_key=google_api_key
            )
        elif llm_provider == "deepseek" and deepseek_api_key:
            from langchain_community.chat_models import ChatOpenAI
            llm_for_test = ChatOpenAI(
                api_key=deepseek_api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL"),
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            )
        else:  # pragma: no cover
            print("No valid LLM configuration found in .env")
            llm_for_test = None
        
        print("[Test Main] Starting LLM-based XML generation test (conceptual).")
        
        log_format = '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s'
        logger.setLevel(logging.DEBUG) # Node logger can be more verbose

        # Path relative to workspace root
        test_json_path_str = "backend/tests/llm_sas_test/1_sample/step2_output_sample.json"
        
        # Determine project root dynamically for robust path construction if needed,
        # but for fixed test paths, direct construction is fine if run from workspace root.
        try:
            # Assumes running from /workspace or that the path is valid from CWD
            resolved_test_json_path = Path(test_json_path_str).resolve()
            if not resolved_test_json_path.exists(): # Try relative to script if absolute fails from CWD
                 script_dir = Path(__file__).parent.resolve()
                 # This needs to go up several levels to reach /workspace, then down.
                 # backend/sas/nodes/ -> ../../../
                 # Then backend/tests/llm_sas_test/1_sample/step2_output_sample.json
                 workspace_root_guess = script_dir.parents[3] # Adjust based on actual structure
                 resolved_test_json_path = workspace_root_guess / test_json_path_str
        except Exception: # Fallback if path resolution is complex or fails
            resolved_test_json_path = Path(test_json_path_str) # Try as is

        if not resolved_test_json_path.exists():
            print(f"ERROR: Test JSON file not found at {resolved_test_json_path} (tried multiple strategies)")
            return

        try:
            with open(resolved_test_json_path, 'r', encoding='utf-8') as f:
                test_input_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode JSON from {resolved_test_json_path}: {e}")
            return
        
        tasks_for_state = test_input_data if isinstance(test_input_data, list) else []
        if not tasks_for_state: # pragma: no cover
            print("ERROR: No tasks loaded from JSON. Ensure it's a list of task objects as per step2_output_sample.json.")
            return

        # Output directory relative to workspace root
        test_output_dir_str = "backend/tests/llm_sas_test/1_sample_sas_llm_generated_xml_output"
        # For testing, clear the output directory first
        test_output_dir_path = _PROJECT_ROOT / test_output_dir_str
        if test_output_dir_path.exists():
            import shutil
            shutil.rmtree(test_output_dir_path)
            print(f"[Test Main] Cleared previous output directory: {test_output_dir_path}")
        
        mock_config = {
            "OUTPUT_DIR_PATH": str(test_output_dir_path), # Use absolute path for robustness in tests
        }
        os.makedirs(test_output_dir_path, exist_ok=True)
        print(f"[Test Main] Mock config created. OUTPUT_DIR_PATH: {mock_config['OUTPUT_DIR_PATH']}")

        initial_state = MockRobotFlowAgentState(
            parsed_flow_steps=tasks_for_state, 
            config=mock_config
        )

        if llm_for_test is None: # pragma: no cover
            print("\n[Test Main] LLM instance is None. Actual LLM calls will be skipped by the node logic (it will error).")
            print("To run the full test, instantiate an LLM and assign it to 'llm_for_test'.\n")
            print("[Test Main] Calling generate_individual_xmls_node with llm=None to check basic flow...")
            final_state = await generate_individual_xmls_node(initial_state, llm=llm_for_test) # Pass None
        else:
            print("[Test Main] LLM instance provided. Calling generate_individual_xmls_node...")
            final_state = await generate_individual_xmls_node(initial_state, llm=llm_for_test)

        if final_state.is_error:
            print(f"[Test Main] Test run reported an error: {final_state.error_message}")
        else:
            print("[Test Main] Test run completed (node did not report an overall error)." )
        
        print(f"[Test Main] Total GeneratedXmlFile entries in state: {len(final_state.generated_node_xmls)}")
        success_count = 0
        failure_count = 0
        for entry_idx, entry in enumerate(final_state.generated_node_xmls):
            status_marker = "OK" if entry.status == "success" else "FAIL"
            path_info = entry.file_path if entry.file_path else "No file generated"
            print(f"  [{status_marker}] Entry {entry_idx+1}: ID={entry.block_id}, Type={entry.type}, Path={path_info}")
            if entry.status == "success":
                success_count +=1
            else:
                failure_count +=1
                print(f"      Error for {entry.block_id}: {entry.error_message}")
        
        total_processed_or_dir_errors = len(final_state.generated_node_xmls)
        print(f"[Test Main] Summary: From {total_processed_or_dir_errors} total entries (incl. dir errors), {success_count} successful XML generations, {failure_count} failed entries (XML gen or dir error)." )
        print(f"[Test Main] Check output files (if any) in: {mock_config['OUTPUT_DIR_PATH']}")

    print("[Test Main] Setting up and running test function...")
    asyncio.run(main_test())
    print("[Test Main] Finished test function.")
