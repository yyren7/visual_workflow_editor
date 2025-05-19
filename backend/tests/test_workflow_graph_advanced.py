import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Type, Any, Dict, List, Tuple

from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage, BaseMessage
from langchain_core.tools import BaseTool
from langchain_deepseek import ChatDeepSeek # <--- 确保导入 DeepSeek LLM
# from langchain_openai import ChatOpenAI # Example if you were using OpenAI

from pydantic import BaseModel, Field

from backend.langgraphchat.graph.agent_state import AgentState
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
from backend.langgraphchat.graph.types import RouteDecision # For type hinting if needed

# --- Configuration for Real LLM (DeepSeek) ---
# 请确保您已设置必要的环境变量，例如 DEEPSEEK_API_KEY
# 您可能还需要指定模型名称
# EXAMPLE_DEEPSEEK_MODEL_NAME = "deepseek-chat" # 或其他兼容的模型

# Define a very simple schema for the mock tool to avoid RecursionError
class SimpleMockToolSchema(BaseModel):
    pass

class MockToolArgsSchema1(BaseModel):
    query: str = Field(description="A query for the tool")
    count: int = Field(default=1, description="A count parameter")

class MockToolArgsSchema2(BaseModel):
    item_id: str = Field(description="ID of the item to process")

# Custom Mock Tool class inheriting from BaseTool (remains useful for planner tool testing)
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

class TestWorkflowGraphWithRealLLM(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            # 与 chat_service.py 中初始化 DeepSeek 的方式保持一致
            # 确保 DEEPSEEK_API_KEY 环境变量已设置
            cls.llm = ChatDeepSeek(
                model="deepseek-chat", # 使用与 chat_service.py 一致或您希望测试的模型
                temperature=0,        # 测试时建议低 temperature
            )
            print("\n" + "="*30 + " INFO " + "="*30)
            print(f"Successfully initialized DeepSeek LLM (model: {cls.llm.model_name}) consistent with ChatService.")
            print("Ensure DEEPSEEK_API_KEY environment variable is set.")
            print("="*79 + "\n")
        except Exception as e:
            cls.llm = None 
            print("\n" + "="*30 + " ERROR " + "="*30)
            print(f"Failed to initialize DeepSeek LLM (model: deepseek-chat) as in ChatService: {e}")
            print("Please ensure 'langchain_deepseek' is installed and DEEPSEEK_API_KEY environment variable is set.")
            print("Tests requiring the LLM will be skipped.")
            print("="*100 + "\n")

    def setUp(self):
        super().setUp()
        if self.llm is None:
            self.skipTest("Real LLM not configured or failed to initialize in setUpClass.")

    async def _run_workflow_and_collect_events(
        self, compiled_workflow, initial_state: AgentState, test_name: str
    ) -> Tuple[List[Tuple[str, str, Dict]], AgentState]:
        print(f"\n--- Test Workflow Start: {test_name} ---")
        print(f"Initial State Input: {initial_state.get('input')}")
        print(f"Initial State Messages: {initial_state.get('messages')}")
        
        events_history: List[Tuple[str, str, Dict]] = [] # (event_type, node_name, data)
        final_graph_output = None
        
        event_stream = compiled_workflow.astream_events(initial_state, version="v2")
        
        print("\n  Workflow Events:")
        async for event in event_stream:
            event_type = event["event"]
            name = event.get("name") # Node name or chain name
            # tags = event.get("tags", [])
            data = event.get("data", {})

            events_history.append((event_type, name, data))
            print(f"    Event: {event_type}, Name: {name}") #, Tags: {tags}")

            if event_type == "on_chat_model_stream" and data.get("chunk"):
                chunk = data.get("chunk")
                if hasattr(chunk, 'content') and chunk.content:
                        print(f"      LLM Stream Content: \"{chunk.content}\"")
                if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                        print(f"      LLM Stream Tool Call Chunks: {chunk.tool_call_chunks}")
            elif event_type == "on_tool_start":
                 print(f"      Tool Start ({name}): Input = {data.get('input')}")
            elif event_type == "on_tool_end":
                 print(f"      Tool End ({name}): Output = {data.get('output')}")
            
            if event_type == "update_state":
                updated_keys = list(data.keys())
                print(f"      State Updated by '{name}': Keys updated = {updated_keys}")
                # if "messages" in data:
                #     print(f"        Messages after update by '{name}': {data['messages']}")
                # if "task_route_decision" in data:
                #      print(f"        Task Route Decision: {data['task_route_decision']}")


            if event_type == "on_chain_end" and name == "LangGraph":
                print(f"      LangGraph Ended. Output: {data.get('output')}")
                final_graph_output = data.get('output')

        print(f"--- Test Workflow End: {test_name} ---\n")
        
        # The final output of the graph is a list of state dicts, one for each final node.
        # If the graph ends at an END state, this list might represent the state just before END.
        # We need to find the most recent complete state.
        final_state_dict = {}
        if isinstance(final_graph_output, list) and final_graph_output:
            # The list contains dicts like {'node_name': state_after_node}
            # We want the full accumulated state.
            # The Graph's final output in v2 astream_events with `output_keys=None` (default)
            # is the full state of the graph when it finishes.
            # Let's find the last full state snapshot from "update_state" from "LangGraph" itself
            # or use the direct output if it's a dict.
            
            # Try to get the final state from the 'on_chain_end' event for LangGraph
            for evt_type, evt_name, evt_data in reversed(events_history):
                if evt_type == "on_chain_end" and evt_name == "LangGraph" and isinstance(evt_data.get("output"), dict):
                    final_state_dict = evt_data["output"]
                    print(f"  Extracted final state from LangGraph on_chain_end event: Keys {list(final_state_dict.keys())}")
                    break
            if not final_state_dict and isinstance(final_graph_output, dict) : # Should be the case
                 final_state_dict = final_graph_output
                 print(f"  Using direct final_graph_output as final state: Keys {list(final_state_dict.keys())}")
            elif not final_state_dict:
                 print("  WARNING: Could not determine the final full state dictionary.")

        return events_history, AgentState(**final_state_dict) if final_state_dict else AgentState(input="", messages=[], flow_context={}, current_flow_id="")

    def _get_last_ai_message_content(self, state: AgentState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return str(msg.content)
        return ""

    def _assert_node_visited(self, events_history: List[Tuple[str, str, Dict]], node_name: str, min_times: int = 1):
        count = 0
        for event_type, name, _ in events_history:
            # We count 'on_chain_start' or 'on_node_start' (if LangServe adds it) for the node
            # More reliably, count when a node updates the state.
            if event_type == "update_state" and name == node_name:
                count += 1
        self.assertGreaterEqual(count, min_times, f"Node '{node_name}' should have been visited at least {min_times} time(s). Found {count} visits via state updates.")
        print(f"  Assertion Check: Node '{node_name}' visited {count} time(s) (via state update).")

    def _get_task_router_decision(self, events_history: List[Tuple[str, str, Dict]]) -> List[RouteDecision]:
        decisions = []
        for event_type, name, data in events_history:
            if event_type == "update_state" and name == "task_router":
                if "task_route_decision" in data and isinstance(data["task_route_decision"], RouteDecision):
                    decisions.append(data["task_route_decision"])
        return decisions

    async def test_route_to_ask_info_and_return(self):
        test_name = "test_route_to_ask_info_and_return"
        
        compiled_workflow = compile_workflow_graph(llm=self.llm, custom_tools=[])
        user_input = "你能做什么？" # Input likely to go to ask_info
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input)],
            flow_context={},
            current_flow_id="test_flow_ask_info_1",
            input_processed=False # input_handler will process this
        )
        
        events_history, final_state = await self._run_workflow_and_collect_events(compiled_workflow, initial_state, test_name)
        
        self._assert_node_visited(events_history, "input_handler")
        self._assert_node_visited(events_history, "task_router", min_times=1) # At least once, maybe more if it loops
        self._assert_node_visited(events_history, "ask_info")

        router_decisions = self._get_task_router_decision(events_history)
        self.assertTrue(any(d.next_node == "ask_info" for d in router_decisions), "Task router should have decided to go to ask_info at some point.")
        
        # The ask_info_node should add an AIMessage
        self.assertTrue(isinstance(final_state.get("messages", [])[-1], AIMessage), "Last message should be an AIMessage from ask_info (or subsequent task_router).")
        print(f"  Final messages: {final_state.get('messages')}")
        # We expect the flow to be at task_router again after ask_info
        # This can be checked by seeing if 'task_router' was the last state-updating node, or by its output.
        # For simplicity, let's check if task_router was visited at least twice if ask_info was visited.
        if any(event[1] == "ask_info" and event[0] == "update_state" for event in events_history):
             self._assert_node_visited(events_history, "task_router", min_times=2)


    async def test_route_to_teaching_and_return(self):
        test_name = "test_route_to_teaching_and_return"
        compiled_workflow = compile_workflow_graph(llm=self.llm, custom_tools=[])
        user_input = "记住这个点位 P100。" # Input likely to go to teaching
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input)],
            current_flow_id="test_flow_teaching_1"
        )
        
        events_history, final_state = await self._run_workflow_and_collect_events(compiled_workflow, initial_state, test_name)
        
        self._assert_node_visited(events_history, "input_handler")
        self._assert_node_visited(events_history, "task_router", min_times=1)
        self._assert_node_visited(events_history, "teaching")

        router_decisions = self._get_task_router_decision(events_history)
        self.assertTrue(any(d.next_node == "teaching" for d in router_decisions), "Task router should have decided to go to teaching.")
        
        self.assertTrue(isinstance(final_state.get("messages", [])[-1], AIMessage), "Last message should be an AIMessage.")
        if any(event[1] == "teaching" and event[0] == "update_state" for event in events_history):
             self._assert_node_visited(events_history, "task_router", min_times=2)

    async def test_route_to_planner_no_tools_and_return(self):
        test_name = "test_route_to_planner_no_tools_and_return"
        compiled_workflow = compile_workflow_graph(llm=self.llm, custom_tools=[]) # No tools provided to planner
        user_input = "帮我规划一个简单的流程图。" # Input for planner
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input)],
            current_flow_id="test_flow_planner_no_tool_1"
        )
        
        events_history, final_state = await self._run_workflow_and_collect_events(compiled_workflow, initial_state, test_name)
        
        self._assert_node_visited(events_history, "input_handler")
        self._assert_node_visited(events_history, "task_router", min_times=1)
        self._assert_node_visited(events_history, "planner")

        router_decisions = self._get_task_router_decision(events_history)
        self.assertTrue(any(d.next_node == "planner" for d in router_decisions), "Task router should have decided to go to planner.")
        
        # Planner should produce an AIMessage, and since no tools, should_continue routes to task_router
        self.assertTrue(isinstance(final_state.get("messages", [])[-1], AIMessage), "Last message should be an AIMessage.")
        # Check that 'tools' node was NOT visited
        self.assertFalse(any(name == "tools" and event_type == "update_state" for event_type, name, _ in events_history), "Tools node should not have been visited.")

        if any(event[1] == "planner" and event[0] == "update_state" for event in events_history):
             self._assert_node_visited(events_history, "task_router", min_times=2)


    async def test_route_to_planner_with_mock_tool_and_return(self):
        test_name = "test_route_to_planner_with_mock_tool_and_return"
        
        tool_name_to_call = "query_processor_tool"
        tool_args = {"query": "search for cats", "count": 1} # LLM might not pick these exact args
        mock_tool_output_content = f"Processed query. Result: Found cats."

        mock_tool_instance = MockToolForTest(
            name=tool_name_to_call,
            description="A mock tool that processes queries.", # LLM will see this description
            output_value=str(mock_tool_output_content),
            args_schema_override=MockToolArgsSchema1
        )
        compiled_workflow = compile_workflow_graph(llm=self.llm, custom_tools=[mock_tool_instance])

        # This input needs to strongly suggest to the DeepSeek LLM to use the 'query_processor_tool'
        user_input = f"请使用 {tool_name_to_call} 工具来查找关于猫的信息。"
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input)],
            current_flow_id="test_flow_planner_with_tool_1"
        )
        
        events_history, final_state = await self._run_workflow_and_collect_events(compiled_workflow, initial_state, test_name)
        
        self._assert_node_visited(events_history, "input_handler")
        self._assert_node_visited(events_history, "task_router", min_times=1) # task_router -> planner
        self._assert_node_visited(events_history, "planner", min_times=1)     # planner -> tools (hopefully) -> planner
        
        router_decisions = self._get_task_router_decision(events_history)
        self.assertTrue(any(d.next_node == "planner" for d in router_decisions), "Task router should have initially decided to go to planner.")

        # Check if the tool was actually called
        tool_called = any(
            event_type == "on_tool_end" and name == tool_name_to_call 
            for event_type, name, _ in events_history
        )
        
        if tool_called:
            print(f"  Assertion Check: Tool '{tool_name_to_call}' was called by the LLM.")
            self._assert_node_visited(events_history, "tools")
            self._assert_node_visited(events_history, "planner", min_times=2) # Planner is visited again after tools

            # Check for ToolMessage in history
            self.assertTrue(
                any(isinstance(msg, ToolMessage) and msg.tool_call_id for msg in final_state.get("messages", [])),
                "A ToolMessage should be present if the tool was called."
            )
        else:
            print(f"  WARNING: Tool '{tool_name_to_call}' was NOT called by the LLM. The input prompt might need adjustment for DeepSeek, or LLM decided not to use it.")
            # If tool not called, planner still runs once.
            # And flow should still go back to task_router
            self._assert_node_visited(events_history, "planner", min_times=1)


        self.assertTrue(isinstance(final_state.get("messages", [])[-1], AIMessage), "Last message should be an AIMessage.")
        if any(event[1] == "planner" and event[0] == "update_state" for event in events_history): # If planner was ever run
             self._assert_node_visited(events_history, "task_router", min_times=2) # Should always return to task_router


    async def test_route_to_end_session(self):
        test_name = "test_route_to_end_session"
        compiled_workflow = compile_workflow_graph(llm=self.llm, custom_tools=[])
        user_input = "结束对话吧，谢谢。" # Input to trigger end_session
        initial_state = AgentState(
            input=user_input,
            messages=[HumanMessage(content=user_input)],
            current_flow_id="test_flow_end_session_1"
        )
        
        events_history, final_state = await self._run_workflow_and_collect_events(compiled_workflow, initial_state, test_name)
        
        self._assert_node_visited(events_history, "input_handler")
        # task_router should be visited once before ending
        self._assert_node_visited(events_history, "task_router")

        router_decisions = self._get_task_router_decision(events_history)
        self.assertTrue(any(d.next_node == "end_session" for d in router_decisions), 
                        f"Task router should have decided to 'end_session'. Decisions: {router_decisions}")
        
        # Check if the graph actually ended. The 'final_graph_output' from 'on_chain_end' for 'LangGraph'
        # should reflect the state *before* hitting the conceptual END node.
        # The absence of further "update_state" events for nodes other than LangGraph itself after
        # the end_session decision is a good indicator.

        # Verify that no other nodes (planner, teaching, ask_info) were visited after task_router's decision to end
        end_decision_made = False
        for event_type, name, data in events_history:
            if name == "task_router" and event_type == "update_state":
                if data.get("task_route_decision") and data["task_route_decision"].next_node == "end_session":
                    end_decision_made = True
                    print("  INFO: 'end_session' decision confirmed by task_router state update.")
                    continue 
            if end_decision_made:
                self.assertNotIn(name, ["planner", "teaching", "ask_info", "tools"], 
                                 f"Node {name} was visited after 'end_session' decision.")
        
        self.assertTrue(end_decision_made, "The 'end_session' decision point was not clearly identified in task_router's state updates.")
        # The last message might be the user's "end" message, or if task_router adds one, that.
        # Let's ensure the message list is not empty.
        self.assertTrue(final_state.get("messages"), "Message list should not be empty at the end.")


    async def test_multi_turn_conversation_flow(self):
        test_name = "test_multi_turn_conversation_flow"
        compiled_workflow = compile_workflow_graph(llm=self.llm, custom_tools=[])

        # Turn 1: Ask info
        user_input_1 = "你是谁？"
        initial_state_1 = AgentState(input=user_input_1, messages=[HumanMessage(content=user_input_1)], current_flow_id="multi_turn_1")
        events_1, state_1 = await self._run_workflow_and_collect_events(compiled_workflow, initial_state_1, f"{test_name}_turn1_ask_info")
        
        self._assert_node_visited(events_1, "task_router")
        self.assertTrue(any(d.next_node == "ask_info" for d in self._get_task_router_decision(events_1)))
        last_msg_1_content = self._get_last_ai_message_content(state_1)
        self.assertGreater(len(last_msg_1_content), 0, "LLM should have responded in ask_info node for turn 1")
        print(f"  Turn 1 AI Response: {last_msg_1_content}")

        # Turn 2: Plan something (based on a new input, using history from state_1)
        user_input_2 = "帮我设计一个包含三个步骤的简单食谱。"
        current_messages_turn_2 = list(state_1.get("messages", [])) # Get history from turn 1
        current_messages_turn_2.append(HumanMessage(content=user_input_2))
        initial_state_2 = AgentState(
            input=user_input_2, # Current input for input_handler
            messages=current_messages_turn_2, # Full history for context
            flow_context=state_1.get("flow_context",{}),
            current_flow_id="multi_turn_1", # same flow
            input_processed=False # Let input_handler process user_input_2
        )
        events_2, state_2 = await self._run_workflow_and_collect_events(compiled_workflow, initial_state_2, f"{test_name}_turn2_planner")
        
        # In events_2, task_router should decide "planner"
        self.assertTrue(any(d.next_node == "planner" for d in self._get_task_router_decision(events_2)),
                        f"Router decisions in Turn 2: {self._get_task_router_decision(events_2)}")
        self._assert_node_visited(events_2, "planner")
        last_msg_2_content = self._get_last_ai_message_content(state_2)
        self.assertGreater(len(last_msg_2_content), 0, "LLM (planner) should have responded for turn 2")
        print(f"  Turn 2 AI Response: {last_msg_2_content}")

        # Turn 3: End conversation
        user_input_3 = "好的，谢谢你，结束吧。"
        current_messages_turn_3 = list(state_2.get("messages", []))
        current_messages_turn_3.append(HumanMessage(content=user_input_3))
        initial_state_3 = AgentState(
            input=user_input_3, messages=current_messages_turn_3, 
            current_flow_id="multi_turn_1", input_processed=False
        )
        events_3, state_3 = await self._run_workflow_and_collect_events(compiled_workflow, initial_state_3, f"{test_name}_turn3_end")
        
        self.assertTrue(any(d.next_node == "end_session" for d in self._get_task_router_decision(events_3)))
        print(f"  Turn 3 AI Response (likely none or user's own last message): {self._get_last_ai_message_content(state_3)}")


if __name__ == '__main__':
    unittest.main() 