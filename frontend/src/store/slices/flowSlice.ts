import { createSlice, PayloadAction, createAsyncThunk, ActionReducerMapBuilder, SerializedError, createReducer } from '@reduxjs/toolkit';
import { Node, Edge, addEdge as reactFlowAddEdge, NodeChange, EdgeChange, applyNodeChanges, applyEdgeChanges } from 'reactflow';
import { NodeData } from '../../components/FlowEditor'; // Adjust path if needed
import { getFlow, updateFlow } from '../../api/flowApi'; // API function to fetch flow data
import { RootState } from '../store';
import undoable, { StateWithHistory, ActionCreators as UndoActionCreators } from 'redux-undo'; // Import redux-undo

// Define the core state managed by undo/redo
interface FlowCoreState {
    nodes: Node<NodeData>[];
    edges: Edge[];
}

// Define the overall flow state including history
interface FlowState {
  currentFlowId: string | null;
  flowName: string;
  history: StateWithHistory<FlowCoreState>; // Use redux-undo state shape
  isLoading: boolean;
  error: string | null;
  isSaving: boolean;
  saveError: string | null;
  lastSaveTime: string | null; // Keep as ISO string for serialization
}

// Initial state for the core undoable part
const initialCoreState: FlowCoreState = {
    nodes: [],
    edges: [],
};

// Initial state for the entire slice
const initialState: FlowState = {
  currentFlowId: null,
  flowName: 'Untitled Flow',
  history: { // Initialize history structure
      past: [],
      present: initialCoreState,
      future: [],
      _latestUnfiltered: initialCoreState, // Required by redux-undo
      group: null, // Required by redux-undo
      index: 0 // Required by redux-undo
  },
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
}

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
        // Use history.present for nodes/edges
        const state = getState().flow;
        const { currentFlowId, flowName, history } = state;
        const { nodes, edges } = history.present; // Get current nodes/edges from history

        if (!currentFlowId) {
            return rejectWithValue('No active flow to save');
        }

        console.log(`Redux: Attempting to save flow ${currentFlowId}...`);
        try {
            const updateData = {
                name: flowName,
                flow_data: { nodes, edges } // Use nodes/edges from history.present
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

// --- Actions for Core Reducer ---
// We still define action creators using createSlice, but the logic moves to flowCoreReducer

// Placeholder actions - their logic will be in flowCoreReducer
const setNodes = createSlice({ name: 'flowCore', initialState: initialCoreState, reducers: { setNodes: (state, action: PayloadAction<Node<NodeData>[]>) => {} } }).actions.setNodes;
const setEdges = createSlice({ name: 'flowCore', initialState: initialCoreState, reducers: { setEdges: (state, action: PayloadAction<Edge[]>) => {} } }).actions.setEdges;
const updateNodeData = createSlice({ name: 'flowCore', initialState: initialCoreState, reducers: { updateNodeData: (state, action: PayloadAction<{ id: string; data: Partial<NodeData> }>) => {} } }).actions.updateNodeData;
const addNode = createSlice({ name: 'flowCore', initialState: initialCoreState, reducers: { addNode: (state, action: PayloadAction<Node<NodeData>>) => {} } }).actions.addNode;
const addEdgeAction = createSlice({ name: 'flowCore', initialState: initialCoreState, reducers: { addEdge: (state, action: PayloadAction<Edge>) => {} } }).actions.addEdge; // Renamed to avoid conflict with reactFlowAddEdge import
const removeElements = createSlice({ name: 'flowCore', initialState: initialCoreState, reducers: { removeElements: (state, action: PayloadAction<{ nodeIds: string[]; edgeIds: string[] }>) => {} } }).actions.removeElements;


// --- Core Reducer for Nodes and Edges (Managed by redux-undo) ---
const flowCoreReducer = createReducer(initialCoreState, (builder) => {
  builder
    .addCase(setNodes, (state, action) => {
      state.nodes = action.payload;
    })
    .addCase(setEdges, (state, action) => {
      state.edges = action.payload;
    })
    .addCase(updateNodeData, (state, action) => {
      state.nodes = state.nodes.map(node =>
        node.id === action.payload.id
          ? { ...node, data: { ...node.data, ...action.payload.data } }
          : node
      );
    })
    .addCase(addNode, (state, action) => {
      state.nodes.push(action.payload); // Simple push, assumes payload is valid Node
    })
    .addCase(addEdgeAction, (state, action) => {
      // Use React Flow's helper to add the edge
      state.edges = reactFlowAddEdge(action.payload, state.edges);
    })
    .addCase(removeElements, (state, action) => {
      const { nodeIds, edgeIds } = action.payload;
      state.nodes = state.nodes.filter(n => !nodeIds.includes(n.id));
      // Also remove edges connected to deleted nodes
      state.edges = state.edges.filter(e => !edgeIds.includes(e.id) && !nodeIds.includes(e.source) && !nodeIds.includes(e.target));
    })
    // Handle React Flow's batch changes via setNodes/setEdges
    .addCase(fetchFlowById.fulfilled, (state, action) => {
      // This case handles the initial load, directly setting the state
      state.nodes = action.payload.nodes || [];
      state.edges = action.payload.edges || [];
    });
});

// Wrap the core reducer with undoable
const undoableFlowCoreReducer = undoable(flowCoreReducer, {
  limit: 50, // Set a limit for the history
  // Filter out actions that shouldn't affect undo/redo if needed
  // filter: filterActions(['flow/fetchByIdStatus/fulfilled']),
});

// --- Main Flow Slice ---
const flowSlice = createSlice({
  name: 'flow',
  initialState,
  reducers: {
    // Actions that modify non-undoable state
    setCurrentFlowId: (state, action: PayloadAction<string | null>) => {
      if (state.currentFlowId !== action.payload) {
        state.currentFlowId = action.payload;
        // Reset non-history state and the history itself
        state.flowName = 'Untitled Flow';
        state.error = null;
        state.isLoading = false;
        state.isSaving = false;
        state.saveError = null;
        state.lastSaveTime = null;
        // Reset history to initial state
        state.history = {
            past: [],
            present: initialCoreState,
            future: [],
            _latestUnfiltered: initialCoreState, group: null, index: 0
        };
      }
    },
    setFlowName: (state, action: PayloadAction<string>) => {
      state.flowName = action.payload;
      // Note: flowName changes are NOT undoable with this setup.
      // If needed, move flowName into FlowCoreState and the core reducer.
    },
    clearSaveError: (state) => {
      state.saveError = null;
    },
    // Action creators for undoable actions are defined above using createSlice hack
    // Their logic is handled by flowCoreReducer and undoable()
  },
  extraReducers: (builder) => {
    builder
      // --- Fetching ---
      .addCase(fetchFlowById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
        console.log('Redux: Fetching flow pending...');
      })
      .addCase(fetchFlowById.fulfilled, (state, action) => {
        // Update non-history state
        state.isLoading = false;
        state.currentFlowId = action.payload.id ?? null;
        state.flowName = action.payload.name;
        state.error = null;
        state.lastSaveTime = new Date().toISOString(); // Assume load time is initial "save" state
        state.isSaving = false;
        state.saveError = null;
        console.log('Redux: Fetching flow fulfilled');
        // Update history state - Let undoable reducer handle this via addMatcher
        // The actual nodes/edges data is passed via the action payload
      })
      .addCase(fetchFlowById.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload ?? action.error.message ?? 'Unknown error';
        state.currentFlowId = null; // Reset id on fetch failure
        state.flowName = 'Untitled Flow';
        // Reset history on error
        state.history = { past: [], present: initialCoreState, future: [], _latestUnfiltered: initialCoreState, group: null, index: 0 };
        console.error('Redux: Fetching flow rejected', action.payload, action.error);
      })
      // --- Saving ---
      .addCase(saveFlow.pending, (state) => {
        console.log('Redux: Saving flow pending...');
        state.isSaving = true;
        state.saveError = null;
      })
      .addCase(saveFlow.fulfilled, (state, action) => {
        console.log('Redux: Saving flow fulfilled at', action.payload.lastSaveTime);
        state.isSaving = false;
        state.lastSaveTime = action.payload.lastSaveTime;
        state.saveError = null;
        // Clear future history on successful save? Optional, but common.
        // state.history.future = [];
      })
      .addCase(saveFlow.rejected, (state, action) => {
        console.error('Redux: Saving flow rejected', action.payload, action.error);
        state.isSaving = false;
        state.saveError = (action.payload as string) ?? action.error.message ?? 'Unknown save error';
      })
      // --- Let undoable reducer handle history actions ---
      .addMatcher(
        // Match all actions intended for the core undoable reducer
        (action) => [
          setNodes.type,
          setEdges.type,
          updateNodeData.type,
          addNode.type,
          addEdgeAction.type, // Use the renamed action type
          removeElements.type,
          UndoActionCreators.undo().type,
          UndoActionCreators.redo().type,
          fetchFlowById.fulfilled.type // Let undoable handle setting initial state too
        ].includes(action.type),
        (state, action) => {
          // Delegate history state updates to the undoable reducer
          state.history = undoableFlowCoreReducer(state.history, action);
        }
      );
  },
});

// Export non-undoable actions
export const { setCurrentFlowId, setFlowName, clearSaveError } = flowSlice.actions;

// Export undoable action creators
export { setNodes, setEdges, updateNodeData, addNode, addEdgeAction as addEdge, removeElements };

// Export Undo/Redo action creators from redux-undo for convenience
export const flowUndo = UndoActionCreators.undo;
export const flowRedo = UndoActionCreators.redo;

// Selectors
export const selectCurrentFlowId = (state: RootState) => state.flow.currentFlowId;
export const selectFlowName = (state: RootState) => state.flow.flowName;
export const selectFlowHistory = (state: RootState) => state.flow.history; // Expose history if needed
export const selectNodes = (state: RootState) => state.flow.history.present.nodes; // Select from present state
export const selectEdges = (state: RootState) => state.flow.history.present.edges; // Select from present state
export const selectCanUndo = (state: RootState) => state.flow.history.past.length > 0;
export const selectCanRedo = (state: RootState) => state.flow.history.future.length > 0;
export const selectIsFlowLoading = (state: RootState) => state.flow.isLoading;
export const selectFlowError = (state: RootState) => state.flow.error;
export const selectIsSaving = (state: RootState) => state.flow.isSaving;
export const selectSaveError = (state: RootState) => state.flow.saveError;
export const selectLastSaveTime = (state: RootState) => state.flow.lastSaveTime;

export default flowSlice.reducer; 