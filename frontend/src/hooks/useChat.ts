import { useState, useCallback } from 'react';
import { updateLangGraphState } from '../api/sasApi';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ChatState {
  [chatId: string]: {
    messages: ChatMessage[];
    loading: boolean;
    error: string | null;
  };
}

export const useChat = () => {
  const [chats, setChats] = useState<ChatState>({});

  const sendMessage = useCallback(async (chatId: string, content: string) => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      throw new Error('Not authenticated');
    }

    // Update local state to show loading
    setChats(prev => ({
      ...prev,
      [chatId]: {
        ...prev[chatId],
        loading: true,
        error: null,
      }
    }));

    try {
      // For LangGraph nodes, use the new API
      if (chatId.includes('_task_') || chatId.includes('_detail_') || !chatId.includes('-')) {
        // This is a LangGraph chat ID (flow_id or flow_id_task_X or flow_id_task_X_detail_Y)
        const result = await updateLangGraphState(chatId, {
          action: 'update_input',
          content: content
        });
        
        // Update local state with success
        setChats(prev => ({
          ...prev,
          [chatId]: {
            messages: [...(prev[chatId]?.messages || []), {
              role: 'user',
              content: content,
              timestamp: new Date().toISOString()
            }],
            loading: false,
            error: null,
          }
        }));
        
        return result;
      }
      
      // For regular chats, use the existing API
      const response = await fetch(`/api/chats/${chatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ content, role: 'user' }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const result = await response.json();
      
      // Update local state with the response
      setChats(prev => ({
        ...prev,
        [chatId]: {
          messages: result.messages || [],
          loading: false,
          error: null,
        }
      }));

      return result;
    } catch (error) {
      setChats(prev => ({
        ...prev,
        [chatId]: {
          ...prev[chatId],
          loading: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        }
      }));
      throw error;
    }
  }, []);

  const getChat = useCallback((chatId: string) => {
    return chats[chatId] || {
      messages: [],
      loading: false,
      error: null,
    };
  }, [chats]);

  return {
    sendMessage,
    getChat,
    chats,
  };
}; 