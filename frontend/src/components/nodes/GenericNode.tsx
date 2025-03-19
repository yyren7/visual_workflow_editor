import React, { memo, useCallback } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, CardContent, Typography, Box, Tooltip } from '@mui/material';

/**
 * 通用节点数据接口
 * 定义从节点模板动态生成的节点数据结构
 */
export interface GenericNodeData {
  /** 节点显示标签 */
  label: string;
  /** 节点描述信息 */
  description?: string;
  /** 节点字段列表 */
  fields: Array<{
    /** 字段名称 */
    name: string;
    /** 字段值 */
    value: any;
    /** 字段类型 */
    type?: string;
  }>;
  /** 输入连接点列表 */
  inputs?: Array<{
    /** 连接点ID */
    id: string;
    /** 连接点标签 */
    label: string;
    /** 连接点位置，0-1之间的值 */
    position?: number;
  }>;
  /** 输出连接点列表 */
  outputs?: Array<{
    /** 连接点ID */
    id: string;
    /** 连接点标签 */
    label: string;
    /** 连接点位置，0-1之间的值 */
    position?: number;
  }>;
  /** 节点类型标识 */
  type: string;
  /** 其他可能的属性 */
  [key: string]: any;
}

/**
 * 通用节点组件
 * 用于动态渲染不同类型的节点
 * 
 * @param props 节点属性，包含节点数据和连接状态
 * @returns React节点组件
 */
const GenericNode = memo(({ data, isConnectable, selected }: NodeProps<GenericNodeData>) => {
  // 处理字段值的显示转换
  const formatFieldValue = useCallback((value: any, type?: string) => {
    if (value === undefined || value === null) return 'none';
    
    // 根据字段类型格式化显示
    if (type === 'boolean') {
      if (typeof value === 'string') {
        const lowerValue = value.toLowerCase();
        if (['true', 'enable', 'on'].includes(lowerValue)) return '✓';
        if (['false', 'disable', 'off'].includes(lowerValue)) return '✗';
      }
      return value ? '✓' : '✗';
    }
    
    return String(value);
  }, []);
  
  // 动态渲染输入连接点
  const renderInputHandles = useCallback(() => {
    if (!data.inputs || data.inputs.length === 0) {
      // 默认至少有一个输入，位于节点左侧中央
      return (
        <Handle
          type="target"
          position={Position.Left}
          id="input"
          style={{ 
            background: '#2196f3',
            width: '12px',
            height: '12px',
            left: '-6px', // 调整左边距，使其始终处于左侧
            top: '50%', // 显式设置为50%
            transform: 'translateY(-50%)', // 垂直居中
            border: '2px solid #1976d2',
            transition: 'all 0.2s ease',
            borderRadius: '6px'
          }}
          isConnectable={isConnectable}
        />
      );
    }
    
    return data.inputs.map((input, index) => {
      // 计算连接点位置，确保均匀分布
      let yPosition;
      
      if (input.position !== undefined) {
        yPosition = input.position;
      } else if (data.inputs && data.inputs.length > 1) {
        // 如果有多个输入点，均匀分布
        const offset = 1.0 / (data.inputs.length + 1);
        yPosition = offset + index * offset;
      } else {
        // 单个输入点放在中间
        yPosition = 0.5;
      }
      
      const topPosition = `${yPosition * 100}%`;
      
      return (
        <Tooltip key={input.id} title={input.label} placement="left">
          <Handle
            type="target"
            position={Position.Left}
            id={input.id}
            style={{ 
              background: '#2196f3',
              width: '12px',
              height: '12px',
              left: '-6px', // 调整左边距，使其始终处于左侧
              top: topPosition,
              transform: 'translateY(-50%)', // 垂直居中
              border: '2px solid #1976d2',
              transition: 'all 0.2s ease',
              borderRadius: '6px',
              cursor: 'crosshair',
            }}
            isConnectable={isConnectable}
          />
        </Tooltip>
      );
    });
  }, [data.inputs, isConnectable]);
  
  // 动态渲染输出连接点
  const renderOutputHandles = useCallback(() => {
    if (!data.outputs || data.outputs.length === 0) {
      return null; // 如果没有输出连接点，不渲染
    }
    
    return data.outputs.map((output, index) => {
      // 计算连接点位置，确保均匀分布
      let yPosition;
      
      if (output.position !== undefined) {
        yPosition = output.position;
      } else if (data.outputs && data.outputs.length > 1) {
        // 如果有多个输出点，均匀分布
        const offset = 1.0 / (data.outputs.length + 1);
        yPosition = offset + index * offset;
      } else {
        // 单个输出点放在中间
        yPosition = 0.5;
      }
      
      const topPosition = `${yPosition * 100}%`;
      
      return (
        <Tooltip key={output.id} title={output.label} placement="right">
          <Handle
            type="source"
            position={Position.Right}
            id={output.id}
            style={{ 
              background: '#ff9800',
              width: '12px',
              height: '12px',
              right: '-6px', // 调整右边距，使其始终处于右侧
              top: topPosition,
              transform: 'translateY(-50%)', // 垂直居中
              border: '2px solid #f57c00',
              transition: 'all 0.2s ease',
              borderRadius: '6px',
              cursor: 'crosshair',
            }}
            isConnectable={isConnectable}
          />
        </Tooltip>
      );
    });
  }, [data.outputs, isConnectable]);

  // 渲染节点卡片
  return (
    <>
      {renderInputHandles()}
      <Card 
        sx={{ 
          minWidth: 180, 
          border: selected ? '2px solid #1976d2' : '1px solid #555',
          borderRadius: '8px',
          boxShadow: selected ? '0 0 10px rgba(25, 118, 210, 0.5)' : '0 2px 5px rgba(0, 0, 0, 0.2)',
          backgroundColor: selected ? 'rgba(25, 118, 210, 0.08)' : 'rgba(45, 45, 45, 1)',
          transition: 'all 0.2s ease',
          '&:hover': {
            boxShadow: '0 4px 8px rgba(0, 0, 0, 0.3)',
            border: '1px solid rgba(255, 255, 255, 0.2)'
          }
        }}
      >
        <CardContent sx={{ p: 2 }}>
          <Typography variant="h6" component="div" gutterBottom sx={{ 
            fontSize: '1rem', 
            fontWeight: 'bold',
            color: selected ? '#fff' : '#eee'
          }}>
            {data.label}
          </Typography>
          {data.description && (
            <Typography variant="body2" color={selected ? "text.secondary" : "rgba(255, 255, 255, 0.7)"} sx={{ fontSize: '0.8rem', mb: 1 }}>
              {data.description}
            </Typography>
          )}
          {data.fields && data.fields.length > 0 && (
            <Box sx={{ mt: 1 }}>
              {data.fields.map((field, index) => (
                <Typography 
                  key={index} 
                  variant="body2" 
                  sx={{ 
                    fontSize: '0.8rem', 
                    display: 'flex', 
                    justifyContent: 'space-between',
                    borderBottom: '1px dotted rgba(255, 255, 255, 0.1)',
                    py: 0.5,
                    color: 'rgba(255, 255, 255, 0.9)'
                  }}
                >
                  <span style={{ fontWeight: 'bold', color: 'rgba(255, 255, 255, 0.8)' }}>{field.name}:</span> 
                  <span>{formatFieldValue(field.value, field.type)}</span>
                </Typography>
              ))}
            </Box>
          )}
          {data.type && (
            <Typography 
              variant="caption" 
              sx={{ 
                display: 'block', 
                mt: 1, 
                color: 'rgba(255, 255, 255, 0.5)',
                fontSize: '0.7rem',
                textAlign: 'right'
              }}
            >
              {data.type}
            </Typography>
          )}
        </CardContent>
      </Card>
      {renderOutputHandles()}
    </>
  );
});

export default GenericNode; 