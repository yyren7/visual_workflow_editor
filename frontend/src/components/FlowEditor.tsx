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
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Box,
  Button,
  TextField,
  IconButton,
  Tooltip,
  Paper
} from '@mui/material';
import { useSnackbar } from 'notistack';
import MenuIcon from '@mui/icons-material/Menu';
// 导入自定义节点和组件
import InputNode from './nodes/InputNode';
import OutputNode from './nodes/OutputNode';
import ProcessNode from './nodes/ProcessNode';
import DecisionNode from './nodes/DecisionNode';
import NodeProperties from './NodeProperties';
import GlobalVariables from './GlobalVariables';
import ChatInterface from './ChatInterface';
import Sidebar from './Sidebar';
import { createFlow, getFlow, updateFlow, deleteFlow } from '../api/api';
import { useTranslation } from 'react-i18next';

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
};

const FlowEditor: React.FC<FlowEditorProps> = ({ flowId }) => {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<NodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [flowName, setFlowName] = useState<string>(t('flowEditor.untitledFlow'));
  const { enqueueSnackbar } = useSnackbar();
  const { fitView } = useReactFlow();
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  useEffect(() => {
    if (flowId) {
      loadFlow(flowId);
    }
  }, [flowId]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (event, node) => {
      setSelectedNode(node as Node<NodeData>);
    },
    [setSelectedNode]
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

  const handleFlowNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFlowName(event.target.value);
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

  const saveFlow = async () => {
    if (!reactFlowInstance) {
      enqueueSnackbar(t('flowEditor.reactFlowNotInitialized'), { variant: 'error' });
      return;
    }

    const flowData = reactFlowInstance.toObject();

    if (flowId) {
      try {
        await updateFlow(flowId, { flow_data: flowData, name: flowName });
        enqueueSnackbar(t('flowEditor.saveSuccess'), { variant: 'success' });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        enqueueSnackbar(`${t('flowEditor.saveError')} ${errorMessage}`, { variant: 'error' });
      }
    } else {
      try {
        const newFlow = await createFlow({ flow_data: flowData, name: flowName });
        enqueueSnackbar(t('flowEditor.saveSuccess'), { variant: 'success' });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        enqueueSnackbar(`${t('flowEditor.saveError')} ${errorMessage}`, { variant: 'error' });
      }
    }
  };

  const deleteCurrentFlow = async () => {
    if (flowId) {
      try {
        await deleteFlow(flowId);
        enqueueSnackbar(t('flowEditor.deleteSuccess'), { variant: 'success' });
        window.location.href = '/flow'; // 重定向到流程编辑器页面，而不是根路径
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

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      console.log(t('flowEditor.processingDrop'));
      
      // 检查是否在ReactFlow区域内
      if (!reactFlowWrapper.current || !reactFlowInstance) {
        console.error(t('flowEditor.invalidReactFlowReference'));
        return;
      }

      // 获取ReactFlow边界
      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      
      // 获取拖拽的节点类型数据
      const nodeType = event.dataTransfer.getData('application/reactflow-node');
      console.log(t('flowEditor.droppedNodeType'), nodeType);
      
      if (!nodeType) {
        console.error(t('flowEditor.nodeTypeNotFound'));
        return;
      }

      // 计算鼠标位置相对于ReactFlow区域的坐标
      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });
      
      console.log(t('flowEditor.calculatedPosition'), position);

      // 创建一个基于类型的默认标签
      let label = t('nodeTypes.unknown');
      switch(nodeType) {
        case 'input': label = t('nodeTypes.input'); break;
        case 'process': label = t('nodeTypes.process'); break;
        case 'output': label = t('nodeTypes.output'); break;
        case 'decision': label = t('nodeTypes.decision'); break;
      }

      // 创建新节点
      const newNode: Node<NodeData> = {
        id: `${nodeType}-${Date.now()}`,
        type: nodeType,
        position,
        data: { label },
      };

      // 添加节点到流程图
      setNodes((nds) => [...nds, newNode]);
      console.log(t('flowEditor.nodeAddSuccess'), newNode);
    },
    [reactFlowInstance, setNodes, t]
  );

  const onUpdateNode = (nodeId: string, updatedNodeData: { data: NodeData }) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return { ...node, data: updatedNodeData.data };
        }
        return node;
      })
    );
  };

  const onInit = (_reactFlowInstance: ReactFlowInstance) => {
    setReactFlowInstance(_reactFlowInstance);
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部工具栏 - 简化版 */}
      <Paper elevation={2} sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderRadius: 0 }}>
        <TextField
          label={t('flowEditor.flowName')}
          variant="outlined"
          size="small"
          value={flowName}
          onChange={handleFlowNameChange}
          sx={{ width: '250px' }}
        />
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {/* 只保留侧边栏切换按钮 */}
          <Tooltip title={t('flowEditor.toggleSidebar')}>
            <IconButton
              color="primary"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              sx={{ mr: 1 }}
            >
              <MenuIcon />
            </IconButton>
          </Tooltip>
          
          {/* 流程操作按钮 */}
          <Button variant="contained" color="primary" sx={{ mr: 1 }} onClick={saveFlow}>
            {t('flowEditor.save')}
          </Button>
          {flowId && (
            <Button variant="contained" color="error" onClick={deleteCurrentFlow}>
              {t('flowEditor.delete')}
            </Button>
          )}
        </Box>
      </Paper>
      
      {/* 主要内容区域 */}
      <Box sx={{ flexGrow: 1, display: 'flex' }}>
        <Sidebar
          isOpen={sidebarOpen}
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
        <Box ref={reactFlowWrapper} sx={{ flexGrow: 1, position: 'relative' }}>
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
            nodeTypes={nodeTypes}
            deleteKeyCode="Delete"
            multiSelectionKeyCode="Control"
            selectionOnDrag={false}
            zoomOnScroll={true}
            snapToGrid={true}
            snapGrid={[15, 15]}
            fitView
            style={{ background: '#1e1e1e' }}
          >
            <Controls showInteractive={true} style={{ backgroundColor: '#2d2d2d', color: '#fff' }} />
            <Background color="#444" gap={12} size={1} variant={BackgroundVariant.Dots} />
          </ReactFlow>
        </Box>
        
        {/* 右侧面板区域，包含属性面板和聊天界面 */}
        <Box sx={{
          display: 'flex',
          flexDirection: 'column',
          width: 350,
          borderLeft: '1px solid #444',
          backgroundColor: '#2d2d2d',
          color: '#eee'
        }}>
          {/* 属性面板 */}
          <Box sx={{ flexGrow: 1, p: 2, overflowY: 'auto' }}>
            <NodeProperties node={selectedNode} onNodePropertyChange={onNodePropertyChange} />
            <GlobalVariables />
          </Box>
          
          {/* 聊天界面 - 独立面板 */}
          <Box
            sx={{
              height: '40%',
              borderTop: '1px solid #444',
              backgroundColor: '#1e1e1e',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <Box sx={{
              p: 1,
              backgroundColor: '#333',
              color: '#eee',
              fontWeight: 'bold',
              fontSize: '0.9rem',
              display: 'flex',
              justifyContent: 'center'
            }}>
              {t('flowEditor.chatAssistant')}
            </Box>
            <Box sx={{ flexGrow: 1, display: 'flex' }}>
              <ChatInterface onAddNode={onAddNode} onUpdateNode={onUpdateNode} />
            </Box>
          </Box>
        </Box>
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