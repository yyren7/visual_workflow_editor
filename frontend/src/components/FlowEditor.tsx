// frontend/src/components/FlowEditor.tsx
import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  Background,
  Node,
  Edge,
  Connection,
  ReactFlowInstance,
  NodeTypes,
  BackgroundVariant,
  DefaultEdgeOptions,
  ConnectionLineType,
  MarkerType,
  Panel,
  NodeMouseHandler,
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
  Typography,
  CircularProgress,
  Alert
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
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';
import FlowSelect from './FlowSelect';
import ConditionNode from './nodes/ConditionNode'; // 添加条件判断节点类型
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import SortIcon from '@mui/icons-material/Sort';
import { clearFlowCache } from './FlowLoader'; // 导入清除缓存的函数
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { getFlow, updateFlow, getLastChatIdForFlow } from '../api/flowApi'; // Ignore unused 'updateFlow' as it IS used in debounced effect
import InputNode from './nodes/InputNode';
import OutputNode from './nodes/OutputNode';
import ProcessNode from './nodes/ProcessNode';
import DecisionNode from './nodes/DecisionNode';
import GenericNode from './nodes/GenericNode';
import NodeProperties from './NodeProperties';
import FlowVariables from './FlowVariables';
import ChatInterface from './ChatInterface';
import NodeSelector from './NodeSelector';
import DraggableResizableContainer from './DraggableResizableContainer';
import { debounce } from 'lodash';
import { getNodeTemplates, NodeTemplatesResponse } from '../api/nodeTemplates'; // Import API function and type

// --- Redux Imports ---
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../store/store';
import {
  fetchFlowById,
  setCurrentFlowId,
  setNodes as setFlowNodes,
  setEdges as setFlowEdges,
  updateNodeData as updateFlowNodeData,
  setFlowName as setReduxFlowName,
  saveFlow,
  selectCurrentFlowId,
  selectFlowName,
  selectNodes,
  selectEdges,
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
  input: InputNode,
  output: OutputNode,
  process: ProcessNode,
  decision: DecisionNode,
  condition: ConditionNode, // Specific component for 'condition'
  generic: GenericNode, // Keep a generic fallback just in case
};

const SAVE_DEBOUNCE_MS = 100;

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
  const isLoading = useSelector(selectIsFlowLoading);
  const error = useSelector(selectFlowError);
  const isSaving = useSelector(selectIsSaving);
  const saveError = useSelector(selectSaveError);
  const lastSaveTime = useSelector(selectLastSaveTime);

  // --- Local State for Dragging ---
  const [isDraggingNode, setIsDraggingNode] = useState(false);

  // Ref to track if it's the initial load to prevent immediate save
  const isInitialLoad = useRef(true);

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
        dispatch(fetchFlowById(targetFlowId)).finally(() => {
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
    chatPosition,
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
        openNodeInfoPanel();
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
        onLayoutClick={handleLayout}
        onToggleSidebar={toggleSidebar}
        onToggleGlobalVars={toggleGlobalVarsPanel}
        onToggleChat={toggleChatPanel}
        isAuthenticated={isAuthenticated}
        onLogout={logout}
        isSaving={isSaving}
        lastSaveTime={lastSaveTime}
      />

      <Box sx={{ display: 'flex', flexGrow: 1, position: 'relative' }}>
        <NodeSelectorSidebar open={sidebarOpen} />

        <Box sx={{ flexGrow: 1, height: '100%', position: 'relative' }} ref={reactFlowWrapper}>
          {error && (
            <Alert severity="error" sx={{ position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)', zIndex: 11 }}>
              {t('flowEditor.errorLoadingFlow')}: {error}
            </Alert>
          )}
          <FlowCanvas
            nodes={nodes}
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
            initialPosition={chatPosition}
            onNodeSelect={handleNodeSelectFromChat}
          />
        )}

        <FlowSelect open={flowSelectOpen} onClose={handleCloseFlowSelect} />
      </Box>
    </Box>
  );
};

export default FlowEditor;