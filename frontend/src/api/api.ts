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

// 定义工作流处理请求接口
export interface WorkflowProcessRequest {
    prompt: string;
    session_id?: string;  // 会话ID，可选
}

// 定义工作流处理响应接口
export interface WorkflowProcessResponse {
    user_input?: string;
    expanded_input?: string;
    step_results: Array<{
        step: string;
        enriched_step?: string;
        tool_action?: {
            tool_type: string;
            result: {
                success: boolean;
                message: string;
                data: any;
            };
        };
    }>;
    missing_info?: any;
    created_nodes?: {
        [key: string]: {
            node_id: string;
            node_type: string;
            node_label: string;
            properties: any;
        };
    };
    session_id?: string;
    nodes?: Array<any>;
    connections?: Array<any>;
    summary?: string;
    error?: string;
    expanded_prompt?: string;
    llm_interactions?: Array<{
        stage: string;
        input: any;
        output: any;
        tool_type?: string;
        tool_params?: any;
    }>;
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
    baseURL: API_BASE_URL,
    withCredentials: true  // 添加凭证支持
});

// 添加请求拦截器，自动附加认证token
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
        const token = localStorage.getItem('access_token');
        
        // 排除不需要token的公开API路径
        const publicPaths = ['/users/login', '/users/register'];
        const isPublicPath = publicPaths.some(path => config.url?.includes(path));
        
        if (!isPublicPath) {
            if (!token) {
                console.warn(`API请求 ${config.url} 需要认证但未找到token`);
            } else {
                console.log(`为请求 ${config.url} 添加认证token`);
                if (config.headers) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
            }
        }
        
        return config;
    },
    (error: any) => {
        console.error('请求拦截器错误:', error);
        return Promise.reject(error);
    }
);

// 添加响应拦截器，处理认证错误
apiClient.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        // 处理401未授权错误
        if (error.response && error.response.status === 401) {
            console.error('认证失败 (401):', error.config.url);
            
            // 可以在这里触发重新认证或跳转到登录页面
            // 如果不是登录请求本身导致的401，可以清除token
            if (!error.config.url.includes('/users/login')) {
                console.warn('检测到认证过期，清除token');
                localStorage.removeItem('access_token');
                
                // 发布认证状态变更事件
                window.dispatchEvent(new Event('loginChange'));
            }
        }
        
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
        const response: AxiosResponse<any> = await axios.post(`${API_BASE_URL}/users/register`, userData, {
            withCredentials: true
        });
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
            },
            withCredentials: true
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
 * 处理工作流提示，创建或修改流程图节点
 * @param {WorkflowProcessRequest} request - 包含提示和可选会话ID的请求
 * @returns {Promise<WorkflowProcessResponse>} - 工作流处理结果
 */
export const processWorkflow = async (request: WorkflowProcessRequest): Promise<WorkflowProcessResponse> => {
    console.log("processWorkflow request:", request);
    try {
        // 获取当前语言
        const currentLanguage = localStorage.getItem('preferredLanguage') || 'en';
        
        // 添加语言到请求
        const requestWithLanguage = {
            ...request,
            language: currentLanguage
        };
        
        const response: AxiosResponse<WorkflowProcessResponse> = await apiClient.post('/workflow/process', requestWithLanguage);
        return response.data;
    } catch (error) {
        console.error("Error processing workflow:", error);
        throw error;
    }
};

// LangChain聊天接口定义
export interface ChatRequest {
    message: string;
    conversation_id?: string;
    metadata?: Record<string, any>;
}

export interface ChatResponse {
    conversation_id: string;
    message: string;
    created_at: string;
    metadata?: Record<string, any>;
    context_used?: boolean;
}

/**
 * 发送聊天消息到LangChain聊天API。
 * @param request 聊天请求
 * @returns 聊天响应
 */
export const sendChatMessage = async (request: ChatRequest): Promise<ChatResponse> => {
    console.log("sendChatMessage request:", request);
    try {
        // 获取当前语言
        const currentLanguage = localStorage.getItem('preferredLanguage') || 'en';
        
        // 添加语言到请求
        const requestWithLanguage = {
            ...request,
            language: currentLanguage
        };
        
        const response: AxiosResponse<ChatResponse> = await apiClient.post('/langchainchat/message', requestWithLanguage);
        return response.data;
    } catch (error) {
        console.error("Error sending chat message:", error);
        throw error;
    }
};

/**
 * 获取用户的聊天会话列表。
 * @returns 会话列表
 */
export const getChatConversations = async (): Promise<Array<any>> => {
    console.log("getChatConversations request");
    try {
        const response: AxiosResponse<Array<any>> = await apiClient.get('/langchainchat/conversations');
        return response.data;
    } catch (error) {
        console.error("Error getting chat conversations:", error);
        throw error;
    }
};

/**
 * 删除指定的聊天会话。
 * @param conversation_id 会话ID
 * @returns 删除结果
 */
export const deleteChatConversation = async (conversation_id: string): Promise<any> => {
    console.log("deleteChatConversation request:", conversation_id);
    try {
        const response: AxiosResponse<any> = await apiClient.delete(`/langchainchat/conversations/${conversation_id}`);
        return response.data;
    } catch (error) {
        console.error("Error deleting chat conversation:", error);
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

// 流程变量相关接口和函数
export interface FlowVariables {
  [key: string]: string;
}

/**
 * 获取流程图的所有变量
 * @param {string} flowId - 流程图ID
 * @returns {Promise<FlowVariables>} - 包含变量的对象
 */
export const getFlowVariables = async (flowId: string): Promise<FlowVariables> => {
  console.log("获取流程图变量:", flowId);
  try {
    const response = await apiClient.get(`/flow-variables/${flowId}`);
    return response.data;
  } catch (error) {
    console.error("获取流程图变量失败:", error);
    throw error;
  }
};

/**
 * 更新流程图的所有变量
 * @param {string} flowId - 流程图ID
 * @param {FlowVariables} variables - 变量对象
 * @returns {Promise<{message: string, count: number}>} - 操作结果
 */
export const updateFlowVariables = async (flowId: string, variables: FlowVariables): Promise<{message: string, count: number}> => {
  console.log("更新流程图变量:", flowId, variables);
  try {
    const response = await apiClient.post(`/flow-variables/${flowId}`, {
      variables: variables
    });
    return response.data;
  } catch (error) {
    console.error("更新流程图变量失败:", error);
    throw error;
  }
};

/**
 * 添加或更新单个变量
 * @param {string} flowId - 流程图ID
 * @param {string} key - 变量名
 * @param {string} value - 变量值
 * @returns {Promise<{message: string}>} - 操作结果
 */
export const addFlowVariable = async (flowId: string, key: string, value: string): Promise<{message: string}> => {
  console.log("添加/更新变量:", flowId, key, value);
  try {
    const response = await apiClient.post(`/flow-variables/${flowId}/variable`, {
      key: key,
      value: value
    });
    return response.data;
  } catch (error) {
    console.error(`添加/更新变量 ${key} 失败:`, error);
    throw error;
  }
};

/**
 * 删除单个变量
 * @param {string} flowId - 流程图ID
 * @param {string} key - 变量名
 * @returns {Promise<{message: string}>} - 操作结果
 */
export const deleteFlowVariable = async (flowId: string, key: string): Promise<{message: string}> => {
  console.log("删除变量:", flowId, key);
  try {
    const response = await apiClient.delete(`/flow-variables/${flowId}/variable/${key}`);
    return response.data;
  } catch (error) {
    console.error(`删除变量 ${key} 失败:`, error);
    throw error;
  }
};

/**
 * 重置流程图所有变量（删除所有变量）
 * @param {string} flowId - 流程图ID
 * @returns {Promise<{message: string}>} - 操作结果
 */
export const resetFlowVariables = async (flowId: string): Promise<{message: string}> => {
  console.log("重置所有变量:", flowId);
  try {
    const response = await apiClient.delete(`/flow-variables/${flowId}`);
    return response.data;
  } catch (error) {
    console.error("重置变量失败:", error);
    throw error;
  }
};

/**
 * 从JSON文件导入变量
 * @param {string} flowId - 流程图ID
 * @param {File} file - JSON文件
 * @returns {Promise<{message: string}>} - 操作结果
 */
export const importFlowVariablesFromFile = async (flowId: string, file: File): Promise<{message: string}> => {
  console.log("从文件导入变量:", flowId, file.name);
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await apiClient.post(`/flow-variables/${flowId}/import`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  } catch (error) {
    console.error("导入变量失败:", error);
    throw error;
  }
};

/**
 * 导出变量为JSON
 * @param {string} flowId - 流程图ID
 * @returns {Promise<{data: string}>} - 包含JSON字符串的对象
 */
export const exportFlowVariablesToJson = async (flowId: string): Promise<{data: string}> => {
  console.log("导出变量:", flowId);
  try {
    const response = await apiClient.get(`/flow-variables/${flowId}/export`);
    return response.data;
  } catch (error) {
    console.error("导出变量失败:", error);
    throw error;
  }
};

// 聊天相关API
export const chatApi = {
  // 创建新的聊天会话
  createChat: async (flowId: string, title?: string) => {
    // 获取当前日期时间并格式化
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0'); // 月份从 0 开始
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const formattedDateTime = `${year}${month}${day}-${hours}${minutes}${seconds}`;
    const defaultChatName = `chat-${formattedDateTime}`;

    const chatDataToSend = {
      flow_id: flowId,
      name: title || defaultChatName, // 使用生成的默认名称
      chat_data: {}
    };
    // 直接请求带尾部斜杠的路径
    const response = await apiClient.post(`/chats/`, chatDataToSend);
    return response.data;
  },

  // 获取特定聊天记录
  getChat: async (chatId: string) => {
    const response = await apiClient.get(`/chats/${chatId}`);
    return response.data;
  },

  // 获取流程图相关的所有聊天记录
  getFlowChats: async (flowId: string, skip: number = 0, limit: number = 10) => {
    const response = await apiClient.get(`/chats/flow/${flowId}`, {
      params: { skip, limit }
    });
    return response.data;
  },

  // 发送消息
  sendMessage: async (chatId: string, content: string, role: string = 'user') => {
    const response = await apiClient.post(`/chats/${chatId}/messages`, {
      content,
      role
    });
    return response.data;
  },

  // 更新聊天记录 (例如，重命名)
  // Define the expected structure for the update payload
  // Ideally, this would import a type from a shared schema definition
  updateChat: async (chatId: string, chatUpdate: { name?: string; chat_data?: any }) => {
    console.log(`API call: updateChat for chatId ${chatId} with data:`, chatUpdate);
    try {
      const response = await apiClient.put(`/chats/${chatId}`, chatUpdate);
      return response.data; // Assuming backend returns the updated chat object
    } catch (error: any) {
      console.error(`Error updating chat ${chatId}:`, error);
       if (error.response && error.response.status === 404) {
        throw new Error("聊天不存在，无法更新");
      } else if (error.response && error.response.status === 403) {
        throw new Error("没有权限更新此聊天");
      }
      throw error; // Re-throw other errors
    }
  },

  // 删除聊天记录
  deleteChat: async (chatId: string) => {
    const response = await apiClient.delete(`/chats/${chatId}`);
    return response.data;
  }
};

// 流程图相关API
export const flowApi = {
  // 获取流程图列表
  getFlows: async () => {
    const response = await axios.get(`${API_BASE_URL}/flows`);
    return response.data;
  },

  // 获取特定流程图
  getFlow: async (flowId: number) => {
    const response = await axios.get(`${API_BASE_URL}/flows/${flowId}`);
    return response.data;
  },

  // 创建新流程图
  createFlow: async (flowData: any) => {
    const response = await axios.post(`${API_BASE_URL}/flows`, flowData);
    return response.data;
  },

  // 更新流程图
  updateFlow: async (flowId: number, flowData: any) => {
    const response = await axios.put(`${API_BASE_URL}/flows/${flowId}`, flowData);
    return response.data;
  },

  // 删除流程图
  deleteFlow: async (flowId: number) => {
    const response = await axios.delete(`${API_BASE_URL}/flows/${flowId}`);
    return response.data;
  }
};

// 暴露apiClient实例（如果需要直接使用）
export { apiClient };