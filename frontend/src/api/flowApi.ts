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
        const response: AxiosResponse<FlowData[]> = await apiClient.get(`/flows?skip=${skip}&limit=${limit}`);
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
 * 复制现有流程图
 * @param {string} flowId - 要复制的流程图ID
 * @returns {Promise<FlowData>} - 返回新创建的流程图数据
 */
export const duplicateFlow = async (flowId: string): Promise<FlowData> => {
  console.log("duplicateFlow request:", flowId);
  try {
    // 先获取原始流程图数据
    const originalFlow = await getFlow(flowId);

    // 创建新的流程图对象，复制原始流程图的数据
    const newFlowData: FlowData = {
      name: `${originalFlow.name} (复制)`,
      flow_data: originalFlow.flow_data,
    };

    // 创建新的流程图
    const newFlow = await createFlow(newFlowData);
    return newFlow;
  } catch (error: any) {
    console.error("复制流程图失败:", error);
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