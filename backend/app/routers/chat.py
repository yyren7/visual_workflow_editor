from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio # 确保导入 asyncio
from collections import defaultdict # 导入 defaultdict
from backend.langgraphchat.context import current_flow_id_var # <--- Import context variable

from backend.app import schemas
from database.connection import get_db, get_db_context
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from backend.app.services.flow_service import FlowService
from database.models import Flow
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

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
        """
        后台任务：处理新消息，使用LangGraph生成回复，并将事件放入队列。
        现在使用 astream_events。
        """
        logger.debug(f"[Chat {c_id}] Background task started (using astream_events).")
        is_error = False
        error_data = {}
        final_reply_accumulator = "" # Used to build the full reply for DB storage
        # sent_ai_content_this_turn is less critical here as tokens should be incremental
        final_state = None

        try:
            # --- Set current_flow_id_var for this task's context ---
            # This ensures that tools or other components called by LangGraph
            # can access the correct flow_id if they rely on this context variable.
            # The flow_id is retrieved after fetching the chat object.
            
            with get_db_context() as db_session_bg:
                logger.debug(f"[Chat {c_id}] Acquired DB session for background task.")
                chat_service_bg = ChatService(db_session_bg)
                flow_service_bg = FlowService(db_session_bg)

                chat = chat_service_bg.get_chat(c_id)
                if not chat:
                    logger.error(f"[Chat {c_id}] Background task could not find chat.")
                    await queue.put({"type": "error", "data": {"message": "Chat not found.", "stage": "setup"}})
                    return
                
                logger.debug(f"[Chat {c_id}] Attempting to save user message to DB before agent call.")
                chat_service_bg.add_message_to_chat(chat_id=c_id, role="user", content=msg_content)
                logger.debug(f"[Chat {c_id}] User message saved to DB.")

                flow_id = chat.flow_id
                # Set the context variable AFTER retrieving flow_id
                token_cv = current_flow_id_var.set(flow_id) 
                logger.debug(f"[Chat {c_id}] Set current_flow_id_var to {flow_id}")


                flow = flow_service_bg.get_flow_instance(flow_id)
                if not flow:
                    logger.error(f"[Chat {c_id}] Background task could not find flow {flow_id}.")
                    await queue.put({"type": "error", "data": {"message": f"Flow {flow_id} not found.", "stage": "setup"}})
                    current_flow_id_var.reset(token_cv) # Reset context var on early exit
                    return
                
                flow_data = flow.flow_data or {}
                logger.debug(f"[Chat {c_id}] Flow data for context: {str(flow_data)[:200]}...")

                logger.debug(f"[Chat {c_id}] Getting compiled LangGraph from ChatService.")
                compiled_graph = chat_service_bg.compiled_workflow_graph
                logger.debug(f"[Chat {c_id}] Successfully got compiled LangGraph.")

                chat_history_raw = chat.chat_data.get("messages", [])
                formatted_history = _format_messages_to_langchain(chat_history_raw[:-1])

                graph_input = {
                    "messages": formatted_history + [HumanMessage(content=msg_content)],
                    "input": msg_content,
                    "flow_context": flow_data.get("graphContextVars", {}),
                    "current_flow_id": flow_id,
                }
                
                messages_count_val = len(graph_input["messages"])
                input_len_val = len(graph_input["input"])
                flow_id_val = graph_input["current_flow_id"]
                logger.debug(f"[Chat {c_id}] Prepared graph input: messages_count={messages_count_val}, input_len={input_len_val}, flow_id={flow_id_val}")

                logger.debug(f"[Chat {c_id}] Invoking compiled_graph.astream_events (version='v2')...")
                
                # Define a set of relevant names if you want to filter events by source node/chain
                # For example: include_names=["agent", "ChatDeepSeek"] # Adjust as per your graph node names
                # If None, all events will be processed.
                event_include_names = None # Or specify: ["agent", "your_llm_node_name_in_graph"]

                async for event in compiled_graph.astream_events(graph_input, version="v2", include_names=event_include_names, include_tags=None):
                    event_name = event.get("event")
                    event_data = event.get("data", {})
                    run_name = event.get("name", "unknown_run") # Name of the runnable that emitted the event

                    logger.info(f"[Chat {c_id}] Received event: '{event_name}' from '{run_name}', Data keys: {list(event_data.keys())}")

                    if event_name == "on_chat_model_stream":
                        chunk = event_data.get("chunk")
                        if chunk and isinstance(chunk, AIMessageChunk) and chunk.content:
                            token = chunk.content
                            logger.debug(f"[Chat {c_id}] LLM Token from '{run_name}': '{token}'")
                            await queue.put({"type": "token", "data": token})
                            final_reply_accumulator += token 
                        elif chunk:
                            logger.debug(f"[Chat {c_id}] Received on_chat_model_stream chunk from '{run_name}' but no content or not AIMessageChunk. Chunk: {chunk}")

                    elif event_name == "on_llm_end": # Usually follows on_chat_model_stream if LLM streamed
                        output = event_data.get("output")
                        if output and isinstance(output, AIMessage) and output.content:
                            logger.info(f"[Chat {c_id}] LLM End from '{run_name}'. Full output (for verification): '{output.content[:100]}...'")
                            # final_reply_accumulator should ideally match output.content by now if streaming was complete
                            if final_reply_accumulator != output.content and not final_reply_accumulator.endswith(output.content): # Basic check
                                logger.warning(f"[Chat {c_id}] Discrepancy between accumulated stream and on_llm_end output from '{run_name}'. Accum: '{final_reply_accumulator[:100]}...', Output: '{output.content[:100]}...'")
                                # Optionally, overwrite accumulator if on_llm_end is considered more authoritative for the full message
                                # final_reply_accumulator = output.content 
                        elif output:
                             logger.debug(f"[Chat {c_id}] Received on_llm_end from '{run_name}' but no content or not AIMessage. Output: {output}")


                    elif event_name == "on_tool_start":
                        tool_name = event_data.get("name") # Name of the tool
                        tool_input = event_data.get("input") # Tool input
                        logger.info(f"[Chat {c_id}] Tool Start: '{tool_name}' from '{run_name}' with input: {str(tool_input)[:100]}...")
                        await queue.put({"type": "tool_start", "data": {"name": tool_name, "input": tool_input}})
                        
                    elif event_name == "on_tool_end":
                        tool_name = event_data.get("name") # Name of the tool
                        tool_output = event_data.get("output") # Tool output
                        # Summarize output for SSE if it's too verbose
                        output_summary = str(tool_output)
                        if len(output_summary) > 200: # Example threshold
                            output_summary = output_summary[:200] + "..."
                        logger.info(f"[Chat {c_id}] Tool End: '{tool_name}' from '{run_name}' with output: {output_summary}")
                        await queue.put({"type": "tool_end", "data": {"name": tool_name, "output_summary": output_summary, "full_output": tool_output}}) # Send summary and full output

                    elif event_name == "on_chain_end": # This might signify the end of a sub-chain or the graph
                        # The 'name' field of the event will tell you which chain ended.
                        # If event.get("name") == "__graph__" (or your top-level graph name), it could be the overall end.
                        outputs_from_chain = event_data.get("output", {})
                        logger.info(f"[Chat {c_id}] Chain End: '{run_name}'. Output keys: {list(outputs_from_chain.keys()) if isinstance(outputs_from_chain, dict) else 'Not a dict'}")
                        if run_name == compiled_graph.name or run_name == "__graph__": # Check if it's the main graph ending
                            final_state = outputs_from_chain # The output of the graph is its final state
                            logger.info(f"[Chat {c_id}] Graph run '{run_name}' ended. Final state (output): {str(final_state)[:200]}...")
                            # final_reply_accumulator should have been built by on_chat_model_stream by now.
                            # If not, or if the graph's final output AIMessage is preferred:
                            if isinstance(final_state, dict) and "messages" in final_state and isinstance(final_state["messages"], list):
                                    for msg_state in reversed(final_state["messages"]):
                                        if isinstance(msg_state, AIMessage) and hasattr(msg_state, 'content') and msg_state.content:
                                            if not final_reply_accumulator: # If streaming yielded nothing
                                                logger.info(f"[Chat {c_id}] Using AIMessage from final graph state as fallback: {msg_state.content[:100]}...")
                                                final_reply_accumulator = msg_state.content
                                                # Stream this fallback content to the client
                                                await queue.put({"type": "token", "data": msg_state.content})
                                                stream_sent_any_token = True # Mark that we sent something
                                            elif final_reply_accumulator != msg_state.content:
                                                logger.warning(f"[Chat {c_id}] Final accumulated reply ('{final_reply_accumulator[:100]}...') differs from final graph state AIMessage ('{msg_state.content[:100]}...'). Preferring accumulated.")
                                            # After processing the first relevant AIMessage from the end of the state, we can break.
                                            break # Line 368 - Belongs to the outer if (line 362)
                    
                    elif event_name == "on_chain_error" or event_name == "on_llm_error" or event_name == "on_tool_error":
                        error_content = str(event_data.get("error", "Unknown error"))
                        logger.error(f"[Chat {c_id}] Error event '{event_name}' from '{run_name}': {error_content}")
                        is_error = True
                        stage = f"error_in_{run_name}"
                        # Try to get a more specific message from the error object if it's an exception
                        error_obj = event_data.get("error")
                        specific_error_message = str(error_obj) if error_obj else "Details not available"
                        
                        error_data = {"message": f"Error in {run_name}: {specific_error_message}", "stage": stage, "details": str(error_obj)}
                        await queue.put({"type": "error", "data": error_data})
                        # Potentially break or decide how to proceed after an error


                    # Add handling for other event types if needed (e.g., on_retriever_start/end)

        except Exception as e:
            is_error = True
            error_message = f"Error during LangGraph astream_events processing: {str(e)}"
            logger.error(f"[Chat {c_id}] {error_message}", exc_info=True)
            error_data = {"message": error_message, "stage": "graph_execution"}
            try:
                await queue.put({"type": "error", "data": error_data})
            except asyncio.QueueFull:
                logger.error(f"[Chat {c_id}] Failed to put error message in full queue after main exception.")
            except Exception as qe:
                logger.error(f"[Chat {c_id}] Failed to put error message in queue after main exception: {qe}")

        finally:
            if 'token_cv' in locals() and token_cv is not None: # Ensure token_cv was set
                current_flow_id_var.reset(token_cv)
                logger.debug(f"[Chat {c_id}] Reset current_flow_id context variable in finally block.")
            else:
                logger.debug(f"[Chat {c_id}] current_flow_id_var might not have been set, skipping reset in finally.")

            if not is_error and final_reply_accumulator:
                try:
                    with get_db_context() as db_session_final:
                        chat_service_final = ChatService(db_session_final)
                        logger.info(f"[Chat {c_id}] Saving AI assistant reply to DB: {final_reply_accumulator[:100]}...")
                        chat_service_final.add_message_to_chat(
                            chat_id=c_id,
                            role="assistant",
                            content=final_reply_accumulator
                        )
                        logger.info(f"[Chat {c_id}] AI assistant reply saved to DB successfully.")
                except Exception as save_err:
                    logger.error(f"[Chat {c_id}] Failed to save AI reply to DB: {save_err}", exc_info=True)
            elif is_error:
                logger.warning(f"[Chat {c_id}] Skipping AI reply save due to an error during processing. Error: {error_data}")
            else:
                logger.warning(f"[Chat {c_id}] Skipping save because final reply was empty or null. Accumulator content: '{final_reply_accumulator}'")
            
            try:
                logger.debug(f"[Chat {c_id}] Putting STREAM_END_SENTINEL into queue.")
                await queue.put(STREAM_END_SENTINEL)
                logger.debug(f"[Chat {c_id}] Stream end sentinel sent.")
            except asyncio.QueueFull:
                logger.error(f"[Chat {c_id}] Failed to put STREAM_END_SENTINEL in full queue.")
            except Exception as qe:
                logger.error(f"[Chat {c_id}] Failed to put STREAM_END_SENTINEL in queue: {qe}")
            
            logger.info(f"[Chat {c_id}] Background task (using astream_events) cleanup completed.")

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
        logger.warning(f"请求 chat {chat_id} 的事件流，但队列不存在或已清理")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active event stream found for chat {chat_id}. Process might not have started, has finished, or an error occurred.")

    event_queue = active_chat_queues[chat_id]
    logger.info(f"找到 chat {chat_id} 的事件队列，准备发送 SSE 事件")

    async def sse_event_sender():
        logger.debug(f"Starting SSE event sender for chat {chat_id}")
        is_first_event = True
        try:
            while True:
                event_data = await event_queue.get()
                
                if event_data is STREAM_END_SENTINEL:
                    logger.info(f"收到 chat {chat_id} 的流结束标记，发送 stream_end 事件并关闭 SSE 连接")
                    yield {
                        "event": STREAM_END_SENTINEL.get("type", "stream_end"),
                        "data": json.dumps(STREAM_END_SENTINEL.get("data", {}))
                    }
                    event_queue.task_done()
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
        except asyncio.CancelledError:
            logger.info(f"SSE event sender for chat {chat_id} was cancelled (client likely disconnected).")
            raise
        except Exception as e:
            logger.error(f"SSE event sender for chat {chat_id} 遇到未处理的错误: {e}", exc_info=True)
            try:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": f"SSE sender encountered a critical error: {str(e)}", "stage": "sse_sending_critical"})
                }
            except Exception as send_err:
                logger.error(f"在SSE发送器中为 {chat_id} 发送最终错误事件失败: {send_err}")
        finally:
            logger.info(f"SSE event sender for chat {chat_id} is cleaning up.")
            if chat_id in active_chat_queues:
                removed_queue = active_chat_queues.pop(chat_id, None)
                if removed_queue:
                    logger.info(f"已成功从 active_chat_queues 中移除 chat {chat_id} 的队列。")
            else:
                logger.warning(f"在 SSE 清理阶段，chat {chat_id} 的队列已不在 active_chat_queues 中，可能已被其他地方清理。")
            
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