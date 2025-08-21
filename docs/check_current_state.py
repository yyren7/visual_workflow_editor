#!/usr/bin/env python3
import sys
import os
sys.path.append('/workspace')

from database.connection import get_db_context
from sqlalchemy import text

flow_id = '36b95799-f2c0-4b27-96ae-38160e5517bd'

try:
    with get_db_context() as db:
        result = db.execute(text('SELECT agent_state FROM flows WHERE id = :flow_id'), {'flow_id': flow_id})
        row = result.fetchone()
        
        if row and row[0]:
            agent_state = row[0]  # agent_state是第一列
            print('=== Flow Agent State ===')
            print(f'Flow ID: {flow_id}')
            
            # 检查任务列表
            tasks = agent_state.get('sas_step1_generated_tasks', [])
            print(f'任务数量: {len(tasks)}')
            
            if tasks:
                print('任务列表:')
                for i, task in enumerate(tasks[:5]):  # 只显示前5个任务
                    name = task.get('name', '未知任务') if isinstance(task, dict) else str(task)
                    task_type = task.get('type', '未知类型') if isinstance(task, dict) else ''
                    print(f'  {i+1}. {name} ({task_type})')
                if len(tasks) > 5:
                    print(f'  ... 还有 {len(tasks) - 5} 个任务')
            else:
                print('任务列表为空')
                
            # 检查其他重要状态
            dialog_state = agent_state.get('dialog_state', '未设置')
            current_request = agent_state.get('current_user_request', '未设置')
            print(f'对话状态: {dialog_state}')
            
            request_display = current_request
            if current_request != '未设置' and len(str(current_request)) > 100:
                request_display = str(current_request)[:100] + '...'
            print(f'当前用户请求: {request_display}')
            
            # 显示完整的agent_state结构
            print('\n=== Agent State 键值 ===')
            for key in sorted(agent_state.keys()):
                value = agent_state[key]
                if isinstance(value, (list, dict)):
                    print(f'{key}: {type(value).__name__}(长度: {len(value)})')
                else:
                    print(f'{key}: {value}')
                    
        else:
            print(f'未找到Flow {flow_id}或agent_state为空')
            
except Exception as e:
    print(f'查询出错: {e}')
    import traceback
    traceback.print_exc() 