"""
SAS Graph Builder 测试 - 第三步：用户批准模块步骤

此文件从第二步加载状态，执行用户批准模块步骤，最终生成XML文件
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

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

async def test_step3_approve_modules():
    """第三步：用户批准模块步骤并生成XML文件"""
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running step 3: Approve module steps and generate XML...")
    
    # 检查第二步状态文件是否存在
    state_file = "/tmp/sas_test_states/step2_state.json"
    if not os.path.exists(state_file):
        logger.error(f"第二步状态文件不存在: {state_file}")
        logger.error("请先运行 test_sas_step2.py")
        return
    
    # 加载第二步的状态
    with open(state_file, 'r', encoding='utf-8') as f:
        step2_data = json.load(f)
    
    logger.info(f"加载第二步状态，时间戳: {step2_data['timestamp']}")
    logger.info(f"第二步完成状态: {step2_data['completion_status']}")
    
    if step2_data['completion_status'] != 'needs_clarification':
        logger.error(f"第二步状态不正确，期望 'needs_clarification'，实际: {step2_data['completion_status']}")
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
    
    # 创建内存checkpointer并恢复状态
    checkpointer = MemorySaver()
    
    # 尝试恢复checkpointer状态
    if step2_data.get('checkpointer_data'):
        try:
            if hasattr(checkpointer, 'storage'):
                checkpointer.storage.update(step2_data['checkpointer_data'])
            logger.info("Checkpointer状态已恢复")
        except Exception as e:
            logger.warning(f"恢复checkpointer状态失败: {e}")
    
    robot_flow_app = create_robot_flow_graph(llm=llm, checkpointer=checkpointer)
    
    # 创建事件广播器和使用相同的chat_id
    event_broadcaster = SASEventBroadcaster()
    test_chat_id = step2_data['chat_id']
    
    # 设置输出目录
    os.makedirs("/tmp/sas_final_test", exist_ok=True)
    
    # 事件收集器
    events_collected = []
    completion_status = None
    processing_complete = asyncio.Event()
    xml_content = None
    
    async def collect_events():
        """收集事件的协程"""
        nonlocal completion_status, xml_content
        try:
            event_queue = await event_broadcaster.get_or_create_queue(test_chat_id)
            while True:
                try:
                    event_item = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    events_collected.append(event_item)
                    logger.info(f"收集到事件: {event_item.get('type', 'unknown')}")
                    
                    # 检查是否有XML内容
                    if event_item.get("type") == "agent_state_updated":
                        agent_state = event_item.get("data", {}).get("agent_state", {})
                        if agent_state.get("final_flow_xml_content"):
                            xml_content = agent_state["final_flow_xml_content"]
                            logger.info("检测到XML内容已生成")
                    
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
        
        logger.info("=== 第三步：用户批准模块步骤 ===")
        
        # 发送用户批准消息
        approve_message = "FRONTEND_APPROVE_MODULE_STEPS"
        logger.info(f"发送批准消息: {approve_message}")
        
        # 处理消息
        await _process_sas_events(test_chat_id, approve_message, robot_flow_app, test_chat_id)
        
        # 等待处理完成
        await asyncio.wait_for(processing_complete.wait(), timeout=300.0)
        
        logger.info(f"第三步完成，状态: {completion_status}")
        
        # 如果没有完全完成，等待一段时间看是否还有更多处理
        if completion_status not in ['completed_success', 'error'] and not xml_content:
            logger.info("等待XML生成完成...")
            await asyncio.sleep(10)
            
            # 再次检查状态
            try:
                config = {"configurable": {"thread_id": test_chat_id}}
                final_state = await robot_flow_app.aget_state(config)
                if hasattr(final_state, 'values') and final_state.values:
                    final_completion = final_state.values.get('completion_status')
                    if final_completion:
                        completion_status = final_completion
                        logger.info(f"最终状态: {completion_status}")
                    
                    # 检查是否有XML内容
                    if final_state.values.get('final_flow_xml_content'):
                        xml_content = final_state.values['final_flow_xml_content']
                        logger.info("从最终状态获取到XML内容")
            except Exception as e:
                logger.warning(f"获取最终状态失败: {e}")
        
        # 保存最终状态和结果
        logger.info("正在保存第三步最终状态...")
        
        # 获取当前状态
        config = {"configurable": {"thread_id": test_chat_id}}
        current_state = await robot_flow_app.aget_state(config)
        
        # 准备保存的数据
        state_data = {
            "step": 3,
            "chat_id": test_chat_id,
            "completion_status": completion_status,
            "timestamp": datetime.now().isoformat(),
            "state_values": current_state.values if hasattr(current_state, 'values') else {},
            "next_actions": current_state.next if hasattr(current_state, 'next') else [],
            "events": events_collected,
            "xml_content": xml_content,
            "checkpointer_data": {},
            "previous_step_data": step2_data
        }
        
        # 尝试获取checkpointer内部数据
        try:
            if hasattr(checkpointer, 'storage'):
                state_data["checkpointer_data"] = dict(checkpointer.storage)
        except Exception as e:
            logger.warning(f"无法获取checkpointer内部数据: {e}")
        
        # 保存到文件
        step3_state_file = "/tmp/sas_test_states/step3_final_state.json"
        with open(step3_state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"第三步最终状态已保存到: {step3_state_file}")
        
        # 检查生成的XML文件
        output_dir = Path("/tmp/sas_final_test")
        xml_files_found = list(output_dir.rglob("*.xml"))
        
        if xml_files_found:
            logger.info("=== 检查生成的XML文件 ===")
            for file_path in xml_files_found:
                logger.info(f"生成的XML文件: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.info(f"文件内容预览 ({len(content)} 字符):")
                    logger.info(content[:500] + "..." if len(content) > 500 else content)
        elif xml_content:
            # 保存从事件中获取的XML内容
            xml_file_path = "/tmp/sas_final_test/generated_flow.xml"
            with open(xml_file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            logger.info(f"=== 从事件中保存的XML内容 ===")
            logger.info(f"XML已保存到: {xml_file_path}")
            logger.info(f"内容预览 ({len(xml_content)} 字符):")
            logger.info(xml_content[:500] + "..." if len(xml_content) > 500 else xml_content)
        else:
            logger.warning("未找到生成的XML文件或内容")
        
        # 最终判断
        if completion_status == "completed_success" or xml_files_found or xml_content:
            logger.info("✅ 第三步测试成功完成 - XML文件已生成")
        else:
            logger.warning("⚠️ 第三步测试可能未完全成功")
        
        # 取消收集器任务
        if not collector_task.done():
            collector_task.cancel()
            
    except asyncio.TimeoutError:
        logger.error("第三步处理超时")
    except Exception as e:
        logger.error(f"第三步测试遇到异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_step3_approve_modules()) 