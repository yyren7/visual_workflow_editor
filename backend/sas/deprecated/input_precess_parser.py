import re
import json
from typing import List, Dict, Any

def _parse_subsection_detail(sub_content_block: str) -> Dict[str, Any]:
    """
    Parses the content block of a sub-section (from Section II) into
    function, clamp_involved, and core_logic.
    """
    text = sub_content_block.strip()
    details = {
        "function": "",
        "clamp_involved": "",
        "core_logic": []
    }

    # Function
    # Extracts text after "Function:" until "Clamp(s) Involved:", "Core Logic:", "Note:", or end of block.
    func_match = re.search(
        r"(?:-\s*)?Function:\s*(.*?)(?=\n\s*(?:-\s*)?(?:Clamp(?:s)?\s*Involved:|Core Logic:|Note:)|$)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if func_match:
        details["function"] = func_match.group(1).strip()

    # Clamp(s) Involved
    # Extracts text after "Clamp(s) Involved:" until "Core Logic:", "Note:", or end of block.
    clamp_match = re.search(
        r"(?:-\s*)?Clamp(?:s)?\s*Involved:\s*(.*?)(?=\n\s*(?:-\s*)?(?:Core Logic:|Note:)|$)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if clamp_match:
        details["clamp_involved"] = clamp_match.group(1).strip()

    # Core Logic
    # Extracts text after "Core Logic:" (possibly on new line) until "Note:" or end of block.
    # Splits the extracted logic into lines.
    core_logic_match = re.search(
        r"(?:-\s*)?Core Logic:\s*\n?(.*?)(?=\n\s*(?:-\s*)?Note:|$)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if core_logic_match:
        logic_text = core_logic_match.group(1).strip()
        details["core_logic"] = [
            line.strip().lstrip('- ').strip() 
            for line in logic_text.split('\n') 
            if line.strip()
        ]
    
    return details

def parse_process_plan_to_json(text_plan: str) -> List[Dict[str, Any]]:
    """
    解析详细流程计划文本为结构化JSON
    专注于三大板块
    """
    if not text_plan.strip():
        return [{"error": "输入文本为空"}]
    
    # 按罗马数字分节
    sections = re.split(r'\n(?=[IVXLCDM]+\.\s+)', text_plan.strip())
    parsed = []
    
    for section_text_block in sections: # Renamed 'section' to 'section_text_block' for clarity
        # 提取节标题
        first_line = section_text_block.split('\n')[0]
        title_match = re.match(r'([IVXLCDM]+)\.\s+(.*)', first_line)
        if not title_match:
            # This could be an introductory paragraph before the first section
            # Or a malformed section. For now, we skip it if no title is found.
            # If there's a need to capture such content, this logic can be adjusted.
            if parsed or sections[0] != section_text_block : # if it's not the first block and we have prior valid sections, it might be an error or malformed
                 # you might want to log this or handle it as an unstructured part.
                 # for now, simply continuing.
                 pass # keep it simple to skip if no roman numeral.
            # If it IS the first block and doesn't match, it might be an intro.
            # Current logic will skip it. If the first block should be captured if it has no title,
            # then a new dictionary type might be needed. Given current structure, skipping is consistent.
            continue 
            
        roman = title_match.group(1)
        section_title_text = title_match.group(2).strip()
        section_dict = {"section_title": f"{roman}. {section_title_text}"}
        
        # The rest of the section content (after the title line)
        # section_content_full = '\n'.join(section_text_block.split('\n')[1:]).strip()

        if roman == "II": # "Sub-programs and Their Functional Descriptions"
            sub_sections_list = []
            # Regex to find sub-tasks: number, title, and content block
            # The content block for each sub-task starts after its title line.
            sub_tasks = re.findall(
                r'(\d+)\.\s+([^\n]+)((?:\n(?!\d+\.|[IVXLCDM]+\.).*)*)', 
                '\n'.join(section_text_block.split('\n')[1:]), # Pass content after section title
                re.DOTALL
            )
            
            current_sub_task_content_start_index = 0
            section_content_after_title = '\n'.join(section_text_block.split('\n')[1:])

            # Improved sub-task splitting logic
            sub_task_matches = list(re.finditer(r'^(\d+)\.\s+([^\n]+)', section_content_after_title, re.MULTILINE))

            for i, match in enumerate(sub_task_matches):
                num = match.group(1)
                sub_title = match.group(2).strip()
                
                start_index = match.end()
                # Content ends at the start of the next sub_task or end of section
                end_index = sub_task_matches[i+1].start() if i + 1 < len(sub_task_matches) else len(section_content_after_title)
                
                sub_content_block = section_content_after_title[start_index:end_index].strip()
                
                parsed_sub_details = _parse_subsection_detail(sub_content_block)
                
                sub_sections_list.append({
                    "item_number": f"{num}",
                    "title": sub_title,
                    "function": parsed_sub_details["function"],
                    "clamp_involved": parsed_sub_details["clamp_involved"],
                    "core_logic": parsed_sub_details["core_logic"]
                })
            section_dict["sub_sections"] = sub_sections_list

        elif roman == "I": # "Main Program Process Description"
            parts = section_text_block.split('\n', 1)
            raw_content = parts[1].strip() if len(parts) > 1 else ""
            section_dict["content"] = [line.strip().lstrip('- ').strip() for line in raw_content.split('\n') if line.strip()]
        
        else: # Handles "III. Modularization and Reuse Explanation" and any other sections
            parts = section_text_block.split('\n', 1)
            raw_content = parts[1].strip() if len(parts) > 1 else ""
            section_dict["content"] = [line.strip().lstrip('- ').strip() for line in raw_content.split('\n') if line.strip()]
        
        parsed.append(section_dict)
    
    # If the first part of the text_plan was an intro without a Roman numeral,
    # and sections[0] was that intro, it would be skipped by the loop.
    # This behavior is maintained. If the intro needs to be captured,
    # the logic for handling `sections[0]` when `title_match` is None would need to change.
    # One simple way to capture intro:
    if text_plan.strip() and (not parsed or (parsed and not text_plan.strip().startswith(parsed[0]["section_title"]))):
        first_section_content = sections[0]
        # Check if the first block was already parsed as a section or if it's truly an intro
        is_intro = True
        if parsed:
            # Check if the content of sections[0] matches the first line of the first parsed section title
            # to avoid duplicating the first section's title as an intro.
            # A bit complex, might need more robust check if intros are common and structured.
            # For now, if `sections[0]` did not produce a `title_match`, it's likely an intro.
            # The `continue` in the loop already handles this.
            # This block might be for specifically adding an "intro" field if sections[0] had no title_match
            
            # Let's refine the condition for intro. If sections[0] did not match a title, it's an intro.
            # The current loop structure with `continue` means `sections[0]` (if it's an intro) is skipped.
            # This is probably fine unless intros must be captured.
            # The user did not request parsing of a generic intro block.
            pass


    return parsed

# 保留完整的测试用例
if __name__ == '__main__':
    # 从文件读取示例输出
    with open("/workspace/database/prompt_database/sas_input_prompt/step1_output_example.txt", "r") as f:
        example_llm_output = f.read()
    parsed_json = parse_process_plan_to_json(example_llm_output)
    print("\n--- Parsed JSON from LLM Output ---")
    print(json.dumps(parsed_json, indent=4, ensure_ascii=False))

    # 其他测试用例保持不变
    print("\n--- Testing Empty Input ---")
    empty_example = ""
    parsed_json_empty = parse_process_plan_to_json(empty_example)
    print(json.dumps(parsed_json_empty, indent=4, ensure_ascii=False))

    print("\n--- Testing Plain Text Input ---")
    no_sections_example = "This is just a single line of text.\nWithout any section markers that is very plain."
    parsed_json_no_sections = parse_process_plan_to_json(no_sections_example)
    print(json.dumps(parsed_json_no_sections, indent=4, ensure_ascii=False))
    
    print("\n--- Testing Only Intro Text ---")
    intro_only_example = """This is an introductory paragraph.
It might have several lines.
It does not start with a Roman numeral section marker.
* Maybe a bullet point: here.
Another line of introduction.
"""
    parsed_json_intro_only = parse_process_plan_to_json(intro_only_example)
    print(json.dumps(parsed_json_intro_only, indent=4, ensure_ascii=False))

    print("\n--- Testing Section with only KVs and Bullets (like Section III) ---")
    section_iii_like = """III. Modularization and Reuse Explanation

*   **Clamp Operations**: Details about clamp operations.
    This is a second line for clamp operations.
*   **Speed Control**: Details about speed control.
*   A plain bullet point item.
"""
    parsed_json_section_iii = parse_process_plan_to_json(section_iii_like)
    print(json.dumps(parsed_json_section_iii, indent=4, ensure_ascii=False))

    print("\n--- Testing Section with only title ---")
    section_title_only = "IV. Empty Section"
    parsed_json_title_only = parse_process_plan_to_json(section_title_only)
    print(json.dumps(parsed_json_title_only, indent=4, ensure_ascii=False)) 
