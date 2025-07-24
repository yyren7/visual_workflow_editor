#!/usr/bin/env python3
"""
分析LangGraph checkpoint数据，查看状态变化过程（修复版本）
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
            
            # 查询checkpoint记录 - 使用正确的列名
            query = """
            SELECT 
                checkpoint_id,
                thread_id,
                parent_checkpoint_id,
                checkpoint_ns,
                type,
                checkpoint,
                metadata
            FROM checkpoints 
            WHERE thread_id = :thread_id
            ORDER BY checkpoint_id
            """
            
            result = db.execute(text(query), {"thread_id": TARGET_THREAD_ID})
            records = result.fetchall()
            
            if not records:
                print(f"❌ 没有找到thread_id {TARGET_THREAD_ID} 的记录")
                
                # 查找类似的thread_id
                similar_query = """
                SELECT DISTINCT thread_id
                FROM checkpoints 
                WHERE thread_id LIKE :pattern
                ORDER BY thread_id
                LIMIT 10
                """
                
                # 使用最后几位字符匹配
                pattern = f"%{TARGET_THREAD_ID[-8:]}%"
                similar_result = db.execute(text(similar_query), {"pattern": pattern})
                similar_records = similar_result.fetchall()
                
                if similar_records:
                    print("\n📋 找到类似的thread_id:")
                    for record in similar_records:
                        print(f"  - {record[0]}")
                else:
                    print("\n📋 最近的10个thread_id:")
                    recent_query = "SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 10"
                    recent_result = db.execute(text(recent_query))
                    recent_records = recent_result.fetchall()
                    for record in recent_records:
                        print(f"  - {record[0]}")
                
                return
            
            print(f"✅ 找到 {len(records)} 条checkpoint记录\n")
            
            # 分析状态变化
            dialog_states = []
            acceptance_changes = []
            step_descriptions = []
            key_events = []
            
            for i, record in enumerate(records):
                print(f"{'='*60}")
                print(f"📝 Checkpoint {i+1}/{len(records)}")
                print(f"🆔 ID: {record.checkpoint_id}")
                print(f"🏷️  Namespace: {record.checkpoint_ns}")
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
                            dialog_states.append((i, dialog_state))
                            key_events.append((i, 'dialog_state', dialog_state))
                        
                        if task_list_accepted is not None:
                            icon = "✅" if task_list_accepted else "❌"
                            print(f"{icon} 任务列表已接受: {task_list_accepted}")
                            acceptance_changes.append((i, 'task_list', task_list_accepted))
                            key_events.append((i, 'task_list_accepted', task_list_accepted))
                        
                        if module_steps_accepted is not None:
                            icon = "✅" if module_steps_accepted else "❌"
                            print(f"{icon} 模块步骤已接受: {module_steps_accepted}")
                            acceptance_changes.append((i, 'module_steps', module_steps_accepted))
                            key_events.append((i, 'module_steps_accepted', module_steps_accepted))
                        
                        if completion_status:
                            print(f"📊 完成状态: {completion_status}")
                            key_events.append((i, 'completion_status', completion_status))
                        
                        if is_error:
                            print(f"🚨 错误状态: {is_error}")
                            key_events.append((i, 'is_error', is_error))
                        
                        if user_input:
                            print(f"💬 用户输入: {str(user_input)[:100]}...")
                            key_events.append((i, 'user_input', str(user_input)[:50]))
                        
                        if current_step_description:
                            print(f"📋 步骤描述: {str(current_step_description)[:100]}...")
                            step_descriptions.append((i, current_step_description))
                        
                        if clarification_question:
                            print(f"❓ 确认问题: {str(clarification_question)[:100]}...")
                            key_events.append((i, 'clarification_question', str(clarification_question)[:50]))
                        
                        # SAS相关数据
                        sas_fields = {}
                        for key, value in data.items():
                            if key.startswith('sas_step') and value:
                                if isinstance(value, list):
                                    sas_fields[key] = f"{len(value)} 项"
                                elif isinstance(value, str) and len(value) > 80:
                                    sas_fields[key] = f"{value[:80]}..."
                                else:
                                    sas_fields[key] = str(value)[:50]
                        
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
                        if metadata and metadata != {}:
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
                for i, (checkpoint_num, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} Checkpoint {checkpoint_num+1}: {state}")
                
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
                for checkpoint_num, acc_type, value in acceptance_changes:
                    print(f"   Checkpoint {checkpoint_num+1}: {acc_type} = {value}")
            
            # 关键事件时间线
            if key_events:
                print(f"\n📅 关键事件时间线:")
                for checkpoint_num, event_type, value in key_events:
                    if event_type == 'dialog_state':
                        print(f"   Checkpoint {checkpoint_num+1}: 🎯 {event_type} = {value}")
                    elif event_type in ['task_list_accepted', 'module_steps_accepted']:
                        icon = "✅" if value else "❌"
                        print(f"   Checkpoint {checkpoint_num+1}: {icon} {event_type} = {value}")
                    elif event_type == 'user_input':
                        print(f"   Checkpoint {checkpoint_num+1}: 💬 {event_type} = {value}...")
                    else:
                        print(f"   Checkpoint {checkpoint_num+1}: 📄 {event_type} = {value}")
            
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
                task_accepted_events = [e for e in key_events if e[1] == 'task_list_accepted' and e[2] == True]
                if task_accepted_events:
                    print("\n🔍 发现task_list_accepted被设置为True的时间点:")
                    for checkpoint_num, _, _ in task_accepted_events:
                        print(f"   - Checkpoint {checkpoint_num+1}")
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