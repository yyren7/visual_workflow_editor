import logging
from typing import List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph # Not used directly here, but for context

# 主图的状态
from ..agent_state import AgentState 
# 机器人流程子图的创建函数和状态 (假设其状态也是 AgentState 或兼容的)
from .robot_flow_planner.graph_builder import create_robot_flow_graph, RobotFlowAgentState
# 机器人流程子图使用的 LLM 实例需要从某个地方获取，这里我们假设可以传递主 LLM
# 或者子图内部会实例化自己的 LLM (目前 create_robot_flow_graph 需要一个 llm)

logger = logging.getLogger(__name__)

async def robot_flow_invoker_node(state: AgentState, llm: BaseChatModel) -> dict:
    """
    调用并执行机器人流程图子图。
    将当前主图的对话历史传递给子图，并在子图完成后，将其历史更新回主图。
    """
    logger.info("--- Invoking Robot Flow Subgraph ---")

    # 1. 从主图状态获取当前消息历史
    current_main_messages: List[BaseMessage] = list(state.get("messages", []))
    current_flow_id = state.get("current_flow_id")
    flow_context = state.get("flow_context")

    # 2. 创建机器人流程图实例
    # create_robot_flow_graph 需要一个 llm 参数。我们传递主图的 llm。
    try:
        robot_flow_subgraph = create_robot_flow_graph(llm=llm)
        logger.info("Robot flow subgraph instance created successfully.")
    except Exception as e:
        logger.error(f"Error creating robot_flow_subgraph: {e}", exc_info=True)
        # 如果子图创建失败，返回错误信息到主图
        error_message = AIMessage(content=f"Error: Could not initialize the robot flow planning module. Details: {e}")
        return {"messages": current_main_messages + [error_message]}

    # 3. 准备子图的初始状态
    # RobotFlowAgentState 可能有不同的字段。我们需要映射主 AgentState 的相关信息。
    # 假设 RobotFlowAgentState 也有 'messages' 字段用于对话。
    # 其他字段如 'config', 'current_flow_id' 等需要根据 RobotFlowAgentState 的定义来设置。
    # 我们将 current_main_messages 传递给子图。
    
    # 构造一个初始的 RobotFlowAgentState
    # 注意: RobotFlowAgentState 的定义可能需要我们传递特定的初始值。
    # 我们需要确保这里的初始化是兼容的。
    # 从 graph_builder.py 中看到 RobotFlowAgentState 包含 config, messages, current_flow_id, raw_user_request 等。
    # 我们将传递 messages 和 current_flow_id。
    # config 可能由子图的 initialize_state_node 设置。
    # raw_user_request 可能需要从最新的 HumanMessage 中提取。
    
    raw_user_request_for_subgraph = ""
    if current_main_messages and isinstance(current_main_messages[-1], HumanMessage):
        if isinstance(current_main_messages[-1].content, str):
            raw_user_request_for_subgraph = current_main_messages[-1].content
        elif isinstance(current_main_messages[-1].content, list): # 处理 content 是列表的情况（例如图片）
             # 查找文本部分
            for item in current_main_messages[-1].content:
                if isinstance(item, dict) and item.get("type") == "text":
                    raw_user_request_for_subgraph = item.get("text", "")
                    break
            if not raw_user_request_for_subgraph:
                 logger.warning("Last human message content is a list but no text part found for raw_user_request_for_subgraph.")

    #  initial_subgraph_state: RobotFlowAgentState = { # type: ignore # RobotFlowAgentState is a TypedDict
    #     "messages": current_main_messages, # 传递整个历史，子图可能需要它
    #     "raw_user_request": raw_user_request_for_subgraph,
    #     "current_flow_id": current_flow_id,
    #     # "config": {}, # 让子图的 initialize_state_node 处理默认配置
    #     # 其他 RobotFlowAgentState 的必须字段需要在这里初始化或由子图的入口处理
    #     # "dialog_state": "initial", # RobotFlowAgentState 的默认值
    #     # "generated_node_xmls": [],
    #     # "parsed_flow_steps": [],
    # }
    # RobotFlowAgentState 会使用 Pydantic 的 default_factory, 所以只需要提供非默认值
    initial_subgraph_input = {
        "messages": current_main_messages,
        "user_input": raw_user_request_for_subgraph,
        "current_flow_id": current_flow_id,
        # 如果 RobotFlowAgentState 的 config 字段有 default_factory=dict, 则不需要显式提供空字典
    }


    logger.info(f"Invoking robot_flow_subgraph with initial input containing {len(current_main_messages)} messages and user_input: '{raw_user_request_for_subgraph[:100]}...'")
    
    # 4. 执行子图
    final_subgraph_state_dict = None
    last_event_output = None # To store the last event from astream

    try:
        async for event in robot_flow_subgraph.astream_events(initial_subgraph_input, {"recursion_limit": 10}, version="v2"):
            # astream_events v2 yields events with data about the graph execution
            # We are interested in the final state when the graph ends or is interrupted.
            # An event with name="end" and tag="__end__" signifies the graph has finished.
            # The output of the graph is in event["data"]["output"]
            if event["event"] == "on_chain_end" and event["name"] == "LangGraph": # Check for the end of the entire graph stream
                # The final output of the graph is typically in the last event data
                # For a compiled graph, the output of astream_events for the graph itself
                # should be the final state.
                if isinstance(event["data"], dict) and "output" in event["data"]:
                    final_subgraph_state_dict = event["data"]["output"]
                    logger.info(f"Subgraph astream_events ended. Final state keys: {final_subgraph_state_dict.keys() if isinstance(final_subgraph_state_dict, dict) else 'Not a dict'}")
                else:
                    logger.warning(f"Subgraph astream_events ended but final output format is unexpected: {event['data']}")
                break # Exit loop once graph end event is received
            elif event["event"] == "on_chain_stream" and event["name"] == "LangGraph":
                # This event contains the full state output chunk by chunk.
                # The last such event before "on_chain_end" would contain the final state.
                # However, relying on on_chain_end is cleaner.
                pass

        if final_subgraph_state_dict is None:
            # This might happen if astream_events finishes without a clear "on_chain_end" event for "LangGraph"
            # or if the loop was exited prematurely. This should ideally not occur.
            logger.error("Robot flow subgraph astream_events completed, but final_subgraph_state_dict was not captured correctly.")
            # Attempt to get state via a non-streaming invoke as a last resort, though this deviates from streaming intent.
            # This path should ideally not be hit if astream_events is handled correctly.
            # Given the prior recursion error, it's better to rely on astream_events correctly yielding the final state or an error.
            # For now, raise an error if state is not captured.
            raise ValueError("Failed to capture final state from robot_flow_subgraph astream_events.")

        logger.info("Robot flow subgraph execution via astream_events completed.")

    except GraphRecursionError as gre: # Specific catch for recursion errors
        logger.error(f"GraphRecursionError during robot_flow_subgraph.astream_events: {gre}", exc_info=True)
        error_message_content = f"Error: Robot flow planning module encountered a recursion limit. Details: {str(gre)}"
        # Ensure messages is a list, even if current_main_messages was None or empty
        messages_to_return = list(current_main_messages or []) + [AIMessage(content=error_message_content)]
        return {
            "messages": messages_to_return,
            "subgraph_completion_status": "error",
            "is_error": True, # Explicitly flag error in the main graph state
            "error_message": error_message_content
        }
    except Exception as e:
        logger.error(f"Error during robot_flow_subgraph.astream_events execution: {e}", exc_info=True)
        error_message_content = f"Error: An issue occurred while interacting with the robot flow planning module. Details: {str(e)}"
        messages_to_return = list(current_main_messages or []) + [AIMessage(content=error_message_content)]
        return {
            "messages": messages_to_return,
            "subgraph_completion_status": "error",
            "is_error": True,
            "error_message": error_message_content
        }

    # 5. 从子图的最终状态提取消息历史
    # Ensure final_subgraph_state_dict is a dictionary before calling .get()
    subgraph_final_messages: List[BaseMessage] = []
    completion_status: Optional[str] = None
    
    if isinstance(final_subgraph_state_dict, dict):
        subgraph_final_messages = final_subgraph_state_dict.get("messages", [])
        completion_status = final_subgraph_state_dict.get("subgraph_completion_status")
        logger.info(f"Extracted from final_subgraph_state_dict: {len(subgraph_final_messages)} messages, status: {completion_status}")
    elif final_subgraph_state_dict is RobotFlowAgentState:
        # If it's already a RobotFlowAgentState Pydantic model instance (less likely from astream_events raw output)
        logger.info("final_subgraph_state_dict is a RobotFlowAgentState Pydantic model instance.")
        subgraph_final_messages = final_subgraph_state_dict.messages
        completion_status = final_subgraph_state_dict.subgraph_completion_status
    else:
        logger.error(f"final_subgraph_state_dict is not a dictionary or RobotFlowAgentState instance. Type: {type(final_subgraph_state_dict)}. Cannot extract messages or status.")
        # This case implies a problem with how final_subgraph_state_dict was obtained or its structure.
        # We should return an error state for the main graph.
        error_message_content = "Internal error: Subgraph returned an unexpected final state format."
        messages_to_return = list(current_main_messages or []) + [AIMessage(content=error_message_content)]
        return {
            "messages": messages_to_return,
            "subgraph_completion_status": "error",
            "is_error": True,
            "error_message": error_message_content
        }

    if not subgraph_final_messages and completion_status != "needs_clarification": # Allow no messages if only needs_clarification
        logger.warning("Robot flow subgraph did not return any messages. Main history will not be updated by subgraph.")
        # 仍然返回原始消息，可能子图通过其他方式指示了完成或错误
        # 但通常我们期望子图通过消息进行通信
        return {
            "messages": current_main_messages,
            "subgraph_completion_status": completion_status,
        }

    # 6. 更新主图的状态
    # 我们将子图的完整消息历史替换主图的消息历史，或者追加。
    # 通常，子图的 messages 应该包含了初始传入的消息，并追加了新的交互。
    # 所以直接使用子图的 messages 是合适的。
    logger.info(f"Robot flow subgraph returned {len(subgraph_final_messages)} messages. Updating main graph state.")

    # 主 AgentState 的其他字段保持不变，除非子图明确要修改它们（不常见）
    # 我们只更新 messages 和 subgraph_completion_status。
    # task_route_decision 和 user_request_for_router 的清除是有条件的。
    update_dict = {
        "messages": subgraph_final_messages,
        "subgraph_completion_status": completion_status,
    }

    if completion_status == "needs_clarification":
        logger.info("Subgraph needs clarification. Preserving task_route_decision and user_request_for_router.")
        # task_route_decision 和 user_request_for_router 将保持不变 (不包含在 update_dict 中)
        # 确保它们在 state 中确实存在且被保留
        if state.get("task_route_decision") is not None: # Redundant if TypedDict enforces, but safe
            update_dict["task_route_decision"] = state.get("task_route_decision")
        if state.get("user_request_for_router") is not None:
            update_dict["user_request_for_router"] = state.get("user_request_for_router")
    else:
        logger.info(f"Subgraph completion status is '{completion_status}'. Clearing task_route_decision and user_request_for_router.")
        update_dict["task_route_decision"] = None
        update_dict["user_request_for_router"] = None
        
    return update_dict 