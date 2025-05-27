// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  chatApi,
  JsonChatResponse,
  ChatEvent,
  OnChatEventCallback,
  OnChatErrorCallback,
  OnChatCloseCallback,
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

// Interface for messages, updated for new event structure
interface DisplayMessage extends Message {
  type: 'text' | 'tool_status' | 'error'; // Refined types
  isStreaming?: boolean; // Indicate if assistant text message is currently streaming

  // Fields for tool status messages
  toolName?: string;
  toolInput?: any;
  toolOutputSummary?: string;
  toolStatus?: 'running' | 'completed' | 'error'; // Status of the tool call
  toolErrorMessage?: string; // Specific error message for a tool failure
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
    // Remove specific handling for old 'tool_card' type
    // if (message.type === 'tool_card' && message.toolInfo) {
    //   markdown += `**[Tool Execution Card]**\n`;
    //   markdown += `* Summary: ${message.toolInfo.summary || 'N/A'}\n`;
    //   if (message.toolInfo.tool_calls_info) {
    //     markdown += `* Calls: ${JSON.stringify(message.toolInfo.tool_calls_info)}\n`;
    //   }
    //   if (message.toolInfo.tool_results_info) {
    //     markdown += `* Results: ${JSON.stringify(message.toolInfo.tool_results_info)}\n`;
    //   }
    //   if (message.toolInfo.error) {
    //     markdown += `* Error: ${message.toolInfo.error}\n`;
    //   }
    //   markdown += `\n`;
    // } else {
    //   markdown += `${message.content}\n\n`;
    // }
    // Render base content (might need refinement for tool_status later)
    if (message.type === 'tool_status') {
         markdown += `**[Tool: ${message.toolName || 'Unknown'}]** - Status: ${message.toolStatus}${message.toolOutputSummary ? '\nOutput: ' + message.toolOutputSummary : ''}${message.toolErrorMessage ? '\nError: ' + message.toolErrorMessage : ''}\n\n`;
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

      // If it's a stream_end event, capture the ID *now*, before the setMessages callback is even queued or executed.
      let capturedStreamEndId: string | null = null;
      if (event.type === 'stream_end') {
        capturedStreamEndId = streamingAssistantMsgIdRef.current;
        console.log(`[ChatInterface stream_end event] Captured streamingAssistantMsgIdRef: ${capturedStreamEndId}`); // Diagnostic log
      }

      setMessages(prevMessages => {
        // const currentStreamingMsgIndex = prevMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current);
        const newMessages = [...prevMessages]; // Create mutable copy
        const currentStreamingMsgIndex = newMessages.findIndex(msg => msg.timestamp === streamingAssistantMsgIdRef.current && msg.type === 'text');
        // console.log("Found streaming index:", currentStreamingMsgIndex);

        // if (currentStreamingMsgIndex === -1 && event.type !== 'final_result' && event.type !== 'error') {
        //   console.warn(`Received event type ${event.type} but no streaming message ref found.`);
        //   return prevMessages;
        // }
        // Allow events even if no streaming message ref exists yet (e.g., first token or tool call)

        // const newMessages = [...prevMessages];

        switch (event.type) {
          case 'token':
            const token = event.data;
            // Capture ref value before async update
            const currentStreamingId = streamingAssistantMsgIdRef.current;
            const streamingMsgIndex = newMessages.findIndex(msg => msg.timestamp === currentStreamingId && msg.type === 'text');

            if (streamingMsgIndex !== -1) {
              // Append token to existing streaming message
              newMessages[streamingMsgIndex] = {
                ...newMessages[streamingMsgIndex],
                content: newMessages[streamingMsgIndex].content + token,
                isStreaming: true, // Keep streaming flag
              };
            } else {
              // If no streaming message exists, create it ONLY if token is not empty
              if (token) {
                const assistantMessageId = currentStreamingId || `assistant-${Date.now()}`;
                if (!currentStreamingId) {
                    streamingAssistantMsgIdRef.current = assistantMessageId; // Update ref if it was null
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

          // case 'final_result': // Removed
          //    const finalData = event.data;
          //    ...
          //   break;
          case 'tool_start':
            // Insert a new message indicating the tool call is starting
            const toolStartMsgId = `tool-${event.data.name}-${Date.now()}`;
            const toolStartMessage: DisplayMessage = {
                 role: 'assistant', // Rendered as assistant message for flow
                 content: '', // No main text content
                 timestamp: toolStartMsgId,
                 type: 'tool_status',
                 toolName: event.data.name,
                 toolInput: event.data.input,
                 toolStatus: 'running',
                 isStreaming: false, // This message itself isn't streaming text
            };
            // Insert *before* the current text streaming message if it exists
            if (currentStreamingMsgIndex !== -1) {
                newMessages.splice(currentStreamingMsgIndex, 0, toolStartMessage);
            } else {
                newMessages.push(toolStartMessage); // Append if no text stream yet
            }
            break;

          case 'tool_end':
            // Find the *last* running tool message with the matching name
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
                 // Optionally add a new completed tool message as fallback?
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
            // 'newMessages' is from the outer 'setMessages' scope: const newMessages = [...prevMessages];
            // 'capturedStreamEndId' was captured when the 'stream_end' event first arrived.
            const finishedMsgIndex = newMessages.findIndex(msg => msg.timestamp === capturedStreamEndId);

            if (finishedMsgIndex !== -1) {
              newMessages[finishedMsgIndex] = {
                ...newMessages[finishedMsgIndex],
                isStreaming: false
              };
              console.log(`[ChatInterface stream_end] Marked message with ID '${capturedStreamEndId}' as not streaming.`);
            } else { // finishedMsgIndex === -1, meaning message with capturedStreamEndId was not found
              if (capturedStreamEndId) {
                // The ref had a value, but it wasn't found in the messages array.
                console.warn(`[ChatInterface stream_end] Message with ref ID '${capturedStreamEndId}' not found. Attempting to mark last streaming assistant message.`);
              } else {
                // The ref was already null when the stream_end event was initially processed.
                console.warn("[ChatInterface stream_end] Streaming message reference was already null when 'stream_end' event was received. Attempting to mark last streaming assistant message.");
              }

              // Attempt to find and mark the absolutely last assistant message that is still marked as streaming.
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
            break; // Break from switch
          case 'error':
            console.error("Received error event:", event.data); // Log the full data object
            const errorData = event.data;
            const errorMessage = `错误 (阶段: ${errorData.stage || '未知'}): ${errorData.message}`;
            setError(errorMessage); // Set global error state

            if (errorData.tool_name) {
                // Find the running tool message to mark as error
                const toolErrorMsgIndex = newMessages.findLastIndex(msg =>
                    msg.type === 'tool_status' &&
                    msg.toolName === errorData.tool_name &&
                    msg.toolStatus === 'running'
                );
                if (toolErrorMsgIndex !== -1) {
                    newMessages[toolErrorMsgIndex] = {
                        ...newMessages[toolErrorMsgIndex],
                        toolStatus: 'error',
                        toolErrorMessage: errorData.message, // Store specific message
                    };
                } else {
                     console.warn(`Received tool error for ${errorData.tool_name} but no matching running tool message found.`);
                     // Add a generic error message instead
                     if (currentStreamingMsgIndex !== -1) {
                        newMessages[currentStreamingMsgIndex] = {
                           ...newMessages[currentStreamingMsgIndex],
                           content: newMessages[currentStreamingMsgIndex].content + `\n\n${errorMessage}`,
                           isStreaming: false,
                        };
                     } else {
                         // Add a new error message block if no streaming message
                         const errorMsgId = streamingAssistantMsgIdRef.current || `error-${Date.now()}`;
                         if (!streamingAssistantMsgIdRef.current) {
                             streamingAssistantMsgIdRef.current = errorMsgId; // Use ref for consistency
                         }
                         newMessages.push({
                             role: 'assistant', // Render as assistant
                             content: errorMessage,
                             timestamp: errorMsgId,
                             type: 'error', // Use specific error type
                             isStreaming: false,
                         });
                     }
                }
            } else {
                 // General error, append to streaming message or add new one
                 if (currentStreamingMsgIndex !== -1) {
                   newMessages[currentStreamingMsgIndex] = {
                     ...newMessages[currentStreamingMsgIndex],
                     content: newMessages[currentStreamingMsgIndex].content + `\n\n${errorMessage}`,
                     isStreaming: false, // Stop streaming on error
                     type: 'error' // Mark message as error type? Or keep text?
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
            setIsSending(false); // Stop sending indicator on error
            // No need to clear ref here, handleChatClose does it
            break;
          case 'ping':
             console.log("Received ping event from server.");
             break;
          default:
            // Use exhaustiveness check helper if possible, or log warning
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
      // No longer need to update isStreaming here, stream_end handles it.
      // setMessages(prevMessages => { ... }); 
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

  // --- 编辑消息处理函数 (更新版本) ---
  const handleStartEditMessage = (message: DisplayMessage) => {
    if (message.role === 'user' && message.timestamp) {
      // --- 关闭任何正在进行的流 --- 
      if (closeEventSourceRef.current) {
        console.log("Starting edit: Closing previous EventSource.");
        closeEventSourceRef.current();
        closeEventSourceRef.current = null;
      }
      // --- 清理流式助手消息引用 --- 
      streamingAssistantMsgIdRef.current = null;
      // --- 移除任何流式占位符 ---
      setMessages(prev => prev.filter(msg => !(msg.isStreaming && msg.role === 'assistant')));
      setInputMessage(''); // <--- 清空主输入框

      setEditingMessageTimestamp(message.timestamp);
      setEditingMessageContent(message.content);
    } else {
      console.warn("Cannot edit non-user message or message without timestamp/ID");
    }
  };

  const handleCancelEditMessage = () => {
    setEditingMessageTimestamp(null);
    setEditingMessageContent("");
  };

  const handleConfirmEditMessage = async () => {
    const originalMessageTimestampToEdit = editingMessageTimestamp; // Capture before clearing state
    if (!originalMessageTimestampToEdit || !activeChatId || !flowId) {
        console.warn("handleConfirmEditMessage: Missing required IDs or content.");
        return;
    }

    // --- 先关闭可能存在的旧连接 (以防万一) ---
    if (closeEventSourceRef.current) {
      console.log("Confirming edit: Closing previous EventSource first (safety).", closeEventSourceRef.current);
      closeEventSourceRef.current();
      closeEventSourceRef.current = null;
    }
    // -----------------------------

    setIsSending(true); 
    setError(null);
    
    const editedContent = editingMessageContent; // Capture before clearing editingMessageContent

    // 1. 更新UI: 立即移除正在编辑的消息及其之后的所有消息，然后添加编辑后的用户消息。
    //    这样用户会立刻看到编辑的结果。后续AI的回复将通过SSE流入。
    setMessages(prevMessages => {
        const editMsgIndex = prevMessages.findIndex(msg => msg.timestamp === originalMessageTimestampToEdit);
        if (editMsgIndex === -1) {
            console.warn("Could not find message to edit in current UI state. Aborting UI update for edit.");
            return prevMessages; // Or handle error more gracefully
        }
        // 保留编辑点之前的所有消息
        const newMessages = prevMessages.slice(0, editMsgIndex);
        // 添加编辑后的用户消息 (用新的临时时间戳以避免key冲突，后端会生成真实的)
        newMessages.push({
            role: 'user',
            content: editedContent,
            timestamp: `user-edited-${Date.now()}`,
            type: 'text'
        });
        return newMessages;
    });

    // 2. 清理编辑状态
    setEditingMessageTimestamp(null);
    setEditingMessageContent("");

    // 3. 添加AI助手消息的占位符 (与 handleSendMessage 类似)
    const assistantMessageId = `assistant-after-edit-${Date.now()}`;
    streamingAssistantMsgIdRef.current = assistantMessageId; // 更新流式消息ID的引用
    const assistantPlaceholder: DisplayMessage = {
      role: 'assistant',
      content: '', 
      timestamp: assistantMessageId,
      type: 'text',
      isStreaming: true 
    };
    setMessages(prev => [...prev, assistantPlaceholder]); // Append placeholder to the new message list

    // 4. 定义 SSE 回调 (这些回调与 handleSendMessage 中的回调几乎完全相同)
    //    可以考虑将这些回调提取到 ChatInterface 组件的顶层作用域，如果它们完全一样的话。
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
           // Handling 'custom_edit_complete_no_sse' from chatApi if backend PUT doesn't return 202
           // This case assumes the API directly returned the updated Chat object.
           case 'custom_edit_complete_no_sse' as any: // Type assertion for custom event
                console.log("Edit complete (no SSE), attempting to refresh chat messages from API response data.");
                const chatDataFromApi = event.data as Chat; // Assuming event.data is the Chat object
                const displayMessages = (chatDataFromApi.chat_data?.messages || []).map((msg): DisplayMessage => ({
                    ...msg,
                    type: 'text' 
                }));
                setIsSending(false);
                streamingAssistantMsgIdRef.current = null; // No stream happened
                // Directly set messages, then remove the placeholder as no streaming will occur
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

      // NEW: Fetch updated messages to reflect permanent timestamp for edited message
      if (activeChatId) {
        fetchChatMessages(activeChatId);
      }
    };
    
    // 5. 调用 API
    if (activeChatId) { 
        if (originalMessageTimestampToEdit && originalMessageTimestampToEdit.startsWith('user-edited-')) {
            console.error("[ChatInterface] CRITICAL: Attempting to call editUserMessage with a temporary UI timestamp:", originalMessageTimestampToEdit);
            setError("编辑错误：内部时间戳问题，请重试。");
            setIsSending(false);
            // Clean up placeholder if it was added
            const assistantMessageId = streamingAssistantMsgIdRef.current; // Get current ref before clearing
            if (assistantMessageId) {
                 setMessages(prev => prev.filter(msg => msg.timestamp !== assistantMessageId));
            }
            streamingAssistantMsgIdRef.current = null; // Clear ref as well
            return; 
        }
        console.log("[ChatInterface] Calling chatApi.editUserMessage with timestamp:", originalMessageTimestampToEdit, "and content:", editedContent);
        closeEventSourceRef.current = chatApi.editUserMessage(
            activeChatId,
            originalMessageTimestampToEdit, // Use the original timestamp for the PUT request
            editedContent, // The new content from the input field
            handleChatEvent, // Standard SSE event handler
            handleChatError, // Standard SSE error handler
            handleChatClose  // Standard SSE close handler
        );
    } else {
        console.error("Cannot confirm edit, activeChatId is null after UI updates.");
        setError("无法编辑消息，没有活动的聊天会话。");
        setIsSending(false);
        // Clean up placeholder if API call wasn't made
        setMessages(prev => prev.filter(msg => msg.timestamp !== assistantPlaceholder.timestamp));
    }
  };
  // --- 结束新增 ---

  // --- Render Logic ---
  const hasActiveChat = !!activeChatId;
  const inputDisabled = !hasActiveChat || isSending || isLoadingChat || isLoadingList || isCreatingChat;

  // --- Rendering Logic (Needs update for clickable nodes) ---
  // --- Rendering Logic (Updated for tool_status) ---
  const renderMessageContent = (message: DisplayMessage) => {
    // Ensure old 'tool_card' logic is completely removed
    // if (message.type === 'tool_card' && message.toolInfo) { ... }

    if (message.type === 'tool_status') {
        // ... (rendering logic for tool_status remains the same as previous edit) ...
        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {message.toolStatus === 'running' && <CircularProgress size={16} />}
                {message.toolStatus === 'completed' && <CheckIcon fontSize="small" color="success" />}
                {message.toolStatus === 'error' && <CloseIcon fontSize="small" color="error" />}
                <Typography variant="body2" component="span" sx={{ fontWeight: 'bold' }}>
                  Tool: {message.toolName || 'Unknown Tool'}
                </Typography>
                <Typography variant="caption" component="span">
                  ({message.toolStatus})
                </Typography>
              </Box>
              {message.toolStatus === 'completed' && message.toolOutputSummary && (
                <Typography variant="body2" sx={{ pl: 3, whiteSpace: 'pre-wrap' }}>
                  Output: {message.toolOutputSummary}
                </Typography>
              )}
               {message.toolStatus === 'error' && message.toolErrorMessage && (
                <Typography variant="body2" color="error" sx={{ pl: 3, whiteSpace: 'pre-wrap' }}>
                  Error: {message.toolErrorMessage}
                </Typography>
              )}
            </Box>
          );
    }

    if (message.type === 'error') {
        // ... (rendering logic for error remains the same) ...
        return <Typography color="error">{message.content}</Typography>;
    }

    // --- 新增：处理正在编辑的消息 ---
    if (editingMessageTimestamp === message.timestamp) {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, width: '100%' }}>
          <TextField
            fullWidth
            multiline
            value={editingMessageContent}
            onChange={(e) => setEditingMessageContent(e.target.value)}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleConfirmEditMessage();
              }
              if (e.key === 'Escape') {
                handleCancelEditMessage();
              }
            }}
            sx={{ 
              backgroundColor: 'white', 
              borderRadius: '4px',
              '.MuiInputBase-input': {
                color: 'black', // 确保文本颜色为黑色
              }
            }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button size="small" variant="outlined" onClick={handleCancelEditMessage}>取消</Button>
            <Button size="small" variant="contained" onClick={handleConfirmEditMessage} disabled={isSending}>
              {isSending ? <CircularProgress size={20}/> : "保存"}
            </Button>
          </Box>
        </Box>
      );
    }
    // --- 结束新增 ---

    // Default to text rendering logic
    // ... (rendering logic for text remains the same) ...
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
            return <span key={index} style={{ whiteSpace: 'pre-wrap'}}>{part}</span>;
          })}
          {message.isStreaming && message.type === 'text' && <CircularProgress size={12} sx={{ ml: 1, verticalAlign: 'middle' }} />}
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
            ...(!hasActiveChat && {
              opacity: 0.6,
            }),
          }}
        >
          {isLoadingChat && (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <CircularProgress />
            </Box>
          )}
          {!isLoadingChat && !hasActiveChat && (
            <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', textAlign: 'center', p: 2 }}>
              <Typography variant="h6" gutterBottom sx={{ color: 'black' }}>请选择或创建聊天</Typography>
              <Typography color="black">从左侧侧边栏选择一个聊天，或点击"新建聊天"开始。</Typography>
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
                  position: 'relative', // Needed for positioning the edit button
                }}
              >
                {renderMessageContent(message)}
                {/* --- 新增：用户消息的编辑按钮 --- */}
                {message.role === 'user' && 
                 message.timestamp && 
                 !message.timestamp.startsWith('user-edited-') &&
                 !editingMessageTimestamp && (
                  <Tooltip title="编辑此消息">
                    <IconButton 
                      size="small"
                      onClick={() => handleStartEditMessage(message)}
                      sx={{
                        position: 'absolute',
                        top: 0,
                        right: 0,
                        color: 'primary.contrastText', // Or a color that contrasts well with primary.light
                        backgroundColor: 'rgba(0,0,0,0.1)', // Slight background for visibility
                        '&:hover': {
                          backgroundColor: 'rgba(0,0,0,0.2)',
                        }
                      }}
                    >
                      <EditIcon fontSize="inherit" />
                    </IconButton>
                  </Tooltip>
                )}
                {/* --- 结束新增 --- */}
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
            disabled={inputDisabled || !!editingMessageTimestamp} // 编辑时禁用主输入框
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
