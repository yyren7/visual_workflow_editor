import asyncio
import os
import pytest
from pathlib import Path
from typing import List, Optional

from backend.langgraphchat.graph.nodes.robot_flow_planner.state import RobotFlowAgentState, GeneratedXmlFile
from backend.langgraphchat.graph.nodes.robot_flow_planner.graph_builder import generate_final_flow_xml_node
from backend.langgraphchat.utils.file_ops import ensure_file_exists, save_text_to_file, read_text_from_file

# Define the directory containing the test XML files
TEST_XML_DIR = Path("/workspace/test_robot_flow_output_deepseek_interactive")

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
    relation_content = await read_text_from_file(str(relation_xml_path))
    assert relation_content is not None, f"Failed to read {relation_xml_path}"

    # 2. Read block_*.xml contents
    block_xml_files: List[GeneratedXmlFile] = []
    for item in TEST_XML_DIR.iterdir():
        if item.is_file() and item.name.startswith("block_") and item.name.endswith(".xml"):
            content = await read_text_from_file(str(item))
            assert content is not None, f"Failed to read {item}"
            # The actual file path is not strictly needed for the merge logic itself if content is provided,
            # but good to have for completeness if the node ever uses it.
            block_xml_files.append(GeneratedXmlFile(file_path=str(item), xml_content=content, description=f"Content of {item.name}"))
    
    assert len(block_xml_files) > 0, f"No block XML files found in {TEST_XML_DIR}"

    # 3. Initialize RobotFlowAgentState
    initial_state = RobotFlowAgentState(
        user_input="Test case for merging XMLs",
        relation_xml_content=relation_content,
        generated_node_xmls=block_xml_files,
        dialog_state="individual_xmls_generated" # A state where merging would occur
    )

    # 4. Call the node function
    # Mocking config if necessary for path resolutions within the node, though not directly used for merging logic itself
    initial_state.config = {"OUTPUT_DIR_PATH": "/tmp/test_output"} # Dummy path
    
    updated_state = await generate_final_flow_xml_node(initial_state)

    # 5. Assertions
    assert updated_state.error_message is None, f"Node returned an error: {updated_state.error_message}"
    assert updated_state.is_error is False, "Node indicated an error state."
    assert updated_state.final_flow_xml_content is not None, "Final flow XML content is None."
    assert isinstance(updated_state.final_flow_xml_content, str), "Final flow XML content is not a string."
    assert len(updated_state.final_flow_xml_content) > 0, "Final flow XML content is empty."

    # Optional: Print or save the merged XML for manual inspection
    print("\\n--- Merged Final Flow XML ---")
    print(updated_state.final_flow_xml_content)
    print("--- End of Merged XML ---")
    
    # You could add more specific assertions here, e.g., checking for certain tags or structure
    # For example, check if it starts with <flow> and ends with </flow> (adjust based on actual root tag)
    # For now, we assume the merge logic inside the node is responsible for valid XML structure.
    # A more robust test might parse the XML and validate its schema or key elements.
    
    # Example: Save to a temporary file for inspection
    # output_merged_xml_path = Path("/tmp/test_output/merged_flow_for_test.xml")
    # if initial_state.config and initial_state.config.get("OUTPUT_DIR_PATH"):
    #     output_merged_xml_path = Path(initial_state.config["OUTPUT_DIR_PATH"]) / "merged_flow_for_test.xml"
    #     output_merged_xml_path.parent.mkdir(parents=True, exist_ok=True)
    #     await save_text_to_file(str(output_merged_xml_path), updated_state.final_flow_xml_content)
    #     print(f"Merged XML saved to {output_merged_xml_path}")

    assert "<block" in updated_state.final_flow_xml_content.lower(), "Merged XML does not seem to contain block elements."
    assert "<relation" in updated_state.final_flow_xml_content.lower(), "Merged XML does not seem to contain relation elements."

    # Example of what inputs the node expects (based on typical usage)
    # generate_final_flow_xml_node reads from state.generated_node_xmls[*].xml_content
    # and state.relation_xml_content

pytest_plugins = ['pytester']

async def main():
    # This is a helper if you want to run this test script directly
    # You'd typically use `pytest tests/test_step4_merge_xml.py`
    await test_generate_final_flow_xml_node_merging()

if __name__ == "__main__":
    asyncio.run(main()) 