import { useCallback, useRef, useEffect } from 'react';

interface SSEConnection {
  eventSource: EventSource | null;
  chatId: string | null;
  cleanup: (() => void) | null;
}

// 全局SSE连接管理器，确保同一时间只有一个连接
class SSEConnectionManager {
  private static instance: SSEConnectionManager;
  private activeConnections: Map<string, EventSource> = new Map();
  private cleanupTimers: Map<string, NodeJS.Timeout> = new Map();
  private connectionPromises: Map<string, Promise<EventSource>> = new Map();

  static getInstance(): SSEConnectionManager {
    if (!SSEConnectionManager.instance) {
      SSEConnectionManager.instance = new SSEConnectionManager();
    }
    return SSEConnectionManager.instance;
  }

  createConnection(
    chatId: string, 
    onEvent: (event: any) => void,
    onError: (error: Error) => void,
    onClose: () => void
  ): () => void {
    // 如果已经有连接，直接返回清理函数
    if (this.activeConnections.has(chatId)) {
      console.warn('SSEManager: Connection already exists for chat:', chatId, '- returning existing cleanup function');
      return () => this.closeConnection(chatId);
    }

    console.log('SSEManager: Creating new connection for chat:', chatId);

    const eventSource = new EventSource(
      `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/chats/${chatId}/events`
    );

    // 保存连接引用
    this.activeConnections.set(chatId, eventSource);

    // 设置事件监听器
    eventSource.onopen = () => {
      console.log('SSEManager: Connection opened for chat:', chatId);
    };

    eventSource.addEventListener('token', (event) => {
      onEvent({ type: 'token', data: event.data });
    });

    eventSource.addEventListener('tool_start', (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent({ type: 'tool_start', data });
      } catch (e) {
        console.error('SSEManager: Error parsing tool_start data:', e);
      }
    });

    eventSource.addEventListener('tool_end', (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent({ type: 'tool_end', data });
      } catch (e) {
        console.error('SSEManager: Error parsing tool_end data:', e);
      }
    });

    eventSource.addEventListener('stream_end', (event) => {
      console.log('SSEManager: Stream ended for chat:', chatId);
      try {
        const data = JSON.parse(event.data);
        onEvent({ type: 'stream_end', data });
      } catch (e) {
        console.error('SSEManager: Error parsing stream_end data:', e);
      }
      
      // 立即强制关闭连接，确保后端能检测到断开
      console.log('SSEManager: Force closing connection immediately after stream_end');
      this.closeConnection(chatId);
      onClose();
    });

    eventSource.addEventListener('error', (event) => {
      try {
        const data = JSON.parse((event as any).data);
        onEvent({ type: 'error', data });
      } catch (e) {
        console.error('SSEManager: Error parsing error event data:', e);
      }
    });

    eventSource.onerror = (error) => {
      console.error('SSEManager: Connection error for chat:', chatId, error);
      
      if (eventSource.readyState === EventSource.CLOSED) {
        this.closeConnection(chatId);
        onError(new Error(`SSE connection closed for chat ${chatId}`));
      }
    };

    // 设置自动清理定时器（5分钟）
    const cleanupTimer = setTimeout(() => {
      console.log('SSEManager: Auto-cleanup connection for chat:', chatId);
      this.closeConnection(chatId);
      onClose();
    }, 5 * 60 * 1000);

    this.cleanupTimers.set(chatId, cleanupTimer);

    // 返回手动关闭函数
    return () => this.closeConnection(chatId);
  }

  closeConnection(chatId: string): void {
    const eventSource = this.activeConnections.get(chatId);
    if (eventSource) {
      console.log('SSEManager: Closing connection for chat:', chatId);
      console.log('SSEManager: Active connections before close:', Array.from(this.activeConnections.keys()));
      eventSource.close();
      this.activeConnections.delete(chatId);
      console.log('SSEManager: Active connections after close:', Array.from(this.activeConnections.keys()));
    }

    // 清理定时器
    const timer = this.cleanupTimers.get(chatId);
    if (timer) {
      clearTimeout(timer);
      this.cleanupTimers.delete(chatId);
    }
    
    // 清理 promise
    this.connectionPromises.delete(chatId);
  }

  closeAllConnections(): void {
    console.log('SSEManager: Closing all connections, count:', this.activeConnections.size);
    const chatIds = Array.from(this.activeConnections.keys());
    chatIds.forEach(chatId => {
      this.closeConnection(chatId);
    });
    
    // 清理所有定时器
    this.cleanupTimers.forEach((timer) => {
      clearTimeout(timer);
    });
    this.cleanupTimers.clear();
    
    // 清理所有promises
    this.connectionPromises.clear();
    
    console.log('SSEManager: All connections closed');
  }

  hasActiveConnection(chatId: string): boolean {
    return this.activeConnections.has(chatId);
  }
}

export const useSSEManager = () => {
  const managerRef = useRef<SSEConnectionManager>(SSEConnectionManager.getInstance());

  const createConnection = useCallback((
    chatId: string,
    onEvent: (event: any) => void,
    onError: (error: Error) => void = () => {},
    onClose: () => void = () => {}
  ) => {
    return managerRef.current.createConnection(chatId, onEvent, onError, onClose);
  }, []);

  const closeConnection = useCallback((chatId: string) => {
    managerRef.current.closeConnection(chatId);
  }, []);

  const hasActiveConnection = useCallback((chatId: string) => {
    return managerRef.current.hasActiveConnection(chatId);
  }, []);

  // 组件卸载时清理所有连接
  useEffect(() => {
    return () => {
      managerRef.current.closeAllConnections();
    };
  }, []);

  return {
    createConnection,
    closeConnection,
    hasActiveConnection
  };
}; 