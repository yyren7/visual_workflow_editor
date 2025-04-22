// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  chatApi,
  JsonChatResponse,
  ChatEvent,
  OnChatEventCallback,
  OnChatErrorCallback,
  OnChatCloseCallback
} from '../api/chatApi'; // 更新 chatApi 导入路径
import { getLastChatIdForFlow } from '../api/flowApi'; // 更新 getLastChatIdForFlow 导入路径
import { Message, Chat } from '../types'; // Assuming Chat type exists in types.ts
import {
  Box, TextField, Button, Paper, Typography, CircularProgress,
  List, ListItem, ListItemButton, ListItemText, IconButton,
  Tooltip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Input
} from '@mui/material';
import {
  Send as SendIcon,
  AddComment as AddCommentIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Check as CheckIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import ToolCallCard from './ToolCallCard'; // <-- 导入新组件

// Interface for messages, potentially adding a type for tool cards
interface DisplayMessage extends Message {
  type?: 'text' | 'tool_card'; // Add type for rendering
  toolInfo?: JsonChatResponse; // Store tool info if it's a tool card
  isStreaming?: boolean; // Indicate if assistant message is currently streaming
}

interface ChatInterfaceProps {
  flowId: string | undefined;
  // chatId prop is no longer needed to drive loading, flowId is the primary driver
  // Keep onChatCreated for potential future use if needed, but primary interaction is within the component
  onChatCreated?: (newChatId: string) => void;
  onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
}

// Helper function to format messages to Markdown
const formatMessagesToMarkdown = (messages: DisplayMessage[], chatName: string): string => {
  let markdown = `# Chat History: ${chatName}\n\n`;
  messages.forEach(message => {
    const role = message.role.charAt(0).toUpperCase() + message.role.slice(1);
    markdown += `## ${role}\n\n`;
    // TODO: Format tool card info for markdown if needed
    if (message.type === 'tool_card' && message.toolInfo) {
      markdown += `**[Tool Execution Card]**\n`;
      markdown += `* Summary: ${message.toolInfo.summary || 'N/A'}\n`;
      if (message.toolInfo.tool_calls_info) {
        markdown += `* Calls: ${JSON.stringify(message.toolInfo.tool_calls_info)}\n`;
      }
      if (message.toolInfo.tool_results_info) {
        markdown += `* Results: ${JSON.stringify(message.toolInfo.tool_results_info)}\n`;
      }
      if (message.toolInfo.error) {
        markdown += `* Error: ${message.toolInfo.error}\n`;
      }
      markdown += `\n`;
    } else {
      markdown += `${message.content}\n\n`;
    }
    markdown += `---\n\n`;
  });
  return markdown;
};

// Helper function to trigger download
const downloadMarkdown = (markdownContent: string, filename: string) => {
  const blob = new Blob([markdownContent], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.md') ? filename : `${filename}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};


const ChatInterface: React.FC<ChatInterfaceProps> = ({
  flowId,
  onChatCreated,
  onNodeSelect,
}) => {
  // --- State Variables ---
  const [chatList, setChatList] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false); // Loading specific chat messages
  const [isSending, setIsSending] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [isDeletingChatId, setIsDeletingChatId] = useState<string | null>(null); // Track which chat is being deleted
  const [isRenamingChatId, setIsRenamingChatId] = useState<string | null>(null);
  const [renameInputValue, setRenameInputValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<null | HTMLDivElement>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<string | null>(null);
  const streamingAssistantMsgIdRef = useRef<string | null>(null);
  const closeEventSourceRef = useRef<(() => void) | null>(null);

  // --- Data Fetching ---

  // Function to fetch chat list for the current flow
  const fetchChatList = useCallback(async (currentFlowId: string) => {
    setIsLoadingList(true);
    setError(null);
    try {
      console.log("Fetching chat list for flow:", currentFlowId);
      // Fetch with a reasonable limit, adjust if needed
      const fetchedChats = await chatApi.getFlowChats(currentFlowId, 0, 100);
      setChatList(fetchedChats || []); // Ensure it's always an array
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
  }, []); // No dependencies, it's a stable function

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
      // Map fetched messages to DisplayMessage, defaulting type to 'text'
      const displayMessages = (chat.chat_data?.messages || []).map((msg): DisplayMessage => ({
        ...msg,
        type: 'text' // Assume text unless content indicates otherwise (or modify later)
      }));
      setMessages(displayMessages);
      console.log("Messages fetched:", chat.chat_data?.messages);
    } catch (err: any) {
      console.error(`Failed to load messages for chat ${chatIdToLoad}:`, err);
      setError(`加载聊天内容失败: ${err.message}`);
      setMessages([]); // Clear messages on error
      // If the active chat fails to load, maybe deactivate it?
      // setActiveChatId(null);
    } finally {
      setIsLoadingChat(false);
    }
  }, []); // Also stable

  // Effect to load initial data when flowId changes
  useEffect(() => {
    if (flowId) {
      console.log("Flow ID changed:", flowId);
      // Reset state for the new flow
      setChatList([]);
      setActiveChatId(null);
      setMessages([]);
      setError(null);
      setIsLoadingList(true);
      setIsLoadingChat(true); // Indicate initial loading

      let lastChatId: string | null = null;

      const loadInitialData = async () => {
        try {
          // 1. Fetch last interacted chat ID
          const lastChatResponse = await getLastChatIdForFlow(flowId);
          lastChatId = lastChatResponse?.chatId ?? null;
          console.log("Last interacted chat ID:", lastChatId);

          // 2. Fetch the full chat list
          await fetchChatList(flowId); // fetchChatList handles its own loading state and updates chatList

          // 3. Set active chat and fetch its messages if lastChatId exists
          setActiveChatId(lastChatId); // Set active chat regardless of whether messages load
          if (lastChatId) {
            await fetchChatMessages(lastChatId); // fetchChatMessages handles its loading state
          } else {
            setIsLoadingChat(false); // No chat to load messages for
          }

        } catch (err: any) {
          console.error('Failed during initial load sequence:', err);
          setError(`初始化聊天界面失败: ${err.message}`);
          setIsLoadingList(false); // Ensure loading states are off on error
          setIsLoadingChat(false);
        }
      };

      loadInitialData();

    } else {
      // Clear state if flowId becomes undefined
      setChatList([]);
      setActiveChatId(null);
      setMessages([]);
      setError(null);
    }
  }, [flowId, fetchChatList, fetchChatMessages]); // Rerun when flowId changes

  // Effect to load messages when activeChatId changes (and is not null)
  useEffect(() => {
    if (activeChatId) {
      console.log("Active chat ID changed:", activeChatId);
      fetchChatMessages(activeChatId);
    } else {
      // Clear messages if no chat is active
      setMessages([]);
    }
  }, [activeChatId, fetchChatMessages]); // Rerun only when activeChatId changes


  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- 新增：清理 Effect ---
  useEffect(() => {
    // 当组件卸载或 flowId/activeChatId 改变时，关闭任何活动的 EventSource 连接
    return () => {
      if (closeEventSourceRef.current) {
        console.log("ChatInterface cleanup: Closing active EventSource.");
        closeEventSourceRef.current();
        closeEventSourceRef.current = null;
      }
    };
  }, []); // 空依赖数组确保只在卸载时运行清理

  // --- Event Handlers ---

  const handleSelectChat = (chatId: string) => {
    if (chatId !== activeChatId) {
      // --- 关闭旧的连接 ---
      if (closeEventSourceRef.current) {
        console.log("Switching chat: Closing previous EventSource.");
        closeEventSourceRef.current();
        closeEventSourceRef.current = null;
      }
      // --------------------
      console.log("Selecting chat:", chatId);
      setActiveChatId(chatId);
      setIsRenamingChatId(null); // Cancel rename if a different chat is selected
    }
  };

  const handleCreateNewChat = async () => {
    if (!flowId || isCreatingChat) return;
    // --- 关闭旧的连接 ---
    if (closeEventSourceRef.current) {
      console.log("Creating new chat: Closing previous EventSource.");
      closeEventSourceRef.current();
      closeEventSourceRef.current = null;
    }
    // --------------------
    setIsCreatingChat(true);
    setError(null);
    try {
      console.log("Creating new chat for flow:", flowId);
      const newChat = await chatApi.createChat(flowId); // 使用 API 默认名称
      console.log("New chat created:", newChat);
      // Refresh list and set new chat as active
      await fetchChatList(flowId); // Update the list
      setActiveChatId(newChat.id); // Select the new chat
      if (onChatCreated) { // Optional: notify parent if needed
        onChatCreated(newChat.id);
      }
    } catch (err: any) {
      console.error('Failed to create new chat:', err);
      setError(`创建新聊天失败: ${err.message}`);
    } finally {
      setIsCreatingChat(false);
    }
  };

  const handleSendMessage = () => {
    if (!inputMessage.trim() || !activeChatId || isSending || isLoadingChat) return;

    // --- 先关闭可能存在的旧连接 ---
    if (closeEventSourceRef.current) {
      console.log("Sending new message: Closing previous EventSource first.");
      closeEventSourceRef.current();
      closeEventSourceRef.current = null;
    }
    // -----------------------------

    setIsSending(true);
    setError(null);
    const userMessage: DisplayMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: `user-${Date.now()}`,
      type: 'text'
    };

    // 立即将用户消息添加到 UI
    setMessages(prev => [...prev, userMessage]);
    const messageToSend = inputMessage;
    setInputMessage('');

    // 添加助手消息占位符
    const assistantMessageId = `assistant-${Date.now()}`;
    streamingAssistantMsgIdRef.current = assistantMessageId; // 记录当前流的消息 ID
    const assistantPlaceholder: DisplayMessage = {
      role: 'assistant',
      content: '', // 初始为空
      timestamp: assistantMessageId,
      type: 'text',
      isStreaming: true // 标记为正在流式传输
    };
    setMessages(prev => [...prev, assistantPlaceholder]);

    // --- 定义 SSE 回调 ---
    const handleChatEvent: OnChatEventCallback = (event) => {
      console.log("Received SSE Event:", JSON.stringify(event)); // 保持这个日志用于调试

      setMessages(prevMessages => {
        // 找到当前正在流式处理的助手消息
        const currentStreamingMsgIndex = prevMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current);
        // console.log("Found streaming index:", currentStreamingMsgIndex);

        if (currentStreamingMsgIndex === -1 && event.type !== 'final_result' && event.type !== 'error') {
          console.warn(`Received event type ${event.type} but no streaming message ref found.`);
          return prevMessages;
        }

        const newMessages = [...prevMessages];

        switch (event.type) {
          case 'llm_chunk':
            if (currentStreamingMsgIndex !== -1) {
              const textChunk = event.data.text;
              // console.log("Applying chunk:", textChunk);
              const previousContent = newMessages[currentStreamingMsgIndex].content;
              newMessages[currentStreamingMsgIndex] = {
                ...newMessages[currentStreamingMsgIndex],
                content: previousContent + textChunk,
                isStreaming: true,
                type: 'text',
                toolInfo: undefined
              };
              // console.log("Updated content:", newMessages[currentStreamingMsgIndex].content);
            } else {
               console.warn("LLM Chunk received but no active streaming message found!");
            }
            break;
          case 'final_result':
             const finalData = event.data;
             let finalContent = finalData.summary || '';
             let finalType: 'text' | 'tool_card' = 'text';
             let finalToolInfo: JsonChatResponse | undefined = undefined;

             if (finalData.error) {
                 finalContent = `错误: ${finalData.error}`;
                 setError(finalData.error); 
             } else if (finalData.tool_calls_info || finalData.tool_results_info) {
                 finalType = 'tool_card';
                 finalContent = finalData.summary || '[工具执行完成]';
                 finalToolInfo = finalData;
             }

             if (currentStreamingMsgIndex !== -1) {
                 newMessages[currentStreamingMsgIndex] = {
                     ...newMessages[currentStreamingMsgIndex],
                     content: finalContent,
                     type: finalType,
                     toolInfo: finalToolInfo,
                     isStreaming: false // 标记流结束
                 };
             } else {
                  newMessages.push({
                      role: 'assistant',
                      content: finalContent,
                      timestamp: `assistant-${Date.now()}`,
                      type: finalType,
                      toolInfo: finalToolInfo,
                      isStreaming: false
                  });
             }
             // --- 不在此处清除 Ref --- 
             // streamingAssistantMsgIdRef.current = null; 
             setIsSending(false); 
            break;
          case 'stream_end':
            console.log("Stream end event received."); // 保持这个日志
            if (currentStreamingMsgIndex !== -1) {
              newMessages[currentStreamingMsgIndex] = {
                ...newMessages[currentStreamingMsgIndex],
                isStreaming: false
              };
            }
            // --- 不在此处清除 Ref --- 
            // streamingAssistantMsgIdRef.current = null; 
            setIsSending(false); 
            break;
          case 'error':
            console.error("Received error event:", event.data.message); // 保持这个日志
            const errorMessage = `错误: ${event.data.message}`;
            if (currentStreamingMsgIndex !== -1) {
              newMessages[currentStreamingMsgIndex] = {
                ...newMessages[currentStreamingMsgIndex],
                content: newMessages[currentStreamingMsgIndex].content + `\n${errorMessage}`,
                isStreaming: false
              };
            } else {
               newMessages.push({
                   role: 'assistant',
                   content: errorMessage,
                   timestamp: `error-${Date.now()}`,
                   type: 'text',
                   isStreaming: false
               });
            }
            setError(event.data.message);
            // --- 不在此处清除 Ref --- 
            // streamingAssistantMsgIdRef.current = null; 
            setIsSending(false); 
            break;
          case 'ping':
             console.log("Received ping event from server.");
             break;
          default:
            console.warn("Received unknown event type:", event);
        }
        return newMessages;
      });
    };

    const handleChatError: OnChatErrorCallback = (error) => {
      console.error("Chat API Error:", error);
      const errorMessage = error.message || "与服务器的连接出错";
      setError(errorMessage);
      // 更新可能存在的占位符以显示错误
      setMessages(prevMessages => {
        const currentStreamingMsgIndex = prevMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current);
        if (currentStreamingMsgIndex !== -1) {
          const newMessages = [...prevMessages];
          newMessages[currentStreamingMsgIndex] = {
            ...newMessages[currentStreamingMsgIndex],
            content: newMessages[currentStreamingMsgIndex].content + `\n错误: ${errorMessage}`,
            isStreaming: false
          };
          return newMessages;
        }
        // 如果没有占位符，可能需要添加新的错误消息，或者仅依赖全局错误状态
        return prevMessages;
      });
      setIsSending(false);
      // streamingAssistantMsgIdRef.current = null; // <-- 移除（或确认不存在）
    };

    const handleChatClose: OnChatCloseCallback = () => {
      console.log("Chat EventSource closed."); // 保持这个日志
      setMessages(prevMessages => {
         const currentStreamingMsgIndex = prevMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current);
         if (currentStreamingMsgIndex !== -1 && prevMessages[currentStreamingMsgIndex].isStreaming) {
             const newMessages = [...prevMessages];
             newMessages[currentStreamingMsgIndex] = {
                 ...newMessages[currentStreamingMsgIndex],
                 isStreaming: false
             };
             return newMessages;
         }
         return prevMessages; 
      });
      setIsSending(false); 
      streamingAssistantMsgIdRef.current = null; // <-- **在这里清除 Ref**
      closeEventSourceRef.current = null; 
    };

    // --- 调用新的 API ---
    if (activeChatId) { // 再次确认 activeChatId 存在
      // 保存关闭函数
      closeEventSourceRef.current = chatApi.sendMessage(
        activeChatId,
        messageToSend,
        handleChatEvent,
        handleChatError,
        handleChatClose
      );
    } else {
      console.error("Cannot send message, activeChatId is null");
      setError("无法发送消息，没有活动的聊天。");
      setIsSending(false);
      // 清理可能已添加的占位符
      setMessages(prev => prev.filter(msg => msg.timestamp !== assistantMessageId));
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const handleDownloadChat = () => {
    if (!activeChatId || messages.length === 0) {
      setError("没有活动的聊天或消息可供下载");
      return;
    }
    const activeChat = chatList.find(chat => chat.id === activeChatId);
    const chatName = activeChat?.name || `chat-${activeChatId}`;
    try {
      const markdown = formatMessagesToMarkdown(messages, chatName);
      downloadMarkdown(markdown, `${chatName}.md`);
      setError(null); // Clear previous errors
    } catch (err: any) {
      console.error('Failed to download chat:', err);
      setError(`下载聊天记录失败: ${err.message}`);
    }

  };

  const handleStartRename = (chatId: string, currentName: string) => {
    setIsRenamingChatId(chatId);
    setRenameInputValue(currentName);
  };

  const handleCancelRename = () => {
    setIsRenamingChatId(null);
    setRenameInputValue('');
  };

  const handleConfirmRename = async (chatId: string) => {
    if (!renameInputValue.trim() || renameInputValue.trim() === chatList.find(c => c.id === chatId)?.name) {
      handleCancelRename(); // Cancel if name is empty or unchanged
      return;
    }
    const originalName = chatList.find(c => c.id === chatId)?.name; // Store original name for potential revert
    setIsLoadingList(true); // Indicate activity
    try {
      console.log(`Renaming chat ${chatId} to: ${renameInputValue.trim()}`);
      // Optimistic UI update (optional but can feel snappier)
      setChatList(prevList => prevList.map(chat =>
        chat.id === chatId ? { ...chat, name: renameInputValue.trim() } : chat
      ));

      await chatApi.updateChat(chatId, { name: renameInputValue.trim() });
      // Refresh the list from the server to get the confirmed state
      await fetchChatList(flowId!); // Assert flowId exists here
      console.log("Chat renamed successfully");
      handleCancelRename(); // Close input field
    } catch (err: any) {
      console.error(`Failed to rename chat ${chatId}:`, err);
      setError(`重命名失败: ${err.message}`);
      // Revert optimistic update if it was implemented
      setChatList(prevList => prevList.map(chat =>
        chat.id === chatId ? { ...chat, name: originalName || chat.name } : chat // 使用 originalName 回滚
      ));
      setIsLoadingList(false); // Ensure loading indicator is off on error
    } finally {
      // fetchChatList sets isLoadingList to false
      // setIsLoadingList(false); // Set loading false if not using optimistic update
    }
  };


  const handleDeleteChat = (chatId: string) => {
    setChatToDelete(chatId);
    setShowDeleteConfirm(true);
  };

  const confirmDeleteChat = async () => {
    if (!chatToDelete || !flowId) return;
    setShowDeleteConfirm(false);
    setIsDeletingChatId(chatToDelete); // Indicate which item is being deleted
    setError(null);
    try {
      console.log(`Deleting chat ${chatToDelete}`);
      await chatApi.deleteChat(chatToDelete);
      console.log("Chat deleted successfully");

      // Clear active chat if it was the one deleted
      if (activeChatId === chatToDelete) {
        setActiveChatId(null);
        setMessages([]);
      }
      // Refresh the chat list
      await fetchChatList(flowId);

    } catch (err: any) {
      console.error(`Failed to delete chat ${chatToDelete}:`, err);
      setError(`删除聊天失败: ${err.message}`);
    } finally {
      setIsDeletingChatId(null);
      setChatToDelete(null);
    }
  };

  const cancelDeleteChat = () => {
    setShowDeleteConfirm(false);
    setChatToDelete(null);
  };


  // --- Render Logic ---
  const hasActiveChat = !!activeChatId;
  const inputDisabled = !hasActiveChat || isSending || isLoadingChat || isLoadingList || isCreatingChat;

  // --- Rendering Logic (Needs update for clickable nodes) ---
  const renderMessageContent = (message: DisplayMessage) => {
    if (message.type === 'tool_card' && message.toolInfo) {
      // --- 使用 ToolCallCard ---
      return <ToolCallCard toolInfo={message.toolInfo} />;
      // -------------------------
      /*  之前的占位符 Box
      return (
        <Box sx={{ border: '1px dashed grey', p: 1, borderRadius: 1, my: 0.5 }}>
          <Typography variant="caption" display="block" gutterBottom>工具执行信息:</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mb: 1 }}>
            {message.content} 
          </Typography>
        </Box>
      );
      */
    }

    // Original logic for rendering text, maybe with clickable nodes
    const parts = message.content.split(/(\[Node: [a-zA-Z0-9_-]+\])/g);
    return (
      <>
        {parts.map((part, index) => {
          const match = part.match(/\[Node: ([a-zA-Z0-9_-]+)\]/);
          if (match) {
            const nodeId = match[1];
            return (
              <Button
                key={index}
                size="small"
                variant="text"
                onClick={() => onNodeSelect(nodeId)}
                sx={{ p: 0, minWidth: 'auto', verticalAlign: 'baseline', textTransform: 'none', display: 'inline', lineHeight: 'inherit' }}
              >
                (Node: {nodeId})
              </Button>
            );
          }
          return <span key={index}>{part}</span>;
        })}
        {/* Show streaming indicator */}
        {message.isStreaming && <CircularProgress size={12} sx={{ ml: 1, verticalAlign: 'middle' }} />}
      </>
    );
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'row', padding: 1, gap: 1, overflow: 'hidden' }}>

      {/* --- Chat List Sidebar (Left) --- */}
      <Paper elevation={2} sx={{ width: '250px', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        {/* Sidebar Header Buttons */}
        <Box sx={{ p: 1, display: 'flex', gap: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddCommentIcon />}
            onClick={handleCreateNewChat}
            disabled={!flowId || isCreatingChat || isLoadingList}
            sx={{ flexGrow: 1 }}
          >
            {isCreatingChat ? <CircularProgress size={20} /> : "新建聊天"}
          </Button>
          <Tooltip title="下载当前聊天记录 (Markdown)">
            <span> {/* Span needed for tooltip when button is disabled */}
              <IconButton
                size="small"
                onClick={handleDownloadChat}
                disabled={!activeChatId || messages.length === 0}
                aria-label="下载聊天记录"
              >
                <DownloadIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Box>

        {/* Chat List */}
        <List sx={{ flexGrow: 1, overflowY: 'auto', p: 0 }}>
          {isLoadingList && !chatList.length && ( // Show loader only if list is truly empty initially
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress /></Box>
          )}
          {!isLoadingList && chatList.length === 0 && (
            <Typography sx={{ p: 2, textAlign: 'center', color: 'text.secondary' }}>暂无聊天记录</Typography>
          )}
          {chatList.map((chat) => (
            <ListItem
              key={chat.id}
              disablePadding
              secondaryAction={isRenamingChatId === chat.id ? (
                <>
                  <IconButton edge="end" aria-label="确认重命名" size="small" onClick={() => handleConfirmRename(chat.id)}>
                    <CheckIcon fontSize="small" />
                  </IconButton>
                  <IconButton edge="end" aria-label="取消重命名" size="small" onClick={handleCancelRename}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </>
              ) : (
                <>
                  <Tooltip title="重命名">
                    <IconButton edge="end" aria-label="重命名" size="small" onClick={(e) => { e.stopPropagation(); handleStartRename(chat.id, chat.name); }}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="删除">
                    <span> {/* Span needed when button is potentially disabled by isDeletingChatId */}
                      <IconButton
                        edge="end"
                        aria-label="删除"
                        size="small"
                        disabled={isDeletingChatId === chat.id}
                        onClick={(e) => { e.stopPropagation(); handleDeleteChat(chat.id); }}
                      >
                        {isDeletingChatId === chat.id ? <CircularProgress size={16} /> : <DeleteIcon fontSize="small" />}
                      </IconButton>
                    </span>
                  </Tooltip>
                </>
              )}
              sx={{ backgroundColor: activeChatId === chat.id ? 'action.selected' : 'inherit' }}
            >
              {isRenamingChatId === chat.id ? (
                <Input
                  value={renameInputValue}
                  onChange={(e) => setRenameInputValue(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleConfirmRename(chat.id); else if (e.key === 'Escape') handleCancelRename(); }}
                  autoFocus
                  fullWidth
                  disableUnderline
                  sx={{ px: 2, py: 1 }}
                />
              ) : (
                <ListItemButton onClick={() => handleSelectChat(chat.id)} dense>
                  <ListItemText primary={chat.name} primaryTypographyProps={{ noWrap: true, title: chat.name }} />
                </ListItemButton>
              )}
            </ListItem>
          ))}
        </List>
        {error && <Typography color="error" variant="caption" sx={{ p: 1 }}>{error}</Typography>}
      </Paper>

      {/* --- Main Chat Area (Right) --- */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {/* Messages Area */}
        <Paper
          elevation={2}
          sx={{
            flex: 1,
            overflow: 'auto',
            p: 2,
            mb: 1,
            backgroundColor: '#ffffff',
            position: 'relative',
          }}
        >
          {isLoadingChat && (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <CircularProgress />
            </Box>
          )}
          {!isLoadingChat && !hasActiveChat && (
            <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', textAlign: 'center', p: 2 }}>
              <Typography variant="h6" gutterBottom>请选择或创建聊天</Typography>
              <Typography color="text.secondary">从左侧侧边栏选择一个聊天，或点击"新建聊天"开始。</Typography>
            </Box>
          )}
          {!isLoadingChat && hasActiveChat && messages.length === 0 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Typography color="black">开始对话吧！</Typography>
            </Box>
          )}
          {!isLoadingChat && messages.length > 0 && messages.map((message) => (
            <Box
              key={message.timestamp} // Use timestamp (or unique ID) as key
              sx={{
                display: 'flex',
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                mb: 1.5
              }}
            >
              <Paper
                elevation={1}
                sx={{
                  p: 1.5,
                  borderRadius: '10px',
                  bgcolor: message.role === 'user' ? 'primary.light' : 'grey.200',
                  // Explicitly set text color for readability, try 'black' for assistant
                  color: message.role === 'user' ? 'primary.contrastText' : 'black',
                  maxWidth: '80%',
                  wordWrap: 'break-word',
                  whiteSpace: 'pre-wrap', // Important for preserving newlines
                }}
              >
                {renderMessageContent(message)}
              </Paper>
            </Box>
          ))}
          <div ref={messagesEndRef} />
        </Paper>

        {/* Input Area */}
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1, mt: 'auto', padding: '8px 0' }}>
          <TextField
            fullWidth
            multiline
            minRows={1}
            maxRows={5}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={hasActiveChat ? "输入消息 (Shift+Enter 换行)" : "请先选择一个聊天"}
            disabled={inputDisabled}
            sx={{
              backgroundColor: '#ffffff',
              borderRadius: '20px',
              '& .MuiOutlinedInput-root': {
                borderRadius: '20px',
                padding: '10px 15px',
                '& fieldset': { border: 'none' },
              },
              '& .MuiInputBase-input': {
                color: 'black',
              }
            }}
          />
          <Button
            variant="contained"
            onClick={handleSendMessage}
            disabled={inputDisabled || !inputMessage.trim()}
            sx={{
              minWidth: 'auto', padding: '10px', borderRadius: '50%', height: '48px', width: '48px',
            }}
            aria-label="发送消息"
          >
            {isSending ? <CircularProgress size={24} color="inherit" /> : <SendIcon />}
          </Button>
        </Box>
      </Box>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={showDeleteConfirm}
        onClose={cancelDeleteChat}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">{"确认删除"}</DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            你确定要删除这个聊天记录吗？此操作无法撤销。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={cancelDeleteChat}>取消</Button>
          <Button onClick={confirmDeleteChat} color="error" autoFocus>
            删除
          </Button>
        </DialogActions>
      </Dialog>

    </Box>
  );
};

export default ChatInterface;
