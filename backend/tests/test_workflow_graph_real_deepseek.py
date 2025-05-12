import unittest
import os
from unittest.mock import patch, AsyncMock # AsyncMock might still be useful for tool internals if needed

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from backend.langgraphchat.graph.agent_state import AgentState
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
from backend.langgraphchat.tools import flow_tools # Import the actual tools
import logging

# Configure basic logging for tests to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper function similar to the one in test_workflow_graph_advanced.py
# to run the workflow and extract final planner state.
async def run_workflow_and_extract_planner_state(compiled_workflow, initial_state: AgentState, test_name: str):
    logger.info(f"--- Test Workflow Start: {test_name} ---")
    logger.info(f"Initial State Input: {initial_state.get('input')}")
    logger.info(f"Initial State Messages: {initial_state.get('messages')}")
    
    final_planner_state = None
    
    event_stream = compiled_workflow.astream_events(initial_state, version="v2")
    
    logger.info("\n  Workflow Events:")
    async for event in event_stream:
        event_type = event["event"]
        name = event.get("name")
        tags = event.get("tags", [])
        data = event.get("data")

        logger.info(f"    Event: {event_type}, Name: {name}, Tags: {tags}")

        if event_type == "on_chat_model_stream" and isinstance(data.get("chunk"), AIMessageChunk):
            chunk = data["chunk"]
            if chunk.content:
                logger.info(f"      LLM Stream Content: \"{chunk.content}\"")
            if chunk.tool_call_chunks:
                logger.info(f"      LLM Stream Tool Call Chunks: {chunk.tool_call_chunks}")
        elif event_type == "on_tool_start":
             logger.info(f"      Tool Start ({name}): Input = {data.get('input')}")
        elif event_type == "on_tool_end":
             logger.info(f"      Tool End ({name}): Output = {data.get('output')}")
        
        if event_type == "update_state":
            updated_keys = list(data.keys())
            logger.info(f"      State Updated by '{name}': Keys updated = {updated_keys}")
            if "messages" in data:
                logger.info(f"        Messages after update by '{name}': {data['messages']}")

        if event_type == "on_chain_end" and name == "LangGraph":
            if data and 'output' in data:
                raw_final_output = data['output']
                if isinstance(raw_final_output, list):
                    for item in reversed(raw_final_output):
                        if isinstance(item, dict) and 'planner' in item:
                            final_planner_state = item['planner']
                            break
                elif isinstance(raw_final_output, dict) and 'planner' in raw_final_output: # Single dict output case
                     final_planner_state = raw_final_output['planner']
                elif isinstance(raw_final_output, dict): # If the output is directly the planner state
                     final_planner_state = raw_final_output


    if final_planner_state and isinstance(final_planner_state, dict) and 'messages' in final_planner_state:
        logger.info(f"\nFinal State Output Messages (from extracted planner state): {final_planner_state.get('messages')}")
    else:
        logger.info(f"\nFinal State Output Messages: N/A (Planner state not found, not a dict, or no messages key)")

    logger.info(f"--- Test Workflow End: {test_name} ---")
    return final_planner_state


class TestWorkflowGraphWithRealDeepSeek(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        if not os.getenv("DEEPSEEK_API_KEY"):
            raise unittest.SkipTest("DEEPSEEK_API_KEY not set. Skipping real DeepSeek tests.")
        
        # You could also consider initializing the LLM once here if it's stateless
        # and doesn't cause issues between tests, but for clarity, per-test init is also fine.

    async def test_deepseek_with_tool_create_start_node(self):
        test_name = "test_deepseek_with_tool_create_start_node"
        logger.info(f"\nRunning {test_name}...")

        try:
            # Instantiate the real LLM
            llm = ChatDeepSeek(model="deepseek-chat", temperature=0) # Use a model that supports tool calling
            # You might need to specify other parameters like api_key if not picked from env by default
        except Exception as e:
            self.skipTest(f"Skipping test: Failed to initialize ChatDeepSeek - {e}")
            return

        # Use the real tools
        real_tools: List[BaseTool] = flow_tools 

        # Compile the workflow graph
        # Ensure custom_tools is passed if flow_tools is not the default or you want to be explicit
        compiled_workflow = compile_workflow_graph(llm=llm, custom_tools=real_tools)

        user_input = "创建一个movel节点"
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input, id="real_human_1")],
            flow_context={"current_flow_id": "test_flow_deepseek_real_tools_1"}, # Example context
            current_flow_id="test_flow_deepseek_real_tools_1",
            input_processed=False # Critical for input_handler_node
        )
        
        # Run the workflow
        planner_final_state = await run_workflow_and_extract_planner_state(
            compiled_workflow, initial_state, test_name
        )

        self.assertIsNotNone(planner_final_state, "Final planner state should not be None.")
        self.assertIsInstance(planner_final_state, dict, "Final planner state should be a dictionary.")
        
        final_messages = planner_final_state.get("messages", [])
        self.assertTrue(len(final_messages) >= 3, 
                        f"Expected at least 3 messages (Human, AI tool call, Tool, AI response), got {len(final_messages)}: {final_messages}")

        # 1. HumanMessage (already in initial_state, effectively the first message)
        self.assertIsInstance(final_messages[0], HumanMessage)
        self.assertEqual(final_messages[0].content, user_input)

        # 2. AIMessage with tool_calls
        # The LLM might add some conversational text before the tool call.
        ai_message_with_tool_call = None
        tool_message_from_execution = None
        final_ai_response_message = None

        for msg in final_messages[1:]: # Start from the second message
            if isinstance(msg, AIMessage) and msg.tool_calls:
                ai_message_with_tool_call = msg
                logger.info(f"Found AIMessage with tool_calls: {msg.tool_calls}")
                # We expect the create_node tool or similar to be called
                self.assertTrue(any(tc['name'].startswith("create_node") for tc in msg.tool_calls),
                                f"Expected a 'create_node' tool call. Got: {msg.tool_calls}")
                break
        
        self.assertIsNotNone(ai_message_with_tool_call, "Expected an AIMessage with tool_calls.")

        # 3. ToolMessage (result of tool execution)
        # Find the ToolMessage that corresponds to the AIMessage's tool call
        if ai_message_with_tool_call:
            expected_tool_call_id = ai_message_with_tool_call.tool_calls[0]['id']
            for msg in final_messages:
                if isinstance(msg, ToolMessage) and msg.tool_call_id == expected_tool_call_id:
                    tool_message_from_execution = msg
                    logger.info(f"Found ToolMessage: {msg.content}")
                    # The content of ToolMessage can be complex (e.g., JSON string of node data)
                    # For now, just assert it exists and is not empty
                    self.assertTrue(msg.content, "ToolMessage content should not be empty.")
                    break
        
        self.assertIsNotNone(tool_message_from_execution, "Expected a ToolMessage after tool execution.")

        # 4. Final AIMessage (LLM's response after tool execution)
        # This should be the last message in the list if the flow completes as expected
        if final_messages and isinstance(final_messages[-1], AIMessage) and not final_messages[-1].tool_calls:
            final_ai_response_message = final_messages[-1]
            logger.info(f"Found final AIMessage response: {final_ai_response_message.content}")
            self.assertTrue(len(final_ai_response_message.content) > 0, "Final AI response should not be empty.")
            # Add more specific assertions if needed, e.g., checking for keywords
            self.assertIn("创建", final_ai_response_message.content.lower(), "Final response should mention creation.")
        
        self.assertIsNotNone(final_ai_response_message, "Expected a final AIMessage without tool_calls.")
        
        # Add more assertions as needed based on the expected behavior of flow_tools
        # For example, if create_node is expected to be called, you could try to
        # verify side effects if your tools have any observable side effects (e.g., DB changes)
        # but that might be out of scope for this specific graph test.

    # You can add more test methods here for different scenarios with real tools
    # For example, a test for updating a node, deleting a node, etc.

if __name__ == '__main__':
    # Important: To run this test, you need to have DEEPSEEK_API_KEY set in your environment.
    # Example: DEEPSEEK_API_KEY="your_api_key" python -m unittest backend.tests.test_workflow_graph_real_deepseek
    unittest.main() 