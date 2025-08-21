// frontend/src/api/api.ts
import axios, { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

// 使用环境变量配置API基础URL，如果不存在则使用默认值
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// 数据接口定义
export interface FlowData {
    id?: string; // UUID字符串
    name: string;
    flow_data?: any;
    user_id?: string; // UUID字符串
    created_at?: string;
    updated_at?: string;
}

export interface NodeGenerationResult {
    id: string;
    type: string;
    data: {
        label: string;
        [key: string]: any;
    };
}

export interface NodeUpdateResult {
    data: {
        label: string;
        [key: string]: any;
    };
}

export interface UserRegisterData {
    username: string;
    password: string;
    email?: string;
}

export interface UserLoginData {
    username: string;
    password: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user_id: string; // UUID字符串
}

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
    baseURL: API_BASE_URL
});

// 添加请求拦截器，自动附加认证token
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
        const token = localStorage.getItem('access_token');
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error: any) => {
        return Promise.reject(error);
    }
);

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
 * Generates a new node using the LLM.
 * @param {string} prompt - The prompt to use for generating the node.
 * @returns {Promise<NodeGenerationResult>} - A promise that resolves to the generated node data.
 */
export const generateNode = async (prompt: string): Promise<NodeGenerationResult> => {
    console.log("generateNode request:", prompt);
    try {
        const response: AxiosResponse<NodeGenerationResult> = await apiClient.post(`/llm/generate_node`, { prompt: prompt });
        return response.data;
    } catch (error) {
        console.error("Error generating node:", error);
        throw error;
    }
};

/**
 * Updates a node using the LLM.
 * @param {string} nodeId - The ID of the node to update.
 * @param {string} prompt - The prompt to use for updating the node.
 * @returns {Promise<NodeUpdateResult>} - A promise that resolves to the updated node data.
 */
export const updateNodeByLLM = async (nodeId: string, prompt: string): Promise<NodeUpdateResult> => {
    console.log("updateNodeByLLM request:", nodeId, prompt);
    try {
        const response: AxiosResponse<NodeUpdateResult> = await apiClient.post(`/llm/update_node/${nodeId}`, { prompt: prompt });
        return response.data;
    } catch (error) {
        console.error("Error updating node by LLM:", error);
        throw error;
    }
};

/**
 * Registers a new user.
 * @param {UserRegisterData} userData - The user data to register (username, password).
 * @returns {Promise<any>} - A promise that resolves to the registered user data.
 */
export const registerUser = async (userData: UserRegisterData): Promise<any> => {
    console.log("registerUser request:", userData);
    try {
        const response: AxiosResponse<any> = await axios.post(`${API_BASE_URL}/users/register`, userData);
        return response.data;
    } catch (error) {
        console.error("Error registering user:", error);
        throw error;
    }
};

/**
 * Logs in an existing user.
 * @param {UserLoginData} userData - The user data to login (username, password).
 * @returns {Promise<LoginResponse>} - A promise that resolves to the login token.
 */
export const loginUser = async (userData: UserLoginData): Promise<LoginResponse> => {
    console.log("loginUser request:", userData);
    try {
        // 将JSON转换为表单数据格式，因为后端使用的是OAuth2PasswordRequestForm
        const formData = new URLSearchParams();
        formData.append('username', userData.username);
        formData.append('password', userData.password);

        const response: AxiosResponse<LoginResponse> = await axios.post(`${API_BASE_URL}/users/login`, formData, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });

        console.log('Login Response:', response.data);
        return response.data;
    } catch (error) {
        console.error("Error logging in user:", error);
        throw error;
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
 * 发送邮件到指定邮箱
 * @param {string} title - 邮件标题
 * @param {string} content - 邮件内容
 * @returns {Promise<any>} - Promise，成功resolve，失败reject
 */
export const sendEmail = async (title: string, content: string): Promise<any> => {
    console.log("sendEmail request:", title, content);
    try {
        const response: AxiosResponse<any> = await apiClient.post('/email/send', {
            to: 'ren.yiyu@nidec.com', // 接收者邮箱
            subject: title,
            body: content,
        });
        return response.data;
    } catch (error) {
        console.error("Error sending email:", error);
        throw error;
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