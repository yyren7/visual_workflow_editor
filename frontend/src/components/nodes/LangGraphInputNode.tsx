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

// 为 sas_step1_generated_tasks 中的任务对象定义类型
interface Task {
  name: string;
  type: string;
  // 可以根据需要添加其他字段，如 description, sub_tasks
}

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
  
  const { updateUserInput } = useAgentStateSync();
  const { subscribe } = useSSEManager();
  const agentState = useSelector(selectAgentState);
  const reduxCurrentFlowId = useSelector(selectCurrentFlowId);

  const operationChatId = data.flowId || reduxCurrentFlowId;

  // --- 派生状态 (Derived State) ---
  // 直接从 agentState 计算出当前是否处于审查模式
  const isInReviewMode = 
    agentState?.dialog_state === 'sas_awaiting_task_list_review' ||
    agentState?.dialog_state === 'sas_awaiting_module_steps_review' ||
    agentState?.dialog_state === 'sas_awaiting_task_list_revision_input' ||
    agentState?.dialog_state === 'sas_awaiting_module_steps_revision_input';

  // 副作用和状态初始化
  useEffect(() => {
    // 当不处于任何编辑或审查模式时，输入框的内容应该反映后端的状态
    if (!isEditing && !showAddForm && !isInReviewMode) {
      setInput(agentState?.current_user_request || data.currentUserRequest || '');
    }

    // 当后端没有任务描述时，自动进入添加新任务的模式
    if (!agentState?.current_user_request && !data.currentUserRequest && !isEditing && !isInReviewMode && !isProcessing) {
      setShowAddForm(true);
    } else if (agentState?.current_user_request || data.currentUserRequest) {
      // 如果有任务了，确保添加表单是关闭的 (除非用户手动点击编辑)
      if (!isEditing) {
        setShowAddForm(false);
      }
    }
  }, [agentState?.current_user_request, data.currentUserRequest, isEditing, isInReviewMode, isProcessing]);

  const cleanupUISseSubscriptions = useCallback(() => {
    if (uiSseUnsubscribeFnsRef.current.length > 0) {
      console.log(`LangGraphInputNode (${id}): Cleaning up ${uiSseUnsubscribeFnsRef.current.length} UI SSE subscriptions for chat: ${operationChatId}`);
      uiSseUnsubscribeFnsRef.current.forEach(unsub => unsub());
      uiSseUnsubscribeFnsRef.current = [];
    }
  }, [id, operationChatId]);

  // 监听 agentState 变化，当进入审查模式时停止 processing 状态
  useEffect(() => {
    if (isInReviewMode && isProcessing) {
      console.log(`LangGraphInputNode (${id}): Agent state changed to review mode (${agentState?.dialog_state}), stopping processing`);
      setIsProcessing(false);
      cleanupUISseSubscriptions();
    }
  }, [isInReviewMode, isProcessing, agentState?.dialog_state, id, cleanupUISseSubscriptions]);


  const handleSend = useCallback(async (overrideInput?: string) => {
    // 在发送时，如果处于审查模式，确保输入框内容被一并发送
    // 如果用户只点击"Approve"，overrideInput 会是 'accept_tasks'，input 会被忽略
    // 如果用户输入了修改意见并点击"Submit"，overrideInput 是 undefined, input 的内容会被发送
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

    console.log(`LangGraphInputNode (${id}): handleSend: Attempting to process with content: "${String(contentToSend).substring(0,30)}..." for operationChatId: ${operationChatId}`);

    try {
      // 这里的 updateUserInput 将会触发整个 LangGraph 流程
      await updateUserInput(contentToSend);
      console.log(`LangGraphInputNode (${id}): handleSend: updateUserInput call completed successfully for ${operationChatId}.`);

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
        console.log(`LangGraphInputNode (${id}): handleSend: UI received stream_end for chat: ${operationChatId}`);
        setProcessingStage(prev => prev.includes('Error') ? prev : 'Processing Complete');
      }));

      newUnsubs.push(subscribe(operationChatId, 'agent_state_updated', (eventData) => {
        console.log(`LangGraphInputNode (${id}): handleSend: UI received agent_state_updated for chat: ${operationChatId}`, eventData);
        // Note: Processing state will be managed by the useEffect that monitors isInReviewMode
      }));

      newUnsubs.push(subscribe(operationChatId, 'connection_error', (errorData) => {
        console.error(`LangGraphInputNode (${id}): handleSend: UI SSE Connection Error for chat ${operationChatId}:`, errorData);
        setErrorMessage('Connection error with UI event stream. Please try again.');
        setIsProcessing(false);
        setProcessingStage('UI Stream Connection Error');
        cleanupUISseSubscriptions();
      }));
      
      newUnsubs.push(subscribe(operationChatId, 'server_error_event', (errorData) => {
        console.error(`LangGraphInputNode (${id}): handleSend: UI SSE Server Error Event for chat ${operationChatId}:`, errorData);
        const message = typeof errorData?.message === 'string' ? errorData.message : 'An error occurred in UI event stream.';
        setStreamingContent(prev => prev + `\nStream Error: ${message}`);
        setErrorMessage(message);
        setIsProcessing(false);
        setProcessingStage('UI Stream Server Error');
        cleanupUISseSubscriptions();
      }));

      uiSseUnsubscribeFnsRef.current = newUnsubs;

    } catch (error) {
      console.error(`LangGraphInputNode (${id}): handleSend: SUCCESSFULLY CAUGHT ERROR from updateUserInput for ${operationChatId}:`, error);
      requestAnimationFrame(() => {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to initiate processing. Please check console.');
        setIsProcessing(false);
        setProcessingStage('Failed to Start or Error During Processing');
      });
    }

    // 成功发起后，重置编辑状态
    setShowAddForm(false);
    setIsEditing(false);
  }, [input, operationChatId, updateUserInput, subscribe, cleanupUISseSubscriptions, id]);

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

    setIsEditing(false);
    // 如果之前没有任务描述，取消后应该回到 "Add Task" 状态
    if (!agentState?.current_user_request && !data.currentUserRequest) {
      setShowAddForm(true);
    } else {
      setShowAddForm(false);
    }
  };

  const handleAddNew = () => {
    setInput('');
    setShowAddForm(true);
    setIsEditing(false);
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

  // 根据审查模式确定标题
  const cardTitle = () => {
    if (isInReviewMode) {
      switch (agentState.dialog_state) {
        case 'sas_awaiting_task_list_review':
          return 'Review Generated Tasks';
        case 'sas_awaiting_task_list_revision_input':
          return 'Provide Revised Description';
        case 'sas_awaiting_module_steps_review':
        case 'sas_awaiting_module_steps_revision_input':
          return 'Review Module Steps';
        default:
          return 'Review Mode';
      }
    }
    return data.label || 'User Input';
  };

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
            {cardTitle()}
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

          {isInReviewMode && agentState && (
            <Box sx={{ mb: 1, flexGrow: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
              {/* Top part for displaying information */}
              <Box sx={{ flexShrink: 0 }}>
                {/* Display clarification question or instruction */}
                <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#ffc107', mb:0.5}}>
                    {agentState.dialog_state === 'sas_awaiting_task_list_revision_input' 
                      ? 'Assistant requires a revised description:' 
                      : 'Assistant Needs Your Input:'}
                  </Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#eee' }}>
                    {agentState.clarification_question || 'Please review the generated tasks below and approve or provide feedback.'}
                  </Typography>
                </Paper>

                {/* Display tasks only in task list review state */}
                {agentState.dialog_state === 'sas_awaiting_task_list_review' && agentState.sas_step1_generated_tasks && (
                  <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733'}}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#90caf9', mb:0.5}}>Proposed Tasks for Review:</Typography>
                    <Box sx={{maxHeight: taskDisplayHeight, overflowY: 'auto'}}>
                      {agentState.sas_step1_generated_tasks.map((task: Task, index: number) => (
                          <Typography key={index} variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#eee', mb: 0.5, fontSize: '0.8rem' }}>
                              {`${index + 1}. ${task.name} (${task.type})`}
                          </Typography>
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
                      ? "Provide feedback or modifications (optional)" 
                      : "Your Response / Revised Description"
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
                          Approve Tasks
                      </Button>
                  )}
                  <Button 
                    size="small" variant="contained" 
                    onClick={() => handleSend()}
                    startIcon={<SendIcon />} 
                    disabled={isProcessing || (agentState.dialog_state !== 'sas_awaiting_task_list_review' && !input.trim())}
                    sx={{ fontSize: '0.8rem'}}
                  >
                    {agentState.dialog_state === 'sas_awaiting_task_list_review' ? 'Submit Feedback' : 'Send Response'}
                  </Button>
                </Box>
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