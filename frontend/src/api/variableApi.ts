import { apiClient } from './apiClient';

// --- 数据接口定义 ---
export interface FlowVariables {
  [key: string]: string;
}

// --- Flow Variables 相关函数 ---

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