import { useCallback } from 'react';
import { Node, Edge, ReactFlowInstance } from 'reactflow';
import { useSnackbar } from 'notistack';
import { useTranslation } from 'react-i18next';
import { NodeData } from '../components/FlowEditor'; // Import NodeData if used internally or for types

// Define the type for the layout completion callback
type LayoutCompleteCallback = (nodes: Node<NodeData>[], edges: Edge[]) => void;

// Hook props no longer need setters, as they are handled by the callback
interface UseFlowLayoutProps {
  reactFlowInstance: ReactFlowInstance | null;
}

// The hook now returns performLayout
interface UseFlowLayoutOutput {
    performLayout: (nodes: Node<NodeData>[], edges: Edge[], onComplete: LayoutCompleteCallback) => void;
    optimizeEdgeCrossings: (edges: Edge[], onComplete: (newEdges: Edge[]) => void) => void; // Modify optimize too
}

export const useFlowLayout = ({
  reactFlowInstance
}: UseFlowLayoutProps): UseFlowLayoutOutput => {
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  // Rename autoLayout to performLayout and accept nodes/edges/callback as arguments
  const performLayout = useCallback(
    (currentNodes: Node<NodeData>[], currentEdges: Edge[], onComplete: LayoutCompleteCallback) => {
      enqueueSnackbar(t('flowEditor.autoLayoutStart') || '正在应用智能布局...', {
        variant: 'info',
        autoHideDuration: 1500
      });

      if (currentNodes.length === 0 || !reactFlowInstance) {
          enqueueSnackbar(t('flowEditor.autoLayoutEmpty') || '没有节点可供布局', { variant: 'warning' });
          return;
      }

      // --- Start of existing autoLayout logic, using currentNodes/currentEdges ---
      const layers: { [key: number]: Node<NodeData>[] } = {};
      let visited = new Set<string>();
      let nodeLevels = new Map<string, number>();

      // Helper functions using currentEdges
      const getNodeIncomers = (nodeId: string): string[] => currentEdges.filter(edge => edge.target === nodeId).map(edge => edge.source);
      const getNodeOutgoers = (nodeId: string): string[] => currentEdges.filter(edge => edge.source === nodeId).map(edge => edge.target);
      const startNodes = currentNodes.filter(node => !currentEdges.some(edge => edge.target === node.id)).map(node => node.id);
      const getNodeConnectionType = (sourceId: string, targetId: string): 'true' | 'false' | 'normal' => {
          const edge = currentEdges.find(e => e.source === sourceId && e.target === targetId);
          // ... rest of getNodeConnectionType logic ...
          return 'normal'; // Placeholder
      };

      // ... rest of the BFS/layering logic using currentNodes/currentEdges ...
      const queue = startNodes.map(id => ({ id, level: 0 }));
      while (queue.length > 0) {
          const { id, level } = queue.shift()!;
          if (visited.has(id)) {
              if ((nodeLevels.get(id) || 0) < level) nodeLevels.set(id, level);
              continue;
          }
          visited.add(id);
          nodeLevels.set(id, level);
          if (!layers[level]) layers[level] = [];
          const node = currentNodes.find(n => n.id === id);
          if (node) layers[level].push(node);
  
          // ... BFS queue population logic ...
      }

      // ... handle unvisited nodes logic ...

      const VERTICAL_SPACING = 200, HORIZONTAL_SPACING = 250, MIN_VERTICAL_GAP = 80;
      const layerKeys = Object.keys(layers).map(Number).sort((a, b) => a - b);
      // Create a copy to modify positions
      const newNodes: Node<NodeData>[] = currentNodes.map(n => ({ ...n }));
      const layerVerticalPositions: { [key: number]: number } = {};

      // ... Calculate vertical positions logic ...

      layerKeys.forEach(layerIndex => {
          const layerNodes = layers[layerIndex];
          const layerWidth = layerNodes.reduce((sum, node) => sum + (node.width || 150), 0) + (layerNodes.length - 1) * HORIZONTAL_SPACING;
          let currentX = -layerWidth / 2;
          // ... updated sorting/grouping logic if needed ...
  
          layerNodes.forEach((node, nodeIndex) => {
              const nodeWidth = node.width || 150;
              const xPosition = currentX + nodeWidth / 2;
              const nodeToUpdate = newNodes.find(n => n.id === node.id);
              if (nodeToUpdate) {
                   // Ensure position is defined
                  nodeToUpdate.position = { 
                      x: xPosition, 
                      y: layerVerticalPositions[layerIndex] ?? (layerIndex * VERTICAL_SPACING) // Fallback Y
                  };
              }
              currentX += nodeWidth + HORIZONTAL_SPACING;
          });
      });
      // --- End of existing autoLayout logic ---

      // Call the callback with the calculated nodes (edges are usually unchanged by layout)
      onComplete(newNodes, currentEdges);

      // Fit view and show success message after state update (via callback)
      setTimeout(() => {
        if (reactFlowInstance) {
             reactFlowInstance.fitView({ padding: 0.2 });
        }
        enqueueSnackbar(t('flowEditor.autoLayoutComplete') || '智能布局已完成', { variant: 'success', autoHideDuration: 2000 });
      }, 100); // Timeout allows React/Redux state to update first
    },
    [reactFlowInstance, enqueueSnackbar, t] // Remove state setters from dependencies
  );

  // Modify optimizeEdgeCrossings similarly
  const optimizeEdgeCrossings = useCallback(
    (currentEdges: Edge[], onComplete: (newEdges: Edge[]) => void) => {
      const edgesBySource: { [key: string]: Edge[] } = {};
      currentEdges.forEach(edge => {
        if (!edgesBySource[edge.source]) edgesBySource[edge.source] = [];
        edgesBySource[edge.source].push(edge);
      });

      const newEdges = currentEdges.map(edge => {
        // ... existing optimization logic ...
        return edge; // Placeholder
      });

      onComplete(newEdges);
      enqueueSnackbar('优化连线完成', { variant: 'info', autoHideDuration: 1000 });
    },
    [enqueueSnackbar]
  );

  // Return the modified functions
  return { performLayout, optimizeEdgeCrossings };
};