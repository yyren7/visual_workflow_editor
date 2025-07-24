"""
SAS Graph Builder 测试文件

此文件包含从 backend/sas/graph_builder.py 中移除的测试代码。
这些测试代码已从主模块中移除，以防止意外执行导致的问题。
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
import aioconsole

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

async def test_simple_workflow():
    """简单的工作流测试 - 使用完整的SAS chat路由器和事件广播器"""
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running simple workflow test...")
    
    # Get LLM configuration
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    gemini_model_name = os.getenv("GEMINI_MODEL")
    if not gemini_api_key:
        logger.error("GOOGLE_API_KEY not found. Skipping simple test.")
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
    os.makedirs("/tmp/sas_simple_test", exist_ok=True)
    
    # 初始用户输入消息
    initial_message = "ロボットが、ティーチングポイントP3およびP4で定義された固定の部品供給ステーションから原材料または一次加工品を掴み取り（部品供給）、次にその部品を第二ステーション（ステーション2）へ搬送し、そこでP15で部品を掴んでからRz軸を90度から-90度へ180度回転させ、別の位置P18へ正確に再配置する中間処理を行い、最後に加工済みまたは処理済みと見なされた部品を最終的な設置エリア（ティーチングポイントP11およびP12で定義）へ搬送して正確に配置することで、一つの完全な作業サイクルを完了させます。"
    
    # 事件收集器 - 持续运行整个测试过程
    events_collected = []
    completion_status = None
    collector_running = True
    processing_step_status = asyncio.Event()
    
    async def collect_events():
        """收集事件的协程 - 持续运行整个测试过程"""
        nonlocal completion_status, collector_running
        try:
            event_queue = await event_broadcaster.get_or_create_queue(test_chat_id)
            while collector_running:
                try:
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=10.0)
                    events_collected.append(event_item)
                    logger.debug(f"收集到事件: {event_item.get('type', 'unknown')}")
                    
                    if event_item.get("type") == "processing_complete":
                        completion_status = event_item.get("data", {}).get("completion_status")
                        logger.info(f"处理完成，状态: {completion_status}")
                        # 通知当前步骤处理完成，但不退出收集器
                        processing_step_status.set()
                    elif event_item.get("type") == "connection_close":
                        logger.info("连接关闭")
                        break
                except asyncio.TimeoutError:
                    logger.debug("等待事件超时，继续...")
                    continue
        except Exception as e:
            logger.error(f"收集事件时出错: {e}")
    
    # 启动事件收集器 - 在整个测试过程中持续运行
    collector_task = asyncio.create_task(collect_events())
    
    # 辅助函数：等待处理完成并返回状态
    async def process_message_and_wait(message_content, step_name):
        nonlocal completion_status
        logger.info(f"=== {step_name} ===")
        logger.info(f"发送消息: {message_content[:100]}...")
        
        # 重置步骤状态
        processing_step_status.clear()
        completion_status = None
        
        # 处理消息
        await _process_sas_events(test_chat_id, message_content, robot_flow_app, test_chat_id)
        
        # 等待当前步骤处理完成
        try:
            await asyncio.wait_for(processing_step_status.wait(), timeout=300.0)
        except asyncio.TimeoutError:
            logger.warning(f"{step_name}处理超时")
            completion_status = "timeout"
        
        logger.info(f"{step_name}完成，状态: {completion_status}")
        return completion_status
    
    try:
        # 第一步：生成任务列表
        status1 = await process_message_and_wait(initial_message, "第一步：生成任务列表")
        logger.info(f"第一步完成，状态: {status1}")
        
        final_status = status1
        
        # 如果第一步需要确认，则等待用户输入批准命令
        if status1 == 'needs_clarification':
            await aioconsole.ainput("任务列表已生成，等待用户批准。请按回车键发送批准命令（FRONTEND_APPROVE_TASKS）...")
            # 第二步：用户通过前端绿色按钮批准任务列表
            status2 = await process_message_and_wait("FRONTEND_APPROVE_TASKS", "第二步：用户批准任务列表")
            logger.info(f"第二步完成，状态: {status2}")
            final_status = status2
            
            # 如果第二步需要确认，则等待用户输入批准命令
            if status2 == 'needs_clarification':
                await aioconsole.ainput("模块步骤已生成，等待用户批准。请按回车键发送批准命令（FRONTEND_APPROVE_MODULE_STEPS）...")
                # 第三步：用户通过前端绿色按钮批准模块步骤
                status3 = await process_message_and_wait("FRONTEND_APPROVE_MODULE_STEPS", "第三步：用户批准模块步骤")
                logger.info(f"第三步完成，状态: {status3}")
                final_status = status3
                
                # 继续等待XML生成完成
                if status3 not in ['completed_success', 'error']:
                    logger.info("等待XML生成完成...")
                    # 等待一段时间看是否有更多处理
                    await asyncio.sleep(5)
                    # 检查最终状态
                    try:
                        config = {"configurable": {"thread_id": test_chat_id}}
                        final_state = await robot_flow_app.aget_state(config)
                        if hasattr(final_state, 'values') and final_state.values:
                            final_completion = final_state.values.get('completion_status')
                            if final_completion:
                                final_status = final_completion
                                logger.info(f"最终状态: {final_status}")
                    except Exception as e:
                        logger.warning(f"获取最终状态失败: {e}")
        
        # 检查最终结果
        logger.info(f"测试完成，最终状态: {final_status}")
        
        # 检查生成的文件
        output_dir = Path("/tmp/sas_simple_test")
        if output_dir.exists():
            logger.info("=== 检查生成的文件 ===")
            xml_files_found = list(output_dir.rglob("*.xml"))
            if xml_files_found:
                for file_path in xml_files_found:
                    logger.info(f"生成的XML文件: {file_path}")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logger.info(f"文件内容预览 ({len(content)} 字符):")
                        logger.info(content[:500] + "..." if len(content) > 500 else content)
            else:
                logger.warning("未找到生成的XML文件")
        else:
            logger.warning(f"输出目录不存在: {output_dir}")
        
        # 检查收集到的事件中是否有XML内容
        xml_content = None
        for event in events_collected:
            if event.get("type") == "agent_state_updated":
                agent_state = event.get("data", {}).get("agent_state", {})
                if agent_state.get("final_flow_xml_content"):
                    xml_content = agent_state["final_flow_xml_content"]
                    break
        
        if xml_content:
            logger.info("=== 从事件中获取的最终XML内容 ===")
            logger.info(xml_content)
        
        if final_status == "completed_success" or xml_files_found or xml_content:
            logger.info("✅ 测试成功完成")
        else:
            logger.warning("⚠️ 测试可能未完全成功")
            
    except Exception as e:
        logger.error(f"测试遇到异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理事件收集器
        logger.info("清理事件收集器...")
        collector_running = False
        if not collector_task.done():
            collector_task.cancel()
            try:
                await collector_task
            except asyncio.CancelledError:
                pass
        logger.info("测试清理完成")

if __name__ == '__main__':
    """
    主测试入口点
    
    这个测试文件包含了从 backend/sas/graph_builder.py 中移除的测试代码。
    使用完整的SAS chat路由器和事件广播器来测试工作流程。
    通过_process_sas_events函数处理特殊消息（FRONTEND_APPROVE_TASKS和FRONTEND_APPROVE_MODULE_STEPS），
    模拟前端绿色按钮的批准操作，完成完整的工作流程并生成XML文件。
    
    测试流程：
    1. 发送初始用户输入 -> 生成任务列表 -> 等待确认
    2. 发送FRONTEND_APPROVE_TASKS -> 生成模块步骤 -> 等待确认  
    3. 发送FRONTEND_APPROVE_MODULE_STEPS -> 生成XML文件 -> 完成
    """
    
    asyncio.run(test_simple_workflow())
