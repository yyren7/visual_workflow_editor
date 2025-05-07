import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from typing import AsyncGenerator

# Import necessary classes
# from backend.app.services.chat_service import ChatService
# from backend.langgraphchat.chains.workflow_chain import WorkflowChainOutput, WorkflowChain # Removed
# from database.models import Chat, Flow, User # Assuming User model exists

# === Tests below are commented out because they target the removed ChatService.process_chat_message method ===
# === New tests should be written to target the background task logic in backend/app/routers/chat.py ===

# class TestChatWorkflow(unittest.TestCase):
#
#     def setUp(self):
#         """Set up test environment"""
#         self.mock_db = MagicMock(spec=Session)
#         # Mock the chat object that add_message_to_chat returns
#         self.mock_chat = MagicMock(spec=Chat)
#         self.mock_chat.flow_id = "test_flow_123" 
#         self.mock_chat.id = "test_chat_456"
#
#         # Patch __init__ of ChatService to prevent real initializations
#         # We will mock the chains directly when needed
#         self.patcher = patch('backend.app.services.chat_service.ChatService.__init__', return_value=None)
#         self.mock_chat_service_init = self.patcher.start()
#         self.addCleanup(self.patcher.stop)
#         
#         # Instantiate ChatService (init is mocked)
#         self.chat_service = ChatService(self.mock_db)
#         # Manually assign mocked db session
#         self.chat_service.db = self.mock_db 
#         
#         # Mock the workflow_chain attribute directly (Now workflow_agent_executor)
#         # self.chat_service.workflow_chain = AsyncMock(spec=WorkflowChain)
#         self.chat_service.workflow_agent_executor = AsyncMock() # Mock the new executor
#         # Mock the add_message_to_chat method
#         self.chat_service.add_message_to_chat = MagicMock(return_value=self.mock_chat)
#         # Mock the _update_flow_in_db method (Removed)
#         # self.chat_service._update_flow_in_db = MagicMock(return_value={"success": True})
#
#     async def _test_process_chat_message_text_response(self):
#         """Tests ChatService.process_chat_message for a streaming text response."""
#         
#         # Arrange
#         chat_id = "test_chat_456"
#         user_message = "你好"
#         expected_ai_response_part1 = "你好！"
#         expected_ai_response_part2 = "有什么可以帮您？"
#         
#         # Mock the stream generator
#         async def mock_stream_generator() -> AsyncGenerator[str, None]:
#             yield expected_ai_response_part1
#             await asyncio.sleep(0) # Allow context switching
#             yield expected_ai_response_part2
#
#         # Mock WorkflowChainOutput with the stream generator (Removed)
#         # mock_workflow_output = WorkflowChainOutput(
#         #     summary="", # Summary is built later
#         #     stream_generator=mock_stream_generator() 
#         # )
#         # Mock the agent executor's ainvoke return value (Structure depends on agent)
#         # Example: Assume it returns a dict with an event stream or similar concept
#         mock_agent_output = {"event_stream": mock_stream_generator()} 
#         
#         # Configure the mocked workflow_agent_executor.ainvoke to return the mock output
#         self.chat_service.workflow_agent_executor.ainvoke.return_value = mock_agent_output
#         
#         # Act (Call the removed method)
#         # result = await self.chat_service.process_chat_message(chat_id, user_message)
#         result = {} # Placeholder, as method is removed
#
#         # Assert
#         # 1. Check if add_message_to_chat was called for the user message
#         self.chat_service.add_message_to_chat.assert_called_once_with(chat_id, "user", user_message)
#         
#         # 2. Check if workflow_agent_executor.ainvoke was called with correct args (including flow_id)
#         # Input structure needs update based on new agent input format
#         expected_chain_input = {
#             "input": user_message,
#             "chat_history": [], # Assuming history loading is mocked or part of input prep
#             "flow_context": {}, # Assuming flow context is mocked or part of input prep
#             # Potentially other keys like flow_id, chat_id depending on agent
#         }
#         # This assertion needs update based on how process_chat_message (if it existed) prepared input
#         # self.chat_service.workflow_agent_executor.ainvoke.assert_called_once_with(expected_chain_input)
#
#         # 3. Check the result (Removed method, so this assertion is invalid)
#         # self.assertIsInstance(result, WorkflowChainOutput)
#         # self.assertIsNotNone(result.stream_generator)
#         
#         # 4. Check if the stream yields the correct content (Still potentially valid if checking mock stream)
#         # stream_content = ""
#         # if result.get("event_stream"):
#         #     async for chunk in result["event_stream"]:
#         #          stream_content += chunk
#         #     self.assertEqual(stream_content, expected_ai_response_part1 + expected_ai_response_part2)
#         
#         # 5. _update_flow_in_db check (Method removed)
#         # self.chat_service._update_flow_in_db.assert_not_called()
#         
#         # Note: Testing the background task requires more complex mocking or 
#         # inspecting the arguments passed to background_tasks.add_task in the router.
#         # This unit test focuses on the service layer logic.
#
#     def test_process_chat_message_text_response_sync(self):
#          """Runs the async test in the event loop."""
#          asyncio.run(self._test_process_chat_message_text_response())
#
#     async def _test_process_chat_message_create_node(self):
#         # Arrange
#         chat_id = "test_chat_456"
#         user_message = "创建一个开始节点"
#         # Define realistic mock node data based on flow_tools.py structure
#         mock_node_data = {
#             "id": "start-1678886400000", # Example ID
#             "type": "generic", 
#             "position": {"x": 150, "y": 150}, # Example position
#             "data": {
#                 "label": "开始",
#                 "nodeType": "start",
#                 "type": "start",
#                 "description": "",
#                 "fields": [],
#                 "inputs": [],
#                 "outputs": [{"id": "output", "label": "输出"}], # Start node typically has an output
#                 "nodeProperties": {
#                      "nodeId": "start-1678886400000",
#                      "nodeType": "start",
#                      "control_x": "enable", 
#                      "control_y": "enable",
#                      "description": "",
#                      "fields": [],
#                      "inputs": [],
#                      "outputs": [{"id": "output", "label": "输出"}],
#                      "point_name_list": [],
#                      "pallet_list": [],
#                      "camera_list": []
#                 },
#                 "control_x": "enable", 
#                 "control_y": "enable",
#                 "point_name_list": [],
#                 "pallet_list": [],
#                 "camera_list": []
#             }
#         }
#         mock_summary = "已为您创建开始节点。"
#         
#         # Mock the agent executor's output (Non-streaming case)
#         mock_agent_output = {
#             "output": mock_summary, # Assuming final answer is in 'output'
#             # How flow updates are passed needs definition (e.g., in state?)
#             # "final_state": {"flow_data": {"nodes": [mock_node_data], "connections": []}} 
#         }
#         self.chat_service.workflow_agent_executor.ainvoke.return_value = mock_agent_output
#         
#         # Act (Call the removed method)
#         # result = await self.chat_service.process_chat_message(chat_id, user_message)
#         result = {} # Placeholder
#         
#         # Assert
#         # 1. Check add_message_to_chat calls (user + assistant)
#         self.assertEqual(self.chat_service.add_message_to_chat.call_count, 2)
#         self.chat_service.add_message_to_chat.assert_any_call(chat_id, "user", user_message)
#         self.chat_service.add_message_to_chat.assert_any_call(chat_id, "assistant", mock_summary)
#         
#         # 2. Check ainvoke call (Input needs update)
#         # expected_chain_input = {...}
#         # self.chat_service.workflow_agent_executor.ainvoke.assert_called_once_with(expected_chain_input)
#
#         # 3. Check _update_flow_in_db call (Method removed)
#         # self.chat_service._update_flow_in_db.assert_called_once_with(...)
#         
#         # 4. Check result (Method removed)
#         # self.assertEqual(result.get('output'), mock_summary)
#
#     def test_process_chat_message_create_node_sync(self):
#         asyncio.run(self._test_process_chat_message_create_node())
#
#
# if __name__ == '__main__':
#     unittest.main() 