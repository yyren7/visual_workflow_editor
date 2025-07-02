import { useState, useCallback } from 'react';
import { chatApi } from '../../api/chatApi';
import { DisplayMessage } from './types';

interface UseChatActionsProps {
  flowId: string | undefined;
  activeChatId: string | null;
  chatList: any[];
  messages: DisplayMessage[];
  
  // State setters
  setChatList: React.Dispatch<React.SetStateAction<any[]>>;
  setActiveChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<DisplayMessage[]>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  
  // Data fetchers
  fetchChatList: (flowId: string) => Promise<any[]>;
  fetchChatMessages: (chatId: string) => Promise<void>;
  
  // SSE handlers
  streamingAssistantMsgIdRef: React.MutableRefObject<string | null>;
  closeEventSourceRef: React.MutableRefObject<(() => void) | null>;
  closeActiveConnection: () => void;
}

export const useChatActions = ({
  flowId,
  activeChatId,
  chatList,
  messages,
  setChatList,
  setActiveChatId,
  setMessages,
  setError,
  fetchChatList,
  fetchChatMessages,
  streamingAssistantMsgIdRef,
  closeEventSourceRef,
  closeActiveConnection,
}: UseChatActionsProps) => {
  const [isSending, setIsSending] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [isDeletingChatId, setIsDeletingChatId] = useState<string | null>(null);
  const [isRenamingChatId, setIsRenamingChatId] = useState<string | null>(null);
  const [renameInputValue, setRenameInputValue] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<string | null>(null);
  const [editingMessageTimestamp, setEditingMessageTimestamp] = useState<string | null>(null);
  const [editingMessageContent, setEditingMessageContent] = useState<string>("");

  // Create new chat
  const handleCreateNewChat = useCallback(async () => {
    if (!flowId || isCreatingChat) return;
    
    closeActiveConnection();
    setIsCreatingChat(true);
    setError(null);
    
    try {
      console.log("Creating new chat for flow:", flowId);
      const newChat = await chatApi.createChat(flowId);
      console.log("New chat created:", newChat);
      
      await fetchChatList(flowId);
      setActiveChatId(newChat.id);
      setEditingMessageTimestamp(null);
      setEditingMessageContent("");
    } catch (err: any) {
      console.error('Failed to create new chat:', err);
      setError(`创建新聊天失败: ${err.message}`);
    } finally {
      setIsCreatingChat(false);
    }
  }, [flowId, isCreatingChat, closeActiveConnection, setError, fetchChatList, setActiveChatId]);

  // Select chat
  const handleSelectChat = useCallback((chatId: string) => {
    if (chatId !== activeChatId) {
      closeActiveConnection();
      console.log("Selecting chat:", chatId);
      setActiveChatId(chatId);
      setIsRenamingChatId(null);
      setEditingMessageTimestamp(null);
      setEditingMessageContent("");

      // Update last active chat for flow
      if (flowId) {
        chatApi.updateLastActiveChatForFlow(flowId, chatId)
          .then(() => console.log(`Successfully updated last active chat to ${chatId} for flow ${flowId}`))
          .catch(err => console.error(`Error updating last active chat for flow ${flowId}:`, err));
      }
    }
  }, [activeChatId, closeActiveConnection, setActiveChatId, setIsRenamingChatId, flowId]);

  // Send message
  const handleSendMessage = useCallback((
    inputMessage: string,
    createSendMessageHandler: any,
    createErrorHandler: any,
    createCloseHandler: any
  ) => {
    if (!inputMessage.trim() || !activeChatId || isSending) return;

    closeActiveConnection();

    setIsSending(true);
    setError(null);
    
    const userMessage: DisplayMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: `user-${Date.now()}`,
      type: 'text'
    };

    setMessages(prev => [...prev, userMessage]);

    const assistantMessageId = `assistant-${Date.now()}`;
    streamingAssistantMsgIdRef.current = assistantMessageId;
    
    const assistantPlaceholder: DisplayMessage = {
      role: 'assistant',
      content: '',
      timestamp: assistantMessageId,
      type: 'text',
      isStreaming: true
    };
    setMessages(prev => [...prev, assistantPlaceholder]);

    if (activeChatId) {
      closeEventSourceRef.current = chatApi.sendMessage(
        activeChatId,
        inputMessage,
        createSendMessageHandler(setMessages, setError, setIsSending),
        createErrorHandler(setError, setIsSending),
        createCloseHandler(setIsSending),
        'user',
        userMessage.timestamp
      );
    } else {
      console.error("Cannot send message, activeChatId is null");
      setError("无法发送消息，没有活动的聊天。");
      setIsSending(false);
      setMessages(prev => prev.filter(msg => msg.timestamp !== assistantMessageId));
    }
  }, [activeChatId, isSending, closeActiveConnection, setError, setMessages, streamingAssistantMsgIdRef, closeEventSourceRef]);

  // Start rename chat
  const handleStartRename = useCallback((chatId: string, currentName: string) => {
    setIsRenamingChatId(chatId);
    setRenameInputValue(currentName);
  }, []);

  // Cancel rename chat
  const handleCancelRename = useCallback(() => {
    setIsRenamingChatId(null);
    setRenameInputValue('');
  }, []);

  // Confirm rename chat
  const handleConfirmRename = useCallback(async (chatId: string) => {
    if (!renameInputValue.trim() || renameInputValue.trim() === chatList.find(c => c.id === chatId)?.name) {
      handleCancelRename();
      return;
    }
    
    const originalName = chatList.find(c => c.id === chatId)?.name;
    
    try {
      console.log(`Renaming chat ${chatId} to: ${renameInputValue.trim()}`);
      setChatList(prevList => prevList.map(chat =>
        chat.id === chatId ? { ...chat, name: renameInputValue.trim() } : chat
      ));

      await chatApi.updateChat(chatId, { name: renameInputValue.trim() });
      if (flowId) {
        await fetchChatList(flowId);
      }
      console.log("Chat renamed successfully");
      handleCancelRename();
    } catch (err: any) {
      console.error(`Failed to rename chat ${chatId}:`, err);
      setError(`重命名失败: ${err.message}`);
      setChatList(prevList => prevList.map(chat =>
        chat.id === chatId ? { ...chat, name: originalName || chat.name } : chat
      ));
    }
  }, [renameInputValue, chatList, handleCancelRename, setChatList, fetchChatList, flowId, setError]);

  // Delete chat
  const handleDeleteChat = useCallback((chatId: string) => {
    setChatToDelete(chatId);
    setShowDeleteConfirm(true);
  }, []);

  // Confirm delete chat
  const confirmDeleteChat = useCallback(async () => {
    if (!chatToDelete || !flowId) return;
    
    setShowDeleteConfirm(false);
    setIsDeletingChatId(chatToDelete);
    setError(null);
    
    try {
      console.log(`Deleting chat ${chatToDelete}`);
      await chatApi.deleteChat(chatToDelete);
      console.log("Chat deleted successfully");

      if (activeChatId === chatToDelete) {
        setActiveChatId(null);
        setMessages([]);
      }
      
      await fetchChatList(flowId);
    } catch (err: any) {
      console.error(`Failed to delete chat ${chatToDelete}:`, err);
      setError(`删除聊天失败: ${err.message}`);
    } finally {
      setIsDeletingChatId(null);
      setChatToDelete(null);
    }
  }, [chatToDelete, flowId, setError, activeChatId, setActiveChatId, setMessages, fetchChatList]);

  // Cancel delete chat
  const cancelDeleteChat = useCallback(() => {
    setShowDeleteConfirm(false);
    setChatToDelete(null);
  }, []);

  // Start edit message
  const handleStartEditMessage = useCallback((message: DisplayMessage) => {
    if (message.role === 'user' && message.timestamp) {
      closeActiveConnection();
      streamingAssistantMsgIdRef.current = null;
      
      setMessages(prev => prev.filter(msg => !(msg.isStreaming && msg.role === 'assistant')));
      
      setEditingMessageTimestamp(message.timestamp);
      setEditingMessageContent(message.content);

      setTimeout(() => {
        const messageElement = document.getElementById(`message-${message.timestamp}`);
        if (messageElement) {
          messageElement.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        }
      }, 0);
    }
  }, [closeActiveConnection, streamingAssistantMsgIdRef, setMessages]);

  // Cancel edit message
  const handleCancelEditMessage = useCallback(() => {
    setEditingMessageTimestamp(null);
    setEditingMessageContent("");
  }, []);

  // Confirm edit message
  const handleConfirmEditMessage = useCallback(async (
    createSendMessageHandler: any,
    createErrorHandler: any,
    createCloseHandler: any
  ) => {
    const originalMessageTimestamp = editingMessageTimestamp;
    if (!originalMessageTimestamp || !activeChatId || !flowId) {
      console.warn("handleConfirmEditMessage: Missing required IDs or content.");
      return;
    }

    if (originalMessageTimestamp.startsWith('user-') && !originalMessageTimestamp.startsWith('user-edited-')) {
      setError("消息尚未完全保存，请稍后再试。");
      return;
    }

    closeActiveConnection();

    setIsSending(true);
    setError(null);
    
    const editedContent = editingMessageContent;

    setMessages(prevMessages => {
      const editMsgIndex = prevMessages.findIndex(msg => msg.timestamp === originalMessageTimestamp);
      if (editMsgIndex === -1) return prevMessages;
      
      const newMessages = prevMessages.slice(0, editMsgIndex);
      newMessages.push({
        role: 'user',
        content: editedContent,
        timestamp: `user-edited-${Date.now()}`,
        type: 'text'
      });
      return newMessages;
    });

    setEditingMessageTimestamp(null);
    setEditingMessageContent("");

    const assistantMessageId = `assistant-after-edit-${Date.now()}`;
    streamingAssistantMsgIdRef.current = assistantMessageId;
    
    const assistantPlaceholder: DisplayMessage = {
      role: 'assistant',
      content: '',
      timestamp: assistantMessageId,
      type: 'text',
      isStreaming: true
    };
    setMessages(prev => [...prev, assistantPlaceholder]);

    if (activeChatId) {
      closeEventSourceRef.current = chatApi.editUserMessage(
        activeChatId,
        originalMessageTimestamp,
        editedContent,
        createSendMessageHandler(setMessages, setError, setIsSending),
        createErrorHandler(setError, setIsSending),
        createCloseHandler(setIsSending)
      );
    }
  }, [editingMessageTimestamp, activeChatId, flowId, editingMessageContent, closeActiveConnection, setError, setMessages, streamingAssistantMsgIdRef, closeEventSourceRef]);

  return {
    // State
    isSending,
    isCreatingChat,
    isDeletingChatId,
    isRenamingChatId,
    renameInputValue,
    showDeleteConfirm,
    chatToDelete,
    editingMessageTimestamp,
    editingMessageContent,
    
    // Actions
    setIsSending,
    setRenameInputValue,
    setEditingMessageContent,
    handleCreateNewChat,
    handleSelectChat,
    handleSendMessage,
    handleStartRename,
    handleCancelRename,
    handleConfirmRename,
    handleDeleteChat,
    confirmDeleteChat,
    cancelDeleteChat,
    handleStartEditMessage,
    handleCancelEditMessage,
    handleConfirmEditMessage,
  };
}; 