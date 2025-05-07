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
                    logger.debug(f"[Chat {c_id}] Received event from graph: {event}")
                    
                    # 简化的事件处理逻辑 - 统一处理字典格式事件
                    try:
                        # 确保事件是字典类型
                        event_dict = event if isinstance(event, dict) else event.__dict__
                        
                        # 获取事件类型
                        event_type = event_dict.get("event")
                        
                        if event_type == "on_chat_model_stream":
                            # 处理流式token
                            data = event_dict.get("data", {})
                            chunk = data.get("chunk")
                            if chunk and hasattr(chunk, 'content') and chunk.content:
                                token = chunk.content
                                if isinstance(token, str):
                                    # 添加更多日志
                                    logger.debug(f"[Chat {c_id}] Received token: {token[:30]}...")
                                    
                                    # 处理可能的完整JSON格式
                                    if '```json' in token and '"action": "final_answer"' in token and '"action_input":' in token:
                                        logger.info(f"[Chat {c_id}] 检测到完整JSON格式回复，准备提取")
                                        try:
                                            # 尝试提取JSON内容
                                            import re
                                            import json
                                            # 使用更健壮的正则表达式提取JSON部分
                                            json_match = re.search(r'({.*"action":\s*"final_answer".*})', token, re.DOTALL)
                                            if json_match:
                                                json_str = json_match.group(1)
                                                # 清理可能的额外字符
                                                json_str = re.sub(r'```json|```', '', json_str).strip()
                                                # 解析JSON
                                                try:
                                                    parsed = json.loads(json_str)
                                                    if "action_input" in parsed:
                                                        # 替换整个最终累积的回复
                                                        extracted_content = parsed.get("action_input", "")
                                                        logger.info(f"[Chat {c_id}] 成功从JSON提取内容: {extracted_content[:50]}...")
                                                        # 替换累积的回复
                                                        final_reply_accumulator = extracted_content
                                                        # 发送提取的内容作为token
                                                        await queue.put({"type": "token", "data": extracted_content})
                                                        # 继续处理下一个事件
                                                        continue
                                                except json.JSONDecodeError as je:
                                                    logger.warning(f"[Chat {c_id}] JSON解析错误: {je}, 将尝试正则提取内容")
                                                    # 尝试直接用正则表达式提取action_input内容
                                                    action_input_match = re.search(r'"action_input":\s*"([^"]*)"', json_str)
                                                    if action_input_match:
                                                        extracted_content = action_input_match.group(1)
                                                        logger.info(f"[Chat {c_id}] 通过正则提取内容: {extracted_content[:50]}...")
                                                        # 替换累积的回复
                                                        final_reply_accumulator = extracted_content
                                                        # 发送提取的内容作为token
                                                        await queue.put({"type": "token", "data": extracted_content})
                                                        # 继续处理下一个事件
                                                        continue
                                        except Exception as e:
                                            logger.error(f"[Chat {c_id}] 解析JSON失败: {str(e)}", exc_info=True)
                                    
                                    # 对于普通token或者提取失败的情况，继续累积
                                    await queue.put({"type": "token", "data": token})
                                    final_reply_accumulator += token
                        
                        elif event_type == "on_tool_start":
                            # 处理工具开始事件
                            data = event_dict.get("data", {})
                            tool_name = data.get("name")
                            tool_input_raw = data.get("input")
                            
                            # 尝试序列化输入
                            try:
                                tool_input_str = json.dumps(tool_input_raw, ensure_ascii=False)
                            except TypeError:
                                tool_input_str = str(tool_input_raw)
                                
                            if tool_name:
                                logger.info(f"[Chat {c_id}] Tool Start: {tool_name} with input: {tool_input_str[:100]}...")
                                await queue.put({"type": "tool_start", "data": {"name": tool_name, "input": tool_input_raw}})
                        
                        elif event_type == "on_tool_end":
                            # 处理工具结束事件
                            data = event_dict.get("data", {})
                            tool_name = data.get("name")
                            output_raw = data.get("output")
                            
                            # 确保输出摘要是字符串
                            output_summary = str(output_raw)
                            
                            # 特殊处理工具返回的字典
                            if isinstance(output_raw, dict) and "message" in output_raw:
                                output_summary = output_raw["message"]
                                if "node_data" in output_raw and isinstance(output_raw["node_data"], dict):
                                    node_label = output_raw['node_data'].get('label') or output_raw['node_data'].get('id', '')
                                    output_summary += f" (Details: {node_label})"
                                elif "data" in output_raw:
                                    if isinstance(output_raw["data"], dict) and "text" in output_raw["data"]:
                                        text_sample = output_raw['data']['text'][:50]
                                        output_summary += f" (Generated Text: {text_sample}...)"
                                    elif isinstance(output_raw["data"], str):
                                        data_sample = output_raw['data'][:50]
                                        output_summary += f" (Data: {data_sample}...)"
                            
                            if tool_name:
                                logger.info(f"[Chat {c_id}] Tool End: ({tool_name}) with output summary: {output_summary[:100]}...")
                                await queue.put({"type": "tool_end", "data": {"name": tool_name, "output_summary": output_summary}})
                        
                        # 新增: 处理模型生成结束事件
                        elif event_type == "on_chat_model_end":
                            logger.info(f"[Chat {c_id}] 检测到模型回复结束事件")
                            # 尝试从完整消息中提取内容
                            try:
                                data = event_dict.get("data", {})
                                # 尝试获取最终生成的消息
                                message = data.get("message")
                                if message and hasattr(message, "content"):
                                    message_content = message.content
                                    logger.info(f"[Chat {c_id}] 从on_chat_model_end获取到完整消息: {message_content[:100]}...")
                                    
                                    # 如果消息包含JSON格式，尝试提取
                                    if '```json' in message_content or '"action": "final_answer"' in message_content:
                                        import re
                                        import json
                                        # 清理可能的markdown代码块
                                        clean_content = re.sub(r'```json|```', '', message_content).strip()
                                        # 提取JSON对象
                                        json_match = re.search(r'({.*"action".*:.*"final_answer".*})', clean_content, re.DOTALL)
                                        if json_match:
                                            json_str = json_match.group(1)
                                            try:
                                                parsed = json.loads(json_str)
                                                if "action_input" in parsed:
                                                    extracted_content = parsed.get("action_input", "")
                                                    logger.info(f"[Chat {c_id}] 从模型结束事件提取内容: {extracted_content[:50]}...")
                                                    # 替换累积的回复
                                                    final_reply_accumulator = extracted_content
                                            except Exception as je:
                                                logger.warning(f"[Chat {c_id}] 解析模型结束事件中的JSON失败: {je}")
                            except Exception as e:
                                logger.error(f"[Chat {c_id}] 处理模型结束事件失败: {str(e)}", exc_info=True)
                                
                        # 检查是否是最终状态
                        if event_type == "end" and event_dict.get("name") == "__graph__":
                            data = event_dict.get("data", {})
                            if isinstance(data.get("output"), dict):
                                final_state = data["output"]
                                logger.info(f"[Chat {c_id}] Captured final graph state: {str(final_state)[:200]}...")
                        
                    except Exception as event_error:
                        logger.error(f"[Chat {c_id}] Error processing event: {str(event_error)}", exc_info=True)

        except Exception as e:
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
            
            # --- 数据库保存逻辑 ---
            if not is_error and final_reply_accumulator:
                try:
                    # 检查最终回复中是否包含JSON格式（可能是流式传输未成功解析的情况）
                    logger.info(f"[Chat {c_id}] 保存前检查最终回复: 长度={len(final_reply_accumulator)}, 前50字符: {final_reply_accumulator[:50]}")
                    
                    # 如果回复仍然包含完整的JSON格式，尝试再次提取
                    if '```json' in final_reply_accumulator and '"action": "final_answer"' in final_reply_accumulator:
                        logger.info(f"[Chat {c_id}] 最终回复仍包含JSON格式，尝试最后一次提取")
                        try:
                            import re
                            import json
                            # 提取JSON部分
                            clean_content = re.sub(r'```json|```', '', final_reply_accumulator).strip()
                            json_match = re.search(r'({.*"action".*:.*"final_answer".*})', clean_content, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(1)
                                parsed = json.loads(json_str)
                                if "action_input" in parsed:
                                    extracted_content = parsed.get("action_input", "")
                                    if extracted_content:
                                        logger.info(f"[Chat {c_id}] 保存前成功提取JSON内容: {extracted_content[:50]}...")
                                        final_reply_accumulator = extracted_content
                        except Exception as e:
                            logger.error(f"[Chat {c_id}] 保存前解析JSON失败: {str(e)}", exc_info=True)
                    
                    # 使用新的独立数据库 Session 进行保存
                    logger.info(f"[Chat {c_id}] Attempting to save messages using new DB session. 最终回复长度: {len(final_reply_accumulator)}")
                    with get_db_context() as db_session_for_save:
                        chat_service_for_save = ChatService(db_session_for_save)
                        flow_service_for_save = FlowService(db_session_for_save)
                       
                        # --- 先保存用户消息 ---
                        logger.info(f"[Chat {c_id}] Attempting to save user message (length: {len(msg_content)})...")
                        user_save_success = chat_service_for_save.add_message_to_chat(
                            chat_id=c_id,
                            role="user",
                            content=msg_content
                        )
                        if not user_save_success:
                            logger.error(f"[Chat {c_id}] Failed to save user message in finally block.")
                        else:
                            logger.info(f"[Chat {c_id}] User message saved to DB.")
                       
                        # 再保存助手消息
                        logger.info(f"[Chat {c_id}] Attempting to save assistant message (length: {len(final_reply_accumulator)})...")
                        final_message_content = final_reply_accumulator
                        assistant_save_success = chat_service_for_save.add_message_to_chat(
                            chat_id=c_id,
                            role="assistant",
                            content=final_message_content
                        )
                        if assistant_save_success:
                            logger.info(f"[Chat {c_id}] Assistant message saved to DB.")
                        else:
                            logger.warning(f"[Chat {c_id}] Failed to save assistant message.")

                        # 从最终状态获取 flow_context (如果它被图修改了)
                        final_flow_context_to_save = None
                        if final_state and isinstance(final_state, dict) and "flow_context" in final_state:
                            final_flow_context_candidate = final_state.get("flow_context")
                            if isinstance(final_flow_context_candidate, dict):
                                final_flow_context_to_save = final_flow_context_candidate
                                logger.info(f"[Chat {c_id}] Extracted final_flow_context from graph state for saving: {str(final_flow_context_to_save)[:100]}...")
                            else:
                                logger.warning(f"[Chat {c_id}] final_state['flow_context'] is not a dict type: {type(final_flow_context_candidate)}. Will not update flow.")

                        # 如果 flow_context 被修改了，则更新 Flow 对象
                        if final_flow_context_to_save is not None: 
                            flow_to_update = flow_service_for_save.get_flow_instance(flow_id)
                            if flow_to_update:
                                current_flow_model_data = flow_to_update.flow_data or {}
                                current_flow_model_data["graphContextVars"] = final_flow_context_to_save
                                flow_to_update.flow_data = current_flow_model_data
                                db_session_for_save.add(flow_to_update)
                                db_session_for_save.commit()
                                logger.info(f"[Chat {c_id}] Successfully updated Flow {flow_id} with new graphContextVars in finally block.")
                            else:
                                logger.error(f"[Chat {c_id}] Could not find Flow {flow_id} in finally block for graphContextVars update.")
                except Exception as save_err:
                    logger.error(f"[Chat {c_id}] Failed to save messages or flow data in finally block: {save_err}", exc_info=True)
            elif is_error:
                logger.warning(f"[Chat {c_id}] Skipping save due to error during agent execution. Error data: {error_data}")
            else:
                logger.warning(f"[Chat {c_id}] Skipping save because final reply was empty or null.")
            
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