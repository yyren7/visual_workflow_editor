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
 * 更新LangGraph状态
 */
export const updateLangGraphState = async (chatId: string, stateUpdate: any) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/langgraph-chats/${chatId}/update-state`,
      stateUpdate,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to update LangGraph state:', error);
    throw error;
  }
};

/**
 * 获取LangGraph状态
 */
export const getLangGraphState = async (flowId: string) => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/langgraph-chats/${flowId}/state`,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to get LangGraph state:', error);
    throw error;
  }
};

/**
 * 初始化LangGraph节点
 */
export const initializeLangGraphNodes = async (flowId: string) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/langgraph-chats/${flowId}/initialize-langgraph`,
      {},
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to initialize LangGraph nodes:', error);
    throw error;
  }
}; 