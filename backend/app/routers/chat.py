from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio # 确保导入 asyncio
import time  # 添加时间模块导入
from datetime import datetime # <--- 修改此行
from collections import defaultdict # 导入 defaultdict
from backend.langgraphchat.context import current_flow_id_var # <--- Import context variable
import uuid # 确保导入

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
# 用于追踪每个chat的SSE连接数
active_sse_connections: Dict[str, int] = defaultdict(int)
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
    支持虚拟Chat ID（使用flow_id作为chat_id）。
    立即返回 202 Accepted，客户端需要随后连接 GET /{chat_id}/events 获取事件。
    """
    chat_service = ChatService(db)
    flow_service = FlowService(db)
    
    # 首先尝试获取常规聊天
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        # 检查chat_id是否是一个有效的LangGraph虚拟Chat ID
        logger.info(f"Chat {chat_id} not found, checking if it's a virtual LangGraph chat ID...")
        
        # 从chat_id中解析flow_id、task_index、detail_index
        # 支持格式：flow_id, flow_id_task_X, flow_id_task_X_detail_Y
        flow_id = chat_id.split('_task_')[0].split('_detail_')[0]
        task_index = None
        detail_index = None
        
        # 解析task_index
        if '_task_' in chat_id:
            task_part = chat_id.split('_task_')[1]
            if '_detail_' in task_part:
                task_index = int(task_part.split('_detail_')[0])
                detail_index = int(task_part.split('_detail_')[1])
            else:
                task_index = int(task_part)
        
        # 尝试验证这是否是一个有效的flow_id
        try:
            flow = verify_flow_ownership(flow_id, current_user, db)
            if flow:
                logger.info(f"Virtual LangGraph chat detected: {chat_id} -> flow_id: {flow_id}, task: {task_index}, detail: {detail_index}")
                
                # 为虚拟聊天创建一个临时的聊天会话
                # 这样可以复用现有的聊天处理逻辑
                if task_index is not None and detail_index is not None:
                    virtual_chat_name = f"Virtual Detail Chat - {flow.name} Task {task_index + 1} Detail {detail_index + 1}"
                elif task_index is not None:
                    virtual_chat_name = f"Virtual Task Chat - {flow.name} Task {task_index + 1}"
                else:
                    virtual_chat_name = f"Virtual LangGraph Chat - {flow.name}"
                
                virtual_chat = chat_service.create_chat(
                    flow_id=flow_id,  # 使用解析出的flow_id
                    name=virtual_chat_name,
                    chat_data={
                        "messages": [], 
                        "is_virtual_langgraph_chat": True,
                        "virtual_chat_id": chat_id,  # 保存原始的虚拟chat_id
                        "task_index": task_index,
                        "detail_index": detail_index
                    }
                )
                
                if virtual_chat:
                    logger.info(f"Created virtual chat {virtual_chat.id} for LangGraph chat_id {chat_id}")
                    # 使用新创建的虚拟聊天
                    chat = virtual_chat
                    # 重要：使用实际创建的chat ID，而不是虚拟chat ID
                    actual_chat_id = virtual_chat.id
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="无法创建虚拟聊天会话"
                    )
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天不存在且不是有效的流程图ID")
        except HTTPException as he:
            # 如果验证失败，重新抛出原始的404错误
            if he.status_code == 404:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天不存在")
            else:
                raise he
        except Exception as e:
            logger.error(f"Error checking virtual LangGraph chat ID {chat_id}: {e}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天不存在")
    else:
        # 常规聊天流程
        actual_chat_id = chat_id
    
    # 验证流程图归属（常规聊天和虚拟聊天都需要）
    verified_flow = verify_flow_ownership(chat.flow_id, current_user, db)
    logger.info(f"Flow ownership 验证通过 for flow: {verified_flow.id} linked to chat: {chat.id}")
    
    if message.role != 'user':
         logger.warning(f"Received message with role '{message.role}' in add_message. Processing as user message.")
         
    # 对于虚拟聊天，我们需要使用原始的chat_id（即flow_id）作为事件队列的key
    # 这样前端就能用flow_id来监听事件
    event_queue_key = chat_id  # 使用原始请求的chat_id
    actual_processing_chat_id = chat.id  # 使用实际的chat记录ID进行处理
    
    event_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE) 
    active_chat_queues[event_queue_key] = event_queue  # 使用原始chat_id作为key
    logger.info(f"为 chat {event_queue_key} (actual: {actual_processing_chat_id}) 创建/设置了新的事件队列")

    background_tasks.add_task(
        _process_and_publish_chat_events, 
        actual_processing_chat_id,  # 传递实际的chat ID给后台任务
        initial_user_message_content=message.content, 
        event_queue=event_queue,
        is_edit_flow=False,
        client_message_id=message.client_message_id
    )
    logger.info(f"已为 chat {event_queue_key} (processing: {actual_processing_chat_id}) 启动后台事件处理任务 (new message, client_id: {message.client_message_id})")
    
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/{chat_id}/events")
async def get_chat_events(chat_id: str, request: Request):
    route_hit_id = str(uuid.uuid4())
    logger.info(f"➡️ Route /events hit for chat_id: {chat_id}, HIT_ID: {route_hit_id}, Client: {request.client.host if request.client else 'unknown'}")

    if chat_id not in active_chat_queues:
        logger.warning(f"➡️ Route /events: No active event queue for chat {chat_id} (HIT_ID: {route_hit_id}). Sending immediate end.")
        async def immediate_end_stream():
            yield {"event": "stream_end", "data": json.dumps({"message": f"No active event stream for chat {chat_id}."})}
        return EventSourceResponse(immediate_end_stream())

    event_queue = active_chat_queues[chat_id]
    logger.info(f"➡️ Route /events: Found event queue for chat {chat_id} (HIT_ID: {route_hit_id})")

    async def sse_event_generator(current_chat_id: str, req: Request, hit_id_from_route: str):
        sse_instance_id = str(uuid.uuid4())
        logger.error(f"🚀🚀🚀 SSE_GENERATOR_INSTANCE_STARTED for chat_id: {current_chat_id}, HIT_ID: {hit_id_from_route}, INSTANCE_ID: {sse_instance_id}, URL: {req.url}")

        active_sse_connections[current_chat_id] += 1
        connection_count = active_sse_connections[current_chat_id]
        logger.info(f"🔴 Running SSE event sender #{connection_count} for chat {current_chat_id} (HIT_ID: {hit_id_from_route}, Instance: {sse_instance_id})")
        
        client_disconnected = False
        
        async def check_disconnect_internal():
            nonlocal client_disconnected
            if client_disconnected:
                return True
            try:
                is_disconnected = await req.is_disconnected()
                if is_disconnected:
                    client_disconnected = True
                    logger.info(f"🔴 SSE client for chat {current_chat_id} DISCONNECTED (Instance: {sse_instance_id}, HIT_ID: {hit_id_from_route}).")
                    return True
                return False
            except Exception as e_disconnect:
                logger.warning(f"🔴 Could not check client disconnect status for chat {current_chat_id} (Instance: {sse_instance_id}, HIT_ID: {hit_id_from_route}): {e_disconnect}")
                return False

        last_ping_time = 0

        try:
            logger.debug(f"SSE sender for {current_chat_id}: Sending initial ping (Instance: {sse_instance_id}).")
            yield {"event": "ping", "data": json.dumps({"timestamp": datetime.utcnow().isoformat(), "message": "SSE connection established"})}

            while not client_disconnected:
                event_data_item = None
                try:
                    logger.debug(f"[SSE {current_chat_id} Instance {sse_instance_id}] Waiting for event from queue...")
                    event_data_item = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    logger.debug(f"[SSE {current_chat_id} Instance {sse_instance_id}] Got event: {str(event_data_item)[:100]}")
                except asyncio.TimeoutError:
                    if await check_disconnect_internal(): break
                    current_time_for_ping = time.time()
                    if (current_time_for_ping - last_ping_time) >= 5.0:
                        logger.debug(f"[SSE {current_chat_id} Instance {sse_instance_id}] Client still connected. Sending ping.")
                        try:
                            yield {"event": "ping", "data": json.dumps({"timestamp": datetime.utcnow().isoformat(), "message": "keep-alive"})}
                            last_ping_time = current_time_for_ping
                        except Exception as ping_err:
                            logger.error(f"[SSE {current_chat_id} Instance {sse_instance_id}] Error sending ping: {ping_err}", exc_info=True)
                            client_disconnected = True
                            break
                    continue
                except asyncio.CancelledError:
                    logger.info(f"SSE event sender for chat {current_chat_id} was CANCELLED (Instance: {sse_instance_id}).")
                    client_disconnected = True
                    break
                except Exception as e_get_q:
                    logger.error(f"[SSE {current_chat_id} Instance {sse_instance_id}] Error getting event from queue: {e_get_q}", exc_info=True)
                    if await check_disconnect_internal(): break
                    try:
                        yield {"event": "error", "data": json.dumps({"message": f"Error fetching event: {str(e_get_q)}", "stage": "sse_queue_read"})}
                    except Exception as send_q_err_e:
                        logger.error(f"[SSE {current_chat_id} Instance {sse_instance_id}] Failed to send queue read error: {send_q_err_e}")
                    client_disconnected = True
                    break
                
                if event_data_item is STREAM_END_SENTINEL:
                    logger.info(f"[SSE {current_chat_id} Instance {sse_instance_id}] Received STREAM_END_SENTINEL. Sending final event.")
                    try:
                        yield {"event": STREAM_END_SENTINEL["type"], "data": json.dumps(STREAM_END_SENTINEL["data"])}
                        if not event_queue.empty():
                             event_queue.task_done()
                    except Exception as send_final_err_e:
                        logger.error(f"[SSE {current_chat_id} Instance {sse_instance_id}] Error sending stream_end sentinel: {send_final_err_e}", exc_info=True)
                    client_disconnected = True
                    break

                if isinstance(event_data_item, dict) and "type" in event_data_item and "data" in event_data_item:
                    event_type_to_send = event_data_item["type"]
                    data_payload_to_send = event_data_item["data"]
                    formatted_data_to_send = json.dumps(data_payload_to_send) if not isinstance(data_payload_to_send, str) else data_payload_to_send
                    logger.debug(f"SSE Sender for {current_chat_id} (Instance {sse_instance_id}): Sending event type '{event_type_to_send}'")
                    yield {"event": event_type_to_send, "data": formatted_data_to_send}
                else:
                    logger.warning(f"[SSE {current_chat_id} Instance {sse_instance_id}] Malformed event from queue: {event_data_item}")
                    yield {"event": "error", "data": json.dumps({"message": "Malformed event from queue.", "stage": "sse_formatting"})}
                
                if not event_queue.empty():
                    event_queue.task_done()
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info(f"SSE event sender for chat {current_chat_id} (Instance {sse_instance_id}) was EXPLICITLY CANCELLED (outer).")
            client_disconnected = True
        except Exception as e_outer_gen:
            logger.error(f"SSE event sender for chat {current_chat_id} (Instance {sse_instance_id}) UNHANDLED outer error: {e_outer_gen}", exc_info=True)
            if not client_disconnected:
                try:
                    yield {"event": "error", "data": json.dumps({"message": f"Critical SSE sender error: {str(e_outer_gen)}", "stage": "sse_critical_outer"})}
                except Exception as send_outer_final_err:
                     logger.error(f"[SSE {current_chat_id} Instance {sse_instance_id}] Failed to send final critical outer error: {send_outer_final_err}")
        finally:
            logger.info(f"🔴 SSE event sender for chat {current_chat_id} (Instance {sse_instance_id}, HIT_ID: {hit_id_from_route}) entering FINALLY block. Client disconnected: {client_disconnected}")
            if active_sse_connections[current_chat_id] > 0:
                 active_sse_connections[current_chat_id] -= 1
            else:
                 logger.warning(f"🔴 SSE Cleanup for {current_chat_id} (Instance {sse_instance_id}): Connection count was already 0 or less before decrementing!")

            remaining_connections = active_sse_connections.get(current_chat_id, 0)
            logger.info(f"🔴 SSE event sender for chat {current_chat_id} (Instance {sse_instance_id}, HIT_ID: {hit_id_from_route}) CLEANING UP. Remaining connections: {remaining_connections}")

            if remaining_connections == 0:
                logger.info(f"🔴 No more SSE connections for chat {current_chat_id} (Instance {sse_instance_id}, HIT_ID: {hit_id_from_route}). Cleaning up queue and connection count entry.")
                active_sse_connections.pop(current_chat_id, None)
                
                if current_chat_id in active_chat_queues and active_chat_queues[current_chat_id] is event_queue:
                    if not event_queue.empty():
                        logger.warning(f"🔴 Cleaning up queue for chat {current_chat_id} (Instance {sse_instance_id}) but it's not empty. {event_queue.qsize()} items remaining (will be lost).")
                        while not event_queue.empty():
                            try:
                                event_queue.get_nowait()
                                event_queue.task_done()
                            except asyncio.QueueEmpty:
                                break
                    active_chat_queues.pop(current_chat_id, None)
                    logger.info(f"🔴 Queue for chat {current_chat_id} (Instance {sse_instance_id}) removed from active_chat_queues.")
                else:
                    logger.warning(f"🔴 Queue for chat {current_chat_id} (Instance {sse_instance_id}) was not found in active_chat_queues or was not the expected instance during final cleanup. Might have been cleaned by another process or a re-entrant call.")
            else:
                logger.warning(f"🔴 Still have {remaining_connections} SSE connections for chat {current_chat_id} (Instance {sse_instance_id}, HIT_ID: {hit_id_from_route}), NOT cleaning up queue or connection count entry fully.")
            logger.info(f"🔴 SSE event sender for chat {current_chat_id} (Instance {sse_instance_id}, HIT_ID: {hit_id_from_route}) FINISHED.")

    return EventSourceResponse(sse_event_generator(chat_id, request, route_hit_id))


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
    logger.info(f"[Chat {chat_id}] Background task started (is_edit_flow: {is_edit_flow}). Initial content (if any): {initial_user_message_content}")
    is_error = False
    error_data = {}
    final_reply_accumulator = ""
    final_state = None
    token_cv = None 

    try:
        with get_db_context() as db_session_bg:
            logger.info(f"[Chat {chat_id}] Acquired DB session for background task.")
            chat_service_bg = ChatService(db_session_bg)
            flow_service_bg = FlowService(db_session_bg)

            chat = chat_service_bg.get_chat(chat_id)
            if not chat:
                logger.error(f"[Chat {chat_id}] Background task could not find chat.")
                await event_queue.put({"type": "error", "data": {"message": "Chat not found.", "stage": "setup"}})
                return
            
            if not is_edit_flow and initial_user_message_content is not None:
                logger.info(f"[Chat {chat_id}] Attempting to save user message to DB before agent call: {initial_user_message_content[:100]}...")
                saved_chat_obj, server_message_timestamp = chat_service_bg.add_message_to_chat(
                    chat_id=chat_id, 
                    role="user", 
                    content=initial_user_message_content
                )
                if saved_chat_obj and server_message_timestamp:
                    logger.info(f"[Chat {chat_id}] User message saved to DB with server_timestamp: {server_message_timestamp}.")
                    if client_message_id:
                        await event_queue.put({
                            "type": "user_message_saved", 
                            "data": {
                                "client_message_id": client_message_id,
                                "server_message_timestamp": server_message_timestamp,
                                "content": initial_user_message_content
                            }
                        })
                        logger.info(f"[Chat {chat_id}] Sent user_message_saved event for client_id: {client_message_id} -> server_ts: {server_message_timestamp}")
                    
                    chat = saved_chat_obj 
                else:
                    logger.error(f"[Chat {chat_id}] Failed to save user message to DB.")
                    await event_queue.put({
                        "type": "error", 
                        "data": {"message": "Failed to save user message.", "stage": "setup"}
                    })
                    return


            flow_id = chat.flow_id
            token_cv = current_flow_id_var.set(flow_id) 
            logger.info(f"[Chat {chat_id}] Set current_flow_id_var to {flow_id}")

            flow = flow_service_bg.get_flow_instance(flow_id)
            if not flow:
                logger.error(f"[Chat {chat_id}] Background task could not find flow {flow_id}.")
                await event_queue.put({"type": "error", "data": {"message": f"Flow {flow_id} not found.", "stage": "setup"}})
                current_flow_id_var.reset(token_cv)
                return
            
            flow_data = flow.flow_data or {}
            logger.debug(f"[Chat {chat_id}] Flow data for context: {str(flow_data)[:200]}...")

            logger.info(f"[Chat {chat_id}] Getting compiled LangGraph from ChatService.")
            compiled_graph = chat_service_bg.compiled_workflow_graph
            logger.info(f"[Chat {chat_id}] Successfully got compiled LangGraph.")

            chat_history_raw = chat.chat_data.get("messages", [])
            
            graph_input_messages = _format_messages_to_langchain(chat_history_raw)
            
            current_user_input_content = ""
            if graph_input_messages and isinstance(graph_input_messages[-1], HumanMessage):
                current_user_input_content = graph_input_messages[-1].content
            else:
                logger.warning(f"[Chat {chat_id}] Could not determine current user input from chat history. Last message: {graph_input_messages[-1] if graph_input_messages else 'No messages'}")
                if initial_user_message_content and not is_edit_flow:
                     current_user_input_content = initial_user_message_content
                elif is_edit_flow and chat_history_raw:
                    last_raw_msg = chat_history_raw[-1]
                    if last_raw_msg.get("role") == "user":
                        current_user_input_content = last_raw_msg.get("content", "")


            graph_input = {
                "messages": graph_input_messages,
                "input": current_user_input_content,
                "flow_context": flow_data.get("graphContextVars", {}),
                "current_flow_id": flow_id,
                "sse_event_queue": event_queue
            }
            
            messages_count_val = len(graph_input["messages"])
            input_len_val = len(graph_input["input"])
            flow_id_val = graph_input["current_flow_id"]
            logger.info(f"[Chat {chat_id}] Prepared graph input: messages_count={messages_count_val}, input_len={input_len_val}, input_content='{current_user_input_content[:50]}...', flow_id={flow_id_val}")

            logger.info(f"[Chat {chat_id}] Invoking compiled_graph.astream_events (version='v2')...")
            
            event_include_names = None

            async for event in compiled_graph.astream_events(graph_input, version="v2", include_names=event_include_names, include_tags=None):
                event_name = event.get("event")
                event_data = event.get("data", {})
                run_name = event.get("name", "unknown_run")

                logger.debug(f"[Chat {chat_id}] Received event: '{event_name}' from '{run_name}', Data keys: {list(event_data.keys())}")
                
                if event_name == "on_chain_end":
                    logger.info(f"[Chat {chat_id}] 🚨 CHAIN END DETECTED: run_name='{run_name}', compiled_graph.name='{compiled_graph.name}'")
                    logger.debug(f"[Chat {chat_id}] 🚨 Output data type: {type(event_data.get('output', 'NO_OUTPUT'))}")
                    if isinstance(event_data.get('output'), dict):
                        output_keys = list(event_data.get('output', {}).keys())
                        logger.debug(f"[Chat {chat_id}] 🚨 Output keys: {output_keys}")
                
                if event_name not in ["on_chat_model_stream"]:
                    logger.debug(f"[Chat {chat_id}] 📋 Event details - Name: {event_name}, Run: {run_name}, Data type: {type(event_data)}")

                if event_name == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and isinstance(chunk, AIMessageChunk) and chunk.content:
                        token = chunk.content
                        logger.debug(f"[Chat {chat_id}] LLM Token from '{run_name}': '{token}'")
                        await event_queue.put({"type": "token", "data": token})
                        final_reply_accumulator += token 
                    elif chunk:
                        logger.warning(f"[Chat {chat_id}] Received on_chat_model_stream chunk from '{run_name}' but no content or not AIMessageChunk. Chunk: {chunk}")

                elif event_name == "on_llm_end":
                    output = event_data.get("output")
                    if output and isinstance(output, AIMessage) and output.content:
                        logger.debug(f"[Chat {chat_id}] LLM End from '{run_name}'. Full output (for verification): '{output.content[:100]}...'")
                        if final_reply_accumulator != output.content and not final_reply_accumulator.endswith(output.content):
                            logger.warning(f"[Chat {chat_id}] Discrepancy between accumulated stream and on_llm_end output from '{run_name}'. Accum: '{final_reply_accumulator[:100]}...', Output: '{output.content[:100]}...'")
                    elif output:
                         logger.warning(f"[Chat {chat_id}] Received on_llm_end from '{run_name}' but no content or not AIMessage. Output: {output}")

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
                    
                    if tool_name and "sas" in tool_name.lower() and isinstance(tool_output, dict):
                        important_keys = ['sas_step1_generated_tasks', 'sas_step2_generated_task_details', 'dialog_state']
                        if any(key in tool_output for key in important_keys):
                            logger.info(f"[Chat {chat_id}] 🎯 工具 '{tool_name}' 输出包含重要状态，触发同步")
                            sync_result = _sync_langgraph_state_to_flow(tool_output, flow_id, flow_service_bg)
                            
                            if sync_result and sync_result.get("needs_frontend_update"):
                                logger.info(f"[Chat {chat_id}] 🎯 工具结束后发送agent_state_updated事件到前端")
                                await event_queue.put({
                                    "type": "agent_state_updated", 
                                    "data": {
                                        "message": f"Agent state updated by tool '{tool_name}'",
                                        "update_types": sync_result.get("update_types", []),
                                        "flow_id": flow_id,
                                        "agent_state": sync_result.get("updated_agent_state", {}),
                                        "trigger": "tool_end"
                                    }
                                })
                            else:
                                logger.info(f"[Chat {chat_id}] 🎯 工具 '{tool_name}' 同步未产生前端更新需求")
                        else:
                            logger.debug(f"[Chat {chat_id}] 🎯 工具 '{tool_name}' 输出不包含重要状态键: {list(tool_output.keys())}")

                elif event_name == "on_chain_end":
                    outputs_from_chain = event_data.get("output", {})
                    logger.info(f"[Chat {chat_id}] 🚨 Chain End: '{run_name}'. Output keys: {list(outputs_from_chain.keys()) if isinstance(outputs_from_chain, dict) else 'Not a dict'}")
                    logger.debug(f"[Chat {chat_id}] 🚨 Chain End output type: {type(outputs_from_chain)}")
                    logger.debug(f"[Chat {chat_id}] 🚨 Chain End output content: {str(outputs_from_chain)[:500]}...")
                    
                    should_sync = False
                    sync_reason = ""
                    
                    if run_name == compiled_graph.name or run_name == "__graph__":
                        should_sync = True
                        sync_reason = "主图执行结束"
                        final_state = outputs_from_chain
                        logger.info(f"[Chat {chat_id}] 🎯 触发条件1: 主图结束 (run_name: {run_name}, graph_name: {compiled_graph.name})")
                        
                    elif "sas" in run_name.lower() and isinstance(outputs_from_chain, dict):
                        important_keys = [
                            'sas_step1_generated_tasks',
                            'sas_step2_generated_task_details', 
                            'dialog_state',
                            'task_list_accepted',
                            'module_steps_accepted',
                            'current_user_request'
                        ]
                        
                        found_keys = [key for key in important_keys if key in outputs_from_chain]
                        if found_keys:
                            should_sync = True
                            sync_reason = f"SAS子图状态更新 (run_name: {run_name}, found_keys: {found_keys})"
                            final_state = outputs_from_chain
                            logger.info(f"[Chat {chat_id}] 🎯 触发条件2: SAS子图状态更新")
                            logger.debug(f"[Chat {chat_id}] 🎯 发现重要键: {found_keys}")
                        else:
                            logger.debug(f"[Chat {chat_id}] 🎯 SAS子图结束但无重要状态: {run_name}, keys: {list(outputs_from_chain.keys())}")
                    
                    elif "robot_flow_invoker" in run_name.lower() and isinstance(outputs_from_chain, dict):
                        if "sas_planner_subgraph_state" in outputs_from_chain:
                            should_sync = True
                            sync_reason = f"机器人流程节点完成 (run_name: {run_name})"
                            final_state = outputs_from_chain
                            logger.info(f"[Chat {chat_id}] 🎯 触发条件3: 机器人流程节点完成")
                        else:
                            logger.debug(f"[Chat {chat_id}] 🎯 机器人流程节点结束但无子图状态: {run_name}")
                    
                    if not should_sync:
                        logger.debug(f"[Chat {chat_id}] 🎯 Chain End不满足同步条件: run_name='{run_name}', graph_name='{compiled_graph.name}', is_dict={isinstance(outputs_from_chain, dict)}")
                    
                    if should_sync:
                        logger.info(f"[Chat {chat_id}] 🎯 触发同步 - 原因: {sync_reason}")
                        logger.debug(f"[Chat {chat_id}] 🎯 Final state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'Not a dict'}. Content: {str(final_state)[:500]}...")
                        
                        if isinstance(final_state, dict):
                            sync_result = _sync_langgraph_state_to_flow(final_state, flow_id, flow_service_bg)
                            
                            if sync_result and sync_result.get("needs_frontend_update"):
                                logger.info(f"[Chat {chat_id}] 🎯 发送agent_state_updated事件到前端")
                                await event_queue.put({
                                    "type": "agent_state_updated", 
                                    "data": {
                                        "message": "Agent state has been updated with new tasks/details",
                                        "update_types": sync_result.get("update_types", []),
                                        "flow_id": flow_id,
                                        "agent_state": sync_result.get("updated_agent_state", {})
                                    }
                                })
                            else:
                                logger.info(f"[Chat {chat_id}] 🎯 同步完成但无需前端更新: sync_result={sync_result}")
                        else:
                            logger.warning(f"[Chat {chat_id}] 🎯 final_state不是字典类型，跳过同步。类型: {type(final_state)}")
                    
                    if run_name == compiled_graph.name or run_name == "__graph__":

                        latest_ai_message_from_state: Optional[str] = None
                        if isinstance(final_state, dict) and "messages" in final_state and isinstance(final_state["messages"], list):
                            
                            for msg_state in reversed(final_state["messages"]):
                                content_candidate: Optional[str] = None
                                is_ai_message = False

                                if isinstance(msg_state, AIMessage):
                                    is_ai_message = True
                                    if hasattr(msg_state, 'content'):
                                        content_candidate = msg_state.content
                                elif isinstance(msg_state, dict) and msg_state.get("type") == "ai":
                                    is_ai_message = True
                                    content_candidate = msg_state.get("content")
                                
                                if is_ai_message:
                                    if content_candidate is not None and isinstance(content_candidate, str) and content_candidate.strip():
                                        latest_ai_message_from_state = content_candidate
                                        logger.info(f"[Chat {chat_id}] Found latest AI message (type: {type(msg_state)}) in final graph state: '{latest_ai_message_from_state[:100]}...'")
                                    else:
                                        logger.warning(f"[Chat {chat_id}] Found AI-like message (type: {type(msg_state)}) in final state, but content is None, not string, or empty/whitespace. Original content: '{str(content_candidate)[:100]}...'")
                                    break
                                if not is_ai_message:
                                    continue
                        
                        if latest_ai_message_from_state:
                            if not final_reply_accumulator:
                                logger.info(f"[Chat {chat_id}] No prior stream. Using AIMessage from final graph state as the reply: '{latest_ai_message_from_state[:100]}...'")
                                final_reply_accumulator = latest_ai_message_from_state
                                await event_queue.put({"type": "token", "data": latest_ai_message_from_state})
                            elif final_reply_accumulator != latest_ai_message_from_state:
                                logger.warning(f"[Chat {chat_id}] Accumulated stream reply ('{final_reply_accumulator[:100]}...') differs from final graph state AIMessage ('{latest_ai_message_from_state[:100]}...').")
                                logger.info(f"[Chat {chat_id}] Overwriting accumulated stream with final AIMessage from graph state for frontend and saving.")
                                final_reply_accumulator = latest_ai_message_from_state
                                await event_queue.put({"type": "token", "data": latest_ai_message_from_state})
                        else:
                            if final_reply_accumulator:
                                logger.info(f"[Chat {chat_id}] Graph ended. No new AIMessage in final state. Using previously accumulated stream as final reply: '{final_reply_accumulator[:100]}...'")
                            else:
                                logger.warning(f"[Chat {chat_id}] Graph ended. No AIMessage in final state and no accumulated stream. Reply will be empty/null if no default is set later.")
                
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
            logger.info(f"[Chat {chat_id}] Reset current_flow_id context variable in finally block.")
        else:
            logger.warning(f"[Chat {chat_id}] current_flow_id_var might not have been set or was already reset, skipping reset in finally.")

        session_should_end = False
        if isinstance(final_state, dict) and final_state.get("output") == "__end__":
            session_should_end = True
        elif isinstance(final_state, str) and final_state == "__end__":
            session_should_end = True

        if session_should_end and not final_reply_accumulator and not is_error:
            default_goodbye_message = "好的，再见！如果您还有其他问题，随时可以再次联系我。"
            logger.info(f"[Chat {chat_id}] Session is ending and no AI reply was generated. Using default goodbye: '{default_goodbye_message}'")
            final_reply_accumulator = default_goodbye_message
            try:
                await event_queue.put({"type": "token", "data": default_goodbye_message})
                logger.info(f"[Chat {chat_id}] Sent default goodbye message to event queue.")
            except asyncio.QueueFull:
                logger.error(f"[Chat {chat_id}] Failed to put default goodbye message in full queue.")
            except Exception as qe_goodbye:
                logger.error(f"[Chat {chat_id}] Failed to put default goodbye message in queue: {qe_goodbye}")

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
            logger.info(f"[Chat {chat_id}] Skipping save because final reply was empty or null. Accumulator content: '{final_reply_accumulator}'")
        
        try:
            logger.info(f"[Chat {chat_id}] Putting STREAM_END_SENTINEL into queue.")
            await event_queue.put(STREAM_END_SENTINEL)
            logger.info(f"[Chat {chat_id}] Stream end sentinel sent.")
        except asyncio.QueueFull:
            logger.error(f"[Chat {chat_id}] Failed to put STREAM_END_SENTINEL in full queue.")
        except Exception as qe:
            logger.error(f"[Chat {chat_id}] Failed to put STREAM_END_SENTINEL in queue: {qe}")
        
        if chat_id in active_chat_queues and active_chat_queues[chat_id] is not event_queue:
            try:
                current_queue = active_chat_queues[chat_id]
                logger.info(f"[Chat {chat_id}] Found active queue during cleanup. Queue size: {current_queue.qsize()}")
                
                has_end_sentinel = False
                temp_items = []
                while not current_queue.empty():
                    try:
                        item = current_queue.get_nowait()
                        temp_items.append(item)
                        if item is STREAM_END_SENTINEL:
                            has_end_sentinel = True
                            logger.info(f"[Chat {chat_id}] Found existing STREAM_END_SENTINEL in queue")
                        current_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                
                for item in temp_items:
                    await current_queue.put(item)
                
                if not has_end_sentinel:
                    logger.info(f"[Chat {chat_id}] No STREAM_END_SENTINEL found in queue, adding one now")
                    await current_queue.put(STREAM_END_SENTINEL)
                    logger.info(f"[Chat {chat_id}] STREAM_END_SENTINEL added to queue during cleanup")
                    
            except asyncio.QueueFull:
                logger.error(f"[Chat {chat_id}] Failed to add STREAM_END_SENTINEL during cleanup - queue is full")
            except Exception as cleanup_err:
                logger.error(f"[Chat {chat_id}] Error during queue cleanup: {cleanup_err}", exc_info=True)
        else:
            logger.info(f"[Chat {chat_id}] No active queue found during cleanup")
            
        logger.info(f"[Chat {chat_id}] Background task (is_edit_flow: {is_edit_flow}) final cleanup completed.")

def _sync_langgraph_state_to_flow(final_state, flow_id, flow_service_bg):
    try:
        logger.info(f"[Flow {flow_id}] 🎯 开始同步LangGraph状态到Flow agent_state...")
        logger.debug(f"[Flow {flow_id}] 🎯 final_state键值: {list(final_state.keys()) if isinstance(final_state, dict) else 'Not a dict'}")
        logger.debug(f"[Flow {flow_id}] 🎯 final_state内容摘要: {str(final_state)[:1000]}...")
        
        flow = flow_service_bg.get_flow_instance(flow_id)
        if not flow:
            logger.error(f"[Flow {flow_id}] 无法找到Flow，同步失败")
            return None
        
        current_agent_state = flow.agent_state or {}
        logger.debug(f"[Flow {flow_id}] 🎯 当前agent_state键值: {list(current_agent_state.keys())}")
        
        needs_sync = False
        sync_updates = {}
        update_types = []
        
        important_fields = [
            'sas_step1_generated_tasks',
            'sas_step2_generated_task_details', 
            'task_list_accepted',
            'module_steps_accepted',
            'dialog_state',
            'subgraph_completion_status',
            'current_user_request',
            'revision_iteration',
            'input_processed'
        ]
        
        for field in important_fields:
            if field in final_state:
                current_value = current_agent_state.get(field)
                new_value = final_state[field]

                # <<< START DEBUG LOGGING >>>
                if field == 'dialog_state' or field == 'sas_step1_generated_tasks':
                    logger.info(f"[SYNC_DEBUG] Comparing field: {field}")
                    logger.info(f"[SYNC_DEBUG]   current_value ('{type(current_value)}'): {str(current_value)[:300]}")
                    logger.info(f"[SYNC_DEBUG]   new_value     ('{type(new_value)}'): {str(new_value)[:300]}")
                    is_different = current_value != new_value
                    logger.info(f"[SYNC_DEBUG]   Comparison result (current_value != new_value): {is_different}")
                # <<< END DEBUG LOGGING >>>

                if current_value != new_value:
                    current_value_str = str(current_value)[:50] + ('...' if len(str(current_value)) > 50 else '')
                    new_value_str = str(new_value)[:50] + ('...' if len(str(new_value)) > 50 else '')
                    logger.info(f"[Flow {flow_id}] 🎯 检测到{field}变化: {current_value_str} -> {new_value_str}")
                    sync_updates[field] = new_value
                    update_types.append(field)
                    needs_sync = True
        
        sas_subgraph_state = final_state.get('sas_planner_subgraph_state')
        if sas_subgraph_state and isinstance(sas_subgraph_state, dict):
            logger.info(f"[Flow {flow_id}] 🎯 发现SAS子图状态，开始提取数据...")
            logger.debug(f"[Flow {flow_id}] 🎯 SAS子图状态键值: {list(sas_subgraph_state.keys())}")
            
            sas_important_fields = [
                'sas_step1_generated_tasks',
                'sas_step2_generated_task_details',
                'sas_step2_module_steps',
                'task_list_accepted',
                'module_steps_accepted',
                'dialog_state',
                'subgraph_completion_status',
                'current_user_request',
                'revision_iteration'
            ]
            
            for field in sas_important_fields:
                if field in sas_subgraph_state:
                    current_value = current_agent_state.get(field)
                    new_value = sas_subgraph_state[field]
                    if current_value != new_value:
                        current_value_str_sas = str(current_value)[:50] + ('...' if len(str(current_value)) > 50 else '')
                        new_value_str_sas = str(new_value)[:50] + ('...' if len(str(new_value)) > 50 else '')
                        logger.info(f"[Flow {flow_id}] 🎯 从SAS子图检测到{field}变化: {current_value_str_sas} -> {new_value_str_sas}")
                        sync_updates[field] = new_value
                        update_types.append(f"sas_{field}")
                        needs_sync = True
            
            sas_tasks = sas_subgraph_state.get('sas_step1_generated_tasks')
            if sas_tasks:
                logger.info(f"[Flow {flow_id}] 🎯 SAS子图包含 {len(sas_tasks)} 个任务:")
                for i, task in enumerate(sas_tasks):
                    if isinstance(task, dict):
                        logger.debug(f"[Flow {flow_id}] 🎯   任务{i+1}: {task.get('name', 'Unknown')} (类型: {task.get('type', 'Unknown')})")
                    else:
                        logger.debug(f"[Flow {flow_id}] 🎯   任务{i+1}: {task}")
            
            sas_details = sas_subgraph_state.get('sas_step2_generated_task_details')
            if sas_details:
                logger.info(f"[Flow {flow_id}] SAS子图包含任务详情: {len(sas_details)} 项")
                for task_key, details in sas_details.items():
                    if isinstance(details, dict) and 'details' in details:
                        detail_count = len(details['details']) if isinstance(details['details'], list) else 1
                        logger.debug(f"[Flow {flow_id}] 🎯   {task_key}: {detail_count} 个详情")
        
        has_task_data = (
            sync_updates.get('sas_step1_generated_tasks') or 
            current_agent_state.get('sas_step1_generated_tasks') or
            (sas_subgraph_state and sas_subgraph_state.get('sas_step1_generated_tasks'))
        )
        
        has_detail_data = (
            sync_updates.get('sas_step2_generated_task_details') or
            current_agent_state.get('sas_step2_generated_task_details') or
            (sas_subgraph_state and sas_subgraph_state.get('sas_step2_generated_task_details'))
        )
        
        needs_frontend_update = has_task_data or has_detail_data
        if needs_frontend_update:
            logger.info(f"[Flow {flow_id}] 🎯 检测到任务数据，需要前端节点更新")
            update_types.append("frontend_nodes")
            needs_sync = True
        
        if needs_sync:
            logger.info(f"[Flow {flow_id}] 🎯 执行状态同步，更新 {len(sync_updates)} 个字段:")
            for key, value in sync_updates.items():
                logger.debug(f"[Flow {flow_id}] 🎯   {key}: {str(value)[:200]}...")
            
            current_agent_state.update(sync_updates)
            flow.agent_state = current_agent_state
            
            result = {
                "needs_frontend_update": needs_frontend_update,
                "update_types": update_types,
                "updated_agent_state": current_agent_state,
                "sync_updates": sync_updates
            }
            
            logger.info(f"[Flow {flow_id}] 🎯 状态同步完成，需要前端更新: {needs_frontend_update}")
            return result
        else:
            logger.info(f"[Flow {flow_id}] 🎯 没有检测到需要同步的状态变化")
            return None
    
    except Exception as e:
        logger.error(f"[Flow {flow_id}] 🎯 状态同步过程中发生错误: {e}", exc_info=True)
        return None 