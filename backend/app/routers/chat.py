from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio # 确保导入 asyncio
from collections import defaultdict # 导入 defaultdict
from backend.langchainchat.context import current_flow_id_var # <--- Import context variable

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
        后台任务：处理新消息，使用 Agent Executor 生成回复，并将事件放入队列。
        """
        logger.debug(f"[Chat {c_id}] Background task started.")
        is_error = False
        error_data = {}
        final_reply_accumulator = "" # 用于累积最终回复

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

                flow_id = chat.flow_id
                # --- Set the context variable --- 
                current_flow_id_var.set(flow_id) # <--- Set context variable here
                logger.debug(f"[Chat {c_id}] Set current_flow_id context variable to: {flow_id}")
                # --------------------------------

                flow = flow_service_bg.get_flow_instance(flow_id) # 获取 Flow 实例
                if not flow:
                     logger.error(f"[Chat {c_id}] Background task could not find flow {flow_id}.")
                     await queue.put({"type": "error", "data": {"message": f"Flow {flow_id} not found.", "stage": "setup"}})
                     return

                current_messages = chat.chat_data.get('messages', [])
                # --- 将原始消息格式转换为 LangChain BaseMessage 对象 ---
                # 移除旧的、错误的导入
                # from backend.langchainchat.memory.db_chat_memory import messages_to_langchain # 导入转换函数
                langchain_history = _format_messages_to_langchain(current_messages) # 使用新的辅助函数
                # ----------------------------------------------------
                flow_data = flow.flow_data # 获取流程图数据

                logger.info(f"[Chat {c_id}] Processing message with {len(langchain_history)} history entries.")
                agent_executor = chat_service_bg.workflow_agent_executor

                # 构建 Agent 输入字典
                agent_input = {
                    "input": msg_content,
                    "chat_history": langchain_history,
                    "flow_context": flow_data,
                    # "flow_id": flow_id # Optional: Keep or remove, tools won't use it directly
                }
                logger.info(f"[Chat {c_id}] Prepared agent input: keys={list(agent_input.keys())}")

                # 使用 astream_events 处理流式响应，并提供所有必需的输入键
                logger.debug(f"[Chat {c_id}] Invoking agent_executor.astream_log with input keys: {list(agent_input.keys())}")

                # --- 使用 astream_log 处理流式响应 --- (新逻辑)
                async for log_entry in agent_executor.astream_log(agent_input): # 移除 include_metadata=True
                    # log_entry 是一个 LogEntry 对象，包含 ops 列表
                    # 我们需要解析 ops 来理解发生了什么
                    # logger.debug(f"[Chat {c_id}] Received log entry: {log_entry}") # 调试时取消注释

                    # 遍历 log_entry 中的操作 (ops)
                    for op in log_entry.ops:
                        # --- 在这里添加详细日志 ---
                        logger.debug(f"[Chat {c_id}] Raw log entry op: {op}")
                        # --------------------------
                        op_path = op.get("path", "") # 获取操作路径

                        # 1. 检测 LLM Token 输出 (需要根据实际输出调整路径判断)
                        # 示例路径: '/logs/ChatOpenAI/streamed_output_str/-' 或 '/logs/RunnableSequence/streamed_output_str/-'
                        # 或者检查 op['op'] == 'add' 且路径包含 'streamed_output_str'
                        if "streamed_output_str" in op_path and op["op"] == "add":
                            token = op.get("value", "")
                            if isinstance(token, str):
                                # logger.debug(f"[Chat {c_id}] LLM Token: {token}")
                                await queue.put({"type": "token", "data": token})
                                # *** 将 token 累积到 final_reply_accumulator ***
                                final_reply_accumulator += token
                                # logger.debug(f"[Chat {c_id}] Accumulated reply length: {len(final_reply_accumulator)}") # Optional debug log
                                # -----------------------------------------------
                                # TODO: 需要区分思考过程的 token 和最终答案的 token 吗？
                                # 目前先将所有 token 都发送，并在循环外累积最终答案
                                # 如果 agent runnable 最后一块是最终答案，可以尝试在这里累积
                                # (但 astream_log 不保证最后一定是答案的 token)
                                # *** 临时累积方案：假设最终答案是连续的 token 流 ***
                                # 需要找到更好的方式判断是否为最终答案的 token
                                # 例如，检查是否在某个特定的最终步骤下
                                # if op_path.startswith("/logs/FinalAnswerRunnable"): # 假设的路径
                                # pass # 仅发送 token，不在此累加 # <--- REMOVED pass

                        # 2. 检测工具调用开始 (需要根据实际输出调整路径判断)
                        # 示例路径: '/logs/AgentExecutor/tool_calls/-' or '/logs/MyAgent/tool_calls/-'
                        # 或者检查 op['op'] == 'add' 且路径包含 'tool_calls'
                        # Langchain AgentExecutor 通常在 /logs/AgentExecutor/iterations/.../tool_invocation 下
                        # 需要找到可靠的路径来提取 tool_name 和 tool_input
                        # 这是一个可能的路径，需要根据实际情况调整
                        if op_path.endswith("/tool_invocation") and op["op"] == "add": # 假设这是工具调用的开始
                            tool_call_data = op.get("value")
                            if isinstance(tool_call_data, dict):
                                 tool_name = tool_call_data.get("tool_name") # 可能需要调整key
                                 tool_input = tool_call_data.get("tool_input") # 可能需要调整key
                                 if tool_name and tool_input is not None:
                                     logger.info(f"[Chat {c_id}] Tool Start: {tool_name} with input: {tool_input}")
                                     await queue.put({"type": "tool_start", "data": {"name": tool_name, "input": tool_input}})
                                     # --- 将工具开始信息追加到累加器 ---
                                     # try:
                                     #     input_str = json.dumps(tool_input, ensure_ascii=False, indent=2)
                                     # except TypeError:
                                     #     input_str = str(tool_input)
                                     # tool_start_md = f"\\n\\n**[Tool Start: {tool_name}]**\\n*Input:*\\n```json\\n{input_str}\\n```\\n*Status: Running...*\\n\"
                                     # final_reply_accumulator += tool_start_md
                                     # ----------------------------------
                                 else:
                                     logger.warning(f"[Chat {c_id}] Could not extract tool_name/tool_input from tool_invocation op: {tool_call_data}")


                        # 3. 检测工具调用结束/结果 (需要根据实际输出调整路径判断)
                        # 示例路径: '/logs/AgentExecutor/tool_result' or '/logs/ToolExecutor/final_output'
                        # Langchain AgentExecutor 通常在 /logs/AgentExecutor/iterations/.../tool_result 下
                        # 需要找到可靠的路径来提取 tool_name 和 output_summary
                        if op_path.endswith("/tool_result") and op["op"] == "add":
                            tool_result_data = op.get("value")
                            if isinstance(tool_result_data, dict):
                                tool_name = tool_result_data.get("tool_name") # TODO: 如何可靠获取?
                                output_raw = tool_result_data.get("tool_output") # 可能需要调整key
                                if output_raw is not None:
                                    output_summary = str(output_raw) # 简单转为字符串作为摘要
                                    tool_name_or_unknown = tool_name or "Unknown Tool"
                                    logger.info(f"[Chat {c_id}] Tool End: ({tool_name_or_unknown}) with output summary: {output_summary[:100]}...")
                                    await queue.put({"type": "tool_end", "data": {"name": tool_name_or_unknown, "output_summary": output_summary}})
                                    # --- 将工具结束信息追加到累加器 ---
                                    # tool_end_md = f"\\n**[Tool End: {tool_name_or_unknown}]**\\n*Status: Completed*\\n*Output Summary:*\\n```\\n{output_summary}\\n```\\n\\n\"
                                    # final_reply_accumulator += tool_end_md
                                    # ----------------------------------
                                else:
                                     logger.warning(f"[Chat {c_id}] Could not extract tool_output from tool_result op: {tool_result_data}")


                        # 4. 尝试从最终输出块获取完整回复 (需要根据 Agent 实现调整)
                        # LangChain AgentExecutor 通常将最终输出放在 run['output'] 中
                        # 在 astream_log 中，可能是在某个特定的 op_path 下，例如 '/final_output' 或根路径的 'replace' 操作
                        # *** 注意：之前的累积 token 方式可能不准确，应依赖这里的逻辑 ***
                        if op_path == "/final_output" and op["op"] == "replace": # 这是一个假设的路径
                           final_output_value = op.get("value")
                           if isinstance(final_output_value, dict) and "output" in final_output_value:
                               final_reply_accumulator = final_output_value["output"] # 覆盖累积结果
                               logger.info(f"[Chat {c_id}] Got final reply from final_output op: {final_reply_accumulator}")
                               # 停止累积 token? 还是让 token 流继续完成?
                        # 移除错误地访问 log_entry.state 的逻辑
                        # elif op_path == "" and op["op"] == "replace" and "final_output" in log_entry.state: # 另一种可能的最终输出信号
                        #    final_output_state = log_entry.state.get("final_output")
                        #    if isinstance(final_output_state, dict) and "output" in final_output_state:
                        #        final_reply_accumulator = final_output_state["output"] # 覆盖累积结果
                        #        logger.info(f"[Chat {c_id}] Got final reply from root replace op state: {final_reply_accumulator}")

        except Exception as e:
            is_error = True
            error_message = f"Error processing chat message: {str(e)}"
            logger.error(f"[Chat {c_id}] {error_message}", exc_info=True)
            # 尝试确定错误阶段
            stage = "unknown" # 默认
            # TODO: 根据异常类型或发生位置判断 stage ('llm', 'tool', 'parsing', 'agent')
            # 例如: if isinstance(e, LLMError): stage = 'llm'
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
            # ----------------------------------------------
            logger.debug(f"[Chat {c_id}] Background task finally block reached. Is error: {is_error}")
            # --- 数据库保存逻辑 (步骤 3 - 修正结构) ---
            if not is_error and final_reply_accumulator:
                try: # <-- TRY block starts here
                    # 使用新的独立数据库 Session 进行保存
                    logger.info(f"[Chat {c_id}] Attempting to save messages using new DB session.")
                    with get_db_context() as db_session_for_save:
                       chat_service_for_save = ChatService(db_session_for_save)
                       
                       # --- 先保存用户消息 ---
                       logger.info(f"[Chat {c_id}] Attempting to save user message (length: {len(msg_content)})...")
                       user_save_success = chat_service_for_save.add_message_to_chat(
                           chat_id=c_id,
                           role="user",
                           content=msg_content
                       )
                       if not user_save_success:
                            logger.error(f"[Chat {c_id}] Failed to save user message in finally block.")
                            # Decide whether to proceed with saving assistant message or raise error
                       else:
                            logger.info(f"[Chat {c_id}] User message saved to DB.")
                       # -----------------------

                       # TODO: 获取 Agent 执行后最终的 flow_data (如果 Agent 修改了它)
                       # final_flow_data = agent_executor.get_final_flow_data() # 假设有这样的方法

                       # 再保存助手消息
                       logger.info(f"[Chat {c_id}] Attempting to save assistant message (length: {len(final_reply_accumulator)})...")
                       assistant_save_success = chat_service_for_save.add_message_to_chat(
                           chat_id=c_id,
                           role="assistant",
                           content=final_reply_accumulator
                       )
                       if not assistant_save_success:
                           logger.error(f"[Chat {c_id}] Failed to save assistant message in finally block.")
                       else:
                            logger.info(f"[Chat {c_id}] Assistant message saved to DB.")
                       # TODO: Add flow update logic if needed
                except Exception as save_err: # <-- EXCEPT block corresponding to the TRY above
                    logger.error(f"[Chat {c_id}] Failed to save messages or flow data in finally block: {save_err}", exc_info=True)
            elif is_error:
                # 考虑是否要将错误信息保存到聊天记录中？
                logger.warning(f"[Chat {c_id}] Skipping save due to error during agent execution. Error data: {error_data}")
                # 可以在这里用新 session 保存一条 system 错误消息
                # try:
                #     with get_db_context() as db_session_for_error_save:
                #         chat_service_for_error_save = ChatService(db_session_for_error_save)
                #         chat_service_for_error_save.add_message_to_chat(
                #             chat_id=c_id,
                #             role="system", # 或者 assistant?
                #             content=f"Error during processing: {error_data.get('message', 'Unknown error')}"
                #         )
                #         logger.info(f"[Chat {c_id}] Saved error message to chat history.")
                # except Exception as error_save_err:
                #         logger.error(f"[Chat {c_id}] Failed to save error message to chat history: {error_save_err}", exc_info=True)
            else:
                 logger.warning(f"[Chat {c_id}] Skipping save because final reply was empty or null.")
            # --- 结束数据库保存逻辑 ---

            # --- 发送流结束标记 --- 
            try:
                logger.debug(f"[Chat {c_id}] Putting STREAM_END_SENTINEL into queue.")
                await queue.put(STREAM_END_SENTINEL)
                logger.debug(f"[Chat {c_id}] Stream end sentinel sent.")
            except asyncio.QueueFull:
                 logger.error(f"[Chat {c_id}] Failed to put STREAM_END_SENTINEL in full queue.")
            except Exception as qe:
                 logger.error(f"[Chat {c_id}] Failed to put STREAM_END_SENTINEL in queue: {qe}")
            # No nested finally needed here for the sentinel sending

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