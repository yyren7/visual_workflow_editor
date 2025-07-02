from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
import time
from typing import Any, Dict, AsyncGenerator
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

router = APIRouter()

# This function was a placeholder based on your last version of the file.
# If it was meant to interact with chat history from the DB for the graph,
# the graph itself (via checkpointer) would handle that state implicitly.
# Keeping it if it serves another purpose or if you want to adapt it.
async def get_chat_history(chat_id: str):
    # In a real scenario, this would fetch from a database or memory
    print(f"Fetching history for chat_id: {chat_id} (placeholder) - Note: Graph manages its own history via checkpointer.")
    return None # Or some history object

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
    flow_id: str = None
):
    """
    Process SAS LangGraph execution and broadcast SSE events via global broadcaster
    """
    logger.info(f"[SAS Chat {chat_id}] Background task started. Input: {message_content[:100]}...")
    is_error = False
    error_data = {}
    final_state = None

    try:
        # Prepare graph input with chat_id for progress events
        graph_input = {
            "user_input": message_content,
            "current_chat_id": chat_id,  # 新增: 传递chat_id用于进度事件
            "thread_id": chat_id,       # 新增: 也作为thread_id传递
        }
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
                
                # Check if this is the main graph or SAS-related chain
                if run_name in ["__graph__", "sas_user_input_to_task_list", "sas_review_and_refine", "sas_process_to_module_steps"] or "sas" in run_name.lower():
                    if isinstance(outputs_from_chain, dict):
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
                            sync_reason = f"SAS状态更新 (run_name: {run_name}, found_keys: {found_keys})"
                            final_state = outputs_from_chain
                            logger.info(f"[SAS Chat {chat_id}] 🎯 触发同步: {sync_reason}")
                
                if should_sync and flow_id:
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
            logger.info(f"[SAS Chat {chat_id}] Broadcasting stream_end event.")
            await event_broadcaster.broadcast_event(chat_id, {"type": "stream_end", "data": {"chat_id": chat_id}})
            logger.info(f"[SAS Chat {chat_id}] Stream end event broadcast.")
        except Exception as qe:
            logger.error(f"[SAS Chat {chat_id}] Failed to broadcast stream_end: {qe}")
        
        logger.info(f"[SAS Chat {chat_id}] Background task completed.")

@router.post("/sas/{chat_id}/events")
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
            yield f"data: {json.dumps({'event': 'start', 'run_id': chat_id})}\n\n"
            
            # Get or create event queue for this chat
            event_queue = await event_broadcaster.get_or_create_queue(chat_id)
            
            while True:
                try:
                    # Wait for events from the broadcaster queue
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    
                    if event_item.get("type") == "stream_end":
                        logger.info(f"[SAS Events {chat_id}] Received stream end")
                        yield f"data: {json.dumps(event_item)}\n\n"
                        break
                    
                    # Send the event to frontend
                    yield f"data: {json.dumps(event_item)}\n\n"
                        
                except asyncio.TimeoutError:
                    logger.debug(f"[SAS Events {chat_id}] SSE timeout, sending ping")
                    yield f"data: {json.dumps({'event': 'ping', 'data': {'timestamp': time.time()}})}\n\n"
                    continue
                        
        except Exception as stream_exc:
            logger.error(f"[SAS Events {chat_id}] SSE流错误: {stream_exc}", exc_info=True)
            error_data = {"event": "error", "data": {"error": str(stream_exc)}}
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            logger.info(f"[SAS Events {chat_id}] SSE事件流结束")
            # Unregister connection when SSE ends
            event_broadcaster.unregister_connection(chat_id)
            yield f"data: {json.dumps({'event': 'end'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/sas/{chat_id}/events")
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
            yield f"data: {json.dumps({'event': 'start', 'run_id': chat_id})}\n\n"
            
            # Get or create event queue for this chat
            event_queue = await event_broadcaster.get_or_create_queue(chat_id)
            
            while True:
                try:
                    # Wait for events from the broadcaster queue
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    
                    if event_item.get("type") == "stream_end":
                        logger.info(f"[SAS Events {chat_id}] Received stream end")
                        yield f"data: {json.dumps(event_item)}\n\n"
                        break
                    
                    # Send the event to frontend
                    yield f"data: {json.dumps(event_item)}\n\n"
                        
                except asyncio.TimeoutError:
                    logger.debug(f"[SAS Events {chat_id}] SSE timeout, sending ping")
                    yield f"data: {json.dumps({'event': 'ping', 'data': {'timestamp': time.time()}})}\n\n"
                    continue
                        
        except Exception as stream_exc:
            logger.error(f"[SAS Events {chat_id}] SSE流错误: {stream_exc}", exc_info=True)
            error_data = {"event": "error", "data": {"error": str(stream_exc)}}
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            logger.info(f"[SAS Events {chat_id}] SSE事件流结束")
            # Unregister connection when SSE ends
            event_broadcaster.unregister_connection(chat_id)
            yield f"data: {json.dumps({'event': 'end'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/sas/{chat_id}/update-state")
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

@router.get("/sas/{chat_id}/state")
async def sas_get_state(
    chat_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access)
):
    """
    Retrieves the current state of a SAS LangGraph flow.
    """
    try:
        config = {"configurable": {"thread_id": chat_id}}
        current_checkpoint = await sas_app.aget_state(config)
        print(f"SAS get-state for chat_id/thread_id: {chat_id}, state: {current_checkpoint}")
        if not current_checkpoint:
            raise HTTPException(status_code=404, detail=f"State for thread_id {chat_id} not found.")
        return current_checkpoint
    except Exception as e:
        print(f"Error in /sas/{chat_id}/state: {e}")
        if "NotFoundError" in str(type(e)) or isinstance(e, HTTPException) and e.status_code == 404:
             raise HTTPException(status_code=404, detail=f"State for thread_id {chat_id} not found.")
        raise HTTPException(status_code=500, detail=str(e))

# Further considerations:
# - Authentication/Authorization (important for production)
# - Error handling and logging
# - Input and Output Pydantic models for validation and serialization

@router.get("/sas/health")
async def health_check():
    return {"status": "ok"} 