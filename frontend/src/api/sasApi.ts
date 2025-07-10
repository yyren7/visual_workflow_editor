import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// 获取认证令牌
const getAuthToken = () => {
  return localStorage.getItem('access_token');
};

// 创建带认证的请求头
const getAuthHeaders = () => {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    'Authorization': token ? `Bearer ${token}` : '',
  };
};

/**
 * 更新SAS状态
 */
export const updateSASState = async (chatId: string, stateUpdate: any) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/sas/${chatId}/update-state`,
      stateUpdate,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to update SAS state:', error);
    throw error;
  }
};

/**
 * 获取SAS状态
 */
export const getSASState = async (flowId: string) => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/sas/${flowId}/state`,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to get SAS state:', error);
    throw error;
  }
};

/**
 * 初始化SAS处理
 */
export const initializeSASProcessing = async (flowId: string) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/sas/${flowId}/messages`,
      { "input": "" },
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to initialize SAS processing:', error);
    throw error;
  }
};

// 为了向后兼容，保留旧的函数名作为别名
export const updateLangGraphState = updateSASState;
export const getLangGraphState = getSASState;
export const initializeLangGraphNodes = initializeSASProcessing; 