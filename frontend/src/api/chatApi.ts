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

// --- 事件和回调类型定义 ---

// Renamed from LlmChunkEvent and updated data type
export interface TokenEvent {
  type: "token";
  data: string; // Backend sends the token string directly
}

// Removed FinalResultEvent as backend sends results via token stream and saves in finally block
// export interface FinalResultEvent { ... }

// New event for tool start
export interface ToolStartEvent {
    type: "tool_start";
    data: {
        name: string;
        input: any; // Input can be complex
    };
}

// New event for tool end
export interface ToolEndEvent {
    type: "tool_end";
    data: {
        name: string;
        output_summary: string; // Backend sends a summary string
    };
}

export interface StreamEndEvent {
  type: "stream_end";
  data: { message: string };
}

// Updated ErrorEvent to include stage from backend
export interface ErrorEvent {
  type: "error";
  data: {
      message: string;
      stage: string; // e.g., 'llm', 'tool', 'parsing', 'setup', 'agent', 'unknown'
      tool_name?: string; // Optional tool name if error occurred in a tool
     [key: string]: any // Allow other potential fields
  };
}

export interface PingEvent {
  type: "ping";
  data: {};
}

// Updated ChatEvent union type
export type ChatEvent = TokenEvent | ToolStartEvent | ToolEndEvent | StreamEndEvent | ErrorEvent | PingEvent;

export type OnChatEventCallback = (event: ChatEvent) => void;
export type OnChatErrorCallback = (error: Error) => void;
export type OnChatCloseCallback = () => void;

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

  // 发送消息 (Updated Event Listeners)
  sendMessage: (
    chatId: string,
    content: string,
    onEvent: OnChatEventCallback,
    onError: OnChatErrorCallback,
    onClose: OnChatCloseCallback,
    role: string = 'user'
  ): (() => void) => {
    const postUrl = `${API_BASE_URL}/chats/${chatId}/messages`;
    const eventUrl = `${API_BASE_URL}/chats/${chatId}/events`;
    const requestBody = { content, role };
    let eventSource: EventSource | null = null;

    const startStreaming = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = {
          'Content-Type': 'application/json',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        console.log(`sendMessage: Triggering backend with POST ${postUrl}`);
        const postResponse = await fetch(postUrl, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(requestBody),
        });

        if (!postResponse.ok) {
          let errorData: any = { message: `Trigger POST failed! Status: ${postResponse.status}` };
          try {
            errorData = { ...errorData, ...(await postResponse.json()) };
          } catch (e) {
            errorData.details = await postResponse.text();
          }
          console.error("sendMessage: Trigger POST failed:", errorData);
          onError(new Error(errorData.detail || errorData.message));
          onClose();
          return;
        }
        if (postResponse.status !== 202) {
          console.warn(`sendMessage: Trigger POST returned status ${postResponse.status}, expected 202.`);
        }
        console.log(`sendMessage: Trigger POST successful (status ${postResponse.status}). Starting EventSource.`);

        eventSource = new EventSource(eventUrl);

        eventSource.onopen = () => {
          console.log(`EventSource connected to ${eventUrl}`);
        };

        eventSource.onerror = (error: Event) => {
          console.error('EventSource failed:', error);
          // Check if the connection was closed by the server normally
          // (readyState === CLOSED and the error target is the eventSource)
          if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            console.log("EventSource closed by server, likely after stream_end.");
            // Don't treat this as a fatal error if the stream ended normally
            // onClose() will be called by the stream_end handler
            // If stream_end wasn't received, it might still be an error, 
            // but we avoid the JSON.parse error here.
          } else {
             // Otherwise, it's a real connection error
             const err = new Error('EventSource connection error.');
             (err as any).originalEvent = error;
             onError(err);
             closeEventSource(); // Close from client-side on real error
          }
        };

        const addEventListener = <T extends ChatEvent>(eventType: T['type']) => {
          eventSource?.addEventListener(eventType, (event: MessageEvent) => {
            try {
              // Data parsing logic needs refinement based on backend changes
              let parsedData: T['data'];
              
              // If the event is 'token', data is already a string (no double encoding)
              if (eventType === 'token') {
                parsedData = event.data as T['data'];
              } else {
                 // For other events (tool_start, tool_end, error, stream_end), 
                 // backend now sends JSON string
                 try {
                   parsedData = JSON.parse(event.data) as T['data'];
                 } catch(parseError) {
                    console.error(`Error parsing JSON for event type ${eventType}:`, event.data, parseError);
                    // Handle specific parsing error without closing the connection immediately
                    onError(new Error(`Failed to parse JSON data for ${eventType}: ${parseError}`));
                    return; // Stop processing this malformed event
                 }
              }

              console.log(`Received event [${eventType}]:`, parsedData);
              onEvent({ type: eventType, data: parsedData } as T);

              // Close the connection specifically when stream_end is received
              if (eventType === 'stream_end') {
                console.log("Received stream_end event. Closing connection.");
                closeEventSource();
              }
            } catch (e) {
              // Catch potential errors in onEvent callback itself or other logic
              console.error(`Error processing SSE event ${eventType}:`, event.data, e);
              onError(new Error(`Failed processing event ${eventType}: ${e}`));
              // Consider if closing is needed here based on the error type
            }
          });
        };

        // Register listeners for expected event types
        addEventListener<TokenEvent>('token');
        addEventListener<ToolStartEvent>('tool_start');
        addEventListener<ToolEndEvent>('tool_end');
        addEventListener<StreamEndEvent>('stream_end'); // Listener for explicit end
        addEventListener<ErrorEvent>('error'); // Listener for backend-sent errors
        // addEventListener<PingEvent>('ping'); // Optional: if backend sends pings

        // No need for a generic 'message' listener if all types are specific
        // eventSource.onmessage = (event) => { ... }

      } catch (error: any) {
        console.error('Error starting chat stream:', error);
        onError(error instanceof Error ? error : new Error('Failed to start chat stream: ' + String(error)));
        onClose();
      }
    };

    const closeEventSource = () => {
      if (eventSource) {
        console.log(`Closing EventSource connection to ${eventUrl}`);
        eventSource.close();
        eventSource = null;
        onClose(); // Notify the UI component that the connection is closed
      }
    };

    startStreaming();

    return closeEventSource;
  },

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
