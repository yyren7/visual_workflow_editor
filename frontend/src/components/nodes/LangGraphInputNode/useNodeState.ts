import { useState, useCallback, useEffect, useRef } from 'react';
import { useSelector } from 'react-redux';
import { selectAgentState, selectCurrentFlowId } from '../../../store/slices/flowSlice';
import { LangGraphInputNodeData, NodeState, AgentStateFlags } from './types';

export const useNodeState = (id: string, data: LangGraphInputNodeData) => {
  // Local state
  const [isInitialized, setIsInitialized] = useState(false);
  const [input, setInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [processingStage, setProcessingStage] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Refs
  const streamingContentRef = useRef<HTMLDivElement>(null);
  const uiSseUnsubscribeFnsRef = useRef<(() => void)[]>([]);
  const taskDescriptionRef = useRef<HTMLDivElement>(null);
  const editTextFieldRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  // Redux state
  const agentState = useSelector(selectAgentState);
  const reduxCurrentFlowId = useSelector(selectCurrentFlowId);

  // Operation chat ID
  const operationChatId = data.flowId || reduxCurrentFlowId;

  // Derived state flags
  const getAgentStateFlags = useCallback((): AgentStateFlags => {
    if (!agentState) {
      return {
        isInReviewMode: false,
        isInProcessingMode: false,
        isXmlGenerationComplete: false,
        isInErrorState: false,
        isInXmlApprovalMode: false,
      };
    }
    const { dialog_state, subgraph_completion_status } = agentState;
    const isProcessing = dialog_state?.includes('generating') ||
                         dialog_state?.includes('merging') ||
                         dialog_state?.includes('processing');
    
    return {
      isInReviewMode: dialog_state?.includes('review'),
      isInProcessingMode: isProcessing,
      isXmlGenerationComplete: subgraph_completion_status === 'completed_success' && dialog_state === 'final_xml_generated_success',
      isInErrorState: dialog_state === 'error',
      isInXmlApprovalMode: dialog_state === 'sas_awaiting_xml_generation_approval',
    };
  }, [agentState]);

  // Get processing description
  const getProcessingDescription = useCallback(() => {
    if (isProcessing && processingStage) {
      return `Local Processing: ${processingStage}`;
    }
    
    switch (agentState?.dialog_state) {
      case 'generating_xml_relation':
        return 'XML relations are being generated...';
      case 'generating_xml_final':
        return 'Final XML output is being generated...';
      case 'sas_step1_tasks_generated':
        return 'Task list has been generated, proceeding to next step...';
      case 'sas_step2_module_steps_generated_for_review':
        return 'Module steps generated and ready for review...';
      case 'sas_generating_individual_xmls':
        return 'Generating individual XML files for each task...';
      case 'sas_module_steps_accepted_proceeding':
        return 'Module steps accepted, proceeding to XML generation...';
      case 'sas_all_steps_accepted_proceed_to_xml':
        return 'All steps accepted, generating XML files...';
      case 'sas_individual_xmls_generated_ready_for_mapping':
        return 'Individual XMLs generated, preparing parameter mapping...';
      case 'sas_step3_to_merge_xml':
        return 'Merging XML files...';
      case 'sas_merging_done_ready_for_concat':
        return 'Concatenating final XML flow...';
      default:
        if (agentState?.subgraph_completion_status === 'processing') {
          return 'Processing workflow...';
        }
        return agentState?.current_step_description || 'Processing task...';
    }
  }, [agentState, isProcessing, processingStage]);

  // Check if processing is stuck
  const isProcessingStuck = useCallback(() => {
    if (!agentState) return false;
    
    const now = Date.now();
    const lastUpdate = agentState.last_updated ? new Date(agentState.last_updated).getTime() : now;
    const timeSinceUpdate = now - lastUpdate;
    
    const stuckStates = [
      'generating_xml_relation',
      'generating_xml_final',
      'sas_generating_individual_xmls',
      'sas_module_steps_accepted_proceeding',
      'sas_all_steps_accepted_proceed_to_xml'
    ];
    
    return stuckStates.includes(agentState.dialog_state) && timeSinceUpdate > 60000; // 60 seconds
  }, [agentState]);

  // Cleanup SSE subscriptions
  const cleanupUISseSubscriptions = useCallback(() => {
    uiSseUnsubscribeFnsRef.current.forEach(unsub => {
      try {
        unsub();
      } catch (error) {
        console.error(`LangGraphInputNode (${id}): Error during SSE cleanup:`, error);
      }
    });
    uiSseUnsubscribeFnsRef.current = [];
  }, [id]);

  // Initialize state effect
  useEffect(() => {
    if (data.flowId && !isInitialized) {
      setIsInitialized(true);
    }
  }, [data.flowId, isInitialized]);
  
  // Logic update based on initialization
  useEffect(() => {
    if (!isInitialized) return;

    const { isInReviewMode, isInProcessingMode } = getAgentStateFlags();
    const hasUserRequest = !!(agentState?.current_user_request || data.currentUserRequest);

    if (!isEditing && !showAddForm && !isInReviewMode && !isInProcessingMode) {
      setInput(agentState?.current_user_request || data.currentUserRequest || '');
    }

    if (!hasUserRequest && !isEditing && !isInReviewMode && !isProcessing && !isInProcessingMode) {
      setShowAddForm(true);
    } else if (hasUserRequest) {
      if (!isEditing && !isInProcessingMode) {
        setShowAddForm(false);
      }
    }
  }, [
    isInitialized,
    agentState?.current_user_request, 
    data.currentUserRequest, 
    isEditing, 
    showAddForm,
    getAgentStateFlags, 
    isProcessing
  ]);

  // Processing state check effect
  useEffect(() => {
    if (!isInitialized) return;

    const { isInProcessingMode } = getAgentStateFlags();
    
    if (isInProcessingMode && !isProcessing) {
      console.warn(`LangGraphInputNode (${id}): Detected processing state on page load for flow ${operationChatId}, dialog_state: ${agentState?.dialog_state}`);
      
      const stuckCheckTimer = setTimeout(() => {
        const currentFlags = getAgentStateFlags();
        if (currentFlags.isInProcessingMode && !isProcessing) {
          console.warn(`LangGraphInputNode (${id}): Processing state appears to be stuck for flow ${operationChatId}`);
        }
      }, 60000);

      return () => clearTimeout(stuckCheckTimer);
    }
  }, [id, operationChatId, agentState?.dialog_state, isProcessing, getAgentStateFlags]);

  // Stop processing when entering review/processing mode effect
  useEffect(() => {
    const { isInReviewMode, isInProcessingMode } = getAgentStateFlags();
    
    if ((isInReviewMode || isInProcessingMode) && isProcessing) {
      console.log(`LangGraphInputNode (${id}): Agent state changed to ${isInReviewMode ? 'review' : 'processing'} mode (${agentState?.dialog_state}), stopping local processing`);
      setIsProcessing(false);
      cleanupUISseSubscriptions();
    }
  }, [agentState?.dialog_state, id, isProcessing, cleanupUISseSubscriptions, getAgentStateFlags]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      console.log(`LangGraphInputNode (${id}): Unmounting. Cleaning up UI SSE subscriptions.`);
      cleanupUISseSubscriptions();
    };
  }, [cleanupUISseSubscriptions, id]);

  // Auto-scroll streaming content
  useEffect(() => {
    if (streamingContentRef.current) {
      streamingContentRef.current.scrollTop = streamingContentRef.current.scrollHeight;
    }
  }, [streamingContent]);

  return {
    // State
    isInitialized,
    input,
    isEditing,
    showAddForm,
    isProcessing,
    streamingContent,
    processingStage,
    errorMessage,
    operationChatId,
    
    // Refs
    streamingContentRef,
    uiSseUnsubscribeFnsRef,
    taskDescriptionRef,
    editTextFieldRef,
    cardRef,
    
    // Derived state
    agentState,
    getAgentStateFlags,
    getProcessingDescription,
    isProcessingStuck,
    
    // Actions
    setInput,
    setIsEditing,
    setShowAddForm,
    setIsProcessing,
    setStreamingContent,
    setProcessingStage,
    setErrorMessage,
    cleanupUISseSubscriptions,
  };
}; 