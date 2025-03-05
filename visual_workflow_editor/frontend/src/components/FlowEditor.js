// frontend/src/components/FlowEditor.js
import React, { useState, useCallback, useRef, useEffect } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Box,
  Button,
  TextField,
  Menu,
  MenuItem,
  IconButton,
  Tooltip,
  Divider,
  Paper
} from '@mui/material';
import { useSnackbar } from 'notistack';
import PropTypes from 'prop-types';
import AddIcon from '@mui/icons-material/Add';
import MenuIcon from '@mui/icons-material/Menu';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
// 导入自定义节点和组件
import InputNode from './nodes/InputNode';
import OutputNode from './nodes/OutputNode';
import ProcessNode from './nodes/ProcessNode';
import DecisionNode from './nodes/DecisionNode';
import NodeSelector from './NodeSelector';
import NodeProperties from './NodeProperties';
import GlobalVariables from './GlobalVariables';
import ChatInterface from './ChatInterface';
import Sidebar from './Sidebar';
import { createFlow, getFlow, updateFlow, deleteFlow } from '../api/api';

// 自定义节点类型
const nodeTypes = {
  input: InputNode,
  output: OutputNode,
  process: ProcessNode,
  decision: DecisionNode,
};

const FlowEditor = ({ flowId }) => {
  const reactFlowWrapper = useRef(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [flowName, setFlowName] = useState('Untitled Flow');
  const { enqueueSnackbar } = useSnackbar();
  const { fitView } = useReactFlow();
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  
  // 节点选择器菜单状态
  const [nodeSelectorAnchorEl, setNodeSelectorAnchorEl] = useState(null);
  const isNodeSelectorOpen = Boolean(nodeSelectorAnchorEl);
  
  // 打开节点选择器菜单
  const handleNodeSelectorClick = (event) => {
    setNodeSelectorAnchorEl(event.currentTarget);
  };
  
  // 关闭节点选择器菜单
  const handleNodeSelectorClose = () => {
    setNodeSelectorAnchorEl(null);
  };

  useEffect(() => {
    if (flowId) {
      loadFlow(flowId);
    }
  }, [flowId]);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const onNodeClick = useCallback(
    (event, node) => {
      setSelectedNode(node);
    },
    [setSelectedNode]
  );

  const onNodePropertyChange = (updatedNode) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === updatedNode.id) {
          // it's important to create a new object for the node, that's why we're spreading it here
          return { ...node, data: updatedNode.data };
        }
        return node;
      })
    );
  };

  const handleFlowNameChange = (event) => {
    setFlowName(event.target.value);
  };

  const loadFlow = async (flowId) => {
    try {
      const flowData = await getFlow(flowId);
      if (flowData && flowData.flow_data) {
        setNodes(flowData.flow_data.nodes || []);
        setEdges(flowData.flow_data.edges || []);
        setFlowName(flowData.name || 'Untitled Flow');
        enqueueSnackbar('Flow loaded successfully!', { variant: 'success' });
      } else {
        enqueueSnackbar('Flow data is invalid.', { variant: 'error' });
      }
    } catch (error) {
      enqueueSnackbar(`Error loading flow: ${error.message}`, { variant: 'error' });
    }
  };

  const saveFlow = async () => {
    if (!reactFlowInstance) {
      enqueueSnackbar('React Flow instance not initialized.', { variant: 'error' });
      return;
    }

    const flowData = reactFlowInstance.toObject();

    if (flowId) {
      try {
        await updateFlow(flowId, { flow_data: flowData, name: flowName });
        enqueueSnackbar('Flow updated successfully!', { variant: 'success' });
      } catch (error) {
        enqueueSnackbar(`Error updating flow: ${error.message}`, { variant: 'error' });
      }
    } else {
      try {
        const newFlow = await createFlow({ flow_data: flowData, name: flowName });
        // window.location.href = `/flow/${newFlow.id}`; // Redirect to the new flow
        enqueueSnackbar('Flow created successfully!', { variant: 'success' });
      } catch (error) {
        enqueueSnackbar(`Error creating flow: ${error.message}`, { variant: 'error' });
      }
    }
  };

  const deleteCurrentFlow = async () => {
    if (flowId) {
      try {
        await deleteFlow(flowId);
        enqueueSnackbar('Flow deleted successfully!', { variant: 'success' });
        window.location.href = '/flow'; // 重定向到流程编辑器页面，而不是根路径
      } catch (error) {
        enqueueSnackbar(`Error deleting flow: ${error.message}`, { variant: 'error' });
      }
    } else {
      enqueueSnackbar('No flow to delete.', { variant: 'warning' });
    }
  };

  // 计算节点的默认位置，避免重叠
  const getNextNodePosition = () => {
    // 基于现有节点数量计算新位置
    const offset = nodes.length * 50;
    return {
      x: 100 + (nodes.length % 3) * 250,
      y: 100 + Math.floor(nodes.length / 3) * 150 + offset % 50
    };
  };

  const onAddNode = (nodeData) => {
    const id = `${nodeData.type}-${Date.now()}`; // Generate a unique ID
    const newNode = {
      id: id,
      type: nodeData.type,
      data: nodeData.data,
      position: getNextNodePosition(), // 动态计算位置
    };
    setNodes((nds) => nds.concat(newNode));
  };

  // 处理拖拽操作
  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    console.log('拖拽悬停中...');
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      console.log('开始处理拖放...');
      
      // 检查是否在ReactFlow区域内
      if (!reactFlowWrapper.current || !reactFlowInstance) {
        console.error('ReactFlow实例或元素引用无效');
        return;
      }

      // 获取ReactFlow边界
      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      
      // 显示事件详情以便调试
      console.log('拖放事件对象:', {
        clientX: event.clientX,
        clientY: event.clientY,
        target: event.target,
        currentTarget: event.currentTarget,
        dataTransfer: {
          types: Array.from(event.dataTransfer.types),
          effectAllowed: event.dataTransfer.effectAllowed
        }
      });
      
      // 获取拖拽的节点类型数据
      const nodeType = event.dataTransfer.getData('application/reactflow-node');
      console.log('拖放的节点类型:', nodeType);
      
      if (!nodeType) {
        console.error('未能获取到节点类型数据');
        return;
      }

      // 计算鼠标位置相对于ReactFlow区域的坐标
      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });
      
      console.log('计算的放置位置:', position);

      // 创建一个基于类型的默认标签
      let label = '未知节点';
      switch(nodeType) {
        case 'input': label = '输入数据节点'; break;
        case 'process': label = '数据处理节点'; break;
        case 'output': label = '输出数据节点'; break;
        case 'decision': label = '决策节点'; break;
      }

      // 创建新节点
      const newNode = {
        id: `${nodeType}-${Date.now()}`,
        type: nodeType,
        position,
        data: { label },
      };

      // 添加节点到流程图
      setNodes((nds) => nds.concat(newNode));
      console.log('节点添加成功:', newNode);
    },
    [reactFlowInstance, setNodes]
  );

  const onUpdateNode = (nodeId, updatedNodeData) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return { ...node, data: updatedNodeData.data };
        }
        return node;
      })
    );
  };

  const onInit = (_reactFlowInstance) => {
    setReactFlowInstance(_reactFlowInstance);
    console.log('Flow初始化:', _reactFlowInstance ? '成功' : '失败');
    
    if (_reactFlowInstance) {
      console.log('ReactFlow实例方法:', Object.keys(_reactFlowInstance));
      console.log('ReactFlow视图:', _reactFlowInstance.toObject());
    }
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部工具栏 */}
      <Paper elevation={2} sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderRadius: 0 }}>
        <TextField
          label="Flow Name"
          variant="outlined"
          size="small"
          value={flowName}
          onChange={handleFlowNameChange}
          sx={{ width: '250px' }}
        />
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {/* 侧边栏切换按钮 */}
          <Tooltip title="切换侧边栏">
            <IconButton
              color="primary"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              sx={{ mr: 1 }}
            >
              <MenuIcon />
            </IconButton>
          </Tooltip>
          
          {/* 节点选择器按钮 */}
          <Tooltip title="节点选择器">
            <IconButton
              color="primary"
              onClick={handleNodeSelectorClick}
              sx={{ mr: 1 }}
            >
              <AddIcon />
            </IconButton>
          </Tooltip>
          
          {/* 节点选择器下拉菜单 */}
          <Menu
            id="node-selector-menu"
            anchorEl={nodeSelectorAnchorEl}
            open={isNodeSelectorOpen}
            onClose={handleNodeSelectorClose}
            PaperProps={{
              sx: {
                width: '280px',
                maxWidth: '100%',
                p: 1
              }
            }}
          >
            <Box sx={{ p: 1, textAlign: 'center', fontWeight: 'bold' }}>
              节点选择器
            </Box>
            <Divider sx={{ my: 1 }} />
            <NodeSelector onNodeSelect={(nodeType) => {
              if (nodeType && nodeType.id) {
                onAddNode({
                  type: nodeType.id,
                  data: { label: nodeType.label }
                });
                handleNodeSelectorClose();
              }
            }} />
          </Menu>
          
          {/* 专用拖拽创建节点区域 */}
          <Paper
            elevation={2}
            sx={{
              display: 'flex',
              alignItems: 'center',
              ml: 2,
              mr: 2,
              p: 1,
              borderRadius: 1,
              border: '1px dashed #666'
            }}
          >
            <Box sx={{ display: 'flex', gap: 1 }}>
              {nodeTypes && Object.keys(nodeTypes).map(type => (
                <Box
                  key={type}
                  draggable
                  onDragStart={(event) => {
                    console.log('直接拖拽开始:', type);
                    event.dataTransfer.setData('application/reactflow-node', type);
                    event.dataTransfer.effectAllowed = 'move';
                  }}
                  sx={{
                    bgcolor: type === 'input' ? '#4caf50' :
                            type === 'process' ? '#2196f3' :
                            type === 'output' ? '#ff9800' :
                            type === 'decision' ? '#9c27b0' : '#777',
                    color: 'white',
                    p: 0.5,
                    px: 1,
                    borderRadius: 1,
                    fontSize: '0.8rem',
                    cursor: 'grab',
                    '&:hover': {
                      opacity: 0.8,
                      boxShadow: '0 0 5px rgba(0,0,0,0.3)'
                    }
                  }}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </Box>
              ))}
            </Box>
          </Paper>

          {/* 快速添加节点按钮 */}
          <Button
            variant="contained"
            color="success"
            sx={{ mr: 1 }}
            onClick={() => onAddNode({
              type: 'input',
              data: { label: '输入节点' }
            })}
          >
            添加输入节点
          </Button>
          <Button
            variant="contained"
            color="info"
            sx={{ mr: 1 }}
            onClick={() => onAddNode({
              type: 'process',
              data: { label: '处理节点' }
            })}
          >
            添加处理节点
          </Button>
          
          {/* 流程操作按钮 */}
          <Button variant="contained" color="primary" sx={{ mr: 1 }} onClick={saveFlow}>
            保存
          </Button>
          {flowId && (
            <Button variant="contained" color="error" onClick={deleteCurrentFlow}>
              删除
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
            defaultZoom={1.2}
            maxZoom={2}
            minZoom={0.5}
            fitView
            sx={{ bgcolor: '#f5f5f5' }}
          >
            <Controls showInteractive={true} />
            <Background variant="dots" gap={12} size={1} color="#99A1A8" />
          </ReactFlow>
        </Box>
        
        {/* 右侧属性面板 */}
        <Box sx={{ width: 300, p: 2, borderLeft: '1px solid #ddd', backgroundColor: '#fff' }}>
          <NodeProperties node={selectedNode} onNodePropertyChange={onNodePropertyChange} />
          <GlobalVariables />
          <ChatInterface onAddNode={onAddNode} onUpdateNode={onUpdateNode} />
        </Box>
      </Box>
    </Box>
  );
};

FlowEditor.propTypes = {
  flowId: PropTypes.string,
};

const FlowEditorWrapper = ({ flowId }) => (
  <ReactFlowProvider>
    <FlowEditor flowId={flowId} />
  </ReactFlowProvider>
);

FlowEditorWrapper.propTypes = {
  flowId: PropTypes.string,
};

export default FlowEditorWrapper;
