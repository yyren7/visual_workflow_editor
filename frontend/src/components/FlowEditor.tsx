// frontend/src/components/FlowEditor.tsx
import React, { useState, useCallback, useRef, useEffect } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  useReactFlow,
  Node,
  Edge,
  Connection,
  NodeMouseHandler,
  ReactFlowInstance,
  NodeTypes,
  XYPosition,
  BackgroundVariant,
  DefaultEdgeOptions,
  ConnectionLineType,
  MarkerType,
  Panel,
  useStore,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Box,
  Button,
  TextField,
  IconButton,
  Tooltip,
  Paper,
  Menu,
  MenuItem,
  Divider,
  Typography
} from '@mui/material';
import { useSnackbar } from 'notistack';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import AddIcon from '@mui/icons-material/Add';
import ChatIcon from '@mui/icons-material/Chat';
import CodeIcon from '@mui/icons-material/Code';
import CloseIcon from '@mui/icons-material/Close';
import InfoIcon from '@mui/icons-material/Info';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
// 导入自定义节点和组件
import InputNode from './nodes/InputNode';
import OutputNode from './nodes/OutputNode';
import ProcessNode from './nodes/ProcessNode';
import DecisionNode from './nodes/DecisionNode';
import GenericNode from './nodes/GenericNode'; // 导入通用节点组件
import NodeProperties from './NodeProperties';
import FlowVariables from './FlowVariables';
import ChatInterface from './ChatInterface';
import NodeSelector from './NodeSelector';
import DraggableResizableContainer from './DraggableResizableContainer'; // 导入可拖动调整大小的容器组件
import { createFlow, getFlow, updateFlow, deleteFlow } from '../api/api';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';
import FlowSelect from './FlowSelect';
import { NodeTypeInfo } from './NodeSelector'; // 导入节点类型信息接口
import ConditionNode from './nodes/ConditionNode'; // 添加条件判断节点类型
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import WidgetsIcon from '@mui/icons-material/Widgets';
import SortIcon from '@mui/icons-material/Sort';

// 节点数据接口定义
export interface NodeData {
  label: string;
  description?: string;
  [key: string]: any;
}

// 节点类型接口
export interface AddNodeParams {
  type: string;
  data: NodeData;
}

// 节点更新接口
export interface UpdateNodeData {
  id: string;
  data: NodeData;
}

// 流程编辑器属性接口
interface FlowEditorProps {
  flowId?: string;
}

// 自定义节点类型
const nodeTypes: NodeTypes = {
  input: InputNode,
  output: OutputNode,
  process: ProcessNode,
  decision: DecisionNode,
  generic: GenericNode, // 添加通用节点类型
  condition: ConditionNode, // 添加条件判断节点类型
};

const FlowEditor: React.FC<FlowEditorProps> = ({ flowId }) => {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<NodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [nodeInfoOpen, setNodeInfoOpen] = useState<boolean>(false);
  const [globalVarsOpen, setGlobalVarsOpen] = useState<boolean>(false);
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  const [toggleMenuAnchorEl, setToggleMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [flowName, setFlowName] = useState<string>(t('flowEditor.untitledFlow'));
  const { enqueueSnackbar } = useSnackbar();
  const { fitView } = useReactFlow();
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [flowSelectOpen, setFlowSelectOpen] = useState<boolean>(false);
  const [chatPosition, setChatPosition] = useState<{ x: number; y: number }>({ 
    x: window.innerWidth - 720,
    y: window.innerHeight - 620
  });
  const [globalVarsPosition, setGlobalVarsPosition] = useState<{ x: number; y: number }>({ x: window.innerWidth - 400, y: 50 });

  // 窗口大小状态
  const [windowSize, setWindowSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight
  });
  
  // 自定义边（连接线）样式
  const defaultEdgeOptions: DefaultEdgeOptions = {
    animated: false,
    style: {
      stroke: '#888',
      strokeWidth: 2,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#888',
      width: 20,
      height: 20,
    },
    type: 'smoothstep', // 使用平滑的阶梯线类型
    // 注意：在React Flow的类型中，pathOptions可能不是DefaultEdgeOptions的一部分
    // 但在运行时它是有效的属性
  };
  
  // 连接线类型
  const connectionLineStyle = {
    stroke: '#1976d2',
    strokeWidth: 2,
    strokeDasharray: '5 5',
  };

  // 窗口大小改变监听
  useEffect(() => {
    const handleResize = () => {
      const newWidth = window.innerWidth;
      const newHeight = window.innerHeight;
      
      setWindowSize({
        width: newWidth,
        height: newHeight
      });
      
      // 更新聊天框位置，确保其完全在可视区域内
      setChatPosition(prev => {
        // 确保不超出右边界
        const maxX = newWidth - 720; // 700宽度 + 20右边距
        // 确保不超出下边界
        const maxY = newHeight - 620; // 600高度 + 20底部边距
        // 确保不超出左边界（至少20px在可视区域内）
        const minX = -680; // -700 + 20左边距
        // 确保不超出上边界（至少顶部栏40px在可视区域内）
        const minY = -560; // -600 + 40顶部栏高度
        
        return {
          x: Math.min(Math.max(prev.x, minX), maxX),
          y: Math.min(Math.max(prev.y, minY), maxY)
        };
      });
      
      // 更新全局变量面板位置
      setGlobalVarsPosition(prev => {
        const maxX = newWidth - 370; // 350宽度 + 20右边距
        const maxY = newHeight - 420; // 400高度 + 20底部边距
        const minX = -330; // -350 + 20左边距
        const minY = -360; // -400 + 40顶部栏高度
        
        return {
          x: Math.min(Math.max(prev.x, minX), maxX),
          y: Math.min(Math.max(prev.y, minY), maxY)
        };
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 添加自动布局功能
  const autoLayout = useCallback(() => {
    // 弹出提示信息
    enqueueSnackbar(t('flowEditor.autoLayoutStart') || '正在应用智能布局...', { 
      variant: 'info',
      autoHideDuration: 1500
    });
    
    if (nodes.length === 0) return;
    
    // 创建层级布局结构
    const layers: { [key: number]: Node[] } = {};
    let visited = new Set<string>();
    let nodeLevels = new Map<string, number>();
    
    // 找出所有输入节点（没有入边的节点）
    const getNodeIncomers = (nodeId: string): string[] => {
      return edges
        .filter(edge => edge.target === nodeId)
        .map(edge => edge.source);
    };

    const getNodeOutgoers = (nodeId: string): string[] => {
      return edges
        .filter(edge => edge.source === nodeId)
        .map(edge => edge.target);
    };
    
    // 找出所有没有入边的节点作为起始点
    const startNodes = nodes
      .filter(node => !edges.some(edge => edge.target === node.id))
      .map(node => node.id);
    
    // 特殊处理Condition节点路径
    // 获取节点是通过条件节点的true路径还是false路径连接的
    const getNodeConnectionType = (sourceId: string, targetId: string): 'true' | 'false' | 'normal' => {
      const edge = edges.find(e => e.source === sourceId && e.target === targetId);
      if (edge) {
        if (edge.sourceHandle === 'true') return 'true';
        if (edge.sourceHandle === 'false') return 'false';
      }
      return 'normal';
    };
    
    // 使用BFS计算每个节点的层级
    const queue = startNodes.map(id => ({ id, level: 0 }));
    while (queue.length > 0) {
      const { id, level } = queue.shift()!;
      if (visited.has(id)) {
        // 如果已访问且当前层级更深，则更新层级
        if ((nodeLevels.get(id) || 0) < level) {
          nodeLevels.set(id, level);
        }
        continue;
      }
      
      visited.add(id);
      nodeLevels.set(id, level);
      
      // 将当前节点添加到对应层
      if (!layers[level]) layers[level] = [];
      const node = nodes.find(n => n.id === id);
      if (node) layers[level].push(node);
      
      // 添加所有后继节点到队列，并确保同一层级的节点顺序保持连贯
      const outgoers = getNodeOutgoers(id);
      
      // 先按类型分组，确保相同类型的节点尽可能靠近
      const outgoersByType: {[key: string]: string[]} = {};
      outgoers.forEach(targetId => {
        const targetNode = nodes.find(n => n.id === targetId);
        if (targetNode) {
          // 为条件节点判断是true路径还是false路径
          const connectionType = getNodeConnectionType(id, targetId);
          let groupKey = targetNode.type || 'unknown';
          
          // 如果是条件节点路径，在类型中添加标记
          if (connectionType !== 'normal') {
            groupKey = `${groupKey}_${connectionType}`;
          }
          
          if (!outgoersByType[groupKey]) outgoersByType[groupKey] = [];
          outgoersByType[groupKey].push(targetId);
        }
      });
      
      // 按类型顺序添加到队列，确保true分支在左侧，false分支在右侧
      // 先添加正常连接和true连接，后添加false连接
      const typeOrder = Object.keys(outgoersByType).sort((a, b) => {
        const aIsFalse = a.includes('_false');
        const bIsFalse = b.includes('_false');
        if (aIsFalse && !bIsFalse) return 1;
        if (!aIsFalse && bIsFalse) return -1;
        return 0;
      });
      
      typeOrder.forEach(type => {
        outgoersByType[type].forEach(targetId => {
          queue.push({ id: targetId, level: level + 1 });
        });
      });
    }
    
    // 处理剩余未访问的节点（可能存在孤立节点或循环）
    const nodesByType: {[key: string]: Node[]} = {};
    nodes.forEach(node => {
      if (!visited.has(node.id)) {
        // 按类型分组未访问的节点
        const type = node.type || 'unknown';
        if (!nodesByType[type]) nodesByType[type] = [];
        nodesByType[type].push(node);
      }
    });
    
    // 按类型顺序处理未访问的节点
    Object.values(nodesByType).forEach(typeNodes => {
      typeNodes.forEach(node => {
        if (!visited.has(node.id)) {
          // 尝试找到合适的层级
          const incomers = getNodeIncomers(node.id);
          const outgoers = getNodeOutgoers(node.id);
          
          let level = 0;
          if (incomers.length > 0) {
            // 放在所有入节点的下一层
            const maxIncomerLevel = Math.max(...incomers
              .map(id => nodeLevels.get(id) || 0));
            level = maxIncomerLevel + 1;
          } else if (outgoers.length > 0) {
            // 放在所有出节点的上一层
            const minOutgoerLevel = Math.min(...outgoers
              .map(id => nodeLevels.get(id) || 0));
            level = Math.max(0, minOutgoerLevel - 1);
          }
          
          nodeLevels.set(node.id, level);
          if (!layers[level]) layers[level] = [];
          layers[level].push(node);
          visited.add(node.id);
        }
      });
    });
    
    // 计算并应用新的节点位置
    const VERTICAL_SPACING = 200;  // 增加垂直间距
    const HORIZONTAL_SPACING = 250; // 增加水平间距
    const MIN_VERTICAL_GAP = 80;   // 最小垂直间隔
    
    const layerKeys = Object.keys(layers).map(Number).sort((a, b) => a - b);
    const newNodes = [...nodes];
    
    // 计算每层的实际垂直位置（考虑上一层节点的影响）
    const layerVerticalPositions: {[key: number]: number} = {};
    
    layerKeys.forEach((layerIndex, index) => {
      if (index === 0) {
        // 第一层固定位置
        layerVerticalPositions[layerIndex] = 0;
      } else {
        // 后续层计算与前一层的距离
        const prevLayerIndex = layerKeys[index - 1];
        const prevLayerY = layerVerticalPositions[prevLayerIndex];
        
        // 基本垂直距离
        let yPosition = prevLayerY + VERTICAL_SPACING;
        
        // 特殊情况处理：当前层有Movel节点，且上一层也有Movel节点
        const currentLayerHasMovel = layers[layerIndex].some(n => n.type === 'generic' && n.data?.type === 'moveL');
        const prevLayerHasMovel = layers[prevLayerIndex].some(n => n.type === 'generic' && n.data?.type === 'moveL');
        
        if (currentLayerHasMovel && prevLayerHasMovel) {
          // 增加额外间距以避免Movel节点堆叠
          yPosition += MIN_VERTICAL_GAP; 
        }
        
        layerVerticalPositions[layerIndex] = yPosition;
      }
    });
    
    layerKeys.forEach(layerIndex => {
      const layerNodes = layers[layerIndex];
      
      // 优化：按节点类型分组和排序，让相同类型的节点尽量靠近
      const nodesByType: {[key: string]: Node[]} = {};
      layerNodes.forEach(node => {
        const type = node.type || 'unknown';
        if (!nodesByType[type]) nodesByType[type] = [];
        nodesByType[type].push(node);
      });
      
      // 重新排列layerNodes，确保相同类型节点连续排列，且考虑true/false分支
      let sortedLayerNodes: Node[] = [];
      
      // 创建一个特殊排序函数，处理条件节点的分支
      // 1. 优先将非条件路径(普通路径)节点放在中间
      // 2. 将true路径节点放在左侧
      // 3. 将false路径节点放在右侧
      const determineConnectionType = (node: Node): number => {
        // 检查该节点是否是其他节点的true或false分支目标
        for (const edge of edges) {
          if (edge.target === node.id) {
            // 检查源节点是否为condition类型
            const sourceNode = nodes.find(n => n.id === edge.source);
            if (sourceNode && (sourceNode.type === 'condition')) {
              if (edge.sourceHandle === 'true') return -1; // true分支放左边
              if (edge.sourceHandle === 'false') return 1; // false分支放右边
            }
          }
        }
        return 0; // 普通节点或无法确定的情况
      };
      
      // 按连接类型分组节点
      const nodesByPathType: {[key: number]: Node[]} = {
        [-1]: [], // true路径节点
        0: [],  // 普通路径节点
        1: []   // false路径节点
      };
      
      Object.entries(nodesByType).forEach(([type, typeNodes]) => {
        typeNodes.forEach(node => {
          const connectionType = determineConnectionType(node);
          nodesByPathType[connectionType].push(node);
        });
      });
      
      // 按true路径->普通路径->false路径的顺序组合
      sortedLayerNodes = [
        ...nodesByPathType[-1], // true路径节点
        ...nodesByPathType[0],  // 普通路径节点
        ...nodesByPathType[1]   // false路径节点
      ];
      
      // 横向排列每层的节点
      sortedLayerNodes.forEach((node, nodeIndex) => {
        // 针对不同类型节点调整水平间距
        let nodeHorizontalSpacing = HORIZONTAL_SPACING;
        
        // MovL节点通常比其他节点显示更多信息，需要更大间距
        if (node.type === 'generic' && node.data?.type === 'moveL') {
          nodeHorizontalSpacing = HORIZONTAL_SPACING * 1.2;
        }
        
        // 循环类型节点也需要更大间距
        if (node.type === 'loop') {
          nodeHorizontalSpacing = HORIZONTAL_SPACING * 1.1;
        }
        
        // 计算该节点的X位置，考虑前面节点可能有不同的间距
        let xPosition = 0;
        if (nodeIndex === 0) {
          // 第一个节点居中放置
          const totalWidth = sortedLayerNodes.reduce((sum, n, idx) => {
            let spacing = HORIZONTAL_SPACING;
            if (n.type === 'generic' && n.data?.type === 'moveL') {
              spacing = HORIZONTAL_SPACING * 1.2;
            } else if (n.type === 'loop') {
              spacing = HORIZONTAL_SPACING * 1.1;
            }
            return sum + (idx < sortedLayerNodes.length - 1 ? spacing : 0);
          }, 0);
          
          xPosition = -totalWidth / 2;
        } else {
          // 非第一个节点，基于前一个节点位置计算
          const prevNode = sortedLayerNodes[nodeIndex - 1];
          const prevNodeToUpdate = newNodes.find(n => n.id === prevNode.id);
          
          if (prevNodeToUpdate) {
            let prevSpacing = HORIZONTAL_SPACING;
            if (prevNode.type === 'generic' && prevNode.data?.type === 'moveL') {
              prevSpacing = HORIZONTAL_SPACING * 1.2;
            } else if (prevNode.type === 'loop') {
              prevSpacing = HORIZONTAL_SPACING * 1.1;
            }
            
            xPosition = prevNodeToUpdate.position.x + prevSpacing;
          }
        }
        
        const nodeToUpdate = newNodes.find(n => n.id === node.id);
        if (nodeToUpdate) {
          nodeToUpdate.position = {
            x: xPosition,
            y: layerVerticalPositions[layerIndex]
          };
        }
      });
    });
    
    // 更新所有节点位置
    setNodes(newNodes);
    
    // 自动适应视图
    setTimeout(() => {
      if (reactFlowInstance) {
        reactFlowInstance.fitView({ padding: 0.2 });
        
        // 显示完成提示
        enqueueSnackbar(t('flowEditor.autoLayoutComplete') || '智能布局已完成', { 
          variant: 'success',
          autoHideDuration: 2000
        });
      }
    }, 100);
  }, [nodes, edges, setNodes, reactFlowInstance]);
  
  // 优化交叉线
  const optimizeEdgeCrossings = useCallback(() => {
    // 为每条边分配不同的offset值，以减少视觉上的交叉
    const edgesBySource: { [key: string]: Edge[] } = {};
    
    // 按源节点分组边
    edges.forEach(edge => {
      if (!edgesBySource[edge.source]) {
        edgesBySource[edge.source] = [];
      }
      edgesBySource[edge.source].push(edge);
    });
    
    // 更新边，为每个源节点的多条边添加偏移
    const newEdges = edges.map(edge => {
      const sourceEdges = edgesBySource[edge.source] || [];
      if (sourceEdges.length > 1) {
        const edgeIndex = sourceEdges.findIndex(e => e.id === edge.id);
        const edgeCount = sourceEdges.length;
        
        // 计算偏移量，使边分散
        const offset = edgeIndex - (edgeCount - 1) / 2;
        const offsetDistance = 20; // 偏移距离
        
        return {
          ...edge,
          style: {
            ...edge.style,
            strokeWidth: 2,
            stroke: edge.style?.stroke || '#888',
          },
          pathOptions: {
            offset: offset * offsetDistance,
          },
        };
      }
      
      return edge;
    });
    
    setEdges(newEdges);
  }, [edges, setEdges]);

  useEffect(() => {
    if (flowId) {
      loadFlow(flowId);
    }
  }, [flowId]);

  // 在FlowEditor组件内添加自动保存功能
  // 使用useEffect监听nodes和edges变化并自动保存
  useEffect(() => {
    // 创建防抖函数确保不会频繁调用API
    type DebouncedFunction = {
      (...args: any[]): void;
      flush?: () => void;
    };
    
    const debounce = (func: Function, delay: number): DebouncedFunction => {
      let timer: NodeJS.Timeout;
      const debouncedFunc = (...args: any) => {
        clearTimeout(timer);
        timer = setTimeout(() => func(...args), delay);
      };
      
      // 添加flush方法
      debouncedFunc.flush = () => {
        clearTimeout(timer);
        func();
      };
      
      return debouncedFunc;
    };

    // 如果还没有加载完成或者没有flowId，则不保存
    if (!flowId || !reactFlowInstance || nodes.length === 0) {
      return;
    }

    // 创建防抖的保存函数
    const debouncedSave = debounce(async () => {
      try {
        const flowData = reactFlowInstance.toObject();
        await updateFlow(flowId, { flow_data: flowData, name: flowName });
        console.log('流程图已自动保存');
        // 使用简单的通知而不是弹出提示，避免打扰用户
        // enqueueSnackbar(t('flowEditor.autoSaveSuccess'), { variant: 'success' });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        console.error('自动保存失败:', errorMessage);
        enqueueSnackbar(`${t('flowEditor.autoSaveError')} ${errorMessage}`, { variant: 'error' });
      }
    }, 2000); // 设置2秒延迟，避免频繁保存

    // 只要nodes或edges变化，就触发自动保存
    debouncedSave();

    // 清理函数
    return () => {
      // 组件卸载时如果有待处理的保存，立即执行
      debouncedSave.flush?.();
    };
  }, [nodes, edges, flowId, reactFlowInstance, flowName, enqueueSnackbar, t]);

  // 在现有useEffect之后添加一个新的useEffect来监听自定义事件
  useEffect(() => {
    // 监听流程图改名事件
    const handleFlowRenamed = (event: CustomEvent) => {
      if (event.detail && event.detail.flowId === flowId && event.detail.newName) {
        setFlowName(event.detail.newName);
        console.log('流程图名称已更新:', event.detail.newName);
        // 可选: 显示一个简单提示
        enqueueSnackbar(t('flowEditor.nameUpdated', '流程图名称已更新'), { 
          variant: 'success',
          autoHideDuration: 3000
        });
      }
    };

    // 添加事件监听器
    window.addEventListener('flow-renamed', handleFlowRenamed as EventListener);

    // 清理函数
    return () => {
      window.removeEventListener('flow-renamed', handleFlowRenamed as EventListener);
    };
  }, [flowId, enqueueSnackbar, t]);

  const onConnect = useCallback(
    (params: Connection) => {
      // 获取源节点的sourceHandle ID，用于区分是来自"true"还是"false"输出
      const sourceHandleId = params.sourceHandle;
      
      // 添加自定义边类
      let className = '';
      if (sourceHandleId === 'true') {
        className = 'true-edge';
      } else if (sourceHandleId === 'false') {
        className = 'false-edge';
      }
      
      // 创建带有正确类名的边
      const edge = {
        ...params,
        className,
        type: 'smoothstep', // 默认使用平滑阶梯线
      };
      
      setEdges((eds) => addEdge(edge, eds));
    },
    [setEdges]
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (event, node) => {
      // 如果当前已经有选中的节点，先取消其选中状态
      if (selectedNode && selectedNode.id !== node.id) {
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id === selectedNode.id) {
              return { ...n, selected: false };
            }
            return n;
          })
        );
      }
      
      // 设置新的选中节点，并确保它的selected状态为true
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === node.id) {
            return { ...n, selected: true };
          }
          return n;
        })
      );
      
      setSelectedNode(node as Node<NodeData>);
      setNodeInfoOpen(true);
    },
    [setSelectedNode, selectedNode, setNodes]
  );

  const onNodePropertyChange = (updatedNode: UpdateNodeData) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === updatedNode.id) {
          return { ...node, data: updatedNode.data };
        }
        return node;
      })
    );
  };

  const loadFlow = async (flowId: string) => {
    try {
      const flowData = await getFlow(flowId);
      if (flowData && flowData.flow_data) {
        setNodes(flowData.flow_data.nodes || []);
        setEdges(flowData.flow_data.edges || []);
        setFlowName(flowData.name || t('flowEditor.untitledFlow'));
        enqueueSnackbar(t('flowEditor.loadSuccess'), { variant: 'success' });
      } else {
        enqueueSnackbar(t('flowEditor.invalidFlowData'), { variant: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.unknown');
      enqueueSnackbar(`${t('flowEditor.loadError')} ${errorMessage}`, { variant: 'error' });
    }
  };

  const deleteCurrentFlow = async () => {
    if (flowId) {
      try {
        await deleteFlow(flowId);
        enqueueSnackbar(t('flowEditor.deleteSuccess'), { variant: 'success' });
        const userId = localStorage.getItem('user_id');
        navigate('/flow', { replace: true });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        enqueueSnackbar(`${t('flowEditor.deleteError')} ${errorMessage}`, { variant: 'error' });
      }
    } else {
      enqueueSnackbar(t('flowEditor.noFlowToDelete'), { variant: 'warning' });
    }
  };

  // 计算节点的默认位置，避免重叠
  const getNextNodePosition = (): XYPosition => {
    // 基于现有节点数量计算新位置
    const offset = nodes.length * 50;
    return {
      x: 100 + (nodes.length % 3) * 250,
      y: 100 + Math.floor(nodes.length / 3) * 150 + offset % 50
    };
  };

  const onAddNode = (nodeData: AddNodeParams) => {
    const id = `${nodeData.type}-${Date.now()}`; // Generate a unique ID
    const newNode: Node<NodeData> = {
      id: id,
      type: nodeData.type,
      data: nodeData.data,
      position: getNextNodePosition(), // 动态计算位置
    };
    setNodes((nds) => [...nds, newNode]);
  };

  // 处理拖拽操作
  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    console.log(t('nodeDrag.hover'));
  }, [t]);

  // 处理节点拖动开始
  const onNodeDragStart = useCallback((event: any, node: Node) => {
    // 添加dragging类以优化拖动性能
    document.querySelectorAll(`.react-flow__node[data-id="${node.id}"]`).forEach(el => {
      el.classList.add('dragging');
    });
  }, []);

  // 处理节点拖动结束
  const onNodeDragStop = useCallback((event: any, node: Node) => {
    // 移除dragging类
    document.querySelectorAll(`.react-flow__node[data-id="${node.id}"]`).forEach(el => {
      el.classList.remove('dragging');
    });
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      console.log('【调试】开始处理节点拖放事件', t('flowEditor.processingDrop'));

      // 检查是否在ReactFlow区域内
      if (!reactFlowWrapper.current || !reactFlowInstance) {
        console.error('【调试】ReactFlow引用无效', t('flowEditor.invalidReactFlowReference'));
        return;
      }

      // 获取ReactFlow边界
      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();

      // 获取拖拽的节点类型数据
      const nodeTypeData = event.dataTransfer.getData('application/reactflow-node');
      console.log('【调试】拖放的节点数据:', nodeTypeData, t('flowEditor.droppedNodeType'));

      if (!nodeTypeData) {
        console.error('【调试】没有找到节点类型数据', t('flowEditor.nodeTypeNotFound'));
        return;
      }

      // 计算鼠标位置相对于ReactFlow区域的坐标
      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      console.log('【调试】计算的位置坐标:', position, t('flowEditor.calculatedPosition'));

      try {
        // 尝试解析节点类型数据为JSON对象（新格式）
        const nodeTypeInfo = JSON.parse(nodeTypeData);
        console.log('【调试】解析后的节点类型信息:', nodeTypeInfo);
        
        // 检查是否是有效的节点类型对象
        if (nodeTypeInfo && typeof nodeTypeInfo === 'object' && nodeTypeInfo.id) {
          console.log('【调试】使用动态节点模板:', nodeTypeInfo);
          
          // 准备字段数据
          const fieldValues: Record<string, any> = {};
          if (nodeTypeInfo.fields && Array.isArray(nodeTypeInfo.fields)) {
            for (const field of nodeTypeInfo.fields) {
              if (field && typeof field === 'object' && field.name && 'default_value' in field) {
                fieldValues[field.name] = field.default_value;
              }
            }
          }
          console.log('【调试】处理后的字段值:', fieldValues);
          
          // 创建通用节点 - 确保使用generic类型
          const newNode: Node<NodeData> = {
            id: `${nodeTypeInfo.type || 'node'}-${Date.now()}`,
            // 重要：此处必须使用'generic'，而不是nodeTypeInfo.type
            type: 'generic',
            position,
            data: {
              label: nodeTypeInfo.label || nodeTypeInfo.id,
              description: nodeTypeInfo.description || '',
              nodeType: nodeTypeInfo.type || nodeTypeInfo.id, // 保存原始节点类型
              type: nodeTypeInfo.type || nodeTypeInfo.id,
              fields: nodeTypeInfo.fields ? nodeTypeInfo.fields.map((f: any) => ({
                name: f.name,
                value: f.default_value,
                type: f.type
              })) : [],
              inputs: nodeTypeInfo.inputs || [],
              outputs: nodeTypeInfo.outputs || [],
              ...fieldValues, // 添加字段值作为数据属性
            },
          };
          
          console.log('【调试】创建的新节点:', newNode);
          
          // 添加节点到流程图
          setNodes((nds) => [...nds, newNode]);
          console.log('【调试】添加动态节点成功');
          return;
        }
      } catch (error) {
        // JSON解析失败，继续使用旧格式
        console.error('【调试】解析节点数据失败，使用旧格式:', error);
      }
      
      // 旧格式处理（兼容现有代码）
      const nodeType = nodeTypeData;
      console.log('【调试】使用旧格式处理节点:', nodeType);
      
      // 创建一个基于类型的默认标签
      let label = t('nodeTypes.unknown');
      switch (nodeType) {
        case 'input': label = t('nodeTypes.input'); break;
        case 'process': label = t('nodeTypes.process'); break;
        case 'output': label = t('nodeTypes.output'); break;
        case 'decision': label = t('nodeTypes.decision'); break;
        default: console.log('【调试】未知节点类型，使用默认标签');
      }
      console.log('【调试】选择的标签:', label);

      // 创建新节点
      const newNode: Node<NodeData> = {
        id: `${nodeType}-${Date.now()}`,
        type: nodeType,
        position,
        data: { label },
      };

      console.log('【调试】创建的默认节点:', newNode);
      
      // 添加节点到流程图
      setNodes((nds) => [...nds, newNode]);
      console.log('【调试】添加默认节点成功', t('flowEditor.nodeAddSuccess'));
    },
    [reactFlowInstance, setNodes, t]
  );

  const onUpdateNode = (nodeId: string, updatedNodeData: { data: NodeData }) => {
    setNodes((nds) =>
      nds.map((node) => (node.id === nodeId ? { ...node, data: updatedNodeData.data } : node))
    );
    enqueueSnackbar(t('flowEditor.nodeUpdated'), { variant: 'success' });
  };

  /**
   * 连接两个节点
   * @param sourceId 源节点ID
   * @param targetId 目标节点ID
   * @param label 连接标签
   */
  const onConnectNodes = (sourceId: string, targetId: string, label?: string) => {
    try {
      // 验证节点存在
      const sourceNode = nodes.find(node => node.id === sourceId);
      const targetNode = nodes.find(node => node.id === targetId);
      
      if (!sourceNode || !targetNode) {
        enqueueSnackbar(t('flowEditor.nodeNotFound'), { variant: 'error' });
        return;
      }
      
      // 创建新的边
      const newEdge: Edge = {
        id: `${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        type: 'default',
        label: label || '',
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      
      // 添加到edges中
      setEdges((eds) => [...eds, newEdge]);
      
      enqueueSnackbar(t('flowEditor.edgeAdded'), { variant: 'success' });
    } catch (error) {
      console.error('Error connecting nodes:', error);
      enqueueSnackbar(t('flowEditor.edgeAddedError'), { variant: 'error' });
    }
  };

  const onInit = (_reactFlowInstance: ReactFlowInstance) => {
    setReactFlowInstance(_reactFlowInstance);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleMenuClose();
  };

  const handleToggleMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setToggleMenuAnchorEl(event.currentTarget);
  };

  const handleToggleMenuClose = () => {
    setToggleMenuAnchorEl(null);
  };

  const handleOpenFlowSelect = () => {
    handleMenuClose();
    setFlowSelectOpen(true);
  };

  // 添加点击背景时取消节点选中的处理
  const onPaneClick = useCallback(() => {
    // 取消所有节点的选中状态
    setNodes((nds) =>
      nds.map((n) => {
        if (n.selected) {
          return { ...n, selected: false };
        }
        return n;
      })
    );
    
    // 清除选中节点和关闭节点信息面板
    setSelectedNode(null);
    setNodeInfoOpen(false);
  }, [setNodes, setSelectedNode]);

  // 重置面板可见性
  const resetPanelVisibility = useCallback(() => {
    setNodeInfoOpen(false);
    setChatOpen(false);
  }, []);

  const toggleVariablesPanel = useCallback(() => {
    setGlobalVarsOpen(!globalVarsOpen);
    if (!globalVarsOpen) {
      resetPanelVisibility();
      setGlobalVarsOpen(true);
    }
  }, [globalVarsOpen, resetPanelVisibility]);

  return (
    <Box sx={{
      height: '100vh',
      width: '100vw',
      display: 'flex',
      flexDirection: 'column',
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      m: 0,
      p: 0,
      boxSizing: 'border-box',
      bgcolor: '#1e1e1e',
      overflow: 'hidden'
    }}>
      {/* 合并后的顶部工具栏 */}
      <Paper elevation={2} sx={{
        p: 0.75,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderRadius: 0,
        minHeight: '48px',
        bgcolor: '#1e1e1e',
        borderBottom: '1px solid #333',
        color: 'white',
        flexShrink: 0,
        zIndex: 10
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
          {/* 侧边栏切换按钮和流程名称区域 */}
          <Tooltip title={t('flowEditor.toggleMenu')}>
            <IconButton
              color="inherit"
              onClick={handleToggleMenuOpen}
              size="small"
            >
              <MenuIcon />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={toggleMenuAnchorEl}
            open={Boolean(toggleMenuAnchorEl)}
            onClose={handleToggleMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'left',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'left',
            }}
            PaperProps={{
              sx: {
                bgcolor: '#333',
                color: 'white',
                '& .MuiMenuItem-root:hover': {
                  bgcolor: 'rgba(255, 255, 255, 0.1)',
                },
                '& .MuiDivider-root': {
                  borderColor: 'rgba(255, 255, 255, 0.12)',
                },
              },
            }}
          >
            <MenuItem
              onClick={() => {
                toggleVariablesPanel();
                handleToggleMenuClose();
              }}
            >
              {globalVarsOpen ? t('flowEditor.closeGlobalVars') : t('flowEditor.openGlobalVars')}
            </MenuItem>
            <MenuItem
              onClick={() => {
                setChatOpen(!chatOpen);
                handleToggleMenuClose();
              }}
            >
              {chatOpen ? t('flowEditor.closeChat') : t('flowEditor.openChat')}
            </MenuItem>
          </Menu>

          <Tooltip title={t('flowEditor.addNode')}>
            <IconButton
              color="inherit"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              size="small"
            >
              <AddIcon />
            </IconButton>
          </Tooltip>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label={t('flowEditor.flowName')}
              variant="outlined"
              size="small"
              value={flowName}
              InputProps={{
                readOnly: true,
              }}
              sx={{
                width: '250px',
                '& .MuiOutlinedInput-root': {
                  color: 'white',
                  height: '36px',
                  '& fieldset': {
                    borderColor: 'rgba(255, 255, 255, 0.23)',
                  },
                  '&:hover fieldset': {
                    borderColor: 'rgba(255, 255, 255, 0.23)',
                  },
                },
                '& .MuiInputLabel-root': {
                  color: 'rgba(255, 255, 255, 0.7)',
                  transform: 'translate(14px, 9px) scale(0.75)',
                  '&.MuiInputLabel-shrink': {
                    transform: 'translate(14px, -6px) scale(0.75)',
                  }
                },
              }}
            />
          </Box>
        </Box>

        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexGrow: 1
        }}>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
          <LanguageSelector />

          {isAuthenticated && (
            <>
              <IconButton
                color="inherit"
                onClick={handleMenuOpen}
                size="small"
              >
                <AccountCircleIcon />
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'right',
                }}
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                PaperProps={{
                  sx: {
                    bgcolor: '#333',
                    color: 'white',
                    '& .MuiMenuItem-root:hover': {
                      bgcolor: 'rgba(255, 255, 255, 0.1)',
                    },
                    '& .MuiDivider-root': {
                      borderColor: 'rgba(255, 255, 255, 0.12)',
                    },
                  },
                }}
              >
                <MenuItem onClick={handleOpenFlowSelect}>
                  {t('nav.flowSelect', '选择流程图')}
                </MenuItem>
                <Divider />
                <MenuItem onClick={handleLogout}>{t('nav.logout')}</MenuItem>
              </Menu>
            </>
          )}
        </Box>
      </Paper>

      {/* 主要内容区域 */}
      <Box sx={{
        flexGrow: 1,
        display: 'flex',
        overflow: 'hidden',
        height: 'calc(100vh - 48px)',  // 减去顶部工具栏的高度
        width: '100%',
        position: 'relative'
      }}>
        {/* 节点选择器面板 - 可关闭 */}
        {sidebarOpen && (
          <Box
            sx={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              width: '220px',
              height: 'auto',
              maxHeight: '60%',
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box sx={{
              p: 1,
              bgcolor: '#333',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              borderBottom: '1px solid #444'
            }}>
              <Typography variant="subtitle2">
                {t('sidebar.title')}
              </Typography>
            </Box>
            <Box sx={{ p: 1.5, overflowY: 'auto', flexGrow: 1 }}>
              <Typography
                variant="body2"
                sx={{
                  mb: 1.5,
                  color: '#aaa',
                  fontStyle: 'italic',
                  fontSize: '0.8rem'
                }}
              >
                {t('sidebar.dragHint')}
              </Typography>
              <NodeSelector />
            </Box>
          </Box>
        )}
        <Box
          ref={reactFlowWrapper}
          sx={{
            flexGrow: 1,
            position: 'relative',
            height: '100%',
            width: '100%',
            '& .react-flow': {
              background: '#1e1e1e',
              width: '100%',
              height: '100%'
            },
            '& .react-flow__container': {
              width: '100%',
              height: '100%'
            },
            '& .react-flow__controls': {
              position: 'fixed',
              left: '20px',
              bottom: '20px',
              zIndex: 5,
            },
            '& .react-flow__attribution': {
              display: 'none'  // 隐藏原有的ReactFlow标识
            },
            '& .version-info': {
              position: 'fixed',
              right: '10px',
              bottom: '10px',
              zIndex: 4,
              backgroundColor: 'transparent',
            }
          }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onInit={onInit}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onNodeDragStart={onNodeDragStart}
            onNodeDragStop={onNodeDragStop}
            nodeTypes={nodeTypes}
            deleteKeyCode="Delete"
            multiSelectionKeyCode="Control"
            selectionOnDrag={false}
            panOnDrag={true} // 允许使用鼠标左键拖动背景
            zoomOnScroll={true}
            zoomOnPinch={true} // 支持触控板缩放
            snapToGrid={false}
            snapGrid={[5, 5]}
            defaultEdgeOptions={defaultEdgeOptions}
            connectionLineStyle={connectionLineStyle}
            connectionLineType={ConnectionLineType.SmoothStep}
            elevateEdgesOnSelect={true}
            fitView
            style={{
              width: '100%',
              height: '100%',
              background: '#1e1e1e'
            }}
            className="fullscreen-flow"
            onPaneClick={onPaneClick}
          >
            <Controls
              showInteractive={true}
              style={{
                backgroundColor: '#2d2d2d',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                padding: '4px',
              }}
            />
            <Background color="#444" gap={12} size={1} variant={BackgroundVariant.Dots} />
            <div className="version-info">
              <VersionInfo />
            </div>
            
            {/* 添加布局工具面板 */}
            <Panel position="top-left" style={{ marginTop: '50px', backgroundColor: '#2d2d2d', color: '#fff', borderRadius: '4px', padding: '8px', border: '1px solid #444' }}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                  布局工具
                </Typography>
                <Tooltip title="自动布局节点，减少线条交叉">
                  <Button 
                    variant="outlined" 
                    size="small" 
                    startIcon={<AutoFixHighIcon />}
                    onClick={() => {
                      autoLayout();
                      setTimeout(optimizeEdgeCrossings, 100);
                    }}
                    sx={{ 
                      textTransform: 'none', 
                      color: '#fff',
                      borderColor: '#666',
                      '&:hover': {
                        borderColor: '#888',
                        backgroundColor: 'rgba(255, 255, 255, 0.08)'
                      }
                    }}
                  >
                    智能布局
                  </Button>
                </Tooltip>
                <Tooltip title="优化连接线，减少视觉交叉">
                  <Button 
                    variant="outlined" 
                    size="small" 
                    startIcon={<SortIcon />}
                    onClick={optimizeEdgeCrossings}
                    sx={{ 
                      textTransform: 'none', 
                      color: '#fff',
                      borderColor: '#666',
                      '&:hover': {
                        borderColor: '#888',
                        backgroundColor: 'rgba(255, 255, 255, 0.08)'
                      }
                    }}
                  >
                    优化连线
                  </Button>
                </Tooltip>
              </Box>
            </Panel>
          </ReactFlow>
        </Box>

        {/* 节点信息面板 - 可关闭 */}
        {nodeInfoOpen && selectedNode && (
          <Box
            sx={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              width: '350px',
              maxHeight: globalVarsOpen ? 'calc(50% - 36px)' : 'calc(100% - 24px)',
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box sx={{
              p: 1,
              bgcolor: '#333',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid #444'
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <InfoIcon fontSize="small" />
                <Typography variant="subtitle2">
                  {t('flowEditor.nodeProperties')}
                </Typography>
              </Box>
              <IconButton
                size="small"
                color="inherit"
                onClick={() => setNodeInfoOpen(false)}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
            <Box sx={{ p: 2, overflowY: 'auto', flexGrow: 1 }}>
              <NodeProperties node={selectedNode} onNodePropertyChange={onNodePropertyChange} />
            </Box>
          </Box>
        )}

        {/* 流程图变量面板 - 可拖动和调整大小 */}
        <DraggableResizableContainer
          title={t('flowEditor.flowVariables')}
          icon={<CodeIcon fontSize="small" />}
          isOpen={globalVarsOpen}
          onClose={() => setGlobalVarsOpen(false)}
          defaultPosition={globalVarsPosition}
          defaultSize={{ width: 350, height: 400 }}
          zIndex={5}
        >
          <FlowVariables />
        </DraggableResizableContainer>

        {/* 聊天界面 - 可拖动和调整大小 */}
        <DraggableResizableContainer
          title={t('flowEditor.chatAssistant')}
          icon={<ChatIcon fontSize="small" />}
          isOpen={chatOpen}
          onClose={() => setChatOpen(false)}
          defaultPosition={chatPosition}
          defaultSize={{ width: 700, height: 600 }}
          zIndex={5}
        >
          <ChatInterface
            onAddNode={onAddNode}
            onUpdateNode={onUpdateNode}
            onConnectNodes={onConnectNodes}
          />
        </DraggableResizableContainer>

        {/* 流程图选择对话框 */}
        <FlowSelect
          open={flowSelectOpen}
          onClose={() => setFlowSelectOpen(false)}
        />
      </Box>
    </Box>
  );
};

// FlowEditorWrapper组件属性接口
interface FlowEditorWrapperProps {
  flowId?: string;
}

const FlowEditorWrapper: React.FC<FlowEditorWrapperProps> = ({ flowId }) => (
  <ReactFlowProvider>
    <FlowEditor flowId={flowId} />
  </ReactFlowProvider>
);

export default FlowEditorWrapper;