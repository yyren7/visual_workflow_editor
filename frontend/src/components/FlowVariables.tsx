// visual_workflow_editor/frontend/src/components/FlowVariables.tsx
import React, { useState, useCallback, useEffect } from 'react';
import { Box, TextField, Button, Typography, List, ListItem, ListItemText, IconButton, Divider, CircularProgress } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import SaveIcon from '@mui/icons-material/Save';
import UploadIcon from '@mui/icons-material/Upload';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useSnackbar } from 'notistack';
import { saveAs } from 'file-saver';
import { useTranslation } from 'react-i18next';
import { useFlowContext } from '../contexts/FlowContext';
import { 
  getFlowVariables, 
  updateFlowVariables, 
  resetFlowVariables, 
  addFlowVariable,
  deleteFlowVariable,
  importFlowVariablesFromFile,
  exportFlowVariablesToJson,
  FlowVariables as FlowVariablesType
} from '../api/api';

// 定义变量类型
interface VariablesType {
  [key: string]: string;
}

/**
 * FlowVariables Component
 *
 * This component manages variables for the current flow, allowing users to load, save, edit, add, and delete variables.
 * It communicates with the backend API for operations on flow variables.
 */
const FlowVariables: React.FC = () => {
  const { t } = useTranslation();
  const [variables, setVariables] = useState<VariablesType>({});
  const [newVariableName, setNewVariableName] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const { enqueueSnackbar } = useSnackbar();
  const { currentFlowId } = useFlowContext(); // 从上下文中获取当前流程图ID
  
  // 获取流程图变量
  const fetchFlowVariables = useCallback(async () => {
    if (!currentFlowId) {
      enqueueSnackbar(t('flowVariables.noActiveFlow'), { variant: 'warning' });
      return;
    }

    try {
      setLoading(true);
      const data = await getFlowVariables(currentFlowId);
      setVariables(data);
      enqueueSnackbar(t('flowVariables.loadSuccess'), { variant: 'success' });
    } catch (error) {
      console.error('获取流程图变量失败:', error);
      enqueueSnackbar(t('flowVariables.loadError'), { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [enqueueSnackbar, t, currentFlowId]);
  
  // 初始加载
  useEffect(() => {
    if (currentFlowId) {
      fetchFlowVariables();
    }
  }, [fetchFlowVariables, currentFlowId]);
  
  // 保存变量到服务器
  const saveVariablesToServer = useCallback(async () => {
    if (!currentFlowId) {
      enqueueSnackbar(t('flowVariables.noActiveFlow'), { variant: 'warning' });
      return;
    }

    try {
      setLoading(true);
      await updateFlowVariables(currentFlowId, variables);
      enqueueSnackbar(t('flowVariables.saveSuccess'), { variant: 'success' });
    } catch (error) {
      console.error('保存流程图变量失败:', error);
      enqueueSnackbar(t('flowVariables.saveError'), { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [variables, enqueueSnackbar, t, currentFlowId]);
  
  // 重置变量
  const handleResetVariables = useCallback(async () => {
    if (!currentFlowId) {
      enqueueSnackbar(t('flowVariables.noActiveFlow'), { variant: 'warning' });
      return;
    }

    try {
      if (window.confirm(t('flowVariables.confirmReset'))) {
        setLoading(true);
        await resetFlowVariables(currentFlowId);
        setVariables({});
        enqueueSnackbar(t('flowVariables.resetSuccess'), { variant: 'success' });
      }
    } catch (error) {
      console.error('重置流程图变量失败:', error);
      enqueueSnackbar(t('flowVariables.resetError'), { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [enqueueSnackbar, t, currentFlowId]);

  /**
   * 从文件加载变量
   * @param {File} file - 包含变量的文件
   */
  const loadVariables = useCallback((file: File) => {
    if (!currentFlowId) {
      enqueueSnackbar(t('flowVariables.noActiveFlow'), { variant: 'warning' });
      return;
    }

    const reader = new FileReader();
    reader.onload = async (e: ProgressEvent<FileReader>) => {
      try {
        if (e.target && e.target.result) {
          const loadedVariables = JSON.parse(e.target.result as string);
          if (typeof loadedVariables === 'object' && loadedVariables !== null) {
            setVariables(loadedVariables);
            enqueueSnackbar(t('flowVariables.loadSuccess'), { variant: 'success' });
            // 自动保存到服务器
            try {
              setLoading(true);
              await updateFlowVariables(currentFlowId, loadedVariables);
              enqueueSnackbar(t('flowVariables.importSuccess'), { variant: 'success' });
            } catch (importError) {
              console.error('导入变量到服务器失败:', importError);
              enqueueSnackbar(t('flowVariables.importError'), { variant: 'error' });
            } finally {
              setLoading(false);
            }
          } else {
            enqueueSnackbar(t('flowVariables.invalidFormat'), { variant: 'error' });
          }
        }
      } catch (error) {
        enqueueSnackbar(t('flowVariables.loadError'), { variant: 'error' });
        console.error("Error loading variables:", error);
      }
    };
    reader.onerror = () => {
      enqueueSnackbar(t('flowVariables.readError'), { variant: 'error' });
    };
    reader.readAsText(file);
  }, [enqueueSnackbar, t, currentFlowId]);

  /**
   * 保存变量到本地文件
   */
  const saveVariablesToFile = useCallback(() => {
    const jsonString = JSON.stringify(variables, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    saveAs(blob, `flow_variables_${currentFlowId}.json`);
    enqueueSnackbar(t('flowVariables.saveFileSuccess'), { variant: 'success' });
  }, [variables, enqueueSnackbar, t, currentFlowId]);

  /**
   * 获取变量值
   * @param {string} name - 变量名
   * @returns {string | undefined} - 变量值
   */
  const getVariable = (name: string): string | undefined => {
    return variables[name];
  };

  /**
   * 设置变量值
   * @param {string} name - 变量名
   * @param {string} value - 变量值
   */
  const setVariable = (name: string, value: string): void => {
    setVariables({ ...variables, [name]: value });
  };

  /**
   * 处理变量值变化
   * @param {string} name - 变量名
   * @param {string} value - 新的变量值
   */
  const handleVariableChange = (name: string, value: string): void => {
    setVariable(name, value);
  };

  /**
   * 添加新变量
   */
  const handleAddVariable = (): void => {
    if (newVariableName && !variables[newVariableName]) {
      setVariable(newVariableName, '');
      setNewVariableName('');
    } else if (variables[newVariableName]) {
      enqueueSnackbar(t('flowVariables.duplicateName'), { variant: 'error' });
    } else {
      enqueueSnackbar(t('flowVariables.emptyName'), { variant: 'warning' });
    }
  };

  /**
   * 删除变量
   * @param {string} name - 要删除的变量名
   */
  const handleDeleteVariable = async (name: string): Promise<void> => {
    if (!currentFlowId) {
      enqueueSnackbar(t('flowVariables.noActiveFlow'), { variant: 'warning' });
      return;
    }

    try {
      setLoading(true);
      await deleteFlowVariable(currentFlowId, name);
      
      // 更新本地状态
      const { [name]: deleted, ...newVariables } = variables;
      setVariables(newVariables);
      
      enqueueSnackbar(t('flowVariables.deleteSuccess', { name }), { variant: 'success' });
    } catch (error) {
      console.error(`删除变量 ${name} 失败:`, error);
      enqueueSnackbar(t('flowVariables.deleteError', { name }), { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  /**
   * 处理文件上传
   * @param {React.ChangeEvent<HTMLInputElement>} event - 上传事件
   */
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0];
    if (file) {
      loadVariables(file);
    }
  };

  // 如果没有活动流程图，显示提示信息
  if (!currentFlowId) {
    return (
      <Box sx={{ padding: 2 }}>
        <Typography variant="h6">{t('flowVariables.title')}</Typography>
        <Divider sx={{ my: 2 }} />
        <Typography>{t('flowVariables.noActiveFlow')}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, borderBottom: '1px solid rgba(0, 0, 0, 0.12)' }}>
        <Typography variant="h6" gutterBottom>
          {t('flowVariables.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          {t('flowVariables.description')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          <Button 
            variant="contained" 
            color="primary" 
            startIcon={<SaveIcon />} 
            onClick={saveVariablesToServer}
            disabled={loading}
          >
            {t('flowVariables.save')}
          </Button>
          <Button 
            variant="outlined" 
            color="secondary" 
            size="small" 
            onClick={handleResetVariables}
            disabled={loading}
            startIcon={<RefreshIcon />}
          >
            {t('flowVariables.reset')}
          </Button>
          <input
            accept=".json"
            style={{ display: 'none' }}
            id="contained-button-file"
            type="file"
            onChange={handleFileUpload}
          />
          <label htmlFor="contained-button-file">
            <Button 
              variant="outlined" 
              component="span" 
              size="small" 
              disabled={loading}
              startIcon={<UploadIcon />}
            >
              {t('flowVariables.import')}
            </Button>
          </label>
          <Button 
            variant="outlined" 
            size="small" 
            onClick={saveVariablesToFile}
            disabled={Object.keys(variables).length === 0 || loading}
          >
            {t('flowVariables.export')}
          </Button>
        </Box>
      </Box>
      
      {/* 变量添加表单 */}
      <Box sx={{ p: 2, borderBottom: '1px solid rgba(0, 0, 0, 0.12)' }}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            label={t('flowVariables.variableName')}
            value={newVariableName}
            onChange={(e) => setNewVariableName(e.target.value)}
            size="small"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleAddVariable();
              }
            }}
            fullWidth
          />
          <Button
            variant="contained"
            color="primary"
            onClick={handleAddVariable}
            startIcon={<AddIcon />}
            disabled={loading}
          >
            {t('flowVariables.add')}
          </Button>
        </Box>
      </Box>

      <List sx={{ width: '100%', bgcolor: 'background.paper', mt: 2 }}>
        {Object.entries(variables).map(([name, value]) => (
          <ListItem
            key={name}
            secondaryAction={
              <IconButton edge="end" aria-label="delete" onClick={() => handleDeleteVariable(name)} disabled={loading}>
                <DeleteIcon />
              </IconButton>
            }
          >
            <ListItemText
              primary={
                <TextField
                  label={t('flowVariables.variableValue')}
                  variant="outlined"
                  size="small"
                  value={value || ''}
                  onChange={(e) => handleVariableChange(name, e.target.value)}
                  fullWidth
                  disabled={loading}
                />
              }
              secondary={name}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

export default FlowVariables; 