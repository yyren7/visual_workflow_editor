import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Handle, Position } from 'reactflow';
import { 
  Card, 
  CardContent, 
  TextField, 
  Typography, 
  Box, 
  IconButton,
  Chip
} from '@mui/material';
import { 
  Edit as EditIcon, 
  Check as CheckIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { useAgentStateSync } from '../../hooks/useAgentStateSync';

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

export const LangGraphTaskNode: React.FC<LangGraphTaskNodeProps> = ({ id, data, selected }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedTask, setEditedTask] = useState<TaskDefinition>(data.task);
  const { updateTask } = useAgentStateSync();

  // 新增：滚动区域的refs
  const taskContentRef = useRef<HTMLDivElement>(null);
  const editFormRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  // 新增：原生DOM事件处理滚轮事件
  useEffect(() => {
    const handleNativeWheel = (e: Event) => {
      const wheelEvent = e as WheelEvent;
      // 只阻止事件传播到ReactFlow，但保留元素的滚动功能
      wheelEvent.stopPropagation();
      console.log('TaskNode滚轮事件传播被阻止:', wheelEvent.target);
    };

    // 为所有滚动区域添加原生事件监听
    const refs = [taskContentRef, editFormRef];
    
    refs.forEach(ref => {
      if (ref.current) {
        // 直接对滚动元素添加事件监听
        const element = ref.current;
        // 查找实际的滚动元素（可能是textarea或子元素）
        const textareas = element.querySelectorAll('textarea');
        const scrollableElement = element;
        
        // 为容器和所有textarea添加监听
        scrollableElement.addEventListener('wheel', handleNativeWheel, { passive: true });
        textareas.forEach(textarea => {
          textarea.addEventListener('wheel', handleNativeWheel, { passive: true });
        });
        
        console.log('为TaskNode元素添加滚轮事件监听:', scrollableElement, textareas);
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
  }, [isEditing, selected]); // 依赖状态变化重新绑定事件

  const handleEdit = useCallback(() => {
    setIsEditing(true);
  }, []);

  const handleSave = useCallback(() => {
    updateTask(data.taskIndex, editedTask);
    setIsEditing(false);
  }, [data.taskIndex, editedTask, updateTask]);

  const handleCancel = useCallback(() => {
    setEditedTask(data.task);
    setIsEditing(false);
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
          border: '1px solid #555',
          borderRadius: '8px',
          boxShadow: selected ? '0 0 0 2px #1976d2, 0 2px 8px rgba(25, 118, 210, 0.4)' : '0 2px 5px rgba(0, 0, 0, 0.2)',
          backgroundColor: selected ? 'rgba(25, 118, 210, 0.08)' : 'rgba(45, 45, 45, 1)',
          transition: 'all 0.3s ease',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          '&:hover': {
            boxShadow: selected 
              ? '0 0 0 2px #1976d2, 0 4px 10px rgba(25, 118, 210, 0.5)'
              : '0 0 0 2px #1976d2, 0 4px 8px rgba(0, 0, 0, 0.3)',
            backgroundColor: selected 
              ? 'rgba(25, 118, 210, 0.12)'
              : 'rgba(45, 45, 45, 1)',
            border: '1px solid transparent'
          }
        }}
        ref={cardRef}
      >
        <CardContent sx={{ 
          p: 2,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} sx={{ flexShrink: 0 }}>
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
                      <Chip 
                        label="任务" 
                        size="small" 
                        color="secondary" 
                        variant="outlined"
                        sx={{ 
                          mr: 1,
                          fontSize: '0.7rem',
                          height: '20px',
                          '& .MuiChip-label': { px: 1 }
                        }}
                      />
                      <IconButton size="small" onClick={handleEdit}>
                        <EditIcon sx={{ fontSize: '1rem' }} />
                      </IconButton>
                    </>
                  ) : (
                    <>
                      <IconButton size="small" onClick={handleCancel}>
                        <CloseIcon sx={{ fontSize: '1rem' }} />
                      </IconButton>
                      <IconButton size="small" onClick={handleSave} color="primary">
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
          </Box>
        </CardContent>
      </Card>
    </>
  );
}; 