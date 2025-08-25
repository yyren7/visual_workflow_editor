#!/usr/bin/env python3
"""
Analyze LangGraph checkpoint data to view state changes
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
    print(f"🔍 分析流程ID: {TARGET_THREAD_ID}")
    print(f"⏰ 时间: {datetime.now()}")
    print("="*80)
    
    try:
        with get_db_context() as db:
            print(f"📊 Querying checkpoint data...")
            
            # Query checkpoint records
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
                print(f"❌ No records found for thread_id {TARGET_THREAD_ID}")
                
                # Find recent records
                recent_query = """
                SELECT DISTINCT thread_id, created_at
                FROM checkpoints 
                ORDER BY created_at DESC
                LIMIT 10
                """
                recent_result = db.execute(text(recent_query))
                recent_records = recent_result.fetchall()
                
                print("\n📋 Recent 10 thread_ids:")
                for record in recent_records:
                    print(f"  - {record.thread_id} ({record.created_at})")
                
                return
            
            print(f"✅ Found {len(records)} checkpoint records\n")
            
            # Analyze state changes
            dialog_states = []
            acceptance_changes = []
            step_descriptions = []
            
            for i, record in enumerate(records):
                print(f"{'='*60}")
                print(f"📝 Checkpoint {i+1}/{len(records)}")
                print(f"🕐 Time: {record.created_at}")
                print(f"🆔 ID: {record.checkpoint_id}")
                print(f"📋 Type: {record.type}")
                print(f"👤 Parent: {record.parent_checkpoint_id}")
                
                if record.checkpoint:
                    try:
                        data = json.loads(record.checkpoint) if isinstance(record.checkpoint, str) else record.checkpoint
                        
                        # Extract key state information
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
                            dialog_states.append((record.created_at, dialog_state))
                        
                        if task_list_accepted is not None:
                            icon = "✅" if task_list_accepted else "❌"
                            print(f"{icon} Task list accepted: {task_list_accepted}")
                            acceptance_changes.append((record.created_at, 'task_list', task_list_accepted))
                        
                        if module_steps_accepted is not None:
                            icon = "✅" if module_steps_accepted else "❌"
                            print(f"{icon} Module steps accepted: {module_steps_accepted}")
                            acceptance_changes.append((record.created_at, 'module_steps', module_steps_accepted))
                        
                        if completion_status:
                            print(f"📊 Completion status: {completion_status}")
                        
                        if is_error:
                            print(f"🚨 Error status: {is_error}")
                        
                        if user_input:
                            print(f"💬 User input: {str(user_input)[:100]}...")
                        
                        if current_step_description:
                            print(f"📋 Step description: {str(current_step_description)[:100]}...")
                            step_descriptions.append((record.created_at, current_step_description))
                        
                        if clarification_question:
                            print(f"❓ Clarification question: {str(clarification_question)[:100]}...")
                        
                        # SAS related data
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
                            print("🤖 SAS data:")
                            for key, value in sas_fields.items():
                                print(f"   {key}: {value}")
                        
                    except Exception as e:
                        print(f"❌ Failed to parse checkpoint data: {e}")
                        print(f"Original data length: {len(str(record.checkpoint)) if record.checkpoint else 0}")
                
                # Parse metadata
                if record.metadata:
                    try:
                        metadata = json.loads(record.metadata) if isinstance(record.metadata, str) else record.metadata
                        print(f"📝 Metadata: {json.dumps(metadata, ensure_ascii=False)}")
                    except:
                        print(f"📝 Metadata (original): {str(record.metadata)[:100]}")
                
                print()
            
            # Detailed analysis
            print("="*80)
            print("🔍 Detailed state change analysis")
            print("="*80)
            
            # Dialog State trajectory analysis
            if dialog_states:
                print("🎯 Dialog State trajectory:")
                for i, (timestamp, state) in enumerate(dialog_states):
                    arrow = " → " if i > 0 else "   "
                    print(f"{arrow} {timestamp}: {state}")
                
                # Analyze state sequence
                states = [state for _, state in dialog_states]
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
                            print(f"   🚨 Problem: directly jumped to module step generation, skipped task review!")
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
                for timestamp, acc_type, value in acceptance_changes:
                    print(f"   {timestamp}: {acc_type} = {value}")
            
            # Step description analysis
            if step_descriptions:
                print(f"\n📋 Step description change:")
                for timestamp, desc in step_descriptions:
                    print(f"   {timestamp}: {desc}")
            
            # Final conclusion
            print(f"\n" + "="*80)
            print("🎯 Problem diagnosis conclusion")
            print("="*80)
            
            states = [state for _, state in dialog_states] if dialog_states else []
            
            if 'sas_step1_tasks_generated' in states and 'sas_awaiting_task_list_review' not in states:
                print("🚨 Problem confirmed: system skipped task review stage")
                print("   - After task generation, it should enter 'sas_awaiting_task_list_review' state")
                print("   - But it directly jumped to other states")
                print("   - This explains why the user didn't see the task review interface")
                
                # Find possible reasons
                if any('task_list_accepted' in str(record.checkpoint) for record in records):
                    print("\n🔍 Possible reasons analysis:")
                    print("   - Check if there is code that automatically sets task_list_accepted = True")
                    print("   - Check if the routing logic correctly handles the review state")
                    print("   - Check if there are any special conditions that skip the review")
            else:
                print("✅ The review process looks normal, the problem may be elsewhere")
    
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis() 