import React, { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle, useMemo } from 'react';
import { Box } from '@mui/material';
import { useChatData } from './useChatData';
import { useSSEHandler } from './useSSEHandler';
import { useChatActions } from './useChatActions';
import { formatMessagesToMarkdown, downloadMarkdown } from './utils';
import { ChatInterfaceProps, ChatInterfaceHandle } from './types';
import ChatMessageArea from '../chat/ChatMessageArea';
import MessageInputBar from '../chat/MessageInputBar';
import DeleteChatDialog from '../chat/DeleteChatDialog';

const ChatInterface = forwardRef<ChatInterfaceHandle, ChatInterfaceProps>((
  {
    flowId,
    onNodeSelect,
    onActiveChatChange,
    onChatInteractionStateChange,
  },
  ref
) => {
  // Input state
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<null | HTMLDivElement>(null);

  // Data management
  const {
    chatList,
    activeChatId,
    messages,
    isLoadingList,
    isLoadingChat,
    error,
    setChatList,
    setActiveChatId,
    setMessages,
    setError,
    fetchChatList,
    fetchChatMessages,
    initializeData,
    clearData,
  } = useChatData();

  // SSE handling
  const {
    streamingAssistantMsgIdRef,
    closeEventSourceRef,
    createSendMessageHandler,
    createErrorHandler,
    createCloseHandler,
    closeActiveConnection,
  } = useSSEHandler();

  // Chat actions
  const {
    isSending,
    isCreatingChat,
    isDeletingChatId,
    isRenamingChatId,
    renameInputValue,
    showDeleteConfirm,
    chatToDelete,
    editingMessageTimestamp,
    editingMessageContent,
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
  } = useChatActions({
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
  });

  // Initialize data when flowId changes
  useEffect(() => {
    if (flowId) {
      initializeData(flowId);
    } else {
      clearData();
    }
  }, [flowId, initializeData, clearData]);

  // Load messages when activeChatId changes
  useEffect(() => {
    if (activeChatId) {
      fetchChatMessages(activeChatId);
    } else {
      setMessages([]);
    }
  }, [activeChatId, fetchChatMessages, setMessages]);

  // Inform parent about active chat name change
  useEffect(() => {
    if (onActiveChatChange) {
      if (activeChatId) {
        const currentChat = chatList.find(chat => chat.id === activeChatId);
        onActiveChatChange(currentChat ? currentChat.name : null);
      } else {
        onActiveChatChange(null);
      }
    }
  }, [activeChatId, chatList, onActiveChatChange]);

  // Memoize interaction state to reduce parent re-renders
  const interactionState = useMemo(() => ({
    isCreatingChat: isCreatingChat,
    canDownload: !!activeChatId && messages.length > 0,
  }), [isCreatingChat, activeChatId, messages.length]);

  // Inform parent about interaction states
  useEffect(() => {
    if (onChatInteractionStateChange) {
      onChatInteractionStateChange(interactionState);
    }
  }, [interactionState, onChatInteractionStateChange]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeActiveConnection();
    };
  }, [closeActiveConnection]);

  // Handle send message
  const handleSendMessageWrapper = useCallback(() => {
    if (!inputMessage.trim() || !activeChatId || isSending || isLoadingChat) return;

    handleSendMessage(
      inputMessage,
      createSendMessageHandler,
      createErrorHandler,
      createCloseHandler
    );
    
    setInputMessage('');
  }, [
    inputMessage,
    activeChatId,
    isSending,
    isLoadingChat,
    handleSendMessage,
    createSendMessageHandler,
    createErrorHandler,
    createCloseHandler
  ]);

  // Handle key press
  const handleKeyPress = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessageWrapper();
    }
  }, [handleSendMessageWrapper]);

  // Handle download chat
  const handleDownloadChat = useCallback(() => {
    if (!activeChatId || messages.length === 0) {
      setError("没有活动的聊天或消息可供下载");
      return;
    }
    
    const activeChat = chatList.find(chat => chat.id === activeChatId);
    const chatName = activeChat?.name || `chat-${activeChatId}`;
    
    try {
      const markdown = formatMessagesToMarkdown(messages, chatName);
      downloadMarkdown(markdown, `${chatName}.md`);
      setError(null);
    } catch (err: any) {
      console.error('Failed to download chat:', err);
      setError(`下载聊天记录失败: ${err.message}`);
    }
  }, [activeChatId, messages, chatList, setError]);

  // Input disabled state
  const hasActiveChat = !!activeChatId;
  const inputDisabled = !hasActiveChat || isSending || isLoadingChat || isLoadingList || isCreatingChat;

  // Expose methods to parent component
  useImperativeHandle(ref, () => ({
    createNewChat: handleCreateNewChat,
    downloadActiveChat: handleDownloadChat,
    getChatList: async () => {
      if (flowId) {
        return await fetchChatList(flowId);
      }
      return null;
    },
    renameChat: async (chatId: string, newName: string) => {
      if (!newName.trim()) {
        console.warn("Rename skipped: new name is empty.");
        return;
      }
      // This would need to be implemented in useChatActions if needed imperatively
      console.log(`[Imperative] Renaming chat ${chatId} to: ${newName.trim()}`);
    },
    deleteChat: (chatId: string) => {
      handleDeleteChat(chatId);
    },
    selectChat: (chatId: string) => {
      handleSelectChat(chatId);
    }
  }), [handleCreateNewChat, handleDownloadChat, fetchChatList, flowId, handleDeleteChat, handleSelectChat]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'row', padding: 1, gap: 1, overflow: 'hidden' }}>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <ChatMessageArea
          messages={messages}
          activeChatId={activeChatId}
          isLoadingChat={isLoadingChat}
          editingMessageTimestamp={editingMessageTimestamp}
          editingMessageContent={editingMessageContent}
          isSending={isSending}
          onNodeSelect={onNodeSelect}
          onStartEditMessage={handleStartEditMessage}
          onEditingContentChange={setEditingMessageContent}
          onConfirmEditMessage={() => handleConfirmEditMessage(createSendMessageHandler, createErrorHandler, createCloseHandler)}
          onCancelEditMessage={handleCancelEditMessage}
        />
        
        <MessageInputBar
          inputMessage={inputMessage}
          inputDisabled={inputDisabled}
          isSending={isSending}
          editingMessageTimestamp={editingMessageTimestamp}
          onInputChange={setInputMessage}
          onSendMessage={handleSendMessageWrapper}
          onKeyPress={handleKeyPress}
          hasActiveChat={hasActiveChat}
        />
      </Box>

      <DeleteChatDialog
        open={showDeleteConfirm}
        onClose={cancelDeleteChat}
        onConfirmDelete={confirmDeleteChat}
      />
    </Box>
  );
});

export default ChatInterface; 