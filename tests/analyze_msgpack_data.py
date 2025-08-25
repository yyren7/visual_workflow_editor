#!/usr/bin/env python3
"""
Analyze msgpack encoded data in the checkpoint_writes table
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
    print("Warning: msgpack not installed, trying to install...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "msgpack"])
    import msgpack
    MSGPACK_AVAILABLE = True

TARGET_THREAD_ID = '26f8c147-7a85-42a9-ad77-9fffae46d64c'

# 配置基本日志
logging.basicConfig(level=logging.WARNING)

def decode_blob(blob_data, blob_type):
    """Decode blob data"""
    if not blob_data:
        return None
    
    try:
        if blob_type == 'msgpack':
            # Use msgpack to decode
            return msgpack.unpackb(blob_data, raw=False, strict_map_key=False)
        elif blob_type == 'null' or blob_type is None:
            # null type, try UTF-8 decoding
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
            # Other types, try multiple decoding methods
            if isinstance(blob_data, bytes):
                # First try msgpack
                try:
                    return msgpack.unpackb(blob_data, raw=False, strict_map_key=False)
                except:
                    pass
                
                # Try UTF-8 + JSON
                try:
                    decoded = blob_data.decode('utf-8')
                    return json.loads(decoded)
                except:
                    pass
                
                # Finally return string
                try:
                    return blob_data.decode('utf-8')
                except:
                    return f"<binary data: {len(blob_data)} bytes>"
            
            return blob_data
    except Exception as e:
        return f"<decode error: {e}>"

def run_analysis():
    print(f"🔍 Analyze msgpack encoded flow ID: {TARGET_THREAD_ID}")
    print(f"⏰ Time: {datetime.now()}")
    print("="*80)
    
    try:
        with get_db_context() as db:
            print(f"📊 Querying checkpoint_writes data...")
            
            # Query records with important status information
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
                print(f"❌ No related records found")
                return
            
            print(f"✅ Found {len(records)} related records\n")
            
            # Analyze state changes
            dialog_states = []
            acceptance_changes = []
            key_events = []
            
            # Group by checkpoint
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
                
                # Parse data for each channel
                checkpoint_state = {}
                
                for record in group_records:
                    channel = record.channel
                    blob_type = record.type
                    blob_data = record.blob
                    
                    decoded_value = decode_blob(blob_data, blob_type)
                    checkpoint_state[channel] = decoded_value
                    
                    print(f"\n📋 {channel} ({blob_type}):")
                    
                    if channel == 'dialog_state' and decoded_value:
                        print(f"   🎯 State: {decoded_value}")
                        dialog_states.append((checkpoint_idx, decoded_value))
                        key_events.append((checkpoint_idx, 'dialog_state', decoded_value))
                    
                    elif channel == 'task_list_accepted' and decoded_value is not None:
                        icon = "✅" if decoded_value else "❌"
                        print(f"   {icon} Task accepted: {decoded_value}")
                        acceptance_changes.append((checkpoint_idx, 'task_list', decoded_value))
                        key_events.append((checkpoint_idx, 'task_list_accepted', decoded_value))
                    
                    elif channel == 'module_steps_accepted' and decoded_value is not None:
                        icon = "✅" if decoded_value else "❌"
                        print(f"   {icon} Module accepted: {decoded_value}")
                        acceptance_changes.append((checkpoint_idx, 'module_steps', decoded_value))
                        key_events.append((checkpoint_idx, 'module_steps_accepted', decoded_value))
                    
                    elif channel == 'completion_status' and decoded_value:
                        print(f"   📊 Completion status: {decoded_value}")
                        key_events.append((checkpoint_idx, 'completion_status', decoded_value))
                    
                    elif channel == 'user_input' and decoded_value:
                        print(f"   💬 User input: {str(decoded_value)[:80]}...")
                        key_events.append((checkpoint_idx, 'user_input', str(decoded_value)[:50]))
                    
                    elif channel == 'clarification_question' and decoded_value:
                        print(f"   ❓ Clarification question: {str(decoded_value)[:80]}...")
                        key_events.append((checkpoint_idx, 'clarification_question', str(decoded_value)[:50]))
                    
                    elif channel == 'current_step_description' and decoded_value:
                        print(f"   📄 Step description: {decoded_value}")
                    
                    elif channel == 'sas_step1_generated_tasks' and decoded_value:
                        if isinstance(decoded_value, list):
                            print(f"   🤖 Generated tasks: {len(decoded_value)}")
                            for i, task in enumerate(decoded_value[:3]):  # Only show first 3
                                task_name = task.get('name', '未知') if isinstance(task, dict) else str(task)[:30]
                                print(f"      {i+1}. {task_name}")
                            if len(decoded_value) > 3:
                                print(f" and {len(decoded_value)-3} more")
                        else:
                            print(f"   🤖 Generated tasks: {decoded_value}")
                    
                    elif channel == 'sas_step2_module_steps' and decoded_value:
                        print(f"   🔧 module steps: {str(decoded_value)[:80]}...")
                    
                    elif channel == 'current_user_request' and decoded_value:
                        print(f"   📝 user request: {str(decoded_value)[:80]}...")
                    
                    else:
                        print(f"   📄 value: {str(decoded_value)[:100]}...")
                
                print()
            
            # Detailed analysis
            print("="*80)
            print("🔍 Detailed state change analysis")
            print("="*80)
            
            # Dialog State trajectory analysis
            if dialog_states:
                print("🎯 Dialog State trajectory:")
                for i, (checkpoint_idx, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} Checkpoint {checkpoint_idx+1}: {state}")
                
                # Analyze state sequence
                states = [state for _, state in dialog_states]
                print(f"\n📊 State sequence:")
                print(f"   {' → '.join(states)}")
                
                # 🔍 Key problem analysis
                print(f"\n🔍 Key problem analysis:")
                
                if 'sas_step1_tasks_generated' in states:
                    step1_idx = states.index('sas_step1_tasks_generated')
                    
                    if step1_idx + 1 < len(states):
                        next_state = states[step1_idx + 1]
                        print(f"   ✓ Next state after task generation: {next_state}")
                        
                        if next_state == 'sas_awaiting_task_list_review':
                            print(f"   ✅ Normal: entered task review state")
                        elif next_state == 'sas_step2_module_steps_generated_for_review':
                            print(f"   🚨 Problem found: directly jumped to module step generation, skipped task review!")
                        else:
                            print(f"   ⚠️  Unexpected state: {next_state}")
                    else:
                        print(f"   ⚠️  No subsequent state after task generation")
                
                # Find if there are any review-related states
                review_states = [s for s in states if 'awaiting' in s or 'review' in s]
                if review_states:
                    print(f"   📋 Found review states: {review_states}")
                else:
                    print(f"   🚨 Warning: no review states found!")
            
            # Acceptance state change analysis
            if acceptance_changes:
                print(f"\n✅ Acceptance state change:")
                for checkpoint_idx, acc_type, value in acceptance_changes:
                    print(f"   Checkpoint {checkpoint_idx+1}: {acc_type} = {value}")
            
            # Key event timeline
            if key_events:
                print(f"\n📅 Key event timeline:")
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
            
            # 🎯 Final conclusion
            print(f"\n" + "="*80)
            print("🎯 Problem diagnosis conclusion")
            print("="*80)
            
            states = [state for _, state in dialog_states] if dialog_states else []
            
            if 'sas_step1_tasks_generated' in states and 'sas_awaiting_task_list_review' not in states:
                print("🚨 Problem confirmed: system skipped task review stage")
                print("   - After task generation, it should enter 'sas_awaiting_task_list_review' state")
                print("   - But it directly jumped to other states")
                print("   - This explains why the user didn't see the task review interface")
                
                # Find where task_list_accepted is set
                task_accepted_events = [e for e in key_events if e[1] == 'task_list_accepted' and e[2] == True]
                if task_accepted_events:
                    print("\n🔍 Found where task_list_accepted is set to True:")
                    for checkpoint_idx, _, _ in task_accepted_events:
                        print(f"   - Checkpoint {checkpoint_idx+1}")
                        
                print("\n🔍 Suggested repair solution:")
                print("   1. Check route_after_sas_step1() in backend/sas/graph_builder.py")
                print("   2. Ensure state.task_list_accepted is set to False after task generation")
                print("   3. Check the trigger conditions for review_and_refine_node")
                print("   4. Verify if the frontend correctly handles the review state")
            else:
                print("✅ The review process looks normal, the problem may be elsewhere")
                if not dialog_states:
                    print("   ⚠️  But no dialog_state change record was found")
    
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis() 