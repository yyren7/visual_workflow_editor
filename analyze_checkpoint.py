#!/usr/bin/env python3
"""
分析LangGraph checkpoint数据，查看状态变化过程
"""

import sys
import os
sys.path.append('/workspace')

import json
import logging
from datetime import datetime
from database.connection import get_db_context
from sqlalchemy import text

TARGET_THREAD_ID = '26f8c147-7a85-42a9-ad77-9fffae46d64c'

# 配置基本日志
logging.basicConfig(level=logging.WARNING)

def run_analysis():
    print(f"🔍 分析流程ID: {TARGET_THREAD_ID}")
    print(f"⏰ 时间: {datetime.now()}")
    print("="*80)
    
    try:
        with get_db_context() as db:
            print(f"📊 正在查询checkpoint数据...")
            
            # 查询checkpoint记录
            query = """
            SELECT 
                checkpoint_id,
                thread_id,
                parent_checkpoint_id,
                type,
                checkpoint,
                metadata,
                created_at
            FROM checkpoints 
            WHERE thread_id = :thread_id
            ORDER BY created_at ASC
            """
            
            result = db.execute(text(query), {"thread_id": TARGET_THREAD_ID})
            records = result.fetchall()
            
            if not records:
                print(f"❌ 没有找到thread_id {TARGET_THREAD_ID} 的记录")
                
                # 查找最近的记录
                recent_query = """
                SELECT DISTINCT thread_id, created_at
                FROM checkpoints 
                ORDER BY created_at DESC
                LIMIT 10
                """
                recent_result = db.execute(text(recent_query))
                recent_records = recent_result.fetchall()
                
                print("\n📋 最近的10个thread_id:")
                for record in recent_records:
                    print(f"  - {record.thread_id} ({record.created_at})")
                
                return
            
            print(f"✅ 找到 {len(records)} 条checkpoint记录\n")
            
            # 分析状态变化
            dialog_states = []
            acceptance_changes = []
            step_descriptions = []
            
            for i, record in enumerate(records):
                print(f"{'='*60}")
                print(f"📝 Checkpoint {i+1}/{len(records)}")
                print(f"🕐 时间: {record.created_at}")
                print(f"🆔 ID: {record.checkpoint_id}")
                print(f"📋 类型: {record.type}")
                print(f"👤 父级: {record.parent_checkpoint_id}")
                
                if record.checkpoint:
                    try:
                        data = json.loads(record.checkpoint) if isinstance(record.checkpoint, str) else record.checkpoint
                        
                        # 提取关键状态信息
                        dialog_state = data.get('dialog_state')
                        task_list_accepted = data.get('task_list_accepted')
                        module_steps_accepted = data.get('module_steps_accepted')
                        completion_status = data.get('completion_status')
                        is_error = data.get('is_error')
                        user_input = data.get('user_input')
                        current_step_description = data.get('current_step_description')
                        clarification_question = data.get('clarification_question')
                        
                        # 显示关键状态
                        if dialog_state:
                            print(f"🎯 对话状态: {dialog_state}")
                            dialog_states.append((record.created_at, dialog_state))
                        
                        if task_list_accepted is not None:
                            icon = "✅" if task_list_accepted else "❌"
                            print(f"{icon} 任务列表已接受: {task_list_accepted}")
                            acceptance_changes.append((record.created_at, 'task_list', task_list_accepted))
                        
                        if module_steps_accepted is not None:
                            icon = "✅" if module_steps_accepted else "❌"
                            print(f"{icon} 模块步骤已接受: {module_steps_accepted}")
                            acceptance_changes.append((record.created_at, 'module_steps', module_steps_accepted))
                        
                        if completion_status:
                            print(f"📊 完成状态: {completion_status}")
                        
                        if is_error:
                            print(f"🚨 错误状态: {is_error}")
                        
                        if user_input:
                            print(f"💬 用户输入: {str(user_input)[:100]}...")
                        
                        if current_step_description:
                            print(f"📋 步骤描述: {str(current_step_description)[:100]}...")
                            step_descriptions.append((record.created_at, current_step_description))
                        
                        if clarification_question:
                            print(f"❓ 确认问题: {str(clarification_question)[:100]}...")
                        
                        # SAS相关数据
                        sas_fields = {}
                        for key, value in data.items():
                            if key.startswith('sas_step') and value:
                                if isinstance(value, list):
                                    sas_fields[key] = f"{len(value)} 项"
                                elif isinstance(value, str) and len(value) > 80:
                                    sas_fields[key] = f"{value[:80]}..."
                                else:
                                    sas_fields[key] = value
                        
                        if sas_fields:
                            print("🤖 SAS数据:")
                            for key, value in sas_fields.items():
                                print(f"   {key}: {value}")
                        
                    except Exception as e:
                        print(f"❌ 解析checkpoint数据失败: {e}")
                        print(f"原始数据长度: {len(str(record.checkpoint)) if record.checkpoint else 0}")
                
                # 解析metadata
                if record.metadata:
                    try:
                        metadata = json.loads(record.metadata) if isinstance(record.metadata, str) else record.metadata
                        print(f"📝 元数据: {json.dumps(metadata, ensure_ascii=False)}")
                    except:
                        print(f"📝 元数据(原始): {str(record.metadata)[:100]}")
                
                print()
            
            # 详细分析
            print("="*80)
            print("🔍 详细状态变化分析")
            print("="*80)
            
            # Dialog State 轨迹分析
            if dialog_states:
                print("🎯 Dialog State 变化轨迹:")
                for i, (timestamp, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} {timestamp}: {state}")
                
                # 分析状态序列
                states = [state for _, state in dialog_states]
                print(f"\n📊 状态序列:")
                print(f"   {' → '.join(states)}")
                
                # 检查关键问题：是否跳过了任务审核
                print(f"\n🔍 关键问题分析:")
                
                if 'sas_step1_tasks_generated' in states:
                    step1_idx = states.index('sas_step1_tasks_generated')
                    
                    if step1_idx + 1 < len(states):
                        next_state = states[step1_idx + 1]
                        print(f"   ✓ 任务生成后的下一个状态: {next_state}")
                        
                        if next_state == 'sas_awaiting_task_list_review':
                            print(f"   ✅ 正常：进入了任务审核状态")
                        elif next_state == 'sas_step2_module_steps_generated_for_review':
                            print(f"   🚨 问题：直接跳到了模块步骤生成，跳过了任务审核！")
                        else:
                            print(f"   ⚠️  异常：跳转到了意外的状态 {next_state}")
                    else:
                        print(f"   ⚠️  任务生成后没有后续状态")
                
                # 查找是否有审核相关状态
                review_states = [s for s in states if 'awaiting' in s or 'review' in s]
                if review_states:
                    print(f"   📋 发现的审核状态: {review_states}")
                else:
                    print(f"   🚨 警告：没有发现任何审核状态！")
            
            # 接受状态变化分析
            if acceptance_changes:
                print(f"\n✅ 接受状态变化:")
                for timestamp, acc_type, value in acceptance_changes:
                    print(f"   {timestamp}: {acc_type} = {value}")
            
            # 步骤描述分析
            if step_descriptions:
                print(f"\n📋 步骤描述变化:")
                for timestamp, desc in step_descriptions:
                    print(f"   {timestamp}: {desc}")
            
            # 最终结论
            print(f"\n" + "="*80)
            print("🎯 问题诊断结论")
            print("="*80)
            
            states = [state for _, state in dialog_states] if dialog_states else []
            
            if 'sas_step1_tasks_generated' in states and 'sas_awaiting_task_list_review' not in states:
                print("🚨 确认问题：系统跳过了任务审核阶段")
                print("   - 任务生成完成后，应该进入 'sas_awaiting_task_list_review' 状态")
                print("   - 但实际上直接跳转到了其他状态")
                print("   - 这解释了为什么用户没有看到任务审核界面")
                
                # 查找可能的原因
                if any('task_list_accepted' in str(record.checkpoint) for record in records):
                    print("\n🔍 可能原因分析：")
                    print("   - 检查是否有代码自动设置 task_list_accepted = True")
                    print("   - 检查路由逻辑是否正确处理审核状态")
                    print("   - 检查是否有跳过审核的特殊条件")
            else:
                print("✅ 审核流程正常，问题可能在其他地方")
    
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis() 