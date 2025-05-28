import React, { useRef, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip,
  CircularProgress,
  Menu,
  MenuItem,
  Input,
  ListItemIcon
} from '@mui/material';
import ChatInterface from '../ChatInterface';
import { useTranslation } from 'react-i18next';
import ChatIcon from '@mui/icons-material/Chat';
import CloseIcon from '@mui/icons-material/Close';
import AddCommentIcon from '@mui/icons-material/AddComment';
import DownloadIcon from '@mui/icons-material/Download';
import HistoryIcon from '@mui/icons-material/History';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckIcon from '@mui/icons-material/Check';
import { ChatInterfaceHandle, ChatInteractionState } from '../chat/chatTypes';
import { Chat } from '../../types';

interface ChatPanelProps {
  flowId: string;
  isOpen: boolean;
  onClose: () => void;
  onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
}

const MIN_PANEL_WIDTH = 300;
const DEFAULT_PANEL_WIDTH = 500;

const ChatPanel: React.FC<ChatPanelProps> = ({
  flowId,
  isOpen,
  onClose,
  onNodeSelect
}) => {
  const { t } = useTranslation();
  const [activeChatName, setActiveChatName] = React.useState<string | null>(null);
  const chatInterfaceRef = useRef<ChatInterfaceHandle>(null);
  const [interactionState, setInteractionState] = useState<ChatInteractionState>({
    isCreatingChat: false,
    canDownload: false,
  });
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameInputValue, setRenameInputValue] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<Chat[]>([]);
  const [panelWidth, setPanelWidth] = useState<number>(DEFAULT_PANEL_WIDTH);
  const isResizing = useRef<boolean>(false);
  const initialMouseX = useRef<number>(0);
  const initialWidth = useRef<number>(0);

  const handleActiveChatChange = (name: string | null) => {
    setActiveChatName(name);
  };

  const handleChatInteractionStateChange = (newState: ChatInteractionState) => {
    setInteractionState(newState);
  };

  const handleCreateNewChat = () => {
    chatInterfaceRef.current?.createNewChat();
  };

  const handleDownloadChat = () => {
    chatInterfaceRef.current?.downloadActiveChat();
  };

  const handleHistoryMenuOpen = async (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
    if (chatInterfaceRef.current && chatInterfaceRef.current.getChatList) {
        const history = await chatInterfaceRef.current.getChatList();
        setChatHistory(history || []);
    } else {
        console.warn("getChatList method not available on chatInterfaceRef. Using placeholder data.");
        setChatHistory([
            { id: '1', name: 'Placeholder Chat 1', chat_data: { messages: [] }, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), flow_id: flowId, user_id: 'placeholder-user' }, 
            { id: '2', name: 'Placeholder Chat 2', chat_data: { messages: [] }, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), flow_id: flowId, user_id: 'placeholder-user' }, 
        ]);
    }
  };

  const handleHistoryMenuClose = () => {
    setAnchorEl(null);
    setRenamingChatId(null);
    setRenameInputValue('');
  };

  const handleStartRename = (chatId: string, currentName: string) => {
    setRenamingChatId(chatId);
    setRenameInputValue(currentName);
  };

  const handleCancelRename = () => {
    setRenamingChatId(null);
    setRenameInputValue('');
  };

  const handleConfirmRename = async () => {
    if (renamingChatId && renameInputValue.trim() !== '') {
      if (chatInterfaceRef.current && chatInterfaceRef.current.renameChat) {
        await chatInterfaceRef.current.renameChat(renamingChatId, renameInputValue.trim());
        if (chatInterfaceRef.current.getChatList) {
            const history = await chatInterfaceRef.current.getChatList();
            setChatHistory(history || []);
        }
      } else {
          console.warn("renameChat method not available on chatInterfaceRef");
      }
      setRenamingChatId(null);
      setRenameInputValue('');
    }
  };

  const handleDeleteChat = async (chatId: string) => {
    if (chatInterfaceRef.current && chatInterfaceRef.current.deleteChat) {
        await chatInterfaceRef.current.deleteChat(chatId);
        if (chatInterfaceRef.current.getChatList) {
            const history = await chatInterfaceRef.current.getChatList();
            setChatHistory(history || []);
        }
    } else {
        console.warn("deleteChat method not available on chatInterfaceRef");
    }
  };

  const handleMouseDownResize = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    isResizing.current = true;
    initialMouseX.current = e.clientX;
    initialWidth.current = panelWidth;
    document.addEventListener('mousemove', handleMouseMoveResize);
    document.addEventListener('mouseup', handleMouseUpResize);
  };

  const handleMouseMoveResize = (e: MouseEvent) => {
    if (!isResizing.current) return;
    const deltaX = e.clientX - initialMouseX.current;
    let newWidth = initialWidth.current - deltaX; 
    if (newWidth < MIN_PANEL_WIDTH) {
      newWidth = MIN_PANEL_WIDTH;
    }
    setPanelWidth(newWidth);
  };

  const handleMouseUpResize = () => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMoveResize);
    document.removeEventListener('mouseup', handleMouseUpResize);
  };

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: `${panelWidth}px`,
        height: '100%',
        zIndex: 5,
        bgcolor: '#282c34',
        color: 'white',
        display: isOpen ? 'flex' : 'none',
        flexDirection: 'column',
        borderLeft: '1px solid #333',
        boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
      }}
    >
      <Box
        onMouseDown={handleMouseDownResize}
        sx={{
          width: '8px',
          height: '100%',
          position: 'absolute',
          left: 0,
          top: 0,
          cursor: 'ew-resize',
          backgroundColor: 'transparent',
          zIndex: 10,
        }}
      />
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          p: 1,
          borderBottom: '1px solid #444',
          flexShrink: 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <ChatIcon fontSize="small" />
          <Typography variant="subtitle2" sx={{ flexGrow: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={activeChatName || t('flowEditor.chatAssistant')}>
            {activeChatName || t('flowEditor.chatAssistant')}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Tooltip title={t('chatInterface.createNewChat')}>
            <span>
              <IconButton
                size="small"
                color="inherit"
                onClick={handleCreateNewChat}
                disabled={!flowId || interactionState.isCreatingChat}
              >
                {interactionState.isCreatingChat ? <CircularProgress size={16} color="inherit" /> : <AddCommentIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={t('chatInterface.history')}>
            <span>
              <IconButton
                size="small"
                color="inherit"
                onClick={handleHistoryMenuOpen}
              >
                <HistoryIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleHistoryMenuClose}
            PaperProps={{ style: { maxHeight: 300, width: '350px', overflowY: 'auto' } }}
          >
            {chatHistory.length === 0 && (
              <MenuItem disabled>
                <Typography variant="body2" color="textSecondary" sx={{ textAlign: 'center', width: '100%' }}>
                  {t('chatHistory.noHistory', 'No chat history')}
                </Typography>
              </MenuItem>
            )}
            {chatHistory.map((chat) => (
              <MenuItem
                key={chat.id}
                onClick={() => {
                  if (renamingChatId !== chat.id) {
                    if (chatInterfaceRef.current && chatInterfaceRef.current.selectChat) {
                        chatInterfaceRef.current.selectChat(chat.id);
                    } else {
                        console.warn("selectChat method not available on chatInterfaceRef");
                    }
                    handleHistoryMenuClose();
                  }
                }}
                sx={{ justifyContent: 'space-between' }}
              >
                {renamingChatId === chat.id ? (
                  <>
                    <Input
                      value={renameInputValue}
                      onChange={(e) => setRenameInputValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleConfirmRename();
                          e.stopPropagation();
                        } else if (e.key === 'Escape') {
                          handleCancelRename();
                          e.stopPropagation();
                        }
                      }}
                      onClick={(e) => e.stopPropagation()}
                      autoFocus
                      fullWidth
                      disableUnderline
                      sx={{ flexGrow: 1, mr: 1 }}
                    />
                    <IconButton size="small" onClick={(e) => { handleConfirmRename(); e.stopPropagation();}}>
                      <CheckIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={(e) => { handleCancelRename(); e.stopPropagation();}}>
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </>
                ) : (
                  <>
                    <Typography variant="body2" sx={{ flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={chat.name}>
                      {chat.name}
                    </Typography>
                    <Tooltip title={t('chatInterface.renameChat', 'Rename Chat')}>
                      <IconButton size="small" onClick={(e) => { handleStartRename(chat.id, chat.name); e.stopPropagation(); }}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('chatInterface.deleteChat', 'Delete Chat')}>
                      <IconButton size="small" onClick={(e) => { handleDeleteChat(chat.id); e.stopPropagation();}}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </>
                )}
              </MenuItem>
            ))}
          </Menu>
          <Tooltip title={t('chatInterface.downloadChat')}>
            <span>
              <IconButton
                size="small"
                color="inherit"
                onClick={handleDownloadChat}
                disabled={!interactionState.canDownload}
              >
                <DownloadIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <IconButton size="small" color="inherit" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      <Box
        sx={{
          flexGrow: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <ChatInterface
          ref={chatInterfaceRef}
          flowId={flowId}
          onNodeSelect={onNodeSelect}
          onActiveChatChange={handleActiveChatChange}
          onChatInteractionStateChange={handleChatInteractionStateChange}
        />
      </Box>
    </Paper>
  );
};

export default ChatPanel; 