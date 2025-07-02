import { useCallback, useRef, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { debounce } from 'lodash';
import _isEqual from 'lodash/isEqual';
import { AppDispatch } from '../../store/store';
import { saveFlow } from '../../store/slices/flowSlice';
import { Node, Edge } from 'reactflow';

const SAVE_DEBOUNCE_MS = 100;

interface SaveHandlerProps {
  nodes: Node[];
  edges: Edge[];
  flowName: string;
  currentFlowId: string | null;
  isLoading: boolean;
  isSaving: boolean;
  isDraggingNode: boolean;
}

export const useSaveHandler = ({
  nodes,
  edges,
  flowName,
  currentFlowId,
  isLoading,
  isSaving,
  isDraggingNode
}: SaveHandlerProps) => {
  const dispatch = useDispatch<AppDispatch>();

  // Ref to track if it's the initial load to prevent immediate save
  const isInitialLoad = useRef(true);
  
  // Ref to store the state of the last successful save or fetch
  const lastSuccessfulSaveStateRef = useRef({ nodes, edges, flowName });

  // Effect to update lastSuccessfulSaveStateRef when data is successfully saved or fetched
  useEffect(() => {
    // This effect runs when lastSaveTime changes (indicating a save/fetch success)
    // or when nodes/edges/flowName themselves change (e.g. initial fetch).
    // It effectively snapshots the state that is considered "committed".
    console.log("FlowEditor: lastSaveTime, nodes, edges, or flowName changed. Updating lastSuccessfulSaveStateRef.");
    lastSuccessfulSaveStateRef.current = { nodes, edges, flowName };
  }, [nodes, edges, flowName]); // lastSaveTime is crucial here but handled externally

  // Mark initial load as complete when flow is loaded
  useEffect(() => {
    if (currentFlowId && !isLoading) {
      isInitialLoad.current = false;
    }
  }, [currentFlowId, isLoading]);

  // --- Debounced Save Function ---
  const debouncedSave = useCallback(
    debounce(() => {
      if (isInitialLoad.current) {
        console.log("FlowEditor: Debounced save skipped (initial load).");
        return;
      }

      // Compare current data with the snapshot of the last successful save/fetch
      const dataHasChanged =
        !_isEqual(nodes, lastSuccessfulSaveStateRef.current.nodes) ||
        !_isEqual(edges, lastSuccessfulSaveStateRef.current.edges) ||
        flowName !== lastSuccessfulSaveStateRef.current.flowName;

      if (dataHasChanged) {
        console.log("FlowEditor: Debounced save triggered due to actual data changes.");
        dispatch(saveFlow()); // saveFlow thunk already uses latest state from Redux
      } else {
        console.log("FlowEditor: Debounced save skipped (no actual data change since last successful save/fetch).");
      }
    }, SAVE_DEBOUNCE_MS),
    [dispatch, nodes, edges, flowName] // nodes, edges, flowName are needed for comparison.
  );

  // --- Effect to trigger debounced save on changes ---
  useEffect(() => {
    if (!isInitialLoad.current && currentFlowId && !isLoading && !isSaving && !isDraggingNode) {
      console.log("FlowEditor: Conditions met for potential save. Calling debouncedSave.");
      debouncedSave();
    }
    // Cleanup function to cancel debounce if component unmounts or dependencies change
    return () => {
      debouncedSave.cancel();
    };
  }, [currentFlowId, debouncedSave, isLoading, isSaving, isDraggingNode]);

  return {
    debouncedSave,
    isInitialLoad: isInitialLoad.current
  };
}; 