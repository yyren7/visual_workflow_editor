// frontend/src/components/FlowEditor.tsx
import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  Node,
  Edge,
  NodeTypes,
  DefaultEdgeOptions,
  MarkerType,
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
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';
import FlowSelect from './FlowSelect';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { getFlow, updateFlow, getLastChatIdForFlow } from '../api/flowApi'; // Ignore unused 'updateFlow' as it IS used in debounced effect
import GenericNode from './nodes/GenericNode';
import { LangGraphInputNode } from './nodes/LangGraphInputNode';
import { LangGraphTaskNode } from './nodes/LangGraphTaskNode';
import { LangGraphDetailNode } from './nodes/LangGraphDetailNode';
import { debounce } from 'lodash';
import { getNodeTemplates, NodeTemplatesResponse } from '../api/nodeTemplates'; // Import API function and type

// --- Redux Imports ---
import { useSelector, useDispatch } from 'react-redux';
import { AppDispatch } from '../store/store';
import {
  fetchFlowById,
  ensureFlowAgentStateThunk,
  setCurrentFlowId,
  setNodes as setFlowNodes,
  setEdges as setFlowEdges,
  setFlowName as setReduxFlowName,
  saveFlow,
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
} from '../store/slices/flowSlice';

// Import custom hooks
import { usePanelManager } from '../hooks/usePanelManager';
import { useFlowLayout } from '../hooks/useFlowLayout';
import { useReactFlowManager } from '../hooks/useReactFlowManager';
import { useLangGraphNodes } from '../hooks/useLangGraphNodes';

// Import UI components
import EditorAppBar from './EditorAppBar'; // Import the new AppBar component
import NodeSelectorSidebar from './editor/NodeSelectorSidebar';
import NodePropertiesPanel from './editor/NodePropertiesPanel';
import FlowVariablesPanel from './editor/FlowVariablesPanel';
import ChatPanel from './editor/ChatPanel';
import FlowCanvas from './FlowCanvas'; // Import the new canvas component

// 节点数据接口定义
export interface NodeData {
  label: string;
  description?: string;
  [key: string]: any;
}

// 流程编辑器属性接口
interface FlowEditorProps {
  flowId?: string;
}

// Base node types with specific components
const baseNodeTypes: NodeTypes = {
  // input: InputNode,
  // output: OutputNode,
  // process: ProcessNode,
  // decision: DecisionNode,
  // condition: ConditionNode, // Specific component for 'condition'
  // generic: GenericNode, // Keep a generic fallback just in case
  langgraph_input: LangGraphInputNode,
  langgraph_task: LangGraphTaskNode,
  langgraph_detail: LangGraphDetailNode,
};

const SAVE_DEBOUNCE_MS = 100;

// LangGraph节点类型常量
const LANGGRAPH_NODE_TYPES = ['langgraph_input', 'langgraph_task', 'langgraph_detail'];

const FlowEditor: React.FC<FlowEditorProps> = ({ flowId: flowIdFromProps }) => {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { enqueueSnackbar } = useSnackbar();
  const { isAuthenticated, logout } = useAuth();
  const dispatch = useDispatch<AppDispatch>();

  // --- State for Node Templates ---
  const [nodeTemplates, setNodeTemplates] = useState<NodeTemplatesResponse | null>(null);
  const [templatesLoading, setTemplatesLoading] = useState<boolean>(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);

  // --- Get State from Redux ---
  const currentFlowId = useSelector(selectCurrentFlowId);
  const flowName = useSelector(selectFlowName);
  const nodes = useSelector(selectNodes);
  const edges = useSelector(selectEdges);
  const agentState = useSelector(selectAgentState);
  const isLoading = useSelector(selectIsFlowLoading);
  const error = useSelector(selectFlowError);
  const isSaving = useSelector(selectIsSaving);
  const saveError = useSelector(selectSaveError);
  const lastSaveTime = useSelector(selectLastSaveTime);

  // --- Local State for Dragging ---
  const [isDraggingNode, setIsDraggingNode] = useState(false);

  // Ref to track if it's the initial load to prevent immediate save
  const isInitialLoad = useRef(true);
  
  // Use LangGraph nodes hook
  const { syncLangGraphNodes } = useLangGraphNodes(agentState);

  // 新增：动态边界计算函数
  const calculateDynamicViewport = useCallback(() => {
    if (!nodes || nodes.length === 0) {
      return {
        x: [0, 800],
        y: [0, 600],
        zoom: [0.1, 1.5]
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
      x: [minX - margin, maxX + margin],
      y: [minY - margin, maxY + margin],
      zoom: [0.1, 2.0] // 允许一定程度的缩放
    };
  }, [nodes]);

  // 新增：设置LangGraph节点不可拖动
  const processedNodes = useMemo(() => {
    return nodes.map(node => ({
      ...node,
      draggable: !LANGGRAPH_NODE_TYPES.includes(node.type || ''), // LangGraph节点不可拖动
      dragHandle: LANGGRAPH_NODE_TYPES.includes(node.type || '') ? undefined : '.drag-handle', // LangGraph节点没有拖拽句柄
      // 确保LangGraph节点有固定尺寸和位置限制
      ...(LANGGRAPH_NODE_TYPES.includes(node.type || '') && {
        style: {
          ...node.style,
          width: node.type === 'langgraph_input' ? 600 : (node.type === 'langgraph_detail' ? 350 : 400),
          height: node.type === 'langgraph_input' ? 400 : (node.type === 'langgraph_detail' ? 400 : 300),
          pointerEvents: 'auto' as const, // 修复类型错误
        },
        selectable: true, // 仍然可选择
        deletable: false, // 不可删除
      })
    }));
  }, [nodes]);

  // 新增：ReactFlow实例配置，包含动态边界限制
  const reactFlowConfig = useMemo(() => {
    const viewport = calculateDynamicViewport();
    return {
      translateExtent: [
        [viewport.x[0], viewport.y[0]], 
        [viewport.x[1], viewport.y[1]]
      ] as [[number, number], [number, number]],
      nodeExtent: [
        [viewport.x[0], viewport.y[0]], 
        [viewport.x[1], viewport.y[1]]
      ] as [[number, number], [number, number]],
      minZoom: viewport.zoom[0],
      maxZoom: viewport.zoom[1],
    };
  }, [calculateDynamicViewport]);

  // --- Effect to fetch Node Templates ---
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setTemplatesLoading(true);
        setTemplatesError(null);
        const templates = await getNodeTemplates();
        setNodeTemplates(templates);
        console.log("FlowEditor: Node templates fetched successfully.", templates);
      } catch (error: any) {
        console.error("FlowEditor: Failed to fetch node templates:", error);
        setTemplatesError(error.message || 'Failed to load node templates');
        enqueueSnackbar(t('flowEditor.errorLoadingTemplates'), { variant: 'error' });
      } finally {
        setTemplatesLoading(false);
      }
    };
    fetchTemplates();
  }, [enqueueSnackbar, t]); // Dependencies for the effect

  // --- Dynamically generate nodeTypes using useMemo ---
  const nodeTypes = useMemo(() => {
    const dynamicTypes: NodeTypes = { ...baseNodeTypes };
    if (nodeTemplates) {
      Object.keys(nodeTemplates).forEach((templateKey) => {
        const template = nodeTemplates[templateKey];
        if (template && template.type && !(template.type in dynamicTypes)) {
          // If the type is not already defined in baseNodeTypes, map it to GenericNode
          dynamicTypes[template.type] = GenericNode;
          console.log(`FlowEditor: Mapping node type '${template.type}' to GenericNode.`);
        }
      });
    }
    console.log("FlowEditor: Final nodeTypes map:", dynamicTypes);
    return dynamicTypes;
  }, [nodeTemplates]); // Dependency: recalculate when nodeTemplates change

  // --- Effect to handle flowId changes (fetch) ---
  useEffect(() => {
    const targetFlowId = flowIdFromProps || null;
    if (targetFlowId !== currentFlowId) {
      isInitialLoad.current = true; // Reset flag when flow ID changes
      console.log(`FlowEditor: Prop flowId changed. Dispatching fetch...`);
      dispatch(setCurrentFlowId(targetFlowId));
      if (targetFlowId) {
        dispatch(fetchFlowById(targetFlowId))
          .then(() => {
            // After fetching, ensure agent_state is complete
            console.log("FlowEditor: Ensuring agent state after fetch...");
            return dispatch(ensureFlowAgentStateThunk(targetFlowId));
          })
          .then(() => {
            // After ensuring agent state, sync LangGraph nodes
            console.log("FlowEditor: Syncing LangGraph nodes after agent state ensure...");
            syncLangGraphNodes();
          })
          .finally(() => {
            // Set initial load complete *after* fetch finishes (success or fail)
            setTimeout(() => { isInitialLoad.current = false; }, 100); // Small delay
            console.log("FlowEditor: Initial fetch finished, allowing saves.");
        });
      }
    } else if (targetFlowId === currentFlowId && isLoading === false && isInitialLoad.current) {
        // Handle case where component mounts with correct ID already in redux but hasn't fetched
        // Or if fetch finished but flag wasn't set due to timing.
        isInitialLoad.current = false;
        console.log("FlowEditor: Initial load flag set to false (ID matched or fetch completed).");
    }
  }, [flowIdFromProps, currentFlowId, dispatch, isLoading]); // Add isLoading dependency

  // --- Debounced Save Function ---
  const debouncedSave = useCallback(
      debounce(() => {
          if (!isInitialLoad.current) { // Only save after initial load
                console.log("FlowEditor: Debounced save triggered.");
                dispatch(saveFlow());
          } else {
              console.log("FlowEditor: Debounced save skipped (initial load).");
          }
      }, SAVE_DEBOUNCE_MS),
      [dispatch] // Dispatch function is stable
  );

  // --- Effect to trigger debounced save on changes ---
  useEffect(() => {
    // Don't trigger save immediately after load or if loading/saving
    // AND Don't trigger save while a node is being dragged
    if (!isInitialLoad.current && currentFlowId && !isLoading && !isSaving && !isDraggingNode) {
      console.log("FlowEditor: Detected change and not dragging. Debouncing save...");
      debouncedSave();
    }
    // Cleanup function to cancel debounce if component unmounts or dependencies change
    return () => {
      debouncedSave.cancel();
    };
    // Remove isSaving from dependency array, keep isLoading for safety? Keep others.
  }, [nodes, edges, flowName, currentFlowId, debouncedSave, isLoading, isDraggingNode]);

  // --- Effect to show save errors ---
   useEffect(() => {
       if (saveError) {
           enqueueSnackbar(`${t('flowEditor.saveError')}: ${saveError}`, { variant: 'error' });
           // Optionally clear the error in redux state after showing?
           // dispatch(clearSaveError()); // Need to add this action if desired
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
  } = useReactFlowManager({
    reactFlowWrapperRef: reactFlowWrapper,
  });

  // --- Panel State (via Hook) ---
  const {
    toggleSidebar,
    closeNodeInfoPanel,
    handleCloseFlowSelect,
    sidebarOpen,
    nodeInfoOpen,
    globalVarsOpen,
    chatOpen,
    toggleGlobalVarsPanel,
    toggleChatPanel,
    nodeInfoPosition,
    globalVarsPosition,
    openNodeInfoPanel,
  } = usePanelManager();

  // --- UI State (Local) ---
  const [flowSelectOpen, setFlowSelectOpen] = useState<boolean>(false);

  // Layout Hook (Example usage, adjust as needed)
  const { performLayout } = useFlowLayout({ reactFlowInstance });
  const handleLayout = useCallback(() => {
    performLayout(nodes, edges, (newNodes: Node<NodeData>[], newEdges: Edge[]) => {
      dispatch(setFlowNodes(newNodes));
      dispatch(setFlowEdges(newEdges));
    });
  }, [nodes, edges, dispatch, performLayout, reactFlowInstance]);

  // *** Constants needed by ReactFlow ***
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
    type: 'smoothstep',
  };
  
  const connectionLineStyle = {
    stroke: '#1976d2',
    strokeWidth: 2,
    strokeDasharray: '5 5',
  };

  // --- Event Handlers & Callbacks ---

  const handleFlowSelect = useCallback(() => {
    setFlowSelectOpen(true);
  }, []);

  const handleFlowNameChange = useCallback((newName: string) => {
    dispatch(setReduxFlowName(newName));
  }, [dispatch]);

  const handleNodeClick: NodeMouseHandler = useCallback((event: React.MouseEvent, node: Node) => {
      // LangGraph节点不需要打开属性面板，它们是自包含的
      if (LANGGRAPH_NODE_TYPES.includes(node.type || '')) {
        setSelectedNode(node);
        console.log('LangGraph node clicked (no panel):', node);
        return; // 不打开属性面板
      }
      
      setSelectedNode(node);
      openNodeInfoPanel();
      console.log('Node clicked (FlowEditor):', node);
  }, [setSelectedNode, openNodeInfoPanel]);

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
          openNodeInfoPanel();
        }
        
        // Optional: Center view on the node
        if (position && reactFlowInstance) {
          reactFlowInstance.setCenter(position.x, position.y, { duration: 800 });
        }
      } else {
        console.warn(`FlowEditor: Node ${nodeId} not found for chat panel selection.`);
      }
    }, [nodes, setSelectedNode, openNodeInfoPanel, reactFlowInstance]);

  // --- Drag Handlers ---
  const handleNodeDragStart = useCallback(() => {
      console.log("FlowEditor: Node drag start.");
      setIsDraggingNode(true);
  }, []);

  const handleNodeDragStop = useCallback(() => {
      console.log("FlowEditor: Node drag stop.");
      // Introduce a small delay before setting dragging to false
      // This helps differentiate a click (instant dragStart/Stop) from a real drag
      // and prevents the save useEffect from triggering on simple clicks.
      const timer = setTimeout(() => {
          setIsDraggingNode(false);
      }, 50); // 50ms delay

      // Cleanup the timer if the component unmounts or drag starts again quickly
      return () => clearTimeout(timer);

      // Save is triggered by useEffect watching nodes/isDraggingNode changing AFTER the delay
  }, []);

  // --- Rendering ---

  // Handle template loading/error states
  if (templatesLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>{t('flowEditor.loadingTemplates')}</Typography>
      </Box>
    );
  }

  if (templatesError) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', p: 3 }}>
         <Alert severity="error" sx={{ mb: 2 }}>
           {t('flowEditor.errorLoadingTemplates')}: {templatesError}
         </Alert>
         {/* Optionally add a retry button */}
      </Box>
    );
  }

  if (isLoading && !currentFlowId) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>{t('flowEditor.loadingFlow')}</Typography>
      </Box>
    );
  }

  if (!currentFlowId && !isLoading && !flowIdFromProps) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', p: 3 }}>
        <Typography variant="h5" gutterBottom>{t('flowEditor.noFlowSelectedTitle')}</Typography>
        <Typography sx={{ mb: 3 }}>{t('flowEditor.noFlowSelectedMessage')}</Typography>
        <Button variant="contained" onClick={handleFlowSelect}>{t('flowEditor.selectOrCreateFlow')}</Button>
        <FlowSelect open={flowSelectOpen} onClose={handleCloseFlowSelect} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <EditorAppBar
        flowName={flowName}
        onFlowNameChange={handleFlowNameChange}
        onSelectFlowClick={handleFlowSelect}
        onToggleSidebar={toggleSidebar}
        onToggleGlobalVars={toggleGlobalVarsPanel}
        onToggleChat={toggleChatPanel}
        isAuthenticated={isAuthenticated}
        onLogout={logout}
        isSaving={isSaving}
        lastSaveTime={lastSaveTime}
        chatOpen={chatOpen}
      />

      <Box sx={{ display: 'flex', flexGrow: 1, position: 'relative' }}>
        <NodeSelectorSidebar open={sidebarOpen} />

        <Box 
          sx={{ 
            flexGrow: 1, 
            height: '100%', 
            position: 'relative',
            transition: 'margin-right 0.3s ease', // This transition might no longer be needed or could be adjusted
          }} 
          ref={reactFlowWrapper}
        >
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
            reactFlowConfig={reactFlowConfig}
          >
            <Panel position="top-right">
              <VersionInfo />
              <LanguageSelector />
            </Panel>
          </FlowCanvas>
        </Box>

        {selectedNode && nodeInfoOpen && (
          <NodePropertiesPanel
            node={selectedNode}
            isOpen={nodeInfoOpen}
            onClose={closeNodeInfoPanel}
            onNodeDataChange={handlePanelNodeDataChange}
            initialPosition={nodeInfoPosition}
          />
        )}

        {globalVarsOpen && (
          <FlowVariablesPanel
          isOpen={globalVarsOpen}
            onClose={toggleGlobalVarsPanel}
            initialPosition={globalVarsPosition}
          />
        )}

        {chatOpen && currentFlowId && (
          <ChatPanel
            flowId={currentFlowId}
            isOpen={chatOpen}
            onClose={toggleChatPanel}
            onNodeSelect={handleNodeSelectFromChat}
          />
        )}

        <FlowSelect open={flowSelectOpen} onClose={handleCloseFlowSelect} />
      </Box>
    </Box>
  );
};

export default FlowEditor;