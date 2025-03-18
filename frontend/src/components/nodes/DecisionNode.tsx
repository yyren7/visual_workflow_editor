// frontend/src/components/nodes/DecisionNode.tsx
import React, { memo, useLayoutEffect, useRef } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';
import { NodeData } from '../FlowEditor';

interface DecisionNodeProps {
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

const DecisionNode: React.FC<DecisionNodeProps> = ({ data, isConnectable = true }) => {
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
          border: '2px solid #9c27b0',
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
              color: '#9c27b0',
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
            {data.description || 'decision'}
          </Typography>
        </CardContent>
      </Card>
      <Handle
        type="target"
        position={Position.Top}
        id="target"
        isConnectable={isConnectable}
        style={{ 
          background: '#9c27b0',
          border: '2px solid #9c27b0',
          width: '8px',
          height: '8px'
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source-true"
        isConnectable={isConnectable}
        style={{ 
          background: '#9c27b0',
          border: '2px solid #9c27b0',
          width: '8px',
          height: '8px',
          left: '25%'
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source-false"
        isConnectable={isConnectable}
        style={{ 
          background: '#9c27b0',
          border: '2px solid #9c27b0',
          width: '8px',
          height: '8px',
          left: '75%'
        }}
      />
      <div style={{ 
        fontSize: '10px', 
        position: 'absolute', 
        bottom: '-20px', 
        left: '25%', 
        transform: 'translateX(-50%)', 
        color: '#fff'
      }}>
        yes
      </div>
      <div style={{ 
        fontSize: '10px', 
        position: 'absolute', 
        bottom: '-20px', 
        left: '75%', 
        transform: 'translateX(-50%)', 
        color: '#fff'
      }}>
        no
      </div>
    </div>
  );
};

export default memo(DecisionNode);