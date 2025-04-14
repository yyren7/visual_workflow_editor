// frontend/src/components/FlowEditor.tsx
import React, { useState, useCallback, useRef, useEffect } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  Background,
  Node,
  Edge,
  Connection,
  NodeMouseHandler,
  ReactFlowInstance,
  NodeTypes,
  BackgroundVariant,
  DefaultEdgeOptions,
  ConnectionLineType,
  MarkerType,
  Panel,
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

// --- Redux Imports ---
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../store/store';
import {
  fetchFlowById,
  setCurrentFlowId,
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
  flowUndo,
  flowRedo,
  selectCanUndo,
  selectCanRedo,
  updateNodeData,
  setNodes,
  setEdges,
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

// 自定义节点类型
const nodeTypes: NodeTypes = {
  input: InputNode,
  output: OutputNode,
  process: ProcessNode,
  decision: DecisionNode,
  generic: GenericNode, // 添加通用节点类型
  condition: ConditionNode, // 添加条件判断节点类型
};

const SAVE_DEBOUNCE_MS = 2000; // Debounce time for saving (e.g., 2 seconds)

const FlowEditor: React.FC<FlowEditorProps> = ({ flowId: flowIdFromProps }) => {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { enqueueSnackbar } = useSnackbar();
  const { isAuthenticated, logout } = useAuth();
  const dispatch = useDispatch<AppDispatch>();

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
  const canUndo = useSelector(selectCanUndo);
  const canRedo = useSelector(selectCanRedo);

  // Ref to track if it's the initial load to prevent immediate save
  const isInitialLoad = useRef(true);

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
          if (currentFlowId && !isLoading && !isSaving && !isInitialLoad.current) {
                console.log("FlowEditor: Debounced save triggered.");
                dispatch(saveFlow());
          } else {
              console.log("FlowEditor: Debounced save skipped (conditions not met).");
          }
      }, SAVE_DEBOUNCE_MS),
      [dispatch, currentFlowId, isLoading, isSaving]
  );

  // --- Effect to trigger debounced save on changes (now relies on history changes) ---
  useEffect(() => {
    if (!isInitialLoad.current) {
        console.log("FlowEditor: Detected change in nodes/edges/name via Redux state. Debouncing save...");
        debouncedSave();
    }
    return () => {
        debouncedSave.cancel();
    };
  }, [nodes, edges, flowName, debouncedSave]);

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
    onNodeClick,
    onPaneClick,
    onDragOver,
    onDrop,
    handleNodeDataUpdate,
    deleteSelectedElements,
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
  } = usePanelManager();

  // --- UI State (Local) ---
  const [flowSelectOpen, setFlowSelectOpen] = useState<boolean>(false);

  // Layout Hook
  const { performLayout } = useFlowLayout({ reactFlowInstance });
  const handleLayout = useCallback(() => {
    performLayout(nodes, edges, (newNodes: Node<NodeData>[], newEdges: Edge[]) => {
        console.log("Dispatching layout changes via setNodes/setEdges");
        dispatch(setNodes(newNodes));
        dispatch(setEdges(newEdges));
    });
  }, [nodes, edges, dispatch, performLayout]);

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

  const handleNodeSelectFromEvent = useCallback((nodeId: string, position?: { x: number; y: number }) => {
    console.log(`FlowEditor: Handling node selection for ${nodeId}`);
    const nodeToSelect = nodes.find((n: Node<NodeData>) => n.id === nodeId);
    if (nodeToSelect) {
      setSelectedNode(nodeToSelect);
      dispatch(setNodes(nodes.map((n: Node<NodeData>) => ({ ...n, selected: n.id === nodeId }))));
      if (position && reactFlowInstance) {
        reactFlowInstance.setCenter(position.x, position.y, { duration: 800 });
      }
    } else {
      console.warn(`FlowEditor: Node ${nodeId} not found.`);
    }
  }, [nodes, dispatch, setSelectedNode, reactFlowInstance]);

  // --- Undo/Redo Handlers ---
  const handleUndo = useCallback(() => {
    dispatch(flowUndo());
  }, [dispatch]);

  const handleRedo = useCallback(() => {
    dispatch(flowRedo());
  }, [dispatch]);

  // --- Keyboard Listener for Delete ---
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const targetElement = event.target as HTMLElement;
      const isInputFocused = targetElement.tagName === 'INPUT' || targetElement.tagName === 'TEXTAREA' || targetElement.isContentEditable;

      if ((event.key === 'Delete' || event.key === 'Backspace') && !isInputFocused) {
        event.preventDefault();
        console.log("Delete/Backspace pressed, calling deleteSelectedElements");
        deleteSelectedElements();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [deleteSelectedElements]);

  // --- Rendering ---

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
        onUndo={handleUndo}
        onRedo={handleRedo}
        canUndo={canUndo}
        canRedo={canRedo}
      />

      <Box sx={{ display: 'flex', flexGrow: 1, position: 'relative' }}>
        <NodeSelectorSidebar open={sidebarOpen} />

        <Box sx={{ flexGrow: 1, height: '100%', position: 'relative' }} ref={reactFlowWrapper}>
          {isLoading && currentFlowId && (
            <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(255, 255, 255, 0.7)', zIndex: 10 }}>
              <CircularProgress />
              <Typography sx={{ ml: 2 }}>{t('flowEditor.loadingFlow')}</Typography>
          </Box>
        )}
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
            onNodeClick={onNodeClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            defaultEdgeOptions={defaultEdgeOptions}
            connectionLineStyle={connectionLineStyle}
            fitView
            reactFlowWrapperRef={reactFlowWrapper}
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
            onNodeDataChange={(id: string, data: Partial<NodeData>) => {
              handleNodeDataUpdate({ id, data });
            }}
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
            onNodeSelect={handleNodeSelectFromEvent}
          />
        )}

        <FlowSelect open={flowSelectOpen} onClose={handleCloseFlowSelect} />
      </Box>
    </Box>
  );
};

export default FlowEditor;