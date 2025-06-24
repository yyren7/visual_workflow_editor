import { useCallback, useRef, useEffect } from 'react';

// 全局SSE连接管理器
class SSEConnectionManager {
  private static instance: SSEConnectionManager;
  private activeConnections: Map<string, EventSource> = new Map();
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

  private _ensureConnection(chatId: string): EventSource {
    if (this.activeConnections.has(chatId)) {
      return this.activeConnections.get(chatId)!;
    }

    console.log('SSEManager: Creating new EventSource for chat:', chatId);
    const eventSource = new EventSource(
      `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${chatId}/events`
    );
    this.activeConnections.set(chatId, eventSource);

    eventSource.onopen = () => {
      console.log('SSEManager: Connection opened for chat:', chatId);
      this.dispatchEvent(chatId, 'open', { chatId }); // Dispatch an 'open' event
    };

    const genericEventListener = (eventType: string) => (event: MessageEvent) => {
      let parsedData: any = event.data;
      try {
        // Attempt to parse if data looks like JSON
        if (typeof event.data === 'string' && (event.data.startsWith('{') || event.data.startsWith('['))) {
          parsedData = JSON.parse(event.data);
        }
      } catch (e) {
        console.warn(`SSEManager: Data for event type '${eventType}' for chat ${chatId} is not valid JSON, using raw data. Error:`, e);
        // parsedData remains event.data
      }
      this.dispatchEvent(chatId, eventType, parsedData);

      // REMOVED: Do not automatically close connection on stream_end here.
      // The connection should close if all subscribers are gone, or if explicitly closed.
      // if (eventType === 'stream_end') {
      //   console.log('SSEManager: Stream ended by event for chat:', chatId, '. Closing connection.');
      //   this.closeConnection(chatId); 
      // }
    };

    // Standard event types from your previous implementation
    eventSource.addEventListener('token', genericEventListener('token'));
    eventSource.addEventListener('tool_start', genericEventListener('tool_start'));
    eventSource.addEventListener('tool_end', genericEventListener('tool_end'));
    eventSource.addEventListener('stream_end', genericEventListener('stream_end'));
    // Add listener for 'agent_state_updated' and any other custom server events
    eventSource.addEventListener('agent_state_updated', genericEventListener('agent_state_updated'));
    // Generic error event from SSE standard
    eventSource.addEventListener('error', (event: MessageEvent) => { // This is for server-sent named 'error' events
        console.error('SSEManager: Received server-sent "error" event for chat:', chatId, event.data);
        let parsedErrorData: any = event.data;
        try {
            if (typeof event.data === 'string') {
                parsedErrorData = JSON.parse(event.data);
            }
        } catch (e) {
            // use raw data if not parsable
        }
        this.dispatchEvent(chatId, 'server_error_event', parsedErrorData); // Distinguish from connection error
    });


    eventSource.onerror = (error) => { // This is for connection errors
      console.error('SSEManager: Connection error for chat:', chatId, error);
      this.dispatchEvent(chatId, 'connection_error', { chatId, error });
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('SSEManager: Connection error led to CLOSED state for chat:', chatId, '. Cleaning up.');
        this.closeConnection(chatId); // Ensure cleanup if error leads to closed state
      }
    };

    // Clear any existing timer before setting a new one
    const existingTimer = this.cleanupTimers.get(chatId);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }
    const cleanupTimer = setTimeout(() => {
      console.log('SSEManager: Auto-cleanup connection for chat (timeout):', chatId);
      this.closeConnection(chatId);
    }, 5 * 60 * 1000); // 5 minutes
    this.cleanupTimers.set(chatId, cleanupTimer);

    return eventSource;
  }

  subscribe(
    chatId: string,
    eventType: string,
    callback: (data: any) => void
  ): () => void {
    this._ensureConnection(chatId); // Ensure connection exists or is created

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
    const eventSource = this.activeConnections.get(chatId);
    if (eventSource) {
      console.log('SSEManager: Closing connection for chat:', chatId);
      eventSource.close();
      this.activeConnections.delete(chatId);
      this.dispatchEvent(chatId, 'close', { chatId }); // Dispatch a 'close' event
    }

    const timer = this.cleanupTimers.get(chatId);
    if (timer) {
      clearTimeout(timer);
      this.cleanupTimers.delete(chatId);
    }
    
    // Clear subscribers for this chat ID
    this.subscribers.delete(chatId);
    console.log('SSEManager: Cleared subscribers for chat:', chatId);
  }

  closeAllConnections(): void {
    console.log('SSEManager: Closing all connections, count:', this.activeConnections.size);
    const chatIds = Array.from(this.activeConnections.keys());
    chatIds.forEach(chatId => {
      this.closeConnection(chatId); // This will also clear subscribers
    });
    // Timers are cleared within closeConnection
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