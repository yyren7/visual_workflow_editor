// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useEffect, useRef } from 'react';
import { chatApi } from '../api/api';
import { Message } from '../types'; // Assuming Chat type might not be needed directly here anymore
import { Box, TextField, Button, Paper, Typography, CircularProgress } from '@mui/material';
import { Send as SendIcon, AddComment as AddCommentIcon } from '@mui/icons-material'; // Import AddCommentIcon

// 确保 flowId 只声明一次且类型正确
interface ChatInterfaceProps {
  flowId: string | undefined;
  chatId: string | null | undefined; // Allow null for explicitly no chat selected
  onChatCreated?: (newChatId: string) => void;
  onChatSelected?: (selectedChatId: string) => void; // Add for future use
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  flowId,
  chatId, // Use the chatId prop directly
  onChatCreated,
  // onChatSelected // Keep for future use
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false); // Loading messages
  const [isSending, setIsSending] = useState(false); // Sending a message
  const [isCreatingChat, setIsCreatingChat] = useState(false); // Creating a new chat
  const messagesEndRef = useRef<null | HTMLDivElement>(null);

  // Load chat messages when chatId prop changes
  useEffect(() => {
    const loadChat = async () => {
      if (chatId) {
        setIsLoading(true);
        setMessages([]); // Clear previous messages
        try {
          console.log("尝试加载聊天，chatId:", chatId);
          const chat = await chatApi.getChat(chatId);
          setMessages(chat.chat_data.messages || []);
        } catch (error) {
          console.error('Failed to load chat:', chatId, error);
          setMessages([]); // Ensure messages are cleared on error
          // Optionally: Notify parent component about the loading error
        } finally {
          setIsLoading(false);
        }
      } else {
        // No chatId provided, reset state
        setMessages([]);
        setIsLoading(false);
        // console.log("ChatInterface: No active chat ID provided.");
      }
    };

    loadChat();
  }, [chatId]); // Depend only on chatId prop

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !chatId || isSending || isCreatingChat || isLoading) return;

    setIsSending(true);
    const userMessage: Message = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    // Optimistic UI update
    setMessages(prev => [...prev, userMessage]);
    const messageToSend = inputMessage; // Store message before clearing
    setInputMessage('');

    try {
      // Send message to server
      const updatedChat = await chatApi.sendMessage(chatId, messageToSend);
      // Replace messages with the authoritative list from the server
      setMessages(updatedChat.chat_data.messages);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Revert optimistic update on error
      setMessages(prev => prev.filter(msg => msg !== userMessage));
      setInputMessage(messageToSend); // Restore input field
      // Optionally: Show error message to user
    } finally {
      setIsSending(false);
    }
  };

  const handleCreateNewChat = async () => {
    if (!flowId || isCreatingChat || isLoading) {
        console.warn("Cannot create chat: Missing flowId or already processing.", { flowId, isCreatingChat, isLoading });
        return;
    }

    setIsCreatingChat(true);
    try {
        console.log("尝试创建新聊天，flowId:", flowId);
        const newChat = await chatApi.createChat(flowId);
        console.log("新聊天已创建:", newChat);
        if (onChatCreated) {
            onChatCreated(newChat.id); // Notify parent to update the active chatId
        }
        // No need to manually set messages here, parent updates chatId prop,
        // which triggers the useEffect to load the new chat.
    } catch (error) {
        console.error('Failed to create new chat:', error);
        // Optionally: Show error message to user
    } finally {
        setIsCreatingChat(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const hasActiveChat = !!chatId;
  const isDisabled = isLoading || isSending || isCreatingChat; // Combined disabled state

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 1 /* Add padding */ }}>
      {/* Messages Area */}
      <Paper
        elevation={2} // Slightly reduced elevation
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 2,
          mb: 1, // Reduced margin
          backgroundColor: '#ffffff', // White background
          position: 'relative', // Needed for overlaying messages/buttons
        }}
      >
        {isLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <CircularProgress />
            </Box>
        )}
        {!isLoading && messages.length === 0 && !hasActiveChat && (
             <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', textAlign: 'center', p: 2 }}>
                <Typography variant="h6" gutterBottom>没有活动的聊天</Typography>
                <Button
                    variant="contained"
                    startIcon={<AddCommentIcon />}
                    onClick={handleCreateNewChat}
                    disabled={!flowId || isCreatingChat} // Disable if no flowId or busy
                 >
                    {isCreatingChat ? "正在创建..." : "创建新聊天"}
                 </Button>
                 {!flowId && <Typography variant="caption" color="error" sx={{ mt: 1 }}>需要先选择一个流程图</Typography>}
             </Box>
        )}
         {!isLoading && messages.length === 0 && hasActiveChat && (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <Typography color="text.secondary">开始对话吧！</Typography>
            </Box>
        )}
        {!isLoading && messages.length > 0 && messages.map((message, index) => (
          <Box
            key={message.timestamp + '-' + index} // Use a more robust key if possible
            sx={{
              display: 'flex',
              justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              mb: 1.5 // Slightly increased margin between messages
            }}
          >
            <Paper
              elevation={1}
              sx={{
                p: '10px 14px', // Adjusted padding
                maxWidth: '80%', // Slightly wider max width
                borderRadius: message.role === 'user' ? '15px 15px 5px 15px' : '15px 15px 15px 5px', // Chat bubble shape
                backgroundColor: message.role === 'user' ? 'primary.main' : '#e0e0e0', // Use theme primary color
                color: message.role === 'user' ? 'primary.contrastText' : 'text.primary', // Contrast text color
                wordBreak: 'break-word', // Ensure long words break
              }}
            >
              <Typography variant="body1" component="div" sx={{ whiteSpace: 'pre-wrap' }}> {/* Use pre-wrap for newlines */}
                {message.content}
              </Typography>
              {/* Optional: Timestamp display */}
              {/* <Typography variant="caption" sx={{ display: 'block', textAlign: 'right', opacity: 0.7, mt: 0.5 }}>
                {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Typography> */}
            </Paper>
          </Box>
        ))}
        <div ref={messagesEndRef} />
      </Paper>

      {/* Input Area - Only show if there is an active chat or possibility to create one */}
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1, mt: 'auto', padding: '8px 0' }}>
            <TextField
              fullWidth
              multiline
              minRows={1} // Start with 1 row
              maxRows={5} // Allow expansion up to 5 rows
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={hasActiveChat ? "输入消息 (Shift+Enter 换行)" : "请先创建或选择一个聊天"}
              disabled={!hasActiveChat || isDisabled} // Disable if no chat or busy
              sx={{
                 backgroundColor: '#ffffff',
                 borderRadius: '20px', // Rounded corners
                 '& .MuiOutlinedInput-root': {
                     borderRadius: '20px',
                     padding: '10px 15px', // Adjust padding
                     '& fieldset': {
                         border: 'none', // Remove border
                     },
                     '&:hover fieldset': {
                        // border: 'none', // Keep borderless on hover
                     },
                     '&.Mui-focused fieldset': {
                        // border: 'none', // Keep borderless on focus
                     },
                 },
              }}
            />
            <Button
              variant="contained"
              onClick={handleSendMessage}
              disabled={!hasActiveChat || !inputMessage.trim() || isDisabled} // Also disable if input is empty
              sx={{
                 minWidth: 'auto', // Allow button to shrink
                 padding: '10px', // Square padding
                 borderRadius: '50%', // Make it circular
                 height: '48px', // Match typical input height
                 width: '48px',
              }}
              aria-label="发送消息"
            >
              {isSending ? <CircularProgress size={24} color="inherit"/> : <SendIcon />}
            </Button>
        </Box>

    </Box>
  );
};

export default ChatInterface;