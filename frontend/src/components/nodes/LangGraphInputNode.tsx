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
  InfoOutlined as InfoIcon,
  AccessTime as AccessTimeIcon
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

  // 新增：错误状态检测（优先级最高）
  const isInErrorState = 
    agentState?.is_error === true ||
    agentState?.subgraph_completion_status === 'error';

  // 新增：XML生成确认模式状态判断
  const isInXmlApprovalMode = 
    agentState?.dialog_state === 'sas_awaiting_xml_generation_approval';

  // 新增：处理中状态判断（只有在非错误状态下才显示处理状态）
  const isInProcessingMode = !isInErrorState && (
    agentState?.dialog_state === 'generating_xml_relation' ||
    agentState?.dialog_state === 'generating_xml_final' ||
    agentState?.dialog_state === 'sas_step1_tasks_generated' ||
    agentState?.dialog_state === 'sas_step2_module_steps_generated_for_review' ||
    agentState?.dialog_state === 'sas_generating_individual_xmls' ||
    agentState?.dialog_state === 'sas_module_steps_accepted_proceeding' ||
    agentState?.dialog_state === 'sas_all_steps_accepted_proceed_to_xml');

  // 新增：XML生成完成状态判断
  const isXmlGenerationComplete = !isInErrorState && (
    agentState?.dialog_state === 'sas_step3_completed' ||
    (agentState?.subgraph_completion_status === 'completed_success' && 
     agentState?.final_flow_xml_path));

  // 新增：获取当前处理状态的描述
  const getProcessingDescription = () => {
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
  };

  // 新增：检测处理状态是否可能已超时/卡住
  const isProcessingStuck = useCallback(() => {
    if (!isInProcessingMode || !agentState) return false;
    
    // 如果没有current_step_description或者messages，可能表示处理卡住了
    const hasRecentActivity = agentState.messages && agentState.messages.length > 0;
    const hasStepDescription = agentState.current_step_description;
    
    // 简单的启发式检查：如果处于处理状态但没有最近的活动迹象
    return !hasRecentActivity && !hasStepDescription;
  }, [isInProcessingMode, agentState]);

  // 新增：重置卡住的状态
  const handleResetStuckState = useCallback(async () => {
    if (!operationChatId) return;
    
    try {
      // 调用后端API重置状态
      const response = await fetch(`/flows/${operationChatId}/reset-stuck-state`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        console.log(`Successfully reset stuck state for flow ${operationChatId}`);
        // 触发状态重新获取
        window.location.reload();
      } else {
        console.error('Failed to reset stuck state:', response.statusText);
        setErrorMessage('重置状态失败，请刷新页面重试');
      }
    } catch (error) {
      console.error('Error resetting stuck state:', error);
      setErrorMessage('重置状态时发生错误');
    }
  }, [operationChatId]);

  // 新增：强制完成当前处理步骤
  const handleForceComplete = useCallback(async () => {
    if (!operationChatId) return;
    
    try {
      const response = await fetch(`/flows/${operationChatId}/force-complete-processing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (response.ok) {
        console.log(`Successfully force completed processing for flow ${operationChatId}`);
        window.location.reload();
      } else {
        console.error('Failed to force complete:', response.statusText);
        setErrorMessage('强制完成失败，请刷新页面重试');
      }
    } catch (error) {
      console.error('Error force completing:', error);
      setErrorMessage('强制完成时发生错误');
    }
  }, [operationChatId]);

  // 副作用和状态初始化
  useEffect(() => {
    // 当不处于任何编辑、审查或处理模式时，输入框的内容应该反映后端的状态
    if (!isEditing && !showAddForm && !isInReviewMode && !isInProcessingMode) {
      setInput(agentState?.current_user_request || data.currentUserRequest || '');
    }

    // 当后端没有任务描述时，自动进入添加新任务的模式
    if (!agentState?.current_user_request && !data.currentUserRequest && !isEditing && !isInReviewMode && !isProcessing && !isInProcessingMode) {
      setShowAddForm(true);
    } else if (agentState?.current_user_request || data.currentUserRequest) {
      // 如果有任务了，确保添加表单是关闭的 (除非用户手动点击编辑)
      if (!isEditing && !isInProcessingMode) {
        setShowAddForm(false);
      }
    }
  }, [agentState?.current_user_request, data.currentUserRequest, isEditing, isInReviewMode, isProcessing, isInProcessingMode]);

  // 新增：页面加载时检测可能的卡住状态
  useEffect(() => {
    if (isInProcessingMode && !isProcessing) {
      // 页面加载时发现处于处理状态，但本地没有processing标志
      // 这可能表示页面重新加载，处理状态可能已卡住
      console.warn(`LangGraphInputNode (${id}): Detected processing state on page load for flow ${operationChatId}, dialog_state: ${agentState?.dialog_state}`);
      
      // 可以设置一个定时器，如果一段时间后仍然没有变化，就提示用户
      const stuckCheckTimer = setTimeout(() => {
        if (isInProcessingMode && !isProcessing) {
          console.warn(`LangGraphInputNode (${id}): Processing state appears to be stuck for flow ${operationChatId}`);
          // 这里可以设置一个state来显示警告信息
        }
      }, 30000); // 30秒后检查

      return () => clearTimeout(stuckCheckTimer);
    }
  }, [isInProcessingMode, isProcessing, id, operationChatId, agentState?.dialog_state]);

  const cleanupUISseSubscriptions = useCallback(() => {
    if (uiSseUnsubscribeFnsRef.current.length > 0) {
      console.log(`LangGraphInputNode (${id}): Cleaning up ${uiSseUnsubscribeFnsRef.current.length} UI SSE subscriptions for chat: ${operationChatId}`);
      uiSseUnsubscribeFnsRef.current.forEach(unsub => unsub());
      uiSseUnsubscribeFnsRef.current = [];
    }
  }, [id, operationChatId]);

  // 监听 agentState 变化，当进入审查或处理模式时停止 processing 状态
  useEffect(() => {
    if ((isInReviewMode || isInProcessingMode) && isProcessing) {
      console.log(`LangGraphInputNode (${id}): Agent state changed to ${isInReviewMode ? 'review' : 'processing'} mode (${agentState?.dialog_state}), stopping local processing`);
      setIsProcessing(false);
      cleanupUISseSubscriptions();
    }
  }, [isInReviewMode, isInProcessingMode, isProcessing, agentState?.dialog_state, id, cleanupUISseSubscriptions]);


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
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return; // 防止在处理、完成、错误或XML确认状态时编辑
    
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
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return; // 防止在处理、完成、错误或XML确认状态时取消
    
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
    if (isInProcessingMode || isXmlGenerationComplete || isInErrorState || isInXmlApprovalMode) return; // 防止在处理、完成、错误或XML确认状态时添加新任务
    
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
    if (isInErrorState) {
      return 'Task Error';
    }
    if (isInXmlApprovalMode) {
      return 'Approve XML Generation';
    }
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
    if (isInProcessingMode) {
      return 'Processing Task';
    }
    if (isXmlGenerationComplete) {
      return 'Task Complete';
    }
    return data.label || 'User Input';
  };

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
            label={
              isInErrorState ? "Error" :
              isInXmlApprovalMode ? "Awaiting Approval" :
              isProcessing ? "Processing" : 
              isInReviewMode ? "Review Mode" : 
              isInProcessingMode ? "Processing Task" :
              isXmlGenerationComplete ? "Complete" :
              (isEditing ? "Editing" : (showAddForm ? "New Task" : "Idle"))
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

          {/* 新增：错误状态显示 */}
          {isInErrorState && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1, backgroundColor: '#3d1a1a', border: '1px solid #f44336', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <ErrorIcon sx={{ fontSize: '1rem', color: '#f44336' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#f44336' }}>
                  Task Processing Error
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#ffcdd2', fontSize: '0.85rem', mb: 1 }}>
                {agentState?.error_message || '任务处理过程中发生错误'}
              </Typography>
              <Typography variant="caption" sx={{ color: '#ffab91', fontSize: '0.75rem', display: 'block', mb: 1 }}>
                当前状态: {agentState?.dialog_state}
              </Typography>
              
              <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                <Button
                  size="small"
                  variant="outlined"
                  color="warning"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={() => window.location.reload()}
                >
                  刷新页面
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={handleResetStuckState}
                >
                  重置任务
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  color="warning"
                  sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                  onClick={handleForceComplete}
                >
                  跳过错误
                </Button>
              </Box>
            </Paper>
          )}

          {/* 新增：XML生成确认模式显示 */}
          {isInXmlApprovalMode && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733', border: '1px solid #ff9800', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <AccessTimeIcon sx={{ fontSize: '1rem', color: '#ff9800' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#ff9800' }}>
                  XML Generation Approval Required
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#ffcc80', fontSize: '0.85rem', mb: 1 }}>
                所有任务和模块步骤已确认完成。系统准备生成XML程序文件。
              </Typography>
              
              {/* 显示任务摘要 */}
              {agentState?.sas_step1_generated_tasks && agentState.sas_step1_generated_tasks.length > 0 && (
                <Box sx={{ mb: 1.5, p: 1, backgroundColor: '#0d1117', borderRadius: 1, border: '1px solid #444' }}>
                  <Typography variant="caption" sx={{ color: '#aaa', fontSize: '0.75rem', display: 'block', mb: 0.5 }}>
                    任务配置摘要:
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.8rem' }}>
                    • 已生成 {agentState.sas_step1_generated_tasks.length} 个任务
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.8rem' }}>
                    • 模块步骤已定义并确认
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#eee', fontSize: '0.8rem' }}>
                    • 准备生成可执行的XML程序文件
                  </Typography>
                </Box>
              )}

              {/* 显示确认问题 */}
              {agentState?.clarification_question && (
                <Box sx={{ mb: 1.5, p: 1, backgroundColor: '#2c1810', borderRadius: 1, border: '1px solid #ff9800' }}>
                  <Typography variant="body2" sx={{ color: '#ffcc80', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>
                    {agentState.clarification_question}
                  </Typography>
                </Box>
              )}

              {/* 确认按钮 */}
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
                  批准生成XML
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  sx={{ fontSize: '0.75rem', minHeight: '28px' }}
                  onClick={() => handleSend('reset')}
                  disabled={isProcessing}
                >
                  重置任务
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="warning"
                  sx={{ fontSize: '0.75rem', minHeight: '28px' }}
                  onClick={() => window.location.reload()}
                >
                  刷新页面
                </Button>
              </Box>
            </Paper>
          )}

          {/* 新增：处理状态显示 */}
          {isInProcessingMode && !isProcessing && (
            <Paper elevation={1} sx={{ p: 1.5, mb: 1, backgroundColor: '#1c2733', border: '1px solid #2196f3', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <ProcessingIcon sx={{ fontSize: '1rem', color: '#2196f3', animation: 'spin 2s linear infinite' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#2196f3' }}>
                  Task Processing
                </Typography>
                {isProcessingStuck() && (
                  <Chip 
                    label="可能卡住"
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
              
              {/* 新增：卡住状态时的恢复选项 */}
              {isProcessingStuck() && (
                <Box sx={{ mt: 1.5, p: 1, backgroundColor: '#2c1810', borderRadius: 1, border: '1px solid #ff9800' }}>
                  <Typography variant="caption" sx={{ color: '#ffb74d', fontSize: '0.75rem', display: 'block', mb: 1 }}>
                    检测到处理可能已卡住。如果长时间没有进展，您可以尝试以下操作：
                  </Typography>
                  <Box display="flex" gap={1} flexWrap="wrap">
                    <Button
                      size="small"
                      variant="outlined"
                      color="warning"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={() => window.location.reload()}
                    >
                      刷新页面
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="error"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={handleResetStuckState}
                    >
                      重置状态
                    </Button>
                    <Button
                      size="small"
                      variant="contained"
                      color="warning"
                      sx={{ fontSize: '0.7rem', minHeight: '24px' }}
                      onClick={handleForceComplete}
                    >
                      强制完成
                    </Button>
                  </Box>
                </Box>
              )}
            </Paper>
          )}

          {/* 新增：XML生成完成提示 */}
          {isXmlGenerationComplete && (
            <Paper elevation={2} sx={{ p: 1.5, mb: 1, backgroundColor: '#1b5e20', color: '#c8e6c9', border: '1px solid #4caf50', flexShrink: 0 }}>
              <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                <CheckIcon sx={{ fontSize: '1rem', color: '#4caf50' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                  Task Completed Successfully
                </Typography>
              </Box>
              <Typography variant="body2" sx={{ color: '#c8e6c9', fontSize: '0.85rem', mb: 1 }}>
                XML文件已成功生成并保存。您的任务处理已完成。
              </Typography>
              {agentState?.final_flow_xml_path && (
                <Typography variant="caption" sx={{ color: '#a5d6a7', fontSize: '0.75rem', fontFamily: 'monospace', display: 'block', mb: 1 }}>
                  文件路径: {agentState.final_flow_xml_path}
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
                    // 这里可以添加查看XML文件的逻辑
                    console.log('View XML file:', agentState?.final_flow_xml_path);
                  }}
                >
                  查看结果
                </Button>
                <Button 
                  size="small" 
                  variant="contained" 
                  color="primary"
                  sx={{ fontSize: '0.8rem' }}
                  onClick={() => {
                    // 重新开始的逻辑 - 可以触发状态重置
                    setShowAddForm(true);
                    setIsEditing(false);
                    setInput('');
                  }}
                >
                  创建新任务
                </Button>
              </Box>
            </Paper>
          )}

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

          {!isEditing && !showAddForm && !isInReviewMode && !isProcessing && !isInProcessingMode && displayUserRequest && (
            <Box sx={{ overflowY: 'auto', flexGrow: 1, mb:1, border: '1px dashed #444', borderRadius:1, p:1 }} ref={taskDescriptionRef}>
              <Typography variant="caption" sx={{color: '#aaa', fontStyle:'italic', display:'block', mb:0.5}}>Current Task Description:</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#fff', fontSize: '0.9rem', lineHeight: 1.5, wordBreak: 'break-word'}}>
                {displayUserRequest}
              </Typography>
            </Box>
          )}
          {!isEditing && !showAddForm && !isInReviewMode && !isProcessing && !isInProcessingMode && !isXmlGenerationComplete && displayUserRequest && (
             <Box display="flex" gap={1} sx={{ flexShrink: 0, mt: 'auto' }}>
                <Button size="small" startIcon={<EditIcon />} onClick={handleEdit} variant="outlined" disabled={isProcessing || isInProcessingMode} sx={{ fontSize: '0.8rem'}}>
                  Edit
                </Button>
              </Box>
          )}

          {(isEditing || showAddForm) && !isInReviewMode && !isProcessing && !isInProcessingMode && (
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

          {!displayUserRequest && !isEditing && !showAddForm && !isInReviewMode && !isProcessing && !isInProcessingMode && (
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