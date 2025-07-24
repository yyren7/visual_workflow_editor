import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from ..state import RobotFlowAgentState, TaskDefinition

logger = logging.getLogger(__name__)

# Helper to load task type descriptions
def _load_all_task_type_descriptions(base_path: str) -> str:
    logger.info(f"Loading all task type descriptions from: {base_path}")
    descriptions = []
    try:
        task_list_path = Path(base_path)
        if task_list_path.is_dir():
            for md_file in task_list_path.glob("*.md"):
                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        descriptions.append(f.read())
                    logger.debug(f"Loaded task type description: {md_file.name}")
                except Exception as e:
                    logger.error(f"Error reading task type description file {md_file}: {e}")
        else:
            logger.warning(f"Task type descriptions path is not a directory: {base_path}")
    except Exception as e:
        logger.error(f"Error accessing task type descriptions path {base_path}: {e}")
        return "Error: Could not load task type descriptions."
    
    if not descriptions:
        logger.warning(f"No task type descriptions found in {base_path}. Prompt will be incomplete.")
        return "Warning: Task type descriptions are missing."
        
    return "\n\n---\n\n".join(descriptions)


async def review_and_refine_node(state: RobotFlowAgentState, llm: BaseChatModel) -> RobotFlowAgentState:
    """
    Review and refine node for handling user feedback and approval processes.
    
    🔧 修改：删除了文本匹配自动批准逻辑
    现在只负责状态转换，不再基于用户输入内容进行自动批准判断
    """
    logger.info(f"✨ review_and_refine_node called with dialog_state: {state.dialog_state}")
    
    # 获取用户输入
    user_input = state.current_user_request or ""
    logger.info(f"User input: {user_input}")

    # 🔧 处理从生成节点进入的初始审核请求
    if state.dialog_state == 'sas_step1_tasks_generated':
        logger.info("📋 首次进入任务列表审核 - 转换状态为审核等待")
        state.dialog_state = 'sas_awaiting_task_list_review'
        state.completion_status = 'needs_clarification'
        
        # 添加提示消息
        task_count = len(state.sas_step1_generated_tasks) if state.sas_step1_generated_tasks else 0
        review_message = f"已生成 {task_count} 个任务，请审核任务列表。您可以点击绿色按钮批准，或在输入框中提供修改建议。"
        if state.messages and not any(review_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=review_message)]
        return state
    
    elif state.dialog_state == 'sas_step2_module_steps_generated_for_review':
        logger.info("📋 首次进入模块步骤审核 - 转换状态为审核等待")
        state.dialog_state = 'sas_awaiting_module_steps_review'
        state.completion_status = 'needs_clarification'
        
        # 添加提示消息
        review_message = "模块步骤已生成，请审核。您可以点击绿色按钮批准，或在输入框中提供修改建议。"
        if state.messages and not any(review_message in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
            state.messages = (state.messages or []) + [AIMessage(content=review_message)]
        return state

    # 🔧 删除了基于文本内容的自动批准逻辑
    # 不再进行 "accept", "agree", "yes" 等关键词匹配
    # 所有批准操作必须通过前端绿色按钮的特殊API调用完成
    
    # 判断当前处于哪个审核阶段
    is_task_list_review = state.dialog_state == 'sas_awaiting_task_list_review'
    is_module_steps_review = state.dialog_state == 'sas_awaiting_module_steps_review'
    
    # 🔧 现在只处理状态转换，不进行文本匹配批准
    if is_task_list_review:
        logger.info("在任务列表审核阶段 - 用户输入将作为反馈处理")
        # 用户输入作为任务修改反馈，不自动批准
        # 批准必须通过前端绿色按钮的 FRONTEND_APPROVE_TASKS 消息触发
        pass
    elif is_module_steps_review:
        logger.info("在模块步骤审核阶段 - 用户输入将作为反馈处理")
        # 用户输入作为模块步骤修改反馈，不自动批准
        # 批准必须通过前端绿色按钮的 FRONTEND_APPROVE_MODULE_STEPS 消息触发
        pass
    else:
        logger.info(f"非审核状态 {state.dialog_state} - 用户输入作为普通反馈处理")
    
    # 🔧 确保默认批准状态都是False
    if not hasattr(state, 'task_list_accepted') or state.task_list_accepted is None:
        state.task_list_accepted = False
    if not hasattr(state, 'module_steps_accepted') or state.module_steps_accepted is None:
        state.module_steps_accepted = False
    
    logger.info(f"✅ review_and_refine_node completed. task_list_accepted={state.task_list_accepted}, module_steps_accepted={state.module_steps_accepted}")
    return state

__all__ = [
    "review_and_refine_node"
] 