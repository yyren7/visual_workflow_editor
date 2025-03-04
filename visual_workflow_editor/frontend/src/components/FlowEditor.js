## frontend/src/components/FlowEditor.js
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
import { Box, Button, Typography, TextField, Snackbar, Alert } from '@mui/material';
import Sidebar from './Sidebar';
import NodeProperties from './NodeProperties';
import GlobalVariables from './GlobalVariables';
import ChatInterface from './ChatInterface';
import { createFlow, getFlow, updateFlow, deleteFlow } from '../api/api';
import { useSnackbar } from 'notistack';
import PropTypes from 'prop-types';

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

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

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
        window.location.href = '/'; // Redirect to home
      } catch (error) {
        enqueueSnackbar(`Error deleting flow: ${error.message}`, { variant: 'error' });
      }
    } else {
      enqueueSnackbar('No flow to delete.', { variant: 'warning' });
    }
  };

  const onAddNode = (nodeData) => {
    const id = `${nodeData.type}-${Date.now()}`; // Generate a unique ID
    const newNode = {
      id: id,
      type: nodeData.type,
      data: nodeData.data,
      position: { x: 100, y: 100 }, // Default position
    };
    setNodes((nds) => nds.concat(newNode));
  };

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

  const onLoad = (_reactFlowInstance) => {
    setReactFlowInstance(_reactFlowInstance);
    console.log('flow loaded:', _reactFlowInstance);
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex' }}>
      <Sidebar isOpen={sidebarOpen} toggleSidebar={toggleSidebar} />
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <TextField
            label="Flow Name"
            variant="outlined"
            size="small"
            value={flowName}
            onChange={handleFlowNameChange}
          />
          <Box>
            <Button variant="contained" color="primary" sx={{ mr: 1 }} onClick={saveFlow}>
              Save
            </Button>
            {flowId && (
              <Button variant="contained" color="error" onClick={deleteCurrentFlow}>
                Delete
              </Button>
            )}
          </Box>
        </Box>
        <Box ref={reactFlowWrapper} sx={{ flexGrow: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onLoad={onLoad}
            fitView
            sx={{ bgcolor: '#f0f0f0' }}
          >
            <Controls />
            <Background variant="dots" gap={20} size={0.5} />
          </ReactFlow>
        </Box>
      </Box>
      <Box sx={{ width: 300, p: 2, borderLeft: '1px solid #ccc' }}>
        <NodeProperties node={selectedNode} onNodePropertyChange={onNodePropertyChange} />
        <GlobalVariables />
        <ChatInterface onAddNode={onAddNode} onUpdateNode={onUpdateNode} />
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
