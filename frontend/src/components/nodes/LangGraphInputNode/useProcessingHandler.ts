import { useCallback } from 'react';
import { useAgentStateSync } from '../../../hooks/useAgentStateSync';
import { useSSEManager } from '../../../hooks/useSSEManager';

export const useProcessingHandler = (
  id: string,
  operationChatId: string | undefined,
  cleanupUISseSubscriptions: () => void,
  setIsProcessing: (value: boolean) => void,
  setStreamingContent: React.Dispatch<React.SetStateAction<string>>,
  setProcessingStage: React.Dispatch<React.SetStateAction<string>>,
  setErrorMessage: (value: string | null) => void,
  setShowAddForm: (value: boolean) => void,
  setIsEditing: (value: boolean) => void,
  uiSseUnsubscribeFnsRef: React.MutableRefObject<(() => void)[]>
) => {
  const { updateUserInput } = useAgentStateSync();
  const { subscribe } = useSSEManager();

  const handleSend = useCallback(async (overrideInput?: string, input?: string) => {
    const contentToSend = overrideInput !== undefined ? overrideInput : input;
    if (!contentToSend?.trim() && overrideInput === undefined) {
      console.warn(`LangGraphInputNode (${id}): Input is empty, not sending.`);
      return;
    }
    if (!operationChatId) {
      console.error(`LangGraphInputNode (${id}): No operationChatId available.`);
      setErrorMessage('Error: Flow ID is missing. Cannot process request.');
      return;
    }

    cleanupUISseSubscriptions();
    setIsProcessing(true);
    setStreamingContent('');
    setProcessingStage('Initializing...');
    setErrorMessage(null);

    try {
      await updateUserInput(contentToSend || '');
      console.log(`LangGraphInputNode (${id}): updateUserInput completed for ${operationChatId}.`);

      const newUnsubs: (() => void)[] = [];

      newUnsubs.push(subscribe(operationChatId, 'token', (eventData) => {
        if (typeof eventData === 'string') {
          setStreamingContent((prev: string) => prev + eventData);
        }
      }));
      
      newUnsubs.push(subscribe(operationChatId, 'tool_start', (eventData) => {
        if (eventData && typeof eventData === 'object' && eventData.name) {
          setProcessingStage(`Tool Started: ${eventData.name}`);
        }
      }));

      newUnsubs.push(subscribe(operationChatId, 'tool_end', (eventData) => {
        if (eventData && typeof eventData === 'object' && eventData.name) {
          setProcessingStage(`Tool Finished: ${eventData.name}`);
        }
      }));

      newUnsubs.push(subscribe(operationChatId, 'stream_end', () => {
        setProcessingStage((prev: string) => prev.includes('Error') ? prev : 'Processing Complete');
      }));

      newUnsubs.push(subscribe(operationChatId, 'connection_error', (errorData) => {
        setErrorMessage('Connection error with UI event stream. Please try again.');
        setIsProcessing(false);
        setProcessingStage('UI Stream Connection Error');
        cleanupUISseSubscriptions();
      }));

      uiSseUnsubscribeFnsRef.current = newUnsubs;

    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to initiate processing.');
      setIsProcessing(false);
      setProcessingStage('Failed to Start');
    }

    setShowAddForm(false);
    setIsEditing(false);
  }, [
    id, 
    operationChatId, 
    cleanupUISseSubscriptions, 
    setIsProcessing, 
    setStreamingContent, 
    setProcessingStage, 
    setErrorMessage, 
    updateUserInput, 
    subscribe, 
    uiSseUnsubscribeFnsRef, 
    setShowAddForm, 
    setIsEditing
  ]);

  // Edit handler
  const handleEdit = useCallback((
    agentState: any,
    data: any,
    isInProcessingMode: boolean,
    isXmlGenerationComplete: boolean,
    isInErrorState: boolean,
    isInXmlApprovalMode: boolean,
    setInput: (value: string) => void
  ) => {
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return;
    
    const currentReq = agentState?.current_user_request || data.currentUserRequest || '';
    setInput(currentReq);
    setIsEditing(true);
    setShowAddForm(false);
    cleanupUISseSubscriptions(); 
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
  }, [cleanupUISseSubscriptions, setIsEditing, setShowAddForm, setStreamingContent, setProcessingStage, setErrorMessage]);

  // Cancel handler
  const handleCancel = useCallback((
    agentState: any,
    data: any,
    isInProcessingMode: boolean,
    isXmlGenerationComplete: boolean,
    isInErrorState: boolean,
    isInXmlApprovalMode: boolean
  ) => {
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return;
    
    cleanupUISseSubscriptions();
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
    setIsProcessing(false);

    setIsEditing(false);
    // If there was no task description before, cancel should return to "Add Task" state
    if (!agentState?.current_user_request && !data.currentUserRequest) {
      setShowAddForm(true);
    } else {
      setShowAddForm(false);
    }
  }, [cleanupUISseSubscriptions, setStreamingContent, setProcessingStage, setErrorMessage, setIsProcessing, setIsEditing, setShowAddForm]);

  // Add new task handler
  const handleAddNew = useCallback((
    isInProcessingMode: boolean,
    isXmlGenerationComplete: boolean,
    isInErrorState: boolean,
    isInXmlApprovalMode: boolean,
    setInput: (value: string) => void
  ) => {
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return;
    
    setInput('');
    setShowAddForm(true);
    setIsEditing(false);
    cleanupUISseSubscriptions();
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
  }, [cleanupUISseSubscriptions, setShowAddForm, setIsEditing, setStreamingContent, setProcessingStage, setErrorMessage]);

  return {
    handleSend,
    handleEdit,
    handleCancel,
    handleAddNew,
  };
}; 