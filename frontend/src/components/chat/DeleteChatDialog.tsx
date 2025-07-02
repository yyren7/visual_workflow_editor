import React from 'react';
import {
  Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle
} from '@mui/material';

interface DeleteChatDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirmDelete: () => void;
}

const DeleteChatDialog: React.FC<DeleteChatDialogProps> = ({
  open,
  onClose,
  onConfirmDelete,
}) => {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      disableEnforceFocus={true}
      disableRestoreFocus={true}
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
        <Button onClick={onClose}>取消</Button>
        <Button onClick={onConfirmDelete} color="error" autoFocus>
          删除
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DeleteChatDialog; 