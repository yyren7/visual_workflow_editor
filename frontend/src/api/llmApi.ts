import { AxiosResponse } from 'axios';
import { apiClient } from './apiClient';

// --- 数据接口定义 ---
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

export interface WorkflowProcessRequest {
    prompt: string;
    session_id?: string;  // 会话ID，可选
    language?: string; // 添加语言参数
}

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

// --- LLM & Workflow 相关函数 ---

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