import { useCallback, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch, RootState } from '../store/store';
import { updateAgentState, selectCurrentFlowId, selectAgentState, fetchFlowById } from '../store/slices/flowSlice';
import { updateLangGraphState } from '../api/langgraphApi';
import { chatApi } from '../api/chatApi';
import { debounce } from 'lodash';
import { useSSEManager } from './useSSEManager';

export const useAgentStateSync = () => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const agentState = useSelector(selectAgentState);
  const { subscribe } = useSSEManager();
  
  const isFirstRender = useRef(true);
  const currentChatIdForSSESubscriptions = useRef<string | null>(null);
  const activeUnsubscribeFunctions = useRef<Array<() => void>>([]);

  const syncToBackend = useRef(
    debounce(async (flowId: string, state: any) => {
      if (!flowId) return;
      try {
        const stateUpdateRequest = {
          action_type: 'direct_update',
          data: state
        };
        await updateLangGraphState(flowId, stateUpdateRequest);
        console.log('useAgentStateSync: Agent state synced to backend for flowId:', flowId);
      } catch (error) {
        console.error('useAgentStateSync: Failed to sync agent state to backend:', error);
      }
    }, 1000)
  ).current;

  const cleanupSseSubscriptions = useCallback(() => {
    if (activeUnsubscribeFunctions.current.length > 0) {
      console.log('useAgentStateSync: Cleaning up existing SSE subscriptions for chat ID:', currentChatIdForSSESubscriptions.current);
      activeUnsubscribeFunctions.current.forEach(unsub => unsub());
      activeUnsubscribeFunctions.current = [];
    }
    currentChatIdForSSESubscriptions.current = null;
  }, []);

  useEffect(() => {
    return () => {
      console.log('useAgentStateSync: Hook unmounting, performing cleanup of subscriptions.');
      cleanupSseSubscriptions();
    };
  }, [cleanupSseSubscriptions]);

  const startLangGraphProcessing = useCallback(async (content: string, taskIndex?: number, detailIndex?: number) => {
    if (!currentFlowId) {
      console.error('useAgentStateSync: No current flow ID, cannot start LangGraph processing.');
      return;
    }

    let dynamicChatId = currentFlowId;
    if (taskIndex !== undefined) {
      dynamicChatId += `_task_${taskIndex}`;
      if (detailIndex !== undefined) {
        dynamicChatId += `_detail_${detailIndex}`;
      }
    }
    console.log(`useAgentStateSync: Preparing to start LangGraph processing for dynamicChatId: ${dynamicChatId}`);

    if (currentChatIdForSSESubscriptions.current && currentChatIdForSSESubscriptions.current !== dynamicChatId) {
        console.log(`useAgentStateSync: Chat ID context changing from ${currentChatIdForSSESubscriptions.current} to ${dynamicChatId}. Cleaning old subscriptions.`);
        cleanupSseSubscriptions();
    }

    try {
      const token = localStorage.getItem('access_token');
      const initialPostUrl = `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${dynamicChatId}/messages`;
      let response = await fetch(initialPostUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ content, role: 'user' }),
      });

      let finalChatIdForSSE = dynamicChatId;

      if (!response.ok) {
        if (response.status === 404) {
          console.warn(`useAgentStateSync: Virtual chat ${dynamicChatId} not found. Attempting to create a real chat as fallback using currentFlowId: ${currentFlowId}.`);
          let chatName = `LangGraph Input - ${new Date().toLocaleTimeString()}`;
          if (taskIndex !== undefined) {
            chatName = `Task ${taskIndex + 1} Input${detailIndex !== undefined ? ` Detail ${detailIndex + 1}` : ''}`;
          }          
          const chatResponse = await chatApi.createChat(currentFlowId, chatName);
          finalChatIdForSSE = chatResponse.id;
          console.log(`useAgentStateSync: Fallback chat created: ${finalChatIdForSSE}. Resending message.`);

          const fallbackPostUrl = `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${finalChatIdForSSE}/messages`;
          response = await fetch(fallbackPostUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ content, role: 'user' }),
          });
          if (!response.ok) throw new Error(`Fallback HTTP Error: ${response.status} ${response.statusText}`);
        } else {
          throw new Error(`Initial HTTP Error: ${response.status} ${response.statusText}`);
        }
      }
      console.log(`useAgentStateSync: Message POST successful for effective chat: ${finalChatIdForSSE}`);

      if (currentChatIdForSSESubscriptions.current !== finalChatIdForSSE || activeUnsubscribeFunctions.current.length === 0 ) {
        console.log(`useAgentStateSync: Setting up new subscriptions for chat ID: ${finalChatIdForSSE}. Previous: ${currentChatIdForSSESubscriptions.current}`);
        cleanupSseSubscriptions();
        currentChatIdForSSESubscriptions.current = finalChatIdForSSE;
        
        const newUnsubs: Array<() => void> = [];
        newUnsubs.push(subscribe(finalChatIdForSSE, 'agent_state_updated', (eventData) => {
          console.log('[DEBUG] useAgentStateSync: Received an SSE event. Type: agent_state_updated');
          console.log('[DEBUG] useAgentStateSync: Event Data Raw:', JSON.stringify(eventData, null, 2));

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
              console.warn('[DEBUG] useAgentStateSync: flow_id MISMATCH. Ignored agent_state_updated. Current in hook:', currentFlowId, 'Received from event:', eventData.flow_id);
            }
          } else {
            console.warn('[DEBUG] useAgentStateSync: Received MALFORMED agent_state_updated event (missing flow_id or agent_state field). EventData:', JSON.stringify(eventData, null, 2));
          }
        }));

        newUnsubs.push(subscribe(finalChatIdForSSE, 'stream_end', (eventData) => {
          console.log('useAgentStateSync: Received stream_end for chat:', finalChatIdForSSE, 'Data:', eventData);
        }));

        newUnsubs.push(subscribe(finalChatIdForSSE, 'connection_error', (errorData) => {
          console.error('useAgentStateSync: SSE connection_error via SSEManager for chat:', finalChatIdForSSE, errorData);
        }));

        newUnsubs.push(subscribe(finalChatIdForSSE, 'server_error_event', (errorData) => {
          console.error('useAgentStateSync: SSE server_error_event via SSEManager for chat:', finalChatIdForSSE, errorData);
        }));
        
        activeUnsubscribeFunctions.current = newUnsubs;
      } else {
        console.log(`useAgentStateSync: Already have active subscriptions for chat ${finalChatIdForSSE}. No new subscriptions created.`);
      }

    } catch (error) {
      console.error('useAgentStateSync: Failed in startLangGraphProcessing:', error);
    }
  }, [currentFlowId, dispatch, subscribe, cleanupSseSubscriptions, agentState]);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (currentFlowId && agentState) {
      const hasRelevantState = agentState.current_user_request || 
                               (agentState.sas_step1_generated_tasks && agentState.sas_step1_generated_tasks.length > 0) ||
                               agentState.dialog_state;
      if (hasRelevantState) {
        console.log('useAgentStateSync: agentState changed, syncing to backend for flowId:', currentFlowId);
        syncToBackend(currentFlowId, agentState);
      }
    }
  }, [agentState, currentFlowId, syncToBackend]);
  
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