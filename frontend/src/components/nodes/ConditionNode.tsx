import React, { memo, useLayoutEffect, useRef } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography, Switch, FormControlLabel } from '@mui/material';
import { NodeData } from '../FlowEditor';

interface ConditionNodeProps {
  data: NodeData & {
    CONDITION?: boolean;
    DESCRIPTION?: string;
  };
  selected?: boolean;
  isConnectable?: boolean;
}

// 获取父节点容器并修改其样式
const useNodeParentFix = (ref: React.RefObject<HTMLDivElement>) => {
  useLayoutEffect(() => {
    if (ref.current) {
      // 获取ReactFlow节点容器（通常是ref.current的父元素或祖先元素）
      const nodeElement = ref.current.closest('.react-flow__node');
      if (nodeElement) {
        // 移除ReactFlow节点的默认样式
        (nodeElement as HTMLElement).style.padding = '0';
        (nodeElement as HTMLElement).style.borderRadius = '0';
        (nodeElement as HTMLElement).style.backgroundColor = 'transparent';
        (nodeElement as HTMLElement).style.border = 'none';
        (nodeElement as HTMLElement).style.overflow = 'visible';
        (nodeElement as HTMLElement).style.display = 'flex';
        (nodeElement as HTMLElement).style.alignItems = 'center';
        (nodeElement as HTMLElement).style.justifyContent = 'center';
      }
    }
  }, [ref]);
};

const ConditionNode: React.FC<ConditionNodeProps> = ({ data, selected = false, isConnectable = true }) => {
  const nodeRef = useRef<HTMLDivElement>(null);
  
  // 应用节点父容器修复
  useNodeParentFix(nodeRef);
  
  // 处理条件切换
  const handleConditionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // 更新节点数据
    if (data && typeof data.updateNodeData === 'function') {
      data.updateNodeData({
        ...data,
        CONDITION: event.target.checked
      });
    }
  };
  
  return (
    <div ref={nodeRef} style={{ width: '100%', height: '100%' }}>
      <Card 
        sx={{
          minWidth: selected ? 180 : 120,
          maxWidth: selected ? 'none' : 150,
          border: '1px solid #555',
          borderRadius: '8px',
          boxShadow: selected ? '0 0 0 2px #1976d2, 0 2px 8px rgba(25, 118, 210, 0.4)' : '0 2px 5px rgba(0, 0, 0, 0.2)',
          backgroundColor: selected ? 'rgba(25, 118, 210, 0.08)' : 'rgba(45, 45, 45, 1)',
          transition: 'all 0.3s ease',
          transform: selected ? 'scale(1)' : 'scale(0.9)',
          '&:hover': {
            boxShadow: selected 
              ? '0 0 0 2px #1976d2, 0 4px 10px rgba(25, 118, 210, 0.5)' // 选中+悬停状态
              : '0 0 0 2px #1976d2, 0 4px 8px rgba(0, 0, 0, 0.3)', // 仅悬停状态
            backgroundColor: selected 
              ? 'rgba(25, 118, 210, 0.12)'  // 选中+悬停状态稍微加深背景
              : 'rgba(45, 45, 45, 1)',
            border: '1px solid transparent', // 使边框透明，由box-shadow显示边框效果
            transform: selected ? 'scale(1)' : 'scale(0.95)' // 悬停时稍微放大未选中节点
          }
        }}
      >
        <CardContent sx={{ 
          padding: selected ? '16px' : '12px', 
          '&:last-child': { paddingBottom: selected ? '16px' : '12px' },
          transition: 'all 0.3s ease'
        }}>
          <Typography 
            variant="h6" 
            component="div" 
            sx={{ 
              fontSize: selected ? '14px' : '12px', 
              fontWeight: 'bold', 
              color: '#fff', 
              marginBottom: selected ? '8px' : '4px',
              transition: 'all 0.3s ease'
            }}
          >
            {data.label || '条件判断'}
            {!selected && (
              <span style={{ 
                marginLeft: '6px', 
                color: data.CONDITION ? '#4caf50' : '#f44336',
                fontSize: '10px'
              }}>
                {data.CONDITION ? '✓' : '✗'}
              </span>
            )}
          </Typography>
          
          {selected && (
            <>
              <Typography 
                variant="body2" 
                sx={{ 
                  color: '#aaa', 
                  fontSize: '12px', 
                  marginBottom: '12px',
                  transition: 'all 0.3s ease'
                }}
              >
                {data.DESCRIPTION || '根据条件决定执行路径'}
              </Typography>
              
              <FormControlLabel
                control={
                  <Switch 
                    checked={data.CONDITION === undefined ? false : data.CONDITION} 
                    onChange={handleConditionChange}
                    color="primary"
                    size="small"
                  />
                }
                label={
                  <Typography variant="body2" sx={{ fontSize: '12px', color: '#ddd' }}>
                    {data.CONDITION ? '条件为真' : '条件为假'}
                  </Typography>
                }
                sx={{ marginBottom: 0 }}
              />
            </>
          )}
          
          {!selected && data.DESCRIPTION && (
            <Typography 
              variant="body2" 
              sx={{ 
                color: 'rgba(255, 255, 255, 0.7)', 
                fontSize: '10px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                transition: 'all 0.3s ease'
              }}
            >
              {data.DESCRIPTION}
            </Typography>
          )}
        </CardContent>
      </Card>
      
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Top}
        id="input"
        isConnectable={isConnectable}
        style={{ 
          background: '#1976d2',
          border: '2px solid #1976d2',
          width: '8px',
          height: '8px'
        }}
      />
      
      {/* 输出连接点 - True */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        isConnectable={isConnectable}
        style={{ 
          background: '#4caf50', // 绿色表示True
          border: '2px solid #4caf50',
          width: '8px',
          height: '8px',
          left: '30%'
        }}
      />
      
      {/* 输出连接点 - False */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        isConnectable={isConnectable}
        style={{ 
          background: '#f44336', // 红色表示False
          border: '2px solid #f44336',
          width: '8px',
          height: '8px',
          left: '70%'
        }}
      />
      
      {/* 连接点标签 */}
      <div style={{ 
        fontSize: '10px', 
        position: 'absolute', 
        bottom: '-20px', 
        left: '30%', 
        transform: 'translateX(-50%)', 
        color: '#4caf50'
      }}>
        True
      </div>
      <div style={{ 
        fontSize: '10px', 
        position: 'absolute', 
        bottom: '-20px', 
        left: '70%', 
        transform: 'translateX(-50%)', 
        color: '#f44336'
      }}>
        False
      </div>
    </div>
  );
};

export default memo(ConditionNode); 