"""
SAS Graph Builder 测试 - 第二步：用户批准任务列表

此文件从第一步加载状态，执行用户批准任务列表，并保存状态到JSON文件中
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from langsmith import Client as LangSmithClient
from langsmith.utils import tracing_is_enabled as langsmith_tracing_is_enabled

from backend.app.routers.sas_chat import gemini_model_name, _process_sas_events, SASEventBroadcaster
from backend.sas.graph_builder import create_robot_flow_graph, RootRunIDCollector
from langgraph.checkpoint.memory import MemorySaver
import pickle
import os

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

async def test_step2_approve_tasks():
    """第二步：用户批准任务列表并保存状态"""
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running step 2: Approve task list...")
    
    # 检查第一步状态文件是否存在
    state_file = "/tmp/sas_test_states/step1_state.json"
    if not os.path.exists(state_file):
        logger.error(f"第一步状态文件不存在: {state_file}")
        logger.error("请先运行 test_sas_step1.py")
        return
    
    # 加载第一步的状态
    with open(state_file, 'r', encoding='utf-8') as f:
        step1_data = json.load(f)
    
    logger.info(f"加载第一步状态，时间戳: {step1_data['timestamp']}")
    logger.info(f"第一步完成状态: {step1_data['completion_status']}")
    
    if step1_data['completion_status'] != 'needs_clarification':
        logger.error(f"第一步状态不正确，期望 'needs_clarification'，实际: {step1_data['completion_status']}")
        return
    
    # Get LLM configuration
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    gemini_model_name = os.getenv("GEMINI_MODEL")
    if not gemini_api_key:
        logger.error("GOOGLE_API_KEY not found. Skipping test.")
        return
    
    llm = ChatGoogleGenerativeAI(
        model=gemini_model_name, 
        google_api_key=gemini_api_key,
        temperature=0,
    )
    
    # 创建新的checkpointer - 我们将手动构建初始状态
    checkpointer = MemorySaver()
    robot_flow_app = create_robot_flow_graph(llm=llm, checkpointer=checkpointer)
    
    # 手动设置初始状态来模拟第一步完成后的状态
    logger.info("手动构建graph状态以继续第二步...")
    
    # 创建事件广播器和使用相同的chat_id
    event_broadcaster = SASEventBroadcaster()
    test_chat_id = step1_data['chat_id']
    
    # 从第一步数据中提取状态值
    step1_state_values = step1_data.get('state_values', {})
    
    # 构建用于第二步的配置
    config = {"configurable": {"thread_id": test_chat_id}}
    
    # 手动构建状态 - 使用第一步的state_values作为基础
    # 我们需要确保对话状态正确设置为等待任务列表审核
    manual_state = {
        **step1_state_values,
        "dialog_state": "sas_awaiting_task_list_review",
        "task_list_accepted": False,
        "module_steps_accepted": False,
    }
    
    logger.info(f"准备手动设置状态，dialog_state: {manual_state.get('dialog_state')}")
    
    # 事件收集器
    events_collected = []
    completion_status = None
    processing_complete = asyncio.Event()
    
    async def collect_events():
        """收集事件的协程"""
        nonlocal completion_status
        try:
            event_queue = await event_broadcaster.get_or_create_queue(test_chat_id)
            while True:
                try:
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    events_collected.append(event_item)
                    logger.info(f"收集到事件: {event_item.get('type', 'unknown')}")
                    
                    if event_item.get("type") == "processing_complete":
                        completion_status = event_item.get("data", {}).get("completion_status")
                        logger.info(f"处理完成，状态: {completion_status}")
                        processing_complete.set()
                        break
                    elif event_item.get("type") == "connection_close":
                        logger.info("连接关闭")
                        break
                except asyncio.TimeoutError:
                    logger.warning("等待事件超时")
                    break
        except Exception as e:
            logger.error(f"收集事件时出错: {e}")
            processing_complete.set()
    
    try:
        # 启动事件收集器
        collector_task = asyncio.create_task(collect_events())
        
        logger.info("=== 第二步：用户批准任务列表 ===")
        
        # 首先尝试手动设置graph状态（如果可能的话）
        try:
            # 使用第一步的状态值初始化graph状态
            await robot_flow_app.aupdate_state(config, manual_state)
            logger.info("手动设置graph状态成功")
        except Exception as e:
            logger.warning(f"手动设置graph状态失败，将依赖默认初始化: {e}")
        
        # 发送用户批准消息
        approve_message = "FRONTEND_APPROVE_TASKS"
        logger.info(f"发送批准消息: {approve_message}")
        
        # 处理消息
        await _process_sas_events(test_chat_id, approve_message, robot_flow_app, test_chat_id)
        
        # 等待处理完成
        await asyncio.wait_for(processing_complete.wait(), timeout=300.0)
        
        logger.info(f"第二步完成，状态: {completion_status}")
        
        # 保存checkpointer状态
        if completion_status == 'needs_clarification':
            logger.info("正在保存第二步状态...")
            
            # 获取当前状态
            config = {"configurable": {"thread_id": test_chat_id}}
            current_state = await robot_flow_app.aget_state(config)
            
            # 准备保存的数据
            state_data = {
                "step": 2,
                "chat_id": test_chat_id,
                "completion_status": completion_status,
                "timestamp": datetime.now().isoformat(),
                "state_values": current_state.values if hasattr(current_state, 'values') else {},
                "next_actions": current_state.next if hasattr(current_state, 'next') else [],
                "events": events_collected,
                "checkpointer_data": {},
                "previous_step_data": step1_data
            }
            
            # 尝试获取checkpointer内部数据
            try:
                if hasattr(checkpointer, 'storage'):
                    state_data["checkpointer_data"] = dict(checkpointer.storage)
            except Exception as e:
                logger.warning(f"无法获取checkpointer内部数据: {e}")
            
            # 保存到文件
            step2_state_file = "/tmp/sas_test_states/step2_state.json"
            with open(step2_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"第二步状态已保存到: {step2_state_file}")
            logger.info("✅ 第二步测试成功完成，可以运行第三步")
        else:
            logger.warning(f"第二步状态不符合预期: {completion_status}")
        
        # 取消收集器任务
        if not collector_task.done():
            collector_task.cancel()
            
    except asyncio.TimeoutError:
        logger.error("第二步处理超时")
    except Exception as e:
        logger.error(f"第二步测试遇到异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_step2_approve_tasks()) 