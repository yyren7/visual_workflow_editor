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
import re
# 移除了urlparse import，不再需要直接解析数据库URL

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

# --- 移除了直接数据库连接函数，改用LangGraph API ---
# 注意：不再需要直接操作数据库，LangGraph的checkpointer会处理所有持久化操作

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

# --- 新增: 专门用于flow_id参数的权限验证依赖 ---
async def verify_flow_access_by_flow_id(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(utils.get_current_user)
):
    """
    一个依赖项，用于验证当前登录用户是否有权访问此流程(通过flow_id参数)。
    专门为使用flow_id作为路径参数的端点设计。
    如果用户未登录或无权访问，将引发HTTPException。
    """
    utils.verify_flow_ownership(flow_id=flow_id, current_user=current_user, db=db)
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
    获取checkpoint的values，StateSnapshot对象有.values属性
    """
    if not checkpoint_obj:
        return {}
    
    try:
        # 根据LangGraph文档，StateSnapshot对象有.values属性
        if hasattr(checkpoint_obj, 'values'):
            values = checkpoint_obj.values
            return values if isinstance(values, dict) else {}
        else:
            logger.warning(f"Checkpoint object missing .values attribute: {type(checkpoint_obj)}")
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
            'completion_status',
            'current_user_request',
            'revision_iteration',
            'clarification_question',
            'generated_node_xmls',
            'final_flow_xml_content'
        ]
        
        # 检查是否有重要字段存在，决定是否需要前端更新
        has_important_fields = any(field in final_state for field in important_fields)
        
        if has_important_fields:
            # 提取前端需要的状态数据
            frontend_agent_state = {}
            update_types = []
            
            # 🔧 修复：序列化 Pydantic 模型对象以避免 JSON 序列化错误
            def serialize_pydantic_objects(obj):
                """安全地序列化 Pydantic 模型对象"""
                if hasattr(obj, 'model_dump'):
                    return obj.model_dump()
                elif hasattr(obj, 'dict'):
                    return obj.dict()
                elif isinstance(obj, list):
                    return [serialize_pydantic_objects(item) for item in obj]
                elif isinstance(obj, dict):
                    return {k: serialize_pydantic_objects(v) for k, v in obj.items()}
                else:
                    return obj
            
            for field in important_fields:
                if field in final_state:
                    # 序列化可能包含 Pydantic 对象的字段
                    field_value = final_state[field]
                    if field in ['sas_step1_generated_tasks', 'sas_step2_generated_task_details', 'sas_step2_module_steps']:
                        field_value = serialize_pydantic_objects(field_value)
                    
                    frontend_agent_state[field] = field_value
                    update_types.append(field)
                    
                    if field in ['dialog_state', 'sas_step1_generated_tasks', 'completion_status']:
                        logger.info(f"[SAS_FRONTEND_UPDATE] 包含重要字段: {field} = {field_value}")
            
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
    flow_id: str = '',
    config: Optional[Dict[str, Any]] = None  # 添加config参数
):
    """
    Process SAS LangGraph execution and broadcast SSE events via global broadcaster
    """
    logger.info(f"[SAS Chat {chat_id}] Background task started. Input: {message_content[:100]}...")
    is_error = False
    error_data = {}
    final_state = None

    try:
        # 如果没有提供外部config，则为astream_events创建一个
        if config is None:
            config = {"configurable": {"thread_id": chat_id}}
        else:
            # 确保即使提供了config，thread_id也已设置
            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["thread_id"] = chat_id
            
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
                
                # 🔧 添加详细的状态日志，帮助诊断问题
                tasks_data = current_persistent_state.get("sas_step1_generated_tasks")
                tasks_count = len(tasks_data) if tasks_data else 0
                logger.info(f"[SAS Chat {chat_id}] 获取到持久化状态:")
                logger.info(f"  - dialog_state: {current_persistent_state.get('dialog_state')}")
                logger.info(f"  - task_list_accepted: {current_persistent_state.get('task_list_accepted', False)}")
                logger.info(f"  - module_steps_accepted: {current_persistent_state.get('module_steps_accepted', False)}")
                logger.info(f"  - sas_step1_generated_tasks count: {tasks_count}")
                logger.info(f"  - revision_iteration: {current_persistent_state.get('revision_iteration', 0)}")
                
                # 🔧 如果任务列表存在，记录任务名称以便跟踪
                if tasks_data:
                    task_names = [task.get('name', 'unnamed') for task in tasks_data if isinstance(task, dict)]
                    logger.info(f"  - Task names: {task_names[:5]}{'...' if len(task_names) > 5 else ''}")
            else:
                logger.warning(f"[SAS Chat {chat_id}] 未找到现有的checkpoint状态")
        except Exception as state_get_error:
            logger.warning(f"[SAS Chat {chat_id}] 获取持久化状态失败，将使用默认值: {state_get_error}")
        
        # 🔧 根据当前持久化状态设置初始值，避免不正确的重置
        # 特别注意：对于特定的消息类型，可能需要保留更多的状态
        preserved_tasks = current_persistent_state.get("sas_step1_generated_tasks", [])
        
        # 🔧 删除了关键字批准逻辑 - 只有前端绿色按钮可以触发批准
        # 所有用户输入都将作为普通输入处理，不再进行关键字匹配批准
        
        graph_input = {
            "dialog_state": "initial",
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
        
        # 🔧 记录即将使用的graph_input状态
        final_tasks_count = len(graph_input["sas_step1_generated_tasks"]) if graph_input["sas_step1_generated_tasks"] else 0
        logger.info(f"[SAS Chat {chat_id}] 即将执行graph，最终任务数量: {final_tasks_count}")
        if graph_input["sas_step1_generated_tasks"]:
            final_task_names = [task.get('name', 'unnamed') for task in graph_input["sas_step1_generated_tasks"] if isinstance(task, dict)]
            logger.info(f"[SAS Chat {chat_id}] 最终任务名称: {final_task_names[:5]}{'...' if len(final_task_names) > 5 else ''}")

        # 🔧 只保留特殊的前端按钮触发消息处理
        if message_content == "start_review":
            # 🔧 新增：处理"开始审核"指令，专门用于从生成完成状态进入审核状态
            current_dialog_state = current_persistent_state.get('dialog_state')
            
            logger.info(f"[SAS Chat {chat_id}] 收到start_review指令，当前状态: {current_dialog_state}")
            
            if current_dialog_state == 'sas_step2_module_steps_generated_for_review':
                # 从模块步骤生成完成状态进入审核状态
                # 不改变dialog_state，让review_and_refine_node处理转换到审核状态
                graph_input["current_step_description"] = "Starting module steps review process..."
                logger.info(f"[SAS Chat {chat_id}] start_review指令将触发模块步骤审核流程")
            else:
                logger.warning(f"[SAS Chat {chat_id}] 收到start_review但当前状态不支持: {current_dialog_state}")
        
        # 🔧 修复：前端绿色按钮专用批准逻辑（使用正确的状态）
        elif message_content == "FRONTEND_APPROVE_TASKS":
            current_dialog_state = current_persistent_state.get('dialog_state')
            if current_dialog_state == 'sas_awaiting_task_list_review':
                graph_input["task_list_accepted"] = True
                graph_input["user_input"] = None # Clear input to prevent re-processing
                graph_input["dialog_state"] = current_dialog_state # Keep state for routing
                logger.info(f"[SAS Chat {chat_id}] Frontend approved task list.")
            else:
                logger.warning(f"[SAS Chat {chat_id}] Frontend attempted to approve tasks but state was incorrect: {current_dialog_state}")
        
        elif message_content == "FRONTEND_APPROVE_MODULE_STEPS":
            current_dialog_state = current_persistent_state.get('dialog_state')
            if current_dialog_state == 'sas_awaiting_module_steps_review':
                graph_input["module_steps_accepted"] = True
                graph_input["user_input"] = None # Clear input
                graph_input["dialog_state"] = current_dialog_state # Keep state for routing
                logger.info(f"[SAS Chat {chat_id}] Frontend approved module steps.")
            else:
                logger.warning(f"[SAS Chat {chat_id}] Frontend attempted to approve module steps but state was incorrect: {current_dialog_state}")
        
        # 🔧 新增：蓝色按钮修改意见逻辑 - 重置批准状态
        elif message_content.startswith("FRONTEND_FEEDBACK:"):
            current_dialog_state = current_persistent_state.get('dialog_state')
            feedback_content = message_content.replace("FRONTEND_FEEDBACK:", "").strip()
            graph_input["current_user_request"] = feedback_content # Update the basis for generation

            if current_dialog_state == 'sas_awaiting_task_list_review':
                graph_input["task_list_accepted"] = False
                graph_input["module_steps_accepted"] = False
                graph_input["dialog_state"] = "user_input_to_task_list"
                logger.info(f"[SAS Chat {chat_id}] Task list feedback received. Resetting approvals and rerouting to task generation.")
            elif current_dialog_state == 'sas_awaiting_module_steps_review':
                graph_input["task_list_accepted"] = True
                graph_input["module_steps_accepted"] = False
                graph_input["dialog_state"] = "task_list_to_module_steps"
                logger.info(f"[SAS Chat {chat_id}] Module steps feedback received. Resetting module approval and rerouting to module step generation.")
            else:
                logger.info(f"[SAS Chat {chat_id}] General feedback received.")
        
        # 🔧 所有其他用户输入都作为普通输入处理，不进行任何自动批准
        else:
            logger.info(f"[SAS Chat {chat_id}] 用户输入作为普通消息处理，无自动批准")

        # 从外部传入的config中获取output_dir_path
        output_dir_path = config.get("output_dir_path")
        if output_dir_path:
            logger.info(f"[SAS Chat {chat_id}] Using output directory from config: {output_dir_path}")
            # 将其放入graph_input的config中，以便被initialize_state_node使用
            if "config" not in graph_input:
                graph_input["config"] = {}
            graph_input["config"]["OUTPUT_DIR_PATH"] = output_dir_path

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
                if run_name in ["__graph__", "sas_user_input_to_task_list", "sas_review_and_refine", "sas_task_list_to_module_steps"] or "sas" in run_name.lower():
                    if isinstance(outputs_from_chain, dict):
                        # 首先检查是否有错误状态
                        if outputs_from_chain.get("is_error", False) or outputs_from_chain.get("dialog_state") == "error" or outputs_from_chain.get("completion_status") == "error":
                            has_error_state = True
                            error_message = outputs_from_chain.get("error_message", "Unknown error occurred in SAS processing")
                            logger.error(f"[SAS Chat {chat_id}] 🚨 检测到节点错误状态: {error_message}")
                            
                            # 立即发送错误事件到前端
                            error_data = {
                                "message": error_message, 
                                "stage": f"sas_node_error_in_{run_name}",
                                "dialog_state": outputs_from_chain.get("dialog_state"),
                                "completion_status": outputs_from_chain.get("completion_status")
                            }
                            await event_broadcaster.broadcast_event(chat_id, {"type": "error", "data": error_data})
                            is_error = True
                            
                        important_keys = [
                            'sas_step1_generated_tasks',
                            'dialog_state',
                            'completion_status',
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
                                            "completion_status": final_state.get("completion_status")
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
            
            # 🔧 修复：从检查点获取最新状态，而不是使用可能过时的 final_state
            latest_state = None
            try:
                config = {"configurable": {"thread_id": chat_id}}
                current_checkpoint = await sas_app.aget_state(config)
                if current_checkpoint:
                    latest_state = get_checkpoint_values(current_checkpoint)
                    logger.info(f"[SAS Chat {chat_id}] 🔧 获取最新检查点状态，dialog_state: {latest_state.get('dialog_state') if latest_state else 'None'}")
            except Exception as e:
                logger.warning(f"[SAS Chat {chat_id}] 获取最新检查点状态失败: {e}")
                # 如果获取失败，回退到使用 final_state
                latest_state = final_state
            
            # 不再发送stream_end事件，保持SSE连接开启
            # logger.info(f"[SAS Chat {chat_id}] Broadcasting stream_end event.")
            # await event_broadcaster.broadcast_event(chat_id, {"type": "stream_end", "data": {"chat_id": chat_id}})
            # logger.info(f"[SAS Chat {chat_id}] Stream end event broadcast.")
            
            # 发送处理完成事件，但保持连接，并包含最终状态
            logger.info(f"[SAS Chat {chat_id}] Broadcasting processing_complete event (keeping connection alive).")
            
            # 🔧 构建 processing_complete 事件数据
            event_data = {
                "type": "processing_complete",
                "data": {
                    "chat_id": chat_id,
                    "message": "SAS processing completed, connection remains open for future events"
                }
            }
            
            # 如果有最终状态，包含在事件中（优先使用最新的检查点状态）
            state_to_send = latest_state if latest_state else final_state
            if state_to_send and isinstance(state_to_send, dict):
                # 🔧 修复：序列化 Pydantic 模型对象以避免 JSON 序列化错误
                def serialize_pydantic_objects(obj):
                    """安全地序列化 Pydantic 模型对象"""
                    if hasattr(obj, 'model_dump'):
                        return obj.model_dump()
                    elif hasattr(obj, 'dict'):
                        return obj.dict()
                    elif isinstance(obj, list):
                        return [serialize_pydantic_objects(item) for item in obj]
                    elif isinstance(obj, dict):
                        return {k: serialize_pydantic_objects(v) for k, v in obj.items()}
                    else:
                        return obj
                
                # 序列化 sas_step1_generated_tasks 中的 TaskDefinition 对象
                sas_step1_tasks = state_to_send.get("sas_step1_generated_tasks")
                if sas_step1_tasks:
                    sas_step1_tasks = serialize_pydantic_objects(sas_step1_tasks)
                
                event_data["data"]["final_state"] = {
                    "dialog_state": state_to_send.get("dialog_state"),
                    "sas_step1_generated_tasks": sas_step1_tasks,
                    "task_list_accepted": state_to_send.get("task_list_accepted"),
                    "module_steps_accepted": state_to_send.get("module_steps_accepted"),
                    "completion_status": state_to_send.get("completion_status"),
                    "clarification_question": state_to_send.get("clarification_question")
                }
                logger.info(f"[SAS Chat {chat_id}] Including final state in processing_complete: {state_to_send.get('dialog_state')}")
            
            await event_broadcaster.broadcast_event(chat_id, event_data)
            
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
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer), # 直接注入真正的Checkpointer
    user: schemas.User = Depends(verify_flow_access)
):
    """
    Updates the state of a SAS LangGraph flow without triggering further execution.
    This is a 'write-only' operation used for UI-driven state saves.
    """
    try:
        state_update_payload = await request.json()
        
        # 最终修复：确保 config 字典中包含 'checkpoint_ns'
        config = {
            "configurable": {
                "thread_id": chat_id,
                "checkpoint_ns": ""  # 为 aput 方法提供必需的键
            }
        }

        # 方案核心：为 checkpointer.aput() 提供所有必需的参数
        # 1. 获取当前最新状态的完整快照元组
        current_checkpoint_tuple = await checkpointer.aget_tuple(config)
        if not current_checkpoint_tuple:
            raise HTTPException(status_code=404, detail=f"Flow with chat_id {chat_id} not found.")

        current_checkpoint = current_checkpoint_tuple.checkpoint
        current_metadata = current_checkpoint_tuple.metadata
        
        # 2. 将前端的局部更新合并到完整状态的 'values' 中
        updated_values = {**current_checkpoint['channel_values'], **state_update_payload}

        # 3. 构造一个新的、完整的检查点 (Checkpoint)
        new_checkpoint = {
            **current_checkpoint,
            "channel_values": updated_values
        }

        # 4. 构造 aput 需要的 metadata 和 new_versions 参数
        #    我们将这次写入明确标记为一次 'update'
        updated_metadata = {**current_metadata, "source": "update"}
        
        #    对于 new_versions，我们假设这次手动更新不改变版本逻辑，
        #    因此直接复用当前的 channel_versions。
        #    这是最安全的做法，因为它确保了下次图执行时，版本依赖依然正确。
        current_versions = current_checkpoint['channel_versions']

        # 5. 调用 checkpointer.aput，并传入所有四个必需的参数
        updated_config = await checkpointer.aput(
            config, 
            new_checkpoint, 
            updated_metadata,
            current_versions
        )

        logger.info(f"SAS update-state for thread {chat_id}: {len(str(state_update_payload))} bytes updated via checkpointer.aput.")
        logger.debug(f"New checkpoint config: {updated_config}")
        
        return updated_config

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body.")
    except Exception as e:
        logger.error(f"Error in /sas/{chat_id}/update-state: {e}", exc_info=True)
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
                    
                logger.debug(f"Attempt {attempt + 1}: No checkpoint found for thread {chat_id}, retrying...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    
            except Exception as retry_error:
                logger.warning(f"Attempt {attempt + 1} failed for thread {chat_id}: {retry_error}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # 记录最终失败的详细信息
                    logger.error(f"Failed to get state for thread {chat_id} after {max_retries} attempts: {retry_error}")
                    raise retry_error
        
        logger.debug(f"Current checkpoint type: {type(current_checkpoint)}")
        logger.debug(f"Current checkpoint exists: {current_checkpoint is not None}")
        
        if current_checkpoint:
            # 使用辅助函数安全地获取values
            try:
                checkpoint_values = get_checkpoint_values(current_checkpoint)
                logger.debug(f"Successfully got checkpoint values: {bool(checkpoint_values)}")
                
                if checkpoint_values:
                    dialog_state = checkpoint_values.get('dialog_state')
                    tasks = checkpoint_values.get('sas_step1_generated_tasks')
                    current_user_request = checkpoint_values.get('current_user_request')
                    
                    logger.debug(f"Dialog state: {dialog_state}")
                    logger.debug(f"Tasks count: {len(tasks) if tasks else 0}")
                    logger.debug(f"Has user request: {bool(current_user_request)}")
                    
                    if tasks:
                        logger.info(f"Found {len(tasks)} tasks for thread {chat_id}")
                    else:
                        logger.info(f"No tasks found for thread {chat_id}")
                else:
                    logger.warning(f"Failed to get checkpoint values for thread {chat_id}")
            except Exception as values_error:
                logger.error(f"Error getting checkpoint values for thread {chat_id}: {values_error}")
                # 即使获取values失败，仍然返回checkpoint，让前端处理
        else:
            logger.warning(f"No checkpoint found for thread {chat_id} after {max_retries} attempts")
        
        if not current_checkpoint:
            # 返回一个默认的空状态而不是404错误，避免前端处理问题
            logger.info(f"Returning default empty state for thread {chat_id}")
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
    user: schemas.User = Depends(verify_flow_access_by_flow_id)
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
        
        # Check if the state is considered stuck
        stuck_states = [
            'generation_failed',
            'sas_generating_individual_xmls',
            'parameter_mapping',
            'merge_xml',
            'error'
        ]
        
        if current_dialog_state not in stuck_states and not is_error_state:
            return {"success": True, "message": "Current state does not require a reset."}
        
        logger.info(f"Resetting stuck state for flow {flow_id} from: {current_dialog_state}")
        
        # 获取checkpoint历史
        checkpoint_history = []
        try:
            async for checkpoint_tuple in sas_app.aget_state_history(config):
                if checkpoint_tuple:  # 简化检查，StateSnapshot对象应该总是有效
                    checkpoint_history.append(checkpoint_tuple)
        except Exception as history_error:
            logger.error(f"获取checkpoint历史失败: {history_error}")
            # 如果无法获取历史，创建干净的初始状态
            checkpoint_history = []
        
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
                "message": f"已重置到干净的初始状态 (从 {current_dialog_state})"
            }
        
        # Define stable states with priority for rollback
        stable_states_priority = [
            'sas_awaiting_module_steps_review',
            'sas_awaiting_task_list_review',
            'initial'
        ]
        
        # Find the most recent stable checkpoint
        target_checkpoint = None
        target_priority = float('inf')
        
        for i in range(1, len(checkpoint_history)):
            checkpoint_tuple = checkpoint_history[i]
            
            # 正确获取checkpoint的状态数据 - 需要通过config重新获取完整状态
            try:
                checkpoint_config = checkpoint_tuple.config
                checkpoint_data = await sas_app.aget_state(checkpoint_config)
                if checkpoint_data:
                    checkpoint_values = get_checkpoint_values(checkpoint_data)
                    dialog_state = checkpoint_values.get('dialog_state')
                    is_error = checkpoint_values.get('is_error', False)
                    
                    # 寻找一个稳定且无错误的checkpoint
                    if dialog_state and dialog_state in stable_states_priority and not is_error:
                        priority = stable_states_priority.index(dialog_state)
                        if priority < target_priority:
                            target_checkpoint = checkpoint_tuple
                            target_priority = priority
                            logger.info(f"Found better rollback target: {dialog_state} (priority {priority})")
                            
                            # 如果找到了最高优先级的状态，就停止搜索
                            if priority == 0:
                                break
                    else:
                        logger.debug(f"Checkpoint {i} not suitable: state={dialog_state}, error={is_error}")
                else:
                    logger.warning(f"Could not get state data for checkpoint {i}")
            except Exception as e:
                logger.warning(f"Error checking checkpoint {i}: {e}")
                continue
        
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
                "message": f"已重置到干净的初始状态 (从 {current_dialog_state})"
            }
        
        # 获取目标checkpoint的完整状态数据
        target_config = target_checkpoint.config
        target_checkpoint_data = await sas_app.aget_state(target_config)
        
        if not target_checkpoint_data:
            raise Exception("无法获取目标checkpoint的状态数据")
        
        target_state = dict(get_checkpoint_values(target_checkpoint_data))
        target_dialog_state = target_state.get('dialog_state')
        
        # 准备回退状态
        target_state['current_step_description'] = f"Reset to {target_dialog_state} checkpoint from stuck state"
        target_state['user_input'] = None
        target_state['is_error'] = False
        target_state['error_message'] = None
        
        # 如果回退到审查状态，确保用户需要重新确认
        if target_dialog_state == 'sas_awaiting_module_steps_review':
            target_state['module_steps_accepted'] = False
            target_state['completion_status'] = 'needs_clarification'
        elif target_dialog_state == 'sas_awaiting_task_list_review':
            target_state['task_list_accepted'] = False
            target_state['module_steps_accepted'] = False
            target_state['completion_status'] = 'needs_clarification'
        
        # 使用LangGraph API安全地更新状态
        await sas_app.aupdate_state(config, target_state)
        
        target_dialog_state = target_state.get('dialog_state')
        logger.info(f"Successfully reset stuck state for flow {flow_id} from {current_dialog_state} to {target_dialog_state}")
        
        return {
            "success": True, 
            "message": f"已从卡住状态重置到: {target_dialog_state} (从 {current_dialog_state})"
        }
            
    except Exception as e:
        logger.error(f"Failed to reset stuck state for flow {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重置卡住状态失败: {str(e)}")



@router.post("/{flow_id}/force-reset-state", response_model=schemas.SuccessResponse)
async def force_reset_state(
    flow_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access_by_flow_id)
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
        try:
            async for checkpoint_tuple in sas_app.aget_state_history(config):
                if checkpoint_tuple:  # 简化检查
                    checkpoint_history.append(checkpoint_tuple)
        except Exception as history_error:
            logger.warning(f"Error getting checkpoint history for flow {flow_id}: {history_error}")
            # 如果无法获取历史，直接创建干净的初始状态
            checkpoint_history = []
        
        # 查找最早的initial checkpoint（从历史列表的末尾开始查找）
        initial_checkpoint = None
        for checkpoint_tuple in reversed(checkpoint_history):
            try:
                # 正确获取checkpoint的状态数据 - 需要通过config重新获取完整状态
                checkpoint_config = checkpoint_tuple.config
                checkpoint_data = await sas_app.aget_state(checkpoint_config)
                if checkpoint_data:
                    checkpoint_values = get_checkpoint_values(checkpoint_data)
                    dialog_state = checkpoint_values.get('dialog_state')
                    
                    if dialog_state == 'initial':
                        initial_checkpoint = checkpoint_tuple
                        logger.info(f"Found initial checkpoint with state: {dialog_state}")
                        break
            except Exception as checkpoint_error:
                logger.warning(f"Error processing checkpoint for flow {flow_id}: {checkpoint_error}")
                continue
        
        if initial_checkpoint:
            # 找到了initial checkpoint，回退到该状态
            try:
                # 获取initial checkpoint的完整状态数据
                target_config = initial_checkpoint.config
                target_checkpoint_data = await sas_app.aget_state(target_config)
                
                if not target_checkpoint_data:
                    raise Exception("无法获取initial checkpoint的状态数据")
                
                initial_state = dict(get_checkpoint_values(target_checkpoint_data))
                
                # 准备初始状态
                initial_state['current_step_description'] = 'Reset to initial checkpoint state'
                initial_state['user_input'] = None  # 清理用户输入
                initial_state['is_error'] = False   # 清除错误状态
                initial_state['error_message'] = None
                
                # 使用LangGraph API安全地更新状态
                await sas_app.aupdate_state(config, initial_state)
                
                logger.info(f"Successfully reset flow {flow_id} to initial checkpoint from {current_dialog_state}")
                return {
                    "success": True, 
                    "message": f"已重置到initial checkpoint状态 (从 {current_dialog_state})"
                }
            except Exception as rollback_error:
                logger.error(f"Failed to rollback to initial checkpoint for flow {flow_id}: {rollback_error}")
                # 如果回退失败，尝试创建干净的初始状态
                logger.warning(f"Rollback failed, creating fresh initial state for flow {flow_id}")
        
        # 没有找到initial checkpoint 或者 回退失败，创建一个真正干净的初始状态
        logger.warning(f"No initial checkpoint found or rollback failed for flow {flow_id}, creating fresh initial state")
        
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
            "message": f"已重置到干净的初始状态 (从 {current_dialog_state})"
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"Failed to force reset to initial state for flow {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"强制重置到初始状态失败: {str(e)}")

@router.post("/{flow_id}/rollback-to-previous", response_model=schemas.SuccessResponse)
async def rollback_to_previous_state(
    flow_id: str,
    sas_app = Depends(get_sas_app),
    user: schemas.User = Depends(verify_flow_access_by_flow_id)
):
    """
    回退到上一个稳定的checkpoint状态（真正的checkpoint回退，不是手动构造状态）
    """
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态信息（用于日志记录）
        current_state_snapshot = await sas_app.aget_state(config)
        if not current_state_snapshot:
            raise HTTPException(status_code=404, detail="无法获取当前状态，流程可能不存在或未初始化")
        
        current_dialog_state = get_checkpoint_values(current_state_snapshot).get('dialog_state')
        logger.info(f"Current state for flow {flow_id}: {current_dialog_state}")
        
        # 获取checkpoint历史（按时间倒序）
        checkpoint_history = []
        try:
            async for checkpoint_tuple in sas_app.aget_state_history(config):
                if checkpoint_tuple:  # 简化检查
                    checkpoint_history.append(checkpoint_tuple)
        except Exception as history_error:
            logger.error(f"获取checkpoint历史失败: {history_error}")
            raise HTTPException(status_code=500, detail="获取历史状态失败")
        
        if len(checkpoint_history) < 2:
            raise HTTPException(status_code=400, detail="No previous checkpoint available to roll back to.")
        
        # Define stable states for rollback targets
        stable_states = [
            'initial',
            'sas_awaiting_task_list_review',
            'sas_awaiting_module_steps_review'
        ]
        
        # Find the most recent stable checkpoint (skipping the current one)
        target_checkpoint = None
        target_checkpoint_index = None
        logger.info(f"Searching through {len(checkpoint_history)} checkpoints for stable state")
        
        for i in range(1, len(checkpoint_history)):
            checkpoint_tuple = checkpoint_history[i]
            
            # 正确获取checkpoint的状态数据
            try:
                checkpoint_config = checkpoint_tuple.config
                checkpoint_data = await sas_app.aget_state(checkpoint_config)
                if checkpoint_data:
                    checkpoint_values = get_checkpoint_values(checkpoint_data)
                    dialog_state = checkpoint_values.get('dialog_state')
                    is_error = checkpoint_values.get('is_error', False)
                    
                    logger.debug(f"Checking checkpoint {i}: dialog_state={dialog_state}, is_error={is_error}")
                    
                    # 寻找一个稳定且无错误的checkpoint
                    if dialog_state in stable_states and not is_error:
                        target_checkpoint = checkpoint_tuple
                        target_checkpoint_index = i
                        logger.info(f"Found suitable rollback target: {dialog_state} at checkpoint {i}")
                        break
                else:
                    logger.warning(f"Could not get state data for checkpoint {i}")
            except Exception as e:
                logger.warning(f"Error checking checkpoint {i}: {e}")
                continue
        
        logger.info(f"Target checkpoint found: {target_checkpoint is not None}")
        
        if not target_checkpoint or target_checkpoint_index is None:
            # 如果找不到任何稳定状态，返回错误
            logger.warning(f"No stable checkpoint found for flow {flow_id}")
            raise HTTPException(status_code=400, detail="没有找到可以回退的稳定checkpoint状态")
        
        # 安全的回滚：使用LangGraph API来创建新的checkpoint，而不是删除旧的
        target_config = target_checkpoint.config
        
        logger.info(f"Rolling back to checkpoint at index {target_checkpoint_index}")
        
        try:
            # 获取目标checkpoint的状态数据
            target_checkpoint_data = await sas_app.aget_state(target_config)
            if not target_checkpoint_data:
                raise Exception("无法获取目标checkpoint的状态数据")
            
            target_state = get_checkpoint_values(target_checkpoint_data)
            target_dialog_state = target_state.get('dialog_state')
            
            # 使用LangGraph API安全地更新状态，创建新的checkpoint
            # 这比直接删除数据库记录更安全，保持了LangGraph的内部一致性
            rollback_state = dict(target_state)  # 复制目标状态
            rollback_state['current_step_description'] = f"Rolled back to {target_dialog_state} checkpoint"
            rollback_state['user_input'] = None  # 清除用户输入
            rollback_state['is_error'] = False   # 清除错误状态
            rollback_state['error_message'] = None
            
            # 如果回退到审查状态，确保用户需要重新确认
            if target_dialog_state == 'sas_awaiting_module_steps_review':
                rollback_state['module_steps_accepted'] = False
                rollback_state['completion_status'] = 'needs_clarification'
            elif target_dialog_state == 'sas_awaiting_task_list_review':
                rollback_state['task_list_accepted'] = False
                rollback_state['module_steps_accepted'] = False
                rollback_state['completion_status'] = 'needs_clarification'
            
            # 使用aupdate_state创建新的checkpoint
            config = {"configurable": {"thread_id": flow_id}}
            await sas_app.aupdate_state(config, rollback_state)
            
            logger.info(f"Successfully rolled back flow {flow_id} from {current_dialog_state} to {target_dialog_state}")
            
            return {
                "success": True, 
                "message": f"已回退到checkpoint状态: {target_dialog_state} (从 {current_dialog_state}，通过创建新checkpoint实现)"
            }
            
        except Exception as rollback_error:
            logger.error(f"Failed to rollback to checkpoint: {rollback_error}")
            raise HTTPException(status_code=500, detail=f"回滚到checkpoint失败: {str(rollback_error)}")
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"Failed to rollback to previous checkpoint for flow {flow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"checkpoint回退失败: {str(e)}") 