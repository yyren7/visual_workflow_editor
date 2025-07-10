import { AxiosResponse } from 'axios';
import { apiClient } from './apiClient'; // 导入共享的 apiClient

// --- 数据接口定义 ---
export interface FlowData {
    id?: string; // UUID字符串
    name: string;
    flow_data?: any;
    sas_state?: any; // 修改字段名
    user_id?: string; // UUID字符串
    created_at?: string;
    updated_at?: string;
}

// --- Flow 相关函数 ---

/**
 * Creates a new flow.
 * @param {FlowData} flowData - The flow data to be created.
 * @returns {Promise<FlowData>} - A promise that resolves to the created flow's ID.
 */
export const createFlow = async (flowData: FlowData): Promise<FlowData> => {
    console.log("createFlow request:", flowData);
    try {
        const response: AxiosResponse<FlowData> = await apiClient.post(`/flows/`, flowData);
        return response.data;
    } catch (error) {
        console.error("Error creating flow:", error);
        throw error;
    }
};

/**
 * Retrieves a flow by its ID.
 * @param {string} flowId - The UUID of the flow to retrieve.
 * @returns {Promise<FlowData>} - A promise that resolves to the flow data.
 */
export const getFlow = async (flowId: string): Promise<FlowData> => {
    console.log("getFlow request:", flowId);
    try {
        const response: AxiosResponse<FlowData> = await apiClient.get(`/flows/${flowId}`);
        return response.data;
    } catch (error: any) {
        if (error.response && error.response.status === 403) {
            console.error("Permission denied: You don't have access to this flow");
            throw new Error("没有权限访问此流程图");
        } else if (error.response && error.response.status === 404) {
            console.error("Flow not found");
            throw new Error("流程图不存在");
        } else {
            console.error("Error getting flow:", error);
            throw error;
        }
    }
};

/**
 * Updates a flow by its ID.
 * @param {string} flowId - The UUID of the flow to update.
 * @param {FlowData} flowData - The updated flow data.
 * @returns {Promise<void>} - A promise that resolves when the flow is updated.
 */
export const updateFlow = async (flowId: string, flowData: FlowData): Promise<void> => {
    console.log("updateFlow request:", flowId, flowData);
    try {
        await apiClient.put(`/flows/${flowId}`, flowData);
    } catch (error: any) {
        if (error.response && error.response.status === 403) {
            console.error("Permission denied: You don't have permission to update this flow");
            throw new Error("没有权限更新此流程图");
        } else if (error.response && error.response.status === 404) {
            console.error("Flow not found");
            throw new Error("流程图不存在");
        } else {
            console.error("Error updating flow:", error);
            throw error;
        }
    }
};

/**
 * Deletes a flow by its ID.
 * @param {string} flowId - The UUID of the flow to delete.
 * @returns {Promise<void>} - A promise that resolves when the flow is deleted.
 */
export const deleteFlow = async (flowId: string): Promise<void> => {
    console.log("deleteFlow request:", flowId);
    try {
        await apiClient.delete(`/flows/${flowId}`);
    } catch (error: any) {
        if (error.response && error.response.status === 403) {
            console.error("Permission denied: You don't have permission to delete this flow");
            throw new Error("没有权限删除此流程图");
        } else if (error.response && error.response.status === 404) {
            console.error("Flow not found");
            throw new Error("流程图不存在");
        } else {
            console.error("Error deleting flow:", error);
            throw error;
        }
    }
};

/**
 * Retrieves the last interacted chat ID for a given flow.
 * Calls the backend endpoint GET /flows/{flowId}/last_chat.
 * @param {string} flowId - The UUID of the flow.
 * @returns {Promise<{ chatId: string | null }>} - A promise resolving to the chat ID or null.
 */
export const getLastChatIdForFlow = async (flowId: string): Promise<{ chatId: string | null }> => {
    console.log(`API call: getLastChatIdForFlow for flowId ${flowId}`);
    try {
        // Make the actual API call using apiClient
        const response: AxiosResponse<{ chatId: string | null }> = await apiClient.get(`/flows/${flowId}/last_chat`);
        // Return the data part of the response, which should match { chatId: string | null }
        return response.data;
    } catch (error: any) {
        if (error.response && error.response.status === 404) {
            // Handle 404 specifically: Flow might exist but no last chat ID recorded, or flow itself not found/no permission.
            console.warn(`getLastChatIdForFlow: Flow ${flowId} not found or access denied (404).`);
            return { chatId: null };
        } else if (error.response && error.response.status === 403) {
             // Handle 403 Forbidden explicitly
             console.warn(`getLastChatIdForFlow: Permission denied for flow ${flowId} (403).`);
             return { chatId: null };
        }
        // Log and rethrow other unexpected errors
        console.error(`Error fetching last chat ID for flow ${flowId}:`, error);
         return { chatId: null }; // Return null as a fallback for other errors
    }
};

/**
 * Get all flows for the current user with pagination.
 * @param {number} skip - The number of flows to skip.
 * @param {number} limit - The maximum number of flows to return.
 * @returns {Promise<FlowData[]>} - A promise that resolves to the flows data.
 */
export const getFlowsForUser = async (skip = 0, limit = 10): Promise<FlowData[]> => {
    console.log("getFlowsForUser request:", skip, limit);
    try {
        const response: AxiosResponse<FlowData[]> = await apiClient.get(`/flows/?skip=${skip}&limit=${limit}`);
        console.log("getFlowsForUser response:", response.status, response.data);
        return response.data || []; // 确保始终返回数组，即使后端返回null
    } catch (error: any) {
        console.error("Error getting flows for user:", error);
        if (error.response) {
            // 服务器返回了错误状态码
            console.error("Server response error:", error.response.status, error.response.data);
            throw new Error(`服务器错误 (${error.response.status}): ${error.response.data?.detail || '未知错误'}`);
        } else if (error.request) {
            // 请求已发送但没有收到响应
            console.error("No response from server:", error.request);
            throw new Error('服务器无响应，请检查网络连接');
        } else {
            // 设置请求时发生错误
            console.error("Request error:", error.message);
            throw error;
        }
    }
};

/**
 * Get user's last active flow or create a default one if none exists.
 * @returns {Promise<FlowData>} - A promise that resolves to the flow data.
 */
// 添加一个标记，防止重复创建流程图
let isCreatingFlow = false;
let cachedFlowData: FlowData | null = null;

export const getOrCreateUserFlow = async (): Promise<FlowData> => {
    console.log("getOrCreateUserFlow request");

    // 如果已经有缓存的流程图数据，直接返回
    if (cachedFlowData && cachedFlowData.id) {
        console.log("Returning cached flow:", cachedFlowData);
        return cachedFlowData;
    }

    // 如果正在创建流程图，阻止重复创建
    if (isCreatingFlow) {
        console.log("Already creating a flow, waiting...");
        // 等待一段时间再检查缓存
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (cachedFlowData && cachedFlowData.id) {
            console.log("Using newly created flow from cache:", cachedFlowData);
            return cachedFlowData;
        }
    }

    try {
        isCreatingFlow = true;

        // 先尝试获取用户的流程列表
        try {
            const flows: FlowData[] = await getFlowsForUser(0, 10);
            // 如果有流程，返回第一个并缓存
            if (flows && flows.length > 0) {
                console.log("Found existing flow:", flows[0]);
                cachedFlowData = flows[0];
                return flows[0];
            }
        } catch (error) {
            console.error("Error fetching flows, will create a new one:", error);
            // 如果获取失败，继续创建新流程图
        }

        // 如果没有流程，创建一个默认流程
        console.log("No flows found or error occurred, creating default flow");
        const defaultFlow: FlowData = {
            name: "默认流程图",
            flow_data: {
                nodes: [],
                edges: [],
                viewport: { x: 0, y: 0, zoom: 1 }
            }
        };

        const newFlow = await createFlow(defaultFlow);
        console.log("Created default flow:", newFlow);
        cachedFlowData = newFlow;
        return newFlow;
    } catch (error) {
        console.error("Error in getOrCreateUserFlow:", error);
        throw error;
    } finally {
        isCreatingFlow = false;
    }
};

/**
 * Updates a flow name by its ID.
 * @param {string} flowId - The UUID of the flow to update.
 * @param {string} newName - The new name for the flow.
 * @returns {Promise<void>} - A promise that resolves when the flow name is updated.
 */
export const updateFlowName = async (flowId: string, newName: string): Promise<void> => {
    console.log("updateFlowName request:", flowId, newName);
    try {
        // 这里只更新流程图名称，而不更新其他数据
        await apiClient.put(`/flows/${flowId}`, { name: newName });
    } catch (error: any) {
        if (error.response && error.response.status === 403) {
            console.error("Permission denied: You don't have permission to update this flow");
            throw new Error("没有权限更新此流程图");
        } else if (error.response && error.response.status === 404) {
            console.error("Flow not found");
            throw new Error("流程图不存在");
        } else {
            console.error("Error updating flow name:", error);
            throw error;
        }
    }
};

/**
 * 深度更新对象中的flowId引用
 * @param {any} obj - 要更新的对象
 * @param {string} oldFlowId - 旧的flowId
 * @param {string} newFlowId - 新的flowId
 * @returns {any} - 更新后的对象
 */
const updateFlowIdReferences = (obj: any, oldFlowId: string, newFlowId: string): any => {
  if (obj === null || obj === undefined) {
    return obj;
  }
  
  if (typeof obj === 'string') {
    // 替换字符串中的flowId引用
    if (obj.includes(oldFlowId)) {
      return obj.replace(new RegExp(oldFlowId, 'g'), newFlowId);
    }
    return obj;
  }
  
  if (Array.isArray(obj)) {
    return obj.map(item => updateFlowIdReferences(item, oldFlowId, newFlowId));
  }
  
  if (typeof obj === 'object') {
    const updated: any = {};
    for (const [key, value] of Object.entries(obj)) {
      updated[key] = updateFlowIdReferences(value, oldFlowId, newFlowId);
    }
    return updated;
  }
  
  return obj;
};

/**
 * 生成新的节点ID
 * @param {string} originalId - 原始ID
 * @returns {string} - 新的ID
 */
const generateNewNodeId = (originalId: string): string => {
  const timestamp = Date.now();
  const randomSuffix = Math.floor(Math.random() * 1000); // 添加随机数避免冲突
  // 保留节点类型前缀，替换时间戳部分
  const parts = originalId.split('-');
  if (parts.length >= 2) {
    return `${parts[0]}-${timestamp}${randomSuffix}`;
  }
  return `node-${timestamp}${randomSuffix}`;
};

/**
 * 生成新的边ID
 * @param {string} source - 源节点ID
 * @param {string} sourceHandle - 源节点连接点
 * @param {string} target - 目标节点ID
 * @param {string} targetHandle - 目标节点连接点
 * @returns {string} - 新的边ID
 */
const generateNewEdgeId = (source: string, sourceHandle: string, target: string, targetHandle: string): string => {
  return `reactflow__edge-${source}${sourceHandle}-${target}${targetHandle}`;
};

/**
 * 深度复制对象并重新生成ID
 * @param {any} obj - 要复制的对象
 * @param {Map<string, string>} idMapping - ID映射表
 * @returns {any} - 复制并重新映射ID后的对象
 */
const deepCopyAndRemapIds = (obj: any, idMapping: Map<string, string>): any => {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(item => deepCopyAndRemapIds(item, idMapping));
  }

  if (typeof obj === 'object') {
    const copied: any = {};
    for (const [key, value] of Object.entries(obj)) {
      copied[key] = deepCopyAndRemapIds(value, idMapping);
    }

    // 重新映射相关ID字段
    if (copied.id && idMapping.has(copied.id)) {
      copied.id = idMapping.get(copied.id);
    }
    if (copied.nodeId && idMapping.has(copied.nodeId)) {
      copied.nodeId = idMapping.get(copied.nodeId);
    }
    if (copied.source && idMapping.has(copied.source)) {
      copied.source = idMapping.get(copied.source);
    }
    if (copied.target && idMapping.has(copied.target)) {
      copied.target = idMapping.get(copied.target);
    }

    return copied;
  }

  return obj;
};

/**
 * 复制流程图
 * @param {string} flowId - 要复制的流程图ID
 * @returns {Promise<any>} - 返回新创建的流程图数据
 */
export const duplicateFlow = async (flowId: string): Promise<any> => {
  try {
    console.log('duplicateFlow request:', flowId);
    
    // 1. 获取原始流程图数据
    const originalFlow = await getFlow(flowId);
    console.log('原始flow数据:', originalFlow);
    
    if (!originalFlow) {
      throw new Error('原始流程图不存在');
    }

    // 2. 解析flow_data
    let originalFlowData: any = {};
    try {
      originalFlowData = typeof originalFlow.flow_data === 'string' 
        ? JSON.parse(originalFlow.flow_data) 
        : (originalFlow.flow_data || {});
    } catch (e) {
      console.warn('解析flow_data失败，使用空对象:', e);
      originalFlowData = {};
    }
    
    console.log('解析后的flow_data:', originalFlowData);
    console.log('原始节点数量:', originalFlowData.nodes?.length || 0);
    console.log('原始边数量:', originalFlowData.edges?.length || 0);

    // 3. 生成新的flow名称
    const newFlowName = `${originalFlow.name || 'Untitled'} (副本)`;

    // 4. 创建ID映射表 - 只处理flow_data中的静态节点
    const idMapping = new Map<string, string>();
    
    // 为flow_data中的节点生成新ID
    if (originalFlowData.nodes && originalFlowData.nodes.length > 0) {
      originalFlowData.nodes.forEach((node: any) => {
        if (node.id) {
          const newId = generateNewNodeId(node.id);
          idMapping.set(node.id, newId);
          console.log(`ID映射: ${node.id} -> ${newId}`);
        }
      });
    } else {
      console.log('警告: 原始流程图没有节点');
    }

    console.log('ID映射表:', Array.from(idMapping.entries()));

    // 5. 深度复制flow_data并重新映射ID
    const remappedFlowData = deepCopyAndRemapIds(originalFlowData, idMapping);

    // 重新生成边的ID
    if (remappedFlowData.edges) {
      remappedFlowData.edges.forEach((edge: any) => {
        if (edge.source && edge.target && edge.sourceHandle && edge.targetHandle) {
          edge.id = generateNewEdgeId(edge.source, edge.sourceHandle, edge.target, edge.targetHandle);
        }
      });
    }

    console.log('重新映射后的节点数量:', remappedFlowData.nodes?.length || 0);
    console.log('重新映射后的边数量:', remappedFlowData.edges?.length || 0);

    // 6. 注意：LangGraph状态现在通过后端的checkpoint复制处理

    // 7. 准备发送到后端的数据
    const flowCreateData = {
      name: newFlowName,
      flow_data: remappedFlowData,
      source_flow_id: flowId  // 添加源flow_id用于checkpoint复制
    };

    console.log('准备发送到后端的数据:', flowCreateData);

    // 8. 创建新流程图
    const newFlow = await createFlow(flowCreateData);
    console.log('复制流程图成功:', newFlow);
    
    // 9. LangGraph状态已通过后端checkpoint复制自动处理
    console.log('LangGraph状态通过checkpoint复制已自动处理');

    return newFlow;
  } catch (error) {
    console.error('复制流程图失败:', error);
    throw error;
  }
};

/**
 * 设置用户最后选择的流程图
 * @param flowId 流程图ID
 * @returns 成功返回true
 */
export const setAsLastSelectedFlow = async (flowId: string): Promise<boolean> => {
    const response = await apiClient.post(`/flows/${flowId}/set-as-last-selected`, null, {
        headers: {
            'Content-Type': 'application/json',
        },
    });
    return response.data;
};

/**
 * 获取用户最后选择的流程图
 * @returns 流程图数据
 */
export const getLastSelectedFlow = async (): Promise<FlowData> => {
    const response = await apiClient.get('/flows/user/last-selected', {
        headers: {
            'Content-Type': 'application/json',
        },
    });
    return response.data;
};

/**
 * 确保流程图有完整的 agent_state 结构
 * @param flowId 流程图ID
 * @returns 更新后的流程图数据
 */
export const ensureFlowAgentState = async (flowId: string): Promise<FlowData> => {
    console.log("ensureFlowAgentState request:", flowId);
    try {
        const response: AxiosResponse<FlowData> = await apiClient.post(`/flows/${flowId}/ensure-agent-state`);
        return response.data;
    } catch (error: any) {
        console.error("Error ensuring flow agent state:", error);
        throw error;
    }
};

// 原始 api.ts 中残留的 flowApi 对象，现在里面的函数已被导出，这个对象不再需要
// export const flowApi = {
//   getFlows: async () => { ... },
//   getFlow: async (flowId: number) => { ... },
//   createFlow: async (flowData: any) => { ... },
//   updateFlow: async (flowId: number, flowData: any) => { ... },
//   deleteFlow: async (flowId: number) => { ... }
// }; 