import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSnackbar } from 'notistack';
import { useFlowContext } from '../../contexts/FlowContext';
import {
  FlowData,
  createFlow,
  updateFlowName,
  deleteFlow,
  duplicateFlow,
  setAsLastSelectedFlow
} from '../../api/flowApi';
import { EditDialogState, DeleteDialogState } from './types';
import { generateDefaultFlowName } from './utils';

export const useFlowActions = (
  updateFlows: (flows: FlowData[]) => void,
  removeFlow: (flowId: string) => void,
  refreshFlows: () => Promise<void>,
  setLoading: (loading: boolean) => void,
  onClose: () => void
) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const { setCurrentFlowId } = useFlowContext();

  // 编辑对话框状态
  const [editDialog, setEditDialog] = useState<EditDialogState>({
    open: false,
    flow: null,
    newName: ''
  });

  // 删除对话框状态
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({
    open: false,
    flow: null
  });

  // 选择流程
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

  // 创建新流程
  const handleCreateNewFlow = async () => {
    try {
      setLoading(true);

      const defaultFlow: Partial<FlowData> = {
        name: generateDefaultFlowName(),
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
      enqueueSnackbar(`创建新流程图失败: ${err instanceof Error ? err.message : '未知错误'}`, { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // 打开编辑对话框
  const handleEditClick = (event: React.MouseEvent, flow: FlowData) => {
    event.stopPropagation();
    setEditDialog({
      open: true,
      flow: flow,
      newName: flow.name
    });
  };

  // 关闭编辑对话框
  const handleEditDialogClose = () => {
    setEditDialog({
      open: false,
      flow: null,
      newName: ''
    });
  };

  // 保存流程名称
  const handleSaveFlowName = async () => {
    if (!editDialog.flow || !editDialog.flow.id) return;

    try {
      setLoading(true);
      await updateFlowName(editDialog.flow.id.toString(), editDialog.newName);

      // 更新本地列表中的名称
      await refreshFlows();

      enqueueSnackbar(t('flowSelect.updateNameSuccess', '流程图名称已更新'), { variant: 'success' });
      handleEditDialogClose();

      // 检查当前打开的流程图是否是正在编辑的流程图
      const currentFlowId = new URLSearchParams(window.location.search).get('id');
      if (currentFlowId === editDialog.flow.id.toString()) {
        // 使用自定义事件而非页面刷新
        const event = new CustomEvent('flow-renamed', {
          detail: {
            flowId: editDialog.flow.id.toString(),
            newName: editDialog.newName
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

  // 打开删除对话框
  const handleDeleteClick = (event: React.MouseEvent, flow: FlowData) => {
    event.preventDefault();
    event.stopPropagation();
    setDeleteDialog({
      open: true,
      flow: flow
    });
  };

  // 关闭删除对话框
  const handleDeleteDialogClose = () => {
    setDeleteDialog({
      open: false,
      flow: null
    });
  };

  // 确认删除流程
  const handleConfirmDelete = async () => {
    if (!deleteDialog.flow || !deleteDialog.flow.id) return;

    try {
      setLoading(true);

      const flowIdToDelete = deleteDialog.flow.id.toString();
      const flowName = deleteDialog.flow.name;

      await deleteFlow(flowIdToDelete);
      removeFlow(flowIdToDelete);

      handleDeleteDialogClose();

      // 延迟显示成功消息
      setTimeout(() => {
        enqueueSnackbar(`${t('flowSelect.deleteSuccess', '流程图已删除')}: "${flowName}"`, { variant: 'success' });

        // 检查当前打开的流程图是否是被删除的流程图
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
    }
  };

  // 复制流程
  const handleDuplicateClick = async (event: React.MouseEvent, flow: FlowData) => {
    event.stopPropagation();

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
        await refreshFlows();

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

  // 更新编辑对话框的新名称
  const handleNewFlowNameChange = (newName: string) => {
    setEditDialog(prev => ({
      ...prev,
      newName
    }));
  };

  return {
    editDialog,
    deleteDialog,
    handleFlowSelect,
    handleCreateNewFlow,
    handleEditClick,
    handleEditDialogClose,
    handleSaveFlowName,
    handleDeleteClick,
    handleDeleteDialogClose,
    handleConfirmDelete,
    handleDuplicateClick,
    handleNewFlowNameChange
  };
}; 