import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Type, Any # Import Type and Any

from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage, AIMessageChunk
from langchain_core.tools import BaseTool # Import BaseTool
from pydantic import BaseModel, Field

from backend.langgraphchat.graph.agent_state import AgentState
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph

# We will not import real tools for now to avoid complex patching and RecursionErrors
# from backend.langgraphchat.tools.flow_tools import get_flow_info_tool_func, GetFlowInfoSchema 

# Define a very simple schema for the mock tool to avoid RecursionError
class SimpleMockToolSchema(BaseModel):
    pass # An empty schema, or with very simple, non-recursive fields if needed

# Custom Mock Tool class inheriting from BaseTool
class MockToolForTest(BaseTool):
    name: str
    description: str
    args_schema: Type[BaseModel] = SimpleMockToolSchema # Default simple schema
    return_direct: bool = False

    # Store the mock for _arun on the instance
    _arun_async_mock: AsyncMock

    def __init__(self, name: str, description: str, output_value: Any, args_schema_override: Type[BaseModel] = None, **kwargs):
        # Need to handle Pydantic V2 style initialization if BaseTool is Pydantic V2
        # For now, assuming standard Pydantic v1/v2 compatible BaseTool init if name/desc are fields
        # Pass _arun_async_mock via kwargs to avoid Pydantic validation if it's not a field
        arun_mock = AsyncMock(return_value=output_value)
        super().__init__(name=name, description=description, _arun_async_mock=arun_mock, **kwargs)
        if args_schema_override:
            self.args_schema = args_schema_override
        # Pydantic v2 might complain about setting _arun_async_mock directly if not a model field
        # A cleaner way for Pydantic V2 is to pass it via model_construct or ensure it is a private attr
        self._arun_async_mock = arun_mock # Explicitly set it after super().__init__ if not passed to super


    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # BaseTool's ainvoke method will call this _arun method.
        # The arguments to the tool (from tool_calls['args']) will be passed as kwargs.
        return await self._arun_async_mock(**kwargs) # Pass kwargs to the mock

    # _run is not strictly necessary if we only use ainvoke/_arun
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("This mock tool is async only.")

class TestWorkflowGraph(unittest.IsolatedAsyncioTestCase):

    async def test_simple_conversation_no_tool_calls(self):
        """测试一个简单的对话流程，LLM直接回复，没有工具调用。"""
        mock_llm = MagicMock()
        final_response_content = "Hello! How can I help you today?"
        mock_llm_with_tools = MagicMock()
        async def mock_astream_simple_gen(*args, **kwargs):
            yield AIMessageChunk(content=final_response_content, id="ai_chunk_1")
        mock_llm_with_tools.astream = MagicMock(return_value=mock_astream_simple_gen()) 
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_tools = []
        compiled_workflow = compile_workflow_graph(llm=mock_llm, custom_tools=mock_tools)
        user_input = "Hi there!"
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input, id="human_msg_1")],
            flow_context={},
            current_flow_id="test_flow_1"
        )
        final_output_state_obj = await compiled_workflow.ainvoke(initial_state)
        self.assertIsInstance(final_output_state_obj, dict) 
        final_messages = final_output_state_obj.get("messages")
        self.assertIsNotNone(final_messages)
        self.assertEqual(len(final_messages), 2) 
        self.assertIsInstance(final_messages[0], HumanMessage)
        self.assertEqual(final_messages[0].content, user_input)
        self.assertIsInstance(final_messages[1], AIMessage) 
        self.assertEqual(final_messages[1].content, final_response_content)
        self.assertFalse(hasattr(final_messages[1], 'tool_calls') and final_messages[1].tool_calls)
        mock_llm_with_tools.astream.assert_called_once()

    async def test_conversation_with_tool_call(self):
        """测试一个包含工具调用的对话流程。"""
        mock_llm = MagicMock()
        tool_name_to_call = "mock_tool_for_flow_info" # Use a distinct mock tool name
        tool_call_id = "tool_call_mock_flow_info_123"
        
        ai_chunk_with_tool_call = AIMessageChunk(
            content="Okay, I need to use a mock tool.",
            tool_calls=[ToolCall(name=tool_name_to_call, args={}, id=tool_call_id)], 
            id="ai_chunk_tool_call_1"
        )
        
        mock_tool_output_dict = {"success": True, "message": "Mock tool executed", "data": "Mock Flow Info"}
        stringified_mock_tool_output = str(mock_tool_output_dict)

        final_response_content_after_tool = f"The tool returned: {stringified_mock_tool_output}. This is the final answer."
        ai_chunk_final_answer = AIMessageChunk(content=final_response_content_after_tool, id="ai_chunk_final_1")

        mock_llm_with_tools = MagicMock()
        async def mock_astream_tool_gen_1(*args, **kwargs):
            yield ai_chunk_with_tool_call
        async def mock_astream_tool_gen_2(*args, **kwargs):
            yield ai_chunk_final_answer
        mock_llm_with_tools.astream = MagicMock(side_effect=[
            mock_astream_tool_gen_1(), 
            mock_astream_tool_gen_2()
        ])
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        # 2. Create an instance of our custom MockToolForTest
        mock_tool_instance = MockToolForTest(
            name=tool_name_to_call,
            description="A custom mock tool for testing flow info.",
            output_value=stringified_mock_tool_output,
            args_schema_override=SimpleMockToolSchema # Ensure simple schema is used
        )
        
        mock_tools = [mock_tool_instance]

        # 3. 编译工作流
        try:
            compiled_workflow = compile_workflow_graph(llm=mock_llm, custom_tools=mock_tools)
        except Exception as e:
            self.fail(f"compile_workflow_graph failed during setup: {e}")

        # 4. 输入状态
        user_input = "Can you use the mock tool?"
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input, id="human_msg_1")],
            flow_context={"some_context": "test"}, # current_flow_id not strictly needed if tool is fully mocked
            current_flow_id="test_flow_mock_tool_1" 
        )

        # 5. 执行工作流
        final_output_state_obj = await compiled_workflow.ainvoke(initial_state)

        # 6. 断言
        self.assertIsInstance(final_output_state_obj, dict)
        final_messages = final_output_state_obj.get("messages")
        
        self.assertIsNotNone(final_messages)
        self.assertEqual(len(final_messages), 4) 
        
        self.assertIsInstance(final_messages[0], HumanMessage)
        self.assertEqual(final_messages[0].content, user_input)
        
        self.assertIsInstance(final_messages[1], AIMessage)
        self.assertEqual(final_messages[1].content, "Okay, I need to use a mock tool.")
        self.assertTrue(hasattr(final_messages[1], 'tool_calls') and final_messages[1].tool_calls)
        self.assertEqual(len(final_messages[1].tool_calls), 1)
        self.assertEqual(final_messages[1].tool_calls[0]['name'], tool_name_to_call)
        self.assertEqual(final_messages[1].tool_calls[0]['id'], tool_call_id)
        self.assertEqual(final_messages[1].tool_calls[0]['args'], {}) 
        
        self.assertIsInstance(final_messages[2], ToolMessage)
        self.assertEqual(final_messages[2].content, stringified_mock_tool_output) 
        self.assertEqual(final_messages[2].tool_call_id, tool_call_id)
        
        self.assertIsInstance(final_messages[3], AIMessage)
        self.assertEqual(final_messages[3].content, final_response_content_after_tool)
        self.assertFalse(hasattr(final_messages[3], 'tool_calls') and final_messages[3].tool_calls)
        
        self.assertEqual(mock_llm_with_tools.astream.call_count, 2)
        
        # Verify the mocked _arun_async_mock was called with the correct arguments
        # The args for the tool (from tool_calls[0]['args']) are passed as kwargs to _arun
        mock_tool_instance._arun_async_mock.assert_called_once_with(**{}) # Empty dict for args

if __name__ == '__main__':
    unittest.main() 