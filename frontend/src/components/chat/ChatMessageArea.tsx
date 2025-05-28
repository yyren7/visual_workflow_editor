import React, { useRef, useEffect } from 'react';
import {
  Box, Paper, Typography, CircularProgress, Button, IconButton, Tooltip
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
        return <Typography color="error">{message.content}</Typography>;
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

  const hasActiveChat = !!activeChatId;

  return (
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
          key={message.timestamp}
          id={`message-${message.timestamp}`} // Keep ID for potential scrolling to edited message
          sx={{
            display: 'flex',
            justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
            mb: 1.5,
            // Add a specific class or style for user messages if needed for edit icon positioning
            ...(message.role === 'user' && { position: 'relative' }) 
          }}
        >
          <Paper
            elevation={1}
            sx={{
              p: 1.5,
              borderRadius: '10px',
              bgcolor: message.role === 'user' ? 'primary.light' : 'grey.200',
              color: message.role === 'user' ? 'primary.contrastText' : 'black',
              maxWidth: '80%',
              wordWrap: 'break-word',
              whiteSpace: 'pre-wrap',
              position: 'relative', // Keep for potential absolute positioned elements within (like edit icon)
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
             editingMessageTimestamp !== message.timestamp && // Condition to hide edit icon when this specific message is being edited
             (
              <Tooltip title="编辑此消息">
                <IconButton 
                  size="small"
                  onClick={() => onStartEditMessage(message)}
                  sx={{
                    position: 'absolute',
                    top: 0,
                    right: 0,
                    color: 'primary.contrastText',
                    backgroundColor: 'rgba(0,0,0,0.1)',
                    '&:hover': {
                      backgroundColor: 'rgba(0,0,0,0.2)',
                    }
                  }}
                >
                  <EditIcon fontSize="inherit" />
                </IconButton>
              </Tooltip>
            )}
          </Paper>
        </Box>
      ))}
      <div ref={messagesEndRef} />
    </Paper>
  );
};

export default ChatMessageArea; 