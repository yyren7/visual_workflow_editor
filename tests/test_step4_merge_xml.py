import asyncio
import os
import pytest
from pathlib import Path
from typing import List, Optional

from backend.langgraphchat.graph.nodes.robot_flow_planner.state import RobotFlowAgentState, GeneratedXmlFile
from backend.langgraphchat.graph.nodes.robot_flow_planner.graph_builder import generate_final_flow_xml_node

# Define the directory containing the test XML files
TEST_XML_DIR = Path("/workspace/test_robot_flow_output_deepseek_interactive")

async def read_text_from_file_async(file_path: str) -> Optional[str]:
    """Asynchronously reads text content from a file."""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Path(file_path).read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

@pytest.mark.asyncio
async def test_generate_final_flow_xml_node_merging():
    """
    Tests the generate_final_flow_xml_node function by providing it with
    block XMLs and a relation XML from a test directory.
    """
    # Ensure the test directory and relation file exist
    if not TEST_XML_DIR.exists() or not (TEST_XML_DIR / "relation.xml").exists():
        pytest.skip(f"Test XML directory {TEST_XML_DIR} or relation.xml not found.")

    # 1. Read relation.xml content
    relation_xml_path = TEST_XML_DIR / "relation.xml"
    relation_content = await read_text_from_file_async(str(relation_xml_path))
    assert relation_content is not None, f"Failed to read {relation_xml_path}"

    # 2. Read block_*.xml contents
    block_xml_files: List[GeneratedXmlFile] = []
    # Gather file read tasks
    read_tasks = []
    file_paths_for_blocks = []

    for item in TEST_XML_DIR.iterdir():
        if item.is_file() and item.name.startswith("block_") and item.name.endswith(".xml"):
            file_paths_for_blocks.append(item)
            read_tasks.append(read_text_from_file_async(str(item)))
    
    block_contents = await asyncio.gather(*read_tasks)

    for i, content in enumerate(block_contents):
        item_path = file_paths_for_blocks[i]
        assert content is not None, f"Failed to read {item_path}"
        
        # Extract block_id and type from filename or content if possible, or use placeholder
        # For simplicity, using filename parts or placeholders
        parts = item_path.name.split('_') # e.g., block_uuid_1_select_robot.xml
        block_id_from_file = parts[2] if len(parts) > 2 else "unknown_id"
        block_type_from_file = parts[3].split('.')[0] if len(parts) > 3 else "unknown_type"

        block_xml_files.append(GeneratedXmlFile(
            block_id=block_id_from_file, # Placeholder or derived from filename
            type=block_type_from_file, # Placeholder or derived from filename
            source_description=f"Content of {item_path.name}",
            status="success", # Assuming files exist and are readable for this test
            file_path=str(item_path),
            xml_content=content
        ))
    
    assert len(block_xml_files) > 0, f"No block XML files found in {TEST_XML_DIR}"

    # 3. Initialize RobotFlowAgentState
    initial_state = RobotFlowAgentState(
        user_input="Test case for merging XMLs",
        relation_xml_content=relation_content,
        generated_node_xmls=block_xml_files,
        dialog_state="individual_xmls_generated" # A state where merging would occur
    )

    # 4. Call the node function
    initial_state.config = {"OUTPUT_DIR_PATH": "/tmp/test_output"} # Dummy path
    
    updated_state = await generate_final_flow_xml_node(initial_state)

    # 5. Assertions
    assert updated_state.error_message is None, f"Node returned an error: {updated_state.error_message}"
    assert updated_state.is_error is False, "Node indicated an error state."
    assert updated_state.final_flow_xml_content is not None, "Final flow XML content is None."
    assert isinstance(updated_state.final_flow_xml_content, str), "Final flow XML content is not a string."
    assert len(updated_state.final_flow_xml_content) > 0, "Final flow XML content is empty."

    print("\\n--- Merged Final Flow XML ---")
    print(updated_state.final_flow_xml_content)
    print("--- End of Merged XML ---")
    
    assert "<block" in updated_state.final_flow_xml_content.lower(), "Merged XML does not seem to contain block elements."
    # The relation.xml itself is expected to be merged, so its content might not be directly wrapped in <relation>
    # Instead, its <relations> (plural) content should be part of the final merged XML.
    # We need to check the actual structure of relation.xml in the test directory.
    # Assuming relation.xml contains a <relations> tag with <relation> tags inside.
    assert "<relations>" in updated_state.final_flow_xml_content.lower() or \
           "<relation " in updated_state.final_flow_xml_content.lower(), \
           "Merged XML does not seem to contain relation elements from relation.xml."


pytest_plugins = ['pytester']

async def main():
    await test_generate_final_flow_xml_node_merging()

if __name__ == "__main__":
    asyncio.run(main()) 