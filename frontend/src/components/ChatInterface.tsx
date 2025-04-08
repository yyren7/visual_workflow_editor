// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useEffect, useRef } from 'react';
import { chatApi } from '../api/api';
import { Message, Chat } from '../types';
import { Box, TextField, Button, Paper, Typography, CircularProgress } from '@mui/material';
import { Send as SendIcon } from '@mui/icons-material';

interface ChatInterfaceProps {
  flowId: number;
  chatId?: number;
  onChatCreated?: (chatId: number) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  flowId,
  chatId,
  onChatCreated
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentChatId, setCurrentChatId] = useState<number | undefined>(chatId);
  const messagesEndRef = useRef<null | HTMLDivElement>(null);

  // 初始化聊天
  useEffect(() => {
    const initializeChat = async () => {
      if (currentChatId) {
        try {
          const chat = await chatApi.getChat(currentChatId);
          setMessages(chat.chat_data.messages || []);
        } catch (error) {
          console.error('Failed to load chat:', error);
        }
      } else {
        try {
          const newChat = await chatApi.createChat(flowId);
          setCurrentChatId(newChat.id);
          if (onChatCreated) {
            onChatCreated(newChat.id);
          }
        } catch (error) {
          console.error('Failed to create chat:', error);
        }
      }
    };

    initializeChat();
  }, [flowId, currentChatId, onChatCreated]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !currentChatId) return;

    setIsLoading(true);
    try {
      // 添加用户消息到界面
      const userMessage: Message = {
        role: 'user',
        content: inputMessage,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, userMessage]);
      setInputMessage('');

      // 发送消息到服务器
      const updatedChat = await chatApi.sendMessage(currentChatId, inputMessage);
      setMessages(updatedChat.chat_data.messages);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 消息列表 */}
      <Paper
        elevation={3}
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 2,
          mb: 2,
          backgroundColor: '#f5f5f5'
        }}
      >
        {messages.map((message, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              mb: 2
            }}
          >
            <Paper
              elevation={1}
              sx={{
                p: 2,
                maxWidth: '70%',
                backgroundColor: message.role === 'user' ? '#e3f2fd' : '#fff'
              }}
            >
              <Typography variant="body1">{message.content}</Typography>
              <Typography variant="caption" color="text.secondary">
                {new Date(message.timestamp).toLocaleTimeString()}
              </Typography>
            </Paper>
          </Box>
        ))}
        <div ref={messagesEndRef} />
      </Paper>

      {/* 输入区域 */}
      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="输入消息..."
          disabled={isLoading}
          sx={{ backgroundColor: '#fff' }}
        />
        <Button
          variant="contained"
          onClick={handleSendMessage}
          disabled={isLoading || !inputMessage.trim()}
          sx={{ minWidth: 100 }}
        >
          {isLoading ? <CircularProgress size={24} /> : <SendIcon />}
        </Button>
      </Box>
    </Box>
  );
};

export default ChatInterface;