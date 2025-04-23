from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio # 确保导入 asyncio
from collections import defaultdict # 导入 defaultdict

from backend.app import schemas
from database.connection import get_db, get_db_context
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from backend.app.services.flow_service import FlowService
from backend.langchainchat.chains.workflow_chain import WorkflowChainOutput
from database.models import Flow

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
         
    # --- 获取或创建此聊天的事件队列 ---
    # 注意：这里简单覆盖可能存在的旧队列，实际应用需要更精细的处理逻辑
    # (例如，如果已有队列，是报错还是等待？)
    event_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE) 
    active_chat_queues[chat_id] = event_queue
    logger.info(f"为 chat {chat_id} 创建/设置了新的事件队列")

    # --- 定义在后台处理流并将事件放入队列的任务 --- 
    async def process_and_publish_events(c_id: str, msg_content: str, queue: asyncio.Queue):
        logger.debug(f"[Chat {c_id}] Background task started.")
        final_content_to_save = None
        is_error = False
        error_content = None
        tool_calls = []
        final_flow_data = None # 用于存储最终的流程图数据

        with get_db_context() as db_session_bg:
            logger.debug(f"[Chat {c_id}] Acquired DB session for background task.")
            chat_service_bg = ChatService(db_session_bg)
            flow_service_bg = FlowService(db_session_bg)
            
            try:
                # 从数据库获取完整的聊天历史（包含刚才添加的用户消息）
                chat = chat_service_bg.get_chat(c_id)
                if not chat:
                    logger.error(f"[Chat {c_id}] Background task could not find chat.")
                    await queue.put({"type": "error", "data": {"message": "Chat not found."}})
                    return
                    
                flow_id = chat.flow_id
                flow = flow_service_bg.get_flow_instance(flow_id) # 获取 Flow 实例
                if not flow:
                     logger.error(f"[Chat {c_id}] Background task could not find flow {flow_id}.")
                     await queue.put({"type": "error", "data": {"message": f"Flow {flow_id} not found."}})
                     return
                     
                current_messages = chat.chat_data.get('messages', [])
                flow_data = flow.flow_data # 获取流程图数据

                logger.info(f"[Chat {c_id}] Processing message with {len(current_messages)} history entries.")
                chain = chat_service_bg.workflow_chain 
                
                # 使用 astream_events 处理流式响应，并提供所有必需的输入键
                input_data = {
                    "user_input": msg_content,
                    "flow_id": flow_id,
                    "chat_id": c_id,
                    "history": current_messages
                }
                async for event in chain.astream_events(
                    input_data, 
                    version="v1"
                ):
                    kind = event["event"]
                    tags = event.get("tags", [])
                    
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if chunk.content:
                            logger.debug(f'[Chat {c_id}] Streaming chunk: {chunk.content}')
                            await queue.put({"type": "token", "data": chunk.content})
                    elif kind == "on_tool_start":
                         logger.info(f'[Chat {c_id}] Tool start event: {event["name"]}, Input: {event["data"].get("input")}')
                         # 将工具调用信息暂存，等结束后一起放入 final_content_to_save
                         tool_calls.append({
                            "tool_name": event["name"],
                            "tool_input": event["data"].get("input")
                         })
                         # 如果需要，也可以立即发送一个事件通知前端工具开始执行
                         await queue.put({"type": "tool_start", "data": {"name": event["name"], "input": event["data"].get("input")}})
                         
                    elif kind == "on_tool_end":
                        logger.info(f'[Chat {c_id}] Tool end event: {event["name"]}, Output: {event["data"].get("output")}')
                        # 找到对应的工具调用并添加输出
                        for call in tool_calls:
                            if call["tool_name"] == event["name"] and "tool_output" not in call:
                                call["tool_output"] = event["data"].get("output")
                                break # 假设每个工具调用名称唯一
                        # 发送事件通知前端工具结束执行
                        await queue.put({"type": "tool_end", "data": {"name": event["name"], "output": event["data"].get("output")}})
                        
                    elif kind == "on_chain_end":
                        # 检查是否有最终输出和可能的流程图更新
                        output = event["data"].get('output')
                        if isinstance(output, WorkflowChainOutput):
                            final_content_to_save = output.final_answer
                            final_flow_data = output.get_flow_data_if_updated() # 获取更新后的 flow_data
                            logger.info(f"[Chat {c_id}] Chain ended. Final Answer: {final_content_to_save}")
                            if final_flow_data:
                                logger.info(f"[Chat {c_id}] Flow data was updated by the chain.")
                        elif isinstance(output, str):
                             final_content_to_save = output
                             logger.info(f"[Chat {c_id}] Chain ended. Final Answer (string): {final_content_to_save}")
                        else:
                            logger.warning(f"[Chat {c_id}] Chain ended but output format is unexpected: {type(output)}")
                    
                    # 处理其他类型的事件 (可根据需要添加)
                    # elif kind == "on_retriever_end":
                    #     logger.debug(f'[Chat {c_id}] Retriever end event: {event["data"]}')
                    # elif kind == "on_prompt_end":
                    #     logger.debug(f'[Chat {c_id}] Prompt end event: {event["data"]}')
                        
            except Exception as e:
                is_error = True
                error_content = f"处理消息时出错: {str(e)}"
                logger.error(f"[Chat {c_id}] Error during message processing: {e}", exc_info=True)
                await queue.put({"type": "error", "data": {"message": error_content}})
                
            # <<< finally 块与 try/except 对齐 >>>
            finally:
                # <<< finally 内部代码增加一级缩进 >>>
                logger.debug(f"[Chat {c_id}] Background task finally block entered.")
                # 必须在 finally 块中，确保即使出错也发送结束标记
                await queue.put(STREAM_END_SENTINEL)
                logger.info(f"[Chat {c_id}] Stream end sentinel sent.")
                
                # --- 保存最终结果（助手回复或错误信息）--- 
                logger.debug(f"[Chat {c_id}] Attempting to save final result.")
                
                content_to_add = None
                role_to_add = None
                
                if is_error:
                    content_to_add = error_content if error_content else "未知处理错误"
                    role_to_add = 'system' 
                elif final_content_to_save:
                    if tool_calls:
                        content_to_add = {
                            "text": final_content_to_save,
                            "tool_calls": tool_calls
                        }
                    else:
                        content_to_add = final_content_to_save
                    role_to_add = 'assistant'
                
                if content_to_add and role_to_add:
                    logger.debug(f"[Chat {c_id}] Acquiring new DB session for saving final result...")
                    with get_db_context() as db_session_for_save:
                        try:
                            logger.debug(f"[Chat {c_id}] Acquired save session. Role: {role_to_add}")
                            chat_service_for_save = ChatService(db_session_for_save)
                            flow_service_for_save = FlowService(db_session_for_save)
                            
                            # 添加助手消息或系统错误消息
                            chat_service_for_save.add_message_to_chat(
                                chat_id=c_id, 
                                role=role_to_add,
                                content=content_to_add
                            )
                            logger.info(f"[Chat {c_id}] Final {role_to_add} message/error saved to DB.")
                            
                            # 如果流程图有更新，保存流程图
                            if final_flow_data:
                                flow_to_update = flow_service_for_save.get_flow(flow_id)
                                if flow_to_update:
                                    flow_to_update.flow_data = final_flow_data
                                    db_session_for_save.commit() # 提交流程图更新
                                    logger.info(f"[Chat {c_id}] Updated flow data saved to DB for flow {flow_id}.")
                                else:
                                    logger.error(f"[Chat {c_id}] Could not find flow {flow_id} to save updated flow data.")
                                    
                        except Exception as save_err:
                            logger.error(f"[Chat {c_id}] Error saving final message/error to DB: {save_err}", exc_info=True)
                else:
                     logger.warning(f"[Chat {c_id}] No final content or error to save.")

        # <<< with db_session_bg 结束 >>>

    # --- 启动后台任务 --- 
    background_tasks.add_task(process_and_publish_events, chat_id, message.content, event_queue)
    logger.info(f"已为 chat {chat_id} 启动后台事件处理任务")

    # --- 立即返回 202 Accepted --- 
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/{chat_id}/events")
async def get_chat_events(chat_id: str):
    """
    用于客户端通过 EventSource 连接以接收聊天事件。
    """
    logger.info(f"收到对 chat {chat_id} 事件流的 GET 请求")
    
    # 查找对应的队列
    if chat_id not in active_chat_queues:
        logger.warning(f"请求 chat {chat_id} 的事件流，但队列不存在")
        # 可以选择返回 404 或等待一小段时间？返回 404 更清晰
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active event stream found for chat {chat_id}. Process might not have started or has finished.")
        
    event_queue = active_chat_queues[chat_id]
    logger.info(f"找到 chat {chat_id} 的事件队列，准备发送 SSE 事件")

    # --- Corrected sse_event_sender function --- 
    async def sse_event_sender():
        is_first_event = True
        try: # <--- Main try block
            while True:
                try:
                    # 从队列获取事件，设置超时以防队列永久阻塞
                    event = await asyncio.wait_for(event_queue.get(), timeout=60.0) 
                except asyncio.TimeoutError:
                     # 长时间没有事件，发送一个心跳或结束？
                     logger.debug(f"等待 chat {chat_id} 事件超时，发送心跳")
                     yield "event: ping\ndata: {}\n\n"
                     continue # 继续等待下一个事件

                # 检查结束标记
                if event == STREAM_END_SENTINEL:
                    logger.info(f"收到 chat {chat_id} 的流结束标记，关闭 SSE 连接")
                    yield f"event: {STREAM_END_SENTINEL['type']}\ndata: {json.dumps(STREAM_END_SENTINEL['data'])}\n\n"
                    # event_queue.task_done() # 标记处理完成
                    break # 退出循环，结束流
                
                # 格式化并发送事件
                event_type = event.get("type", "message") # 默认事件类型
                event_data = event.get("data", {})
                try:
                    data_json = json.dumps(event_data)
                except TypeError:
                    logger.error(f"序列化事件数据为 JSON 失败 (type: {event_type}, chat: {chat_id})", exc_info=True)
                    data_json = json.dumps({"error": "Failed to serialize event data"})
                    event_type = "error" # 将事件类型改为 error
                
                sse_message = f"event: {event_type}\ndata: {data_json}\n\n"
                yield sse_message
                # event_queue.task_done() # 标记处理完成
                
                # 添加日志记录第一个事件
                if is_first_event:
                     logger.info(f"已发送第一个 SSE 事件 (type: {event_type}) 到 chat {chat_id} 的监听者")
                     is_first_event = False

        # --- Correctly indented except and finally blocks --- 
        except asyncio.CancelledError:
             logger.info(f"客户端断开了 chat {chat_id} 的事件流连接")
        except Exception as e:
             logger.error(f"发送 chat {chat_id} 的 SSE 事件时出错: {e}", exc_info=True)
             # 尝试发送最后一个错误事件
             try:
                 error_data = json.dumps({"message": f"Server error during event sending: {e}"})
                 yield f"event: error\ndata: {error_data}\n\n"
             except Exception:
                 pass # 忽略发送最终错误的失败
        finally:
             logger.info(f"SSE 事件发送器完成或终止 for chat {chat_id}")
             # 注意：不在此处删除队列，因为后台任务可能还在运行或需要清理
             # 清理逻辑需要更健壮的设计
    # --- End of sse_event_sender function ---

    return StreamingResponse(sse_event_sender(), media_type="text/event-stream")


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