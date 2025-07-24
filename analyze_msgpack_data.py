#!/usr/bin/env python3
"""
分析checkpoint_writes表中的msgpack编码数据
"""

import sys
import os
sys.path.append('/workspace')

import json
import logging
from datetime import datetime
from database.connection import get_db_context
from sqlalchemy import text

# 尝试导入msgpack
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    print("警告：msgpack未安装，将尝试安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "msgpack"])
    import msgpack
    MSGPACK_AVAILABLE = True

TARGET_THREAD_ID = '26f8c147-7a85-42a9-ad77-9fffae46d64c'

# 配置基本日志
logging.basicConfig(level=logging.WARNING)

def decode_blob(blob_data, blob_type):
    """解码blob数据"""
    if not blob_data:
        return None
    
    try:
        if blob_type == 'msgpack':
            # 使用msgpack解码
            return msgpack.unpackb(blob_data, raw=False, strict_map_key=False)
        elif blob_type == 'null' or blob_type is None:
            # null类型，尝试UTF-8解码
            if isinstance(blob_data, bytes):
                decoded = blob_data.decode('utf-8')
                if decoded.strip():
                    try:
                        return json.loads(decoded)
                    except:
                        return decoded
                return None
            return blob_data
        else:
            # 其他类型，尝试多种解码方式
            if isinstance(blob_data, bytes):
                # 先尝试msgpack
                try:
                    return msgpack.unpackb(blob_data, raw=False, strict_map_key=False)
                except:
                    pass
                
                # 再尝试UTF-8 + JSON
                try:
                    decoded = blob_data.decode('utf-8')
                    return json.loads(decoded)
                except:
                    pass
                
                # 最后返回字符串
                try:
                    return blob_data.decode('utf-8')
                except:
                    return f"<binary data: {len(blob_data)} bytes>"
            
            return blob_data
    except Exception as e:
        return f"<decode error: {e}>"

def run_analysis():
    print(f"🔍 分析msgpack编码的流程ID: {TARGET_THREAD_ID}")
    print(f"⏰ 时间: {datetime.now()}")
    print("="*80)
    
    try:
        with get_db_context() as db:
            print(f"📊 正在查询checkpoint_writes数据...")
            
            # 查询有关键状态信息的记录
            important_channels = [
                'dialog_state', 'task_list_accepted', 'module_steps_accepted',
                'completion_status', 'user_input', 'clarification_question',
                'current_step_description', 'sas_step1_generated_tasks',
                'sas_step2_module_steps', 'current_user_request'
            ]
            
            query = """
            SELECT 
                thread_id,
                checkpoint_id,
                task_id,
                idx,
                channel,
                type,
                blob,
                task_path
            FROM checkpoint_writes 
            WHERE thread_id = :thread_id
            AND channel = ANY(:channels)
            ORDER BY checkpoint_id, idx
            """
            
            result = db.execute(text(query), {
                "thread_id": TARGET_THREAD_ID,
                "channels": important_channels
            })
            records = result.fetchall()
            
            if not records:
                print(f"❌ 没有找到相关记录")
                return
            
            print(f"✅ 找到 {len(records)} 条相关记录\n")
            
            # 分析状态变化
            dialog_states = []
            acceptance_changes = []
            key_events = []
            
            # 按checkpoint分组
            checkpoint_groups = {}
            for record in records:
                checkpoint_id = record.checkpoint_id
                if checkpoint_id not in checkpoint_groups:
                    checkpoint_groups[checkpoint_id] = []
                checkpoint_groups[checkpoint_id].append(record)
            
            for checkpoint_idx, (checkpoint_id, group_records) in enumerate(checkpoint_groups.items()):
                print(f"{'='*60}")
                print(f"📝 Checkpoint {checkpoint_idx+1}: {checkpoint_id}")
                task_paths = set(r.task_path for r in group_records)
                print(f"🎯 节点: {', '.join(task_paths)}")
                print(f"{'='*60}")
                
                # 解析每个channel的数据
                checkpoint_state = {}
                
                for record in group_records:
                    channel = record.channel
                    blob_type = record.type
                    blob_data = record.blob
                    
                    decoded_value = decode_blob(blob_data, blob_type)
                    checkpoint_state[channel] = decoded_value
                    
                    print(f"\n📋 {channel} ({blob_type}):")
                    
                    if channel == 'dialog_state' and decoded_value:
                        print(f"   🎯 状态: {decoded_value}")
                        dialog_states.append((checkpoint_idx, decoded_value))
                        key_events.append((checkpoint_idx, 'dialog_state', decoded_value))
                    
                    elif channel == 'task_list_accepted' and decoded_value is not None:
                        icon = "✅" if decoded_value else "❌"
                        print(f"   {icon} 任务接受: {decoded_value}")
                        acceptance_changes.append((checkpoint_idx, 'task_list', decoded_value))
                        key_events.append((checkpoint_idx, 'task_list_accepted', decoded_value))
                    
                    elif channel == 'module_steps_accepted' and decoded_value is not None:
                        icon = "✅" if decoded_value else "❌"
                        print(f"   {icon} 模块接受: {decoded_value}")
                        acceptance_changes.append((checkpoint_idx, 'module_steps', decoded_value))
                        key_events.append((checkpoint_idx, 'module_steps_accepted', decoded_value))
                    
                    elif channel == 'completion_status' and decoded_value:
                        print(f"   📊 完成状态: {decoded_value}")
                        key_events.append((checkpoint_idx, 'completion_status', decoded_value))
                    
                    elif channel == 'user_input' and decoded_value:
                        print(f"   💬 用户输入: {str(decoded_value)[:80]}...")
                        key_events.append((checkpoint_idx, 'user_input', str(decoded_value)[:50]))
                    
                    elif channel == 'clarification_question' and decoded_value:
                        print(f"   ❓ 确认问题: {str(decoded_value)[:80]}...")
                        key_events.append((checkpoint_idx, 'clarification_question', str(decoded_value)[:50]))
                    
                    elif channel == 'current_step_description' and decoded_value:
                        print(f"   📄 步骤描述: {decoded_value}")
                    
                    elif channel == 'sas_step1_generated_tasks' and decoded_value:
                        if isinstance(decoded_value, list):
                            print(f"   🤖 生成任务: {len(decoded_value)} 个")
                            for i, task in enumerate(decoded_value[:3]):  # 只显示前3个
                                task_name = task.get('name', '未知') if isinstance(task, dict) else str(task)[:30]
                                print(f"      {i+1}. {task_name}")
                            if len(decoded_value) > 3:
                                print(f"      ... 还有 {len(decoded_value)-3} 个")
                        else:
                            print(f"   🤖 生成任务: {decoded_value}")
                    
                    elif channel == 'sas_step2_module_steps' and decoded_value:
                        print(f"   🔧 模块步骤: {str(decoded_value)[:80]}...")
                    
                    elif channel == 'current_user_request' and decoded_value:
                        print(f"   📝 用户请求: {str(decoded_value)[:80]}...")
                    
                    else:
                        print(f"   📄 值: {str(decoded_value)[:100]}...")
                
                print()
            
            # 详细分析
            print("="*80)
            print("🔍 详细状态变化分析")
            print("="*80)
            
            # Dialog State 轨迹分析
            if dialog_states:
                print("🎯 Dialog State 变化轨迹:")
                for i, (checkpoint_idx, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} Checkpoint {checkpoint_idx+1}: {state}")
                
                # 分析状态序列
                states = [state for _, state in dialog_states]
                print(f"\n📊 状态序列:")
                print(f"   {' → '.join(states)}")
                
                # 🔍 关键问题分析
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
                for checkpoint_idx, acc_type, value in acceptance_changes:
                    print(f"   Checkpoint {checkpoint_idx+1}: {acc_type} = {value}")
            
            # 关键事件时间线
            if key_events:
                print(f"\n📅 关键事件时间线:")
                for checkpoint_idx, event_type, value in key_events:
                    location = f"Checkpoint {checkpoint_idx+1}"
                    if event_type == 'dialog_state':
                        print(f"   {location}: 🎯 {event_type} = {value}")
                    elif event_type in ['task_list_accepted', 'module_steps_accepted']:
                        icon = "✅" if value else "❌"
                        print(f"   {location}: {icon} {event_type} = {value}")
                    elif event_type == 'user_input':
                        print(f"   {location}: 💬 {event_type} = {value}...")
                    else:
                        print(f"   {location}: 📄 {event_type} = {value}")
            
            # 🎯 最终结论
            print(f"\n" + "="*80)
            print("🎯 问题诊断结论")
            print("="*80)
            
            states = [state for _, state in dialog_states] if dialog_states else []
            
            if 'sas_step1_tasks_generated' in states and 'sas_awaiting_task_list_review' not in states:
                print("🚨 确认问题：系统跳过了任务审核阶段")
                print("   - 任务生成完成后，应该进入 'sas_awaiting_task_list_review' 状态")
                print("   - 但实际上直接跳转到了其他状态")
                print("   - 这解释了为什么用户没有看到任务审核界面")
                
                # 查找task_list_accepted被设置的位置
                task_accepted_events = [e for e in key_events if e[1] == 'task_list_accepted' and e[2] == True]
                if task_accepted_events:
                    print("\n🔍 发现task_list_accepted被设置为True的位置:")
                    for checkpoint_idx, _, _ in task_accepted_events:
                        print(f"   - Checkpoint {checkpoint_idx+1}")
                        
                print("\n🔍 建议修复方案：")
                print("   1. 检查 backend/sas/graph_builder.py 中的 route_after_sas_step1() 函数")
                print("   2. 确保任务生成后设置 state.task_list_accepted = False")
                print("   3. 检查 review_and_refine_node 的触发条件")
                print("   4. 验证前端是否正确处理审核状态")
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