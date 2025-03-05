// frontend/src/components/NodeSelector.js
import React from 'react';
import { Box, List, ListItem, ListItemText } from '@mui/material';
import PropTypes from 'prop-types';

const nodeTypes = [
  {
    id: 'input',
    label: 'Input Node',
  },
  {
    id: 'output',
    label: 'Output Node',
  },
  {
    id: 'process',
    label: 'Process Node',
  },
  {
    id: 'decision',
    label: 'Decision Node',
  },
];

/**
 * NodeSelector Component
 *
 * This component displays a list of available node types that can be added to the flow.
 * It provides a method to retrieve the available node types.
 */
const NodeSelector = ({ onNodeSelect }) => {
  /**
   * Gets the available node types.
   * @returns {Array<object>} - An array of node type objects.
   */
  const getNodeTypes = () => {
    return nodeTypes;
  };

  const onDragStart = (event, nodeType) => {
    // 确保事件正确触发并设置数据
    console.log('拖拽开始:', nodeType.id);
    event.dataTransfer.setData('application/reactflow-node', nodeType.id);
    event.dataTransfer.effectAllowed = 'move';
    
    // 添加拖拽时的视觉反馈
    if (event.target.classList) {
      event.target.classList.add('dragging');
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
  const onDragEnd = (event) => {
    console.log('拖拽结束');
    if (event.target.classList) {
      event.target.classList.remove('dragging');
    }
  };

  return (
    <Box sx={{ width: '100%', bgcolor: 'background.paper' }}>
      <nav aria-label="node types">
        <List>
          {getNodeTypes().map((nodeType) => (
            <ListItem
              key={nodeType.id}
              disablePadding
              draggable={true}
              onDragStart={(event) => onDragStart(event, nodeType)}
              onDragEnd={onDragEnd}
              sx={{
                cursor: 'grab',
                padding: '8px 16px',
                margin: '4px 0',
                border: '1px dashed #aaa',
                borderRadius: '4px',
                '&:hover': {
                  backgroundColor: 'rgba(25, 118, 210, 0.08)',
                  border: '1px solid #1976d2',
                },
                '&.dragging': {
                  opacity: 0.5,
                  backgroundColor: 'rgba(25, 118, 210, 0.12)',
                }
              }}
              >
              <ListItemText
                primary={nodeType.label}
                secondary="拖拽至流程图"
                primaryTypographyProps={{
                  fontWeight: 'bold'
                }}
              />
            </ListItem>
          ))}
        </List>
      </nav>
    </Box>
  );
};

NodeSelector.propTypes = {
  onNodeSelect: PropTypes.func, // 改为可选prop
};

NodeSelector.defaultProps = {
  onNodeSelect: () => {}, // 提供默认空函数
};

export default NodeSelector;
