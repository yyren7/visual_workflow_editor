import React from 'react';
import {
  Box,
  Button,
  TextField,
  IconButton,
  Tooltip,
  Paper,
  Menu,
  MenuItem,
  Divider,
  Typography
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import AddIcon from '@mui/icons-material/Add';
import LanguageSelector from '../LanguageSelector'; // Assuming LanguageSelector is in parent dir
import { TFunction } from 'i18next'; // Import TFunction type

interface FlowToolbarProps {
  flowName: string;
  isAuthenticated: boolean;
  sidebarOpen: boolean; // Needed to decide AddIcon tooltip/state maybe?
  globalVarsOpen: boolean;
  chatOpen: boolean;
  toggleMenuAnchorEl: null | HTMLElement;
  anchorEl: null | HTMLElement;
  onToggleSidebar: () => void;
  onToggleGlobalVarsPanel: () => void;
  onToggleChatPanel: () => void;
  onOpenFlowSelect: () => void;
  onLogout: () => void;
  onToggleMenuOpen: (event: React.MouseEvent<HTMLButtonElement>) => void;
  onToggleMenuClose: () => void;
  onMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
  onMenuClose: () => void;
  t: TFunction; // Pass t function for translations
}

const FlowToolbar: React.FC<FlowToolbarProps> = ({
  flowName,
  isAuthenticated,
  sidebarOpen,
  globalVarsOpen,
  chatOpen,
  toggleMenuAnchorEl,
  anchorEl,
  onToggleSidebar,
  onToggleGlobalVarsPanel,
  onToggleChatPanel,
  onOpenFlowSelect,
  onLogout,
  onToggleMenuOpen,
  onToggleMenuClose,
  onMenuOpen,
  onMenuClose,
  t,
}) => {
  return (
    <Paper elevation={2} sx={{
      p: 0.75,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      borderRadius: 0,
      minHeight: '48px',
      bgcolor: '#1e1e1e',
      borderBottom: '1px solid #333',
      color: 'white',
      flexShrink: 0,
      zIndex: 10
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
        {/* Left Side: Toggle Menu, Add Node, Flow Name */}
        <Tooltip title={t('flowEditor.toggleMenu')}>
          <IconButton
            color="inherit"
            onClick={onToggleMenuOpen}
            size="small"
          >
            <MenuIcon />
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={toggleMenuAnchorEl}
          open={Boolean(toggleMenuAnchorEl)}
          onClose={onToggleMenuClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          PaperProps={{
            sx: {
              bgcolor: '#333', color: 'white',
              '& .MuiMenuItem-root:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' },
              '& .MuiDivider-root': { borderColor: 'rgba(255, 255, 255, 0.12)' },
            },
          }}
        >
          <MenuItem onClick={() => { onToggleGlobalVarsPanel(); onToggleMenuClose(); }}>
            {globalVarsOpen ? t('flowEditor.closeGlobalVars') : t('flowEditor.openGlobalVars')}
          </MenuItem>
          {/* <MenuItem onClick={() => { onToggleChatPanel(); onToggleMenuClose(); }}> */}
          {/* {chatOpen ? t('flowEditor.closeChat') : t('flowEditor.openChat')} */}
          {/* </MenuItem> */}
        </Menu>

        <Tooltip title={t('flowEditor.addNode')}>
          <IconButton
            color="inherit"
            onClick={onToggleSidebar} // Use the passed handler
            size="small"
          // Optionally change appearance based on sidebarOpen if needed
          >
            <AddIcon />
          </IconButton>
        </Tooltip>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TextField
            label={t('flowEditor.flowName')}
            variant="outlined"
            size="small"
            value={flowName}
            InputProps={{ readOnly: true }}
            sx={{
              width: '250px',
              '& .MuiOutlinedInput-root': {
                color: 'white', height: '36px',
                '& fieldset': { borderColor: 'rgba(255, 255, 255, 0.23)' },
                '&:hover fieldset': { borderColor: 'rgba(255, 255, 255, 0.23)' },
              },
              '& .MuiInputLabel-root': {
                color: 'rgba(255, 255, 255, 0.7)', transform: 'translate(14px, 9px) scale(0.75)',
                '&.MuiInputLabel-shrink': { transform: 'translate(14px, -6px) scale(0.75)' }
              },
            }}
          />
        </Box>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexGrow: 1 }}>
        {/* Center Area (Currently Empty) */}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
        {/* Right Side: Language Selector, User Menu */}
        <LanguageSelector />
        {isAuthenticated && (
          <>
            <IconButton color="inherit" onClick={onMenuOpen} size="small">
              <AccountCircleIcon />
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={onMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              PaperProps={{
                sx: {
                  bgcolor: '#333', color: 'white',
                  '& .MuiMenuItem-root:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' },
                  '& .MuiDivider-root': { borderColor: 'rgba(255, 255, 255, 0.12)' },
                },
              }}
            >
              <MenuItem onClick={onOpenFlowSelect}>
                {t('nav.flowSelect', '选择流程图')}
              </MenuItem>
              <Divider />
              <MenuItem onClick={onLogout}>{t('nav.logout')}</MenuItem>
            </Menu>
          </>
        )}
      </Box>
    </Paper>
  );
};

export default FlowToolbar; 