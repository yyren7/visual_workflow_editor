import { useState, useCallback, useRef, Dispatch, SetStateAction } from 'react';
import {
  Node,
  Edge,
  Connection,
  NodeMouseHandler,
  ReactFlowInstance,
  addEdge,
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
import _isEqual from 'lodash/isEqual'; // 引入 isEqual

// --- Redux Imports ---
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../store/store';
import {
    setNodes as setFlowNodes,
    setEdges as setFlowEdges,
    updateNodeData as updateFlowNodeData,
    addNode as addFlowNode, // Assuming an addNode action exists or will be added
    addEdge as addFlowEdge, // Assuming an addEdge action exists or will be added
    selectNodes,
    selectEdges,
} from '../store/slices/flowSlice';

// --- 辅助函数：比较节点数组，忽略 selected 属性 ---
function haveNodesChanged(currentNodes: Node[], nextNodes: Node[]): boolean {
  if (currentNodes.length !== nextNodes.length) {
    return true; // 长度不同，肯定变了
  }
  // 使用 Map 方便通过 ID 查找，理论上 O(N)
  const currentNodeMap = new Map(currentNodes.map(n => [n.id, n]));

  for (const nextNode of nextNodes) {
    const currentNode = currentNodeMap.get(nextNode.id);
    if (!currentNode) {
      return true; // 找到了新节点 ID，说明有增加
    }
    // 比较核心属性，忽略 selected
    if (
      currentNode.position.x !== nextNode.position.x ||
      currentNode.position.y !== nextNode.position.y ||
      currentNode.type !== nextNode.type ||
      currentNode.width !== nextNode.width ||  // 注意 width/height 可能为 undefined
      currentNode.height !== nextNode.height ||
      !_isEqual(currentNode.data, nextNode.data) // 深度比较 data
      // 可以根据需要添加其他需要比较的属性 (例如 zIndex, extent, etc.)
    ) {
      return true; // 发现实质性差异
    }
  }
   // 检查是否有节点被移除（旧 Map 中的 ID 在新数组中找不到）
  if (currentNodes.some(cn => !nextNodes.find(nn => nn.id === cn.id))) {
    return true;
  }

  return false; // 没有发现实质性差异
}

// --- 辅助函数：比较边数组，忽略 selected 属性 ---
function haveEdgesChanged(currentEdges: Edge[], nextEdges: Edge[]): boolean {
  if (currentEdges.length !== nextEdges.length) {
    return true; // 长度不同，肯定变了
  }
  const currentEdgeMap = new Map(currentEdges.map(e => [e.id, e]));

  for (const nextEdge of nextEdges) {
     const currentEdge = currentEdgeMap.get(nextEdge.id);
     if (!currentEdge) {
       return true; // 找到了新边 ID，说明有增加
     }
     // 比较核心属性，忽略 selected
     if (
       currentEdge.source !== nextEdge.source ||
       currentEdge.target !== nextEdge.target ||
       currentEdge.sourceHandle !== nextEdge.sourceHandle ||
       currentEdge.targetHandle !== nextEdge.targetHandle ||
       currentEdge.type !== nextEdge.type ||
       currentEdge.label !== nextEdge.label ||
       currentEdge.animated !== nextEdge.animated ||
       !_isEqual(currentEdge.data, nextEdge.data) || // 深度比较 data
       !_isEqual(currentEdge.style, nextEdge.style) || // 深度比较 style
       !_isEqual(currentEdge.markerStart, nextEdge.markerStart) || // 比较 marker
       !_isEqual(currentEdge.markerEnd, nextEdge.markerEnd)
       // 可以根据需要添加其他需要比较的属性 (zIndex, interactionWidth, etc.)
     ) {
       return true; // 发现实质性差异
     }
   }
   // 检查是否有边被移除
   if (currentEdges.some(ce => !nextEdges.find(ne => ne.id === ce.id))) {
     return true;
   }

  return false; // 没有发现实质性差异
}

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
      // dispatch(setFlowNodes(applyNodeChanges(changes, nodes)));
      // 计算下一个状态
      const nextNodes = applyNodeChanges(changes, nodes);
      // 比较当前状态和下一个状态，忽略 selected
      if (haveNodesChanged(nodes, nextNodes)) {
          console.log("useReactFlowManager: Substantive node changes detected, dispatching setFlowNodes.");
        // 只有在有实质变化时才 dispatch
        dispatch(setFlowNodes(nextNodes));
      } else {
          console.log("useReactFlowManager: Only selection node changes detected, skipping dispatch.");
          // 可选：如果需要立即更新画布上的选中状态（即使 Redux 未更新），
          // 可能需要一种不同的方式，但这通常由 React Flow 内部处理。
      }
    },
    [dispatch, nodes] // Dependency: dispatch and the current nodes state
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      // Apply changes using the helper and dispatch the result to Redux
      // dispatch(setFlowEdges(applyEdgeChanges(changes, edges)));
      // 计算下一个状态
      const nextEdges = applyEdgeChanges(changes, edges);
      // 比较当前状态和下一个状态，忽略 selected
      if (haveEdgesChanged(edges, nextEdges)) {
          console.log("useReactFlowManager: Substantive edge changes detected, dispatching setFlowEdges.");
        // 只有在有实质变化时才 dispatch
        dispatch(setFlowEdges(nextEdges));
      } else {
           console.log("useReactFlowManager: Only selection edge changes detected, skipping dispatch.");
      }
    },
    [dispatch, edges] // Dependency: dispatch and the current edges state
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      // Dispatch an action to add the edge (potentially via addEdge helper)
      // Assuming flowSlice handles the logic of actually adding the edge
       const newEdge = { ...connection, id: uuidv4() }; // Ensure edge has an ID if needed by slice
       dispatch(setFlowEdges(addEdge(newEdge, edges))); // Use React Flow's addEdge helper with current edges
       // OR: If you have a dedicated addEdge action:
       // dispatch(addFlowEdge(connection));
    },
    [dispatch, edges]
  );

  const onInit = useCallback((instance: ReactFlowInstance) => {
    setReactFlowInstance(instance);
    console.log('React Flow instance initialized:', instance);
  }, []); // No dispatch needed here

  const onNodeClick: NodeMouseHandler = useCallback((event, node) => {
    setSelectedNode(node);
    console.log('Node clicked (useReactFlowManager):', node);
  }, []); // Keep local selection management

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []); // Keep local selection management

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
        data: { label: nodeLabel, description: '' },
      };

      console.log('Node dropped (dispatching): ', newNode);
      // Dispatch action to add the node
      dispatch(setFlowNodes(nodes.concat(newNode))); // Simple concat, assumes setFlowNodes replaces the array
      // OR: If you have a dedicated addNode action:
      // dispatch(addFlowNode(newNode));
      enqueueSnackbar(t('flowEditor.nodeAdded', { type: nodeLabel }), { variant: 'success' });
    },
    [reactFlowInstance, dispatch, nodes, t, enqueueSnackbar, reactFlowWrapperRef] // Add dispatch and nodes dependencies
  );

  // Function to update node data from properties panel
  const handleNodeDataUpdate = useCallback(
    // Payload type matches the action defined in flowSlice
    (update: { id: string; data: Partial<NodeData> }) => {
        console.log("useReactFlowManager: dispatching updateFlowNodeData", update);
        dispatch(updateFlowNodeData(update));

      // Update local selected node state if the updated node is the selected one
      setSelectedNode((currentSelected) => {
        if (currentSelected && currentSelected.id === update.id) {
            // Create a new object for the updated selected node state
            return { ...currentSelected, data: { ...currentSelected.data, ...update.data } };
        }
        return currentSelected;
      });
    },
    [dispatch]
  );

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
  };
}; 