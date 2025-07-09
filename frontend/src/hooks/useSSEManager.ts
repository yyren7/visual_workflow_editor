import { useCallback, useRef, useEffect } from 'react';
import { fetchEventSource, EventSourceMessage } from '@sentool/fetch-event-source';
import { useAuth } from '../contexts/AuthContext';

// 临时的占位类型
export type SSEState = 'CONNECTING' | 'OPEN' | 'CLOSED' | 'ERROR';

// 全局SSE连接管理器
class SSEConnectionManager {
  private static instance: SSEConnectionManager;
  private activeConnections: Map<string, AbortController> = new Map();
  private subscribers: Map<string, Map<string, Set<(data: any) => void>>> = new Map();
  private cleanupTimers: Map<string, NodeJS.Timeout> = new Map();
  // private connectionPromises: Map<string, Promise<EventSource>> = new Map(); // Potentially useful for concurrent subscriptions to the same new connection, but adds complexity. Let's omit for now.

  static getInstance(): SSEConnectionManager {
    if (!SSEConnectionManager.instance) {
      SSEConnectionManager.instance = new SSEConnectionManager();
    }
    return SSEConnectionManager.instance;
  }

  private dispatchEvent(chatId: string, eventType: string, data: any): void {
    const eventSubscribers = this.subscribers.get(chatId)?.get(eventType);
    if (eventSubscribers) {
      eventSubscribers.forEach(callback => {
        try {
          callback(data);
        } catch (e) {
          console.error('SSEManager: Error in subscriber callback', e);
        }
      });
    }
  }

  private _ensureConnection(chatId: string): void {
    if (this.activeConnections.has(chatId)) {
      // 如果已有活动的Controller，直接返回
      return;
    }

    const apiUrl = `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/sas/${chatId}/events`;
    console.log(`[SSE_MANAGER_LOG] _ensureConnection: Creating new fetchEventSource for chat: ${chatId}, URL: ${apiUrl}`);
    
    // 为每个连接创建一个AbortController，以便我们可以手动关闭它
    const controller = new AbortController();
    this.activeConnections.set(chatId, controller);
    
    fetchEventSource(apiUrl, {
      signal: controller.signal,
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        'Accept': 'text/event-stream',
      },
      
      onopen: async (response: any) => {
        if (response.ok) {
          console.log('[SSE_MANAGER_LOG] Connection opened for chat:', chatId);
          this.dispatchEvent(chatId, 'open', { chatId });
        } else {
          console.error(`[SSE_MANAGER_LOG] Failed to open SSE connection for chat ${chatId}. Status: ${response.status}`, await response.text());
          this.dispatchEvent(chatId, 'connection_error', { chatId, error: new Error(`HTTP ${response.status}`) });
          this.closeConnection(chatId); // 连接失败时立即清理
        }
      },

      onmessage: (event: EventSourceMessage) => {
        const eventType = event.event;
        console.log(`[SSE_MANAGER_DEBUG] Raw SSE event received for chat ${chatId}:`, {
          event: eventType,
          data: event.data,
          id: event.id,
          retry: event.retry
        });
        
        if (!eventType || eventType === 'message') {
          // 忽略未命名事件或标准 'message' 事件，因为我们的应用需要特定的事件类型
          console.log(`[SSE_MANAGER_DEBUG] Ignoring unnamed or 'message' event for chat ${chatId}. EventType: '${eventType}'`);
          return;
        }

        let parsedData: any;
        try {
          // 检查数据是否已经是对象，或者是否为JSON字符串
          if (typeof event.data === 'string') {
            parsedData = JSON.parse(event.data);
          } else {
            // 如果不是字符串，假设它已经是我们需要的对象
            parsedData = event.data;
          }
          console.log(`[SSE_MANAGER_DEBUG] Successfully parsed event data for '${eventType}' on chat ${chatId}:`, parsedData);
        } catch (e) {
          console.warn(`SSEManager: Data for event '${eventType}' on chat ${chatId} is not valid JSON and could not be used directly. Raw data:`, event.data, "Error:", e);
          // 如果解析失败，我们可以选择分发原始数据或忽略
          // 为了与现有逻辑保持一致，我们选择忽略
          return;
        }
        
        // 直接使用从 SSE 事件中获取的 eventType 和解析后的数据进行分发
        console.log(`[SSE_MANAGER_DEBUG] Dispatching event: '${eventType}' for chat: ${chatId}`, parsedData);
        this.dispatchEvent(chatId, eventType, parsedData);
      },
      
      onclose: () => {
        // 这个回调在连接正常关闭时（被服务器或客户端中止）触发
        console.log(`[SSE_MANAGER_LOG] Connection closed for chat: ${chatId}. This is expected on stream end or manual closure.`);
        // 不需要在这里调用 this.closeConnection(chatId)，因为它会被外部逻辑（如 stream_end 事件或组件卸载）调用
        // 避免循环调用
      },

      onerror: (error: any) => {
        console.error(`[SSE_MANAGER_LOG] Connection error for chat: ${chatId}`, error);
        this.dispatchEvent(chatId, 'connection_error', { chatId, error });
        this.closeConnection(chatId); // 发生不可恢复的错误时，关闭并清理
      }
    });

    // 清理逻辑现在由 closeConnection 方法中的 controller.abort() 处理
  }

  subscribe(
    chatId: string,
    eventType: string,
    callback: (data: any) => void
  ): () => void {
    console.log(`[SSE_MANAGER_LOG] subscribe called for chat: ${chatId}, eventType: ${eventType}`);
    this._ensureConnection(chatId);

    if (!this.subscribers.has(chatId)) {
      this.subscribers.set(chatId, new Map());
    }
    const chatEventSubscribers = this.subscribers.get(chatId)!;

    if (!chatEventSubscribers.has(eventType)) {
      chatEventSubscribers.set(eventType, new Set());
    }
    const callbackSet = chatEventSubscribers.get(eventType)!;
    callbackSet.add(callback);

    console.log(`SSEManager: Subscribed to [${eventType}] for chat [${chatId}]. Total subscribers for this event: ${callbackSet.size}`);

    return () => {
      const currentChatEventSubscribers = this.subscribers.get(chatId);
      if (currentChatEventSubscribers) {
        const currentCallbackSet = currentChatEventSubscribers.get(eventType);
        if (currentCallbackSet) {
          currentCallbackSet.delete(callback);
          console.log(`SSEManager: Unsubscribed from [${eventType}] for chat [${chatId}]. Remaining for this event: ${currentCallbackSet.size}`);
          if (currentCallbackSet.size === 0) {
            currentChatEventSubscribers.delete(eventType);
            console.log(`SSEManager: No more subscribers for [${eventType}] on chat [${chatId}].`);
          }
        }
        // Check if there are any subscribers left for this chat ID at all
        let totalSubscribersForChat = 0;
        currentChatEventSubscribers.forEach(set => totalSubscribersForChat += set.size);
        
        if (totalSubscribersForChat === 0) {
          console.log(`SSEManager: No more subscribers for any event on chat [${chatId}]. Closing connection.`);
          this.closeConnection(chatId); // Close if no subscribers left for this chat at all
        }
      }
    };
  }

  closeConnection(chatId: string): void {
    console.log(`[SSE_MANAGER_LOG] closeConnection called for chat: ${chatId}`);
    const controller = this.activeConnections.get(chatId);
    if (controller) {
      console.log('[SSE_MANAGER_LOG] Aborting fetchEventSource connection for chat:', chatId);
      controller.abort(); // 中止 fetch 请求，这将触发 onclose 回调
      this.activeConnections.delete(chatId);
      this.dispatchEvent(chatId, 'close', { chatId }); // Dispatch a 'close' event
    }
    
    // 清理订阅者
    this.subscribers.delete(chatId);
    console.log('SSEManager: Cleared subscribers for chat:', chatId);
  }

  closeAllConnections(): void {
    console.log('SSEManager: Closing all connections, count:', this.activeConnections.size);
    const chatIds = Array.from(this.activeConnections.keys());
    chatIds.forEach(chatId => {
      this.closeConnection(chatId);
    });
  }

  hasActiveConnection(chatId: string): boolean {
    return this.activeConnections.has(chatId);
  }
}

export const useSSEManager = () => {
  const managerRef = useRef<SSEConnectionManager>(SSEConnectionManager.getInstance());

  // useEffect to ensure closeAllConnections is called on hook unmount (e.g. app closes)
  // This is a bit broad, usually cleanup is tied to component lifecycle that uses the hook.
  // If the manager is a true singleton, this might close connections unexpectedly if another part of the app still uses it.
  // For a true singleton app-wide manager, explicit close or per-chat close via unsubscribe is better.
  // Let's keep it for now but with a comment.
  useEffect(() => {
    const manager = managerRef.current; // Capture manager instance
    return () => {
      // This will close ALL connections when a component *using* this hook unmounts.
      // This might not be desired if the manager is meant to persist connections across component lifecycles.
      // Consider if closeAllConnections here is appropriate or if cleanup should be more granular.
      // manager.closeAllConnections(); 
      // console.log("useSSEManager: Hook unmounted. Called closeAllConnections - review if this is intended behavior.");
    };
  }, []); // Empty dependency means this runs once on mount and cleanup on unmount of the component that *first* uses the hook.


  const subscribe = useCallback((
    chatId: string,
    eventType: string,
    callback: (data: any) => void
  ): (() => void) => {
    return managerRef.current.subscribe(chatId, eventType, callback);
  }, []);

  const closeConnection = useCallback((chatId: string) => {
    managerRef.current.closeConnection(chatId);
  }, []);

  const hasActiveConnection = useCallback((chatId: string) => {
    return managerRef.current.hasActiveConnection(chatId);
  }, []);

  return {
    subscribe,
    closeConnection,
    hasActiveConnection,
    // Expose closeAllConnections if manual global cleanup is needed, e.g. on user logout
    // closeAllConnections: () => managerRef.current.closeAllConnections() 
  };
}; 