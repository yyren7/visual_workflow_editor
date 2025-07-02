import React from 'react';
import { Box, Button } from '@mui/material';
import { FlowDebugPanelProps } from './types';

const FlowDebugPanel: React.FC<FlowDebugPanelProps> = ({
  currentFlowId,
  agentState,
  nodes,
  onDebugAgentState
}) => {
  // 只在开发环境显示
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  return (
    <Box sx={{ 
      position: 'absolute', 
      top: 80, 
      right: 20, 
      zIndex: 1000,
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      p: 1,
      borderRadius: 1,
      border: '1px solid #ccc'
    }}>
      <Button
        variant="outlined"
        size="small"
        onClick={onDebugAgentState}
        sx={{ fontSize: '0.75rem', minWidth: 'auto', px: 1 }}
      >
        🐛 调试Agent状态
      </Button>
    </Box>
  );
};

export default FlowDebugPanel; 