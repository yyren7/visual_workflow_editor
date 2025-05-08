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
        """
        logger.debug(f"[Chat {c_id}] Background task started.")
        is_error = False
        error_data = {}
        final_reply_accumulator = "" # 用于累积最终回复
        final_state = None # 用于存储图的最终状态

        try:
            # --- 使用上下文管理器获取数据库会话 ---
            with get_db_context() as db_session_bg:
                logger.debug(f"[Chat {c_id}] Acquired DB session for background task.")
                chat_service_bg = ChatService(db_session_bg)
                flow_service_bg = FlowService(db_session_bg) # 在同一会话中创建 FlowService

                # --- 获取聊天和流程数据 ---
                chat = chat_service_bg.get_chat(c_id)
                if not chat:
                    logger.error(f"[Chat {c_id}] Background task could not find chat.")
                    await queue.put({"type": "error", "data": {"message": "Chat not found.", "stage": "setup"}})
                    return
                
                # 记录用户消息到数据库 (注意：这里的 db_session_bg 是后台任务的 session)
                # 确保在 Agent 调用前保存用户消息，以便历史记录是最新的
                logger.debug(f"[Chat {c_id}] Attempting to save user message to DB before agent call.")
                chat_service_bg.add_message_to_chat(chat_id=c_id, role="user", content=msg_content)
                logger.debug(f"[Chat {c_id}] User message saved to DB.")

                flow_id = chat.flow_id
                flow = flow_service_bg.get_flow_instance(flow_id) # 使用 get_flow_instance 获取 ORM 对象
                if not flow:
                    logger.error(f"[Chat {c_id}] Background task could not find flow {flow_id}.")
                    await queue.put({"type": "error", "data": {"message": f"Flow {flow_id} not found.", "stage": "setup"}})
                    return
                
                flow_data = flow.flow_data or {} # flow.flow_data 是流程图的具体结构
                logger.debug(f"[Chat {c_id}] Flow data for context: {str(flow_data)[:200]}...")

                # --- 获取 LangGraph Runnable ---
                logger.debug(f"[Chat {c_id}] Getting compiled LangGraph from ChatService.")
                compiled_graph = chat_service_bg.compiled_workflow_graph # ChatService 现在提供这个属性
                logger.debug(f"[Chat {c_id}] Successfully got compiled LangGraph.")

                # --- 准备 LangGraph 输入 ---
                # 从 chat.chat_data 中获取历史消息
                chat_history_raw = chat.chat_data.get("messages", [])
                
                # 格式化历史消息
                formatted_history = _format_messages_to_langchain(chat_history_raw[:-1]) # 排除当前用户输入，它将作为新的 HumanMessage

                graph_input = {
                    "messages": formatted_history + [HumanMessage(content=msg_content)], # 包含当前用户消息作为 HumanMessage
                    "input": msg_content, # AgentState 也需要 input 字段
                    "flow_context": flow_data.get("graphContextVars", {}), # 使用 graphContextVars 作为流程上下文
                    "current_flow_id": flow_id,
                }
                
                # 简化 f-string 以避免潜在的解析问题
                messages_count_val = len(graph_input["messages"])
                input_len_val = len(graph_input["input"])
                flow_id_val = graph_input["current_flow_id"]
                logger.debug(f"[Chat {c_id}] Prepared graph input: messages_count={messages_count_val}, input_len={input_len_val}, flow_id={flow_id_val}")

                # --- 调用 LangGraph astream_log ---
                logger.debug(f"[Chat {c_id}] Invoking compiled_graph.astream_log...")

                async for event in compiled_graph.astream_log(graph_input, include_names=["agent", "tools"]):
                    logger.critical(f"[Chat {c_id}] RAW EVENT OBJECT TYPE: {type(event).__name__}")
                    # logger.critical(f"[Chat {c_id}] RAW EVENT OBJECT DIR: {dir(event)}") # Potentially verbose

                    processed_op_in_event = False # Flag to see if any op in event.ops was processed

                    if hasattr(event, 'ops') and isinstance(event.ops, list):
                        logger.debug(f"[Chat {c_id}] Event has 'ops' attribute (list of {len(event.ops)} operations). Iterating...")
                        for op_item_idx, op_item in enumerate(event.ops):
                            if not isinstance(op_item, dict):
                                logger.warning(f"[Chat {c_id}] op_item {op_item_idx} is not a dict, skipping: {op_item}")
                                continue

                            op_from_ops = op_item.get('op')
                            path_from_ops = op_item.get('path')
                            value_from_ops = op_item.get('value')
                            logger.debug(f"[Chat {c_id}] Op item {op_item_idx} --- Op: {op_from_ops}, Path: {path_from_ops}, ValueType: {type(value_from_ops).__name__}")

                            if op_from_ops in ['add', 'replace']:
                                processed_op_in_event = True # Mark that we are processing an op
                                target_paths = ("/logs/agent/final_output", "/logs/agent/streamed_output/", "/streamed_output/", "/final_output")
                                if path_from_ops and path_from_ops.startswith(target_paths):
                                    logger.debug(f"[Chat {c_id}] Path matched from ops: {path_from_ops}. ValueType: {type(value_from_ops).__name__}")
                                    patch_value = value_from_ops # Use the value from the current op_item

                                    if isinstance(patch_value, dict) and "messages" in patch_value and isinstance(patch_value.get("messages"), list):
                                        logger.debug(f"[Chat {c_id}] Op value has 'messages' list.")
                                        for i, msg_item in enumerate(patch_value["messages"]):
                                            logger.debug(f"[Chat {c_id}] Checking message item {i} in op_value['messages'], type: {type(msg_item).__name__}")
                                            if isinstance(msg_item, AIMessage) and hasattr(msg_item, 'content') and msg_item.content:
                                                logger.info(f"[Chat {c_id}] Extracted AIMessage from ops (path: {path_from_ops}, direct): {msg_item.content[:100]}...")
                                                final_reply_accumulator = msg_item.content
                                                await queue.put({"type": "token", "data": final_reply_accumulator})
                                    elif isinstance(patch_value, dict) and "agent" in patch_value and isinstance(patch_value.get("agent"), dict) and "messages" in patch_value["agent"] and isinstance(patch_value["agent"].get("messages"), list):
                                        logger.debug(f"[Chat {c_id}] Op value has 'agent' with 'messages' list.")
                                        agent_messages = patch_value["agent"]["messages"]
                                        for i, msg_item in enumerate(agent_messages):
                                            logger.debug(f"[Chat {c_id}] Checking message item {i} in op_value['agent']['messages'], type: {type(msg_item).__name__}")
                                            if isinstance(msg_item, AIMessage) and hasattr(msg_item, 'content') and msg_item.content:
                                                logger.info(f"[Chat {c_id}] Extracted AIMessage from ops (path: {path_from_ops}, nested): {msg_item.content[:100]}...")
                                                final_reply_accumulator = msg_item.content
                                                await queue.put({"type": "token", "data": final_reply_accumulator})
                                    else:
                                        logger.debug(f"[Chat {c_id}] Path {path_from_ops} matched from ops, but value structure for messages not recognized.")
                                else:
                                     logger.debug(f"[Chat {c_id}] Path {path_from_ops} from ops did NOT match target paths for AIMessage extraction.")
                            # else: logger.debug(f"[Chat {c_id}] Op type {op_from_ops} is not add/replace or path is None.")
                    # Standard LangChain events (if event was not a RunLogPatch with ops or ops processing didn't set accumulator)
                    # These usually have event.event and event.data if event itself has these attrs and is not a dict
                    elif hasattr(event, 'event') and hasattr(event, 'data'):
                        event_type_from_attr = event.event
                        data_from_attr = event.data # This is event.data directly
                        logger.debug(f"[Chat {c_id}] Processing as Standard Event --- Type: {event_type_from_attr}")
                        processed_op_in_event = True # Mark that we are processing this event type

                        if event_type_from_attr == "on_chat_model_stream":
                            # Ensure data_from_attr is a dictionary for these standard events for .get() usage
                            chunk_data = data_from_attr if isinstance(data_from_attr, dict) else {}
                            chunk = chunk_data.get("chunk")
                            if chunk and hasattr(chunk, 'content') and chunk.content:
                                token = chunk.content
                                if isinstance(token, str):
                                    # ... (rest of on_chat_model_stream logic, using token and final_reply_accumulator) ...
                                    logger.debug(f"[Chat {c_id}] Stream token: '{token[:50]}...'. Current accumulator: '{final_reply_accumulator[:30]}...'")
                                    is_json_action = '"action": "final_answer"' in token
                                    if not final_reply_accumulator or is_json_action:
                                        if is_json_action:
                                            logger.info(f"[Chat {c_id}] JSON action in stream, attempting parse to override accumulator.")
                                            try:
                                                import re; import json
                                                json_match = re.search(r'({.*"action":\s*"final_answer".*})', token, re.DOTALL)
                                                if json_match:
                                                    json_str = json_match.group(1); json_str = re.sub(r'```json|```', '', json_str).strip()
                                                    parsed = json.loads(json_str)
                                                    if "action_input" in parsed:
                                                        final_reply_accumulator = parsed.get("action_input", "")
                                                        logger.info(f"[Chat {c_id}] Accumulator OVERRIDDEN by JSON in stream: {final_reply_accumulator[:50]}...")
                                            except Exception as e_json:
                                                logger.error(f"[Chat {c_id}] Error parsing JSON from stream for override: {e_json}", exc_info=True)
                                                if not final_reply_accumulator: # Fallback: if parse fails and accumulator was empty, append the raw token.
                                                    final_reply_accumulator += token 
                                        else: 
                                            if not final_reply_accumulator : 
                                                final_reply_accumulator += token
                                    await queue.put({"type": "token", "data": token})

                        elif event_type_from_attr == "on_chat_model_end":
                            message_data = data_from_attr if isinstance(data_from_attr, dict) else {}
                            message = message_data.get("message")
                            if isinstance(message, AIMessage) and hasattr(message, 'content') and message.content:
                                logger.info(f"[Chat {c_id}] AIMessage from on_chat_model_end: {message.content[:100]}...")
                                final_reply_accumulator = message.content 
                        
                        elif event_type_from_attr == "on_tool_start":
                            tool_data = data_from_attr if isinstance(data_from_attr, dict) else {}
                            tool_name = tool_data.get("name")
                            tool_input_raw = tool_data.get("input")
                            # ... (tool start logic) ...
                            try:
                                tool_input_str = json.dumps(tool_input_raw, ensure_ascii=False)
                            except TypeError:
                                tool_input_str = str(tool_input_raw)
                            if tool_name:
                                logger.info(f"[Chat {c_id}] Tool Start: {tool_name} with input: {tool_input_str[:100]}...")
                                await queue.put({"type": "tool_start", "data": {"name": tool_name, "input": tool_input_raw}})
                        
                        elif event_type_from_attr == "on_tool_end":
                            tool_data = data_from_attr if isinstance(data_from_attr, dict) else {}
                            tool_name = tool_data.get("name")
                            output_raw = tool_data.get("output")
                            # ... (tool end logic) ...
                            output_summary = str(output_raw)
                            if isinstance(output_raw, dict) and "message" in output_raw:
                                output_summary = output_raw["message"]
                                # ... (message formatting)
                            if tool_name:
                                logger.info(f"[Chat {c_id}] Tool End: ({tool_name}) with output summary: {output_summary[:100]}...")
                                await queue.put({"type": "tool_end", "data": {"name": tool_name, "output_summary": output_summary}})
                        
                        # Potentially other standard event types like on_chain_end, on_retriever_end etc.
                        elif hasattr(event, 'name') and event.name == "__graph__" and event_type_from_attr == "on_chain_end":
                            final_output_data = data_from_attr if isinstance(data_from_attr, dict) else {}
                            output_final_graph = final_output_data.get("output")
                            if isinstance(output_final_graph, dict):
                                final_state = output_final_graph
                                logger.info(f"[Chat {c_id}] Captured final graph state from on_chain_end: {str(final_state)[:200]}...")
                                if not final_reply_accumulator and "messages" in final_state and isinstance(final_state["messages"], list):
                                    for msg_state in reversed(final_state["messages"]):
                                        if isinstance(msg_state, AIMessage) and hasattr(msg_state, 'content') and msg_state.content:
                                            logger.info(f"[Chat {c_id}] AIMessage from final graph state (fallback): {msg_state.content[:100]}...")
                                            final_reply_accumulator = msg_state.content
                                            break
                    else: # If not a RunLogPatch with ops, and not a standard event with event/data attributes
                        if not processed_op_in_event: # Only log if no op inside event.ops was processed either
                            logger.warning(f"[Chat {c_id}] Unrecognized event structure. TYPE: {type(event).__name__}, has_ops: {hasattr(event, 'ops')}, has_event_attr: {hasattr(event, 'event')}. Event obj: {str(event)[:300]}...")

                    # End of the primary try for event processing
                    # except Exception as event_error: # This was moved one level up in original code
                    #    logger.error(f"[Chat {c_id}] Error processing individual event/op_item: {str(event_error)}", exc_info=True)
            
            # This was the original location of the broad exception handler for the whole async for loop
            # It has been moved inside the loop to handle errors per event/op_item if necessary,
            # but a general one here might still be useful if the iterator itself fails.
            # For now, individual event processing errors are logged inside the loop.

        except Exception as e: # This catches errors in the async for loop setup or unhandled errors within an iteration
            is_error = True
            error_message = f"Error processing chat message: {str(e)}"
            logger.error(f"[Chat {c_id}] {error_message}", exc_info=True)
            # 尝试确定错误阶段
            stage = "unknown" # 默认
            error_data = {"message": error_message, "stage": stage}
            try:
                await queue.put({"type": "error", "data": error_data})
            except asyncio.QueueFull:
                logger.error(f"[Chat {c_id}] Failed to put error message in full queue.")
            except Exception as qe:
                logger.error(f"[Chat {c_id}] Failed to put error message in queue: {qe}")

        finally:
            # --- Reset the context variable (important!) ---
            current_flow_id_var.set(None)
            logger.debug(f"[Chat {c_id}] Reset current_flow_id context variable.")
            
            # --- 保存AI回复到数据库 ---
            if not is_error and final_reply_accumulator: # 只有在没有错误且回复非空时才保存
                try:
                    # 重新获取数据库会话，因为之前的会话可能已关闭
                    # 注意：如果在同一个 try/finally 块的早期部分 db_session_bg 仍然有效且未关闭，
                    # 并且没有发生可能使其失效的异常，理论上可以直接使用 chat_service_bg。
                    # 但为了更安全，尤其是在复杂的异步和异常处理中，使用新的上下文获取会话更稳妥。
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
            else: # final_reply_accumulator is empty or null
                logger.warning(f"[Chat {c_id}] Skipping save because final reply was empty or null. Accumulator content: '{final_reply_accumulator}'")
            
            # --- 发送流结束标记 --- 
            try:
                logger.debug(f"[Chat {c_id}] Putting STREAM_END_SENTINEL into queue.")
                await queue.put(STREAM_END_SENTINEL)
                logger.debug(f"[Chat {c_id}] Stream end sentinel sent.")
            except asyncio.QueueFull:
                logger.error(f"[Chat {c_id}] Failed to put STREAM_END_SENTINEL in full queue.")
            except Exception as qe:
                logger.error(f"[Chat {c_id}] Failed to put STREAM_END_SENTINEL in queue: {qe}")
            
            # --- 清理资源 ---
            logger.info(f"[Chat {c_id}] Background task cleanup completed.")
            # 注意：我们不在这里从active_chat_queues中移除队列
            # 因为那应该在sse_event_sender的finally块中完成，当所有事件被发送后

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

    async def sse_event_sender():
        """
        异步生成器，从队列中获取事件并格式化为 SSE。
        """
        logger.debug(f"Starting SSE event sender for chat {chat_id}")
        is_first_event = True
        try:
            while True:
                event_data = await event_queue.get()
                
                # 检查是否是结束标记
                if event_data is STREAM_END_SENTINEL:
                    logger.info(f"收到 chat {chat_id} 的流结束标记，发送 stream_end 事件并关闭 SSE 连接")
                    # 先发送 stream_end 事件
                    yield {
                        "event": STREAM_END_SENTINEL.get("type", "stream_end"),
                        "data": json.dumps(STREAM_END_SENTINEL.get("data", {}))
                    }
                    event_queue.task_done() # 标记处理完成
                    break # 然后结束循环

                # 确保 event_data 是字典，包含 'type' 和 'data'
                if isinstance(event_data, dict) and "type" in event_data and "data" in event_data:
                    event_type = event_data.get("type", "message")
                    data_payload = event_data.get("data", {})
                    
                    # 根据数据类型决定是否需要 json.dumps
                    if isinstance(data_payload, str): 
                        # 对于 token 等简单字符串，直接发送
                        formatted_data = data_payload
                    else:
                        # 对于字典等复杂类型，进行 json.dumps
                        try:
                            formatted_data = json.dumps(data_payload)
                        except TypeError:
                            logger.error(f"序列化事件数据为 JSON 失败 (type: {event_type}, chat: {chat_id})", exc_info=True)
                            # 发送一个错误事件替代
                            event_type = "error"
                            formatted_data = json.dumps({"message": f"Failed to serialize event data for type {event_type}", "stage": "sse_formatting"})

                    if is_first_event:
                        logger.info(f"已发送第一个 SSE 事件 (type: {event_type}) 到 chat {chat_id} 的监听者")
                        is_first_event = False
                        
                    # logger.debug(f"Sending SSE event: type={event_type}, data={formatted_data}") # 调试时取消注释
                    yield {
                        "event": event_type,
                        "data": formatted_data # 发送已格式化的数据
                    }
                else:
                    logger.warning(f"Invalid event data format received for chat {chat_id}: {event_data}")

                event_queue.task_done()

        except asyncio.CancelledError:
            logger.info(f"SSE 事件发送器 for chat {chat_id} 被取消")
            # 可以在这里进行清理工作，但通常由 finally 处理
        except Exception as e:
            logger.error(f"SSE 事件发送器 for chat {chat_id} 发生错误: {e}", exc_info=True)
        finally:
            logger.info(f"SSE 事件发送器完成或终止 for chat {chat_id}")
            # 从 active_chat_queues 中移除队列，避免内存泄漏
            if chat_id in active_chat_queues:
                # 确保队列为空，防止未处理的任务
                # while not event_queue.empty():
                #     try:
                #         event_queue.get_nowait()
                #         event_queue.task_done()
                #     except asyncio.QueueEmpty:
                #         break
                #     except Exception as eqe:
                #         logger.warning(f"Error emptying queue during finally block for chat {chat_id}: {eqe}")
                del active_chat_queues[chat_id]
                logger.info(f"已移除 chat {chat_id} 的事件队列")

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