// frontend/src/components/nodes/OutputNode.js
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';

const OutputNode = ({ data }) => {
  return (
    <Card sx={{ minWidth: 150, border: '1px solid #f44336' }}>
      <CardContent>
        <Typography variant="h6" component="div" sx={{ fontSize: 14, fontWeight: 'bold', color: '#f44336' }}>
          {data.label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {data.description || '输出数据节点'}
        </Typography>
        <Handle type="target" position={Position.Top} id="target" />
      </CardContent>
    </Card>
  );
};

export default memo(OutputNode);