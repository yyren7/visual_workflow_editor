import { AxiosResponse } from 'axios';
import { apiClient } from './apiClient';

// --- 数据接口定义 ---
export interface ChatRequest {
    message: string;
    conversation_id?: string;
    metadata?: Record<string, any>;
    language?: string; // 添加语言参数
}

export interface ChatResponse {
    conversation_id: string;
    message: string;
    created_at: string;
    metadata?: Record<string, any>;
    context_used?: boolean;
}

export interface Chat {
    id: string;
    flow_id: string;
    user_id: string;
    name: string;
    chat_data: { messages?: any[] }; // 根据实际结构调整
    created_at: string;
    updated_at: string;
}

export interface Message {
    role: string;
    content: string;
    timestamp: string;
}

// --- Chat 相关函数 ---

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

// --- chatApi 对象 (包含与普通聊天记录相关的操作) ---
export const chatApi = {
  // 创建新的聊天会话
  createChat: async (flowId: string, title?: string): Promise<Chat> => {
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
  getChat: async (chatId: string): Promise<Chat> => {
    const response = await apiClient.get(`/chats/${chatId}`);
    return response.data;
  },

  // 获取流程图相关的所有聊天记录
  getFlowChats: async (flowId: string, skip: number = 0, limit: number = 10): Promise<Chat[]> => {
    const response = await apiClient.get(`/chats/flow/${flowId}`, {
      params: { skip, limit }
    });
    return response.data;
  },

  // 发送消息
  sendMessage: async (chatId: string, content: string, role: string = 'user'): Promise<Chat> => {
    const response = await apiClient.post(`/chats/${chatId}/messages`, {
      content,
      role
    });
    return response.data;
  },

  // 更新聊天记录 (例如，重命名)
  updateChat: async (chatId: string, chatUpdate: { name?: string; chat_data?: any }): Promise<Chat> => {
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
  deleteChat: async (chatId: string): Promise<{message: string}> => {
    const response = await apiClient.delete(`/chats/${chatId}`);
    return response.data;
  }
}; 