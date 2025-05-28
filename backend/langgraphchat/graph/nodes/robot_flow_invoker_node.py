import logging
from typing import List
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
    # LangGraph 的 .ainvoke() 方法接受一个字典作为输入。
    # 我们需要确保 initial_subgraph_state 符合 RobotFlowAgentState 的结构。
    final_subgraph_state_dict = None
    try:
        # .astream() 返回一个异步生成器，我们需要迭代以获取最终状态
        async for event_output in robot_flow_subgraph.astream(initial_subgraph_input, {"recursion_limit": 5}):
            # event_output 是一个字典，键是节点名，值是该节点的输出
            # 我们关心的是最终的累积状态，这通常在最后一个事件中，或者需要从事件流中推断
            # LangGraph 的 stream 事件会给出每个节点的输出。
            # 我们需要最后一次输出的完整状态。
            # 对于 .ainvoke，它直接返回最终状态。
            # 对于 .astream，最后一个事件通常包含所有累积的状态。
            # 我们取最后一个事件的最后一个节点的状态（通常是 __end__ 之前的那个）
            # 或者，更简单地，如果 create_robot_flow_graph 返回的是编译后的图，
            # 它的 ainvoke 应该返回最终状态字典。
            # `create_robot_flow_graph` 返回 `workflow.compile().ainvoke`
            # 所以这里可以直接 ainvoke
            pass # Astreaming to completion
        
        # After streaming, get the final state
        # The `RobotFlowAgentState` is a TypedDict. The compiled graph's `ainvoke`
        # or the final result of `astream_events` (if processed correctly) will give this TypedDict.
        # For simplicity, let's assume ainvoke provides the final state directly if create_robot_flow_graph returns a compiled graph.
        # If create_robot_flow_graph returns a callable that internally calls astream, we need to adjust.
        # The type hint for create_robot_flow_graph is `Callable[[Dict[str, Any]], Any]`
        # This implies it's ready to be called.

        final_subgraph_state_dict = await robot_flow_subgraph.ainvoke(initial_subgraph_input, {"recursion_limit": 5})

        if final_subgraph_state_dict is None:
             raise ValueError("Robot flow subgraph did not return a final state.")
        
        logger.info("Robot flow subgraph execution completed.")

    except Exception as e:
        logger.error(f"Error during robot_flow_subgraph execution: {e}", exc_info=True)
        error_message = AIMessage(content=f"Error: An issue occurred while interacting with the robot flow planning module. Details: {e}")
        # Preserve original messages and add error
        return {"messages": current_main_messages + [error_message]}

    # 5. 从子图的最终状态提取消息历史
    # 假设子图的最终状态是一个字典，并且包含 'messages' 键
    subgraph_final_messages: List[BaseMessage] = final_subgraph_state_dict.get("messages", [])
    
    if not subgraph_final_messages:
        logger.warning("Robot flow subgraph did not return any messages. Main history will not be updated by subgraph.")
        # 仍然返回原始消息，可能子图通过其他方式指示了完成或错误
        # 但通常我们期望子图通过消息进行通信

    # 6. 更新主图的状态
    # 我们将子图的完整消息历史替换主图的消息历史，或者追加。
    # 通常，子图的 messages 应该包含了初始传入的消息，并追加了新的交互。
    # 所以直接使用子图的 messages 是合适的。
    logger.info(f"Robot flow subgraph returned {len(subgraph_final_messages)} messages. Updating main graph state.")

    completion_status = final_subgraph_state_dict.get("subgraph_completion_status")
    
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