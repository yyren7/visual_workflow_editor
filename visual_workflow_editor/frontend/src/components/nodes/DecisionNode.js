// frontend/src/components/nodes/DecisionNode.js
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';

const DecisionNode = ({ data }) => {
  return (
    <Card sx={{ minWidth: 150, border: '1px solid #9c27b0' }}>
      <CardContent>
        <Typography variant="h6" component="div" sx={{ fontSize: 14, fontWeight: 'bold', color: '#9c27b0' }}>
          {data.label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {data.description || '决策节点'}
        </Typography>
        <Handle type="target" position={Position.Top} id="target" />
        <Handle type="source" position={Position.Bottom} id="source-true" style={{ left: '25%' }} />
        <Handle type="source" position={Position.Bottom} id="source-false" style={{ left: '75%' }} />
        <div style={{ fontSize: 10, position: 'absolute', bottom: 2, left: '20%' }}>是</div>
        <div style={{ fontSize: 10, position: 'absolute', bottom: 2, left: '70%' }}>否</div>
      </CardContent>
    </Card>
  );
};

export default memo(DecisionNode);