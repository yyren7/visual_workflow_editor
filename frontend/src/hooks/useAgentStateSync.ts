import { useCallback, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch } from '../store/store';
import { updateAgentState, selectCurrentFlowId, selectAgentState } from '../store/slices/flowSlice';
import { updateLangGraphState } from '../api/langgraphApi';
import { chatApi } from '../api/chatApi';
import { debounce } from 'lodash';

export const useAgentStateSync = () => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const agentState = useSelector(selectAgentState);
  
  // Track if this is the first render to avoid syncing on mount
  const isFirstRender = useRef(true);

  // Debounced sync function to avoid too many API calls
  const syncToBackend = useRef(
    debounce(async (flowId: string, state: any) => {
      if (!flowId) return;
      
      try {
        // Format the request according to backend schema
        const stateUpdateRequest = {
          action_type: 'direct_update',
          data: state
        };
        
        await updateLangGraphState(flowId, stateUpdateRequest);
        console.log('Agent state synced to backend');
      } catch (error) {
        console.error('Failed to sync agent state to backend:', error);
      }
    }, 1000) // 1 second debounce
  ).current;

  // Update agent state in Redux
  const updateState = useCallback((updates: any) => {
    dispatch(updateAgentState(updates));
  }, [dispatch]);

  // 新增：启动LangGraph处理的函数
  const startLangGraphProcessing = useCallback(async (content: string, taskIndex?: number, detailIndex?: number) => {
    if (!currentFlowId) {
      console.error('No current flow ID available for LangGraph processing');
      return;
    }

    try {
      console.log('Starting LangGraph processing for input:', content, { taskIndex, detailIndex });
      
      // 动态构建chat ID，支持三种格式：
      // 1. flow_id - 整个流程的聊天
      // 2. flow_id_task_X - 特定任务的聊天
      // 3. flow_id_task_X_detail_Y - 特定任务的特定detail的聊天
      let dynamicChatId = currentFlowId;
      
      if (taskIndex !== undefined) {
        dynamicChatId += `_task_${taskIndex}`;
        if (detailIndex !== undefined) {
          dynamicChatId += `_detail_${detailIndex}`;
        }
      }
      
      console.log('Using dynamic LangGraph chat ID:', dynamicChatId);
      
      // 发送消息来启动LangGraph处理
      // 这个chat ID可能是虚拟的，后端会智能处理
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${dynamicChatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          content: content,
          role: 'user'
        }),
      });

      if (!response.ok) {
        // 如果虚拟chat不存在，创建一个真实的chat作为fallback
        if (response.status === 404) {
          console.log('Virtual chat not found, creating real chat as fallback...');
          
          // 为不同级别的聊天创建不同的名称
          let chatName;
          if (taskIndex !== undefined && detailIndex !== undefined) {
            chatName = `Detail Chat - Task ${taskIndex + 1} Detail ${detailIndex + 1}`;
          } else if (taskIndex !== undefined) {
            chatName = `Task Chat - Task ${taskIndex + 1}`;
          } else {
            chatName = `LangGraph Chat - ${new Date().toLocaleString()}`;
          }
          
          const chatResponse = await chatApi.createChat(currentFlowId, chatName);
          
          // 使用新创建的chat ID重新发送请求
          const fallbackResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${chatResponse.id}/messages`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({
              content: content,
              role: 'user'
            }),
          });
          
          if (!fallbackResponse.ok) {
            throw new Error(`Fallback HTTP ${fallbackResponse.status}: ${fallbackResponse.statusText}`);
          }
          
          console.log('LangGraph processing started with fallback chat ID:', chatResponse.id);
          return;
        }
        
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      console.log('LangGraph processing started successfully with dynamic chat ID:', dynamicChatId);
      
    } catch (error) {
      console.error('Failed to start LangGraph processing:', error);
    }
  }, [currentFlowId]);

  // Update specific parts of agent state
  const updateUserInput = useCallback(async (content: string, taskIndex?: number, detailIndex?: number) => {
    // 首先更新agent state
    updateState({ current_user_request: content });
    
    // 然后启动LangGraph处理，传递taskIndex和detailIndex
    await startLangGraphProcessing(content, taskIndex, detailIndex);
  }, [updateState, startLangGraphProcessing]);

  const updateTask = useCallback((taskIndex: number, task: any) => {
    const currentTasks = agentState.sas_step1_generated_tasks || [];
    const updatedTasks = [...currentTasks];
    
    if (taskIndex < updatedTasks.length) {
      updatedTasks[taskIndex] = task;
    } else {
      updatedTasks.push(task);
    }
    
    updateState({ sas_step1_generated_tasks: updatedTasks });
  }, [agentState, updateState]);

  const updateTaskDetails = useCallback((taskIndex: number, details: string[]) => {
    const currentDetails = agentState.sas_step2_generated_task_details || {};
    const updatedDetails = {
      ...currentDetails,
      [taskIndex.toString()]: { details }
    };
    
    updateState({ sas_step2_generated_task_details: updatedDetails });
  }, [agentState, updateState]);

  // Sync to backend when agent state changes
  useEffect(() => {
    // Skip the first render
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    if (currentFlowId && agentState) {
      syncToBackend(currentFlowId, agentState);
    }
  }, [agentState, currentFlowId, syncToBackend]);

  return {
    updateUserInput,
    updateTask,
    updateTaskDetails,
    updateState,
    startLangGraphProcessing, // 导出新函数以便其他地方使用
  };
}; 