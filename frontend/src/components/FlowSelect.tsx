import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  IconButton,
  Typography,
  Box,
  CircularProgress,
  Paper,
  TextField,
  InputAdornment,
  Divider,
  Button,
  ListItemSecondaryAction,
  Dialog as EditDialog,
  DialogActions,
  DialogContent as EditDialogContent,
  DialogTitle as EditDialogTitle
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { getFlowsForUser, FlowData, createFlow, updateFlowName, deleteFlow, duplicateFlow, setAsLastSelectedFlow } from '../api/api';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSnackbar } from 'notistack';
import { useFlowContext } from '../contexts/FlowContext';

interface FlowSelectProps {
  open: boolean;
  onClose: () => void;
}

const FlowSelect: React.FC<FlowSelectProps> = ({ open, onClose }) => {
  const [flows, setFlows] = useState<FlowData[]>([]);
  const [filteredFlows, setFilteredFlows] = useState<FlowData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const { setCurrentFlowId } = useFlowContext();

  // 编辑流程图名称相关状态
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingFlow, setEditingFlow] = useState<FlowData | null>(null);
  const [newFlowName, setNewFlowName] = useState('');

  // 删除流程图确认对话框相关状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingFlow, setDeletingFlow] = useState<FlowData | null>(null);

  useEffect(() => {
    const fetchFlows = async () => {
      if (!open) return;

      try {
        setLoading(true);
        setError(null);
        // 减少请求数量，避免可能的性能问题
        const userFlows = await getFlowsForUser(0, 100);
        console.log("成功获取流程图列表:", userFlows.length);
        setFlows(userFlows);
        setFilteredFlows(userFlows);
      } catch (err) {
        console.error('加载流程图列表失败:', err);
        // 添加更多错误信息输出
        if (err instanceof Error) {
          console.error('错误详情:', err.message);
          setError(`${t('flowSelect.error', '加载流程图失败')}: ${err.message}`);
        } else {
          setError(t('flowSelect.error', '加载流程图失败'));
        }
      } finally {
        setLoading(false);
      }
    };

    fetchFlows();
  }, [open, t]);

  // 当搜索词变化时，过滤流程图
  useEffect(() => {
    if (searchTerm.trim() === '') {
      setFilteredFlows(flows);
    } else {
      const filtered = flows.filter(flow =>
        flow.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredFlows(filtered);
    }
  }, [searchTerm, flows]);

  const handleFlowSelect = (flowId: string | number | undefined) => {
    if (flowId !== undefined) {
      const userId = localStorage.getItem('user_id');

      // 设置当前流程图ID到FlowContext
      setCurrentFlowId(flowId.toString());
      console.log("选择流程图：设置currentFlowId =", flowId.toString());

      // 通知后端，将此流程图设置为最后选择的流程图
      setAsLastSelectedFlow(flowId.toString())
        .then(() => console.log("已将流程图设置为最后选择的流程图"))
        .catch(err => console.error("设置最后选择的流程图失败:", err));

      // 使用navigate而非window.location.href，避免整页刷新
      navigate(`/flow?id=${flowId}${userId ? `&user=${userId}` : ''}`);

      // 发布自定义事件，通知其他组件流程图已更改
      const event = new CustomEvent('flow-changed', {
        detail: { flowId: flowId.toString() }
      });
      window.dispatchEvent(event);

      onClose(); // 关闭选择窗口
    }
  };

  // 打开编辑流程图名称对话框
  const handleEditClick = (event: React.MouseEvent, flow: FlowData) => {
    event.stopPropagation(); // 阻止事件冒泡，避免触发流程图选择
    setEditingFlow(flow);
    setNewFlowName(flow.name);
    setEditDialogOpen(true);
  };

  // 关闭编辑对话框
  const handleEditDialogClose = () => {
    setEditDialogOpen(false);
    setEditingFlow(null);
  };

  // 保存流程图新名称
  const handleSaveFlowName = async () => {
    if (!editingFlow || !editingFlow.id) return;

    try {
      setLoading(true);
      await updateFlowName(editingFlow.id.toString(), newFlowName);

      // 更新本地列表中的名称
      const updatedFlows = flows.map(flow => {
        if (flow.id === editingFlow.id) {
          return { ...flow, name: newFlowName };
        }
        return flow;
      });

      setFlows(updatedFlows);
      setFilteredFlows(updatedFlows.filter(flow =>
        searchTerm.trim() === '' || flow.name.toLowerCase().includes(searchTerm.toLowerCase())
      ));

      enqueueSnackbar(t('flowSelect.updateNameSuccess', '流程图名称已更新'), { variant: 'success' });
      handleEditDialogClose();

      // 检查当前打开的流程图是否是正在编辑的流程图
      // 如果是，发布自定义事件通知流程图名称已更改
      const currentFlowId = new URLSearchParams(window.location.search).get('id');
      if (currentFlowId === editingFlow.id.toString()) {
        // 使用自定义事件而非页面刷新
        const event = new CustomEvent('flow-renamed', {
          detail: {
            flowId: editingFlow.id.toString(),
            newName: newFlowName
          }
        });
        window.dispatchEvent(event);
      }

    } catch (err) {
      console.error('更新流程图名称失败:', err);
      if (err instanceof Error) {
        enqueueSnackbar(`${t('flowSelect.updateNameError', '更新名称失败')}: ${err.message}`, { variant: 'error' });
      } else {
        enqueueSnackbar(t('flowSelect.updateNameError', '更新名称失败'), { variant: 'error' });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNewFlow = async () => {
    try {
      setLoading(true);
      setError(null);

      // 避免生成重复名称的流程图，添加随机数
      const randomId = Math.floor(Math.random() * 1000);
      const defaultFlow: Partial<FlowData> = {
        name: `新流程图 ${new Date().toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        })}-${randomId}`,
        flow_data: {
          nodes: [],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 }
        }
      };

      const newFlow = await createFlow(defaultFlow as FlowData);
      console.log("成功创建新流程图:", newFlow);

      if (newFlow && newFlow.id) {
        // 设置当前流程图ID到FlowContext
        setCurrentFlowId(newFlow.id.toString());
        console.log("创建流程图：设置currentFlowId =", newFlow.id.toString());

        // 通知后端，将此流程图设置为最后选择的流程图
        try {
          await setAsLastSelectedFlow(newFlow.id.toString());
          console.log("已将新流程图设置为最后选择的流程图");
        } catch (err: any) {
          console.error("设置最后选择的流程图失败:", err);
        }

        const userId = localStorage.getItem('user_id');
        navigate(`/flow?id=${newFlow.id}${userId ? `&user=${userId}` : ''}`);
        onClose();
      }
    } catch (err) {
      console.error('创建新流程图失败:', err);
      setError(`创建新流程图失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return '';

    try {
      const date = new Date(dateString);
      // 简单格式化，不依赖外部库
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateString;
    }
  };

  // 打开删除流程图确认对话框
  const handleDeleteClick = (event: React.MouseEvent, flow: FlowData) => {
    event.preventDefault(); // 使用preventDefault而不是仅停止冒泡
    event.stopPropagation(); // 仍然阻止事件冒泡

    // 设置要删除的流程图并打开确认对话框
    setDeletingFlow(flow);
    setDeleteDialogOpen(true);
  };

  // 关闭删除确认对话框
  const handleDeleteDialogClose = () => {
    setDeleteDialogOpen(false);
    // 延迟清除删除流程图的状态，确保对话框完全关闭
    setTimeout(() => {
      setDeletingFlow(null);
    }, 100);
  };

  // 确认删除流程图
  const handleConfirmDelete = async () => {
    if (!deletingFlow || !deletingFlow.id) return;

    try {
      setLoading(true);

      // 先保存要删除的流程图ID，因为后面会清除deletingFlow
      const flowIdToDelete = deletingFlow.id.toString();
      const flowName = deletingFlow.name;

      await deleteFlow(flowIdToDelete);

      // 从本地列表中移除被删除的流程图
      const updatedFlows = flows.filter(flow => flow.id !== flowIdToDelete);
      setFlows(updatedFlows);
      setFilteredFlows(updatedFlows.filter(flow =>
        searchTerm.trim() === '' || flow.name.toLowerCase().includes(searchTerm.toLowerCase())
      ));

      // 先关闭对话框
      setDeleteDialogOpen(false);

      // 延迟显示成功消息，确保对话框已关闭
      setTimeout(() => {
        enqueueSnackbar(`${t('flowSelect.deleteSuccess', '流程图已删除')}: "${flowName}"`, { variant: 'success' });

        // 检查当前打开的流程图是否是被删除的流程图
        // 如果是，重定向到主页
        const currentFlowId = new URLSearchParams(window.location.search).get('id');
        if (currentFlowId === flowIdToDelete) {
          navigate('/flow', { replace: true });
        }
      }, 300);

    } catch (err) {
      console.error('删除流程图失败:', err);
      if (err instanceof Error) {
        enqueueSnackbar(`${t('flowSelect.deleteError', '删除失败')}: ${err.message}`, { variant: 'error' });
      } else {
        enqueueSnackbar(t('flowSelect.deleteError', '删除失败'), { variant: 'error' });
      }
    } finally {
      setLoading(false);
      // 不在这里调用handleDeleteDialogClose，避免在操作完成前关闭对话框
      setTimeout(() => {
        setDeletingFlow(null);
      }, 300);
    }
  };

  // 复制流程图
  const handleDuplicateClick = async (event: React.MouseEvent, flow: FlowData) => {
    event.stopPropagation(); // 阻止事件冒泡，避免触发流程图选择

    try {
      setLoading(true);
      const newFlow = await duplicateFlow(flow.id as string);

      if (newFlow && newFlow.id) {
        // 设置当前流程图ID到FlowContext
        setCurrentFlowId(newFlow.id.toString());
        console.log("复制流程图：设置currentFlowId =", newFlow.id.toString());

        // 通知后端，将此流程图设置为最后选择的流程图
        try {
          await setAsLastSelectedFlow(newFlow.id.toString());
          console.log("已将复制的流程图设置为最后选择的流程图");
        } catch (err: any) {
          console.error("设置最后选择的流程图失败:", err);
        }

        // 刷新流程图列表
        const updatedFlows = await getFlowsForUser(0, 100);
        setFlows(updatedFlows);
        setFilteredFlows(updatedFlows.filter(f =>
          searchTerm.trim() === '' || f.name.toLowerCase().includes(searchTerm.toLowerCase())
        ));

        enqueueSnackbar(t('flowSelect.duplicateSuccess', '流程图已复制'), { variant: 'success' });

        // 导航到新流程图
        const userId = localStorage.getItem('user_id');
        navigate(`/flow?id=${newFlow.id}${userId ? `&user=${userId}` : ''}`);
        onClose();
      }
    } catch (err) {
      console.error('复制流程图失败:', err);
      if (err instanceof Error) {
        enqueueSnackbar(`${t('flowSelect.duplicateError', '复制流程图失败')}: ${err.message}`, { variant: 'error' });
      } else {
        enqueueSnackbar(t('flowSelect.duplicateError', '复制流程图失败'), { variant: 'error' });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        fullWidth
        maxWidth="sm"
        PaperProps={{
          sx: {
            bgcolor: '#2d2d2d',
            color: 'white',
            border: '1px solid #444'
          }
        }}
      >
        <DialogTitle sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: '#333',
          borderBottom: '1px solid #444'
        }}>
          <Typography variant="h6" component="div">{t('flowSelect.title', '选择流程图')}</Typography>
          <IconButton
            edge="end"
            color="inherit"
            onClick={onClose}
            aria-label="close"
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, pb: 2 }}>
          {/* 搜索框 */}
          <Box sx={{ mb: 2 }}>
            <TextField
              fullWidth
              variant="outlined"
              placeholder={t('flowSelect.search', '搜索流程图...')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              size="small"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: 'rgba(255, 255, 255, 0.7)' }} />
                  </InputAdornment>
                ),
                sx: {
                  color: 'white',
                  '& .MuiOutlinedInput-notchedOutline': {
                    borderColor: 'rgba(255, 255, 255, 0.23)',
                  },
                  '&:hover .MuiOutlinedInput-notchedOutline': {
                    borderColor: 'rgba(255, 255, 255, 0.87)',
                  },
                }
              }}
            />
          </Box>

          {/* 创建新流程图按钮 */}
          <Box sx={{ mb: 2 }}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={handleCreateNewFlow}
              disabled={loading}
              sx={{
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.23)',
                '&:hover': {
                  borderColor: 'rgba(255, 255, 255, 0.87)',
                  bgcolor: 'rgba(255, 255, 255, 0.08)'
                }
              }}
            >
              {t('flowSelect.createNew', '创建新流程图')}
            </Button>
          </Box>

          <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.12)', mb: 2 }} />

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Typography color="error" sx={{ p: 2 }}>
              {error}
            </Typography>
          ) : filteredFlows.length === 0 ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              {searchTerm ? (
                <Typography sx={{ color: '#aaa', fontStyle: 'italic' }}>
                  {t('flowSelect.noSearchResults', '没有找到匹配的流程图')}
                </Typography>
              ) : (
                <Typography sx={{ color: '#aaa', fontStyle: 'italic' }}>
                  {t('flowSelect.noFlows', '没有找到流程图')}
                </Typography>
              )}
            </Box>
          ) : (
            <Box sx={{ maxHeight: '350px', overflow: 'auto' }}>
              <List sx={{ width: '100%', p: 0 }}>
                {filteredFlows.map((flow) => (
                  <Paper
                    key={flow.id}
                    elevation={2}
                    sx={{
                      mb: 1,
                      bgcolor: '#383838',
                      '&:hover': {
                        bgcolor: '#444',
                      }
                    }}
                  >
                    <ListItemButton onClick={() => handleFlowSelect(flow.id)}>
                      <ListItem
                        disablePadding
                        sx={{ display: 'block' }}
                        secondaryAction={
                          <Box sx={{ display: 'flex' }}>
                            <IconButton
                              edge="end"
                              aria-label="edit"
                              onClick={(e) => handleEditClick(e, flow)}
                              sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
                            >
                              <EditIcon />
                            </IconButton>
                            <IconButton
                              edge="end"
                              aria-label="duplicate"
                              onClick={(e) => handleDuplicateClick(e, flow)}
                              sx={{
                                color: 'rgba(255, 255, 255, 0.7)',
                                '&:hover': {
                                  color: '#42a5f5',
                                }
                              }}
                            >
                              <ContentCopyIcon />
                            </IconButton>
                            <IconButton
                              edge="end"
                              aria-label="delete"
                              onClick={(e) => handleDeleteClick(e, flow)}
                              sx={{
                                color: 'rgba(255, 255, 255, 0.7)',
                                // 添加更明显的样式，确保点击触发
                                '&:hover': {
                                  color: '#f44336',
                                }
                              }}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Box>
                        }
                      >
                        <ListItemText
                          primary={flow.name}
                          secondary={
                            <Box sx={{ display: 'flex', alignItems: 'center', color: '#aaa', mt: 0.5 }}>
                              <AccessTimeIcon fontSize="small" sx={{ mr: 0.5, fontSize: '0.9rem' }} />
                              <Typography variant="caption" sx={{ fontSize: '0.8rem' }}>
                                {flow.updated_at ? formatDate(flow.updated_at) : formatDate(flow.created_at)}
                              </Typography>
                            </Box>
                          }
                          primaryTypographyProps={{
                            fontWeight: 'medium',
                            color: 'white'
                          }}
                          secondaryTypographyProps={{
                            component: 'div'
                          }}
                        />
                      </ListItem>
                    </ListItemButton>
                  </Paper>
                ))}
              </List>
            </Box>
          )}
        </DialogContent>
      </Dialog>

      {/* 编辑流程图名称的对话框 */}
      <Dialog
        open={editDialogOpen}
        onClose={handleEditDialogClose}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            bgcolor: '#2d2d2d',
            color: 'white',
            border: '1px solid #444'
          }
        }}
      >
        <DialogTitle sx={{ bgcolor: '#333', borderBottom: '1px solid #444' }}>
          <Typography component="div">{t('flowSelect.editFlowName', '编辑流程图名称')}</Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, pb: 1, mt: 1 }}>
          <TextField
            autoFocus
            margin="dense"
            label={t('flowSelect.flowName', '流程图名称')}
            type="text"
            fullWidth
            variant="outlined"
            value={newFlowName}
            onChange={(e) => setNewFlowName(e.target.value)}
            InputProps={{
              sx: {
                color: 'white',
              }
            }}
            InputLabelProps={{
              sx: {
                color: 'rgba(255, 255, 255, 0.7)',
              }
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                '& fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.23)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.87)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'primary.main',
                },
              }
            }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 1 }}>
          <Button
            onClick={handleEditDialogClose}
            sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
          >
            {t('common.cancel', '取消')}
          </Button>
          <Button
            onClick={handleSaveFlowName}
            variant="contained"
            disabled={!newFlowName.trim() || loading}
          >
            {t('common.save', '保存')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 删除流程图确认对话框 */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteDialogClose}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            bgcolor: '#2d2d2d',
            color: 'white',
            border: '1px solid #444'
          }
        }}
        disableEscapeKeyDown
      >
        <DialogTitle sx={{
          bgcolor: '#333',
          borderBottom: '1px solid #444',
          color: '#ff5252'
        }}>
          <Typography component="div">{t('flowEditor.deleteConfirmTitle', '确认删除流程图?')}</Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, pb: 1, mt: 1 }}>
          <Typography sx={{ mb: 2 }}>
            {t('flowEditor.deleteConfirmContent', '此操作无法撤销')}
          </Typography>
          {deletingFlow?.name && (
            <Typography sx={{
              fontWeight: 'bold',
              fontSize: '1.1rem',
              p: 1,
              bgcolor: 'rgba(255, 0, 0, 0.1)',
              borderRadius: 1
            }}>
              "{deletingFlow.name}"
            </Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 1 }}>
          <Button
            onClick={handleDeleteDialogClose}
            sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
          >
            {t('flowEditor.cancel', '取消')}
          </Button>
          <Button
            onClick={handleConfirmDelete}
            variant="contained"
            color="error"
            disabled={loading}
          >
            {t('flowEditor.delete', '删除')}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default FlowSelect; 