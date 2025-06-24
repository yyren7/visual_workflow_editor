import React, { useState, useCallback, useEffect, useRef } from 'react';
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
  Paper
} from '@mui/material';
import { 
  Send as SendIcon, 
  Edit as EditIcon,
  Add as AddIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  AutoFixHigh as ProcessingIcon,
  ErrorOutline as ErrorIcon,
  InfoOutlined as InfoIcon
} from '@mui/icons-material';
import { useAgentStateSync } from '../../hooks/useAgentStateSync';
import { useSSEManager } from '../../hooks/useSSEManager';
import { useSelector } from 'react-redux';
import { selectAgentState, selectCurrentFlowId } from '../../store/slices/flowSlice';

interface LangGraphInputNodeData {
  label: string;
  flowId: string;
  userInput?: string;
  currentUserRequest?: string;
}

interface LangGraphInputNodeProps {
  id: string;
  data: LangGraphInputNodeData;
  selected: boolean;
}

interface ReviewContextData {
  clarification_question?: string;
  originalRequest?: string;
  tasks?: any[];
  details?: any;
  dialog_state?: string;
}

const parseReviewContext = (clarificationQuestion: string): ReviewContextData | null => {
  if (!clarificationQuestion) return null;

  const originalRequestRegex = /Original Request:\s*```text\s*([\s\S]*?)\s*```/m;
  const generatedTasksRegex = /Generated Tasks(?: \(Iteration \d+\))?:\s*```json\s*([\s\S]*?)\s*```/m;
  const userFeedbackRegex = /Your Feedback:\s*```text\s*([\s\S]*?)\s*```/m;
  const instructionalTextRegex = /```\s*Your Feedback:[\s\S]*?```\s*([\s\S]*)/m;


  const originalRequestMatch = clarificationQuestion.match(originalRequestRegex);
  const generatedTasksMatch = clarificationQuestion.match(generatedTasksRegex);
  const userFeedbackMatch = clarificationQuestion.match(userFeedbackRegex);
  const instructionalTextMatch = clarificationQuestion.match(instructionalTextRegex);

  if (originalRequestMatch && originalRequestMatch[1] && generatedTasksMatch && generatedTasksMatch[1] && userFeedbackMatch && userFeedbackMatch[1]) {
    // Attempt to parse tasks if it's JSON, otherwise keep as string or handle error
    let parsedTasks: any[] | string = generatedTasksMatch[1].trim();
    try {
      parsedTasks = JSON.parse(parsedTasks);
    } catch (e) {
      console.warn('parseReviewContext: generatedTasks content is not valid JSON, keeping as string. Content:', parsedTasks);
      // Decide if you want to return null or the string itself for tasks
      // For now, let's assume if it's not parsable JSON for tasks, the context is invalid for 'tasks: any[]'
      // return null; // Or handle differently, e.g. tasks: parsedTasks (as string)
    }

    return {
      originalRequest: originalRequestMatch[1].trim(),
      tasks: parsedTasks,
      dialog_state: instructionalTextMatch && instructionalTextMatch[1] ? instructionalTextMatch[1].trim() : "Please provide a complete revised task description in the input field. You can also choose to 'approve' the generated tasks.",
    };
  }
  console.warn("parseReviewContext: Failed to match all expected parts or parse tasks. Question:", clarificationQuestion);
  return null;
};

export const LangGraphInputNode: React.FC<LangGraphInputNodeProps> = ({ id, data, selected }) => {
  const [input, setInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [processingStage, setProcessingStage] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const streamingContentRef = useRef<HTMLDivElement>(null);
  const uiSseUnsubscribeFnsRef = useRef<(() => void)[]>([]);
  
  const taskDescriptionRef = useRef<HTMLDivElement>(null);
  const editTextFieldRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  
  const { updateUserInput, startLangGraphProcessing } = useAgentStateSync();
  const { subscribe, closeConnection: closeSSEConnectionByManager } = useSSEManager();
  const agentState = useSelector(selectAgentState);
  const reduxCurrentFlowId = useSelector(selectCurrentFlowId);

  const [isInReviewMode, setIsInReviewMode] = useState(false);
  const [reviewContext, setReviewContext] = useState<ReviewContextData | null>(null);

  const operationChatId = data.flowId || reduxCurrentFlowId;

  const cleanupUISseSubscriptions = useCallback(() => {
    if (uiSseUnsubscribeFnsRef.current.length > 0) {
      console.log(`LangGraphInputNode (${id}): Cleaning up ${uiSseUnsubscribeFnsRef.current.length} UI SSE subscriptions for chat: ${operationChatId}`);
      uiSseUnsubscribeFnsRef.current.forEach(unsub => unsub());
      uiSseUnsubscribeFnsRef.current = [];
    }
  }, [id, operationChatId]);

  useEffect(() => {
    if (agentState?.dialog_state === 'sas_clarification_needed' && agentState?.clarification_question) {
      setIsInReviewMode(true);
      setReviewContext({
        clarification_question: agentState.clarification_question,
        originalRequest: agentState.current_user_request || data.currentUserRequest || '',
      });
      setInput('');
      setIsEditing(false); 
      setShowAddForm(false);
      cleanupUISseSubscriptions();
    } else if (agentState?.dialog_state === 'sas_awaiting_task_list_review' && agentState?.sas_step1_generated_tasks) {
      setIsInReviewMode(true);
      setReviewContext({
        originalRequest: agentState.current_user_request || data.currentUserRequest || '',
        tasks: agentState.sas_step1_generated_tasks,
        dialog_state: agentState.dialog_state,
      });
      setInput(agentState.current_user_request || data.currentUserRequest || '');
      setIsEditing(false);
      setShowAddForm(false);
      cleanupUISseSubscriptions();
    } else {
      if (!isEditing && !showAddForm && !isInReviewMode) {
        setInput(agentState?.current_user_request || data.currentUserRequest || '');
      }
      if (isInReviewMode && agentState?.dialog_state !== 'sas_clarification_needed' && agentState?.dialog_state !== 'sas_awaiting_task_list_review') {
        setIsInReviewMode(false);
        setReviewContext(null);
      }
    }

    if (!agentState?.current_user_request && !data.currentUserRequest && !isEditing && !isInReviewMode) {
      setShowAddForm(true);
    } else if (agentState?.current_user_request || data.currentUserRequest) {
      setShowAddForm(false);
    }

  }, [agentState, data.currentUserRequest, isEditing, showAddForm, isInReviewMode, cleanupUISseSubscriptions, id]);

  const handleSend = useCallback(async (overrideInput?: string) => {
    const contentToSend = overrideInput !== undefined ? overrideInput : input;
    if (!contentToSend.trim() && overrideInput === undefined) {
      console.warn(`LangGraphInputNode (${id}): Input is empty, not sending.`);
      return;
    }
    if (!operationChatId) {
        console.error(`LangGraphInputNode (${id}): No operationChatId (flowId) available. Cannot send.`);
        setErrorMessage('Error: Flow ID is missing. Cannot process request.');
        return;
    }

    cleanupUISseSubscriptions();

    setIsProcessing(true);
    setStreamingContent('');
    setProcessingStage('Initializing...');
    setErrorMessage(null);
    if (streamingContentRef.current) {
      streamingContentRef.current.scrollTop = streamingContentRef.current.scrollHeight;
    }

    try {
      await updateUserInput(contentToSend);
      console.log(`LangGraphInputNode (${id}): updateUserInput called for chat: ${operationChatId}`);

      const newUnsubs: (() => void)[] = [];

      newUnsubs.push(subscribe(operationChatId, 'token', (eventData) => {
        if (typeof eventData === 'string') {
          setStreamingContent(prev => prev + eventData);
        } else {
          console.warn(`LangGraphInputNode (${id}): Received token event with non-string data:`, eventData);
        }
      }));
      
      newUnsubs.push(subscribe(operationChatId, 'tool_start', (eventData) => {
        if (eventData && typeof eventData === 'object' && eventData.name) {
          setProcessingStage(`Tool Started: ${eventData.name}`);
        } else {
           setProcessingStage('Tool Started');
        }
      }));

      newUnsubs.push(subscribe(operationChatId, 'tool_end', (eventData) => {
         if (eventData && typeof eventData === 'object' && eventData.name) {
          setProcessingStage(`Tool Finished: ${eventData.name}`);
        } else {
           setProcessingStage('Tool Finished');
        }
      }));

      newUnsubs.push(subscribe(operationChatId, 'stream_end', (eventData) => {
        console.log(`LangGraphInputNode (${id}): Received stream_end for UI for chat: ${operationChatId}`);
        setIsProcessing(false);
        setProcessingStage(prev => prev.includes('Error') ? prev : 'Processing Complete');
        cleanupUISseSubscriptions();
      }));

      newUnsubs.push(subscribe(operationChatId, 'connection_error', (errorData) => {
        console.error(`LangGraphInputNode (${id}): SSE Connection Error for chat ${operationChatId}:`, errorData);
        setErrorMessage('Connection error. Please try again.');
        setIsProcessing(false);
        setProcessingStage('Connection Error');
        cleanupUISseSubscriptions();
      }));
      
      newUnsubs.push(subscribe(operationChatId, 'server_error_event', (errorData) => {
        console.error(`LangGraphInputNode (${id}): SSE Server Error Event for chat ${operationChatId}:`, errorData);
        const message = typeof errorData?.message === 'string' ? errorData.message : 'An error occurred during processing.';
        setStreamingContent(prev => prev + `\nError: ${message}`);
        setErrorMessage(message);
        setIsProcessing(false);
        setProcessingStage('Error Occurred');
        cleanupUISseSubscriptions();
      }));

      uiSseUnsubscribeFnsRef.current = newUnsubs;

    } catch (error) {
      console.error(`LangGraphInputNode (${id}): Error calling updateUserInput or setting up UI subscriptions for chat ${operationChatId}:`, error);
      setErrorMessage('Failed to initiate processing. Please check console.');
      setIsProcessing(false);
      setProcessingStage('Failed to Start');
      cleanupUISseSubscriptions();
    }

    setShowAddForm(false);
    setIsEditing(false);
  }, [input, data.flowId, reduxCurrentFlowId, updateUserInput, subscribe, cleanupUISseSubscriptions, id]);

  useEffect(() => {
    if (streamingContentRef.current) {
      streamingContentRef.current.scrollTop = streamingContentRef.current.scrollHeight;
    }
  }, [streamingContent]);

  const handleEdit = () => {
    const currentReq = agentState?.current_user_request || data.currentUserRequest || '';
    setInput(currentReq);
    setIsEditing(true);
    setShowAddForm(false);
    setIsInReviewMode(false);
    setReviewContext(null);
    cleanupUISseSubscriptions(); 
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
  };

  const handleCancel = () => {
    cleanupUISseSubscriptions();
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
    setIsProcessing(false);

    if (isInReviewMode && reviewContext) {
      setInput(reviewContext.originalRequest || '');
    } else if (isEditing) {
      setInput(agentState?.current_user_request || data.currentUserRequest || '');
      setIsEditing(false);
    } else if (showAddForm) {
      setInput('');
      if (agentState?.current_user_request || data.currentUserRequest) {
        setShowAddForm(false);
      }
    } else {
      setInput(agentState?.current_user_request || data.currentUserRequest || '');
    }
  };

  const handleAddNew = () => {
    setInput('');
    setShowAddForm(true);
    setIsEditing(false);
    setIsInReviewMode(false);
    setReviewContext(null);
    cleanupUISseSubscriptions();
    setStreamingContent(''); 
    setProcessingStage('');
    setErrorMessage(null);
  };

  useEffect(() => {
    return () => {
      console.log(`LangGraphInputNode (${id}): Unmounting. Cleaning up UI SSE subscriptions.`);
      cleanupUISseSubscriptions();
    };
  }, [cleanupUISseSubscriptions, id]);

  const stopPropagation = (e: React.WheelEvent | React.MouseEvent) => e.stopPropagation();

  const cardBackgroundColor = selected ? '#1e2a50' : '#2c3e50';
  const inputAreaHeight = isInReviewMode ? 'auto' : (isEditing || showAddForm ? 'auto' : 'auto');
  const taskDisplayHeight = '150px';

  const displayUserRequest = agentState?.current_user_request || data.currentUserRequest;

  return (
    <Card 
      ref={cardRef}
      sx={{ 
        width: 600, 
        minHeight: isInReviewMode || (isEditing || showAddForm) ? 300 : (displayUserRequest ? 200: 150) , 
        maxHeight: '80vh',
        backgroundColor: cardBackgroundColor, 
        border: selected ? '2px solid #76a9fa' : '2px solid #4a5568',
        borderRadius: '8px',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.3s ease',
        boxShadow: selected ? '0 0 15px rgba(118, 169, 250, 0.5)' : '0 4px 8px rgba(0,0,0,0.3)',
        overflow: 'hidden'
      }}
      onWheelCapture={stopPropagation}
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
            {isInReviewMode ? (reviewContext?.clarification_question ? "Clarification Needed" : "Review Generated Tasks") : (data.label || 'User Input')}
          </Typography>
          <Chip 
            label={isProcessing ? "Processing" : (isInReviewMode ? "Review Mode" : (isEditing ? "Editing" : (showAddForm ? "New Task" : "Idle")))}
            size="small" 
            color={isProcessing ? "success" : (isInReviewMode ? "warning" : (isEditing || showAddForm ? "info" : "primary"))}
            variant="outlined"
            icon={isProcessing ? <ProcessingIcon fontSize="small"/> : undefined}
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
          {errorMessage && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1.5, backgroundColor: '#ffebee', color: '#c62828', display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
              <ErrorIcon fontSize="small" />
              <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>{errorMessage}</Typography>
            </Paper>
          )}

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
                {streamingContent || (isProcessing ? 'Waiting for response...' : '')}
              </Typography>
            </Box>
          )}
          {isProcessing && <LinearProgress color="success" sx={{ mb: 1, height: 3, borderRadius: 1.5, flexShrink: 0 }} /> }

          {isInReviewMode && reviewContext && (
            <Box sx={{ mb: 1, flexGrow: 1, overflowY: 'auto' }}>
              {reviewContext.clarification_question && (
                <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#ffc107', mb:0.5}}>Question from Assistant:</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#eee' }}>{reviewContext.clarification_question}</Typography>
                </Paper>
              )}
              {reviewContext.tasks && (
                <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                   <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#ffc107', mb:0.5}}>Proposed Tasks for Review:</Typography>
                   <Box sx={{maxHeight: taskDisplayHeight, overflowY: 'auto'}}>
                    {reviewContext.tasks.map((task, index) => (
                        <Typography key={index} variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#eee', mb: 0.5 }}>
                            {`${index + 1}. ${task.name} (${task.type})`}
                        </Typography>
                    ))}
                   </Box>
                </Paper>
              )}
              <TextField
                fullWidth
                variant="outlined"
                label={reviewContext.clarification_question ? "Your Response / Clarification" : "Revise Task Description (Optional)"}
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
              <Box display="flex" justifyContent="flex-end" gap={1} sx={{ flexShrink: 0 }}>
                {reviewContext.dialog_state === 'sas_awaiting_task_list_review' && (
                    <Button 
                        size="small" variant="contained" color="success"
                        onClick={() => handleSend("accept_tasks")}
                        startIcon={<CheckIcon />} disabled={isProcessing} sx={{ fontSize: '0.8rem'}}
                    >
                        Approve Tasks
                    </Button>
                )}
                <Button 
                  size="small" variant="contained" 
                  onClick={() => handleSend()}
                  startIcon={<SendIcon />} disabled={isProcessing || !input.trim()}
                  sx={{ fontSize: '0.8rem'}}
                >
                  {reviewContext.clarification_question ? 'Send Response' : 'Submit Revised Description'}
                </Button>
              </Box>
            </Box>
          )}

          {!isEditing && !showAddForm && !isInReviewMode && !isProcessing && displayUserRequest && (
            <Box sx={{ overflowY: 'auto', flexGrow: 1, mb:1, border: '1px dashed #444', borderRadius:1, p:1 }} ref={taskDescriptionRef}>
              <Typography variant="caption" sx={{color: '#aaa', fontStyle:'italic', display:'block', mb:0.5}}>Current Task Description:</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#fff', fontSize: '0.9rem', lineHeight: 1.5, wordBreak: 'break-word'}}>
                {displayUserRequest}
              </Typography>
            </Box>
          )}
          {!isEditing && !showAddForm && !isInReviewMode && !isProcessing && displayUserRequest && (
             <Box display="flex" gap={1} sx={{ flexShrink: 0, mt: 'auto' }}>
                <Button size="small" startIcon={<EditIcon />} onClick={handleEdit} variant="outlined" disabled={isProcessing} sx={{ fontSize: '0.8rem'}}>
                  Edit
                </Button>
              </Box>
          )}

          {(isEditing || showAddForm) && !isInReviewMode && !isProcessing && (
            <Box sx={{ height: inputAreaHeight, display: 'flex', flexDirection: 'column', flexGrow:1, overflowY:'auto' }} ref={editTextFieldRef}>
              <TextField
                fullWidth
                variant="outlined"
                label={isEditing ? "Edit Task Description" : "New Task Description"}
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
                {(isEditing || showAddForm) && ( 
                  <Button size="small" onClick={handleCancel} disabled={isProcessing} sx={{ fontSize: '0.8rem'}} variant="outlined">
                    Cancel
                  </Button>
                )}
                <Button 
                  size="small" variant="contained" 
                  onClick={() => handleSend()} 
                  startIcon={isEditing ? <CheckIcon /> : <SendIcon />}
                  disabled={isProcessing || !input.trim()}
                  sx={{ fontSize: '0.8rem'}}
                >
                  {isEditing ? 'Confirm Edit' : 'Send'}
                </Button>
              </Box>
            </Box>
          )}

          {!displayUserRequest && !isEditing && !showAddForm && !isInReviewMode && !isProcessing && (
            <Box textAlign="center" py={3} sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
              <InfoIcon sx={{fontSize: '2rem', color: 'rgba(255, 255, 255, 0.3)', mb:1 }}/>
              <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '0.9rem', mb: 2 }}>
                No task description yet.
              </Typography>
              <Button startIcon={<AddIcon />} onClick={handleAddNew} variant="contained" color="primary" size="medium" sx={{ fontSize: '0.8rem'}}>
                Add Task Description
              </Button>
            </Box>
          )}
        </Box>
      </CardContent>
      <Handle type="source" position={Position.Right} style={{ background: '#555' }} />
    </Card>
  );
}; 