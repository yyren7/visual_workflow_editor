// visual_workflow_editor/frontend/src/components/NodeSelector.tsx
import React, { useState, useEffect } from 'react';
import { Box, List, ListItem, ListItemText, CircularProgress, Typography, Alert } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { getNodeTemplates, NodeTemplate } from '../api/nodeTemplates';

// 节点类型定义接口（保留向后兼容）
export interface NodeTypeInfo {
  id: string;
  label: string;
  description?: string;
  fields?: any[];
  inputs?: any[];
  outputs?: any[];
  type?: string;
}

// 组件属性接口
interface NodeSelectorProps {
  onNodeSelect?: (nodeType: NodeTypeInfo) => void;
}

/**
 * NodeSelector Component
 *
 * 此组件显示可添加到流程图的节点类型列表。
 * 通过API从后端获取动态节点模板。
 */
const NodeSelector: React.FC<NodeSelectorProps> = ({ onNodeSelect = () => {} }) => {
  const { t } = useTranslation();
  const [nodeTemplates, setNodeTemplates] = useState<NodeTemplate[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // 在组件加载时获取节点模板
  useEffect(() => {
    const fetchNodeTemplates = async () => {
      try {
        setLoading(true);
        const templatesResponse = await getNodeTemplates();
        // 将响应对象转换为数组
        const templatesArray = Object.values(templatesResponse);
        console.log('【调试】从API获取的节点模板:', templatesResponse);
        console.log('【调试】转换为数组后的节点模板:', templatesArray);
        setNodeTemplates(templatesArray);
        setError(null);
      } catch (err) {
        console.error('【调试】获取节点模板失败:', err);
        setError(t('nodeSelector.loadError'));
      } finally {
        setLoading(false);
      }
    };
    
    fetchNodeTemplates();
  }, [t]);
  
  /**
   * 获取可用的节点类型（备用方法）
   * 如果API加载失败，使用这个备用节点列表
   * @returns {Array<NodeTypeInfo>} - 节点类型对象数组
   */
  const getFallbackNodeTypes = (): NodeTypeInfo[] => {
    return [
      {
        id: 'input',
        label: t('nodeTypes.input'),
      },
      {
        id: 'output',
        label: t('nodeTypes.output'),
      },
      {
        id: 'process',
        label: t('nodeTypes.process'),
      },
      {
        id: 'decision',
        label: t('nodeTypes.decision'),
      },
    ];
  };

  /**
   * 将NodeTemplate转换为NodeTypeInfo
   * 保持与现有代码的兼容性
   * @param template 节点模板
   * @returns 节点类型信息
   */
  const convertTemplateToNodeType = (template: NodeTemplate): NodeTypeInfo => {
    console.log('【调试】开始转换模板:', template);
    const nodeType = {
      id: template.id,
      label: template.label,
      description: template.description,
      type: template.type,
      fields: template.fields,
      inputs: template.inputs,
      outputs: template.outputs
    };
    console.log('【调试】转换后的节点类型:', nodeType);
    return nodeType;
  };

  /**
   * 拖拽开始处理函数
   * @param event 拖拽事件
   * @param nodeType 节点类型
   */
  const onDragStart = (event: React.DragEvent<HTMLLIElement>, nodeType: NodeTypeInfo): void => {
    // 确保事件正确触发并设置数据
    console.log(t('nodeDrag.start'), nodeType.id);
    
    // 将整个节点类型对象序列化传递，而不仅仅是id
    event.dataTransfer.setData('application/reactflow-node', JSON.stringify(nodeType));
    event.dataTransfer.effectAllowed = 'move';
    
    // 添加拖拽时的视觉反馈
    if (event.currentTarget.classList) {
      event.currentTarget.classList.add('dragging');
    }
    
    // 设置拖拽图像以提高用户体验
    const dragImage = document.createElement('div');
    dragImage.textContent = nodeType.label;
    dragImage.style.backgroundColor = '#1976d2';
    dragImage.style.color = 'white';
    dragImage.style.padding = '10px';
    dragImage.style.borderRadius = '4px';
    dragImage.style.position = 'absolute';
    dragImage.style.top = '-1000px';
    document.body.appendChild(dragImage);
    
    try {
      event.dataTransfer.setDragImage(dragImage, 0, 0);
    } catch (error) {
      console.error('设置拖拽图像失败:', error);
    }
    
    // 延迟移除辅助元素
    setTimeout(() => {
      document.body.removeChild(dragImage);
    }, 0);
  };

  // 添加拖拽结束事件处理函数
  const onDragEnd = (event: React.DragEvent<HTMLLIElement>): void => {
    console.log(t('nodeDrag.end'));
    if (event.currentTarget.classList) {
      event.currentTarget.classList.remove('dragging');
    }
  };

  // 显示加载状态
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
        <CircularProgress />
      </Box>
    );
  }

  // 显示错误状态
  if (error) {
    console.warn('Using fallback node types due to error:', error);
    // 如果出错，使用备用节点类型列表
    return (
      <Box sx={{ width: '100%' }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <nav aria-label="node types">
          <List>
            {getFallbackNodeTypes().map((nodeType) => (
              <ListItem
                key={nodeType.id}
                disablePadding
                draggable={true}
                onDragStart={(event) => onDragStart(event, nodeType)}
                onDragEnd={onDragEnd}
                onClick={() => onNodeSelect(nodeType)}
                sx={{
                  cursor: 'grab',
                  padding: '8px 16px',
                  margin: '4px 0',
                  border: '1px dashed rgba(255, 255, 255, 0.3)',
                  borderRadius: '4px',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    border: '1px solid rgba(255, 255, 255, 0.6)',
                  },
                  '&.dragging': {
                    opacity: 0.5,
                    backgroundColor: 'rgba(255, 255, 255, 0.15)',
                  }
                }}
              >
                <ListItemText
                  primary={nodeType.label}
                  secondary={t('nodeTypes.dragHint')}
                  primaryTypographyProps={{
                    fontWeight: 'bold',
                    color: 'white'
                  }}
                  secondaryTypographyProps={{
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '0.75rem'
                  }}
                />
              </ListItem>
            ))}
          </List>
        </nav>
      </Box>
    );
  }

  // 没有模板时显示提示
  if (nodeTemplates.length === 0) {
    return (
      <Box sx={{ padding: 2 }}>
        <Typography color="text.secondary">
          {t('nodeSelector.noTemplates')}
        </Typography>
      </Box>
    );
  }

  // 正常渲染节点模板列表
  return (
    <Box sx={{ width: '100%', bgcolor: 'transparent' }}>
      <nav aria-label="node types">
        <List>
          {nodeTemplates.map((template) => {
            const nodeType = convertTemplateToNodeType(template);
            return (
              <ListItem
                key={nodeType.id}
                disablePadding
                draggable={true}
                onDragStart={(event) => onDragStart(event, nodeType)}
                onDragEnd={onDragEnd}
                onClick={() => onNodeSelect(nodeType)}
                sx={{
                  cursor: 'grab',
                  padding: '8px 16px',
                  margin: '4px 0',
                  border: '1px dashed rgba(255, 255, 255, 0.3)',
                  borderRadius: '4px',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    border: '1px solid rgba(255, 255, 255, 0.6)',
                  },
                  '&.dragging': {
                    opacity: 0.5,
                    backgroundColor: 'rgba(255, 255, 255, 0.15)',
                  }
                }}
              >
                <ListItemText
                  primary={nodeType.label}
                  secondary={nodeType.description || t('nodeTypes.dragHint')}
                  primaryTypographyProps={{
                    fontWeight: 'bold',
                    color: 'white'
                  }}
                  secondaryTypographyProps={{
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '0.75rem'
                  }}
                />
              </ListItem>
            );
          })}
        </List>
      </nav>
    </Box>
  );
};

export default NodeSelector;