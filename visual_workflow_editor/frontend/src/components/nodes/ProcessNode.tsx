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
    <Card sx={{ minWidth: 150, border: '1px solid #009688' }}>
      <CardContent>
        <Typography variant="h6" component="div" sx={{ fontSize: 14, fontWeight: 'bold', color: '#009688' }}>
          {data.label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {data.description || '数据处理节点'}
        </Typography>
        <Handle type="target" position={Position.Top} id="target" />
        <Handle type="source" position={Position.Bottom} id="source" />
      </CardContent>
    </Card>
  );
};

export default memo(ProcessNode);