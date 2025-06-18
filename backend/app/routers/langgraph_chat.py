from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging
from datetime import datetime

from backend.app import schemas
from database.connection import get_db
from backend.app.utils import get_current_user, verify_flow_ownership
from backend.app.services.chat_service import ChatService
from backend.app.services.flow_service import FlowService
from database.models import Flow

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/langgraph-chats",
    tags=["langgraph-chats"],
    responses={404: {"description": "Not found"}},
)

@router.post("/{chat_id}/update-state")
async def update_langgraph_state(
    chat_id: str,
    state_update: schemas.LangGraphStateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Update LangGraph state for a specific chat ID.
    The chat_id follows the naming convention:
    - Raw input: flow_id
    - Task: flow_id_task_X
    - Detail: flow_id_task_X_detail_Y
    """
    logger.info(f"Updating LangGraph state for chat_id: {chat_id}")
    
    # Extract flow_id from chat_id
    flow_id = chat_id.split('_task_')[0].split('_detail_')[0]
    
    # Verify flow ownership
    flow = verify_flow_ownership(flow_id, current_user, db)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )
    
    # Get or initialize agent_state
    flow_service = FlowService(db)
    current_state = flow.agent_state or {}
    
    # Parse the action from state_update
    action = state_update.action_type
    update_data = state_update.data
    
    if action == 'update_input':
        # Update the current_user_request
        current_state['current_user_request'] = update_data.get('content', '')
        
    elif action == 'update_task':
        # Update a specific task
        task_index = update_data.get('taskIndex')
        task_data = update_data.get('task')
        
        if 'sas_step1_generated_tasks' not in current_state:
            current_state['sas_step1_generated_tasks'] = []
        
        tasks = current_state['sas_step1_generated_tasks']
        if task_index < len(tasks):
            tasks[task_index] = task_data
        else:
            # If task doesn't exist, append it
            tasks.append(task_data)
            
    elif action == 'update_details':
        # Update task details
        task_index = update_data.get('taskIndex')
        details = update_data.get('details')
        
        if 'sas_step2_generated_task_details' not in current_state:
            current_state['sas_step2_generated_task_details'] = {}
        
        current_state['sas_step2_generated_task_details'][str(task_index)] = {
            'details': details
        }
    
    elif action == 'direct_update':
        # Direct state update - replace entire state
        current_state = update_data
        
    else:
        # Fallback: merge update data into current state
        current_state.update(update_data)
    
    # Update the flow's agent_state
    success = flow_service.update_flow_agent_state(flow_id, current_state)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent state"
        )
    
    # Also update the chat if it's a real chat (not just flow_id)
    if '_task_' in chat_id or '_detail_' in chat_id:
        chat_service = ChatService(db)
        # Create or update chat with the specific ID
        existing_chat = chat_service.get_chat(chat_id)
        
        if existing_chat:
            # Update existing chat
            chat_service.update_chat(
                chat_id=chat_id,
                chat_data={'state_update': state_update.dict(), 'timestamp': str(datetime.utcnow())}
            )
        else:
            # Create new chat
            chat_service.create_chat(
                flow_id=flow_id,
                name=f"LangGraph State - {chat_id}",
                chat_data={'state_update': state_update.dict(), 'timestamp': str(datetime.utcnow())}
            )
    
    return {"status": "success", "message": "State updated successfully"}


@router.get("/{flow_id}/state")
async def get_langgraph_state(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Get the current LangGraph state for a flow.
    """
    # Verify flow ownership
    flow = verify_flow_ownership(flow_id, current_user, db)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )
    
    # Return the agent_state
    return {
        "flow_id": flow_id,
        "agent_state": flow.agent_state or {},
        "last_updated": flow.updated_at.isoformat() if flow.updated_at else None
    }


@router.post("/{flow_id}/initialize-langgraph")
async def initialize_langgraph_nodes(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Initialize LangGraph nodes in the flow based on the current agent state.
    This creates the visual nodes for input, tasks, and details.
    """
    # Verify flow ownership
    flow = verify_flow_ownership(flow_id, current_user, db)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )
    
    flow_service = FlowService(db)
    agent_state = flow.agent_state or {}
    
    # Get current flow data
    flow_data = flow.flow_data if flow.flow_data else {"nodes": [], "edges": []}
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])
    
    # Create input node
    input_node = {
        "id": f"langgraph_input_{flow_id}",
        "type": "langgraph_input",
        "position": {"x": 400, "y": 50},
        "data": {
            "label": "User Input",
            "flowId": flow_id,
            "currentUserRequest": agent_state.get("current_user_request", "")
        }
    }
    
    # Add input node if not exists
    if not any(node["id"] == input_node["id"] for node in nodes):
        nodes.append(input_node)
    
    # Create task nodes
    tasks = agent_state.get("sas_step1_generated_tasks", [])
    y_offset = 250
    
    for i, task in enumerate(tasks):
        # 计算居中位置，让多个任务节点在input节点下方居中排列
        total_width = len(tasks) * 350  # 每个任务节点350px宽度间隔
        start_x = 400 - total_width / 2 + 175  # 从中央开始，向左偏移一半总宽度，再加上节点宽度的一半
        
        task_node = {
            "id": f"langgraph_task_{flow_id}_{i}",
            "type": "langgraph_task",
            "position": {"x": start_x + (i * 350), "y": y_offset}, # 居中排列
            "data": {
                "label": f"Task {i + 1}",
                "flowId": flow_id,
                "taskIndex": i,
                "task": task
            }
        }
        
        # Add task node if not exists
        if not any(node["id"] == task_node["id"] for node in nodes):
            nodes.append(task_node)
        
        # Create edge from input to task
        edge_id = f"edge_input_to_task_{i}"
        if not any(edge["id"] == edge_id for edge in edges):
            edges.append({
                "id": edge_id,
                "source": input_node["id"],
                "target": task_node["id"],
                "type": "smoothstep"
            })
        
        # Create detail nodes for this task
        task_details = agent_state.get("sas_step2_generated_task_details", {}).get(str(i), {})
        details = task_details.get("details", [])
        
        for j, detail in enumerate(details):
            detail_node = {
                "id": f"langgraph_detail_{flow_id}_{i}_{j}",
                "type": "langgraph_detail",
                "position": {"x": start_x + (i * 350), "y": y_offset + 200 + (j * 150)}, # 在对应task节点下方
                "data": {
                    "label": f"Step {j + 1}",
                    "flowId": flow_id,
                    "taskIndex": i,
                    "taskName": task.get("name", f"Task {i + 1}"),
                    "details": [detail] if isinstance(detail, str) else detail
                }
            }
            
            # Add detail node if not exists
            if not any(node["id"] == detail_node["id"] for node in nodes):
                nodes.append(detail_node)
            
            # Create edge from task to detail
            detail_edge_id = f"edge_task_{i}_to_detail_{j}"
            if not any(edge["id"] == detail_edge_id for edge in edges):
                edges.append({
                    "id": detail_edge_id,
                    "source": task_node["id"],
                    "target": detail_node["id"],
                    "type": "smoothstep"
                })
    
    # Update flow data
    flow_data["nodes"] = nodes
    flow_data["edges"] = edges
    
    # Save updated flow directly
    try:
        flow.flow_data = flow_data
        flow.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Flow {flow_id} updated with LangGraph nodes")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update flow {flow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update flow with LangGraph nodes"
        )
    
    return {
        "status": "success",
        "message": "LangGraph nodes initialized successfully",
        "nodes_created": len([n for n in nodes if n["type"].startswith("langgraph_")]),
        "edges_created": len([e for e in edges if "langgraph" in e["source"] or "langgraph" in e["target"]])
    } 