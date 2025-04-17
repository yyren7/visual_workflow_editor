import { AxiosResponse } from 'axios'; // Re-enable import
import { apiClient, API_BASE_URL } from './apiClient'; // Import API_BASE_URL
// Remove the non-existent import
// import { getAuthToken } from '../utils/auth'; 

// Import types from the central types file
import { Chat } from '../types';

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

// Interface for the non-streaming JSON response (based on WorkflowChainOutput)
export interface JsonChatResponse {
  nodes?: Array<Record<string, any>> | null;
  connections?: Array<Record<string, any>> | null;
  summary?: string;
  error?: string | null;
  tool_calls_info?: Array<Record<string, any>> | null;
  tool_results_info?: Array<Record<string, any>> | null;
}

// Interface for the streaming response - now holds the stream directly
export interface StreamedChatResponse {
  stream: ReadableStream<Uint8Array>; 
}

// Type guard to check the response type
export function isStreamedResponse(response: any): response is StreamedChatResponse {
  // Check if the response object itself has a 'stream' property of the correct type
  return response && response.stream instanceof ReadableStream;
}

export function isJsonResponse(response: any): response is JsonChatResponse {
  return response && typeof response.stream === 'undefined';
}

// Combined type for the sendMessage return value
export type SendMessageResponse = StreamedChatResponse | JsonChatResponse;

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
    const now = new Date();
    const formattedDateTime = now.toISOString().replace(/[:.]/g, '-');
    const defaultChatName = `chat-${formattedDateTime}`;
    const chatDataToSend = {
      flow_id: flowId,
      name: title || defaultChatName,
      chat_data: { messages: [] } // Ensure messages array uses imported Message type if needed by backend
    };
    // Use the imported Chat type for the response expectation
    const response = await apiClient.post<Chat>(`/chats/`, chatDataToSend);
    return response.data;
  },

  // 获取特定聊天记录
  getChat: async (chatId: string): Promise<Chat> => {
    const response = await apiClient.get<Chat>(`/chats/${chatId}`);
    return response.data;
  },

  // 获取流程图相关的所有聊天记录
  getFlowChats: async (flowId: string, skip: number = 0, limit: number = 100): Promise<Chat[]> => {
    const response = await apiClient.get<Chat[]>(`/chats/flow/${flowId}`, {
      params: { skip, limit }
    });
    return response.data;
  },

  // 发送消息
  sendMessage: async (
    chatId: string,
    content: string,
    role: string = 'user'
  ): Promise<SendMessageResponse> => {
    // Revert to using fetch for this specific endpoint to handle ReadableStream correctly in the browser.
    // Axios with responseType: 'stream' doesn't work reliably in browsers.
    const url = `${API_BASE_URL}/chats/${chatId}/messages`; // Use full URL for fetch
    const requestBody = { content, role };

    // --- Manually retrieve token (using the correct key) --- 
    const token = localStorage.getItem('access_token');
    // Note: No console warning here if token is missing, 
    // rely on backend to potentially reject or handle unauthenticated requests.
    
    console.log(`sendMessage: POST ${url} using fetch API`);
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      // --- Manually add Authorization header --- 
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        // --- Manual error handling for fetch --- 
        let errorData: any = { message: `HTTP error! status: ${response.status}` };
        // Special handling for 401 Unauthorized (needed again for fetch)
        if (response.status === 401) {
             errorData.message = "认证失败或令牌无效，请重新登录。";
             // Optionally clear token and trigger logout/redirect like the interceptor does
             localStorage.removeItem('access_token');
             window.dispatchEvent(new Event('loginChange')); 
        }
        try {
          const errorJson = await response.json(); // Try to get error details from body
          errorData = { ...errorData, ...errorJson };
        } catch (e) {
          // If body is not JSON or empty
          const errorText = await response.text();
          errorData.details = errorText.substring(0, 200); 
        }
        console.error("sendMessage fetch error response:", errorData);
        const error = new Error(errorData.detail || errorData.message);
        (error as any).response = errorData; // Attach details if needed
        throw error;
      }

      // --- Handle response based on Content-Type --- 
      const contentType = response.headers.get('content-type');
      console.log("sendMessage response contentType:", contentType);

      if (contentType && contentType.includes('text/plain')) {
         if (!response.body) {
             throw new Error('Streaming response has no body');
         }
         console.log("sendMessage: Detected text/plain, returning stream from fetch response.body.");
         // Return the ReadableStream from fetch
         return { stream: response.body }; 
      } else if (contentType && contentType.includes('application/json')) {
         console.log("sendMessage: Detected application/json, parsing JSON.");
         const jsonData: JsonChatResponse = await response.json();
         console.log("sendMessage: Parsed JSON response:", jsonData);
         return jsonData;
      } else {
         console.warn(`sendMessage: Unexpected content type: ${contentType}. Attempting to read as text.`);
         const fallbackText = await response.text();
         // Return as JSON response with summary and error indication
         return { summary: fallbackText.substring(0, 500), error: `Unexpected content type: ${contentType}` };
      }

    } catch (error: any) {
       // Catch fetch-specific errors (e.g., network issues) or re-throw errors from response handling
       console.error("Error in sendMessage fetch API call:", error);
       // Ensure the error is an Error object
       throw error instanceof Error ? error : new Error('Failed to send message: ' + String(error));
    }
  },

  // --- Keep updateChat and deleteChat as they were --- 
  updateChat: async (chatId: string, chatUpdate: { name?: string; chat_data?: any }): Promise<Chat> => {
    console.log(`API call: updateChat for chatId ${chatId} with data:`, chatUpdate);
    try {
      const response = await apiClient.put<Chat>(`/chats/${chatId}`, chatUpdate);
      return response.data;
    } catch (error: any) {
      console.error(`Error updating chat ${chatId}:`, error);
      if (error.response && error.response.status === 404) {
        throw new Error("聊天不存在，无法更新");
      } else if (error.response && error.response.status === 403) {
        throw new Error("没有权限更新此聊天");
      }
      throw error;
    }
  },

  deleteChat: async (chatId: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/chats/${chatId}`);
    return response.data;
  }
};
