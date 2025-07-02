import { useState, useCallback } from 'react';
import { chatApi } from '../../api/chatApi';
import { getLastChatIdForFlow } from '../../api/flowApi';
import { DisplayMessage } from './types';

export const useChatData = () => {
  const [chatList, setChatList] = useState<any[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Function to fetch chat list for the current flow
  const fetchChatList = useCallback(async (currentFlowId: string) => {
    setIsLoadingList(true);
    setError(null);
    try {
      console.log("Fetching chat list for flow:", currentFlowId);
      const fetchedChats = await chatApi.getFlowChats(currentFlowId, 0, 100);
      setChatList(fetchedChats || []);
      console.log("Chat list fetched:", fetchedChats);
      return fetchedChats || [];
    } catch (err: any) {
      console.error('Failed to load chat list:', err);
      setError(`加载聊天列表失败: ${err.message}`);
      setChatList([]);
      return [];
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  // Function to fetch messages for a specific chat ID
  const fetchChatMessages = useCallback(async (chatIdToLoad: string) => {
    if (!chatIdToLoad) {
      setMessages([]);
      setIsLoadingChat(false);
      return;
    }
    setIsLoadingChat(true);
    setError(null);
    try {
      console.log("Fetching messages for chat:", chatIdToLoad);
      const chat = await chatApi.getChat(chatIdToLoad);
      const displayMessages = (chat.chat_data?.messages || []).map((msg): DisplayMessage => ({
        ...msg,
        type: 'text'
      }));
      setMessages(displayMessages);
      console.log("Messages fetched:", chat.chat_data?.messages);
    } catch (err: any) {
      console.error(`Failed to load messages for chat ${chatIdToLoad}:`, err);
      setError(`加载聊天内容失败: ${err.message}`);
      setMessages([]);
    } finally {
      setIsLoadingChat(false);
    }
  }, []);

  // Function to get last chat ID for flow
  const getLastChatId = useCallback(async (flowId: string) => {
    try {
      const lastChatResponse = await getLastChatIdForFlow(flowId);
      return lastChatResponse?.chatId ?? null;
    } catch (err: any) {
      console.error('Failed to get last chat ID:', err);
      return null;
    }
  }, []);

  // Initialize data for flow
  const initializeData = useCallback(async (flowId: string) => {
    if (!flowId) return;
    
    console.log("Flow ID changed:", flowId);
    // Reset state for the new flow
    setChatList([]);
    setActiveChatId(null);
    setMessages([]);
    setError(null);
    setIsLoadingList(true);
    setIsLoadingChat(true);

    try {
      // 1. Fetch last interacted chat ID
      const lastChatId = await getLastChatId(flowId);
      console.log("Last interacted chat ID:", lastChatId);

      // 2. Fetch the full chat list
      await fetchChatList(flowId);

      // 3. Set active chat and fetch its messages if lastChatId exists
      setActiveChatId(lastChatId);
      if (lastChatId) {
        await fetchChatMessages(lastChatId);
      } else {
        setIsLoadingChat(false);
      }
    } catch (err: any) {
      console.error('Failed during initial load sequence:', err);
      setError(`初始化聊天界面失败: ${err.message}`);
      setIsLoadingList(false);
      setIsLoadingChat(false);
    }
  }, [fetchChatList, fetchChatMessages, getLastChatId]);

  // Clear data
  const clearData = useCallback(() => {
    setChatList([]);
    setActiveChatId(null);
    setMessages([]);
    setError(null);
    setIsLoadingList(false);
    setIsLoadingChat(false);
  }, []);

  return {
    // State
    chatList,
    activeChatId,
    messages,
    isLoadingList,
    isLoadingChat,
    error,
    
    // Actions
    setChatList,
    setActiveChatId,
    setMessages,
    setError,
    fetchChatList,
    fetchChatMessages,
    initializeData,
    clearData,
  };
}; 