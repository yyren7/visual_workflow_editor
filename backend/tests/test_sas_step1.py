"""
SAS Graph Builder 测试 - 第一步：生成任务列表

此文件执行第一步任务列表生成，并将checkpointer状态保存到JSON文件中
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

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

async def test_step1_generate_task_list():
    """第一步：生成任务列表并保存状态"""
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running step 1: Generate task list...")
    
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
    
    # 创建内存checkpointer来保持状态
    checkpointer = MemorySaver()
    robot_flow_app = create_robot_flow_graph(llm=llm, checkpointer=checkpointer)
    
    # 创建事件广播器和测试chat_id
    event_broadcaster = SASEventBroadcaster()
    test_chat_id = "test_chat_001"
    
    # 设置输出目录
    os.makedirs("/tmp/sas_test_states", exist_ok=True)
    
    # 初始用户输入消息
    initial_message = "ロボットが、ティーチングポイントP3およびP4で定義された固定の部品供給ステーションから原材料または一次加工品を掴み取り（部品供給）、次にその部品を第二ステーション（ステーション2）へ搬送し、そこでP15で部品を掴んでからRz軸を90度から-90度へ180度回転させ、別の位置P18へ正確に再配置する中間処理を行い、最後に加工済みまたは処理済みと見なされた部品を最終的な設置エリア（ティーチングポイントP11およびP12で定義）へ搬送して正確に配置することで、一つの完全な作業サイクルを完了させます。"
    
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
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=60.0)
                    events_collected.append(event_item)
                    logger.info(f"收集到事件: {event_item.get('type', 'unknown')}")
                    
                    if event_item.get("type") == "processing_complete":
                        event_data = event_item.get("data", {})
                        completion_status = event_data.get("completion_status")
                        dialog_state_from_event = event_data.get("dialog_state")
                        logger.info(f"收到processing_complete事件，completion_status: {completion_status}, dialog_state: {dialog_state_from_event}")
                        processing_complete.set()
                        break
                    elif event_item.get("type") == "connection_close":
                        logger.info("连接关闭")
                        processing_complete.set()
                        break
                except asyncio.TimeoutError:
                    logger.warning("等待事件超时，设置完成标志")
                    processing_complete.set()
                    break
        except Exception as e:
            logger.error(f"收集事件时出错: {e}")
            processing_complete.set()
    
    try:
        # 启动事件收集器
        collector_task = asyncio.create_task(collect_events())
        
        logger.info("=== 第一步：生成任务列表 ===")
        logger.info(f"发送消息: {initial_message[:100]}...")
        
        # 处理消息
        await _process_sas_events(test_chat_id, initial_message, robot_flow_app, test_chat_id)
        
        # 等待处理完成
        try:
            await asyncio.wait_for(processing_complete.wait(), timeout=300.0)
        except asyncio.TimeoutError:
            logger.warning("等待processing_complete超时，检查当前状态...")
            # 即使超时也尝试获取当前状态
        
        logger.info(f"第一步完成，状态: {completion_status}")
        
        # 获取最新状态
        config = {"configurable": {"thread_id": test_chat_id}}
        current_state = await robot_flow_app.aget_state(config)
        
        # 检查dialog_state而不是completion_status
        dialog_state = None
        if hasattr(current_state, 'values') and current_state.values:
            dialog_state = current_state.values.get('dialog_state')
            if not completion_status:
                completion_status = current_state.values.get('completion_status', 'unknown')
        
        logger.info(f"当前dialog_state: {dialog_state}")
        logger.info(f"当前completion_status: {completion_status}")
        
        # 始终尝试保存状态，不管状态如何
        logger.info("正在保存checkpointer状态...")
        
        # 准备保存的数据
        state_data = {
            "step": 1,
            "chat_id": test_chat_id,
            "completion_status": completion_status,
            "dialog_state": dialog_state,
            "timestamp": datetime.now().isoformat(),
            "state_values": current_state.values if hasattr(current_state, 'values') else {},
            "next_actions": current_state.next if hasattr(current_state, 'next') else [],
            "events": events_collected,
            "checkpointer_data": {}
        }
        
        # 尝试获取checkpointer内部数据
        try:
            if hasattr(checkpointer, 'storage'):
                state_data["checkpointer_data"] = dict(checkpointer.storage)
        except Exception as e:
            logger.warning(f"无法获取checkpointer内部数据: {e}")
        
        # 保存状态到JSON文件
        state_file = "/tmp/sas_test_states/step1_state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"状态已保存到: {state_file}")
        logger.info("注意：由于MemorySaver包含不可序列化的对象，后续步骤将创建新的checkpointer实例")
        
        # 根据状态给出相应的结果
        if dialog_state == 'sas_awaiting_task_list_review':
            logger.info("✅ 第一步测试成功完成，可以运行第二步")
        else:
            logger.warning(f"第一步状态可能不符合预期，dialog_state: {dialog_state}, completion_status: {completion_status}")
        
        # 取消收集器任务
        if not collector_task.done():
            collector_task.cancel()
            
    except asyncio.TimeoutError:
        logger.error("第一步处理超时")
    except Exception as e:
        logger.error(f"第一步测试遇到异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_step1_generate_task_list()) 