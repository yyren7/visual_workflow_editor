import React, { useCallback } from 'react';
import { Handle, Position } from 'reactflow';
import { 
  Card, 
  CardContent, 
  TextField, 
  Typography, 
  Box, 
  IconButton,
  Button,
  Chip,
  LinearProgress,
  Paper,
  CircularProgress,
  Skeleton
} from '@mui/material';
import { 
  Send as SendIcon, 
  Edit as EditIcon,
  Add as AddIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  AutoFixHigh as ProcessingIcon,
  ErrorOutline as ErrorIcon,
  InfoOutlined as InfoIcon,
  AccessTime as AccessTimeIcon
} from '@mui/icons-material';

import { LangGraphInputNodeProps, Task } from './types';
import { useNodeState } from './useNodeState';
import { useErrorRecovery } from './useErrorRecovery';
import { useAgentStateSync } from '../../../hooks/useAgentStateSync';
import { useSSEManager } from '../../../hooks/useSSEManager';
import { useTranslation } from 'react-i18next';

export const LangGraphInputNode: React.FC<LangGraphInputNodeProps> = ({ id, data, selected }) => {
  const { t } = useTranslation();
  
  // Node state management
  const {
    isInitialized,
    input,
    isEditing,
    showAddForm,
    isProcessing,
    streamingContent,
    processingStage,
    errorMessage,
    operationChatId,
    streamingContentRef,
    uiSseUnsubscribeFnsRef,
    taskDescriptionRef,
    editTextFieldRef,
    cardRef,
    agentState,
    getAgentStateFlags,
    getProcessingDescription,
    isProcessingStuck,
    setInput,
    setIsEditing,
    setShowAddForm,
    setIsProcessing,
    setStreamingContent,
    setProcessingStage,
    setErrorMessage,
    cleanupUISseSubscriptions,
  } = useNodeState(id, data);

  // Error recovery
  const {
    handleResetStuckState,
    handleForceReset,
    handleRollbackToPrevious,
    handleForceComplete,
  } = useErrorRecovery(operationChatId, setErrorMessage);

  // Processing logic
  const { updateUserInput } = useAgentStateSync();
  const { subscribe } = useSSEManager();

  // Main processing handler
  const handleSend = useCallback(async (overrideInput?: string) => {
    const contentToSend = overrideInput !== undefined ? overrideInput : input;
    if (!contentToSend.trim() && overrideInput === undefined) {
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
      await updateUserInput(contentToSend);
      
      const newUnsubs: (() => void)[] = [];

      newUnsubs.push(subscribe(operationChatId, 'token', (eventData) => {
        if (typeof eventData === 'string') {
          setStreamingContent(prev => prev + eventData);
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

      newUnsubs.push(subscribe(operationChatId, 'error', (eventData) => {
        console.error(`LangGraphInputNode (${id}): Received error event:`, eventData);
        const errorMessage = eventData?.message || 'An error occurred during processing';
        setErrorMessage(errorMessage);
        setIsProcessing(false);
        setProcessingStage('Error');
        cleanupUISseSubscriptions();
      }));

      newUnsubs.push(subscribe(operationChatId, 'connection_error', (eventData) => {
        console.error(`LangGraphInputNode (${id}): SSE Connection Error:`, eventData);
        setErrorMessage('Connection error with event stream. Please try again.');
        setIsProcessing(false);
        setProcessingStage('Connection Error');
        cleanupUISseSubscriptions();
      }));
      
      newUnsubs.push(subscribe(operationChatId, 'server_error_event', (eventData) => {
        console.error(`LangGraphInputNode (${id}): SSE Server Error Event:`, eventData);
        const message = eventData?.message || 'A server error occurred';
        setErrorMessage(message);
        setIsProcessing(false);
        setProcessingStage('Server Error');
        cleanupUISseSubscriptions();
      }));

      newUnsubs.push(subscribe(operationChatId, 'stream_end', () => {
        setProcessingStage(prev => prev.includes('Error') ? prev : 'Processing Complete');
        setIsProcessing(false);
      }));

      uiSseUnsubscribeFnsRef.current = newUnsubs;

    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to initiate processing.');
      setIsProcessing(false);
      setProcessingStage('Failed to Start');
    }

    setShowAddForm(false);
    setIsEditing(false);
  }, [input, operationChatId, updateUserInput, subscribe, id, cleanupUISseSubscriptions, setIsProcessing, setStreamingContent, setProcessingStage, setErrorMessage, uiSseUnsubscribeFnsRef, setShowAddForm, setIsEditing]);

  // UI event handlers
  const handleEdit = useCallback(() => {
    const { isInProcessingMode, isXmlGenerationComplete, isInErrorState, isInXmlApprovalMode } = getAgentStateFlags();
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return;
    
    const currentReq = agentState?.current_user_request || data.currentUserRequest || '';
    setInput(currentReq);
    setIsEditing(true);
    setShowAddForm(false);
    cleanupUISseSubscriptions(); 
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
  }, [getAgentStateFlags, agentState, data, setInput, setIsEditing, setShowAddForm, cleanupUISseSubscriptions, setStreamingContent, setProcessingStage, setErrorMessage]);

  const handleCancel = useCallback(() => {
    const { isInProcessingMode, isXmlGenerationComplete, isInErrorState, isInXmlApprovalMode } = getAgentStateFlags();
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return;
    
    cleanupUISseSubscriptions();
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
    setIsProcessing(false);

    setIsEditing(false);
    if (!agentState?.current_user_request && !data.currentUserRequest) {
      setShowAddForm(true);
    } else {
      setShowAddForm(false);
    }
  }, [getAgentStateFlags, cleanupUISseSubscriptions, setStreamingContent, setProcessingStage, setErrorMessage, setIsProcessing, setIsEditing, agentState, data, setShowAddForm]);

  const handleAddNew = useCallback(() => {
    const { isInProcessingMode, isXmlGenerationComplete, isInErrorState, isInXmlApprovalMode } = getAgentStateFlags();
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return;
    
    setInput('');
    setShowAddForm(true);
    setIsEditing(false);
    cleanupUISseSubscriptions();
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
  }, [getAgentStateFlags, setInput, setShowAddForm, setIsEditing, cleanupUISseSubscriptions, setStreamingContent, setProcessingStage, setErrorMessage]);

  // Event prevention - only for wheel events when selected
  const stopWheelPropagation = (e: React.WheelEvent) => e.stopPropagation();

  // UI state
  const { isInReviewMode, isInErrorState, isInXmlApprovalMode, isInProcessingMode, isXmlGenerationComplete } = getAgentStateFlags();
  const cardBackgroundColor = selected ? '#1e2a50' : '#2c3e50';
  const displayUserRequest = agentState?.current_user_request || data.currentUserRequest;
  const taskDisplayHeight = '150px';

  // Card title based on state
  const cardTitle = () => {
    if (isInErrorState) return t('nodes.input.taskError');
    if (isInXmlApprovalMode) return t('nodes.input.approveXmlGeneration');
    if (isInReviewMode) {
      switch (agentState.dialog_state) {
        case 'sas_awaiting_task_list_review':
          return t('nodes.input.reviewGeneratedTasks');
        case 'sas_awaiting_task_list_revision_input':
          return t('nodes.input.provideRevisedDescription');
        case 'sas_awaiting_module_steps_review':
        case 'sas_awaiting_module_steps_revision_input':
          return t('nodes.input.reviewModuleSteps');
        default:
          return t('nodes.input.reviewMode');
      }
    }
    if (isInProcessingMode) return t('nodes.input.processingTask');
    if (isXmlGenerationComplete) return t('nodes.input.taskComplete');
    return data.label || t('nodes.input.userInput');
  };

  // 如果尚未初始化，则显示一个占位符
  if (!isInitialized) {
    return (
      <Card sx={{ 
        width: 600, 
        minHeight: 200,
        backgroundColor: cardBackgroundColor, 
        border: selected ? '2px solid #76a9fa' : '2px solid #4a5568',
        borderRadius: '8px',
        display: 'flex',
        flexDirection: 'column',
        p: 2,
        boxSizing: 'border-box'
      }}>
        {/* Handles to prevent React Flow warnings */}
        <Handle type="target" position={Position.Left} style={{ background: '#555' }} />
        <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
        
        <Box display="flex" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Skeleton variant="text" sx={{ fontSize: '1rem', width: '40%', bgcolor: 'grey.700' }} />
          <Skeleton variant="rounded" width={60} height={20} sx={{ bgcolor: 'grey.700', borderRadius: '16px' }} />
        </Box>

        <Skeleton variant="rounded" sx={{ flexGrow: 1, bgcolor: 'grey.700', mb: 2, borderRadius: 1 }} />

        <Box display="flex" justifyContent="flex-start" gap={1}>
          <Skeleton variant="rounded" width={80} height={32} sx={{ bgcolor: 'grey.700', borderRadius: 1 }} />
        </Box>
      </Card>
    );
  }

  return (
    <Card 
      ref={cardRef}
      sx={{ 
        width: 600, 
        minHeight: isInReviewMode || (isEditing || showAddForm) ? 300 : 
                  isInErrorState ? 280 :
                  isInXmlApprovalMode ? 320 :
                  isInProcessingMode ? 250 : 
                  isXmlGenerationComplete ? 280 :
                  (displayUserRequest ? 200: 150), 
        maxHeight: '80vh',
        backgroundColor: cardBackgroundColor, 
        border: selected ? '2px solid #76a9fa' : '2px solid #4a5568',
        borderRadius: '8px',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.3s ease',
        boxShadow: selected ? '0 0 15px rgba(118, 169, 250, 0.5)' : '0 4px 8px rgba(0,0,0,0.3)',
        overflow: 'hidden',
        '& @keyframes spin': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' }
        }
      }}
      onWheelCapture={selected ? stopWheelPropagation : undefined}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#555' }} />
      
      <CardContent sx={{ 
        p: 2, 
        transition: 'all 0.3s ease',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}> 
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1} sx={{ flexShrink: 0 }}>
          <Typography 
            variant="h6"
            sx={{ 
              fontSize: '1rem',
              fontWeight: 'bold',
              color: selected ? '#fff' : '#eee',
              transition: 'all 0.3s ease'
            }}
          >
            {cardTitle()}
          </Typography>
          <Chip 
            label={
              isInErrorState ? t('nodes.input.error') :
              isInXmlApprovalMode ? t('nodes.input.awaitingApproval') :
              isProcessing ? t('nodes.input.processing') : 
              isInReviewMode ? t('nodes.input.reviewMode') : 
              isInProcessingMode ? t('nodes.input.processingTask') :
              isXmlGenerationComplete ? t('nodes.input.complete') :
              (isEditing ? t('nodes.input.editing') : (showAddForm ? t('nodes.input.newTask') : t('nodes.input.idle')))
            }
            size="small" 
            color={
              isInErrorState ? "error" :
              isInXmlApprovalMode ? "warning" :
              isProcessing ? "success" : 
              isInReviewMode ? "warning" : 
              isInProcessingMode ? "info" :
              isXmlGenerationComplete ? "success" :
              (isEditing || showAddForm ? "info" : "primary")
            }
            variant="outlined"
            icon={
              isInErrorState ? <ErrorIcon fontSize="small"/> :
              isInXmlApprovalMode ? <AccessTimeIcon fontSize="small"/> :
              isProcessing ? <ProcessingIcon fontSize="small"/> : 
              isInProcessingMode ? <ProcessingIcon fontSize="small"/> : 
              isXmlGenerationComplete ? <CheckIcon fontSize="small"/> : 
              undefined
            }
            sx={{ 
              fontSize: '0.7rem',
              height: '20px',
              '& .MuiChip-label': { px: 1 }
            }}
          />
        </Box>
        
        <Box sx={{ 
          mt: 1, 
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          {/* Error Message */}
          {errorMessage && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1.5, backgroundColor: '#ffebee', color: '#c62828', display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
              <ErrorIcon fontSize="small" />
              <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>{errorMessage}</Typography>
            </Paper>
          )}

          {/* Processing Display */}
          {(isProcessing || streamingContent) && !isInReviewMode && (
            <Box sx={{ mb: 1, flexShrink: 0, border: '1px solid #444', borderRadius: 1, p:1, maxHeight: '150px', overflowY: 'auto' }} ref={streamingContentRef}>
              {isProcessing && !streamingContent && (
                <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                  <ProcessingIcon sx={{ fontSize: '1rem', color: '#4caf50' }} />
                  <Typography variant="body2" sx={{ color: '#aaa', fontSize: '0.8rem', fontStyle: 'italic' }}>
                    {processingStage || 'Processing...'}
                  </Typography>
                </Box>
              )}
              {isProcessing && streamingContent && (
                 <Typography variant="caption" sx={{ color: '#aaa', fontSize: '0.75rem', display: 'block', mb: 0.5 }}>{processingStage}</Typography>
              )}
              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '0.85rem', color: '#e0e0e0' }}>
                {streamingContent || (isProcessing ? t('nodes.input.waitingForResponse') : '')}
              </Typography>
            </Box>
          )}
          {isProcessing && <LinearProgress color="success" sx={{ mb: 1, height: 3, borderRadius: 1.5, flexShrink: 0 }} /> }

          {/* Error State Display */}
          {isInErrorState && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1, backgroundColor: '#3d1a1a', border: '1px solid #f44336', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <ErrorIcon sx={{ fontSize: '1rem', color: '#f44336' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#f44336' }}>
                  {t('nodes.input.taskProcessingError')}
                </Typography>
              </Box>
              <Typography 
                variant="body2" 
                component="pre"
                sx={{ 
                  color: '#ffcdd2', 
                  fontSize: '0.85rem', 
                  mb: 1,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'inherit'
                }}
              >
                {agentState?.error_message || t('nodes.input.taskProcessingErrorDesc')}
              </Typography>
              <Typography variant="caption" sx={{ color: '#ffab91', fontSize: '0.75rem', display: 'block', mb: 1 }}>
                {t('nodes.input.currentState', { state: agentState?.dialog_state })}
              </Typography>
              
              <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                <Button
                  size="small"
                  variant="outlined"
                  color="warning"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={() => window.location.reload()}
                >
                  {t('nodes.input.refreshPage')}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="info"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={handleRollbackToPrevious}
                >
                  {t('nodes.input.rollbackState')}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={handleForceReset}
                >
                  {t('nodes.input.resetToInitial')}
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  color="warning"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={handleForceComplete}
                >
                  {t('nodes.input.skipError')}
                </Button>
              </Box>
            </Paper>
          )}

          {/* XML Generation Approval Mode */}
          {isInXmlApprovalMode && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733', border: '1px solid #ff9800', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <AccessTimeIcon sx={{ fontSize: '1rem', color: '#ff9800' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#ff9800' }}>
                  {t('nodes.input.xmlGenerationApprovalRequired')}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#ffcc80', fontSize: '0.85rem', mb: 1 }}>
                {t('nodes.input.xmlApprovalDesc')}
              </Typography>
              
              {/* Task Summary */}
              {agentState?.sas_step1_generated_tasks && agentState.sas_step1_generated_tasks.length > 0 && (
                <Box sx={{ mb: 1.5, p: 1, backgroundColor: '#0d1117', borderRadius: 1, border: '1px solid #444' }}>
                  <Typography variant="caption" sx={{ color: '#aaa', fontSize: '0.75rem', display: 'block', mb: 0.5 }}>
                    {t('nodes.input.taskConfigSummary')}
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.8rem' }}>
                    {t('nodes.input.tasksGenerated', { count: agentState.sas_step1_generated_tasks.length })}
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.8rem' }}>
                    {t('nodes.input.moduleStepsDefined')}
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.8rem' }}>
                    {t('nodes.input.readyToGenerate')}
                  </Typography>
                </Box>
              )}

              {/* Confirmation Question */}
              {agentState?.clarification_question && (
                <Box sx={{ mb: 1.5, p: 1, backgroundColor: '#2c1810', borderRadius: 1, border: '1px solid #ff9800' }}>
                  <Typography variant="body2" sx={{ color: '#ffcc80', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>
                    {agentState.clarification_question}
                  </Typography>
                </Box>
              )}

              {/* Approval Buttons */}
              <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                <Button
                  size="small"
                  variant="contained"
                  color="success"
                  startIcon={<CheckIcon />}
                  sx={{ fontSize: '0.75rem', minHeight: '28px' }}
                  onClick={() => handleSend('approve')}
                  disabled={isProcessing}
                >
                  {t('nodes.input.approveGenerateXml')}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  sx={{ fontSize: '0.75rem', minHeight: '28px' }}
                  onClick={() => handleSend('reset')}
                  disabled={isProcessing}
                >
                  {t('nodes.input.resetTask')}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="warning"
                  sx={{ fontSize: '0.75rem', minHeight: '28px' }}
                  onClick={() => window.location.reload()}
                >
                  {t('nodes.input.refreshPage')}
                </Button>
              </Box>
            </Paper>
          )}

          {/* Processing Mode Display */}
          {isInProcessingMode && !isProcessing && (
            <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733', border: '1px solid #2196f3', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <ProcessingIcon sx={{ fontSize: '1rem', color: '#2196f3', animation: 'spin 2s linear infinite' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#2196f3' }}>
                  {t('nodes.input.taskProcessing')}
                </Typography>
                {isProcessingStuck() && (
                  <Chip 
                    label={t('nodes.input.possibleStuck')}
                    size="small"
                    color="warning"
                    variant="outlined"
                    sx={{ fontSize: '0.6rem', height: '18px' }}
                  />
                )}
              </Box>
              <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.85rem' }}>
                {getProcessingDescription()}
              </Typography>
              {agentState?.current_step_description && (
                <Typography variant="caption" sx={{ color: '#aaa', fontSize: '0.75rem', display: 'block', mt: 0.5, fontStyle: 'italic' }}>
                  {agentState.current_step_description}
                </Typography>
              )}
              
              {/* Stuck State Recovery Options */}
              {isProcessingStuck() && (
                <Box sx={{ mt: 1.5, p: 1, backgroundColor: '#2c1810', borderRadius: 1, border: '1px solid #ff9800' }}>
                  <Typography variant="caption" sx={{ color: '#ffb74d', fontSize: '0.75rem', display: 'block', mb: 1 }}>
                    {t('nodes.input.stuckDetected')}
                  </Typography>
                  <Box display="flex" gap={1} flexWrap="wrap">
                    <Button
                      size="small"
                      variant="outlined"
                      color="warning"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={() => window.location.reload()}
                    >
                      {t('nodes.input.refreshPage')}
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="info"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={handleRollbackToPrevious}
                    >
                      {t('nodes.input.rollbackState')}
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="error"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={handleForceReset}
                    >
                      {t('nodes.input.resetToInitial')}
                    </Button>
                    <Button
                      size="small"
                      variant="contained"
                      color="warning"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={handleForceComplete}
                    >
                      {t('nodes.input.skipError')}
                    </Button>
                  </Box>
                </Box>
              )}
            </Paper>
          )}

          {/* XML Generation Complete */}
          {isXmlGenerationComplete && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1, backgroundColor: '#1b5e20', color: '#c8e6c9', border: '1px solid #4caf50', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <CheckIcon sx={{ fontSize: '1rem', color: '#4caf50' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                  {t('nodes.input.taskCompletedSuccessfully')}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#c8e6c9', fontSize: '0.85rem', mb: 1 }}>
                {t('nodes.input.xmlFileGenerated')}
              </Typography>
              {agentState?.final_flow_xml_path && (
                <Typography variant="caption" sx={{ color: '#a5d6a7', fontSize: '0.75rem', fontFamily: 'monospace', display: 'block', mb: 1 }}>
                  {t('nodes.input.filePath', { path: agentState.final_flow_xml_path })}
                </Typography>
              )}
              <Box display="flex" gap={1} mt={1}>
                <Button 
                  size="small" 
                  variant="outlined" 
                  sx={{ 
                    fontSize: '0.8rem', 
                    color: '#4caf50', 
                    borderColor: '#4caf50',
                    '&:hover': {
                      borderColor: '#66bb6a',
                      backgroundColor: 'rgba(76, 175, 80, 0.1)'
                    }
                  }}
                  onClick={() => {
                    console.log('View XML file:', agentState?.final_flow_xml_path);
                  }}
                >
                  {t('nodes.input.viewResult')}
                </Button>
                <Button 
                  size="small" 
                  variant="contained" 
                  color="primary"
                  sx={{ fontSize: '0.8rem' }}
                  onClick={() => {
                    setShowAddForm(true);
                    setIsEditing(false);
                    setInput('');
                  }}
                >
                  {t('nodes.input.createNewTask')}
                </Button>
              </Box>
            </Paper>
          )}

          {/* 🎯 REVIEW MODE - 这就是您要找的部分！ */}
          {isInReviewMode && agentState && (
            <Box sx={{ mb: 1, flexGrow: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
              {/* Top part for displaying information */}
              <Box sx={{ flexShrink: 0 }}>
                {/* Display clarification question or instruction */}
                <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#ffc107', mb:0.5}}>
                    {agentState.dialog_state === 'sas_awaiting_task_list_revision_input' 
                      ? t('nodes.input.assistantRequiresRevisedDescription') 
                      : t('nodes.input.assistantNeedsYourInput')}
                  </Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#eee' }}>
                    {agentState.clarification_question || t('nodes.input.pleaseReviewGeneratedTasks')}
                  </Typography>
                </Paper>

                {/* 🌟 显示任务列表 */}
                {agentState.dialog_state === 'sas_awaiting_task_list_review' && agentState.sas_step1_generated_tasks && (
                  <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#90caf9', mb:0.5}}>{t('nodes.input.proposedTasksForReview')}:</Typography>
                    <Box sx={{maxHeight: taskDisplayHeight, overflowY: 'auto'}}>
                      {agentState.sas_step1_generated_tasks.map((task: Task, index: number) => (
                          <Typography key={index} variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#eee', mb: 0.5, fontSize: '0.8rem' }}>
                              {`${index + 1}. ${task.name} (${task.type})`}
                          </Typography>
                      ))}
                    </Box>
                  </Paper>
                )}

                {/* 🌟 显示模块步骤 */}
                {agentState.dialog_state === 'sas_awaiting_module_steps_review' && agentState.sas_step1_generated_tasks && (
                  <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#90caf9', mb:0.5}}>{t('nodes.input.generatedModuleStepsForReview')}:</Typography>
                    <Box sx={{maxHeight: taskDisplayHeight, overflowY: 'auto'}}>
                      {agentState.sas_step1_generated_tasks.map((task: Task, index: number) => (
                        <Box key={index} sx={{ mb: 1.5, p: 1, backgroundColor: '#0d1117', borderRadius: 1, border: '1px solid #444' }}>
                          <Typography variant="subtitle2" sx={{ color: '#4caf50', fontSize: '0.8rem', fontWeight: 'bold', mb: 0.5 }}>
                            {t('nodes.input.task', { index: index + 1, name: task.name })}
                          </Typography>
                          {task.details && task.details.length > 0 && (
                            <Box sx={{ ml: 1 }}>
                              {task.details.map((detail: string, detailIndex: number) => (
                                <Typography key={detailIndex} variant="body2" sx={{ color: '#eee', fontSize: '0.75rem', mb: 0.3 }}>
                                  • {detail}
                                </Typography>
                              ))}
                            </Box>
                          )}
                          {(!task.details || task.details.length === 0) && (
                            <Typography variant="body2" sx={{ color: '#aaa', fontSize: '0.75rem', fontStyle: 'italic' }}>
                              {t('nodes.input.moduleStepsPending')}
                            </Typography>
                          )}
                        </Box>
                      ))}
                    </Box>
                  </Paper>
                )}
              </Box>

              {/* Bottom part for user input and actions */}
              <Box sx={{ mt: 'auto', flexShrink: 0 }}>
                <TextField
                  fullWidth
                  variant="outlined"
                  label={
                    agentState.dialog_state === 'sas_awaiting_task_list_review' 
                      ? t('nodes.input.provideFeedback') 
                      : t('nodes.input.yourResponse')
                  }
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  multiline
                  rows={3}
                  disabled={isProcessing}
                  sx={{ 
                    mb: 1,
                    textarea: { color: '#fff', fontSize: '0.9rem' },
                    label: { color: '#bbb' },
                    '& .MuiOutlinedInput-root': {
                      '& fieldset': { borderColor: '#555' },
                      '&:hover fieldset': { borderColor: '#777' },
                    }
                  }}
                />
                <Box display="flex" justifyContent="flex-end" gap={1}>
                  {agentState.dialog_state === 'sas_awaiting_task_list_review' && (
                      <Button 
                          size="small" variant="contained" color="success"
                          onClick={() => handleSend("accept_tasks")}
                          startIcon={<CheckIcon />} disabled={isProcessing} sx={{ fontSize: '0.8rem'}}
                      >
                          {t('nodes.input.approveTasks')}
                      </Button>
                  )}
                  {agentState.dialog_state === 'sas_awaiting_module_steps_review' && (
                      <Button 
                          size="small" variant="contained" color="success"
                          onClick={() => handleSend("accept_module_steps")}
                          startIcon={<CheckIcon />} disabled={isProcessing} sx={{ fontSize: '0.8rem'}}
                      >
                          {t('nodes.input.approveModuleSteps')}
                      </Button>
                  )}
                  <Button 
                    size="small" variant="contained" 
                    onClick={() => handleSend()}
                    startIcon={<SendIcon />} 
                    disabled={isProcessing || ((agentState.dialog_state !== 'sas_awaiting_task_list_review' && agentState.dialog_state !== 'sas_awaiting_module_steps_review') && !input.trim())}
                    sx={{ fontSize: '0.8rem'}}
                  >
                    {agentState.dialog_state === 'sas_awaiting_task_list_review' ? t('nodes.input.submitFeedback') : 
                     agentState.dialog_state === 'sas_awaiting_module_steps_review' ? t('nodes.input.submitFeedback') : t('nodes.input.sendResponse')}
                  </Button>
                </Box>
              </Box>
            </Box>
          )}

          {/* Task Display */}
          {!isEditing && !showAddForm && !isInReviewMode && !isProcessing && !isInProcessingMode && displayUserRequest && (
            <Box sx={{ overflowY: 'auto', flexGrow: 1, mb:1, border: '1px dashed #444', borderRadius:1, p:1 }} ref={taskDescriptionRef}>
              <Typography variant="caption" sx={{color: '#aaa', fontStyle:'italic', display:'block', mb:0.5}}>{t('nodes.input.currentTaskDescription')}:</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#fff', fontSize: '0.9rem', lineHeight: 1.5, wordBreak: 'break-word'}}>
                {displayUserRequest}
              </Typography>
            </Box>
          )}

          {/* Edit Controls */}
          {!isEditing && !showAddForm && !isInReviewMode && !isProcessing && !isInProcessingMode && !isXmlGenerationComplete && displayUserRequest && (
             <Box display="flex" gap={1} sx={{ flexShrink: 0, mt: 'auto' }}>
                <Button size="small" startIcon={<EditIcon />} onClick={handleEdit} variant="outlined" disabled={isProcessing || isInProcessingMode} sx={{ fontSize: '0.8rem'}}>
                  {t('nodes.input.edit')}
                </Button>
              </Box>
          )}

          {/* Input Form */}
          {(isEditing || showAddForm) && !isInReviewMode && !isProcessing && !isInProcessingMode && (
            <Box sx={{ height: 'auto', display: 'flex', flexDirection: 'column', flexGrow:1, overflowY:'auto' }} ref={editTextFieldRef}>
              <TextField
                fullWidth
                variant="outlined"
                label={isEditing ? t('nodes.input.editTaskDescription') : t('nodes.input.newTaskDescription')}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                multiline
                rows={showAddForm ? 5 : 3}
                autoFocus={showAddForm || isEditing}
                sx={{ 
                  mb: 1, 
                  flexGrow: 1,
                  textarea: { color: '#fff', fontSize: '0.9rem' },
                  label: { color: '#bbb' },
                  '& .MuiOutlinedInput-root': {
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    '& fieldset': { borderColor: '#555' },
                    '&:hover fieldset': { borderColor: '#777' },
                    '&.Mui-focused fieldset': { borderColor: '#76a9fa' },
                    '& .MuiInputBase-inputMultiline': {
                        flexGrow: 1,
                        overflowY: 'auto'
                    }
                  }
                }}
              />
              <Box display="flex" justifyContent="flex-end" gap={1} sx={{flexShrink:0}}>
                <Button size="small" onClick={handleCancel} disabled={isProcessing} sx={{ fontSize: '0.8rem'}} variant="outlined">
                  {t('nodes.input.cancel')}
                </Button>
                <Button 
                  size="small" variant="contained" 
                  onClick={() => handleSend()} 
                  startIcon={isEditing ? <CheckIcon /> : <SendIcon />}
                  disabled={isProcessing || !input.trim()}
                  sx={{ fontSize: '0.8rem'}}
                >
                  {isEditing ? t('nodes.input.confirmEdit') : t('nodes.input.send')}
                </Button>
              </Box>
            </Box>
          )}

          {/* No Task Display */}
          {!displayUserRequest && !isEditing && !showAddForm && !isInReviewMode && !isProcessing && !isInProcessingMode && (
            <Box textAlign="center" py={3} sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
              <InfoIcon sx={{fontSize: '2rem', color: 'rgba(255, 255, 255, 0.3)', mb:1 }}/>
              <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '0.9rem', mb: 2 }}>
                {t('nodes.input.noTaskDescriptionYet')}
              </Typography>
              <Button startIcon={<AddIcon />} onClick={handleAddNew} variant="contained" color="primary" size="medium" sx={{ fontSize: '0.8rem'}}>
                {t('nodes.input.addTaskDescription')}
              </Button>
            </Box>
          )}
        </Box>
      </CardContent>
      
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </Card>
  );
}; 