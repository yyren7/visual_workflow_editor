import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Type, Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage, AIMessageChunk
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from backend.langgraphchat.graph.agent_state import AgentState
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph

# Define a very simple schema for the mock tool to avoid RecursionError
class SimpleMockToolSchema(BaseModel):
    pass

class MockToolArgsSchema1(BaseModel):
    query: str = Field(description="A query for the tool")
    count: int = Field(default=1, description="A count parameter")

class MockToolArgsSchema2(BaseModel):
    item_id: str = Field(description="ID of the item to process")

# Custom Mock Tool class inheriting from BaseTool
class MockToolForTest(BaseTool):
    name: str
    description: str
    args_schema: Type[BaseModel] = SimpleMockToolSchema
    return_direct: bool = False
    _arun_async_mock: AsyncMock

    def __init__(self, name: str, description: str, output_value: Any, args_schema_override: Type[BaseModel] = None, **kwargs):
        arun_mock = AsyncMock(return_value=output_value)
        super().__init__(name=name, description=description, **kwargs)
        if args_schema_override:
            self.args_schema = args_schema_override
        self._arun_async_mock = arun_mock

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        return await self._arun_async_mock(**kwargs)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("This mock tool is async only.")

class TestWorkflowGraphAdvanced(unittest.IsolatedAsyncioTestCase):

    async def _run_workflow_and_print_events(self, compiled_workflow, initial_state: AgentState, test_name: str) -> Dict:
        print(f"\n--- Test Workflow Start: {test_name} ---")
        print(f"Initial State Input: {initial_state.get('input')}")
        print(f"Initial State Messages: {initial_state.get('messages')}")
        print(f"Initial State Flow Context: {initial_state.get('flow_context')}")
        print(f"Initial State Input Processed: {initial_state.get('input_processed')}")
        
        final_state_output_from_event = None # This will be the direct content of 'planner' node state
        
        event_stream = compiled_workflow.astream_events(initial_state, version="v2")
        
        print("\n  Workflow Events:")
        async for event in event_stream:
            event_type = event["event"]
            name = event.get("name")
            tags = event.get("tags", [])
            data = event.get("data")

            print(f"    Event: {event_type}, Name: {name}, Tags: {tags}")

            if event_type == "on_chat_model_stream":
                chunk = data.get("chunk")
                if isinstance(chunk, AIMessageChunk):
                    if chunk.content:
                        print(f"      LLM Stream Content: \"{chunk.content}\"")
                    if chunk.tool_call_chunks:
                        print(f"      LLM Stream Tool Call Chunks: {chunk.tool_call_chunks}")
            elif event_type == "on_tool_start":
                 print(f"      Tool Start ({name}): Input = {data.get('input')}")
            elif event_type == "on_tool_end":
                 print(f"      Tool End ({name}): Output = {data.get('output')}")
            
            if event_type == "update_state":
                updated_keys = list(data.keys())
                print(f"      State Updated by '{name}': Keys updated = {updated_keys}")
                if "messages" in data: # Log messages if updated by any node
                    print(f"        Messages after update by '{name}': {data['messages']}")


            if event_type == "on_chain_end" and name == "LangGraph":
                print(f"      EVENT DATA for on_chain_end (LangGraph): {data}")
                if data and 'output' in data:
                    raw_final_state_list_or_dict = data['output']
                    print(f"      Captured raw_final_state_list_or_dict from on_chain_end (LangGraph) data['output']: {raw_final_state_list_or_dict}")
                    
                    processed_planner_state = None
                    if isinstance(raw_final_state_list_or_dict, list):
                        for item in reversed(raw_final_state_list_or_dict):
                            if isinstance(item, dict) and 'planner' in item and isinstance(item['planner'], dict):
                                processed_planner_state = item['planner']
                                print(f"        Extracted 'planner' state from list: {processed_planner_state}")
                                break
                        if not processed_planner_state:
                             print("        No 'planner' state found in the list of final outputs, or 'planner' value is not a dict.")
                    elif isinstance(raw_final_state_list_or_dict, dict):
                        # If the output is a single dict, it might be {'planner': actual_state} or just actual_state
                        if 'planner' in raw_final_state_list_or_dict and isinstance(raw_final_state_list_or_dict['planner'], dict):
                            processed_planner_state = raw_final_state_list_or_dict['planner']
                            print(f"        Extracted 'planner' state from dict: {processed_planner_state}")
                        # It could also be that the graph directly returns the final state dict (e.g. if only one node at the end)
                        # In our case, the 'planner' node itself returns a dict like {'messages': [...], 'input': None, ...}
                        # So, if raw_final_state_list_or_dict *is* that dict, we use it.
                        # Let's assume for now the structure from list traversal is the primary path.
                        # If not found via list or direct {'planner':...}, then maybe raw_final_state_list_or_dict *is* the planner state.
                        # This part might need refinement based on actual LangGraph output variety.
                        # For now, we prioritize extracting from a list or a dict with a 'planner' key.
                        # If the output is directly the planner's state dict (e.g. from a simpler graph):
                        elif 'messages' in raw_final_state_list_or_dict : # Heuristic: if it has 'messages', it might be the planner state itself
                            processed_planner_state = raw_final_state_list_or_dict
                            print(f"        Raw final state is a dict, and looks like planner state itself: {processed_planner_state}")

                    final_state_output_from_event = processed_planner_state
        
        # Print messages from the extracted planner state
        if final_state_output_from_event and isinstance(final_state_output_from_event, dict) and 'messages' in final_state_output_from_event:
            print(f"\nFinal State Output Messages (from extracted planner state): {final_state_output_from_event.get('messages')}")
        else:
            print(f"\nFinal State Output Messages: N/A (Planner state not found, not a dict, or no messages key)")

        print(f"--- Test Workflow End: {test_name} ---\n")
        # The assertion is now on final_state_output_from_event, which should be the planner's dict state
        self.assertIsNotNone(final_state_output_from_event, "Final planner state output (after processing list/dict) should not be None")
        self.assertIsInstance(final_state_output_from_event, dict, "Final planner state should be a dictionary.")
        return final_state_output_from_event


    async def test_simple_conversation_no_tool_calls(self):
        test_name = "test_simple_conversation_no_tool_calls"
        print(f"\nRunning {test_name}...")
        mock_llm = MagicMock()
        final_response_content = "Hello! This is a simple response from the LLM."
        mock_llm_with_tools = MagicMock()
        async def mock_astream_simple_gen(*args, **kwargs):
            print(f"    Mock LLM ({test_name}): Received input for astream: args={args}, kwargs={kwargs}")
            yield AIMessageChunk(content="Hello! ", id="chunk_s_1")
            yield AIMessageChunk(content="This is a simple response ", id="chunk_s_1")
            yield AIMessageChunk(content="from the LLM.", id="chunk_s_1")
        mock_llm_with_tools.astream = MagicMock(return_value=mock_astream_simple_gen())
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_tools = []
        compiled_workflow = compile_workflow_graph(llm=mock_llm, custom_tools=mock_tools)
        user_input = "Hi there, can you say hello without tools?"
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input, id="human_msg_simple_1")],
            flow_context={},
            current_flow_id="test_flow_simple_1",
            input_processed=False
        )
        
        planner_final_state = await self._run_workflow_and_print_events(compiled_workflow, initial_state, test_name)
        
        final_messages = None
        if planner_final_state and isinstance(planner_final_state, dict) and 'messages' in planner_final_state:
            final_messages = planner_final_state['messages']
        
        self.assertIsNotNone(final_messages, "Final messages should not be None after extraction from planner state")
        self.assertEqual(len(final_messages), 2)
        self.assertIsInstance(final_messages[0], HumanMessage)
        self.assertEqual(final_messages[0].content, user_input)
        self.assertIsInstance(final_messages[1], AIMessage)
        self.assertEqual(final_messages[1].content, final_response_content)
        self.assertFalse(hasattr(final_messages[1], 'tool_calls') and final_messages[1].tool_calls)
        mock_llm_with_tools.astream.assert_called_once()

    async def test_single_tool_call_with_args(self):
        test_name = "test_single_tool_call_with_args"
        print(f"\nRunning {test_name}...")
        mock_llm = MagicMock()
        tool_name_to_call = "query_processor_tool"
        tool_call_id = "tool_call_query_proc_123"
        tool_args = {"query": "search for advanced cats", "count": 3}
        
        ai_chunk_with_tool_call = AIMessageChunk(
            content=f"Okay, I will use the {tool_name_to_call} for your advanced request.",
            tool_calls=[ToolCall(name=tool_name_to_call, args=tool_args, id=tool_call_id)],
            id="ai_chunk_tool_call_single_1"
        )
        
        mock_tool_output_content = f"Processed query '{tool_args['query']}' {tool_args['count']} times. Result: Found many advanced cats."
        stringified_mock_tool_output = str(mock_tool_output_content)

        final_response_content_after_tool = f"The advanced tool said: {mock_tool_output_content}. What next?"
        ai_chunk_final_answer = AIMessageChunk(content=final_response_content_after_tool, id="ai_chunk_final_single_1")

        mock_llm_with_tools = MagicMock()
        async def mock_astream_tool_gen_1(*args, **kwargs):
            print(f"    Mock LLM ({test_name} - Phase 1): Received input for astream: args={args}, kwargs={kwargs}")
            yield ai_chunk_with_tool_call
        async def mock_astream_tool_gen_2(*args, **kwargs):
            print(f"    Mock LLM ({test_name} - Phase 2): Received input for astream: args={args}, kwargs={kwargs}")
            yield AIMessageChunk(content="The advanced tool said: ", id="final_single_chunk_part1")
            yield AIMessageChunk(content=mock_tool_output_content, id="final_single_chunk_part1")
            yield AIMessageChunk(content=". What next?", id="final_single_chunk_part1")

        mock_llm_with_tools.astream = MagicMock(side_effect=[
            mock_astream_tool_gen_1(),
            mock_astream_tool_gen_2()
        ])
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        mock_tool_instance = MockToolForTest(
            name=tool_name_to_call,
            description="A mock tool that processes queries with a count.",
            output_value=stringified_mock_tool_output,
            args_schema_override=MockToolArgsSchema1
        )
        mock_tools = [mock_tool_instance]

        compiled_workflow = compile_workflow_graph(llm=mock_llm, custom_tools=mock_tools)
        user_input = "Use your advanced query tool for cats, three times."
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input, id="human_msg_single_args_1")],
            flow_context={"user_preference": "likes_advanced_cats"},
            current_flow_id="test_flow_single_tool_args_advanced_1",
            input_processed=False
        )

        planner_final_state = await self._run_workflow_and_print_events(compiled_workflow, initial_state, test_name)
        
        final_messages = None
        if planner_final_state and isinstance(planner_final_state, dict) and 'messages' in planner_final_state:
            final_messages = planner_final_state['messages']

        self.assertIsNotNone(final_messages, "Final messages should not be None after extraction from planner state")
        self.assertEqual(len(final_messages), 4)
        
        self.assertEqual(final_messages[1].tool_calls[0]['args'], tool_args)
        self.assertEqual(final_messages[2].content, stringified_mock_tool_output)
        self.assertEqual(final_messages[3].content, final_response_content_after_tool)
        
        self.assertEqual(mock_llm_with_tools.astream.call_count, 2)
        mock_tool_instance._arun_async_mock.assert_called_once_with(**tool_args)

    async def test_two_sequential_tool_calls(self):
        test_name = "test_two_sequential_tool_calls"
        print(f"\nRunning {test_name}...")
        mock_llm = MagicMock()

        tool_A_name = "item_fetch_tool_v2"
        tool_A_call_id = "tool_call_A_v2_001"
        tool_A_args = {"item_id": "item789"}
        tool_A_output_content = "Fetched item789: <detailed_item_data_v2>"
        stringified_tool_A_output = str(tool_A_output_content)

        tool_B_name = "item_process_tool_v2"
        tool_B_call_id = "tool_call_B_v2_002"
        tool_B_args = {"item_id": "item789"}
        tool_B_output_content = "Processed item789 v2 successfully with extra steps."
        stringified_tool_B_output = str(tool_B_output_content)
        
        ai_chunk_call_tool_A = AIMessageChunk(
            content="Okay, first I need to fetch the v2 item.",
            tool_calls=[ToolCall(name=tool_A_name, args=tool_A_args, id=tool_A_call_id)],
            id="ai_chunk_A_v2_1"
        )
        ai_chunk_call_tool_B = AIMessageChunk(
            content="V2 Item fetched. Now I will process it using the v2 method.",
            tool_calls=[ToolCall(name=tool_B_name, args=tool_B_args, id=tool_B_call_id)],
            id="ai_chunk_B_v2_1"
        )
        final_answer_content = f"After v2 fetching and v2 processing: {tool_B_output_content} All done."
        
        mock_llm_with_tools = MagicMock()
        async def stream_phase1_seq(*args, **kwargs):
            print(f"    Mock LLM ({test_name} - Phase 1): Received input for astream: args={args}, kwargs={kwargs}")
            yield ai_chunk_call_tool_A
        async def stream_phase2_seq(*args, **kwargs):
            print(f"    Mock LLM ({test_name} - Phase 2): Received input for astream: args={args}, kwargs={kwargs}")
            yield ai_chunk_call_tool_B
        async def stream_phase3_seq(*args, **kwargs):
            print(f"    Mock LLM ({test_name} - Phase 3): Received input for astream: args={args}, kwargs={kwargs}")
            yield AIMessageChunk(content="After v2 fetching and v2 processing: ",id="final_seq_chunk_part1")
            yield AIMessageChunk(content=tool_B_output_content, id="final_seq_chunk_part1")
            yield AIMessageChunk(content=" All done.", id="final_seq_chunk_part1")
        
        mock_llm_with_tools.astream = MagicMock(side_effect=[
            stream_phase1_seq(), stream_phase2_seq(), stream_phase3_seq()
        ])
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        mock_tool_A_instance = MockToolForTest(
            name=tool_A_name, description="Fetches an item (v2).",
            output_value=stringified_tool_A_output, args_schema_override=MockToolArgsSchema2
        )
        mock_tool_B_instance = MockToolForTest(
            name=tool_B_name, description="Processes an item (v2).",
            output_value=stringified_tool_B_output, args_schema_override=MockToolArgsSchema2
        )
        mock_tools_list = [mock_tool_A_instance, mock_tool_B_instance]

        compiled_workflow = compile_workflow_graph(llm=mock_llm, custom_tools=mock_tools_list)
        user_input_seq = "Fetch and process item789 using v2 methods."
        initial_state_seq = AgentState(
            input=user_input_seq,
            messages=[HumanMessage(content=user_input_seq, id="human_msg_seq_v2_1")],
            flow_context={}, 
            current_flow_id="test_flow_seq_tools_v2_1",
            input_processed=False
        )

        planner_final_state = await self._run_workflow_and_print_events(compiled_workflow, initial_state_seq, test_name)

        final_messages = None
        if planner_final_state and isinstance(planner_final_state, dict) and 'messages' in planner_final_state:
            final_messages = planner_final_state['messages']
            
        self.assertIsNotNone(final_messages, "Final messages should not be None after extraction from planner state")
        self.assertEqual(len(final_messages), 6)
        
        self.assertEqual(final_messages[1].tool_calls[0]['name'], tool_A_name)
        self.assertEqual(final_messages[1].tool_calls[0]['args'], tool_A_args)
        self.assertEqual(final_messages[2].content, stringified_tool_A_output)

        self.assertEqual(final_messages[3].tool_calls[0]['name'], tool_B_name)
        self.assertEqual(final_messages[3].tool_calls[0]['args'], tool_B_args)
        self.assertEqual(final_messages[4].content, stringified_tool_B_output)
        
        self.assertEqual(final_messages[5].content, final_answer_content)

        self.assertEqual(mock_llm_with_tools.astream.call_count, 3)
        mock_tool_A_instance._arun_async_mock.assert_called_once_with(**tool_A_args)
        mock_tool_B_instance._arun_async_mock.assert_called_once_with(**tool_B_args)

if __name__ == '__main__':
    # This allows running tests directly from the file
    # You might need to adjust PYTHONPATH or run with `python -m unittest discover backend.tests`
    # or `python -m unittest backend.tests.test_workflow_graph_advanced`
    unittest.main() 