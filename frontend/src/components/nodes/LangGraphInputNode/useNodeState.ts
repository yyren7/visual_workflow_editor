import { useState, useCallback, useEffect, useRef } from 'react';
import { useSelector } from 'react-redux';
import { selectAgentState, selectCurrentFlowId } from '../../../store/slices/flowSlice';
import { LangGraphInputNodeData, AgentStateFlags } from './types';

export const useNodeState = (id: string, data: LangGraphInputNodeData) => {
  // Local state
  const [isInitialized, setIsInitialized] = useState(false);
  const [input, setInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Refs
  const streamingContentRef = useRef<HTMLDivElement>(null);
  const taskDescriptionRef = useRef<HTMLDivElement>(null);
  const editTextFieldRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  // Redux state
  const agentState = useSelector(selectAgentState);
  const reduxCurrentFlowId = useSelector(selectCurrentFlowId);

  // Derived state from Redux
  const streamingContent = agentState?.streamingContent || '';
  const processingStage = agentState?.processingStage || '';
  const isProcessing = !!processingStage && processingStage !== 'Processing Complete' && !processingStage.startsWith('Error');

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
        isReadyForReview: false,
      };
    }
    const { dialog_state, subgraph_completion_status } = agentState;
    
    // 扩展处理中状态检测
    const isProcessing = dialog_state?.includes('generating') ||
                         dialog_state?.includes('merging') ||
                         dialog_state?.includes('processing') ||
                         dialog_state === 'sas_xml_generation_approved' ||
                         dialog_state === 'sas_step3_completed';
    
    // 审核模式状态
    const isInReviewMode = dialog_state === 'sas_awaiting_task_list_review' ||
                          dialog_state === 'sas_awaiting_task_list_revision_input' ||
                          dialog_state === 'sas_awaiting_module_steps_review' ||
                          dialog_state === 'sas_awaiting_module_steps_revision_input';
    
    // 准备审核状态
    const isReadyForReview = dialog_state === 'sas_step1_tasks_generated' ||
                            dialog_state === 'sas_step2_module_steps_generated_for_review';
    
    // 扩展错误状态检测
    const isInErrorState = dialog_state === 'error' ||
                          dialog_state === 'generation_failed' ||
                          dialog_state === 'sas_processing_error';
    
    return {
      isInReviewMode,
      isInProcessingMode: isProcessing,
      isXmlGenerationComplete: subgraph_completion_status === 'completed_success' && dialog_state === 'final_xml_generated_success',
      isInErrorState,
      isInXmlApprovalMode: dialog_state === 'sas_awaiting_xml_generation_approval',
      isReadyForReview,
    };
  }, [agentState]);

  // Get processing description
  const getProcessingDescription = useCallback(() => {
    if (isProcessing && processingStage) {
      return `Local Processing: ${processingStage}`;
    }
    
    if (!agentState) return 'Initializing...';

    switch (agentState.dialog_state) {
      case 'generating_xml_relation':
        return 'XML relations are being generated...';
      case 'generating_xml_final':
        return 'Final XML output is being generated...';
      case 'sas_step1_tasks_generated':
        return 'Task list has been generated, proceeding to next step...';
      case 'sas_step2_module_steps_generated_for_review':
        return 'Module steps generated and ready for review...';
      case 'sas_step3_completed':
        return 'Parameter mapping completed successfully...';
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
      case 'sas_merging_completed':
        return 'XML merging completed successfully...';
      case 'sas_merging_completed_no_files':
        return 'XML merging completed (no files to merge)...';
      case 'sas_merging_done_ready_for_concat':
        return 'Concatenating final XML flow...';
      case 'sas_xml_generation_approved':
        return 'XML generation approved, starting process...';
      case 'generation_failed':
        return 'Generation process failed, please try again...';
      case 'sas_processing_error':
        return 'Processing error occurred...';
      default:
        if (agentState.subgraph_completion_status === 'processing') {
          return 'Processing workflow...';
        }
        return agentState.current_step_description || 'Processing task...';
    }
  }, [agentState, isProcessing, processingStage]);

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
      'sas_all_steps_accepted_proceed_to_xml',
      'sas_step3_to_merge_xml',
      'sas_merging_completed',
      'sas_merging_completed_no_files',
      'sas_xml_generation_approved',
      'sas_step3_completed'
    ];
    
    return stuckStates.includes(agentState.dialog_state) && timeSinceUpdate > 60000; // 60 seconds
  }, [agentState]);

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
    setErrorMessage,
  };
}; 