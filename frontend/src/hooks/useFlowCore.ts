import { useState, useEffect, useCallback } from 'react';
import { Node, Edge, ReactFlowInstance } from 'reactflow';
import { useSnackbar } from 'notistack';
import { useTranslation } from 'react-i18next';
import { getFlow, getLastChatIdForFlow, updateFlow } from '../api/flowApi';
import { clearFlowCache } from '../components/FlowLoader'; // Adjust path if needed
import { NodeData } from '../components/FlowEditor'; // Adjust path if needed
import { useFlowPersistence } from './useFlowPersistence'; // Use the existing persistence hook
import { Dispatch, SetStateAction } from 'react'; // Import Dispatch and SetStateAction

interface UseFlowCoreProps {
  flowId: string | undefined;
  flowName: string;
  nodes: Node<NodeData>[];
  edges: Edge[];
  setNodes: Dispatch<SetStateAction<Node<NodeData>[]>>;
  setEdges: Dispatch<SetStateAction<Edge<any>[]>>;
  reactFlowInstance: ReactFlowInstance | null;
  onLoadComplete?: (loadedFlowName: string) => void;
  setFlowName: Dispatch<SetStateAction<string>>;
  setSelectedNode: Dispatch<SetStateAction<Node<NodeData> | null>>;
  setNodeInfoOpen: Dispatch<SetStateAction<boolean>>;
  onNodeSelectFromEvent?: (nodeId: string, position?: { x: number; y: number }) => void;
}

interface UseFlowCoreOutput {
  flowName: string;
  isLoadingFlow: boolean;
  isLoadingChatId: boolean;
}

export const useFlowCore = ({
  flowId,
  flowName,
  nodes,
  edges,
  setNodes,
  setEdges,
  reactFlowInstance,
  onLoadComplete,
  setFlowName,
  setSelectedNode,
  setNodeInfoOpen,
  onNodeSelectFromEvent,
}: UseFlowCoreProps): UseFlowCoreOutput => {
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const [isLoadingFlow, setIsLoadingFlow] = useState<boolean>(false);
  const [isLoadingChatId, setIsLoadingChatId] = useState<boolean>(false);

  // --- Flow Loading Logic --- //
  const loadFlow = useCallback(async (flowIdToLoad: string) => {
    if (!flowIdToLoad) return;
    setIsLoadingFlow(true);
    console.log(`useFlowCore: Loading flow ${flowIdToLoad}...`);
    try {
      const flowData = await getFlow(flowIdToLoad);
      if (flowData && flowData.flow_data) {
        setNodes(flowData.flow_data.nodes || []);
        setEdges(flowData.flow_data.edges || []);
        const loadedName = flowData.name || t('flowEditor.untitledFlow');
        setFlowName(loadedName);
        console.log(`useFlowCore: Flow ${flowIdToLoad} loaded successfully.`);
        enqueueSnackbar(t('flowEditor.loadSuccess'), { variant: 'success' });
        if (onLoadComplete) {
          onLoadComplete(loadedName);
        }
        // Fit view after loading
        setTimeout(() => {
          if (reactFlowInstance) {
            reactFlowInstance.fitView({ duration: 500 });
          }
        }, 100); // Small delay to ensure nodes/edges are rendered
      } else {
        setNodes([]); // Clear if data is invalid
        setEdges([]);
        setFlowName(t('flowEditor.untitledFlow'));
        console.error(`useFlowCore: Invalid flow data received for ${flowIdToLoad}.`);
        enqueueSnackbar(t('flowEditor.invalidFlowData'), { variant: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.unknown');
      console.error(`useFlowCore: Error loading flow ${flowIdToLoad}:`, errorMessage);
      enqueueSnackbar(`${t('flowEditor.loadError')} ${errorMessage}`, { variant: 'error' });
      // Optionally clear state on load error?
      // setNodes([]);
      // setEdges([]);
      // setFlowName(t(\'flowEditor.untitledFlow\'));
    } finally {
      setIsLoadingFlow(false);
    }
  }, [enqueueSnackbar, setEdges, setFlowName, setNodes, t, onLoadComplete, reactFlowInstance]);

  // Effect to load flow when flowId changes
  useEffect(() => {
    if (flowId) {
      loadFlow(flowId);
    }
    // Clear state if flowId becomes undefined (e.g., navigating away)
    else {
      setNodes([]);
      setEdges([]);
      setFlowName(t('flowEditor.untitledFlow'));
    }
  }, [flowId, loadFlow, setNodes, setEdges, setFlowName, t]);

  // --- Event Listener Logic --- //
  useEffect(() => {
    const handleFlowRefresh = (event: CustomEvent) => {
      console.log('useFlowCore: Received flow-refresh event', event.detail);
      if (event.detail?.flowId === flowId && flowId) {
        clearFlowCache(flowId);
        setTimeout(() => {
          console.log('useFlowCore: Refreshing flow data...');
          loadFlow(flowId);
          // Check if we need to select a node
          if (event.detail?.metadata?.node_id && onNodeSelectFromEvent) {
            const nodeId = event.detail.metadata.node_id;
            const position = event.detail?.metadata?.position;
            console.log(`useFlowCore: Requesting node selection for ${nodeId}`);
            // Give time for nodes to potentially update before selecting
            setTimeout(() => {
              onNodeSelectFromEvent(nodeId, position);
            }, 600); // Increased delay slightly
          }
        }, 300);
      }
    };

    const handleFlowRenamed = (event: CustomEvent) => {
      if (event.detail && event.detail.flowId === flowId && event.detail.newName) {
        setFlowName(event.detail.newName);
        console.log('useFlowCore: Flow name updated via event:', event.detail.newName);
        enqueueSnackbar(t('flowEditor.nameUpdated'), { variant: 'success', autoHideDuration: 3000 });
      }
    };

    window.addEventListener('flow-refresh', handleFlowRefresh as EventListener);
    window.addEventListener('flow-renamed', handleFlowRenamed as EventListener);

    return () => {
      window.removeEventListener('flow-refresh', handleFlowRefresh as EventListener);
      window.removeEventListener('flow-renamed', handleFlowRenamed as EventListener);
    };
  }, [flowId, loadFlow, enqueueSnackbar, t, onNodeSelectFromEvent, setFlowName]);

  // --- Initial Chat ID Logic --- //
  useEffect(() => {
    const fetchInitialChatId = async () => {
      if (flowId) {
        console.log(`useFlowCore: flowId is ${flowId}, fetching last chat ID.`);
        setIsLoadingChatId(true);
        try {
          // We fetch it, but don't directly use it here.
          // ChatInterface fetches its own initial chat ID.
          await getLastChatIdForFlow(flowId);
          // console.log("Last chat ID response (in useFlowCore):", response);
        } catch (error) {
          console.error("useFlowCore: Failed to fetch last chat ID for flow:", flowId, error);
          // Don't necessarily show snackbar, ChatInterface handles its errors
        } finally {
          setIsLoadingChatId(false);
        }
      } else {
        console.log("useFlowCore: flowId is null/undefined, skipping chat ID fetch.");
        setIsLoadingChatId(false); // Ensure loading is false
      }
    };
    fetchInitialChatId();
  }, [flowId]);

  // --- Flow Persistence (Auto-Save) --- //
  useFlowPersistence({
    flowId,
    flowName,
    nodes,
    edges,
    reactFlowInstance,
    setNodes,
    setEdges,
    setFlowName,
    setSelectedNode,
    setNodeInfoOpen,
  });

  // --- Return Values --- //
  return {
    flowName,
    isLoadingFlow,
    isLoadingChatId,
  };
}; 