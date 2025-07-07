import React, { useState, useCallback, useRef, useEffect, lazy } from 'react';
import {
  Node,
  Edge,
  Panel,
  NodeMouseHandler,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Box,
  Button,
  Typography,
  CircularProgress,
  Alert
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import LanguageSelector from '../LanguageSelector';
import VersionInfo from '../VersionInfo';
import FlowSelect from '../FlowSelect';

// Redux Imports
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch } from '../../store/store';
import {
  fetchFlowById,
  setCurrentFlowId,
  setNodes as setFlowNodes,
  setEdges as setFlowEdges,
  setFlowName as setReduxFlowName,
  selectCurrentFlowId,
  selectFlowName,
  selectNodes,
  selectEdges,
  selectAgentState,
  selectIsFlowLoading,
  selectFlowError,
  selectIsSaving,
  selectSaveError,
  selectLastSaveTime,
  selectNode,
} from '../../store/slices/flowSlice';

// Import custom hooks
import { usePanelManager } from '../../hooks/usePanelManager';
import { useFlowLayout } from '../../hooks/useFlowLayout';
import { useReactFlowManager } from '../../hooks/useReactFlowManager';
import { useLangGraphNodes } from '../../hooks/useLangGraphNodes';

// Import UI components
import EditorAppBar from '../EditorAppBar';
// import NodeSelectorSidebar from '../editor/NodeSelectorSidebar'; // 1. 注释掉直接导入
import NodePropertiesPanel from '../editor/NodePropertiesPanel';
import FlowVariablesPanel from '../editor/FlowVariablesPanel';
import ChatPanel from '../editor/ChatPanel';
import FlowCanvas from '../FlowCanvas';

// Import local hooks and components
import { useFlowConfig } from './useFlowConfig';
import { useSaveHandler } from './useSaveHandler';
import { LANGGRAPH_NODE_TYPES } from './viewportUtils';
import FlowDebugPanel from './FlowDebugPanel';
import { FlowEditorProps, NodeData } from './types';

// 1. 使用 React.lazy 动态导入 NodeSelectorSidebar
const NodeSelectorSidebar = lazy(() => import('../editor/NodeSelectorSidebar'));

const FlowEditor: React.FC<FlowEditorProps> = ({ flowId: flowIdFromProps }) => {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { enqueueSnackbar } = useSnackbar();
  const { isAuthenticated, logout } = useAuth();
  const dispatch = useDispatch<AppDispatch>();

  // --- Get State from Redux ---
  const currentFlowId = useSelector(selectCurrentFlowId);
  const flowName = useSelector(selectFlowName);
  const nodes = useSelector(selectNodes) ?? [];
  const edges = useSelector(selectEdges) ?? [];
  const agentState = useSelector(selectAgentState);
  const isLoading = useSelector(selectIsFlowLoading);
  const error = useSelector(selectFlowError);
  const isSaving = useSelector(selectIsSaving);
  const saveError = useSelector(selectSaveError);
  const lastSaveTime = useSelector(selectLastSaveTime);

  // --- Local State for Dragging ---
  const [isDraggingNode, setIsDraggingNode] = useState(false);

  // Use flow configuration hook
  const {
    nodeTypes,
    processedNodes,
    reactFlowConfig,
    defaultEdgeOptions,
    connectionLineStyle,
    debugAgentState
  } = useFlowConfig({ nodes, edges, agentState });

  // Use save handler hook
  const { isInitialLoad } = useSaveHandler({
    nodes,
    edges,
    flowName: flowName || '',
    currentFlowId,
    isLoading,
    isSaving,
    isDraggingNode
  });

  // Use LangGraph nodes hook
  const { syncLangGraphNodes } = useLangGraphNodes(agentState);

  // --- Effect to handle flowId changes (fetch) ---
  useEffect(() => {
    const targetFlowId = flowIdFromProps || null;
    if (targetFlowId) {
      if (!currentFlowId || targetFlowId !== currentFlowId) {
        console.log(`FlowEditor: Dispatching fetch for flowId: ${targetFlowId}`);
        dispatch(fetchFlowById(targetFlowId));
      }
    } else {
      console.log("FlowEditor: No flowId provided.");
    }
  }, [flowIdFromProps, currentFlowId, dispatch]);

  // --- Effect to show save errors ---
  useEffect(() => {
    if (saveError) {
      enqueueSnackbar(`${t('flowEditor.saveError')}: ${saveError}`, { variant: 'error' });
    }
  }, [saveError, enqueueSnackbar, t]);

  // --- React Flow State (via Hook) ---
  const {
    onNodesChange,
    onEdgesChange,
    selectedNode,
    setSelectedNode,
    reactFlowInstance,
    onConnect,
    onInit,
    onPaneClick,
    onDragOver,
    onDrop,
    handleNodeDataUpdate,
    onNodesDelete,
    onEdgesDelete,
  } = useReactFlowManager({
    reactFlowWrapperRef: reactFlowWrapper,
  });

  // --- Panel State (via Hook) ---
  const {
    panelStates,
    togglePanel,
    openPanel,
    closePanel,
    nodeInfoPosition,
    globalVarsPosition,
  } = usePanelManager();

  // Layout Hook
  const { performLayout } = useFlowLayout({ reactFlowInstance });
  const handleLayout = useCallback(() => {
    performLayout(nodes, edges, (newNodes: Node<NodeData>[], newEdges: Edge[]) => {
      dispatch(setFlowNodes(newNodes));
      dispatch(setFlowEdges(newEdges));
    });
  }, [nodes, edges, dispatch, performLayout, reactFlowInstance]);

  // --- Event Handlers & Callbacks ---
  const handleFlowSelect = useCallback(() => {
    openPanel('flowSelectOpen');
  }, [openPanel]);

  const handleFlowNameChange = useCallback((newName: string) => {
    dispatch(setReduxFlowName(newName));
  }, [dispatch]);

  const handleNodeClick: NodeMouseHandler = useCallback((event: React.MouseEvent, node: Node) => {
    // 重要：首先调用 Redux action 来更新节点选择状态
    dispatch(selectNode(node.id));
    
    // LangGraph节点不需要打开属性面板，它们是自包含的
    if (LANGGRAPH_NODE_TYPES.includes(node.type || '')) {
      setSelectedNode(node);
      console.log('LangGraph node clicked (no panel):', node);
      return; // 不打开属性面板
    }
    
    setSelectedNode(node);
    openPanel('nodeInfoOpen');
    console.log('Node clicked (FlowEditor):', node);
  }, [setSelectedNode, openPanel, dispatch]);

  // Intermediate callback for NodePropertiesPanel
  const handlePanelNodeDataChange = useCallback((id: string, data: Partial<NodeData>) => {
    handleNodeDataUpdate({ id, data });
  }, [handleNodeDataUpdate]);

  // Callback for ChatPanel node selection
  const handleNodeSelectFromChat = useCallback((nodeId: string, position?: { x: number; y: number }) => {
    const nodeToSelect = nodes.find((n: Node) => n.id === nodeId);
    if (nodeToSelect) {
      setSelectedNode(nodeToSelect);
      
      // LangGraph节点不需要打开属性面板
      if (!LANGGRAPH_NODE_TYPES.includes(nodeToSelect.type || '')) {
        openPanel('nodeInfoOpen');
      }
      
      // Optional: Center view on the node
      if (position && reactFlowInstance) {
        reactFlowInstance.setCenter(position.x, position.y, { duration: 800 });
      }
    } else {
      console.warn(`FlowEditor: Node ${nodeId} not found for chat panel selection.`);
    }
  }, [nodes, setSelectedNode, openPanel, reactFlowInstance]);

  // --- Drag Handlers ---
  const handleNodeDragStart = useCallback(() => {
    console.log("FlowEditor: Node drag start.");
    setIsDraggingNode(true);
  }, []);

  const handleNodeDragStop = useCallback(() => {
    console.log("FlowEditor: Node drag stop.");
    const timer = setTimeout(() => {
      setIsDraggingNode(false);
    }, 50); // 50ms delay

    return () => clearTimeout(timer);
  }, []);

  // --- Loading and Error States ---
  if (!currentFlowId && !isLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', p: 3 }}>
        <Typography variant="h5" gutterBottom>{t('flowEditor.noFlowSelectedTitle')}</Typography>
        <Typography sx={{ mb: 3 }}>{t('flowEditor.noFlowSelectedMessage')}</Typography>
        <Button variant="contained" onClick={handleFlowSelect}>{t('flowEditor.selectOrCreateFlow')}</Button>
        <FlowSelect open={panelStates.flowSelectOpen} onClose={() => closePanel('flowSelectOpen')} />
      </Box>
    );
  }

  // --- Main Render ---
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <EditorAppBar
        flowName={flowName || ''}
        onFlowNameChange={handleFlowNameChange}
        onSelectFlowClick={handleFlowSelect}
        onToggleSidebar={() => togglePanel('sidebarOpen')}
        onToggleGlobalVars={() => togglePanel('globalVarsOpen')}
        onToggleChat={() => togglePanel('chatOpen')}
        isAuthenticated={isAuthenticated}
        onLogout={logout}
        isSaving={isSaving}
        lastSaveTime={lastSaveTime}
        chatOpen={panelStates.chatOpen}
      />

      {/* 调试面板 */}
      <FlowDebugPanel
        currentFlowId={currentFlowId}
        agentState={agentState}
        nodes={nodes}
        onDebugAgentState={debugAgentState}
      />

      <Box sx={{ display: 'flex', flexGrow: 1, position: 'relative' }}>
        {/* 使用 React.Suspense 包裹懒加载的组件 */}
        <React.Suspense fallback={
          <Box sx={{
            width: panelStates.sidebarOpen ? '250px' : '0px',
            transition: 'width 0.3s ease',
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRight: '1px solid #333'
          }}>
            {panelStates.sidebarOpen && <CircularProgress size={24} />}
          </Box>
        }>
          <NodeSelectorSidebar open={panelStates.sidebarOpen} />
        </React.Suspense>

        <Box 
          sx={{ 
            flexGrow: 1, 
            height: '100%', 
            position: 'relative',
            transition: 'margin-right 0.3s ease',
          }} 
          ref={reactFlowWrapper}
        >
          {isLoading && (
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                zIndex: 12, // Ensure it's above the canvas
              }}
            >
              <CircularProgress />
              <Typography sx={{ ml: 2, color: 'white' }}>{t('flowEditor.loadingFlow')}</Typography>
            </Box>
          )}
          {error && (
            <Alert severity="error" sx={{ position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)', zIndex: 11 }}>
              {t('flowEditor.errorLoadingFlow')}: {error}
            </Alert>
          )}
          <FlowCanvas
            nodes={processedNodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={onInit}
            onPaneClick={onPaneClick}
            onNodeClick={handleNodeClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            defaultEdgeOptions={defaultEdgeOptions}
            connectionLineStyle={connectionLineStyle}
            fitView
            reactFlowWrapperRef={reactFlowWrapper}
            onAutoLayout={handleLayout}
            onNodeDragStart={handleNodeDragStart}
            onNodeDragStop={handleNodeDragStop}
            onNodesDelete={onNodesDelete}
            onEdgesDelete={onEdgesDelete}
            reactFlowConfig={reactFlowConfig}
          >
            <Panel position="top-right">
              <VersionInfo />
              <LanguageSelector />
            </Panel>
          </FlowCanvas>
        </Box>

        {selectedNode && panelStates.nodeInfoOpen && (
          <NodePropertiesPanel
            node={selectedNode}
            isOpen={panelStates.nodeInfoOpen}
            onClose={() => closePanel('nodeInfoOpen')}
            onNodeDataChange={handlePanelNodeDataChange}
            initialPosition={nodeInfoPosition}
          />
        )}

        {panelStates.globalVarsOpen && (
          <FlowVariablesPanel
            isOpen={panelStates.globalVarsOpen}
            onClose={() => togglePanel('globalVarsOpen')}
            initialPosition={globalVarsPosition}
          />
        )}

        {panelStates.chatOpen && currentFlowId && (
          <ChatPanel
            flowId={currentFlowId}
            isOpen={panelStates.chatOpen}
            onClose={() => togglePanel('chatOpen')}
            onNodeSelect={handleNodeSelectFromChat}
          />
        )}

        <FlowSelect open={panelStates.flowSelectOpen} onClose={() => closePanel('flowSelectOpen')} />
      </Box>
    </Box>
  );
};

export default FlowEditor;
