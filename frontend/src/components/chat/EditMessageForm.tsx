import React from 'react';
import {
  Box, TextField, Button, CircularProgress
} from '@mui/material';

interface EditMessageFormProps {
  editingMessageContent: string;
  isSending: boolean;
  onContentChange: (content: string) => void;
  onConfirmEdit: () => void;
  onCancelEdit: () => void;
}

const EditMessageForm: React.FC<EditMessageFormProps> = ({
  editingMessageContent,
  isSending,
  onContentChange,
  onConfirmEdit,
  onCancelEdit,
}) => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, width: '100%' }}>
      <TextField
        fullWidth
        multiline
        value={editingMessageContent}
        onChange={(e) => onContentChange(e.target.value)}
        autoFocus
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onConfirmEdit();
          }
          if (e.key === 'Escape') {
            onCancelEdit();
          }
        }}
        sx={{ 
          backgroundColor: 'white', 
          borderRadius: '4px',
          '.MuiInputBase-input': {
            color: 'black',
          }
        }}
      />
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 1 }}>
        <Button size="small" variant="outlined" onClick={onCancelEdit} sx={{color: 'primary.contrastText', borderColor: 'primary.contrastText'}}>取消</Button>
        <Button size="small" variant="contained" onClick={onConfirmEdit} disabled={isSending} color="secondary">
          {isSending ? <CircularProgress size={20}/> : "保存"}
        </Button>
      </Box>
    </Box>
  );
};

export default EditMessageForm; 