import { useState, useEffect, useCallback } from 'react';
import { Node, Edge, ReactFlowInstance } from 'reactflow';
import { useSnackbar } from 'notistack';
import { useTranslation } from 'react-i18next';
import { getFlow, updateFlow, getLastChatIdForFlow } from '../api/flowApi';
import { clearFlowCache } from '../components/FlowLoader';
import { debounce } from 'lodash';
import { NodeData } from '../components/FlowEditor/types';

interface UseFlowPersistenceProps {
  flowId?: string;
  nodes: Node[];
  edges: Edge[];
  flowName: string; // Need flowName for saving
  setNodes: (nodes: Node[] | ((prevNodes: Node[]) => Node[])) => void;
  setEdges: (edges: Edge[] | ((prevEdges: Edge[]) => Edge[])) => void;
  setFlowName: (name: string) => void;
  setSelectedNode: (node: Node<NodeData> | null) => void; // For flow-refresh event
  setNodeInfoOpen: (open: boolean) => void; // For flow-refresh event
  reactFlowInstance: ReactFlowInstance | null;
}

export const useFlowPersistence = ({
  flowId,
  nodes,
  edges,
  flowName,
  setNodes,
  setEdges,
  setFlowName,
  setSelectedNode,
  setNodeInfoOpen,
  reactFlowInstance
}: UseFlowPersistenceProps) => {
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();
  const [isLoadingFlow, setIsLoadingFlow] = useState<boolean>(true);
  const [initialLoadComplete, setInitialLoadComplete] = useState<boolean>(false);

  // --- Load Flow Logic --- //
  const loadFlow = useCallback(async (flowIdToLoad: string) => {
    setIsLoadingFlow(true);
    console.log(`Persistence: Loading flow ${flowIdToLoad}`);
    try {
      const flowData = await getFlow(flowIdToLoad);
      if (flowData && flowData.flow_data) {
        setNodes(flowData.flow_data.nodes || []);
        setEdges(flowData.flow_data.edges || []);
        setFlowName(flowData.name || t('flowEditor.untitledFlow'));
        enqueueSnackbar(t('flowEditor.loadSuccess'), { variant: 'success' });
        console.log(`Persistence: Flow ${flowIdToLoad} loaded successfully.`);
      } else {
        enqueueSnackbar(t('flowEditor.invalidFlowData'), { variant: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.unknown');
      enqueueSnackbar(`${t('flowEditor.loadError')} ${errorMessage}`, { variant: 'error' });
      console.error(`Persistence: Error loading flow ${flowIdToLoad}:`, errorMessage);
    } finally {
      setIsLoadingFlow(false);
      setInitialLoadComplete(true); // Mark initial load as complete
    }
  }, [enqueueSnackbar, setEdges, setFlowName, setNodes, t]);

  // Effect to load flow when flowId changes
  useEffect(() => {
    if (flowId) {
      setInitialLoadComplete(false); // Reset load complete flag
      loadFlow(flowId);
    } else {
      // Handle case where flowId becomes undefined (e.g., navigating away)
      setNodes([]);
      setEdges([]);
      setFlowName(t('flowEditor.untitledFlow'));
      setIsLoadingFlow(false);
      setInitialLoadComplete(false);
    }
    // Explicitly not including loadFlow here to avoid loop if loadFlow itself changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowId, setNodes, setEdges, setFlowName, t]);

  // --- Auto Save Logic --- //
  const debouncedSave = useCallback(
    debounce(async () => {
      if (!flowId || !reactFlowInstance || !initialLoadComplete) { // Don't save before initial load
        console.log('AutoSave: Skipping save (no flowId/instance or initial load pending).');
        return;
      }
      const token = localStorage.getItem('access_token');
      if (!token) {
        console.log('AutoSave: Skipping save, user logged out.');
        return;
      }

      console.log(`AutoSave: Triggered for flow ${flowId}`);
      try {
        const flowData = reactFlowInstance.toObject();
        // Filter out any temporary/internal properties from nodes/edges if necessary before saving
        await updateFlow(flowId, { flow_data: flowData, name: flowName });
        console.log(`AutoSave: Flow ${flowId} saved successfully.`);
        clearFlowCache(flowId);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        console.error(`AutoSave: Error saving flow ${flowId}:`, errorMessage);
        enqueueSnackbar(`${t('flowEditor.autoSaveError')} ${errorMessage}`, { variant: 'error' });
      }
    }, 300),
    [flowId, reactFlowInstance, flowName, enqueueSnackbar, t, initialLoadComplete] // Include initialLoadComplete
  );

  // Effect to trigger save on node/edge changes after initial load
  useEffect(() => {
    if (initialLoadComplete) { // Only save after the initial load is done
      console.log("AutoSave: Nodes or edges changed, triggering debounced save...");
      debouncedSave();
    }
    return () => {
      debouncedSave.cancel();
    };
  }, [nodes, edges, initialLoadComplete, debouncedSave]);

  // --- Event Handling Logic --- //
  // Handle flow-refresh events
  useEffect(() => {
    const handleFlowRefresh = (event: CustomEvent) => {
      console.log('Persistence: Received flow-refresh event', event.detail);
      if (flowId && event.detail?.metadata?.flowId === flowId) { // Check if event is for the current flow
        clearFlowCache(flowId);
        setTimeout(() => {
          console.log('Persistence: Refreshing flow data...');
          loadFlow(flowId);
          if (event.detail?.metadata?.node_id && reactFlowInstance) {
            const nodeId = event.detail.metadata.node_id;
            setTimeout(() => {
              // Use reactFlowInstance.getNode as nodes state might not be updated yet
              const node = reactFlowInstance.getNode(nodeId);
              if (node) {
                setSelectedNode(node as Node<NodeData>);
                setNodeInfoOpen(true);
                setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === nodeId })));
                if (event.detail?.metadata?.position) {
                  reactFlowInstance.setCenter(event.detail.metadata.position.x, event.detail.metadata.position.y, { duration: 800 });
                }
              }
            }, 500);
          }
        }, 300);
      }
    };
    window.addEventListener('flow-refresh', handleFlowRefresh as EventListener);
    return () => window.removeEventListener('flow-refresh', handleFlowRefresh as EventListener);
  }, [flowId, loadFlow, reactFlowInstance, setNodes, setSelectedNode, setNodeInfoOpen]);

  // Handle flow-renamed events
  useEffect(() => {
    const handleFlowRenamed = (event: CustomEvent) => {
      if (event.detail && event.detail.flowId === flowId && event.detail.newName) {
        setFlowName(event.detail.newName);
        console.log('Persistence: Flow name updated:', event.detail.newName);
        enqueueSnackbar(t('flowEditor.nameUpdated', '流程图名称已更新'), { variant: 'success', autoHideDuration: 3000 });
      }
    };
    window.addEventListener('flow-renamed', handleFlowRenamed as EventListener);
    return () => window.removeEventListener('flow-renamed', handleFlowRenamed as EventListener);
  }, [flowId, setFlowName, enqueueSnackbar, t]);

  // Return state/functions needed by the component
  return { isLoadingFlow };
}; 