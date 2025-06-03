import React from 'react';
import {
  Box, TextField, Button, CircularProgress
} from '@mui/material';
import {
  Send as SendIcon
} from '@mui/icons-material';

interface MessageInputBarProps {
  inputMessage: string;
  inputDisabled: boolean;
  isSending: boolean;
  editingMessageTimestamp: string | null; // To disable input when editing
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
  onKeyPress: (event: React.KeyboardEvent) => void;
  hasActiveChat: boolean;
}

const MessageInputBar: React.FC<MessageInputBarProps> = ({
  inputMessage,
  inputDisabled,
  isSending,
  editingMessageTimestamp,
  onInputChange,
  onSendMessage,
  onKeyPress,
  hasActiveChat
}) => {
  return (
    <Box sx={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: 1,
      mt: 'auto', 
      padding: '12px 16px',
      borderTop: '1px solid #e0e0e0',
    }}>
      <TextField
        fullWidth
        multiline
        minRows={1}
        maxRows={5}
        value={inputMessage}
        onChange={(e) => onInputChange(e.target.value)}
        onKeyPress={onKeyPress}
        placeholder={hasActiveChat ? "输入消息 (Shift+Enter 换行)" : "请先选择一个聊天"}
        disabled={inputDisabled || !!editingMessageTimestamp}
        sx={{
          backgroundColor: '#ffffff',
          borderRadius: '24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          '& .MuiOutlinedInput-root': {
            borderRadius: '24px',
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
        onClick={onSendMessage}
        disabled={inputDisabled || !inputMessage.trim()}
        sx={{
          minWidth: 'auto',
          padding: '0px',
          borderRadius: '50%',
          height: '42px',
          width: '42px',
          background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          '&:hover': {
            background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
          }
        }}
        aria-label="发送消息"
      >
        {isSending ? <CircularProgress size={22} color="inherit" /> : <SendIcon sx={{ fontSize: 20 }}/>}
      </Button>
    </Box>
  );
};

export default MessageInputBar; 