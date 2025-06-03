import React, { useRef, useEffect } from 'react';
import {
  Box, Paper, Typography, CircularProgress, Button, IconButton, Tooltip, Grow
} from '@mui/material';
import {
    Edit as EditIcon,
    Check as CheckIcon,
    Close as CloseIcon
} from '@mui/icons-material';
import { DisplayMessage } from './chatTypes';
import EditMessageForm from './EditMessageForm';

interface ChatMessageAreaProps {
  messages: DisplayMessage[];
  activeChatId: string | null;
  isLoadingChat: boolean;
  editingMessageTimestamp: string | null;
  editingMessageContent: string;
  isSending: boolean;
  onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
  onStartEditMessage: (message: DisplayMessage) => void;
  onEditingContentChange: (content: string) => void;
  onConfirmEditMessage: () => void;
  onCancelEditMessage: () => void;
}

const ChatMessageArea: React.FC<ChatMessageAreaProps> = ({
  messages,
  activeChatId,
  isLoadingChat,
  editingMessageTimestamp,
  editingMessageContent,
  isSending,
  onNodeSelect,
  onStartEditMessage,
  onEditingContentChange,
  onConfirmEditMessage,
  onCancelEditMessage,
}) => {
  const messagesEndRef = useRef<null | HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const internalRenderMessageContent = (message: DisplayMessage) => {
    // This function is now internal to ChatMessageArea
    // It was previously in ChatInterface.tsx
    // Note: This function might need access to `editingMessageTimestamp`, `editingMessageContent`,
    // `setEditingMessageContent`, `handleConfirmEditMessage`, `handleCancelEditMessage`
    // if the editing UI is also moved here. For now, we assume editing UI might be separate or passed differently.

    if (message.type === 'tool_status') {
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
        return <Typography color="error" sx={{ fontWeight: 400 }}>{message.content}</Typography>;
    }

    // Editing UI is NOT part of this initial ChatMessageArea. 
    // It will remain in ChatInterface or be a separate component for now.
    // if (editingMessageTimestamp === message.timestamp) { ... }

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
                  sx={{ p: 0, minWidth: 'auto', verticalAlign: 'baseline', textTransform: 'none', display: 'inline', lineHeight: 'inherit', fontWeight: 400 }}
                >
                  (Node: {nodeId})
                </Button>
              );
            }
            return <span key={index} style={{ whiteSpace: 'pre-wrap', fontWeight: 400 }}>{part}</span>;
          })}
          {message.isStreaming && message.type === 'text' && <CircularProgress size={12} sx={{ ml: 1, verticalAlign: 'middle' }} />}
        </>
      );
  };

  const hasActiveChat = !!activeChatId;

  return (
    <Paper
      elevation={0}
      sx={{
        flex: 1,
        overflow: 'auto',
        p: 2,
        mb: 1,
        backgroundColor: '#f3f4f6',
        position: 'relative',
        scrollBehavior: 'smooth',
        overscrollBehaviorY: 'contain',
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
          <Typography variant="h6" gutterBottom sx={{ color: 'black', fontWeight: 600 }}>请选择或创建聊天</Typography>
          <Typography sx={{ color: '#4b5563', fontWeight: 300 }}>从左侧侧边栏选择一个聊天，或点击"新建聊天"开始。</Typography>
        </Box>
      )}
      {!isLoadingChat && hasActiveChat && messages.length === 0 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Typography sx={{ color: '#4b5563', fontWeight: 300 }}>开始对话吧！</Typography>
        </Box>
      )}
      {!isLoadingChat && messages.length > 0 && messages.map((message, index) => (
        <Grow in={true} key={`grow-${message.timestamp}`} timeout={500}>
          <Box
            key={message.timestamp}
            id={`message-${message.timestamp}`}
            sx={{
              display: 'flex',
              justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              mb: 1.5,
              ...(message.role === 'user' && { position: 'relative' }) 
            }}
          >
            <Paper
              elevation={0}
              sx={{
                paddingTop: 1.5,
                paddingBottom: 1.5,
                paddingLeft: 1.5,
                paddingRight: message.role === 'user' ? 4.5 : 1.5,
                borderRadius: '16px',
                background: message.role === 'user' 
                  ? 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' 
                  : '#ffffff',
                color: message.role === 'user' ? 'white' : 'black',
                boxShadow: message.role === 'user' 
                  ? '0 2px 8px rgba(37, 99, 235, 0.3)' 
                  : '0 2px 8px rgba(0, 0, 0, 0.08)',
                maxWidth: '80%',
                wordWrap: 'break-word',
                whiteSpace: 'pre-wrap',
                position: 'relative',
              }}
            >
              {editingMessageTimestamp === message.timestamp && message.role === 'user' ? (
                <EditMessageForm
                  editingMessageContent={editingMessageContent}
                  isSending={isSending}
                  onContentChange={onEditingContentChange}
                  onConfirmEdit={onConfirmEditMessage}
                  onCancelEdit={onCancelEditMessage}
                />
              ) : (
                internalRenderMessageContent(message)
              )}
              {message.role === 'user' && 
               message.timestamp && 
               !message.timestamp.startsWith('user-edited-') &&
               editingMessageTimestamp !== message.timestamp &&
               (
                <Tooltip title="编辑此消息">
                  <IconButton
                    size="small"
                    onClick={() => onStartEditMessage(message)}
                    sx={{
                      position: 'absolute',
                      top: '4px',
                      right: '4px',
                      width: 24,
                      height: 24,
                      color: 'primary.contrastText',
                      backgroundColor: 'rgba(0,0,0,0.1)',
                      '&:hover': {
                        backgroundColor: 'rgba(0,0,0,0.2)',
                      }
                    }}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </Paper>
          </Box>
        </Grow>
      ))}
      <div ref={messagesEndRef} />
    </Paper>
  );
};

export default ChatMessageArea; 