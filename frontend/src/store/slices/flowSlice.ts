import { createSlice, PayloadAction, createAsyncThunk, ActionReducerMapBuilder, SerializedError } from '@reduxjs/toolkit';
import { Node, Edge, addEdge as reactFlowAddEdge } from 'reactflow';
import { NodeData } from '../../components/FlowEditor'; // Adjust path if needed
import { getFlow, updateFlow, ensureFlowAgentState } from '../../api/flowApi'; // API function to fetch flow data
import { RootState } from '../store';

interface FlowState {
  currentFlowId: string | null;
  flowName: string;
  nodes: Node<NodeData>[];
  edges: Edge[];
  agentState: any; // Agent state from backend
  isLoading: boolean;
  error: string | null;
  // Add other relevant state, e.g., selectedNodeId?
  isSaving: boolean;
  saveError: string | null;
  lastSaveTime: string | null;
}

const initialState: FlowState = {
  currentFlowId: null,
  flowName: 'Untitled Flow', // Default name
  nodes: [],
  edges: [],
  agentState: {},
  isLoading: false,
  error: null,
  isSaving: false,
  saveError: null,
  lastSaveTime: null,
};

// Define the payload type for fulfilled action explicitly
interface FetchFlowByIdPayload {
    id: string;
    name: string;
    nodes: Node<NodeData>[];
    edges: Edge[];
    agent_state?: any;
}

// Async thunk to ensure flow has complete agent_state
export const ensureFlowAgentStateThunk = createAsyncThunk<FetchFlowByIdPayload, string, { rejectValue: string }>(
    'flow/ensureAgentState',
    async (flowId: string, { rejectWithValue }) => {
        try {
            console.log(`Redux: Ensuring agent state for flow ${flowId}`);
            const flowData = await ensureFlowAgentState(flowId);
            if (flowData && flowData.id) {
                return {
                    id: flowData.id,
                    name: flowData.name || 'Untitled Flow',
                    nodes: flowData.flow_data?.nodes || [],
                    edges: flowData.flow_data?.edges || [],
                    agent_state: flowData.agent_state || {},
                };
            } else {
                console.error(`Redux: Invalid flow data received after ensuring agent state for ${flowId}`);
                return rejectWithValue('Invalid flow data received');
            }
        } catch (error: any) {
            console.error(`Redux: Error ensuring agent state for flow ${flowId}:`, error);
            return rejectWithValue(error.message || 'Failed to ensure agent state');
        }
    }
);

// Async thunk for fetching flow data
// Redux Toolkit's createAsyncThunk handles the async logic and dispatches pending/fulfilled/rejected actions
export const fetchFlowById = createAsyncThunk<FetchFlowByIdPayload, string, { rejectValue: string }>(
    'flow/fetchByIdStatus',
    async (flowId: string, { rejectWithValue }) => {
        try {
            console.log(`Redux: Fetching flow ${flowId}`);
            const flowData = await getFlow(flowId);
            if (flowData && flowData.id && flowData.flow_data) {
                return {
                    id: flowData.id,
                    name: flowData.name || 'Untitled Flow',
                    nodes: flowData.flow_data.nodes || [],
                    edges: flowData.flow_data.edges || [],
                    agent_state: flowData.agent_state || {},
                };
            } else {
                console.error(`Redux: Invalid flow data received for ${flowId}. Data:`, flowData);
                return rejectWithValue('Invalid flow data received');
            }
        } catch (error: any) {
            console.error(`Redux: Error loading flow ${flowId}:`, error);
            return rejectWithValue(error.message || 'Failed to fetch flow');
        }
    }
);

// --- Async Thunk for saving flow data ---
interface SaveFlowPayload {
    // Define payload if needed, e.g., returning the last save time?
    lastSaveTime: string;
}
interface SaveFlowArgs {
    flowId: string;
    name: string;
    nodes: Node<NodeData>[];
    edges: Edge[];
}

export const saveFlow = createAsyncThunk<SaveFlowPayload, void, { state: RootState, rejectValue: string }>( // Get state type from RootState
    'flow/saveStatus',
    async (_, { getState, rejectWithValue }) => {
        const state = getState().flow; // Get current flow state
        const { currentFlowId, flowName, nodes, edges } = state;

        if (!currentFlowId) {
            return rejectWithValue('No active flow to save');
        }

        console.log(`Redux: Attempting to save flow ${currentFlowId}...`);
        try {
            // Prepare data for the API, ensuring 'selected' state is not persisted
            const nodesToSave = nodes.map(({ selected, ...nodeRest }) => nodeRest);
            // Edges generally don't have a selected state that needs stripping, 
            // but if they did, you'd map them similarly.
            // const edgesToSave = edges.map(({ selected, ...edgeRest }) => edgeRest);

            const updateData = {
                name: flowName,
                flow_data: { nodes: nodesToSave, edges /* Use original edges or edgesToSave if needed */ }
            };
            await updateFlow(currentFlowId, updateData);
            const saveTime = new Date().toISOString();
            console.log(`Redux: Flow ${currentFlowId} saved successfully at ${saveTime}`);
            return { lastSaveTime: saveTime };
        } catch (error: any) {
            console.error(`Redux: Error saving flow ${currentFlowId}:`, error);
            return rejectWithValue(error.message || 'Failed to save flow');
        }
    },
    {
        // Prevent saving if already saving or loading
        condition: (_, { getState }) => {
            const { isSaving, isLoading } = getState().flow;
            if (isSaving || isLoading) {
                console.log('Redux: Save condition failed (already saving or loading).');
                return false;
            }
            return true;
        }
    }
);

const flowSlice = createSlice({
  name: 'flow',
  initialState,
  reducers: {
    // Action to set the current flow ID (e.g., when navigating or selecting)
    setCurrentFlowId: (state: FlowState, action: PayloadAction<string | null>) => {
      // If ID changes, reset related state? Or let fetch handle it?
      if (state.currentFlowId !== action.payload) {
          state.currentFlowId = action.payload;
          // Reset state when ID changes before fetching new data
          state.nodes = [];
          state.edges = [];
          state.flowName = 'Untitled Flow';
          state.agentState = {};
          state.error = null;
          state.isLoading = false; // Will be set true by fetch thunk
          // Reset save status when flow changes
          state.isSaving = false;
          state.saveError = null;
          state.lastSaveTime = null;
      }
    },
    // Direct reducers to update nodes/edges (e.g., from React Flow changes)
    // These might be replaced by actions dispatched from useReactFlowManager or similar
    setNodes: (state: FlowState, action: PayloadAction<Node<NodeData>[]>) => {
      state.nodes = action.payload;
      // TODO: Consider triggering auto-save here via middleware or another thunk?
    },
    setEdges: (state: FlowState, action: PayloadAction<Edge[]>) => {
      state.edges = action.payload;
      // TODO: Consider triggering auto-save here?
    },
    addNode: (state: FlowState, action: PayloadAction<Node<NodeData>>) => {
        // Simple concat, assumes payload is a single node object
        state.nodes.push(action.payload);
        // TODO: Trigger auto-save?
    },
    addEdge: (state: FlowState, action: PayloadAction<Edge>) => {
        // Use React Flow's helper within the reducer for consistency
        // Note: reactFlowAddEdge might return the same array if edge is duplicate/invalid
        state.edges = reactFlowAddEdge(action.payload, state.edges);
        // TODO: Trigger auto-save?
    },
    updateNodeData: (state: FlowState, action: PayloadAction<{ id: string; data: Partial<NodeData> }>) => {
        const nodeIndex = state.nodes.findIndex((n: Node<NodeData>) => n.id === action.payload.id);
        if (nodeIndex !== -1) {
            state.nodes[nodeIndex] = {
                ...state.nodes[nodeIndex],
                data: { ...state.nodes[nodeIndex].data, ...action.payload.data }
            };
        }
        // TODO: Trigger auto-save?
    },
    setFlowName: (state: FlowState, action: PayloadAction<string>) => {
        state.flowName = action.payload;
        // TODO: Trigger auto-save for name change?
    },
    updateAgentState: (state: FlowState, action: PayloadAction<any>) => {
        state.agentState = { ...state.agentState, ...action.payload };
    },
    // Reducer to handle single node selection
    selectNode: (state: FlowState, action: PayloadAction<string>) => {
      const selectedNodeId = action.payload;
      console.log('🔍 Redux selectNode action 被调用，节点ID:', selectedNodeId);
      console.log('🔍 当前节点数量:', state.nodes.length);
      
      const beforeUpdate = state.nodes.find(n => n.id === selectedNodeId);
      console.log('🔍 更新前节点状态:', beforeUpdate ? { id: beforeUpdate.id, selected: beforeUpdate.selected } : '节点未找到');
      
      state.nodes = state.nodes.map(node => ({
        ...node,
        selected: node.id === selectedNodeId,
      }));
      
      const afterUpdate = state.nodes.find(n => n.id === selectedNodeId);
      console.log('🔍 更新后节点状态:', afterUpdate ? { id: afterUpdate.id, selected: afterUpdate.selected } : '节点未找到');
      console.log('🔍 总共选中的节点数量:', state.nodes.filter(n => n.selected).length);
    },
    // Reducer to deselect all nodes
    deselectAllNodes: (state: FlowState) => {
      state.nodes = state.nodes.map(node => ({
        ...node,
        selected: false,
      }));
    },
    // 添加删除节点的 reducer
    deleteNode: (state: FlowState, action: PayloadAction<string>) => {
      const nodeId = action.payload;
      // 删除节点
      state.nodes = state.nodes.filter(node => node.id !== nodeId);
      // 删除与该节点相关的所有边
      state.edges = state.edges.filter(edge => 
        edge.source !== nodeId && edge.target !== nodeId
      );
    },
    // 添加删除边的 reducer
    deleteEdge: (state: FlowState, action: PayloadAction<string>) => {
      const edgeId = action.payload;
      state.edges = state.edges.filter(edge => edge.id !== edgeId);
    },
    // Add other reducers as needed (e.g., addNode, addEdge, deleteNode)
  },
  extraReducers: (builder: ActionReducerMapBuilder<FlowState>) => {
    builder
      .addCase(fetchFlowById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
        console.log('Redux: Fetching flow pending...');
      })
      .addCase(fetchFlowById.fulfilled, (state: FlowState, action: PayloadAction<FetchFlowByIdPayload>) => {
        state.isLoading = false;
        state.currentFlowId = action.payload.id; // Ensure currentFlowId matches the payload
        state.flowName = action.payload.name;
        state.nodes = action.payload.nodes;
        state.edges = action.payload.edges;
        state.agentState = action.payload.agent_state || {};
        state.error = null;
        // Added detailed log
        console.log(
          `Redux: Fetching flow ${action.payload.id} fulfilled. Nodes count: ${action.payload.nodes.length}, AgentState tasks:`, 
          action.payload.agent_state?.sas_step1_generated_tasks || 'No tasks in agentState'
        );
        state.lastSaveTime = new Date().toISOString(); // Or from flowData if backend provides it
        state.isSaving = false;
        state.saveError = null;
      })
      .addCase(fetchFlowById.rejected, (state: FlowState, action: PayloadAction<string | undefined, string, { arg: string; requestId: string; rejectedWithValue: boolean; aborted: boolean; condition: boolean; }, SerializedError>) => {
        state.isLoading = false;
        state.error = action.payload ?? action.error.message ?? 'Unknown error';
        state.nodes = [];
        state.edges = [];
        state.flowName = 'Untitled Flow';
        state.agentState = {};
        console.error('Redux: Fetching flow rejected', action.payload, action.error);
      });
    // --- Save Flow Cases ---
    builder
        .addCase(saveFlow.pending, (state) => {
            console.log('Redux: Saving flow pending...');
            state.isSaving = true;
            state.saveError = null;
        })
        .addCase(saveFlow.fulfilled, (state, action: PayloadAction<SaveFlowPayload>) => {
            console.log('Redux: Saving flow fulfilled at', action.payload.lastSaveTime);
            state.isSaving = false;
            state.lastSaveTime = action.payload.lastSaveTime;
            state.saveError = null;
        })
        .addCase(saveFlow.rejected, (state, action) => {
            console.error('Redux: Saving flow rejected', action.payload, action.error);
            state.isSaving = false;
            // Use action.payload (string) or action.error.message
            state.saveError = (action.payload as string) ?? action.error.message ?? 'Unknown save error';
            // Keep last successful save time?
        });
    // --- Ensure Agent State Cases ---
    builder
        .addCase(ensureFlowAgentStateThunk.fulfilled, (state: FlowState, action: PayloadAction<FetchFlowByIdPayload>) => {
            // Update agent state when ensure operation completes
            state.agentState = action.payload.agent_state || {};
            console.log('Redux: Agent state ensured and updated');
        })
        .addCase(ensureFlowAgentStateThunk.rejected, (state: FlowState, action) => {
            console.error('Redux: Failed to ensure agent state', action.payload, action.error);
            // Don't update the state on failure, keep existing agent_state
        });
  },
});

export const {
    setCurrentFlowId,
    setNodes,
    setEdges,
    addNode,
    addEdge,
    updateNodeData,
    setFlowName,
    updateAgentState,
    selectNode,      // Export new action
    deselectAllNodes, // Export new action
    deleteNode,       // Export new action
    deleteEdge        // Export new action
} = flowSlice.actions;

// Selectors
export const selectCurrentFlowId = (state: RootState) => state.flow.currentFlowId;
export const selectFlowName = (state: RootState) => state.flow.flowName;
export const selectNodes = (state: RootState) => state.flow.nodes;
export const selectEdges = (state: RootState) => state.flow.edges;
export const selectAgentState = (state: RootState) => state.flow.agentState;
export const selectIsFlowLoading = (state: RootState) => state.flow.isLoading;
export const selectFlowError = (state: RootState) => state.flow.error;
export const selectIsSaving = (state: RootState) => state.flow.isSaving;
export const selectSaveError = (state: RootState) => state.flow.saveError;
export const selectLastSaveTime = (state: RootState) => state.flow.lastSaveTime;

export default flowSlice.reducer; 