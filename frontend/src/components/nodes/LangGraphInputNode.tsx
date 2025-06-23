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
  AutoFixHigh as ProcessingIcon
} from '@mui/icons-material';
import { useAgentStateSync } from '../../hooks/useAgentStateSync';
import { useSSEManager } from '../../hooks/useSSEManager';

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

export const LangGraphInputNode: React.FC<LangGraphInputNodeProps> = ({ id, data, selected }) => {
  const [input, setInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  
  // 新增：流式输出相关状态
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [processingStage, setProcessingStage] = useState('');
  const streamingContentRef = useRef<HTMLDivElement>(null);
  const currentChatIdRef = useRef<string | null>(null);
  
  // 新增：滚动区域的refs
  const taskDescriptionRef = useRef<HTMLDivElement>(null);
  const editTextFieldRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  
  const { updateUserInput } = useAgentStateSync();
  const { createConnection, closeConnection } = useSSEManager();

  // 初始化状态
  useEffect(() => {
    if (data.currentUserRequest) {
      setInput(data.currentUserRequest);
    } else {
      // 如果没有现有的用户请求，默认显示添加表单
      setShowAddForm(true);
    }
  }, [data.currentUserRequest]);

  // 新增：启动SSE监听流式输出的函数
  const startStreamListener = useCallback((chatId: string) => {
    // 清理之前的连接
    if (currentChatIdRef.current) {
      closeConnection(currentChatIdRef.current);
    }

    console.log('LangGraphInputNode: 开始监听流式输出，chatId:', chatId);
    
    setIsProcessing(true);
    setStreamingContent('');
    setProcessingStage('正在连接...');
    
    currentChatIdRef.current = chatId;

    // 使用统一的SSE管理器创建连接
    const cleanup = createConnection(
      chatId,
      (event) => {
        console.log('LangGraphInputNode: 收到SSE事件:', event.type);
        
        switch (event.type) {
          case 'token':
            setStreamingContent(prev => prev + event.data);
            setProcessingStage('正在生成任务列表...');
            // 自动滚动到底部
            setTimeout(() => {
              if (streamingContentRef.current) {
                streamingContentRef.current.scrollTop = streamingContentRef.current.scrollHeight;
              }
            }, 50);
            break;
            
          case 'tool_start':
            setProcessingStage(`正在执行: ${event.data.name || '工具处理'}...`);
            break;
            
          case 'tool_end':
            setProcessingStage('正在生成任务列表...');
            break;
            
          case 'stream_end':
            setIsProcessing(false);
            setProcessingStage('');
            currentChatIdRef.current = null;
            // 3秒后清除流式内容
            setTimeout(() => {
              setStreamingContent('');
            }, 3000);
            break;
            
          case 'error':
            console.error('LangGraphInputNode: SSE错误:', event.data);
            setProcessingStage('处理出错');
            break;
        }
      },
      (error) => {
        console.error('LangGraphInputNode: SSE连接错误:', error);
        setIsProcessing(false);
        setProcessingStage('连接失败');
        setStreamingContent(prev => prev + '\n\n[连接失败，请重试]');
        currentChatIdRef.current = null;
      },
      () => {
        console.log('LangGraphInputNode: SSE连接已关闭');
        setIsProcessing(false);
        setProcessingStage('');
        currentChatIdRef.current = null;
      }
    );

    return cleanup;
  }, [createConnection, closeConnection]);

  // 清理SSE连接
  useEffect(() => {
    return () => {
      console.log('LangGraphInputNode组件卸载，清理SSE连接');
      if (currentChatIdRef.current) {
        closeConnection(currentChatIdRef.current);
        currentChatIdRef.current = null;
      }
      setIsProcessing(false);
      setStreamingContent('');
      setProcessingStage('');
    };
  }, [closeConnection]);

  // 新增：原生DOM事件处理滚轮事件
  useEffect(() => {
    const handleNativeWheel = (e: Event) => {
      const wheelEvent = e as WheelEvent;
      // 只阻止事件传播到ReactFlow，但保留元素的滚动功能
      wheelEvent.stopPropagation();
      console.log('滚轮事件传播被阻止，但保留滚动功能:', wheelEvent.target);
    };

    // 为所有滚动区域添加原生事件监听
    const refs = [streamingContentRef, taskDescriptionRef, editTextFieldRef];
    
    refs.forEach(ref => {
      if (ref.current) {
        // 直接对滚动元素添加事件监听
        const element = ref.current;
        // 查找实际的滚动元素（可能是textarea或子元素）
        const scrollableElement = element.querySelector('textarea') || element;
        
        scrollableElement.addEventListener('wheel', handleNativeWheel, { passive: true });
        console.log('为元素添加滚轮事件监听:', scrollableElement);
      }
    });

    return () => {
      refs.forEach(ref => {
        if (ref.current) {
          const element = ref.current;
          const scrollableElement = element.querySelector('textarea') || element;
          scrollableElement.removeEventListener('wheel', handleNativeWheel);
        }
      });
    };
  }, [isEditing, showAddForm, isProcessing]); // 依赖状态变化重新绑定事件

  const handleSubmit = useCallback(() => {
    if (!input.trim()) return;
    
    // 确保清理之前的连接
    if (currentChatIdRef.current) {
      console.log('清理之前的SSE连接');
      closeConnection(currentChatIdRef.current);
      currentChatIdRef.current = null;
    }
    
    // 使用flowId作为虚拟chatId启动流式监听
    const virtualChatId = data.flowId;
    console.log('开始新的SSE连接，chatId:', virtualChatId);
    startStreamListener(virtualChatId);
    
    updateUserInput(input);
    setIsEditing(false);
    setShowAddForm(false);
  }, [input, updateUserInput, data.flowId, startStreamListener, closeConnection]);

  const handleEdit = useCallback(() => {
    setInput(data.currentUserRequest || '');
    setIsEditing(true);
    setShowAddForm(false);
  }, [data.currentUserRequest]);

  const handleCancel = useCallback(() => {
    setInput(data.currentUserRequest || '');
    setIsEditing(false);
    setShowAddForm(false);
  }, [data.currentUserRequest]);

  const handleAddNew = useCallback(() => {
    setInput('');
    setShowAddForm(true);
    setIsEditing(false);
  }, []);

  return (
    <>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ 
          background: '#ff9800',
          width: '12px',
          height: '12px',
          bottom: '-6px',
          border: '2px solid #f57c00',
          transition: 'all 0.2s ease',
          borderRadius: '6px'
        }}
      />
      <Card 
        ref={cardRef}
        sx={{ 
          width: 600, // 固定宽度
          height: 400, // 固定高度
          border: '1px solid #555',
          borderRadius: '8px',
          boxShadow: selected ? '0 0 0 2px #1976d2, 0 2px 8px rgba(25, 118, 210, 0.4)' : '0 2px 5px rgba(0, 0, 0, 0.2)',
          backgroundColor: selected ? 'rgba(25, 118, 210, 0.08)' : 'rgba(45, 45, 45, 1)',
          transition: 'all 0.3s ease',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden', // 防止整个Card溢出
          // 移除transform缩放，始终保持正常大小
          '&:hover': {
            boxShadow: selected 
              ? '0 0 0 2px #1976d2, 0 4px 10px rgba(25, 118, 210, 0.5)'
              : '0 0 0 2px #1976d2, 0 4px 8px rgba(0, 0, 0, 0.3)',
            backgroundColor: selected 
              ? 'rgba(25, 118, 210, 0.12)'
              : 'rgba(45, 45, 45, 1)',
            border: '1px solid transparent',
            // 移除hover时的缩放
          }
        }}
        // 移除onWheel处理，使用原生事件监听
      >
        <CardContent sx={{ 
          p: 2, 
          transition: 'all 0.3s ease',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}> 
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} sx={{ flexShrink: 0 }}> {/* 标题栏不收缩 */}
            <Typography 
              variant="h6"
              sx={{ 
                fontSize: '1rem', // 固定字体大小
                fontWeight: 'bold',
                color: selected ? '#fff' : '#eee',
                transition: 'all 0.3s ease'
              }}
            >
              {data.label || '机器人任务描述'}
            </Typography>
            <Chip 
              label={isProcessing ? "处理中" : "用户输入"} 
              size="small" 
              color={isProcessing ? "success" : "primary"}
              variant="outlined"
              icon={isProcessing ? <ProcessingIcon /> : undefined}
              sx={{ 
                fontSize: '0.7rem',
                height: '20px',
                '& .MuiChip-label': { px: 1 }
              }}
            />
          </Box>
          
          {/* 内容区域 - 移除整体滚动，让各个组件自己处理滚动 */}
          <Box sx={{ 
            mt: 1, 
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden', // 防止溢出，但不添加滚动条
          }}>
            {/* 流式输出显示区域 */}
            {isProcessing && (
              <Box sx={{ mb: 2, flexShrink: 0 }}> {/* 添加flexShrink: 0确保不被压缩 */}
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <ProcessingIcon sx={{ fontSize: '1rem', color: '#4caf50' }} />
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      color: '#4caf50', 
                      fontSize: '0.8rem',
                      fontWeight: 'bold'
                    }}
                  >
                    {processingStage || '正在处理...'}
                  </Typography>
                </Box>
                <LinearProgress 
                  color="success" 
                  sx={{ 
                    mb: 1,
                    height: 3,
                    borderRadius: 1.5
                  }} 
                />
                {streamingContent && (
                  <Paper 
                    ref={streamingContentRef}
                    // 移除onWheel处理，使用原生事件监听
                    sx={{ 
                      p: 1.5, 
                      bgcolor: 'rgba(76, 175, 80, 0.1)', 
                      borderRadius: 1,
                      border: '1px solid rgba(76, 175, 80, 0.3)',
                      height: '120px', // 固定合适的高度
                      maxHeight: '120px', // 确保不会超出
                      overflowY: 'auto', // 流式内容区域的滚动条
                      overflowX: 'hidden',
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      color: '#e8f5e8',
                      // 自定义滚动条样式
                      '&::-webkit-scrollbar': {
                        width: '6px',
                      },
                      '&::-webkit-scrollbar-track': {
                        background: 'rgba(255, 255, 255, 0.1)',
                        borderRadius: '3px',
                      },
                      '&::-webkit-scrollbar-thumb': {
                        background: 'rgba(255, 255, 255, 0.3)',
                        borderRadius: '3px',
                        '&:hover': {
                          background: 'rgba(255, 255, 255, 0.5)',
                        },
                      },
                    }}
                  >
                    <Typography 
                      variant="body2" 
                      component="div"
                      sx={{ 
                        fontSize: '0.75rem',
                        lineHeight: 1.4,
                        color: 'inherit'
                      }}
                    >
                      {streamingContent}
                    </Typography>
                  </Paper>
                )}
              </Box>
            )}

            {/* 显示现有的用户请求 */}
            {data.currentUserRequest && !isEditing && !showAddForm && (
              <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.7)', 
                    fontSize: '0.9rem',
                    mb: 1,
                    flexShrink: 0 // 标签不收缩
                  }}
                >
                  当前任务描述：
                </Typography>
                <Box 
                  ref={taskDescriptionRef}
                  // 移除onWheel处理，使用原生事件监听
                  sx={{ 
                    p: 2, 
                    bgcolor: 'rgba(33, 150, 243, 0.1)', 
                    borderRadius: 1, 
                    mb: 2,
                    border: '1px solid rgba(33, 150, 243, 0.3)',
                    flexGrow: 1, // 占据剩余空间
                    minHeight: '120px', // 设置最小高度
                    maxHeight: '200px', // 设置最大高度，确保按钮可见
                    overflowY: 'auto', // 任务描述显示区域的滚动条
                    overflowX: 'hidden',
                    // 自定义滚动条样式
                    '&::-webkit-scrollbar': {
                      width: '6px',
                    },
                    '&::-webkit-scrollbar-track': {
                      background: 'rgba(255, 255, 255, 0.1)',
                      borderRadius: '3px',
                    },
                    '&::-webkit-scrollbar-thumb': {
                      background: 'rgba(255, 255, 255, 0.3)',
                      borderRadius: '3px',
                      '&:hover': {
                        background: 'rgba(255, 255, 255, 0.5)',
                      },
                    },
                  }}
                >
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      whiteSpace: 'pre-wrap',
                      color: '#fff',
                      fontSize: '0.9rem',
                      lineHeight: 1.5,
                      wordBreak: 'break-word', // 添加自动换行
                    }}
                  >
                    {data.currentUserRequest}
                  </Typography>
                </Box>
                <Box display="flex" gap={1} sx={{ flexShrink: 0 }}>
                  <Button 
                    size="small" 
                    startIcon={<EditIcon />}
                    onClick={handleEdit}
                    variant="outlined"
                    disabled={isProcessing}
                    sx={{ fontSize: '0.8rem', py: 0.8, px: 2 }}
                  >
                    修改
                  </Button>
                  {/* 移除新建按钮 */}
                </Box>
              </Box>
            )}

            {/* 编辑/新建表单 */}
            {(isEditing || showAddForm) && !isProcessing && (
              <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.7)', 
                    fontSize: '0.9rem',
                    mb: 1,
                    flexShrink: 0
                  }}
                >
                  {isEditing ? '修改任务描述：' : '输入机器人任务描述：'}
                </Typography>
                <TextField
                  ref={editTextFieldRef}
                  fullWidth
                  multiline
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="请详细描述机器人任务..."
                  // 移除onWheel处理，使用原生事件监听
                  sx={{ 
                    mb: 2,
                    flexGrow: 1, // 占据剩余空间
                    minHeight: '120px', // 设置最小高度
                    maxHeight: '200px', // 设置最大高度，确保按钮可见
                    '& .MuiOutlinedInput-root': {
                      fontSize: '0.9rem',
                      height: '100%', // 占满父容器
                      '& textarea': {
                        height: '100% !important', // 文本区域占满
                        overflow: 'auto !important', // 文本框的滚动条
                        resize: 'none', // 禁止手动调整大小
                      }
                    }
                  }}
                  autoFocus
                />
                <Box display="flex" gap={1} justifyContent="flex-end" sx={{ flexShrink: 0 }}>
                  <Button 
                    size="small"
                    startIcon={<CloseIcon />}
                    onClick={handleCancel}
                    variant="outlined"
                    sx={{ fontSize: '0.8rem', py: 0.8, px: 2 }}
                  >
                    取消
                  </Button>
                  <Button 
                    size="small"
                    startIcon={<CheckIcon />}
                    onClick={handleSubmit}
                    disabled={!input.trim()}
                    variant="contained"
                    color="primary"
                    sx={{ fontSize: '0.8rem', py: 0.8, px: 2 }}
                  >
                    {isEditing ? '更新' : '提交'}
                  </Button>
                </Box>
              </Box>
            )}

            {/* 空状态 - 当没有任何内容时显示 */}
            {!data.currentUserRequest && !isEditing && !showAddForm && !isProcessing && (
              <Box textAlign="center" py={3} sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.5)', 
                    fontSize: '0.9rem',
                    mb: 2 
                  }}
                >
                  还没有任务描述
                </Typography>
                <Button 
                  startIcon={<AddIcon />}
                  onClick={handleAddNew}
                  variant="contained"
                  color="primary"
                  size="medium"
                  sx={{ fontSize: '0.8rem', py: 1, px: 3 }}
                >
                  添加任务描述
                </Button>
              </Box>
            )}

            {/* 处理状态显示 */}
            {!data.currentUserRequest && isProcessing && (
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.5)',
                    fontSize: '0.9rem',
                    fontStyle: 'italic',
                    textAlign: 'center'
                  }}
                >
                  正在处理...
                </Typography>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>
    </>
  );
}; 