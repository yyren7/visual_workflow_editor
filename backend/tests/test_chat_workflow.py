import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from typing import AsyncGenerator

# Import necessary classes
from backend.app.services.chat_service import ChatService
from backend.langchainchat.chains.workflow_chain import WorkflowChainOutput, WorkflowChain
from database.models import Chat, Flow, User # Assuming User model exists

class TestChatWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up test environment"""
        self.mock_db = MagicMock(spec=Session)
        # Mock the chat object that add_message_to_chat returns
        self.mock_chat = MagicMock(spec=Chat)
        self.mock_chat.flow_id = "test_flow_123" 
        self.mock_chat.id = "test_chat_456"

        # Patch __init__ of ChatService to prevent real initializations
        # We will mock the chains directly when needed
        self.patcher = patch('backend.app.services.chat_service.ChatService.__init__', return_value=None)
        self.mock_chat_service_init = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        
        # Instantiate ChatService (init is mocked)
        self.chat_service = ChatService(self.mock_db)
        # Manually assign mocked db session
        self.chat_service.db = self.mock_db 
        
        # Mock the workflow_chain attribute directly
        self.chat_service.workflow_chain = AsyncMock(spec=WorkflowChain)
        # Mock the add_message_to_chat method
        self.chat_service.add_message_to_chat = MagicMock(return_value=self.mock_chat)
        # Mock the _update_flow_in_db method
        self.chat_service._update_flow_in_db = MagicMock(return_value={"success": True})

    async def _test_process_chat_message_text_response(self):
        """Tests ChatService.process_chat_message for a streaming text response."""
        
        # Arrange
        chat_id = "test_chat_456"
        user_message = "你好"
        expected_ai_response_part1 = "你好！"
        expected_ai_response_part2 = "有什么可以帮您？"
        
        # Mock the stream generator
        async def mock_stream_generator() -> AsyncGenerator[str, None]:
            yield expected_ai_response_part1
            await asyncio.sleep(0) # Allow context switching
            yield expected_ai_response_part2

        # Mock WorkflowChainOutput with the stream generator
        mock_workflow_output = WorkflowChainOutput(
            summary="", # Summary is built later
            stream_generator=mock_stream_generator() 
        )
        
        # Configure the mocked workflow_chain.ainvoke to return the mock output
        self.chat_service.workflow_chain.ainvoke.return_value = mock_workflow_output
        
        # Act
        result = await self.chat_service.process_chat_message(chat_id, user_message)

        # Assert
        # 1. Check if add_message_to_chat was called for the user message
        self.chat_service.add_message_to_chat.assert_called_once_with(chat_id, "user", user_message)
        
        # 2. Check if workflow_chain.ainvoke was called with correct args (including flow_id)
        expected_chain_input = {
            "user_input": user_message,
            "db_session": self.mock_db,
            "flow_id": self.mock_chat.flow_id 
        }
        self.chat_service.workflow_chain.ainvoke.assert_called_once_with(expected_chain_input)

        # 3. Check if the result is the WorkflowChainOutput object containing the stream
        self.assertIsInstance(result, WorkflowChainOutput)
        self.assertIsNotNone(result.stream_generator)
        
        # 4. Check if the stream yields the correct content (optional but good)
        stream_content = ""
        async for chunk in result.stream_generator:
             stream_content += chunk
        self.assertEqual(stream_content, expected_ai_response_part1 + expected_ai_response_part2)
        
        # 5. _update_flow_in_db should NOT have been called for streaming response
        self.chat_service._update_flow_in_db.assert_not_called()
        
        # Note: Testing the background task requires more complex mocking or 
        # inspecting the arguments passed to background_tasks.add_task in the router.
        # This unit test focuses on the service layer logic.

    def test_process_chat_message_text_response_sync(self):
         """Runs the async test in the event loop."""
         asyncio.run(self._test_process_chat_message_text_response())

    async def _test_process_chat_message_create_node(self):
        # Arrange
        chat_id = "test_chat_456"
        user_message = "创建一个开始节点"
        # Define realistic mock node data based on flow_tools.py structure
        mock_node_data = {
            "id": "start-1678886400000", # Example ID
            "type": "generic", 
            "position": {"x": 150, "y": 150}, # Example position
            "data": {
                "label": "开始",
                "nodeType": "start",
                "type": "start",
                "description": "",
                "fields": [],
                "inputs": [],
                "outputs": [{"id": "output", "label": "输出"}], # Start node typically has an output
                "nodeProperties": {
                     "nodeId": "start-1678886400000",
                     "nodeType": "start",
                     "control_x": "enable", 
                     "control_y": "enable",
                     "description": "",
                     "fields": [],
                     "inputs": [],
                     "outputs": [{"id": "output", "label": "输出"}],
                     "point_name_list": [],
                     "pallet_list": [],
                     "camera_list": []
                },
                "control_x": "enable", 
                "control_y": "enable",
                "point_name_list": [],
                "pallet_list": [],
                "camera_list": []
            }
        }
        mock_summary = "已为您创建开始节点。"
        
        mock_workflow_output = WorkflowChainOutput(
            summary=mock_summary,
            nodes=[mock_node_data],
            connections=[],
            stream_generator=None
        )
        self.chat_service.workflow_chain.ainvoke.return_value = mock_workflow_output
        
        # Act
        result = await self.chat_service.process_chat_message(chat_id, user_message)
        
        # Assert
        # 1. Check add_message_to_chat calls (user + assistant)
        self.assertEqual(self.chat_service.add_message_to_chat.call_count, 2)
        self.chat_service.add_message_to_chat.assert_any_call(chat_id, "user", user_message)
        self.chat_service.add_message_to_chat.assert_any_call(chat_id, "assistant", mock_summary)
        
        # 2. Check ainvoke call
        expected_chain_input = {
            "user_input": user_message,
            "db_session": self.mock_db,
            "flow_id": self.mock_chat.flow_id 
        }
        self.chat_service.workflow_chain.ainvoke.assert_called_once_with(expected_chain_input)

        # 3. Check _update_flow_in_db call
        # Note: The tool result (mock_node_data) is what WorkflowChain returns,
        # and ChatService should pass this directly to _update_flow_in_db.
        self.chat_service._update_flow_in_db.assert_called_once_with(
            self.mock_chat.flow_id, [mock_node_data], []
        )
        
        # 4. Check result
        self.assertIsInstance(result, WorkflowChainOutput)
        self.assertEqual(result.summary, mock_summary)
        # WorkflowChainOutput itself contains the nodes/connections
        self.assertEqual(result.nodes, [mock_node_data])
        self.assertEqual(result.connections, []) # Expect empty list for connections
        self.assertIsNone(result.stream_generator)

    def test_process_chat_message_create_node_sync(self):
        asyncio.run(self._test_process_chat_message_create_node())


if __name__ == '__main__':
    unittest.main() 