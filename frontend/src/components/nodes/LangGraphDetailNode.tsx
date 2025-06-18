import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Handle, Position } from 'reactflow';
import { 
  Card, 
  CardContent, 
  TextField, 
  Typography, 
  Box, 
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip
} from '@mui/material';
import { 
  Edit as EditIcon, 
  Delete as DeleteIcon,
  Add as AddIcon,
  Check as CheckIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { useAgentStateSync } from '../../hooks/useAgentStateSync';

interface LangGraphDetailNodeData {
  label: string;
  flowId: string;
  taskIndex: number;
  taskName: string;
  details: string[];
}

interface LangGraphDetailNodeProps {
  id: string;
  data: LangGraphDetailNodeData;
  selected: boolean;
}

export const LangGraphDetailNode: React.FC<LangGraphDetailNodeProps> = ({ id, data, selected }) => {
  const [details, setDetails] = useState<string[]>(data.details || []);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newDetail, setNewDetail] = useState('');
  const { updateTaskDetails } = useAgentStateSync();

  // 新增：滚动区域的refs
  const detailsListRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  // 新增：原生DOM事件处理滚轮事件
  useEffect(() => {
    const handleNativeWheel = (e: Event) => {
      const wheelEvent = e as WheelEvent;
      // 只阻止事件传播到ReactFlow，但保留元素的滚动功能
      wheelEvent.stopPropagation();
      console.log('DetailNode滚轮事件传播被阻止:', wheelEvent.target);
    };

    // 为所有滚动区域添加原生事件监听
    const refs = [detailsListRef];
    
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
        
        console.log('为DetailNode元素添加滚轮事件监听:', scrollableElement, textareas);
      }
    });

    // 处理对话框中的文本框
    if (isAddingNew && dialogRef.current) {
      const dialogTextareas = dialogRef.current.querySelectorAll('textarea');
      dialogTextareas.forEach(textarea => {
        textarea.addEventListener('wheel', handleNativeWheel, { passive: true });
      });
    }

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
      
      // 清理对话框事件监听
      if (dialogRef.current) {
        const dialogTextareas = dialogRef.current.querySelectorAll('textarea');
        dialogTextareas.forEach(textarea => {
          textarea.removeEventListener('wheel', handleNativeWheel);
        });
      }
    };
  }, [editingIndex, isAddingNew, selected]); // 依赖状态变化重新绑定事件

  const handleSaveDetails = useCallback(() => {
    updateTaskDetails(data.taskIndex, details);
  }, [data.taskIndex, details, updateTaskDetails]);

  const handleEditDetail = useCallback((index: number) => {
    setEditingIndex(index);
    setEditValue(details[index]);
  }, [details]);

  const handleSaveEdit = useCallback(() => {
    if (editingIndex !== null) {
      const newDetails = [...details];
      newDetails[editingIndex] = editValue;
      setDetails(newDetails);
      setEditingIndex(null);
      setEditValue('');
      handleSaveDetails();
    }
  }, [editingIndex, editValue, details, handleSaveDetails]);

  const handleCancelEdit = useCallback(() => {
    setEditingIndex(null);
    setEditValue('');
  }, []);

  const handleDeleteDetail = useCallback((index: number) => {
    const newDetails = details.filter((_, i) => i !== index);
    setDetails(newDetails);
    handleSaveDetails();
  }, [details, handleSaveDetails]);

  const handleAddDetail = useCallback(() => {
    if (newDetail.trim()) {
      const newDetails = [...details, newDetail.trim()];
      setDetails(newDetails);
      setNewDetail('');
      setIsAddingNew(false);
      handleSaveDetails();
    }
  }, [newDetail, details, handleSaveDetails]);

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        style={{ 
          background: '#4caf50',
          width: '12px',
          height: '12px',
          top: '-6px',
          border: '2px solid #388e3c',
          transition: 'all 0.2s ease',
          borderRadius: '6px'
        }}
      />
      <Card 
        sx={{ 
          width: 350,
          height: 400,
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
              label="详情步骤" 
              size="small" 
              color="success" 
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
                {data.taskName} - 模块步骤
              </Typography>
              {selected && (
                <Box display="flex" gap={0.5}>
                  <Chip 
                    label="步骤" 
                    size="small" 
                    color="info" 
                    variant="outlined"
                    sx={{ 
                      mr: 1,
                      fontSize: '0.7rem',
                      height: '20px',
                      '& .MuiChip-label': { px: 1 }
                    }}
                  />
                  <IconButton size="small" color="primary" onClick={() => setIsAddingNew(true)}>
                    <AddIcon sx={{ fontSize: '1rem' }} />
                  </IconButton>
                </Box>
              )}
            </Box>

            {selected && (
              <Box sx={{ 
                mt: 1, 
                flexGrow: 1,
                overflowY: 'auto', // 详细步骤区域的滚动条
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
              ref={detailsListRef}
              >
                {details.length > 0 ? (
                  <List dense sx={{ p: 0 }}>
                    {details.map((detail, index) => (
                      <ListItem 
                        key={index} 
                        divider 
                        sx={{ 
                          px: 0,
                          py: 0.5,
                          borderColor: 'rgba(255, 255, 255, 0.1)'
                        }}
                      >
                        {editingIndex === index ? (
                          <Box display="flex" alignItems="center" width="100%" gap={1}>
                            <TextField
                              fullWidth
                              multiline
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              size="small"
                              sx={{ 
                                '& .MuiInputBase-root': { 
                                  fontSize: '0.8rem',
                                  color: '#fff'
                                },
                                '& textarea': {
                                  overflow: 'auto !important', // 编辑文本框的滚动条
                                  resize: 'none',
                                }
                              }}
                            />
                            <IconButton size="small" onClick={handleSaveEdit}>
                              <CheckIcon sx={{ fontSize: '1rem' }} />
                            </IconButton>
                            <IconButton size="small" onClick={handleCancelEdit}>
                              <CloseIcon sx={{ fontSize: '1rem' }} />
                            </IconButton>
                          </Box>
                        ) : (
                          <>
                            <ListItemText 
                              primary={`步骤 ${index + 1}`}
                              secondary={detail}
                              primaryTypographyProps={{
                                sx: { 
                                  fontSize: '0.8rem',
                                  color: 'rgba(255, 255, 255, 0.8)',
                                  fontWeight: 'bold'
                                }
                              }}
                              secondaryTypographyProps={{
                                sx: { 
                                  fontSize: '0.75rem',
                                  color: 'rgba(255, 255, 255, 0.7)',
                                  whiteSpace: 'pre-wrap'
                                }
                              }}
                            />
                            <ListItemSecondaryAction>
                              <IconButton 
                                edge="end" 
                                size="small" 
                                onClick={() => handleEditDetail(index)}
                                sx={{ mr: 0.5 }}
                              >
                                <EditIcon sx={{ fontSize: '0.9rem' }} />
                              </IconButton>
                              <IconButton 
                                edge="end" 
                                size="small" 
                                color="error"
                                onClick={() => handleDeleteDetail(index)}
                              >
                                <DeleteIcon sx={{ fontSize: '0.9rem' }} />
                              </IconButton>
                            </ListItemSecondaryAction>
                          </>
                        )}
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Box textAlign="center" py={2}>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        color: 'rgba(255, 255, 255, 0.5)',
                        fontSize: '0.8rem',
                        mb: 1
                      }}
                    >
                      还没有步骤详情
                    </Typography>
                    <Button 
                      startIcon={<AddIcon />}
                      onClick={() => setIsAddingNew(true)}
                      variant="contained"
                      color="primary"
                      size="small"
                      sx={{ fontSize: '0.7rem', py: 0.5 }}
                    >
                      添加步骤
                    </Button>
                  </Box>
                )}
              </Box>
            )}

            {!selected && (
              <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '0.7rem',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical'
                  }}
                >
                  {details.length > 0 ? `${details.length} 个步骤` : '点击查看详情'}
                </Typography>
              </Box>
            )}
          </Box>

          <Dialog 
            open={isAddingNew} 
            onClose={() => setIsAddingNew(false)} 
            maxWidth="sm" 
            fullWidth
            PaperProps={{
              sx: {
                backgroundColor: 'rgba(45, 45, 45, 0.95)',
                color: '#fff'
              }
            }}
            ref={dialogRef}
          >
            <DialogTitle sx={{ color: '#fff' }}>添加新步骤</DialogTitle>
            <DialogContent>
              <TextField
                autoFocus
                fullWidth
                multiline
                rows={3}
                label="步骤描述"
                value={newDetail}
                onChange={(e) => setNewDetail(e.target.value)}
                sx={{ 
                  mt: 2,
                  '& .MuiInputBase-root': { 
                    color: '#fff'
                  },
                  '& .MuiInputLabel-root': {
                    color: 'rgba(255, 255, 255, 0.7)'
                  },
                  '& textarea': {
                    overflow: 'auto !important', // 对话框文本框的滚动条
                    resize: 'none',
                  }
                }}
              />
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setIsAddingNew(false)} sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>
                取消
              </Button>
              <Button onClick={handleAddDetail} variant="contained">
                添加
              </Button>
            </DialogActions>
          </Dialog>
        </CardContent>
      </Card>
    </>
  );
}; 