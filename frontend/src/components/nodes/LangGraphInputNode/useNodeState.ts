import { useState, useCallback, useEffect, useRef } from 'react';
import { useSelector } from 'react-redux';
import { selectAgentState, selectCurrentFlowId } from '../../../store/slices/flowSlice';
import { LangGraphInputNodeData, NodeState, AgentStateFlags } from './types';

export const useNodeState = (id: string, data: LangGraphInputNodeData) => {
  // Local state
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
    const isInReviewMode = 
      agentState?.dialog_state === 'sas_awaiting_task_list_review' ||
      agentState?.dialog_state === 'sas_awaiting_module_steps_review' ||
      agentState?.dialog_state === 'sas_awaiting_task_list_revision_input' ||
      agentState?.dialog_state === 'sas_awaiting_module_steps_revision_input';

    const isInErrorState = 
      agentState?.is_error === true ||
      agentState?.subgraph_completion_status === 'error';

    const isInXmlApprovalMode = 
      agentState?.dialog_state === 'sas_awaiting_xml_generation_approval';

    const isInProcessingMode = !isInErrorState && (
      agentState?.dialog_state === 'generating_xml_relation' ||
      agentState?.dialog_state === 'generating_xml_final' ||
      agentState?.dialog_state === 'sas_step1_tasks_generated' ||
      agentState?.dialog_state === 'sas_step2_module_steps_generated_for_review' ||
      agentState?.dialog_state === 'sas_generating_individual_xmls' ||
      agentState?.dialog_state === 'sas_module_steps_accepted_proceeding' ||
      agentState?.dialog_state === 'sas_all_steps_accepted_proceed_to_xml');

    const isXmlGenerationComplete = !isInErrorState && (
      agentState?.dialog_state === 'sas_step3_completed' ||
      (agentState?.subgraph_completion_status === 'completed_success' && 
       agentState?.final_flow_xml_path));

    return {
      isInReviewMode,
      isInErrorState,
      isInXmlApprovalMode,
      isInProcessingMode,
      isXmlGenerationComplete,
    };
  }, [agentState]);

  // Get processing description
  const getProcessingDescription = useCallback(() => {
    switch (agentState?.dialog_state) {
      case 'sas_step1_tasks_generated':
        return '正在生成详细模块步骤...';
      case 'sas_step2_module_steps_generated_for_review':
        return '模块步骤已生成，准备进入下一阶段...';
      case 'sas_generating_individual_xmls':
        return '正在生成个体XML文件...';
      case 'generating_xml_relation':
        return '正在生成XML关系文件...';
      case 'generating_xml_final':
        return '正在生成最终XML文件...';
      case 'sas_module_steps_accepted_proceeding':
        return '模块步骤已确认，正在进行下一步...';
      case 'sas_all_steps_accepted_proceed_to_xml':
        return '所有步骤已确认，正在生成XML...';
      default:
        return '正在处理中...';
    }
  }, [agentState]);

  // Check if processing is stuck
  const isProcessingStuck = useCallback(() => {
    const { isInProcessingMode } = getAgentStateFlags();
    if (!isInProcessingMode || !agentState) return false;
    
    const hasRecentActivity = agentState.messages && agentState.messages.length > 0;
    const hasStepDescription = agentState.current_step_description;
    
    return !hasRecentActivity && !hasStepDescription;
  }, [agentState, getAgentStateFlags]);

  // Cleanup SSE subscriptions
  const cleanupUISseSubscriptions = useCallback(() => {
    if (uiSseUnsubscribeFnsRef.current.length > 0) {
      console.log(`LangGraphInputNode (${id}): Cleaning up ${uiSseUnsubscribeFnsRef.current.length} UI SSE subscriptions for chat: ${operationChatId}`);
      uiSseUnsubscribeFnsRef.current.forEach(unsub => unsub());
      uiSseUnsubscribeFnsRef.current = [];
    }
  }, [id, operationChatId]);

  // Initialize state effect
  useEffect(() => {
    const { isInReviewMode, isInProcessingMode } = getAgentStateFlags();
    
    if (!isEditing && !showAddForm && !isInReviewMode && !isInProcessingMode) {
      setInput(agentState?.current_user_request || data.currentUserRequest || '');
    }

    if (!agentState?.current_user_request && !data.currentUserRequest && !isEditing && !isInReviewMode && !isProcessing && !isInProcessingMode) {
      setShowAddForm(true);
    } else if (agentState?.current_user_request || data.currentUserRequest) {
      if (!isEditing && !isInProcessingMode) {
        setShowAddForm(false);
      }
    }
  }, [agentState?.current_user_request, data.currentUserRequest, isEditing, getAgentStateFlags, isProcessing]);

  // Processing state check effect
  useEffect(() => {
    const { isInProcessingMode } = getAgentStateFlags();
    
    if (isInProcessingMode && !isProcessing) {
      console.warn(`LangGraphInputNode (${id}): Detected processing state on page load for flow ${operationChatId}, dialog_state: ${agentState?.dialog_state}`);
      
      const stuckCheckTimer = setTimeout(() => {
        const currentFlags = getAgentStateFlags();
        if (currentFlags.isInProcessingMode && !isProcessing) {
          console.warn(`LangGraphInputNode (${id}): Processing state appears to be stuck for flow ${operationChatId}`);
        }
      }, 30000);

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