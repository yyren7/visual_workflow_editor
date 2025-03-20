// frontend/src/components/nodes/ProcessNode.tsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card, CardContent, Typography, TextField, Stack } from '@mui/material';
import { NodeData } from '../FlowEditor';

interface ProcessNodeProps {
  data: NodeData;
  selected?: boolean;
  isConnectable: boolean;
}

const ProcessNode: React.FC<ProcessNodeProps> = ({ data, selected = false, isConnectable }) => {
  // 获取或设置字段值的处理函数
  const getFieldValue = (fieldName: string, defaultValue: string = '') => {
    return data[fieldName] || defaultValue;
  };

  // 更新字段值的处理函数
  const handleFieldChange = (fieldName: string, value: string) => {
    // 使用类型保护确保data.updateNodeData是函数
    if (typeof data.updateNodeData === 'function') {
      data.updateNodeData({
        id: data.id,
        data: {
          ...data,
          [fieldName]: value,
        },
      });
    }
  };

  return (
    <div>
      <Handle
        type="target"
        position={Position.Top}
        id="target"
        style={{ background: '#4d70ff', width: '10px', height: '10px' }}
        isConnectable={isConnectable}
      />
      <Card 
        sx={{ 
          minWidth: selected ? 180 : 120,
          maxWidth: selected ? 'none' : 150,
          bgcolor: '#2d2d2d',
          color: '#fff',
          borderRadius: '4px',
          border: '2px solid #00bcd4',
          boxShadow: selected ? '0 0 0 2px #00bcd4, 0 2px 8px rgba(0, 188, 212, 0.4)' : 'none',
          transition: 'all 0.3s ease',
          transform: selected ? 'scale(1)' : 'scale(0.9)',
          '&:hover': {
            boxShadow: '0 0 0 2px #00bcd4, 0 4px 8px rgba(0, 188, 212, 0.6)',
            transform: selected ? 'scale(1)' : 'scale(0.95)'
          }
        }}
      >
        <CardContent 
          sx={{ 
            padding: selected ? '12px' : '8px',
            '&:last-child': { paddingBottom: selected ? '12px' : '8px' },
            transition: 'all 0.3s ease'
          }}
        >
          <Typography 
            variant="h6" 
            sx={{ 
              fontSize: selected ? '14px' : '12px', 
              fontWeight: 'bold', 
              color: '#00bcd4',
              mb: selected ? 1 : 0.5
            }}
          >
            {data.label}
          </Typography>
          
          {selected ? (
            <Stack spacing={1} mt={1}>
              <TextField
                label="参数1"
                size="small"
                value={getFieldValue('param1', '')}
                onChange={(e) => handleFieldChange('param1', e.target.value)}
                variant="outlined"
                fullWidth
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': {
                      borderColor: 'rgba(255, 255, 255, 0.23)',
                    },
                    '&:hover fieldset': {
                      borderColor: 'rgba(255, 255, 255, 0.23)',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: '#00bcd4',
                    },
                  },
                  '& .MuiInputLabel-root': {
                    color: 'rgba(255, 255, 255, 0.7)',
                  },
                  '& .MuiInputLabel-root.Mui-focused': {
                    color: '#00bcd4',
                  },
                }}
              />
              <TextField
                label="参数2"
                size="small"
                value={getFieldValue('param2', '')}
                onChange={(e) => handleFieldChange('param2', e.target.value)}
                variant="outlined"
                fullWidth
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': {
                      borderColor: 'rgba(255, 255, 255, 0.23)',
                    },
                    '&:hover fieldset': {
                      borderColor: 'rgba(255, 255, 255, 0.23)',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: '#00bcd4',
                    },
                  },
                  '& .MuiInputLabel-root': {
                    color: 'rgba(255, 255, 255, 0.7)',
                  },
                  '& .MuiInputLabel-root.Mui-focused': {
                    color: '#00bcd4',
                  },
                }}
              />
            </Stack>
          ) : (
            data.description && (
              <Typography 
                variant="body2" 
                sx={{ 
                  fontSize: '10px',
                  color: 'rgba(255, 255, 255, 0.7)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical'
                }}
              >
                {data.description}
              </Typography>
            )
          )}
        </CardContent>
      </Card>
      <Handle
        type="source"
        position={Position.Bottom}
        id="source"
        style={{ background: '#4d70ff', width: '10px', height: '10px' }}
        isConnectable={isConnectable}
      />
    </div>
  );
};

export default memo(ProcessNode);