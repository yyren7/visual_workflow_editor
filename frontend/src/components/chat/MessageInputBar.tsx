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
    <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1, mt: 'auto', padding: '8px 0' }}>
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
        onClick={onSendMessage}
        disabled={inputDisabled || !inputMessage.trim()}
        sx={{
          minWidth: 'auto', padding: '10px', borderRadius: '50%', height: '48px', width: '48px',
        }}
        aria-label="发送消息"
      >
        {isSending ? <CircularProgress size={24} color="inherit" /> : <SendIcon />}
      </Button>
    </Box>
  );
};

export default MessageInputBar; 