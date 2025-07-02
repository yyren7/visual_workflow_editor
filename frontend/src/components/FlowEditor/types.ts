import { NodeTypes } from 'reactflow';

// 节点数据接口定义
export interface NodeData {
  label: string;
  description?: string;
  [key: string]: any;
}

// 流程编辑器属性接口
export interface FlowEditorProps {
  flowId?: string;
}

// 视口配置接口
export interface ViewportConfig {
  translateExtent: [[number, number], [number, number]];
  nodeExtent: [[number, number], [number, number]];
  minZoom: number;
  maxZoom: number;
}

// ReactFlow配置接口
export interface ReactFlowConfig {
  translateExtent: [[number, number], [number, number]];
  nodeExtent: [[number, number], [number, number]];
  minZoom: number;
  maxZoom: number;
}

// 调试面板属性接口
export interface FlowDebugPanelProps {
  currentFlowId: string | null;
  agentState: any;
  nodes: any[];
  onDebugAgentState: () => void;
} 