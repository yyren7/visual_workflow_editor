import { useCallback, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch, RootState } from '../store/store';
import {
  updateAgentState,
  selectCurrentFlowId,
  selectAgentState,
  fetchFlowById,
  setActiveLangGraphStreamFlowId,
  setProcessingStatus,
  appendStreamingContent,
  setProcessingStage,
} from '../store/slices/flowSlice';
import { updateLangGraphState } from '../api/langgraphApi';
import { debounce } from 'lodash';
import { useSSEManager } from './useSSEManager';
import { store } from '../store/store';

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

  // 🔧 新增：主动获取最新状态的功能
  const forceStateSync = useCallback(async (flowId: string) => {
    if (!flowId) return;
    
    try {
      console.log('[SYNC_FIX] 🔄 Force syncing state for flowId:', flowId);
      dispatch(fetchFlowById(flowId));
    } catch (error) {
      console.error('[SYNC_FIX] ❌ Failed to force sync state:', error);
    }
  }, [dispatch]);

  // 🔧 新增：检查状态不一致的情况
  const checkStateSyncHealth = useCallback((flowId: string) => {
    if (!flowId) return;
    
    const currentState = store.getState().flow.agentState;
    console.log('[SYNC_FIX] 🔍 Health check - Current state:', currentState?.dialog_state);
    
    // 如果状态看起来不对，主动同步
    if (currentState?.dialog_state === 'sas_step2_module_steps_generated_for_review') {
      console.log('[SYNC_FIX] ⚠️ Detected potentially stale state, forcing sync...');
      forceStateSync(flowId);
    }
  }, [forceStateSync]);

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
            // 🔧 修复：对于虚拟 chatId 404，应该尝试使用基础 flowId
            console.warn(`[AGENT_SYNC_LOG] Virtual chat ${dynamicChatId} not found (404). Falling back to base flowId: ${currentFlowId}.`);
            finalChatIdForSSE = currentFlowId;
            
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
              console.log(`[AGENT_SYNC_DEBUG] Raw agent_state_updated event received for chat ${finalChatIdForSSE}:`, eventData);
              if (eventData && typeof eventData === 'object' && eventData.agent_state) {
                console.log('[DEBUG] useAgentStateSync: Received agent_state_updated. Bypassing strict flow_id check and dispatching update.');
                console.log('[DEBUG] useAgentStateSync:   Received for SSE stream ID:', finalChatIdForSSE);
                console.log('[DEBUG] useAgentStateSync:   Event flow_id:', eventData.flow_id);
                console.log('[DEBUG] useAgentStateSync:   Current Redux flow_id:', currentFlowId);
                console.log('[DEBUG] useAgentStateSync:   Agent state keys received:', Object.keys(eventData.agent_state));
                
                if (eventData.agent_state.dialog_state) {
                  console.log('[DEBUG] useAgentStateSync:   Received dialog_state:', eventData.agent_state.dialog_state);
                  
                  // 🔧 特别处理审核状态同步
                  if (eventData.agent_state.dialog_state === 'sas_awaiting_module_steps_review') {
                    console.log('[SYNC_FIX] 🎯 Detected sas_awaiting_module_steps_review state - ensuring proper sync!');
                    
                    // 确保clarification_question也被正确同步
                    if (eventData.agent_state.clarification_question) {
                      console.log('[SYNC_FIX] 📝 Clarification question received:', eventData.agent_state.clarification_question.substring(0, 100) + '...');
                    }
                    
                    // 确保module_steps_accepted标志正确
                    if (eventData.agent_state.module_steps_accepted !== undefined) {
                      console.log('[SYNC_FIX] ✅ Module steps accepted flag:', eventData.agent_state.module_steps_accepted);
                    }
                  }
                }
                
                if (eventData.agent_state.sas_step1_generated_tasks) {
                  console.log('[DEBUG] useAgentStateSync:   Received sas_step1_generated_tasks count:', eventData.agent_state.sas_step1_generated_tasks.length);
                }
                
                console.log('[AGENT_SYNC_DEBUG] About to dispatch updateAgentState with:', eventData.agent_state);
                dispatch(updateAgentState(eventData.agent_state));
                
                // 🔧 强制UI重新渲染以确保状态变化生效
                if (eventData.agent_state.dialog_state === 'sas_awaiting_module_steps_review') {
                  console.log('[SYNC_FIX] 🔄 Forcing UI update for review state...');
                  // 稍微延迟重新获取状态以确保redux更新完成
                  setTimeout(() => {
                    console.log('[SYNC_FIX] 📊 Current Redux state after update:', store.getState().flow.agentState?.dialog_state);
                  }, 100);
                }
              } else {
                console.warn('[AGENT_SYNC_LOG] Received agent_state_updated event but eventData.agent_state is missing or invalid:', eventData);
              }
            } else if (eventType === 'stream_start') {
              console.log(`[AGENT_SYNC_LOG] Stream started for chat ${finalChatIdForSSE}. EventData:`, eventData);
              dispatch(setProcessingStage('Starting...'));
            } else if (eventType === 'stream_end') {
              console.log(`[AGENT_SYNC_LOG] Stream ended for chat ${finalChatIdForSSE}. EventData:`, eventData);
              dispatch(setProcessingStage('Processing Complete'));
              
              // 🔧 在stream_end时检查是否需要状态同步
              if (eventData && eventData.final_state) {
                console.log('[SYNC_FIX] 🔄 Stream ended with final state, checking for dialog_state:', eventData.final_state.dialog_state);
                if (eventData.final_state.dialog_state === 'sas_awaiting_module_steps_review') {
                  console.log('[SYNC_FIX] 🎯 Stream ended in review state - ensuring state sync!');
                  dispatch(updateAgentState(eventData.final_state));
                }
              }
            } else if (eventType === 'token') {
              if (typeof eventData === 'string') {
                dispatch(appendStreamingContent(eventData));
              }
            } else if (eventType === 'tool_start') {
              if (eventData && typeof eventData === 'object' && eventData.name) {
                dispatch(setProcessingStage(`Tool Started: ${eventData.name}`));
              }
            } else if (eventType === 'tool_end') {
              if (eventData && typeof eventData === 'object' && eventData.name) {
                dispatch(setProcessingStage(`Tool Finished: ${eventData.name}`));
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
            } else if (eventType === 'connection_error' || eventType === 'server_error_event') {
              console.error(`[AGENT_SYNC_LOG] SSE ${eventType} for chat ${finalChatIdForSSE}. Data:`, eventData);
              const errorMsg = eventData?.message || `A ${eventType} occurred.`;
              dispatch(setProcessingStage(`Error: ${errorMsg}`));
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
    dispatch(setProcessingStatus(true));
    await startLangGraphProcessing(content, taskIndex, detailIndex);
  }, [dispatch, startLangGraphProcessing]);

  const updateTask = useCallback((taskIndex: number, task: any) => {
    if (!agentState) return;
    const currentTasks = agentState.sas_step1_generated_tasks || [];
    const updatedTasks = [...currentTasks];
    if (taskIndex < updatedTasks.length) updatedTasks[taskIndex] = task;
    else updatedTasks.push(task);
    dispatch(updateAgentState({ sas_step1_generated_tasks: updatedTasks }));
  }, [agentState, dispatch]);

  const updateTaskDetails = useCallback((taskIndex: number, details: string[]) => {
    if (!agentState) return;
    const currentDetails = agentState.sas_step2_generated_task_details || {};
    const updatedDetails = { ...currentDetails, [taskIndex.toString()]: { details } };
    dispatch(updateAgentState({ sas_step2_generated_task_details: updatedDetails }));
  }, [agentState, dispatch]);

  const sendAutoConfirmation = useCallback(async (chatId: string, confirmation: string) => {
    try {
      console.log(`useAgentStateSync: Sending auto confirmation "${confirmation}" to SAS chat ${chatId}`);
      const token = localStorage.getItem('access_token');
      // 🔧 使用正确的 SAS API 端点 - /events 而不是 /messages
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${chatId}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ input: confirmation }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      console.log(`useAgentStateSync: Auto confirmation "${confirmation}" sent successfully to SAS ${chatId}`);
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
    forceStateSync, // 🔧 新增：暴露给外部使用
    checkStateSyncHealth, // 🔧 新增：暴露给外部使用
  };
}; 