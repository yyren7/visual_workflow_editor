import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Handle, Position } from 'reactflow';
import { 
  Card, 
  CardContent, 
  TextField, 
  Typography, 
  Box, 
  IconButton,
  Chip,
  CircularProgress
} from '@mui/material';
import { 
  Edit as EditIcon, 
  Check as CheckIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { useSelector } from 'react-redux';
import { useAgentStateSync } from '../../hooks/useAgentStateSync';
import { useSSEManager } from '../../hooks/useSSEManager';
import { selectActiveLangGraphStreamFlowId } from '../../store/slices/flowSlice';

interface TaskDefinition {
  name: string;
  type: string;
  description?: string;
  sub_tasks?: string[];
}

interface LangGraphTaskNodeData {
  label: string;
  flowId: string;
  taskIndex: number;
  task: TaskDefinition;
}

interface LangGraphTaskNodeProps {
  id: string;
  data: LangGraphTaskNodeData;
  selected: boolean;
}

// =================================================================================
// TODO (未来功能): 单个任务的详情更新流程
//
// 当前组件只在用户点击"编辑"时，在本地 state 中修改任务的元数据（名称，类型等）。
// 未来的增强方向是：
// 1. 在卡片上提供一个 "Regenerate Details" 或 "Update Details" 按钮。
// 2. 当用户修改了任务的描述（description）并点击该按钮时，触发一个新的工作流。
// 3. 这个工作流将使用 `useAgentStateSync` 中的一个新函数（例如 `regenerateDetailsForTask`）。
// 4. 该函数会向后端发送一个特定的请求，其中包含 `taskIndex` 和修改后的任务描述。
// 5. 后端接收到后，会进入 `sas_awaiting_module_steps_revision_input` 状态，
//    并只针对这一个任务重新运行 "process_description_to_module_steps" 节点。
// 6. 这个节点在运行时，会通过 SSE 推送 `task_detail_generation_start` 和 `task_detail_generation_end` 事件，
//    当前的 SSE 监听逻辑可以被复用，来显示加载状态。
// =================================================================================

export const LangGraphTaskNode: React.FC<LangGraphTaskNodeProps> = ({ id, data, selected }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedTask, setEditedTask] = useState<TaskDefinition>(data.task);
  const { updateTask } = useAgentStateSync();
  const { subscribe } = useSSEManager();
  const activeStreamingFlowId = useSelector(selectActiveLangGraphStreamFlowId);

  const [isProcessingDetail, setIsProcessingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const taskContentRef = useRef<HTMLDivElement>(null);
  const editFormRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleNativeWheel = (e: Event) => {
      const wheelEvent = e as WheelEvent;
      wheelEvent.stopPropagation();
      // console.log('TaskNode滚轮事件传播被阻止:', wheelEvent.target); // 可以取消注释以调试
    };

    const refs = [taskContentRef, editFormRef];
    
    refs.forEach(ref => {
      if (ref.current) {
        const element = ref.current;
        const textareas = element.querySelectorAll('textarea');
        const scrollableElement = element;
        
        scrollableElement.addEventListener('wheel', handleNativeWheel, { passive: true });
        textareas.forEach(textarea => {
          textarea.addEventListener('wheel', handleNativeWheel, { passive: true });
        });
      }
    });

    return () => {
      refs.forEach(ref => {
        if (ref.current) {
          const element = ref.current;
          const textareas = element.querySelectorAll('textarea');
          const scrollableElement = element;
          
          scrollableElement.removeEventListener('wheel', handleNativeWheel);
          textareas.forEach(textarea => {
            textarea.removeEventListener('wheel', handleNativeWheel);
          });
        }
      });
    };
  }, [isEditing, selected]);

  // 新的 SSE 订阅逻辑
  useEffect(() => {
    if (activeStreamingFlowId !== data.flowId) {
      console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Skipping SSE for task details. Active stream ID ('${activeStreamingFlowId}') !== Node's flowId ('${data.flowId}'). Node expects to listen on its base flow's main stream.`);
      return; 
    }

    const sseChatIdForTaskDetails = data.flowId; 
    console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Subscribing to detail events on main flow SSE stream: ${sseChatIdForTaskDetails}`);

    const unsubs: (() => void)[] = [];

    unsubs.push(subscribe(sseChatIdForTaskDetails, 'task_detail_generation_start', (eventData: any) => {
      console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Received task_detail_generation_start on ${sseChatIdForTaskDetails}`, eventData);
      if (eventData && eventData.taskIndex === data.taskIndex) {
        setIsProcessingDetail(true);
        setDetailError(null);
        console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Detail processing STARTED.`);
      }
    }));

    unsubs.push(subscribe(sseChatIdForTaskDetails, 'task_detail_generation_end', (eventData: any) => {
      console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Received task_detail_generation_end on ${sseChatIdForTaskDetails}`, eventData);
      if (eventData && eventData.taskIndex === data.taskIndex) {
        setIsProcessingDetail(false);
        if (eventData.status === 'failure') {
          setDetailError(eventData.error_message || 'Failed to generate details.');
          console.error(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Detail processing FAILED:`, eventData.error_message);
        } else {
          setDetailError(null);
          console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Detail processing ENDED successfully.`);
          // 如果后端在task_detail_generation_end事件中发送了详情数据，可以在这里更新
          // 例如: if (eventData.details) dispatch(updateTaskDetailsInRedux(data.taskIndex, eventData.details));
        }
      }
    }));

    return () => {
      console.log(`LangGraphTaskNode (${id}, TaskIndex: ${data.taskIndex}): Unsubscribing from detail events on sseChatId: ${sseChatIdForTaskDetails}`);
      unsubs.forEach(unsub => unsub());
    };
  }, [data.flowId, data.taskIndex, id, subscribe, activeStreamingFlowId]); // 依赖项

  const handleEdit = useCallback(() => {
    if (isProcessingDetail) return;
    setIsEditing(true);
  }, [isProcessingDetail]);

  const handleSave = useCallback(() => {
    updateTask(data.taskIndex, editedTask);
    setIsEditing(false);
  }, [data.taskIndex, editedTask, updateTask]);

  // TODO: 未来实现单个任务详情更新时，将使用此函数
  const handleRegenerateDetails = useCallback(() => {
    // 1. 从 editedTask state 中获取修改后的任务描述
    const updatedDescription = editedTask.description;
    console.log(`TODO: Regenerate details for task ${data.taskIndex} with new description:`, updatedDescription);

    // 2. 调用一个新的来自 useAgentStateSync 的 hook 函数
    //    例如: regenerateDetailsForTask(data.taskIndex, updatedDescription);

    // 3. UI 进入 isProcessingDetail 状态
    setIsProcessingDetail(true);

  }, [data.taskIndex, editedTask]);

  const handleCancel = useCallback(() => {
    setEditedTask(data.task);
    setIsEditing(false);
  }, [data.task]);

  useEffect(() => {
    setEditedTask(data.task);
  }, [data.task]);

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        style={{ 
          background: '#2196f3',
          width: '12px',
          height: '12px',
          top: '-6px',
          border: '2px solid #1976d2',
          transition: 'all 0.2s ease',
          borderRadius: '6px'
        }}
      />
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
        sx={{ 
          width: 400,
          height: 300,
          border: isProcessingDetail ? '2px dashed #ff9800' : (selected ? '2px solid #1976d2' : '1px solid #555'),
          borderRadius: '8px',
          boxShadow: selected ? '0 0 0 2px #1976d2, 0 2px 8px rgba(25, 118, 210, 0.4)' : '0 2px 5px rgba(0, 0, 0, 0.2)',
          backgroundColor: selected ? 'rgba(25, 118, 210, 0.08)' : 'rgba(45, 45, 45, 1)',
          transition: 'all 0.3s ease',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          opacity: isProcessingDetail ? 0.7 : 1,
          '&:hover': {
            boxShadow: selected 
              ? '0 0 0 2px #1976d2, 0 4px 10px rgba(25, 118, 210, 0.5)'
              : '0 0 0 2px #1976d2, 0 4px 8px rgba(0, 0, 0, 0.3)',
            backgroundColor: selected 
              ? 'rgba(25, 118, 210, 0.12)'
              : 'rgba(45, 45, 45, 1)',
            border: isProcessingDetail ? '2px dashed #ff9800' : '1px solid transparent'
          }
        }}
        ref={cardRef}
      >
        <CardContent sx={{ 
          p: 2,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative'
        }}>
          {isProcessingDetail && (
            <Box sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              backgroundColor: 'rgba(0,0,0,0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 10,
              borderRadius: 'inherit'
            }}>
              <CircularProgress size={30} color="warning" />
              <Typography variant="caption" sx={{ml:1, color: '#ff9800'}}>Generating Details...</Typography>
            </Box>
          )}

          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} sx={{ flexShrink: 0, opacity: isProcessingDetail ? 0.5 : 1 }}>
            <Typography 
              variant="h6"
              sx={{ 
                fontSize: '0.9rem',
                fontWeight: 'bold',
                color: selected ? '#fff' : '#eee'
              }}
            >
              {data.label}
            </Typography>
            <Chip 
              label={data.task.type || 'Task'} 
              size="small" 
              color="secondary" 
              variant="outlined"
              sx={{ 
                fontSize: '0.7rem',
                height: '20px',
                '& .MuiChip-label': { px: 1 }
              }}
            />
          </Box>
          
          <Box sx={{ 
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            opacity: isProcessingDetail ? 0.5 : 1 
          }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={selected ? 1 : 0.5} sx={{ flexShrink: 0 }}>
              <Typography 
                variant="h6"
                sx={{ 
                  fontSize: selected ? '1rem' : '0.85rem', 
                  fontWeight: 'bold',
                  color: selected ? '#fff' : '#eee',
                  transition: 'all 0.3s ease'
                }}
              >
                Task {data.taskIndex + 1}: {editedTask.name}
              </Typography>
              {selected && (
                <Box display="flex" gap={0.5}>
                  {!isEditing ? (
                    <>
                      <IconButton size="small" onClick={handleEdit} disabled={isProcessingDetail}>
                        <EditIcon sx={{ fontSize: '1rem' }} />
                      </IconButton>
                    </>
                  ) : (
                    <>
                      <IconButton size="small" onClick={handleCancel} disabled={isProcessingDetail}>
                        <CloseIcon sx={{ fontSize: '1rem' }} />
                      </IconButton>
                      <IconButton size="small" onClick={handleSave} color="primary" disabled={isProcessingDetail}>
                        <CheckIcon sx={{ fontSize: '1rem' }} />
                      </IconButton>
                    </>
                  )}
                </Box>
              )}
            </Box>

            {selected && !isEditing && (
              <Box sx={{ 
                mt: 1, 
                flexGrow: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
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
              ref={taskContentRef}
              >
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '0.8rem',
                    mb: 1
                  }}
                >
                  类型: {editedTask.type}
                </Typography>
                {editedTask.description && (
                  <Typography 
                    variant="body1" 
                    sx={{ 
                      mb: 2,
                      color: '#fff',
                      fontSize: '0.85rem'
                    }}
                  >
                    {editedTask.description}
                  </Typography>
                )}
                
                {editedTask.sub_tasks && editedTask.sub_tasks.length > 0 && (
                  <Box>
                    <Typography 
                      variant="subtitle2" 
                      sx={{ 
                        color: 'rgba(255, 255, 255, 0.8)',
                        fontSize: '0.8rem',
                        mb: 1
                      }}
                    >
                      子任务 ({editedTask.sub_tasks.length}):
                    </Typography>
                    <Box sx={{ ml: 2 }}>
                      {editedTask.sub_tasks.map((subtask: string, idx: number) => (
                        <Typography 
                          key={idx} 
                          variant="body2" 
                          sx={{ 
                            color: 'rgba(255, 255, 255, 0.6)',
                            fontSize: '0.75rem'
                          }}
                        >
                          • {subtask}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            )}

            {selected && isEditing && (
              <Box sx={{ 
                mt: 1, 
                flexGrow: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
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
              ref={editFormRef}
              >
                <TextField
                  fullWidth
                  label="任务名称"
                  value={editedTask.name}
                  onChange={(e) => setEditedTask({...editedTask, name: e.target.value})}
                  sx={{ 
                    mb: 2,
                    '& .MuiInputBase-root': { fontSize: '0.8rem' }
                  }}
                  size="small"
                />
                <TextField
                  fullWidth
                  label="任务类型"
                  value={editedTask.type}
                  onChange={(e) => setEditedTask({...editedTask, type: e.target.value})}
                  sx={{ 
                    mb: 2,
                    '& .MuiInputBase-root': { fontSize: '0.8rem' }
                  }}
                  size="small"
                />
                <TextField
                  fullWidth
                  multiline
                  rows={2}
                  label="任务描述"
                  value={editedTask.description || ''}
                  onChange={(e) => setEditedTask({...editedTask, description: e.target.value})}
                  sx={{ 
                    mb: 2,
                    '& .MuiInputBase-root': { 
                      fontSize: '0.8rem'
                    },
                    '& textarea': {
                      overflow: 'auto !important',
                      resize: 'none',
                    }
                  }}
                  size="small"
                />
                <TextField
                  fullWidth
                  label="子任务 (逗号分隔)"
                  value={editedTask.sub_tasks?.join(', ') || ''}
                  onChange={(e) => setEditedTask({ 
                    ...editedTask, 
                    sub_tasks: e.target.value.split(',').map(s => s.trim()).filter(s => s)
                  })}
                  sx={{ '& .MuiInputBase-root': { fontSize: '0.8rem' } }}
                  size="small"
                />
              </Box>
            )}

            {!selected && (
              <Box sx={{ mt: 0.5, flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '0.7rem',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical'
                  }}
                >
                  {editedTask.description || editedTask.type}
                </Typography>
                {editedTask.sub_tasks && editedTask.sub_tasks.length > 0 && (
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      color: 'rgba(255, 255, 255, 0.5)',
                      fontSize: '0.65rem',
                      display: 'block',
                      mt: 0.5
                    }}
                  >
                    {editedTask.sub_tasks.length} 个子任务
                  </Typography>
                )}
              </Box>
            )}

            {detailError && selected && !isEditing && (
              <Typography 
                variant="caption" 
                color="error" 
                sx={{ mt: 1, fontSize: '0.75rem', flexShrink: 0, border: '1px solid red', p:0.5, borderRadius:1, backgroundColor: 'rgba(255,0,0,0.1)'}}
              >
                Error generating details: {detailError}
              </Typography>
            )}
          </Box>
        </CardContent>
      </Card>
    </>
  );
}; 