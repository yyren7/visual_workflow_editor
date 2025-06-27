import { useCallback, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch, RootState } from '../store/store';
import { updateAgentState, selectCurrentFlowId, selectAgentState, fetchFlowById, setActiveLangGraphStreamFlowId } from '../store/slices/flowSlice';
import { updateLangGraphState } from '../api/langgraphApi';
import { chatApi } from '../api/chatApi';
import { debounce } from 'lodash';
import { useSSEManager } from './useSSEManager';

export const useAgentStateSync = () => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const agentState = useSelector(selectAgentState);
  const { subscribe, closeConnection: closeSseConnection } = useSSEManager();
  
  const currentChatIdForSSESubscriptions = useRef<string | null>(null);
  const activeUnsubscribeFunctions = useRef<Array<() => void>>([]);

  const cleanupSseSubscriptions = useCallback(() => {
    const chatIdToClose = currentChatIdForSSESubscriptions.current;

    if (activeUnsubscribeFunctions.current.length > 0) {
      console.log('[AGENT_SYNC_LOG] Cleaning up existing SSE subscriptions for chat ID:', chatIdToClose);
      activeUnsubscribeFunctions.current.forEach(unsub => unsub());
      activeUnsubscribeFunctions.current = [];
    }
    
    currentChatIdForSSESubscriptions.current = null;
    dispatch(setActiveLangGraphStreamFlowId(null));

    if (chatIdToClose) {
      console.log(`[AGENT_SYNC_LOG] Explicitly closing SSE connection for chat ID: ${chatIdToClose} after its stream ended/errored or context changed.`);
      closeSseConnection(chatIdToClose);
    }
  }, [dispatch, closeSseConnection]);

  useEffect(() => {
    return () => {
      console.log('useAgentStateSync: Hook unmounting, performing cleanup of subscriptions.');
      cleanupSseSubscriptions();
    };
  }, [cleanupSseSubscriptions]);

  const startLangGraphProcessing = useCallback(async (content: string, taskIndex?: number, detailIndex?: number) => {
    console.log(`[AGENT_SYNC_LOG] startLangGraphProcessing called with content: "${content?.substring(0, 50)}...", taskIndex: ${taskIndex}, detailIndex: ${detailIndex}`);
    if (!currentFlowId) {
      console.error('[AGENT_SYNC_LOG] No current flow ID, cannot start LangGraph processing.');
      return;
    }

    let dynamicChatId = currentFlowId;
    if (taskIndex !== undefined) {
      dynamicChatId += `_task_${taskIndex}`;
      if (detailIndex !== undefined) {
        dynamicChatId += `_detail_${detailIndex}`;
      }
    }
    console.log(`[AGENT_SYNC_LOG] Preparing for dynamicChatId: ${dynamicChatId}`);

    if (currentChatIdForSSESubscriptions.current && currentChatIdForSSESubscriptions.current !== dynamicChatId) {
        console.log(`[AGENT_SYNC_LOG] Chat ID context changing from ${currentChatIdForSSESubscriptions.current} to ${dynamicChatId}. Cleaning old subscriptions.`);
        cleanupSseSubscriptions();
    }

    try {
      const token = localStorage.getItem('access_token');
      const sseUrl = `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${dynamicChatId}/events`;
      console.log(`[AGENT_SYNC_LOG] Starting processing with POST to SSE endpoint: ${sseUrl} with content: "${content?.substring(0,50)}..."`);
      
      let response = await fetch(sseUrl, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json', 
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({ input: content }),
      });
      console.log(`[AGENT_SYNC_LOG] POST to SSE endpoint response status: ${response.status}, ok: ${response.ok}`);

      let finalChatIdForSSE = dynamicChatId;

      if (!response.ok) {
        const isBaseFlowIdAttempt = (dynamicChatId === currentFlowId);
        if (response.status === 404) {
          if (isBaseFlowIdAttempt) {
            console.error(`[AGENT_SYNC_LOG] Critical Error: POST to base flowId ${currentFlowId}/events returned 404. This flow may be inactive or deleted on the backend.`);
            dispatch(setActiveLangGraphStreamFlowId(null));
            throw new Error(`Base flow ${currentFlowId} not found by backend for new events.`);
          } else {
            console.warn(`[AGENT_SYNC_LOG] Virtual chat ${dynamicChatId} not found (404). Attempting to create a real chat as fallback using currentFlowId: ${currentFlowId}.`);
            dispatch(setActiveLangGraphStreamFlowId(null));
            let chatName = `LangGraph Fallback - ${new Date().toLocaleTimeString()}`;
            if (taskIndex !== undefined) { 
              chatName = `Task ${taskIndex + 1} Fallback${detailIndex !== undefined ? ` Detail ${detailIndex + 1}` : ''}`;
            }
            
            const chatResponse = await chatApi.createChat(currentFlowId, chatName);
            finalChatIdForSSE = chatResponse.id;
            console.log(`[AGENT_SYNC_LOG] Fallback chat created with ID: ${finalChatIdForSSE} (context: original flow ${currentFlowId}). Resending message to this new chat.`);

            const fallbackSseUrl = `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${finalChatIdForSSE}/events`;
            console.log(`[AGENT_SYNC_LOG] Attempting fallback POST to SSE endpoint: ${fallbackSseUrl} with content: "${content?.substring(0,50)}..."`);
            response = await fetch(fallbackSseUrl, {
              method: 'POST',
              headers: { 
                'Content-Type': 'application/json', 
                'Authorization': `Bearer ${token}`,
                'Accept': 'text/event-stream'
              },
              body: JSON.stringify({ input: content }),
            });
            console.log(`[AGENT_SYNC_LOG] Fallback POST to SSE endpoint response status: ${response.status}, ok: ${response.ok}`);
            if (!response.ok) throw new Error(`Fallback HTTP Error: ${response.status} ${response.statusText}`);
          }
        } else {
          throw new Error(`Initial HTTP Error: ${response.status} ${response.statusText}`);
        }
      }
      console.log(`[AGENT_SYNC_LOG] POST to SSE endpoint successful for effective chat ID: ${finalChatIdForSSE}`);
      dispatch(setActiveLangGraphStreamFlowId(finalChatIdForSSE));

      if (currentChatIdForSSESubscriptions.current !== finalChatIdForSSE || activeUnsubscribeFunctions.current.length === 0 ) {
        console.log(`[AGENT_SYNC_LOG] Setting up new SSE subscriptions for chat ID: ${finalChatIdForSSE}. Previous SSE chat ID: ${currentChatIdForSSESubscriptions.current}`);
        cleanupSseSubscriptions();
        currentChatIdForSSESubscriptions.current = finalChatIdForSSE;
        
        const newUnsubs: Array<() => void> = [];
        const eventsToSubscribe: string[] = ['agent_state_updated', 'stream_end', 'connection_error', 'server_error_event', 'token', 'tool_start', 'tool_end', 'user_message_saved', 'ping', 'task_progress'];
        
        eventsToSubscribe.forEach(eventType => {
          console.log(`[AGENT_SYNC_LOG] Subscribing to SSE event type: '${eventType}' for chat ID: ${finalChatIdForSSE}`);
          const eventCallback = (eventData: any) => {
            console.log(`[AGENT_SYNC_LOG] Received SSE event '${eventType}' for chat ${finalChatIdForSSE}. Data:`, eventData);
            const isActiveStream = finalChatIdForSSE === currentChatIdForSSESubscriptions.current;

            if (eventType === 'agent_state_updated') {
              if (eventData && typeof eventData === 'object' && eventData.flow_id && eventData.agent_state) {
                console.log('[DEBUG] useAgentStateSync: Event data is valid object with flow_id and agent_state.');
                console.log('[DEBUG] useAgentStateSync:   eventData.flow_id:', eventData.flow_id);
                console.log('[DEBUG] useAgentStateSync:   currentFlowId (from Redux):', currentFlowId);
                if (eventData.flow_id === currentFlowId) {
                  console.log('[DEBUG] useAgentStateSync: flow_id MATCHES. Dispatching updateAgentState.');
                  console.log('[DEBUG] useAgentStateSync:   Agent state keys received:', Object.keys(eventData.agent_state));
                  if (eventData.agent_state.dialog_state) {
                    console.log('[DEBUG] useAgentStateSync:   Received dialog_state:', eventData.agent_state.dialog_state);
                  }
                  if (eventData.agent_state.sas_step1_generated_tasks) {
                    console.log('[DEBUG] useAgentStateSync:   Received sas_step1_generated_tasks count:', eventData.agent_state.sas_step1_generated_tasks.length);
                  }
                  dispatch(updateAgentState(eventData.agent_state));
                } else {
                  console.warn('[DEBUG] useAgentStateSync: flow_id MISMATCH on agent_state_updated. Current flow in Redux:', currentFlowId, 'Received from event for stream ', finalChatIdForSSE, 'eventData.flow_id:', eventData.flow_id);
                }
              } else {
                console.warn('[DEBUG] useAgentStateSync: Received MALFORMED agent_state_updated event (missing flow_id or agent_state field). EventData:', JSON.stringify(eventData, null, 2));
              }
            } else if (eventType === 'task_progress') {
              // 处理任务进度事件
              if (eventData && typeof eventData === 'object') {
                const { task_index, task_name, status, details } = eventData;
                const progressMessage = `[TASK_PROGRESS] 任务 ${task_index >= 0 ? task_index : 'Overall'}: ${task_name} - ${status}${details ? ` (${details})` : ''}`;
                
                if (status === 'processing') {
                  console.log(`🟡 ${progressMessage}`);
                } else if (status === 'completed') {
                  console.log(`🟢 ${progressMessage}`);
                } else if (status === 'error') {
                  console.error(`🔴 ${progressMessage}`);
                } else {
                  console.log(`⚪ ${progressMessage}`);
                }
                
                // 这里可以添加更多的UI更新逻辑，例如更新进度条、状态指示器等
                // 暂时先在控制台显示，后续可以扩展到UI组件
              }
            } else if (eventType === 'stream_end') {
              console.log(`[AGENT_SYNC_LOG] SSE stream_end for chat ${finalChatIdForSSE}. Data:`, eventData);
              if (isActiveStream) {
                console.log(`[AGENT_SYNC_LOG] Main stream ${finalChatIdForSSE} ended. Cleaning up subscriptions.`);
                cleanupSseSubscriptions();
              }
            } else if (eventType === 'connection_error' || eventType === 'server_error_event') {
              console.error(`[AGENT_SYNC_LOG] SSE ${eventType} for chat ${finalChatIdForSSE}. Data:`, eventData);
              if (isActiveStream) { 
                console.warn(`[AGENT_SYNC_LOG] Error ('${eventType}') on active stream ${finalChatIdForSSE}. Cleaning up subscriptions.`);
                cleanupSseSubscriptions();
              }
            } else if (eventType === 'ping') {
              // Typically, pings don't carry data or require action other than keeping connection alive.
              // console.log(`[AGENT_SYNC_LOG] Ping received for chat ${finalChatIdForSSE}`);
            } else {
              // Handle other event types like 'token', 'tool_start', 'tool_end', 'user_message_saved' if necessary
              // For now, they are mostly for logging or direct display elsewhere.
            }
          };
          newUnsubs.push(subscribe(finalChatIdForSSE, eventType, eventCallback));
        });
        
        activeUnsubscribeFunctions.current = newUnsubs;
      } else {
        console.log(`useAgentStateSync: Already have active subscriptions for chat ${finalChatIdForSSE}. No new subscriptions created.`);
      }

    } catch (error) {
      console.error('useAgentStateSync: Failed in startLangGraphProcessing:', error);
      dispatch(setActiveLangGraphStreamFlowId(null));
      if(currentChatIdForSSESubscriptions.current){
        console.warn('[AGENT_SYNC_LOG] Error during startLangGraphProcessing. Cleaning up subscriptions for potentially related chat ID:', currentChatIdForSSESubscriptions.current );
        cleanupSseSubscriptions();
      }
      throw error;
    }
  }, [currentFlowId, dispatch, subscribe, cleanupSseSubscriptions, closeSseConnection]);

  const updateUserInput = useCallback(async (content: string, taskIndex?: number, detailIndex?: number) => {
    dispatch(updateAgentState({ current_user_request: content })); 
    await startLangGraphProcessing(content, taskIndex, detailIndex);
  }, [dispatch, startLangGraphProcessing]);

  const updateTask = useCallback((taskIndex: number, task: any) => {
    const currentTasks = agentState.sas_step1_generated_tasks || [];
    const updatedTasks = [...currentTasks];
    if (taskIndex < updatedTasks.length) updatedTasks[taskIndex] = task;
    else updatedTasks.push(task);
    dispatch(updateAgentState({ sas_step1_generated_tasks: updatedTasks }));
  }, [agentState, dispatch]);

  const updateTaskDetails = useCallback((taskIndex: number, details: string[]) => {
    const currentDetails = agentState.sas_step2_generated_task_details || {};
    const updatedDetails = { ...currentDetails, [taskIndex.toString()]: { details } };
    dispatch(updateAgentState({ sas_step2_generated_task_details: updatedDetails }));
  }, [agentState, dispatch]);

  const sendAutoConfirmation = useCallback(async (chatId: string, confirmation: string) => {
    try {
      console.log(`useAgentStateSync: Sending auto confirmation "${confirmation}" to chat ${chatId}`);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ content: confirmation, role: 'user' }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      console.log(`useAgentStateSync: Auto confirmation "${confirmation}" sent successfully to ${chatId}`);
    } catch (error) {
      console.error('useAgentStateSync: Failed to send auto confirmation:', error);
    }
  }, []);

  const checkAndHandleAwaitingStates = useCallback(async (currentLocalAgentState: any, chatId: string) => {
    if (!currentLocalAgentState || !chatId) return;
    const dialogState = currentLocalAgentState.dialog_state;
    const awaitingStates = [
      'sas_awaiting_task_list_review',
      'sas_awaiting_module_steps_review', 
      'awaiting_enrichment_confirmation',
      'awaiting_user_input'
    ];
    if (awaitingStates.includes(dialogState)) {
      console.log(`useAgentStateSync: Detected awaiting state: ${dialogState} for chat ${chatId}. Auto-confirmation logic is currently disabled.`);
    }
  }, [sendAutoConfirmation]);

  return {
    updateUserInput,
    updateTask,
    updateTaskDetails,
    startLangGraphProcessing,
  };
}; 