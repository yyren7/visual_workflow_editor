#!/usr/bin/env python3
"""
简化的状态分析：专注于dialog_state变化
"""

import sys
import os
sys.path.append('/workspace')

try:
    import msgpack
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "msgpack"])
    import msgpack

from database.connection import get_db_context
from sqlalchemy import text

TARGET_THREAD_ID = '26f8c147-7a85-42a9-ad77-9fffae46d64c'

def decode_msgpack_blob(blob_data):
    """解码msgpack blob"""
    try:
        if blob_data:
            return msgpack.unpackb(blob_data, raw=False, strict_map_key=False)
    except:
        pass
    return None

def main():
    print(f"🔍 简化分析: {TARGET_THREAD_ID}")
    print("="*50)
    
    try:
        with get_db_context() as db:
            # 只查询关键状态字段
            query = """
            SELECT 
                checkpoint_id,
                channel,
                type,
                blob,
                task_path
            FROM checkpoint_writes 
            WHERE thread_id = :thread_id
            AND channel IN ('dialog_state', 'task_list_accepted', 'module_steps_accepted', 'completion_status')
            ORDER BY checkpoint_id, idx
            """
            
            result = db.execute(text(query), {"thread_id": TARGET_THREAD_ID})
            records = result.fetchall()
            
            print(f"找到 {len(records)} 条关键记录\n")
            
            # 按checkpoint分组
            checkpoints = {}
            for record in records:
                cid = record.checkpoint_id
                if cid not in checkpoints:
                    checkpoints[cid] = {'task_path': record.task_path}
                
                # 解码数据
                value = decode_msgpack_blob(record.blob)
                if value is not None:
                    checkpoints[cid][record.channel] = value
            
            # 显示每个checkpoint的状态
            dialog_states = []
            for i, (cid, data) in enumerate(checkpoints.items()):
                print(f"Checkpoint {i+1}: {data.get('task_path', '未知')}")
                
                if 'dialog_state' in data:
                    state = data['dialog_state']
                    print(f"  🎯 Dialog State: {state}")
                    dialog_states.append(state)
                
                if 'task_list_accepted' in data:
                    icon = "✅" if data['task_list_accepted'] else "❌"
                    print(f"  {icon} Task List Accepted: {data['task_list_accepted']}")
                
                if 'module_steps_accepted' in data:
                    icon = "✅" if data['module_steps_accepted'] else "❌"
                    print(f"  {icon} Module Steps Accepted: {data['module_steps_accepted']}")
                
                if 'completion_status' in data:
                    print(f"  📊 Completion Status: {data['completion_status']}")
                
                print()
            
            # 分析状态序列
            print("="*50)
            print("🎯 状态序列分析")
            print("="*50)
            
            if dialog_states:
                print("Dialog State 变化:")
                for i, state in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} {state}")
                
                print(f"\n完整序列: {' → '.join(dialog_states)}")
                
                # 检查关键问题
                if 'sas_step1_tasks_generated' in dialog_states:
                    step1_idx = dialog_states.index('sas_step1_tasks_generated')
                    if step1_idx + 1 < len(dialog_states):
                        next_state = dialog_states[step1_idx + 1]
                        print(f"\n🔍 分析：任务生成后 → {next_state}")
                        
                        if next_state == 'sas_awaiting_task_list_review':
                            print("✅ 正常：进入了任务审核")
                        else:
                            print("🚨 问题：跳过了任务审核！")
                            print(f"   应该是: sas_step1_tasks_generated → sas_awaiting_task_list_review")
                            print(f"   实际是: sas_step1_tasks_generated → {next_state}")
                    else:
                        print("\n⚠️  任务生成后没有后续状态")
                
                # 检查是否有审核状态
                review_states = [s for s in dialog_states if 'awaiting' in s]
                if review_states:
                    print(f"\n📋 发现的审核状态: {review_states}")
                else:
                    print(f"\n🚨 警告：没有发现任何审核状态！")
                    print("   这确认了跳过审核的问题")
            else:
                print("❌ 没有找到dialog_state变化")
    
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 