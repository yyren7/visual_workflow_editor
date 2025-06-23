import { useCallback, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch, RootState } from '../store/store';
import { updateAgentState, selectCurrentFlowId, selectAgentState, fetchFlowById } from '../store/slices/flowSlice';
import { updateLangGraphState } from '../api/langgraphApi';
import { chatApi } from '../api/chatApi';
import { debounce } from 'lodash';

export const useAgentStateSync = () => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const agentState = useSelector(selectAgentState);
  
  // Track if this is the first render to avoid syncing on mount
  const isFirstRender = useRef(true);
  
  // 新增：跟踪当前活跃的SSE连接
  const activeSSEConnection = useRef<{
    eventSource: EventSource | null;
    chatId: string | null;
    cleanup: (() => void) | null;
  }>({
    eventSource: null,
    chatId: null,
    cleanup: null
  });

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

  // 新增：清理当前SSE连接的函数
  const cleanupCurrentSSEConnection = useCallback(() => {
    const current = activeSSEConnection.current;
    if (current.eventSource) {
      console.log('Cleaning up existing SSE connection for chat:', current.chatId);
      current.eventSource.close();
      current.eventSource = null;
    }
    if (current.cleanup) {
      current.cleanup();
      current.cleanup = null;
    }
    current.chatId = null;
  }, []);

  // 新增：启动LangGraph处理的函数
  const startLangGraphProcessing = useCallback(async (content: string, taskIndex?: number, detailIndex?: number) => {
    if (!currentFlowId) {
      console.error('No current flow ID available for LangGraph processing');
      return;
    }

    try {
      console.log('Starting LangGraph processing for input:', content, { taskIndex, detailIndex });
      
      // 清理之前的SSE连接，避免重复连接
      cleanupCurrentSSEConnection();
      
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

      let finalChatId = dynamicChatId;

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
          finalChatId = chatResponse.id;
          
          // 使用新创建的chat ID重新发送请求
          const fallbackResponse = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${finalChatId}/messages`, {
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
          
          console.log('LangGraph processing started with fallback chat ID:', finalChatId);
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      } else {
        console.log('LangGraph processing started successfully with dynamic chat ID:', finalChatId);
      }

      // 只在这里设置一次SSE监听器，使用最终确定的chat ID
      setupSSEListener(finalChatId);
      
    } catch (error) {
      console.error('Failed to start LangGraph processing:', error);
    }
  }, [currentFlowId, cleanupCurrentSSEConnection]);

  // 新增：设置SSE事件监听器
  const setupSSEListener = useCallback((chatId: string) => {
    if (!chatId) return;

    // 如果已经有相同chat ID的连接，不重复创建
    if (activeSSEConnection.current.chatId === chatId && activeSSEConnection.current.eventSource) {
      console.log('SSE connection already exists for chat:', chatId);
      return;
    }

    // 清理之前的连接
    cleanupCurrentSSEConnection();
    
    // 添加延迟，避免快速重复创建连接
    if (activeSSEConnection.current.chatId === chatId) {
      console.log('SSE connection just cleaned up for same chat:', chatId, 'skipping immediate reconnect');
      return;
    }

    console.log('Setting up SSE listener for chat:', chatId);
    
    // 添加连接状态跟踪
    let connectionClosed = false;
    let retryCount = 0;
    const maxRetries = 3;
    
    const createConnection = () => {
      if (connectionClosed) return null;
      
      const eventSource = new EventSource(
        `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${chatId}/events`,
        {
          withCredentials: false
        }
      );

      // 监听agent_state_updated事件
      eventSource.addEventListener('agent_state_updated', (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('🎯 Received agent_state_updated event:', data);
          console.log('🎯 Event data keys:', Object.keys(data));
          console.log('🎯 Agent state keys:', data.agent_state ? Object.keys(data.agent_state) : 'No agent_state');
          
          // 验证这个事件是否属于当前flow
          if (data.flow_id && data.agent_state) {
            console.log('🎯 Validating event for current flow...');
            console.log('🎯 Event flow_id:', data.flow_id);
            console.log('🎯 Current flow_id:', currentFlowId);
            console.log('🎯 Agent state has tasks:', !!(data.agent_state.sas_step1_generated_tasks?.length));
            console.log('🎯 Agent state has details:', !!(data.agent_state.sas_step2_generated_task_details && Object.keys(data.agent_state.sas_step2_generated_task_details).length));
            
            if (data.flow_id === currentFlowId) {
              console.log('🎯 ✅ Event belongs to current flow, updating Redux agent state...');
              console.log('🎯 Updating Redux agent state with:', data.agent_state);
              
              // 直接更新Redux中的agent state
              dispatch(updateAgentState(data.agent_state));
              
              // 可选：显示通知
              console.log(`🎯 Agent state updated successfully! Update types: ${data.update_types?.join(', ')}`);
              
              // 新增：检查是否需要自动确认等待状态
              checkAndHandleAwaitingStates(data.agent_state, chatId);
              
              // 新增：手动触发节点同步（如果需要）
              setTimeout(() => {
                console.log('🎯 Triggering manual node sync after agent state update...');
                // 这里可以触发额外的同步逻辑，如果需要的话
              }, 100);
            } else {
              console.log('🎯 ⚠️ Event flow_id does not match current flow_id, ignoring...');
            }
          } else {
            console.log('🎯 ❌ Event missing flow_id or agent_state, ignoring...');
          }
        } catch (error) {
          console.error('🎯 ❌ Error parsing agent_state_updated event:', error);
        }
      });

      // 处理其他事件（可选）
      eventSource.addEventListener('token', (event) => {
        console.log('Received token:', event.data);
        // 重置重试计数，因为收到了有效数据
        retryCount = 0;
      });

      // 监听stream_end事件，表示流结束
      eventSource.addEventListener('stream_end', (event) => {
        console.log('Received stream_end event for chat:', chatId);
        connectionClosed = true;
        eventSource.close();
        console.log('SSE connection closed due to stream end');
        
        // 清理引用
        if (activeSSEConnection.current.eventSource === eventSource) {
          activeSSEConnection.current.eventSource = null;
          activeSSEConnection.current.chatId = null;
        }
      });

      eventSource.addEventListener('error', (event) => {
        console.error('SSE error event:', event);
      });

      // 监听连接状态
      eventSource.onopen = () => {
        console.log('SSE connection opened for chat:', chatId);
        retryCount = 0; // 重置重试计数
      };

      eventSource.onerror = (error) => {
        console.error('SSE connection error for chat:', chatId, error);
        
        if (connectionClosed) {
          return; // 如果已标记为关闭，不再重连
        }
        
        // 检查连接状态并决定是否重连
        if (eventSource.readyState === EventSource.CLOSED) {
          if (retryCount < maxRetries) {
            retryCount++;
            console.log(`SSE connection closed, retrying (${retryCount}/${maxRetries}) in 2 seconds...`);
            setTimeout(() => {
              if (!connectionClosed) {
                const newEventSource = createConnection();
                if (newEventSource) {
                  activeSSEConnection.current.eventSource = newEventSource;
                }
              }
            }, 2000);
          } else {
            console.log('Max retries reached, stopping SSE reconnection attempts');
            connectionClosed = true;
            if (activeSSEConnection.current.eventSource === eventSource) {
              activeSSEConnection.current.eventSource = null;
              activeSSEConnection.current.chatId = null;
            }
          }
        }
      };

      return eventSource;
    };

    const eventSource = createConnection();
    if (!eventSource) return;

    // 保存连接引用
    activeSSEConnection.current = {
      eventSource,
      chatId,
      cleanup: null
    };
    
    // 设置定时器，在一定时间后关闭连接（避免资源泄露）
    const cleanup = setTimeout(() => {
      console.log('Closing SSE connection for chat due to timeout:', chatId);
      connectionClosed = true;
      if (eventSource) {
        eventSource.close();
      }
      if (activeSSEConnection.current.eventSource === eventSource) {
        activeSSEConnection.current.eventSource = null;
        activeSSEConnection.current.chatId = null;
      }
    }, 5 * 60 * 1000); // 5分钟后关闭

    activeSSEConnection.current.cleanup = () => {
      clearTimeout(cleanup);
    };

    // 返回清理函数
    return () => {
      console.log('Cleaning up SSE connection for chat:', chatId);
      connectionClosed = true;
      clearTimeout(cleanup);
      if (eventSource) {
        eventSource.close();
      }
      if (activeSSEConnection.current.eventSource === eventSource) {
        activeSSEConnection.current.eventSource = null;
        activeSSEConnection.current.chatId = null;
        activeSSEConnection.current.cleanup = null;
      }
    };
  }, [currentFlowId, dispatch, cleanupCurrentSSEConnection]);

  // 新增：轮询检查agent_state变化的函数
  const pollForAgentStateChanges = useCallback(() => {
    if (!currentFlowId) return;

    let pollCount = 0;
    const maxPolls = 30; // 最多轮询30次（约5分钟）
    const pollInterval = 10000; // 每10秒轮询一次
    
    // 保存开始轮询时的状态，用于比较
    const initialTaskCount = agentState?.sas_step1_generated_tasks?.length || 0;
    const initialDialogState = agentState?.dialog_state;

    const polling = setInterval(async () => {
      pollCount++;
      console.log(`Polling for agent state changes (${pollCount}/${maxPolls})...`);

      try {
        // 重新获取flow数据以更新agent_state
        const result = await dispatch(fetchFlowById(currentFlowId));
        console.log('Agent state refreshed from server');
        
        // 检查是否有重要状态变化（任务生成等）
        if (result.payload && typeof result.payload === 'object' && 'agent_state' in result.payload) {
          const newAgentState = (result.payload as any).agent_state;
          const newTaskCount = newAgentState?.sas_step1_generated_tasks?.length || 0;
          const newDialogState = newAgentState?.dialog_state;
          
          // 检查是否有显著变化
          if (newTaskCount > initialTaskCount || 
              (newDialogState && newDialogState !== initialDialogState)) {
            console.log('Detected significant agent state changes, stopping polling');
            console.log(`Task count: ${initialTaskCount} -> ${newTaskCount}`);
            console.log(`Dialog state: ${initialDialogState} -> ${newDialogState}`);
            clearInterval(polling);
            return;
          }
        }

        // 达到最大轮询次数时停止
        if (pollCount >= maxPolls) {
          console.log('Max polling attempts reached, stopping');
          clearInterval(polling);
        }
      } catch (error) {
        console.error('Error during agent state polling:', error);
        clearInterval(polling);
      }
    }, pollInterval);

    // 清理函数
    return () => clearInterval(polling);
  }, [currentFlowId, dispatch, agentState]);

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

  // 新增：发送自动确认消息的函数
  const sendAutoConfirmation = useCallback(async (chatId: string, confirmation: string) => {
    try {
      console.log(`Sending auto confirmation "${confirmation}" to chat ${chatId}`);
      
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          content: confirmation,
          role: 'user'
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      console.log(`Auto confirmation "${confirmation}" sent successfully`);
    } catch (error) {
      console.error('Failed to send auto confirmation:', error);
    }
  }, []);

  // 新增：检查并处理等待状态的函数
  const checkAndHandleAwaitingStates = useCallback(async (agentState: any, chatId: string) => {
    if (!agentState || !chatId) return;

    const dialogState = agentState.dialog_state;
    const hasClaficationQuestion = agentState.clarification_question;
    
    // 检查是否处于等待用户确认的状态
    const awaitingStates = [
      'sas_awaiting_task_list_review',
      'sas_awaiting_module_steps_review', 
      'awaiting_enrichment_confirmation',
      'awaiting_user_input'
    ];

    if (awaitingStates.includes(dialogState)) {
      console.log(`Detected awaiting state: ${dialogState}`);
      
      // 暂时禁用自动确认，让流程按照设计的步骤执行
      // TODO: 根据实际需求决定是否启用自动确认
      console.log(`Detected awaiting state: ${dialogState}, but auto-confirmation is disabled`);
      
      // 注释掉自动确认逻辑，让用户手动确认或让流程继续
      /*
      // 检查是否有生成的任务需要确认
      if (dialogState === 'sas_awaiting_task_list_review' && agentState.sas_step1_generated_tasks) {
        console.log('Auto-confirming task list...');
        await sendAutoConfirmation(chatId, 'accept');
      }
      // 检查是否有模块步骤需要确认  
      else if (dialogState === 'sas_awaiting_module_steps_review') {
        console.log('Auto-confirming module steps...');
        await sendAutoConfirmation(chatId, 'accept');
      }
      // 检查是否有enriched plan需要确认
      else if (dialogState === 'awaiting_enrichment_confirmation') {
        console.log('Auto-confirming enriched plan...');
        await sendAutoConfirmation(chatId, 'yes');
      }
      // 一般等待用户输入的情况，如果有明确的问题，可以提供默认回答
      else if (dialogState === 'awaiting_user_input' && hasClaficationQuestion) {
        console.log('Auto-responding to clarification question...');
        await sendAutoConfirmation(chatId, 'continue');
      }
      */
    }
  }, [sendAutoConfirmation]);

  return {
    updateUserInput,
    updateTask,
    updateTaskDetails,
    updateState,
    startLangGraphProcessing, // 导出新函数以便其他地方使用
  };
}; 