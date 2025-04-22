from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio # 确保导入 asyncio
from collections import defaultdict # 导入 defaultdict

from backend.app import schemas
from database.connection import get_db
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from backend.langchainchat.chains.workflow_chain import WorkflowChainOutput
from database.models import Flow
from database.connection import SessionLocal # Import session factory

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
        logger.info(f"[BG Task {c_id}] 开始处理消息并发布事件...")
        final_content_to_save = "" # 用于保存最终的AI回复文本
        has_stream_output = False
        non_stream_result = None
        db_session_bg = None
        chat_service_bg = None # Initialize chat_service_bg

        # --- Main try block for the background task --- 
        try:
            # --- Nested try...except for the service call --- 
            result_from_service = None # Initialize result within the main try
            try:
                db_session_bg = SessionLocal()
                chat_service_bg = ChatService(db_session_bg)
                logger.info(f"[BG Task {c_id}] Calling ChatService.process_chat_message...")
                result_from_service = await chat_service_bg.process_chat_message(
                    chat_id=c_id,
                    user_message=msg_content
                )
                logger.info(f"[BG Task {c_id}] ChatService.process_chat_message returned type: {type(result_from_service)}")
            except Exception as service_err:
                logger.error(f"[BG Task {c_id}] Error calling ChatService.process_chat_message: {service_err}", exc_info=True)
                # Set an error result dictionary
                result_from_service = {"error": f"Error processing message: {service_err}"}
            # --- End of nested try...except ---

            # --- Process the result (outside nested try...except, inside main try) ---
            if isinstance(result_from_service, WorkflowChainOutput):
                chain_output = result_from_service
                if chain_output.event_stream:
                    has_stream_output = True
                    logger.info(f"[BG Task {c_id}] 检测到事件流，开始迭代...")
                    async for event in chain_output.event_stream:
                        try:
                            await asyncio.wait_for(queue.put(event), timeout=5.0)
                            if event.get("type") == "llm_chunk":
                                final_content_to_save += event.get("data", {}).get("text", "")
                        except asyncio.TimeoutError:
                            logger.error(f"[BG Task {c_id}] 事件队列已满或超时，无法放入事件: {event}")
                            await queue.put({"type": "error", "data": {"message": "Internal queue full or timeout."}})
                            break
                        except Exception as put_err:
                            logger.error(f"[BG Task {c_id}] 放入事件到队列时出错: {put_err}", exc_info=True)
                            await queue.put({"type": "error", "data": {"message": f"Error queueing event: {put_err}"}})
                            break
                    logger.info(f"[BG Task {c_id}] 事件流处理完成。")
                else:
                    logger.info(f"[BG Task {c_id}] 收到非流式响应: {chain_output.model_dump(exclude={'event_stream'})}")
                    non_stream_result = chain_output
                    try:
                        await asyncio.wait_for(queue.put({"type": "final_result", "data": chain_output.model_dump(exclude={'event_stream'})}), timeout=5.0)
                        if chain_output.summary:
                            final_content_to_save = chain_output.summary
                        if chain_output.error:
                            logger.error(f"[BG Task {c_id}] WorkflowChainOutput contained an error: {chain_output.error}")
                    except asyncio.TimeoutError:
                        logger.error(f"[BG Task {c_id}] 事件队列已满或超时，无法放入非流式结果")
                    except Exception as put_err:
                        logger.error(f"[BG Task {c_id}] 放入非流式结果到队列时出错: {put_err}", exc_info=True)

            elif isinstance(result_from_service, dict) and "error" in result_from_service:
                logger.error(f"[BG Task {c_id}] Chat service 返回或产生错误字典: {result_from_service['error']}")
                non_stream_result = result_from_service
                try:
                    await asyncio.wait_for(queue.put({"type": "error", "data": result_from_service}), timeout=5.0)
                    final_content_to_save = result_from_service.get('summary', "处理时发生错误")
                except asyncio.TimeoutError:
                    logger.error(f"[BG Task {c_id}] 事件队列已满或超时，无法放入错误结果")
                except Exception as put_err:
                    logger.error(f"[BG Task {c_id}] 放入错误结果到队列时出错: {put_err}", exc_info=True)

            elif result_from_service is None:
                # This case might happen if the service call failed very early or was interrupted
                logger.error(f"[BG Task {c_id}] Chat service call resulted in None.")
                non_stream_result = {"error": "Internal error: Failed to get result from service."}
                try:
                     await asyncio.wait_for(queue.put({"type": "error", "data": non_stream_result}), timeout=5.0)
                     final_content_to_save = "内部服务器错误"
                except asyncio.TimeoutError:
                     logger.error(f"[BG Task {c_id}] 事件队列已满或超时，无法放入内部错误结果")
                except Exception as put_err:
                     logger.error(f"[BG Task {c_id}] 放入内部错误结果到队列时出错: {put_err}", exc_info=True)

            else:
                # Handle unexpected result types
                logger.error(f"[BG Task {c_id}] Chat service 返回未知结果类型: {type(result_from_service)}")
                non_stream_result = {"error": f"Internal server error: Unexpected result type {type(result_from_service).__name__}."}
                try:
                    await asyncio.wait_for(queue.put({"type": "error", "data": non_stream_result}), timeout=5.0)
                    final_content_to_save = "内部服务器错误"
                except asyncio.TimeoutError:
                    logger.error(f"[BG Task {c_id}] 事件队列已满或超时，无法放入未知错误结果")
                except Exception as put_err:
                    logger.error(f"[BG Task {c_id}] 放入未知错误结果到队列时出错: {put_err}", exc_info=True)

        # --- Main finally block for the background task --- 
        finally:
            # --- 放入结束标记 ---
            try:
                logger.info(f"[BG Task {c_id}] 准备放入流结束标记到队列")
                await asyncio.wait_for(queue.put(STREAM_END_SENTINEL), timeout=5.0)
                logger.info(f"[BG Task {c_id}] 已放入流结束标记")
            except Exception as final_put_err:
                logger.error(f"[BG Task {c_id}] 放入结束标记时出错: {final_put_err}", exc_info=True)

            # --- 后台保存最终回复 (使用新的独立 Session) --- 
            if final_content_to_save:
                 logger.info(f"[BG Task {c_id}] 准备保存最终的助手回复 (长度: {len(final_content_to_save)}) ...")
                 db_session_for_save = None # Initialize
                 try:
                      logger.info(f"[BG Task {c_id}] 获取用于保存回复的 *新* DB Session...")
                      db_session_for_save = SessionLocal() # <--- 获取 *新的* Session
                      chat_service_for_save = ChatService(db_session_for_save) # <--- 使用新 Session 初始化 Service
                      logger.info(f"[BG Task {c_id}] 使用新 Session 调用 add_message_to_chat 保存助手回复...")
                      save_ok = chat_service_for_save.add_message_to_chat(c_id, "assistant", final_content_to_save)
                      if save_ok:
                           logger.info(f"[BG Task {c_id}] 成功保存助手回复 (使用新 Session)。")
                      else:
                           logger.error(f"[BG Task {c_id}] 保存助手回复失败 (使用新 Session, add_message_to_chat 返回失败)。")
                 except Exception as save_err:
                      logger.error(f"[BG Task {c_id}] 使用新 Session 保存助手回复时发生错误: {save_err}", exc_info=True)
                 finally:
                      if db_session_for_save: # <--- 关闭用于保存的 Session
                           try:
                                db_session_for_save.close()
                                logger.info(f"[BG Task {c_id}] 关闭用于保存回复的 DB Session")
                           except Exception as close_save_err:
                                logger.error(f"[BG Task {c_id}] 关闭用于保存回复的 DB Session 时出错: {close_save_err}", exc_info=True)
            else:
                 # Log why nothing was saved
                 logger.warning(f"[BG Task {c_id}] 没有累积的助手回复内容可保存。")
                 if non_stream_result and isinstance(non_stream_result, WorkflowChainOutput) and (non_stream_result.nodes or non_stream_result.connections):
                      logger.info(f"[BG Task {c_id}] (原因: 检测到工具调用结果且无摘要)")
                 elif non_stream_result:
                      logger.info(f"[BG Task {c_id}] (原因: 收到非流式结果但无内容可保存)")
                 elif not has_stream_output:
                      logger.info(f"[BG Task {c_id}] (原因: 未生成流式输出且无非流式结果)")

            # --- 关闭后台任务启动时创建的 DB Session (db_session_bg) --- 
            if db_session_bg: # db_session_bg 是 try 块中创建的那个
                try:
                    db_session_bg.close()
                    logger.info(f"[BG Task {c_id}] 关闭后台 DB Session (在任务开始时创建的)")
                except Exception as close_err:
                    logger.error(f"[BG Task {c_id}] 关闭后台 DB Session (在任务开始时创建的) 时出错: {close_err}", exc_info=True)

            logger.info(f"[BG Task {c_id}] 处理和发布事件的任务完成。")
            # --- End of main finally block ---

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