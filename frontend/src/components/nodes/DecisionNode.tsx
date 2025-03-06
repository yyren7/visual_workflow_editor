// frontend/src/components/nodes/DecisionNode.tsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography } from '@mui/material';
import { NodeData } from '../FlowEditor';

interface DecisionNodeProps {
  data: NodeData & {
    description?: string;
  };
}

const DecisionNode: React.FC<DecisionNodeProps> = ({ data }) => {
  return (
    <div className="react-flow__node-decision" style={{ border: 'none', background: 'transparent', padding: 0 }}>
      <Card sx={{ 
        minWidth: 150, 
        border: '1px solid #9c27b0',
        borderRadius: '4px',
        backgroundColor: '#1e1e1e',
        boxShadow: 'none',
        overflow: 'visible',
        position: 'relative'
      }}>
        <CardContent sx={{ 
          padding: '10px',
          paddingBottom: '10px !important', // 覆盖CardContent最后一个子元素的padding-bottom
          '&:last-child': { paddingBottom: '10px' }
        }}>
          <Typography variant="h6" component="div" sx={{ fontSize: 14, fontWeight: 'bold', color: '#9c27b0' }}>
            {data.label}
          </Typography>
          <Typography variant="body2" sx={{ color: '#aaa' }}>
            {data.description || 'decision'}
          </Typography>
          <Handle type="target" position={Position.Top} id="target" />
          <Handle type="source" position={Position.Bottom} id="source-true" style={{ left: '25%' }} />
          <Handle type="source" position={Position.Bottom} id="source-false" style={{ left: '75%' }} />
          <div style={{ fontSize: 10, position: 'absolute', bottom: 2, left: '20%', color: '#fff' }}>yes</div>
          <div style={{ fontSize: 10, position: 'absolute', bottom: 2, left: '70%', color: '#fff' }}>no</div>
        </CardContent>
      </Card>
    </div>
  );
};

export default memo(DecisionNode);