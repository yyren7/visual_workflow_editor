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

from backend.app.routers.sas_chat import SASEventBroadcaster, _process_sas_events
from backend.sas.graph_builder import RootRunIDCollector, create_robot_flow_graph
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
    output_dir = Path("/tmp/sas_simple_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    # 清理之前运行的旧文件
    for f in output_dir.glob("*"):
        if f.is_file():
            f.unlink()

    # 初始用户输入消息
    initial_message ="""ロボットが、
    ハンド１で部品供給ステーションから一次加工品を掴み取り（部品供給）、
    次に加工ステーションに移動し、
    そこでハンド２で加工済み部品を掴んでから、
    ハンド１で一次加工品を加工ステーションに置く、
    最後に加工済み部品を完成エリアへ搬送することで、
    一つの完全な作業サイクルを完了させます。"""
    
    
# "ロボットが、ティーチングポイントP3およびP4で定義された固定の部品供給ステーションから原材料または一次加工品を掴み取り（部品供給）、次にその部品を第二ステーション（ステーション2）へ搬送し、そこでP15で部品を掴んでからRz軸を90度から-90度へ180度回転させ、別の位置P18へ正確に再配置する中間処理を行い、最後に加工済みまたは処理済みと見なされた部品を最終的な設置エリア（ティーチINGポイントP11およびP12で定義）へ搬送して正確に配置することで、一つの完全な作業サイクルを完了させます。"

    # 事件收集器 - 持续运行整个测试过程
    events_collected = []
    completion_status = None
    collector_running = True
    processing_step_status = asyncio.Event()
    
    async def collect_events():
        """收集事件的协程 - 持续运行整个测试过程"""
        nonlocal completion_status, collector_running
        try:
            # 确保广播器已初始化
            if not event_broadcaster.is_initialized():
                await event_broadcaster.initialize()

            event_queue = await event_broadcaster.get_or_create_queue(test_chat_id)
            while collector_running:
                try:
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=10.0)
                    events_collected.append(event_item)
                    logger.debug(f"收集到事件: {event_item.get('type', 'unknown')}")
                    
                    if event_item.get("type") == "processing_complete":
                        # 修复：completion_status 嵌套在 final_state 中
                        final_state_data = event_item.get("data", {}).get("final_state", {})
                        if final_state_data:
                            completion_status = final_state_data.get("completion_status")
                        else:
                            # 兼容旧格式或无final_state的事件
                            completion_status = event_item.get("data", {}).get("completion_status")
                        
                        logger.info(f"处理完成，状态: {completion_status}")
                        # 通知当前步骤处理完成，但不退出收集器
                        processing_step_status.set()
                    elif event_item.get("type") == "agent_state_updated":
                        agent_state = event_item.get("data", {}).get("agent_state", {})
                        if agent_state.get("final_flow_xml_content"):
                            logger.info("检测到 final_flow_xml_content，认为处理完成")
                            completion_status = agent_state.get("completion_status", "completed_success")
                            processing_step_status.set()
                    elif event_item.get("type") == "connection_close":
                        logger.info("连接关闭")
                        break
                except asyncio.TimeoutError:
                    logger.debug("等待事件超时，继续...")
                    continue
        except Exception as e:
            logger.error(f"收集事件时出错: {e}")
            import traceback
            traceback.print_exc()

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
        
        # 获取RootRunIDCollector
        root_run_id_collector = RootRunIDCollector()
        
        # 处理消息
        # 注意：在新的流程中，我们可能需要传递更多的配置信息
        config = {
            "configurable": {"thread_id": test_chat_id},
            "callbacks": [root_run_id_collector],
            "output_dir_path": str(output_dir) # 将输出目录传递给graph
        }
        
        # 修正：将config作为关键字参数传递给_process_sas_events
        await _process_sas_events(
            chat_id=test_chat_id, 
            message_content=message_content, 
            sas_app=robot_flow_app, 
            flow_id=test_chat_id,
            config=config # 传递config
        )
        
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
        
        # 如果第一步需要确认，则等待用户输入批准命令
        if status1 == 'needs_clarification':
            logger.info("任务列表已生成，等待用户批准。")
            await asyncio.sleep(1) # 短暂等待，确保前端可以接收到状态
            # 第二步：用户通过前端绿色按钮批准任务列表
            status2 = await process_message_and_wait("FRONTEND_APPROVE_TASKS", "第二步：用户批准任务列表")
            logger.info(f"第二步完成，状态: {status2}")
            
            # 如果第二步需要确认，则等待用户输入批准命令
            if status2 == 'needs_clarification':
                logger.info("模块步骤已生成，等待用户批准。")
                await asyncio.sleep(1) # 短暂等待
                # 第三步：用户通过前端绿色按钮批准模块步骤
                status3 = await process_message_and_wait("FRONTEND_APPROVE_MODULE_STEPS", "第三步：用户批准模块步骤")
                logger.info(f"第三步完成，状态: {status3}")
                final_status = status3
            else:
                final_status = status2
        else:
            final_status = status1
        
        # 在最后，我们需要主动检查最终状态，因为XML生成可能是最后一个异步步骤
        # 增加一个更长的等待时间，以确保所有异步操作（如文件写入）都有时间完成。
        logger.info("等待最终的XML生成和状态更新...")
        await asyncio.sleep(15) # 增加等待时间

        # 再次检查最终状态
        final_status_from_state = None
        xml_content_from_state = None
        try:
            config_get_state = {"configurable": {"thread_id": test_chat_id}}
            final_state_data = await robot_flow_app.aget_state(config_get_state)
            
            if final_state_data and final_state_data.values:
                final_state = final_state_data.values
                
                final_status_from_state = final_state.get('completion_status')
                if final_status_from_state:
                    logger.info(f"从 aget_state 获取的最终状态: {final_status_from_state}")
                    final_status = final_status_from_state # 更新最终状态

                # 从最终状态获取XML内容
                xml_content_from_state = final_state.get('final_flow_xml_content')
                if xml_content_from_state:
                    logger.info("=== 从 aget_state 获取的最终XML内容 ===")
                    logger.info(xml_content_from_state)
                    # 将内容写入文件以便验证
                    (output_dir / "final_flow_from_state.xml").write_text(xml_content_from_state, encoding="utf-8")
            else:
                logger.warning("aget_state返回了空的状态数据")

        except Exception as e:
            logger.warning(f"获取最终状态或XML内容失败: {e}", exc_info=True)

        # 检查最终结果
        logger.info(f"测试完成，最终状态: {final_status}")
        
        # 检查生成的文件
        logger.info("=== 检查生成的文件 ===")
        xml_files_found = list(output_dir.rglob("*.xml"))
        if xml_files_found:
            for file_path in xml_files_found:
                logger.info(f"找到的XML文件: {file_path}")
                # 打印非空文件的内容
                if file_path.stat().st_size > 0:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logger.info(f"--- 文件内容: {file_path.name} ({len(content)} 字符) ---")
                        logger.info(content[:800] + "..." if len(content) > 800 else content)
                        logger.info("-" * (len(f"--- 文件内容: {file_path.name} ({len(content)} 字符) ---")))
                else:
                    logger.info(f"文件为空: {file_path.name}")
        else:
            logger.warning("在输出目录中未找到生成的XML文件")
            
        # 从事件中寻找最终的XML内容
        xml_content_from_event = None
        for event in reversed(events_collected):
            if event.get("type") == "agent_state_updated":
                agent_state = event.get("data", {}).get("agent_state", {})
                if agent_state.get("final_flow_xml_content"):
                    xml_content_from_event = agent_state["final_flow_xml_content"]
                    break
        
        if xml_content_from_event:
            logger.info("=== 从事件中获取的最终XML内容 ===")
            logger.info(xml_content_from_event)

        if final_status == "completed_success" or any(f.stat().st_size > 0 for f in xml_files_found):
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
    
    此测试模拟了完整的SAS工作流程，包括多步骤的用户批准。
    它使用`_process_sas_events`函数来处理初始用户输入和后续的
    模拟前端批准消息（`FRONTEND_APPROVE_TASKS` 和 `FRONTEND_APPROVE_MODULE_STEPS`）。
    
    测试流程：
    1.  **初始请求**: 发送日语描述，AI生成任务列表。
    2.  **等待批准**: Graph状态变为 `needs_clarification`，等待用户批准任务列表。
    3.  **批准任务列表**: 发送 `FRONTEND_APPROVE_TASKS`，AI根据任务列表生成模块步骤。
    4.  **等待批准**: Graph状态再次变为 `needs_clarification`，等待用户批准模块步骤。
    5.  **批准模块步骤**: 发送 `FRONTEND_APPROVE_MODULE_STEPS`，AI开始生成最终的XML文件。
    6.  **完成**: Graph执行完毕，生成 `_merged.xml` 文件并更新最终状态。
    """
    
    asyncio.run(test_simple_workflow())
