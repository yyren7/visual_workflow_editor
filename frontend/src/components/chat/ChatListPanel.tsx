import React, { useState } from 'react';
import {
  Box, Button, List, ListItem, ListItemButton, ListItemText,
  IconButton, Tooltip, Input, Typography, CircularProgress, Paper
} from '@mui/material';
import {
  AddComment as AddCommentIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Check as CheckIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { Chat } from '../../types'; // Assuming Chat type is in ../../types
import { DisplayMessage } from './chatTypes';

interface ChatListPanelProps {
  chatList: Chat[];
  activeChatId: string | null;
  isLoadingList: boolean;
  isCreatingChat: boolean;
  isDeletingChatId: string | null;
  isRenamingChatId: string | null;
  error: string | null;
  flowId: string | undefined;
  onSelectChat: (chatId: string) => void;
  onStartRename: (chatId: string, currentName: string) => void;
  onCancelRename: () => void;
  onConfirmRename: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
  renameInputValue: string;
  onRenameInputChange: (value: string) => void;
}

const ChatListPanel: React.FC<ChatListPanelProps> = ({
  chatList,
  activeChatId,
  isLoadingList,
  isCreatingChat,
  isDeletingChatId,
  isRenamingChatId,
  error,
  flowId,
  onSelectChat,
  onStartRename,
  onCancelRename,
  onConfirmRename,
  onDeleteChat,
  renameInputValue,
  onRenameInputChange,
}) => {
  return (
    <Paper elevation={2} sx={{ width: '250px', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
      <List sx={{ flexGrow: 1, overflowY: 'auto', p: 0, borderTop: '1px solid', borderColor: 'divider' }}>
        {isLoadingList && !chatList.length && (
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
                <IconButton edge="end" aria-label="确认重命名" size="small" onClick={() => onConfirmRename(chat.id)}>
                  <CheckIcon fontSize="small" />
                </IconButton>
                <IconButton edge="end" aria-label="取消重命名" size="small" onClick={onCancelRename}>
                  <CloseIcon fontSize="small" />
                </IconButton>
              </>
            ) : (
              <>
                <Tooltip title="重命名">
                  <IconButton edge="end" aria-label="重命名" size="small" onClick={(e) => { e.stopPropagation(); onStartRename(chat.id, chat.name); }}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="删除">
                  <span>
                    <IconButton
                      edge="end"
                      aria-label="删除"
                      size="small"
                      disabled={isDeletingChatId === chat.id}
                      onClick={(e) => { e.stopPropagation(); onDeleteChat(chat.id); }}
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
                onChange={(e) => onRenameInputChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') onConfirmRename(chat.id); else if (e.key === 'Escape') onCancelRename(); }}
                autoFocus
                fullWidth
                disableUnderline
                sx={{ px: 2, py: 1 }}
              />
            ) : (
              <ListItemButton onClick={() => onSelectChat(chat.id)} dense>
                <ListItemText primary={chat.name} primaryTypographyProps={{ noWrap: true, title: chat.name }} />
              </ListItemButton>
            )}
          </ListItem>
        ))}
      </List>
      {error && <Typography color="error" variant="caption" sx={{ p: 1 }}>{error}</Typography>}
    </Paper>
  );
};

export default ChatListPanel; 