import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROMPT_DIR = "/workspace/database/prompt_database/flow_structure_prompt/"

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
        filled_content = filled_content.replace(f"{{{{{placeholder}}}}}", str(value))
    return filled_content

def get_filled_prompt(template_file_name: str, placeholder_values: Dict[str, str]) -> Optional[str]:
    """Loads a prompt template and fills its placeholders."""
    template_content = load_prompt_template(template_file_name)
    if template_content:
        return fill_placeholders(template_content, placeholder_values)
    return None

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