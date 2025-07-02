import { Node, NodeTypes } from 'reactflow';
import GenericNode from '../nodes/GenericNode';
import { LangGraphInputNode } from '../nodes/LangGraphInputNode';
import { LangGraphTaskNode } from '../nodes/LangGraphTaskNode';
import { LangGraphDetailNode } from '../nodes/LangGraphDetailNode';
import { LANGGRAPH_NODE_TYPES } from './viewportUtils';
import { NodeTemplatesResponse } from '../../api/nodeTemplates';

// 基础节点类型
export const baseNodeTypes: NodeTypes = {
  langgraph_input: LangGraphInputNode,
  langgraph_task: LangGraphTaskNode,
  langgraph_detail: LangGraphDetailNode,
};

/**
 * 处理节点，设置LangGraph节点的特殊属性
 * @param nodes 原始节点数组
 * @returns 处理后的节点数组
 */
export const processNodes = (nodes: Node[]): Node[] => {
  const processed = nodes.map(node => {
    const isLangGraphNode = LANGGRAPH_NODE_TYPES.includes(node.type || '');
    const processedNode = {
      ...node,
      draggable: !isLangGraphNode, // LangGraph节点不可拖动
      dragHandle: isLangGraphNode ? undefined : '.drag-handle', // LangGraph节点没有拖拽句柄
      // 确保LangGraph节点有固定尺寸和位置限制
      ...(isLangGraphNode && {
        style: {
          ...node.style,
          pointerEvents: 'auto' as const,
        },
        selectable: true, // 仍然可选择
        deletable: false, // 不可删除
      })
    };
    
    // 重要：确保 selected 属性不被覆盖
    processedNode.selected = node.selected;
    
    // 添加调试日志
    console.log(`节点 ${node.id} (${node.type}):`, {
      isLangGraphNode,
      deletable: processedNode.deletable !== false,
      selectable: processedNode.selectable !== false,
      draggable: processedNode.draggable,
      selected: processedNode.selected,
      actualWidth: node.width, 
      actualHeight: node.height,
      styleFromNode: node.style,
    });
    
    return processedNode;
  });
  
  console.log('processedNodes 总数:', processed.length);
  console.log('processedNodes 中选中的节点:', processed.filter(n => n.selected).map(n => ({ id: n.id, selected: n.selected })));
  return processed;
};

/**
 * 动态生成节点类型映射
 * @param nodeTemplates 节点模板
 * @returns 节点类型映射
 */
export const generateNodeTypes = (nodeTemplates: NodeTemplatesResponse | null): NodeTypes => {
  const dynamicTypes: NodeTypes = { ...baseNodeTypes };
  
  if (nodeTemplates) {
    Object.keys(nodeTemplates).forEach((templateKey) => {
      const template = nodeTemplates[templateKey];
      if (template && template.type && !(template.type in dynamicTypes)) {
        // 如果类型不在baseNodeTypes中定义，映射到GenericNode
        dynamicTypes[template.type] = GenericNode;
        console.log(`FlowEditor: Mapping node type '${template.type}' to GenericNode.`);
      }
    });
  }
  
  console.log("FlowEditor: Final nodeTypes map:", dynamicTypes);
  return dynamicTypes;
}; 