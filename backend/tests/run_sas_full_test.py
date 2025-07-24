"""
SAS Graph Builder 完整测试运行脚本

此脚本按顺序运行三个测试步骤：
1. 生成任务列表
2. 用户批准任务列表  
3. 用户批准模块步骤并生成XML

每个步骤都会保存状态，可以单独运行每个步骤进行调试
"""

import asyncio
import logging
import os
import sys

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_full_test():
    """运行完整的三步测试"""
    
    logger.info("="*60)
    logger.info("开始运行SAS Graph Builder完整测试")
    logger.info("="*60)
    
    # 清理旧的状态文件
    state_dir = "/tmp/sas_test_states"
    if os.path.exists(state_dir):
        import shutil
        shutil.rmtree(state_dir)
        logger.info("已清理旧的状态文件")
    
    try:
        # 第一步：生成任务列表
        logger.info("\n🚀 开始执行第一步：生成任务列表...")
        from test_sas_step1 import test_step1_generate_task_list
        await test_step1_generate_task_list()
        logger.info("✅ 第一步完成")
        
        # 检查第一步是否成功
        step1_state_file = "/tmp/sas_test_states/step1_state.json"
        if not os.path.exists(step1_state_file):
            logger.error("❌ 第一步状态文件未生成，测试失败")
            return
        
        # 第二步：用户批准任务列表
        logger.info("\n🚀 开始执行第二步：用户批准任务列表...")
        from test_sas_step2 import test_step2_approve_tasks
        await test_step2_approve_tasks()
        logger.info("✅ 第二步完成")
        
        # 检查第二步是否成功
        step2_state_file = "/tmp/sas_test_states/step2_state.json"
        if not os.path.exists(step2_state_file):
            logger.error("❌ 第二步状态文件未生成，测试失败")
            return
        
        # 第三步：用户批准模块步骤并生成XML
        logger.info("\n🚀 开始执行第三步：用户批准模块步骤并生成XML...")
        from test_sas_step3 import test_step3_approve_modules
        await test_step3_approve_modules()
        logger.info("✅ 第三步完成")
        
        # 检查最终结果
        step3_state_file = "/tmp/sas_test_states/step3_final_state.json"
        if os.path.exists(step3_state_file):
            import json
            with open(step3_state_file, 'r', encoding='utf-8') as f:
                final_data = json.load(f)
            
            logger.info("\n" + "="*60)
            logger.info("测试结果总结")
            logger.info("="*60)
            logger.info(f"最终完成状态: {final_data.get('completion_status')}")
            
            if final_data.get('xml_content'):
                logger.info("✅ XML内容已生成")
                logger.info(f"XML内容长度: {len(final_data['xml_content'])} 字符")
            else:
                logger.warning("⚠️ 未检测到XML内容")
            
            # 检查生成的文件
            xml_files = []
            for output_dir in ["/tmp/sas_final_test", "/tmp/sas_simple_test"]:
                if os.path.exists(output_dir):
                    import glob
                    xml_files.extend(glob.glob(f"{output_dir}/**/*.xml", recursive=True))
            
            if xml_files:
                logger.info(f"✅ 找到 {len(xml_files)} 个XML文件:")
                for xml_file in xml_files:
                    logger.info(f"  - {xml_file}")
            
            if final_data.get('completion_status') == 'completed_success' or final_data.get('xml_content') or xml_files:
                logger.info("🎉 完整测试成功完成！")
            else:
                logger.warning("⚠️ 测试可能未完全成功")
        else:
            logger.error("❌ 第三步状态文件未生成，测试失败")
        
    except Exception as e:
        logger.error(f"❌ 测试过程中遇到异常: {e}")
        import traceback
        traceback.print_exc()

def run_single_step(step_number):
    """运行单个测试步骤"""
    
    if step_number == 1:
        logger.info("运行第一步：生成任务列表")
        from test_sas_step1 import test_step1_generate_task_list
        asyncio.run(test_step1_generate_task_list())
    elif step_number == 2:
        logger.info("运行第二步：用户批准任务列表")
        from test_sas_step2 import test_step2_approve_tasks
        asyncio.run(test_step2_approve_tasks())
    elif step_number == 3:
        logger.info("运行第三步：用户批准模块步骤并生成XML")
        from test_sas_step3 import test_step3_approve_modules
        asyncio.run(test_step3_approve_modules())
    else:
        logger.error(f"无效的步骤号: {step_number}，请使用 1, 2, 或 3")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 运行指定步骤
        try:
            step = int(sys.argv[1])
            run_single_step(step)
        except ValueError:
            logger.error("请提供有效的步骤号 (1, 2, 或 3)")
            logger.info("用法:")
            logger.info("  python run_sas_full_test.py     # 运行完整测试")
            logger.info("  python run_sas_full_test.py 1   # 只运行第一步")
            logger.info("  python run_sas_full_test.py 2   # 只运行第二步")
            logger.info("  python run_sas_full_test.py 3   # 只运行第三步")
    else:
        # 运行完整测试
        asyncio.run(run_full_test()) 