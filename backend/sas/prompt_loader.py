import os
import logging
import re  # 新增：用于清理文件名中的特殊字符
from datetime import datetime  # 新增：用于生成时间戳
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def get_dynamic_output_path(flow_id: str, username: str) -> str:
    """
    根据流程图号和用户名生成动态输出路径
    
    Args:
        flow_id: 流程图ID
        username: 用户名
        
    Returns:
        格式化的输出路径
    """
    base_path = "/workspace/database/flow_database/result"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 清理用户名和流程图ID，移除特殊字符
    clean_username = re.sub(r'[^a-zA-Z0-9_.-]', '_', username)
    clean_flow_id = re.sub(r'[^a-zA-Z0-9_.-]', '_', flow_id)
    
    # 创建路径：用户名/流程图号_时间戳
    dynamic_path = os.path.join(
        base_path,
        clean_username,
        f"flow_{clean_flow_id}_{timestamp}"
    )
    
    logger.info(f"生成动态输出路径: {dynamic_path}")
    return dynamic_path

DEFAULT_CONFIG = {
    "GENERAL_INSTRUCTION_INTRO": "As an intelligent agent for creating robot process files, you need to perform the following multi-step process to generate robot control XML files based on the context and the user's latest natural language input:",
    "NODE_TEMPLATE_DIR_PATH": os.getenv("NODE_TEMPLATE_DIR_PATH", "/workspace/database/node_database/quick-fcpr-new"), # Read from environment variable, use default value if not set
    "OUTPUT_DIR_PATH": None,  # 强制设为None，禁止使用固定的example_run路径，必须动态生成
    "EXAMPLE_FLOW_STRUCTURE_DOC_PATH": "/workspace/database/document_database/flow.xml",
    "BLOCK_ID_PREFIX_EXAMPLE": "block_uuid",
    "RELATION_FILE_NAME_ACTUAL": "relation.xml",
    "FINAL_FLOW_FILE_NAME_ACTUAL": "flow.xml"
}

PROMPT_DIR = "/workspace/database/prompt_database/flow_structure_prompt/"
NODE_DESCRIPTION_FILE_PATH = "/workspace/database/prompt_database/node_description/block_description.md"
SAS_STEP1_PROMPT_FILE_PATH = "/workspace/database/prompt_database/sas_input_prompt/step1_user_input_to_process_description_prompt_en.md"
# Path for the new prompt template
SAS_STEP1_TASK_LIST_PROMPT_PATH = "/workspace/database/prompt_database/task_based_prompt/step1_user_input_to_task_list_prompt_en.md"
TASK_LIST_DEFINITION_DIR_PATH = "/workspace/database/prompt_database/task_based_prompt/task_list/"
BLOCK_DESCRIPTION_FILE_PATH = "/workspace/database/prompt_database/node_description/block_description.md" # Renamed for clarity

def load_prompt_template(template_file_name: str) -> Optional[str]:
    """Loads a prompt template from the specified file in the PROMPT_DIR."""
    file_path = os.path.join(PROMPT_DIR, template_file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt template file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading prompt template {file_path}: {e}")
        return None

def fill_placeholders(template_content: str, placeholder_values: Dict[str, str]) -> str:
    """Fills placeholders in the template content with provided values."""
    filled_content = template_content
    for placeholder, value in placeholder_values.items():
        # Ensure placeholder is a string, especially if it comes from an unexpected source.
        placeholder_key = f"{{{{{str(placeholder)}}}}}"
        filled_content = filled_content.replace(placeholder_key, str(value))
    return filled_content

def get_filled_prompt(template_file_name: str, placeholder_values: Dict[str, str]) -> Optional[str]:
    """Loads a prompt template and fills its placeholders."""
    template_content = load_prompt_template(template_file_name)
    if template_content:
        return fill_placeholders(template_content, placeholder_values)
    return None

def load_node_descriptions(description_file_path: str = NODE_DESCRIPTION_FILE_PATH) -> Dict[str, str]:
    """Loads node descriptions from the specified file."""
    descriptions: Dict[str, str] = {}
    if not os.path.exists(description_file_path):
        logger.warning(f"Node description file not found: {description_file_path}. Returning empty descriptions.")
        # Attempt to create the directory and an empty file if it doesn't exist.
        try:
            os.makedirs(os.path.dirname(description_file_path), exist_ok=True)
            with open(description_file_path, 'w', encoding='utf-8') as f:
                # Optionally write a header or initial comment
                f.write("# Node Descriptions (Format: block_type_name: Description)\n")
            logger.info(f"Created an empty node description file: {description_file_path}")
        except Exception as e:
            logger.error(f"Error creating node description file {description_file_path}: {e}")
        return descriptions
        
    try:
        with open(description_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): # Skip empty lines and comments
                    continue
                if ':' in line:
                    parts = line.split(':', 1)
                    block_type = parts[0].strip()
                    description = parts[1].strip()
                    if block_type and description:
                        descriptions[block_type] = description
                    else:
                        logger.warning(f"Skipping malformed line in {description_file_path}: {line}")
                else:
                    logger.warning(f"Skipping line without colon in {description_file_path}: {line}")
    except Exception as e:
        logger.error(f"Error loading node descriptions from {description_file_path}: {e}")
    return descriptions

def append_node_description(block_type: str, description: str, description_file_path: str = NODE_DESCRIPTION_FILE_PATH) -> None:
    """Appends a new node description to the specified file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(description_file_path), exist_ok=True)
        with open(description_file_path, 'a', encoding='utf-8') as f:
            f.write(f"{block_type}: {description}\n")
        logger.info(f"Appended description for '{block_type}' to {description_file_path}")
    except Exception as e:
        logger.error(f"Error appending node description for '{block_type}' to {description_file_path}: {e}")

def load_raw_prompt_file(file_path: str) -> Optional[str]:
    """Loads raw content from the specified file path."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading prompt file {file_path}: {e}")
        return None

def get_sas_step1_formatted_prompt(user_task_description: str) -> Optional[str]:
    """
    Loads the SAS step 1 prompt and formats it with the user's task description.
    Additionally includes available block descriptions to ensure generated steps
    strictly correspond to available blocks.
    """
    base_prompt_content = load_raw_prompt_file(SAS_STEP1_PROMPT_FILE_PATH)
    if not base_prompt_content:
        return None
    
    # Load available block descriptions
    node_descriptions = load_node_descriptions()
    if not node_descriptions:
        logger.warning("No node descriptions loaded. Generated process may not align with available blocks.")
        available_blocks_section = "\n## Available Robot Control Blocks\n\n**Warning**: No block descriptions available. Please ensure all generated steps can be implemented with standard robot control blocks.\n"
    else:
        # Format the node descriptions into a readable section
        available_blocks_section = "\n## Available Robot Control Blocks\n\n"
        available_blocks_section += "**CRITICAL REQUIREMENT**: All generated process steps MUST strictly correspond to the following available blocks. Do NOT create steps that exceed these block capabilities.\n\n"
        available_blocks_section += "### Block Types and Their Capabilities:\n\n"
        
        for block_type, description in sorted(node_descriptions.items()):
            available_blocks_section += f"- **{block_type}**: {description}\n"
        
        available_blocks_section += "\n### Mapping Requirements:\n\n"
        available_blocks_section += "1. **Each step in your process description MUST map to one of the above block types**\n"
        available_blocks_section += "2. **Do NOT describe any functionality that cannot be achieved with these blocks**\n" 
        available_blocks_section += "3. **When describing steps, explicitly mention which block type(s) will be used**\n"
        available_blocks_section += "4. **Pay attention to precautions and limitations mentioned for each block**\n"
        available_blocks_section += "5. **Ensure proper sequence and dependencies (e.g., 'select robot' before movement, 'set motor' before movements)**\n\n"
    
    # Insert the available blocks section before the example
    # Find the position to insert (before "## Example Fewshot")
    example_pos = base_prompt_content.find("## Example Fewshot")
    if example_pos != -1:
        # Insert before the example section
        modified_prompt = base_prompt_content[:example_pos] + available_blocks_section + base_prompt_content[example_pos:]
    else:
        # If "Example Fewshot" not found, append before the end
        modified_prompt = base_prompt_content + available_blocks_section
    
    # Append the user's task description in a structured way
    formatted_user_input = f"""
## User's Task Input (Process this new request)

[Robot Task Description: {user_task_description}]

## Your Detailed Process Description Plan (Based on the User's Task Input above)

**IMPORTANT REMINDER**: 
- Every step you describe MUST be implementable using ONLY the available blocks listed above
- Include block type references in your descriptions (e.g., "Block Type: `moveP`")
- Respect all precautions and limitations mentioned for each block type
- Do not invent capabilities that don't exist in the available blocks

Please generate your detailed process description plan now:
"""
    
    return modified_prompt + formatted_user_input

def get_sas_step1_task_list_generation_prompt(user_task_description: str, language: str = "en") -> Optional[str]:
    """
    Loads the SAS Step 1 task list generation prompt and formats it with task type descriptions,
    block descriptions, and the user's task description.
    """
    # Determine the correct prompt file based on language (though only EN is specified for now)
    # This could be expanded if other languages are added for step1_user_input_to_task_list_prompt
    base_prompt_content = load_raw_prompt_file(SAS_STEP1_TASK_LIST_PROMPT_PATH)
    if not base_prompt_content:
        logger.error(f"Failed to load task list generation prompt: {SAS_STEP1_TASK_LIST_PROMPT_PATH}")
        return None

    # 1. Load Task Type Descriptions
    task_type_descriptions_content = ""
    try:
        if os.path.exists(TASK_LIST_DEFINITION_DIR_PATH) and os.path.isdir(TASK_LIST_DEFINITION_DIR_PATH):
            for filename in sorted(os.listdir(TASK_LIST_DEFINITION_DIR_PATH)):
                if filename.endswith(".md"):
                    file_path = os.path.join(TASK_LIST_DEFINITION_DIR_PATH, filename)
                    task_desc = load_raw_prompt_file(file_path)
                    if task_desc:
                        task_type_descriptions_content += f"\n\n---\n### From file: {filename}\n---\n{task_desc}"
                    else:
                        logger.warning(f"Could not read task description file: {file_path}")
            if not task_type_descriptions_content:
                 logger.warning(f"No .md files found or read in {TASK_LIST_DEFINITION_DIR_PATH}")
                 task_type_descriptions_content = "No task type descriptions were loaded. Please ensure they are correctly placed."
        else:
            logger.error(f"Task list definition directory not found: {TASK_LIST_DEFINITION_DIR_PATH}")
            task_type_descriptions_content = "Error: Task type descriptions directory not found."
    except Exception as e:
        logger.error(f"Error loading task type descriptions from {TASK_LIST_DEFINITION_DIR_PATH}: {e}", exc_info=True)
        task_type_descriptions_content = f"Error loading task type descriptions: {e}"

    # 2. Load Allowed Block Types
    block_descriptions_content = load_raw_prompt_file(BLOCK_DESCRIPTION_FILE_PATH)
    if not block_descriptions_content:
        logger.warning(f"Block description file not found: {BLOCK_DESCRIPTION_FILE_PATH}. Using placeholder text.")
        block_descriptions_content = "No block descriptions were loaded. Feasibility assessment will be based on general knowledge."
    
    # 3. Fill placeholders in the base prompt
    placeholders = {
        "TASK_TYPE_DESCRIPTIONS": task_type_descriptions_content,
        "ALLOWED_BLOCK_TYPES": block_descriptions_content
    }
    
    prompt_with_context = fill_placeholders(base_prompt_content, placeholders)

    # 4. Append the user's task description
    # The prompt already has a section for the user's input, so we append it in a structured way.
    # Based on the modified prompt, the user input section is marked by:
    # "(User Robot Task Description will be appended here by the system)"
    # We can replace this line or append after it.
    # For simplicity, we'll append it after the main content of the prompt template.

    formatted_user_input_section = f"""

## User Robot Task Description (Process this to generate the Task List)

```text
{user_task_description}
```

## Generated Task List (JSON format as described in guidelines)

**IMPORTANT REMINDER**: 
- Analyze the user's description carefully.
- Identify the Main Task and decompose it into sub-tasks.
- Use ONLY the Task Types defined in the "Task Type Descriptions" section.
- Refer to the "Allowed Block Types" for contextual understanding of robot capabilities to ensure tasks are feasible.
- Ensure the output is a valid JSON list of task objects, following the structure specified in the guidelines (name, type, target, sub_tasks, description).
- Pay attention to hierarchical relationships and the order of tasks.

```json
[
  // Your generated JSON task list starts here
]
```
"""
    
    final_prompt = prompt_with_context + formatted_user_input_section
    logger.debug(f"Generated Step 1 Task List Prompt:\n{final_prompt[:1000]}...") # Log a snippet
    return final_prompt

# Example usage (for testing purposes, can be removed or commented out)
# if __name__ == '__main__':
#     # First, load the main placeholders definitions
#     placeholders_content = load_prompt_template("flow_placeholders.md")
#     # This typically would be parsed to extract default values if needed,
#     # but for this example, we'll manually define the runtime config.

#     runtime_config = {
#         "GENERAL_INSTRUCTION_INTRO": "As an AI assistant for robot flows...",
#         "ROBOT_NAME_EXAMPLE": "my_robot_007",
#         "POINT_NAME_EXAMPLE_1": "safe_point",
#         "POINT_NAME_EXAMPLE_2": "work_start_point",
#         "POINT_NAME_EXAMPLE_3": "work_end_point",
#         "NODE_TEMPLATE_DIR_PATH": "/data/robot_templates/model_xyz",
#         "OUTPUT_DIR_PATH": "/results/run_123",
#         "EXAMPLE_FLOW_STRUCTURE_DOC_PATH": "/docs/sample_flow.xml",
#         "BLOCK_ID_PREFIX_EXAMPLE": "op_block",
#         "RELATION_FILE_NAME_ACTUAL": "connections.xml",
#         "FINAL_FLOW_FILE_NAME_ACTUAL": "main_program.xml"
#     }

#     step1_prompt = get_filled_prompt("flow_step1_understand_input.md", runtime_config)
#     if step1_prompt:
#         print("--- Step 1 Prompt ---")
#         print(step1_prompt)
    
#     main_flow_prompt = get_filled_prompt("main_flow_prompt_template.md", runtime_config)
#     if main_flow_prompt:
#         print("\n--- Main Flow Prompt ---")
#         print(main_flow_prompt) 