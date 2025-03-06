// frontend/src/components/nodes/ProcessNode.tsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';
import { NodeData } from '../FlowEditor';

interface ProcessNodeProps {
  data: NodeData & {
    description?: string;
  };
}

const ProcessNode: React.FC<ProcessNodeProps> = ({ data }) => {
  return (
    <div className="react-flow__node-process" style={{ border: 'none', background: 'transparent', padding: 0 }}>
      <Card sx={{ 
        minWidth: 150, 
        border: '1px solid #009688',
        borderRadius: '4px',
        backgroundColor: '#1e1e1e',
        boxShadow: 'none',
        overflow: 'visible'
      }}>
        <CardContent sx={{ 
          padding: '10px',
          paddingBottom: '10px !important', // 覆盖CardContent最后一个子元素的padding-bottom
          '&:last-child': { paddingBottom: '10px' }
        }}>
          <Typography variant="h6" component="div" sx={{ fontSize: 14, fontWeight: 'bold', color: '#009688' }}>
            {data.label}
          </Typography>
          <Typography variant="body2" sx={{ color: '#aaa' }}>
            {data.description || 'process'}
          </Typography>
          <Handle type="target" position={Position.Top} id="target" />
          <Handle type="source" position={Position.Bottom} id="source" />
        </CardContent>
      </Card>
    </div>
  );
};

export default memo(ProcessNode);