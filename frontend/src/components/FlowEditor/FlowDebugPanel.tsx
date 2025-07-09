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

  // 直接检查SAS状态的函数
  const debugSASState = async () => {
    if (!currentFlowId) {
      console.log('🔧 [DEBUG] No currentFlowId available');
      return;
    }

    try {
      console.log('🔧 [DEBUG] Fetching SAS state for flowId:', currentFlowId);
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${currentFlowId}/state`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });

      console.log('🔧 [DEBUG] SAS state response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('🔧 [DEBUG] Raw SAS response:', data);
        console.log('🔧 [DEBUG] Response type:', typeof data);
        console.log('🔧 [DEBUG] Response keys:', Object.keys(data || {}));
        
        let stateValues = null;
        if (data && Array.isArray(data)) {
          console.log('🔧 [DEBUG] Response is array, length:', data.length);
          // LangGraph StateSnapshot的第0个元素包含状态数据
          if (data.length > 0 && data[0] && typeof data[0] === 'object') {
            console.log('🔧 [DEBUG] Using data[0] as state values');
            console.log('🔧 [DEBUG] data[0] keys:', Object.keys(data[0]));
            console.log('🔧 [DEBUG] data[0] content:', data[0]);
            stateValues = data[0];
          } else {
            console.log('🔧 [DEBUG] Array[0] is not valid state object');
          }
        } else if (data && data.values) {
          console.log('🔧 [DEBUG] Values found:', data.values);
          console.log('🔧 [DEBUG] Values type:', typeof data.values);
          console.log('🔧 [DEBUG] Values keys:', Object.keys(data.values || {}));
          
          if (typeof data.values === 'function') {
            console.log('🔧 [DEBUG] data.values is a function, calling it...');
            stateValues = data.values();
          } else {
            stateValues = data.values;
          }
        } else {
          console.log('🔧 [DEBUG] ❌ No values field found in response');
          stateValues = data;
        }
        
        if (stateValues) {
          console.log('🔧 [DEBUG] Final state values:', stateValues);
          console.log('🔧 [DEBUG] Final state values keys:', Object.keys(stateValues));
          
          if (stateValues.sas_step1_generated_tasks) {
            console.log('🔧 [DEBUG] ✅ Found sas_step1_generated_tasks:', stateValues.sas_step1_generated_tasks);
          } else {
            console.log('🔧 [DEBUG] ❌ No sas_step1_generated_tasks found');
          }
          
          console.log('🔧 [DEBUG] Dialog state:', stateValues.dialog_state);
          console.log('🔧 [DEBUG] Current user request:', stateValues.current_user_request);
          console.log('🔧 [DEBUG] Task list accepted:', stateValues.task_list_accepted);
        } else {
          console.log('🔧 [DEBUG] ❌ No state values extracted');
        }
      } else {
        console.log('🔧 [DEBUG] ❌ Response not ok:', response.statusText);
      }
    } catch (error) {
      console.error('🔧 [DEBUG] ❌ Error fetching SAS state:', error);
    }
  };

  return (
    <Box sx={{ 
      position: 'absolute', 
      top: 80, 
      right: 20, 
      zIndex: 1000,
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      p: 1,
      borderRadius: 1,
      border: '1px solid #ccc',
      display: 'flex',
      flexDirection: 'column',
      gap: 1
    }}>
      <Button
        variant="outlined"
        size="small"
        onClick={onDebugAgentState}
        sx={{ fontSize: '0.75rem', minWidth: 'auto', px: 1 }}
      >
        🐛 调试Agent状态
      </Button>
      <Button
        variant="outlined"
        size="small"
        onClick={debugSASState}
        sx={{ fontSize: '0.75rem', minWidth: 'auto', px: 1, backgroundColor: '#e3f2fd' }}
      >
        🔍 检查SAS状态
      </Button>
    </Box>
  );
};

export default FlowDebugPanel; 