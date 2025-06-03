// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import {
  chatApi,
  JsonChatResponse,
  ChatEvent,
  OnChatEventCallback,
  OnChatErrorCallback,
  OnChatCloseCallback,
} from '../api/chatApi'; // 更新 chatApi 导入路径
import { getLastChatIdForFlow } from '../api/flowApi'; // 更新 getLastChatIdForFlow 导入路径
import { Chat } from '../types'; // Assuming Chat type exists in types.ts
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
import { DisplayMessage, ChatInterfaceProps, ChatInterfaceHandle, ChatInteractionState } from './chat/chatTypes'; // Added import
import { formatMessagesToMarkdown, downloadMarkdown } from './chat/chatUtils'; // Added import
// import ChatListPanel from './chat/ChatListPanel'; // Removed import for ChatListPanel
import ChatMessageArea from './chat/ChatMessageArea'; // Added import for ChatMessageArea
import MessageInputBar from './chat/MessageInputBar'; // Added import for MessageInputBar
import DeleteChatDialog from './chat/DeleteChatDialog'; // Added import for DeleteChatDialog

// Interface for messages, updated for new event structure
// interface DisplayMessage extends Message {  // REMOVE THIS
//   type: 'text' | 'tool_status' | 'error'; // Refined types
//   isStreaming?: boolean; // Indicate if assistant text message is currently streaming

//   // Fields for tool status messages
//   toolName?: string;
//   toolInput?: any;
//   toolOutputSummary?: string;
//   toolStatus?: 'running' | 'completed' | 'error'; // Status of the tool call
//   toolErrorMessage?: string; // Specific error message for a tool failure
// }

// interface ChatInterfaceProps { // REMOVE THIS
//   flowId: string | undefined;
//   // chatId prop is no longer needed to drive loading, flowId is the primary driver
//   // Keep onChatCreated for potential future use if needed, but primary interaction is within the component
//   onChatCreated?: (newChatId: string) => void;
//   onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
// }

// Helper function to format messages to Markdown // REMOVE THIS
// const formatMessagesToMarkdown = (messages: DisplayMessage[], chatName: string): string => {
//   let markdown = `# Chat History: ${chatName}\n\n`;
//   messages.forEach(message => {
//     const role = message.role.charAt(0).toUpperCase() + message.role.slice(1);
//     markdown += `## ${role}\n\n`;
//     // Remove specific handling for old 'tool_card' type
//     // if (message.type === 'tool_card' && message.toolInfo) {
//     //   markdown += `**[Tool Execution Card]**\n`;
//     //   markdown += `* Summary: ${message.toolInfo.summary || 'N/A'}\n`;
//     //   if (message.toolInfo.tool_calls_info) {
//     //     markdown += `* Calls: ${JSON.stringify(message.toolInfo.tool_calls_info)}\n`;
//     //   }
//     //   if (message.toolInfo.tool_results_info) {
//     //     markdown += `* Results: ${JSON.stringify(message.toolInfo.tool_results_info)}\n`;
//     //   }
//     //   if (message.toolInfo.error) {
//     //     markdown += `* Error: ${message.toolInfo.error}\n`;
//     //   }
//     //   markdown += `\n`;
//     // } else {
//     //   markdown += `${message.content}\n\n`;
//     // }
//     // Render base content (might need refinement for tool_status later)
//     if (message.type === 'tool_status') {
//          markdown += `**[Tool: ${message.toolName || 'Unknown'}]** - Status: ${message.toolStatus}${message.toolOutputSummary ? '\nOutput: ' + message.toolOutputSummary : ''}${message.toolErrorMessage ? '\nError: ' + message.toolErrorMessage : ''}\n\n`;
//     } else {
//          markdown += `${message.content}\n\n`;
//     }
//     markdown += `--- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
// };

// Helper function to trigger download // REMOVE THIS
// const downloadMarkdown = (markdownContent: string, filename: string) => {
//   const blob = new Blob([markdownContent], { type: 'text/markdown' });
//   const url = URL.createObjectURL(blob);
//   const a = document.createElement('a');
//   a.href = url;
//   a.download = filename.endsWith('.md') ? filename : `${filename}.md`;
//   document.body.appendChild(a);
//   a.click();
//   document.body.removeChild(a);
//   URL.revokeObjectURL(url);
// };

const ChatInterface = forwardRef<ChatInterfaceHandle, ChatInterfaceProps>((
  {
    flowId,
    onNodeSelect,
    onActiveChatChange,
    onChatInteractionStateChange,
  },
  ref
) => {
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

  // --- 新增：编辑消息相关的状态 ---
  const [editingMessageTimestamp, setEditingMessageTimestamp] = useState<string | null>(null);
  const [editingMessageContent, setEditingMessageContent] = useState<string>("");
  // --- 结束新增 ---

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

  // Effect to inform parent about active chat name change
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

  // Effect to inform parent about interaction states for buttons
  useEffect(() => {
    if (onChatInteractionStateChange) {
      onChatInteractionStateChange({
        isCreatingChat: isCreatingChat,
        canDownload: !!activeChatId && messages.length > 0,
      });
    }
  }, [isCreatingChat, activeChatId, messages, onChatInteractionStateChange]);

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
      handleCancelEditMessage(); // <--- 在这里添加，取消编辑状态

      // --- 新增：通知后端更新最后活动聊天 ---
      if (flowId) {
        chatApi.updateLastActiveChatForFlow(flowId, chatId)
          .then(() => console.log(`Successfully updated last active chat to ${chatId} for flow ${flowId}`))
          .catch(err => console.error(`Error updating last active chat for flow ${flowId}:`, err));
      } else {
        console.warn("Cannot update last active chat: flowId is undefined.");
      }
      // --- 结束新增 ---
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
      handleCancelEditMessage(); // <--- 添加此行以取消编辑状态
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

      let capturedStreamEndId: string | null = null;
      if (event.type === 'stream_end') {
        capturedStreamEndId = streamingAssistantMsgIdRef.current;
        console.log(`[ChatInterface stream_end event] Captured streamingAssistantMsgIdRef: ${capturedStreamEndId}`);
      }

      setMessages(prevMessages => {
        const newMessages = [...prevMessages];
        const currentStreamingMsgIndex = newMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current && msg.type === 'text');

        switch (event.type) {
          case 'user_message_saved':
            const { client_message_id, server_message_timestamp, content: userContent } = event.data as { client_message_id: string, server_message_timestamp: string, content: string };
            const userMsgIndex = newMessages.findIndex(msg => msg.timestamp === client_message_id && msg.role === 'user');
            if (userMsgIndex !== -1) {
              newMessages[userMsgIndex] = {
                ...newMessages[userMsgIndex],
                timestamp: server_message_timestamp,
              };
              console.log(`[ChatInterface] User message timestamp updated: ${client_message_id} -> ${server_message_timestamp}`);
            } else {
              console.warn(`[ChatInterface] Received user_message_saved for ${client_message_id} but not found in UI.`);
            }
            break;
          case 'token':
            const token = event.data;
            const currentStreamingId = streamingAssistantMsgIdRef.current;
            const streamingMsgIndex = newMessages.findIndex(msg => msg.timestamp === currentStreamingId && msg.type === 'text');

            if (streamingMsgIndex !== -1) {
              newMessages[streamingMsgIndex] = {
                ...newMessages[streamingMsgIndex],
                content: newMessages[streamingMsgIndex].content + token,
                isStreaming: true,
              };
            } else {
              if (token) {
                const assistantMessageId = currentStreamingId || `assistant-${Date.now()}`;
                if (!currentStreamingId) {
                    streamingAssistantMsgIdRef.current = assistantMessageId;
                }
                newMessages.push({
                  role: 'assistant',
                  content: token,
                  timestamp: assistantMessageId,
                  type: 'text',
                  isStreaming: true,
                });
              } else {
                  console.log("Ignoring empty token for new message creation.");
              }
            }
            break;
          case 'tool_start':
            const toolStartMsgId = `tool-${event.data.name}-${Date.now()}`;
            const toolStartMessage: DisplayMessage = {
                 role: 'assistant',
                 content: '',
                 timestamp: toolStartMsgId,
                 type: 'tool_status',
                 toolName: event.data.name,
                 toolInput: event.data.input,
                 toolStatus: 'running',
                 isStreaming: false,
            };
            if (currentStreamingMsgIndex !== -1) {
                newMessages.splice(currentStreamingMsgIndex, 0, toolStartMessage);
            } else {
                newMessages.push(toolStartMessage);
            }
            break;
          case 'tool_end':
            const toolEndMsgIndex = newMessages.findLastIndex(msg =>
                msg.type === 'tool_status' &&
                msg.toolName === event.data.name &&
                msg.toolStatus === 'running'
            );
            if (toolEndMsgIndex !== -1) {
              newMessages[toolEndMsgIndex] = {
                ...newMessages[toolEndMsgIndex],
                toolStatus: 'completed',
                toolOutputSummary: event.data.output_summary,
              };
            } else {
                 console.warn(`Received tool_end for ${event.data.name} but no matching running tool message found.`);
                 const toolEndFallback: DisplayMessage = {
                     role: 'assistant',
                     content: '',
                     timestamp: `tool-end-fallback-${event.data.name}-${Date.now()}`,
                     type: 'tool_status',
                     toolName: event.data.name,
                     toolStatus: 'completed',
                     toolOutputSummary: event.data.output_summary,
                     isStreaming: false
                 };
                 if (currentStreamingMsgIndex !== -1) {
                    newMessages.splice(currentStreamingMsgIndex, 0, toolEndFallback);
                 } else {
                    newMessages.push(toolEndFallback);
                 }
            }
            break;
          case 'stream_end':
            const finishedMsgIndex = newMessages.findIndex(msg => msg.timestamp === capturedStreamEndId);

            if (finishedMsgIndex !== -1) {
              newMessages[finishedMsgIndex] = {
                ...newMessages[finishedMsgIndex],
                isStreaming: false
              };
              console.log(`[ChatInterface stream_end] Marked message with ID '${capturedStreamEndId}' as not streaming.`);
            } else {
              if (capturedStreamEndId) {
                console.warn(`[ChatInterface stream_end] Message with ref ID '${capturedStreamEndId}' not found. Attempting to mark last streaming assistant message.`);
              } else {
                console.warn("[ChatInterface stream_end] Streaming message reference was already null when 'stream_end' event was received. Attempting to mark last streaming assistant message.");
              }

              const lastStreamingAssistantMsgIndex = newMessages.findLastIndex(msg =>
                msg.role === 'assistant' && msg.isStreaming === true
              );

              if (lastStreamingAssistantMsgIndex !== -1) {
                newMessages[lastStreamingAssistantMsgIndex] = { ...newMessages[lastStreamingAssistantMsgIndex], isStreaming: false };
                console.log(`[ChatInterface stream_end] Marked last streaming assistant message (ID: ${newMessages[lastStreamingAssistantMsgIndex].timestamp}, Index: ${lastStreamingAssistantMsgIndex}) as finished as a fallback.`);
              } else {
                console.log("[ChatInterface stream_end] No specific message by ref found, and no other streaming assistant message was found to mark as finished.");
              }
            }
            break;
          case 'error':
            console.error("Received error event:", event.data);
            const errorData = event.data;
            const errorMessage = `错误 (阶段: ${errorData.stage || '未知'}): ${errorData.message}`;
            setError(errorMessage);

            if (errorData.tool_name) {
                const toolErrorMsgIndex = newMessages.findLastIndex(msg =>
                    msg.type === 'tool_status' &&
                    msg.toolName === errorData.tool_name &&
                    msg.toolStatus === 'running'
                );
                if (toolErrorMsgIndex !== -1) {
                    newMessages[toolErrorMsgIndex] = {
                        ...newMessages[toolErrorMsgIndex],
                        toolStatus: 'error',
                        toolErrorMessage: errorData.message,
                    };
                } else {
                     console.warn(`Received tool error for ${errorData.tool_name} but no matching running tool message found.`);
                     if (currentStreamingMsgIndex !== -1) {
                        newMessages[currentStreamingMsgIndex] = {
                           ...newMessages[currentStreamingMsgIndex],
                           content: newMessages[currentStreamingMsgIndex].content + `\n\n${errorMessage}`,
                           isStreaming: false,
                        };
                     } else {
                         const errorMsgId = streamingAssistantMsgIdRef.current || `error-${Date.now()}`;
                         if (!streamingAssistantMsgIdRef.current) {
                             streamingAssistantMsgIdRef.current = errorMsgId;
                         }
                         newMessages.push({
                             role: 'assistant',
                             content: errorMessage,
                             timestamp: errorMsgId,
                             type: 'error',
                             isStreaming: false,
                         });
                     }
                }
            } else {
                 if (currentStreamingMsgIndex !== -1) {
                   newMessages[currentStreamingMsgIndex] = {
                     ...newMessages[currentStreamingMsgIndex],
                     content: newMessages[currentStreamingMsgIndex].content + `\n\n${errorMessage}`,
                     isStreaming: false,
                     type: 'error'
                   };
                 } else {
                     const errorMsgId = streamingAssistantMsgIdRef.current || `error-${Date.now()}`;
                     if (!streamingAssistantMsgIdRef.current) {
                         streamingAssistantMsgIdRef.current = errorMsgId;
                     }
                     newMessages.push({
                         role: 'assistant',
                         content: errorMessage,
                         timestamp: errorMsgId,
                         type: 'error',
                         isStreaming: false,
                     });
                 }
            }
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
        return prevMessages;
      });
      setIsSending(false);
    };

    const handleChatClose: OnChatCloseCallback = () => {
      console.log("Chat EventSource closed.");
      setIsSending(false); 
      streamingAssistantMsgIdRef.current = null;
      closeEventSourceRef.current = null; 
    };

    // --- 调用新的 API ---
    if (activeChatId) {
      closeEventSourceRef.current = chatApi.sendMessage(
        activeChatId,
        messageToSend,
        handleChatEvent,
        handleChatError,
        handleChatClose,
        'user',
        userMessage.timestamp
      );
    } else {
      console.error("Cannot send message, activeChatId is null");
      setError("无法发送消息，没有活动的聊天。");
      setIsSending(false);
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
      setError(null);
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
      handleCancelRename();
      return;
    }
    const originalName = chatList.find(c => c.id === chatId)?.name;
    setIsLoadingList(true);
    try {
      console.log(`Renaming chat ${chatId} to: ${renameInputValue.trim()}`);
      setChatList(prevList => prevList.map(chat =>
        chat.id === chatId ? { ...chat, name: renameInputValue.trim() } : chat
      ));

      await chatApi.updateChat(chatId, { name: renameInputValue.trim() });
      await fetchChatList(flowId!);
      console.log("Chat renamed successfully");
      handleCancelRename();
    } catch (err: any) {
      console.error(`Failed to rename chat ${chatId}:`, err);
      setError(`重命名失败: ${err.message}`);
      setChatList(prevList => prevList.map(chat =>
        chat.id === chatId ? { ...chat, name: originalName || chat.name } : chat
      ));
      setIsLoadingList(false);
    }
  };


  const handleDeleteChat = (chatId: string) => {
    setChatToDelete(chatId);
    setShowDeleteConfirm(true);
  };

  const confirmDeleteChat = async () => {
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
  };

  const cancelDeleteChat = () => {
    setShowDeleteConfirm(false);
    setChatToDelete(null);
  };

  const handleStartEditMessage = (message: DisplayMessage) => {
    if (message.role === 'user' && message.timestamp) {
      if (closeEventSourceRef.current) {
        console.log("Starting edit: Closing previous EventSource.");
        closeEventSourceRef.current();
        closeEventSourceRef.current = null;
      }
      streamingAssistantMsgIdRef.current = null;
      // Remove any streaming assistant messages as we are starting a new interaction flow
      setMessages(prev => prev.filter(msg => !(msg.isStreaming && msg.role === 'assistant')));
      setInputMessage(''); // Clear main input when starting edit

      setEditingMessageTimestamp(message.timestamp);
      setEditingMessageContent(message.content);

      setTimeout(() => {
        const messageElement = document.getElementById(`message-${message.timestamp}`);
        if (messageElement) {
          // Try to scroll the message being edited into view if it's not fully visible.
          // 'nearest' will scroll only if it's not visible.
          messageElement.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        }
      }, 0);
    } else {
      console.warn("Cannot edit non-user message or message without timestamp/ID");
    }
  };

  const handleCancelEditMessage = () => {
    setEditingMessageTimestamp(null);
    setEditingMessageContent("");
  };

  const handleConfirmEditMessage = async () => {
    const originalMessageTimestampToEdit = editingMessageTimestamp;
    if (!originalMessageTimestampToEdit || !activeChatId || !flowId) {
        console.warn("handleConfirmEditMessage: Missing required IDs or content.");
        return;
    }

    if (closeEventSourceRef.current) {
      console.log("Confirming edit: Closing previous EventSource first (safety).", closeEventSourceRef.current);
      closeEventSourceRef.current();
      closeEventSourceRef.current = null;
    }

    setIsSending(true); 
    setError(null);
    
    const editedContent = editingMessageContent;

    setMessages(prevMessages => {
        const editMsgIndex = prevMessages.findIndex(msg => msg.timestamp === originalMessageTimestampToEdit);
        if (editMsgIndex === -1) {
            console.warn("Could not find message to edit in current UI state. Aborting UI update for edit.");
            return prevMessages;
        }
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

    const handleChatEvent: OnChatEventCallback = (event) => {
      console.log("Received SSE Event (after edit):", JSON.stringify(event));
      let capturedStreamEndId: string | null = null;
      if (event.type === 'stream_end') {
        capturedStreamEndId = streamingAssistantMsgIdRef.current;
      }
      setMessages(prevMessages => {
        const newMessages = [...prevMessages];
        const currentStreamingMsgIndex = newMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current && msg.type === 'text');

        switch (event.type) {
          case 'token':
            const token = event.data;
            const currentStreamingId = streamingAssistantMsgIdRef.current;
            const streamingMsgIndex = newMessages.findIndex(msg => msg.timestamp === currentStreamingId && msg.type === 'text');
            if (streamingMsgIndex !== -1) {
              newMessages[streamingMsgIndex] = {
                ...newMessages[streamingMsgIndex],
                content: newMessages[streamingMsgIndex].content + token,
                isStreaming: true,
              };
            } else {
              if (token) {
                const newAssistantMessageId = currentStreamingId || `assistant-token-${Date.now()}`;
                if (!currentStreamingId) streamingAssistantMsgIdRef.current = newAssistantMessageId;
                newMessages.push({
                  role: 'assistant', content: token, timestamp: newAssistantMessageId, type: 'text', isStreaming: true,
                });
              }
            }
            break;
          case 'tool_start':
            const toolStartMsgId = `tool-${event.data.name}-${Date.now()}`;
            const toolStartMessage: DisplayMessage = {
                 role: 'assistant', content: '', timestamp: toolStartMsgId, type: 'tool_status',
                 toolName: event.data.name, toolInput: event.data.input, toolStatus: 'running', isStreaming: false,
            };
            if (currentStreamingMsgIndex !== -1) newMessages.splice(currentStreamingMsgIndex, 0, toolStartMessage);
            else newMessages.push(toolStartMessage);
            break;
          case 'tool_end':
            const toolEndMsgIndex = newMessages.findLastIndex(msg =>
                msg.type === 'tool_status' && msg.toolName === event.data.name && msg.toolStatus === 'running'
            );
            if (toolEndMsgIndex !== -1) {
              newMessages[toolEndMsgIndex] = {
                ...newMessages[toolEndMsgIndex], toolStatus: 'completed', toolOutputSummary: event.data.output_summary,
              };
            } else {
                 const toolEndFallback: DisplayMessage = {
                     role: 'assistant', content: '', timestamp: `tool-end-fallback-${event.data.name}-${Date.now()}`,
                     type: 'tool_status', toolName: event.data.name, toolStatus: 'completed',
                     toolOutputSummary: event.data.output_summary, isStreaming: false
                 };
                 if (currentStreamingMsgIndex !== -1) newMessages.splice(currentStreamingMsgIndex, 0, toolEndFallback);
                 else newMessages.push(toolEndFallback);
            }
            break;
          case 'stream_end':
            const finishedMsgIndex = newMessages.findIndex(msg => msg.timestamp === capturedStreamEndId);
            if (finishedMsgIndex !== -1) {
              newMessages[finishedMsgIndex] = { ...newMessages[finishedMsgIndex], isStreaming: false };
            } else {
              const lastStreamingAssistantMsgIndex = newMessages.findLastIndex(msg => msg.role === 'assistant' && msg.isStreaming === true);
              if (lastStreamingAssistantMsgIndex !== -1) {
                newMessages[lastStreamingAssistantMsgIndex] = { ...newMessages[lastStreamingAssistantMsgIndex], isStreaming: false };
              }
            }
            break;
          case 'error':
            const errorData = event.data;
            const errorMessage = `错误 (阶段: ${errorData.stage || '未知'}): ${errorData.message}`;
            setError(errorMessage);
            if (errorData.tool_name) {
                const toolErrorMsgIndex = newMessages.findLastIndex(msg =>
                    msg.type === 'tool_status' && msg.toolName === errorData.tool_name && msg.toolStatus === 'running'
                );
                if (toolErrorMsgIndex !== -1) {
                    newMessages[toolErrorMsgIndex] = { ...newMessages[toolErrorMsgIndex], toolStatus: 'error', toolErrorMessage: errorData.message };
                } else {
                     if (currentStreamingMsgIndex !== -1) {
                        newMessages[currentStreamingMsgIndex] = { ...newMessages[currentStreamingMsgIndex], content: newMessages[currentStreamingMsgIndex].content + `\n\n${errorMessage}`, isStreaming: false };
                     } else {
                         const errorMsgId = streamingAssistantMsgIdRef.current || `error-${Date.now()}`;
                         if (!streamingAssistantMsgIdRef.current) streamingAssistantMsgIdRef.current = errorMsgId;
                         newMessages.push({ role: 'assistant', content: errorMessage, timestamp: errorMsgId, type: 'error', isStreaming: false });
                     }
                }
            } else {
                 if (currentStreamingMsgIndex !== -1) {
                   newMessages[currentStreamingMsgIndex] = { ...newMessages[currentStreamingMsgIndex], content: newMessages[currentStreamingMsgIndex].content + `\n\n${errorMessage}`, isStreaming: false, type: 'error' };
                 } else {
                     const errorMsgId = streamingAssistantMsgIdRef.current || `error-${Date.now()}`;
                     if (!streamingAssistantMsgIdRef.current) streamingAssistantMsgIdRef.current = errorMsgId;
                     newMessages.push({ role: 'assistant', content: errorMessage, timestamp: errorMsgId, type: 'error', isStreaming: false });
                 }
            }
            setIsSending(false);
            break;
          case 'ping':
             console.log("Received ping event from server (after edit).");
             break;
           case 'custom_edit_complete_no_sse' as any:
                console.log("Edit complete (no SSE), attempting to refresh chat messages from API response data.");
                const chatDataFromApi = event.data as Chat;
                const displayMessages = (chatDataFromApi.chat_data?.messages || []).map((msg): DisplayMessage => ({
                    ...msg,
                    type: 'text' 
                }));
                setIsSending(false);
                streamingAssistantMsgIdRef.current = null;
                return displayMessages.filter(msg => msg.timestamp !== assistantPlaceholder.timestamp);

          default:
            console.warn("Received unknown event type (after edit):", event);
        }
        return newMessages;
      });
    };

    const handleChatError: OnChatErrorCallback = (error) => {
      console.error("Chat API Error (after edit):", error);
      const errorMessage = error.message || "与服务器的连接出错 (编辑后)";
      setError(errorMessage);
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
        return prevMessages;
      });
      setIsSending(false);
    };

    const handleChatClose: OnChatCloseCallback = () => {
      console.log("Chat EventSource closed (after edit).");
      setIsSending(false); 
      streamingAssistantMsgIdRef.current = null; 
      closeEventSourceRef.current = null; 

      if (activeChatId) {
        fetchChatMessages(activeChatId);
      }
    };
    
    if (activeChatId) { 
        // 新增检查：如果 originalMessageTimestampToEdit 是一个原始的客户端临时ID，则阻止编辑
        if (originalMessageTimestampToEdit && originalMessageTimestampToEdit.startsWith('user-') && !originalMessageTimestampToEdit.startsWith('user-edited-')) {
            console.error("[ChatInterface] CRITICAL: Attempting to edit message with a client-side temporary ID that has not been confirmed by the server yet:", originalMessageTimestampToEdit);
            setError("消息尚未完全保存，请稍后再试。"); // Inform user
            setIsSending(false);
            // Clear the optimistic assistant message placeholder if it exists
            const assistantMsgId = streamingAssistantMsgIdRef.current;
            if (assistantMsgId) {
                 setMessages(prev => prev.filter(msg => msg.timestamp !== assistantMsgId));
            }
            streamingAssistantMsgIdRef.current = null;
            return;
        }

        if (originalMessageTimestampToEdit && originalMessageTimestampToEdit.startsWith('user-edited-')) {
            console.error("[ChatInterface] CRITICAL: Attempting to call editUserMessage with a temporary UI timestamp:", originalMessageTimestampToEdit);
            setError("编辑错误：内部时间戳问题，请重试。");
            setIsSending(false);
            const assistantMessageId = streamingAssistantMsgIdRef.current;
            if (assistantMessageId) {
                 setMessages(prev => prev.filter(msg => msg.timestamp !== assistantMessageId));
            }
            streamingAssistantMsgIdRef.current = null;
            return; 
        }
        console.log("[ChatInterface] Calling chatApi.editUserMessage with timestamp:", originalMessageTimestampToEdit, "and content:", editedContent);
        closeEventSourceRef.current = chatApi.editUserMessage(
            activeChatId,
            originalMessageTimestampToEdit,
            editedContent,
            handleChatEvent,
            handleChatError,
            handleChatClose
        );
    } else {
        console.error("Cannot confirm edit, activeChatId is null after UI updates.");
        setError("无法编辑消息，没有活动的聊天会话。");
        setIsSending(false);
        setMessages(prev => prev.filter(msg => msg.timestamp !== assistantPlaceholder.timestamp));
    }
  };

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
      const originalName = chatList.find(c => c.id === chatId)?.name;
      setIsLoadingList(true);
      try {
        console.log(`[Imperative] Renaming chat ${chatId} to: ${newName.trim()}`);
        await chatApi.updateChat(chatId, { name: newName.trim() });
        await fetchChatList(flowId!);
        console.log("[Imperative] Chat renamed successfully");
      } catch (err: any) {
        console.error(`[Imperative] Failed to rename chat ${chatId}:`, err);
        setError(`重命名失败: ${err.message}`);
      } finally {
        setIsLoadingList(false);
      }
    },
    deleteChat: async (chatId: string) => {
      handleDeleteChat(chatId);
    },
    selectChat: (chatId: string) => {
      handleSelectChat(chatId);
    }
  }));

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'row', padding: 1, gap: 1, overflow: 'hidden' }}>

      {/* ChatListPanel was here - Removed */}
      {/* <ChatListPanel
        chatList={chatList}
        activeChatId={activeChatId}
        isLoadingList={isLoadingList}
        isCreatingChat={isCreatingChat}
        isDeletingChatId={isDeletingChatId}
        isRenamingChatId={isRenamingChatId}
        error={error}
        flowId={flowId}
        onSelectChat={handleSelectChat}
        onStartRename={handleStartRename}
        onCancelRename={handleCancelRename}
        onConfirmRename={handleConfirmRename}
        onDeleteChat={handleDeleteChat}
        renameInputValue={renameInputValue}
        onRenameInputChange={setRenameInputValue}
      /> */}

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
          onConfirmEditMessage={handleConfirmEditMessage}
          onCancelEditMessage={handleCancelEditMessage}
        />
        
        <MessageInputBar
          inputMessage={inputMessage}
          inputDisabled={inputDisabled}
          isSending={isSending}
          editingMessageTimestamp={editingMessageTimestamp}
          onInputChange={setInputMessage}
          onSendMessage={handleSendMessage}
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
