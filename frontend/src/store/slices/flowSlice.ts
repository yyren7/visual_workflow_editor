import { createSlice, PayloadAction, createAsyncThunk, ActionReducerMapBuilder, SerializedError } from '@reduxjs/toolkit';
import { Node, Edge, addEdge as reactFlowAddEdge } from 'reactflow';
import { NodeData } from '../../components/FlowEditor/types'; // 修正导入路径
import { getFlow, updateFlow } from '../../api/flowApi'; // 使用 getFlow 替代 ensureFlowAgentState
import { RootState } from '../store';

interface FlowState {
  currentFlowId: string | null;
  flowName: string | null; // 可以为 null
  nodes: Node<NodeData>[] | null; // 可以为 null
  edges: Edge[] | null; // 可以为 null
  agentState: {
    streamingContent?: string;
    processingStage?: string;
    [key: string]: any;
  } | null;
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
            
            // 🔧 同时获取Flow数据和LangGraph状态
            const [flowData, sasState] = await Promise.all([
                getFlow(flowId),
                // 获取LangGraph checkpoint状态
                fetch(`${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${flowId}/state`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        'Content-Type': 'application/json'
                    }
                }).then(async (res) => {
                    if (res.ok) {
                        const data = await res.json();
                        console.log('🔧 [DEBUG] Raw SAS state response:', data);
                        console.log('🔧 [DEBUG] Response type:', typeof data);
                        console.log('🔧 [DEBUG] Response keys:', Object.keys(data || {}));
                        
                        // 🔧 修复：正确处理LangGraph StateSnapshot响应
                        let stateValues = null;
                        if (data && Array.isArray(data)) {
                            console.log('🔧 [DEBUG] Response is array, length:', data.length);
                            // LangGraph StateSnapshot的第0个元素包含状态数据
                            if (data.length > 0 && data[0] && typeof data[0] === 'object') {
                                console.log('🔧 [DEBUG] Using data[0] as state values');
                                console.log('🔧 [DEBUG] data[0] keys:', Object.keys(data[0]));
                                console.log('🔧 [DEBUG] data[0] content:', data[0]);
                                stateValues = data[0];
                            } else {
                                console.log('🔧 [DEBUG] Array[0] is not valid state object');
                            }
                        } else if (data && typeof data === 'object') {
                            console.log('🔧 [DEBUG] Processing data object...');
                            // 如果data有values函数，调用它获取真正的状态
                            if (typeof data.values === 'function') {
                                console.log('🔧 [DEBUG] data.values is a function, calling it...');
                                stateValues = data.values();
                            } else if (data.values && typeof data.values === 'object') {
                                console.log('🔧 [DEBUG] data.values is an object, using directly...');
                                console.log('🔧 [DEBUG] data.values keys:', Object.keys(data.values));
                                stateValues = data.values;
                            } else {
                                console.log('🔧 [DEBUG] No values field found, using data directly...');
                                stateValues = data;
                            }
                        }
                        
                        console.log('🔧 [DEBUG] Final stateValues:', stateValues);
                        console.log('🔧 [DEBUG] Final stateValues keys:', Object.keys(stateValues || {}));
                        
                        // 检查是否有任务数据
                        if (stateValues && stateValues.sas_step1_generated_tasks) {
                            console.log('🔧 [DEBUG] ✅ Found sas_step1_generated_tasks:', stateValues.sas_step1_generated_tasks);
                        } else {
                            console.log('🔧 [DEBUG] ❌ No sas_step1_generated_tasks found in stateValues');
                        }
                        
                        // 🔧 深度复制并序列化状态，确保移除任何函数
                        const serializedState = JSON.parse(JSON.stringify(stateValues || {}));
                        console.log('🔧 [DEBUG] Serialized state:', serializedState);
                        return serializedState;
                    } else if (res.status === 404) {
                        // 如果没有找到LangGraph状态，返回默认初始状态
                        console.log(`Redux: No LangGraph state found for ${flowId}, using default initial state`);
                        return {
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
                        };
                    } else {
                        throw new Error(`Failed to fetch SAS state: ${res.status} ${res.statusText}`);
                    }
                }).catch(error => {
                    console.warn(`Redux: Error fetching SAS state for ${flowId}, using default:`, error);
                    // 出错时返回默认状态
                    return {
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
                    };
                })
            ]);

            if (flowData && flowData.id) {
                console.log(`Redux: Successfully fetched flow data and SAS state for ${flowId}`);
                console.log(`Redux: Flow nodes: ${flowData.flow_data?.nodes?.length || 0}, SAS dialog_state: ${sasState?.dialog_state}`);
                
                return {
                    id: flowData.id,
                    name: flowData.name || 'Untitled Flow',
                    // 如果 flow_data 为 null/undefined，则返回空数组
                    nodes: flowData.flow_data?.nodes || [],
                    edges: flowData.flow_data?.edges || [],
                    // 🔧 使用从LangGraph checkpoint获取的真实状态
                    sas_state: sasState,
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
    resetFlowState: (state) => {
      // 重置为初始状态
      Object.assign(state, initialState);
      console.log('Redux: Flow state has been reset.');
    },
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
        const newState = action.payload;
        // 🔧 确保状态可序列化，移除任何函数
        const serializableNewState = JSON.parse(JSON.stringify(newState || {}));
        
        if (state.agentState) {
            state.agentState = { ...state.agentState, ...serializableNewState };
        } else {
            state.agentState = serializableNewState;
        }
        // 当主要状态更新时，重置流式内容，为下一次流式输出做准备
        if (state.agentState) {
          state.agentState.streamingContent = '';
        }
    },
    appendStreamingContent: (state: FlowState, action: PayloadAction<string>) => {
      if (state.agentState) {
        if (!state.agentState.streamingContent) {
          state.agentState.streamingContent = '';
        }
        state.agentState.streamingContent += action.payload;
      }
    },
    setProcessingStage: (state: FlowState, action: PayloadAction<string>) => {
      if (state.agentState) {
        state.agentState.processingStage = action.payload;
      } else {
        state.agentState = { processingStage: action.payload };
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
    setProcessingStatus: (state: FlowState, action: PayloadAction<boolean>) => {
      if (state.agentState) {
        state.agentState.isProcessingUserInput = action.payload;
        if (action.payload) {
          // When starting, also clear any leftover review/error states
          state.agentState.dialog_state = 'sas_processing_user_input';
        }
      } else {
        // If agentState doesn't exist, create it
        state.agentState = {
          isProcessingUserInput: action.payload,
          dialog_state: action.payload ? 'sas_processing_user_input' : 'initial',
        };
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
        // 在加载新数据之前，立即清空旧数据，防止闪烁
        state.nodes = null;
        state.edges = null;
        state.currentFlowId = null;
        state.flowName = null;
        state.agentState = null;
        console.log('Redux: Fetching flow data pending, cleared old state.');
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
        
        // 🔧 新增：详细打印agentState调试信息
        console.log('🔧 [DEBUG] Full sas_state received:', action.payload.sas_state);
        if (action.payload.sas_state) {
          console.log('🔧 [DEBUG] sas_state keys:', Object.keys(action.payload.sas_state));
          console.log('🔧 [DEBUG] dialog_state:', action.payload.sas_state.dialog_state);
          console.log('🔧 [DEBUG] sas_step1_generated_tasks:', action.payload.sas_state.sas_step1_generated_tasks);
          console.log('🔧 [DEBUG] current_user_request:', action.payload.sas_state.current_user_request);
          console.log('🔧 [DEBUG] task_list_accepted:', action.payload.sas_state.task_list_accepted);
          console.log('🔧 [DEBUG] module_steps_accepted:', action.payload.sas_state.module_steps_accepted);
        } else {
          console.log('🔧 [DEBUG] No sas_state received!');
        }
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
    appendStreamingContent,
    setProcessingStage,
    selectNode,
    deselectAllNodes,
    deleteNode,
    deleteEdge,
    setProcessingStatus,
    setActiveLangGraphStreamFlowId,
    resetFlowState,
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