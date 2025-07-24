#!/usr/bin/env python3
"""
分析checkpoint_writes表中的状态变化数据
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
    print(f"🔍 分析checkpoint_writes中的流程ID: {TARGET_THREAD_ID}")
    print(f"⏰ 时间: {datetime.now()}")
    print("="*80)
    
    try:
        with get_db_context() as db:
            print(f"📊 正在查询checkpoint_writes数据...")
            
            # 查询checkpoint_writes记录
            query = """
            SELECT 
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                task_id,
                idx,
                channel,
                type,
                blob,
                task_path
            FROM checkpoint_writes 
            WHERE thread_id = :thread_id
            ORDER BY checkpoint_id, idx
            """
            
            result = db.execute(text(query), {"thread_id": TARGET_THREAD_ID})
            records = result.fetchall()
            
            if not records:
                print(f"❌ 没有找到thread_id {TARGET_THREAD_ID} 的写入记录")
                
                # 查找类似的thread_id
                similar_query = """
                SELECT DISTINCT thread_id
                FROM checkpoint_writes 
                WHERE thread_id LIKE :pattern
                ORDER BY thread_id
                LIMIT 10
                """
                
                pattern = f"%{TARGET_THREAD_ID[-8:]}%"
                similar_result = db.execute(text(similar_query), {"pattern": pattern})
                similar_records = similar_result.fetchall()
                
                if similar_records:
                    print("\n📋 找到类似的thread_id:")
                    for record in similar_records:
                        print(f"  - {record[0]}")
                else:
                    print("\n📋 最近的10个thread_id:")
                    recent_query = "SELECT DISTINCT thread_id FROM checkpoint_writes ORDER BY checkpoint_id DESC LIMIT 10"
                    recent_result = db.execute(text(recent_query))
                    recent_records = recent_result.fetchall()
                    for record in recent_records:
                        print(f"  - {record[0]}")
                
                return
            
            print(f"✅ 找到 {len(records)} 条写入记录\n")
            
            # 分析状态变化
            dialog_states = []
            acceptance_changes = []
            key_events = []
            checkpoint_groups = {}
            
            for i, record in enumerate(records):
                checkpoint_id = record.checkpoint_id
                if checkpoint_id not in checkpoint_groups:
                    checkpoint_groups[checkpoint_id] = []
                checkpoint_groups[checkpoint_id].append(record)
            
            # 按checkpoint分组显示
            for checkpoint_idx, (checkpoint_id, group_records) in enumerate(checkpoint_groups.items()):
                print(f"{'='*60}")
                print(f"📝 Checkpoint {checkpoint_idx+1}: {checkpoint_id}")
                print(f"📝 包含 {len(group_records)} 条写入记录")
                print(f"{'='*60}")
                
                for j, record in enumerate(group_records):
                    print(f"\n--- 写入记录 {j+1} ---")
                    print(f"🆔 Task ID: {record.task_id}")
                    print(f"📋 Channel: {record.channel}")
                    print(f"🏷️  Type: {record.type}")
                    print(f"📍 Index: {record.idx}")
                    print(f"🛤️  Task Path: {record.task_path}")
                    
                    # 解析blob数据
                    if record.blob:
                        try:
                            # blob是二进制数据，需要解码
                            blob_str = record.blob.decode('utf-8') if isinstance(record.blob, bytes) else str(record.blob)
                            data = json.loads(blob_str)
                            
                            # 查找关键状态信息
                            if isinstance(data, dict):
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
                                    dialog_states.append((checkpoint_idx, j, dialog_state))
                                    key_events.append((checkpoint_idx, j, 'dialog_state', dialog_state))
                                
                                if task_list_accepted is not None:
                                    icon = "✅" if task_list_accepted else "❌"
                                    print(f"{icon} 任务列表已接受: {task_list_accepted}")
                                    acceptance_changes.append((checkpoint_idx, j, 'task_list', task_list_accepted))
                                    key_events.append((checkpoint_idx, j, 'task_list_accepted', task_list_accepted))
                                
                                if module_steps_accepted is not None:
                                    icon = "✅" if module_steps_accepted else "❌"
                                    print(f"{icon} 模块步骤已接受: {module_steps_accepted}")
                                    acceptance_changes.append((checkpoint_idx, j, 'module_steps', module_steps_accepted))
                                    key_events.append((checkpoint_idx, j, 'module_steps_accepted', module_steps_accepted))
                                
                                if completion_status:
                                    print(f"📊 完成状态: {completion_status}")
                                    key_events.append((checkpoint_idx, j, 'completion_status', completion_status))
                                
                                if is_error:
                                    print(f"🚨 错误状态: {is_error}")
                                
                                if user_input:
                                    print(f"💬 用户输入: {str(user_input)[:80]}...")
                                    key_events.append((checkpoint_idx, j, 'user_input', str(user_input)[:50]))
                                
                                if current_step_description:
                                    print(f"📋 步骤描述: {str(current_step_description)[:80]}...")
                                
                                if clarification_question:
                                    print(f"❓ 确认问题: {str(clarification_question)[:80]}...")
                                
                                # SAS相关数据
                                sas_fields = {}
                                for key, value in data.items():
                                    if key.startswith('sas_step') and value:
                                        if isinstance(value, list):
                                            sas_fields[key] = f"{len(value)} 项"
                                        elif isinstance(value, str) and len(value) > 60:
                                            sas_fields[key] = f"{value[:60]}..."
                                        else:
                                            sas_fields[key] = str(value)[:40]
                                
                                if sas_fields:
                                    print("🤖 SAS数据:")
                                    for key, value in sas_fields.items():
                                        print(f"   {key}: {value}")
                            
                            # 显示数据预览
                            if len(blob_str) > 200:
                                print(f"📄 数据预览: {blob_str[:200]}...")
                            else:
                                print(f"📄 完整数据: {blob_str}")
                                
                        except Exception as e:
                            print(f"❌ 解析blob数据失败: {e}")
                            print(f"原始blob长度: {len(record.blob) if record.blob else 0}")
                
                print()
            
            # 详细分析
            print("="*80)
            print("🔍 详细状态变化分析")
            print("="*80)
            
            # Dialog State 轨迹分析
            if dialog_states:
                print("🎯 Dialog State 变化轨迹:")
                for i, (checkpoint_idx, write_idx, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} Checkpoint {checkpoint_idx+1}-{write_idx+1}: {state}")
                
                # 分析状态序列
                states = [state for _, _, state in dialog_states]
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
                            print(f"   🚨 问题发现：直接跳到了模块步骤生成，跳过了任务审核！")
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
                for checkpoint_idx, write_idx, acc_type, value in acceptance_changes:
                    print(f"   Checkpoint {checkpoint_idx+1}-{write_idx+1}: {acc_type} = {value}")
            
            # 关键事件时间线
            if key_events:
                print(f"\n📅 关键事件时间线:")
                for checkpoint_idx, write_idx, event_type, value in key_events:
                    location = f"Checkpoint {checkpoint_idx+1}-{write_idx+1}"
                    if event_type == 'dialog_state':
                        print(f"   {location}: 🎯 {event_type} = {value}")
                    elif event_type in ['task_list_accepted', 'module_steps_accepted']:
                        icon = "✅" if value else "❌"
                        print(f"   {location}: {icon} {event_type} = {value}")
                    elif event_type == 'user_input':
                        print(f"   {location}: 💬 {event_type} = {value}...")
                    else:
                        print(f"   {location}: 📄 {event_type} = {value}")
            
            # 最终结论
            print(f"\n" + "="*80)
            print("🎯 问题诊断结论")
            print("="*80)
            
            states = [state for _, _, state in dialog_states] if dialog_states else []
            
            if 'sas_step1_tasks_generated' in states and 'sas_awaiting_task_list_review' not in states:
                print("🚨 确认问题：系统跳过了任务审核阶段")
                print("   - 任务生成完成后，应该进入 'sas_awaiting_task_list_review' 状态")
                print("   - 但实际上直接跳转到了其他状态")
                print("   - 这解释了为什么用户没有看到任务审核界面")
                
                # 查找task_list_accepted被设置的位置
                task_accepted_events = [e for e in key_events if e[2] == 'task_list_accepted' and e[3] == True]
                if task_accepted_events:
                    print("\n🔍 发现task_list_accepted被设置为True的位置:")
                    for checkpoint_idx, write_idx, _, _ in task_accepted_events:
                        print(f"   - Checkpoint {checkpoint_idx+1}-{write_idx+1}")
                        
                print("\n🔍 建议检查：")
                print("   1. backend/sas/nodes/review_and_refine.py 中的审核逻辑")
                print("   2. backend/sas/graph_builder.py 中的路由函数")
                print("   3. 是否有代码自动设置 task_list_accepted = True")
                print("   4. 前端是否发送了跳过审核的指令")
            else:
                print("✅ 审核流程看起来正常，问题可能在其他地方")
                if not dialog_states:
                    print("   ⚠️  但是没有找到任何dialog_state变化记录")
    
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis() 