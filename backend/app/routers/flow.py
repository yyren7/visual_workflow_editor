## backend/app/routers/flow.py
from typing import List, Dict, Any, Optional
# 不再需要UUID类型
# from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body, Response
from sqlalchemy.orm import Session
from backend.app import schemas, utils
from database.models import Flow, FlowVariable, Chat
from database.connection import get_db
from backend.config import APP_CONFIG
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.user_flow_service import UserFlowService
from backend.app.services.flow_service import FlowService
from backend.app.services.flow_variable_service import FlowVariableService
from backend.app.dependencies import get_checkpointer # MODIFIED: Import from dependencies
from backend.app.routers.sas_chat import get_sas_app  # Import to get SAS app for state management
from backend.sas.state import RobotFlowAgentState # 导入 RobotFlowAgentState 模型
import logging # Add logging
from sqlalchemy import desc # Import desc for ordering

logger = logging.getLogger(__name__) # Add logger

router = APIRouter(
    prefix="/flows",
    tags=["flows"],
    responses={404: {"description": "Not found"}},
)

def get_flow_service(
    db: Session = Depends(get_db),
) -> FlowService:
    return FlowService(db=db)


@router.post("/", response_model=schemas.Flow)
async def create_flow(
    flow_data: schemas.FlowCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service),
    sas_app = Depends(get_sas_app)
):
    """
    创建新的流程图，并立即初始化对应的 LangGraph SAS 状态。
    """
    # 1. 创建数据库记录
    new_db_flow = await flow_service.create_flow(
        owner_id=current_user.id,
        name=flow_data.name,
        data=flow_data.flow_data
    )
    
    # 2. 立即初始化 LangGraph 状态
    try:
        flow_id = str(new_db_flow.id)
        config = {"configurable": {"thread_id": flow_id}}
        
        # 检查是否传递了sas_state，如果有则使用它，否则使用默认状态
        if flow_data.sas_state:
            # 使用传递的sas_state
            logger.info(f"Using provided sas_state for new flow {flow_id}")
            initial_state_dict = flow_data.sas_state
            
            # 验证传递的状态是否有效，如果无效则使用默认状态
            try:
                validated_state = RobotFlowAgentState(**initial_state_dict)
                initial_state_dict = validated_state.model_dump(exclude_none=False)
                logger.info(f"Validated provided sas_state for flow {flow_id} (dialog_state: {initial_state_dict.get('dialog_state')})")
            except Exception as validation_error:
                logger.warning(f"Invalid sas_state provided for flow {flow_id}: {validation_error}. Using default state.")
                default_state_model = RobotFlowAgentState()
                initial_state_dict = default_state_model.model_dump(exclude_none=False)
        else:
            # 使用默认的 SAS 状态
            default_state_model = RobotFlowAgentState()
            initial_state_dict = default_state_model.model_dump(exclude_none=False)
            logger.info(f"Using default sas_state for new flow {flow_id} (dialog_state: {initial_state_dict.get('dialog_state')})")
        
        # 保存到 LangGraph checkpointer
        await sas_app.aupdate_state(config, initial_state_dict)
        
        logger.info(f"Created new flow {flow_id} for user {current_user.id} with SAS state")
        
    except Exception as e:
        # 如果 LangGraph 状态初始化失败，记录错误但不影响流程图创建
        logger.error(f"Failed to initialize SAS state for new flow {new_db_flow.id}: {e}", exc_info=True)
        logger.info(f"Created new flow {new_db_flow.id} for user {current_user.id} (SAS state initialization failed)")
    
    return new_db_flow


@router.get("/{flow_id}", response_model=schemas.FlowDetail)
async def get_flow(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service),
    sas_app = Depends(get_sas_app)
):
    """
    获取流程图详情，包括从 LangGraph 获取的当前 SAS 状态
    """
    # 验证所有权
    verify_flow_ownership(flow_id, current_user, db)
    
    # 从数据库获取流程图基本信息
    flow_data = await flow_service.get_flow(flow_id)
    if not flow_data:
        raise HTTPException(status_code=404, detail="流程图不存在")
    
    # 尝试从 LangGraph 获取 SAS 状态
    try:
        config = {"configurable": {"thread_id": flow_id}}
        state_snapshot = await sas_app.aget_state(config)
        
        if state_snapshot and hasattr(state_snapshot, 'values') and state_snapshot.values:
            # 验证状态完整性，确保包含所有必要字段
            try:
                validated_state = RobotFlowAgentState(**state_snapshot.values)
                flow_data["sas_state"] = validated_state.model_dump(exclude_none=False)
                logger.info(f"Retrieved and validated SAS state for flow {flow_id} (dialog_state: {flow_data['sas_state'].get('dialog_state')})")
            except Exception as validation_error:
                logger.warning(f"SAS state validation failed for flow {flow_id}: {validation_error}. Using default state.")
                # 状态验证失败，使用默认状态
                default_state = RobotFlowAgentState()
                flow_data["sas_state"] = default_state.model_dump(exclude_none=False)
        else:
            logger.warning(f"No valid SAS state found for flow {flow_id}. This should not happen for flows created after the fix.")
            # 如果没有状态，提供默认状态而不是 None
            default_state = RobotFlowAgentState()
            flow_data["sas_state"] = default_state.model_dump(exclude_none=False)
            logger.info(f"Provided default SAS state for flow {flow_id} (dialog_state: {flow_data['sas_state'].get('dialog_state')})")
    except Exception as e:
        logger.error(f"Failed to fetch SAS state for flow {flow_id}: {e}", exc_info=True)
        # 出现异常时，也提供默认状态而不是 None
        default_state = RobotFlowAgentState()
        flow_data["sas_state"] = default_state.model_dump(exclude_none=False)
        logger.info(f"Provided fallback default SAS state for flow {flow_id} due to error")
    
    return flow_data


@router.put("/{flow_id}", response_model=schemas.Flow)
async def update_flow(
    flow_id: str,
    flow_update: schemas.FlowUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service)
):
    """
    更新流程图的基本信息（名称、flow_data）
    """
    # 验证所有权
    verify_flow_ownership(flow_id, current_user, db)
    
    success = await flow_service.update_flow(
        flow_id=flow_id,
        data=flow_update.flow_data,
        name=flow_update.name
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="更新流程图失败")
    
    # 返回更新后的流程图
    updated_flow = await flow_service.get_flow(flow_id)
    return updated_flow


@router.delete("/{flow_id}", response_model=bool)
async def delete_flow(
    flow_id: str, 
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service),
    sas_app = Depends(get_sas_app)
):
    """
    删除流程图，包括数据库记录和对应的 LangGraph 状态。
    必须登录并且只能删除自己的流程。
    """
    _ = verify_flow_ownership(flow_id, current_user, flow_service.db)

    # 1. 首先删除 LangGraph checkpointer 中的状态
    try:
        config = {"configurable": {"thread_id": flow_id}}
        # 注意：LangGraph 可能没有直接的 delete 方法，这里我们先尝试获取状态
        # 如果状态存在，记录日志；如果需要实际删除，可能需要调用 checkpointer 的具体方法
        state_snapshot = await sas_app.aget_state(config)
        if state_snapshot and hasattr(state_snapshot, 'values'):
            logger.info(f"Found SAS state for flow {flow_id} before deletion")
            # TODO: 实际删除状态的代码可能需要根据具体的 checkpointer 类型实现
            # 例如：await sas_app.checkpointer.adelete(config)
        else:
            logger.info(f"No SAS state found for flow {flow_id}, skipping state deletion")
    except Exception as e:
        logger.warning(f"Could not delete SAS state for flow {flow_id}: {e}")
        # 继续删除数据库记录，即使状态删除失败
    
    # 2. 删除数据库记录
    success = await flow_service.delete_flow(flow_id=flow_id)
    if not success:
        raise HTTPException(status_code=404, detail="Flow not found or deletion failed")
    
    logger.info(f"Successfully deleted flow {flow_id} and associated resources")
    return True


@router.get("/", response_model=List[schemas.Flow])
async def get_flows(
    skip: int = 0,
    limit: int = 100,
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service)
):
    """
    获取当前用户的流程图列表
    """
    flows = await flow_service.get_flows(owner_id=current_user.id, limit=limit)
    return flows


@router.post("/{flow_id}/set-as-last-selected", response_model=bool)
async def set_as_last_selected(flow_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Sets a flow as the user's last selected flow. 必须登录并且只能选择自己的流程。
    """
    verify_flow_ownership(flow_id, current_user, db)
    
    flow_service = UserFlowService(db)
    success = flow_service.set_last_selected_flow_id(current_user.id, flow_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="无法更新用户流程图偏好")
    
    return True


@router.get("/user/last-selected", response_model=schemas.Flow)
async def get_last_selected_flow(
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service)
):
    """
    Gets the user's last selected flow, including agent_state. 必须登录才能获取。
    """
    # UserFlowService is separate and uses db directly. We get db from flow_service.
    user_flow_service = UserFlowService(flow_service.db)
    selected_flow_id = user_flow_service.get_last_selected_flow_id(current_user.id)
    
    flow_to_return_id = None
    if not selected_flow_id:
        # 如果用户没有选择过流程图，获取最新的一个 (DB query)
        latest_flow_model = flow_service.db.query(Flow).filter(Flow.owner_id == current_user.id).order_by(Flow.updated_at.desc()).first()
        if not latest_flow_model:
            raise HTTPException(status_code=404, detail="用户没有流程图")
        flow_to_return_id = str(latest_flow_model.id)
    else:
        # 检查记录的流程图是否存在 (DB query)
        flow_exists = flow_service.db.query(Flow).filter(Flow.id == selected_flow_id, Flow.owner_id == current_user.id).first()
        if not flow_exists:
            # 如果记录的流程图不存在，获取最新的一个
            latest_flow_model = flow_service.db.query(Flow).filter(Flow.owner_id == current_user.id).order_by(Flow.updated_at.desc()).first()
            if not latest_flow_model:
                raise HTTPException(status_code=404, detail="用户没有流程图")
            flow_to_return_id = str(latest_flow_model.id)
        # 更新用户偏好
            user_flow_service.set_last_selected_flow_id(current_user.id, flow_to_return_id)
        else:
            flow_to_return_id = str(selected_flow_id)

    if not flow_to_return_id: # Should not happen if logic above is correct
         raise HTTPException(status_code=404, detail="无法确定要返回的流程图")

    # 获取包含 agent_state 的完整流程图详情
    flow_details_dict = await flow_service.get_flow(flow_id=flow_to_return_id)
    if not flow_details_dict:
        # This case implies the flow_to_return_id (which should be valid in DB) was not found by flow_service.get_flow
        # This could happen if flow_service.get_flow has stricter checks or if there's a race condition.
        # Or if the ID conversion (e.g. UUID to str) has issues.
        logger.error(f"Failed to get flow details for supposedly valid flow_id: {flow_to_return_id}")
        raise HTTPException(status_code=500, detail="获取流程图详细信息时出错")
        
    return schemas.Flow(**flow_details_dict)


# --- Modify endpoint to get last interacted chat ID ---
@router.get("/{flow_id}/last_chat", response_model=schemas.LastChatResponse)
async def get_flow_last_chat_id(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取流程图最后交互且仍然存在的聊天 ID。
    如果记录的最后交互聊天已被删除，则尝试查找最新的、仍然存在的聊天。
    """
    try:
        logger.info(f"Attempting to get last valid chat ID for flow: {flow_id} for user: {current_user.id}")
        flow = verify_flow_ownership(flow_id, current_user, db) # Verify ownership and get flow

        last_chat_id = flow.last_interacted_chat_id
        valid_chat_id_to_return = None

        if last_chat_id:
            # 1. Check if the recorded last_chat_id still exists
            chat_exists = db.query(Chat).filter(
                Chat.id == last_chat_id,
                Chat.flow_id == flow_id # Ensure it belongs to the correct flow
            ).first()

            if chat_exists:
                logger.info(f"Recorded last chat ID {last_chat_id} is valid for flow {flow_id}.")
                valid_chat_id_to_return = last_chat_id
            else:
                logger.warning(f"Recorded last chat ID {last_chat_id} for flow {flow_id} not found or deleted. Searching for fallback.")
                # 2. If not exists, find the most recent *existing* chat for this flow
                fallback_chat = db.query(Chat).filter(
                    Chat.flow_id == flow_id
                ).order_by(desc(Chat.updated_at)).first() # Order by updated_at descending

                if fallback_chat:
                    logger.info(f"Found fallback chat ID {fallback_chat.id} for flow {flow_id}.")
                    valid_chat_id_to_return = fallback_chat.id
                    # Optional: Update the flow's last_interacted_chat_id to the new valid one
                    try:
                        flow.last_interacted_chat_id = fallback_chat.id
                        db.add(flow)
                        db.commit()
                        logger.info(f"Updated flow {flow_id}'s last_interacted_chat_id to {fallback_chat.id}.")
                    except Exception as update_err:
                         logger.error(f"Failed to update last_interacted_chat_id for flow {flow_id}", exc_info=True)
                         db.rollback() # Rollback the specific update attempt on error
                else:
                    logger.warning(f"No existing chats found for flow {flow_id} as fallback.")
                    # Optional: Clear the invalid last_interacted_chat_id if no fallback exists
                    if flow.last_interacted_chat_id is not None: # Only update if it was previously set
                        try:
                            flow.last_interacted_chat_id = None
                            db.add(flow)
                            db.commit()
                            logger.info(f"Cleared invalid last_interacted_chat_id for flow {flow_id}.")
                        except Exception as clear_err:
                             logger.error(f"Failed to clear last_interacted_chat_id for flow {flow_id}", exc_info=True)
                             db.rollback() # Rollback the specific clear attempt on error

        else:
             logger.info(f"No last interacted chat ID recorded for flow {flow_id}.")
             # last_chat_id was None initially, so valid_chat_id_to_return remains None

        logger.info(f"Returning last chat ID for flow {flow_id}: {valid_chat_id_to_return}")
        return schemas.LastChatResponse(chatId=valid_chat_id_to_return)

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        logger.warning(f"HTTPException getting last chat ID for flow {flow_id}: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch other potential errors
        logger.error(f"Unexpected error getting last chat ID for flow {flow_id}", exc_info=True)
        db.rollback() # Rollback any potential transaction changes from this function
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取最后聊天ID时出错: {str(e)}"
        )
# --- End modify endpoint ---

# --- 新增: 设置流程的最后交互聊天 ---
@router.post("/{flow_id}/set_last_chat", status_code=status.HTTP_204_NO_CONTENT)
async def set_flow_last_chat(
    flow_id: str,
    payload: schemas.SetLastChatRequest, # 使用定义的请求体模型
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    设置指定流程图的最后交互聊天ID。
    必须登录，并且只能操作自己的流程图。
    """
    logger.info(f"Attempting to set last interacted chat for flow: {flow_id} to chat: {payload.chat_id} for user: {current_user.id}")

    # 1. 验证流程图所有权并获取流程对象
    flow = verify_flow_ownership(flow_id, current_user, db)

    # 2. 验证 chat_id 对应的聊天是否存在且属于该 flow
    chat_to_set = db.query(Chat).filter(
        Chat.id == payload.chat_id,
        Chat.flow_id == flow_id # 确保聊天属于当前流程
    ).first()

    if not chat_to_set:
        logger.warning(f"Chat ID {payload.chat_id} not found or does not belong to flow {flow_id} for user {current_user.id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {payload.chat_id} not found for flow {flow_id}"
        )

    # 3. 更新流程的 last_interacted_chat_id
    try:
        flow.last_interacted_chat_id = payload.chat_id
        db.add(flow) # 添加到会话以进行更新
        db.commit()
        db.refresh(flow) # 刷新以获取更新后的状态 (可选，但良好实践)
        logger.info(f"Successfully set last interacted chat for flow {flow_id} to {payload.chat_id}")
        # 对于 204 No Content，通常不返回任何响应体
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to set last interacted chat for flow {flow_id} to {payload.chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update the last interacted chat for the flow."
        )
# --- 结束新增 ---

@router.post("/{flow_id}/ensure-agent-state", response_model=schemas.FlowDetail, deprecated=True)
async def ensure_agent_state(
    flow_id: str,
    current_user: schemas.User = Depends(get_current_user),
    flow_service: FlowService = Depends(get_flow_service),
    sas_app = Depends(get_sas_app)
):
    """
    [已弃用] 确保流程图有完整的 agent_state 结构。
    
    注意：此端点已弃用。现在所有新创建的流程图都会在创建时自动初始化 SAS 状态，
    而 get_flow 端点会自动提供默认状态。建议使用 GET /flows/{flow_id} 替代。
    
    如果 LangGraph 中没有状态，会初始化一个默认状态。
    返回的 agent_state 会确保包含所有字段，即使其值为 null。
    """    
    # 验证流程图所有权
    verify_flow_ownership(flow_id, current_user, flow_service.db)
    
    # 从数据库获取流程图基本信息
    flow_data = await flow_service.get_flow(flow_id)
    if not flow_data:
        raise HTTPException(status_code=404, detail="流程图不存在")
    
    # 尝试从 LangGraph 获取当前状态
    try:
        config = {"configurable": {"thread_id": flow_id}}
        state_snapshot = await sas_app.aget_state(config)
        
        current_agent_state_dict = {}
        if state_snapshot and hasattr(state_snapshot, 'values') and state_snapshot.values:
            current_agent_state_dict = state_snapshot.values
            logger.info(f"Retrieved existing agent state for flow {flow_id}")
        else:
            # 如果没有 LangGraph 状态，初始化一个完整的默认状态
            default_state_model = RobotFlowAgentState()
            # 直接使用 Pydantic 模型的 dump 方法来获取包含所有默认值的字典
            current_agent_state_dict = default_state_model.model_dump(exclude_none=False)
            logger.info(f"No valid agent state found for flow {flow_id}. Initializing with full default state.")
            
            # 使用 LangGraph 的 update_state 初始化状态
            await sas_app.aupdate_state(config, current_agent_state_dict)
            logger.info(f"Initialized default agent state for flow {flow_id}")
        
        # 实例化 Pydantic 模型以确保所有字段都存在
        validated_state = RobotFlowAgentState(**current_agent_state_dict)
        
        # 使用 exclude_none=False 来确保所有字段（即使是 None）都被序列化
        full_agent_state = validated_state.model_dump(exclude_none=False)

        # 将 agent_state 添加到流程图数据中返回给前端
        flow_data["sas_state"] = full_agent_state
        
        return schemas.FlowDetail(**flow_data)
        
    except Exception as e:
        logger.error(f"Failed to ensure agent state for flow {flow_id}: {e}", exc_info=True)
        # 即使失败，也尝试返回一个空的、结构完整的 agent_state
        flow_data["sas_state"] = RobotFlowAgentState().model_dump(exclude_none=False)
        return schemas.FlowDetail(**flow_data)

@router.post("/{flow_id}/reset-stuck-state", response_model=schemas.SuccessResponse)
async def reset_stuck_state(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    sas_app = Depends(get_sas_app)
):
    """
    重置卡住的处理状态，将其恢复到可编辑状态
    """
    # 验证所有权
    verify_flow_ownership(flow_id, current_user, db)
    
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态
        state_snapshot = await sas_app.aget_state(config)
        if not state_snapshot or not hasattr(state_snapshot, 'values'):
            raise HTTPException(status_code=404, detail="未找到该流程的状态")
        
        current_state = state_snapshot.values
        
        # 检查是否处于处理状态或需要重置的状态
        processing_states = [
            'generating_xml_relation',
            'generating_xml_final', 
            'sas_generating_individual_xmls',
            'sas_module_steps_accepted_proceeding',
            'sas_all_steps_accepted_proceed_to_xml'
        ]
        
        # 扩展：也支持重置完成状态和错误状态
        resettable_states = processing_states + [
            'sas_step3_completed',
            'final_xml_generated_success',
            'error'
        ]
        
        current_dialog_state = current_state.get('dialog_state')
        is_error_state = current_state.get('is_error', False)
        
        if current_dialog_state in resettable_states or is_error_state:
            # 根据当前状态确定合适的重置策略
            if current_dialog_state in ['sas_step3_completed', 'final_xml_generated_success']:
                # 如果是完成状态，回退到step2审查状态
                reset_state = {
                    **current_state,
                    'dialog_state': 'sas_step2_module_steps_generated_for_review',
                    'subgraph_completion_status': None,
                    'is_error': False,
                    'error_message': None,
                    'current_step_description': 'Reset from completed state for re-review',
                    'module_steps_accepted': False,  # 重新需要用户确认
                    'final_flow_xml_path': None,
                    'generated_xml_files': []
                }
                logger.info(f"Reset completed state for flow {flow_id} to step2 review")
            else:
                # 对于处理状态和错误状态，重置为初始状态
                reset_state = {
                    **current_state,
                    'dialog_state': 'initial',
                    'subgraph_completion_status': None,
                    'is_error': False,
                    'error_message': None,
                    'current_step_description': 'Reset from stuck/error state',
                    'task_list_accepted': False,
                    'module_steps_accepted': False,
                    'revision_iteration': 0
                }
                logger.info(f"Reset stuck/error state for flow {flow_id} to initial")
            
            await sas_app.aupdate_state(config, reset_state)
            
            return {"success": True, "message": f"已重置状态从 {current_dialog_state} 到 {reset_state['dialog_state']}"}
        else:
            return {"success": True, "message": "当前状态不需要重置"}
            
    except Exception as e:
        logger.error(f"Failed to reset stuck state for flow {flow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"重置状态失败: {str(e)}")

@router.post("/{flow_id}/force-complete-processing", response_model=schemas.SuccessResponse)
async def force_complete_processing(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    sas_app = Depends(get_sas_app)
):
    """
    强制完成当前的处理步骤，跳转到完成状态
    """
    # 验证所有权
    verify_flow_ownership(flow_id, current_user, db)
    
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态
        state_snapshot = await sas_app.aget_state(config)
        if not state_snapshot or not hasattr(state_snapshot, 'values'):
            raise HTTPException(status_code=404, detail="未找到该流程的状态")
        
        current_state = state_snapshot.values
        
        # 根据当前状态强制设置为适当的完成状态
        current_dialog_state = current_state.get('dialog_state')
        
        if current_dialog_state in ['generating_xml_relation', 'generating_xml_final']:
            # 如果正在生成XML，强制设置为完成状态
            completed_state = {
                **current_state,
                'dialog_state': 'sas_step3_completed',
                'subgraph_completion_status': 'completed_success',
                'is_error': False,
                'error_message': None,
                'current_step_description': 'Processing forcefully completed by user',
                # 如果没有XML路径，提供一个默认路径
                'final_flow_xml_path': current_state.get('final_flow_xml_path') or f'/tmp/flow_{flow_id}_force_completed.xml'
            }
        elif current_dialog_state in ['sas_generating_individual_xmls']:
            # 如果正在生成个体XML，设置为relation生成完成
            completed_state = {
                **current_state,
                'dialog_state': 'generating_xml_final',
                'current_step_description': 'Individual XMLs forcefully completed, proceeding to final XML'
            }
        else:
            # 其他处理状态，设置为通用完成状态
            completed_state = {
                **current_state,
                'dialog_state': 'sas_step3_completed',
                'subgraph_completion_status': 'completed_success',
                'current_step_description': 'Processing forcefully completed by user'
            }
        
        await sas_app.aupdate_state(config, completed_state)
        
        logger.info(f"Force completed processing for flow {flow_id} from state {current_dialog_state}")
        return {"success": True, "message": "已强制完成当前处理步骤"}
        
    except Exception as e:
        logger.error(f"Failed to force complete processing for flow {flow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"强制完成失败: {str(e)}")

# 流程图变量相关端点
@router.get("/{flow_id}/variables")
async def get_flow_variables(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    获取流程图变量
    """
    verify_flow_ownership(flow_id, current_user, db)
    
    variable_service = FlowVariableService(db)
    variables = variable_service.get_flow_variables(flow_id)
    
    return {"flow_id": flow_id, "variables": variables}

@router.put("/{flow_id}/variables")
async def update_flow_variables(
    flow_id: str,
    variables: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    更新流程图变量
    """
    verify_flow_ownership(flow_id, current_user, db)
    
    variable_service = FlowVariableService(db)
    variable_service.update_flow_variables(flow_id, variables)
    
    return {"success": True, "message": "变量更新成功"}

@router.post("/{flow_id}/force-reset-state", response_model=schemas.SuccessResponse)
async def force_reset_state(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    sas_app = Depends(get_sas_app)
):
    """
    强制重置状态，无论当前处于什么状态都会重置到初始状态
    """
    # 验证所有权
    verify_flow_ownership(flow_id, current_user, db)
    
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取当前状态以保留有用信息
        state_snapshot = await sas_app.aget_state(config)
        current_state = {}
        if state_snapshot and hasattr(state_snapshot, 'values'):
            current_state = state_snapshot.values
        
        # 强制重置到初始状态，但保留一些基本信息
        reset_state = {
            'dialog_state': 'initial',
            'subgraph_completion_status': None,
            'is_error': False,
            'error_message': None,
            'current_step_description': 'State forcefully reset by user',
            'task_list_accepted': False,
            'module_steps_accepted': False,
            'revision_iteration': 0,
            'sas_step1_generated_tasks': None,
            'sas_step2_module_steps': None,
            'sas_step2_generated_task_details': None,
            'clarification_question': None,
            'final_flow_xml_path': None,
            'generated_xml_files': [],
            'current_user_request': current_state.get('current_user_request'),  # 保留用户原始请求
            'active_plan_basis': current_state.get('active_plan_basis'),  # 保留计划基础
            'user_input': None,
            'messages': [],  # 清空消息历史
            'config': current_state.get('config', {})  # 保留配置
        }
        
        await sas_app.aupdate_state(config, reset_state)
        
        logger.info(f"Force reset state for flow {flow_id} from {current_state.get('dialog_state')} to initial")
        return {"success": True, "message": "已强制重置状态到初始状态"}
        
    except Exception as e:
        logger.error(f"Failed to force reset state for flow {flow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"强制重置状态失败: {str(e)}")

@router.post("/{flow_id}/rollback-to-previous", response_model=schemas.SuccessResponse)
async def rollback_to_previous_state(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    sas_app = Depends(get_sas_app)
):
    """
    回退到上一个稳定的状态
    """
    # 验证所有权
    verify_flow_ownership(flow_id, current_user, db)
    
    try:
        config = {"configurable": {"thread_id": flow_id}}
        
        # 获取状态历史
        history = []
        async for state in sas_app.aget_state_history(config):
            if hasattr(state, 'values') and state.values:
                history.append(state)
        
        if len(history) < 2:
            return {"success": False, "message": "没有找到可以回退的历史状态"}
        
        # 找到上一个稳定的状态
        # 排除当前状态（索引0），从索引1开始寻找
        target_state = None
        stable_states = [
            'initial',
            'sas_step1_tasks_generated',
            'sas_step2_module_steps_generated_for_review'
        ]
        
        for i in range(1, len(history)):
            state_values = history[i].values
            dialog_state = state_values.get('dialog_state')
            is_error = state_values.get('is_error', False)
            
            # 寻找一个稳定且无错误的状态
            if dialog_state in stable_states and not is_error:
                target_state = state_values
                break
        
        if not target_state:
            # 如果没找到稳定状态，回退到初始状态
            target_state = {
                'dialog_state': 'initial',
                'subgraph_completion_status': None,
                'is_error': False,
                'error_message': None,
                'current_step_description': 'Rolled back to initial state',
                'task_list_accepted': False,
                'module_steps_accepted': False,
                'revision_iteration': 0,
                'current_user_request': history[0].values.get('current_user_request'),
                'active_plan_basis': history[0].values.get('active_plan_basis'),
                'user_input': None,
                'messages': [],
                'config': history[0].values.get('config', {})
            }
            logger.info(f"No stable state found, rolling back to initial state for flow {flow_id}")
        else:
            # 清理一些可能导致问题的字段
            target_state = dict(target_state)
            target_state['current_step_description'] = f"Rolled back to {target_state['dialog_state']} state"
            target_state['user_input'] = None
            logger.info(f"Rolling back to stable state {target_state['dialog_state']} for flow {flow_id}")
        
        await sas_app.aupdate_state(config, target_state)
        
        return {"success": True, "message": f"已回退到状态: {target_state['dialog_state']}"}
        
    except Exception as e:
        logger.error(f"Failed to rollback state for flow {flow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"状态回退失败: {str(e)}")
