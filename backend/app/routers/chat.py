from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import logging
import json

from backend.app import schemas
from database.connection import get_db
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from backend.langchainchat.chains.workflow_chain import WorkflowChainOutput
from database.models import Flow

logger = logging.getLogger(__name__)

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
    向聊天添加用户消息，触发处理流程。
    根据处理结果返回流式响应 (文本) 或 JSON 响应 (工具调用/错误)。
    使用后台任务在流结束后保存 AI 回复。
    """
    chat_service = ChatService(db)
    chat = chat_service.get_chat(chat_id)
    
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天不存在")
    verified_flow = verify_flow_ownership(chat.flow_id, current_user, db)
    logger.info(f"Flow ownership 验证通过 for flow: {verified_flow.id} linked to chat: {chat_id}")
    if message.role != 'user':
         logger.warning(f"Received message with role '{message.role}' in add_message. Processing as user message.")
         
    try:
        # Call the service layer. It now returns WorkflowChainOutput or a Dict on error.
        result_from_service = await chat_service.process_chat_message(
            chat_id=chat_id,
            user_message=message.content
        )
        
        # --- Check the type of result from service --- 
        if isinstance(result_from_service, WorkflowChainOutput):
            chain_output = result_from_service
            
            if chain_output.stream_generator:
                # --- Handle Streaming Response with Background Save --- 
                logger.info(f"Chat service returned stream for chat {chat_id}. Preparing StreamingResponse with background save.")
                
                # Get the original generator from the service output
                original_generator = chain_output.stream_generator
                
                async def stream_wrapper_with_save(generator: AsyncGenerator[str, None]):
                    accumulated_content = ""
                    try:
                        async for text_chunk in generator:
                            accumulated_content += text_chunk
                            yield text_chunk # Yield to client
                    except Exception as e:
                        logger.error(f"Error during stream generation for chat {chat_id}: {e}", exc_info=True)
                        # Still try to save whatever was accumulated before the error
                    finally:
                        logger.info(f"Stream finished or terminated for chat {chat_id}. Adding background task to save content.")
                        if accumulated_content:
                            # Add the save operation as a background task
                            # Pass necessary arguments: chat_id, role, content
                            # IMPORTANT: chat_service.add_message_to_chat needs a valid db session.
                            # BackgroundTasks run *after* the response, so the request-scoped session `db`
                            # might be closed. We need a way to get a new session for the background task.
                            # Option 1: Pass db session factory `get_db` (if possible)
                            # Option 2: Modify `add_message_to_chat` to create its own session (less ideal)
                            # Option 3: Create a helper function that gets a new session and calls add_message_to_chat.
                            
                            # --- Using Option 3: Define a helper --- 
                            def save_message_task(c_id: str, role: str, content: str):
                                logger.info(f"[BG Task {c_id}] Started: Save message.")
                                db_session_bg = None # Initialize
                                try:
                                    from database.database import SessionLocal # Import session factory
                                    db_session_bg = SessionLocal()
                                    logger.info(f"[BG Task {c_id}] Created new DB session.")
                                    
                                    # Instantiate service with new session
                                    chat_service_bg = ChatService(db_session_bg)
                                    logger.info(f"[BG Task {c_id}] Instantiated ChatService with new session.")
                                    
                                    logger.info(f"[BG Task {c_id}] Calling add_message_to_chat...")
                                    save_result = chat_service_bg.add_message_to_chat(c_id, role, content)
                                    
                                    if save_result:
                                        logger.info(f"[BG Task {c_id}] Success: Saved message.")
                                    else:
                                        # add_message_to_chat logs its own errors, but log failure here too.
                                        logger.error(f"[BG Task {c_id}] Failed: add_message_to_chat returned None or False.")
                                        
                                except ImportError as ie:
                                     logger.error(f"[BG Task {c_id}] ImportError: Could not import SessionLocal. {ie}", exc_info=True)
                                except Exception as bg_err:
                                    logger.error(f"[BG Task {c_id}] Error during execution: {bg_err}", exc_info=True)
                                finally:
                                     if db_session_bg:
                                         try:
                                             db_session_bg.close()
                                             logger.info(f"[BG Task {c_id}] Closed DB session.")
                                         except Exception as close_err:
                                              logger.error(f"[BG Task {c_id}] Error closing DB session: {close_err}", exc_info=True)
                                     else:
                                          logger.warning(f"[BG Task {c_id}] DB session was not created, nothing to close.")
                                     logger.info(f"[BG Task {c_id}] Finished.")
                                
                            background_tasks.add_task(save_message_task, chat_id, "assistant", accumulated_content)
                        else:
                            logger.warning(f"Stream finished for chat {chat_id}, but no content accumulated for background save.")

                # Return the streaming response, passing the background_tasks object
                return StreamingResponse(stream_wrapper_with_save(original_generator), 
                                         media_type="text/plain; charset=utf-8", 
                                         background=background_tasks)
            
            else:
                # --- Handle Non-Streaming JSON Response (Tool calls, errors, etc.) ---
                logger.info(f"Chat service returned non-streaming output for chat {chat_id}. Preparing JSONResponse.")
                # Exclude the (None) generator field before sending
                response_data = chain_output.model_dump(exclude={'stream_generator'})
                 # Update Flow's last_interacted_chat_id only on non-streaming success?
                # Or keep it updated regardless? Let's keep it for now.
                try:
                    flow_to_update = db.query(Flow).filter(Flow.id == chat.flow_id).first()
                    if flow_to_update:
                        flow_to_update.last_interacted_chat_id = chat_id
                        db.commit()
                        logger.info(f"(Non-stream) Updated Flow {chat.flow_id} last_interacted_chat_id to {chat_id}")
                except Exception as update_err:
                    logger.error(f"(Non-stream) Failed to update Flow last_interacted_chat_id: {update_err}", exc_info=True)
                    db.rollback()
                
                return JSONResponse(content=response_data)
                
        elif isinstance(result_from_service, dict) and "error" in result_from_service:
             # --- Handle Initial Error Dictionary from Service --- 
             logger.error(f"Chat service returned an initial error dictionary for chat {chat_id}: {result_from_service['error']}")
             # You might want a specific status code here, e.g., 400 or 500
             return JSONResponse(content=result_from_service, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
             # --- Unexpected result type from service --- 
             logger.error(f"Chat service returned an unexpected result type for chat {chat_id}: {type(result_from_service)}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="处理消息时返回了意外的结果类型")

    except HTTPException as http_exc:
         # Re-raise HTTPExceptions (like 404 Not Found, 403 Forbidden)
         raise http_exc
    except Exception as e:
        # Catch-all for other unexpected errors during processing
        logger.error(f"处理聊天消息端点时发生意外错误 (Chat ID: {chat_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理消息时发生内部错误"
        )


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