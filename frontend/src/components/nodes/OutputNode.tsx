// frontend/src/components/nodes/OutputNode.tsx
import React, { memo, useLayoutEffect, useRef } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';
import { NodeData } from '../FlowEditor';

interface OutputNodeProps {
  data: NodeData & {
    description?: string;
  };
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

const OutputNode: React.FC<OutputNodeProps> = ({ data, isConnectable = true }) => {
  const nodeRef = useRef<HTMLDivElement>(null);
  
  // 应用节点父容器修复
  useNodeParentFix(nodeRef);
  
  return (
    <div ref={nodeRef} style={{ width: '100%', height: '100%' }}>
      <Card 
        sx={{
          width: '100%',
          height: '100%',
          backgroundColor: '#1e1e1e',
          color: 'white',
          borderRadius: '4px',
          border: '2px solid #f44336',
          boxShadow: 'none',
          position: 'relative',
          overflow: 'visible',
          '& .MuiCardContent-root': {
            padding: '8px',
            '&:last-child': { 
              paddingBottom: '8px' 
            }
          }
        }}
      >
        <CardContent>
          <Typography 
            variant="h6" 
            component="div" 
            sx={{ 
              fontSize: '14px', 
              fontWeight: 'bold', 
              color: '#f44336',
              marginBottom: '4px'
            }}
          >
            {data.label}
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ 
              color: '#aaa',
              fontSize: '12px'
            }}
          >
            {data.description || 'output'}
          </Typography>
        </CardContent>
      </Card>
      <Handle
        type="target"
        position={Position.Top}
        id="target"
        isConnectable={isConnectable}
        style={{ 
          background: '#f44336',
          border: '2px solid #f44336',
          width: '8px',
          height: '8px'
        }}
      />
    </div>
  );
};

export default memo(OutputNode);