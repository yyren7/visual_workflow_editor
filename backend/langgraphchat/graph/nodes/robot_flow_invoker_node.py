import logging
from typing import List, Optional, AsyncIterator
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, AIMessageChunk
from langgraph.graph import StateGraph
from langgraph.errors import GraphRecursionError

# 主图的状态
from ..agent_state import AgentState 
# 机器人流程子图的创建函数和状态 (假设其状态也是 AgentState 或兼容的)
from ..subgraph.sas.graph_builder import create_robot_flow_graph, RobotFlowAgentState
# 机器人流程子图使用的 LLM 实例需要从某个地方获取，这里我们假设可以传递主 LLM
# 或者子图内部会实例化自己的 LLM (目前 create_robot_flow_graph 需要一个 llm)

logger = logging.getLogger(__name__)

async def robot_flow_invoker_node(state: AgentState, llm: BaseChatModel, sas_subgraph_app: StateGraph) -> AsyncIterator[dict]:
    """
    调用并执行机器人流程图子图。
    将当前主图的对话历史传递给子图，并在子图完成后，将其历史更新回主图。
    此节点现在支持流式输出 AIMessageChunk。
    管理SAS子图的持久化状态以支持多轮澄清。
    """
    logger.info("--- Invoking Robot Flow Subgraph (Streaming Enabled, State Persistence Enabled) ---")

    # 1. 从主图状态获取当前消息历史
    current_main_messages: List[BaseMessage] = list(state.get("messages", []))
    current_flow_id = state.get("current_flow_id")
    # flow_context = state.get("flow_context") # Not directly used for subgraph input prep here

    # 2. 机器人流程图实例现在通过参数传入 (sas_subgraph_app)
    # try:
    #     robot_flow_subgraph = create_robot_flow_graph(llm=llm) # 旧的创建方式
    #     logger.info("Robot flow subgraph instance created successfully.")
    # except Exception as e:
    #     logger.error(f\"Error creating robot_flow_subgraph: {e}\", exc_info=True)
    #     error_message = AIMessage(content=f\"Error: Could not initialize the robot flow planning module. Details: {e}\")
    #     yield {"messages": current_main_messages + [error_message], "subgraph_completion_status": "error", "is_error": True, "error_message": str(e), "sas_planner_subgraph_state": None}
    #     return

    # 直接使用传入的 sas_subgraph_app
    robot_flow_subgraph = sas_subgraph_app
    if not robot_flow_subgraph:
        logger.error("SAS Subgraph (sas_subgraph_app) was not provided to robot_flow_invoker_node.")
        error_message = AIMessage(content="Error: The robot flow planning module is not available.")
        yield {"messages": current_main_messages + [error_message], "subgraph_completion_status": "error", "is_error": True, "error_message": "SAS subgraph not provided.", "sas_planner_subgraph_state": None}
        return
    logger.info("Using provided SAS subgraph instance.")

    # 3. 准备子图的初始状态
    raw_user_request_for_subgraph = ""
    if current_main_messages and isinstance(current_main_messages[-1], HumanMessage):
        if isinstance(current_main_messages[-1].content, str):
            raw_user_request_for_subgraph = current_main_messages[-1].content
        elif isinstance(current_main_messages[-1].content, list):
            for item in current_main_messages[-1].content:
                if isinstance(item, dict) and item.get("type") == "text":
                    raw_user_request_for_subgraph = item.get("text", "")
                    break
            if not raw_user_request_for_subgraph:
                 logger.warning("Last human message content is a list but no text part found for raw_user_request_for_subgraph.")

    persisted_sas_state = state.get("sas_planner_subgraph_state")
    subgraph_input_for_current_run: dict # This will be RobotFlowAgentState compatible

    if persisted_sas_state:
        logger.info(f"Found persisted SAS subgraph state. Using it as a base.")
        subgraph_input_for_current_run = persisted_sas_state.copy() # Start with the old state
        subgraph_input_for_current_run["user_input"] = raw_user_request_for_subgraph # Provide new user input for this turn
        subgraph_input_for_current_run["messages"] = current_main_messages # Update with the latest full message history
        # Other fields like current_flow_id, config should be part of persisted_sas_state if set previously.
        # The SAS initialize_state_node will re-evaluate user_input and messages.
        logger.info(f"Persisted SAS state updated with new user_input: '{raw_user_request_for_subgraph[:50]}...' and current messages ({len(current_main_messages)}).")
    else:
        logger.info("No persisted SAS state. Creating fresh input for SAS subgraph.")
        subgraph_input_for_current_run = {
            "messages": current_main_messages,
            "user_input": raw_user_request_for_subgraph,
            "current_flow_id": current_flow_id,
            # Config will be handled by SAS subgraph's initialize_state_node using its defaults
            # and potentially merging anything explicitly passed in its 'config' field within this dict.
            # For a fresh run, we are not passing an explicit 'config' dict here, letting SAS defaults take over.
        }

    logger.info(f"Invoking robot_flow_subgraph with input: { {k: (v[:100] + '...' if isinstance(v, str) and len(v) > 100 else v) for k, v in subgraph_input_for_current_run.items() if k != 'messages'} } containing {len(subgraph_input_for_current_run.get('messages',[]))} messages.")
    
    # 4. 执行子图
    final_subgraph_state_dict = None

    try:
        async for event in robot_flow_subgraph.astream_events(subgraph_input_for_current_run, {"recursion_limit": 10}, version="v2"): # recursion_limit might need adjustment
            if event["event"] == "on_chain_stream":
                chunk_data = event.get("data", {}).get("chunk")
                if isinstance(chunk_data, dict):
                    for _node_name, node_output in chunk_data.items():
                        if isinstance(node_output, dict) and "messages" in node_output:
                            messages_in_chunk = node_output["messages"]
                            if messages_in_chunk and isinstance(messages_in_chunk[-1], AIMessageChunk):
                                logger.debug(f"Streaming AIMessageChunk from subgraph: {messages_in_chunk[-1].content}")
                                yield {"messages": [messages_in_chunk[-1]]}
            
            elif event["event"] == "on_chain_end" and event["name"] == "LangGraph": 
                if isinstance(event["data"], dict) and "output" in event["data"]:
                    # The output here is the final state of the subgraph
                    final_subgraph_state_dict = event["data"]["output"]
                    logger.info(f"Subgraph astream_events ended. Final state keys: {final_subgraph_state_dict.keys() if isinstance(final_subgraph_state_dict, dict) else 'Not a dict'}")
                else:
                    logger.warning(f"Subgraph astream_events ended but final output format is unexpected: {event['data']}")
                break 

        if final_subgraph_state_dict is None:
            logger.error("Robot flow subgraph astream_events completed, but final_subgraph_state_dict was not captured correctly.")
            raise ValueError("Failed to capture final state from robot_flow_subgraph astream_events.")

        logger.info("Robot flow subgraph execution via astream_events completed.")

    except GraphRecursionError as gre:
        logger.error(f"GraphRecursionError during robot_flow_subgraph.astream_events: {gre}", exc_info=True)
        error_message_content = f"Error: Robot flow planning module encountered a recursion limit. Details: {str(gre)}"
        messages_to_return = list(current_main_messages or []) + [AIMessage(content=error_message_content)]
        yield {
            "messages": messages_to_return,
            "subgraph_completion_status": "error",
            "is_error": True, 
            "error_message": error_message_content,
            "sas_planner_subgraph_state": None # Clear SAS state on error
        }
        return 
    except Exception as e:
        logger.error(f"Error during robot_flow_subgraph.astream_events execution: {e}", exc_info=True)
        error_message_content = f"Error: An issue occurred while interacting with the robot flow planning module. Details: {str(e)}"
        messages_to_return = list(current_main_messages or []) + [AIMessage(content=error_message_content)]
        yield {
            "messages": messages_to_return,
            "subgraph_completion_status": "error",
            "is_error": True,
            "error_message": error_message_content,
            "sas_planner_subgraph_state": None # Clear SAS state on error
        }
        return 

    # 5. 从子图的最终状态提取消息历史和完成状态
    subgraph_final_messages: List[BaseMessage] = []
    completion_status: Optional[str] = None
    
    if isinstance(final_subgraph_state_dict, dict):
        # The messages from the subgraph state are what we need to pass back to the main graph's history.
        subgraph_final_messages = final_subgraph_state_dict.get("messages", []) 
        completion_status = final_subgraph_state_dict.get("subgraph_completion_status")
        logger.info(f"Extracted from final_subgraph_state_dict: {len(subgraph_final_messages)} messages, status: {completion_status}")
    else:
        logger.error(f"final_subgraph_state_dict is not a dictionary. Type: {type(final_subgraph_state_dict)}. Cannot extract messages or status.")
        error_message_content = "Internal error: Subgraph returned an unexpected final state format."
        messages_to_return = list(current_main_messages or []) + [AIMessage(content=error_message_content)]
        yield {
            "messages": messages_to_return,
            "subgraph_completion_status": "error",
            "is_error": True,
            "error_message": error_message_content,
            "sas_planner_subgraph_state": None # Clear SAS state
        }
        return 

    if not subgraph_final_messages and completion_status != "needs_clarification":
        logger.warning("Robot flow subgraph did not return any messages and does not need clarification. Main history might not be fully updated by subgraph.")
        # This situation is a bit ambiguous. If the subgraph truly finished without messages,
        # we still need to decide what the main graph's message history should be.
        # For now, we will pass back the subgraph_final_messages (which is empty in this branch).
        # The main graph usually expects the message history to be continuous.
        # If the subgraph is meant to clear history, it should do so explicitly in its state.

    # 6. 更新主图的状态
    logger.info(f"Robot flow subgraph returned {len(subgraph_final_messages)} messages. Updating main graph state.")

    update_dict: dict[str, Any] = { # Make type explicit for clarity
        "messages": subgraph_final_messages, # Use messages from the subgraph's state
        "subgraph_completion_status": completion_status,
    }

    if completion_status == "needs_clarification":
        logger.info("Subgraph needs clarification. Preserving task_route_decision and user_request_for_router. Storing SAS subgraph state.")
        # Preserve routing decision for re-entry
        if state.get("task_route_decision") is not None:
            update_dict["task_route_decision"] = state.get("task_route_decision")
        if state.get("user_request_for_router") is not None:
            update_dict["user_request_for_router"] = state.get("user_request_for_router")
        # Store the full state of the SAS subgraph for persistence
        update_dict["sas_planner_subgraph_state"] = final_subgraph_state_dict 
    elif completion_status == "completed_success":
        logger.info(f"Subgraph completed successfully. Extracting important data and preserving SAS state for sync.")
        # Clear routing decision as workflow is complete
        update_dict["task_route_decision"] = None
        update_dict["user_request_for_router"] = None
        
        # **关键修复**：保留SAS子图状态以便数据同步
        # 即使子图完成，我们也需要保留状态用于状态同步
        update_dict["sas_planner_subgraph_state"] = final_subgraph_state_dict
        
        # **新增**：直接提取重要数据到主图状态
        if isinstance(final_subgraph_state_dict, dict):
            # 提取任务数据
            if "sas_step1_generated_tasks" in final_subgraph_state_dict:
                update_dict["sas_step1_generated_tasks"] = final_subgraph_state_dict["sas_step1_generated_tasks"]
                logger.info(f"Extracted {len(final_subgraph_state_dict['sas_step1_generated_tasks'])} tasks from SAS subgraph")
            
            # 提取详情数据
            if "sas_step2_generated_task_details" in final_subgraph_state_dict:
                update_dict["sas_step2_generated_task_details"] = final_subgraph_state_dict["sas_step2_generated_task_details"]
                logger.info(f"Extracted {len(final_subgraph_state_dict['sas_step2_generated_task_details'])} task details from SAS subgraph")
            
            # 提取其他重要状态
            important_fields = ["current_user_request", "dialog_state", "task_list_accepted", "module_steps_accepted"]
            for field in important_fields:
                if field in final_subgraph_state_dict:
                    update_dict[field] = final_subgraph_state_dict[field]
                    logger.info(f"Extracted {field}: {final_subgraph_state_dict[field]}")
    else: # Covers "error" or other unexpected terminal status
        logger.info(f"Subgraph completion status is '{completion_status}'. Clearing task_route_decision, user_request_for_router, and SAS subgraph state.")
        update_dict["task_route_decision"] = None
        update_dict["user_request_for_router"] = None
        update_dict["sas_planner_subgraph_state"] = None # Clear persisted SAS state on error
        
    yield update_dict 