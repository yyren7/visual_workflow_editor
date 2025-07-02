import { Node } from 'reactflow';
import { ViewportConfig } from './types';

// LangGraph节点类型常量
export const LANGGRAPH_NODE_TYPES = ['langgraph_input', 'langgraph_task', 'langgraph_detail'];

/**
 * 计算动态视口配置
 * @param nodes 节点数组
 * @returns 视口配置
 */
export const calculateDynamicViewport = (nodes: Node[]): ViewportConfig => {
  if (!nodes || nodes.length === 0) {
    return {
      translateExtent: [[0, 0], [800, 600]],
      nodeExtent: [[0, 0], [800, 600]],
      minZoom: 0.1,
      maxZoom: 1.5
    };
  }

  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;

  // 计算所有节点的边界
  nodes.forEach(node => {
    const nodeWidth = node.width || (LANGGRAPH_NODE_TYPES.includes(node.type || '') ? 600 : 200);
    const nodeHeight = node.height || (LANGGRAPH_NODE_TYPES.includes(node.type || '') ? 300 : 100);
    
    minX = Math.min(minX, node.position.x);
    maxX = Math.max(maxX, node.position.x + nodeWidth);
    minY = Math.min(minY, node.position.y);
    maxY = Math.max(maxY, node.position.y + nodeHeight);
  });

  // 添加边距（扩展范围）
  const margin = 200;
  return {
    translateExtent: [
      [minX - margin, minY - margin], 
      [maxX + margin, maxY + margin]
    ],
    nodeExtent: [
      [minX - margin, minY - margin], 
      [maxX + margin, maxY + margin]
    ],
    minZoom: 0.1,
    maxZoom: 2.0 // 允许一定程度的缩放
  };
}; 