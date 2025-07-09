from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, Response
import asyncio
import json
import time
from typing import Any, Dict, AsyncGenerator, Optional
import os
from dotenv import load_dotenv
import logging
from collections import defaultdict

from sqlalchemy.orm import Session
from backend.app import schemas, utils
from database.connection import get_db

from langchain_google_genai import ChatGoogleGenerativeAI
# from langgraph.checkpoint.aiopg import PostgresSaver # Old import
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # CORRECTED Import for async Postgres
from langchain_core.messages import AIMessage, AIMessageChunk

from backend.sas.graph_builder import create_robot_flow_graph
from backend.config import DB_CONFIG # Import DB_CONFIG for database URL
from backend.app.dependencies import get_checkpointer
from backend.sas.state import RobotFlowAgentState # 确保导入

load_dotenv() # Load .env file

logger = logging.getLogger(__name__)

# --- Stream End Sentinel ---
STREAM_END_SENTINEL = object()

# --- LLM Initialization ---
LLM_INSTANCE = None
try:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
    if google_api_key:
        LLM_INSTANCE = ChatGoogleGenerativeAI(
            model=gemini_model_name,
            google_api_key=google_api_key,
            temperature=0,
            convert_system_message_to_human=True
        )
        logger.info(f"SAS Chat Router: Successfully initialized Gemini LLM: {gemini_model_name}")
    else:
        logger.error("SAS Chat Router: GOOGLE_API_KEY not found. LLM_INSTANCE is None.")
except Exception as e:
    logger.error(f"SAS Chat Router: Error initializing Gemini LLM: {e}. LLM_INSTANCE is None.")
# --- End LLM Initialization ---

# --- Persistence (Checkpointer) Initialization ---
# Note: AsyncPostgresSaver initialization needs to be done within an async context
# Since this module is loaded at startup, we'll need to initialize it lazily or use the app's checkpointer
CHECKPOINTER = None
print("SAS Chat Router: CHECKPOINTER will be initialized from app.state when needed.")
# --- End Persistence Initialization ---

# --- SAS App Initialization ---
# The sas_app will be created dynamically with the checkpointer from app.state
def get_sas_app(checkpointer: AsyncPostgresSaver = Depends(get_checkpointer)):
    """Get or create the SAS app with the current checkpointer"""
    if LLM_INSTANCE:
        return create_robot_flow_graph(llm=LLM_INSTANCE, checkpointer=checkpointer)
    else:
        logger.error("SAS Chat Router: LLM_INSTANCE is None, returning dummy app.")
        class DummySasApp:
            async def ainvoke(self, *args, **kwargs): return {"error": "LLM not configured for SAS app"}
            async def aget_state(self, *args, **kwargs): return {"error": "LLM not configured for SAS app"}
            async def aupdate_state(self, *args, **kwargs): return {"error": "LLM not configured for SAS app"}
            async def astream_events(self, *args, **kwargs):
                async def empty_generator():
                    yield {"error": "LLM not configured for SAS app"}
                    return
                return empty_generator()
        return DummySasApp()
# --- End SAS App Initialization ---

# --- 新增: 权限验证依赖 ---
async def verify_flow_access(
    chat_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(utils.get_current_user)
):
    """
    一个依赖项，用于验证当前登录用户是否有权访问此流程(chat_id/flow_id)。
    如果用户未登录或无权访问，将引发HTTPException。
    """
    utils.verify_flow_ownership(flow_id=chat_id, current_user=current_user, db=db)
    return current_user
# --- 结束新增 ---

router = APIRouter(
    prefix="/sas", # 修复：统一使用 /sas 前缀，与前端期望保持一致
    tags=["sas"],
    responses={404: {"description": "Not found"}},
)

@router.post("/threads", status_code=201)  # 调整为 /sas/threads
async def initialize_sas_thread(
    request: Request,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(utils.get_current_user),
    db: Session = Depends(get_db)
):
    """
    为新的 flow_id 初始化 LangGraph 状态。
    当前端创建一个新流程后，应立即调用此端点。
    
    请求体应包含: {"flow_id": "uuid-string"}
    """
    try:
        body = await request.json()
        flow_id = body.get("flow_id")
        
        if not flow_id:
            raise HTTPException(status_code=400, detail="Missing 'flow_id' in request body")
        
        # First, verify ownership of the flow record itself
        utils.verify_flow_ownership(flow_id, user, db)
        
        config = {"configurable": {"thread_id": flow_id}}
        
        # Check if state already exists to prevent accidental overwrites
        try:
            existing_state = await sas_app.aget_state(config)
            if existing_state and get_checkpoint_values(existing_state):
                logger.warning(f"SAS state for thread {flow_id} already exists. Not re-initializing.")
                return {"status": "exists", "thread_id": flow_id, "message": "SAS thread already initialized"}
        except Exception as check_error:
            logger.info(f"No existing state found for thread {flow_id}, proceeding with initialization")

        # Create a new, default state using dictionary to avoid type checking issues
        initial_state_dict = {
            "messages": [],
            "current_chat_id": flow_id,
            "thread_id": flow_id,
            "dialog_state": "initial",
            "config": {},
            "task_list_accepted": False,
            "module_steps_accepted": False,
            "is_error": False,
            "language": "zh",
            "relation_xml_content": "",
            "relation_xml_path": "",
            "revision_iteration": 0,
            "generated_node_xmls": [],
            "merged_xml_file_paths": []
        }
        
        await sas_app.aupdate_state(config, initial_state_dict)
        logger.info(f"Successfully initialized SAS state for thread_id: {flow_id}")
        
        return {"status": "created", "thread_id": flow_id, "message": "SAS thread initialized successfully"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Failed to initialize SAS state for thread_id {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize SAS state: {e}")

@router.delete("/threads/{thread_id}", status_code=204)  # 调整为 /sas/threads/{thread_id}
async def delete_sas_thread(
    thread_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access) # verify_flow_access uses chat_id, which is thread_id here
):
    """
    删除与 flow_id 关联的 LangGraph 状态。
    注意：这取决于 checkpointer 的实现。
    对于 AsyncPostgresSaver, 没有直接的删除方法, 此处为逻辑占位。
    """
    # verify_flow_access is already called via Depends
    logger.info(f"Attempting to delete SAS thread for flow {thread_id} by user {user.id}")
    
    # TODO: Implement actual deletion if the checkpointer backend supports it.
    # For now, this endpoint serves as a logical placeholder for the complete workflow.
    # e.g., await sas_app.checkpointer.adelete(config)
    
    try:
        # For now, we can try to clear the state by setting it to an empty/initial state
        # This is a workaround until proper deletion is implemented
        config = {"configurable": {"thread_id": thread_id}}
        
        # Try to get current state to verify it exists
        current_state = await sas_app.aget_state(config)
        if current_state and hasattr(current_state, 'values'):
            logger.info(f"Found existing SAS state for thread {thread_id}, clearing it")
            # Set to a minimal/empty state as a form of "deletion"
            empty_state_dict = {
                "messages": [],
                "current_chat_id": thread_id,
                "thread_id": thread_id,
                "dialog_state": "initial",
                "config": {},
                "task_list_accepted": False,
                "module_steps_accepted": False,
                "is_error": False,
                "language": "zh",
                "relation_xml_content": "",
                "relation_xml_path": "",
                "revision_iteration": 0,
                "generated_node_xmls": [],
                "merged_xml_file_paths": []
            }
            empty_state_dict['current_step_description'] = 'Thread deleted'
            
            await sas_app.aupdate_state(config, empty_state_dict)
            logger.info(f"Successfully cleared SAS state for thread {thread_id}")
        else:
            logger.info(f"No SAS state found for thread {thread_id}, nothing to delete")
            
    except Exception as e:
        logger.warning(f"Could not clear SAS state for thread {thread_id}: {e}")
        # Don't raise an exception here as the deletion might still be considered successful
        # from a business logic perspective
    
    logger.warning(f"SAS thread deletion for {thread_id} is not fully implemented in the backend checkpointer.")
    
    return Response(status_code=204)

# This function was a placeholder based on your last version of the file.
# If it was meant to interact with chat history from the DB for the graph,
# the graph itself (via checkpointer) would handle that state implicitly.
# Keeping it if it serves another purpose or if you want to adapt it.
async def get_chat_history(chat_id: str):
    # In a real scenario, this would fetch from a database or memory
    print(f"Fetching history for chat_id: {chat_id} (placeholder) - Note: Graph manages its own history via checkpointer.")
    return None # Or some history object

def get_checkpoint_values(checkpoint_obj) -> dict:
    """
    健壮地获取checkpoint的values，处理可能是方法或属性的情况
    """
    if not checkpoint_obj or not hasattr(checkpoint_obj, 'values'):
        return {}
    
    try:
        if callable(checkpoint_obj.values):
            result = checkpoint_obj.values()
        else:
            result = checkpoint_obj.values
        
        # 确保返回的是字典类型
        if isinstance(result, dict):
            return result
        else:
            logger.warning(f"Checkpoint values is not a dict, got: {type(result)}")
            return {}
    except Exception as e:
        logger.error(f"Error getting checkpoint values: {e}")
        return {}

async def _prepare_frontend_update(final_state: dict, flow_id: str) -> dict:
    """
    准备前端更新数据，直接从LangGraph状态，不存储副本到Flow模型
    遵循单一数据源原则：LangGraph PostgreSQL是唯一真实数据源
    """
    try:
        logger.info(f"[SAS Flow {flow_id}] 🎯 准备前端更新数据...")
        
        # SAS specific important fields that should trigger frontend updates
        important_fields = [
            'sas_step1_generated_tasks',
            'sas_step2_generated_task_details', 
            'sas_step2_module_steps',
            'task_list_accepted',
            'module_steps_accepted',
            'dialog_state',
            'subgraph_completion_status',
            'current_user_request',
            'revision_iteration',
            'clarification_question',
            'parsed_flow_steps',
            'generated_node_xmls',
            'final_flow_xml_content'
        ]
        
        # 检查是否有重要字段存在，决定是否需要前端更新
        has_important_fields = any(field in final_state for field in important_fields)
        
        if has_important_fields:
            # 提取前端需要的状态数据
            frontend_agent_state = {}
            update_types = []
            
            for field in important_fields:
                if field in final_state:
                    frontend_agent_state[field] = final_state[field]
                    update_types.append(field)
                    
                    if field in ['dialog_state', 'sas_step1_generated_tasks', 'subgraph_completion_status']:
                        logger.info(f"[SAS_FRONTEND_UPDATE] 包含重要字段: {field} = {final_state[field]}")
            
            logger.info(f"[SAS Flow {flow_id}] 🎯 准备发送前端更新，字段: {update_types}")
            
            return {
                "needs_frontend_update": True,
                "update_types": update_types,
                "updated_agent_state": frontend_agent_state
            }
        else:
            logger.info(f"[SAS Flow {flow_id}] 🎯 无重要字段变化，无需前端更新")
            return {"needs_frontend_update": False}
            
    except Exception as e:
        logger.error(f"[SAS Flow {flow_id}] 🎯 准备前端更新失败: {e}", exc_info=True)
        return {"needs_frontend_update": False}

# Global event broadcasting system for SAS SSE events
class SASEventBroadcaster:
    def __init__(self):
        self.chat_queues: Dict[str, asyncio.Queue] = {}
        self.active_connections: Dict[str, int] = defaultdict(int)  # Track active SSE connections per chat
    
    async def get_or_create_queue(self, chat_id: str) -> asyncio.Queue:
        """Get or create event queue for a chat"""
        if chat_id not in self.chat_queues:
            self.chat_queues[chat_id] = asyncio.Queue(maxsize=1000)
        return self.chat_queues[chat_id]
    
    async def broadcast_event(self, chat_id: str, event_data: dict):
        """Broadcast event to all SSE connections for a chat"""
        if chat_id in self.chat_queues:
            try:
                await self.chat_queues[chat_id].put(event_data)
                logger.debug(f"[BROADCASTER] Event broadcast to chat {chat_id}: {event_data.get('type', 'unknown')}")
            except asyncio.QueueFull:
                logger.warning(f"[BROADCASTER] Queue full for chat {chat_id}, dropping event")
    
    def register_connection(self, chat_id: str):
        """Register a new SSE connection"""
        self.active_connections[chat_id] += 1
        logger.info(f"[BROADCASTER] SSE connection registered for {chat_id}, total: {self.active_connections[chat_id]}")
    
    def unregister_connection(self, chat_id: str):
        """Unregister an SSE connection"""
        if chat_id in self.active_connections:
            self.active_connections[chat_id] = max(0, self.active_connections[chat_id] - 1)
            logger.info(f"[BROADCASTER] SSE connection unregistered for {chat_id}, remaining: {self.active_connections[chat_id]}")
            
            # Clean up queue if no more connections
            if self.active_connections[chat_id] == 0 and chat_id in self.chat_queues:
                logger.info(f"[BROADCASTER] Cleaning up queue for {chat_id} (no more connections)")
                del self.chat_queues[chat_id]
                del self.active_connections[chat_id]

# Global broadcaster instance
event_broadcaster = SASEventBroadcaster()

async def _process_sas_events(
    chat_id: str, 
    message_content: str, 
    sas_app,
    flow_id: str = ''
):
    """
    Process SAS LangGraph execution and broadcast SSE events via global broadcaster
    """
    logger.info(f"[SAS Chat {chat_id}] Background task started. Input: {message_content[:100]}...")
    is_error = False
    error_data = {}
    final_state = None

    try:
        # Prepare graph input, merging initial state values.
        # This ensures the graph starts with a clean, correct state for this run.
        logger.info(f"[SAS Chat {chat_id}] Preparing initial state for graph execution.")
        
        # 🔧 获取当前持久化状态，避免不必要的重置
        current_persistent_state = {}
        try:
            config = {"configurable": {"thread_id": chat_id}}
            current_state_snapshot = await sas_app.aget_state(config)
            if current_state_snapshot:
                current_persistent_state = get_checkpoint_values(current_state_snapshot)
                logger.info(f"[SAS Chat {chat_id}] 获取到持久化状态，task_list_accepted: {current_persistent_state.get('task_list_accepted', False)}, module_steps_accepted: {current_persistent_state.get('module_steps_accepted', False)}")
        except Exception as state_get_error:
            logger.warning(f"[SAS Chat {chat_id}] 获取持久化状态失败，将使用默认值: {state_get_error}")
        
        # 🔧 根据当前持久化状态设置初始值，避免不正确的重置
        graph_input = {
            "dialog_state": "sas_processing_user_input",
            "current_step_description": "Processing your request...",
            "current_user_request": message_content,
            "task_list_accepted": current_persistent_state.get("task_list_accepted", False),      # 🔧 保留持久化状态
            "module_steps_accepted": current_persistent_state.get("module_steps_accepted", False), # 🔧 保留持久化状态
            "revision_iteration": current_persistent_state.get("revision_iteration", 0),
            "sas_step1_generated_tasks": current_persistent_state.get("sas_step1_generated_tasks", []),
            "sas_step2_module_steps": current_persistent_state.get("sas_step2_module_steps", ""),
            "clarification_question": "",
            "user_input": message_content, # Pass the input through
            "current_chat_id": chat_id,  # For progress events
            "thread_id": chat_id,       # For state management
        }

        # Adjust state for specific approval actions
        if message_content == "accept_tasks":
            graph_input["dialog_state"] = "sas_tasks_accepted_processing"
            graph_input["current_step_description"] = "Tasks approved. Generating module steps..."
            graph_input["task_list_accepted"] = True
        elif message_content == "accept_module_steps":
            graph_input["dialog_state"] = "sas_modules_accepted_processing"
            graph_input["current_step_description"] = "Module steps approved. Proceeding to next phase..."
            graph_input["module_steps_accepted"] = True
        elif message_content == "accept":
            # 新增：处理通用的"accept"指令，根据当前状态判断是哪种accept
            # 🔧 使用已获取的持久化状态，避免重复查询造成的竞态条件
            current_dialog_state = current_persistent_state.get('dialog_state')
            
            logger.info(f"[SAS Chat {chat_id}] 收到通用accept指令，当前状态: {current_dialog_state}")
            
            if current_dialog_state == 'sas_awaiting_task_list_review':
                # 在任务列表审核阶段，转换为任务接受
                graph_input["dialog_state"] = "sas_tasks_accepted_processing"
                graph_input["current_step_description"] = "Tasks approved. Generating module steps..."
                graph_input["task_list_accepted"] = True
                logger.info(f"[SAS Chat {chat_id}] 通用accept解释为任务列表接受")
            elif current_dialog_state == 'sas_awaiting_module_steps_review':
                # 在模块步骤审核阶段，转换为模块步骤接受
                graph_input["dialog_state"] = "sas_modules_accepted_processing"
                graph_input["current_step_description"] = "Module steps approved. Proceeding to next phase..."
                graph_input["module_steps_accepted"] = True
                logger.info(f"[SAS Chat {chat_id}] 通用accept解释为模块步骤接受")
            else:
                # 如果不在预期的审核状态，按普通用户输入处理
                logger.warning(f"[SAS Chat {chat_id}] 收到accept但当前状态不是审核状态: {current_dialog_state}")

        config = {"configurable": {"thread_id": chat_id}}
        
        logger.info(f"[SAS Chat {chat_id}] Invoking SAS graph with astream_events...")
        
        async for event in sas_app.astream_events(graph_input, config=config, version="v2"):
            event_name = event.get("event")
            event_data = event.get("data", {})
            run_name = event.get("name", "unknown_run")

            logger.debug(f"[SAS Chat {chat_id}] Received event: '{event_name}' from '{run_name}'")
            
            if event_name == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and isinstance(chunk, AIMessageChunk) and chunk.content:
                    token = chunk.content
                    logger.debug(f"[SAS Chat {chat_id}] LLM Token: '{token}'")
                    await event_broadcaster.broadcast_event(chat_id, {"type": "token", "data": token})
            
            elif event_name == "on_tool_start":
                tool_name = event_data.get("name")
                tool_input = event_data.get("input")
                logger.info(f"[SAS Chat {chat_id}] Tool Start: '{tool_name}'")
                await event_broadcaster.broadcast_event(chat_id, {"type": "tool_start", "data": {"name": tool_name, "input": tool_input}})
                
            elif event_name == "on_tool_end":
                tool_name = event_data.get("name")
                tool_output = event_data.get("output")
                logger.info(f"[SAS Chat {chat_id}] Tool End: '{tool_name}'")
                await event_broadcaster.broadcast_event(chat_id, {"type": "tool_end", "data": {"name": tool_name, "output_summary": str(tool_output)[:200]}})
            
            elif event_name == "on_chain_end":
                outputs_from_chain = event_data.get("output", {})
                logger.info(f"[SAS Chat {chat_id}] 🚨 Chain End: '{run_name}'. Output keys: {list(outputs_from_chain.keys()) if isinstance(outputs_from_chain, dict) else 'Not a dict'}")
                
                should_sync = False
                sync_reason = ""
                has_error_state = False
                
                # Check if this is the main graph or SAS-related chain
                if run_name in ["__graph__", "sas_user_input_to_task_list", "sas_review_and_refine", "sas_process_to_module_steps"] or "sas" in run_name.lower():
                    if isinstance(outputs_from_chain, dict):
                        # 首先检查是否有错误状态
                        if outputs_from_chain.get("is_error", False) or outputs_from_chain.get("dialog_state") == "error" or outputs_from_chain.get("subgraph_completion_status") == "error":
                            has_error_state = True
                            error_message = outputs_from_chain.get("error_message", "Unknown error occurred in SAS processing")
                            logger.error(f"[SAS Chat {chat_id}] 🚨 检测到节点错误状态: {error_message}")
                            
                            # 立即发送错误事件到前端
                            error_data = {
                                "message": error_message, 
                                "stage": f"sas_node_error_in_{run_name}",
                                "dialog_state": outputs_from_chain.get("dialog_state"),
                                "subgraph_completion_status": outputs_from_chain.get("subgraph_completion_status")
                            }
                            await event_broadcaster.broadcast_event(chat_id, {"type": "error", "data": error_data})
                            is_error = True
                            
                        important_keys = [
                            'sas_step1_generated_tasks',
                            'dialog_state',
                            'subgraph_completion_status',
                            'task_list_accepted',
                            'module_steps_accepted',
                            'clarification_question'
                        ]
                        
                        found_keys = [key for key in important_keys if key in outputs_from_chain]
                        if found_keys:
                            should_sync = True
                            sync_reason = f"SAS状态更新 (run_name: {run_name}, found_keys: {found_keys}, has_error: {has_error_state})"
                            final_state = outputs_from_chain
                            logger.info(f"[SAS Chat {chat_id}] 🎯 触发同步: {sync_reason}")
                
                if should_sync and flow_id and final_state:
                    try:
                        # 准备前端更新数据（不涉及Flow模型，遵循单一数据源原则）
                        frontend_update_result = await _prepare_frontend_update(final_state, flow_id)
                        
                        if frontend_update_result and frontend_update_result.get("needs_frontend_update"):
                            logger.info(f"[SAS Chat {chat_id}] 🎯 发送agent_state_updated事件到前端")
                            await event_broadcaster.broadcast_event(chat_id, {
                                "type": "agent_state_updated", 
                                "data": {
                                    "message": "SAS agent state updated",
                                    "update_types": frontend_update_result.get("update_types", []),
                                    "flow_id": flow_id,
                                    "agent_state": frontend_update_result.get("updated_agent_state", {}),
                                    "trigger": "sas_chain_end"
                                }
                            })
                            # 给前端时间处理这个重要事件
                            await asyncio.sleep(0.1)
                        else:
                            logger.info(f"[SAS Chat {chat_id}] 🎯 状态处理完成但无需前端更新")
                            # 即使无重要字段变化，也发送基本的状态信息让前端知道处理已完成
                            if final_state and final_state.get("dialog_state"):
                                await event_broadcaster.broadcast_event(chat_id, {
                                    "type": "agent_state_updated",
                                    "data": {
                                        "message": "SAS state processing completed",
                                        "flow_id": flow_id,
                                        "agent_state": {
                                            "dialog_state": final_state.get("dialog_state"),
                                            "clarification_question": final_state.get("clarification_question"),
                                            "sas_step1_generated_tasks": final_state.get("sas_step1_generated_tasks"),
                                            "task_list_accepted": final_state.get("task_list_accepted"),
                                            "module_steps_accepted": final_state.get("module_steps_accepted"),
                                            "subgraph_completion_status": final_state.get("subgraph_completion_status")
                                        },
                                        "trigger": "sas_state_completed"
                                    }
                                })
                                # 给前端时间处理这个事件
                                await asyncio.sleep(0.1)
                    except Exception as frontend_update_error:
                        logger.error(f"[SAS Chat {chat_id}] 🎯 前端更新过程中出错: {frontend_update_error}", exc_info=True)
            
            elif event_name in ["on_chain_error", "on_llm_error", "on_tool_error"]:
                error_content = str(event_data.get("error", "Unknown error"))
                logger.error(f"[SAS Chat {chat_id}] Error event '{event_name}' from '{run_name}': {error_content}")
                is_error = True
                error_data = {"message": f"Error in {run_name}: {error_content}", "stage": f"error_in_{run_name}"}
                await event_broadcaster.broadcast_event(chat_id, {"type": "error", "data": error_data})

    except Exception as e:
        is_error = True
        error_message = f"Error during SAS LangGraph processing: {str(e)}"
        logger.error(f"[SAS Chat {chat_id}] {error_message}", exc_info=True)
        error_data = {"message": error_message, "stage": "sas_execution"}
        try:
            await event_broadcaster.broadcast_event(chat_id, {"type": "error", "data": error_data})
        except Exception as qe:
            logger.error(f"[SAS Chat {chat_id}] Failed to broadcast error: {qe}")

    finally:
        try:
            # 给前端一点时间处理之前的事件，特别是agent_state_updated事件
            await asyncio.sleep(0.5)  # 500ms延迟确保重要事件被处理
            
            # 不再发送stream_end事件，保持SSE连接开启
            # logger.info(f"[SAS Chat {chat_id}] Broadcasting stream_end event.")
            # await event_broadcaster.broadcast_event(chat_id, {"type": "stream_end", "data": {"chat_id": chat_id}})
            # logger.info(f"[SAS Chat {chat_id}] Stream end event broadcast.")
            
            # 发送处理完成事件，但保持连接
            logger.info(f"[SAS Chat {chat_id}] Broadcasting processing_complete event (keeping connection alive).")
            await event_broadcaster.broadcast_event(chat_id, {
                "type": "processing_complete", 
                "data": {
                    "chat_id": chat_id, 
                    "message": "SAS processing completed, connection remains open for future events"
                }
            })
            
        except Exception as qe:
            logger.error(f"[SAS Chat {chat_id}] Failed to broadcast processing_complete: {qe}")
        
        logger.info(f"[SAS Chat {chat_id}] Background task completed, but SSE connection remains open.")

@router.post("/{chat_id}/events")
async def sas_chat_events_post(
    chat_id: str,
    request: Request,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    SAS POST端点：启动SAS处理并返回SSE流
    """
    # 处理POST请求：启动SAS处理
    try:
        body = await request.json()
        message_content = body.get("input")

        if message_content is None:
            raise HTTPException(status_code=400, detail="Missing 'input' in request body")

        logger.info(f"SAS POST for chat_id/thread_id: {chat_id}, input: {message_content[:100]}...")

        # Extract flow_id from chat_id if possible (for state sync)
        flow_id = chat_id  # Assuming chat_id is flow_id for SAS
        
        # Start background task to process SAS events using the global broadcaster
        asyncio.create_task(_process_sas_events(chat_id, message_content, sas_app, flow_id))
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body.")
    except Exception as e:
        logger.error(f"Error in POST /sas/{chat_id}/events: {e}", exc_info=True)
        # 即使启动处理失败，也尝试提供SSE流来发送错误信息
        await event_broadcaster.broadcast_event(chat_id, {
            "type": "error", 
            "data": {"message": f"Failed to start processing: {str(e)}", "stage": "startup"}
        })

    # 返回SSE流
    logger.info(f"SAS SSE stream for chat_id/thread_id: {chat_id}")
    
    # Register this SSE connection
    event_broadcaster.register_connection(chat_id)
    
    async def event_generator():
        try:
            # 🔧 修复：使用标准SSE格式发送起始事件
            yield f"event: start\ndata: {json.dumps({'run_id': chat_id})}\n\n"
            
            # Get or create event queue for this chat
            event_queue = await event_broadcaster.get_or_create_queue(chat_id)
            
            while True:
                try:
                    # Wait for events from the broadcaster queue
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    
                    # 检查是否收到断开连接的信号
                    if event_item.get("type") == "connection_close":
                        logger.info(f"[SAS Events {chat_id}] Received connection_close signal")
                        yield f"event: connection_close\ndata: {json.dumps(event_item.get('data', {}))}\n\n"
                        break
                    
                    # 移除stream_end的特殊处理，让连接保持开启
                    # if event_item.get("type") == "stream_end":
                    #     logger.info(f"[SAS Events {chat_id}] Received stream end")
                    #     # 🔧 修复：使用标准SSE格式
                    #     yield f"event: stream_end\ndata: {json.dumps(event_item.get('data', {}))}\n\n"
                    #     break
                    
                    # 🔧 修复：使用标准SSE格式发送所有事件（包括processing_complete）
                    event_type = event_item.get("type", "message")
                    event_data = event_item.get("data", {})
                    logger.debug(f"[SAS Events {chat_id}] Sending event '{event_type}' with data: {str(event_data)[:100]}...")
                    yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                        
                except asyncio.TimeoutError:
                    logger.debug(f"[SAS Events {chat_id}] SSE timeout, sending ping")
                    # 🔧 修复：使用标准SSE格式发送ping
                    yield f"event: ping\ndata: {json.dumps({'timestamp': time.time()})}\n\n"
                    continue
                        
        except Exception as stream_exc:
            logger.error(f"[SAS Events {chat_id}] SSE流错误: {stream_exc}", exc_info=True)
            # 🔧 修复：使用标准SSE格式发送错误
            yield f"event: error\ndata: {json.dumps({'error': str(stream_exc)})}\n\n"
        finally:
            logger.info(f"[SAS Events {chat_id}] SSE事件流结束")
            # Unregister connection when SSE ends
            event_broadcaster.unregister_connection(chat_id)
            # 🔧 修复：使用标准SSE格式发送结束事件
            yield f"event: end\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/{chat_id}/events")
async def sas_chat_events_get(
    chat_id: str,
    request: Request,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    SAS GET端点：连接到现有的SSE流
    """
    logger.info(f"SAS GET SSE stream for chat_id/thread_id: {chat_id}")
    
    # Register this SSE connection
    event_broadcaster.register_connection(chat_id)
    
    async def event_generator():
        try:
            # 🔧 修复：使用标准SSE格式发送起始事件
            yield f"event: start\ndata: {json.dumps({'run_id': chat_id})}\n\n"
            
            # Get or create event queue for this chat
            event_queue = await event_broadcaster.get_or_create_queue(chat_id)
            
            while True:
                try:
                    # Wait for events from the broadcaster queue
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    
                    # 检查是否收到断开连接的信号
                    if event_item.get("type") == "connection_close":
                        logger.info(f"[SAS Events {chat_id}] Received connection_close signal")
                        yield f"event: connection_close\ndata: {json.dumps(event_item.get('data', {}))}\n\n"
                        break
                    
                    # 移除stream_end的特殊处理，让连接保持开启
                    # if event_item.get("type") == "stream_end":
                    #     logger.info(f"[SAS Events {chat_id}] Received stream end")
                    #     # 🔧 修复：使用标准SSE格式
                    #     yield f"event: stream_end\ndata: {json.dumps(event_item.get('data', {}))}\n\n"
                    #     break
                    
                    # 🔧 修复：使用标准SSE格式发送所有事件（包括processing_complete）
                    event_type = event_item.get("type", "message")
                    event_data = event_item.get("data", {})
                    logger.debug(f"[SAS Events {chat_id}] Sending event '{event_type}' with data: {str(event_data)[:100]}...")
                    yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                        
                except asyncio.TimeoutError:
                    logger.debug(f"[SAS Events {chat_id}] SSE timeout, sending ping")
                    # 🔧 修复：使用标准SSE格式发送ping
                    yield f"event: ping\ndata: {json.dumps({'timestamp': time.time()})}\n\n"
                    continue
                        
        except Exception as stream_exc:
            logger.error(f"[SAS Events {chat_id}] SSE流错误: {stream_exc}", exc_info=True)
            # 🔧 修复：使用标准SSE格式发送错误
            yield f"event: error\ndata: {json.dumps({'error': str(stream_exc)})}\n\n"
        finally:
            logger.info(f"[SAS Events {chat_id}] SSE事件流结束")
            # Unregister connection when SSE ends
            event_broadcaster.unregister_connection(chat_id)
            # 🔧 修复：使用标准SSE格式发送结束事件
            yield f"event: end\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/{chat_id}/update-state")
async def sas_update_state(
    chat_id: str,
    request: Request,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    Updates the state of a SAS LangGraph flow.
    """
    try:
        state_update_payload = await request.json()
        config = {"configurable": {"thread_id": chat_id}}
        updated_checkpoint = await sas_app.aupdate_state(config, state_update_payload)
        print(f"SAS update-state for chat_id/thread_id: {chat_id}, update: {state_update_payload}, response: {updated_checkpoint}")
        return updated_checkpoint
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body.")
    except Exception as e:
        print(f"Error in /sas/{chat_id}/update-state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{chat_id}/state")
async def sas_get_state(
    chat_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    Retrieves the current state of a SAS LangGraph flow.
    """
    try:
        # 确保用户权限验证完成
        if not user:
            raise HTTPException(status_code=401, detail="User authentication required")
        
        print(f"🔧 [DEBUG] SAS get-state for chat_id/thread_id: {chat_id}, user: {user.username if hasattr(user, 'username') else 'unknown'}")
        
        config = {"configurable": {"thread_id": chat_id}}
        
        # 添加重试机制，防止时序问题
        max_retries = 3
        retry_delay = 0.1
        current_checkpoint = None
        
        for attempt in range(max_retries):
            try:
                current_checkpoint = await sas_app.aget_state(config)
                if current_checkpoint:
                    break
                    
                print(f"🔧 [DEBUG] Attempt {attempt + 1}: No checkpoint found, retrying...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    
            except Exception as retry_error:
                print(f"🔧 [DEBUG] Attempt {attempt + 1} failed: {retry_error}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise retry_error
        
        print(f"🔧 [DEBUG] Current checkpoint type: {type(current_checkpoint)}")
        print(f"🔧 [DEBUG] Current checkpoint exists: {current_checkpoint is not None}")
        
        if current_checkpoint:
            # 使用辅助函数安全地获取values
            try:
                checkpoint_values = get_checkpoint_values(current_checkpoint)
                print(f"🔧 [DEBUG] Successfully got checkpoint values: {bool(checkpoint_values)}")
                
                if checkpoint_values:
                    dialog_state = checkpoint_values.get('dialog_state')
                    tasks = checkpoint_values.get('sas_step1_generated_tasks')
                    current_user_request = checkpoint_values.get('current_user_request')
                    
                    print(f"🔧 [DEBUG] Dialog state: {dialog_state}")
                    print(f"🔧 [DEBUG] Tasks count: {len(tasks) if tasks else 0}")
                    print(f"🔧 [DEBUG] Has user request: {bool(current_user_request)}")
                    
                    if tasks:
                        print(f"🔧 [DEBUG] ✅ Found {len(tasks)} tasks")
                    else:
                        print(f"🔧 [DEBUG] ❌ No tasks found")
                else:
                    print(f"🔧 [DEBUG] Failed to get checkpoint values")
            except Exception as values_error:
                print(f"🔧 [DEBUG] Error getting checkpoint values: {values_error}")
                # 即使获取values失败，仍然返回checkpoint，让前端处理
        else:
            print(f"🔧 [DEBUG] ❌ No checkpoint found after {max_retries} attempts")
        
        if not current_checkpoint:
            # 返回一个默认的空状态而不是404错误，避免前端处理问题
            print(f"🔧 [DEBUG] Returning default empty state for {chat_id}")
            return {
                "values": {
                    "dialog_state": "initial",
                    "messages": [],
                    "task_list_accepted": False,
                    "module_steps_accepted": False,
                    "current_step_description": "No state found, using default initial state"
                },
                "config": {"configurable": {"thread_id": chat_id}},
                "metadata": {"source": "default_empty_state"}
            }
            
        return current_checkpoint
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        error_msg = f"Error in /sas/{chat_id}/state: {e}"
        print(error_msg)
        logger.error(error_msg, exc_info=True)
        
        # 检查是否是权限相关的错误
        if "permission" in str(e).lower() or "unauthorized" in str(e).lower() or "forbidden" in str(e).lower():
            raise HTTPException(status_code=403, detail=f"Permission denied for thread_id {chat_id}")
        
        # 对于其他错误，返回一个更友好的错误信息
        raise HTTPException(status_code=500, detail=f"Unable to retrieve state for thread_id {chat_id}: {str(e)[:100]}")

# Further considerations:
# - Authentication/Authorization (important for production)
# - Error handling and logging
# - Input and Output Pydantic models for validation and serialization

@router.post("/{chat_id}/disconnect-sse")
async def disconnect_sse_connection(
    chat_id: str,
    user: schemas.User = Depends(verify_flow_access)
):
    """
    主动断开指定chat_id的SSE连接
    用于用户切换flow或关闭页面时清理连接
    """
    try:
        # 发送断开信号到所有该chat_id的SSE连接
        await event_broadcaster.broadcast_event(chat_id, {
            "type": "connection_close",
            "data": {
                "chat_id": chat_id,
                "reason": "client_requested_disconnect",
                "message": "SSE connection closed by client request"
            }
        })
        
        logger.info(f"Disconnect signal sent for chat {chat_id} SSE connections")
        return {"success": True, "message": f"Disconnect signal sent for chat {chat_id}"}
        
    except Exception as e:
        logger.error(f"Failed to send disconnect signal for chat {chat_id}: {e}")
        return {"success": False, "message": f"Failed to disconnect: {str(e)}"}

@router.get("/health")
async def health_check():
    """简单的健康检查端点"""
    return {"status": "ok", "message": "SAS Chat is healthy"}

@router.post("/{flow_id}/reset-stuck-state", response_model=schemas.SuccessResponse)
async def reset_stuck_state(
    flow_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    重置卡住的处理状态，通过checkpoint回退到最近的稳定状态
    """
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态
        current_state_snapshot = await sas_app.aget_state(config)
        if not current_state_snapshot:
            raise HTTPException(status_code=404, detail="未找到该流程的状态")
        
        current_state = get_checkpoint_values(current_state_snapshot)
        current_dialog_state = current_state.get('dialog_state')
        is_error_state = current_state.get('is_error', False)
        
        # 检查是否处于卡住或错误状态
        stuck_states = [
            'generating_xml_relation',
            'generating_xml_final', 
            'sas_generating_individual_xmls',
            'sas_module_steps_accepted_proceeding',
            'sas_all_steps_accepted_proceed_to_xml',
            'sas_step3_completed',
            'final_xml_generated_success',
            'error'
        ]
        
        if current_dialog_state not in stuck_states and not is_error_state:
            return {"success": True, "message": "当前状态不需要重置"}
        
        logger.info(f"Resetting stuck state for flow {flow_id} from: {current_dialog_state}")
        
        # 获取checkpoint历史
        checkpoint_history = []
        async for checkpoint_tuple in sas_app.aget_state_history(config):
            if hasattr(checkpoint_tuple, 'checkpoint') and checkpoint_tuple.checkpoint:
                checkpoint_history.append(checkpoint_tuple)
        
        if len(checkpoint_history) < 2:
            # 没有历史，创建干净的初始状态
            initial_state_dict = {
                "messages": [],
                "dialog_state": "initial",
                "config": {},
                "task_list_accepted": False,
                "module_steps_accepted": False,
                "is_error": False,
                "language": "zh",
                "relation_xml_content": "",
                "relation_xml_path": "",
                "revision_iteration": 0,
                "generated_node_xmls": [],
                "merged_xml_file_paths": [],
                "current_step_description": "Reset to clean initial state (no history found)"
            }
            
            await sas_app.aupdate_state(config, initial_state_dict)
            
            return {
                "success": True, 
                "message": "已重置到干净的初始状态",
                "reset_details": {
                    "from_state": current_dialog_state,
                    "to_state": "initial",
                    "reset_type": "clean_initial_state"
                }
            }
        
        # 定义稳定状态优先级（按重要性排序）
        stable_states_priority = [
            'sas_awaiting_module_steps_review',       # 最优先：模块步骤审查状态
            'sas_awaiting_task_list_review',          # 次优先：任务列表审查状态  
            'sas_step2_module_steps_generated_for_review',
            'sas_step1_tasks_generated',
            'sas_awaiting_module_steps_revision_input',
            'sas_awaiting_task_list_revision_input',
            'initial'                                 # 最后选择：初始状态
        ]
        
        # 查找最近的稳定checkpoint（跳过当前状态）
        target_checkpoint = None
        target_priority = float('inf')
        
        for i in range(1, len(checkpoint_history)):
            checkpoint_tuple = checkpoint_history[i]
            checkpoint_values = checkpoint_tuple.checkpoint.get('channel_values', {})
            dialog_state = checkpoint_values.get('dialog_state')
            is_error = checkpoint_values.get('is_error', False)
            
            # 寻找一个稳定且无错误的checkpoint
            if dialog_state in stable_states_priority and not is_error:
                priority = stable_states_priority.index(dialog_state)
                if priority < target_priority:
                    target_checkpoint = checkpoint_tuple
                    target_priority = priority
                    logger.info(f"Found better rollback target: {dialog_state} (priority {priority})")
                    
                    # 如果找到了最高优先级的状态，就停止搜索
                    if priority == 0:
                        break
        
        if not target_checkpoint:
            # 没有找到稳定checkpoint，创建初始状态
            initial_state_dict = {
                "messages": [],
                "dialog_state": "initial",
                "config": {},
                "task_list_accepted": False,
                "module_steps_accepted": False,
                "is_error": False,
                "language": "zh",
                "relation_xml_content": "",
                "relation_xml_path": "",
                "revision_iteration": 0,
                "generated_node_xmls": [],
                "merged_xml_file_paths": [],
                "current_step_description": "Reset to clean initial state (no stable checkpoint found)"
            }
            
            await sas_app.aupdate_state(config, initial_state_dict)
            
            return {
                "success": True, 
                "message": "已重置到干净的初始状态",
                "reset_details": {
                    "from_state": current_dialog_state,
                    "to_state": "initial",
                    "reset_type": "clean_initial_state"
                }
            }
        
        # 获取目标checkpoint的完整状态
        target_config = target_checkpoint.config
        target_checkpoint_data = await sas_app.aget_state(target_config)
        
        if not target_checkpoint_data:
            raise Exception("无法获取目标checkpoint的状态数据")
        
        # 使用目标checkpoint的完整状态
        target_state = dict(get_checkpoint_values(target_checkpoint_data))
        target_state['current_step_description'] = f"Reset to {target_state.get('dialog_state')} checkpoint from stuck state"
        target_state['user_input'] = None
        target_state['is_error'] = False
        target_state['error_message'] = None
        
        # 如果回退到审查状态，确保用户需要重新确认
        if target_state.get('dialog_state') == 'sas_awaiting_module_steps_review':
            target_state['module_steps_accepted'] = False
            target_state['completion_status'] = 'needs_clarification'
        elif target_state.get('dialog_state') == 'sas_awaiting_task_list_review':
            target_state['task_list_accepted'] = False
            target_state['module_steps_accepted'] = False
            target_state['completion_status'] = 'needs_clarification'
        
        await sas_app.aupdate_state(config, target_state)
        
        target_dialog_state = target_state.get('dialog_state')
        logger.info(f"Successfully reset stuck state for flow {flow_id} from {current_dialog_state} to {target_dialog_state}")
        
        return {
            "success": True, 
            "message": f"已从卡住状态重置到: {target_dialog_state}",
            "reset_details": {
                "from_state": current_dialog_state,
                "to_state": target_dialog_state,
                "checkpoint_time": target_config.get('configurable', {}).get('thread_ts'),
                "reset_type": "checkpoint_rollback"
            }
        }
            
    except Exception as e:
        logger.error(f"Failed to reset stuck state for flow {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重置卡住状态失败: {str(e)}")

@router.post("/{flow_id}/force-complete-processing", response_model=schemas.SuccessResponse)
async def force_complete_processing(
    flow_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    强制完成当前的处理步骤，跳转到完成状态
    """
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态
        state_snapshot = await sas_app.aget_state(config)
        if not state_snapshot:
            raise HTTPException(status_code=404, detail="未找到该流程的状态")
        
        current_state = get_checkpoint_values(state_snapshot)
        
        # 根据当前状态强制设置为适当的完成状态
        current_dialog_state = current_state.get('dialog_state')
        
        if current_dialog_state in ['generating_xml_relation', 'generating_xml_final']:
            # 如果正在生成XML，强制设置为完成状态
            completed_state = {
                **current_state,
                'dialog_state': 'sas_step3_completed',
                'subgraph_completion_status': 'completed_success',
                'is_error': False,
                'error_message': None,
                'current_step_description': 'Processing forcefully completed by user',
                # 如果没有XML路径，提供一个默认路径
                'final_flow_xml_path': current_state.get('final_flow_xml_path') or f'/tmp/flow_{flow_id}_force_completed.xml'
            }
        elif current_dialog_state in ['sas_generating_individual_xmls']:
            # 如果正在生成个体XML，设置为relation生成完成
            completed_state = {
                **current_state,
                'dialog_state': 'generating_xml_final',
                'current_step_description': 'Individual XMLs forcefully completed, proceeding to final XML'
            }
        else:
            # 其他处理状态，设置为通用完成状态
            completed_state = {
                **current_state,
                'dialog_state': 'sas_step3_completed',
                'subgraph_completion_status': 'completed_success',
                'current_step_description': 'Processing forcefully completed by user'
            }
        
        await sas_app.aupdate_state(config, completed_state)
        
        logger.info(f"Force completed processing for flow {flow_id} from state {current_dialog_state}")
        return {"success": True, "message": "已强制完成当前处理步骤"}
        
    except Exception as e:
        logger.error(f"Failed to force complete processing for flow {flow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"强制完成失败: {str(e)}")

@router.post("/{flow_id}/force-reset-state", response_model=schemas.SuccessResponse)
async def force_reset_state(
    flow_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    强制重置到最早的initial checkpoint状态（真正的checkpoint回退，而不是手动构造状态）
    """
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态信息（用于日志记录）
        current_state_snapshot = await sas_app.aget_state(config)
        current_dialog_state = 'unknown'
        if current_state_snapshot:
            current_dialog_state = get_checkpoint_values(current_state_snapshot).get('dialog_state', 'unknown')
        
        logger.info(f"Force resetting flow {flow_id} from state: {current_dialog_state}")
        
        # 获取完整的checkpoint历史（按时间倒序）
        checkpoint_history = []
        async for checkpoint_tuple in sas_app.aget_state_history(config):
            if hasattr(checkpoint_tuple, 'checkpoint') and checkpoint_tuple.checkpoint:
                checkpoint_history.append(checkpoint_tuple)
        
        # 查找最早的initial checkpoint（从历史列表的末尾开始查找）
        initial_checkpoint = None
        for checkpoint_tuple in reversed(checkpoint_history):
            checkpoint_values = checkpoint_tuple.checkpoint.get('channel_values', {})
            dialog_state = checkpoint_values.get('dialog_state')
            
            if dialog_state == 'initial':
                initial_checkpoint = checkpoint_tuple
                logger.info(f"Found initial checkpoint at {checkpoint_tuple.config}")
                break
        
        if initial_checkpoint:
            # 找到了initial checkpoint，回退到该状态
            target_config = initial_checkpoint.config
            target_checkpoint_data = await sas_app.aget_state(target_config)
            
            if not target_checkpoint_data:
                raise Exception("无法获取initial checkpoint的状态数据")
            
            # 使用initial checkpoint的完整状态
            initial_state = dict(get_checkpoint_values(target_checkpoint_data))
            initial_state['current_step_description'] = 'Reset to initial checkpoint state'
            initial_state['user_input'] = None  # 清理用户输入
            
            await sas_app.aupdate_state(config, initial_state)
            
            logger.info(f"Successfully reset flow {flow_id} to initial checkpoint from {current_dialog_state}")
            return {
                "success": True, 
                "message": "已重置到initial checkpoint状态",
                "reset_details": {
                    "from_state": current_dialog_state,
                    "to_state": "initial",
                    "checkpoint_time": target_config.get('configurable', {}).get('thread_ts'),
                    "reset_type": "checkpoint_rollback"
                }
            }
        else:
            # 没有找到initial checkpoint，创建一个真正干净的初始状态
            logger.warning(f"No initial checkpoint found for flow {flow_id}, creating fresh initial state")
            
            # 创建干净的初始状态
            initial_state_dict = {
                "messages": [],
                "dialog_state": "initial",
                "config": {},
                "task_list_accepted": False,
                "module_steps_accepted": False,
                "is_error": False,
                "language": "zh",
                "relation_xml_content": "",
                "relation_xml_path": "",
                "revision_iteration": 0,
                "generated_node_xmls": [],
                "merged_xml_file_paths": [],
                "current_step_description": "Reset to clean initial state (no checkpoint found)",
                "user_input": None
            }
            
            await sas_app.aupdate_state(config, initial_state_dict)
            
            logger.info(f"Successfully reset flow {flow_id} to clean initial state from {current_dialog_state}")
            return {
                "success": True, 
                "message": "已重置到干净的初始状态",
                "reset_details": {
                    "from_state": current_dialog_state,
                    "to_state": "initial",
                    "checkpoint_time": None,
                    "reset_type": "clean_initial_state"
                }
            }
        
    except Exception as e:
        logger.error(f"Failed to force reset to initial state for flow {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"强制重置到初始状态失败: {str(e)}")

@router.post("/{flow_id}/rollback-to-previous", response_model=schemas.SuccessResponse)
async def rollback_to_previous_state(
    flow_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    回退到上一个稳定的checkpoint状态（真正的checkpoint回退，不是手动构造状态）
    """
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态信息（用于日志记录）
        current_state_snapshot = await sas_app.aget_state(config)
        if not current_state_snapshot:
            return {"success": False, "message": "无法获取当前状态"}
        
        current_dialog_state = get_checkpoint_values(current_state_snapshot).get('dialog_state')
        logger.info(f"Current state for flow {flow_id}: {current_dialog_state}")
        
        # 获取checkpoint历史（按时间倒序）
        checkpoint_history = []
        async for checkpoint_tuple in sas_app.aget_state_history(config):
            if hasattr(checkpoint_tuple, 'checkpoint') and checkpoint_tuple.checkpoint:
                checkpoint_history.append(checkpoint_tuple)
        
        if len(checkpoint_history) < 2:
            return {"success": False, "message": "没有找到可以回退的历史checkpoint"}
        
        # 定义稳定状态列表，用于查找合适的回退目标
        stable_states = [
            'initial',
            'sas_step1_tasks_generated',
            'sas_awaiting_task_list_review',          # 任务列表审查状态
            'sas_step2_module_steps_generated_for_review',
            'sas_awaiting_module_steps_review',       # 模块步骤审查状态（用户点击承认按钮的状态）
            'sas_xml_generation_approved',            # XML生成承认后的状态
            'sas_awaiting_task_list_revision_input',  # 任务列表修订输入状态
            'sas_awaiting_module_steps_revision_input' # 模块步骤修订输入状态
        ]
        
        # 查找最近的稳定checkpoint（跳过当前checkpoint，从第二个开始）
        target_checkpoint = None
        for i in range(1, len(checkpoint_history)):
            checkpoint_tuple = checkpoint_history[i]
            checkpoint_values = checkpoint_tuple.checkpoint.get('channel_values', {})
            dialog_state = checkpoint_values.get('dialog_state')
            is_error = checkpoint_values.get('is_error', False)
            
            logger.info(f"Checking checkpoint {i}: dialog_state={dialog_state}, is_error={is_error}")
            
            # 寻找一个稳定且无错误的checkpoint
            if dialog_state in stable_states and not is_error:
                target_checkpoint = checkpoint_tuple
                logger.info(f"Found suitable rollback target: {dialog_state} at {checkpoint_tuple.config}")
                break
        
        if not target_checkpoint:
            return {"success": False, "message": "没有找到合适的稳定checkpoint进行回退"}
        
        # 获取目标checkpoint的完整状态
        target_config = target_checkpoint.config
        target_checkpoint_data = await sas_app.aget_state(target_config)
        
        if not target_checkpoint_data:
            return {"success": False, "message": "无法获取目标checkpoint的状态数据"}
        
        # 使用目标checkpoint的完整状态，但更新一些必要的字段
        target_state = dict(get_checkpoint_values(target_checkpoint_data))
        target_state['current_step_description'] = f"Rolled back to {target_state.get('dialog_state')} checkpoint"
        target_state['user_input'] = None  # 清理用户输入，避免重复处理
        
        # 如果回退到审查状态，确保用户需要重新确认
        if target_state.get('dialog_state') == 'sas_awaiting_module_steps_review':
            target_state['module_steps_accepted'] = False
            target_state['completion_status'] = 'needs_clarification'
        elif target_state.get('dialog_state') == 'sas_awaiting_task_list_review':
            target_state['task_list_accepted'] = False
            target_state['module_steps_accepted'] = False
            target_state['completion_status'] = 'needs_clarification'
        
        # 更新到目标checkpoint状态
        await sas_app.aupdate_state(config, target_state)
        
        target_dialog_state = target_state.get('dialog_state')
        logger.info(f"Successfully rolled back flow {flow_id} from {current_dialog_state} to {target_dialog_state}")
        
        return {
            "success": True, 
            "message": f"已回退到checkpoint状态: {target_dialog_state}",
            "rollback_details": {
                "from_state": current_dialog_state,
                "to_state": target_dialog_state,
                "checkpoint_time": target_config.get('configurable', {}).get('thread_ts')
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to rollback to previous checkpoint for flow {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"checkpoint回退失败: {str(e)}") 