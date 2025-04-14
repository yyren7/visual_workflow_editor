import { useState, useCallback, useRef, Dispatch, SetStateAction } from 'react';
import {
  Node,
  Edge,
  Connection,
  NodeMouseHandler,
  ReactFlowInstance,
  XYPosition,
  NodeChange,
  EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
} from 'reactflow';
import { NodeData } from '../components/FlowEditor'; // Adjust path if needed
import { useSnackbar } from 'notistack';
import { useTranslation } from 'react-i18next';
import { v4 as uuidv4 } from 'uuid';

// --- Redux Imports ---
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../store/store';
import {
    setNodes as setFlowNodes,
    setEdges as setFlowEdges,
    updateNodeData as updateFlowNodeData,
    addNode as addFlowNode,
    addEdge as addFlowEdge,
    removeElements as removeFlowElements,
    selectNodes,
    selectEdges,
} from '../store/slices/flowSlice';

// Define the types for the hook's return value
interface UseReactFlowManagerOutput {
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  selectedNode: Node<NodeData> | null;
  setSelectedNode: Dispatch<SetStateAction<Node<NodeData> | null>>;
  reactFlowInstance: ReactFlowInstance | null;
  reactFlowWrapper: React.RefObject<HTMLDivElement>;
  onConnect: (connection: Connection) => void;
  onInit: (instance: ReactFlowInstance) => void;
  onNodeClick: NodeMouseHandler;
  onPaneClick: () => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: React.DragEvent) => void;
  handleNodeDataUpdate: (update: { id: string; data: Partial<NodeData> }) => void;
  deleteSelectedElements: () => void;
}

// Define props for the hook
interface UseReactFlowManagerProps {
  reactFlowWrapperRef: React.RefObject<HTMLDivElement>; // Receive the ref
}

export const useReactFlowManager = ({
  reactFlowWrapperRef,
}: UseReactFlowManagerProps): UseReactFlowManagerOutput => {
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const dispatch = useDispatch<AppDispatch>();

  // --- Get State from Redux ---
  const nodes = useSelector(selectNodes);
  const edges = useSelector(selectEdges);

  // --- Local State ---
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  // --- Handlers using Redux ---
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Apply changes using the helper and dispatch the result to Redux
      dispatch(setFlowNodes(applyNodeChanges(changes, nodes)));
    },
    [dispatch, nodes] // Dependency: dispatch and the current nodes state
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      // Apply changes using the helper and dispatch the result to Redux
      dispatch(setFlowEdges(applyEdgeChanges(changes, edges)));
    },
    [dispatch, edges] // Dependency: dispatch and the current edges state
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      // Add check for null source/target
      if (!connection.source || !connection.target) {
        console.error("Cannot connect edge: source or target is null", connection);
        return;
      }

      // connection.source and connection.target are guaranteed to be strings here
      const newEdge: Edge = {
          id: uuidv4(),
          type: 'smoothstep',
          source: connection.source, // Explicitly use the validated source
          target: connection.target, // Explicitly use the validated target
          sourceHandle: connection.sourceHandle,
          targetHandle: connection.targetHandle,
          // You might want to add other default edge properties if needed
      };

      dispatch(addFlowEdge(newEdge));
    },
    [dispatch]
  );

  const onInit = useCallback((instance: ReactFlowInstance) => {
    setReactFlowInstance(instance);
    console.log('React Flow instance initialized:', instance);
  }, []);

  const onNodeClick: NodeMouseHandler = useCallback((event, node) => {
    setSelectedNode(node);
    console.log('Node clicked (useReactFlowManager):', node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowWrapperRef.current || !reactFlowInstance) {
        console.error("React Flow wrapper or instance not available for drop event.");
        return;
      }

      const reactFlowBounds = reactFlowWrapperRef.current.getBoundingClientRect();
      const type = event.dataTransfer.getData('application/reactflow');
      const nodeLabel = event.dataTransfer.getData('application/nodeLabel') || t('nodes.newNode');
      const nodeDescription = event.dataTransfer.getData('application/nodeDescription') || '';

      if (typeof type === 'undefined' || !type) {
        return;
      }

      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      const newNode: Node<NodeData> = {
        id: uuidv4(),
        type,
        position,
        data: { label: nodeLabel, description: nodeDescription },
      };

      console.log('Node dropped (dispatching addFlowNode): ', newNode);
      // Dispatch the dedicated addFlowNode action
      dispatch(addFlowNode(newNode));

      enqueueSnackbar(t('flowEditor.nodeAdded', { type: nodeLabel }), { variant: 'success' });
    },
    [reactFlowInstance, dispatch, t, enqueueSnackbar, reactFlowWrapperRef] // Removed nodes dependency
  );

  // Function to update node data from properties panel
  const handleNodeDataUpdate = useCallback(
    (update: { id: string; data: Partial<NodeData> }) => {
        console.log("useReactFlowManager: dispatching updateFlowNodeData", update);
        dispatch(updateFlowNodeData(update));

      // Update local selected node state if the updated node is the selected one
      setSelectedNode((currentSelected) => {
        if (currentSelected && currentSelected.id === update.id) {
            return { ...currentSelected, data: { ...currentSelected.data, ...update.data } };
        }
        return currentSelected;
      });
    },
    [dispatch]
  );

  // Function to delete selected elements
  const deleteSelectedElements = useCallback(() => {
      if (!reactFlowInstance) {
          console.warn("deleteSelectedElements called before React Flow instance is ready.");
          return;
      }

      const selectedNodes = reactFlowInstance.getNodes().filter(n => n.selected);
      const selectedEdges = reactFlowInstance.getEdges().filter(e => e.selected);

      if (selectedNodes.length > 0 || selectedEdges.length > 0) {
          const nodeIdsToRemove = selectedNodes.map(n => n.id);
          const edgeIdsToRemove = selectedEdges.map(e => e.id);
          console.log("Dispatching removeFlowElements: ", { nodeIdsToRemove, edgeIdsToRemove });
          dispatch(removeFlowElements({ nodeIds: nodeIdsToRemove, edgeIds: edgeIdsToRemove }));
      } else {
          console.log("No elements selected for deletion.");
      }
  }, [reactFlowInstance, dispatch]);

  // --- Return values ---
  return {
    onNodesChange,
    onEdgesChange,
    selectedNode,
    setSelectedNode,
    reactFlowInstance,
    reactFlowWrapper: reactFlowWrapperRef,
    onConnect,
    onInit,
    onNodeClick,
    onPaneClick,
    onDragOver,
    onDrop,
    handleNodeDataUpdate,
    deleteSelectedElements,
  };
}; 