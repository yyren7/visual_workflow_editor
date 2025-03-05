// frontend/src/components/nodes/InputNode.js
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';

const InputNode = ({ data }) => {
  return (
    <Card sx={{ minWidth: 150, border: '1px solid #1976d2' }}>
      <CardContent>
        <Typography variant="h6" component="div" sx={{ fontSize: 14, fontWeight: 'bold', color: '#1976d2' }}>
          {data.label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {data.description || '输入数据节点'}
        </Typography>
        <Handle type="source" position={Position.Bottom} id="source" />
      </CardContent>
    </Card>
  );
};

export default memo(InputNode);