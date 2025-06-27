import { createSlice, PayloadAction, createAsyncThunk, ActionReducerMapBuilder, SerializedError } from '@reduxjs/toolkit';
import { Node, Edge, addEdge as reactFlowAddEdge } from 'reactflow';
import { NodeData } from '../../components/FlowEditor'; // Adjust path if needed
import { getFlow, updateFlow } from '../../api/flowApi'; // 使用 getFlow 替代 ensureFlowAgentState
import { RootState } from '../store';

interface FlowState {
  currentFlowId: string | null;
  flowName: string | null; // 可以为 null
  nodes: Node<NodeData>[] | null; // 可以为 null
  edges: Edge[] | null; // 可以为 null
  agentState: any | null; // 可以为 null
  isLoading: boolean;
  error: string | null;
  isSaving: boolean;
  saveError: string | null;
  lastSaveTime: string | null;
  activeLangGraphStreamFlowId: string | null;
}

const initialState: FlowState = {
  currentFlowId: null,
  flowName: null,
  nodes: null,
  edges: null,
  agentState: null,
  isLoading: false,
  error: null,
  isSaving: false,
  saveError: null,
  lastSaveTime: null,
  activeLangGraphStreamFlowId: null,
};

// 为 fulfilled action 定义 payload 类型
interface FetchFlowByIdPayload {
    id: string;
    name: string;
    nodes: Node<NodeData>[];
    edges: Edge[];
    sas_state: any;
}

// 改造 fetchFlowById，使其成为唯一的数据获取入口
export const fetchFlowById = createAsyncThunk<FetchFlowByIdPayload, string, { rejectValue: string }>(
    'flow/fetchById', // Action 名称更新
    async (flowId: string, { rejectWithValue }) => {
        try {
            console.log(`Redux: Fetching flow and agent state for ${flowId}`);
            // 直接调用 getFlow 来获取所有数据（现在后端会自动提供完整的 sas_state）
            const flowData = await getFlow(flowId);
            if (flowData && flowData.id) {
                return {
                    id: flowData.id,
                    name: flowData.name || 'Untitled Flow',
                    // 如果 flow_data 为 null/undefined，则返回空数组
                    nodes: flowData.flow_data?.nodes || [],
                    edges: flowData.flow_data?.edges || [],
                    // 后端现在保证总是返回有效的 sas_state，但仍然保留安全检查
                    sas_state: flowData.sas_state || {
                        dialog_state: "initial",
                        messages: [],
                        config: {},
                        generated_node_xmls: [],
                        task_list_accepted: false,
                        module_steps_accepted: false,
                        revision_iteration: 0,
                        is_error: false,
                        language: "zh",
                        relation_xml_content: "",
                        relation_xml_path: "",
                        merged_xml_file_paths: []
                    },
                };
            } else {
                console.error(`Redux: Invalid data received for ${flowId}. Data:`, flowData);
                return rejectWithValue('Invalid or incomplete flow data received');
            }
        } catch (error: any) {
            console.error(`Redux: Error loading flow ${flowId}:`, error);
            return rejectWithValue(error.message || 'Failed to fetch flow data');
        }
    }
);

// --- saveFlow thunk ---
interface SaveFlowPayload {
    lastSaveTime: string;
}

export const saveFlow = createAsyncThunk<SaveFlowPayload, void, { state: RootState, rejectValue: string }>(
    'flow/saveStatus',
    async (_, { getState, rejectWithValue }) => {
        const state = getState().flow;
        const { currentFlowId, flowName, nodes, edges } = state;

        if (!currentFlowId || !nodes || !edges || !flowName) { // 增加 null 检查
            return rejectWithValue('No active flow or flow data to save');
        }

        console.log(`Redux: Attempting to save flow ${currentFlowId}...`);
        try {
            const nodesToSave = nodes.map(({ selected, ...nodeRest }) => nodeRest);
            
            const updateData = {
                name: flowName,
                flow_data: { nodes: nodesToSave, edges }
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
    setCurrentFlowId: (state: FlowState, action: PayloadAction<string | null>) => {
      state.currentFlowId = action.payload;
    },
    setNodes: (state: FlowState, action: PayloadAction<Node<NodeData>[]>) => {
      state.nodes = action.payload;
    },
    setEdges: (state: FlowState, action: PayloadAction<Edge[]>) => {
      state.edges = action.payload;
    },
    addNode: (state: FlowState, action: PayloadAction<Node<NodeData>>) => {
        if (state.nodes) {
            state.nodes.push(action.payload);
        }
    },
    addEdge: (state: FlowState, action: PayloadAction<Edge>) => {
        if (state.edges) {
            state.edges = reactFlowAddEdge(action.payload, state.edges);
        }
    },
    updateNodeData: (state: FlowState, action: PayloadAction<{ id: string; data: Partial<NodeData> }>) => {
        if (!state.nodes) return;
        const nodeIndex = state.nodes.findIndex((n: Node<NodeData>) => n.id === action.payload.id);
        if (nodeIndex !== -1) {
            state.nodes[nodeIndex] = {
                ...state.nodes[nodeIndex],
                data: { ...state.nodes[nodeIndex].data, ...action.payload.data }
            };
        }
    },
    setFlowName: (state: FlowState, action: PayloadAction<string>) => {
        state.flowName = action.payload;
    },
    updateAgentState: (state: FlowState, action: PayloadAction<any>) => {
        if (state.agentState) {
            state.agentState = { ...state.agentState, ...action.payload };
        } else {
            state.agentState = action.payload;
        }
    },
    selectNode: (state: FlowState, action: PayloadAction<string>) => {
      if (!state.nodes) return;
      const selectedNodeId = action.payload;
      state.nodes = state.nodes.map(node => ({
        ...node,
        selected: node.id === selectedNodeId,
      }));
    },
    deselectAllNodes: (state: FlowState) => {
      if (state.nodes) {
        state.nodes = state.nodes.map(node => ({
          ...node,
          selected: false,
        }));
      }
    },
    deleteNode: (state: FlowState, action: PayloadAction<string>) => {
      const nodeId = action.payload;
      if (state.nodes) {
        state.nodes = state.nodes.filter(node => node.id !== nodeId);
      }
      if (state.edges) {
        state.edges = state.edges.filter(edge => 
          edge.source !== nodeId && edge.target !== nodeId
        );
      }
    },
    deleteEdge: (state: FlowState, action: PayloadAction<string>) => {
      const edgeId = action.payload;
      if (state.edges) {
        state.edges = state.edges.filter(edge => edge.id !== edgeId);
      }
    },
    setActiveLangGraphStreamFlowId: (state: FlowState, action: PayloadAction<string | null>) => {
      state.activeLangGraphStreamFlowId = action.payload;
    },
  },
  extraReducers: (builder: ActionReducerMapBuilder<FlowState>) => {
    builder
      .addCase(fetchFlowById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
        // 在加载新数据之前，不清空旧数据，UI可以继续显示旧内容直到加载完成
        console.log('Redux: Fetching flow data pending...');
      })
      .addCase(fetchFlowById.fulfilled, (state: FlowState, action: PayloadAction<FetchFlowByIdPayload>) => {
        // 直接用后端返回的真实状态覆盖
        state.currentFlowId = action.payload.id;
        state.flowName = action.payload.name;
        state.nodes = action.payload.nodes;
        state.edges = action.payload.edges;
        state.agentState = action.payload.sas_state;
        
        state.isLoading = false;
        state.error = null;
        state.lastSaveTime = new Date().toISOString();
        
        console.log(
          `Redux: Fetching flow data fulfilled for ${action.payload.id}. Nodes: ${action.payload.nodes.length}, DialogState: ${action.payload.sas_state?.dialog_state}`
        );
      })
      .addCase(fetchFlowById.rejected, (state: FlowState, action) => {
        // 加载失败时，只更新错误状态，不清除可能仍然有用的旧数据
        state.isLoading = false;
        state.error = (action.payload as string) ?? action.error.message ?? 'Unknown error';
        console.error('Redux: Fetching flow data rejected', action.payload, action.error);
      });
      
    // saveFlow extraReducers
    builder
        .addCase(saveFlow.pending, (state) => {
            state.isSaving = true;
            state.saveError = null;
        })
        .addCase(saveFlow.fulfilled, (state, action: PayloadAction<SaveFlowPayload>) => {
            state.isSaving = false;
            state.lastSaveTime = action.payload.lastSaveTime;
            state.saveError = null;
        })
        .addCase(saveFlow.rejected, (state, action) => {
            state.isSaving = false;
            state.saveError = (action.payload as string) ?? action.error.message ?? 'Unknown save error';
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
    deleteEdge,       // Export new action
    setActiveLangGraphStreamFlowId, // Export new action
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
export const selectActiveLangGraphStreamFlowId = (state: RootState) => state.flow.activeLangGraphStreamFlowId; // Added selector

export default flowSlice.reducer; 