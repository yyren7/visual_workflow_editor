from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio # 确保导入 asyncio
from datetime import datetime # <--- 修改此行
from collections import defaultdict # 导入 defaultdict
from backend.langgraphchat.context import current_flow_id_var # <--- Import context variable

from backend.app import schemas
from database.connection import get_db, get_db_context
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from backend.app.services.flow_service import FlowService
from database.models import Flow
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, AIMessageChunk

logger = logging.getLogger(__name__)

# --- 新增：用于存储活动事件流的内存队列 --- 
# Key: chat_id, Value: asyncio.Queue
# 注意：简单内存实现，不适用于多进程/多实例部署
active_chat_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
# 用于通知 GET 请求流已结束的标记
STREAM_END_SENTINEL = {"type": "stream_end", "data": {"message": "Stream finished or no stream generated."}}
# 队列最大长度，防止内存无限增长
MAX_QUEUE_SIZE = 100 
# --- 结束新增 ---

router = APIRouter(
    prefix="/chats",
    tags=["chats"],
    responses={404: {"description": "Not found"}},
)

# --- 辅助函数：将数据库消息格式转换为 Langchain 格式 ---
def _format_messages_to_langchain(messages: List[Dict]) -> List[BaseMessage]:
    """将包含 'role' 和 'content' 的字典列表转换为 Langchain BaseMessage 列表。"""
    langchain_messages = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        # 可以选择性地处理其他 role，例如 'system'
        # else:
        #     logger.warning(f"Unknown message role '{role}' encountered during formatting.")
    return langchain_messages

@router.post("/", response_model=schemas.Chat)
async def create_chat(
    chat: schemas.ChatCreate, 
    request: Request,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    创建新的聊天记录，必须登录并且只能为自己的流程图创建聊天
    """
    print(f"成功进入 create_chat 函数: {request.method} {request.url.path}")
    logger.info(f"成功进入 create_chat 函数: {request.method} {request.url.path}")

    try:
        # 验证流程图存在且属于当前用户
        logger.info(f"验证 flow ownership: {chat.flow_id}")
        verified_flow = verify_flow_ownership(chat.flow_id, current_user, db)
        logger.info(f"Flow ownership 验证通过 for flow: {verified_flow.id}")

        # 创建聊天
        logger.info(f"调用 chat_service.create_chat")
        chat_service = ChatService(db)
        db_chat = chat_service.create_chat(
            flow_id=chat.flow_id,
            name=chat.name,
            chat_data=chat.chat_data
        )
        logger.info(f"chat_service.create_chat 返回: {db_chat}")

        if not db_chat:
            logger.error("chat_service.create_chat 未成功创建聊天，引发 400")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法创建聊天"
            )

        # --- Update Flow's last_interacted_chat_id ---
        if verified_flow: # Ensure we have the flow object
            try:
                verified_flow.last_interacted_chat_id = db_chat.id
                db.commit()
                logger.info(f"更新 Flow {verified_flow.id} 的 last_interacted_chat_id 为 {db_chat.id}")
            except Exception as update_err:
                logger.error(f"更新 Flow last_interacted_chat_id 失败 (Flow: {verified_flow.id}, Chat: {db_chat.id}): {update_err}", exc_info=True)
                db.rollback() # Rollback only the failed update
        else:
             logger.warning(f"无法更新 Flow 的 last_interacted_chat_id，因为在创建聊天后未能获取 Flow 对象 (Flow ID: {chat.flow_id})")
        # --- End Update ---

        logger.info(f"成功创建聊天，返回 chat 对象 ID: {db_chat.id}")
        return db_chat
    except HTTPException as http_exc:
        logger.error(f"处理 create_chat 时发生 HTTPException: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"处理 create_chat 时发生意外错误", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建聊天时发生内部错误: {str(e)}"
        )


@router.get("/{chat_id}", response_model=schemas.Chat)
async def get_chat(
    chat_id: str, 
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取聊天记录，必须登录并且只能访问自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verify_flow_ownership(chat.flow_id, current_user, db)
    
    return chat


@router.get("/flow/{flow_id}", response_model=List[schemas.Chat])
async def get_flow_chats(
    flow_id: str, 
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取流程图的所有聊天记录，必须登录并且只能访问自己流程图的聊天
    """
    # 验证流程图属于当前用户
    verify_flow_ownership(flow_id, current_user, db)
    
    # 获取聊天列表
    chat_service = ChatService(db)
    chats = chat_service.get_chats_for_flow(flow_id, skip, limit)
    
    return chats


@router.put("/{chat_id}", response_model=schemas.Chat)
async def update_chat(
    chat_id: str,
    chat_update: schemas.ChatUpdate,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    更新聊天记录，必须登录并且只能更新自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verify_flow_ownership(chat.flow_id, current_user, db)
    
    # 更新聊天
    updated_chat = chat_service.update_chat(
        chat_id=chat_id,
        name=chat_update.name,
        chat_data=chat_update.chat_data
    )
    
    if not updated_chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="更新聊天失败"
        )
    
    return updated_chat


@router.put("/{chat_id}/messages/{message_timestamp}", status_code=status.HTTP_202_ACCEPTED)
async def edit_user_message(
    chat_id: str,
    message_timestamp: str, 
    edit_data: schemas.ChatMessageEdit, 
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    编辑用户消息, 删除此消息之后的所有消息, 并以新内容重新生成用户消息。
    然后像新消息一样触发 LangGraph 工作流。
    必须登录并且只能操作自己流程图的聊天。
    立即返回 202 Accepted，客户端需要随后连接 GET /{chat_id}/events 获取事件。
    """
    logger.info(f"Attempting to edit message {message_timestamp} in chat {chat_id} and trigger workflow.")
    chat_service = ChatService(db)
    chat_before_edit = chat_service.get_chat(chat_id)

    if not chat_before_edit:
        logger.error(f"Chat {chat_id} not found for editing message.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    verify_flow_ownership(chat_before_edit.flow_id, current_user, db)
    logger.debug(f"Ownership verified for flow {chat_before_edit.flow_id}")

    # 在调用服务层之前，先检查消息是否存在
    message_found = False
    if chat_before_edit.chat_data and "messages" in chat_before_edit.chat_data:
        messages = chat_before_edit.chat_data.get("messages", [])
        if isinstance(messages, list): # 确保 messages 是列表
            for msg in messages:
                if isinstance(msg, dict) and msg.get("timestamp") == message_timestamp and msg.get("role") == "user":
                    message_found = True
                    break
    
    if not message_found:
        logger.error(f"User message with timestamp {message_timestamp} not found in chat {chat_id} before calling service.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"要编辑的消息不存在或时间戳不匹配 (ts: {message_timestamp})"
        )

    updated_chat = chat_service.edit_user_message_and_truncate(
        chat_id=chat_id,
        message_timestamp=message_timestamp,
        new_content=edit_data.new_content
    )

    if not updated_chat:
        logger.error(f"Failed to edit message {message_timestamp} in chat {chat_id} via service.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # 改为500，因为此时更可能是内部问题
            detail="编辑消息时发生内部服务器错误"
        )
    
    logger.info(f"Successfully edited message {message_timestamp} in chat {chat_id}. DB state updated.")

    # --- 触发后台事件处理 ---
    event_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE) 
    active_chat_queues[chat_id] = event_queue
    logger.info(f"为 chat {chat_id} (after edit) 创建/设置了新的事件队列")

    # The initial_user_message_content is not strictly needed by _process_and_publish_chat_events
    # when is_edit_flow is True, as it will read the latest from DB.
    background_tasks.add_task(
        _process_and_publish_chat_events, 
        chat_id, 
        initial_user_message_content=None, # Content is already in DB
        event_queue=event_queue,
        is_edit_flow=True
    )
    logger.info(f"已为 chat {chat_id} (after edit) 启动后台事件处理任务")

    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/{chat_id}/messages")
async def add_message(
    chat_id: str,
    message: schemas.ChatAddMessage,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Response:
    """
    向聊天添加用户消息，触发后台处理流程。
    立即返回 202 Accepted，客户端需要随后连接 GET /{chat_id}/events 获取事件。
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天不存在")
    verified_flow = verify_flow_ownership(chat.flow_id, current_user, db)
    logger.info(f"Flow ownership 验证通过 for flow: {verified_flow.id} linked to chat: {chat_id}")
    if message.role != 'user':
         logger.warning(f"Received message with role '{message.role}' in add_message. Processing as user message.")
         
    event_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE) 
    active_chat_queues[chat_id] = event_queue
    logger.info(f"为 chat {chat_id} 创建/设置了新的事件队列")

    background_tasks.add_task(
        _process_and_publish_chat_events, 
        chat_id, 
        initial_user_message_content=message.content, 
        event_queue=event_queue,
        is_edit_flow=False,
        client_message_id=message.client_message_id
    )
    logger.info(f"已为 chat {chat_id} 启动后台事件处理任务 (new message, client_id: {message.client_message_id})")
    
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/{chat_id}/events")
async def get_chat_events(chat_id: str, request: Request):
    """
    用于客户端通过 EventSource 连接以接收聊天事件。
    """
    logger.info(f"收到对 chat {chat_id} 事件流的 GET 请求 from IP: {request.client.host if request.client else 'unknown'}")

    if chat_id not in active_chat_queues:
        logger.warning(f"请求 chat {chat_id} 的事件流，但队列不存在或已清理")
        # It's possible the client is trying to connect after the stream has ended and queue cleaned up.
        # Return a specific SSE event indicating this rather than a 404, so client can handle gracefully.
        async def immediate_end_stream():
            yield {
                "event": "stream_end", # Or a custom "already_closed" event type
                "data": json.dumps({"message": f"No active event stream for chat {chat_id}. It may have already finished or was never started."})
            }
            logger.info(f"Sent immediate stream_end for non-existent/cleaned queue {chat_id}")
        return EventSourceResponse(immediate_end_stream())

    event_queue = active_chat_queues[chat_id]
    logger.info(f"找到 chat {chat_id} 的事件队列，准备发送 SSE 事件")

    async def sse_event_sender():
        logger.debug(f"Starting SSE event sender for chat {chat_id}")
        client_disconnected = False
        event_data = None # Initialize event_data

        async def check_disconnect():
            nonlocal client_disconnected
            try:
                # This is a FastAPI specific way to check if client disconnected
                # It might not work perfectly for all server setups / ASGI servers
                # but is a common approach.
                await request.is_disconnected() 
                if await request.is_disconnected(): # Check again to be sure
                    client_disconnected = True
                    logger.info(f"SSE client for chat {chat_id} disconnected (checked via request.is_disconnected()).")
            except Exception as e: # Handle cases where request.is_disconnected might not be available or raises error
                logger.debug(f"Could not check client disconnect status for chat {chat_id}: {e}")

        try:
            # 发送初始的心跳/连接确认事件
            logger.debug(f"SSE sender for {chat_id}: Sending initial ping.")
            yield {
                "event": "ping",
                "data": json.dumps({"timestamp": datetime.utcnow().isoformat(), "message": "SSE connection established"})
            }

            while not client_disconnected:
                event_data = None # Reset event_data at the start of each iteration
                try:
                    # Timeout to allow disconnect check
                    logger.debug(f"[SSE {chat_id}] Waiting for event from queue...")
                    event_data = await asyncio.wait_for(event_queue.get(), timeout=1.0) 
                    logger.debug(f"[SSE {chat_id}] Got event: {str(event_data)[:100]}")
                except asyncio.TimeoutError:
                    logger.debug(f"[SSE {chat_id}] Queue get timed out. Checking disconnect.")
                    await check_disconnect()
                    if client_disconnected:
                        logger.debug(f"[SSE {chat_id}] Client disconnected after timeout. Breaking loop.")
                        break 
                    # Send ping if not disconnected
                    logger.debug(f"[SSE {chat_id}] Client still connected. Sending ping.")
                    try:
                        yield {
                            "event": "ping",
                            "data": json.dumps({"timestamp": datetime.utcnow().isoformat(), "message": "keep-alive"})
                        }
                    except Exception as ping_err:
                        logger.error(f"[SSE {chat_id}] Error sending ping: {ping_err}", exc_info=True)
                        # Potentially break or handle client disconnect here too
                        await check_disconnect()
                        if client_disconnected:
                            break
                    # Removed the 15s sleep from here, ping now acts as the periodic keep-alive
                    # The timeout on queue.get() serves as the loop beat.
                    continue # Continue to next iteration to wait for new event or another timeout
                except asyncio.CancelledError:
                    logger.info(f"SSE event sender for chat {chat_id} was cancelled (likely client disconnect or task shutdown).")
                    client_disconnected = True # Ensure flag is set
                    break # Exit loop
                except Exception as e_get:
                    logger.error(f"[SSE {chat_id}] Error getting event from queue: {e_get}", exc_info=True)
                    await check_disconnect() # Check if this error caused disconnect
                    if client_disconnected:
                        break
                    # If still connected, report error and continue or break based on severity?
                    # For now, let's try to send an error and break to be safe.
                    try:
                        yield {"event": "error", "data": json.dumps({"message": f"Error fetching event from queue: {str(e_get)}", "stage": "sse_queue_read_error"})}
                    except Exception as send_q_err:
                        logger.error(f"[SSE {chat_id}] Failed to send queue read error to client: {send_q_err}")
                    client_disconnected = True # Assume critical error, stop processing
                    break

                if event_data is None: # Should not happen if loop logic is correct, but as a safeguard
                    logger.warning(f"[SSE {chat_id}] event_data is None after queue.get() succeeded without timeout/exception. This is unexpected. Skipping.")
                    continue
                
                if event_data is STREAM_END_SENTINEL:
                    logger.info(f"[SSE {chat_id}] Received stream end sentinel. Sending final event and closing.")
                    try:
                        yield {
                            "event": STREAM_END_SENTINEL.get("type", "stream_end"),
                            "data": json.dumps(STREAM_END_SENTINEL.get("data", {}))
                        }
                        event_queue.task_done()
                    except Exception as send_final_err:
                        logger.error(f"[SSE {chat_id}] Error sending stream_end sentinel: {send_final_err}", exc_info=True)
                    client_disconnected = True # Mark as disconnected to ensure loop termination
                    break 

                if isinstance(event_data, dict) and "type" in event_data and "data" in event_data:
                    event_type = event_data.get("type", "message")
                    data_payload = event_data.get("data", {})
                    
                    if isinstance(data_payload, str): 
                        formatted_data = data_payload
                    else:
                        try:
                            formatted_data = json.dumps(data_payload)
                        except TypeError:
                            logger.error(f"序列化事件数据为 JSON 失败 (type: {event_type}, chat: {chat_id})", exc_info=True)
                            event_type = "error"
                            formatted_data = json.dumps({"message": f"Failed to serialize event data for type {event_type}", "stage": "sse_formatting"})
                    
                    logger.debug(f"SSE Sender for {chat_id}: Sending event type '{event_type}'")
                    yield {
                        "event": event_type,
                        "data": formatted_data
                    }
                else:
                    logger.warning(f"从队列中获取的事件格式不正确 (chat: {chat_id}): {event_data}")
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": "Received malformed event from queue.", "stage": "sse_formatting"})
                    }
                event_queue.task_done()
                await asyncio.sleep(0.01) # Tiny sleep to allow other tasks, prevent tight loop if queue fills fast
        
        except asyncio.CancelledError: # Typically when client disconnects and server cancels the task
            logger.info(f"SSE event sender for chat {chat_id} was explicitly cancelled (outer). Client disconnected: {client_disconnected}")
            # No need to raise, just exit gracefully
        except Exception as e_outer:
            logger.error(f"SSE event sender for chat {chat_id} encountered an UNHANDLED (outer) error: {e_outer}", exc_info=True)
            if not client_disconnected : 
                try:
                    logger.debug(f"[SSE {chat_id}] Attempting to send critical error to client: {e_outer}")
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": f"SSE sender encountered a critical error: {str(e_outer)}", "stage": "sse_sending_critical_outer"})
                    }
                except Exception as send_outer_err:
                    logger.error(f"[SSE {chat_id}] Failed to send final critical (outer) error to client: {send_outer_err}")
        finally:
            logger.info(f"SSE event sender for chat {chat_id} is cleaning up. Final client_disconnected status: {client_disconnected}")
            # Only remove queue if it was ours and task is truly ending
            # If cancelled due to disconnect, this might be called.
            # If STREAM_END_SENTINEL was processed, it should be removed there.
            # However, a robust cleanup is good.
            if chat_id in active_chat_queues and active_chat_queues[chat_id] is event_queue:
                # Check if queue is empty, if not, log warning as some events might be lost
                if not event_queue.empty():
                    logger.warning(f"Cleaning up queue for chat {chat_id} but it's not empty. {event_queue.qsize()} items remaining.")
                    # Drain the queue to prevent tasks from hanging on put() if this queue instance is reused (though defaultdict should create new)
                    while not event_queue.empty():
                        try:
                            event_queue.get_nowait()
                            event_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                
                removed_queue = active_chat_queues.pop(chat_id, None)
                if removed_queue:
                    logger.info(f"已成功从 active_chat_queues 中移除 chat {chat_id} 的队列 (Final cleanup).")
            else:
                logger.warning(f"在 SSE 清理阶段，chat {chat_id} 的队列已不在 active_chat_queues 中或不匹配当前实例，可能已被其他地方清理。")
            
    return EventSourceResponse(sse_event_sender())


@router.delete("/{chat_id}", response_model=bool)
async def delete_chat(
    chat_id: str,
    db: Session = Depends(get_db), 
    current_user: schemas.User = Depends(get_current_user)
):
    """
    删除聊天记录，必须登录并且只能删除自己流程图的聊天
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天不存在"
        )
    
    # 验证流程图属于当前用户
    verify_flow_ownership(chat.flow_id, current_user, db)
    
    # 删除聊天
    success = chat_service.delete_chat(chat_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="删除聊天失败"
        )
    
    return True 

# --- 提取出来的后台事件处理函数 ---
async def _process_and_publish_chat_events(
    chat_id: str, 
    initial_user_message_content: Optional[str], 
    event_queue: asyncio.Queue,
    is_edit_flow: bool = False,
    client_message_id: Optional[str] = None
):
    """
    后台任务：处理聊天逻辑（添加消息，调用LangGraph），并通过队列发布SSE事件。
    """
    logger.debug(f"[Chat {chat_id}] Background task started (is_edit_flow: {is_edit_flow}). Initial content (if any): {initial_user_message_content}")
    is_error = False
    error_data = {}
    final_reply_accumulator = ""
    final_state = None
    # Declare token_cv here to ensure it's in scope for the finally block
    token_cv = None 

    try:
        with get_db_context() as db_session_bg:
            logger.debug(f"[Chat {chat_id}] Acquired DB session for background task.")
            chat_service_bg = ChatService(db_session_bg)
            flow_service_bg = FlowService(db_session_bg)

            chat = chat_service_bg.get_chat(chat_id)
            if not chat:
                logger.error(f"[Chat {chat_id}] Background task could not find chat.")
                await event_queue.put({"type": "error", "data": {"message": "Chat not found.", "stage": "setup"}})
                return
            
            # If it's a new message flow (not an edit), add the user message to DB.
            # For an edit flow, edit_user_message_and_truncate already updated the DB.
            if not is_edit_flow and initial_user_message_content is not None:
                logger.debug(f"[Chat {chat_id}] Attempting to save user message to DB before agent call: {initial_user_message_content[:100]}...")
                # chat_service_bg.add_message_to_chat 返回 (Chat, str) 或 (None, None)
                saved_chat_obj, server_message_timestamp = chat_service_bg.add_message_to_chat(
                    chat_id=chat_id, 
                    role="user", 
                    content=initial_user_message_content
                )
                if saved_chat_obj and server_message_timestamp:
                    logger.debug(f"[Chat {chat_id}] User message saved to DB with server_timestamp: {server_message_timestamp}.")
                    # 如果有 client_message_id，则推送事件告知前端时间戳对应关系
                    if client_message_id:
                        await event_queue.put({
                            "type": "user_message_saved", 
                            "data": {
                                "client_message_id": client_message_id,
                                "server_message_timestamp": server_message_timestamp,
                                "content": initial_user_message_content # 可以选择性包含内容以供前端校验
                            }
                        })
                        logger.info(f"[Chat {chat_id}] Sent user_message_saved event for client_id: {client_message_id} -> server_ts: {server_message_timestamp}")
                    
                    # Re-fetch chat to ensure chat_data is up-to-date for history formatting
                    # 使用返回的 saved_chat_obj 即可，无需重新查询
                    chat = saved_chat_obj 
                else:
                    logger.error(f"[Chat {chat_id}] Failed to save user message to DB.")
                    await event_queue.put({
                        "type": "error", 
                        "data": {"message": "Failed to save user message.", "stage": "setup"}
                    })
                    return # 如果消息保存失败，则终止后续处理


            flow_id = chat.flow_id
            token_cv = current_flow_id_var.set(flow_id) 
            logger.debug(f"[Chat {chat_id}] Set current_flow_id_var to {flow_id}")

            flow = flow_service_bg.get_flow_instance(flow_id)
            if not flow:
                logger.error(f"[Chat {chat_id}] Background task could not find flow {flow_id}.")
                await event_queue.put({"type": "error", "data": {"message": f"Flow {flow_id} not found.", "stage": "setup"}})
                current_flow_id_var.reset(token_cv)
                return
            
            flow_data = flow.flow_data or {}
            logger.debug(f"[Chat {chat_id}] Flow data for context: {str(flow_data)[:200]}...")

            logger.debug(f"[Chat {chat_id}] Getting compiled LangGraph from ChatService.")
            compiled_graph = chat_service_bg.compiled_workflow_graph
            logger.debug(f"[Chat {chat_id}] Successfully got compiled LangGraph.")

            chat_history_raw = chat.chat_data.get("messages", [])
            
            # The graph input should be ALL messages from history.
            # The last message in chat_history_raw is the one the agent needs to respond to.
            graph_input_messages = _format_messages_to_langchain(chat_history_raw)
            
            # Determine the current user input based on the last message in the formatted history
            current_user_input_content = ""
            if graph_input_messages and isinstance(graph_input_messages[-1], HumanMessage):
                current_user_input_content = graph_input_messages[-1].content
            else: # Should not happen if history is well-formed and ends with a user message
                logger.warning(f"[Chat {chat_id}] Could not determine current user input from chat history. Last message: {graph_input_messages[-1] if graph_input_messages else 'No messages'}")
                # Fallback, though this indicates an issue upstream (e.g. after edit, no user message is last)
                if initial_user_message_content and not is_edit_flow: # Use initial content if new message
                     current_user_input_content = initial_user_message_content
                elif is_edit_flow and chat_history_raw: # If edit, try to get last message from raw data
                    last_raw_msg = chat_history_raw[-1]
                    if last_raw_msg.get("role") == "user":
                        current_user_input_content = last_raw_msg.get("content", "")


            graph_input = {
                "messages": graph_input_messages, # Full history including the latest user message
                "input": current_user_input_content, # The content of the latest user message
                "flow_context": flow_data.get("graphContextVars", {}),
                "current_flow_id": flow_id,
            }
            
            messages_count_val = len(graph_input["messages"])
            input_len_val = len(graph_input["input"])
            flow_id_val = graph_input["current_flow_id"]
            logger.debug(f"[Chat {chat_id}] Prepared graph input: messages_count={messages_count_val}, input_len={input_len_val}, input_content='{current_user_input_content[:50]}...', flow_id={flow_id_val}")

            logger.debug(f"[Chat {chat_id}] Invoking compiled_graph.astream_events (version='v2')...")
            
            event_include_names = None

            async for event in compiled_graph.astream_events(graph_input, version="v2", include_names=event_include_names, include_tags=None):
                event_name = event.get("event")
                event_data = event.get("data", {})
                run_name = event.get("name", "unknown_run")

                logger.info(f"[Chat {chat_id}] Received event: '{event_name}' from '{run_name}', Data keys: {list(event_data.keys())}")

                if event_name == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and isinstance(chunk, AIMessageChunk) and chunk.content:
                        token = chunk.content
                        logger.debug(f"[Chat {chat_id}] LLM Token from '{run_name}': '{token}'")
                        await event_queue.put({"type": "token", "data": token})
                        final_reply_accumulator += token 
                    elif chunk:
                        logger.debug(f"[Chat {chat_id}] Received on_chat_model_stream chunk from '{run_name}' but no content or not AIMessageChunk. Chunk: {chunk}")

                elif event_name == "on_llm_end":
                    output = event_data.get("output")
                    if output and isinstance(output, AIMessage) and output.content:
                        logger.info(f"[Chat {chat_id}] LLM End from '{run_name}'. Full output (for verification): '{output.content[:100]}...'")
                        if final_reply_accumulator != output.content and not final_reply_accumulator.endswith(output.content):
                            logger.warning(f"[Chat {chat_id}] Discrepancy between accumulated stream and on_llm_end output from '{run_name}'. Accum: '{final_reply_accumulator[:100]}...', Output: '{output.content[:100]}...'")
                    elif output:
                         logger.debug(f"[Chat {chat_id}] Received on_llm_end from '{run_name}' but no content or not AIMessage. Output: {output}")

                elif event_name == "on_tool_start":
                    tool_name = event_data.get("name")
                    tool_input = event_data.get("input")
                    logger.info(f"[Chat {chat_id}] Tool Start: '{tool_name}' from '{run_name}' with input: {str(tool_input)[:100]}...")
                    await event_queue.put({"type": "tool_start", "data": {"name": tool_name, "input": tool_input}})
                    
                elif event_name == "on_tool_end":
                    tool_name = event_data.get("name")
                    tool_output = event_data.get("output")
                    output_summary = str(tool_output)
                    if len(output_summary) > 200:
                        output_summary = output_summary[:200] + "..."
                    logger.info(f"[Chat {chat_id}] Tool End: '{tool_name}' from '{run_name}' with output: {output_summary}")
                    await event_queue.put({"type": "tool_end", "data": {"name": tool_name, "output_summary": output_summary, "full_output": tool_output}})

                elif event_name == "on_chain_end": 
                    outputs_from_chain = event_data.get("output", {})
                    logger.info(f"[Chat {chat_id}] Chain End: '{run_name}'. Output keys: {list(outputs_from_chain.keys()) if isinstance(outputs_from_chain, dict) else 'Not a dict'}")
                    if run_name == compiled_graph.name or run_name == "__graph__":
                        final_state = outputs_from_chain
                        logger.info(f"[Chat {chat_id}] Graph run '{run_name}' ended. Final state (output): {str(final_state)[:200]}...")
                        if isinstance(final_state, dict) and "messages" in final_state and isinstance(final_state["messages"], list):
                                for msg_state in reversed(final_state["messages"]):
                                    if isinstance(msg_state, AIMessage) and hasattr(msg_state, 'content') and msg_state.content:
                                        if not final_reply_accumulator:
                                            logger.info(f"[Chat {chat_id}] Using AIMessage from final graph state as fallback: {msg_state.content[:100]}...")
                                            final_reply_accumulator = msg_state.content
                                            await event_queue.put({"type": "token", "data": msg_state.content})
                                        elif final_reply_accumulator != msg_state.content:
                                            logger.warning(f"[Chat {chat_id}] Final accumulated reply ('{final_reply_accumulator[:100]}...') differs from final graph state AIMessage ('{msg_state.content[:100]}...'). Preferring accumulated.")
                                        break 
                
                elif event_name == "on_chain_error" or event_name == "on_llm_error" or event_name == "on_tool_error":
                    error_content = str(event_data.get("error", "Unknown error"))
                    logger.error(f"[Chat {chat_id}] Error event '{event_name}' from '{run_name}': {error_content}")
                    is_error = True
                    stage = f"error_in_{run_name}"
                    error_obj = event_data.get("error")
                    specific_error_message = str(error_obj) if error_obj else "Details not available"
                    
                    error_data = {"message": f"Error in {run_name}: {specific_error_message}", "stage": stage, "details": str(error_obj)}
                    await event_queue.put({"type": "error", "data": error_data})

    except Exception as e:
        is_error = True
        error_message = f"Error during LangGraph astream_events processing: {str(e)}"
        logger.error(f"[Chat {chat_id}] {error_message}", exc_info=True)
        error_data = {"message": error_message, "stage": "graph_execution"}
        try:
            await event_queue.put({"type": "error", "data": error_data})
        except asyncio.QueueFull:
            logger.error(f"[Chat {chat_id}] Failed to put error message in full queue after main exception.")
        except Exception as qe:
            logger.error(f"[Chat {chat_id}] Failed to put error message in queue after main exception: {qe}")

    finally:
        if token_cv is not None: 
            current_flow_id_var.reset(token_cv)
            logger.debug(f"[Chat {chat_id}] Reset current_flow_id context variable in finally block.")
        else:
            logger.debug(f"[Chat {chat_id}] current_flow_id_var might not have been set or was already reset, skipping reset in finally.")

        # --- 新增：处理会话结束时的默认回复 ---
        session_should_end = False
        if isinstance(final_state, dict) and final_state.get("output") == "__end__":
            session_should_end = True
        elif isinstance(final_state, str) and final_state == "__end__": # Fallback for simpler __end__ signal
            session_should_end = True
        # You might have other ways to check if the session should end based on your specific final_state structure
        # For example, if final_state has a specific key from your graph like final_state.get('next_node') == '__end__'

        if session_should_end and not final_reply_accumulator and not is_error:
            default_goodbye_message = "好的，再见！如果您还有其他问题，随时可以再次联系我。"
            logger.info(f"[Chat {chat_id}] Session is ending and no AI reply was generated. Using default goodbye: '{default_goodbye_message}'")
            final_reply_accumulator = default_goodbye_message
            try:
                # Ensure this default message is also sent as a token to the client
                await event_queue.put({"type": "token", "data": default_goodbye_message})
                logger.debug(f"[Chat {chat_id}] Sent default goodbye message to event queue.")
            except asyncio.QueueFull:
                logger.error(f"[Chat {chat_id}] Failed to put default goodbye message in full queue.")
            except Exception as qe_goodbye:
                logger.error(f"[Chat {chat_id}] Failed to put default goodbye message in queue: {qe_goodbye}")
        # --- 结束新增 ---

        if not is_error and final_reply_accumulator:
            try:
                with get_db_context() as db_session_final:
                    chat_service_final = ChatService(db_session_final)
                    logger.info(f"[Chat {chat_id}] Saving AI assistant reply to DB: {final_reply_accumulator[:100]}...")
                    chat_service_final.add_message_to_chat(
                        chat_id=chat_id,
                        role="assistant",
                        content=final_reply_accumulator
                    )
                    logger.info(f"[Chat {chat_id}] AI assistant reply saved to DB successfully.")
            except Exception as save_err:
                logger.error(f"[Chat {chat_id}] Failed to save AI reply to DB: {save_err}", exc_info=True)
        elif is_error:
            logger.warning(f"[Chat {chat_id}] Skipping AI reply save due to an error during processing. Error: {error_data}")
        else:
            logger.warning(f"[Chat {chat_id}] Skipping save because final reply was empty or null. Accumulator content: '{final_reply_accumulator}'")
        
        try:
            logger.debug(f"[Chat {chat_id}] Putting STREAM_END_SENTINEL into queue.")
            await event_queue.put(STREAM_END_SENTINEL)
            logger.debug(f"[Chat {chat_id}] Stream end sentinel sent.")
        except asyncio.QueueFull:
            logger.error(f"[Chat {chat_id}] Failed to put STREAM_END_SENTINEL in full queue.")
        except Exception as qe:
            logger.error(f"[Chat {chat_id}] Failed to put STREAM_END_SENTINEL in queue: {qe}")
        
        logger.info(f"[Chat {chat_id}] Background task (is_edit_flow: {is_edit_flow}) cleanup completed.") 