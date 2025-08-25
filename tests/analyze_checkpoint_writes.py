#!/usr/bin/env python3
"""
Analyze state change data in the checkpoint_writes table
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

# Configure basic logging
logging.basicConfig(level=logging.WARNING)

def run_analysis():
    print(f"🔍 Analyzing checkpoint_writes for thread ID: {TARGET_THREAD_ID}")
    print(f"⏰ Time: {datetime.now()}")
    print("="*80)
    
    try:
        with get_db_context() as db:
            print(f"📊 Querying checkpoint_writes data...")
            
            # Query checkpoint_writes records
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
                print(f"❌ No records found for thread_id {TARGET_THREAD_ID}")
                
                # Find similar thread_ids
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
                    print("\n📋 Found similar thread_ids:")
                    for record in similar_records:
                        print(f"  - {record[0]}")
                else:
                    print("\n📋 Recent 10 thread_ids:")
                    recent_query = "SELECT DISTINCT thread_id FROM checkpoint_writes ORDER BY checkpoint_id DESC LIMIT 10"
                    recent_result = db.execute(text(recent_query))
                    recent_records = recent_result.fetchall()
                    for record in recent_records:
                        print(f"  - {record[0]}")
                
                return
            
            print(f"✅ Found {len(records)} write records\n")
            
            # Analyze state changes
            dialog_states = []
            acceptance_changes = []
            key_events = []
            checkpoint_groups = {}
            
            for i, record in enumerate(records):
                checkpoint_id = record.checkpoint_id
                if checkpoint_id not in checkpoint_groups:
                    checkpoint_groups[checkpoint_id] = []
                checkpoint_groups[checkpoint_id].append(record)
            
            # Display by checkpoint
            for checkpoint_idx, (checkpoint_id, group_records) in enumerate(checkpoint_groups.items()):
                print(f"{'='*60}")
                print(f"📝 Checkpoint {checkpoint_idx+1}: {checkpoint_id}")
                print(f"📝 Contains {len(group_records)} write records")
                print(f"{'='*60}")
                
                for j, record in enumerate(group_records):
                    print(f"\n--- Write record {j+1} ---")
                    print(f"🆔 Task ID: {record.task_id}")
                    print(f"📋 Channel: {record.channel}")
                    print(f"🏷️  Type: {record.type}")
                    print(f"📍 Index: {record.idx}")
                    print(f"🛤️  Task Path: {record.task_path}")
                    
                    # Parse blob data
                    if record.blob:
                        try:
                            # blob is binary data, needs to be decoded
                            blob_str = record.blob.decode('utf-8') if isinstance(record.blob, bytes) else str(record.blob)
                            data = json.loads(blob_str)
                            
                            # Find key state information
                            if isinstance(data, dict):
                                dialog_state = data.get('dialog_state')
                                task_list_accepted = data.get('task_list_accepted')
                                module_steps_accepted = data.get('module_steps_accepted')
                                completion_status = data.get('completion_status')
                                is_error = data.get('is_error')
                                user_input = data.get('user_input')
                                current_step_description = data.get('current_step_description')
                                clarification_question = data.get('clarification_question')
                                
                                # Display key states
                                if dialog_state:
                                    print(f"🎯 Dialog state: {dialog_state}")
                                    dialog_states.append((checkpoint_idx, j, dialog_state))
                                    key_events.append((checkpoint_idx, j, 'dialog_state', dialog_state))
                                
                                if task_list_accepted is not None:
                                    icon = "✅" if task_list_accepted else "❌"
                                    print(f"{icon} Task list accepted: {task_list_accepted}")
                                    acceptance_changes.append((checkpoint_idx, j, 'task_list', task_list_accepted))
                                    key_events.append((checkpoint_idx, j, 'task_list_accepted', task_list_accepted))
                                
                                if module_steps_accepted is not None:
                                    icon = "✅" if module_steps_accepted else "❌"
                                    print(f"{icon} Module steps accepted: {module_steps_accepted}")
                                    acceptance_changes.append((checkpoint_idx, j, 'module_steps', module_steps_accepted))
                                    key_events.append((checkpoint_idx, j, 'module_steps_accepted', module_steps_accepted))
                                
                                if completion_status:
                                    print(f"📊 Completion status: {completion_status}")
                                    key_events.append((checkpoint_idx, j, 'completion_status', completion_status))
                                
                                if is_error:
                                    print(f"🚨 Error status: {is_error}")
                                
                                if user_input:
                                    print(f"💬 User input: {str(user_input)[:80]}...")
                                    key_events.append((checkpoint_idx, j, 'user_input', str(user_input)[:50]))
                                
                                if current_step_description:
                                    print(f"📋 Step description: {str(current_step_description)[:80]}...")
                                
                                if clarification_question:
                                    print(f"❓ Clarification question: {str(clarification_question)[:80]}...")
                                
                                # SAS related data
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
                                    print("🤖 SAS data:")
                                    for key, value in sas_fields.items():
                                        print(f"   {key}: {value}")
                            
                            # Display data preview
                            if len(blob_str) > 200:
                                print(f"📄 Data preview: {blob_str[:200]}...")
                            else:
                                print(f"📄 Full data: {blob_str}")
                                
                        except Exception as e:
                            print(f"❌ Failed to parse blob data: {e}")
                            print(f"Original blob length: {len(record.blob) if record.blob else 0}")
                
                print()
            
            # Detailed analysis
            print("="*80)
            print("🔍 Detailed state change analysis")
            print("="*80)
            
            # Dialog State trajectory analysis
            if dialog_states:
                print("🎯 Dialog State trajectory:")
                for i, (checkpoint_idx, write_idx, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} Checkpoint {checkpoint_idx+1}-{write_idx+1}: {state}")
                
                # Analyze state sequence
                states = [state for _, _, state in dialog_states]
                print(f"\n📊 State sequence:")
                print(f"   {' → '.join(states)}")
                
                # Check key problem: whether to skip task review
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
            
            # 接受状态变化分析
            if acceptance_changes:
                print(f"\n✅ Acceptance state change:")
                for checkpoint_idx, write_idx, acc_type, value in acceptance_changes:
                    print(f"   Checkpoint {checkpoint_idx+1}-{write_idx+1}: {acc_type} = {value}")
            
            # Key event timeline
            if key_events:
                print(f"\n📅 Key event timeline:")
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
            
            # Final conclusion
            print(f"\n" + "="*80)
            print("🎯 Problem diagnosis conclusion")
            print("="*80)
            
            states = [state for _, _, state in dialog_states] if dialog_states else []
            
            if 'sas_step1_tasks_generated' in states and 'sas_awaiting_task_list_review' not in states:
                print("🚨 Problem confirmed: system skipped task review stage")
                print("   - After task generation, it should enter 'sas_awaiting_task_list_review' state")
                print("   - But it directly jumped to other states")
                print("   - This explains why the user didn't see the task review interface")
                
                # Find where task_list_accepted is set
                task_accepted_events = [e for e in key_events if e[2] == 'task_list_accepted' and e[3] == True]
                if task_accepted_events:
                    print("\n🔍 Found where task_list_accepted is set to True:")
                    for checkpoint_idx, write_idx, _, _ in task_accepted_events:
                        print(f"   - Checkpoint {checkpoint_idx+1}-{write_idx+1}")
                        
                print("\n🔍 Suggested checks:")
                print("   1. Review logic in backend/sas/nodes/review_and_refine.py")
                print("   2. Routing logic in backend/sas/graph_builder.py")
                print("   3. Whether there is code that automatically sets task_list_accepted = True")
                print("   4. Whether the frontend sent a skip review instruction")
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