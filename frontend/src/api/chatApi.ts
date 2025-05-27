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

    const response: AxiosResponse<ChatResponse> = await apiClient.post('/langgraphchat/message', requestWithLanguage);
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
    const response: AxiosResponse<Array<any>> = await apiClient.get('/langgraphchat/conversations');
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
    const response: AxiosResponse<any> = await apiClient.delete(`/langgraphchat/conversations/${conversation_id}`);
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

  // 更新聊天记录 (例如，重命名)
  updateChat: async (chatId: string, updates: { name?: string; chat_data?: Record<string, any> }): Promise<Chat> => {
    const response = await apiClient.put<Chat>(`/chats/${chatId}`, updates);
    return response.data;
  },

  // 删除聊天记录
  deleteChat: async (chatId: string): Promise<boolean> => {
    // Assuming the backend returns a boolean or a 204 No Content for success
    await apiClient.delete(`/chats/${chatId}`);
    return true; // Or handle response more specifically if needed
  },

  // 编辑用户消息并截断后续消息, 然后触发 agent 响应流
  editUserMessage: (
    chatId: string,
    messageTimestamp: string,
    newContent: string,
    onEvent: OnChatEventCallback,
    onError: OnChatErrorCallback,
    onClose: OnChatCloseCallback
  ): (() => void) => {
    const editUrl = `${API_BASE_URL}/chats/${chatId}/messages/${messageTimestamp}`;
    const eventUrl = `${API_BASE_URL}/chats/${chatId}/events`;
    const requestBody = { new_content: newContent };
    let eventSource: EventSource | null = null;

    const startProcessingAndStreaming = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = {
          'Content-Type': 'application/json',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        console.log(`editUserMessage API: Triggering backend with PUT ${editUrl}`);
        const putResponse = await fetch(editUrl, {
          method: 'PUT',
          headers: headers,
          body: JSON.stringify(requestBody),
        });

        if (!putResponse.ok) { // Covers 2xx and other statuses like 4xx, 5xx
          let errorData: any = { message: `Edit PUT request failed! Status: ${putResponse.status}` };
          try {
            errorData = { ...errorData, ...(await putResponse.json()) }; // Try to parse error details
          } catch (e) { 
            errorData.details = await putResponse.text(); // Fallback to text if JSON parsing fails
          }
          console.error("editUserMessage API: Edit PUT request failed:", errorData);
          onError(new Error(errorData.detail || errorData.message));
          onClose(); // Ensure onClose is called to clean up UI state (e.g., isSending)
          return;
        }
        
        // 重要: 只有当后端返回 202 Accepted 时，我们才开始监听 SSE 事件
        // 其他成功状态 (例如 200 OK 如果后端直接返回了更新后的 Chat 对象且不触发 SSE) 需要不同的处理
        if (putResponse.status !== 202) { 
          console.warn(`editUserMessage API: Edit PUT returned status ${putResponse.status}, expected 202 if SSE is to follow. Handling as non-SSE success for now.`);
          // 如果不是202, 假设操作成功但没有SSE流，可以尝试解析响应体为 Chat 对象
          try {
            const updatedChat = await putResponse.json();
            // 调用一个特殊的事件来告诉UI更新，但这不是一个标准的SSE事件
            // 或者，让前端的 handleConfirmEditMessage 在这里直接调用 fetchChatMessages
            onEvent({ type: 'custom_edit_complete_no_sse', data: updatedChat } as any); 
          } catch (e) {
            console.error("editUserMessage API: Failed to parse response body after non-202 success: ", e);
            onError(new Error(`Edit succeeded with status ${putResponse.status} but response parsing failed.`));
          }
          onClose(); // Clean up UI
          return;
        }

        console.log(`editUserMessage API: Edit PUT successful (status ${putResponse.status}). Starting EventSource for subsequent agent response.`);

        // ---- Start EventSource listening (logic copied and adapted from sendMessage) ----
        eventSource = new EventSource(eventUrl); // Assumes withCredentials is not needed or handled by global fetch config

        eventSource.onopen = () => {
          console.log(`EventSource (for editUserMessage) connected to ${eventUrl}`);
        };

        eventSource.onerror = (error: Event) => {
          console.error('EventSource (for editUserMessage) failed:', error);
          if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            console.log("EventSource (for editUserMessage) closed by server, likely after stream_end.");
          } else {
             const err = new Error('EventSource (for editUserMessage) connection error.');
             (err as any).originalEvent = error;
             onError(err);
             closeEventSource(); 
          }
        };

        const addEventListener = <T extends ChatEvent>(eventType: T['type']) => {
          eventSource?.addEventListener(eventType, (event: MessageEvent) => {
            try {
              let parsedData: T['data'];
              if (eventType === 'token') {
                parsedData = event.data as T['data']; 
              } else {
                 try {
                   parsedData = JSON.parse(event.data) as T['data'];
                 } catch(parseError) {
                    console.error(`Error parsing JSON for event type ${eventType} (editUserMessage):`, event.data, parseError);
                    onError(new Error(`Failed to parse JSON data for ${eventType}: ${parseError}`));
                    return; 
                 }
              }
              // console.log(`Received event [${eventType}] (editUserMessage):`, parsedData); // Can be verbose
              onEvent({ type: eventType, data: parsedData } as T);
              if (eventType === 'stream_end') {
                console.log("Received stream_end event (editUserMessage). Closing connection.");
                closeEventSource();
              }
            } catch (e) {
              console.error(`Error processing SSE event ${eventType} (editUserMessage):`, event.data, e);
              onError(new Error(`Failed processing event ${eventType}: ${e}`));
            }
          });
        };

        // Register listeners
        addEventListener<TokenEvent>('token');
        addEventListener<ToolStartEvent>('tool_start');
        addEventListener<ToolEndEvent>('tool_end');
        addEventListener<StreamEndEvent>('stream_end');
        addEventListener<ErrorEvent>('error');
        addEventListener<PingEvent>('ping');
        // ---- End EventSource listening ----

      } catch (error: any) { // Catch errors from the fetch call itself or other synchronous parts
        console.error('editUserMessage API: Error during startProcessingAndStreaming:', error);
        onError(error instanceof Error ? error : new Error('Failed to initiate chat edit and stream: ' + String(error)));
        onClose(); // Ensure cleanup
      }
    };

    const closeEventSource = () => {
      if (eventSource) {
        console.log(`Closing EventSource connection to ${eventUrl} (from editUserMessage API utility)`);
        eventSource.close();
        eventSource = null;
        // onClose callback is critical for UI state management (e.g. setIsSending(false))
        // It should be called when the logical stream operation is considered complete or aborted.
        onClose(); 
      }
    };

    startProcessingAndStreaming();
    return closeEventSource; // Return the function that can be used to prematurely close the EventSource
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
  }
};
